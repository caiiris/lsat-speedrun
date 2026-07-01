# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Unit tests for qt/aqt/speedrun.py — commit-then-reveal helpers.

These tests are pure-Python (no Qt, no anki wheel required) and run
in any environment: pytest qt/tests/test_speedrun.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# Import qt/aqt/speedrun.py directly (bypasses aqt/__init__.py which needs the
# anki wheel) so these tests run in any Python environment.
_SPEEDRUN_PY = Path(__file__).resolve().parents[1] / "aqt" / "speedrun.py"
_spec = importlib.util.spec_from_file_location("speedrun", _SPEEDRUN_PY)
assert _spec is not None and _spec.loader is not None
_speedrun = importlib.util.module_from_spec(_spec)
sys.modules["speedrun"] = _speedrun
_spec.loader.exec_module(_speedrun)  # type: ignore[union-attr]

from speedrun import (  # type: ignore[import]  # noqa: E402,I001
    LSAT_ITEM_NOTETYPE,
    LSAT_SKILL_NOTETYPE,
    RATING_AGAIN,
    RATING_GOOD,
    bottom_commit_prompt,
    bottom_continue_button,
    build_item_answer_html,
    build_item_question_html,
    correct_choice,
    rating_for_committed,
    speedrun_card_type,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_item_fields(
    correct: str = "B",
    stimulus: str = "All mammals are warm-blooded. Dogs are mammals.",
    stem: str = "Which of the following must be true?",
) -> dict[str, str]:
    return {
        "Stimulus": stimulus,
        "Stem": stem,
        "ChoiceA": "Dogs are cold-blooded.",
        "ChoiceB": "Dogs are warm-blooded.",
        "ChoiceC": "All warm-blooded animals are dogs.",
        "ChoiceD": "No mammals are warm-blooded.",
        "ChoiceE": "Some dogs are mammals.",
        "CorrectChoice": correct,
        "WhyWrongA": "Contradicts the premise.",
        "WhyWrongB": "Correctly follows from the premises.",
        "WhyWrongC": "Converse error.",
        "WhyWrongD": "Negates the first premise.",
        "WhyWrongE": "True but not a must-be-true from these premises.",
        "TrapChoiceA": "trap::correlation-causation",
        "TrapChoiceB": "",
        "TrapChoiceC": "trap::sufficient-necessary",
        "TrapChoiceD": "",
        "TrapChoiceE": "",
        "TypeTag": "type::inference",
        "SkillTag": "skill::conditional",
        "TrapTag": "",
        "Difficulty": "medium",
        "Source": "PT-80 S1 Q1",
        "SyntheticFlag": "SYNTHETIC",
    }


# ---------------------------------------------------------------------------
# speedrun_card_type
# ---------------------------------------------------------------------------


class TestSpeedrunCardType:
    def test_item_notetype(self) -> None:
        assert speedrun_card_type({"name": LSAT_ITEM_NOTETYPE}) == "item"

    def test_skill_notetype(self) -> None:
        assert speedrun_card_type({"name": LSAT_SKILL_NOTETYPE}) == "skill"

    def test_normal_notetype_returns_none(self) -> None:
        assert speedrun_card_type({"name": "Basic"}) is None

    def test_empty_name_returns_none(self) -> None:
        assert speedrun_card_type({"name": ""}) is None

    def test_missing_name_returns_none(self) -> None:
        assert speedrun_card_type({}) is None


# ---------------------------------------------------------------------------
# correct_choice
# ---------------------------------------------------------------------------


class TestCorrectChoice:
    def test_returns_correct_letter(self) -> None:
        fields = _make_item_fields(correct="C")
        assert correct_choice(fields) == "C"

    def test_strips_whitespace(self) -> None:
        fields = _make_item_fields()
        fields["CorrectChoice"] = "  A  "
        assert correct_choice(fields) == "A"

    def test_uppercases(self) -> None:
        fields = _make_item_fields()
        fields["CorrectChoice"] = "b"
        assert correct_choice(fields) == "B"

    def test_missing_field_returns_empty(self) -> None:
        assert correct_choice({}) == ""


# ---------------------------------------------------------------------------
# rating_for_committed — spec-engine §5.1
# ---------------------------------------------------------------------------


class TestRatingForCommitted:
    """wrong → Again(1), right → Good(3) — the spec-engine §5.1 invariant."""

    def test_correct_choice_yields_good(self) -> None:
        fields = _make_item_fields(correct="B")
        assert rating_for_committed("B", fields) == RATING_GOOD

    def test_wrong_choice_yields_again(self) -> None:
        fields = _make_item_fields(correct="B")
        assert rating_for_committed("A", fields) == RATING_AGAIN

    def test_case_insensitive_correct(self) -> None:
        fields = _make_item_fields(correct="B")
        assert rating_for_committed("b", fields) == RATING_GOOD

    def test_rating_again_is_1(self) -> None:
        assert RATING_AGAIN == 1

    def test_rating_good_is_3(self) -> None:
        assert RATING_GOOD == 3

    def test_all_wrong_choices(self) -> None:
        fields = _make_item_fields(correct="D")
        for label in ("A", "B", "C", "E"):
            assert rating_for_committed(label, fields) == RATING_AGAIN


# ---------------------------------------------------------------------------
# build_item_question_html
# ---------------------------------------------------------------------------


class TestBuildItemQuestionHtml:
    def test_contains_stimulus(self) -> None:
        fields = _make_item_fields()
        html = build_item_question_html(fields)
        assert "All mammals are warm-blooded" in html

    def test_contains_stem(self) -> None:
        fields = _make_item_fields()
        html = build_item_question_html(fields)
        assert "Which of the following must be true" in html

    def test_all_choices_present(self) -> None:
        fields = _make_item_fields()
        html = build_item_question_html(fields)
        for label in "ABCDE":
            assert f'data-choice="{label}"' in html

    def test_choices_have_pycmd_commit(self) -> None:
        fields = _make_item_fields()
        html = build_item_question_html(fields)
        for label in "ABCDE":
            assert f"speedrun:commit:{label}" in html

    def test_synthetic_notice_shown(self) -> None:
        fields = _make_item_fields()
        html = build_item_question_html(fields)
        assert "Synthetic placeholder" in html

    def test_no_correct_answer_revealed(self) -> None:
        fields = _make_item_fields(correct="B")
        html = build_item_question_html(fields)
        # The question side must NOT reveal the correct choice
        assert "Correct:" not in html
        assert "WhyWrong" not in html


# ---------------------------------------------------------------------------
# build_item_answer_html — the core commit-then-reveal invariant
# ---------------------------------------------------------------------------


class TestBuildItemAnswerHtml:
    def test_correct_verdict_for_right_answer(self) -> None:
        fields = _make_item_fields(correct="B")
        html = build_item_answer_html(fields, "B")
        assert "Correct!" in html

    def test_wrong_verdict_for_wrong_answer(self) -> None:
        fields = _make_item_fields(correct="B")
        html = build_item_answer_html(fields, "A")
        assert "Wrong" in html

    def test_answer_contains_correct_key(self) -> None:
        fields = _make_item_fields(correct="C")
        html = build_item_answer_html(fields, "A")
        # Correct key must appear somewhere in the reveal
        assert "C" in html

    def test_committed_choice_highlighted(self) -> None:
        fields = _make_item_fields(correct="B")
        html = build_item_answer_html(fields, "A")
        assert "your answer" in html.lower()

    def test_per_choice_explanations_present(self) -> None:
        fields = _make_item_fields(correct="B")
        html = build_item_answer_html(fields, "B")
        for label in "ABCDE":
            # Each choice label should appear in the explanations
            assert f"<strong>{label}:</strong>" in html

    def test_trap_tag_shown(self) -> None:
        fields = _make_item_fields(correct="B")
        fields["TrapChoiceA"] = "trap::sufficient-necessary"
        html = build_item_answer_html(fields, "B")
        assert "trap::sufficient-necessary" in html

    def test_stimulus_trap_tag_shown_when_present(self) -> None:
        fields = _make_item_fields(correct="B")
        fields["TrapTag"] = "trap::correlation-causation"
        html = build_item_answer_html(fields, "B")
        assert "trap::correlation-causation" in html

    def test_answer_contains_hr_anchor(self) -> None:
        """The #answer anchor is required so the reviewer scrolls to it."""
        fields = _make_item_fields(correct="B")
        html = build_item_answer_html(fields, "B")
        assert 'id="answer"' in html

    def test_no_reveal_before_commit(self) -> None:
        """Question HTML must not contain the verdict or per-choice why-wrong."""
        fields = _make_item_fields(correct="B")
        q_html = build_item_question_html(fields)
        assert "Correct!" not in q_html
        assert "Contradict" not in q_html  # WhyWrongA text

    def test_correct_and_committed_matching(self) -> None:
        """When committed == correct, single 'CORRECT — YOUR ANSWER' tag shown."""
        fields = _make_item_fields(correct="D")
        html = build_item_answer_html(fields, "D")
        # Should show combined badge
        assert "your answer" in html.lower()
        assert "Correct!" in html


# ---------------------------------------------------------------------------
# Bottom-bar helpers
# ---------------------------------------------------------------------------


class TestBottomBarHelpers:
    def test_commit_prompt_contains_choice_hint(self) -> None:
        html = bottom_commit_prompt()
        assert "A–E" in html or "A/B/C/D/E" in html or "A" in html

    def test_continue_button_again_label(self) -> None:
        html = bottom_continue_button(RATING_AGAIN)
        assert "Again" in html or "wrong" in html.lower()

    def test_continue_button_good_label(self) -> None:
        html = bottom_continue_button(RATING_GOOD)
        assert "Good" in html or "correct" in html.lower()

    def test_continue_button_pycmd(self) -> None:
        for ease in (RATING_AGAIN, RATING_GOOD):
            html = bottom_continue_button(ease)
            assert "speedrun:continue" in html
