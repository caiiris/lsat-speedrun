# Spec: UI / Presentation — study-plan surface & the LR drill interaction

> How **Speedrun** presents itself to the learner. It reframes the product away from
> Anki's deck/flashcard surface into an **LSAT study-plan + practice-session app**, and
> defines the **Logical Reasoning drill interaction** (commit-then-reveal enriched with
> prephrase + name-the-trap). Grounded in learning science; every graded signal still
> flows through the existing engine.
>
> **Authority:** this is a **living** design spec (created post-plan, 2026-06-30), not a
> frozen one — update it in place as the UI evolves. It is the current truth for the
> presentation layer and **overrides** the stock-Anki reviewer/deck framing implied by the
> PRD and spec-engine §6/§8. Source decisions: **D-SR33** (product reframe), **D-SR34**
> (drill interaction). Companions: [`spec-engine.md`](./spec-engine.md) (the engine it rides on),
> [`spec-measurement.md`](./spec-measurement.md) (the three scores it shows),
> [`decisions.md`](./decisions.md), [`AGENTS.md`](./AGENTS.md).

## 0. The one-line thesis

> Studying for the LSAT is **diagnose → drill your weakest reasoning → do timed sections →
> review your errors**, driven by three honest scores — **not** flipping a deck of cards.
> The Anki engine underneath is unchanged; only the surface changes.

**Hard boundary (D-SR33):** presentation/session layer only. FSRS skill scheduling,
`draw_item_for_skill`, the `AnswerCard` path, revlog→Performance, the give-up gate, sync,
and mobile are all **unchanged**. A "session" is just a framed batch of due skill cards;
the drawn item + commit-then-reveal + rating are the existing mechanic.

## 1. Learning-science principles → interaction

| Principle (evidence) | What it means here | UI behavior |
|---|---|---|
| **Generation effect / prephrasing** (produce before you recognize) | Predicting the answer beats picking from 5 | **Prephrase** step before choices (self-scored v1) |
| **Error-driven learning + misconception diagnosis** | The wrong answer is the lesson | **Name-the-trap** on a miss (deterministic, from item tags) |
| **Elaborated, immediate feedback** | Feedback works best right after commit and when it explains | Per-choice **why-wrong** + trap at the moment of error |
| **Desirable difficulties** (Bjork) | Productive difficulty > fluency illusion | Commit-before-reveal, **interleaved** sets, **blind review** |
| **Metacognitive calibration** | Strong test-takers know when they're guessing | Optional **confidence** tap → timed-vs-untimed / confidence gap |
| **Reduce extraneous load + worked-example fading** | One clean argument; scaffolding that fades | Single-argument canvas; prephrase prompts lighten as Performance rises |
| **Self-regulated learning / deliberate practice** | A goal + a single next action; practice at the edge of competence | Home = study-plan with **one** recommended next drill (weakest high-frequency skill) |

**Scoring stays deterministic + AI-free (D-SR34):** the multiple-choice **commit** is the only
graded signal (→ FSRS rating + Performance, spec-engine §5.1). Prephrase is self-scored;
name-the-trap is checked against the item's `TrapChoiceA–E` tags. No AI is required for any
score. Optional AI *feedback* on free-text prephrase is deferred until AI is available
(Wednesday night, current constraint) and stays under the honesty contract (AI never owns
correctness — D-SR14/D1).

## 2. Design language

- **Metaphor:** a calm **reasoning workspace** — you *mark up an argument*, you don't flip a card.
- **Palette:** cool pale paper `#F5F7FA` · slate ink `#1B2430` · **indigo** structural accent
  `#3E3A8C` · success green `#2E7D5B` · error clay `#B4472E` · **signature amber** `#C99A2E`
  (reserved *only* for the trap-diagnosis element).
- **Type:** a readable **transitional serif** for the argument/stimulus (it's prose, treat it
  as prose) · a precise **grotesk sans** for UI/labels · **monospace** for taxonomy tags
  (`type::assumption`) — they are literally code-like tags, so show them as such.
- **Signature element:** the **"Name the trap" chip** that appears on a wrong answer — the one
  bold, memorable interaction; everything else stays quiet and disciplined.
- **Quality floor:** responsive to mobile (AnkiDroid parity), visible keyboard focus,
  reduced-motion respected, no Anki chrome anywhere (no deck list, due counts, "Show Answer",
  4 colored ease buttons).

## 3. Screens

### 3.1 Home — the study plan (replaces the deck browser)
The anti-deck-list. Shows **where you stand** (the three scores, honestly gated) and the
**single next action**. Mockup: [`./assets/home-study-plan-mockup.png`](./assets/home-study-plan-mockup.png).

