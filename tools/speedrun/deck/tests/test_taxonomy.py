# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Tests for docs/speedrun/data/taxonomy.json schema validity and tag-string contract.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
TAXONOMY_JSON = REPO_ROOT / "docs" / "speedrun" / "data" / "taxonomy.json"

TAG_RE = re.compile(r"^(type|skill|trap)::[a-z0-9][a-z0-9\-]*$")


@pytest.fixture(scope="module")
def taxonomy() -> dict:
    assert TAXONOMY_JSON.exists(), f"taxonomy.json not found at {TAXONOMY_JSON}"
    with open(TAXONOMY_JSON, encoding="utf-8") as f:
        return json.load(f)


class TestTaxonomyTopLevel:
    def test_has_required_top_level_keys(self, taxonomy: dict) -> None:
        required = {
            "version",
            "axis1_question_types",
            "axis2_reasoning_subskills",
            "trap_catalog",
            "tag_prefixes",
            "tagging_rules",
        }
        missing = required - taxonomy.keys()
        assert not missing, f"Missing top-level keys: {missing}"

    def test_version_is_string(self, taxonomy: dict) -> None:
        assert isinstance(taxonomy["version"], str)

    def test_tag_prefixes(self, taxonomy: dict) -> None:
        prefixes = taxonomy["tag_prefixes"]
        assert prefixes["question_type"] == "type::"
        assert prefixes["reasoning_subskill"] == "skill::"
        assert prefixes["trap"] == "trap::"


class TestAxis1QuestionTypes:
    def test_approximately_13_types(self, taxonomy: dict) -> None:
        types = taxonomy["axis1_question_types"]
        assert 10 <= len(types) <= 15, (
            f"Expected ~13 question types, got {len(types)}"
        )

    def test_all_required_fields_present(self, taxonomy: dict) -> None:
        required = {"id", "canonical_name", "tag", "description", "approx_frequency_pct"}
        for qt in taxonomy["axis1_question_types"]:
            missing = required - qt.keys()
            assert not missing, f"QT {qt.get('id', '?')} missing fields: {missing}"

    def test_all_tags_have_correct_prefix(self, taxonomy: dict) -> None:
        for qt in taxonomy["axis1_question_types"]:
            tag = qt["tag"]
            assert tag.startswith("type::"), f"QT tag must start with 'type::': {tag!r}"
            assert TAG_RE.match(tag), f"QT tag fails format check: {tag!r}"

    def test_no_duplicate_tags(self, taxonomy: dict) -> None:
        tags = [qt["tag"] for qt in taxonomy["axis1_question_types"]]
        assert len(tags) == len(set(tags)), f"Duplicate QT tags found: {tags}"

    def test_no_duplicate_ids(self, taxonomy: dict) -> None:
        ids = [qt["id"] for qt in taxonomy["axis1_question_types"]]
        assert len(ids) == len(set(ids)), f"Duplicate QT IDs found: {ids}"

    def test_frequency_pcts_are_nonnegative(self, taxonomy: dict) -> None:
        for qt in taxonomy["axis1_question_types"]:
            assert qt["approx_frequency_pct"] >= 0, (
                f"QT {qt['id']} has negative frequency"
            )

    def test_high_frequency_types_present(self, taxonomy: dict) -> None:
        """Flaw, Assumption, and Inference must be present (brainlift J.1: ~40%)."""
        tags = {qt["tag"] for qt in taxonomy["axis1_question_types"]}
        assert "type::flaw" in tags, "type::flaw missing from taxonomy"
        assert "type::assumption" in tags, "type::assumption missing from taxonomy"
        assert "type::inference" in tags, "type::inference missing from taxonomy"


