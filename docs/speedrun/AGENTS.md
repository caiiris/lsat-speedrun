# Speedrun — agent orientation

> **Speedrun** is an LSAT study app **forked from Anki**: one shared Rust engine, a
> desktop app + an Android (AnkiDroid) companion that sync, and three *separately
> reported* scores — Memory, Performance, Readiness — each with an honest range and
> a rule for when it refuses to guess. It trains *reasoning* by scheduling the
> **skill/trap**, not the literal flashcard.
>
> **Current state (2026-06-30):** **desktop build green; WP-2 contract + WP-3/4/5 engine core merged to `main`.**
> The plan (PRD + 4 specs + decision log) is verified to integrate with **zero schema
> change** and split into a phased build plan ([`build-plan.md`](./build-plan.md), WP-0…WP-19).
> **Built so far** (all additive, tests green): Wave-1 offline tooling — WP-1 data contract
> (`docs/speedrun/data/` + `tools/speedrun/deck/`), WP-11 AI tagging (`tools/speedrun/tagging/`),
> WP-12 AI card-check (`tools/speedrun/cardcheck/`), WP-16 eval harnesses (`tools/speedrun/eval/`).
> **The build env is now unblocked** ([B008](./backlog.md)
> resolved): space-free path, Rust 1.92, `out/` build == HEAD, `anki` v26.05 imports, and the
> whole offline suite is green (198 passed). **WP-0a desktop build + WP-2 proto contract + the
> WP-3/4/5 engine core have all landed on `main`** (merged; combined `just build` +
> `just test-rust` + `just test-py` green): **WP-3** fresh-item draw (`draw_item_for_skill` +
> local served-item sidecar), **WP-4** interleaving (`InterleavedSkills` review order + deck-
> options toggle), **WP-5** `skill_mastery` aggregate — all additive, zero schema change, FSRS
> and the answer path reused. **Next: WP-6 (desktop reviewer) + WP-7 (Memory + give-up gate).**
> WP-0b (AnkiDroid build) still needs the dev's machine ([B001](./backlog.md)).
>
> This is the **Speedrun project's** front door. It is *not* the repo-root
> `AGENTS.md` (that's upstream Anki's build doc → `CLAUDE.md`).

## Source of truth (read in this order)

1. **This file** — current project state + the override ledger.
2. **Decision log** [`decisions.md`](./decisions.md) — latest non-superseded entry wins.
3. **Iterations log** — *not created yet* (appears at first build/test-driven change).
4. **PRD / specs** — *original intent, written before implementation* ([`prd-speedrun.md`](./prd-speedrun.md), `spec-*.md`). **Frozen.** Superseded wherever a later decision or an "Overrides" entry below says so. **When a spec and a decision conflict, the decision wins — do not defer to the PRD.**

## Overrides since the plan

_Newest first._
- **spec-measurement §4.3** readiness formula → corrected to **drop the double `w_S`**: `expected_raw = N_lr · Σ w_S·Perf(S)` (D-SR18, **resolved** — math verified).
- **spec-measurement §4.3** Readiness output in v1 is an explicit **"LR-only estimate"** with a wider band (D-SR19, refines D-SR12).

## Stack

- **Rust** core engine — `rslib/` (the brownfield change lives here; ships to desktop + phone)
- **Python / PyQt6** desktop GUI — `qt/aqt/`
- **TypeScript / Svelte** web UI (dashboard, reviewer) — `ts/`
- **Android** companion — an **AnkiDroid** fork (shares the Rust backend)
- **Sync** — self-hosted **`anki-sync-server`** (already in `rslib/sync/`)
- License: **AGPL-3.0-or-later**, credit to Anki.

## Where things are

