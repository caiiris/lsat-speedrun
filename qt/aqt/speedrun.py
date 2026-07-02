# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Speedrun WP-6 / WP-21 — commit-then-reveal reviewer helpers.

Pure-Python module: no Qt, no anki wheel required.  Imported only by
qt/aqt/reviewer.py to keep Speedrun logic isolated from the upstream
reviewer codebase so upstream diffs stay minimal.

Design notes (spec-ui §2/§3.2, D-SR30, D-SR34):
- Prephrase: shown before choices for untimed drills; text field where the
  learner predicts what the answer must do.  Self-scored on reveal.
- Choices: the 5-option commit surface (click to lock in; no reveal before).
- Reveal: verdict + accordion choices (why-wrong per choice) + prephrase
  self-check + name-the-trap on a wrong commit.
- Name-the-trap: amber chips of candidate traps; checked deterministically
  against TrapChoiceX (D-SR34).  No AI.
- Normal Anki decks are UNAFFECTED: all Speedrun behaviour is gated on
  notetype name.

Reasoning map rail (Premise/Conclusion/The gap): OMITTED in v1 — the LSAT
Item notetype has no marked-conclusion field yet (known gap, D-SR34; tracked
in WP-21-log.md).
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
# Design language (spec-ui §2)
# ---------------------------------------------------------------------------

# Palette
_C_BG = "#F5F7FA"         # cool pale paper (outer background)
_C_CARD = "#fff"          # card/panel background
_C_INK = "#1B2430"        # slate ink (primary text)
_C_INDIGO = "#3E3A8C"     # structural accent (buttons, tags, borders)
_C_GREEN = "#2E7D5B"      # success
_C_CLAY = "#B4472E"       # error
_C_AMBER = "#C99A2E"      # trap chips ONLY
_C_BORDER = "#E2E6EE"     # subtle border

# Trap display labels — maps the stored tag string to a human-readable name.
# Keys are the canonical trap slugs from docs/speedrun/data/taxonomy.json
# (argument_flaws + distractor_traps). Keep in sync with the taxonomy.
TRAP_DISPLAY_NAMES: dict[str, str] = {
    # argument flaws (in the stimulus)
    "trap::sufficient-necessary": "Sufficient/Necessary confusion",
    "trap::correlation-causation": "Correlation \u2260 causation",
    "trap::circular": "Circular reasoning",
    "trap::equivocation": "Equivocation",
    "trap::part-whole": "Part/whole error",
    "trap::hasty-generalization": "Hasty generalization",
    "trap::false-dichotomy": "False dichotomy",
    "trap::straw-man": "Straw man",
    "trap::ad-hominem": "Ad hominem",
    "trap::appeal-authority": "Appeal to authority",
    "trap::false-analogy": "False analogy",
    "trap::scope-shift": "Scope shift",
    # distractor / answer-choice traps
    "trap::half-true": "Half true",
    "trap::too-extreme": "Too extreme",
    "trap::out-of-scope": "Out of scope",
    "trap::contradicts": "Contradicts the text",
    "trap::wrong-direction": "Wrong direction",
    "trap::reversal": "Reversal",
    "trap::irrelevant-comparison": "Irrelevant comparison",
}

# Plain-language, learner-facing glosses for each trap (one line, no jargon).
# Surfaced next to the label so a two-word slug isn't cryptic. Same key set
# as TRAP_DISPLAY_NAMES (the taxonomy's canonical trap slugs).
TRAP_DESCRIPTIONS: dict[str, str] = {
    "trap::sufficient-necessary": "Confuses \u201cenough to\u201d with \u201crequired for.\u201d",
    "trap::correlation-causation": "Assumes one thing caused another just because they occur together.",
    "trap::circular": "Uses the conclusion as its own support.",
    "trap::equivocation": "A key word quietly changes meaning mid-argument.",
    "trap::part-whole": "Assumes what\u2019s true of a part is true of the whole (or vice versa).",
    "trap::hasty-generalization": "Draws a broad conclusion from too small a sample.",
    "trap::false-dichotomy": "Pretends there are only two options when others exist.",
    "trap::straw-man": "Distorts the opponent\u2019s point, then knocks down the distortion.",
    "trap::ad-hominem": "Attacks the person instead of their argument.",
    "trap::appeal-authority": "Leans on who said it rather than whether it\u2019s true.",
    "trap::false-analogy": "Compares two cases that differ in a way that matters.",
    "trap::scope-shift": "The conclusion is about something narrower or broader than the evidence.",
    "trap::half-true": "Partly right, but leaves out or distorts a key part.",
    "trap::too-extreme": "Overstates it \u2014 \u201call/never/always\u201d where the argument was cautious.",
    "trap::out-of-scope": "Brings in something the argument never mentioned.",
    "trap::contradicts": "Directly conflicts with something the argument states.",
    "trap::wrong-direction": "Does the opposite of the task \u2014 e.g. strengthens when you needed to weaken.",
    "trap::reversal": "Flips the logic \u2014 treats the condition backwards (necessary \u2194 sufficient).",
    "trap::irrelevant-comparison": "Compares two things the argument isn\u2019t actually weighing.",
}

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
# Trap helpers
# ---------------------------------------------------------------------------


