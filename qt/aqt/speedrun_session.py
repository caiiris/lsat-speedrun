# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Speedrun WP-22 — Session layer: bounded drill session + result + blind review.

Opens a full-page Qt dialog that drives a complete study session:

  1. Assembles a bounded card queue from the LSAT Speedrun deck.
  2. Runs each item through the WP-21 drill interaction (prephrase →
     choices → reveal) *without touching mw.reviewer*.
  3. Records per-item outcome (correct/wrong, trap missed, item fields).
  4. Shows the set-result screen (spec-ui §3.3, lr-set-result-mockup.png).
  5. Supports "Blind review your misses" as a nested blind-review session.

Session modes (D-SR35):
  targeted  — ≤10 items drawn from the LSAT Speedrun deck (focus skill
               shown in header; FSRS queue naturally surfaces the weakest
               skill first; true per-skill pre-filtering is a B-list item
               because it would require a filtered deck — documented in
               WP-22-log.md as L3).
  mixed     — ≤10 items, standard FSRS queue order (naturally interleaved
               because the deck uses InterleavedSkills order, D-SR6).
  timed     — ≤25 items, choices-only (no prephrase), running clock.
  blind     — re-runs session misses untimed (nested; triggered from the
               result screen, not from Home directly).

Hard invariants (spec-ui §0 / D-SR33):
  - Normal Anki study is UNAFFECTED: the session dialog uses its own
    AnkiWebView and is gated on LSAT Speedrun notetypes.
  - Every item is answered via answer_card() (FSRS/undo/sync intact).
  - Session accuracy is display-only; Performance/Memory/Readiness still
    come from the engine (revlog + SpeedrunDashboard).
  - No Rust / proto / schema changes.

Bridge commands handled (same tag protocol as reviewer.py):
  speedrun:prephrase:reveal  — read prephrase input, transition to choices
  speedrun:prephrase:skip    — skip prephrase, go to choices
  speedrun:commit:<A-E>      — commit choice, transition to reveal
  speedrun:trap:<tag>        — name-the-trap chip selected
  speedrun:continue          — answer card + advance to next item or result
  speedrun:flag:<index>      — toggle flag-to-revisit on item at 1-based index
  speedrun:blind-review      — start blind review of missed/flagged items
  speedrun:another-drill     — dismiss dialog (caller may re-open a new session)
  speedrun:home              — dismiss dialog, return to Home
