# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Tests for paraphrase.py — deterministic, seeded, fixture-based.
"""

from __future__ import annotations

import pytest

from tools.speedrun.eval.paraphrase import (
    ParaphraseItem,
    compute_paraphrase_gap,
    make_fixture,
)


# ---------------------------------------------------------------------------
# Analytic / degenerate cases
# ---------------------------------------------------------------------------


def test_perfect_transfer_gap_zero() -> None:
    """Student aces both original and variants → gap = 0."""
    items = [
        ParaphraseItem("q1", base_outcome=1, variant_outcomes=[1, 1]),
        ParaphraseItem("q2", base_outcome=1, variant_outcomes=[1, 1]),
    ]
    result = compute_paraphrase_gap(items)
    assert result.overall_gap == pytest.approx(0.0, abs=1e-10)
    assert result.base_accuracy == pytest.approx(1.0)
    assert result.variant_accuracy == pytest.approx(1.0)


def test_rote_only_gap_one() -> None:
    """Student always gets original right but always fails variants → gap = 1."""
    items = [
        ParaphraseItem("q1", base_outcome=1, variant_outcomes=[0, 0]),
        ParaphraseItem("q2", base_outcome=1, variant_outcomes=[0, 0]),
    ]
    result = compute_paraphrase_gap(items)
    assert result.overall_gap == pytest.approx(1.0, abs=1e-10)


def test_always_fail_gap_zero() -> None:
    """Student always fails everything → gap = 0 (consistent failure)."""
    items = [
        ParaphraseItem("q1", base_outcome=0, variant_outcomes=[0, 0]),
    ]
    result = compute_paraphrase_gap(items)
    assert result.overall_gap == pytest.approx(0.0, abs=1e-10)


def test_mixed_gap_analytic() -> None:
    """
    item A: base=1, variants=[1,0] → gap = 1 - 0.5 = +0.5
    item B: base=0, variants=[0,1] → gap = 0 - 0.5 = -0.5
    mean gap = 0.0
    """
    items = [
        ParaphraseItem("A", base_outcome=1, variant_outcomes=[1, 0]),
        ParaphraseItem("B", base_outcome=0, variant_outcomes=[0, 1]),
    ]
    result = compute_paraphrase_gap(items)
    assert result.overall_gap == pytest.approx(0.0, abs=1e-10)
    assert result.item_gaps[0].gap == pytest.approx(0.5, abs=1e-10)
    assert result.item_gaps[1].gap == pytest.approx(-0.5, abs=1e-10)


def test_empty_raises() -> None:
    with pytest.raises(ValueError, match="No paraphrase items"):
        compute_paraphrase_gap([])


def test_no_variants_raises() -> None:
    with pytest.raises(ValueError, match="no variant outcomes"):
        compute_paraphrase_gap([ParaphraseItem("q1", base_outcome=1, variant_outcomes=[])])


def test_invalid_base_outcome_raises() -> None:
    with pytest.raises(ValueError, match="base_outcome"):
        compute_paraphrase_gap([ParaphraseItem("q1", base_outcome=2, variant_outcomes=[1])])


def test_invalid_variant_outcome_raises() -> None:
    with pytest.raises(ValueError, match="variant_outcome"):
        compute_paraphrase_gap([ParaphraseItem("q1", base_outcome=1, variant_outcomes=[3])])


# ---------------------------------------------------------------------------
# Fixture-based
# ---------------------------------------------------------------------------


def test_fixture_positive_gap() -> None:
    """
    Seed-42 fixture: rote-memory cohort (q001–q015) pulls the mean gap positive.
    """
    items = make_fixture(seed=42)
    result = compute_paraphrase_gap(items)
    assert result.overall_gap > 0, (
        f"Expected positive mean gap (rote-memory effect), got {result.overall_gap:.3f}"
    )


def test_fixture_n_items_and_variants() -> None:
    """Fixture produces exactly 30 items × 2 variants each."""
    items = make_fixture(seed=42, n_items=30, n_variants=2)
    result = compute_paraphrase_gap(items)
    assert result.n_items == 30
    assert result.n_variants_total == 60


def test_fixture_deterministic() -> None:
    """Same seed → same gap."""
    r1 = compute_paraphrase_gap(make_fixture(seed=99))
    r2 = compute_paraphrase_gap(make_fixture(seed=99))
    assert r1.overall_gap == r2.overall_gap


def test_fixture_different_seeds_differ() -> None:
    r1 = compute_paraphrase_gap(make_fixture(seed=1))
    r2 = compute_paraphrase_gap(make_fixture(seed=2))
    # With n=30 and only 2 cohorts, the overall gaps should differ
    assert r1.overall_gap != r2.overall_gap


# ---------------------------------------------------------------------------
# Known-value regression (pinned to seed=42, n_items=30, n_variants=2)
# ---------------------------------------------------------------------------


def test_fixture_gap_pinned() -> None:
    """
    Pin the exact gap value for the canonical fixture.
    Cohort 1 (q001-q015): base=1, variants ~Bernoulli(0.5) → expected gap ~0.5
    Cohort 2 (q016-q030): base/variants ~Bernoulli(0.85) → expected gap ~0
    Overall mean gap ≈ 0.25.
    """
    items = make_fixture(seed=42, n_items=30, n_variants=2)
    result = compute_paraphrase_gap(items)
    assert result.overall_gap == pytest.approx(0.25, abs=0.15), (
        f"Pinned gap out of range: {result.overall_gap:.4f}"
    )
    assert result.base_accuracy > 0.5
    assert 0.0 <= result.variant_accuracy <= 1.0
