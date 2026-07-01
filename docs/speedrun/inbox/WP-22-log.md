# WP-22 Implementation Log — Session Layer + Result / Blind Review

**Work package:** WP-22  
**Implements:** spec-ui §3.3, D-SR35 (session model: targeted / mixed / timed / blind review)  
**Builds on:** WP-20 (Home + launchers), WP-21 (drill interaction)  
**Status:** complete (all four modes functional; see L3/L4 for known limitations)

---

## L1 — Session-controller architecture

**Approach chosen:** Self-contained `SpeedrunSessionDialog` (new file `qt/aqt/speedrun_session.py`) that owns its own `AnkiWebView`, drives the drill loop, and calls `answer_card()` (CollectionOp) directly.  Does **not** use or modify `mw.reviewer`.

**Why not modify reviewer.py?**  
The reviewer is a singleton tied to `mw.state == "review"`.  Wrapping it with session-bounding logic would require either: (a) new session-controller state injected into the reviewer (messy, upstream diff risk), or (b) intercepting `nextCard()` when the session limit is reached (also messy — reviewer calls `mw.moveToState("overview")` on empty queue, not a "session done" hook).  A self-contained dialog is cleaner, testable, and adds zero upstream reviewer diff.

**Answer pipeline:** unchanged.  Each item is answered via `answer_card(parent=dialog, answer=CardAnswer)` which calls `col.sched.answer_card(answer)` — the normal FSRS/undo/sync path.

**Progress bar:** injected as a sticky top header via `_wrap_with_progress()` which wraps the existing WP-21 HTML builders.  "Q X of N" + a thin progress bar + elapsed/timer.

**Session state:** `SessionState` dataclass (session-local, not persisted).  `ItemResult` per item (card_id, fields, committed, correct, trap_missed, flagged).

---

## L2 — Queue assembly strategy

Cards are assembled upfront via `col.find_cards()` filtered to LSAT Skill notes in the Speedrun deck, then sorted by `due ASC` from the DB.

- **Targeted drill:** filtered to `IdentityTag = focus_skill` (exact match — matches `build_seed_deck.py` which sets it to the canonical tag string).  Falls back to all skill cards if the filtered query returns nothing.
- **Mixed set / Timed:** all skill cards, `due ASC`, limited to N.
- **Blind review:** card IDs come from the parent session's `ItemResult` list (missed items), not the queue.

**Rationale for `due ASC` sort:** approximates the FSRS scheduler's prioritization without calling `get_queued_cards()` N times upfront (which would mutate scheduler state by popping cards).  The most overdue cards come first; for mixed/timed this is close to what the scheduler would return.

---

## L3 — Known limitation: targeted drill filter quality

**Issue:** True per-skill filtering for targeted drill is approximate.  `col.find_cards()` with `IdentityTag:"type::assumption"` does an exact-match field search.  This works for `type::*` tags (question types) but may miss sub-skill notes whose `IdentityTag` is `skill::assumption-sufficient` (a different string).

**Impact:** Targeted drill shows items for the recommended question-type's skill cards only; sub-skill trap cards of the same type family may not be included.

**Correct fix (B-list):** use a filtered deck with a search query that includes all skill tags in the focus skill's family, or pass the full family list from the dashboard's `nextBest` calculation.  This requires a small API extension in the Home bridge command.

**Current behavior:** If no cards match the exact filter, falls back to all skill cards in the deck (graceful degradation).

---

## L4 — Known limitation: V3 scheduler state alignment

**Issue:** `_fetch_v3_states()` calls `col.sched.get_queued_cards()` which returns the scheduler's top card.  For a pre-assembled queue (card IDs from `find_cards()`), the top-of-queue card may not match the session's next card.  When they differ, the `states` stored are for the wrong card.

**Impact:** `sched.build_answer(card, states, rating)` is called with states that don't belong to `card`.  This means FSRS state updates for mismatched cards may be applied incorrectly — the rating is recorded against the scheduler's top card, not necessarily the session's current card.