"""
from __future__ import annotations

import html
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import aqt
import aqt.main
from aqt.qt import (
    QDialog,
    Qt,
    QTimer,
)
from aqt.utils import disable_help_button, restoreGeom, saveGeom
from aqt.webview import AnkiWebView, AnkiWebViewKind

# Speedrun helpers from WP-21 (no Qt, pure Python — safe to import here)
from aqt.speedrun import (
    LSAT_ITEM_NOTETYPE,
    LSAT_SKILL_NOTETYPE,
    RATING_AGAIN,
    RATING_GOOD,
    build_choices_html,
    build_prephrase_html,
    build_reveal_html,
    correct_choice,
    get_item_fields,
    rating_for_committed,
    speedrun_card_type,
    _SHARED_CSS,  # noqa: WPS437 — internal, but needed for result screen
    _C_BG,
    _C_CARD,
    _C_INK,
    _C_INDIGO,
    _C_GREEN,
    _C_CLAY,
    _C_AMBER,
    _C_BORDER,
    TRAP_DISPLAY_NAMES,
)

# ---------------------------------------------------------------------------
# Session constants (D-SR35 — tunable dev defaults)
# ---------------------------------------------------------------------------

SESSION_SIZES: dict[str, int] = {
    "targeted": 10,
    "mixed": 10,
    "timed": 25,
    "blind": 25,  # upper-bound on blind review; in practice len(misses) ≤ N
}

_GEOM_KEY = "speedrunSession"

# Deck name sentinel
_SPEEDRUN_DECK_NAME = "LSAT Speedrun"


# ---------------------------------------------------------------------------
# Per-item result record
# ---------------------------------------------------------------------------


@dataclass
class ItemResult:
    """Outcome of a single session item."""

    index: int          # 1-based position in the session
    card_id: int        # the LSAT Skill card that was answered
    item_fields: dict[str, str]  # LSAT Item fields (for result screen / blind review)
    committed: str      # choice the learner locked in (A–E)
    correct: str        # ground-truth correct choice from item fields
    is_correct: bool    # committed == correct
    trap_missed: str    # trap tag for the committed wrong choice (empty if correct)
    flagged: bool = False  # learner tapped the revisit star on the result screen


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------


@dataclass
class SessionState:
    """All mutable session state, shared across the drill loop."""

    mode: str                           # 'targeted'|'mixed'|'timed'|'blind'
    focus_skill: str                    # e.g. 'type::assumption', or '' for mixed/timed
    label: str                          # human-readable session label
    card_ids: list[int]                 # ordered list of skill card IDs to study
    current_index: int = 0              # 0-based index into card_ids

    # Per-item state (reset each card)
    v3_states: Any = None               # SchedulingStates from get_queued_cards
    current_card: Any = None            # anki.cards.Card
    current_item_fields: dict[str, str] | None = None
    committed: str | None = None
    prephrase_text: str | None = None   # None = skipped; "" = submitted empty
    trap_chosen: str | None = None
    trap_result: str | None = None

    # Accumulated results (one per answered item)
    results: list[ItemResult] = field(default_factory=list)

    # Timer (timed mode)
    start_time: float = field(default_factory=time.monotonic)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _esc(s: str) -> str:
    return html.escape(s, quote=False)


def _find_speedrun_deck_id(mw: aqt.main.AnkiQt) -> int:
    if not mw.col:
        return 1
    try:
        for d in mw.col.decks.all_names_and_ids():
            if d.name.startswith(_SPEEDRUN_DECK_NAME):
                return int(d.id)
        deck = mw.col.decks.get_current()
        if deck:
            return int(deck["id"])
    except Exception:
        pass
    return 1


def _trap_display(tag: str) -> str:
    return TRAP_DISPLAY_NAMES.get(
        tag, tag.removeprefix("trap::").replace("-", " ").title()
    )


def _assemble_card_ids(
    mw: aqt.main.AnkiQt,
    deck_id: int,
    mode: str,
    focus_skill: str,
) -> list[int]:
    """Return a list of LSAT Skill card IDs to study for this session.

    Uses col.find_cards() with a search query.  For targeted drill we
    additionally filter by the focus skill's IdentityTag field.  The
    results are sorted by due date (ascending) so the most overdue /
    highest-priority cards appear first.

    Limitation (documented in WP-22-log L3): LSAT Skill notes store the
    identity tag in the IdentityTag field, but find_cards() field search
    requires an exact match which is not easily done for sub-strings.  We
    use Anki's "field:value" syntax; if the IdentityTag field contains
    exactly the focus_skill value this matches.  In practice it does —
    the build_seed_deck.py sets IdentityTag to the canonical tag string.
    """
    col = mw.col
    if col is None:
        return []

    limit = SESSION_SIZES.get(mode, 10)

    try:
        if mode == "targeted" and focus_skill:
            # Search for the skill card(s) whose IdentityTag matches the focus
            # skill.  There is exactly ONE LSAT Skill card per skill (data
            # contract: 38 skill notes), so this normally matches a single card.
            search = f'deck:"{_SPEEDRUN_DECK_NAME}" note:"{LSAT_SKILL_NOTETYPE}" IdentityTag:"{focus_skill}"'
            matched = list(col.find_cards(search))
            if matched:
                # B036 fix: a targeted drill reviews that skill card `limit`
                # times, drawing a FRESH item each rep (the *skill* is the FSRS
                # unit — D-SR3 — not the item).  Previously we returned the
                # distinct matched cards, so a single-skill drill was only one
                # question long.  If the focus resolved to several cards (a
                # subtype), cycle through them to fill the session.
                return [matched[i % len(matched)] for i in range(limit)]
            # No exact IdentityTag match — fall through to unfiltered skill cards.

        # mixed / timed (or targeted fallback): distinct skill cards, ordered by
        # due (most overdue first), which approximates the FSRS queue order
        # without mutating scheduler state.
        search = f'deck:"{_SPEEDRUN_DECK_NAME}" note:"{LSAT_SKILL_NOTETYPE}"'
        card_ids = list(col.find_cards(search))
        if card_ids:
            rows = col.db.all(
                "SELECT id, due FROM cards WHERE id IN ({}) ORDER BY due ASC".format(
                    ",".join(str(c) for c in card_ids)
                )
            )
            card_ids = [r[0] for r in rows]
        return card_ids[:limit]

    except Exception as exc:
        print(f"[Speedrun WP-22] _assemble_card_ids failed: {exc}")
        return []


# ---------------------------------------------------------------------------
# Progress header HTML (injected above each drill item)
# ---------------------------------------------------------------------------


def _build_progress_header(
    current: int,
    total: int,
    label: str,
    mode: str,
    elapsed_seconds: float = 0.0,
    timed_timer_id: str = "sr-timer",
) -> str:
    """Thin top bar: 'Label  ·  Q X of N  [live elapsed clock]'.

    The elapsed clock ticks live (JS, every second) in *all* modes.  It is
    seeded with ``elapsed_seconds`` as an offset so the clock stays **continuous
    across page transitions** (prephrase → choices → reveal → next question)
    rather than resetting or freezing on each render.  Timed mode renders it
    prominently (amber/bold); other modes render it muted.
    """
    progress_pct = int((current / max(total, 1)) * 100)

    # Offset (ms) so the JS clock resumes from the session's elapsed time on
    # each fresh render instead of restarting at 0.
    offset_ms = int(max(elapsed_seconds, 0.0) * 1000)
    is_timed = mode == "timed"
    timer_color = _C_AMBER if is_timed else "#888"
    timer_weight = "700" if is_timed else "400"
    timer_size = "0.9em" if is_timed else "0.85em"

    timer_html = (
        f'<span id="{timed_timer_id}" style="font-family:monospace;'
        f'font-size:{timer_size};color:{timer_color};font-weight:{timer_weight};'
        f'margin-left:auto;"></span>'
        f"<script>\n"
        f"(function(){{\n"
        f"  var start = Date.now() - {offset_ms};\n"
        f"  var el = document.getElementById('{timed_timer_id}');\n"
        f"  function tick(){{\n"
        f"    var s = Math.floor((Date.now()-start)/1000);\n"
        f"    var m = Math.floor(s/60); var ss = s%60;\n"
        f"    if(el) el.textContent = m+':'+(ss<10?'0':'')+ss+' elapsed';\n"
        f"  }}\n"
        f"  setInterval(tick, 1000);\n"
        f"  tick();\n"
        f"}})();\n"
        f"</script>\n"
    )

    return (
        f'<div style="display:flex;align-items:center;gap:12px;'
        f'padding:10px 18px;background:{_C_CARD};border-bottom:1px solid {_C_BORDER};'
        f'font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,sans-serif;'
        f'font-size:0.88em;color:#555;position:sticky;top:0;z-index:100;">\n'
        f'<span style="font-weight:600;color:{_C_INDIGO};">{_esc(label)}</span>\n'
        f'<span style="color:#bbb;">·</span>\n'
        f'<span>Question <strong>{current}</strong> of <strong>{total}</strong></span>\n'
        # Progress bar
        f'<div style="flex:1;max-width:140px;height:4px;background:#E5E7EB;'
        f'border-radius:2px;overflow:hidden;">'
        f'<div style="width:{progress_pct}%;height:100%;background:{_C_INDIGO};'
        f'border-radius:2px;transition:width 0.3s;"></div>'
        f"</div>\n"
        f"{timer_html}"
        f"</div>\n"
    )


def _format_elapsed(seconds: float) -> str:
    s = int(seconds)
    m = s // 60
    s = s % 60
    return f"{m}:{s:02d} elapsed"


# ---------------------------------------------------------------------------
# Result screen HTML
# ---------------------------------------------------------------------------


def _build_result_html(state: SessionState, elapsed: float) -> str:
    """Full set-result screen (spec-ui §3.3, lr-set-result-mockup.png)."""
    results = state.results
    total = len(results)
    correct_count = sum(1 for r in results if r.is_correct)
    score_pct = int((correct_count / max(total, 1)) * 100)
    miss_count = total - correct_count

    elapsed_str = _format_elapsed(elapsed)

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    label_safe = _esc(state.label)
    header = (
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'padding:14px 20px;background:{_C_CARD};border-bottom:1px solid {_C_BORDER};">'
        f'<span style="font-weight:600;color:{_C_INDIGO};font-family:-apple-system,sans-serif;">'
        f"{label_safe} — complete"
        f"</span>"
        f'<span style="font-family:monospace;font-size:0.88em;color:#888;">'
        f"{_esc(elapsed_str)}"
        f"</span>"
        f"</div>\n"
    )

    # ------------------------------------------------------------------
    # Score card (left)
    # ------------------------------------------------------------------
    # Donut SVG: a simple circle arc
    radius = 42
    circumference = 2 * 3.14159 * radius
    dash = circumference * score_pct / 100
    gap = circumference - dash
    # Color: green if >=70%, amber if >=50%, clay if <50%
    donut_color = _C_GREEN if score_pct >= 70 else (_C_AMBER if score_pct >= 50 else _C_CLAY)

    donut_svg = (
        f'<svg width="110" height="110" viewBox="-60 -60 120 120" '
        f'style="transform:rotate(-90deg);" aria-hidden="true">'
        f'<circle r="{radius}" fill="none" stroke="#E5E7EB" stroke-width="10"/>'
        f'<circle r="{radius}" fill="none" stroke="{donut_color}" stroke-width="10" '
        f'stroke-dasharray="{dash:.1f} {gap:.1f}" stroke-linecap="round"/>'
        f'</svg>'
        f'<div style="position:absolute;inset:0;display:flex;align-items:center;'
        f'justify-content:center;flex-direction:column;">'
        f'<span style="font-size:1.1em;font-weight:700;color:{_C_INDIGO};">{score_pct}%</span>'
        f'<span style="font-size:0.7em;color:#888;">correct</span>'
        f"</div>"
    )

    wit_text = ""
    if miss_count == 0:
        wit_text = "clean sweep — no misses"
    elif miss_count == 1:
        wit_text = "one to revisit"
    else:
        wit_text = f"nice — the misses are where the points are"

    score_card = (
        f'<div style="background:{_C_CARD};border:1px solid {_C_BORDER};border-radius:12px;'
        f'padding:24px 28px;flex:1;min-width:260px;">'
        # Big score number
        f'<div style="font-size:2.6em;font-weight:700;color:{_C_INK};font-family:-apple-system,sans-serif;'
        f'letter-spacing:-0.02em;margin-bottom:4px;">'
        f"{correct_count} / {total} correct"
        f"</div>"
        # Sub-line (performance delta — session-local only)
        f'<div style="font-size:0.85em;color:#888;margin-bottom:16px;">'
        f"Session score (display only — Performance comes from the engine)"
        f"</div>"
        # Donut + wit-text row
        f'<div style="display:flex;align-items:center;gap:20px;">'
        f'<div style="position:relative;width:110px;height:110px;flex-shrink:0;">'
        f"{donut_svg}"
        f"</div>"
        f'<div style="font-style:italic;color:#888;font-size:0.93em;font-family:Georgia,serif;">'
        f"{_esc(wit_text)}"
        f"</div>"
        f"</div>"
        f"</div>"
    )

    # ------------------------------------------------------------------
    # Where you slipped (right)
    # ------------------------------------------------------------------
    misses = [r for r in results if not r.is_correct]

    if misses:
        slip_rows = ""
        for r in misses:
            trap_display = _trap_display(r.trap_missed) if r.trap_missed else "—"
            trap_chip_style = (
                f"display:inline-block;background:{_C_AMBER};color:#fff;"
                f"font-family:monospace;font-size:0.8em;padding:2px 8px;border-radius:4px;"
                f"font-weight:600;"
            )
            # Item title from Stimulus first ~40 chars
            stimulus_short = r.item_fields.get("Stimulus", "")[:55]
            if len(r.item_fields.get("Stimulus", "")) > 55:
                stimulus_short += "…"

            slip_rows += (
                f'<div style="display:flex;align-items:flex-start;gap:10px;'
                f'padding:10px 0;border-bottom:1px solid {_C_BORDER};">'
                # Q number
                f'<span style="font-weight:700;color:{_C_CLAY};font-size:0.9em;'
                f'min-width:28px;padding-top:1px;">Q{r.index}</span>'
                # Content
                f'<div style="flex:1;">'
                f'<div style="font-size:0.88em;color:{_C_INK};margin-bottom:3px;">'
                f"{_esc(stimulus_short)}"
                f"</div>"
                f'<div style="font-size:0.8em;color:#888;">'
                f"fell for: <span style=\"{trap_chip_style}\">{_esc(trap_display)}</span>"
                f"</div>"
                f"</div>"
                f"</div>"
            )

        where_slipped = (
            f'<div style="background:{_C_CARD};border:1px solid {_C_BORDER};border-radius:12px;'
            f'padding:20px 22px;flex:1;min-width:240px;">'
            f'<div style="font-size:1em;font-weight:700;color:{_C_INK};margin-bottom:12px;">'
            f"Where you slipped"
            f"</div>"
            f"{slip_rows}"
            f"</div>"
        )
    else:
        where_slipped = (
            f'<div style="background:{_C_CARD};border:1px solid {_C_BORDER};border-radius:12px;'
            f'padding:20px 22px;flex:1;min-width:240px;">'
            f'<div style="font-size:1em;font-weight:700;color:{_C_INK};margin-bottom:10px;">'
            f"Where you slipped"
            f"</div>"
            f'<div style="font-size:0.9em;color:{_C_GREEN};font-weight:600;">'
            f"\u2713 No misses — excellent work!"
            f"</div>"
            f"</div>"
        )

    # ------------------------------------------------------------------
    # All-items strip with flag-to-revisit stars
    # ------------------------------------------------------------------
    item_chips = ""
    for r in results:
        border_color = _C_GREEN if r.is_correct else _C_CLAY
        text_color = _C_GREEN if r.is_correct else _C_CLAY
        # Star: filled if flagged
        star_char = "\u2605" if r.flagged else "\u2606"
        star_color = _C_AMBER if r.flagged else "#ccc"
        item_chips += (
            f'<div id="sr-item-{r.index}" '
            f'style="display:flex;flex-direction:column;align-items:center;gap:4px;">'
            f'<div style="width:42px;height:42px;border-radius:8px;'
            f'border:2px solid {border_color};display:flex;align-items:center;'
            f'justify-content:center;font-weight:700;font-size:0.95em;color:{text_color};">'
            f"{r.index}"
            f"</div>"
            f'<span onclick="pycmd(\'speedrun:flag:{r.index}\');" '
            f'id="sr-star-{r.index}" '
            f'style="font-size:1.2em;cursor:pointer;color:{star_color};'
            f'user-select:none;" title="Flag to revisit">'
            f"{star_char}"
            f"</span>"
            f"</div>"
        )

    all_items_strip = (
        f'<div style="background:{_C_CARD};border:1px solid {_C_BORDER};border-radius:12px;'
        f'padding:18px 22px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'margin-bottom:14px;">'
        f'<span style="font-weight:600;color:{_C_INK};">All {total} questions</span>'
        f'<span style="font-size:0.8em;color:#888;">\u2606 Tap a star to flag a question to revisit</span>'
        f"</div>"
        f'<div style="display:flex;flex-wrap:wrap;gap:10px;">'
        f"{item_chips}"
        f"</div>"
        f"</div>"
    )

    # ------------------------------------------------------------------
    # Flag update script (replaces star in-place without page reload)
    # ------------------------------------------------------------------
    flag_script = (
        f"<script>\n"
        f"function srUpdateStar(idx, flagged){{\n"
        f"  var el=document.getElementById('sr-star-'+idx);\n"
        f"  if(!el) return;\n"
        f"  el.textContent=flagged?'\\u2605':'\\u2606';\n"
        f"  el.style.color=flagged?'{_C_AMBER}':'#ccc';\n"
        f"}}\n"
        f"</script>\n"
    )

    # ------------------------------------------------------------------
    # CTA buttons
    # ------------------------------------------------------------------
    if miss_count > 0:
        blind_btn = (
            f'<button onclick="pycmd(\'speedrun:blind-review\');" '
            f'style="background:{_C_INDIGO};color:#fff;border:none;'
            f'padding:13px 28px;border-radius:8px;font-size:1.02em;font-weight:700;'
            f'cursor:pointer;display:flex;align-items:center;gap:8px;">'
            f"Blind review your {miss_count} miss{'es' if miss_count != 1 else ''} \u2192"
            f"</button>"
            f'<div style="font-size:0.75em;color:{_C_AMBER};letter-spacing:0.06em;'
            f'font-weight:700;margin-top:5px;">\u2606 RECOMMENDED NEXT STEP</div>'
        )
    else:
        blind_btn = ""

    another_btn = (
        f'<button onclick="pycmd(\'speedrun:another-drill\');" '
        f'style="border:2px solid {_C_INDIGO};color:{_C_INDIGO};background:{_C_CARD};'
        f'padding:12px 24px;border-radius:8px;font-size:0.98em;font-weight:600;'
        f'cursor:pointer;">'
        f"Another drill"
        f"</button>"
    )

    home_link = (
        f'<button onclick="pycmd(\'speedrun:home\');" '
        f'style="background:none;border:none;color:{_C_INDIGO};font-size:0.93em;'
        f'cursor:pointer;text-decoration:underline;padding:0;">'
        f"Back to study plan"
        f"</button>"
    )

    note_text = (
        f'<div style="font-size:0.78em;color:#999;margin-top:12px;text-align:center;">'
        f"\u24d8 Blind review re-runs your misses untimed \u2014 decide again before seeing the key."
        f"</div>"
    )

    cta_row = (
        f'<div style="display:flex;flex-wrap:wrap;align-items:center;gap:14px;margin-top:4px;">'
        f'<div style="display:flex;flex-direction:column;align-items:flex-start;">'
        f"{blind_btn}"
        f"</div>"
        f"{another_btn}"
        f"{home_link}"
        f"</div>"
        f"{note_text}"
    )

    # ------------------------------------------------------------------
    # Assembly
    # ------------------------------------------------------------------
    body = (
        f'<div style="padding:18px 20px;max-width:960px;margin:0 auto;'
        f'display:flex;flex-direction:column;gap:16px;">'
        # Score + Where-slipped row
        f'<div style="display:flex;gap:16px;flex-wrap:wrap;">'
        f"{score_card}"
        f"{where_slipped}"
        f"</div>"
        # All-items strip
        f"{all_items_strip}"
        # CTA
        f"{cta_row}"
        f"</div>"
    )

    return (
        _SHARED_CSS
        + f'<div style="font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,sans-serif;'
        + f'background:{_C_BG};min-height:100vh;">'
        + header
        + body
        + flag_script
        + "</div>"
    )


# ---------------------------------------------------------------------------
# Wrap an existing drill HTML fragment with the progress header
# ---------------------------------------------------------------------------


def _wrap_with_progress(
    drill_html: str,
    state: SessionState,
    elapsed: float = 0.0,
) -> str:
    """Prepend the progress header bar to drill HTML."""
    current = state.current_index + 1
    total = len(state.card_ids)
    header = _build_progress_header(
        current, total, state.label, state.mode, elapsed
    )
    # The drill HTML starts with the _SHARED_CSS <style> block; insert the
    # header after it.
    style_end = drill_html.find("</style>")
    if style_end != -1:
        insert_at = style_end + len("</style>")
        return drill_html[:insert_at] + "\n" + header + drill_html[insert_at:]
    return header + drill_html


# ---------------------------------------------------------------------------
# Session dialog
# ---------------------------------------------------------------------------


class SpeedrunSessionDialog(QDialog):
    """
    Full-page session dialog (WP-22).

    Drives the drill loop, captures results, and shows the set-result +
    blind-review screens.  Does NOT use mw.reviewer.
    """

    def __init__(
        self,
        mw: aqt.main.AnkiQt,
        *,
        mode: str = "targeted",
        focus_skill: str = "",
        deck_id: int | None = None,
        blind_items: list[ItemResult] | None = None,
    ) -> None:
        super().__init__(mw, Qt.WindowType.Window)
        mw.garbage_collect_on_dialog_finish(self)
        self.mw = mw
        self.name = _GEOM_KEY
        self._blind_items = blind_items  # non-None → blind review mode

        # Resolve deck_id
        self._deck_id = deck_id if deck_id is not None else _find_speedrun_deck_id(mw)

        # Human-readable label
        if mode == "blind":
            label = "Blind review"
        elif mode == "targeted" and focus_skill:
            skill_short = focus_skill.replace("type::", "").replace("-", " ").title()
            label = f"{skill_short} family · drill"
        elif mode == "mixed":
            label = "Mixed set"
        elif mode == "timed":
            label = "Timed section"
        else:
            label = "Drill"

        # Assemble card queue
        if blind_items is not None:
            # Blind review: the card IDs come from the missed items
            card_ids = [r.card_id for r in blind_items]
        else:
            card_ids = _assemble_card_ids(mw, self._deck_id, mode, focus_skill)

        self._state = SessionState(
            mode=mode,
            focus_skill=focus_skill,
            label=label,
            card_ids=card_ids,
        )

        self.setWindowTitle(f"Speedrun — {label}")
        disable_help_button(self)
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        restoreGeom(self, self.name, default_size=(1040, 720))

        from aqt.qt import QVBoxLayout

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.web = AnkiWebView(kind=AnkiWebViewKind.MAIN)
        layout.addWidget(self.web)
        self.web.set_bridge_command(self._on_bridge_cmd, self)

        # Load first item (or show empty-state if no cards)
        self._start_session()
        self.show()
        self.activateWindow()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def _start_session(self) -> None:
        """Show the first item or an empty state if the queue is empty."""
        if not self._state.card_ids:
            self._show_empty_state()
            return
        self._state.start_time = time.monotonic()
        self._load_current_item()

    def _load_current_item(self) -> None:
        """Load the card at the current index and show the prephrase / choices phase."""
        state = self._state
        if state.current_index >= len(state.card_ids):
            self._show_result_screen()
            return

        card_id = state.card_ids[state.current_index]

        # Reset per-item state
        state.current_card = None
        state.current_item_fields = None
        state.committed = None
        state.prephrase_text = None
        state.trap_chosen = None
        state.trap_result = None
        state.v3_states = None

        # Ensure the Speedrun deck is current so get_queued_cards() serves it
        try:
            from anki.decks import DeckId
            self.mw.col.decks.select(DeckId(self._deck_id))
        except Exception as exc:
            print(f"[Speedrun WP-22] decks.select failed: {exc}")

        # Load the card object
        try:
            from anki.cards import Card
            state.current_card = self.mw.col.get_card(card_id)
            # Start the card timer so answer_card()'s time_taken() is valid.
            # (Without this, time_taken() reads an unset timer_started.)
            state.current_card.start_timer()
        except Exception as exc:
            print(f"[Speedrun WP-22] get_card({card_id}) failed: {exc}")
            self._advance_to_next()
            return

        card = state.current_card
        card_kind = speedrun_card_type(card.note_type())

        if card_kind == "skill":
            item_fields = self._draw_item_fields(card_id)
            if item_fields is None:
                # Pool empty — skip this card silently
                self._advance_to_next()
                return
            state.current_item_fields = item_fields
        elif card_kind == "item":
            try:
                state.current_item_fields = get_item_fields(card.note())
            except Exception:
                self._advance_to_next()
                return
        else:
            # Non-Speedrun card — skip
            self._advance_to_next()
            return

        # Get V3 states for answering (using get_queued_cards)
        self._fetch_v3_states(card_id)

        # Show drill (prephrase or choices based on mode)
        self._show_drill_question()

    def _draw_item_fields(self, skill_card_id: int) -> dict[str, str] | None:
        """Call draw_item_for_skill and return the drawn item's fields."""
        from anki.notes import NoteId
        from anki.scheduler.v3 import Scheduler as V3Scheduler

        sched = self.mw.col.sched
        if not isinstance(sched, V3Scheduler):
            return None
        try:
            item_note_id: int = sched.draw_item_for_skill(skill_card_id)
            if not item_note_id:
                return None
            item_note = self.mw.col.get_note(NoteId(item_note_id))
            if item_note.note_type()["name"] != LSAT_ITEM_NOTETYPE:
                return None
            return get_item_fields(item_note)
        except Exception as exc:
            print(f"[Speedrun WP-22] draw_item_for_skill failed: {exc}")
            return None

    def _fetch_v3_states(self, card_id: int) -> None:
        """Fetch V3 scheduling states for *this specific* card.

        B036 fix: uses ``get_scheduling_states(card_id)`` (the same backend
        path the legacy ``answerCard`` uses) so the states are valid regardless
        of the card's position in the scheduler queue.  Previously we relied on
        ``get_queued_cards()`` returning our card as the queue top; when it
        didn't (card not due, or the same skill card reviewed repeatedly in a
        targeted drill), ``v3_states`` was effectively unusable and the answer
        was silently dropped — so nothing reached the revlog and Performance
        never accrued.  Fetching per-card guarantees every answer is recorded.
        """
        from anki.scheduler.v3 import Scheduler as V3Scheduler

        sched = self.mw.col.sched
        if not isinstance(sched, V3Scheduler):
            self._state.v3_states = None
            return
        try:
            self._state.v3_states = self.mw.col._backend.get_scheduling_states(card_id)
        except Exception as exc:
            print(f"[Speedrun WP-22] get_scheduling_states({card_id}) failed: {exc}")
            self._state.v3_states = None

    # ------------------------------------------------------------------
    # Drill rendering
    # ------------------------------------------------------------------

    def _show_drill_question(self) -> None:
        state = self._state
        fields = state.current_item_fields
        if fields is None:
            return

        mode = state.mode
        elapsed = time.monotonic() - state.start_time

        if mode == "timed":
            # Timed: skip prephrase, go straight to choices
            drill_html = build_choices_html(fields)
        elif mode == "blind":
            # Blind review: always start at choices (no prephrase)
            drill_html = build_choices_html(fields)
        else:
            # Untimed modes: start with prephrase
            drill_html = build_prephrase_html(fields)

        page_html = _wrap_with_progress(drill_html, state, elapsed)
        self.web.stdHtml(page_html)

    def _show_drill_choices(self) -> None:
        """Transition to the choices phase (after prephrase)."""
        state = self._state
        fields = state.current_item_fields
        if fields is None:
            return

        elapsed = time.monotonic() - state.start_time
        drill_html = build_choices_html(fields)
        page_html = _wrap_with_progress(drill_html, state, elapsed)
        self.web.stdHtml(page_html)

    def _show_drill_reveal(self) -> None:
        """Show the reveal phase for the committed answer."""
        state = self._state
        fields = state.current_item_fields
        committed = state.committed
        if fields is None or committed is None:
            return

        elapsed = time.monotonic() - state.start_time
        drill_html = build_reveal_html(
            fields,
            committed,
            prephrase_text=state.prephrase_text,
            trap_chosen=state.trap_chosen,
            trap_result=state.trap_result,
        )
        page_html = _wrap_with_progress(drill_html, state, elapsed)
        self.web.stdHtml(page_html)

    # ------------------------------------------------------------------
    # Answering a card
    # ------------------------------------------------------------------

    def _answer_current_card(self) -> None:
        """Submit the answer for the current card via AnswerCard op."""
        state = self._state
        card = state.current_card
        if card is None or state.committed is None:
            self._record_result_and_advance()
            return

        fields = state.current_item_fields or {}
        ease = rating_for_committed(state.committed, fields)  # 1 or 3

        from anki.scheduler.v3 import Scheduler as V3Scheduler, CardAnswer
        from aqt.operations.scheduling import answer_card

        sched = self.mw.col.sched
        if not isinstance(sched, V3Scheduler):
            # Non-v3 scheduler: record result and advance without answering
            self._record_result_and_advance()
            return

        if state.v3_states is None:
            # No scheduling states: record and advance without mutating FSRS
            self._record_result_and_advance()
            return

        try:
            rating = (
                CardAnswer.GOOD if ease == RATING_GOOD else CardAnswer.AGAIN
            )
            answer = sched.build_answer(
                card=card,
                states=state.v3_states,
                rating=rating,
            )
            answer_card(parent=self, answer=answer).success(
                lambda _: self._record_result_and_advance()
            ).run_in_background()
        except Exception as exc:
            print(f"[Speedrun WP-22] answer_card failed: {exc}")
            self._record_result_and_advance()

    def _record_result_and_advance(self) -> None:
        """Record the item outcome and advance to the next card."""
        state = self._state
        fields = state.current_item_fields or {}
        committed = state.committed or ""
        correct = correct_choice(fields)
        is_correct = committed.upper() == correct.upper()

        # Trap missed = the trap tag for the committed wrong choice
        trap_missed = ""
        if not is_correct and committed:
            trap_missed = fields.get(f"TrapChoice{committed.upper()}", "").strip()

        result = ItemResult(
            index=len(state.results) + 1,
            card_id=state.current_card.id if state.current_card else 0,
            item_fields=fields,
            committed=committed,
            correct=correct,
            is_correct=is_correct,
            trap_missed=trap_missed,
        )
        state.results.append(result)
        self._advance_to_next()

    def _advance_to_next(self) -> None:
        """Move to the next card or show the result screen."""
        self._state.current_index += 1
        self._load_current_item()

    # ------------------------------------------------------------------
    # Result and blind review
    # ------------------------------------------------------------------

    def _show_result_screen(self) -> None:
        """Show the set-result screen (spec-ui §3.3)."""
        elapsed = time.monotonic() - self._state.start_time
        result_html = _build_result_html(self._state, elapsed)
        self.web.stdHtml(result_html)

    def _show_empty_state(self) -> None:
        """No cards available for this session."""
        html_body = (
            _SHARED_CSS
            + f'<div style="padding:40px;text-align:center;font-family:-apple-system,sans-serif;">'
            + f'<div style="font-size:1.3em;font-weight:700;color:{_C_INDIGO};margin-bottom:12px;">'
            + "No items available for this session"
            + "</div>"
            + f'<div style="color:#888;margin-bottom:24px;">'
            + "Import the LSAT Speedrun deck to get started."
            + "</div>"
            + f'<button onclick="pycmd(\'speedrun:home\');" '
            + f'style="background:{_C_INDIGO};color:#fff;border:none;padding:10px 22px;'
            + f'border-radius:6px;font-size:1em;cursor:pointer;">'
            + "Back to study plan"
            + "</button>"
            + "</div>"
        )
        self.web.stdHtml(html_body)

    def _start_blind_review(self) -> None:
        """Open a nested blind-review session for missed items."""
        misses = [r for r in self._state.results if not r.is_correct]
        flagged_extras = [r for r in self._state.results if r.flagged and r.is_correct]
        items_to_review = misses + flagged_extras

        if not items_to_review:
            return

        SpeedrunSessionDialog(
            self.mw,
            mode="blind",
            focus_skill="",
            deck_id=self._deck_id,
            blind_items=items_to_review,
        )

    # ------------------------------------------------------------------
    # Bridge command handler
    # ------------------------------------------------------------------

    def _on_bridge_cmd(self, cmd: str) -> bool:
        state = self._state

        # Prephrase: "Reveal choices" button
        if cmd == "speedrun:prephrase:reveal":
            if state.current_item_fields is not None and state.committed is None:
                self.web.evalWithCallback(
                    "document.getElementById('sr-prephrase-input')?.value ?? ''",
                    self._on_prephrase_revealed,
                )
            return True

        # Prephrase: "Skip" button
        if cmd == "speedrun:prephrase:skip":
            if state.current_item_fields is not None and state.committed is None:
                state.prephrase_text = None
                self._show_drill_choices()
            return True

        # Commit a choice (A–E)
        if cmd.startswith("speedrun:commit:"):
            choice = cmd[len("speedrun:commit:"):].strip().upper()
            if choice in ("A", "B", "C", "D", "E") and state.committed is None:
                state.committed = choice
                self._show_drill_reveal()
            return True

        # Name-the-trap chip
        if cmd.startswith("speedrun:trap:"):
            trap_tag = cmd[len("speedrun:trap:"):]
            if state.committed is not None and state.current_item_fields is not None:
                self._on_trap_chosen(trap_tag)
            return True

        # Continue / Next question
        if cmd == "speedrun:continue":
            if state.committed is not None:
                self._answer_current_card()
            return True

        # Flag-to-revisit (result screen)
        if cmd.startswith("speedrun:flag:"):
            try:
                idx = int(cmd[len("speedrun:flag:"):])
                self._toggle_flag(idx)
            except ValueError:
                pass
            return True

        # Blind review (from result screen)
        if cmd == "speedrun:blind-review":
            self._start_blind_review()
            return True

        # Another drill (from result screen)
        if cmd == "speedrun:another-drill":
            # Dismiss this dialog; the Home dialog (if open) stays visible.
            # The user can start a new session from Home.
            self.reject()
            return True

        # Back to study plan (from result screen)
        if cmd == "speedrun:home":
            self.reject()
            # Re-open the Home dialog
            aqt.dialogs.open("SpeedrunHome", self.mw)
            return True

        return False

    def _on_prephrase_revealed(self, text: str | None) -> None:
        """Callback from JS: user typed a prediction and clicked 'Reveal choices'."""
        self._state.prephrase_text = text if text is not None else ""
        self._show_drill_choices()

    def _on_trap_chosen(self, trap_tag: str) -> None:
        """Handle name-the-trap chip selection (D-SR34)."""
        state = self._state
        state.trap_chosen = trap_tag
        fields = state.current_item_fields
        committed = state.committed
        if fields is None or committed is None:
            return

        expected = fields.get(f"TrapChoice{committed.upper()}", "").strip()

        def _norm(t: str) -> str:
            return t.strip().removeprefix("trap::").lower()

        state.trap_result = (
            "correct"
            if expected and _norm(expected) == _norm(trap_tag)
            else "wrong"
        )

        # Re-render the reveal with the trap feedback result
        self._show_drill_reveal()

    def _toggle_flag(self, idx: int) -> None:
        """Toggle the flag-to-revisit star for item at 1-based index idx."""
        results = self._state.results
        for r in results:
            if r.index == idx:
                r.flagged = not r.flagged
                # Update the star via JS (no page reload)
                self.web.eval(
                    f"srUpdateStar({idx}, {str(r.flagged).lower()});"
                )
                return

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def reject(self) -> None:
        saveGeom(self, self.name)
        self.web.cleanup()
        self.web = None  # type: ignore[assignment]
        aqt.dialogs.markClosed("SpeedrunSession")
        QDialog.reject(self)

    def closeWithCallback(self, callback: Callable[[], None]) -> None:
        self.reject()
        callback()

    @classmethod
    def open(
        cls,
        mw: aqt.main.AnkiQt,
        *,
        mode: str = "targeted",
        focus_skill: str = "",
        deck_id: int | None = None,
    ) -> "SpeedrunSessionDialog":
        """Open a new session dialog (always creates a fresh instance)."""
        # Sessions are not singletons — close any existing instance first
        existing = aqt.dialogs._dialogs.get("SpeedrunSession", [None, None])[1]
        if existing is not None:
            try:
                existing.reject()
            except Exception:
                pass
        dlg = cls(mw, mode=mode, focus_skill=focus_skill, deck_id=deck_id)
        aqt.dialogs._dialogs["SpeedrunSession"][1] = dlg
        return dlg