class TestAxis2ReasoningSubskills:
    def test_has_subskills(self, taxonomy: dict) -> None:
        skills = taxonomy["axis2_reasoning_subskills"]
        assert len(skills) >= 4, f"Expected ≥4 reasoning sub-skills, got {len(skills)}"

    def test_all_required_fields_present(self, taxonomy: dict) -> None:
        required = {"id", "name", "tag", "priority", "description"}
        for sk in taxonomy["axis2_reasoning_subskills"]:
            missing = required - sk.keys()
            assert not missing, f"Subskill {sk.get('id', '?')} missing: {missing}"

    def test_all_tags_have_correct_prefix(self, taxonomy: dict) -> None:
        for sk in taxonomy["axis2_reasoning_subskills"]:
            tag = sk["tag"]
            assert tag.startswith("skill::"), f"Subskill tag must start 'skill::': {tag!r}"
            assert TAG_RE.match(tag), f"Subskill tag fails format check: {tag!r}"

    def test_no_duplicate_tags(self, taxonomy: dict) -> None:
        tags = [sk["tag"] for sk in taxonomy["axis2_reasoning_subskills"]]
        assert len(tags) == len(set(tags)), "Duplicate subskill tags"

    def test_conclusion_id_present(self, taxonomy: dict) -> None:
        """conclusion-id is the most critical sub-skill (K.4 / K.2)."""
        tags = {sk["tag"] for sk in taxonomy["axis2_reasoning_subskills"]}
        assert "skill::conclusion-id" in tags

    def test_conditional_present(self, taxonomy: dict) -> None:
        tags = {sk["tag"] for sk in taxonomy["axis2_reasoning_subskills"]}
        assert "skill::conditional" in tags

    def test_valid_priority_values(self, taxonomy: dict) -> None:
        valid = {"critical", "high", "medium", "low"}
        for sk in taxonomy["axis2_reasoning_subskills"]:
            assert sk["priority"] in valid, (
                f"Subskill {sk['id']} has invalid priority: {sk['priority']!r}"
            )


class TestTrapCatalog:
    def test_has_both_subcatalogs(self, taxonomy: dict) -> None:
        trap_cat = taxonomy["trap_catalog"]
        assert "argument_flaws" in trap_cat
        assert "distractor_traps" in trap_cat

    def test_argument_flaws_not_empty(self, taxonomy: dict) -> None:
        flaws = taxonomy["trap_catalog"]["argument_flaws"]
        assert len(flaws) >= 5, f"Expected ≥5 argument flaws, got {len(flaws)}"

    def test_distractor_traps_not_empty(self, taxonomy: dict) -> None:
        traps = taxonomy["trap_catalog"]["distractor_traps"]
        assert len(traps) >= 3, f"Expected ≥3 distractor traps, got {len(traps)}"

    def test_all_trap_tags_have_correct_prefix(self, taxonomy: dict) -> None:
        trap_cat = taxonomy["trap_catalog"]
        all_traps = trap_cat["argument_flaws"] + trap_cat["distractor_traps"]
        for trap in all_traps:
            tag = trap["tag"]
            assert tag.startswith("trap::"), f"Trap tag must start 'trap::': {tag!r}"
            assert TAG_RE.match(tag), f"Trap tag fails format check: {tag!r}"

    def test_no_duplicate_trap_tags(self, taxonomy: dict) -> None:
        trap_cat = taxonomy["trap_catalog"]
        all_traps = trap_cat["argument_flaws"] + trap_cat["distractor_traps"]
        tags = [t["tag"] for t in all_traps]
        assert len(tags) == len(set(tags)), f"Duplicate trap tags: {tags}"

    def test_sufficient_necessary_present(self, taxonomy: dict) -> None:
        """Most common flaw; must be in the catalog (K.2, K.4)."""
        trap_cat = taxonomy["trap_catalog"]
        tags = {t["tag"] for t in trap_cat["argument_flaws"]}
        assert "trap::sufficient-necessary" in tags

    def test_required_fields_on_each_trap(self, taxonomy: dict) -> None:
        required = {"id", "name", "tag", "description", "frequency"}
        trap_cat = taxonomy["trap_catalog"]
        all_traps = trap_cat["argument_flaws"] + trap_cat["distractor_traps"]
        for trap in all_traps:
            missing = required - trap.keys()
            assert not missing, f"Trap {trap.get('id', '?')} missing: {missing}"


class TestTagUniquenessAcrossAxes:
    def test_no_tag_collision_across_axes(self, taxonomy: dict) -> None:
        """type::, skill::, trap:: tags must all be globally unique."""
        all_tags: list[str] = []
        all_tags.extend(qt["tag"] for qt in taxonomy["axis1_question_types"])
        all_tags.extend(sk["tag"] for sk in taxonomy["axis2_reasoning_subskills"])
        trap_cat = taxonomy["trap_catalog"]
        all_tags.extend(t["tag"] for t in trap_cat["argument_flaws"])
        all_tags.extend(t["tag"] for t in trap_cat["distractor_traps"])
        assert len(all_tags) == len(set(all_tags)), (
            f"Tag collision across axes detected in: {all_tags}"
        )
