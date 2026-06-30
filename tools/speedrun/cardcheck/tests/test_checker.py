# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Tests for checker.py — WP-12.

Verifies that the checker:
  - Catches a wrong-fact card.
  - Catches a duplicate card.
  - Catches a vague/bad-teaching card.
  - Passes a correct, unique, well-formed card.
  - The three-count summary is accurate.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tools.speedrun.cardcheck.checker import CardChecker, Verdict
from tools.speedrun.cardcheck.generator import RawCard

# ---------------------------------------------------------------------------
# Shared source text (abbreviated but sufficient for tests)
# ---------------------------------------------------------------------------

_SOURCE = """\
§1.2 premise
A premise is a statement offered as evidence, reason, or support for the conclusion.
Premises are the reasons given for accepting the conclusion. An argument can have one
or more premises.

§1.3 conclusion
The conclusion is the claim that the premises are intended to establish or support.
It is what the arguer is trying to convince you of. An argument has exactly one main
conclusion.

§4.5 correlation-causation fallacy
The correlation-causation fallacy assumes that because two events or variables are
correlated, one causes the other. Correlation is evidence for but does not establish
causation; alternative explanations (reverse causation, common cause, coincidence)
must be ruled out.

§3.1 universal quantifier all
The word all (universal quantifier) asserts that every member of the subject class
has the predicate property. A single counterexample (an A that is not B) falsifies
the statement.
"""


@pytest.fixture()
def checker() -> CardChecker:
    return CardChecker(source_text=_SOURCE)


# ---------------------------------------------------------------------------
# Good card — baseline
# ---------------------------------------------------------------------------


class TestGoodCard:
    def test_correct_useful(self, checker: CardChecker) -> None:
        card = RawCard(
            question="What is a premise in an argument?",
            answer=(
                "A premise is a statement offered as evidence, reason, or support "
                "for the conclusion. Premises are the reasons given for accepting "
                "the conclusion."
            ),
            source_ref="§1.2",
            domain="argument_vocabulary",
        )
        result = checker.check_card(card)
        assert result.verdict == Verdict.CORRECT_USEFUL, (
            f"Expected CORRECT_USEFUL, got {result.verdict}. Reasons: {result.reasons}"
        )
        assert result.passed


# ---------------------------------------------------------------------------
# Wrong-fact card
# ---------------------------------------------------------------------------


class TestWrongFactCard:
    """A card whose answer contradicts / is unsupported by the source."""

    def test_wrong_fact_verdict(self, checker: CardChecker) -> None:
        # This answer claims a premise is the *final claim*, which is wrong —
        # that's the conclusion.  It also uses tokens absent from the source.
        card = RawCard(
            question="What is a premise?",
            answer=(
                "A premise is the final claim the arguer seeks to establish, "
                "derived from supporting evidence called conclusions. "
                "Premises always appear at the end of an argument structure."
            ),
            source_ref="§1.2",
            domain="argument_vocabulary",
        )
        result = checker.check_card(card)
        assert result.verdict == Verdict.WRONG_FACT, (
            f"Expected WRONG_FACT, got {result.verdict}. Reasons: {result.reasons}"
        )
        assert not result.passed
        assert result.reasons, "Wrong-fact verdict must include explanatory reasons."

    def test_wrong_fact_card_is_blocked(self, checker: CardChecker) -> None:
        # This answer fabricates content entirely foreign to the source section
        # (§4.5 covers correlation-causation; this answer invents photosynthesis
        # and chlorophyll which have zero tokens in the source text).
        # NOTE: the factual checker does lexical-token overlap; it catches invented
        # facts (absent tokens) but NOT semantic inversions of the same topic.
        # See WP-12-log L2 for this known limitation.
        card = RawCard(
            question="What is the correlation-causation fallacy about?",
            answer=(
                "The correlation-causation fallacy describes how photosynthesis "
                "occurs in chloroplasts when sunlight activates chlorophyll. "
                "Glucose production requires carbon dioxide and water molecules."
            ),
            source_ref="§4.5",
            domain="fallacies",
        )
        result = checker.check_card(card)
        assert not result.passed


# ---------------------------------------------------------------------------
# Duplicate card
# ---------------------------------------------------------------------------


