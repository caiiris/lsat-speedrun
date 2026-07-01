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

<sub>Created with the `iris-plan` skill by Iris Cai · maintained with `iris-log`.</sub>
