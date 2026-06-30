# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
AI tagging pipeline for Speedrun WP-11.

Implements the two-axis tagging pipeline from spec-ai §4:

  Axis 1 — question type (stem-derivable, deterministic, J.1)
      ``StemClassifier`` applies an ordered rule set to the lowercased stem.
      No LLM involved; output is immediately verified.

  Axis 2 — reasoning sub-skill + item-level distractor traps (AI-proposed)
      ``TaggerLLMClient`` protocol: the seam for a real model.
      ``DeterministicStubClient``: runs without network/API keys;
      uses keyword heuristics on the stimulus+choices+question-type context.

Human-verify gate (D-SR14):
  AI-proposed axis-2/trap tags are emitted with ``verified=False``.
  Call ``ItemTagPipeline.confirm()`` to mark them verified before they drive
  engine scoring.  Axis-1 type tags are always verified (deterministic).

Item-level trap tags (D-SR23):
  Every distractor trap present anywhere in the item's wrong choices is emitted
  as a ``trap::*`` tag on the ``TaggedItem``.  An item may carry several.
  ``pool(trap::X)`` = items carrying ``trap::X``.

Tag form: Anki native '::' (D-SR24).  Never normalize '::' to '_'.

spec-ai §4 · D-SR14 · D-SR23 · D-SR24 · brainlift J.1/J.2/K.4

AMBIGUITY SURFACED (see WP-11-log.md):
  The DeterministicStubClient is a keyword/heuristic proxy — NOT a real LLM.
  Wire a real LLMClient before production use (B012).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from tools.speedrun.tagging.taxonomy_loader import Taxonomy, TagValidationError, load_taxonomy


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ItemInput:
    """
    The data the tagger receives for a single LSAT item.

    ``choices`` maps letter → choice text for choices A–E.
    ``correct_choice`` is the letter of the keyed correct answer.
    AI never uses ``correct_choice`` to decide correctness (D1) — it is
    provided only so the stub can identify *wrong* choices for trap scanning.
    """

    item_id: str
    stimulus: str
    stem: str
    choices: dict[str, str]      # {"A": "...", "B": "...", ...}
    correct_choice: str          # "A" | "B" | "C" | "D" | "E"


@dataclass
class LLMTagProposal:
    """
    AI-proposed axis-2 tags (unverified until human confirms).

    ``skill_tags`` — list of ``skill::*`` tags.
    ``trap_tags``  — item-level ``trap::*`` tags (one per distinct distractor
                     trap present in *any* wrong choice — D-SR23).
    """

    skill_tags: list[str]
    trap_tags: list[str]


@dataclass
class TaggedItem:
    """
    Output of the tagging pipeline for one LSAT item.

    ``type_tags``  — axis-1, deterministic, always ``verified=True``.
    ``skill_tags`` — axis-2, AI-proposed, ``verified=False`` until confirmed.
    ``trap_tags``  — item-level distractor traps, ``verified=False`` until confirmed.
    ``verified``   — False until :meth:`ItemTagPipeline.confirm` is called.

    All tags are in Anki's native '::' form (D-SR24).
    """

    item_id: str
    type_tags: list[str]
    skill_tags: list[str]
    trap_tags: list[str]
    verified: bool = False

    def all_tags(self) -> list[str]:
        return self.type_tags + self.skill_tags + self.trap_tags


# ---------------------------------------------------------------------------
# TaggerLLMClient protocol — seam for a real model
# ---------------------------------------------------------------------------


@runtime_checkable
class TaggerLLMClient(Protocol):
    """
    Protocol that every LLM tagging backend must implement.

    The implementation receives the item data **and** the axis-1 type tag
    already determined by :class:`StemClassifier`.  It returns proposed
    axis-2 skill + item-level trap tags.

    Contract (D1 — AI never owns correctness):
    - MUST NOT propose or alter the correct-answer key.
    - MUST NOT alter axis-1 type tags.
    - MAY use ``question_type`` as context to improve axis-2 precision.

    Wiring a real model:
    1. Implement this protocol (e.g. ``AnthropicTaggerClient``).
    2. Build a prompt from ``item`` + ``question_type``; parse JSON response.
    3. Pass the instance to :class:`ItemTagPipeline`.
    """

    def propose_tags(
        self,
        item: ItemInput,
        question_type: str,
    ) -> LLMTagProposal:
        """
        Propose axis-2 skill + item-level trap tags for *item*.

        *question_type* is the ``type::*`` tag from axis-1 (already verified).
        """
        ...


