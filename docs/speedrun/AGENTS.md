# Speedrun — agent orientation

> **Speedrun** is an LSAT study app **forked from Anki**: one shared Rust engine, a
> desktop app + an Android (AnkiDroid) companion that sync, and three *separately
> reported* scores — Memory, Performance, Readiness — each with an honest range and
> a rule for when it refuses to guess. It trains *reasoning* by scheduling the
> **skill/trap**, not the literal flashcard.
>
> **Current state (2026-06-30):** **desktop review loop runnable; WP-2 + WP-3/4/5 engine + WP-6 reviewer + WP-7 measurement merged to `main`.**
> The plan (PRD + 4 specs + decision log) is verified to integrate with **zero schema
> change** and split into a phased build plan ([`build-plan.md`](./build-plan.md), WP-0…WP-19).
> **Built so far** (all additive, tests green): Wave-1 offline tooling — WP-1 data contract
> (`docs/speedrun/data/` + `tools/speedrun/deck/`), WP-11 AI tagging (`tools/speedrun/tagging/`),
> WP-12 AI card-check (`tools/speedrun/cardcheck/`), WP-16 eval harnesses (`tools/speedrun/eval/`).
> **The build env is now unblocked** ([B008](./backlog.md)
> resolved): space-free path, Rust 1.92, `out/` build == HEAD, `anki` v26.05 imports, and the
> whole offline suite is green (198 passed). **WP-0a desktop build + WP-2 proto contract + the
> WP-3/4/5 engine + WP-6 reviewer + WP-7 measurement + **WP-14 dashboard** have all landed on
> `main`** (merged; combined `just build` + `just test-rust` + `just test-py` + `just test-ts` green):
> **WP-3** fresh-item draw + sidecar, **WP-4** interleaving + deck-options toggle, **WP-5**
> `skill_mastery`, **WP-6** desktop reviewer (commit-then-reveal Level 1; Level-2 wired, needs
> live-GUI verify), **WP-7** `readiness_gate` + Memory, **WP-14** Performance (Wilson) + Readiness
> (abstain-gated) + the **3-score dashboard** (`ts/routes/speedrun-dashboard/`) via the
> `SpeedrunDashboard` RPC — all additive, zero schema change, FSRS + answer path reused. **The
> desktop app now runs the full loop and shows the scored dashboard** (a demo seed deck is in the
> local profile). **Next: WP-0b (AnkiDroid build — dev's machine, [B001](./backlog.md)), WP-10
> (sync), the Friday AI wiring (WP-13), and the proof lane (WP-16/17/18).**
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
- **PRD + spec-engine §6/§8** stock-Anki reviewer/deck framing → the product is reframed as an **LSAT study-plan + practice-session app** (home = dashboard/study-plan; drills/timed-sections/blind-review, not a due queue; no deck/card/ease chrome). Presentation layer only — engine unchanged. See [`spec-ui.md`](./spec-ui.md) (D-SR33). Drill interaction adds prephrase + name-the-trap, MC commit stays the deterministic graded signal (D-SR34).
- **spec-engine §8** drawn-item render → v1 uses **Python field injection (`web.eval`)** on desktop instead of the `RenderUncommittedCard` RPC named in §8; render/answer stay decoupled (D-SR30; revisit for AnkiDroid → B029).
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
| [`decisions.md`](./decisions.md) | Decision log D-SR1…37 (append-only; **next free ID: D-SR38**) |
| [`spec-engine.md`](./spec-engine.md) | The Rust change: skill-as-card interleaving + fresh-item draw, mastery query, data model |
| [`spec-measurement.md`](./spec-measurement.md) | Memory/Performance/Readiness models, the give-up gate, evals |
| [`spec-ui.md`](./spec-ui.md) | **Presentation/UX (living):** study-plan surface + the LR drill interaction (reframe away from Anki decks/flashcards) — D-SR33/34 |
| [`spec-sync-mobile.md`](./spec-sync-mobile.md) | Self-hosted sync, conflict rule, AnkiDroid companion |
| [`spec-ai.md`](./spec-ai.md) | AI honesty contract, anchor tagging eval, card-check, injection guard |
| [`build-plan.md`](./build-plan.md) | Dispatcher output: work packages WP-0…WP-19, phases, deps, parallel lanes |
| [`backlog.md`](./backlog.md) | Known gaps / risks / open issues (B001…) |
| [`../lsat-speedrun-brainlift.md`](../lsat-speedrun-brainlift.md) | Research grounding (pedagogy, psychometrics, AI) |
| [`../../extra/architecture/ANKI_ARCHITECTURE.md`](../../extra/architecture/ANKI_ARCHITECTURE.md) | How the upstream Anki engine works (git-ignored) |

Upstream code the change lands in: `rslib/src/scheduler/`, `rslib/src/stats/`, `proto/anki/`, `qt/aqt/reviewer.py`, `ts/`.

## Conventions that bite

- **IDs:** decisions are `D-SR<N>`, stable, **append-only — supersede, never rewrite** (next free: **D-SR38**). Backlog is `B<NNN>`, monotonic, never reused (next free: **B040**).
- **Frozen docs:** the PRD + specs are one-and-done. Don't edit them to track drift — record changes as a **new decision** + an **Overrides** line here.
- **Engine invariants** (don't break these — they're the project's whole thesis + grade):
  - **Zero schema change.** Ride existing tables + `Card.custom_data`/tags; no schema-version bump (keeps sync/downgrade/`dbcheck` safe and upstream rebases cheap). [D-SR4]
  - **Reuse FSRS / `answer_card` / undo / sync** — never fork them. The interleaving order is a new additive `ReviewCardOrder` enum variant. [D-SR3, D-SR6]
  - **AI never owns correctness** — keyed lookup only; every AI output is generate-then-verify, beats a baseline, and the app **still scores with AI off**; **no AI before Friday**. [D-SR14]
  - **Never show a Readiness number without its evidence**, and **abstain** below ≥200 attempts AND ≥50% coverage (an automatic fail otherwise). [D-SR10]
- **Build/test:** use `just` / `./ninja` (see repo-root `CLAUDE.md`); proto changes need a full build to regenerate bindings.

## Current focus

**Wednesday core + the 3-score dashboard are built** (desktop, no AI): WP-0a desktop + WP-2 contract
+ WP-3/4/5 engine + **WP-6 reviewer** + **WP-7 gate/Memory** + **WP-14 Performance/Readiness +
dashboard** are all merged to `main`; combined `just build` + `just test-rust` + `just test-py` +
`just test-ts` are green. **The desktop app runs the full interleaved commit-then-reveal loop and
shows the scored dashboard** (Memory / Performance / Readiness-or-Abstain) — a demo seed deck is in
the local profile (`User 1`; synthetic + thin coverage, so Readiness will honestly abstain).
**Active direction — UX reframe (D-SR33/D-SR34, [`spec-ui.md`](./spec-ui.md)):** the Anki
deck/flashcard surface reads wrong for a reasoning exam, so we are reframing the presentation into
an **LSAT study-plan + practice-session app** (home = dashboard/study-plan; drills / timed sections /
blind review; drill interaction adds **prephrase** + **name-the-trap**, MC commit stays the
deterministic graded signal). **Presentation layer only — engine untouched.** This **reshapes WP-6
(reviewer → drill/session surface) and WP-14 (dashboard → home)** and adds a small `ts/` session
layer; all additive. Design mockups in `docs/speedrun/assets/`. **Landed (all merged to `main`, build +
`just test-ts`/`test-py` green):** **WP-20** Home, **WP-21** drill (prephrase + name-the-trap), **WP-22**
session layer (drills/mixed/timed/blind + result), **WP-24** full-window shell (`SPEEDRUN_SHELL` flag:
Home on launch + Anki chrome hidden), **WP-25** Home-as-hub (Sync/Browse/Add/Stats/More surfaced in the
Home → the deck browser is never a user surface, D-SR37). The Home renders + matches the mockup (its earlier "blank/awful" was
three GUI-only bugs B034/B035/B037, all fixed). **Desktop UX reframe is functionally complete — pending
owner GUI-verify.** Open polish: B033 (reasoning-map/marked-conclusion field), B036 (session filter/state),
B038 (Home Memory "no meta cards"), B039 (Sync/Browse button in shell).

**Also next:** **WP-0b (AnkiDroid build)** — #1 risk, dev's machine ([B001](./backlog.md)) —
**WP-10 (sync)**, AI wiring (WP-13; AI available **Wed night** per current constraint), proof lane
(WP-16/17/18). **Verify on device:** WP-6 Level-2 live-GUI pass. Deadlines: **Wed** core · **Fri**
AI + sync · **Sun** prove + ship. *(`main` is ahead of `origin/main` by local merges — push when ready.)*

**Resolved this round:** **WP-14 landed** → promoted **D-SR31** (revlog ease→outcome mapping,
resolves the ease half of B014) + **D-SR32** (Readiness band/confidence/coverage method + combined
`SpeedrunDashboard` RPC); **B031 fixed** (Memory now exposed to Python). **New backlog:** B032
(dashboard UI minimal — deck-picker/i18n/polish deferred). **Earlier:** WP-6/7 (→D-SR29/30,
B027–B030), WP-3/4/5 (→D-SR27/28), B008/WP-2. **Still open:** B013 (`variant_of`) · B012 (real-LLM —
Friday) · B001 (mobile) · B023/B026 (fmt/lint debt) · B014 (`split.py`) · WP-6 GUI verification.

---

<sub>Maintained with the `iris-log` skill by Iris Cai.</sub>
