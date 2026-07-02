# Speedrun — Backlog (bugs · refactors · issues)

> One file for bugs, refactors, and non-decision open questions, distinguished by
> `type`. Status updates in place; closed items are marked done with a verdict,
> never deleted. Companions: [`AGENTS.md`](./AGENTS.md), [`decisions.md`](./decisions.md),
> the specs (`spec-*.md`).
>
> **IDs:** `B001…`, monotonic, never reused. **Status keys:** open · in-progress ·
> fixed · done · wontfix · known-gap · duplicate · false-positive. **Severity:**
> critical · high · medium · low.
>
> Note: undecided *design forks* live in the decision log as `Status: open` (e.g.
> the AI feature roster, D-SR14), **not** here. This file is for non-decision
> issues, debt, and known gaps.

## Summary (2026-07-01)

| Status | IDs |
|---|---|
| open | B002, B005, B006, B007, B012, B013, B014, B017, B019, B020, B022, B023, B024, B025, B026, B027, B028, B029, B030, B032, B033, B041, B042, B043, B044, B045, B046, B047, B048, B049, B050, B051, B052 |
| known-gap | B003, B004, B011, B015, B016, B018 |
| fixed / done | B001, B008, B009, B010, B021, B031, B034, B035, B037, B039, B040, B036, B038, B053 |

---

### B001 — AnkiDroid build must rebuild the shared Rust backend for Android

- **Type:** issue · **Status:** done · **Severity:** high
- **Discovered:** 2026-06-30 by Opus during iris-plan (spec-sync-mobile)
- **Ref:** [`spec-sync-mobile.md`](./spec-sync-mobile.md) §9; D-SR7
- **Context:** the engine change ships to the phone *only* after the Speedrun `rslib`
  is built into the AnkiDroid backend library and the fork builds on a device. The
  assignment explicitly warns teams that leave the mobile build late don't finish.
- **Resolution (2026-07-01, owner):** **WP-0b green on dev machine.** Stock AnkiDroid
  builds + reviews on a Pixel 10 emulator (`~/dev/droid/Anki-Android`). Then
  `Anki-Android-Backend` sibling checkout: `anki` submodule at `lsat-speedrun` @
  `d9220b6b` (26.05 / Rust 1.92), NDK `29.0.14206865`, `./build.sh` →
  `rsdroid-release.aar`, `local_backend=true` in `Anki-Android/local.properties` →
  AnkiDroid runs on emulator with the custom backend. **Pitfall:** a Python venv for
  `analogical-reasoning` exposed a script named `ar` on `PATH`, breaking
  `tree-sitter` builds — fix: `export AR=/usr/bin/ar` before `./build.sh`.
- **Links:** D-SR7; unblocks WP-8/10/15; PRD AC 9.B path open.

### B002 — Render-vs-answer decoupling is the one custom reviewer surface

- **Type:** issue · **Status:** open (verified feasible) · **Severity:** medium
- **Discovered:** 2026-06-30 by Opus during the consistency/feasibility pass
- **Ref:** [`spec-engine.md`](./spec-engine.md) §8; D-SR3
- **Context:** Level-2 renders a *drawn* item while scheduling/answering the *skill
  card*. Stock Anki couples "the card you see = the card you answer." Feasible via
  the existing `RenderUncommittedCard`/`RenderExistingCard` RPCs + answering the
  skill card with the standard `CardAnswer` — but it's the main place a careless
  change could break the answer flow. Must be honored in **both** the desktop
  (`qt/aqt/reviewer.py` + `ts/reviewer/`) and AnkiDroid reviewers.
- **Update (2026-07-01, WP-8):** AnkiDroid path shipped — `SpeedrunReviewSession` calls
  `drawItemForSkill`, renders drawn-item HTML, answers the skill card via `answerCard`.
  Desktop still uses Python field injection (D-SR30). **Device verify pending.**
- **Links:** D-SR3; relates B001.

### B003 — FSRS-as-skill scheduling: interval optimality unproven

- **Type:** issue · **Status:** known-gap · **Severity:** medium
- **Discovered:** 2026-06-30 by Opus during the consistency pass
- **Ref:** D-SR3 (gaps); [`spec-measurement.md`](./spec-measurement.md) §3
- **Context:** FSRS estimates *per-item* memory; Speedrun applies it to a *skill*
  (fresh item each review), reinterpreting stability/difficulty as skill-level.
  Scheduling stays **valid** (a normal review stream), and this is the brainlift's
  intended bet (D4) — but whether the resulting intervals are *optimal* for skill
  practice is unverified.
- **Resolution (when closed):** judge via the memory-calibration eval (Brier/log-loss
  on held-out reviews); if poorly calibrated, revisit the skill↔FSRS mapping.
- **Links:** D-SR3, D-SR9; spec-measurement §7.

### B004 — Per-device Performance can drift until both devices sync

- **Type:** issue · **Status:** known-gap · **Severity:** low
- **Discovered:** 2026-06-30 by Opus during the consistency pass
- **Ref:** D-SR4; [`spec-engine.md`](./spec-engine.md) §7
- **Context:** Performance is recomputed per-device from the synced skill revlog;
  specific-item attribution lives in a local sidecar, so two devices can differ
  briefly before a sync completes. Accepted for v1 (no corruption, no score loss).
- **Resolution (when closed):** phase-2 synced per-item-outcome table if exact
  cross-device Performance is required.
- **Links:** D-SR4.

### B005 — Item-redistribution licensing deferred to ops

- **Type:** issue · **Status:** open · **Severity:** medium
- **Discovered:** 2026-06-30 by Opus during iris-plan (owner-directed)
- **Ref:** D-SR11; [`prd-speedrun.md`](./prd-speedrun.md) §8
- **Context:** v1 bundles a **cited** seed deck of real LSAT items for grading; the
  owner deferred redistribution licensing as separate logistics, not a code concern.
  Must be resolved before any public distribution of the bundled deck.
- **Links:** D-SR11.

### B006 — Tag human-verification throughput is the coverage bottleneck

- **Type:** issue · **Status:** open · **Severity:** medium
- **Discovered:** 2026-06-30 by Opus during iris-plan (spec-ai)
- **Ref:** [`spec-ai.md`](./spec-ai.md) §9; D-SR13, D-SR14
- **Context:** axis-2 (reasoning sub-skill) and trap tags are AI-assisted but must be
  **human-verified** before they drive scores. Verification throughput gates how
  fast coverage rises (and thus when Readiness un-abstains).
- **Resolution (when closed):** prioritize the high-frequency skills first
  (Flaw/Assumption/Inference ≈ 40% of LR) to raise coverage fastest.
- **Links:** D-SR13, D-SR14; relates B007.

### B007 — Thin per-skill item pools cause repeats / uncovered skills

- **Type:** issue · **Status:** open · **Severity:** low
- **Discovered:** 2026-06-30 by Opus during iris-plan (spec-engine)
- **Ref:** [`spec-engine.md`](./spec-engine.md) §9
- **Context:** fresh-item selection needs a **minimum pool size** per skill; below it
  the engine either repeats items or marks the skill uncovered (feeding
  coverage/abstain). The bundled seed deck must meet the minimum for any demoed
  skill.
- **Update (2026-07-01, Opus, D-SR38):** by **question type** the pool now clears the
  production floor (all 13 `type::*` at ≥10, 151 items total). By **reasoning sub-skill**
  it's still uneven — `skill::prephrase`=0, `skill::quantifier`=6 (< the production 10),
  the rest ≥42. Type-axis repeats are no longer a demo risk; the skill-axis thinness is
  carved out as **B043**.
- **Links:** relates B006, B043, D-SR38; feeds the coverage gate (spec-measurement §5).

### B008 — Build env can't compile the engine: spaced repo path + no Rust toolchain

- **Type:** issue · **Status:** fixed · **Severity:** high
- **Discovered:** 2026-06-30 by Opus during the WP-0 environment probe
- **Ref:** repo at `/Users/kittysnowball/Desktop/Alpha AI/anki` ("Alpha AI" contains a space); `docs/development.md` ("folder path must not contain spaces"); `rust-toolchain.toml` pins 1.92.0.
- **Context:** WP-0 (build from source) cannot run here. Two blockers: (1) the repo path contains a **space**, which Anki's ninja build + `CARGO_TARGET_DIR=out/rust` plumbing can break on; (2) **rustc/cargo are not installed**, and there is no `out/` (never built). GUI run also needs a display (headless), and AnkiDroid needs Android SDK/NDK — both need the dev's machine.
- **Resolution (2026-06-30, Opus):** **Both desktop blockers cleared.** The repo now lives at the space-free `/Users/kittysnowball/dev/lsat-speedrun`; Rust 1.92.0 (rustc/cargo/rustup) is installed and matches `rust-toolchain.toml`; a full `out/` build exists with `out/buildhash == HEAD (f4fe85cc)`. Verified: `just build` (= `./ninja pylib qt`) succeeds, and `anki` v26.05 imports (`PYTHONPATH=out/pylib:pylib` for the generated `buildinfo`/`_rsbridge`/`_fluent` modules). **WP-0a (desktop) is green.** The GUI `just run` (needs a display) and **WP-0b (AnkiDroid)** (needs Android SDK/NDK + device) remain on the dev's machine → tracked under **B001**.
- **Links:** unblocks WP-0a + all engine WPs (`build-plan.md`); WP-0b/mobile build still open under B001.

