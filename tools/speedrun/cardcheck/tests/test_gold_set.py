# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Tests for gold_set.json integrity — WP-12.

Verifies:
  - Exactly 50 items.
  - Each item is well-formed (required fields, non-empty strings).
  - IDs are unique and follow the GS-NNN scheme.
  - source_ref fields reference valid sections from the source text.
  - No LSAT-item content (questions must not contain stimulus/answer-choice patterns).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_BASE = Path(__file__).parent.parent
_GOLD_PATH = _BASE / "gold_set.json"
_SOURCE_PATH = _BASE / "logic_meta_vocab.txt"


@pytest.fixture(scope="module")
def gold_data() -> dict[str, object]:
    return json.loads(_GOLD_PATH.read_text(encoding="utf-8"))  # type: ignore[return-value]


@pytest.fixture(scope="module")
def gold_items(gold_data: dict[str, object]) -> list[dict[str, object]]:
    return gold_data["items"]  # type: ignore[return-value]


@pytest.fixture(scope="module")
def source_text() -> str:
    return _SOURCE_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Count
# ---------------------------------------------------------------------------


class TestCount:
    def test_exactly_50_items(self, gold_items: list[dict[str, object]]) -> None:
        assert len(gold_items) == 50, (
            f"Gold set must have exactly 50 items, got {len(gold_items)}."
        )


# ---------------------------------------------------------------------------
# Schema / well-formedness
# ---------------------------------------------------------------------------


_REQUIRED_FIELDS = {"id", "domain", "source_ref", "question", "answer", "key_terms"}
_ID_PATTERN = re.compile(r"^GS-\d{3}$")
_VALID_DOMAINS = {
    "argument_vocabulary",
    "indicator_words",
    "quantifiers",
    "fallacies",
}
_MIN_QUESTION_LEN = 15
_MIN_ANSWER_LEN = 30


class TestSchemaWellFormedness:
    def test_required_fields_present(self, gold_items: list[dict[str, object]]) -> None:
        for item in gold_items:
            missing = _REQUIRED_FIELDS - set(item.keys())
            assert not missing, (
                f"Item {item.get('id', '?')} is missing fields: {missing}"
            )

    def test_id_format(self, gold_items: list[dict[str, object]]) -> None:
        for item in gold_items:
            assert _ID_PATTERN.match(str(item["id"])), (
                f"ID {item['id']!r} does not match GS-NNN pattern."
            )

    def test_ids_unique(self, gold_items: list[dict[str, object]]) -> None:
        ids = [str(item["id"]) for item in gold_items]
        assert len(ids) == len(set(ids)), "Gold set contains duplicate IDs."

    def test_ids_sequential(self, gold_items: list[dict[str, object]]) -> None:
        ids = sorted(str(item["id"]) for item in gold_items)
        for i, id_ in enumerate(ids, start=1):
            expected = f"GS-{i:03d}"
            assert id_ == expected, (
                f"ID gap or mismatch: expected {expected}, got {id_}."
            )

    def test_domain_values(self, gold_items: list[dict[str, object]]) -> None:
        for item in gold_items:
            assert item["domain"] in _VALID_DOMAINS, (
                f"Item {item['id']} has unknown domain {item['domain']!r}. "
                f"Valid: {_VALID_DOMAINS}"
            )

    def test_questions_non_empty(self, gold_items: list[dict[str, object]]) -> None:
        for item in gold_items:
            q = str(item["question"]).strip()
            assert len(q) >= _MIN_QUESTION_LEN, (
                f"Item {item['id']} question too short: {q!r}"
            )

    def test_answers_non_empty(self, gold_items: list[dict[str, object]]) -> None:
        for item in gold_items:
            a = str(item["answer"]).strip()
            assert len(a) >= _MIN_ANSWER_LEN, (
                f"Item {item['id']} answer too short: {a!r}"
            )

    def test_key_terms_non_empty(self, gold_items: list[dict[str, object]]) -> None:
        for item in gold_items:
            terms = item["key_terms"]
            assert isinstance(terms, list) and len(terms) >= 1, (
                f"Item {item['id']} must have at least one key_term."
            )

    def test_source_ref_format(self, gold_items: list[dict[str, object]]) -> None:
        """Source refs must be §N.M style."""
        ref_pat = re.compile(r"^§[\d]+\.[\d]+$")
        for item in gold_items:
            ref = str(item["source_ref"])
            assert ref_pat.match(ref), (
                f"Item {item['id']} has malformed source_ref: {ref!r}"
            )


# ---------------------------------------------------------------------------
# Source coverage
# ---------------------------------------------------------------------------


class TestSourceCoverage:
    def test_source_refs_exist_in_source(
        self,
        gold_items: list[dict[str, object]],
        source_text: str,
    ) -> None:
        """Every source_ref must correspond to a section heading in the source file."""
        for item in gold_items:
            ref = str(item["source_ref"])
            assert ref in source_text, (
                f"Item {item['id']} source_ref {ref!r} not found in source text."
            )

    def test_domain_counts(self, gold_items: list[dict[str, object]]) -> None:
        """
        Domain distribution should be roughly as documented in metadata.
        Checks that each domain has at least 5 items (sanity only, not strict).
        """
        from collections import Counter
        counts = Counter(str(item["domain"]) for item in gold_items)
        for domain in _VALID_DOMAINS:
            assert counts[domain] >= 5, (
                f"Domain {domain!r} has only {counts[domain]} items; expected ≥5."
            )


# ---------------------------------------------------------------------------
# No-LSAT-item guard
# ---------------------------------------------------------------------------


_LSAT_PATTERNS = [
    re.compile(r"\(A\)\s+", re.IGNORECASE),  # answer choice format
    re.compile(r"\(B\)\s+", re.IGNORECASE),
    re.compile(r"PrepTest", re.IGNORECASE),
    re.compile(r"LSAC", re.IGNORECASE),
    re.compile(r"answer choice", re.IGNORECASE),
    re.compile(r"stimulus", re.IGNORECASE),
]


class TestNoLsatItems:
    """
    Gold set items must be general logic/argument concepts, never LSAT items.
    spec-ai §5, D-SR15, brainlift F.2.
    """

    def test_no_lsat_patterns_in_questions(
        self, gold_items: list[dict[str, object]]
    ) -> None:
        for item in gold_items:
            for pat in _LSAT_PATTERNS:
                assert not pat.search(str(item["question"])), (
                    f"Item {item['id']} question contains LSAT-item pattern "
                    f"{pat.pattern!r}: {item['question']!r}"
                )

    def test_no_lsat_patterns_in_answers(
        self, gold_items: list[dict[str, object]]
    ) -> None:
        for item in gold_items:
            for pat in _LSAT_PATTERNS:
                assert not pat.search(str(item["answer"])), (
                    f"Item {item['id']} answer contains LSAT-item pattern "
                    f"{pat.pattern!r}: {item['answer']!r}"
                )