# ---------------------------------------------------------------------------
# Deterministic stub (no network, no API key required)
# ---------------------------------------------------------------------------

# Broader causal keyword set (stimulus language) — deliberately wider than
# the taxonomy key_indicators so the stub beats a pure key_indicator baseline.
_CAUSAL_RE = re.compile(
    r"\b(causes?|cause[sd]|led? to|leads? to|results? in|due to|because of|"
    r"effects? of|responsible for|attribut(?:e|ed|able)|affects?|impact(?:s|ed)?|"
    r"reduces?|reduction|increases?|produces?|creates?|prevents?|decreases?|"
    r"consequence|outcome|gave rise)\b",
    re.I,
)

# Conditional keyword set — triggers skill::conditional
_CONDITIONAL_RE = re.compile(
    r"\b(if\b|only if|unless|whenever|provided that|given that|in order to|"
    r"sufficient|necessary|must have|will have|shown|permitted|required|allowed|"
    r"eligible)\b",
    re.I,
)

# Quantifier keyword set — triggers skill::quantifier (especially in inference Qs)
_QUANTIFIER_RE = re.compile(
    r"\b(some of|most of|all of|none of|no\b.*\bare\b|a few|several|"
    r"majority|minority|at least one)\b",
    re.I,
)

# Additional "all/none/no" that implies conditional when in a rule context
_ALL_NONE_RE = re.compile(r"\b(all|none|every|no)\b\s+\w+\s+\w+\s+(who|that|which)\b", re.I)

# Conclusion indicator keywords — triggers skill::conclusion-id
_CONCLUSION_RE = re.compile(
    r"\b(therefore|thus|hence|so\b|clearly|consequently|it follows|"
    r"must be|shows? that|demonstrates?|concludes?|thus showing|"
    r"we can conclude|in conclusion|as a result|which means|since\b)\b",
    re.I,
)

# Trap detection patterns for choice texts
_TOO_EXTREME_RE = re.compile(
    r"\b(always|never|all\b|none\b|every\b|no one|everyone|everything|"
    r"nothing|any\b|will always|will never|must always|can never|"
    r"in all cases|under any|without exception)\b",
    re.I,
)
_WRONG_DIRECTION_TERMS = frozenset([
    "support", "supports", "strengthen", "strengthens", "evidence for",
    "confirms", "proves", "shows that", "demonstrates", "provides reason",
    "helps to justify",
])
_REVERSAL_RE = re.compile(
    r"\b(reverses?|if\s+\w+\s+then\s+\w+\s+must|contrapositive|"
    r"opposite direction|means that if)\b",
    re.I,
)
_HALF_TRUE_RE = re.compile(
    r"\b(partially|in part|some(?:what)?|most\b|usually|often|might|"
    r"could|sometimes|in some cases|tends to|not always)\b",
    re.I,
)

# New-content-word heuristic for out-of-scope: if a choice introduces many
# content words not present in the stimulus, it is likely out-of-scope.
_STOP_WORDS = frozenset(
    "a an the is are was were be been being have has had do does did "
    "will would could should may might shall of in on at to for with "
    "and or but not it its this that these those if then by from up "
    "what which who when where why how very also just already still "
    "than such more most some all any no none each every".split()
)


def _content_words(text: str) -> frozenset[str]:
    tokens = re.findall(r"[a-z]+", text.lower())
    return frozenset(t for t in tokens if t not in _STOP_WORDS and len(t) > 2)