### B009 — Tag `::` vs `_`: verify Anki hierarchical-tag search before WP-3

- **Type:** bug · **Status:** fixed · **Severity:** high
- **Discovered:** 2026-06-30 by WP-1 build agent (inbox L4/L8)
- **Ref:** `tools/speedrun/deck/build_seed_deck.py`; spec-engine §5.2
- **Context:** the seed builder stored skill-note identity tags as `::`→`_` (e.g. `type_flaw`) and the coverage search converted to `_` too — but item notes were tagged with native `::`, so coverage search silently returned 0.
- **Resolution (2026-06-30, Opus):** Verified `rslib/src/tags/mod.rs` uses `::` as the native hierarchy separator (`rsplit_once("::")`). Standardized on native `::` everywhere; reverted the `.replace("::","_")` at `build_seed_deck.py:459` and `:526` so skill tags and the coverage search match the item tags. Decision recorded as **D-SR24**. (A round-trip test on a built collection is still advisable — folded into WP-3 / B016.)
- **Links:** D-SR24, D-SR17; WP-3.

### B010 — Distractor-trap skills: scheduling / pool semantics unresolved

- **Type:** issue · **Status:** done (resolved → D-SR23) · **Severity:** medium
- **Discovered:** 2026-06-30 by WP-1 build agent (inbox L12)
- **Ref:** `build_seed_deck.py:_skill_notes_from_taxonomy`; spec-engine §5.2
- **Context:** distractor traps (half-true, too-extreme…) are *answer-choice* properties, not stimulus types, so "schedule the half-true trap" has no clear item pool. Options: (A) draw from items whose any distractor carries that trap; (B) distractor traps aren't schedulable skills.
- **Resolution (2026-06-30, owner):** Option **A** — distractor traps **are** schedulable skills; pool(`trap::X`) = items carrying `trap::X`. Recorded as **D-SR23**; WP-11 must emit item-level `trap::*` tags so the pools are populated.
- **Links:** D-SR23, D-SR17.

### B011 — Card-check factual checker misses semantic inversions

- **Type:** issue · **Status:** known-gap · **Severity:** medium
- **Discovered:** 2026-06-30 by WP-12 build agent (inbox L-B1)
- **Ref:** `tools/speedrun/cardcheck/checker.py:FactualChecker`
- **Context:** lexical token-coverage passes a card that uses the right vocabulary to assert the *opposite* claim (e.g. "correlation *proves* causation"). D1 forbids a model-judged verify; a symbolic negation detector is non-trivial.
- **Resolution:** revisit before phase-2 real-model AI eval; consider a deterministic negation/entailment check.
- **Links:** D-SR20.

### B012 — Real LLM client + canonical source not wired (AI features)

- **Type:** issue · **Status:** open · **Severity:** medium
- **Discovered:** 2026-06-30 by WP-12 build agent (inbox L-D2/L-A1/L-A2)
- **Ref:** `tools/speedrun/cardcheck/generator.py:LLMClient`; spec-ai §5
- **Context:** generation uses a deterministic stub behind an `LLMClient` seam; the "run vs gold set" recall interpretation and a canonical single-source URI both need a real model. Same seam applies to tagging (WP-11) and difficulty/readiness model wiring.
- **Resolution:** wire a real model behind the existing seams when AI features go live (Fri); use a canonical primary source.
- **Links:** D-SR20, D-SR14; WP-11.

### B013 — Paraphrase variant linking field undefined (`Card.custom_data.variant_of`)

- **Type:** issue · **Status:** open · **Severity:** medium
- **Discovered:** 2026-06-30 by WP-16 build agent (inbox L6) — cross-WP with WP-1
- **Ref:** `tools/speedrun/eval/README.md`; spec-engine §7; D-SR4
- **Context:** the paraphrase eval needs base↔variant item links; WP-16 proposes `Card.custom_data.variant_of = base_item_id` (zero schema change per D-SR4), but WP-1's notetypes didn't define it.
- **Resolution:** add `variant_of` to the LSAT Item data model (custom_data/tag) in the engine/data WP; confirm with spec owner.
- **Links:** D-SR4; spec-engine §7.

### B014 — Eval wiring gaps: ease→outcome mapping + no held-out split utility

- **Type:** issue · **Status:** open · **Severity:** medium
- **Discovered:** 2026-06-30 by WP-16 build agent (inbox L4/L5)
- **Ref:** `tools/speedrun/eval/README.md`; spec-measurement §7
- **Context:** (1) `revlog.ease`→0/1 outcome mapping is spec-silent (README assumes ease≥2→1, ease=1→0 — confirm); (2) harnesses take pre-split data but there's no `split.py` to create/pin a leak-free time-based held-out split.
- **Update (2026-06-30, WP-14):** part (1) **resolved** → the ease→outcome mapping is now canonical (`ease≥2`=correct, `ease==1`=wrong, `ease=0` excluded) as **D-SR31**, matching the README's assumption. Part (2) (`split.py`) is still open.
- **Resolution:** ~~confirm the ease mapping~~ (done, D-SR31); add a `split.py` utility before running real evals.
- **Links:** spec-measurement §7; D-SR10, D-SR22, **D-SR31**.

### B015 — Seed-deck coverage below production threshold (synthetic-only)

- **Type:** issue · **Status:** known-gap · **Severity:** low
- **Discovered:** 2026-06-30 by WP-1 build agent (inbox L11)
- **Ref:** `docs/speedrun/data/weights.json`; spec-engine §9
- **Context:** seed uses `MIN_POOL_SIZE_SEED=3` with 7 synthetic items → only 3/13 types covered at the production threshold (10). Real items (D-SR11) needed for real coverage.
- **Update (2026-06-30, Opus):** `sample_items.json` expanded to **39 synthetic items (3 per all 13 `type::*`)** so seed coverage is now **13/13 at `MIN_POOL_SIZE_SEED=3`** — this makes Level-2 `draw_item_for_skill` work for every question type in the demo. Still **synthetic** and still below the production threshold of 10, so this does not close the gap; real items (D-SR11) remain required.
- **Update (2026-07-01, Opus, D-SR38):** pool migrated to per-type files under `tools/speedrun/deck/items/` and **expanded to 151 synthetic items — all 13 `type::*` now at ≥10**, so `build_seed_deck --min-pool 10` reports **13/13 (100%)** at the *production* threshold. **Gap still open:** these are synthetic placeholders, so this clears the *structural/count* threshold but not the *real-content* requirement — real items (D-SR11) are still needed before this is truly closed. Per-skill dashboard pool sizes still to do.
- **Update (2026-07-01, Opus, D-SR39):** the **upload-your-own** side of D-SR11 now has a concrete tool — `import_prep_book.py` imports locally-owned prep-book items (`SyntheticFlag=REAL`, cited) into a **gitignored** `deck/imported/`, merged via `build_seed_deck --import`. This lets a user study real items locally, but does **not** close B015 for the *bundled* deck (imports are personal-use, never committed/shared). Bundled default stays synthetic.
- **Resolution:** recompute coverage vs production threshold once **licensed, redistributable** real items are bundled; show per-skill pool sizes on the dashboard.
- **Links:** B007, B043, D-SR11, D-SR38, **D-SR39**.

### B016 — Tooling / test-hygiene debt (anki import, models.add, media cleanup, plot test)

