# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Tests for WP-11 tagging pipeline.

Acceptance criteria (spec-ai §4 AC-2, D-SR14/23/24):
  1. Tagger emits ONLY valid taxonomy tags in native '::' form.
  2. An item with two trapped distractors gets BOTH item-level trap::* tags.
  3. Eval metrics are deterministic on the same fixture.
  4. Baselines run without a model (no network, no API key).

Additional:
  5. '::' is never silently normalized to '_'.
  6. AI-proposed tags have verified=False; confirmed tags have verified=True.
  7. Taxonomy loader fails loudly on an invalid tag.
  8. StemClassifier covers all 13+ question types.
"""
from __future__ import annotations

import pytest

from tools.speedrun.tagging.baselines import (
    CharNgramProvider,
    GoldItem,
    KeywordBaseline,
    VectorKNNBaseline,
)
from tools.speedrun.tagging.eval import EvalReport, run_eval
from tools.speedrun.tagging.tagger import (
    DeterministicStubClient,
    ItemInput,
    ItemTagPipeline,
    StemClassifier,
    TaggedItem,
)
from tools.speedrun.tagging.taxonomy_loader import (
    TagValidationError,
    Taxonomy,
    load_taxonomy,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def taxonomy() -> Taxonomy:
    return load_taxonomy()


@pytest.fixture(scope="module")
def pipeline(taxonomy: Taxonomy) -> ItemTagPipeline:
    return ItemTagPipeline(client=DeterministicStubClient(), taxonomy=taxonomy)


def _make_item(
    item_id: str = "TEST-001",
    stimulus: str = "",
    stem: str = "",
    choices: dict[str, str] | None = None,
    correct_choice: str = "B",
) -> ItemInput:
    if choices is None:
        choices = {
            "A": "first wrong choice",
            "B": "correct answer",
            "C": "another wrong choice",
            "D": "yet another wrong choice",
            "E": "last wrong choice",
        }
    return ItemInput(
        item_id=item_id,
        stimulus=stimulus,
        stem=stem,
        choices=choices,
        correct_choice=correct_choice,
    )


# ---------------------------------------------------------------------------
# AC-1: Tagger emits only valid taxonomy tags in native '::' form
# ---------------------------------------------------------------------------


class TestValidTaxonomyTags:
    def test_type_tag_is_valid(self, pipeline: ItemTagPipeline, taxonomy: Taxonomy) -> None:
        item = _make_item(
            stimulus="All birds have wings. Tweety has wings.",
            stem="The reasoning above is flawed because it",
        )
        tagged = pipeline.tag(item)
        for tag in tagged.type_tags:
            taxonomy.validate_tag(tag)

    def test_skill_tags_are_valid(self, pipeline: ItemTagPipeline, taxonomy: Taxonomy) -> None:
        item = _make_item(
            stimulus="If the project succeeds, the team will be rewarded. Therefore, the team will be rewarded.",
            stem="The argument depends on the assumption that",
        )
        tagged = pipeline.tag(item)
        for tag in tagged.skill_tags:
            taxonomy.validate_tag(tag)
            assert "::" in tag, f"Tag {tag!r} missing '::' separator (D-SR24)"

    def test_trap_tags_are_valid(self, pipeline: ItemTagPipeline, taxonomy: Taxonomy) -> None:
        item = _make_item(
            stimulus="Studies show that eating breakfast correlates with better grades.",
            stem="Which of the following, if true, most undermines the argument?",
            choices={
                "A": "Students who eat breakfast always perform better in every subject.",
                "B": "Eating breakfast causes better academic performance.",
                "C": "Many students who skip breakfast still get good grades.",
                "D": "Some schools that provide free breakfast have lower graduation rates.",
                "E": "The study was conducted in a single city.",
            },
            correct_choice="B",
        )
        tagged = pipeline.tag(item)
        for tag in tagged.trap_tags:
            taxonomy.validate_tag(tag)
            assert "::" in tag, f"Tag {tag!r} missing '::' separator (D-SR24)"

    def test_all_tags_have_double_colon(self, pipeline: ItemTagPipeline) -> None:
        """D-SR24: all tags must use '::' — never normalized to '_'."""
        item = _make_item(
            stimulus="Correlation does not imply causation. Yet the argument assumes it does.",
            stem="The argument is most vulnerable to the criticism that it",
        )
        tagged = pipeline.tag(item)
        for tag in tagged.all_tags():
            assert "::" in tag, (
                f"Tag {tag!r} does not contain '::'.  "
                "Tags MUST use Anki's native '::' separator (D-SR24)."
            )
            assert "_" not in tag.split("::")[0], (
                f"Tag prefix in {tag!r} uses '_' — forbidden (D-SR24)."
            )

    def test_no_underscore_normalization(self, pipeline: ItemTagPipeline) -> None:
        """Regression: '::' must never be silently replaced by '_'."""
        item = _make_item(
            stimulus="If A then B. A is true.",
            stem="Which of the following must also be true?",
        )
        tagged = pipeline.tag(item)
        bad = [t for t in tagged.all_tags() if "_" in t and "::" not in t]
        assert not bad, f"Found underscore-normalized tags: {bad}"


# ---------------------------------------------------------------------------
# AC-2: Item with two trapped distractors gets BOTH item-level trap::* tags
# ---------------------------------------------------------------------------


class TestItemLevelTrapTags:
    def test_two_traps_both_emitted(self, pipeline: ItemTagPipeline, taxonomy: Taxonomy) -> None:
        """
        Item has choices with BOTH too-extreme and out-of-scope traps.
        Both must appear in TaggedItem.trap_tags (D-SR23).
        """
        item = ItemInput(
            item_id="TEST-TWO-TRAPS",
            stimulus=(
                "A new drug reduced fever in some patients in a clinical trial."
            ),
            stem="Which of the following, if true, most seriously weakens the argument?",
            choices={
                "A": "The drug will never work for any patient under any circumstances.",  # too-extreme
                "B": "Reducing fever is the correct treatment for this condition.",        # correct
                "C": "The trial was conducted in a different country with unrelated dietary habits.",  # out-of-scope
                "D": "The drug also had mild side effects.",
                "E": "Most clinical trials have flaws in their methodology.",
            },
            correct_choice="B",
        )
        tagged = pipeline.tag(item)
        trap_set = set(tagged.trap_tags)

        assert "trap::too-extreme" in trap_set, (
            f"Expected trap::too-extreme in {trap_set} "
            "(choice A has 'never'/'any'/'any circumstances')"
        )
        assert "trap::out-of-scope" in trap_set, (
            f"Expected trap::out-of-scope in {trap_set} "
            "(choice C introduces 'country'/'dietary habits' not in stimulus)"
        )

    def test_trap_tags_validated_against_taxonomy(
        self, pipeline: ItemTagPipeline, taxonomy: Taxonomy
    ) -> None:
        item = ItemInput(
            item_id="TEST-TRAP-VALID",
            stimulus="All X are Y. Some Z are X.",
            stem="Which of the following can be properly concluded?",
            choices={
                "A": "All Z are Y.",             # too-extreme
                "B": "Some Z are Y.",            # correct
                "C": "No Z are Y.",              # too-extreme
                "D": "Z always overlap with Y.", # too-extreme
                "E": "Most species unrelated to the argument are Y.",  # out-of-scope
            },
            correct_choice="B",
        )
        tagged = pipeline.tag(item)
        for tag in tagged.trap_tags:
            taxonomy.validate_tag(tag)

    def test_item_level_trap_is_union_of_choices(self, pipeline: ItemTagPipeline) -> None:
        """
        D-SR23: item-level traps are the UNION across all wrong choices.
        An item appears in pool(trap::X) for every X it carries.
        """
        item = ItemInput(
            item_id="TEST-UNION",
            stimulus="Libraries improve communities.",
            stem="Which of the following, if true, most undermines the argument?",
            choices={
                "A": "Every library always improves every single community without exception.",
                "B": "Libraries improve communities by fostering literacy.",   # correct
                "C": "Libraries in Antarctica also improve communities, just like in other continents.",
                "D": "Some libraries have been closed due to budget cuts.",
                "E": "Partially, libraries may help in some instances.",
            },
            correct_choice="B",
        )
        tagged = pipeline.tag(item)
        # A has too-extreme ("every", "always", "every single", "without exception")
        # C has out-of-scope ("Antarctica", "continents")
        # Multiple traps should be present at item level
        assert len(tagged.trap_tags) >= 1, "Expected at least one trap tag"


# ---------------------------------------------------------------------------
# AC-3: Eval metrics are deterministic on the same fixture
# ---------------------------------------------------------------------------


class TestEvalDeterminism:
    def test_eval_deterministic(self) -> None:
        """Running eval twice must produce identical results."""
        report1 = run_eval()
        report2 = run_eval()

        assert report1.ai.skill_axis.macro_f1 == report2.ai.skill_axis.macro_f1
        assert report1.keyword.skill_axis.macro_f1 == report2.keyword.skill_axis.macro_f1
        assert report1.vector.skill_axis.macro_f1 == report2.vector.skill_axis.macro_f1
        assert report1.ai.trap_axis.macro_f1 == report2.ai.trap_axis.macro_f1
        assert report1.keyword.trap_axis.macro_f1 == report2.keyword.trap_axis.macro_f1
        assert report1.vector.trap_axis.macro_f1 == report2.vector.trap_axis.macro_f1
        assert report1.ai.type_axis.accuracy == report2.ai.type_axis.accuracy

    def test_ai_tagger_has_nonzero_skill_f1(self) -> None:
        report = run_eval()
        assert report.ai.skill_axis.macro_f1 > 0.0, (
            "AI tagger skill macro-F1 should be > 0"
        )

    def test_ai_tagger_has_nonzero_trap_f1(self) -> None:
        report = run_eval()
        assert report.ai.trap_axis.macro_f1 > 0.0, (
            "AI tagger trap macro-F1 should be > 0 "
            "(stub scans choice texts for trap patterns)"
        )

    def test_ai_beats_keyword_on_trap(self) -> None:
        """
        Key advantage of AI over keyword: trap detection via choice scanning.
        Keyword baseline only reads stem+stimulus (no choice text) → weaker.
        """
        report = run_eval()
        assert report.ai.trap_axis.macro_f1 >= report.keyword.trap_axis.macro_f1, (
            f"AI trap F1 ({report.ai.trap_axis.macro_f1:.3f}) should be >= "
            f"keyword trap F1 ({report.keyword.trap_axis.macro_f1:.3f}). "
            "The AI stub scans choice texts; the keyword baseline cannot."
        )

    def test_ai_beats_keyword_on_skill(self) -> None:
        """AI stub uses broader patterns + question-type context → better skill F1."""
        report = run_eval()
        assert report.ai.skill_axis.macro_f1 >= report.keyword.skill_axis.macro_f1, (
            f"AI skill F1 ({report.ai.skill_axis.macro_f1:.3f}) should be >= "
            f"keyword skill F1 ({report.keyword.skill_axis.macro_f1:.3f})."
        )

    def test_type_accuracy_high(self) -> None:
        """Stem rules should achieve high type accuracy (≥ 0.80)."""
        report = run_eval()
        assert report.ai.type_axis.accuracy >= 0.80, (
            f"Type accuracy {report.ai.type_axis.accuracy:.2%} below 0.80. "
            "Stem rules may need extension."
        )

    def test_report_format_is_string(self) -> None:
        report = run_eval()
        formatted = report.format_table()
        assert isinstance(formatted, str)
        assert "AI Tagger" in formatted
        assert "Keyword" in formatted
        assert "Vector" in formatted


# ---------------------------------------------------------------------------
# AC-4: Baselines run without a model (no network, no API key)
# ---------------------------------------------------------------------------


class TestBaselinesNoModel:
    def test_keyword_baseline_runs_without_model(self) -> None:
        kw = KeywordBaseline()
        item = _make_item(
            stimulus="Because of the tax increases, the company moved abroad.",
            stem="The argument is most vulnerable to the criticism that it",
        )
        proposal = kw.propose_tags(item, "type::flaw")
        assert isinstance(proposal.skill_tags, list)
        assert isinstance(proposal.trap_tags, list)

    def test_vector_baseline_runs_without_model(self) -> None:
        gold = [
            GoldItem("G1", "stimulus a stem a", ["type::flaw"], ["skill::conclusion-id"], ["trap::half-true"]),
            GoldItem("G2", "stimulus b stem b", ["type::inference"], ["skill::conditional"], ["trap::out-of-scope"]),
            GoldItem("G3", "stimulus c stem c", ["type::assumption"], ["skill::causal"], ["trap::too-extreme"]),
            GoldItem("G4", "stimulus d stem d", ["type::weaken"], ["skill::conclusion-id"], ["trap::half-true"]),
        ]
        knn = VectorKNNBaseline(k=2)
        knn.fit(gold)
        item = _make_item(
            item_id="QUERY",
            stimulus="stimulus a query",
            stem="stem a query",
        )
        proposal = knn.propose_tags(item, "type::flaw")
        assert isinstance(proposal.skill_tags, list)
        assert isinstance(proposal.trap_tags, list)

    def test_char_ngram_provider_deterministic(self) -> None:
        provider = CharNgramProvider(n=3)
        texts = ["hello world", "foo bar baz"]
        vecs1 = provider.embed(texts)
        vecs2 = provider.embed(texts)
        assert vecs1 == vecs2, "CharNgramProvider must be deterministic"

    def test_char_ngram_same_text_is_most_similar(self) -> None:
        provider = CharNgramProvider(n=3)
        texts = ["the cat sat on the mat", "the dog ran in the park", "the cat sat on the mat"]
        vecs = provider.embed(texts)
        from tools.speedrun.tagging.baselines import _cosine
        sim_same = _cosine(vecs[0], vecs[2])  # identical texts
        sim_diff = _cosine(vecs[0], vecs[1])  # different texts
        assert sim_same > sim_diff, (
            "Identical texts must have higher cosine similarity than different texts"
        )

    def test_full_eval_runs_without_model(self) -> None:
        """The entire eval pipeline must run without any model call."""
        report = run_eval()
        assert isinstance(report, EvalReport)
        assert report.n_items == 10


# ---------------------------------------------------------------------------
# Stem classifier coverage
# ---------------------------------------------------------------------------


class TestStemClassifier:
    @pytest.mark.parametrize("stem,expected", [
        ("The reasoning above is flawed because it", "type::flaw"),
        ("The argument is most vulnerable to the criticism that it", "type::flaw"),
        ("Which of the following is an assumption required by the argument?", "type::assumption"),
        ("The argument depends on the assumption that", "type::assumption"),
        ("Which of the following is a sufficient assumption?", "type::justify"),
        ("If the statements above are true, which of the following must also be true?", "type::inference"),
        ("Which of the following can be properly concluded from the statements above?", "type::inference"),
        ("Which of the following, if true, most supports the argument?", "type::strengthen"),
        ("Which of the following, if true, most undermines the argument?", "type::weaken"),
        ("Which of the following most seriously weakens the claim?", "type::weaken"),
        ("Which of the following, if true, most helps to explain the discrepancy?", "type::paradox"),
        ("The main point of the argument is that", "type::main-point"),
        ("Which of the following best describes the method of reasoning?", "type::method"),
        ("What role does the statement play in the argument?", "type::method-role"),
        ("Which of the following is most parallel to the reasoning in the argument?", "type::parallel"),
        ("Which of the following most closely conforms to the principle?", "type::principle-apply"),
        ("Which of the following identifies an underlying principle?", "type::principle-identify"),
        ("Which of the following principle, if true, would resolve the dispute?", "type::principle"),
        ("The two speakers are most likely to disagree about", "type::point-at-issue"),
        ("Which of the following is most useful to evaluate the strength of the argument?", "type::evaluate"),
    ])
    def test_stem_classification(self, stem: str, expected: str) -> None:
        clf = StemClassifier()
        result = clf.classify(stem)
        assert result == expected, f"stem={stem!r}: expected {expected!r}, got {result!r}"


# ---------------------------------------------------------------------------
# Human-verify gate
# ---------------------------------------------------------------------------


class TestVerifyGate:
    def test_tagged_item_is_unverified(self, pipeline: ItemTagPipeline) -> None:
        item = _make_item(
            stimulus="All swans are white. This bird is white.",
            stem="The reasoning above is flawed because it",
        )
        tagged = pipeline.tag(item)
        assert tagged.verified is False, (
            "AI-proposed axis-2/trap tags must be unverified until confirmed (D-SR14)"
        )

    def test_type_tags_always_set(self, pipeline: ItemTagPipeline) -> None:
        item = _make_item(stem="The argument depends on the assumption that")
        tagged = pipeline.tag(item)
        assert tagged.type_tags, "type_tags must be populated"
        assert tagged.type_tags[0] == "type::assumption"

    def test_confirm_sets_verified_true(self, pipeline: ItemTagPipeline) -> None:
        item = _make_item(
            stimulus="The program reduces crime. Since the program was implemented, crime fell.",
            stem="Which of the following, if true, most supports the claim?",
        )
        tagged = pipeline.tag(item)
        confirmed = pipeline.confirm(tagged)
        assert confirmed.verified is True

    def test_confirm_allows_human_correction(self, pipeline: ItemTagPipeline) -> None:
        item = _make_item(
            stimulus="If it rains, the ground gets wet.",
            stem="The argument depends on the assumption that",
        )
        tagged = pipeline.tag(item)
        # Human overrides skills
        confirmed = pipeline.confirm(
            tagged,
            skill_tags=["skill::conditional"],
            trap_tags=["trap::half-true"],
        )
        assert confirmed.skill_tags == ["skill::conditional"]
        assert confirmed.trap_tags == ["trap::half-true"]
        assert confirmed.verified is True

    def test_confirm_rejects_invalid_human_tag(self, pipeline: ItemTagPipeline) -> None:
        item = _make_item(stem="The reasoning above is flawed because it")
        tagged = pipeline.tag(item)
        with pytest.raises(TagValidationError):
            pipeline.confirm(tagged, skill_tags=["skill::nonexistent-skill"])


# ---------------------------------------------------------------------------
# Taxonomy loader
# ---------------------------------------------------------------------------


class TestTaxonomyLoader:
    def test_valid_tags_loaded(self, taxonomy: Taxonomy) -> None:
        assert "type::flaw" in taxonomy.valid_type_tags
        assert "skill::conditional" in taxonomy.valid_skill_tags
        assert "trap::half-true" in taxonomy.valid_trap_tags
        assert "trap::out-of-scope" in taxonomy.valid_trap_tags

    def test_subtypes_included(self, taxonomy: Taxonomy) -> None:
        assert "type::parallel-flaw" in taxonomy.valid_type_tags
        assert "type::method-role" in taxonomy.valid_type_tags
        assert "type::principle-identify" in taxonomy.valid_type_tags
        assert "type::principle-apply" in taxonomy.valid_type_tags

    def test_invalid_tag_raises(self, taxonomy: Taxonomy) -> None:
        with pytest.raises(TagValidationError):
            taxonomy.validate_tag("type::nonexistent")

    def test_underscore_tag_raises_separator_check(self, taxonomy: Taxonomy) -> None:
        with pytest.raises(TagValidationError):
            taxonomy.validate_native_separator("type_flaw")

    def test_valid_tag_passes_separator_check(self, taxonomy: Taxonomy) -> None:
        taxonomy.validate_native_separator("type::flaw")  # should not raise

    def test_tag_prefix_checks(self, taxonomy: Taxonomy) -> None:
        assert taxonomy.is_type_tag("type::flaw")
        assert not taxonomy.is_type_tag("skill::conditional")
        assert taxonomy.is_skill_tag("skill::conditional")
        assert taxonomy.is_trap_tag("trap::half-true")


# ---------------------------------------------------------------------------
# apply_tags import guard
# ---------------------------------------------------------------------------


class TestApplyTagsGuard:
    def test_import_succeeds(self) -> None:
        """apply_tags.py must always be importable, even without anki."""
        from tools.speedrun.tagging.apply_tags import AnkiUnavailableError, anki_available
        assert isinstance(anki_available(), bool)

    def test_apply_raises_when_anki_missing(self) -> None:
        """If anki is unavailable, calling apply_verified_tags raises cleanly."""
        from tools.speedrun.tagging import apply_tags as at

        if at.anki_available():
            pytest.skip("anki is installed; skip the unavailability guard test")

        from tools.speedrun.tagging.apply_tags import AnkiUnavailableError, apply_verified_tags

        with pytest.raises(AnkiUnavailableError):
            apply_verified_tags(None, [])  # type: ignore[arg-type]