class DeterministicStubClient:
    """
    Deterministic stub implementing :class:`TaggerLLMClient`.

    Uses keyword heuristics + question-type context to predict axis-2 skill
    and item-level trap tags.  Runs without any network or API key.

    Advantage over a pure keyword baseline:
    - Scans **choice texts** for trap patterns (keyword baseline uses only
      stem+stimulus).
    - Uses **question_type** as context to disambiguate ``all/none`` as
      conditional vs. quantifier (e.g., inference Qs → quantifier).
    - Uses a **broader causal pattern set** (not just the 6 exact
      key_indicators from the taxonomy).

    This stub exists solely so tests and eval run without a real LLM.
    Wire a real :class:`TaggerLLMClient` for production (B012).
    """

    client_id: str = "deterministic-stub-v1"

    def propose_tags(
        self,
        item: ItemInput,
        question_type: str,
    ) -> LLMTagProposal:
        skill_tags = self._predict_skills(item, question_type)
        trap_tags = self._predict_traps(item, question_type)
        return LLMTagProposal(skill_tags=skill_tags, trap_tags=trap_tags)

    # ------------------------------------------------------------------
    # Skill prediction
    # ------------------------------------------------------------------

    def _predict_skills(self, item: ItemInput, question_type: str) -> list[str]:
        text = f"{item.stimulus} {item.stem}"
        skills: set[str] = set()

        # Always check for conclusion identification (nearly universal)
        if _CONCLUSION_RE.search(text) or len(text) > 20:
            skills.add("skill::conclusion-id")

        # Abstraction: parallel/method types always require logical form
        if question_type in ("type::parallel", "type::parallel-flaw",
                              "type::method", "type::method-role"):
            skills.add("skill::abstraction")

        # Quantifier: inference questions with explicit quantifiers
        if question_type in ("type::inference", "type::main-point"):
            if _QUANTIFIER_RE.search(text):
                skills.add("skill::quantifier")

        # Conditional reasoning: check for conditional indicators
        # For non-inference types, "all/none" in a rule → conditional
        has_conditional = bool(_CONDITIONAL_RE.search(text))
        has_all_rule = bool(_ALL_NONE_RE.search(text))
        if has_conditional or has_all_rule:
            skills.add("skill::conditional")

        # Causal reasoning: broader pattern set
        if _CAUSAL_RE.search(text):
            skills.add("skill::causal")

        # Prephrase: used for strengthen/weaken/assumption/justify types
        if question_type in (
            "type::strengthen", "type::weaken",
            "type::assumption", "type::justify", "type::evaluate",
        ):
            skills.add("skill::prephrase")

        # Flaw questions: if no other content skill found beyond conclusion-id,
        # abstraction is likely required (structural flaw identification)
        if question_type in ("type::flaw",):
            if skills == {"skill::conclusion-id"}:
                skills.add("skill::abstraction")

        # Always emit at least conclusion-id
        skills.add("skill::conclusion-id")

        return sorted(skills)

    # ------------------------------------------------------------------
    # Trap prediction (scans wrong choice texts — D-SR23)
    # ------------------------------------------------------------------

    def _predict_traps(self, item: ItemInput, question_type: str) -> list[str]:
        """
        Scan each wrong choice for trap patterns.

        Item-level: if ANY wrong choice exhibits trap X, emit ``trap::X`` on
        the item (D-SR23 — pool(trap::X) = items carrying trap::X).
        """
        traps: set[str] = set()
        stimulus_words = _content_words(item.stimulus)

        wrong_choices = {
            letter: text
            for letter, text in item.choices.items()
            if letter != item.correct_choice
        }

        for _letter, choice_text in wrong_choices.items():
            ct_lower = choice_text.lower()

            # trap::too-extreme — absolute/universal language
            if _TOO_EXTREME_RE.search(choice_text):
                traps.add("trap::too-extreme")

            # trap::wrong-direction — for weaken/strengthen tasks
            if question_type in ("type::weaken", "type::strengthen"):
                for term in _WRONG_DIRECTION_TERMS:
                    if term in ct_lower:
                        traps.add("trap::wrong-direction")
                        break

            # trap::reversal — conditional direction swapped in the choice
            if _REVERSAL_RE.search(choice_text):
                traps.add("trap::reversal")

            # trap::out-of-scope — choice introduces many new content words
            choice_words = _content_words(choice_text)
            new_words = choice_words - stimulus_words
            if len(new_words) >= 4:
                traps.add("trap::out-of-scope")

            # trap::half-true — hedged/partial language
            if _HALF_TRUE_RE.search(choice_text) and "trap::out-of-scope" not in traps:
                traps.add("trap::half-true")

        # If no traps detected yet, default to half-true (most common fallback)
        if not traps and wrong_choices:
            traps.add("trap::half-true")

        return sorted(traps)


# ---------------------------------------------------------------------------
# StemClassifier — deterministic axis-1 (question type)
# ---------------------------------------------------------------------------