- **Type:** refactor · **Status:** known-gap · **Severity:** low
- **Discovered:** 2026-06-30 by WP-1 + WP-16 build agents (inbox WP-1 L2/L9/L10, WP-16 L7)
- **Ref:** `tools/speedrun/deck/tests/`, `tools/speedrun/eval/calibration.py`
- **Context:** minors bundled — (a) `anki` not pip-importable so 15 deck tests skip until `just wheels`; (b) `col.models.add` in-place mutation quirk (must re-fetch by name); (c) test media-folder cleanup may be incomplete; (d) matplotlib plot path is guarded but untested.
- **Update (2026-06-30, Opus):** with the engine now built (B008), `anki` imports via `PYTHONPATH=out/pylib:pylib:tools ANKI_TEST_MODE=1`. Running the full speedrun suite that way surfaced + fixed a **latent fixture bug** in `test_build_deck.py`: `open_col` didn't depend on `coverage_report`, so an `open_col`-only test could open an empty collection first and lock the file, breaking the later `build_seed_deck` call (the deck tests had only ever *skipped*, so this never showed). Fixed by making `open_col` depend on `coverage_report`. **Whole speedrun suite now green: 198 passed, 1 skipped** (the 1 skip = the guarded matplotlib plot, item (d)). Still open: wire these tests into the build's pytest folder with `out/pylib` on `pythonpath` (the `check:pytest:tools` rule runs `tools/tests` only and sets `pythonpath = tools`), plus items (c)/(d).
- **Resolution:** address opportunistically; ensure CI builds the wheel + adds `out/pylib` to the tools-test pythonpath before deck tests.
- **Links:** B008 (env).

### B017 — Implement no-silent-fallback in StemClassifier (D-SR26)

- **Type:** issue · **Status:** open · **Severity:** medium
- **Discovered:** 2026-06-30 by WP-11 build agent (inbox L-A4); decided D-SR26
- **Ref:** `tools/speedrun/tagging/tagger.py:StemClassifier._DEFAULT_TYPE`
- **Context:** unmatched stems currently return `type::flaw` silently; D-SR26 rules they must route to human-verify (`type::unknown` / untyped), excluded from coverage/scheduling.
- **Resolution:** change the default; add `type::unknown` handling; test unmatched stem → unknown (not flaw).
- **Links:** D-SR26.

### B018 — Tagging stub can't detect semantic skills/traps (needs real LLM)

- **Type:** issue · **Status:** known-gap · **Severity:** medium
- **Discovered:** 2026-06-30 by WP-11 build agent (inbox L-A1/L-A2/L-A3/L-B1)
- **Ref:** `tools/speedrun/tagging/tagger.py:DeterministicStubClient`; `gold_labels.json`
- **Context:** the deterministic stub scores ~0 F1 on semantically-determined labels (`skill::abstraction` on flaw items, `trap::half-true`, `trap::irrelevant-comparison`, `trap::reversal`); gold set is n=10 synthetic. Honest limitation — real macro-F1 needs the real LLM + ≥50 human-labeled items.
- **Resolution:** when B012 wires a real model, extend the gold set to ≥50 and re-run the eval.
- **Links:** B012, D-SR14, D-SR23.

### B019 — VectorKNNBaseline has no `fit()` guard

- **Type:** issue · **Status:** open · **Severity:** low
- **Discovered:** 2026-06-30 by WP-11 build agent (inbox L-B2)
- **Ref:** `tools/speedrun/tagging/baselines.py:VectorKNNBaseline.propose_tags`
- **Context:** `propose_tags()` before `fit()` raises at call time but isn't guarded at construction; add an unfitted flag / lazy init.
- **Links:** —.

### B020 — `apply_tags._find_note` is an O(n) linear scan

- **Type:** refactor · **Status:** open · **Severity:** low
- **Discovered:** 2026-06-30 by WP-11 build agent (inbox L-B3)
- **Ref:** `tools/speedrun/tagging/apply_tags.py:_find_note`
- **Context:** linear scan over all LSAT Item notes — fine at seed scale, slow for 7,500+ real items. Use `col.find_notes` by `_id` or an index before production import.
- **Links:** D-SR11.

### B021 — Coverage query used single-quoted deck filter → always 0 coverage

- **Type:** bug · **Status:** fixed · **Severity:** high
- **Discovered:** 2026-06-30 by Opus, first real run of `build_seed_deck.py` against the built `anki` lib (v26.05)
- **Ref:** `tools/speedrun/deck/build_seed_deck.py:529` (`_build_coverage_report`)
- **Context:** the coverage search built the deck filter with `{DECK_ITEMS!r}` (Python repr → **single** quotes: `deck:'LSAT Speedrun::Items'`). Anki search requires **double** quotes; single quotes are mis-parsed, so the query returned **0 for every skill** → coverage always 0/13 → the give-up gate would *always* abstain. (Items were correctly created, suspended, and tagged with native `::`; only the query was wrong.)
- **Resolution:** changed to `deck:"{DECK_ITEMS}"`. Verified on a temp collection: coverage now reports flaw=3, inference=2, assumption=2 (matches the 7 synthetic items).
- **Links:** relates B009/D-SR24 (tag form); exposes B016 (anki-dependent tests were skipped, so this slipped through — add a non-skipped integration test).

### B022 — Speedrun deck preset new/day = 100 is a dev placeholder (pacing TBD)

- **Type:** issue · **Status:** open · **Severity:** low
- **Discovered:** 2026-06-30 by Opus (seed-deck preset addition)
- **Ref:** `tools/speedrun/deck/build_seed_deck.py` (`NEW_CARDS_PER_DAY`, `REVIEWS_PER_DAY`, the "LSAT Speedrun" preset)
- **Context:** the builder now ships a dedicated preset at 100 new/day + 1000 rev/day to lift Anki's default 20/day cap so all 38 skills / 13 meta are available. The numbers are an arbitrary dev default — real new-card pacing for the skill-as-card model is a pedagogy/deck-config decision, not a fixed constant.
- **Resolution:** revisit pacing when the engine (skill scheduling) lands; likely drive from deck options / FSRS rather than a hardcoded preset value.
- **Links:** spec-engine; relates D-SR3.

### B023 — Speedrun docs/data files are not dprint-formatted (blocks `just check`/`just fmt`)

- **Type:** refactor · **Status:** open · **Severity:** low
- **Discovered:** 2026-06-30 by Opus, first `just fmt` run after WP-2
- **Ref:** `dprint check` lists 22 files under `docs/speedrun/**` (all `.md` + `data/*.json`), `docs/lsat-speedrun-brainlift.md`, and `tools/speedrun/{cardcheck/gold_set.json, deck/sample_items.json, eval/README.md, tagging/gold_labels.json}`.
- **Context:** the entire Wave-1 docs/data tree was committed (f4fe85cc) without running dprint, so `just check`/`just fmt` fail on formatting before reaching tests — independent of any engine change. `.dprint.json` covers md/json/toml/ts/scss (not `.rs`/`.proto`); the WP-2 Rust + proto edits are verified clean (`cargo fmt --check`, `clang-format --dry-run -Werror` both pass).
- **Resolution:** run `just fix-fmt` (`dprint fmt`) once over the speedrun tree and commit the (whitespace-only) reformat; ideally add a pre-commit/CI guard so new docs land formatted. Deferred here to avoid bundling 22 files of churn (incl. data-contract JSON) into the WP-2 change.
- **Links:** relates B016 (test/format hygiene).

### B024 — Difficulty-appropriate item selection deferred (WP-3 draws uniformly at random)

- **Type:** issue · **Status:** open · **Severity:** medium
- **Discovered:** 2026-06-30 by WP-3 build agent (inbox L3)
- **Ref:** `rslib/src/scheduler/queue/selection.rs:draw_item_for_skill_impl`; spec-engine §5.2; D-SR14
- **Context:** spec-engine §5.2 wants fresh-item selection to prefer **difficulty-appropriate** (warm-started) items, but the AI difficulty model (spec-ai / D-SR14) isn't built. WP-3 ships **uniform-random** selection among fresh candidates as an explicit, code-commented placeholder.
- **Resolution:** replace the random pick with a difficulty-weighted sampler once WP-11 emits per-item difficulty signals.
- **Links:** D-SR14; WP-11; spec-engine §5.2.

### B025 — Served-item sidecar is in-memory only (not persisted across restart)

- **Type:** issue · **Status:** open (accepted for v1) · **Severity:** low
- **Discovered:** 2026-06-30 by WP-3 build agent (inbox L2/L8)
- **Ref:** `rslib/src/scheduler/queue/selection.rs` (`SERVED_SIDECAR`, a `LazyLock<Mutex<HashMap<col_path → skill → log>>>`); spec-engine §7; D-SR4
- **Context:** the repeat-avoidance sidecar is process-level and keyed by collection path — local, non-synced, non-undoable (per D-SR4). It **resets on process restart**, so on the first draw after a restart the avoidance window is empty and any item (incl. the most-recently-served) may re-draw. Acceptable per D-SR4 "best-effort."
- **Resolution:** if repeats-after-restart matter, persist to a JSON sidecar file beside the collection (the interface is already isolated behind the served-log type).
- **Links:** D-SR4; spec-engine §7.