def _collect_item_traps(fields: dict[str, str]) -> list[str]:
    """Return unique non-empty trap tag strings found across all TrapChoiceA–E."""
    seen: list[str] = []
    for label in _CHOICE_LABELS:
        trap = fields.get(f"TrapChoice{label}", "").strip()
        if trap and trap not in seen:
            seen.append(trap)
    return seen


def _trap_label(tag: str) -> str:
    return TRAP_DISPLAY_NAMES.get(tag, tag.removeprefix("trap::").replace("-", " ").title())


def _trap_description(tag: str) -> str:
    """Plain-language gloss for a trap tag (empty string if unknown)."""
    return TRAP_DESCRIPTIONS.get(tag, "")


# ---------------------------------------------------------------------------
# HTML escape helper
# ---------------------------------------------------------------------------


def _esc(s: str) -> str:
    return html.escape(s, quote=False)


# ---------------------------------------------------------------------------
# Shared CSS injected into all Speedrun HTML
# ---------------------------------------------------------------------------

_SHARED_CSS = f"""
<style>
.sr-drill {{
  display: flex;
  gap: 18px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 15px;
  color: {_C_INK};
  background: {_C_BG};
  padding: 14px;
  box-sizing: border-box;
  min-height: 100%;
}}
.sr-main {{
  flex: 1;
  min-width: 0;
  background: {_C_CARD};
  border-radius: 12px;
  border: 1px solid {_C_BORDER};
  padding: 22px 24px;
}}
.sr-rail {{
  width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}}
.sr-rail-card {{
  background: {_C_CARD};
  border-radius: 10px;
  border: 1px solid {_C_BORDER};
  padding: 14px;
}}
.sr-type-tag {{
  font-family: monospace;
  font-size: 0.78em;
  color: {_C_INDIGO};
  margin-bottom: 10px;
  letter-spacing: 0.02em;
}}
.sr-stimulus {{
  font-family: Georgia, "Times New Roman", serif;
  font-size: 1.04em;
  line-height: 1.65;
  color: {_C_INK};
  margin-bottom: 14px;
}}
.sr-stem {{
  font-size: 0.97em;
  color: {_C_INK};
  font-weight: 500;
  margin-bottom: 14px;
  line-height: 1.5;
}}
.sr-synthetic-flag {{
  font-size: 0.78em;
  color: #b08000;
  background: #fffde7;
  border: 1px solid #f9a825;
  border-radius: 4px;
  padding: 3px 8px;
  margin-bottom: 10px;
  display: inline-block;
}}
.sr-chip {{
  display: inline-block;
  border: 1.5px solid {_C_AMBER};
  color: {_C_INK};
  border-radius: 20px;
  padding: 4px 13px;
  font-size: 0.85em;
  cursor: pointer;
  background: {_C_CARD};
  transition: background 0.12s, color 0.12s;
  margin: 3px 4px 3px 0;
  user-select: none;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}}
.sr-chip:hover {{
  background: #fff8e0;
}}
.sr-chip-selected {{
  background: {_C_AMBER} !important;
  color: #fff !important;
  border-color: {_C_AMBER} !important;
}}
.sr-chip-correct {{
  background: {_C_GREEN} !important;
  color: #fff !important;
  border-color: {_C_GREEN} !important;
}}
.sr-chip-wrong {{
  background: {_C_CLAY} !important;
  color: #fff !important;
  border-color: {_C_CLAY} !important;
}}
</style>
"""


# ---------------------------------------------------------------------------
# Right-rail fragments
# ---------------------------------------------------------------------------


def _rail_tags_html(fields: dict[str, str]) -> str:
    type_tag = _esc(fields.get("TypeTag", ""))
    skill_tag = _esc(fields.get("SkillTag", ""))
    tags = []
    if type_tag:
        tags.append(f'<div style="font-family:monospace;font-size:0.82em;color:{_C_INDIGO};margin-bottom:4px;">{type_tag}</div>')
    if skill_tag:
        for t in skill_tag.split():
            tags.append(f'<div style="font-family:monospace;font-size:0.78em;color:#555;margin-bottom:2px;">{t}</div>')
    return "".join(tags)


def _human_tag(tag: str) -> str:
    """Convert a raw taxonomy tag to a human-readable label (no `type::` jargon)."""
    name = tag.split("::", 1)[-1].replace("-", " ").title()
    return name.replace(" Id", " ID")