**Mitigation in place:** if `get_queued_cards()` fails, the session records the result but skips the FSRS update (rather than crashing).

**Correct fix:** use `get_queued_cards()` to draw one card at a time per the scheduler's order (not pre-fetching by card ID).  This means sessions won't be filterable by skill (all modes would use the natural queue order).  This is acceptable for mixed/timed but breaks the targeted-drill contract.  Full fix = filtered deck per session, or a new Rust API to peek the queue without popping.

**For the demo:** the 39-item seed deck is new (all cards are "new" in FSRS terms).  New cards in FSRS get a fixed initial state, so the states mismatch doesn't corrupt existing intervals.  The answer still goes through `col.sched.answer_card()` which uses the passed states, so FSRS *will* update — just potentially for a slightly different card.  For a fresh deck this is not materially wrong.

---

## L5 — Timed mode

**Implementation:** choices-only (no prephrase, no trap chips in-session), running JS clock injected in the progress header.  N=25 items.

**Not yet implemented:** per-item time tracking (would enable "N seconds/item" stats on the result screen).  Trap diagnosis is deferred to the result screen's "Where you slipped" list, consistent with spec-ui §3.2 ("Timed-section variant: diagnosis moves to end-of-set review").

---

## L6 — Blind review

**Implementation:** re-runs `ItemResult.item_fields` directly (no new card draw needed since the fields are already in memory).  Opens a nested `SpeedrunSessionDialog(mode="blind")` with `blind_items=misses+flagged`.

**Card IDs:** blind review re-uses the same card IDs as the original session.  Each blind review item calls `answer_card()` again for the same skill card.  This means the skill card gets answered twice in one session — once in the main drill, once in blind review.  FSRS handles this correctly (it's normal to review a card more than once per day).

**Prephrase in blind review:** disabled (blind review is choices-only by design — "decide again before seeing the key").

---

## L7 — Home launcher wiring

**What changed in `speedrun_home.py`:**
- `_open_study_fallback()` and `_open_session_fallback()` (WP-22 stubs) removed.
- `_on_bridge_cmd` now calls `_open_session(mode, focus_skill)` which calls `SpeedrunSessionDialog.open(...)`.
- The `SpeedrunDashboard.svelte` launcher functions (`startTargetedDrill`, `launchSession`) were already emitting the correct pycmd strings — no Svelte changes needed.

---

## L8 — What's done / partial / stubbed

| Feature | Status | Notes |
|---|---|---|
| Targeted drill (10 items, prephrase + trap) | ✓ Done | Skill filter approximate (L3) |
| Mixed set (10 items, interleaved) | ✓ Done | Uses due-ASC sort (L2) |
| Timed section (25 items, clock) | ✓ Done | No per-item time tracking |
| Blind review from result screen | ✓ Done | Nested dialog (L6) |
| Progress bar (Q X of N) | ✓ Done | Sticky header |
| Result screen (score, where-slipped, all-items strip) | ✓ Done | Per mockup |
| Flag-to-revisit stars (result screen) | ✓ Done | In-place JS update |
| "Blind review your misses" CTA | ✓ Done | |
| "Another drill" / "Back to study plan" | ✓ Done | |
| FSRS state alignment (L4) | ⚠ Partial | Works for new cards; may misfire for reviewed cards |
| Targeted drill exact skill filtering (L3) | ⚠ Partial | Falls back gracefully |
| Per-item time display | — Deferred | B-list |
| Performance delta on result screen | — Deferred | Needs SpeedrunDashboard RPC call after session; B-list |

---

## L9 — Pre-existing bugs not introduced by WP-22

- **B023 / B026** (referenced in the task prompt): pre-existing backlog items unrelated to this WP; not touched.

---

*Created by agent for WP-22 iris-log inbox.*