### B026 — Full `just check` not green: pre-existing lint/format debt in Wave-1 tooling

- **Type:** refactor · **Status:** open · **Severity:** low
- **Discovered:** 2026-06-30 by WP-3/WP-4/WP-5 build agents (all three reported the same pre-existing failures)
- **Ref:** `tools/speedrun/deck/build_seed_deck.py:507` + `tools/speedrun/deck/tests/test_build_deck.py:86` (mypy); `tools/speedrun/` (ruff, WP-12); `docs/speedrun/*.md` (dprint → B023)
- **Context:** on the merged engine tree `just build`, `just test-rust`, and `just test-py` are **all green**, but the full `just check` still fails on pre-existing formatting/lint of Wave-1 files: dprint on docs (B023), ruff on `tools/speedrun`, and mypy on `build_seed_deck.py` / `test_build_deck.py`. **None are introduced by the engine WPs** — verified by all three lanes.
- **Resolution:** `just fix-fmt` / `just fix-lint`, fix the mypy annotations on the Wave-1 tooling, and wire `out/pylib` into the tools-test pythonpath (relates B016) so a clean `just check` gates future work.
- **Links:** B023 (dprint), B016 (test hygiene).

### B027 — Reviewer: no keyboard shortcut to commit an answer (mouse-only choice select)

- **Type:** issue · **Status:** open · **Severity:** low
- **Discovered:** 2026-06-30 by WP-6 build agent (inbox B-WP6-001)
- **Ref:** `qt/aqt/reviewer.py` (`onEnterKey`), `qt/aqt/speedrun.py`
- **Context:** in the Speedrun commit-then-reveal surface, choices A–E are selected by click (`pycmd('speedrun:commit:X')`); there's no 1–5 / A–E keyboard shortcut to commit. Enter/Space are (correctly) blocked before commit and submit Continue after.
- **Resolution:** add key handlers (1–5) that map to commit before reveal.
- **Links:** WP-6; spec-engine §6.

### B028 — Reviewer: empty item pool falls back silently (no user-visible signal)

- **Type:** issue · **Status:** open · **Severity:** low
- **Discovered:** 2026-06-30 by WP-6 build agent (inbox B-WP6-002)
- **Ref:** `qt/aqt/reviewer.py` (`_speedrun_draw_item_fields`)
- **Context:** for a Level-2 skill card, if `draw_item_for_skill` errors or the pool is empty, the reviewer silently falls back to normal rendering. Safe, but the user gets no signal that the skill is uncovered.
- **Resolution:** surface an "uncovered skill / empty pool" message (ties into the coverage/abstain UX).
- **Links:** WP-6; B007/B015 (thin pools); spec-engine §9.

### B029 — Level-2 render uses Python field injection, not the `RenderUncommittedCard` RPC

- **Type:** issue · **Status:** open (v1 accepted → D-SR30) · **Severity:** medium
- **Discovered:** 2026-06-30 by WP-6 build agent (inbox B-WP6-003 / L5)
- **Ref:** `qt/aqt/speedrun.py`, `qt/aqt/reviewer.py`; spec-engine §8; D-SR30
- **Context:** WP-6 injects drawn-item HTML from Python (`web.eval`) instead of the §8 render RPCs. Works on desktop, but AnkiDroid can't reuse a Python-only path → cross-platform parity risk for WP-8/WP-15.
- **Resolution:** for mobile, either wire the `RenderUncommittedCard` RPC path (shared engine) or reimplement injection in the AnkiDroid reviewer; decide during WP-8.
- **Links:** D-SR30; B002; WP-8/WP-15.

### B030 — Reviewer: auto-advance disabled for Speedrun cards (Continue-only)

- **Type:** issue · **Status:** open · **Severity:** low
- **Discovered:** 2026-06-30 by WP-6 build agent (inbox B-WP6-004)
- **Ref:** `qt/aqt/reviewer.py` (`_showEaseButtons` → single Continue)
- **Context:** Speedrun review replaces the 4-ease panel with a single Continue button (ease derived from correctness, spec §5.1); any user auto-advance / typed-answer preferences are effectively disabled on these cards.
- **Resolution:** confirm this is the desired UX; if not, honor the auto-advance settings.
- **Links:** WP-6; spec-engine §5.1/§6.

### B031 — Memory score not yet callable from Python (Rust-only until WP-14)

- **Type:** issue · **Status:** fixed (WP-14) · **Severity:** low
- **Discovered:** 2026-06-30 by WP-7 build agent (inbox L1)
- **Ref:** `rslib/src/stats/measurement.rs` (`memory_score_impl`); D-SR29
- **Context:** `memory_score_impl` is implemented + tested in Rust but has no proto RPC / pylib wrapper, so the dashboard/Python can't call it yet. Deferred to WP-14 (adds the `MetaMemory` RPC there to avoid duplicate rebuilds / merge churn).
- **Resolution:** ~~add the `MetaMemory` (or equivalent) RPC + pylib wrapper in WP-14.~~ **Resolved by WP-14** — the `SpeedrunDashboard` RPC's `memory` field exposes mean + bootstrap CI + card count (D-SR32).
- **Links:** D-SR29; WP-14; spec-measurement §4.1.

### B032 — Speedrun dashboard UI is minimal (deck-picker / i18n / polish deferred)

- **Type:** refactor · **Status:** open · **Severity:** low
- **Discovered:** 2026-06-30 by WP-14 build agent (inbox L7)
- **Ref:** `ts/routes/speedrun-dashboard/` (`SpeedrunDashboard.svelte`, `[...deckId]/+page.*`)
- **Context:** the dashboard route is functional and honesty-faithful (three cards, Wilson-CI bars, abstain panel with no Readiness number, always-visible "LR-only estimate" badge), but the UI is minimal: no interactive **deck picker** (deck_id comes from the route param), **English literals** (no `ftl` i18n), no dark-mode polish/animations, and no calibration/paraphrase chart integration.
- **Resolution:** add a deck picker + i18n strings + visual polish; wire the proof-eval charts (WP-16) when they produce output.
- **Links:** WP-14; spec-measurement §8; WP-16.

### B033 — Reasoning map + stimulus flaw not surfaced (needs a marked-conclusion item field)

- **Type:** issue · **Status:** open · **Severity:** medium
- **Discovered:** 2026-07-01 by WP-21 build agent (inbox L3) + orchestrator merge review
- **Ref:** `qt/aqt/speedrun.py` (`build_reveal_html` rail placeholder), `tools/speedrun/deck/build_seed_deck.py` (LSAT Item notetype), spec-ui §3.2; D-SR34
- **Context:** the drill's **Reasoning map** rail (Premise / Conclusion / The gap, spec-ui §3.2) is a **placeholder** — the `LSAT Item` notetype has no marked-conclusion field, so it can't be populated deterministically (and inventing premise/conclusion parsing would need AI/NLP). Relatedly, the redesigned reveal (WP-21) **no longer surfaces the stimulus-level flaw** (`TrapTag`) that the old reviewer showed; it belongs in this rail. Per-choice trap categories (`TrapChoiceX`) *are* shown.
- **Resolution:** add an additive **`Conclusion`/`MarkedConclusion` field** to the LSAT Item notetype + `build_seed_deck.py` (data, not schema — rides notetype fields), populate it, then render the reasoning map + stimulus flaw. Confirm with spec owner.
- **Links:** D-SR34; spec-ui §3.2; relates D-SR13 (taxonomy)/B013 (item data model).

Note (2026-07-01): WP-21's redesign renamed/reworked the reviewer HTML; the WP-6 `qt/tests/test_speedrun.py` asserted the old markup, so **8 tests were stale after merge** — updated by the orchestrator to the new intended behavior (verdict "You chose X", humanized "Trap category", accordion why-wrong, generic "Next question"). Suite green again (35/35). Not a bug — flagged so the history is clear.

### B034 — Speedrun Home renders blank: deck_id passed as number, not bigint

- **Type:** bug · **Status:** fixed · **Severity:** high
- **Discovered:** 2026-07-01 by owner (opened Tools→Speedrun Home → blank) + Opus root-cause
- **Ref:** `ts/routes/speedrun-dashboard/[...deckId]/+page.ts` (+ `index.ts`); the `SpeedrunDashboard` RPC (`deck_id` int64)
- **Context:** the page loader did `parseInt(params.deckId)` → a JS **number**, but `deck_id` is `int64` so the generated client expects a **`bigint`**; passing a number throws at request-build time, so the `load()` fails and the page renders **blank**. Never hit before because WP-14/WP-20 were verified by build+unit tests, not the GUI. (This is the "bigint/number mismatch" svelte-check had flagged.)
- **Resolution (2026-07-01):** convert to `BigInt(...)` in `+page.ts` and `index.ts`; `just build` green. WP-24's Home redesign inherits the fixed loader.
- **Links:** WP-14/WP-20; D-SR32; feeds WP-24 (Home redesign).