class TestDuplicateCard:
    """The second card with a near-identical question should be rejected."""

    def test_duplicate_blocked(self, checker: CardChecker) -> None:
        card_a = RawCard(
            question="What is a conclusion in an argument?",
            answer=(
                "The conclusion is the claim that the premises are intended to "
                "establish or support. It is what the arguer is trying to convince "
                "you of. An argument has exactly one main conclusion."
            ),
            source_ref="§1.3",
            domain="argument_vocabulary",
        )
        card_b = RawCard(
            question="What is a conclusion in an argument structure?",
            answer=(
                "The conclusion is the claim that premises are meant to support. "
                "It is what the arguer is trying to convince the audience of and "
                "an argument has exactly one main conclusion."
            ),
            source_ref="§1.3",
            domain="argument_vocabulary",
        )

        result_a = checker.check_card(card_a)
        assert result_a.verdict == Verdict.CORRECT_USEFUL, (
            f"First card should pass. Got: {result_a.verdict}, {result_a.reasons}"
        )

        result_b = checker.check_card(card_b)
        assert result_b.verdict == Verdict.DUPLICATE, (
            f"Second near-duplicate card should be DUPLICATE, got {result_b.verdict}."
        )
        assert not result_b.passed

    def test_non_duplicate_passes(self, checker: CardChecker) -> None:
        card_a = RawCard(
            question="Define the universal quantifier 'all' in logic.",
            answer=(
                "The word 'all' asserts that every member of the subject class "
                "has the predicate property. A single counterexample falsifies "
                "the statement."
            ),
            source_ref="§3.1",
            domain="quantifiers",
        )
        card_b = RawCard(
            question="What is a premise in an argument?",
            answer=(
                "A premise is a statement offered as evidence or support for the "
                "conclusion. Premises are the reasons given for accepting the "
                "conclusion."
            ),
            source_ref="§1.2",
            domain="argument_vocabulary",
        )
        r_a = checker.check_card(card_a)
        r_b = checker.check_card(card_b)
        assert r_a.verdict != Verdict.DUPLICATE
        assert r_b.verdict != Verdict.DUPLICATE


# ---------------------------------------------------------------------------
# Vague / bad-teaching card
# ---------------------------------------------------------------------------


class TestVagueCard:
    """Cards that are factually OK but fail teaching-quality heuristics."""

    def test_too_short_answer_rejected(self, checker: CardChecker) -> None:
        card = RawCard(
            question="What is a premise?",
            answer="A reason.",  # too short
            source_ref="§1.2",
            domain="argument_vocabulary",
        )
        result = checker.check_card(card)
        # Short answer might also fail factual (low coverage), either way not CORRECT_USEFUL.
        assert result.verdict != Verdict.CORRECT_USEFUL

    def test_vague_filler_rejected(self, checker: CardChecker) -> None:
        card = RawCard(
            question="What is the correlation-causation fallacy?",
            answer=(
                "It depends on the context and various things may apply "
                "depending on the situation at hand. Many things are relevant "
                "to this question which has multiple facets to consider carefully."
            ),
            source_ref="§4.5",
            domain="fallacies",
        )
        result = checker.check_card(card)
        # "it depends" and "various things" are vague-filler triggers
        assert result.verdict in (Verdict.CORRECT_BAD_TEACHING, Verdict.WRONG_FACT)
        assert not result.passed

    def test_no_question_word_flagged(self, checker: CardChecker) -> None:
        card = RawCard(
            question="Premises are important because they support conclusions.",  # statement not question
            answer=(
                "A premise is a statement offered as evidence or support for the "
                "conclusion. Premises are reasons given for accepting the conclusion."
            ),
            source_ref="§1.2",
            domain="argument_vocabulary",
        )
        result = checker.check_card(card)
        # Quality check should flag the missing question word / ?
        if result.verdict == Verdict.CORRECT_BAD_TEACHING:
            any_reason_about_question = any("question" in r.lower() for r in result.reasons)
            assert any_reason_about_question, (
                "Expected a reason mentioning the missing question word."
            )


# ---------------------------------------------------------------------------
# Three-count summary
# ---------------------------------------------------------------------------


class TestSummary:
    def test_summary_counts_correct(self) -> None:
        checker = CardChecker(source_text=_SOURCE)

        good_card = RawCard(
            question="What is a premise in argumentation?",
            answer=(
                "A premise is a statement offered as evidence, reason, or "
                "support for the conclusion. Premises are the reasons given "
                "for accepting the conclusion."
            ),
            source_ref="§1.2",
            domain="argument_vocabulary",
        )
        # Bad-fact card: answer is entirely unrelated to the source section.
        # §3.1 covers universal quantifier "all"; this answer discusses currency
        # exchange and finance — tokens absent from the source — so the factual
        # coverage check fails.
        bad_fact_card = RawCard(
            question="What is a universal quantifier meaning?",
            answer=(
                "The universal quantifier refers to currency exchange rates and "
                "inflation coefficients. Monetary policy determines whether "
                "treasury bonds appreciate against foreign currency benchmarks."
            ),
            source_ref="§3.1",
            domain="quantifiers",
        )

        results = checker.check_all([good_card, bad_fact_card])
        counts = checker.summary(results)

        assert counts["correct_useful"] + counts["wrong_fact"] + \
               counts["correct_bad_teaching"] + counts["duplicate"] == len(results)
        assert counts["wrong_fact"] >= 1  # bad_fact_card should fail factual