def _reveal_tested_html(fields: dict[str, str]) -> str:
    """Post-answer 'what this tested' card — plain English, not raw type::/skill:: tags."""
    type_tag = fields.get("TypeTag", "")
    skill_tokens = [t for t in fields.get("SkillTag", "").split() if t]
    type_line = _human_tag(type_tag) if type_tag else "\u2014"
    skills_line = ", ".join(_human_tag(t) for t in skill_tokens)
    skills_html = (
        f'<div style="font-size:0.82em;color:#888;margin-top:3px;">{_esc(skills_line)}</div>'
        if skills_line
        else ""
    )
    return (
        f'<div class="sr-rail-card">'
        f'<div style="font-size:0.72em;font-weight:700;color:#888;letter-spacing:0.08em;'
        f'margin-bottom:6px;">WHAT THIS TESTED</div>'
        f'<div style="font-size:0.92em;color:{_C_INK};font-weight:600;">{_esc(type_line)}</div>'
        f"{skills_html}"
        f"</div>"
    )


def _rail_tip_html(fields: dict[str, str]) -> str:
    # Deliberately does NOT name the question type/skill: identifying the type
    # from the stem is part of the task, so we don't spoil it before commit.
    # The taxonomy tags are revealed afterwards, in build_reveal_html.
    return (
        f'<div class="sr-rail-card">'
        f'<div style="color:{_C_AMBER};font-size:0.72em;font-weight:700;letter-spacing:0.12em;margin-bottom:7px;">TIP</div>'
        f'<div style="font-size:0.88em;color:{_C_INK};line-height:1.5;font-weight:600;">'
        f"Read the stem, name the question type in your head, then predict the answer before reading the choices \u2014 it stops you from rationalizing a wrong one."
        f"</div>"
        f'<div style="color:#aaa;font-size:0.76em;margin-top:8px;">(tips fade as your score rises)</div>'
        f"</div>"
    )


def _rail_confidence_html() -> str:
    return (
        f'<div class="sr-rail-card">'
        f'<div style="font-size:0.8em;color:#888;margin-bottom:8px;font-weight:600;">Confidence</div>'
        f'<div style="display:flex;gap:8px;align-items:center;">'
        f'<span onclick="srConf(1)" id="sr-c1" title="Low" style="font-size:22px;cursor:pointer;color:#ddd;user-select:none;">&#9679;</span>'
        f'<span onclick="srConf(2)" id="sr-c2" title="Medium" style="font-size:22px;cursor:pointer;color:#ddd;user-select:none;">&#9679;</span>'
        f'<span onclick="srConf(3)" id="sr-c3" title="High" style="font-size:22px;cursor:pointer;color:#ddd;user-select:none;">&#9679;</span>'
        f'<span id="sr-conf-label" style="font-size:0.8em;color:#aaa;margin-left:4px;"></span>'
        f"</div>"
        f"</div>"
        f'<script>function srConf(n){{["Low","Medium","High"].forEach(function(l,i){{var e=document.getElementById("sr-c"+(i+1));e.style.color=i<n?"{_C_AMBER}":"#ddd";}});var lbl=document.getElementById("sr-conf-label");if(lbl)lbl.textContent=["Low","Medium","High"][n-1];}};</script>'
    )


def _rail_next_button_html() -> str:
    return (
        f'<button onclick="pycmd(\'speedrun:continue\');" '
        f'style="width:100%;background:{_C_INDIGO};color:#fff;border:none;padding:13px 0;'
        f'border-radius:8px;font-size:1em;font-weight:700;cursor:pointer;'
        f'letter-spacing:0.01em;margin-top:4px;">'
        f"Next question \u2192"
        f"</button>"
    )


# ---------------------------------------------------------------------------
# 1. Prephrase state HTML
# ---------------------------------------------------------------------------