| Path | What |
|---|---|
| [`prd-speedrun.md`](./prd-speedrun.md) | User-facing contract: the 3 scores, honesty/give-up rules, ACs, edge-cases |
| [`decisions.md`](./decisions.md) | Decision log D-SR1…28 (append-only; **next free ID: D-SR29**) |
| [`spec-engine.md`](./spec-engine.md) | The Rust change: skill-as-card interleaving + fresh-item draw, mastery query, data model |
| [`spec-measurement.md`](./spec-measurement.md) | Memory/Performance/Readiness models, the give-up gate, evals |
| [`spec-sync-mobile.md`](./spec-sync-mobile.md) | Self-hosted sync, conflict rule, AnkiDroid companion |
| [`spec-ai.md`](./spec-ai.md) | AI honesty contract, anchor tagging eval, card-check, injection guard |
| [`build-plan.md`](./build-plan.md) | Dispatcher output: work packages WP-0…WP-19, phases, deps, parallel lanes |
| [`backlog.md`](./backlog.md) | Known gaps / risks / open issues (B001…) |
| [`../lsat-speedrun-brainlift.md`](../lsat-speedrun-brainlift.md) | Research grounding (pedagogy, psychometrics, AI) |
| [`../../extra/architecture/ANKI_ARCHITECTURE.md`](../../extra/architecture/ANKI_ARCHITECTURE.md) | How the upstream Anki engine works (git-ignored) |

Upstream code the change lands in: `rslib/src/scheduler/`, `rslib/src/stats/`, `proto/anki/`, `qt/aqt/reviewer.py`, `ts/`.

## Conventions that bite

- **IDs:** decisions are `D-SR<N>`, stable, **append-only — supersede, never rewrite** (next free: **D-SR29**). Backlog is `B<NNN>`, monotonic, never reused (next free: **B027**).
- **Frozen docs:** the PRD + specs are one-and-done. Don't edit them to track drift — record changes as a **new decision** + an **Overrides** line here.
- **Engine invariants** (don't break these — they're the project's whole thesis + grade):
  - **Zero schema change.** Ride existing tables + `Card.custom_data`/tags; no schema-version bump (keeps sync/downgrade/`dbcheck` safe and upstream rebases cheap). [D-SR4]
  - **Reuse FSRS / `answer_card` / undo / sync** — never fork them. The interleaving order is a new additive `ReviewCardOrder` enum variant. [D-SR3, D-SR6]
  - **AI never owns correctness** — keyed lookup only; every AI output is generate-then-verify, beats a baseline, and the app **still scores with AI off**; **no AI before Friday**. [D-SR14]
  - **Never show a Readiness number without its evidence**, and **abstain** below ≥200 attempts AND ≥50% coverage (an automatic fail otherwise). [D-SR10]
- **Build/test:** use `just` / `./ninja` (see repo-root `CLAUDE.md`); proto changes need a full build to regenerate bindings.

## Current focus

**Engine core (WP-3/4/5) merged to `main`** on top of WP-0a desktop + WP-2 contract; combined
`just build` + `just test-rust` + `just test-py` are green (14 Rust unit tests across the three
lanes; the proto stubs are now real impls). **Next: WP-6** (desktop reviewer — commit-then-reveal
+ render the drawn item via `RenderUncommittedCard`, `qt/aqt/reviewer.py` + `ts/reviewer/`) and
**WP-7** (Memory score + the pure-function `readiness_gate`), then **WP-14** (Perf/Readiness +
dashboard, consumes `skill_mastery`). **WP-0b (AnkiDroid build)** still needs the dev's machine
([B001](./backlog.md), #1 schedule risk). Deadlines: **Wed** core (no AI) · **Fri** AI + sync ·
**Sun** prove + ship. *(Note: `main` is ahead of `origin/main` by the merge commits — push when ready.)*

**Resolved this round:** **WP-3/4/5 landed** (fresh-item draw, interleaving, mastery — additive,
zero schema change) → promoted **D-SR27** (skill-identity = first `type::/skill::/trap::` tag) +
**D-SR28** (mastery threshold 0.90). **New backlog:** B024 (difficulty-weighting deferred → WP-11),
B025 (sidecar in-memory only), B026 (full `just check` still red on pre-existing Wave-1 lint/fmt).
**Earlier:** B008 (env unblocked) · WP-2 (proto contract) · B016/B021 (deck fixes) · D-SR18 ·
B009 (→D-SR24) · B010 (→D-SR23). **Still open:** B013 (`variant_of`) · B012 (real-LLM — Friday) ·
B001 (mobile build) · B023/B026 (fmt/lint debt).

---

<sub>Maintained with the `iris-log` skill by Iris Cai.</sub>