### B035 — `speedrunDashboard` RPC 404s from the web (not in mediasrv `exposed_backend_list`)

- **Type:** bug · **Status:** fixed · **Severity:** high
- **Discovered:** 2026-07-01 by owner (Home showed `404: Invalid path: _anki/speedrunDashboard`) + Opus
- **Ref:** `qt/aqt/mediasrv.py` (`exposed_backend_list` / `post_handlers`)
- **Context:** the web frontend calls backend RPCs by POSTing `/_anki/<method>`; mediasrv only routes methods listed in `exposed_backend_list` (→ `<method>_raw` on `RustBackend`). WP-14 added the `SpeedrunDashboard` RPC + pylib wrapper but **never added `speedrun_dashboard` to `exposed_backend_list`**, so the Home's fetch 404'd. (Only surfaced now because WP-14 was verified via pylib/Rust, not an actual web call.)
- **Resolution (2026-07-01):** added `"speedrun_dashboard"` under StatsService in `exposed_backend_list`; verified `mediasrv` imports and `speedrunDashboard` is registered. **Lesson:** any new frontend-facing backend RPC must be added here.
- **Links:** B034 (same chain — dashboard RPC never exercised over the web); WP-14/WP-20; feeds WP-24.

### B036 — Session (WP-22): targeted drill serves only 1 question + reviews not committed to revlog

- **Type:** bug · **Status:** fixed (pending owner live-GUI verify) · **Severity:** high
- **Discovered:** 2026-07-01 by WP-22 build agent (inbox L3/L4); **owner-confirmed symptoms 2026-07-01**
- **Ref:** `qt/aqt/speedrun_session.py` (`_assemble_card_ids`, `_fetch_v3_states`, `_answer_current_card`)
- **Context (original):** (1) the **targeted-drill skill filter** matches the exact `IdentityTag` and falls back to *all* skill cards if none match; (2) the session **pre-fetches a card-id queue**, so V3-scheduler states can mismatch for non-new cards (skips the FSRS update rather than crashing).
- **Owner-observed (2026-07-01):** *"the Flaw family drill only lets you do one question, then returns to Home; and my progress isn't saved."* Root causes confirmed in code:
  1. **One-question drill.** There is exactly **one `LSAT Skill` card per skill** (data contract: 38 skill notes). `_assemble_card_ids` for `targeted` returns *distinct skill cards* matching `IdentityTag:"type::flaw"` → **1 card** → `[:10]` → a single-question session. A targeted drill must instead **re-serve the same skill card N times**, calling `draw_item_for_skill` for a fresh item each rep (the app schedules the *skill*, not the item — D-SR3/B003).
  2. **Reviews not saved.** `_answer_current_card` only calls `answer_card()` when `state.v3_states is not None`, and `_fetch_v3_states` only sets it when the skill card is the **top of `get_queued_cards()`**. When it isn't (card not due / not queue-top), the answer path is skipped → **nothing written to the revlog** → no FSRS update, card stays put, same item re-appears (compounded by the in-memory-only served sidecar, B025).
