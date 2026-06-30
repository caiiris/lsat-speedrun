# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Tests for calibration.py — deterministic, seeded, fixture-based.

All assertions use known analytic results or tight approximate bounds.
"""

from __future__ import annotations

import math
import pytest

from tools.speedrun.eval.calibration import (
    ReviewPair,
    compute_calibration,
    make_overconfident_fixture,
    make_well_calibrated_fixture,
)


# ---------------------------------------------------------------------------
# Analytic / degenerate cases
# ---------------------------------------------------------------------------


def test_perfect_predictor_brier_zero() -> None:
    """A model that always predicts the correct outcome has Brier = 0."""
    pairs = [
        ReviewPair(predicted_r=1.0, outcome=1),
        ReviewPair(predicted_r=0.0, outcome=0),
        ReviewPair(predicted_r=1.0, outcome=1),
    ]
    result = compute_calibration(pairs)
    assert result.brier_score == pytest.approx(0.0, abs=1e-10)


def test_worst_predictor_brier_one() -> None:
    """A model that is always maximally wrong has Brier = 1."""
    pairs = [
        ReviewPair(predicted_r=0.0, outcome=1),
        ReviewPair(predicted_r=1.0, outcome=0),
    ]
    result = compute_calibration(pairs)
    assert result.brier_score == pytest.approx(1.0, abs=1e-10)


def test_constant_half_predictor() -> None:
    """predict=0.5 always: Brier = 0.25, log-loss = log(2)."""
    pairs = [ReviewPair(predicted_r=0.5, outcome=o) for o in [0, 1, 0, 1]]
    result = compute_calibration(pairs)
    assert result.brier_score == pytest.approx(0.25, abs=1e-10)
    assert result.log_loss == pytest.approx(math.log(2), abs=1e-6)


def test_empty_input_raises() -> None:
    with pytest.raises(ValueError, match="No review pairs"):
        compute_calibration([])


def test_invalid_predicted_r_raises() -> None:
    with pytest.raises(ValueError, match="predicted_r"):
        compute_calibration([ReviewPair(predicted_r=1.5, outcome=1)])


def test_invalid_outcome_raises() -> None:
    with pytest.raises(ValueError, match="outcome"):
        compute_calibration([ReviewPair(predicted_r=0.5, outcome=2)])


# ---------------------------------------------------------------------------
# Fixture-based: well-calibrated vs mis-calibrated
# ---------------------------------------------------------------------------


def test_well_calibrated_fixture_brier_low() -> None:
    """
    Seed-42 well-calibrated fixture (n=2000): Brier should be well under 0.25
    (the score for a constant 0.5 predictor).
    """
    pairs = make_well_calibrated_fixture(seed=42, n=2000)
    result = compute_calibration(pairs)
    # A well-calibrated model Brier ≈ E[p*(1-p)] = mean variance of Bernoulli(p).
    # For p ~ Uniform[0,1], E[p*(1-p)] = 1/6 ≈ 0.167 — well below the constant-0.5
    # baseline of 0.25.
    assert result.brier_score < 0.22, f"Expected Brier < 0.22, got {result.brier_score}"
    assert result.log_loss < 0.60, f"Expected log-loss < 0.60, got {result.log_loss}"


def test_overconfident_fixture_brier_higher() -> None:
    """
    Mis-calibrated overconfident fixture has higher Brier than a fair model.
    Both use the same seed so counts are comparable.
    """
    pairs_good = make_well_calibrated_fixture(seed=42, n=2000)
    pairs_bad = make_overconfident_fixture(seed=42, n=2000)
    r_good = compute_calibration(pairs_good)
    r_bad = compute_calibration(pairs_bad)
    assert r_bad.brier_score > r_good.brier_score, (
        f"Mis-calibrated model Brier ({r_bad.brier_score:.4f}) should exceed "
        f"well-calibrated ({r_good.brier_score:.4f})"
    )


def test_well_calibrated_fixture_deterministic() -> None:
    """Same seed → same result (determinism guarantee)."""
    r1 = compute_calibration(make_well_calibrated_fixture(seed=7))
    r2 = compute_calibration(make_well_calibrated_fixture(seed=7))
    assert r1.brier_score == r2.brier_score
    assert r1.log_loss == r2.log_loss


def test_different_seeds_differ() -> None:
    """Different seeds → different results (fixture is not trivially constant)."""
    r1 = compute_calibration(make_well_calibrated_fixture(seed=1, n=500))
    r2 = compute_calibration(make_well_calibrated_fixture(seed=2, n=500))
    assert r1.brier_score != r2.brier_score


# ---------------------------------------------------------------------------
# Known-value regression test (pinned to seed=42, n=2000)
# ---------------------------------------------------------------------------


def test_well_calibrated_brier_pinned() -> None:
    """
    Pin the exact Brier / log-loss for the canonical fixture so regressions
    surface immediately.  Recompute with the formula if the fixture changes.
    """
    pairs = make_well_calibrated_fixture(seed=42, n=2000)
    result = compute_calibration(pairs)
    # Pinned values (measured from the seeded RNG; regenerate if fixture logic changes).
    # Note: well-calibrated fixture Brier ≈ E[p*(1-p)] = mean variance of a Bernoulli(p)
    # for p uniform on [0,1], which is 1/6 ≈ 0.1667. Empirical value with seed=42 is ~0.164.
    assert result.brier_score == pytest.approx(0.1642, abs=0.005)
    assert result.log_loss == pytest.approx(0.4957, abs=0.020)
    assert result.n_total == 2000


# ---------------------------------------------------------------------------
# Bin count
# ---------------------------------------------------------------------------


def test_bin_count_default() -> None:
    """Default 10 bins; populated bins ≤ 10."""
    pairs = make_well_calibrated_fixture(seed=42, n=1000)
    result = compute_calibration(pairs, n_bins=10)
    assert len(result.bins) <= 10
    assert all(b.n > 0 for b in result.bins)


def test_bin_count_custom() -> None:
    pairs = [ReviewPair(predicted_r=i / 20, outcome=1) for i in range(20)]
    result = compute_calibration(pairs, n_bins=5)
    assert len(result.bins) <= 5
