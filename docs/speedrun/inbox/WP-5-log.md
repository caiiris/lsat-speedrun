# Speedrun WP-5 — Inbox Log

> **Provisional local IDs** (L1, L2, …) — the orchestrator merges these into
> `decisions.md` and `backlog.md` after review. Do NOT promote IDs or edit the
> canonical logs directly from this file.
>
> Work package: **WP-5 — Mastery query (`skill_mastery`)**  
> Date: 2026-06-30  
> Agent: Sonnet 4.6 via Cursor

---

## Decisions / alternatives / spec ambiguities

### L1 — Mastered threshold: 0.9 (spec §5.4 gap)
- **Type:** decision (local, pending promotion)
- **Status:** resolved locally
- **Context:** spec-engine §5.4 says "mastered (count of skill cards whose FSRS recall ≥ threshold)" but does not fix the threshold value. D-SR5 doesn't specify it either.
- **Chose:** `MASTERY_RECALL_THRESHOLD = 0.90`. Rationale: (a) 90% recall corresponds to the user having near-zero chance of forgetting the skill, matching the "mastered" colloquial meaning; (b) Anki's own "desired retention" defaults to 0.90 in FSRS; (c) lower values (0.80) let marginally-learned skills count as mastered, inflating the dashboard; (d) higher (0.95) is too strict at early stages when skills are just becoming stable. The threshold is a module-level constant — easy to change via a single-line config decision if the orchestrator disagrees.
- **Risk:** Threshold may need calibration once real user data exists. Flag for WP-7 (Memory score).
- **Ref:** spec-engine §5.4, D-SR5

### L2 — Skill identity from note tags (spec §7 + build_seed_deck.py)
- **Type:** decision (local, confirming spec)
- **Status:** resolved locally
- **Context:** The spec says skill identity is "stored on the skill card via existing `Card.custom_data` JSON field and/or tags." `build_seed_deck.py` stores the `IdentityTag` (e.g., `type::assumption`) as a note tag — the `notes.tags` column.
- **Chose:** Group by the **first tag** on the note that matches the pattern `type::*`, `skill::*`, or `trap::*`. This is the `IdentityTag` from `build_seed_deck.py`. For LSAT Skill notes there is exactly one such tag. For robustness: if a note has multiple matching tags (shouldn't happen for skill notes), pick the first lexicographically.
- **Risk:** If future content uses `custom_data` instead of tags for skill identity, this function would need updating. The storage query filters by notetype name = "LSAT Skill" as the primary guard.
- **Ref:** spec-engine §7, build_seed_deck.py line 486

### L3 — Filter by notetype name "LSAT Skill" (design choice)
- **Type:** decision (local)
- **Status:** resolved locally
- **Context:** The mastery query must distinguish skill cards (LSAT Skill notetype) from item cards (LSAT Item notetype — which are suspended pool cards). Filtering by deck alone is insufficient if both notetypes coexist in the same deck hierarchy.
- **Chose:** JOIN with `notetypes` table and filter `nt.name = 'LSAT Skill'`. This cleanly separates skill cards. The notetypes table has a unique index on `name`, so the subquery is O(1).
- **Considered:** Filtering by tag pattern (`n.tags LIKE '% type::%'`) — rejected because item notes also carry skill/type/trap tags; this would double-count.
- **Risk:** None — notetype name is a stable contract (established in WP-1/WP-2).
- **Ref:** build_seed_deck.py, NOTETYPE_SKILL = "LSAT Skill"

### L4 — Recall computation: Rust (not SQL) for FSRS retrievability
- **Type:** decision (local)
- **Status:** resolved locally
- **Context:** The spec says "one indexed SQL aggregate". Pure SQL could use `extract_fsrs_retrievability` (a custom SQLite scalar function already registered in `storage/sqlite.rs`), but this would require passing timing parameters (days_elapsed, now, next_day_at) into the SQL query and doing aggregation in SQL — complex and fragile. Alternatively, fetch per-card rows and aggregate in Rust.
- **Chose:** Single indexed SQL query fetches `(note_tags, card_data, due, ivl)` for skill cards in the deck hierarchy. Rust iterates this result set, calls `FSRS::new(None).current_retrievability_seconds(...)` (the EXISTING rslib facility — not forked), groups by skill, and aggregates. This is ONE SQL round-trip (indexed), satisfies D-SR5's "single indexed aggregate" intent, and keeps correctness of FSRS recall in the existing Rust code.
- **Why "one indexed SQL query" is preserved:** The SQL uses indexes `ix_cards_sched(did,queue,due)` for deck filter, `ix_cards_nid` for the note join, `idx_notes_mid` for notetype filter, and `idx_notetypes_name` for name lookup. All in one prepared statement; no per-card Rust SQL calls.
- **Ref:** D-SR5, spec-engine §5.4, storage/sqlite.rs add_extract_fsrs_retrievability

### L5 — Pre-existing risk: LSAT Skill deck_id must match the collection
- **Type:** risk
- **Status:** open
- **Context:** The `skill_mastery(deck_id)` RPC requires the caller to pass the correct deck ID for the "LSAT Speedrun::Skills" deck (or its parent). If called with deck_id = 0 or an unrelated deck, the query returns an empty result (not an error). This is correct behavior — an empty result means "no skill cards found."
- **Chose:** Return empty `SkillMasteryResponse` for an unknown or empty deck — same as any dashboard query over an empty deck.
- **Ref:** spec-engine §5.5

### L6 — Cards without FSRS memory state (new cards, not yet reviewed)
- **Type:** decision (local)
- **Status:** resolved locally
- **Context:** Newly-created skill cards have no memory state (`card.data` has no `s`/`d` fields). `memory_state()` returns `None`. These cards count toward `total` but have `recall = 0.0` (they have never been reviewed, so they are definitionally not mastered).
- **Chose:** Cards with no memory state contribute `recall = 0.0` to avg_recall and do NOT count as mastered. This is honest: an unreviewed card is never mastered.
- **Ref:** rslib/src/storage/card/data.rs CardData::memory_state()

## Bugs found

### L7 — None found in files touched by WP-5
- **Type:** pre-existing bug report
- **Status:** none found
- **Context:** Examined `rslib/src/stats/service.rs`, `rslib/src/storage/card/mod.rs`, `rslib/src/stats/graphs/retrievability.rs`, `rslib/src/storage/sqlite.rs`. No pre-existing bugs in the code paths WP-5 touches. The `extract_fsrs_retrievability` SQLite function is correct (cross-referenced with `current_retrievability_seconds` usage in stats/card.rs).