- **Clarification for the owner's "progress not saved":** by design the app tracks progress at the **skill** level (the skill card's revlog history → Performance), **not per individual item** (D-SR4 / B003) — it never "remembers" a specific question as done. But right now even the skill-level review is being dropped (cause 2), so nothing accumulates.
- **Resolution:** (a) targeted mode: loop the focus skill card up to `SESSION_SIZES["targeted"]`, drawing a fresh item + re-fetching scheduler state each rep; (b) commit reliably — re-fetch V3 states for the actual card immediately before `answer_card()` (don't depend on pre-fetched queue-top); (c) verify on live GUI (headless can't). Ties into ability-tracking (Performance/Readiness) actually receiving data.
- **Fix (2026-07-01, Opus — `qt/aqt/speedrun_session.py`):**
  1. `_assemble_card_ids` targeted branch now returns `[matched[i % len(matched)] for i in range(limit)]` — the single focus skill card repeated to the session size (10), so a targeted drill serves 10 questions (a fresh item drawn each rep). Mixed/timed unchanged (distinct cards by due).
  2. `_fetch_v3_states` now uses `col._backend.get_scheduling_states(card_id)` (the legacy-answerCard path) instead of matching `get_queued_cards()` top — states are valid for any card, so every answer reaches `answer_card()` → a revlog row is written and Performance accrues. This also fixes commit reliability for mixed/timed.
  3. `_load_current_item` calls `card.start_timer()` so `answer_card()`'s `time_taken()` is valid.
  Added tests (`TestAssembleCardIdsTargetedRepeat`); 26 qt session tests + lint green. **Not yet GUI-verified** (headless can't drive the reviewer) — needs a `just run` drill pass.
- **Known residual (separate from B036):** blind review re-serves the missed *skill card* and draws a **fresh** item, so it does not reproduce the exact missed item (per-item identity isn't stored — D-SR4/B003). Tracked as a follow-up, not part of this fix.
- **Links:** WP-22; D-SR35; D-SR3/D-SR4/B003 (skill-level, not per-item); B025 (served sidecar); B044 (weak-skill/mistakes modes, unblocked by this); WP-3 (selection), D-SR27.

### B037 — Speedrun Home RPC 403: webview kind lacked API access

- **Type:** bug · **Status:** fixed · **Severity:** high
- **Discovered:** 2026-07-01 by owner (Home showed `403 Forbidden` after clicking Speedrun Home) + Opus
- **Ref:** `qt/aqt/webview.py` (`AnkiWebViewKind`, `have_api_access` tuple, `AuthInterceptor`); `qt/aqt/speedrun_home.py`
- **Context:** Anki only injects the `Authorization: Bearer <apikey>` header (required by mediasrv `_have_api_access`) for webviews whose `kind` is in `have_api_access`. WP-20's Home dialog used `AnkiWebViewKind.MAIN`, which is **not** API-enabled, so the dashboard RPC POST was rejected with 403.
- **Resolution (2026-07-01):** added `AnkiWebViewKind.SPEEDRUN_HOME`, included it in the `have_api_access` set, and switched `speedrun_home.py` to that kind. **Lesson:** any Anki webview that calls backend RPCs must use an API-enabled kind.
- **Links:** B034/B035 (same chain — WP-20 Home never worked over the web until GUI-tested); WP-14/WP-20; feeds WP-24.

### B038 — Home Memory card shows "No meta cards yet" despite 13 LSAT Meta cards

- **Type:** bug · **Status:** FIXED (2026-07-02, root cause = B053) · **Severity:** low → was actually the whole Home dashboard reading the wrong deck
- **Discovered:** 2026-07-01 by owner (Home rendered; Memory card says "No meta cards yet")
- **Ref:** `qt/aqt/speedrun_home.py:_find_speedrun_deck_id`; `SpeedrunDashboard` RPC; `ts/routes/speedrun-dashboard/`
- **Context:** the profile's `LSAT Speedrun::Meta` deck has 13 Meta cards, but the Home's Memory card rendered the empty state. **Root cause found (B053):** the guess in this entry ("the `deck_id` passed to the dashboard doesn't include the Meta subdeck") was correct — `_find_speedrun_deck_id` threw on a bad API call and **always returned `1` (Default deck)**, so the Home always queried Default (no meta cards, no skill revlog). Not a memory-query bug at all; the engine was fine.
- **Resolution:** fixed by B053 (drop the invalid `decks.get_current()` call so the "LSAT Speedrun" loop actually runs). After the fix the Home resolves the root deck → Memory shows the real value. Verified independently: the running backend returns meta=13 for the root deck vs meta=0 for deck 1.
- **Links:** **B053 (root cause + fix)**; D-SR29 (Memory), D-SR32 (dashboard RPC); WP-14/WP-20.

### B039 — Speedrun shell: expose Anki functions (Sync/Browse) inside the Home (nicety)

- **Type:** issue · **Status:** fixed (WP-25) · **Severity:** low
- **Discovered:** 2026-07-01 by WP-24 build agent (inbox)
- **Ref:** `qt/aqt/main.py` (`SPEEDRUN_SHELL`, `_deckBrowserState`), `qt/aqt/speedrun_home.py`
- **Context:** WP-24 first *hid* Anki's toolbar, which risked losing access to Browse/Add/Stats/Sync. **Fixed (2026-07-01):** the toolbar is no longer hidden — the maximized Speedrun Home merely *covers* the main window, so **closing the Home reveals full, functional Anki** (nothing lost). Remaining nicety: so the user rarely needs to leave Speedrun, surface **Sync + Browse** as buttons inside the Home shell itself.
- **Resolution:** add Home buttons / a minimal Speedrun bar for Sync + Browse (→ `mw.onSync` / `mw.onBrowse`); optional.
- **Links:** D-SR36; WP-24; spec-ui §2.

### B040 — Shell shows TWO windows (Home dialog + Anki main); closing Anki main quits both

- **Type:** bug · **Status:** fixed (WP-26) · **Severity:** high
- **Discovered:** 2026-07-01 by owner
- **Ref:** `qt/aqt/speedrun_home.py` (`SpeedrunHomeDialog` — a top-level QDialog), `qt/aqt/main.py` (`_speedrun_auto_open_home`)
- **Context:** WP-24 opens the Home as a **separate maximized dialog on top of** the `AnkiQt` main window (still in the deck-browser state), so **two windows** appear; the main window is the real app, so closing it quits everything while closing the Home only closes the dialog. Not a true single-window shell.
- **Resolution (WP-26):** render the Speedrun Home **as the main window's content** (`mw.web`) as the launch state (whitelist `/_anki/speedrunDashboard` for the main webview; move the Home pycmd bridge to `mw`), so there's exactly one window and closing it quits normally. Fallback: hide `mw` + route Home-close→quit.
- **Links:** D-SR36/D-SR37; WP-24/WP-26.

### B041 — Home dashboard doesn't auto-refresh after a session closes

- **Type:** issue · **Status:** open · **Severity:** low
- **Discovered:** 2026-07-01 by WP-26 build agent (inbox L5)
- **Ref:** `qt/aqt/main.py` (`_speedrunHomeState`, `_speedrun_open_session`), `ts/routes/speedrun-dashboard/`
- **Context:** with the single-window shell, the Home lives in `mw.web`; when a `SpeedrunSessionDialog` closes, the Home page isn't reloaded, so the scores/skill-map can be stale until the user presses `Ctrl+Shift+H` (which re-loads the state).
- **Resolution:** on session-dialog close, signal the Home to reload (re-`moveToState("speedrunHome")` or a JS refresh hook).
- **Links:** WP-26; D-SR37; WP-22.

### B042 — Reskinned Stats: some D3 chart series colors + calendar heatmap still default (not Speedrun palette)

- **Type:** issue · **Status:** open (partially addressed) · **Severity:** low
- **Discovered:** 2026-07-01 by WP-27 build agent (deferred)
- **Ref:** `ts/routes/graphs/graphs-base.scss` (`body.speedrun-stats`), the graph TS (`card-counts.ts`, `reviews.ts`, `intervals.ts`, `CalendarGraph`, `EaseGraph`, etc.)
- **Context:** WP-27 reskins the Stats page chrome (background, cards, headings, controls, accent) to Speedrun, but the **chart series colors** (D3 `interpolate*`/`scheme*`, hardcoded in TS) were initially left at Anki defaults.
- **Update 2026-07-01 (user feedback "these two clearly have a different style"):** recolored the two always/most-visible charts to the drill palette (spec-ui §2), gated on `body.speedrun-stats` so stock Anki is untouched:
  - **Card Counts** pie + legend → `speedrunBarColours` (indigo/amber/clay/green/muted) in `card-counts.ts`.
  - **Reviews** bars/series → indigo·green·amber·clay ramps in `reviews.ts` (`binColor`).
  - `--state-new/learn/review` tokens overridden (TodayStats numbers), card titles switched from Georgia serif → the drill's mono uppercase eyebrow treatment.
- **Remaining:** calendar heatmap + the less-visible graphs (intervals, ease, difficulty, retrievability, stability, hourly, buttons, added, future-due) still use Anki's default d3 colors. Mostly empty on the demo deck; retheme the same way when polishing.
- **Links:** WP-27; spec-ui §2.

### B043 — Reasoning-sub-skill (`skill::`) pools uneven: `skill::prephrase`=0, `skill::quantifier`=6

- **Type:** issue · **Status:** open · **Severity:** low
- **Discovered:** 2026-07-01 by Opus during the D-SR38 content build-out
- **Ref:** `tools/speedrun/deck/items/type-*.json` (`SkillTag`); [`taxonomy.json`](./data/taxonomy.json) SK04/SK05; [`weights.json`](./data/weights.json) `coverage_thresholds.min_pool_size_production=10`
- **Context:** the 151-item pool clears the production floor on the **type** axis but not on every **skill** axis. Tally: `skill::conclusion-id`=70, `skill::causal`=70, `skill::abstraction`=47, `skill::conditional`=42, `skill::quantifier`=6, `skill::prephrase`=0. Two are below 10. `skill::prephrase` (SK04) is really a *study behavior* (predict-before-choices, D-SR34), not a property of a stimulus, so tagging items with it is debatable — decide whether it should ever be an item-level schedulable skill or only a drill-mode signal. `skill::quantifier` (SK05, all/most/some/none) is a genuine reasoning skill and just under-authored.
- **Update (2026-07-01, Opus, D-SR39):** `skill::quantifier` **resolved** — authored 4 fresh synthetic all/most/some/none inference items (SYNTH-INFERENCE-014–017), pool now 155 items and `skill::quantifier` = **10** (at floor). `skill::prephrase`=0 still open, pending the ruling on whether it is item-taggable at all.
- **Resolution:** (a) **still open** — rule on whether `skill::prephrase` is item-taggable or drill-only; (b) ~~author `skill::quantifier` items~~ **done** (D-SR39); (c) surface per-skill pool sizes on the dashboard (shared with B015).
- **Links:** B007, B015, D-SR38, **D-SR39**, D-SR13, D-SR34.

### B044 — Session-mode choice: "drill my weak skills" vs "review what I got wrong"

- **Type:** issue (feature) · **Status:** open · **Severity:** low
- **Discovered:** 2026-07-01 by owner ("shouldn't it drill what I'm bad at? or let me pick: practice what I got wrong vs what I'm bad at")
- **Ref:** `qt/aqt/speedrun_home.py`, `qt/aqt/speedrun_session.py`, `rslib/src/stats/performance.rs` (`best_next_skill`), `ts/routes/speedrun-dashboard/SpeedrunDashboard.svelte` (`focusSkill`/`startTargetedDrill`)
- **Context:** the owner expected adaptive "drill your weakest skill" and a choice between that and "review your mistakes."
  - **"What I'm bad at"** already exists in design: "Today's focus" = `best_next_skill` = argmax `w_S·(1−Perf(S))·marginal` (D-SR9). It currently cold-starts on **Flaw** because with no revlog data every skill scores `w_S·1·1`, so the highest-frequency type wins. It cannot adapt until reviews are actually recorded → **blocked by B036** (answers not committed).
  - **"What I got wrong"** exists only as **session-local blind review** (re-run this session's misses). No persistent cross-session mistakes bank. Per **D-SR4/B003** there is no per-item outcome store; FSRS already resurfaces skills you rate Again(1) sooner, but not specific questions.
- **Resolution (proposal):** (a) surface an explicit mode toggle on Home — "Weakest skills" (adaptive, existing recommender) vs "Review misses"; (b) for "review misses" v1, drive it off the FSRS lapse/again queue at the skill level (no new schema, honors D-SR4) rather than a per-item store; (c) revisit a persistent per-item mistakes bank only if per-question review is truly wanted (would need a local, non-synced store — phase-2). Prereq: **B036** so Performance data exists to make "weakest" meaningful.
- **Links:** B036 (prereq — reviews not saved), D-SR9 (next-best-thing), D-SR4/B003 (skill-level, not per-item), D-SR35 (session modes).

### B045 — Add an easier "single-concept" drill tier beneath full practice items

- **Type:** issue (feature) · **Status:** open · **Severity:** low
- **Discovered:** 2026-07-01 by owner ("we should have easier single-concept-based drill questions in addition to these actual practice problems")
- **Ref:** `docs/speedrun/data/notetypes.md` (`LSAT Meta` vs `LSAT Item`), spec-ui §3.2, `docs/speedrun/data/taxonomy.json` (axis-2 sub-skills)
- **Context:** the current drill serves **full LR items** (stimulus + 5 choices). The owner wants a lighter tier that isolates **one concept/sub-skill** — e.g. "sufficient vs necessary," "spot the conclusion," "all/most/some inference," "name this flaw" — as quick atomic exercises for building fundamentals before full problems. This sits *between* the declarative `LSAT Meta` flashcards (pure vocab/definitions) and full `LSAT Item` practice: a micro-item that tests *applying* one sub-skill in isolation.
- **Design questions:** (a) new notetype (`LSAT Concept`/`LSAT Micro`) vs reuse `LSAT Item` with a `Tier` field and shorter stems; (b) how it scores — feed the same skill's Performance, or a separate "fundamentals" track so it doesn't inflate exam-Performance; (c) authoring format + validator support; (d) surface: a "Fundamentals" session mode on Home, or scaffolding that fades as a skill's Performance rises (ties D-SR34 worked-example fading).
- **Resolution (proposal):** spec a `micro`/`concept` tier (likely a `Tier: concept|full` field on `LSAT Item` to avoid a new notetype + zero schema change), author a small set per sub-skill, and add a "Fundamentals" drill mode; keep concept-tier outcomes on a separate display track initially so exam-Readiness stays full-item-based. Needs an owner decision before build.
- **Links:** D-SR34 (scaffolding/fading), D-SR13 (taxonomy sub-skills), notetypes contract (D-SR38), B043 (skill-axis coverage).

### B046 — Purpose-built Speedrun stats view (replace reskinned Anki graphs)

- **Type:** issue (refactor/feature) · **Status:** open · **Severity:** medium
- **Discovered:** 2026-07-01 by owner + Opus — after four consecutive jargon spot-fixes on the reskinned Anki Statistics page (DI-SR1 steps 3–6: deck/collection → "this deck" → deck-picker button → removed deck controls entirely).
- **Ref:** `ts/routes/graphs/` (reskinned Anki stats, WP-27/DI-SR1), `qt/aqt/stats.py`; the data source `SpeedrunDashboard` RPC (`rslib/src/stats/{performance.rs, measurement.rs}`, WP-14); `ts/routes/speedrun-dashboard/`.
- **Context:** the "Statistics" surface is still fundamentally **Anki's** (decks, cards, reviews, ease, intervals, PDF export) reskinned to the Speedrun palette. Every term the owner hits reads as not-their-app (deck/collection, ease buttons, card counts), so it's been whack-a-mole to de-jargon piece by piece. The metrics a Speedrun learner actually cares about — **Memory / Performance / Readiness / per-skill map / timed-vs-untimed / calibration** — already exist via the `SpeedrunDashboard` RPC (WP-14) and are shown on Home, but there is no dedicated *deep* stats view built on them; "Stats" still routes to Anki's graphs.
- **Resolution (proposal):** build a **Speedrun-native stats page** (new `ts/route`, driven by `SpeedrunDashboard` + a small history RPC) presenting: Performance trend per skill over time, Readiness trajectory toward the abstain gate, accuracy by question-type/trap, timed-vs-untimed and confidence-vs-correctness gaps, and coverage. Route the Home "Stats" action there instead of Anki's graphs (keep Anki's graphs reachable only as an "advanced/raw" link, or drop from the shell). Retire the reskin spot-fixes (DI-SR1) and **B042** once this lands. Needs a spec pass (which metrics/time-series, and what history the RPC must expose) before build.
- **Links:** supersedes the ongoing DI-SR1 reskin approach; closes/absorbs **B042** (chart recolors) when done; builds on WP-14 (D-SR32 dashboard RPC), spec-measurement; relates B038 (Memory query), B036 (reviews must actually record for any of this to populate).

### B047 — Built backend (`out/`) lags `HEAD`; proof artifacts must rebuild first

- **Type:** issue · **Status:** open · **Severity:** medium
- **Discovered:** 2026-07-01 by Opus while adding the Python end-to-end engine test (D-SR40)
- **Ref:** `out/buildhash` (`f4fe85cc`) vs `git rev-parse HEAD` (`d9220b6b2`); `qt/tools/build_installer.py`; the Wednesday proof lane (WP-16/19)
- **Context:** the checked-in build tree in `out/` was produced at commit `f4fe85cc`, but `main`/`HEAD` is `d9220b6b2` (later UX-reframe + Stats + content merges). Anything run against `out/pylib` / the built app — including the new `pylib/tests/test_speedrun_engine.py` and any **clean-build / install / demo recording** — is exercising a *stale* engine + Qt layer. The engine RPCs (WP-3/5) predate `f4fe85cc`, so the new test still passes, but a proof recording made now would not match the current source (and the installer bundles wheels built from `out/`).
- **Resolution:** run a fresh `just build` (and `just wheels` before building the installer) so `out/buildhash == HEAD`, then capture the clean-build/test/install/phone recordings against that build. Ideally add a proof-lane step that asserts `out/buildhash == HEAD` before recording.
- **Links:** D-SR40 (test runs against `out/`); B008 (build env); WP-9 installer; WP-16/WP-19 proof lane.

### B048 — WP-9 demo-deck tooling is manual (no `just` recipe) + couples to the seed-builder function

- **Type:** refactor · **Status:** open · **Severity:** low
- **Discovered:** 2026-07-02 by Opus while adding `export_deck.py` (D-SR42)
- **Ref:** `tools/speedrun/deck/export_deck.py`, `tools/speedrun/installer/{README.md, make_demo_deck.sh}`; `justfile`; `tools/speedrun/deck/build_seed_deck.py:build_seed_deck`
- **Context:** the demo-deck export is only discoverable via the runbook + wrapper script — it was deliberately **not** wired into `justfile` to avoid editing a file other agents were mid-change on. It also imports `build_seed_deck.build_seed_deck()` directly, so a signature change there breaks the exporter (guarded by `test_export_deck.py`, but still coupling). The installer build itself is likewise driven by the upstream `./tools/build-installer` rather than a Speedrun `just` recipe.
- **Resolution:** once the `justfile` churn settles, add `just speedrun-demo-deck` (+ maybe `just speedrun-installer`) recipes; consider a thin stable entry point in the deck package so the exporter isn't bound to the builder's internal signature.
- **Links:** D-SR42; relates B023/B026 (tooling wiring), WP-9.

### B049 — Installer ships "Anki" branding (bundle id / name / icon), not "Speedrun"

- **Type:** issue · **Status:** open · **Severity:** low
- **Discovered:** 2026-07-02 by Opus during the WP-9 installer runbook (D-SR42)
- **Ref:** `qt/installer/app/pyproject.toml` (`formal_name = "Anki"`, `bundle = "net.ankiweb"`, `icon`, `description`)
- **Context:** the Briefcase installer produces an app called **Anki** (bundle `net.ankiweb`, Anki icon), even though it launches into Speedrun Home. As an AGPL fork that's acceptable to hand in, but if Speedrun should present as its own product the installer metadata + icon need changing. Editing `pyproject.toml` (and adding a Speedrun icon) is cosmetic but changes the bundle id (a distinct app on disk) — decide before any real distribution.
- **Resolution:** decide whether to rebrand for v1; if yes, set `formal_name`/`bundle`/`description` + add `resources/speedrun.{icns,ico,png}` and confirm the mac/windows templates pick them up. Keep as "Anki" for the Wednesday proof unless owner wants otherwise.
- **Links:** D-SR42; WP-9; spec-ui §2 (Speedrun brand palette).

### B050 — AnkiDroid: Speedrun scores scoped to Default deck + new-study-screen drill likely still blank

- **Type:** issue · **Status:** done (2026-07-02, Opus) · **Severity:** medium
- **Verdict:** both loose ends closed on the arm64 emulator. (1) `SpeedrunScoresActivity` now resolves the `LSAT Speedrun` deck (`decks.idForName("LSAT Speedrun")` → `startsWith` fallback → current), mirroring desktop `_find_speedrun_deck_id`; scores panel header reads "LSAT Speedrun" with 13 meta cards / 8 attempts instead of the empty Default. (2) Re-verified the drill under the **new study screen** (`newReviewerOptions` on): prephrase → reveal choices → commit → "Correct! You chose D" + per-choice rationale + Again/Hard/Good/Easy all render. **No guard needed** — `ReviewerViewModel` injects the drill via `eval` into the persistent WebView's `#qa`, which is already loaded, so it never hits the null-WebView path the legacy `Reviewer` did (that's why only the legacy path needed `recreateWebView()`). See DI-SR6.
- **Discovered:** 2026-07-02 by Opus during on-emulator WP-8/WP-15 verification (DI-SR6)
- **Ref:** `~/dev/droid/Anki-Android/AnkiDroid/.../speedrun/SpeedrunScoresActivity.kt`; `.../ui/windows/reviewer/ReviewerViewModel.kt`; `.../AbstractFlashcardViewer.kt` (`displaySpeedrunHtml`, fixed for legacy `Reviewer`)
- **Context:** two loose ends found while verifying the drill on the arm64 emulator (the legacy-reviewer blank-card bug itself is **fixed** — DI-SR6):
  1. **Scores deck scope.** `SpeedrunScoresActivity` calls `speedrunDashboard` for what resolves to the **Default** deck, so it reports "No LSAT Meta cards in this deck yet" / 0% even though the synced `LSAT Speedrun` deck has data. Desktop defaults to the Speedrun deck; mobile should target `LSAT Speedrun` (or the deck the user is studying), not Default.
  2. **New study screen.** The blank-render fix (ensure the WebView is attached before loading custom HTML) was applied to the legacy `Reviewer` path only. The new-study-screen `ReviewerViewModel` drill path was **not** re-verified on device and likely needs the equivalent guard.
- **Resolution:** point the scores activity at the `LSAT Speedrun` deck id (mirror desktop's default-deck resolution); re-verify the drill under the new study screen and add the same WebView-attach guarantee if it renders blank.
- **Links:** DI-SR6 (legacy fix); WP-8/WP-15; D-SR41 (sync unblock that enabled the verify).

### B051 — AnkiDroid legacy `Reviewer`: prephrase typing still hijacked by key-shortcuts

- **Type:** issue / limitation · **Status:** open (won't-fix-soon) · **Severity:** low
- **Discovered:** 2026-07-02 by Opus while fixing prephrase typing on the new study screen (DI-SR8).
- **Context:** DI-SR8 fixed prephrase typing on the **new study screen** by exposing `ReviewerViewModel.isInputFocused` (set via the `focusin`/`focusout` posts from `ankidroid-reviewer.js`) and honoring it in `ReviewerFragment.dispatchKeyEvent`. The **legacy** `Reviewer`/`AbstractFlashcardViewer` has **no equivalent WebView-input focus signal** — `answerFieldIsFocused()` only checks the native type-answer `EditText`, and its WebView isn't set `isFocusableInTouchMode` for arbitrary inputs — so a keystroke in the Speedrun prephrase field on the legacy reviewer still fires a reviewer shortcut instead of typing.
- **Resolution (deferred):** legacy reviewer is being superseded by the new study screen; steer mobile Speedrun users to `newReviewerOptions` (where type + scroll + full drill flow are verified) rather than porting the focus-signal plumbing into the deprecated path. Revisit only if the legacy reviewer must stay a supported Speedrun surface.
- **Links:** DI-SR8; WP-8.

### B052 — Local `User 1` profile now holds fabricated reviews; simulator is untested + couples to the dashboard field contract

- **Type:** issue / tech-debt · **Status:** open · **Severity:** low
- **Discovered:** 2026-07-02 by Opus (dashboard-demo simulator, D-SR43)
- **Ref:** `tools/speedrun/deck/simulate_reviews.py`; `~/Library/Application Support/Anki2/User 1/collection.anki2` (+ `collection.anki2.bak-20260702-014813`); `out/speedrun-demo-reviewed.colpkg`
- **Context:** to make the 3-score dashboard show real numbers on screen (D-SR43), the local `User 1` profile was populated in place with **fabricated** reviews (~250 `revlog` rows + FSRS `memory_state` on the 13 meta cards). Consequences: (1) it is **not real performance** — any proof recording made from this profile must be labelled a UI/measurement *demo*, not a genuine study session (relates B015); (2) a clean **cold-start / abstain** demo now requires restoring `collection.anki2.bak-<ts>` (or rebuilding the seed / making a fresh profile); (3) the simulator has **no test** and depends on both `build_seed_deck`'s signature (temp mode) and the dashboard's read contract (`revlog(cid,ease)` for `LSAT Skill`, `memory_state` for `LSAT Meta`) — a field/notetype rename would silently break it; (4) writes bypass undo and set `revlog.usn=0`, so they'd sync as-is if this profile is ever synced.
- **Resolution:** to restore cold-start: `cp "collection.anki2.bak-20260702-014813" collection.anki2` in the profile dir (app closed). If the simulator becomes a kept tool, add a round-trip test (mirror `test_export_deck.py`) and a thin stable read-contract shared with the dashboard; otherwise treat as throwaway demo tooling. Also fixes the demo symptom of B038 (meta cards now have memory state → Memory card shows a value).
- **Update (2026-07-02, Opus) — sync-conflict side effect (mitigated):** the direct `revlog`/card writes bump the collection's sync state, so on next launch the desktop app raised a **full-sync conflict dialog** ("choose which version to keep") against the self-hosted server (`customSyncUrl=http://127.0.0.1:8080/`, whose collection is empty), and the dashboard behind it rendered the cold-start empty state. **Data was never lost** — `lsof` confirmed the running app had the populated `User 1/collection.anki2` open, and a copy read meta=13 / attempts=259 / eligible=True with the app's own deck-picker (`_find_speedrun_deck_id` → root `LSAT Speedrun`). **Mitigation:** made a `collection.anki2.populated-bak-<ts>` backup and set the profile's `autoSync=False` (+`syncMedia=False`) in `prefs21.db` (pickled profile dict) so startup skips sync and opens straight to the populated Home. **Do not click "Download from AnkiWeb"** on that dialog — it would overwrite the local populated collection with the empty server copy; "Upload to AnkiWeb" (or Cancel) is safe. For a synced demo, resolve once via Upload.
- **Update (2026-07-02, Opus) — DB corruption from a stale WAL sidecar (fixed):** after the first in-place run the app failed to open the profile with `DbError … DatabaseCorrupt … "database disk image is malformed"`. **Root cause:** a **stale `collection.anki2-shm` from a prior session (dated Jun 30)** was left in the profile dir; when the desktop app opened the collection it mis-recovered against that stale shared-memory file and corrupted the main db. (Raw `sqlite3` confirmed the post-crash `collection.anki2` was malformed; the `.bak` was intact — its `no such collation sequence: unicase` error is just raw sqlite lacking Anki's custom collation, **not** corruption.) **Fix / procedure that works:** (1) `rm -f collection.anki2 collection.anki2-shm collection.anki2-wal`; (2) restore the `.bak`; (3) re-run the simulator; (4) **`rm -f` any `-wal`/`-shm`** so the app opens a clean single file. Verified `pragma integrity_check = ok` + dashboard populated + no sidecars. **Lesson for the tool:** any in-place writer must ensure no stale/foreign `-wal`/`-shm` remain around the target db before the app opens; prefer operating on a copy or clearing sidecars post-close. pylib's own open/close leaves no sidecars, so the hazard is specifically *pre-existing* ones.
- **Links:** D-SR43; relates B015 (synthetic content), B038 (Home Memory "no meta cards"), B048 (tooling not wired into `just`).

### B053 — Home dashboard always queried the Default deck (`_find_speedrun_deck_id` threw → returned 1)

- **Type:** bug · **Status:** FIXED (2026-07-02, Opus) · **Severity:** high (silently defeated the whole Home dashboard)
- **Discovered:** 2026-07-02 by Opus while debugging why the populated dashboard rendered empty (D-SR43 demo)
- **Ref:** `qt/aqt/speedrun_home.py:_find_speedrun_deck_id` (used by `main.py:_speedrunHomeState` → `speedrun-dashboard/<deck_id>`); cf. the correct copy in `qt/aqt/speedrun_session.py:_find_speedrun_deck_id`
- **Context:** the Home version called `mw.col.decks.get_current()` **first**, but `DeckManager` has no `get_current()` (only `current()` / `get_current_id()`). The `AttributeError` was swallowed by the function's `except Exception: pass`, so it **always fell through to `return 1`** — the Home always loaded `speedrun-dashboard/1` (Default deck), which has no LSAT Skill revlog and no Meta cards → Memory "no meta cards", Performance 0%, Readiness abstain (0/200). It stayed invisible until now because the real `LSAT Speedrun` deck also had no review data (cold start looked identical to Default); populating it (D-SR43) exposed the bug. Proven live: DevTools showed the webview at `/speedrun-dashboard/1`, and a direct backend query returned meta=13/attempts=259 for the root deck vs meta=0/attempts=0 for deck 1. The `speedrun_session.py` twin was unaffected (it runs the name-match loop **before** the bad call).
- **Resolution:** removed the pre-loop `get_current()` call; the function now runs the `startswith("LSAT Speedrun")` loop first and falls back to `get_current_id()`. Fix is source-only Python (`run.py` loads source `qt/` ahead of `out/qt`), so it applies on next app launch — **no rebuild needed**, just restart. This also fixes **B038**.
- **Links:** fixes B038; surfaced by D-SR43; relates WP-20 (Home), WP-14 (dashboard RPC).

---

<sub>Maintained with the `iris-log` skill by Iris Cai.</sub>