def build_prephrase_html(fields: dict[str, str]) -> str:
    """Prephrase state: stimulus + stem + prediction text field + blurred choices.

    Emits pycmd('speedrun:prephrase:reveal') on button click (with JS reading
    the input value first) and pycmd('speedrun:prephrase:skip') on Skip.
    """
    stimulus = fields.get("Stimulus", "")
    stem = fields.get("Stem", "")
    synthetic = fields.get("SyntheticFlag", "")

    synthetic_html = (
        '<div class="sr-synthetic-flag">[Synthetic placeholder \u2014 for testing only]</div>\n'
        if synthetic == "SYNTHETIC"
        else ""
    )

    # Blurred (obscured) choices — visual only, not clickable
    blurred_rows = ""
    for label in _CHOICE_LABELS:
        text = _esc(fields.get(f"Choice{label}", ""))
        blurred_rows += (
            f'<div style="display:flex;align-items:center;gap:12px;padding:9px 12px;'
            f'margin:4px 0;border-radius:7px;border:1px solid {_C_BORDER};">'
            f'<span style="min-width:22px;height:22px;border-radius:50%;border:1.5px solid #bbb;'
            f'display:flex;align-items:center;justify-content:center;font-size:0.85em;color:#999;'
            f'flex-shrink:0;">{label}</span>'
            f'<span style="color:#ccc;">{text}</span>'
            f"</div>\n"
        )

    prephrase_box = (
        f'<div style="background:#f0f0fa;border:2px solid {_C_INDIGO};border-radius:10px;'
        f'padding:18px 20px;margin-bottom:16px;">\n'
        f'<div style="font-family:monospace;font-size:0.72em;color:{_C_INDIGO};'
        f'letter-spacing:0.08em;margin-bottom:7px;">PREPHRASE \u00b7 predict before you look</div>\n'
        f'<div style="font-size:1.02em;font-weight:700;color:{_C_INDIGO};margin-bottom:12px;">'
        f"In one line, predict what the correct answer must say.</div>\n"
        f'<input id="sr-prephrase-input" type="text" autocomplete="off" '
        f'placeholder="e.g. jot your prediction before you look\u2026" '
        f'style="width:100%;padding:10px 13px;border:1px solid #c0c4d4;border-radius:6px;'
        f'font-size:0.95em;box-sizing:border-box;outline:none;font-family:inherit;'
        f'background:#fff;" '
        f'onkeydown="if(event.key===\'Enter\'){{pycmd(\'speedrun:prephrase:reveal\');}}" />\n'
        f'<div style="display:flex;align-items:center;gap:16px;margin-top:12px;">\n'
        f'<button onclick="pycmd(\'speedrun:prephrase:reveal\');" '
        f'style="background:{_C_INDIGO};color:#fff;border:none;padding:9px 20px;'
        f'border-radius:6px;font-size:0.95em;cursor:pointer;font-weight:600;">'
        f"Reveal choices \u2192</button>\n"
        f'<button onclick="pycmd(\'speedrun:prephrase:skip\');" '
        f'style="background:none;border:none;color:{_C_INDIGO};font-size:0.95em;'
        f'cursor:pointer;text-decoration:underline;padding:0;">'
        f"Skip</button>\n"
        f"</div>\n"
        f'<div style="color:#999;font-size:0.8em;margin-top:9px;">'
        f"You\u2019ll check your prediction against the key after you answer.</div>\n"
        f"</div>\n"
    )

    hidden_choices = (
        f'<div style="position:relative;">\n'
        f'<div style="filter:blur(3px);pointer-events:none;user-select:none;">\n'
        f"{blurred_rows}"
        f"</div>\n"
        f'<div style="position:absolute;inset:0;display:flex;align-items:center;'
        f'justify-content:center;">'
        f'<div style="background:#fff;border:1px solid {_C_BORDER};border-radius:20px;'
        f'padding:7px 18px;font-size:0.88em;color:#666;'
        f'box-shadow:0 2px 8px rgba(0,0,0,0.08);">'
        f"\U0001f512 5 choices hidden until you predict</div>\n"
        f"</div>\n"
        f"</div>\n"
    )

    # Auto-focus the input after render
    focus_script = (
        '<script>(function(){var inp=document.getElementById("sr-prephrase-input");'
        'if(inp){inp.focus();}})()</script>\n'
    )

    rail = (
        f'<div class="sr-rail">\n'
        f"{_rail_tip_html(fields)}\n"
        f"</div>\n"
    )

    main = (
        f'<div class="sr-main">\n'
        f"{synthetic_html}"
        f'<div class="sr-stimulus">{stimulus}</div>\n'
        f'<div style="height:1px;background:{_C_BORDER};margin:12px 0;"></div>\n'
        f'<div class="sr-stem">{stem}</div>\n'
        f"{prephrase_box}"
        f"{hidden_choices}"
        f"</div>\n"
    )

    return (
        _SHARED_CSS
        + '<div class="sr-drill">\n'
        + main
        + rail
        + "</div>\n"
        + focus_script
    )


# ---------------------------------------------------------------------------
# 2. Choices state HTML (was build_item_question_html)
# ---------------------------------------------------------------------------


def build_choices_html(fields: dict[str, str]) -> str:
    """Commit-phase HTML for an LSAT Item.

    Shows stimulus + stem + 5 choices, each as a clickable row that emits
    pycmd('speedrun:commit:X').  Does NOT contain the answer-side reveal.
    Design matches spec-ui §2 (indigo accent, clean workspace feel).
    """
    stimulus = fields.get("Stimulus", "")
    stem = fields.get("Stem", "")
    synthetic = fields.get("SyntheticFlag", "")

    synthetic_html = (
        '<div class="sr-synthetic-flag">[Synthetic placeholder \u2014 for testing only]</div>\n'
        if synthetic == "SYNTHETIC"
        else ""
    )

    choices_html = ""
    for label in _CHOICE_LABELS:
        text = fields.get(f"Choice{label}", "")
        choices_html += (
            f'<div class="sr-choice-row" '
            f'style="display:flex;align-items:center;gap:12px;padding:10px 14px;'
            f'margin:5px 0;border-radius:8px;border:1px solid {_C_BORDER};'
            f'cursor:pointer;transition:border-color 0.12s,background 0.12s;" '
            f'onmouseover="this.style.borderColor=\'{_C_INDIGO}\';this.style.background=\'#f5f5ff\'" '
            f'onmouseout="this.style.borderColor=\'{_C_BORDER}\';this.style.background=\'\'" '
            f"onclick=\"pycmd('speedrun:commit:{label}');\">\n"
            f'<span style="min-width:26px;height:26px;border-radius:50%;border:1.5px solid #bbb;'
            f'display:flex;align-items:center;justify-content:center;font-size:0.85em;'
            f'font-weight:600;color:#666;flex-shrink:0;">{label}</span>\n'
            f'<span style="line-height:1.45;">{text}</span>\n'
            f"</div>\n"
        )

    main = (
        f'<div class="sr-main">\n'
        f"{synthetic_html}"
        f'<div class="sr-stimulus">{stimulus}</div>\n'
        f'<div style="height:1px;background:{_C_BORDER};margin:12px 0;"></div>\n'
        f'<div class="sr-stem">{stem}</div>\n'
        f'<div style="margin-top:8px;">\n'
        f"{choices_html}"
        f"</div>\n"
        f'<div style="color:#999;font-size:0.82em;margin-top:12px;">'
        f"Click your answer to commit \u2014 no reveal until you choose."
        f"</div>\n"
        f"</div>\n"
    )

    # Rail: a non-spoiling coaching tip only — taxonomy tags are withheld until
    # reveal so the learner must identify the question type themselves.
    rail = (
        f'<div class="sr-rail">\n'
        f"{_rail_tip_html(fields)}\n"
        f"</div>\n"
    )

    return (
        _SHARED_CSS
        + '<div class="sr-drill">\n'
        + main
        + rail
        + "</div>\n"
    )


