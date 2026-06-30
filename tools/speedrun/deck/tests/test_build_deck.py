# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Tests for tools/speedrun/deck/build_seed_deck.py.

These tests require the anki Python package to be installed/built.
If it is not importable, the test module is skipped with an informative
message (see the `anki_available` fixture).

To run once the anki wheel is built:
    just wheels && pytest tools/speedrun/deck/tests/test_build_deck.py -v

NOTE (L2 in WP-1-log.md): The anki package is not a standard pip package in
this repo — it is built from the Rust+Python source. So these tests are
expected to be skipped in a vanilla Python environment; they run correctly
after `just wheels` has been executed.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Generator

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
BUILD_DECK_MODULE = REPO_ROOT / "tools" / "speedrun" / "deck" / "build_seed_deck.py"
SAMPLE_ITEMS_JSON = REPO_ROOT / "tools" / "speedrun" / "deck" / "sample_items.json"
TAXONOMY_JSON = REPO_ROOT / "docs" / "speedrun" / "data" / "taxonomy.json"


# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------

def _anki_importable() -> bool:
    try:
        import anki  # noqa: F401
        return True
    except ImportError:
        return False


anki_available = pytest.mark.skipif(
    not _anki_importable(),
    reason=(
        "anki package not installed. Build the wheel first with 'just wheels', "
        "then re-run this test. See L2 in docs/speedrun/inbox/WP-1-log.md."
    ),
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tmp_col_path() -> Generator[str, None, None]:
    """Create a temporary .anki2 collection file and clean up after."""
    fd, path = tempfile.mkstemp(suffix=".anki2", prefix="speedrun_test_")
    os.close(fd)
    os.unlink(path)
    yield path
    if os.path.exists(path):
        os.unlink(path)
    # Anki also creates a .anki2-wal and .anki2-shm alongside.
    for ext in ["-wal", "-shm", ".media", ".log", ".log.last"]:
        sibling = path + ext
        if os.path.exists(sibling):
            os.unlink(sibling)
    # media folder
    media = path + ".media"
    if os.path.isdir(media):
        shutil.rmtree(media, ignore_errors=True)


@pytest.fixture(scope="module")
def coverage_report(tmp_col_path: str):
    """Run build_seed_deck once and return the CoverageReport."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "tools" / "speedrun" / "deck"))
    from build_seed_deck import build_seed_deck

    return build_seed_deck(
        col_path=tmp_col_path,
        items_json_path=SAMPLE_ITEMS_JSON,
        min_pool_size=1,  # use 1 for seed test so most skills pass
        verbose=False,
    )


@pytest.fixture(scope="module")
def open_col(tmp_col_path: str):
    """Return an open Collection for inspection (closed at module teardown)."""
    from anki.collection import Collection
    col = Collection(tmp_col_path)
    yield col
    col.close()


# ---------------------------------------------------------------------------
# Sample items file
# ---------------------------------------------------------------------------

class TestSampleItemsFile:
    def test_sample_items_file_exists(self) -> None:
        assert SAMPLE_ITEMS_JSON.exists(), f"sample_items.json not found: {SAMPLE_ITEMS_JSON}"

    def test_all_items_marked_synthetic(self) -> None:
        with open(SAMPLE_ITEMS_JSON, encoding="utf-8") as f:
            data = json.load(f)
        for item in data["items"]:
            assert item.get("SyntheticFlag") == "SYNTHETIC", (
                f"Item {item.get('_id', '?')} must have SyntheticFlag=SYNTHETIC (D-SR11)"
            )

    def test_all_required_fields_present(self) -> None:
        required = {
            "SyntheticFlag", "TypeTag", "SkillTag", "Difficulty",
            "Source", "Stimulus", "Stem",
            "ChoiceA", "ChoiceB", "ChoiceC", "ChoiceD", "ChoiceE",
            "CorrectChoice",
        }
        with open(SAMPLE_ITEMS_JSON, encoding="utf-8") as f:
            data = json.load(f)
        for item in data["items"]:
            missing = required - item.keys()
            assert not missing, (
                f"Item {item.get('_id', '?')} missing fields: {missing}"
            )

    def test_correct_choice_is_valid(self) -> None:
        with open(SAMPLE_ITEMS_JSON, encoding="utf-8") as f:
            data = json.load(f)
        for item in data["items"]:
            assert item["CorrectChoice"] in ("A", "B", "C", "D", "E"), (
                f"Item {item.get('_id', '?')} has invalid CorrectChoice: {item['CorrectChoice']!r}"
            )

    def test_type_tags_are_valid(self) -> None:
        import re
        tag_re = re.compile(r"^type::[a-z0-9][a-z0-9\-]*$")
        with open(SAMPLE_ITEMS_JSON, encoding="utf-8") as f:
            data = json.load(f)
        for item in data["items"]:
            tag = item.get("TypeTag", "")
            assert tag_re.match(tag), (
                f"Item {item.get('_id', '?')} has invalid TypeTag: {tag!r}"
            )

    def test_source_contains_synthetic_label(self) -> None:
        with open(SAMPLE_ITEMS_JSON, encoding="utf-8") as f:
            data = json.load(f)
        for item in data["items"]:
            assert "SYNTHETIC" in item.get("Source", ""), (
                f"Item {item.get('_id', '?')} Source must include 'SYNTHETIC'"
            )

    def test_has_items_for_high_frequency_types(self) -> None:
        """Items for Flaw, Assumption, and Inference must be present (high-freq skills)."""
        with open(SAMPLE_ITEMS_JSON, encoding="utf-8") as f:
            data = json.load(f)
        type_tags = {item["TypeTag"] for item in data["items"]}
        assert "type::flaw" in type_tags, "No Flaw items in sample_items.json"
        assert "type::assumption" in type_tags, "No Assumption items in sample_items.json"
        assert "type::inference" in type_tags, "No Inference items in sample_items.json"


# ---------------------------------------------------------------------------
# Collection-level tests (require anki package)
# ---------------------------------------------------------------------------

class TestBuildDeckNotetypes:
    @anki_available
    def test_three_notetypes_exist(self, open_col) -> None:
        names = {nt.name for nt in open_col.models.all_names_and_ids()}
        assert "LSAT Meta" in names, "LSAT Meta notetype not found"
        assert "LSAT Skill" in names, "LSAT Skill notetype not found"
        assert "LSAT Item" in names, "LSAT Item notetype not found"

    @anki_available
    def test_lsat_meta_fields(self, open_col) -> None:
        nt = open_col.models.by_name("LSAT Meta")
        field_names = {f["name"] for f in nt["flds"]}
        required = {"Front", "Back", "Category", "Source", "Notes"}
        missing = required - field_names
        assert not missing, f"LSAT Meta missing fields: {missing}"

    @anki_available
    def test_lsat_skill_fields(self, open_col) -> None:
        nt = open_col.models.by_name("LSAT Skill")
        field_names = {f["name"] for f in nt["flds"]}
        required = {
            "SkillName", "SkillType", "IdentityTag",
            "Description", "KeyTechnique", "CommonErrors", "Notes",
        }
        missing = required - field_names
        assert not missing, f"LSAT Skill missing fields: {missing}"

    @anki_available
    def test_lsat_item_fields(self, open_col) -> None:
        nt = open_col.models.by_name("LSAT Item")
        field_names = {f["name"] for f in nt["flds"]}
        required = {
            "Stimulus", "Stem",
            "ChoiceA", "ChoiceB", "ChoiceC", "ChoiceD", "ChoiceE",
            "CorrectChoice",
            "WhyWrongA", "WhyWrongB", "WhyWrongC", "WhyWrongD", "WhyWrongE",
            "TrapChoiceA", "TrapChoiceB", "TrapChoiceC", "TrapChoiceD", "TrapChoiceE",
            "TypeTag", "SkillTag", "TrapTag",
            "Difficulty", "Source", "SyntheticFlag",
        }
        missing = required - field_names
        assert not missing, f"LSAT Item missing fields: {missing}"

    @anki_available
    def test_each_notetype_has_one_template(self, open_col) -> None:
        for name in ("LSAT Meta", "LSAT Skill", "LSAT Item"):
            nt = open_col.models.by_name(name)
            assert len(nt["tmpls"]) >= 1, f"{name} has no templates"


class TestBuildDeckNotes:
    @anki_available
    def test_skill_notes_created(self, open_col, coverage_report) -> None:
        nt = open_col.models.by_name("LSAT Skill")
        nids = open_col.models.nids(nt["id"])
        assert len(nids) >= 13, (
            f"Expected ≥13 LSAT Skill notes (one per QT), got {len(nids)}"
        )

    @anki_available
    def test_meta_notes_created(self, open_col) -> None:
        nt = open_col.models.by_name("LSAT Meta")
        nids = open_col.models.nids(nt["id"])
        assert len(nids) >= 5, (
            f"Expected ≥5 LSAT Meta notes (seed vocab/flaw/indicators), got {len(nids)}"
        )

    @anki_available
    def test_item_notes_created(self, open_col) -> None:
        nt = open_col.models.by_name("LSAT Item")
        nids = open_col.models.nids(nt["id"])
        with open(SAMPLE_ITEMS_JSON, encoding="utf-8") as f:
            sample_data = json.load(f)
        expected = len(sample_data["items"])
        assert len(nids) == expected, (
            f"Expected {expected} LSAT Item notes (one per sample_items entry), "
            f"got {len(nids)}"
        )

    @anki_available
    def test_all_item_cards_are_suspended(self, open_col) -> None:
        """Item cards must all be suspended (pool, never directly studied)."""
        nt = open_col.models.by_name("LSAT Item")
        nids = open_col.models.nids(nt["id"])
        for nid in nids:
            note = open_col.get_note(nid)
            for card in note.cards():
                assert card.queue == -1, (
                    f"LSAT Item card {card.id} is not suspended (queue={card.queue}). "
                    "Item cards must be suspended (spec-engine §7)."
                )

    @anki_available
    def test_skill_notes_have_identity_tags(self, open_col) -> None:
        """Each LSAT Skill note should have exactly one identity tag."""
        nt = open_col.models.by_name("LSAT Skill")
        nids = open_col.models.nids(nt["id"])
        for nid in nids:
            note = open_col.get_note(nid)
            assert len(note.tags) >= 1, f"LSAT Skill note {nid} has no tags"

    @anki_available
    def test_item_notes_have_synthetic_tag(self, open_col) -> None:
        """Item notes should carry synthetic::true tag."""
        nt = open_col.models.by_name("LSAT Item")
        nids = open_col.models.nids(nt["id"])
        for nid in nids:
            note = open_col.get_note(nid)
            assert "synthetic::true" in note.tags, (
                f"LSAT Item note {nid} missing synthetic::true tag"
            )


class TestBuildDeckCoverageReport:
    @anki_available
    def test_coverage_report_returned(self, coverage_report) -> None:
        from build_seed_deck import CoverageReport
        assert isinstance(coverage_report, CoverageReport)

    @anki_available
    def test_total_skills_equals_question_type_count(
        self, coverage_report, open_col
    ) -> None:
        with open(TAXONOMY_JSON, encoding="utf-8") as f:
            taxonomy = json.load(f)
        n_qt = len(taxonomy["axis1_question_types"])
        assert coverage_report.total_skills == n_qt, (
            f"CoverageReport.total_skills={coverage_report.total_skills} "
            f"but taxonomy has {n_qt} question types"
        )

    @anki_available
    def test_coverage_fraction_between_0_and_1(self, coverage_report) -> None:
        f = coverage_report.coverage_fraction
        assert 0.0 <= f <= 1.0, f"Coverage fraction {f} out of [0, 1]"


class TestSyntheticGuard:
    """build_seed_deck must reject items missing SyntheticFlag (D-SR11)."""

    @anki_available
    def test_rejects_item_without_synthetic_flag(self, tmp_col_path: str) -> None:
        import sys
        sys.path.insert(0, str(REPO_ROOT / "tools" / "speedrun" / "deck"))
        from build_seed_deck import build_seed_deck

        bad_items = {
            "_disclaimer": "test",
            "items": [
                {
                    "SyntheticFlag": "REAL",  # should be rejected
                    "TypeTag": "type::flaw",
                    "SkillTag": "skill::conclusion-id",
                    "TrapTag": "",
                    "Difficulty": 1,
                    "Source": "LSAT PT 101 Q1",
                    "Stimulus": "Test stimulus.",
                    "Stem": "Test stem?",
                    "ChoiceA": "A", "ChoiceB": "B", "ChoiceC": "C",
                    "ChoiceD": "D", "ChoiceE": "E",
                    "CorrectChoice": "A",
                    "WhyWrongA": "", "WhyWrongB": "", "WhyWrongC": "",
                    "WhyWrongD": "", "WhyWrongE": "",
                    "TrapChoiceA": "", "TrapChoiceB": "", "TrapChoiceC": "",
                    "TrapChoiceD": "", "TrapChoiceE": "",
                }
            ],
        }

        import json as _json
        import tempfile
        fd, items_path = tempfile.mkstemp(suffix=".json")
        try:
            os.close(fd)
            with open(items_path, "w", encoding="utf-8") as f:
                _json.dump(bad_items, f)

            fd2, col2 = tempfile.mkstemp(suffix=".anki2")
            os.close(fd2)
            os.unlink(col2)
            try:
                with pytest.raises(ValueError, match="SyntheticFlag"):
                    build_seed_deck(
                        col_path=col2,
                        items_json_path=items_path,
                        verbose=False,
                    )
            finally:
                for ext in ["", "-wal", "-shm", ".media"]:
                    p = col2 + ext
                    if os.path.exists(p):
                        os.unlink(p)
                if os.path.isdir(col2 + ".media"):
                    shutil.rmtree(col2 + ".media", ignore_errors=True)
        finally:
            os.unlink(items_path)
