# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Tests for docs/speedrun/data/weights.json:
  - LR frequency weights sum to ~1.0
  - Raw-to-scaled conversion table is monotone and within scale bounds
  - All weight keys are valid type:: tags
  - Coverage thresholds present and sane
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
WEIGHTS_JSON = REPO_ROOT / "docs" / "speedrun" / "data" / "weights.json"
TAXONOMY_JSON = REPO_ROOT / "docs" / "speedrun" / "data" / "taxonomy.json"

TYPE_TAG_RE = re.compile(r"^type::[a-z0-9][a-z0-9\-]*$")


@pytest.fixture(scope="module")
def weights() -> dict:
    assert WEIGHTS_JSON.exists(), f"weights.json not found at {WEIGHTS_JSON}"
    with open(WEIGHTS_JSON, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def taxonomy() -> dict:
    assert TAXONOMY_JSON.exists()
    with open(TAXONOMY_JSON, encoding="utf-8") as f:
        return json.load(f)


class TestWeightSchema:
    def test_has_required_top_level_keys(self, weights: dict) -> None:
        required = {
            "lr_frequency_weights",
            "raw_to_scaled_conversion",
            "coverage_thresholds",
        }
        missing = required - weights.keys()
        assert not missing, f"Missing keys in weights.json: {missing}"

    def test_lr_weights_section_has_weights_dict(self, weights: dict) -> None:
        lr = weights["lr_frequency_weights"]
        assert "weights" in lr, "'weights' dict missing from lr_frequency_weights"
        assert isinstance(lr["weights"], dict)

    def test_has_disclaimer(self, weights: dict) -> None:
        assert "_disclaimer" in weights, "weights.json must carry a _disclaimer field"


class TestLRFrequencyWeights:
    def test_weights_sum_to_one(self, weights: dict) -> None:
        w = weights["lr_frequency_weights"]["weights"]
        total = sum(w.values())
        assert abs(total - 1.0) < 1e-9, (
            f"LR weights must sum to exactly 1.0, got {total:.10f}"
        )

    def test_all_weights_nonnegative(self, weights: dict) -> None:
        w = weights["lr_frequency_weights"]["weights"]
        for tag, val in w.items():
            assert val >= 0, f"Negative weight for {tag}: {val}"

    def test_all_keys_are_valid_type_tags(self, weights: dict) -> None:
        w = weights["lr_frequency_weights"]["weights"]
        for tag in w:
            assert TYPE_TAG_RE.match(tag), (
                f"Weight key is not a valid type:: tag: {tag!r}"
            )

    def test_high_frequency_types_present_and_plausible(self, weights: dict) -> None:
        """Flaw + Assumption + Inference should sum to ~40% (brainlift J.1)."""
        w = weights["lr_frequency_weights"]["weights"]
        assert "type::flaw" in w, "type::flaw missing from weights"
        assert "type::assumption" in w, "type::assumption missing from weights"
        assert "type::inference" in w, "type::inference missing from weights"
        core_sum = w["type::flaw"] + w["type::assumption"] + w["type::inference"]
        assert 0.30 <= core_sum <= 0.55, (
            f"Flaw+Assumption+Inference should be ~40%, got {core_sum:.2%}"
        )

    def test_no_single_type_dominates_unreasonably(self, weights: dict) -> None:
        w = weights["lr_frequency_weights"]["weights"]
        for tag, val in w.items():
            assert val <= 0.35, f"Single type {tag} has unreasonably high weight: {val:.2%}"

    def test_weights_keys_match_taxonomy(self, weights: dict, taxonomy: dict) -> None:
        """Every weight key should correspond to a type:: tag in the taxonomy."""
        taxonomy_tags = {qt["tag"] for qt in taxonomy["axis1_question_types"]}
        weight_tags = set(weights["lr_frequency_weights"]["weights"].keys())
        unknown = weight_tags - taxonomy_tags
        assert not unknown, (
            f"Weights contain type tags not in taxonomy.json: {unknown}"
        )

    def test_form_lr_items_is_plausible(self, weights: dict) -> None:
        lr = weights["lr_frequency_weights"]
        n = lr.get("_form_lr_items")
        assert n is not None, "_form_lr_items not set"
        assert 40 <= n <= 60, f"_form_lr_items {n} outside plausible range 40-60"


class TestRawToScaledTable:
    def test_table_exists_and_nonempty(self, weights: dict) -> None:
        table = weights["raw_to_scaled_conversion"]["table"]
        assert len(table) > 0, "raw_to_scaled table is empty"

    def test_table_covers_full_raw_range(self, weights: dict) -> None:
        table = weights["raw_to_scaled_conversion"]["table"]
        raws = {entry["raw"] for entry in table}
        assert 0 in raws, "raw=0 must be in table"
        # At least one entry at max raw (≥70)
        assert max(raws) >= 70, f"Max raw score {max(raws)} seems too low"

    def test_scaled_scores_within_lsat_range(self, weights: dict) -> None:
        table = weights["raw_to_scaled_conversion"]["table"]
        for entry in table:
            assert 120 <= entry["scaled"] <= 180, (
                f"Scaled score {entry['scaled']} out of LSAT range 120-180 "
                f"(raw={entry['raw']})"
            )

    def test_scaled_is_monotone_nondecreasing_with_raw(self, weights: dict) -> None:
        """Higher raw → same or higher scaled (non-decreasing)."""
        table = sorted(weights["raw_to_scaled_conversion"]["table"], key=lambda e: e["raw"])
        for i in range(1, len(table)):
            assert table[i]["scaled"] >= table[i - 1]["scaled"], (
                f"Scaled score decreased from raw={table[i-1]['raw']} "
                f"(scaled={table[i-1]['scaled']}) to raw={table[i]['raw']} "
                f"(scaled={table[i]['scaled']})"
            )

    def test_max_raw_maps_to_180(self, weights: dict) -> None:
        table = weights["raw_to_scaled_conversion"]["table"]
        max_entry = max(table, key=lambda e: e["raw"])
        assert max_entry["scaled"] == 180, (
            f"Max raw ({max_entry['raw']}) should map to 180, got {max_entry['scaled']}"
        )

    def test_raw_zero_maps_to_120(self, weights: dict) -> None:
        table = weights["raw_to_scaled_conversion"]["table"]
        zero_entries = [e for e in table if e["raw"] == 0]
        assert zero_entries, "raw=0 not found in table"
        assert zero_entries[0]["scaled"] == 120, (
            f"raw=0 should map to 120, got {zero_entries[0]['scaled']}"
        )

    def test_disclaimer_present(self, weights: dict) -> None:
        conv = weights["raw_to_scaled_conversion"]
        assert "_disclaimer" in conv, "raw_to_scaled_conversion must have a _disclaimer"


class TestCoverageThresholds:
    def test_thresholds_present(self, weights: dict) -> None:
        ct = weights["coverage_thresholds"]
        required = {
            "min_pool_size_seed",
            "min_pool_size_production",
            "readiness_gate_min_attempts",
            "readiness_gate_min_coverage",
        }
        missing = required - ct.keys()
        assert not missing, f"Missing coverage threshold keys: {missing}"

    def test_gate_thresholds_match_spec(self, weights: dict) -> None:
        """spec-measurement §6 / D-SR10: ≥200 attempts AND ≥50% coverage."""
        ct = weights["coverage_thresholds"]
        assert ct["readiness_gate_min_attempts"] == 200, (
            f"Gate min attempts should be 200 (D-SR10), got {ct['readiness_gate_min_attempts']}"
        )
        assert abs(ct["readiness_gate_min_coverage"] - 0.50) < 1e-9, (
            f"Gate min coverage should be 0.50 (D-SR10), got {ct['readiness_gate_min_coverage']}"
        )

    def test_pool_sizes_sane(self, weights: dict) -> None:
        ct = weights["coverage_thresholds"]
        assert ct["min_pool_size_seed"] >= 1
        assert ct["min_pool_size_production"] >= ct["min_pool_size_seed"]
