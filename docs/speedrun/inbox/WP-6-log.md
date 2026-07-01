# Speedrun WP-6 — Inbox Log

> **Provisional local IDs** (L1, L2, …) — the orchestrator merges these into
> `decisions.md` and `backlog.md` after review. Do NOT promote IDs or edit the
> canonical logs directly from this file.
>
> Work package: **WP-6 — Desktop reviewer: commit-then-reveal + drawn-item render**  
> Date: 2026-07-01  
> Agent: Claude Sonnet 4.6 via Cursor

---

## Summary of what was built

### Level 1 — DONE (commit-then-reveal over LSAT Item cards)

**New file: `qt/aqt/speedrun.py`**  
Pure-Python helper module (no Qt, no anki wheel) with:
- `speedrun_card_type(note_type) -> 'item' | 'skill' | None` — the gate; all Speedrun behavior off for normal cards.
- `build_item_question_html(fields)` — commit phase: stimulus + stem + 5 clickable choice divs, each emitting `pycmd('speedrun:commit:X')`. Does NOT contain the correct answer.
- `build_item_answer_html(fields, committed)` — reveal phase: verdict banner (correct/wrong), highlighted choices, per-choice why-wrong + trap tags, stimulus trap tag, source, skill tags.
- `rating_for_committed(committed, fields)` — maps choice to FSRS rating (§5.1: wrong→Again(1), right→Good(3)).
- `bottom_commit_prompt()` / `bottom_continue_button(ease)` — bottom-bar HTML replacing the stock "Show Answer" / 4-ease buttons.

