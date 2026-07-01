# WP-21 Build Log — Drill interaction surface (prephrase + name-the-trap)

> iris-log inbox format. Agent: WP-21 subagent · Date: 2026-07-01.
> Source decisions: D-SR33, D-SR34, D-SR35. Companion: `docs/speedrun/spec-ui.md §3.2`.

---

## L1 — Prephrase self-check UX

**Decision taken:** Prephrase self-check ("did your prediction match?") is
**pure JS / ephemeral** — no Python state, no database write, no pycmd round-trip.
The reveal HTML inlines `srSelfCheck(v)` JS; a Yes/No button visually toggles.
The check result is session-display-only (calibration signal for the learner;
not a graded signal → spec §4 confirms prephrase is self-scored).

**Rationale:** D-SR34 explicitly says "v1 is self-scored"; spec-ui §4 says
"prephrase / confidence → session-local for v1 (calibration)". Storing the
self-check result in `Card.custom_data` (no schema change) was considered but
deferred — it adds no value without analytics on top, and analytics need WP-17.

**Risk:** The self-check result is lost on card navigation. Acceptable for v1.
Promote to a decision (D-SR36) if we choose to persist it in phase-2.

---

## L2 — Name-the-trap wired to TrapChoiceX (deterministic, no AI)

**How it works:**
1. On a wrong commit, `build_reveal_html` calls `_collect_item_traps(fields)` to
   gather all unique non-empty `TrapChoiceA–E` values from the current item.
2. These are displayed as amber chips below the committed (wrong) choice.
3. User clicks a chip → `pycmd('speedrun:trap:<trap-tag>')` →
   `_sr_on_trap_chosen(trap_tag)` in `reviewer.py`.
4. Check: `expected = fields[f"TrapChoice{committed}"].strip()` vs `trap_tag`.
   Normalized via `.removeprefix("trap::")` for loose match. Result: `"correct"`
   or `"wrong"` stored in `_sr_trap_result`, re-injected into reveal HTML.
5. **No AI anywhere in this path.** Fully deterministic from the item fields.

**Edge cases handled:**
- `TrapChoiceX == ""` for the committed choice → no name-the-trap chips shown
  (correct answer committed would have `TrapChoiceX == ""`).
- Chips disabled after selection (cursor: default + no onclick).
- Correct chip turns green; wrong chip turns clay; both show icon (✓/✗).

**Note on chip candidates:** Chips are sourced from ALL `TrapChoiceA–E` values
in the item (not just the committed choice's trap). This is intentional — the
learner should pick from the full item's trap set, not a single revealed trap.
The correct answer for THEIR choice is still checked deterministically.

---

## L3 — Reasoning map rail OMITTED (marked-conclusion gap)

**Status: known gap, logged per task instructions.**

The spec-ui §3.2 and the mockup show a "Reasoning Map" right rail with
Premise / Conclusion / The gap. This cannot be built deterministically because
the LSAT Item notetype has **no `MarkedConclusion` field** (or equivalent).
The stimulus text cannot be split into Premise/Conclusion/Gap without:
- A heuristic parser (unreliable, not AI-contract-compliant), OR
- A new item field added to the notetype and seed deck.

**Decision taken:** Show a placeholder stub in the reasoning-map rail:
`"(Premise / Conclusion / The gap — coming once items have a marked-conclusion
field)"`. This is honest and non-fabricated. The rail card IS rendered so the
layout matches the mockup.

**What to do next:** Add `Conclusion` (or `Argument`) field to `LSAT Item`
notetype + `build_seed_deck.py` → then surface it here deterministically.
This is an additive data change, no schema change (just a new note field).
Track as a backlog item (→ B033 or next free ID per AGENTS.md).

---

## L4 — Confidence storage: session-local (ephemeral JS)

**Decision taken:** Confidence tap (low/medium/high dot buttons) is pure JS —
`srConf(n)` inline function in the reveal HTML. The selected level is displayed
visually in amber but not persisted.

**Rationale:** D-SR34 says "session-local for v1 (calibration)"; spec-ui §4 says
"`Card.custom_data` only if needed (no schema change)". Since we have no analytics
consumer for confidence data yet, persisting it adds overhead with no payoff.
Promote to a decision if we build calibration reports.

---

## L5 — Phase state machine (`_sr_phase`)

The WP-6 commit-then-reveal surface used a binary question/answer state.
WP-21 adds a three-phase sub-state on top of Anki's `state`:

```
Card loaded
  └→ _sr_phase = 'prephrase'   (if LSAT Item/Skill card)
       User clicks "Reveal choices" or "Skip"
         └→ _sr_phase = 'choices'
              User clicks a choice
                └→ _sr_committed = 'X', _showAnswer() called
                     └→ _sr_phase = 'revealed'  (set inside _showAnswer)
                          User clicks trap chip (if wrong)
                            └→ _sr_trap_chosen, _sr_trap_result set; HTML re-injected
                          User clicks "Next question" / Space/Enter
                            └→ _answerCard(ease) → nextCard() → reset
```

**Entry invariant:** `_sr_phase` resets to `'prephrase'` in `nextCard()`. The
prephrase phase is always shown for untimed drills (default). Timed sections
(not yet built) would set `_sr_phase = 'choices'` directly — deferred to WP-22.

---

## L6 — Design language implementation notes

Implemented per spec-ui §2:
- Palette: #F5F7FA paper, #1B2430 ink, #3E3A8C indigo accent, #2E7D5B green,
  #B4472E clay, #C99A2E amber (trap chips only).
- Serif (Georgia) for stimulus text.
- Monospace for type tags and skill tags.
- Two-column layout (main canvas + right rail) via flexbox in all three phases.
- Amber exclusively for trap chips and TIP label — no other amber elements.

Deviations from mockup (honest):
- **No session progress bar** ("Question 4 of 10") — session layer not built yet
  (WP-22/WP-23). The bottom bar still shows Anki's due-count stats.
- **No "Untimed" badge** in top-right — mode/session layer not built.
- **Reasoning map** omitted (L3 above).
- Font: Georgia serif (system) not a custom web font — acceptable for v1.
- Choice accordion expand/collapse uses inline onclick JS (no external function);
  script tags run via Anki's `setInnerHTML` which re-executes them.

---

## L7 — Pre-existing build issues (B023/B026)

Pre-existing fmt/lint debt (B023 format, B026 mypy) is distinct from WP-21 work.
WP-21 does NOT fix these. The reviewer.py and speedrun.py changes in this WP
are lint-clean (verified via `just lint`). If the build reports B023/B026-related
failures, those are pre-existing and not introduced by WP-21.

---

## L8 — Merge-risk vs WP-20

WP-20 reshapes `ts/routes/speedrun-dashboard/`. WP-21 owns:
- `qt/aqt/speedrun.py` (full rewrite)
- `qt/aqt/reviewer.py` (additive changes to Speedrun section only)

**No TypeScript files touched by WP-21.** Overlap risk:
- `qt/aqt/reviewer.py`: WP-20 does NOT touch this file (it owns dashboard TS).
  No conflict expected.
- `qt/aqt/speedrun.py`: WP-20 does NOT touch this file. No conflict.
- Merge order: either WP-20 or WP-21 can land first without conflict.

---

<sub>Created by WP-21 subagent · 2026-07-01</sub>
