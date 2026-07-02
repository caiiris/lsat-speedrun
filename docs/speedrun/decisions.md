# Speedrun — Decision Log

> The running record of every meaningful design choice for **Speedrun** (an
> LSAT study app forked from Anki), in the fixed shape **Chose → Considered →
> Gaps/risks**. IDs are stable and never renumbered. This is the source of
> *current* truth: where a later decision conflicts with the frozen PRD/spec, the
> entry here wins.
>
> Companions: [`AGENTS.md`](./AGENTS.md) (front door + authority order) ·
> [`prd-speedrun.md`](./prd-speedrun.md) · the specs
> ([`spec-engine.md`](./spec-engine.md), [`spec-measurement.md`](./spec-measurement.md),
> [`spec-sync-mobile.md`](./spec-sync-mobile.md), [`spec-ai.md`](./spec-ai.md)) ·
> [`backlog.md`](./backlog.md) · the brainlift
> [`../lsat-speedrun-brainlift.md`](../lsat-speedrun-brainlift.md) ·
> the engine map [`../../extra/architecture/ANKI_ARCHITECTURE.md`](../../extra/architecture/ANKI_ARCHITECTURE.md).

## Section index

| Cluster | IDs | Topic |
|---|---|---|
| Product | D-SR1, D-SR2, D-SR12, D-SR13 | Exam, the three scores, scope, taxonomy |
| Engine | D-SR3, D-SR4, D-SR5, D-SR6 | Rust change, reuse strategy, mastery query, study feature |
| Platform | D-SR7, D-SR8 | Mobile, sync |
| Measurement | D-SR9, D-SR10 | Readiness mapping, give-up rule |
| Content | D-SR11 | Item source & licensing |
| AI | D-SR14, D-SR15 | AI contract + roster, AI-card-check |
| Ops | D-SR16 | Doc home |
| Build · wave 1 | D-SR17–D-SR26 | taxonomy, readiness, card-check, leakage, trap scheduling, tag form, tagging eval |
| Build · wave 2 (engine) | D-SR27, D-SR28 | skill-identity resolution, mastery threshold |
| Build · wave 3 (measure/reviewer) | D-SR29, D-SR30 | Memory band + exposure, drawn-item render mechanism |
| Build · wave 4 (dashboard) | D-SR31, D-SR32 | revlog ease→outcome mapping, Readiness band/confidence/coverage method |
| Product · UX reframe | D-SR33, D-SR34, D-SR35, D-SR36, D-SR37 | presentation reframe, LR drill interaction, session/review flow, full-window shell, Home-as-hub |
| Build · wave 5 (content/test) | D-SR38, D-SR39, D-SR40 | per-type item pool + validator, prep-book import/pattern-abstraction, Python end-to-end engine test |
| Build · wave 6 (tooling/packaging) | D-SR41, D-SR42, D-SR43 | dev debugger port vs sync server, WP-9 demo-deck export/installer runbook, dashboard-demo review simulator |

---

### D-SR1 — Exam: LSAT (post-2024 format)

- **Status:** resolved
- **Chose:** Build the whole app for the **LSAT**, current format: two scored Logical Reasoning sections + one Reading Comprehension section, no Logic Games (removed Aug 2024), scored **120–180**.
- **Considered:** MCAT (huge fact base — flatters a flashcard score model but the coverage problem is enormous); GMAT Focus (adaptive scoring is its own modeling project); USMLE Step 1 (pass/fail only since 2022 — no scale to project). Rejected because the LSAT is the *honest hard case*: it has almost no memorizable facts, so a naive flashcard→score model visibly fails, which forces the project to actually build the memory→performance→readiness bridge instead of hiding behind recall.
- **Gaps / risks:**
  - A low-fact exam makes "Memory" the *smallest* of the three scores — the project's value rests almost entirely on the harder Performance and Readiness bridges.
  - No public per-student "study history → real practice-test score" dataset exists for a one-week build, so Readiness validation stays at the calibrated-steps level (see D-SR9).

### D-SR2 — Three scores, reframed for a low-fact exam

- **Status:** resolved
- **Chose:** Keep the assignment's three *separate* scores but define them for the LSAT: **Memory** = automaticity of the declarative meta-layer only (logic/argument vocabulary, named-flaw catalog, indicator/quantifier words), via FSRS recall probability. **Performance** = P(correct) on a *fresh, unseen* LR/RC item of a given question-type × reasoning-sub-skill × trap, estimated from history on *other* items of that skill. **Readiness** = projected 120–180 with a range + a coverage-gated confidence + the single best next thing to study.
- **Considered:** The assignment's MCAT-flavored framing (Memory ≈ fact recall) — rejected for the LSAT because the test is self-contained (Insight 5): no content vocabulary earns points, so a fact-recall "Memory" score would be measuring the wrong thing and would inflate apparent readiness.
- **Gaps / risks:**
  - Performance must be proven *distinct* from Memory or it's just copying FSRS — addressed by the paraphrase test (PRD AC bucket G).
  - The meta-layer is genuinely small, so Memory may saturate early; that's honest, not a bug.

### D-SR3 — Brownfield engine change: skill-as-card interleaving / fresh-item draw (Level 2)