# Keep the old name as an alias so any other existing references don't break
build_item_question_html = build_choices_html


# ---------------------------------------------------------------------------
# 3. Reveal state HTML
# ---------------------------------------------------------------------------


def build_reveal_html(
    fields: dict[str, str],
    committed: str,
    prephrase_text: str | None = None,
    trap_chosen: str | None = None,
    trap_result: str | None = None,
) -> str:
    """Full reveal HTML shown after the learner commits a choice.

    Includes: verdict banner, accordion choices (auto-expanded for correct +
    committed), prephrase self-check (if prephrase_text is not None),
    name-the-trap chips (on wrong commit, if TrapChoiceX is non-empty),
    right rail (taxonomy tags, confidence tap, next-question button).

    spec-ui §3.2 states 3-4; D-SR34.
    """
    correct = correct_choice(fields)
    is_correct = committed.upper() == correct

    stimulus = fields.get("Stimulus", "")
    stem = fields.get("Stem", "")
    synthetic = fields.get("SyntheticFlag", "")

    synthetic_html = (
        '<div class="sr-synthetic-flag">[Synthetic \u2014 for testing only]</div>\n'
        if synthetic == "SYNTHETIC"
        else ""
    )

    # ------------------------------------------------------------------
    # Verdict banner
    # ------------------------------------------------------------------
    if is_correct:
        verdict_bg = "#e8f5ee"
        verdict_border = _C_GREEN
        verdict_color = _C_GREEN
        verdict_text = f"\u2713 Correct!  You chose {committed}."
    else:
        verdict_bg = "#fdf0ed"
        verdict_border = _C_CLAY
        verdict_color = _C_CLAY
        verdict_text = (
            f"\u2717 Wrong.  You chose <strong>{committed}</strong> \u2014 "
            f"correct answer is <strong>{correct}</strong>."
        )

    verdict_html = (
        f'<div style="padding:10px 16px;border-radius:8px;margin-bottom:16px;'
        f'font-weight:700;font-size:1em;background:{verdict_bg};color:{verdict_color};'
        f'border:2px solid {verdict_border};">{verdict_text}</div>\n'
    )

    # ------------------------------------------------------------------
    # Accordion choices
    # ------------------------------------------------------------------
    # Determine traps for name-the-trap chips (shown under the committed wrong choice)
    show_name_trap = (
        not is_correct
        and bool(fields.get(f"TrapChoice{committed}", "").strip())
    )
    item_traps = _collect_item_traps(fields) if show_name_trap else []

    choices_html = ""
    for label in _CHOICE_LABELS:
        text = fields.get(f"Choice{label}", "")
        why = fields.get(f"WhyWrong{label}", "")
        trap_tag = fields.get(f"TrapChoice{label}", "").strip()

        is_this_correct = (label == correct)
        is_this_committed = (label == committed.upper())

        # Header styling
        if is_this_correct and is_this_committed:
            circle_border = _C_GREEN
            circle_color = _C_GREEN
            row_border = _C_GREEN
            row_bg = "#e8f5ee"
            chevron_color = _C_GREEN
            verdict_icon = f'<span style="color:{_C_GREEN};font-weight:700;margin-left:auto;">\u2713</span>'
        elif is_this_correct:
            circle_border = _C_GREEN
            circle_color = _C_GREEN
            row_border = _C_GREEN
            row_bg = "#e8f5ee"
            chevron_color = _C_GREEN
            verdict_icon = f'<span style="color:{_C_GREEN};font-weight:700;margin-left:auto;">\u2713</span>'
        elif is_this_committed:
            circle_border = _C_CLAY
            circle_color = _C_CLAY
            row_border = _C_CLAY
            row_bg = "#fdf0ed"
            chevron_color = _C_CLAY
            verdict_icon = f'<span style="color:{_C_CLAY};font-weight:700;margin-left:auto;">\u2717</span>'
        else:
            circle_border = "#bbb"
            circle_color = "#777"
            row_border = _C_BORDER
            row_bg = _C_CARD
            chevron_color = "#aaa"
            verdict_icon = ""

        auto_open = "block" if (is_this_correct or is_this_committed) else "none"

        # Detail content
        why_label = "Why correct:" if is_this_correct else "Why wrong:"
        why_color = _C_GREEN if is_this_correct else _C_CLAY
        why_html = (
            f'<div style="font-size:0.88em;color:{why_color};margin-bottom:6px;font-weight:600;">{why_label}</div>'
            f'<div style="font-size:0.9em;color:{_C_INK};line-height:1.5;margin-bottom:8px;">{why}</div>'
            if why
            else ""
        )
        if trap_tag and not is_this_correct:
            trap_label_text = _trap_label(trap_tag)
            trap_desc = _trap_description(trap_tag)
            desc_html = (
                f'<span style="color:#999;"> \u2014 {_esc(trap_desc)}</span>'
                if trap_desc
                else ""
            )
            why_html += (
                f'<div style="font-size:0.8em;color:#888;margin-bottom:6px;">'
                f'Trap category: <code style="background:#fff8e0;padding:1px 5px;'
                f'border-radius:3px;color:{_C_AMBER};font-weight:600;">{_esc(trap_label_text)}</code>'
                f"{desc_html}</div>\n"
            )

        # Name-the-trap chips (only for committed wrong choice)
        trap_chips_html = ""
        if is_this_committed and show_name_trap:
            trap_chips_html = _build_trap_chips_html(
                item_traps,
                trap_chosen,
                trap_result,
                committed=committed.upper(),
                answer_trap=trap_tag,
            )

        detail_html = (
            f'<div style="padding:12px 14px 10px 14px;border-top:1px solid {_C_BORDER};">'
            f"{why_html}"
            f"{trap_chips_html}"
            f"</div>"
        )

        toggle_js = (
            "(function(el){"
            "var d=el.nextElementSibling;"
            "if(d){d.style.display=d.style.display==='none'?'block':'none';}"
            "})(this)"
        )

        choices_html += (
            f'<div style="border-radius:8px;border:1.5px solid {row_border};'
            f'background:{row_bg};margin:5px 0;overflow:hidden;">\n'
            # Header row (clickable toggle)
            f'<div onclick="{toggle_js}" '
            f'style="display:flex;align-items:center;gap:12px;padding:10px 14px;cursor:pointer;">\n'
            f'<span style="min-width:26px;height:26px;border-radius:50%;'
            f'border:1.5px solid {circle_border};display:flex;align-items:center;'
            f'justify-content:center;font-size:0.85em;font-weight:700;'
            f'color:{circle_color};flex-shrink:0;">{label}</span>\n'
            f'<span style="line-height:1.45;flex:1;">{text}</span>\n'
            f"{verdict_icon}\n"
            f'<span style="color:{chevron_color};font-size:0.8em;margin-left:8px;">\u25be</span>\n'
            f"</div>\n"
            # Detail (auto-open for correct + committed)
            f'<div style="display:{auto_open};">\n'
            f"{detail_html}\n"
            f"</div>\n"
            f"</div>\n"
        )

    # ------------------------------------------------------------------
    # Prephrase self-check
    # ------------------------------------------------------------------
    self_check_html = ""
    if prephrase_text is not None:
        escaped_prediction = _esc(prephrase_text) if prephrase_text else ""
        if escaped_prediction:
            prediction_display = (
                f'<div style="background:#f8f8fc;border-left:3px solid {_C_INDIGO};'
                f'padding:8px 12px;border-radius:0 6px 6px 0;margin-bottom:10px;'
                f'font-size:0.9em;color:{_C_INK};font-style:italic;">'
                f'Your prediction: \u201c{escaped_prediction}\u201d'
                f"</div>\n"
            )
        else:
            prediction_display = (
                '<div style="font-size:0.85em;color:#aaa;margin-bottom:10px;">'
                "(You did not type a prediction.)"
                "</div>\n"
            )

        selfcheck_header = (
            f'<div style="border-top:1px solid {_C_BORDER};margin-top:16px;padding-top:14px;">\n'
            f'<div style="font-size:0.85em;font-weight:700;color:{_C_INDIGO};'
            f'letter-spacing:0.04em;margin-bottom:8px;">PREPHRASE SELF-CHECK</div>\n'
            f"{prediction_display}"
        )

        if not is_correct:
            # You missed the item — don't ask "did your prediction match?" (it
            # clearly didn't lead you to the key).  Prompt reflection instead.
            self_check_html = (
                selfcheck_header
                + f'<div style="font-size:0.88em;color:{_C_INK};line-height:1.5;">'
                + "Compare your prediction with the correct answer above \u2014 "
                + "where did your reasoning diverge?</div>\n"
                + "</div>\n"
            )
        else:
            self_check_html = (
                selfcheck_header
                + f'<div style="font-size:0.88em;color:{_C_INK};margin-bottom:8px;">'
                + f"Did your prediction match the key?</div>\n"
                + f'<div id="sr-selfcheck-btns" style="display:flex;gap:8px;">\n'
                + f'<button onclick="srSelfCheck(\'yes\')" id="sr-sc-yes" '
                + f'style="padding:5px 16px;border-radius:6px;border:1.5px solid {_C_GREEN};'
                + f'color:{_C_GREEN};background:{_C_CARD};cursor:pointer;font-size:0.88em;font-weight:600;">'
                + f"\U0001f44d Yes</button>\n"
                + f'<button onclick="srSelfCheck(\'no\')" id="sr-sc-no" '
                + f'style="padding:5px 16px;border-radius:6px;border:1.5px solid {_C_CLAY};'
                + f'color:{_C_CLAY};background:{_C_CARD};cursor:pointer;font-size:0.88em;font-weight:600;">'
                + f"\U0001f44e Not quite</button>\n"
                + f"</div>\n"
                + f'<div id="sr-selfcheck-result" style="font-size:0.82em;color:#888;'
                + f'margin-top:6px;display:none;"></div>\n'
                + f"</div>\n"
                + f"<script>\n"
            f"function srSelfCheck(v){{\n"
            f"  var yes=document.getElementById('sr-sc-yes');\n"
            f"  var no=document.getElementById('sr-sc-no');\n"
            f"  var res=document.getElementById('sr-selfcheck-result');\n"
            f"  if(!yes||!no||!res) return;\n"
            f"  if(v==='yes'){{\n"
            f"    yes.style.background='{_C_GREEN}';yes.style.color='#fff';\n"
            f"    no.style.background='';no.style.color='{_C_CLAY}';\n"
            f"    res.textContent='Nice \u2014 your prediction was on track.';\n"
            f"  }} else {{\n"
            f"    no.style.background='{_C_CLAY}';no.style.color='#fff';\n"
            f"    yes.style.background='';yes.style.color='{_C_GREEN}';\n"
            f"    res.textContent='That\u2019s the learning moment \u2014 revisit what the gap was.';\n"
            f"  }}\n"
            f"  res.style.display='block';\n"
            f"}}\n"
            f"</script>\n"
        )

    # ------------------------------------------------------------------
    # Main canvas assembly
    # ------------------------------------------------------------------
    main = (
        f'<div class="sr-main">\n'
        f"{synthetic_html}"
        f"<hr id=\"answer\" style=\"display:none;\">\n"
        f"{verdict_html}"
        f'<div class="sr-stimulus" style="font-size:0.97em;">{stimulus}</div>\n'
        f'<div style="height:1px;background:{_C_BORDER};margin:10px 0;"></div>\n'
        f'<div class="sr-stem" style="margin-bottom:10px;">{stem}</div>\n'
        f'<div style="margin-top:4px;">\n'
        f"{choices_html}"
        f"</div>\n"
        f"{self_check_html}"
        f"</div>\n"
    )

    # ------------------------------------------------------------------
    # Right rail assembly
    # ------------------------------------------------------------------
    rail = (
        f'<div class="sr-rail">\n'
        f'<div class="sr-rail-card">\n'
        f'<div style="font-size:0.8em;font-weight:700;color:#888;margin-bottom:8px;">REASONING MAP</div>\n'
        f'<div style="font-size:0.8em;color:#bbb;font-style:italic;line-height:1.4;">'
        f"(Premise / Conclusion / The gap \u2014 coming once items have a marked-conclusion field)</div>\n"
        f"</div>\n"
        f"{_reveal_tested_html(fields)}\n"
        f"{_rail_confidence_html()}\n"
        f"{_rail_next_button_html()}\n"
        f"</div>\n"
    )

    return (
        _SHARED_CSS
        + '<div class="sr-drill">\n'
        + main
        + rail
        + "</div>\n"
    )


