# WP-27 log — Restyle Stats page to Speedrun design language

_iris-log inbox · WP-27 · 2026-07-01_

---

## L1 — Theming approach: CSS variable override, scoped to `body.speedrun-stats`

**Decision:** Use Anki's existing CSS custom-property token system as the override hook.
The graphs page already uses `--canvas`, `--canvas-elevated`, `--border`, `--border-subtle`,
`--fg` throughout its component tree. By overriding those variables on `body.speedrun-stats`,
all child components (TitledContainer, RangeBox, GraphsPage) inherit the Speedrun palette
automatically — **no shared component files changed**.

**Gate mechanism:** The `body.speedrun-stats` class is added by SvelteKit's `+page.svelte`
on mount, conditioned on the `?sr=1` URL param. The Qt stats dialog (`aqt/stats.py`) appends
`?sr=1` to the SvelteKit path only when `SPEEDRUN_SHELL=True`. `SPEEDRUN_SHELL=False` → no
param → no class → stock Anki stats unchanged. Teardown removes the class on unmount.

**Files changed:**

| File | Change |
|---|---|
| `qt/aqt/stats.py` | `NewDeckStats.refresh()`: loads `graphs?sr=1` when `SPEEDRUN_SHELL` |
| `ts/routes/graphs/+page.svelte` | `onMount` adds `body.speedrun-stats` on `?sr` param; renders Speedrun header strip |
| `ts/routes/graphs/graphs-base.scss` | `body.speedrun-stats { … }` block overrides Anki tokens + adds component-level styles |

No shared component files (`TitledContainer.svelte`, `Graph.svelte`, etc.) were touched.

---

## L2 — What is themed vs. left default

### Themed (visually matches Speedrun design language)

- **Page background** → cool pale paper `#F5F7FA` (via `body.background` + `--canvas` override)
- **Graph card containers** (TitledContainer) → white surface `#FFFFFF`, border `#DDE2E9`,
  corner radius 12px (`--border-radius-medium`), soft shadow
- **Card headings (h1)** → grotesk sans, indigo `#3E3A8C`, matches Home card eyebrow style
- **Sticky controls bar** (RangeBox) → white background, bottom border `#DDE2E9`, subtle shadow;
  radio/text inputs styled with indigo accent and focus ring
- **Form controls** → radio `accent-color: #3E3A8C`; text inputs get indigo focus outline
- **Speedrun header strip** → "Speedrun · Statistics" header above the controls bar with
  indigo brand text, matching the Home header feel
- **Buttons** → indigo hover/focus states

### Left at default (not recolored)

- **D3 chart series colors** — hardcoded in TypeScript files (`reviews.ts`, `intervals.ts`,
  etc.) via `d3.interpolate*` color scales. Recoloring would require chart logic rewrites,
  which is out of scope (WP-27 is presentation-only, CSS/Svelte only). The cool pale paper
  background provides enough contrast; charts remain readable. Potential polish item.
- **SVG axis text fill** — `.tick text` has an `opacity: 0.5` applied by `Graph.svelte`
  as a `:global` style; the `fill: #1b2430` override in `graphs-base.scss` tints them
  toward Speedrun ink but the opacity effect stays. Minor.
- **Night mode** — the Speedrun override block does not handle `.night-mode` body class.
  Since `SPEEDRUN_SHELL=True` always uses light mode (the Home shell is light-mode), this
  is not a concern for the current product path. Night mode with Speedrun stats is deferred.
- **Print / PDF export** — retains the Speedrun palette since `body.speedrun-stats` persists
  across print. The PDF export button still functions correctly.
- **CalendarGraph** — uses its own hardcoded heatmap colors; not overridden.
- **Tooltip** — uses stock Anki `--canvas-overlay` / `--fg`; will pick up `--fg` override
  from the token cascade but overlay background is not explicitly overridden (minor).

---

## L3 — Risks and merge notes

- **Merge risk (low):** `ts/routes/graphs/+page.svelte` and `graphs-base.scss` are contained
  within `ts/routes/graphs/` and are not expected to conflict with concurrent work.
  `qt/aqt/stats.py` has a single-line change in `NewDeckStats.refresh()`.
- **Shared file risk (none):** No shared lib components (`TitledContainer`, `Graph`, etc.)
  were modified; all CSS cascades from the scoped body class.
- **SPEEDRUN_SHELL invariant preserved:** `SPEEDRUN_SHELL=False` path: `refresh()` loads
  `graphs` (no param) → no body class added → stock Anki styling fully unchanged.
- **B023/B026 fmt/lint debt:** pre-existing; not introduced by this WP.

---

## L4 — How to verify (GUI steps)

1. `just run` to launch the desktop app.
2. The app opens in single-window Speedrun shell (WP-26).
3. Click **Stats** in the Home header (top-right icon bar) → `mw.onStats()` → Stats dialog opens.
4. **Expected:** pale paper background `#F5F7FA`, "Speedrun · Statistics" header strip,
   graph cards with white surface + rounded corners + indigo `#3E3A8C` headings,
   sticky controls bar with white background + indigo radio accent.
5. **Stock Anki check:** set `SPEEDRUN_SHELL = False` in `qt/aqt/main.py`, restart, open
   stats → should look identical to upstream Anki (no Speedrun styling).

_Owner GUI-verify required (agent cannot drive Qt GUI)._

---

_Created by agent · WP-27 · 2026-07-01_
