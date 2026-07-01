# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Speedrun WP-6 — commit-then-reveal reviewer helpers.

Pure-Python module: no Qt, no anki wheel required.  Imported only by
qt/aqt/reviewer.py to keep Speedrun logic isolated from the upstream
reviewer codebase so upstream diffs stay minimal.

Design notes (spec-engine §6, §8, D-SR3, D-SR4):
- Level 1: LSAT Item cards use the existing FSRS-scheduled item-card flow.
  The reviewer detects the "LSAT Item" notetype and replaces the standard
  show-answer-button UI with per-choice commit buttons.  After the learner
  commits a choice the answer side reveals correct key + per-choice
  "why wrong" + trap tag, then auto-answers the card via the normal
  answer_card path (wrong → Again(1), right → Good(3)).
- Level 2: LSAT Skill cards.  The reviewer calls draw_item_for_skill(),
  loads the drawn item note, builds the question/answer HTML from the item
  fields, and answers the SKILL card (not the item card) via the normal
  path.  Render-source and answer-target are decoupled (§8, [B002]).
- Normal Anki decks are UNAFFECTED: all Speedrun behaviour is gated on
  notetype name.
"""

from __future__ import annotations

import html
from typing import Any

# ---------------------------------------------------------------------------
# Notetype identifiers (must match build_seed_deck.py constants exactly)
# ---------------------------------------------------------------------------

LSAT_ITEM_NOTETYPE = "LSAT Item"
LSAT_SKILL_NOTETYPE = "LSAT Skill"

SPEEDRUN_NOTETYPES = frozenset({LSAT_ITEM_NOTETYPE, LSAT_SKILL_NOTETYPE})

_CHOICE_LABELS = ("A", "B", "C", "D", "E")

# FSRS ratings — spec-engine §5.1
RATING_AGAIN = 1   # wrong
RATING_GOOD = 3    # right


# ---------------------------------------------------------------------------
# Card-type detection
# ---------------------------------------------------------------------------


def speedrun_card_type(note_type: dict[str, Any]) -> str | None:
    """Return 'item', 'skill', or None for a given notetype dict.

    Gates ALL Speedrun reviewer behaviour.  Normal cards return None and the
    upstream reviewer path is taken unchanged.
    """
    name = note_type.get("name", "")
    if name == LSAT_ITEM_NOTETYPE:
        return "item"
    if name == LSAT_SKILL_NOTETYPE:
        return "skill"
    return None


# ---------------------------------------------------------------------------
# Field extraction helpers
# ---------------------------------------------------------------------------


def get_item_fields(note: Any) -> dict[str, str]:
    """Return all fields of an LSAT Item note as a {field_name: value} dict."""
    flds = note.note_type()["flds"]
    return {f["name"]: note[f["name"]] for f in flds}


def correct_choice(fields: dict[str, str]) -> str:
    """Return the correct choice letter ('A'–'E'), uppercased, stripped."""
    return fields.get("CorrectChoice", "").strip().upper()


def rating_for_committed(committed: str, fields: dict[str, str]) -> int:
    """Map committed choice to FSRS rating (spec-engine §5.1)."""
    correct = correct_choice(fields)
    return RATING_GOOD if committed.upper() == correct else RATING_AGAIN


# ---------------------------------------------------------------------------
# HTML builders
# ---------------------------------------------------------------------------


def _esc(s: str) -> str:
    return html.escape(s, quote=False)


def build_item_question_html(fields: dict[str, str]) -> str:
    """Commit-phase HTML for an LSAT Item.

    Shows stimulus + stem + 5 choices, each as a clickable div that emits
    pycmd('speedrun:commit:X').  Does NOT contain the answer-side reveal.
    """
    stimulus = fields.get("Stimulus", "")
    stem = fields.get("Stem", "")
    type_tag = _esc(fields.get("TypeTag", ""))
    synthetic = fields.get("SyntheticFlag", "")

    # Synthetic-item notice
    if synthetic == "SYNTHETIC":
        synthetic_html = (
            '<div class="sr-synthetic-flag" style="'
            "color:#b08000;background:#fffde7;border:1px solid #f9a825;"
            'padding:4px 8px;border-radius:4px;margin-bottom:8px;font-size:0.85em;">'
            "[Synthetic placeholder — for testing only]"
            "</div>\n"
        )
    else:
        synthetic_html = ""

    # Choices (each is a clickable commit target)
    choices_html = ""
    for label in _CHOICE_LABELS:
        text = fields.get(f"Choice{label}", "")
        choices_html += (
            f'<div class="sr-choice" data-choice="{label}" '
            'style="cursor:pointer;padding:6px 10px;margin:4px 0;border-radius:5px;'
            'border:1px solid #ddd;transition:background 0.15s;" '
            f'onmouseover="this.style.background=\'#e8f0fe\'" '
            f'onmouseout="this.style.background=\'\'" '
            f"onclick=\"pycmd('speedrun:commit:{label}');\">"
            f"<strong>{label}.</strong> {text}"
            "</div>\n"
        )

    type_html = (
        f'<div class="sr-type-tag" style="margin-top:6px;color:#666;font-size:0.85em;">'
        f"<code>{type_tag}</code></div>\n"
        if type_tag
        else ""
    )

    return (
        '<div class="sr-item-review">\n'
        f"{synthetic_html}"
        f'<div class="sr-stimulus" style="margin-bottom:12px;">{stimulus}</div>\n'
        '<hr style="margin:10px 0;">\n'
        f'<div class="sr-stem" style="font-weight:bold;margin-bottom:10px;">{stem}</div>\n'
        '<div class="sr-choices">\n'
        f"{choices_html}"
        "</div>\n"
        f"{type_html}"
        '<div class="sr-commit-hint" style="color:#888;font-size:0.85em;margin-top:8px;">'
        "Click your answer to commit — no reveal until you choose."
        "</div>\n"
        "</div>"
    )


def build_item_answer_html(fields: dict[str, str], committed: str) -> str:
    """Reveal-phase HTML shown after the learner commits a choice.

    Includes: verdict banner, original question (choices no longer clickable),
    correct-key highlight, per-choice why-wrong + trap tags, stimulus trap tag,
    source, skill tags.
    """
    correct = correct_choice(fields)
    is_correct = committed.upper() == correct

    # Verdict banner
    if is_correct:
        verdict_style = (
            "padding:10px 16px;border-radius:6px;margin-bottom:12px;font-weight:bold;"
            "font-size:1.05em;background:#e8f5e9;color:#2e7d32;border:2px solid #4caf50;"
        )
        verdict_text = f"✓ Correct!  You chose {committed}."
    else:
        verdict_style = (
            "padding:10px 16px;border-radius:6px;margin-bottom:12px;font-weight:bold;"
            "font-size:1.05em;background:#ffebee;color:#c62828;border:2px solid #f44336;"
        )
        verdict_text = (
            f"✗ Wrong.  You chose <strong>{committed}</strong> — "
            f"correct answer is <strong>{correct}</strong>."
        )

    # Static choice list (non-clickable, with correct/committed highlights)
    choices_html = ""
    for label in _CHOICE_LABELS:
        text = fields.get(f"Choice{label}", "")
        if label == correct and label == committed:
            bg = "background:#e8f5e9;border-color:#4caf50;"
            badge = " ✓ your answer"
        elif label == correct:
            bg = "background:#e8f5e9;border-color:#4caf50;"
            badge = " ✓"
        elif label == committed:
            bg = "background:#ffebee;border-color:#f44336;"
            badge = " ✗ your answer"
        else:
            bg = ""
            badge = ""
        choices_html += (
            f'<div class="sr-choice-static" style="padding:5px 10px;margin:3px 0;'
            f"border-radius:4px;border:1px solid #ddd;{bg}\">"
            f"<strong>{label}.</strong> {text}"
            f"<span style=\"font-size:0.85em;color:{'#2e7d32' if '✓' in badge else '#c62828'}\">"
            f"{badge}</span>"
            "</div>\n"
        )

    # Per-choice explanations
    per_choice_html = ""
    for label in _CHOICE_LABELS:
        why = fields.get(f"WhyWrong{label}", "")
        trap = fields.get(f"TrapChoice{label}", "")
        trap_html = (
            f' <code class="sr-trap" style="background:#fff3e0;padding:1px 4px;'
            f"border-radius:3px;font-size:0.85em;\">{_esc(trap)}</code>"
            if trap
            else ""
        )
        if label == correct:
            label_style = "font-weight:bold;color:#2e7d32;"
        elif label == committed:
            label_style = "font-weight:bold;color:#c62828;"
        else:
            label_style = "color:#555;"

        per_choice_html += (
            f'<div class="sr-why" style="margin:4px 0;{label_style}">'
            f"<strong>{label}:</strong> {why}{trap_html}"
            "</div>\n"
        )

    # Extra metadata
    trap_tag = fields.get("TrapTag", "")
    source = fields.get("Source", "")
    skill_tag = fields.get("SkillTag", "")
    synthetic = fields.get("SyntheticFlag", "")

    extras = ""
    if trap_tag:
        extras += (
            '<div class="sr-stim-trap" style="margin-top:10px;padding:6px 10px;'
            "background:#fff3e0;border-radius:4px;font-size:0.9em;\">"
            f"Stimulus flaw: <code>{_esc(trap_tag)}</code></div>\n"
        )
    if source:
        extras += (
            '<div class="sr-source" style="color:#888;font-size:0.8em;margin-top:6px;">'
            f"{_esc(source)}</div>\n"
        )
    if skill_tag:
        extras += (
            '<div class="sr-skill-tags" style="color:#666;font-size:0.8em;">'
            f"<code>{_esc(skill_tag)}</code></div>\n"
        )
    if synthetic == "SYNTHETIC":
        extras += (
            '<div style="color:#b08000;font-size:0.75em;margin-top:4px;">'
            "[Synthetic item]</div>\n"
        )

    stimulus = fields.get("Stimulus", "")
    stem = fields.get("Stem", "")
    type_tag = _esc(fields.get("TypeTag", ""))

    type_html = (
        f'<div class="sr-type-tag" style="margin-top:6px;color:#666;font-size:0.85em;">'
        f"<code>{type_tag}</code></div>\n"
        if type_tag
        else ""
    )

    return (
        '<div class="sr-item-review">\n'
        f'<div style="{verdict_style}">{verdict_text}</div>\n'
        # Question section (static, non-clickable)
        f'<div class="sr-stimulus" style="margin-bottom:12px;">{stimulus}</div>\n'
        '<hr style="margin:10px 0;">\n'
        f'<div class="sr-stem" style="font-weight:bold;margin-bottom:10px;">{stem}</div>\n'
        '<div class="sr-choices-static">\n'
        f"{choices_html}"
        "</div>\n"
        f"{type_html}"
        '<hr id="answer" style="margin:14px 0;">\n'
        # Reveal section
        '<div class="sr-reveal">\n'
        '<div style="font-weight:bold;margin-bottom:6px;">Why each choice:</div>\n'
        f"{per_choice_html}"
        "</div>\n"
        f"{extras}"
        "</div>"
    )


# ---------------------------------------------------------------------------
# Bottom-bar HTML snippets for the Speedrun reviewer states
# ---------------------------------------------------------------------------


def bottom_commit_prompt(remaining: str = "") -> str:
    """Bottom-bar centre content for the commit (question) phase.

    Replaces the standard 'Show Answer' button.  Remaining count is appended
    if non-empty so the stats display is unchanged.
    """
    return (
        "<table cellpadding=0><tr><td class=stat2 align=center>"
        '<div style="color:#555;font-style:italic;padding:6px 0;">'
        "↑ Click a choice (A–E) to commit your answer"
        f"<span class=stattxt>{remaining}</span>"
        "</div>"
        "</td></tr></table>"
    )


def bottom_continue_button(ease: int) -> str:
    """Bottom-bar centre content for the reveal (answer) phase.

    Shows a single 'Continue' button that submits the determined ease value.
    """
    label = "Again (wrong)" if ease == RATING_AGAIN else "Good (correct)"
    colour = "#c62828" if ease == RATING_AGAIN else "#2e7d32"
    return (
        "<center><table cellpadding=0 cellspacing=0><tr>"
        f'<td align=center><button onclick=\'pycmd("speedrun:continue");\'  '
        f'style="background:{colour};color:#fff;border:none;padding:8px 22px;'
        "border-radius:6px;font-size:1em;cursor:pointer;font-weight:bold;\" "
        f'title="Space / Enter">'
        f"{label}</button></td>"
        "</tr></table></center>"
    )
