# Speedrun WP-7 — Inbox Log

> **Provisional local IDs** (L1, L2, …) — the orchestrator merges these into
> `decisions.md` and `backlog.md` after review. Do NOT promote IDs or edit the
> canonical logs directly from this file.
>
> Work package: **WP-7 — Memory score + give-up gate**  
> Date: 2026-06-30  
> Agent: Sonnet 4.6 via Cursor

---

## Decisions / alternatives / spec ambiguities

### L1 — Memory proto exposure deferred to WP-14
- **Type:** decision (local, pending promotion)
- **Status:** resolved locally
- **Context:** The task brief offers two paths for exposing Memory to Python/dashboard: (a) add a `MetaMemory` protobuf RPC in `proto/anki/stats.proto`, run a full `just build` to regenerate bindings, and wire a pylib stub; or (b) fully implement + unit-test the Rust function and hand the RPC wire-up to WP-14.
- **Chose:** Option (b) — defer proto wiring to WP-14. Rationale:
  1. A full `just build` in a fresh worktree with no `out/` cache is slow (10–20 min) and risky to interrupt.
  2. WP-6 (desktop reviewer) is running in parallel touching `qt/` and `ts/reviewer/`; any proto regeneration in WP-7 would produce a merge conflict in the generated `_backend_generated.py` and `backend.ts` files, requiring manual merge sequencing.
  3. WP-14 (Performance + Readiness + dashboard) already depends on WP-7 and will perform a full `just build` for its own RPCs anyway — adding the `MetaMemory` RPC there costs zero extra build time.
  4. The Rust implementation is complete and fully unit-tested; WP-14 has a clear, tested interface (`Collection::memory_score_impl`) to wrap.
- **Risk:** Memory is not callable from Python until WP-14 lands. This delays end-to-end dashboard integration but does not block any Phase-1 acceptance criterion (spec-measurement AC 1 requires the computation, not the dashboard wire-up).
- **Ref:** spec-measurement §4.1, AC 1; build-plan.md WP-7/WP-14; D-SR10

### L2 — Bootstrap band: 1 000 percentile-bootstrap with a fixed seed
- **Type:** decision (local)
- **Status:** resolved locally
- **Context:** spec-measurement §4.1 specifies "band = bootstrap CI over per-card R" but does not fix the number of resamples, the CI level, or whether to use percentile vs BCa bootstrap.
- **Chose:** 1 000 percentile resamples, 95% CI (2.5 / 97.5 percentiles), seeded with a fixed constant (`0xDEAD_BEEF_1234_5678`). Rationale:
  - 1 000 resamples is sufficient for a smooth CI on ≤ 200 Meta cards (the LSAT Meta deck is small — WP-1 seeded 13 Meta notes). At this N, Monte-Carlo noise in the CI boundaries is < 0.001.
  - Percentile bootstrap (vs BCa) is simpler, well-understood, and adequate when the underlying distribution (per-card recall) is reasonably symmetric (it often is at high recall). BCa adds complexity without meaningful benefit for this use case.
  - Fixed seed makes the score bit-reproducible for the same input, which aids debugging and eval scripting. The seed is a module constant; changing it requires no interface change.
- **Risk:** At very low N (1–2 Meta cards), the CI will be degenerate (all resamples identical). This is handled correctly — the CI collapses to the mean, which is the honest answer.
- **Ref:** spec-measurement §4.1

### L3 — Unreviewed Meta cards: recall = 0.0 (same as WP-5)
- **Type:** decision (local, confirming WP-5 precedent)
- **Status:** resolved locally
- **Context:** New Meta cards that have never been reviewed have no FSRS memory state (`card.data` has no `s`/`d` fields). The WP-5 log (L6) established that such cards contribute `recall = 0.0` for skill cards.
- **Chose:** Apply the same rule for Meta cards: no memory state → `recall = 0.0`. This is honest: an unreviewed vocab/flaw card is definitionally not remembered. The cold-start expectation (spec-measurement §9) is that Memory will show a low score at first, which is correct.
- **Risk:** Users with a freshly-imported deck will see Memory ≈ 0 (13 Meta cards all unreviewed). This is the correct and honest signal.
- **Ref:** WP-5-log.md §L6; spec-measurement §9

