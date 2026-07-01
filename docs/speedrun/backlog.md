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

## Summary (2026-06-30)

| Status | IDs |
|---|---|
| open | B001, B002, B005, B006, B007, B012, B013, B014, B017, B019, B020, B022, B023, B024, B025, B026, B027, B028, B029, B030, B032, B033, B036 |
| known-gap | B003, B004, B011, B015, B016, B018 |
| fixed / done | B008, B009, B010, B021, B031, B034, B035, B037 |

---

### B001 — AnkiDroid build must rebuild the shared Rust backend for Android

- **Type:** issue · **Status:** open · **Severity:** high
- **Discovered:** 2026-06-30 by Opus during iris-plan (spec-sync-mobile)
- **Ref:** [`spec-sync-mobile.md`](./spec-sync-mobile.md) §9; D-SR7
- **Context:** the engine change ships to the phone *only* after the Speedrun `rslib`
  is built into the AnkiDroid backend library and the fork builds on a device. The
  assignment explicitly warns teams that leave the mobile build late don't finish.
- **Resolution (when closed):** a trivial shared-engine review loop running on a
  real device/emulator **before** layering the engine change.
- **Links:** D-SR7; blocks PRD AC 9.B.

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
- **Links:** relates B006; feeds the coverage gate (spec-measurement §5).

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
- **Resolution:** recompute coverage vs production threshold once real items are imported; show per-skill pool sizes on the dashboard.
- **Links:** B007, D-SR11.

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

### B036 — Session (WP-22) known limits: approximate targeted-drill filter + V3 prefetch state

- **Type:** issue · **Status:** open · **Severity:** low
- **Discovered:** 2026-07-01 by WP-22 build agent (inbox L3/L4)
- **Ref:** `qt/aqt/speedrun_session.py`
- **Context:** (1) the **targeted-drill skill filter** matches the exact `IdentityTag` and falls back to *all* skill cards if none match — sub-skill/variant items can be missed; (2) the session **pre-fetches a card-id queue**, so V3-scheduler states can mismatch for non-new cards (safe for the all-new seed deck; skips the FSRS update rather than crashing). Both are graceful-degradation v1 limits.
- **Resolution:** tighten the skill filter (use the pool query from WP-3 / `tag:skill::S`) and re-fetch scheduler state per item before answering, once past the seed-deck demo.
- **Links:** WP-22; D-SR35; relates WP-3 (selection), D-SR27.

### B037 — Speedrun Home RPC 403: webview kind lacked API access

- **Type:** bug · **Status:** fixed · **Severity:** high
- **Discovered:** 2026-07-01 by owner (Home showed `403 Forbidden` after clicking Speedrun Home) + Opus
- **Ref:** `qt/aqt/webview.py` (`AnkiWebViewKind`, `have_api_access` tuple, `AuthInterceptor`); `qt/aqt/speedrun_home.py`
- **Context:** Anki only injects the `Authorization: Bearer <apikey>` header (required by mediasrv `_have_api_access`) for webviews whose `kind` is in `have_api_access`. WP-20's Home dialog used `AnkiWebViewKind.MAIN`, which is **not** API-enabled, so the dashboard RPC POST was rejected with 403.
- **Resolution (2026-07-01):** added `AnkiWebViewKind.SPEEDRUN_HOME`, included it in the `have_api_access` set, and switched `speedrun_home.py` to that kind. **Lesson:** any Anki webview that calls backend RPCs must use an API-enabled kind.
- **Links:** B034/B035 (same chain — WP-20 Home never worked over the web until GUI-tested); WP-14/WP-20; feeds WP-24.

---

<sub>Maintained with the `iris-log` skill by Iris Cai.</sub>