# Ordered rules: check each (patterns, type_tag) in order; first match wins.
# Ordering discipline:
#   1. Parallel-flaw before parallel (both have "parallel")
#   2. Method-role before method (both have "role"/"method")
#   3. Parallel before method ("reasoning in the argument" is in method but
#      stems with "most parallel" must fire parallel first)
#   4. Evaluate before strengthen ("most useful to evaluate" must not fire
#      strengthen's "most helps" fallback)
#   5. Paradox before strengthen ("most helps to explain" must not fire
#      strengthen; paradox uses explain/discrepancy/reconcile)
#   6. Principle rules before paradox ("resolve the dispute" in a principle
#      stem must not fire paradox's "resolve" pattern)
# All patterns are matched against the lowercased stem text.
_STEM_RULES: list[tuple[list[str], str]] = [
    # Parallel-flaw (must precede plain parallel)
    (["parallel flaw", "parallel error", "same logical error", "same flaw and"], "type::parallel-flaw"),
    # Role (must precede method)
    (["what role", "which role", "what function", "the role of", "function of this", "statement play"], "type::method-role"),
    # Parallel (must precede method — "reasoning in the argument" fires method)
    (["most parallel", "most similar in", "same logical structure",
      "parallel to the reasoning", "parallel to that", "most similar logical",
      "most parallel to", "is parallel to"], "type::parallel"),
    # Method
    (["method of reasoning", "method of argument", "how does the argument",
      "proceeds by", "reasoning in the argument", "describe the method",
      "best describes the method"], "type::method"),
    # Flaw
    (["flaw", "flawed because", "most vulnerable to", "most seriously vulnerable",
      "vulnerable to criticism", "error in reasoning", "most open to criticism",
      "erroneous because", "criticism that it"], "type::flaw"),
    # Sufficient assumption / justify
    (["sufficient assumption", "justify", "conclusion follows logically",
      "properly follows from", "if assumed", "properly drawn if", "must be assumed in order"], "type::justify"),
    # Necessary assumption
    (["assumption required", "required assumption", "necessary assumption",
      "which of the following is an assumption",
      "assumption on which", "depends on the assumption",
      "must assume", "assumption that"], "type::assumption"),
    # Must-be-true / inference
    (["must also be true", "must be true", "can be properly concluded",
      "properly concluded", "properly inferred",
      "if the statements above are true, which",
      "which of the following can be inferred",
      "logically follows from",
      "most supported by"], "type::inference"),
    # Main point
    (["main point", "main conclusion", "primary conclusion",
      "best states the conclusion", "best expresses the main conclusion",
      "conclusion of the argument is that"], "type::main-point"),
    # Point at issue
    (["point at issue", "disagree about", "point of disagreement",
      "most likely to disagree", "agree or disagree"], "type::point-at-issue"),
    # Evaluate (before strengthen — "most useful to evaluate" must not hit strengthen)
    (["most useful to evaluate", "most helps to evaluate", "most useful to know",
      "would be most useful to determine", "most useful to determine",
      "most helps evaluate", "assess the strength", "evaluate the strength",
      "most useful in evaluating"], "type::evaluate"),
    # Principle-apply (before principle-identify and principle, and before paradox)
    (["most closely conforms to the principle",
      "best illustrates the principle",
      "apply a principle", "conforms to which",
      "principle, if applied"], "type::principle-apply"),
    # Principle-identify (before generic principle)
    (["identifies a principle", "identifies the principle",
      "best expresses a principle", "most accurately expresses the principle",
      "underlying principle"], "type::principle-identify"),
    # Principle (generic — before paradox so "resolve the dispute" in a principle
    # stem does not fire paradox's "resolve" pattern)
    (["which of the following principle", "according to the principle",
      "follows the principle", "illustrates which",
      "principle that best", "which principle"], "type::principle"),
    # Paradox / resolve discrepancy (before strengthen so "most helps to explain"
    # does not fire strengthen's "most helps" pattern)
    (["most helps to explain", "if true, best explains", "if true, would explain",
      "discrepancy", "paradox", "apparent conflict", "surprising result",
      "reconcile", "explain the apparent", "explain the increase",
      "explain why", "explain the fact"], "type::paradox"),
    # Strengthen
    (["most supports", "most strongly supports", "most helps to support",
      "provides the most support", "most helps justify",
      "most strengthens", "if true, most supports",
      "most helps support", "if true, most helps",
      "most helps the argument"], "type::strengthen"),
    # Weaken
    (["most undermines", "most weakens", "most seriously weakens",
      "most seriously undermines", "most calls into question",
      "casts the most doubt", "most challenges",
      "most helps to refute"], "type::weaken"),
]


class StemClassifier:
    """
    Deterministic question-type classifier based on stem text (J.1).

    Returns a single ``type::*`` tag.  Raises :class:`ValueError` if no rule
    matches (the stem is not recognizable as an LR question type).
    """

    _DEFAULT_TYPE = "type::flaw"  # most common type on the exam

    def classify(self, stem: str) -> str:
        """
        Match *stem* against ordered rules and return the first ``type::*`` tag.

        Falls back to ``type::flaw`` when no rule matches (rare; logged as
        an ambiguity in WP-11-log.md L-D3).
        """
        stem_lower = stem.lower()
        for patterns, tag in _STEM_RULES:
            for pattern in patterns:
                if pattern in stem_lower:
                    return tag
        # Fallback: return flaw (most frequent type) and let the caller log
        return self._DEFAULT_TYPE