### L4 — Notetype filter: "LSAT Meta" by name (mirrors WP-5's "LSAT Skill")
- **Type:** decision (local, confirming design)
- **Status:** resolved locally
- **Context:** The storage query must distinguish Meta cards from Skill and Item cards, all of which may coexist in the same deck hierarchy (the Meta deck is a sibling of Skills and Items under "LSAT Speedrun").
- **Chose:** Filter by `n.mid = (SELECT id FROM notetypes WHERE name = 'LSAT Meta')`, exactly mirroring the WP-5 "LSAT Skill" filter. The notetype name is a stable contract established in WP-1 (`NOTETYPE_META = "LSAT Meta"` in `build_seed_deck.py`).
- **Considered:** Tag-based filter (`n.tags LIKE '% category::vocab %'`) — rejected because Meta notes don't necessarily carry a unique tag distinct from skill-identity tags.
- **Risk:** None — same reasoning as WP-5-log.md §L3.
- **Ref:** WP-5-log.md §L3; `tools/speedrun/deck/build_seed_deck.py` NOTETYPE_META

### L5 — `elapsed_seconds_for_card` reuse: `pub(super)` in service.rs
- **Type:** decision (local)
- **Status:** resolved locally
- **Context:** `measurement.rs` needs the same elapsed-seconds helper that `service.rs` uses for skill cards. Duplicating the function would risk the two drifting apart.
- **Chose:** Change `elapsed_seconds_for_card` in `service.rs` from `fn` (private) to `pub(super)` (visible within the `stats` module). `measurement.rs` references it as `crate::stats::service::elapsed_seconds_for_card`. This is the minimum visibility change; it does not break any existing callers.
- **Risk:** None — `pub(super)` does not increase the public API surface.
- **Ref:** `rslib/src/stats/service.rs`, `rslib/src/stats/measurement.rs`

### L6 — `meta_cards_in_decks` refactored via shared `cards_in_decks_by_notetype`
- **Type:** decision (local)
- **Status:** resolved locally
- **Context:** Adding `meta_cards_in_decks` alongside `skill_cards_in_decks` in `speedrun.rs` would have duplicated the SQL construction logic. Both functions differ only in the notetype name literal.
- **Chose:** Extract a private `cards_in_decks_by_notetype(&self, deck_ids, notetype_name)` helper in `SqliteStorage`; `skill_cards_in_decks` and `meta_cards_in_decks` both delegate to it. The notetype name is our own constant (no injection risk); the SQL string is constructed with a simple `replace('\'', "''")` escape for safety.
- **Risk:** Refactoring `skill_cards_in_decks` to call the shared helper changes its implementation (but not its behaviour). WP-5's existing unit tests (`test_skill_mastery_aggregate`) cover the invariant.
- **Ref:** `rslib/src/storage/card/speedrun.rs`

---

## Bugs found

### L7 — Pre-existing: `elapsed_seconds_for_card` was private, limiting reuse
- **Type:** minor design gap (not a correctness bug)
- **Status:** resolved in WP-7 (`pub(super)`)
- **Context:** The helper was `fn` (crate-private) when WP-5 wrote it, because only `service.rs` needed it. WP-7 needs the same computation for Meta cards without forking.
- **Resolution:** Promoted to `pub(super)` (stats-module-visible) in WP-7. This is additive and backward-compatible.
- **Ref:** `rslib/src/stats/service.rs`

### L8 — None found in other files touched by WP-7
- **Type:** pre-existing bug report
- **Status:** none found
- **Context:** Examined `rslib/src/stats/service.rs`, `rslib/src/storage/card/speedrun.rs`, `rslib/src/storage/card/data.rs`. No pre-existing correctness bugs in the code paths WP-7 touches beyond L7.
