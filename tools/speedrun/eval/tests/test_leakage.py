# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Tests for leakage.py — deterministic, fixture-based.

Key assertions:
  - The planted exact duplicate is always caught.
  - The planted near-duplicate is caught at the default threshold.
  - Clean item sets produce no hits.
  - Threshold tuning works as expected.
"""

from __future__ import annotations

import pytest

from tools.speedrun.eval.leakage import (
    LeakageScanner,
    TextItem,
    make_fixture,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scanner(threshold: float = 0.85) -> LeakageScanner:
    return LeakageScanner(threshold=threshold)


# ---------------------------------------------------------------------------
# Exact duplicate detection
# ---------------------------------------------------------------------------


def test_exact_duplicate_caught() -> None:
    train = [TextItem("tr1", "The cat sat on the mat.")]
    test = [TextItem("te1", "The cat sat on the mat.")]
    report = _scanner().scan(train, test)
    assert not report.clean
    assert len(report.hits) == 1
    assert report.hits[0].match_type == "exact"
    assert report.hits[0].similarity == 1.0
    assert report.score_zeroed


def test_exact_duplicate_whitespace_trimmed() -> None:
    """Leading/trailing whitespace is stripped before hashing."""
    train = [TextItem("tr1", "  Hello world.  ")]
    test = [TextItem("te1", "  Hello world.  ")]
    report = _scanner().scan(train, test)
    assert not report.clean
    assert report.hits[0].match_type == "exact"


def test_minor_change_not_exact() -> None:
    """A one-word change must NOT be flagged as exact."""
    train = [TextItem("tr1", "The cat sat on the mat.")]
    test = [TextItem("te1", "The dog sat on the mat.")]
    report = _scanner(threshold=0.99).scan(train, test)
    exact_hits = [h for h in report.hits if h.match_type == "exact"]
    assert len(exact_hits) == 0


# ---------------------------------------------------------------------------
# Near-duplicate detection
# ---------------------------------------------------------------------------


def test_near_duplicate_caught() -> None:
    """
    Minor-edit near-duplicate is caught at default threshold.

    The char-ngram fallback is designed for minor-edit near-copies (same text
    with a word inserted/changed).  Full synonym paraphrase ("students" →
    "pupils") yields lower cosine (~0.65) and requires an EmbeddingProvider;
    that limitation is documented in the README.
    """
    train = [
        TextItem(
            "tr1",
            "Researchers found that students who slept eight hours performed better "
            "on memory tests than those who slept six hours.",
        )
    ]
    test = [
        # Same sentence with one word inserted ("only") — a clear minor-edit near-duplicate
        TextItem(
            "te1",
            "Researchers found that students who slept eight hours performed better "
            "on memory tests than those who slept only six hours.",
        )
    ]
    report = _scanner(threshold=0.85).scan(train, test)
    assert not report.clean
    assert any(h.match_type == "near_duplicate" for h in report.hits)


def test_unrelated_text_not_flagged() -> None:
    """Completely unrelated texts must not be flagged."""
    train = [
        TextItem("tr1", "All mammals are warm-blooded vertebrates."),
        TextItem("tr2", "The French Revolution began in 1789."),
    ]
    test = [
        TextItem("te1", "Photosynthesis converts light energy into chemical energy."),
        TextItem("te2", "The circumference of a circle equals two pi times the radius."),
    ]
    report = _scanner(threshold=0.85).scan(train, test)
    assert report.clean, f"Expected clean, got hits: {report.hits}"
    assert not report.score_zeroed


# ---------------------------------------------------------------------------
# Planted-fixture assertions (spec-measurement §7 acceptance criterion)
# ---------------------------------------------------------------------------


def test_planted_fixture_exact_detected() -> None:
    train, test = make_fixture()
    report = _scanner().scan(train, test)
    exact_ids = {h.test_id for h in report.hits if h.match_type == "exact"}
    assert "leak_exact" in exact_ids, (
        f"Exact duplicate 'leak_exact' not detected; hits: {report.hits}"
    )


def test_planted_fixture_near_duplicate_detected() -> None:
    train, test = make_fixture()
    report = _scanner().scan(train, test)
    near_ids = {h.test_id for h in report.hits}
    assert "leak_near" in near_ids, (
        f"Near-duplicate 'leak_near' not detected; hits: {report.hits}"
    )


def test_planted_fixture_clean_items_not_flagged() -> None:
    """te001 and te002 are unrelated and must not appear in hits."""
    train, test = make_fixture()
    report = _scanner().scan(train, test)
    hit_ids = {h.test_id for h in report.hits}
    assert "te001" not in hit_ids, "'te001' was falsely flagged as a leak"
    assert "te002" not in hit_ids, "'te002' was falsely flagged as a leak"


def test_planted_fixture_score_zeroed() -> None:
    """Any leakage detection sets score_zeroed = True."""
    train, test = make_fixture()
    report = _scanner().scan(train, test)
    assert report.score_zeroed


def test_planted_fixture_report_not_clean() -> None:
    train, test = make_fixture()
    report = _scanner().scan(train, test)
    assert not report.clean


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_train() -> None:
    test = [TextItem("te1", "Some text.")]
    report = _scanner().scan([], test)
    assert report.clean
    assert report.n_train == 0


def test_empty_test() -> None:
    train = [TextItem("tr1", "Some text.")]
    report = _scanner().scan(train, [])
    assert report.clean
    assert report.n_test == 0


def test_both_empty() -> None:
    report = _scanner().scan([], [])
    assert report.clean


def test_threshold_one_catches_only_exact() -> None:
    """threshold=1.0 means only exact matches are caught."""
    train = [
        TextItem(
            "tr1",
            "Researchers found that students who slept eight hours performed better.",
        )
    ]
    test = [
        # near-duplicate — should NOT be flagged at threshold=1.0
        TextItem(
            "te1",
            "Scientists discovered that pupils who slept eight hours scored higher.",
        ),
        # exact duplicate — SHOULD be flagged
        TextItem(
            "te2",
            "Researchers found that students who slept eight hours performed better.",
        ),
    ]
    report = _scanner(threshold=1.0).scan(train, test)
    hit_ids = {h.test_id for h in report.hits}
    assert "te2" in hit_ids
    assert "te1" not in hit_ids


def test_threshold_zero_catches_everything_similar() -> None:
    """threshold=0.0 catches everything with any overlap (vacuous)."""
    train = [TextItem("tr1", "the quick brown fox")]
    test = [TextItem("te1", "the quick brown fox jumps over the lazy dog")]
    report = _scanner(threshold=0.0).scan(train, test)
    assert not report.clean


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_scan_is_deterministic() -> None:
    """Identical inputs must produce identical results (no randomness)."""
    train, test = make_fixture()
    r1 = _scanner().scan(train, test)
    r2 = _scanner().scan(train, test)
    assert [(h.test_id, h.train_id, h.similarity) for h in r1.hits] == [
        (h.test_id, h.train_id, h.similarity) for h in r2.hits
    ]
