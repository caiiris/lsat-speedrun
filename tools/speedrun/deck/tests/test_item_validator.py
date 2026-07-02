# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Tests for tools/speedrun/deck/item_validator.py — the deterministic (no-AI)
quality gate for the LSAT Item pool.

Two layers:
  1. Contract tests for the validator itself (well-formed vs planted defects).
  2. A content test asserting the *actual* pool under deck/items/ has zero
     validation errors, so a bad item can never land in the DB.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DECK_DIR = REPO_ROOT / "tools" / "speedrun" / "deck"
ITEMS_DIR = DECK_DIR / "items"
sys.path.insert(0, str(DECK_DIR))

from item_validator import (  # noqa: E402
    TagUniverse,
    load_taxonomy,
    validate_items,
)
from items_loader import load_items  # noqa: E402


def _universe() -> TagUniverse:
    return TagUniverse.from_taxonomy(load_taxonomy())


# A minimal well-formed item used as the base for planted-defect tests.
GOOD_ITEM = {
    "_id": "SYNTH-TEST-001",
    "SyntheticFlag": "SYNTHETIC",
    "TypeTag": "type::flaw",
    "SkillTag": "skill::conclusion-id skill::conditional",
    "TrapTag": "trap::sufficient-necessary",
    "Difficulty": 2,
    "Source": "SYNTHETIC — test fixture, not a real LSAT question",
    "Stimulus": "All cats are mammals. Whiskers is a mammal. So Whiskers is a cat.",
    "Stem": "The reasoning is flawed because it",
    "ChoiceA": "treats a sufficient condition as a necessary one",
    "ChoiceB": "assumes all mammals are cats without support",
    "ChoiceC": "relies on an ambiguous use of 'mammal'",
    "ChoiceD": "ignores that some cats are not mammals",
    "ChoiceE": "draws a conclusion about a specific case from a general claim",
    "CorrectChoice": "B",
    "WhyWrongA": "The stimulus does not confuse sufficient and necessary here.",
    "WhyWrongB": "CORRECT. Being a mammal does not make something a cat.",
    "WhyWrongC": "No term shifts meaning; equivocation is not the flaw.",
    "WhyWrongD": "This contradicts the premise that all cats are mammals.",
    "WhyWrongE": "The argument's error is not about general-to-specific inference.",
    "TrapChoiceA": "trap::reversal",
    "TrapChoiceB": "",
    "TrapChoiceC": "trap::out-of-scope",
    "TrapChoiceD": "trap::contradicts",
    "TrapChoiceE": "trap::half-true",
}


class TestValidatorAcceptsGoodItem:
    def test_good_item_has_no_errors(self) -> None:
        result = validate_items([copy.deepcopy(GOOD_ITEM)], _universe())
        assert result.ok, result.errors


class TestValidatorCatchesDefects:
    def _err_on(self, mutate) -> list[str]:
        item = copy.deepcopy(GOOD_ITEM)
        mutate(item)
        return validate_items([item], _universe()).errors

    def test_bad_synthetic_flag(self) -> None:
        errs = self._err_on(lambda it: it.update(SyntheticFlag="BOGUS"))
        assert any("SyntheticFlag" in e for e in errs)

    def test_real_item_with_citation_ok(self) -> None:
        item = copy.deepcopy(GOOD_ITEM)
        item.update(
            SyntheticFlag="REAL",
            Source=(
                "Author, Title (2024), ISBN 9780000000000, Q1 — publisher-original; "
                "personal import from locally owned materials; not for redistribution."
            ),
        )
        assert validate_items([item], _universe()).ok

    def test_unknown_type_tag(self) -> None:
        errs = self._err_on(lambda it: it.update(TypeTag="type::nonsense"))
        assert any("TypeTag" in e for e in errs)

    def test_unknown_skill_tag(self) -> None:
        errs = self._err_on(lambda it: it.update(SkillTag="skill::made-up"))
        assert any("SkillTag" in e for e in errs)

    def test_unknown_trap_choice_tag(self) -> None:
        errs = self._err_on(lambda it: it.update(TrapChoiceA="trap::not-real"))
        assert any("TrapChoiceA" in e for e in errs)

    def test_correct_choice_out_of_range(self) -> None:
        errs = self._err_on(lambda it: it.update(CorrectChoice="F"))
        assert any("CorrectChoice" in e for e in errs)

    def test_correct_choice_must_have_empty_trap(self) -> None:
        errs = self._err_on(lambda it: it.update(TrapChoiceB="trap::half-true"))
        assert any("empty TrapChoiceB" in e for e in errs)

    def test_correct_why_must_say_correct(self) -> None:
        errs = self._err_on(lambda it: it.update(WhyWrongB="It is right."))
        assert any("should start with 'CORRECT'" in e for e in errs)

    def test_wrong_choice_needs_trap(self) -> None:
        errs = self._err_on(lambda it: it.update(TrapChoiceA=""))
        assert any("empty TrapChoiceA" in e for e in errs)

    def test_wrong_choice_needs_why(self) -> None:
        errs = self._err_on(lambda it: it.update(WhyWrongA=""))
        assert any("empty WhyWrongA" in e for e in errs)

    def test_difficulty_out_of_range(self) -> None:
        errs = self._err_on(lambda it: it.update(Difficulty=9))
        assert any("Difficulty" in e for e in errs)

    def test_difficulty_must_be_int(self) -> None:
        errs = self._err_on(lambda it: it.update(Difficulty="hard"))
        assert any("Difficulty" in e for e in errs)

    def test_duplicate_id(self) -> None:
        a = copy.deepcopy(GOOD_ITEM)
        b = copy.deepcopy(GOOD_ITEM)
        b["Stimulus"] = "A wholly different stimulus about widgets and gadgets."
        errs = validate_items([a, b], _universe()).errors
        assert any("duplicate _id" in e for e in errs)

    def test_duplicate_stimulus(self) -> None:
        a = copy.deepcopy(GOOD_ITEM)
        b = copy.deepcopy(GOOD_ITEM)
        b["_id"] = "SYNTH-TEST-002"  # distinct id, same stimulus
        errs = validate_items([a, b], _universe()).errors
        assert any("Stimulus duplicates" in e for e in errs)


class TestRealPoolIsClean:
    """The shipped pool must validate with zero errors."""

    def test_pool_has_no_validation_errors(self) -> None:
        items = load_items(ITEMS_DIR)["items"]
        result = validate_items(items, _universe())
        assert result.ok, "Pool has validation errors:\n" + "\n".join(result.errors)

    def test_pool_ids_are_unique(self) -> None:
        items = load_items(ITEMS_DIR)["items"]
        ids = [it.get("_id") for it in items if it.get("_id")]
        assert len(ids) == len(set(ids)), "Duplicate _id values in the pool"
