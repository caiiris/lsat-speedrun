# Speedrun WP-3 — Inbox Log

> **Provisional local IDs** (L1, L2, …) — the orchestrator merges these into
> `decisions.md` and `backlog.md` after review.  Do NOT promote IDs or edit
> the canonical logs directly from this file.
>
> Work package: **WP-3 — Fresh-item selection (`draw_item_for_skill`)**
> Date: 2026-06-30
> Agent: Sonnet 4.6 via Cursor (worktree `wp3-a3f9c2b1`)

---

## Decisions / alternatives / spec ambiguities resolved

### L1 — Skill identity tag resolution: which tag counts?

- **Type:** spec ambiguity / decision
- **Status:** resolved locally
- **Context:** The spec says "skill of(skill_card_id)" — the representation of
  skill identity is not fully pinned down in spec-engine §5.2. Three candidates:
  (a) note tag, (b) `Card.custom_data` JSON field, (c) notetype field value.
- **Chose:** Note tags, accepting the first tag whose prefix is `type::`,
  `skill::`, or `trap::`.  `build_seed_deck.py` confirms: skill notes are
  added with `note.tags = [nd["IdentityTag"]]` — the identity tag IS the
  sole note tag.  Custom_data is empty for skill cards in the seed deck.
- **Considered:** Reading the `IdentityTag` field from note fields — rejected
  because the spec specifies tags for pool lookup (`tag:skill::S`), and
  reading the field adds a field-order dependency.
- **Risk:** If skill notes are created with additional tags (e.g. by the user),
  the search picks the first `type::`/`skill::`/`trap::` tag.  This is
  fine for the seed deck but should be documented.
- **Ref:** `build_seed_deck.py:_populate_collection` line
  `note.tags = [nd["IdentityTag"]]`; spec-engine §5.2; D-SR24.

---

### L2 — Sidecar storage: file vs in-memory

- **Type:** design decision
- **Status:** resolved locally
- **Context:** D-SR4 / spec-engine §7 say sidecar is "profile folder file
  **or** in-memory".  File-backed sidecar survives process restarts but
  adds I/O complexity; in-memory is simpler, is sufficient for v1, and
  matches the "best-effort" qualifier.
- **Chose:** In-memory process-level static
  (`std::sync::LazyLock<Mutex<HashMap<String, HashMap<String, SkillServedLog>>>>`),
  keyed by `col_path → skill_tag → log`.  The sidecar resets on restart (the
  worst case is that one item may repeat on the first draw after restart).
- **Considered:** JSON file alongside the collection (e.g.
  `{col_path}.speedrun-served.json`) — more persistent, but adds file I/O on
  every draw and complicates test isolation.  Deferred to a later decision.
- **Risk (deferred):** Sidecar is lost on process restart; on the first draw
  after a restart the window is empty and any item (including the most recently
  served) may be re-drawn.  Acceptable per D-SR4 "best-effort".
- **Ref:** spec-engine §7; D-SR4; `selection.rs:SERVED_SIDECAR`.

---

### L3 — Difficulty-appropriate selection: deferred

- **Type:** deferred item / design decision
- **Status:** open (deferred to WP-11 / phase-2)
- **Context:** spec-engine §5.2 says "preferring difficulty-appropriate items
  (warm-started difficulty — D4 / spec-ai)".  The difficulty warm-start model
  (AI-driven from spec-ai, D-SR14) is not yet built.
- **Chose:** Uniform random selection among fresh candidates.  This is
  explicitly acknowledged as a placeholder in the code comment.
- **Risk:** Without difficulty weighting, learners may encounter items that are
  systematically too hard or too easy.  This will be addressed once the AI
  tagging pipeline (WP-11) produces difficulty scores.
- **Action for later WP:** Replace `rand::rng().random_range(0..candidates.len())`
  with a difficulty-weighted sampler once WP-11 emits difficulty data.
- **Ref:** spec-engine §5.2; D-SR14; `selection.rs:draw_item_for_skill_impl`.

---

### L4 — Sidecar fallback trigger: unreachable in normal operation

- **Type:** design note / implementation finding
- **Status:** documented (no action needed)
- **Context:** The spec says to test "falls back to least-recently-served when
  all are served within W".  With W = `min(pool_size − 1, MAX_SIDECAR_WINDOW)`,
  the fallback (`candidates.is_empty()`) cannot be triggered through the normal
  API because recent(W) returns at most W = pool_size−1 items, always leaving
  at least one fresh candidate.
- **Resolution:** The fallback is defensive code that activates only when the
  sidecar has stale/extra entries (e.g., pool shrink while sidecar retained
  old entries).  Unit tests cover the fallback via the `SkillServedLog`
  helpers directly (`served_log_least_recently_served_*` tests) and via the
  `sidecar_fallback_least_recently_served` helper test.  The `draw_item_for_skill_impl`
  integration tests verify the main path (fresh selection + avoidance window).