# Backward-compat alias — existing callers that pass (fields, committed) still work,
# and the optional drill-state args forward through to build_reveal_html.
def build_item_answer_html(
    fields: dict[str, str],
    committed: str,
    prephrase_text: str | None = None,
    trap_chosen: str | None = None,
    trap_result: str | None = None,
) -> str:
    return build_reveal_html(
        fields,
        committed,
        prephrase_text=prephrase_text,
        trap_chosen=trap_chosen,
        trap_result=trap_result,
    )


# ---------------------------------------------------------------------------
# Name-the-trap chips HTML builder
# ---------------------------------------------------------------------------


def _build_trap_chips_html(
    item_traps: list[str],
    trap_chosen: str | None,
    trap_result: str | None,
    committed: str = "",
    answer_trap: str = "",
) -> str:
    """Build the amber trap-chip row for the name-the-trap interaction.

    item_traps: unique non-empty TrapChoiceX values from this item.
    trap_chosen: the tag string the learner clicked (or None).
    trap_result: 'correct' | 'wrong' | None.
    committed: the letter the learner picked (for the instruction copy).
    """
    if not item_traps:
        return ""

    pick_phrase = (
        f"Answer {committed} is a classic wrong-answer trap."
        if committed
        else "This is a classic wrong-answer trap."
    )
    prompt = (
        "Diagnose your miss: tap the trap type you think it is."
        if trap_chosen is None
        else "You tapped a trap type:"
    )
    header = (
        f'<div style="font-size:0.8em;font-weight:700;color:{_C_AMBER};'
        f'letter-spacing:0.06em;margin-bottom:6px;margin-top:4px;">NAME THE TRAP</div>\n'
        f'<div style="font-size:0.83em;color:#888;margin-bottom:8px;">'
        f"{_esc(pick_phrase)} {_esc(prompt)}</div>\n"
    )

    chips = ""
    for trap_tag in item_traps:
        label = _trap_label(trap_tag)
        gloss = _trap_description(trap_tag)
        tooltip = html.escape(gloss, quote=True) if gloss else ""
        escaped_tag = _esc(trap_tag).replace("'", "\\'")
        if trap_chosen is not None and trap_tag == trap_chosen:
            if trap_result == "correct":
                css_extra = " sr-chip-correct"
                suffix = " \u2713"
            elif trap_result == "wrong":
                css_extra = " sr-chip-wrong"
                suffix = " \u2717"
            else:
                css_extra = " sr-chip-selected"
                suffix = ""
        else:
            css_extra = ""
            suffix = ""

        if trap_chosen is not None:
            # Already selected — disable clicking
            chips += (
                f'<span class="sr-chip{css_extra}" title="{tooltip}" '
                f'style="cursor:default;">{_esc(label)}{suffix}</span>'
            )
        else:
            chips += (
                f'<span class="sr-chip{css_extra}" title="{tooltip}" style="cursor:pointer;" '
                f"onclick=\"pycmd('speedrun:trap:{escaped_tag}');\">"
                f"{_esc(label)}{suffix}</span>"
            )

    result_msg = ""
    if trap_chosen is not None and trap_result is not None:
        # Always name + define the actual trap on the chosen answer, so the
        # learner walks away knowing what the trap means (not just a slug).
        answer_label = _trap_label(answer_trap) if answer_trap else ""
        answer_gloss = _trap_description(answer_trap) if answer_trap else ""
        gloss_tail = f" \u2014 {_esc(answer_gloss)}" if answer_gloss else ""
        if trap_result == "correct":
            result_msg = (
                f'<div style="font-size:0.82em;color:{_C_GREEN};margin-top:8px;font-weight:600;">'
                f"\u2713 Yes \u2014 <strong>{_esc(answer_label)}</strong>{gloss_tail}</div>\n"
            )
        else:
            result_msg = (
                f'<div style="font-size:0.82em;color:{_C_CLAY};margin-top:8px;font-weight:600;">'
                f"\u2717 Not quite \u2014 it\u2019s <strong>{_esc(answer_label)}</strong>{gloss_tail}</div>\n"
            )

    return (
        f'<div style="margin-top:10px;padding-top:8px;border-top:1px solid #f0e8d0;">\n'
        f"{header}"
        f'<div style="margin-bottom:4px;">{chips}</div>\n'
        f"{result_msg}"
        f"</div>\n"
    )


