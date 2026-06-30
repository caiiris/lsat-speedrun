# Speedrun WP-4 — Inbox Log

> **Provisional local IDs** (L1, L2, …) — the orchestrator merges these into
> `decisions.md` and `backlog.md` after review. Do NOT promote IDs or edit the
> canonical logs directly from this file.
>
> Work package: **WP-4 — Interleaving order (`ReviewCardOrder` variant)**  
> Date: 2026-06-30  
> Agent: Sonnet 4.6 via Cursor

---

## Decisions / alternatives / spec ambiguities

### L1 — How to derive a card's question type (spec ambiguity)
- **Type:** decision (local, pending promotion)
- **Status:** resolved locally
- **Context:** The spec says "determine each card's question-type from its tags/note (`type::X`)" but doesn't specify whether to look at the card's `custom_data` field, the note's tags, or elsewhere. Each `DueCard` in the queue builder has a `note_id` but no tags.
- **Chose:** Fetch the note tags via a single batched query (`storage.get_note_tags_by_id_list`) after review cards are gathered, then parse the first `type::*` segment from each note's tag string. This is the cheapest correct approach: one SQL round-trip for all review cards, no per-card extra queries, consistent with D-SR24 (native `::` tags).
- **Considered:** (a) Storing the type in `Card.custom_data` — would require WP-1 deck builder to write it there too, adding coupling; (b) adding a `type` column to the SQL query in `review_order_sql` — would require joining `notes` in the DB fetch and touching the shared `due_cards.sql`, which is higher merge risk; (c) fetching a full `Note` per card — equivalent but heavier than `NoteTags`.
- **Impact:** The implementation depends on LSAT Skill cards having `type::*` tags on their notes (written by WP-1 `build_seed_deck.py`). Cards without a `type::*` tag share a single "untyped" group and participate in the round-robin, preserving FSRS meta-cards in the queue without crashing.
- **Ref:** spec-engine §5.3, D-SR24, `rslib/src/scheduler/queue/builder/gathering.rs`

### L2 — Interleaving insertion point: builder vs SQL (design choice)
- **Type:** decision (local)
- **Status:** resolved locally
- **Context:** The WP-2 stub already maps `InterleavedSkills` → `ReviewOrderSubclause::Day` as the DB sort order. We could add a SQL-level sort, or do the reorder in the builder.
- **Chose:** Keep the DB fallback (`ReviewOrderSubclause::Day`) and reorder **in the builder** (`gathering.rs`) after all review cards are fetched. This approach: (1) avoids touching `storage/card/mod.rs` (shared/sensitive), (2) the interleaving requires tag data not available in pure SQL without a join, (3) keeps the DB query fast and consistent with other orders.
- **Considered:** SQL-level interleaving via a window function or JOIN — not feasible without schema changes or very complex SQL; SQLite doesn't have a standard PARTITION BY ROW_NUMBER() that maps cleanly to round-robin.
- **Impact:** Minimal; the `storage/card/mod.rs` fallback is left as-is (one-line, already correct for gathering order).
- **Ref:** `rslib/src/storage/card/mod.rs:898`, `rslib/src/scheduler/queue/builder/gathering.rs`

### L3 — Round-robin tie-breaking: group order equals gather order (design choice)
- **Type:** decision (local)
- **Status:** resolved locally
- **Context:** The round-robin emits one card per group per pass. The order in which groups are visited in each pass equals the order they first appeared in the gathered review queue (i.e., the due-date order from the DB fallback). Within each group, the within-group order is also the due-date order.
- **Chose:** First-seen group order as the round-robin rotation order. This is deterministic and preserves the FSRS due-date signal as a secondary tiebreaker within groups.
- **Considered:** Alphabetical by type name (unstable across taxonomy changes); random (non-deterministic, bad for ablation); by group size descending (front-loads dominant types, not desired).
- **Ref:** `gathering.rs` `interleave_review_cards_by_question_type`