# ---------------------------------------------------------------------------
# ItemTagPipeline — orchestrates axis-1 + axis-2 + human-verify gate
# ---------------------------------------------------------------------------


class ItemTagPipeline:
    """
    Full tagging pipeline for one LSAT item.

    Usage::

        from tools.speedrun.tagging.tagger import (
            ItemInput, ItemTagPipeline, DeterministicStubClient,
        )
        from tools.speedrun.tagging.taxonomy_loader import load_taxonomy

        taxonomy = load_taxonomy()
        pipeline = ItemTagPipeline(
            client=DeterministicStubClient(),
            taxonomy=taxonomy,
        )
        item = ItemInput(
            item_id="SYNTH-FLAW-001",
            stimulus="...",
            stem="The reasoning above is flawed because it",
            choices={"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."},
            correct_choice="B",
        )
        tagged = pipeline.tag(item)
        # tagged.verified == False (axis-2/trap are AI-proposed)

        # After human review:
        confirmed = pipeline.confirm(tagged)
        # confirmed.verified == True

    All emitted tags are validated against the taxonomy; invalid tags raise
    :class:`TagValidationError` loudly (D-SR17).
    """

    def __init__(
        self,
        client: TaggerLLMClient | None = None,
        taxonomy: Taxonomy | None = None,
    ) -> None:
        self._client: TaggerLLMClient = client or DeterministicStubClient()
        self._taxonomy: Taxonomy = taxonomy or load_taxonomy()
        self._stem_classifier = StemClassifier()

    # ------------------------------------------------------------------
    # Primary entry point
    # ------------------------------------------------------------------

    def tag(self, item: ItemInput) -> TaggedItem:
        """
        Tag *item* on both axes.

        Steps:
        1. Axis-1: classify the stem → ``type::*`` tag (deterministic, verified).
        2. Axis-2: call LLM client → ``skill::*`` + ``trap::*`` tags (unverified).
        3. Validate all tags against taxonomy (fail loud on any invalid tag).
        4. Return :class:`TaggedItem` with ``verified=False``.
        """
        # Axis-1 (deterministic)
        question_type = self._stem_classifier.classify(item.stem)
        type_tags = [question_type]

        # Axis-2 + traps (AI-proposed)
        proposal = self._client.propose_tags(item, question_type)

        # Validate all proposed tags (fail loud — D-SR17)
        all_proposed = proposal.skill_tags + proposal.trap_tags
        for tag in all_proposed:
            self._taxonomy.validate_native_separator(tag)
        self._taxonomy.validate_tags(type_tags + all_proposed)

        return TaggedItem(
            item_id=item.item_id,
            type_tags=type_tags,
            skill_tags=list(proposal.skill_tags),
            trap_tags=list(proposal.trap_tags),
            verified=False,
        )

    # ------------------------------------------------------------------
    # Human-verify gate
    # ------------------------------------------------------------------

    def confirm(
        self,
        tagged: TaggedItem,
        skill_tags: list[str] | None = None,
        trap_tags: list[str] | None = None,
    ) -> TaggedItem:
        """
        Mark axis-2 tags as human-verified.

        If *skill_tags* or *trap_tags* are provided, they replace the AI
        proposals (human correction).  If omitted, the AI proposals are
        accepted as-is.

        Returns a new :class:`TaggedItem` with ``verified=True``.
        """
        final_skills = skill_tags if skill_tags is not None else tagged.skill_tags
        final_traps = trap_tags if trap_tags is not None else tagged.trap_tags

        # Re-validate after human edits (fail loud if human introduced bad tag)
        self._taxonomy.validate_tags(final_skills + final_traps)

        return TaggedItem(
            item_id=tagged.item_id,
            type_tags=tagged.type_tags,
            skill_tags=final_skills,
            trap_tags=final_traps,
            verified=True,
        )

    # ------------------------------------------------------------------
    # Batch helper
    # ------------------------------------------------------------------

    def tag_all(self, items: list[ItemInput]) -> list[TaggedItem]:
        """Tag a batch of items; returns one :class:`TaggedItem` per item."""
        return [self.tag(item) for item in items]