**Modified: `qt/aqt/reviewer.py`** (additive, gated)
- `_sr_committed`, `_sr_item_fields`, `_sr_card_kind` — per-card state, reset in `nextCard()`.
- `nextCard()` extended: detects Speedrun notetype; for Skill cards, calls `_speedrun_draw_item_fields()` (Level 2).
- `_speedrun_draw_item_fields()` — `isinstance(sched, V3Scheduler)` guard before calling `draw_item_for_skill`; returns `None` on failure → falls back to normal rendering.
- `_speedrun_item_fields_for_display()` — abstraction for Level 1 (reads item note's own fields) vs Level 2 (returns stored drawn-item fields).
- `_showQuestion()` — uses `build_item_question_html` for Speedrun cards; falls through to stock path for normal cards.
- `_showAnswer()` — uses `build_item_answer_html` + committed choice for Speedrun; falls through to stock path.
- `_linkHandler()` — `speedrun:commit:X` → records committed choice + calls `_showAnswer()`; `speedrun:continue` → calls `_answerCard(ease)` with deterministic ease.
- `onEnterKey()` — blocks stock "show answer" behavior during Speedrun question phase; Space/Enter on the reveal calls `speedrun:continue`.
- `_showAnswerButton()` — replaces "Show Answer" button with "Select A–E" prompt for Speedrun.
- `_showEaseButtons()` — replaces 4-button ease panel with single "Continue (correct/wrong)" button for Speedrun.

**New file: `qt/tests/test_speedrun.py`**  
35 pure-Python unit tests; run without anki wheel: `pytest qt/tests/test_speedrun.py`.  
Covers: card-type detection, correctness gate, FSRS rating mapping (§5.1), HTML builders (stimulus/stem/choices present, choices have pycmd commit, no answer in question HTML, verdict in answer HTML, per-choice highlights, trap tags, `#answer` anchor), bottom-bar helpers.

### Level 2 — FUNCTIONALLY WIRED (draw_item_for_skill path)

Level 2 is wired end-to-end:
1. `nextCard()` calls `_speedrun_draw_item_fields()` when card notetype is "LSAT Skill".
2. `_speedrun_draw_item_fields()` calls `self.mw.col.sched.draw_item_for_skill(card.id)` (WP-3's engine call), loads the drawn item note, returns its fields.
3. `_speedrun_item_fields_for_display()` returns the stored drawn-item fields for Skill cards.
4. All downstream HTML building, commit tracking, and answer routing uses the drawn item fields — but **answers the Skill card** via the normal `_answerCard()` path. Render-source and answer-target are fully decoupled (§8, [B002]).
5. On draw failure (empty pool, no identity tag, backend error), `_speedrun_draw_item_fields()` returns `None` → `_sr_card_kind` is reset to `None` → the Skill card falls back to normal Anki rendering (shows its own template).

**Status: Level 2 is code-complete and wired.** It has NOT had GUI testing on a live collection with real Skill cards + a populated item pool (that requires the dev's machine). It depends on WP-3's `draw_item_for_skill` already being in `main`.

---

## Decisions / alternatives / spec ambiguities

### L1 — Gating strategy: notetype name string match
- **Type:** decision
- **Status:** resolved locally
- **Chose:** Gate ALL Speedrun behavior on `note_type["name"] in ("LSAT Item", "LSAT Skill")`. Constants are defined once in `speedrun.py` and must match `build_seed_deck.py:NOTETYPE_ITEM` / `NOTETYPE_SKILL` exactly (they do: `"LSAT Item"`, `"LSAT Skill"`).
- **Considered:** gating on deck name (`LSAT Speedrun::*`) — rejected because deck membership is mutable (user could move cards); notetype name is the stable identity.
- **Risk:** if a user renames the notetype, Speedrun behavior silently disables. Acceptable for v1.
- **Ref:** `qt/aqt/speedrun.py:LSAT_ITEM_NOTETYPE`, `build_seed_deck.py:NOTETYPE_ITEM`

### L2 — Commit-then-reveal state model
- **Type:** decision
- **Status:** resolved
- **Chose:** Three per-card state fields on `Reviewer`: `_sr_card_kind` (type gate), `_sr_committed` (committed choice letter A-E), `_sr_item_fields` (drawn item fields for Level 2). All reset in `nextCard()`. This keeps Speedrun state co-located with reviewer state without forking the reviewer class.
- **Considered:** subclassing `Reviewer` → rejected because (a) the reviewer is instantiated in aqt/__init__.py with no plug-in point and (b) it would require more invasive upstream changes; (b) a separate state machine class → rejected as over-engineering for three fields.
- **Risk:** any upstream change to `Reviewer.__init__` must add these fields or we get an AttributeError. Low risk since we control the file.

### L3 — No reveal before commit (invariant enforcement)
- **Type:** decision
- **Status:** resolved
- **Chose:** The "Show Answer" button and Space/Enter keyboard shortcut are both blocked for Speedrun cards in the question state. The only way to advance is clicking a choice (A-E) in the card content. `onEnterKey()` returns early for Speedrun question state.
- **Considered:** allowing Space/Enter to trigger a commit at a random choice → confusing; allowing "Show Answer" to show a prompt instead of the answer → simpler but violates the spec's hard requirement.
- **Gap:** keyboard commit (press 1/2/3/4/5 for A/B/C/D/E) is not implemented. Mouse click is the only commit path. [→ B-new: keyboard shortcuts for choice commit]

### L4 — Level 2 fallback on empty pool
- **Type:** decision
- **Status:** resolved
- **Chose:** If `draw_item_for_skill` raises any exception (empty pool, no identity tag, backend error), log the error and fall back to rendering the Skill card's own template (normal Anki behavior). The user sees the skill card instead of a drawn item — degraded but not broken.
- **Considered:** show an error dialog → too disruptive; skip the card entirely → loses the FSRS review event; suspend the card → permanent and irreversible side effect. Graceful fallback is safest.
- **Gap:** the fallback gives no user-visible signal that pool is empty. A tooltip or info message would improve UX. [→ B-new: empty-pool UX signal]

### L5 — Level 2 render path: Python field injection (not RenderUncommittedCard RPC)
- **Type:** deviation from spec
- **Status:** resolved locally; flag for orchestrator
- **Context:** Spec-engine §8 says "render the drawn item via the existing `RenderUncommittedCard`/`RenderExistingCard` RPC." The RPC renders a card object through the notetype template. Using it would require creating an unsuspended dummy card for the drawn item note, which (a) temporarily modifies the collection, (b) risks the item entering the review queue, and (c) is fiddly from Python without writing a new RPC/helper.
- **Chose:** Read the item note's fields in Python (`get_item_fields(note)`) and build the HTML directly in `build_item_question_html` / `build_item_answer_html`. The HTML produced is semantically identical to what the LSAT Item template generates. This is simpler, faster, and doesn't touch the engine.
- **Risk:** if the notetype template is customized (e.g., CSS classes changed), the Python-built HTML won't pick it up. Acceptable for v1 since the template is controlled by `build_seed_deck.py`.
- **Overrides:** spec-engine §8 (partial) — does NOT use `RenderUncommittedCard`/`RenderExistingCard`; flag for future RPC-based render if template customization becomes a requirement.

### L6 — Field name assumptions (from build_seed_deck.py)
- **Type:** implementation constraint
- **Status:** documented
- **Fields used:** `Stimulus`, `Stem`, `ChoiceA`–`ChoiceE`, `CorrectChoice`, `WhyWrongA`–`WhyWrongE`, `TrapChoiceA`–`TrapChoiceE`, `TypeTag`, `SkillTag`, `TrapTag`, `Difficulty`, `Source`, `SyntheticFlag`.
- **Source of truth:** `build_seed_deck.py:_make_notetype_item()` (field list at line ~166).
- **Risk:** if any field name changes in `build_seed_deck.py`, the HTML builders silently produce empty content for that field (`.get(field, "")` pattern). No crash. A test against a real collection would catch this.

### L7 — Auto-answer (Continue button) vs manual ease selection
- **Type:** decision
- **Status:** resolved
- **Chose:** After commit, show ONE "Continue" button colored red (Again) or green (Good) based on correctness. Clicking it (or pressing Space/Enter) submits the deterministic ease. The user cannot override the ease in normal flow.
- **Considered:** showing two buttons (Wrong/Correct) and letting the user override — adds a manual step but allows "self-reported correct/wrong" like Anki's existing flow. Spec §5.1 says "correctness is a deterministic key lookup" which implies no user override.
- **Gap:** power users may want to override (e.g., "I got it right but guessed"). Deferred to v2.

---

## Bugs found / technical debt

### B-WP6-001 — No keyboard shortcut for choice commit
- **Status:** open
- **Detail:** Users must click a choice with the mouse. Pressing 1-5 (or A-E) to commit a choice is not implemented. For accessibility and speed, keyboard commits would be valuable.
- **Workaround:** mouse click.

### B-WP6-002 — No user-visible signal when Level-2 pool is empty
- **Status:** open
- **Detail:** If `draw_item_for_skill` fails (empty pool), the reviewer silently falls back to showing the Skill card's own template. The user doesn't know why they're seeing skill meta-content instead of an item.
- **Workaround:** check pool coverage with the seed deck builder.

### B-WP6-003 — Level 2 does not use RenderUncommittedCard RPC (L5 above)
- **Status:** tracked / intentional deviation
- **Detail:** See L5. May need to be revisited if template customization is required.

### B-WP6-004 — Auto-advance (secondsToShowQuestion) disabled for Speedrun
- **Status:** open
- **Detail:** Auto-advance is skipped for Speedrun cards (the auto-advance timer call at the end of `_showQuestion()` is omitted). This is intentional (the commit-then-reveal flow is learner-driven), but it means the auto-advance feature is silently no-op for Speedrun decks.

### Pre-existing: B023 / B026 (fmt/lint debt in tools/speedrun/)
- Not introduced by WP-6. These are the ruff/dprint issues in `tools/speedrun/tagging/` and `tools/speedrun/deck/` that were present in `main` before this branch.

---

## [B002] risk note — render-vs-answer wiring

This is the risk flagged in `backlog.md` and `build-plan.md`. WP-6's implementation:
- **Does NOT fork or alter `answer_card`, FSRS, undo, or sync** (D-SR3, D-SR4). The ease value determined by `rating_for_committed` is passed to the existing `_answerCard(ease)` which calls `answer_card(parent=self.mw, answer=answer)` — the same call as stock Anki.
- **Does decouple render-source from answer-target** for Level 2: the drawn item note's fields are rendered, but the skill card is answered. The Rust engine's `draw_item_for_skill` handles the sidecar log (repeat-avoidance).
- **L5 deviation**: render path uses Python field injection rather than `RenderUncommittedCard` RPC — functionally equivalent for v1.

The [B002] risk is mitigated. The one real residual risk is: the answer pipeline is exercised with `_sr_card_kind` truthy, meaning `_showAnswer()` and `_showEaseButtons()` take the Speedrun branches. A regression in those branches could affect ALL Speedrun reviews. This is why the unit tests test the state-machine logic explicitly.

---

## Manual GUI verification required

**This agent cannot drive the Qt GUI headlessly.** The following must be manually verified on the dev's machine:

1. Open a Speedrun deck containing `LSAT Item` cards.
2. Start review (Level 1 path):
   - Confirm: stimulus + stem + choices show with clickable choice divs.
   - Confirm: "Show Answer" button is REPLACED by "Select a choice above" prompt.
   - Confirm: clicking a choice (e.g., B) shows the reveal with verdict banner + per-choice explanations.
   - Confirm: the "Continue" button is green for a correct choice, red for wrong.
   - Confirm: Space/Enter after commit submits Continue; Space/Enter before commit does nothing.
   - Confirm: a wrong answer advances FSRS with Again(1); a correct answer with Good(3). (Check revlog.)
   - Confirm: undo works (normal Anki undo path — not forked).
3. Open a Speedrun deck containing `LSAT Skill` cards (Level 2 path):
   - Confirm: if item pool is populated, a drawn item is shown (not the skill card's own template).
   - Confirm: commit-then-reveal works identically to Level 1.
   - Confirm: the SKILL card's FSRS state is updated (not the item card's).
   - Confirm: if item pool is empty, the skill card's template shows as fallback (no crash).
4. Open a normal Anki deck (e.g., Basic):
   - Confirm: behavior is EXACTLY as before WP-6 — standard "Show Answer" button, 4 ease buttons, normal answer flow.

---

<sub>WP-6 build agent — 2026-07-01 — Claude Sonnet 4.6 via Cursor</sub>