- **Status:** resolved
- **Chose:** The headline Rust change is a **Level 2** engine change that takes the brainlift's **D2** literally: the **skill/trap is the FSRS-scheduled unit** (modeled as a synthetic "skill card"), and on each due review the engine **draws a fresh, unseen item** of that skill from a pool and renders it (commit-then-reveal). New Rust lives in the queue builder (selection + interleaving) + a new protobuf RPC + pylib call. **Level 1** (interleaving + commit-reveal over real item-cards, FSRS scheduling the item) is the **Wednesday checkpoint** so a working review loop always exists.
- **Considered:** (a) *Level 1 only* — milder, lower-risk, but "serve a fresh item" isn't native and Performance isn't measured directly; kept as the fallback/checkpoint, not the headline. (b) *Points-at-stake queue* (order by skill-weight × weakness) — a real scheduler change but its value-ordering philosophy **fights interleaving** (the chosen study feature), so it would create two competing ordering stories; deferred to phase-2. (c) *Mastery-query-only as headline* — too peripheral to count as a real engine change; kept as a supporting change instead (D-SR5).
- **Gaps / risks:**
  - New data-model surface (skill cards + item pool) competes for time with the mobile + sync requirements in the same week → mitigated by the Level-1 Wednesday checkpoint and zero schema change (D-SR4).
  - The reviewer must render a *drawn* item rather than the card's own note fields — the one integration point that diverges from stock Anki. Verified feasible via the existing `RenderUncommittedCard`/`RenderExistingCard` RPCs while answering the skill card with the standard `CardAnswer` (reviewer extended, not forked).
  - **FSRS modelling caveat:** FSRS estimates per-*item* memory; applying it to a *skill* (a fresh item each review) reinterprets stability/difficulty as skill-level. Scheduling stays valid (it's a normal review stream), but whether the resulting intervals are *optimal* for skill practice is unproven — this is the brainlift's intended bet (D4); revisit with the calibration eval.

### D-SR4 — Reuse FSRS / answer path / undo / sync; no new synced table in v1

- **Status:** resolved
- **Chose:** Build *within* Anki's architecture with **zero schema change**: skill cards are answered through the **normal `answer_card` path** (so FSRS interval math is untouched and stays valid per D2), the **revlog** records each review, **undo** works because the review is an ordinary `Op::AnswerCard` transaction, and **sync rides the existing `cards`/`notes`/`revlog`/`graves` tables**. **Performance derives from the synced skill revlog** (every skill review is a fresh item, so the rating already encodes correct/wrong) — so **no new table** is needed for scores. Per-card metadata (skill id) rides the existing `Card.custom_data` field / tags. Repeat-avoidance is a **best-effort local sidecar outside the collection** (profile folder / session memory), not a synced or undoable mutation.
- **Considered:** (a) A dedicated **synced per-item-outcome table** for exact cross-device Performance — rejected for v1 because it adds sync surface, an upstream-merge-risky **schema bump** (downgrade path, `dbcheck`), and competes with the graded sync work; revisit if per-device recomputation proves insufficient. (b) Putting the served-item record *inside* the collection as an undoable change — rejected because it would force a schema change for a non-authoritative convenience log.
- **Gaps / risks:**
  - Per-device Performance recomputation can drift slightly between devices until both have synced; acceptable for v1, flagged for phase-2.
  - The local sidecar is non-authoritative: an undone review may make an item re-eligible to draw (no corruption, no score loss). Acceptable.

### D-SR5 — Mastery-query RPC for dashboard latency

- **Status:** resolved
- **Chose:** Add a small additive Rust **mastery-query RPC** (per-skill mastered-count + average recall) implemented as one indexed SQL aggregate, to keep the three-score dashboard under the p95 < 1s target on 50k cards.
- **Considered:** Computing aggregates in Python over `DBProxy` — rejected as likely to blow the latency budget on 50k cards.
- **Gaps / risks:**
  - Another (small) new RPC to test; low merge risk because it's additive and read-only.

### D-SR6 — Study feature under ablation: interleaving

- **Status:** resolved
- **Chose:** The single learning-science feature tested with the 3-build ablation (full / feature-off / plain Anki, equal study time) is **interleaving** (mixing question types/skills within a session). Pre-stated hypothesis: *"Interleaving question types within a session raises accuracy on new, mixed-type items at equal study time, versus blocked practice."* Implemented as a **new additive `ReviewCardOrder` enum variant** in deck config (idiomatic — that enum already drives review ordering; extensible to future orders like points-at-stake), so the ablation is simply selecting the stock order.
- **Considered:** Blind Review (novel, but harder to ablate cleanly in a week); prephrasing/generation (good, but interleaving has the strongest direct evidence — H.1, ~76% delayed gain — and reuses the Rust change).
- **Gaps / risks:**
  - A one-week ablation has a small N and short retention window; report effect size + range + null results honestly (the assignment rewards a fair test that *could* fail).

### D-SR7 — Mobile: Android via AnkiDroid fork

- **Status:** resolved
- **Chose:** The phone companion is an **AnkiDroid fork** (Android), which already runs Anki's Rust backend and shares sync — so the engine change (D-SR3) ships to phone via the shared backend.
- **Considered:** Android thin client running the Rust backend directly (more control, more build risk); iOS via Rust FFI (closest to "real" Anki iOS, hardest in a week). iOS deferred (Android-first).
- **Gaps / risks:**
  - The Level-2 reviewer change (render a drawn item) must be ported to AnkiDroid's review UI, not just the desktop — a second UI integration.
  - AnkiDroid's build/toolchain is its own learning curve; budget time before Thursday.

### D-SR8 — Sync: self-hosted anki-sync-server; conflict = USN/graves merge

- **Status:** resolved
- **Chose:** Use Anki's **existing sync**, self-hosted via the `anki-sync-server` binary already in `rslib/sync`. The conflict rule for the same card reviewed offline on both devices is **Anki's USN/graves review-merge** (both reviews are retained in the revlog; none double-counted), documented as the project's conflict rule.
- **Considered:** A custom sync layer (unnecessary reinvention, more risk); AnkiWeb hosted sync (external dependency, less control over the test).
- **Gaps / risks:**
  - Anki's merge is at the review-log level; the "single correct winner" framing in the assignment's conflict test maps to "both reviews kept, FSRS state recomputed deterministically" — we must document this precisely so it reads as a real conflict rule, not a dodge.

### D-SR9 — Readiness mapping: performance-weighted coverage → published conversion + band

- **Status:** resolved
- **Chose:** Project 120–180 by aggregating per-skill **Performance**, weighting each skill by its exam frequency, converting to a scaled score via a **published LSAT raw→scaled conversion**, and reporting a **band** whose width grows with estimation variance + coverage gaps.
- **Considered:** Full IRT-lite (ability θ → scale) — more principled but data-hungry and riskier in a week; concordance-only on a raw % — simplest but weak on coverage honesty. The chosen method is the honest middle: transparent, week-feasible, and the band visibly widens when data is thin.
- **Gaps / risks:**
  - Exam-frequency weights and the conversion table are approximations from public sources, not LSAC's true equating — state this and cite sources.
  - Without real practice-test outcomes, Readiness is validated only at the calibrated-steps level (Step 1–3), not end-to-end (Step 4 is bonus) — by design (D-SR1).

### D-SR10 — Give-up rule: ≥200 attempts AND ≥50% coverage, as a pure gate

- **Status:** resolved
- **Chose:** The app shows **no** Readiness projection until **≥200 graded item-attempts AND ≥50% taxonomy coverage**; otherwise it **abstains** with an honest panel (evidence so far, exactly what's missing, past-guess accuracy once available, the single best next thing to study). Implemented as a **pure function** `readiness_gate(attempts, coverage, …) -> Eligible | Abstain{reasons[]}` so it is directly unit-testable, with an integration test asserting the dashboard payload contains no point estimate while abstaining.
- **Considered:** Lighter (100 / 40% — shows a number sooner, weaker), stricter (300 / 60% — abstains longer). The default matches the assignment's worked example and is defensible.
- **Gaps / risks:**
  - Thresholds are a judgment call, not derived from a power analysis — documented as a stated line, tunable.
  - Memory and per-skill Performance still render where they have data; only the 120–180 projection gates (so the dashboard isn't empty pre-threshold).

### D-SR11 — Item source: bundled cited seed deck + upload-your-own; licensing deferred

- **Status:** resolved
- **Chose:** Ship the engine + taxonomy + tagging + a **bundled, source-cited seed deck of real LSAT items** (so graders get a working deck out of the box) **and** support **upload-your-own** (official LawHub PrepTests). The app never *authors* LR items (F.2). Licensing is treated as **separate operational logistics**, handled later — not a code concern for this build.
- **Considered:** Upload-your-own only (cleaner legally, but graders have no deck); synthetic items only (conflicts with "AI never authors LSAT items"). Per the owner: bundling is required for grading; cite sources, defer licensing.
- **Gaps / risks:**
  - **Owned gap:** redistribution licensing of bundled real items is unresolved and intentionally deferred to ops; not blocking the code. Every bundled item carries a source citation.

### D-SR12 — v1 scope: LR + lightweight daily-reading stub; RC = phase-2

- **Status:** resolved
- **Chose:** Graded v1 covers **Logical Reasoning** end-to-end (engine, three scores, interleaving, AI tagging) **plus a lightweight daily-reading stub** (a domain-rotating passage → produced structural map → vocab harvest, non-AI on Wednesday). **Reading Comprehension question practice** and the **full** daily-reading module are **phase-2**, reusing the same engine.
- **Considered:** LR-only (cleanest, but hides the fluency-substrate vision); LR + full RC (doubles the taxonomy/tagging work in one week). The stub shows the vision at low cost.
- **Gaps / risks:**
  - Coverage % is computed over the **LR** taxonomy in v1; the dashboard must label this honestly ("LR coverage") so Readiness isn't mistaken for whole-exam readiness.

### D-SR13 — Taxonomy: PowerScore-based, two axes + trap catalog

- **Status:** resolved
- **Chose:** Own a **PowerScore-derived** taxonomy: **axis 1** = ~13 LR question types (stem-derivable: Flaw, Assumption, Inference/Must-Be-True, Strengthen, Weaken, Paradox, Principle, Parallel, Method, Main Point, …); **axis 2** = reasoning sub-skills (conclusion-ID, conditional, causal, formal-logic quantifiers, abstraction); plus a finite **trap catalog**. RC types added in phase-2.
- **Considered:** A from-scratch taxonomy (needless; industry already converges per Insight 3 / J.1) — rejected. PowerScore is the de-facto standard (the brainlift's Category-K authority).
- **Gaps / risks:**
  - Names diverge across publishers; we pick and own one mapping (a concordance exists). Axis-2 tags are fuzzier → AI-assisted then human-verified (D-SR14).

### D-SR14 — AI: a binding honesty contract + one anchor eval + an open roster

- **Status:** resolved (contract + anchor) / **open** (the broader roster)
- **Chose:** A binding **AI honesty contract** that holds for *every* AI output: traces to a **named source** → **generate-then-verify** (AI never owns correctness — D1) → checked on a **held-out set** → **beats a simpler baseline** (keyword/vector) → app **still scores with AI off** → **no AI before Friday**. One **committed anchor evaluated feature: skill/trap/type auto-tagging** of imported items (held-out accuracy vs human gold labels; baselines keyword + vector kNN). The rest of the roster (explanation/diagnosis, difficulty warm-start, daily-reading generation+feedback, **RAG / knowledge-graph** methods) is **open / in flux** — each must clear the contract when added.
- **Considered:** Locking the full feature roster now — rejected; the owner is still exploring RAG/graph methods and may add features. The contract + anchor keep the plan dispatch-ready without freezing the roster. (§13's "graph beats keyword + vector with real numbers" is itself a contract-satisfying eval and can become a second evaluated feature.)
- **Gaps / risks:**
  - **Open:** which roster features actually ship Friday, and whether a graph/RAG method becomes a second evaluated feature — to be resolved as the AI work firms up; tracked, not blocking.
  - Axis-2 / trap tags need human verification before they drive scores → a labeling-throughput cost.

### D-SR15 — AI-card-check (gold set): meta-vocabulary only

- **Status:** resolved
- **Chose:** The card-generation safety check (assignment 7f) generates **meta-layer cards only** (logic/argument vocabulary, flaw definitions, indicator/quantifier words) from **one cited source**, checked against a **50-item held-out gold set** via **generate-then-verify** (factual correctness vs source, non-duplication, teaching quality). A **pass cutoff is fixed before looking** (0 wrong-fact tolerance + a minimum useful-rate); the three counts (correct&useful / wrong / correct-but-bad-teaching) are reported; failing cards are blocked. The source is **sanitized for hidden text** before generation (prompt-injection guard).
- **Considered:** Generating LR items (forbidden by F.2); checking generated explanations against published rationales (kept as an optional second gold set, not the primary). Meta-vocab is the only flashcard-appropriate layer (Insight 5), so it's the honest target.
- **Gaps / risks:**
  - A 50-item gold set is small; report confidence intervals on the pass-rate.

### D-SR16 — Doc home: `docs/speedrun/`

- **Status:** resolved
- **Chose:** Planning docs (PRD, specs, this log) live in a tracked **`docs/speedrun/`** folder, beside the brainlift in `docs/`. Architecture references stay in git-ignored `extra/architecture/`.
- **Considered:** `docs/` flat with a `speedrun-` prefix (less grouped); `extra/` (git-ignored — wrong for a public AGPL handin).
- **Gaps / risks:**
  - None material.

---

> **Build · wave 1 (D-SR17–D-SR22)** — decisions made during the WP-1/WP-12/WP-16
> build agents (2026-06-30), promoted from their inbox logs.

### D-SR17 — Taxonomy materialization (13 types, Principle standalone, 38 skill notes)

- **Status:** resolved
- **Decided:** 2026-06-30, WP-1 build agent (promotes inbox L1/L3/L7)
- **Chose:** Materialize the PowerScore taxonomy as **13 axis-1 question types** (Principle a standalone type with identify/apply subtypes; Justify standalone; Role a Method subtype), **6 axis-2 sub-skills**, and **19 traps** (12 argument flaws + 7 distractor traps) → **38 LSAT Skill notes**. Tag strings frozen in `docs/speedrun/data/taxonomy.json`.
- **Considered:** Principle as a cross-type overlay (PowerScore purist) — rejected (breaks single-type pool selection); 14/15-type counts — rejected for the ~13 brainlift consensus.
- **Gaps / risks:** distractor-trap skills' schedulability unresolved (→ B010); any tag-string change ripples to all WPs.
- **Ref:** `docs/speedrun/data/taxonomy.json`, spec-engine §7, D-SR13.

### D-SR18 — Readiness formula correction (drop double `w_S`) — **Overrides spec-measurement §4.3**

- **Status:** resolved (confirmed 2026-06-30 by Opus)
- **Decided:** 2026-06-30, WP-1 build agent (inbox L5); confirmed by orchestrator
- **Chose:** Treat `items_per_skill_on_form(S) = w_S · N_lr` and **drop the extra outer `w_S`**, giving `expected_raw = N_lr · Σ_S [w_S · Perf(S)]` (= N_lr at Perf=1). Implemented in `weights.json`.
- **Considered:** the literal §4.3 formula (double `w_S`) → `Σ w_S²·Perf < N_lr` at Perf=1, wrong unless a frequency-squared weighting was intended.
- **Verified:** the literal formula is mathematically inconsistent with the "perfect performance ⇒ max raw" sanity check (`Σw_S²<1`), so the double `w_S` is a typo. The corrected form is the frequency-weighted mean performance × total items. Override stands; no further confirmation needed.
- **Overrides:** spec-measurement §4.3 (see `AGENTS.md` → "Overrides since the plan").
- **Ref:** `docs/speedrun/data/weights.json`, spec-measurement §4.3.

### D-SR19 — v1 Readiness is an explicit "LR-only estimate"

- **Status:** resolved (refines D-SR12)
- **Decided:** 2026-06-30, WP-1 build agent (inbox L6)
- **Chose:** With no RC items in v1, the LR+RC raw→scaled table can't take a full-form raw, so report a **labeled "LR-only projected score" with a wider band** (Option B), not an assumed RC fill-in.
- **Considered:** (A) assume RC Perf = mean LR Perf and scale up (overclaims); (C) abstain entirely (too conservative for v1).
- **Gaps / risks:** dashboard must clearly label "LR-only estimate"; revisit when RC lands.
- **Ref:** `weights.json`, spec-measurement §4.3, D-SR12.

### D-SR20 — Card-check verification is deterministic & lexical (real LLM behind a seam)

- **Status:** resolved (verify) / open (real generator)
- **Decided:** 2026-06-30, WP-12 build agent (inbox L-D1/L-D2)
- **Chose:** The `FactualChecker` verifies via lexical token-coverage vs the cited source (≥30%) — fully deterministic, D1-compliant (no model judges correctness). Generation sits behind an `LLMClient` protocol with a `DeterministicStubClient`; a real model is a deferred wiring task.
- **Considered:** embedding/NLI verification (reintroduces a model at verify time → violates D1); hardcoding stub answers (defeats the factual check).
- **Gaps / risks:** lexical check misses **semantic inversions** (→ B011); real LLM not wired (→ B012).
- **Ref:** `tools/speedrun/cardcheck/{checker,generator}.py`, spec-ai §5, D1.

### D-SR21 — Card-check thresholds (cutoffs + dedup)

- **Status:** resolved
- **Decided:** 2026-06-30, WP-12 build agent (inbox L-D3/L-D4)
- **Chose:** Pre-declared `WRONG_FACT_TOLERANCE = 0`, `MIN_USEFUL_RATE = 0.60`; near-duplicate block at Jaccard ≥ 0.65 on question tokens; Wilson 95% CIs reported.
- **Considered:** 70% useful floor (may over-fail a real model); 50% (too lenient); TF-IDF/edit-distance dedup (more complex).
- **Gaps / risks:** floors are non-binding on the verbatim stub (~93% useful); become binding with a real model.
- **Ref:** `tools/speedrun/cardcheck/report.py`, spec-ai §5.

### D-SR22 — Leakage fallback = char-3gram cosine + `EmbeddingProvider` seam

- **Status:** resolved
- **Decided:** 2026-06-30, WP-16 build agent (inbox L1)
- **Chose:** Deterministic char-3gram TF cosine (stdlib, no deps) as the default leakage near-duplicate detector, behind an `EmbeddingProvider` protocol so a real sentence-embedding model can be injected.
- **Considered:** char-2gram (too coarse), word-TF (misses morphology), BM25 (extra dep).
- **Gaps / risks:** fallback catches verbatim + minor-edit copies but scores full paraphrase ~0.65 (< 0.85 threshold) → real model needed for semantic paraphrase (→ B014).
- **Ref:** `tools/speedrun/eval/leakage.py`, spec-measurement §7.

### D-SR23 — Distractor traps ARE schedulable skills (pool = items carrying the trap)

- **Status:** resolved
- **Decided:** 2026-06-30 by owner (resolves B010)
- **Chose:** Distractor traps (half-true, too-extreme, …) are **first-class schedulable skills**, like argument flaws. The item pool for `trap::X` = LSAT Item notes carrying `trap::X` (≥1 distractor exhibits trap X); an item can belong to several trap pools.
- **Considered:** traps as item-level signals only, not schedulable — rejected by owner; the trap is a practiceable discrimination skill.
- **Gaps / risks:** items must be tagged at the **item level** with every distractor trap they contain → **WP-11 must emit item-level `trap::*` tags** (not only per-choice); a single item appears in multiple trap pools (fine for selection).
- **Ref:** spec-engine §5.2, D-SR17; closes B010.

### D-SR24 — Canonical tags use Anki's native `::` hierarchy separator

- **Status:** resolved
- **Decided:** 2026-06-30 by Opus (resolves B009)
- **Chose:** Tag strings keep `::` intact (`type::flaw`, `skill::conditional`, `trap::half-true`); the pool query is `tag:skill::S` (spec-engine §5.2). Anki uses `::` as the native tag-hierarchy separator (`rslib/src/tags/mod.rs` `rsplit_once("::")`). Reverted the WP-1 agent's `::`→`_` normalization in `build_seed_deck.py`.
- **Considered:** normalizing `::`→`_` "for safety" (WP-1 default) — rejected: unnecessary, flattens the hierarchy, and silently broke coverage search (items tagged `::`, search used `_` → 0 results).
- **Gaps / risks:** search is exact-match (`tag:type::flaw`); subtree queries need `tag:type::*`. WP-3 should still add a round-trip test on a built collection.
- **Ref:** `rslib/src/tags/mod.rs`, `build_seed_deck.py`, spec-engine §5.2; closes B009.

### D-SR25 — Tagging eval design: fair keyword baseline + AI-reads-choices advantage

- **Status:** resolved
- **Decided:** 2026-06-30, WP-11 build agent (promotes inbox L-D1/L-D2/L-D4)
- **Chose:** The keyword baseline uses an extended causal lexicon (a competent baseline, not a strawman) on **stem+stimulus only**; the AI tagger's wedge is that it **reads the answer-choice texts** to detect distractor traps (spec-ai §4 restricts the keyword baseline to stem+stimulus). Vector-kNN falls back to stem rules when no kNN majority emerges.
- **Considered:** keyword on only the 6 taxonomy key_indicators (strawman); giving keyword access to choices (conflates the baselines).
- **Gaps / risks:** the AI's trap-axis advantage comes substantially from having **more input** (choices), not only better modelling — **state this transparently** in the writeup so the "beats a simpler method" claim is honest.
- **Ref:** `tools/speedrun/tagging/{baselines,tagger}.py`, spec-ai §4, D-SR14.

### D-SR26 — Unrecognized stems route to human-verify (no silent `type::flaw` fallback)

- **Status:** resolved (overrides the WP-11 stub default; implement via B017)
- **Decided:** 2026-06-30 by Opus (resolves inbox L-A4 / L-D3)
- **Chose:** When no stem rule matches, the tagger must **not** silently assign `type::flaw`; instead mark the item `type::unknown` (or leave untyped) and route it to the human-verify queue. A confident wrong type corrupts pool selection + coverage.
- **Considered:** keep the `type::flaw` default (silently mislabels); raise `ValueError` (crashes batch tagging).
- **Gaps / risks:** small `StemClassifier` change needed (→ B017); `type::unknown` must be excluded from coverage/scheduling.
- **Ref:** `tools/speedrun/tagging/tagger.py:StemClassifier`, spec-ai §4.

---

> **Build · wave 2 (engine, D-SR27–D-SR28)** — decisions promoted from the WP-3/WP-4/WP-5
> engine build agents (2026-06-30), after their branches merged to `main`.

### D-SR27 — Skill identity = first `type::` / `skill::` / `trap::` note tag

- **Status:** resolved
- **Decided:** 2026-06-30, promoted from WP-3/WP-4/WP-5 build agents (inbox WP-3 L1, WP-4 L1, WP-5 L2/L3)
- **Chose:** A skill card's (and item's) skill identity is the **first note tag** whose prefix is `type::`, `skill::`, or `trap::` — the `IdentityTag` written by `build_seed_deck.py` (`note.tags = [IdentityTag]`). All three engine lanes **independently converged** on this: WP-3 (`draw_item_for_skill` pool lookup), WP-4 (interleave grouping by `type::*`), WP-5 (mastery grouping). Skill-vs-item is disambiguated by **notetype name** ("LSAT Skill"), *not* by tag, so item notes (which also carry `type::/skill::/trap::` tags) are not miscounted.
- **Considered:** reading `Card.custom_data` or a notetype field for identity — rejected: the pool query is tag-based (`tag:skill::S`, spec-engine §5.2), a field read adds a field-order dependency, and custom_data is empty on seed skill cards.
- **Gaps / risks:** assumes exactly one identity tag per skill card; a user-added second `type::/skill::/trap::` tag → first wins (documented). The grouping-key form is now frozen across three lanes — a taxonomy tag-string change ripples to WP-3/4/5.
- **Ref:** `build_seed_deck.py` (`note.tags = [IdentityTag]`), spec-engine §5.2/§5.4/§7, D-SR24; inbox WP-3 L1 / WP-4 L1 / WP-5 L2/L3.

### D-SR28 — Mastery threshold: FSRS recall ≥ 0.90

- **Status:** resolved (tunable single const)
- **Decided:** 2026-06-30, WP-5 build agent (inbox L1/L6)
- **Chose:** A skill card counts as **mastered** when its current FSRS recall (retrievability) ≥ **0.90**, as the module constant `MASTERY_RECALL_THRESHOLD` feeding `skill_mastery`. 0.90 matches FSRS's default desired-retention; recall uses the existing `FSRS::current_retrievability_seconds` (not forked). Cards with no memory state (never reviewed) contribute recall 0.0 and are not mastered.
- **Considered:** 0.80 (marginally-learned skills count → inflates the dashboard), 0.95 (too strict early).
- **Gaps / risks:** a judgment line, not calibrated from real data — revisit with WP-7 (Memory) / the calibration eval; single-line change if it needs tuning.
- **Ref:** `rslib/src/stats/service.rs` (`MASTERY_RECALL_THRESHOLD`), spec-engine §5.4, D-SR5; inbox WP-5 L1/L6.

---

> **Build · wave 3 (measurement + reviewer, D-SR29–D-SR30)** — promoted from the WP-6/WP-7
> build agents (2026-06-30), after their branches merged to `main`.

### D-SR29 — Memory band = 1000-resample bootstrap; Python/dashboard exposure deferred to WP-14

- **Status:** resolved (compute) / deferred (exposure)
- **Decided:** 2026-06-30, WP-7 build agent (inbox L1/L2)
- **Chose:** Memory score (spec-measurement §4.1) = mean FSRS recall over `LSAT Meta` cards; **band = 95% percentile bootstrap CI, 1000 resamples, fixed seed** (deterministic). Unreviewed Meta cards contribute recall 0.0 (mirrors D-SR28 / WP-5). The computation lives in Rust (`memory_score_impl`), but **exposing it to Python is deferred to WP-14**: a `MetaMemory` proto RPC would need a full rebuild and collide with parallel proto regen, and WP-14 (dashboard) already depends on WP-7, so it adds the RPC there at zero extra cost.
- **Considered:** analytic normal CI (wrong for small, bounded recall samples); adding the proto RPC now (build + merge-coordination cost with no consumer yet).
- **Gaps / risks:** until WP-14, Memory is Rust-only (not callable from pylib) → tracked B031.
- **Ref:** `rslib/src/stats/measurement.rs`, spec-measurement §4.1 / AC 1, D-SR5; inbox WP-7 L1/L2.

### D-SR30 — Level-2 drawn item rendered via Python field injection, not `RenderUncommittedCard` — **Overrides spec-engine §8 (render mechanism)**

- **Status:** resolved (v1) — revisit for AnkiDroid parity
- **Decided:** 2026-06-30, WP-6 build agent (inbox L5)
- **Chose:** The desktop reviewer renders the drawn item by reading its note fields in Python and injecting HTML via `web.eval()`, rather than the `RenderUncommittedCard`/`RenderExistingCard` RPCs that spec-engine §8 named. Functionally equivalent for v1 and simpler (no TS rebuild); **render-source and answer-target stay decoupled**, so the [B002] invariant (the *skill card* is answered via the unchanged path) is still honored.
- **Considered:** the §8 RPC path (the "verified feasible" mechanism) — deferred because field injection landed faster and the answer pipeline is untouched either way.
- **Gaps / risks:** AnkiDroid (WP-8/WP-15) can't reuse a Python-only render → mobile needs either the RPC path or its own injection; revisit for cross-platform parity (→ B029). Overrides spec-engine §8's stated *mechanism*, not its intent.
- **Overrides:** spec-engine §8 (see `AGENTS.md` → "Overrides since the plan").
- **Ref:** `qt/aqt/speedrun.py`, `qt/aqt/reviewer.py`, spec-engine §8, D-SR3; inbox WP-6 L5; B029.

---

> **Build · wave 4 (dashboard, D-SR31–D-SR32)** — promoted from the WP-14 build agent
> (2026-06-30), after its branch merged to `main`.

### D-SR31 — Revlog ease→outcome mapping: ease ≥ 2 = correct, ease == 1 (Again) = wrong

- **Status:** resolved
- **Decided:** 2026-06-30, WP-14 build agent (inbox L1); resolves the ease-mapping half of B014
- **Chose:** For Performance (and eval outcomes), a skill-card revlog row counts as **correct iff `ease ≥ 2`**; `ease == 1` (Again) is wrong; only `ease BETWEEN 1 AND 4` rows count (manual-reschedule `ease = 0` excluded). Mirrors Anki's own "true retention" stat and the WP-6 reviewer's `wrong→Again(1) / right→Good(3)` convention (D-SR3 §5.1) — so Hard(2) counts as correct (retrieval succeeded, if slow).
- **Considered:** treating Hard(2) as wrong (penalizes effort, diverges from Anki retention); a recency-weighted / hard-penalized variant (phase-2).
- **Gaps / risks:** Hard=correct can slightly inflate Performance for Hard-heavy users; revisit in phase-2. This is the same mapping the WP-16 eval README assumed (B014) — now canonical.
- **Ref:** `rslib/src/storage/card/speedrun.rs::skill_revlog_in_decks`, spec-measurement §4.2, D-SR3; inbox WP-14 L1; B014.

### D-SR32 — Readiness band / confidence / coverage method (v1)

- **Status:** resolved (tunable constants)
- **Decided:** 2026-06-30, WP-14 build agent (inbox L2/L4/L5/L6/L8)
- **Chose:** The dashboard is one combined **`SpeedrunDashboard(deck_id)`** RPC returning Memory + per-skill Performance + Readiness-or-Abstain, with an **`eligible` flag that callers MUST check before rendering any Readiness number** (the honesty-critical field, D-SR10). Readiness math (when eligible): **band = Wilson-width component (`Σ w_S·N_lr·(wilson_high−wilson_low)/2`) + coverage-gap component (`(1−coverage)·N_lr·0.5`)**, both projected LR→full-form by **×(76/50)** (Option B, D-SR19); both components shrink as N↑/coverage↑ (satisfies the "band widens as data thins" AC). **Confidence tiers:** high (coverage ≥ 85% AND ≥ 500 attempts), medium (≥ 65% AND ≥ 300), else low. **LR coverage** = fraction of the 13 `type::*` question-types with ≥ 5 attempts (`skill::*`/`trap::*` show per-skill Performance but don't count toward coverage/the gate).
- **Considered:** three separate RPCs (more round-trips); coverage counting `skill::`/`trap::` (diverges from the weighted LR taxonomy, D-SR12); coverage-gap coefficient 1.0 (max-conservative) — chose 0.5 as the intermediate.
- **Gaps / risks:** the band coefficient and confidence thresholds are informed judgment calls, not calibrated — revisit with WP-17 ablation / real data. Coverage uses "≥5 attempts" rather than spec §5's "pool ≥ min size AND ≥ min attempts"; acceptable for v1.
- **Ref:** `rslib/src/stats/performance.rs`, `proto/anki/stats.proto` (`SpeedrunDashboard`), `docs/speedrun/data/weights.json`, spec-measurement §4.3/§5/§8, D-SR9/D-SR10/D-SR18/D-SR19; inbox WP-14 L2/L4/L5/L6/L8.

---

> **Product · UX reframe (D-SR33–D-SR34)** — decided 2026-06-30 with the owner after
> reviewing the running demo; the Anki reviewer/deck surface reads as "flashcards," which is
> the wrong mental model for a reasoning exam. **Presentation layer only — the engine
> (FSRS skill scheduling, `draw_item_for_skill`, revlog→Performance, the gate, sync, mobile)
> is unchanged.** Full design captured in [`spec-ui.md`](./spec-ui.md).

### D-SR33 — Product surface is a study-plan + practice-session app, not a deck of flashcards — **Overrides PRD/spec reviewer-and-deck framing**

- **Status:** resolved (design); build reshapes WP-6/WP-14, adds a `ts/` session layer
- **Decided:** 2026-06-30 by owner + Opus (demo-driven)
- **Chose:** Reframe the whole user-facing surface away from Anki's deck browser / due-queue / "cards": the **home is a study-plan dashboard** (the three scores + the single "next best thing"), and studying happens in **sessions** — *Targeted drill* (weakest high-frequency skill), *Mixed set* (interleaved), *Timed section*, and *Blind review* — each a **start → work → score → review** arc, ending on a set-level result + review screen. Anki chrome (deck list, due counts, "Show Answer", the 4 colored ease buttons, heatmaps) is hidden; language is LSAT-native ("items, drills, sections, review", not "cards, decks, reviews"). **This is a presentation/session layer only — every graded signal still flows through the existing engine** (a session = a batch of due skill cards; the drawn item + commit-then-reveal + `AnswerCard` are unchanged). RC (phase-2) gets a **passage workspace** layout under the same draw model, so the presentation does not paint us into a corner.
- **Considered:** keeping the stock Anki reviewer/deck UI (fastest, but the flashcard framing misrepresents reasoning practice and tanks the product); rethinking the scheduling model or the Anki foundation itself (rejected — that would discard the graded brownfield-engine thesis and the week's work; owner scoped this to *UI only*).
- **Grounding:** self-regulated learning (goal + progress + a single next action reduces avoidance and choice overload); deliberate practice (drive practice to the edge of competence via the weakest-skill recommendation); the app already computes "next best thing" (D-SR9/WP-14).
- **Gaps / risks:** reshapes WP-6 (reviewer → session/drill surface) and WP-14 (dashboard → home) and adds session state/timer/results screens in `ts/` — all additive, no Rust/schema change. Does **not** address the FSRS-as-skill pedagogy question (B003), which is intentionally kept.
- **Overrides:** PRD (Anki-reviewer/deck framing) + spec-engine §6/§8 presentation assumptions (see `AGENTS.md` → "Overrides since the plan").
- **Ref:** [`spec-ui.md`](./spec-ui.md), spec-engine §6/§8, D-SR3/D-SR6/D-SR9; supersedes the implied stock-Anki UI.

### D-SR34 — LR drill interaction: commit-then-reveal + prephrase + name-the-trap, with the MC commit as the deterministic scoring backbone

- **Status:** resolved
- **Decided:** 2026-06-30 by owner + Opus
- **Chose:** Enrich the drill interaction beyond "pick 1 of 5, reveal" (recognition-only) with two learning layers, while keeping scoring deterministic and **AI-free**:
  1. **Generation — prephrase.** Before the choices (some of the time; scaffolded early, faded as Performance rises), the learner predicts what the answer must do. v1 is **self-scored** on reveal ("did your prediction match?"); optional AI feedback on the free text is deferred until AI is available (**Wednesday night** per the current constraint) and, when added, must obey the honesty contract (AI never owns correctness — D-SR14/D1).
  2. **Error diagnosis — name-the-trap.** On a wrong commit, the learner classifies *why* their choice was wrong by picking the trap; this is **deterministically checked against the item's per-choice `TrapChoiceA–E` tags** (already in the data model — no AI, no new data).
  Plus an optional **confidence** tap (calibration signal) and an untimed **blind-review** mode. The **multiple-choice commit remains the sole deterministic graded signal** that drives the FSRS rating + Performance (spec §5.1). Interaction intensity is **mode-driven**: timed sections = fast MC only; untimed drills = full prephrase + eliminate/diagnose; wrong answers trigger the trap step.
- **Considered:** free-text answers as the graded signal (can't grade deterministically without AI → violates D1 / no-AI-pre-Wed); MC-only (recognition, weak for reasoning); highlight-the-conclusion input (needs a new marked-conclusion item field — deferred, tracked separately).
- **Grounding (learning science):** the *generation effect* / prephrasing (produce before recognizing); *error-driven learning* + misconception diagnosis (naming the trap turns a miss into the lesson); *elaborated, immediate feedback* (per-choice why-wrong at the moment of error); *desirable difficulties* (commit-before-reveal, interleaving, blind review — Bjork); *metacognitive calibration* (confidence vs. correctness).
- **Gaps / risks:** confidence/prephrase capture needs somewhere to live — session-local for v1 (calibration), `Card.custom_data` if it must persist (no schema change); "highlight the conclusion" needs a new item field before it can be auto-checked.
- **Ref:** [`spec-ui.md`](./spec-ui.md), `tools/speedrun/deck/sample_items.json` (`TrapChoiceA–E`), spec-engine §5.1/§6, D-SR14/D1; brainlift K.1 (prephrasing) / D5 (trap signals).

### D-SR35 — Session model & review flow (drills / mixed / timed / blind review)

- **Status:** resolved (sizes are tunable dev defaults)
- **Decided:** 2026-06-30 by owner + Opus (extends D-SR33)
- **Chose:** Studying happens in bounded **sessions**, not an open due-queue. Four modes:
  - **Targeted drill** (~10 items) — all items drawn for the single recommended skill (weakest high-frequency, the dashboard's next-best-thing); untimed; full prephrase + name-the-trap.
  - **Mixed set** (~10) — interleaved across due skills (`ReviewCardOrder::InterleavedSkills`, D-SR6); untimed.
  - **Timed section** (~25 + a clock) — fast MC only; no prephrase/chips; error diagnosis deferred to the result screen (simulates the real test).
  - **Blind review** — re-runs the session's **misses / flagged items untimed**, forcing a fresh commit before the key.
  A session is a **framed batch pulled from the due-skill queue + fresh-item draws** (WP-3/WP-4); every item is answered via the normal `AnswerCard` path. The **result screen** shows session accuracy, a "where you slipped" list (the trap per miss, from `TrapChoiceX`), flag-to-revisit, and blind-review as the recommended next step.
- **Considered:** Anki's infinite due-queue (rejected — it *is* the deck feel we're removing); fixed full-section-only (too rigid for daily practice).
- **Gaps / risks:** session sizes/mode thresholds are judgment calls (relate B022 pacing); session misses are tracked **session-local**; flagged items persist via `Card.custom_data` only if needed (no schema change). Session accuracy is **display-only** — Memory/Performance/Readiness still come from the engine (revlog + `SpeedrunDashboard`), never from this screen.
- **Ref:** [`spec-ui.md`](./spec-ui.md) §3.3, spec-engine §5.2/§5.3, D-SR6/D-SR9/D-SR33; relates B022.

### D-SR36 — Speedrun is a full-window shell that hides Anki's default UI (refines D-SR33)

- **Status:** resolved (direction) — build = WP-24
- **Decided:** 2026-07-01 by owner (after the first cut still "looked like Anki")
- **Chose:** The reframe's first cut (WP-20/21) *extended* Anki — an opt-in Tools→"Speedrun Home" menu + a reviewer that only changes on skill cards — leaving Anki's deck browser, top toolbar, "Show Answer" chrome, and plain meta flashcards front-and-center, so it still reads as Anki. Instead, make Speedrun a **full-window shell**: **open Speedrun Home as the main surface on launch**, **hide/replace Anki's top toolbar + deck browser**, and **route all studying through Speedrun sessions/drill**. Essential functions (sync, browse) stay reachable via a minimal Speedrun bar or the native menu. Still **presentation-only** — the Anki windows/state machine are wrapped/hidden, not removed, and the engine/FSRS/scores/sync are untouched (a flag can restore stock Anki).
- **Considered:** the opt-in menu + extended reviewer (WP-20/21 as first built — too timid; still feels like Anki); a separate standalone app embedding the Rust engine (too heavy for the week, loses the fork thesis).
- **Gaps / risks:** touches Anki's **main-window state machine + toolbar** — the riskiest presentation change so far; must keep Browse/Sync/Add reachable; must not break normal Anki when the shell is off; verify on a real GUI (headless can't).
- **Ref:** [`spec-ui.md`](./spec-ui.md), D-SR33; build = WP-24.

### D-SR37 — Speedrun Home is the self-sufficient hub; the Anki deck browser is never a user surface (refines D-SR36)

- **Status:** resolved (direction) — build = WP-25
- **Decided:** 2026-07-01 by owner ("I don't want to drop into the full Anki deck browser; I want any functionality Anki had to be accessible from Speedrun Home")
- **Chose:** All Anki functionality (**Sync, Browse, Add, Stats, Import/Export, Deck options, Preferences**) is surfaced **inside the Speedrun Home** via a top bar / "More" menu, wired through the Home's pycmd bridge to the existing `mw.*` actions (they open standard Anki dialogs on top of the Home, then return to it). The raw Anki **deck browser is not a surface the user uses or falls back to** — it stays hidden/covered behind the maximized Home. This **supersedes the intermediate "close Home → full Anki" idea** (functionality was reachable but via the deck browser, which the owner rejected).
- **Considered:** (a) close-Home-to-reach-Anki (rejected — drops into the deck browser); (b) keeping the Anki toolbar visible under the shell (rejected — same). Chose surfacing functions in the Home instead.
- **Gaps / risks:** every Anki action that should be reachable must be explicitly wired into the Home bridge (an un-surfaced action becomes inaccessible while in the shell); `SPEEDRUN_SHELL=False` remains the escape hatch to stock Anki. Non-destructive: Anki dialogs/engine unchanged.
- **Ref:** `qt/aqt/speedrun_home.py` (bridge), `ts/routes/speedrun-dashboard/SpeedrunDashboard.svelte` (top bar), `qt/aqt/main.py` (`SPEEDRUN_SHELL`), spec-ui §2; refines D-SR36; build = WP-25.

### D-SR38 — Item pool is per-type JSON files + a deterministic (no-AI) validator; expanded to 151 synthetic items at the production floor

- **Status:** resolved
- **Decided:** 2026-07-01 by owner + Opus (content build-out, "no AI yet")
- **Chose:** Restructure the seed item pool from the single `tools/speedrun/deck/sample_items.json` into a **directory of per-type files** `tools/speedrun/deck/items/type-<slug>.json` (one file per `type::*`, `_format_version: 2.0`), loaded/merged by a new **`items_loader.py`** (dir *or* single-file, dedupes on `_id`). Add **`item_validator.py`** — a deterministic, AI-free gate that enforces the full LSAT Item contract against `taxonomy.json`: required fields, `SyntheticFlag`/`Source`, valid & consistent `type::`/`skill::`/`trap::` tags, `CorrectChoice` in A–E, a `WhyWrong*` for every choice, `TrapChoice*` present on wrong choices and empty on the correct one, `Difficulty` 1–5, and unique `_id`/`Stimulus`. It reports blocking **errors** and advisory **warnings** (e.g. "all distractors share one trap"). Then **authored the pool up to the production floor**: 151 synthetic items, **all 13 `type::*` at ≥10** (flaw 16; assumption/inference 13; strengthen/weaken/principle 12; paradox/parallel/method 11; justify/main-point/point-at-issue/evaluate 10). `build_seed_deck.py` + tests now read through the loader; validator + 84 deck tests green; `build_seed_deck --min-pool 10` reports **13/13 (100%)**.
- **Considered:** keeping one monolithic `sample_items.json` (rejected — doesn't scale for authoring, noisy diffs, merge pain); an AI author/validator (rejected — "no AI yet" + D-SR14 keeps correctness AI-free); enforcing coverage only in the deck builder (kept the builder's coverage check, but a standalone validator gives a fast content gate independent of a built collection).
- **Grounding:** the validator makes the data contract (D-SR13) machine-checkable so authored/imported items can't silently drift from the taxonomy; per-type files keep each question type independently editable and reviewable.
- **Gaps / risks:** all 151 items are **synthetic placeholders** — this raises *structural* coverage to the production floor but does **not** close the real-content gap (B015 stays open; real items still gated on D-SR11 licensing). Per-**skill** coverage is uneven: `skill::prephrase` has **0** items (it's a study-behavior tag, not really item-level) and `skill::quantifier` only **6** → tracked as **B043**. Difficulty skews to 2–3 (only 4 at L1, 2 at L4).
- **Overrides:** the item-pool path moved from `sample_items.json` (referenced in D-SR34 and B015) to `tools/speedrun/deck/items/` — those refs now point at the directory.
- **Ref:** `tools/speedrun/deck/{items_loader.py, item_validator.py, items/type-*.json, build_seed_deck.py}`, [`taxonomy.json`](./data/taxonomy.json), [`weights.json`](./data/weights.json) (`coverage_thresholds`); relates B007/B015/B043; data contract D-SR13.

### D-SR39 — Prep-book items: local personal import (gitignored, cited) + pattern-abstraction to author fresh synthetic items; never commit source text

- **Status:** resolved
- **Decided:** 2026-07-01 by owner + Opus (owner supplied two owned prep-book PDFs and asked to "take the questions and cite," then "use them as templates for modified synthetic")
- **Chose:** Two clearly separated paths, split on the copyright line (**citation is attribution, not a redistribution license**; prep-book questions are the *publisher's* copyright, not LSAC's):
  1. **Personal import (real items):** `import_prep_book.py` extracts LR items from a **locally owned** PDF (via `pdftotext`) into `LSAT Item` JSON under `tools/speedrun/deck/imported/` — which is **gitignored**. Items carry `SyntheticFlag="REAL"`, a full `Source` (author/title/ISBN/question#), and a `License="personal-import-not-for-redistribution"` field. `item_validator.py` now accepts `REAL` (requires a substantial citation); `build_seed_deck.py` gained `--import <dir>` (repeatable) that **merges** the committed synthetic pool with local imports at build time into the user's own `.anki2` (verified: 151 synthetic + 68 imported = 219, tests green). **No book text ever enters git** — only the user's own collection.
  2. **Pattern-abstraction → fresh synthetic (copyright-clean augmentation):** `derive_patterns.py` reduces imported items to **content-free logical skeletons** (`type`/`skill`/`trap`/coarse `logical_form`, **all stimulus & choice prose stripped**) — an authoring reference, gitignored. Fresh synthetic items are then **hand-authored** against those skeletons with new scenarios, sharing only the *unprotectable logical form* (modus tollens, sufficient/necessary, quantifier inference), and labeled honestly `SYNTHETIC`. First use: the Rotich book's skeletons are dominated by `skill::conditional` (50/68) — used that signal plus the B043 gap to author **4 new `skill::quantifier` inference items** (SYNTH-INFERENCE-014–017), taking the pool to **155** and `skill::quantifier` from 6 → **10** (closes the quantifier half of B043).
- **Considered:** (a) committing the book questions with citations (rejected — redistribution of copyrighted work; citation ≠ license); (b) **mechanically modifying** originals by swapping names/wording and calling them synthetic (rejected — a **derivative work** is still copyrighted, and it would mislabel provenance, violating D-SR11's honesty); (c) AI-generating items from the skeletons (deferred — gated by D-SR11/D-SR14 "no AI authoring of LR items"; would need its own decision). Chose deterministic import + human authoring from unprotectable form.
- **Grounding:** copyright protects *expression*, not *ideas/logical form* — authoring fresh expression against an abstracted pattern is what a human author does after studying prep books; keeping imports out of git and honestly flagged preserves the D-SR11 provenance contract and the "app scores with AI off" invariant (D-SR14).
- **Gaps / risks:** the Rotich parser gets ~68/100 Ch.4 questions (messy PDF layout skips the rest) and imported per-choice `WhyWrong` is a placeholder (book gives one explanation per Q) — review before relying on imported explanations; type tags are stem-heuristic and may mis-tag; APEX book not yet parsed (different layout). Imported items are **REAL/personal-use only** and must not be committed or synced to any shared deck.
- **Overrides:** refines D-SR11 (its "upload-your-own" path now has a concrete tool + a `REAL`-item validator path); does not change the bundled default (still synthetic-only unless `--import` is passed).
- **Update (2026-07-01, Opus):** clarified the copyright line — it is **abstraction level, not source**. Extracting an unprotectable *pattern* (`type`/`skill`/`trap`/logical form) and authoring *fresh* expression is legitimate (it is what PowerScore/Manhattan/Kaplan do) for **any** source including official LSAC items; only reproducing/re-skinning a specific question's *expression* is a derivative. `derive_patterns.py` gained a `--pdf --book apex-2019` **pattern-only** mode that reads the (LSAC-copyright) APEX practice test **transiently and persists no prose** — emits only per-question logical-form labels for LR §2/§3 (skips AR §1 off-format per D-SR1, and RC §4). APEX LR skews strengthen/weaken/causal-alternate-cause (complements Rotich's conditional skew). Bright line unchanged: no source prose committed; fresh synthetic output is original + committable.
- **Ref:** `tools/speedrun/deck/{import_prep_book.py, derive_patterns.py (--pdf --book), items_loader.py (merge_item_pools), item_validator.py, build_seed_deck.py (--import)}`, `.gitignore` (`tools/speedrun/deck/imported/`); relates B007/B015/B043; D-SR11/D-SR13/D-SR14.

### D-SR40 — Prove the Rust engine change end-to-end from Python with a self-contained pylib test

- **Status:** resolved
- **Decided:** 2026-07-01 by Opus (closing the Wednesday deliverable "1 test that calls it from Python")
- **Chose:** Add `pylib/tests/test_speedrun_engine.py` — a Python-level test suite that drives the brownfield Rust additions (WP-3 `draw_item_for_skill`, WP-5 `skill_mastery`) through their **generated backend + pylib wrappers**, covering the full Python → backend → Rust path the Rust unit tests can't. It builds a **minimal collection in-test** (creates the `LSAT Skill`/`LSAT Item` notetypes, the `LSAT Speedrun::Skills`/`::Items` decks, a tagged skill card + item pool) using the shared `tests.shared.getEmptyCol` fixture, then asserts: a draw returns a pool member, consecutive draws avoid an immediate repeat, an empty pool surfaces an error to Python, mastery aggregates the skill's card count, and an empty deck yields no rows. 5 tests, green; ruff/format clean; auto-included in `just test-py` (it lives in `pylib/tests`).
- **Considered:** (a) building the real seed deck via `build_seed_deck.py` and asserting against it — rejected as heavier, slower, and coupled to content/`anki`-wheel availability (the tools tests already skip without it, B016); a self-contained minimal collection is faster and hermetic. (b) A `qt/`-level test — rejected because the existing `qt/tests/test_speedrun.py` only exercises pure-Python UI helpers, not the engine RPC, so it doesn't satisfy "calls the Rust change from Python." (c) No Python test (rely on Rust unit tests only) — rejected: the deliverable explicitly wants the cross-language call proven.
- **Grounding:** the assignment's Wednesday checklist requires the Rust change to be shown working end-to-end including a test that calls it from Python; the pylib wrappers existed (`v3.py:draw_item_for_skill`, `collection.py:skill_mastery`) but nothing exercised them.
- **Gaps / risks:** the test asserts behavioral contracts, not FSRS-accurate mastery values (unreviewed cards → `mastered=0`), which is sufficient for the cross-language proof but not a measurement test (that's WP-7/WP-14 Rust coverage). It runs against the built backend in `out/pylib`; if that build lags `HEAD` the test still passes (the RPCs are older than the current build) but proof artifacts should use a fresh build — see B047.
- **Ref:** `pylib/tests/test_speedrun_engine.py`; `rslib/src/scheduler/queue/selection.rs` (WP-3), `rslib/src/stats/service.rs` + `storage/card/speedrun.rs` (WP-5); build-plan WP-3/WP-5; relates B016, B047.

### D-SR41 — Move the dev QtWebEngine debugger off port 8080 (9222) so it stops shadowing the self-hosted sync server

- **Status:** resolved
- **Decided:** 2026-07-02 by Opus (debugging the desktop "sync failed: 404 for url ()" against `just sync-server`)
- **Chose:** Change the QtWebEngine Chromium remote-debugging port from **8080 → 9222** (Chromium's own default) in `run`, `run.bat`, `.vscode.dist/launch.json`, and `tools/reload_webviews.py`. **Root cause:** WP-10's `anki-sync-server` (`just sync-server`) binds `0.0.0.0:8080`, but the dev `run` script also set `QTWEBENGINE_REMOTE_DEBUGGING=8080`, so a running desktop app opened `127.0.0.1:8080` for its Chromium DevTools endpoint. Because `127.0.0.1` is a more specific route than `0.0.0.0`, every sync request the app POSTed to `http://127.0.0.1:8080/sync/…` was answered by the **DevTools server** (which 404s all `/sync/…` paths and yields reqwest's empty-url `for url ()` message) instead of the sync server — which is why the sync-server terminal only ever logged `uri="/"`. Confirmed by `lsof` (python pid on `127.0.0.1:8080`, anki-sync on `*:8080`) and `/json/version` returning `"Browser":"Anki/"`. Moving the *debugger* (rather than the sync server) means the user's saved `customSyncUrl=http://127.0.0.1:8080/` on **both** desktop and phone keeps working unchanged.
- **Considered:** (a) moving the **sync server** to a new port instead (rejected — forces the owner to re-point desktop *and* AnkiDroid prefs, and 8080 is the well-known anki-sync-server default users expect); (b) leaving it and documenting a manual `QTWEBENGINE_REMOTE_DEBUGGING=…` override (rejected — silent, recurring footgun; the collision only appears once someone runs the sync server, i.e. exactly the WP-10/WP-15 owner path); (c) binding the sync server to `127.0.0.1` explicitly (rejected — doesn't resolve the same-port clash and breaks LAN phone access).
- **Grounding:** self-hosted sync (D-SR8, spec-sync-mobile §9) has to coexist with the standard `just run` dev loop on one machine; a dev-tool default silently intercepting product traffic is a defect regardless of which tool "owns" 8080.
- **Gaps / risks:** upstream Anki docs (`docs-site/addons/debugging.mdx`, `porting2.0.mdx`) still describe the 8080 debugger convention — left unedited (they instruct a *manual* opt-in that still works); anyone who hardcodes 8080 for DevTools must now use 9222. `just web-watch`/`reload_webviews.py` updated in lockstep so hot-reload still works.
- **Overrides:** none (dev tooling only; no PRD/spec touched).
- **Ref:** `run`, `run.bat`, `.vscode.dist/launch.json`, `tools/reload_webviews.py`; sync harness `tools/speedrun/sync/` (WP-10); relates D-SR8, WP-15.

### D-SR42 — WP-9 clean-machine demo: export the seed deck as a single importable package (additive tooling, no build-system edits)

- **Status:** resolved
- **Decided:** 2026-07-02 by Opus (WP-9 installer / clean-machine demo enablement)
- **Chose:** Reuse Anki's **existing Briefcase installer** (`qt/installer/`, `qt/tools/build_installer.py`, `./tools/build-installer` = `RELEASE=2 ./ninja installer`) as-is — it bundles the `anki`+`aqt` wheels built from `out/`, so the Rust engine change + the whole Speedrun UI ship automatically, and `SPEEDRUN_SHELL=True` (default in `qt/aqt/main.py`) means the packaged app **opens into Speedrun Home** with no env var. Because a clean install has an **empty profile**, add **new, self-contained tooling** to produce one importable exam-deck file: `tools/speedrun/deck/export_deck.py` (builds/uses a seed collection → `.apkg` [default, additive File→Import] or `.colpkg` [full-collection]), a `make_demo_deck.sh` wrapper, and a WP-9 runbook `tools/speedrun/installer/README.md`. All **additive** — no edits to `justfile`, `qt/installer/*`, `build/*`, or app/engine code (deliberately, to avoid colliding with other agents). Verified round-trip: import into an empty collection → 214 cards (38 skill + 163 item + 13 meta) + all four `LSAT Speedrun` decks. Covered by `tools/speedrun/deck/tests/test_export_deck.py` (5 tests, anki-skip-guarded).
- **Considered:** (a) a first-run **auto-import** of a bundled deck baked into app startup — rejected for now (touches startup code → collision risk; the demo is a one-time import); revisit if a zero-touch first-run is wanted. (b) Adding a **`just` recipe** for the installer/demo deck — deferred to avoid editing the shared `justfile` mid-flight (→ B048). (c) Exporting only a **`.colpkg`** — kept as an option but defaulted to `.apkg` because additive import doesn't wipe an existing profile and reads as "load your exam deck." (d) **Rebranding** the installer to "Speedrun" — deferred as cosmetic/optional (→ B049).
- **Grounding:** the Wednesday deliverable is "an installer that runs on a clean machine" + "loads your exam deck and runs a review"; the blocker was never the installer machinery (upstream, works) but (1) getting the build to `HEAD` (B047) and (2) an importable deck for the empty-profile demo — this closes (2) with repeatable, test-covered tooling.
- **Gaps / risks:** the exported deck is **synthetic** (B015) — the demo's "exam deck" is placeholders, not licensed real items; the installer + clean-machine **recording** still require the dev machine (not done here); macOS artifacts are **adhoc-signed** by default → Gatekeeper prompt on a clean Mac (documented). `export_deck.py` couples to `build_seed_deck.build_seed_deck()`'s signature (→ B048).
- **Ref:** `tools/speedrun/deck/export_deck.py`, `tools/speedrun/installer/{README.md, make_demo_deck.sh}`, `tools/speedrun/deck/tests/test_export_deck.py`; consumes `qt/tools/build_installer.py` + `qt/installer/`; build-plan WP-9; relates B015, B047, B048, B049.

### D-SR43 — Populate the dashboard demo by fabricating a study history directly into `revlog` + FSRS state (not by replaying the answer path)

- **Status:** resolved
- **Decided:** 2026-07-02 by Opus (owner wanted the 3-score dashboard to show real numbers on screen instead of the cold-start abstain/empty state)
- **Chose:** Add `tools/speedrun/deck/simulate_reviews.py` — additive demo/QA tooling that fabricates a plausible study history so the dashboard renders populated. It writes exactly what each score reads (verified against the engine source): **Performance/Readiness/coverage** ← rows `INSERT`ed into `revlog (cid, ease)` for the 13 `type::*` `LSAT Skill` cards (ease 3=correct / 1=wrong), ~20 attempts/type with per-type target accuracies (0.55–0.86) → ~250 attempts, 13/13 coverage → clears the ≥200-attempt **and** ≥50%-coverage gate so Readiness shows a **point + band** (verified: **165 [153–175]**, next-best `type::principle`); **Memory** ← FSRS `memory_state` (stability/difficulty) + `last_review_time` set on the 13 `LSAT Meta` cards via the pylib `Card` wrapper → engine-computed recall **~92% [90–94%]**. Deterministic (`--seed`). Applied **in place** to the local `User 1` profile (backed up to `collection.anki2.bak-<ts>` first; no app running → no lock); also exports a shareable `out/speedrun-demo-reviewed.colpkg`. Verified by reopening the on-disk collection fresh (post-close) — all three scores persist.
- **Considered:** (a) **Replaying the real `answer_card` path** for ~250 reviews — rejected: needs time-travel between reviews (FSRS makes a card non-due for minutes/days after each answer), which is far more code and fragile, for a *fabricated* demo anyway. Direct `revlog`/`memory_state` writes hit exactly the fields the dashboard queries. (b) **Setting card memory state via raw `data`-JSON SQL** — rejected: pylib already exposes `Card.memory_state` (`FsrsMemoryState`) + `last_review_time`, so `update_card` is the supported, schema-safe path. (c) **Shipping the demo as `.apkg`** — rejected: `.apkg` export does **not** carry `revlog`, so Performance/Readiness would be empty after import; the artifact must be a **`.colpkg`** (full collection). (d) **Only exporting a colpkg** (not touching `User 1`) — the colpkg is provided too, but in-place population lets the owner just launch the app and record.
- **Grounding:** the Wednesday proof wants "a memory model running, with an honest score: a range plus the give-up rule" *shown on screen*; the seed profile was synthetic + thin, so Readiness honestly abstained and Memory read 0 (unreviewed) — correct but undemonstrative. This produces a realistic populated state (and can equally show the abstain path with fewer `--attempts-per-type`).
- **Gaps / risks:** the data is **fabricated** (B015/B052) — it is a UI/measurement *demo*, not a real study session, and must not be presented as genuine performance; a proof recording should say so. `User 1` now contains synthetic reviews → restore `collection.anki2.bak-<ts>` (or rebuild the seed) for a clean cold-start demo (B052). Writes bypass undo and set `revlog.usn=0`; fine locally but would sync as-is. Couples to `build_seed_deck` (temp mode) and to the dashboard's field contract (guarded only by manual verification, not a test → B052).
- **Overrides:** none (additive demo tooling; no PRD/spec/engine touched).
- **Ref:** `tools/speedrun/deck/simulate_reviews.py`; reads-contract from `rslib/src/stats/{measurement.rs, performance.rs, service.rs}` (WP-7/WP-14); `pylib/anki/cards.py` (`FSRSMemoryState`, `last_review_time`); `out/speedrun-demo-reviewed.colpkg`; relates B015, B038, B052; builds on D-SR42.

### D-SR44 — AnkiDroid session layer (WP-22 on mobile): a standalone `SpeedrunSessionActivity`, not reviewer flags

- **Status:** resolved
- **Decided:** 2026-07-02 by Opus (owner: *"now where are my buttons to drill"* → *"do those three"* — wanted the desktop Home's mixed/timed/blind sessions on the phone)
- **Chose:** Port the desktop session layer (`qt/aqt/speedrun_session.py`, `SpeedrunSessionDialog`) to Android as a **new self-contained `SpeedrunSessionActivity`** (its own full-screen WebView), rather than bolting session behaviour onto AnkiDroid's reviewer. It **reuses the existing mobile drill primitives** — `SpeedrunReviewSession` for per-item state (prephrase→choices→reveal, commit, name-the-trap) and `SpeedrunHtml.build*` for the drill HTML — and adds only the session container in Kotlin (`SpeedrunSessionHtml`: sticky progress/timer header + scored result screen). Queue: `col.findCards('deck:"LSAT Speedrun" note:"LSAT Skill"').take(N)` (mixed 10, timed/blind 25). Each item answered via `col.sched.answerCard(card, rating)` (the per-card `getSchedulingStates` path — same B036-safe approach as desktop; FSRS/undo/sync intact). Mode differences: **mixed** = prephrase on; **timed** = choices-only + prominent amber clock; **blind** = choices-only, untimed. Result screen mirrors spec-ui §3.3 (donut, "where you slipped" with trap chips, all-questions strip with flag-to-revisit stars) and offers **blind review** of misses (restarts the same activity with the missed card IDs). Session accuracy is **display-only** (Performance/Memory/Readiness still come from the engine via the revlog/`SpeedrunDashboard`). Launched from the mobile Home's three "Or choose a session" cards (`speedrun://session/<mode>`, intercepted in `SpeedrunScoresActivity`). **No Rust/proto/schema change; stock AnkiDroid reviewer untouched.**
- **Considered:** (a) **Reviewer-mode flags** (drive mixed/timed/blind inside AnkiDroid's own reviewer via a mode enum) — rejected: the reviewer has no bounded queue, no result screen, no timer, and mixing session chrome into it risks regressing stock study; a standalone activity keeps the blast radius zero and matches the desktop 1:1. (b) **A SvelteKit session route** shared with desktop (the eventual `ts/routes/speedrun-session/`) — deferred: that route doesn't exist yet on either platform and would be a much larger lift; the Kotlin port reuses code already on the phone. (c) **Bounded count enforcement** beyond `take(N)` — the deck currently has 21 skill cards, so timed/blind sessions run min(N, 21); fine for the synthetic pool.
- **Grounding:** desktop Home (D-SR33/D-SR35) offers targeted/mixed/timed/blind; the mobile Home (WP-15) had only scores + a single reviewer "Start drill", so the phone couldn't run a bounded, scored, timed set. This brings the phone to session parity for mixed/timed/blind (targeted-by-skill is not yet a mobile button — see gaps).
- **Gaps / risks:** **targeted** (per-focus-skill) session not ported — mobile only has mixed/timed/blind (the reviewer "Start drill" is the closest to targeted); a per-skill mobile filter is future work. The result screen's flag-to-revisit stars persist only within the session (not written back). Verified on the Pixel emulator end-to-end (launch → header/timer → commit/reveal/traps → next records answer → result donut + slips + stars → blind review restart → back to Home) but **not on the owner's device**, and not yet covered by an instrumented test. Synthetic item pool (B015).
- **Overrides:** none (additive; mirrors D-SR35 session modes on mobile; no PRD/spec/engine touched).
- **Ref:** `~/dev/droid/Anki-Android/AnkiDroid/.../speedrun/{SpeedrunSessionActivity,SpeedrunSessionHtml}.kt` (new), `SpeedrunReviewSession.kt` (+`currentFields`/`skipToChoices`), `SpeedrunDashboardHtml.kt` (launcher cards), `SpeedrunScoresActivity.kt` (URL intercept), `AndroidManifest.xml`; ports `qt/aqt/speedrun_session.py`; relates D-SR33/D-SR35, WP-15/WP-22, B015.

---

<sub>Created with the `iris-plan` skill by Iris Cai · maintained with `iris-log`.</sub>
