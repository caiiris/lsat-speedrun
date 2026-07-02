# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
WP-22 — Unit tests for the pure-Python helpers in speedrun_session.py.

These tests are pure-Python (no Qt, no anki wheel).  They isolate the
helper functions by importing speedrun.py and speedrun_session.py via
importlib, patching out the Qt / aqt dependencies the same way the Qt
test runner would.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


# ---------------------------------------------------------------------------
# Bootstrap: load speedrun.py and speedrun_session.py without the anki wheel
# ---------------------------------------------------------------------------

def _load_module(path: Path, name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_QT = Path(__file__).resolve().parents[1]  # qt/

# 1. Load speedrun.py (no external deps)
_speedrun = _load_module(_QT / "aqt" / "speedrun.py", "speedrun_wp21")

# 2. Stub the Qt + aqt imports so speedrun_session.py can be loaded
def _make_stub(name: str) -> types.ModuleType:
    m = types.ModuleType(name)
    sys.modules[name] = m
    return m


for _name in (
    "aqt",
    "aqt.main",
    "aqt.qt",
    "aqt.utils",
    "aqt.webview",
    "aqt.speedrun",
):
    if _name not in sys.modules:
        _make_stub(_name)

# Point aqt.speedrun at the real speedrun module
sys.modules["aqt.speedrun"] = _speedrun  # type: ignore[assignment]

# Stub QDialog, Qt, QTimer in aqt.qt
_qt = sys.modules["aqt.qt"]
_qt.QDialog = object  # type: ignore[attr-defined]
_qt.Qt = types.SimpleNamespace(WindowType=types.SimpleNamespace(Window=0))  # type: ignore[attr-defined]
_qt.QTimer = object  # type: ignore[attr-defined]

# Stub aqt.utils helpers
_utils = sys.modules["aqt.utils"]
_utils.disable_help_button = lambda *a, **kw: None  # type: ignore[attr-defined]
_utils.restoreGeom = lambda *a, **kw: None  # type: ignore[attr-defined]
_utils.saveGeom = lambda *a, **kw: None  # type: ignore[attr-defined]
_utils.tr = types.SimpleNamespace()  # type: ignore[attr-defined]

# Stub aqt.webview
_webview = sys.modules["aqt.webview"]
_webview.AnkiWebView = object  # type: ignore[attr-defined]
_webview.AnkiWebViewKind = types.SimpleNamespace(MAIN=0)  # type: ignore[attr-defined]

# 3. Load speedrun_session.py
_session = _load_module(_QT / "aqt" / "speedrun_session.py", "speedrun_session_wp22")


# ---------------------------------------------------------------------------
# Helpers (re-use from the loaded modules)
# ---------------------------------------------------------------------------

_format_elapsed = _session._format_elapsed  # type: ignore[attr-defined]
_build_progress_header = _session._build_progress_header  # type: ignore[attr-defined]
_build_result_html = _session._build_result_html  # type: ignore[attr-defined]
SessionState = _session.SessionState  # type: ignore[attr-defined]
ItemResult = _session.ItemResult  # type: ignore[attr-defined]
SESSION_SIZES = _session.SESSION_SIZES  # type: ignore[attr-defined]


def _make_item_fields(correct: str = "B") -> dict:
    return {
        "Stimulus": "All mammals are warm-blooded.",
        "Stem": "Which must be true?",
        "ChoiceA": "Dogs are cold-blooded.",
        "ChoiceB": "Dogs are warm-blooded.",
        "ChoiceC": "All warm-blooded animals are dogs.",
        "ChoiceD": "No mammals are warm-blooded.",
        "ChoiceE": "Some dogs are mammals.",
        "CorrectChoice": correct,
        "WhyWrongA": "Contradicts premise.",
        "WhyWrongB": "Follows from premises.",
        "WhyWrongC": "Converse error.",
        "WhyWrongD": "Negates premise.",
        "WhyWrongE": "True but not must-be-true.",
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
        "SyntheticFlag": "",
    }


def _make_state(
    mode: str = "targeted",
    n_results: int = 3,
    n_correct: int = 2,
) -> "SessionState":
    state = SessionState(
        mode=mode,
        focus_skill="type::assumption",
        label="Assumption family · drill",
        card_ids=list(range(1, n_results + 1)),
        current_index=n_results,
    )
    fields = _make_item_fields()
    for i in range(n_results):
        is_corr = i < n_correct
        state.results.append(
            ItemResult(
                index=i + 1,
                card_id=i + 1,
                item_fields=fields,
                committed="B" if is_corr else "A",
                correct="B",
                is_correct=is_corr,
                trap_missed="" if is_corr else "trap::correlation-causation",
            )
        )
    return state


# ---------------------------------------------------------------------------
# _format_elapsed
# ---------------------------------------------------------------------------


class TestFormatElapsed:
    def test_zero(self) -> None:
        assert _format_elapsed(0) == "0:00 elapsed"

    def test_seconds_only(self) -> None:
        assert _format_elapsed(45) == "0:45 elapsed"

    def test_one_minute(self) -> None:
        assert _format_elapsed(60) == "1:00 elapsed"

    def test_mixed(self) -> None:
        assert _format_elapsed(125) == "2:05 elapsed"


# ---------------------------------------------------------------------------
# _build_progress_header
# ---------------------------------------------------------------------------


class TestBuildProgressHeader:
    def test_shows_question_number(self) -> None:
        html = _build_progress_header(3, 10, "Drill", "targeted")
        assert "3" in html
        assert "10" in html

    def test_shows_label(self) -> None:
        html = _build_progress_header(1, 5, "Mixed set", "mixed")
        assert "Mixed set" in html

    def test_timed_mode_has_timer_script(self) -> None:
        html = _build_progress_header(1, 25, "Timed section", "timed")
        assert "setInterval" in html

    def test_non_timed_also_has_live_ticker(self) -> None:
        # The elapsed clock now ticks live in all modes (was static/frozen).
        html = _build_progress_header(1, 10, "Drill", "targeted")
        assert "setInterval" in html

    def test_clock_seeded_with_elapsed_offset(self) -> None:
        # Continuous across renders: JS start is offset by elapsed (ms).
        html = _build_progress_header(3, 10, "Drill", "targeted", elapsed_seconds=46.0)
        assert "Date.now() - 46000" in html


# ---------------------------------------------------------------------------
# SESSION_SIZES
# ---------------------------------------------------------------------------


class TestSessionSizes:
    def test_targeted_is_10(self) -> None:
        assert SESSION_SIZES["targeted"] == 10

    def test_mixed_is_10(self) -> None:
        assert SESSION_SIZES["mixed"] == 10

    def test_timed_is_25(self) -> None:
        assert SESSION_SIZES["timed"] == 25


# ---------------------------------------------------------------------------
# _build_result_html
# ---------------------------------------------------------------------------


class TestAssembleCardIdsTargetedRepeat:
    """B036 fix: a targeted drill re-serves the single focus skill card N times."""

    class _FakeCol:
        def __init__(self, matched: list[int]) -> None:
            self._matched = matched

        def find_cards(self, query: str) -> list[int]:
            # Only the IdentityTag-filtered search is exercised in these tests.
            return self._matched

    class _FakeMw:
        def __init__(self, col: object) -> None:
            self.col = col

    def _assemble(self, matched: list[int], focus: str):
        mw = self._FakeMw(self._FakeCol(matched))
        return _session._assemble_card_ids(mw, 1, "targeted", focus)  # type: ignore[attr-defined]

    def test_single_skill_card_fills_session(self) -> None:
        # One matching skill card → repeated up to the targeted session size.
        ids = self._assemble([101], "type::flaw")
        assert ids == [101] * SESSION_SIZES["targeted"]
        assert len(ids) == 10  # was 1 before the fix

    def test_multiple_matches_cycle(self) -> None:
        ids = self._assemble([101, 102], "type::principle")
        assert len(ids) == SESSION_SIZES["targeted"]
        assert ids[:4] == [101, 102, 101, 102]


class TestBuildResultHtml:
    def test_shows_score(self) -> None:
        state = _make_state(n_results=5, n_correct=4)
        html = _build_result_html(state, 120.0)
        assert "4 / 5 correct" in html

    def test_shows_session_complete(self) -> None:
        state = _make_state()
        html = _build_result_html(state, 60.0)
        assert "complete" in html.lower()

    def test_shows_where_slipped_on_miss(self) -> None:
        state = _make_state(n_results=3, n_correct=2)
        html = _build_result_html(state, 60.0)
        assert "Where you slipped" in html
        # Trap chip for missed item
        assert "Correlation" in html or "correlation" in html

    def test_no_miss_no_slipped_items(self) -> None:
        state = _make_state(n_results=3, n_correct=3)
        html = _build_result_html(state, 60.0)
        # All correct: Where you slipped section present but shows no slip rows
        assert "No misses" in html

    def test_blind_review_button_shown_on_miss(self) -> None:
        state = _make_state(n_results=5, n_correct=3)
        html = _build_result_html(state, 90.0)
        assert "Blind review" in html
        assert "speedrun:blind-review" in html

    def test_no_blind_review_button_on_perfect(self) -> None:
        state = _make_state(n_results=5, n_correct=5)
        html = _build_result_html(state, 90.0)
        assert "speedrun:blind-review" not in html

    def test_all_items_strip_present(self) -> None:
        state = _make_state(n_results=4, n_correct=3)
        html = _build_result_html(state, 90.0)
        assert "All 4 questions" in html

    def test_flag_stars_present(self) -> None:
        state = _make_state(n_results=3, n_correct=2)
        html = _build_result_html(state, 60.0)
        assert "speedrun:flag:" in html

    def test_back_to_study_plan_button(self) -> None:
        state = _make_state()
        html = _build_result_html(state, 60.0)
        assert "speedrun:home" in html

    def test_another_drill_button(self) -> None:
        state = _make_state()
        html = _build_result_html(state, 60.0)
        assert "speedrun:another-drill" in html

    def test_elapsed_time_shown(self) -> None:
        state = _make_state()
        html = _build_result_html(state, 742.0)  # 12:22
        assert "12:22" in html

    def test_score_100_pct_green_donut(self) -> None:
        state = _make_state(n_results=5, n_correct=5)
        html = _build_result_html(state, 60.0)
        # 100% should show green donut color
        from speedrun_wp21 import _C_GREEN  # type: ignore[import]
        assert _C_GREEN in html

    def test_score_low_red_donut(self) -> None:
        state = _make_state(n_results=5, n_correct=1)
        html = _build_result_html(state, 60.0)
        from speedrun_wp21 import _C_CLAY  # type: ignore[import]
        assert _C_CLAY in html
