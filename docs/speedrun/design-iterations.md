# Speedrun — design iterations log

> Test-/feedback-driven changes to the product surface. Append-only; newest last
> within each entry. Decisions that come out of an iteration graduate to
> [`decisions.md`](./decisions.md); this log captures the *why it changed* trail.
> IDs are `DI-SR<N>`, monotonic (**next free: DI-SR2**).

---

### DI-SR1 — Stats page reskin, converging on the drill's visual language

- **Surface:** desktop Statistics page (`ts/routes/graphs/`), shown via the
  Speedrun Home "Stats" action. Gated on `body.speedrun-stats` (set only by the
  Speedrun shell, `?sr=1`) so stock Anki is untouched.
- **Goal:** the Stats page should read as the *same app* as the practice-questions
  (drill) UI — same palette, type, cards — not as raw Anki charts.

**Iteration trail (owner feedback each round):**

1. **CSS-only reskin (WP-27).** Overrode Anki's CSS tokens (`--canvas`,
   `--border`, `--fg`, radius) + styled `TitledContainer`/`RangeBox` under
   `body.speedrun-stats`. → *"see how nothing changed"*: token overrides didn't
   penetrate Svelte-scoped components.
2. **Scoped component styling.** Moved card/heading styles directly into
   `TitledContainer.svelte` via `:global(body.speedrun-stats) …`. → *"mildly
   better? but the font is bad… make it similar to the practice questions UI."*
3. **Typography pass.** Card titles → Georgia serif; body → grotesk. → *"these
   two clearly have a different style."*
4. **Chart recolor + heading regrammar (this round).** Owner granted full
   permission to change Anki fonts/colors ("just don't randomly delete their
   stuff"). Root causes of the residual mismatch were (a) the **hardcoded D3
   chart colors** (bright-blue pie, multicolor legend) that CSS can't reach, and
   (b) **serif card titles**, a treatment that never appears in the drill.
   - **Card Counts** pie + legend → `speedrunBarColours` (indigo/amber/clay/
     green/muted), `ts/routes/graphs/card-counts.ts`.
   - **Reviews** bars/series → indigo·green·amber·clay light→saturated ramps,
     `ts/routes/graphs/reviews.ts` (`binColor`).
   - Card titles: Georgia serif → the drill's **mono uppercase eyebrow**
     (matching `type::flaw` / `PREPHRASE`), `TitledContainer.svelte` +
     `graphs-base.scss` (kept in sync).
   - `--state-new/learn/review` tokens → drill palette (TodayStats numbers).
5. **Heading font correction.** → *"the font is horrible"*: uppercase bare
   monospace reads clunky for section titles. Root fix: match the drill's
   **prominent grotesk heading exactly** — the indigo prompt "In one line, what
   must the right answer do?" (`speedrun.py`): stack `-apple-system,
   BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`, weight 700, ~1.05rem,
   indigo, sentence case, normal tracking. Also aligned the **body font stack**
   to the same (dropped "Inter", which was rendering differently from the drill).
   (Earlier "grotesk bad" round used an Inter stack + tight tracking + small size
   — the family wasn't the problem; the treatment was.)

- **Palette source of truth:** `spec-ui.md §2` / `qt/aqt/speedrun.py` constants
  (`_C_INDIGO #3E3A8C`, `_C_GREEN #2E7D5B`, `_C_CLAY #B4472E`, `_C_AMBER #C99A2E`,
  paper `#F5F7FA`, ink `#1B2430`).
- **Remaining (B042):** calendar heatmap + the less-visible graphs (intervals,
  ease, difficulty, retrievability, stability, hourly, buttons, added, future-due)
  still use Anki's default d3 colors — mostly empty on the demo deck; retheme the
  same way (class-gated) when polishing.
- **Constraint honored:** additive + reversible; no Anki stats content/graphs
  removed; stock Anki unaffected (no `speedrun-stats` class → default colors).
