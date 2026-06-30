# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Generate-then-verify card checker for Speedrun WP-12.

Applies three independent checks to each generated RawCard:
  (a) FactualChecker — correctness vs. the cited source text.
  (b) DuplicationChecker — not a near-duplicate of existing accepted cards.
  (c) QualityChecker — teaching-quality heuristics (reject vague/trivial).

Verification is grounded in the cited source, NOT in model self-judgment (D1).
AI never owns correctness; the checker is purely deterministic.

spec-ai §5 · D-SR15 · brainlift F.5/F.6
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from tools.speedrun.cardcheck.generator import RawCard

# ---------------------------------------------------------------------------
# Verdict enumeration
# ---------------------------------------------------------------------------


class Verdict(str, Enum):
    CORRECT_USEFUL = "correct_useful"
    WRONG_FACT = "wrong_fact"
    CORRECT_BAD_TEACHING = "correct_bad_teaching"
    DUPLICATE = "duplicate"


# ---------------------------------------------------------------------------
# Check result
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    """Result of checking one card."""

    card: RawCard
    verdict: Verdict
    reasons: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.verdict == Verdict.CORRECT_USEFUL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> set[str]:
    """Lowercase word-tokens for overlap computation."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _token_overlap(a: str, b: str) -> float:
    """Jaccard similarity between two token bags."""
    ta = _tokenize(a)
    tb = _tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _find_source_section(source_text: str, ref: str) -> str:
    """
    Extract the text of a named section from *source_text*.

    Supports refs of the form ``§N.M`` or ``§N``.  Returns everything from
    the matching heading line to the next heading line at the same or higher
    level, or to end-of-file.
    """
    if not ref:
        return source_text  # fall back to full text

    # Escape the ref for regex (§ is not a regex special char, but dot is).
    escaped = re.escape(ref)
    pattern = re.compile(rf"^{escaped}\b.*$", re.MULTILINE)
    m = pattern.search(source_text)
    if not m:
        return source_text

    start = m.start()
    # Next section heading at the same or higher level.
    next_heading = re.compile(r"^§[\d]", re.MULTILINE)
    nxt = next_heading.search(source_text, m.end())
    end = nxt.start() if nxt else len(source_text)
    return source_text[start:end]


# ---------------------------------------------------------------------------
# (a) FactualChecker
# ---------------------------------------------------------------------------


class FactualChecker:
    """
    Verifies that the card's answer is factually consistent with the cited
    source text.

    Strategy: for each key term in the gold-set answer or in the card answer,
    check that the source section contains supporting text.  This is a
    *necessary* condition — if the source does not contain the answer
    substance, the card fails.

    Limitations (surfaced in WP-12-log L2): this is a lexical containment
    check, not a semantic one.  A real LLM-checked factual verification would
    be stronger but would reintroduce model self-judgment (banned by D1).
    The chosen method is the defensible minimum for D1 compliance.
    """

    # Minimum fraction of key token pairs from the answer that must appear
    # in the source section.
    _COVERAGE_THRESHOLD: float = 0.30

    def __init__(self, source_text: str) -> None:
        self._source_text = source_text

    def check(self, card: RawCard) -> tuple[bool, list[str]]:
        """
        Returns (ok, reasons).

        ok=True means the answer is supported by the source.
        """
        section = _find_source_section(self._source_text, card.source_ref)
        section_tokens = _tokenize(section)
        answer_tokens = _tokenize(card.answer)

        # Stop-words that carry no factual signal.
        _STOP = frozenset(
            "a an the is are was were be been being have has had do does did "
            "will would could should may might shall of in on at to for with "
            "and or but not it its this that these those if then by from up "
            "what which who when where why how".split()
        )
        meaningful_answer_tokens = answer_tokens - _STOP

        if not meaningful_answer_tokens:
            return False, ["Answer has no meaningful content tokens."]

        overlap_count = sum(1 for t in meaningful_answer_tokens if t in section_tokens)
        coverage = overlap_count / len(meaningful_answer_tokens)

        if coverage < self._COVERAGE_THRESHOLD:
            return False, [
                f"Factual check failed: only {coverage:.0%} of answer tokens found "
                f"in source section '{card.source_ref}' "
                f"(threshold {self._COVERAGE_THRESHOLD:.0%})."
            ]
        return True, []


# ---------------------------------------------------------------------------
# (b) DuplicationChecker
# ---------------------------------------------------------------------------


class DuplicationChecker:
    """
    Rejects a card if its question is a near-duplicate of an already-accepted
    card.  Uses Jaccard similarity on question tokens.
    """

    _DUPLICATE_THRESHOLD: float = 0.65

    def __init__(self) -> None:
        self._accepted_questions: list[str] = []

    def check(self, card: RawCard) -> tuple[bool, list[str]]:
        """
        Returns (ok, reasons).  ok=False if the question is a near-duplicate.
        """
        for prev in self._accepted_questions:
            sim = _token_overlap(card.question, prev)
            if sim >= self._DUPLICATE_THRESHOLD:
                return False, [
                    f"Duplicate: question Jaccard similarity {sim:.2f} ≥ "
                    f"{self._DUPLICATE_THRESHOLD} vs existing card: "
                    f"'{prev[:80]}...'"
                ]
        return True, []

    def accept(self, card: RawCard) -> None:
        """Mark *card* as accepted so subsequent cards are checked against it."""
        self._accepted_questions.append(card.question)

    def reset(self) -> None:
        self._accepted_questions.clear()


# ---------------------------------------------------------------------------
# (c) QualityChecker
# ---------------------------------------------------------------------------


class QualityChecker:
    """
    Heuristic teaching-quality filter.  Rejects cards that are:

    - Too short (question or answer below minimum character length).
    - Too vague (answer is a one-word stub or uses only generic filler).
    - Trivially circular (question word is the whole answer).
    - Question is not a question (missing question word or "?").
    """

    _MIN_QUESTION_LEN: int = 15
    _MIN_ANSWER_LEN: int = 30
    _MAX_ANSWER_LEN: int = 2_000

    _VAGUE_FILLERS: frozenset[str] = frozenset(
        [
            "it depends",
            "various things",
            "many things",
            "see above",
            "see below",
            "n/a",
            "tbd",
            "todo",
            "placeholder",
            "unknown",
        ]
    )

    _QUESTION_WORDS: frozenset[str] = frozenset(
        ["what", "which", "how", "why", "when", "where", "who", "name", "define", "explain"]
    )

    def check(self, card: RawCard) -> tuple[bool, list[str]]:
        reasons: list[str] = []

        q = card.question.strip()
        a = card.answer.strip()

        # Length checks.
        if len(q) < self._MIN_QUESTION_LEN:
            reasons.append(f"Question too short ({len(q)} chars < {self._MIN_QUESTION_LEN}).")
        if len(a) < self._MIN_ANSWER_LEN:
            reasons.append(f"Answer too short ({len(a)} chars < {self._MIN_ANSWER_LEN}).")
        if len(a) > self._MAX_ANSWER_LEN:
            reasons.append(f"Answer too long ({len(a)} chars > {self._MAX_ANSWER_LEN}).")

        # Vague filler check.
        a_lower = a.lower()
        for filler in self._VAGUE_FILLERS:
            if filler in a_lower:
                reasons.append(f"Answer contains vague filler: '{filler}'.")

        # Question word check — must begin with or contain a question word.
        q_lower = q.lower()
        has_question_word = any(q_lower.startswith(w) or f" {w} " in q_lower for w in self._QUESTION_WORDS)
        if not has_question_word and "?" not in q:
            reasons.append("Question lacks a question word or '?'.")

        # Trivial circularity check: answer is just the question restated.
        q_tokens = _tokenize(q)
        a_tokens = _tokenize(a)
        if a_tokens and q_tokens:
            answer_only = a_tokens - q_tokens
            if len(answer_only) < 3:
                reasons.append("Answer adds fewer than 3 new tokens beyond the question (trivially circular).")

        return (len(reasons) == 0), reasons


# ---------------------------------------------------------------------------
# CardChecker — orchestrates all three checks
# ---------------------------------------------------------------------------


class CardChecker:
    """
    Orchestrates factual, duplication, and quality checks for a stream of
    generated cards.  Returns one :class:`CheckResult` per card and
    maintains running tallies of the three counts required by spec-ai §5.

    Usage::

        checker = CardChecker(source_text=source)
        results = checker.check_all(cards)
        print(checker.summary())
    """

    def __init__(self, source_text: str) -> None:
        self._factual = FactualChecker(source_text)
        self._dedup = DuplicationChecker()
        self._quality = QualityChecker()

    def check_card(self, card: RawCard) -> CheckResult:
        """
        Check a single card.  Returns a :class:`CheckResult`.

        Order of checks (fail-fast on worst first):
        1. Factual correctness (wrong-fact = worst outcome).
        2. Duplication (close-second; a dup is not a "wrong" card but is useless).
        3. Teaching quality.
        """
        # (a) Factual
        fact_ok, fact_reasons = self._factual.check(card)
        if not fact_ok:
            return CheckResult(card=card, verdict=Verdict.WRONG_FACT, reasons=fact_reasons)

        # (b) Duplication
        dup_ok, dup_reasons = self._dedup.check(card)
        if not dup_ok:
            return CheckResult(card=card, verdict=Verdict.DUPLICATE, reasons=dup_reasons)

        # (c) Quality
        qual_ok, qual_reasons = self._quality.check(card)
        if not qual_ok:
            return CheckResult(
                card=card,
                verdict=Verdict.CORRECT_BAD_TEACHING,
                reasons=qual_reasons,
            )

        # All checks passed — accept and register for future dedup.
        self._dedup.accept(card)
        return CheckResult(card=card, verdict=Verdict.CORRECT_USEFUL, reasons=[])

    def check_all(self, cards: list[RawCard]) -> list[CheckResult]:
        """Check a batch of cards and return one result per card."""
        return [self.check_card(c) for c in cards]

    def summary(self, results: list[CheckResult]) -> dict[str, int]:
        """
        Return the three counts required by spec-ai §5:
          correct_useful / wrong_fact / correct_bad_teaching
        Plus ``duplicate`` as an informational fourth count.
        """
        counts: dict[str, int] = {
            "correct_useful": 0,
            "wrong_fact": 0,
            "correct_bad_teaching": 0,
            "duplicate": 0,
        }
        for r in results:
            if r.verdict == Verdict.CORRECT_USEFUL:
                counts["correct_useful"] += 1
            elif r.verdict == Verdict.WRONG_FACT:
                counts["wrong_fact"] += 1
            elif r.verdict == Verdict.CORRECT_BAD_TEACHING:
                counts["correct_bad_teaching"] += 1
            elif r.verdict == Verdict.DUPLICATE:
                counts["duplicate"] += 1
        return counts
