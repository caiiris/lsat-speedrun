# Speedrun WP-1 — Inbox Log

> **Provisional local IDs** (L1, L2, …) — the orchestrator merges these into
> `decisions.md` and `backlog.md` after review. Do NOT promote IDs or edit the
> canonical logs directly from this file.
>
> Work package: **WP-1 — Taxonomy + notetypes + seed-deck data contract**  
> Date: 2026-06-30  
> Agent: Sonnet 4.6 via Cursor

---

## Decisions / alternatives / spec ambiguities

### L1 — Principle taxonomy placement (spec ambiguity)
- **Type:** decision (local, pending promotion)
- **Status:** resolved locally; flag for orchestrator
- **Context:** PowerScore treats Principle as an "overlay" (not a standalone type) and Role as a subtype of Method. Magoosh frequency data and the brainlift J.1 text ("~13 types") both implicitly include Principle as a full type.
- **Chose:** Promote Principle to a standalone type 13, with `type::principle-identify` and `type::principle-apply` subtypes. Keep Role as `type::method-role` subtype. This gives exactly 13 primary types.
- **Considered:** Treating Principle as a modifier tag across other types (PowerScore purist view) — rejected because it complicates pool selection (a single-type constraint per LSAT Skill note becomes ambiguous).
- **Impact:** The 13-type taxonomy in `taxonomy.json` is the stable contract. If this conflicts with a later decision, the tag strings would need to change → other WPs affected.
- **Ref:** `docs/speedrun/data/taxonomy.json`, D-SR13, brainlift J.1

### L2 — anki package availability for tests (known gap)
- **Type:** issue / known gap
- **Status:** known-gap
- **Context:** `build_seed_deck.py` and `test_build_deck.py` both `import anki`. In this repo, the `anki` package is a compiled wheel (`pylib/rsbridge`) built via `just wheels` — it is NOT a standard pip package. In a vanilla Python environment (CI, fresh checkout), the import fails.
- **Resolution:** Tests in `test_build_deck.py` are decorated with `@anki_available` and skip gracefully when the package is not installed. The `test_taxonomy.py` and `test_weights.py` tests have no anki dependency and run in any environment.
- **To run full suite:** `just wheels && pytest tools/speedrun/deck/tests/ -v`
- **Ref:** `tools/speedrun/deck/tests/test_build_deck.py`, CLAUDE.md

### L3 — Taxonomy count: 13 or 14 question types? (spec ambiguity)
- **Type:** ambiguity
- **Status:** resolved locally as 13 (see L1)
- **Context:** Some sources list 14 types by counting both Assumption (Necessary) and Justify (Sufficient Assumption) as top-level types. Others subsume Justify under Strengthen or Assumption. The brainlift says "~13 recurring question types."
- **Chose:** Both `type::assumption` and `type::justify` are separate top-level types (the most important disambiguation for learners). Total = 13 with Principle as one type containing two subtypes. If a future decision promotes subtypes to full types, the count increases to 15+.
- **Ref:** taxonomy.json, brainlift J.1, D-SR13

### L4 — Tag normalization: `::` becomes `_` in Anki tags (implementation note)
- **Type:** issue / implementation detail
- **Status:** known-gap; surfaced for WP-3 (Rust engine)
- **Context:** Anki's tag system does not natively support `::` in tag names — colons are often normalized to `_` or stripped. `build_seed_deck.py` stores identity tags by replacing `::` with `_` (e.g., `type::flaw` → `type_flaw`) to be safe.
- **Risk:** The pool-search query in spec-engine §5.2 uses `tag:skill::S` syntax. WP-3 must verify whether the Rust search engine handles `::` in tags or requires the normalized form. If normalized, the tag-matching logic must be consistent.
- **Action for WP-3:** Test `col.find_notes("tag:type_flaw")` vs `tag:type::flaw` against a built collection.
- **Ref:** `tools/speedrun/deck/build_seed_deck.py:_build_coverage_report`, spec-engine §5.2

### L5 — Readiness formula: w_S appears twice in spec-measurement §4.3 (spec bug)
- **Type:** ambiguity / potential spec bug
- **Status:** open
- **Context:** spec-measurement §4.3 formula:
  ```
  expected_raw = sum_S [ w_S * Perf(S) * items_per_skill_on_form(S) ]
  ```
  If `items_per_skill_on_form(S) = w_S * N_lr`, then `w_S` appears twice:
  `expected_raw = N_lr * sum_S [ w_S^2 * Perf(S) ]`
  At uniform Perf=1: `expected_raw = N_lr * sum(w_S^2) < N_lr` (wrong — should equal N_lr).
- **Resolution used in weights.json:** Interpret `items_per_skill_on_form(S)` as the raw item count (`w_S * N_lr`), and drop the extra `w_S` from the outer formula, so:
  `expected_raw = sum_S [ Perf(S) * items_per_skill_on_form(S) ] = N_lr * sum_S [ w_S * Perf(S) ]`
  At Perf=1: `expected_raw = N_lr`. ✓