# ---------------------------------------------------------------------------
# Bottom-bar HTML snippets for the Speedrun reviewer states
# ---------------------------------------------------------------------------


def bottom_commit_prompt(remaining: str = "", phase: str = "choices") -> str:
    """Bottom-bar centre content for the commit (question) phase.

    Replaces the standard 'Show Answer' button.  Remaining count is appended
    if non-empty so the stats display is unchanged.
    """
    if phase == "prephrase":
        msg = "Type your prediction above, then click \u2018Reveal choices\u2019"
    else:
        msg = "\u2191 Click a choice (A\u2013E) to commit your answer"
    return (
        "<table cellpadding=0><tr><td class=stat2 align=center>"
        f'<div style="color:#555;font-style:italic;padding:6px 0;">'
        f"{msg}"
        f"<span class=stattxt>{remaining}</span>"
        "</div>"
        "</td></tr></table>"
    )


def bottom_continue_button(ease: int = RATING_GOOD) -> str:
    """Bottom-bar centre content for the reveal (answer) phase.

    Shows a single 'Next question' button.  Ease is recorded silently;
    the button label no longer exposes it (de-Anki'd chrome, spec-ui §2).
    """
    return (
        "<center><table cellpadding=0 cellspacing=0><tr>"
        f'<td align=center><button onclick=\'pycmd("speedrun:continue");\'  '
        f'style="background:{_C_INDIGO};color:#fff;border:none;padding:8px 28px;'
        f'border-radius:6px;font-size:1em;cursor:pointer;font-weight:bold;" '
        f'title="Space / Enter">'
        f"Next question \u2192</button></td>"
        "</tr></table></center>"
    )