```
┌───────────────────────────────────────────────────────────┐
│  Speedrun            [ Memory ] [ Performance ] [ Readiness ]│  ← 3 honest scores
│                        84%        61%            — (abstains) │    (Readiness shows the
│                                                              │     abstain panel until
│  ▸ Today's focus:  Assumption family  (your weakest, 14% of  │     ≥200 att & ≥50% cov)
│                    the exam)                                  │
│     [ Start targeted drill ]   ~10 items · ~12 min           │
│                                                              │
│  Or choose a session:                                        │
│   [ Mixed set ]  [ Timed section ]  [ Blind review ]         │
│                                                              │
│  Skill map (Performance, with bands)                         │
│   Flaw        ▓▓▓▓▓▓▓░░  72%                                 │
│   Assumption  ▓▓▓░░░░░░  34%   ← recommended                 │
│   Inference   ▓▓▓▓▓░░░░  56%   … (per type, from WP-14)      │
└───────────────────────────────────────────────────────────┘
```
- Readiness renders the **abstain panel** ("Not enough evidence yet — 0/200 attempts · LR
  coverage 100%") until the gate opens; never a number while abstaining (D-SR10).
- "Today's focus" = the dashboard's **next-best-thing** (D-SR9); one action, to cut choice overload.

### 3.2 Drill — the LR item (the heart; replaces the reviewer)
States, in order. See the mockup: [`./assets/lr-drill-mockup.png`](./assets/lr-drill-mockup.png).

1. **Prephrase** (mode-driven; untimed drills, faded as mastery rises) — mockup:
   [`./assets/lr-prephrase-mockup.png`](./assets/lr-prephrase-mockup.png)
   > *"In one line, what must the right answer do?"* — text field + "Skip"; the 5 choices stay
   > **hidden until you predict** (generation before recognition). Self-scored on reveal.
2. **Choices / commit** — the argument (conclusion underlined) + stem + 5 clean rows; select →
   **Lock in**. No colors before commit.
3. **Reveal** — correct row → green; your pick if wrong → clay; each row expands to why-wrong;
   trap chips appear. **Prephrase self-check** ("did your prediction match?").
4. **Name-the-trap** (on a wrong commit) — the signature amber chip row on your pick; pick the
   trap → checked against `TrapChoiceX`.
5. Right rail: **Reasoning map** (Premise / Conclusion / The gap), mono taxonomy tags,
   confidence, and a single **Next question** (never 4 ease buttons).

**Timed-section variant:** fast MC only — no prephrase, no chips, a running clock; diagnosis
moves to the end-of-set review.

### 3.3 Set result + blind review
Mockup: [`./assets/lr-set-result-mockup.png`](./assets/lr-set-result-mockup.png).
End of a session: `7/10`, a **"Where you slipped"** list naming the **trap you fell for** on each
miss (from `TrapChoiceX`), an all-items strip with **flag-to-revisit** stars, and the emphasized
next step **"Blind review your misses"** — which re-runs missed items **untimed**, forcing a fresh
commit *before* the key is shown. Session accuracy is a per-session display; Performance still
derives from the revlog (spec-measurement §4.2), not from this screen.

### 3.4 RC passage workspace (phase-2, designed now so we don't box ourselves in)
For RC the drawn "item" is a **passage + question set**: reading pane (highlight/annotate) beside
questions with the same commit-then-reveal. Same engine draw; a workspace, not a card.

## 4. How it maps to the engine (nothing new in Rust)

- **Session start** → build the due-skill queue (interleaved order for Mixed, D-SR6) and take a
  batch; **each question** → `draw_item_for_skill(skill_card_id)` (WP-3) renders a fresh item.
- **Commit** → correctness → rating (wrong→Again(1), right→Good(3), spec §5.1) → `AnswerCard`
  (unchanged path; FSRS/undo/sync intact).
- **Scores** → `SpeedrunDashboard` RPC (WP-14): Memory, per-skill Performance (Wilson), Readiness
  or abstain, coverage — rendered on Home and the result screen.
- **Prephrase / confidence** → session-local for v1 (calibration); persist via `Card.custom_data`
  only if needed (no schema change). **Name-the-trap** → read the item's trap tags.

## 5. What this reshapes (all additive)

- **WP-6** (reviewer) → the **drill/session surface** (`qt/aqt` + `ts/reviewer/`): prephrase,
  name-the-trap chips, reasoning map, de-Anki'd chrome.
- **WP-14** (dashboard) → the **Home study-plan** (session launchers + skill map on top of the
  existing dashboard RPC).
- **New:** a small **session layer** in `ts/` (session state, timer, set-result + blind-review
  screens). No Rust/proto/schema changes.

## 6. Open items

- **Confidence/prephrase storage** — session-local now; `custom_data` if it must persist (→ decide during build).
- **Highlight-the-conclusion** input needs a new **marked-conclusion item field** (additive data, not schema) — deferred (D-SR34).
- **AI prephrase feedback** — enable after AI is available (Wed night), honesty-contract-gated (D-SR14).
- **Mobile parity** — the same surface must port to AnkiDroid (relates B029/D-SR30 render path).

---

<sub>Created with the `iris-log` skill by Iris Cai · 2026-06-30 (D-SR33/D-SR34).</sub>