- **Ref:** `selection.rs:tests::sidecar_fallback_least_recently_served`.

---

### L5 — Double-quoted deck filter in search (B021 re-confirmation)

- **Type:** implementation note / bug prevention
- **Status:** resolved (confirmed D-SR24 + B021 apply here)
- **Context:** The pool search is `tag:{skill_tag} deck:"LSAT Speedrun::Items"`.
  B021 (discovered in WP-1) established that Anki search requires DOUBLE quotes
  for deck names containing `::`.  Single quotes silently return 0 results.
- **Chose:** Always use double-quoted deck name in `draw_item_for_skill_impl`.
  Added a code comment citing B021 so future readers understand why.
- **Ref:** `selection.rs:draw_item_for_skill_impl`; B021; D-SR24.

---

### L6 — Trap pools: item-level `trap::X` tag lookup (D-SR23)

- **Type:** spec clarification / implementation note
- **Status:** resolved (inherits D-SR23)
- **Context:** WP-1-log L12 asked: how does `draw_item_for_skill` work for
  distractor trap skills (e.g. `trap::half-true`)?  D-SR23 resolved this: the
  pool for `trap::X` = LSAT Item notes carrying `trap::X`.
- **Chose:** The selection algorithm is skill-tag-agnostic: it searches
  `tag:{skill_tag} deck:"LSAT Speedrun::Items"` regardless of whether the
  skill_tag is `type::`, `skill::`, or `trap::`.  No special casing required.
- **Risk:** Items must be tagged at the item level with every distractor trap
  they contain (WP-11 responsibility, D-SR23).  If WP-11 omits item-level
  `trap::*` tags, trap pools will be empty and `draw_item_for_skill` will
  return an error.
- **Ref:** D-SR23; `selection.rs:draw_item_for_skill_impl`; spec-engine §5.2.

---

### L7 — MAX_SIDECAR_WINDOW cap choice: 50

- **Type:** design decision
- **Status:** resolved locally
- **Context:** The spec says W = min(pool_size − 1, N) but doesn't specify N.
- **Chose:** N = 50 (constant `MAX_SIDECAR_WINDOW`).  With typical pools of
  5–30 items this bound is rarely binding; it caps memory use for very large
  pools (100+ items) at 50 × 8 bytes = 400 bytes per skill per collection.
- **Considered:** N = 20 (tighter), N = 100 (more avoidance).
- **Ref:** `selection.rs:MAX_SIDECAR_WINDOW`.

---

## Bugs found

### L8 — Pre-existing: `invalid_input!` macro terminates function, not closure

- **Type:** implementation note / pitfall
- **Status:** worked around
- **Context:** `invalid_input!("msg")` expands to a `return Err(...)` statement.
  Using it inside a `.ok_or_else(|| { invalid_input!(...) })` closure would
  try to return from the closure, not from the enclosing function — a compile
  error.
- **Resolution:** Used `.or_invalid("msg")?` (the `OrInvalid` trait method)
  instead of `.ok_or_else(|| invalid_input!(...))` throughout the implementation.
- **Ref:** `selection.rs:draw_item_for_skill_impl`; `rslib/src/error/invalid_input.rs`.

---

### L9 — Test isolation: in-memory collections share sidecar key `:memory:`

- **Type:** bug risk / test design
- **Status:** resolved in tests
- **Context:** `Collection::new()` creates an in-memory SQLite collection with
  `col_path = ":memory:"`.  Multiple tests using `Collection::new()` would
  share the sidecar key and could interfere.
- **Resolution:** Tests that exercise `draw_item_for_skill_impl` use
  `open_fs_test_collection()` (which creates a real unique-path tempdir
  collection) to ensure each test has a distinct `col_path` and thus an
  isolated sidecar partition.  Tests that test sidecar helpers directly
  use a synthetic string key (e.g. `"test_fallback_col"`) and clean up
  explicitly.
- **Ref:** `selection.rs:tests`; `rslib/src/tests.rs:open_fs_test_collection`.

---

## Merge-risk notes

### L10 — Collision zone with WP-4

- **Type:** risk / coordination note
- **Status:** informational
- **Context:** WP-4 also lives under `rslib/src/scheduler/queue/`.  WP-3's
  only change there is adding one line (`pub(crate) mod selection;`) to
  `rslib/src/scheduler/queue/mod.rs`.  WP-4 touches `builder/{gathering,mod}.rs`.
  The collision window is narrow but exists if WP-4 also modifies `queue/mod.rs`.
- **Recommendation:** When merging WP-3 and WP-4 branches, check for conflicts
  in `queue/mod.rs`.  If both add a `mod` declaration, merge both lines.

---

<sub>Maintained with the `iris-log` skill by Iris Cai.</sub>
