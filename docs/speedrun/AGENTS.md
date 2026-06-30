# Speedrun — agent orientation

> **Speedrun** is an LSAT study app **forked from Anki**: one shared Rust engine, a
> desktop app + an Android (AnkiDroid) companion that sync, and three *separately
> reported* scores — Memory, Performance, Readiness — each with an honest range and
> a rule for when it refuses to guess. It trains *reasoning* by scheduling the
> **skill/trap**, not the literal flashcard.
>
> **Current state (2026-06-30):** **design complete + build-scoped; Wave-1 offline tooling landed.**
> The plan (PRD + 4 specs + decision log) is verified to integrate with **zero schema
> change** and split into a phased build plan ([`build-plan.md`](./build-plan.md), WP-0…WP-19).
> **Built so far** (all additive, tests green): WP-1 data contract (`docs/speedrun/data/` +
> `tools/speedrun/deck/`), WP-12 AI card-check (`tools/speedrun/cardcheck/`), WP-16 eval
> harnesses (`tools/speedrun/eval/`). **Engine/app code is NOT started yet** — gated on
> WP-0 (fork + build), which is blocked here (see [B008](./backlog.md)).
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
| [`decisions.md`](./decisions.md) | Decision log D-SR1…26 (append-only; **next free ID: D-SR27**) |
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

- **IDs:** decisions are `D-SR<N>`, stable, **append-only — supersede, never rewrite** (next free: **D-SR27**). Backlog is `B<NNN>`, monotonic, never reused (next free: **B021**).
- **Frozen docs:** the PRD + specs are one-and-done. Don't edit them to track drift — record changes as a **new decision** + an **Overrides** line here.
- **Engine invariants** (don't break these — they're the project's whole thesis + grade):
  - **Zero schema change.** Ride existing tables + `Card.custom_data`/tags; no schema-version bump (keeps sync/downgrade/`dbcheck` safe and upstream rebases cheap). [D-SR4]
  - **Reuse FSRS / `answer_card` / undo / sync** — never fork them. The interleaving order is a new additive `ReviewCardOrder` enum variant. [D-SR3, D-SR6]
  - **AI never owns correctness** — keyed lookup only; every AI output is generate-then-verify, beats a baseline, and the app **still scores with AI off**; **no AI before Friday**. [D-SR14]
  - **Never show a Readiness number without its evidence**, and **abstain** below ≥200 attempts AND ≥50% coverage (an automatic fail otherwise). [D-SR10]
- **Build/test:** use `just` / `./ninja` (see repo-root `CLAUDE.md`); proto changes need a full build to regenerate bindings.

## Current focus

**Wave-1 offline tooling done** (WP-1/12/16). **Blocked on WP-0** (fork + desktop +
AnkiDroid build) — must run on a **space-free path** with Rust installed ([B008](./backlog.md)).
Once WP-0 is green: land **WP-2** (protobuf contract) → fan out engine lanes
**WP-3/4/5** (worktrees) + **WP-6/WP-7**. Deadlines: **Wed** core (no AI) · **Fri**
AI + sync · **Sun** prove + ship.

**Resolved this round:** D-SR18 (formula, math-verified) · B009 (native `::` tags → D-SR24,
code fixed) · B010 (distractor traps schedulable → D-SR23). **Still open:** B013
(`variant_of` field, for the engine/data WP) · B012 (real-LLM wiring — Friday).

---

<sub>Maintained with the `iris-log` skill by Iris Cai.</sub>