### L4 — Untyped cards (no `type::*` tag) participate in round-robin (design choice)
- **Type:** decision (local)
- **Status:** resolved locally
- **Context:** LSAT Meta cards (vocab flashcards) and any skill card that hasn't been tagged yet carry no `type::*` tag. These appear in the review queue when they're due.
- **Chose:** Cards without a `type::*` tag are bucketed into a single "untyped" group (key = empty string). This group participates in the round-robin alongside typed groups — so untyped cards are interleaved rather than blocked at the front or back.
- **Risk:** If a deck has many untyped cards (e.g., the full Meta deck), the untyped group may be large and produce consecutive untyped cards after the typed groups exhaust. This is acceptable (they're not skill cards and the spec only specifies "skill cards").
- **Ref:** `extract_question_type` function, spec-engine §5.3

### L5 — `search_nids` deduplication required (bug avoidance)
- **Type:** bug avoidance / implementation note
- **Status:** resolved
- **Context:** `storage.get_note_tags_by_id_list` uses `with_ids_in_searched_notes_table`, which inserts into a temporary table with `nid integer PRIMARY KEY`. If a note has multiple review-due cards (possible for multi-card notetypes), inserting the same `nid` twice raises a UNIQUE constraint error.
- **Chose:** Deduplicate note IDs before calling `get_note_tags_by_id_list` using a `HashSet<NoteId>` passed through an ordered filter to preserve the first-occurrence order.
- **Ref:** `gathering.rs` `interleave_review_cards_by_question_type`, `storage/note/search_nids_setup.sql`

### L6 — FTL string placement and naming convention (implementation note)
- **Type:** implementation note
- **Status:** resolved
- **Context:** The FTL key `deck-config-sort-order-interleaved-skills` maps to the TypeScript function `tr.deckConfigSortOrderInterleavedSkills()` by Anki's camelCase convention. Added after `deck-config-sort-order-retrievability-descending` in `ftl/core/deck-config.ftl`.
- **Ref:** `ftl/core/deck-config.ftl`, `ts/routes/deck-options/choices.ts`

### L7 — Simulator (fsrs/simulator.rs) left as-is (intentional)
- **Type:** decision (local)
- **Status:** resolved
- **Context:** `simulator.rs` maps `InterleavedSkills → None`. The comment in that file says "InterleavedSkills is a Speedrun queue-builder reordering (WP-4); it doesn't translate to a simulator load-balance interval shift." This is correct: interleaving is a session-ordering choice, not an interval or difficulty tweak.
- **Chose:** Leave `simulator.rs` unchanged. The `None` mapping is the correct semantic: the simulator ignores session ordering.
- **Ref:** `rslib/src/scheduler/fsrs/simulator.rs:120-122`

---

## Bugs found

### L8 — No pre-existing bugs found in the builder path
- **Type:** pre-existing issue scan
- **Status:** no action needed
- **Context:** Reviewed `gathering.rs`, `mod.rs`, and `storage/card/mod.rs` for related bugs. The existing code is clean; the WP-2 placeholder (Day fallback for InterleavedSkills) is correct and expected.

---

## Risks

### L9 — Merge risk with WP-3
- **Type:** merge risk
- **Status:** open (for orchestrator)
- **Context:** WP-3 adds a new `selection.rs` and modifies `scheduler/service/mod.rs`. WP-4 modifies `builder/gathering.rs` and `builder/mod.rs`. These are different files. Overlap risk: `builder/mod.rs` — WP-3 may touch it to wire `gather_cards` or `build_queues`. Recommend: merge WP-4 first, then WP-3 rebases.
- **Ref:** build-plan.md collision zones, WP-3/4 dispatch matrix

### L10 — `just build` required before `just test-rust` (operational note)
- **Type:** operational note
- **Status:** resolved operationally
- **Context:** The worktree starts without an `out/` directory. Bare `cargo check` fails because build scripts (rslib/i18n/gather.rs) need generated files. `just build` must run first to produce `out/` and the i18n RS module; then `just test-rust` runs the suite.
- **Ref:** CLAUDE.md, B008 (build env)

---

<sub>WP-4 build agent (Sonnet 4.6) · 2026-06-30</sub>