- **Action needed:** Confirm with spec owner which formula is correct. If the double-w_S is intentional (a frequency-squared weighting), `weights.json` should document the intent.
- **Ref:** `docs/speedrun/data/weights.json:readiness_formula_note`, spec-measurement §4.3

### L6 — v1 Readiness projection: LR-only vs. full-exam (scope gap)
- **Type:** ambiguity / design decision
- **Status:** open; three options documented
- **Context:** D-SR12 says v1 covers LR only. The raw→scaled table maps total raw score (LR + RC, ~76 items). v1 has no RC items, so a full-form raw score cannot be computed.
- **Options:** (A) Assume RC Perf = mean LR Perf and scale up; (B) label output "LR-only projected score" and report only the LR portion; (C) abstain on Readiness until RC added.
- **Chose for weights.json:** Option B (honest, least assumption). But `weights.json` documents all three.
- **Impact for WP-8 (dashboard):** The Readiness card must clearly label "LR-only estimate" and show a wider band.
- **Ref:** `docs/speedrun/data/weights.json:readiness_formula_note`, D-SR12, spec-measurement §4.3

### L7 — LSAT Skill note count: 38, not 35 (spec-engine §7 undercount)
- **Type:** implementation note
- **Status:** resolved
- **Context:** spec-engine §7 says "one per skill/trap." The taxonomy produces:
  - 13 axis-1 question types → 13 Skill notes
  - 6 axis-2 reasoning sub-skills → 6 Skill notes
  - 12 argument flaws + 7 distractor traps = 19 trap entries → 19 Skill notes
  - Total: **38** LSAT Skill notes
- **Note:** Not all traps are schedulable skills in the FSRS sense (distractor traps are better modeled as item-level signals). A future decision may split trap skills from argument-flaw skills. Logged for WP-3.
- **Ref:** `tools/speedrun/deck/build_seed_deck.py:_skill_notes_from_taxonomy`, taxonomy.json

---

## Bugs / tech debt / open issues

### L8 — Anki tag colon normalization: test needed (bug risk)
- **Type:** bug risk
- **Status:** open
- **Context:** See L4. `build_seed_deck.py` uses `.replace("::", "_")` for tag storage, but the search in `_build_coverage_report` uses the normalized form `tag:{tag.replace("::", "_")}`. If Anki's search accepts the original `::` form, the search may fail silently (returning 0 results) without error.
- **Ref:** `build_seed_deck.py:_build_coverage_report:line ~anki_tag`
- **Mitigation needed:** Add a round-trip test: add note with tag `type_flaw`, search `tag:type_flaw`, assert count > 0.

### L9 — `col.models.add` mutation after write (Anki API quirk)
- **Type:** tech debt / API note
- **Status:** known-gap; documented for future agents
- **Context:** `col.models.add(m)` mutates `m` in-place (assigns `m["id"]`), then `col.models.by_name(name)` is called to get the authoritative copy. This pattern is required because `add` uses the legacy API and `_mutate_after_write` only works if we re-fetch. The code in `build_seed_deck.py` follows this pattern but it is fragile if the legacy API changes.
- **Ref:** `pylib/anki/models.py:add:_mutate_after_write`, `build_seed_deck.py:_populate_collection`

### L10 — Media folder cleanup in tests (test hygiene)
- **Type:** tech debt
- **Status:** open
- **Context:** Anki creates a `.media` folder alongside every collection file. The test fixture in `test_build_deck.py` attempts to clean it up, but if Anki creates it under a different path or naming convention the cleanup may be incomplete.
- **Ref:** `test_build_deck.py:tmp_col_path`

### L11 — Minimum pool size is too low for real coverage (design note)
- **Type:** issue
- **Status:** known-gap
- **Context:** `MIN_POOL_SIZE_SEED = 3` is set to allow the synthetic placeholder items to demonstrate coverage. In production, `min_pool_size_production = 10` (from `weights.json`). The seed deck with 7 synthetic items covers only 3 of 13 LR question types at the production threshold.
- **Action:** Once real items are imported (D-SR11), recalculate coverage against the production threshold. Track per-skill pool sizes in the dashboard.
- **Ref:** `weights.json:coverage_thresholds`, spec-engine §9

### L12 — Distractor traps as LSAT Skill notes: scheduling semantics unclear
- **Type:** issue / ambiguity
- **Status:** open
- **Context:** Distractor traps (D01–D07: half-true, too-extreme, etc.) are added as LSAT Skill notes by `_skill_notes_from_taxonomy`. But distractor traps are answer-choice properties, not stimulus properties — scheduling "practice on the half-true trap" doesn't map cleanly to a skill/pool selection query (what item pool would a `trap::half-true` skill draw from?).
- **Two interpretations:** (A) Each LSAT Item note's TrapChoiceX fields implicitly create a pool for that trap; the pool query uses `tag:trap_half-true` on items where any TrapChoiceX matches. (B) Distractor traps are not schedulable skills; only argument flaws are.
- **Action for WP-3:** Resolve before implementing `draw_item_for_skill` for trap skills.
- **Ref:** `build_seed_deck.py:_skill_notes_from_taxonomy`, spec-engine §5.2

---

<sub>Maintained with the `iris-log` skill by Iris Cai.</sub>
