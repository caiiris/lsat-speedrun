# WP-20 build log — Home study-plan surface

> iris-log inbox format (provisional — pending promotion to decisions.md by reviewer).
> Created: 2026-07-01, WP-20 build agent.
> Branch: wp20-home-study-plan (worktree).

---

## L1 — Entry-point approach

**Decision:** added `speedrun-dashboard` to `is_sveltekit_page()` in
`qt/aqt/mediasrv.py` so the existing SvelteKit route serves the Home screen
via the standard mediasrv fallback mechanism (the SvelteKit `index.html`
is served for any matching path; client-side routing handles
`/speedrun-dashboard/<deck_id>`). No new page or route was needed.

A new `SpeedrunHomeDialog` (`qt/aqt/speedrun_home.py`) opens the page in a
resizable Qt dialog, registered as `"SpeedrunHome"` in the `DialogManager`.
The dialog is reached via **Tools → Speedrun Home…** (shortcut `Ctrl+Shift+H`),
added programmatically in `main.py::_setup_speedrun_home_menu()` to avoid
modifying the `.ui` form file (keeps upstream rebase cost low).

**URL to view (after `just run`):**
`http://localhost:40000/speedrun-dashboard/1` (replace `1` with the actual
LSAT Speedrun deck ID found in the Qt UI or via Tools → Speedrun Home…).

---

## L2 — "Start targeted drill" seam to WP-22

**Status:** provisional seam in place.

The "Start targeted drill" button emits `pycmd("speedrun:home:start-drill:<skill>")`.
The `SpeedrunHomeDialog._on_bridge_cmd` handler catches this and, as the best
available entry until WP-22, closes the Home dialog and navigates the Qt main
window to the deck overview for the LSAT Speedrun deck (standard study path).

Session launchers (Mixed set / Timed section / Blind review) similarly emit
`pycmd("speedrun:home:session:<type>")` and fall through to the same study
fallback.

**WP-22 contract (TODO):**
- Replace `_open_study_fallback` with a real SvelteKit session route navigation.
- Create `ts/routes/speedrun-session/` with `?type=mixed|timed|blind` parameter.
- Once the session route exists, the button can navigate directly in the webview
  without closing the dialog (`window.location.href = "/speedrun-session?type=..."`)
  and the pycmd seam can be removed.

---

## L3 — Data from the RPC: what was available vs needed

The `SpeedrunDashboard` RPC (`D-SR32`) provides all data needed for the Home
screen, with one minor gap:

| Spec element | RPC field | Status |
|---|---|---|
| Memory mean + band | `memory.meanRecall`, `ciLower/ciUpper` | ✓ available |
| Performance overall + band | `overallPerf` (+ Wald approx from `totalAttempts`) | ✓ — band approximated from Wald; Wilson is per-skill |
| Readiness abstain panel | `eligible`, `abstain.reasons`, `abstain.coverage`, `abstain.nextBest` | ✓ available |
| Readiness eligible score | `readiness.point`, `bandLow/bandHigh`, `confidence` | ✓ available |
| Today's focus skill | `abstain.nextBest` / `readiness.nextBest` | ✓ available |
| Skill map per-type bars | `skillPerf[].wilsonLow/High`, `correct/attempts` | ✓ available |
| RECOMMENDED badge | derived from `focusSkill` | ✓ derived |
| Streak / total time (header) | not in RPC | ✗ not available — header shows brand only |

The streak and total-study-time indicators visible in the mockup header are not
in the `SpeedrunDashboard` RPC (`D-SR32`). They are omitted from v1; the header
shows only the "Speedrun" brand. A future RPC addition or a separate call would
be needed to add them.

---

## L4 — Design deviations from the mockup

1. **Header streak/time**: omitted (data not in RPC — see L3 above).
2. **Performance band chip**: uses a Wald approximation on `totalAttempts * overallPerf`
   rather than a true Wilson CI for the aggregated performance. This is acceptable for
   display (the per-skill map shows true Wilson CIs). Consider adding an aggregate
   Wilson to the RPC in a future iteration.
3. **Session launcher icons**: hand-drawn SVG approximations matching the mockup's
   shuffle/clock/eye motifs; not pixel-perfect but visually coherent.
4. **Exam-frequency weights in skill map**: the spec mentions "14% of the exam" for the
   Assumption family in the focus heading. This weight data is in `docs/speedrun/data/weights.json`
   but is not in the `SpeedrunDashboard` RPC. The focus sub-heading shows accuracy instead.
   Add `examWeight` to the RPC response in a future iteration if the weight label is desired.

---

## L5 — Bugs encountered

- **`<style>` in a `<script>` comment** broke the Svelte preprocessor. The comment
  `// Referenced as CSS variables in <style>; also used...` confused the Svelte file
  parser which uses regex matching for tag boundaries. Fixed by rephrasing the comment.
- **`<tr>` directly in `<table>`** produced a Svelte a11y/validity warning. Fixed by
  wrapping rows in `<tbody>`.

---

## L6 — Pre-existing failures (NOT introduced by WP-20)

- **Rust**: `cargo clippy` reports 5 unused-import errors in `rslib/src/stats/mod.rs`
  (from WP-14). These exist on `main` before any WP-20 change.
- **TypeScript**: 2 pre-existing `bigint`/`number` type mismatches in
  `ts/routes/speedrun-dashboard/index.ts` and `[...deckId]/+page.ts` (generated
  backend API changed `deckId` to `bigint`; fix is a separate task).
- **dprint / ruff / mypy on docs+tools**: B023/B026 from AGENTS.md — not touched.

---

## L7 — Merge-risk vs WP-21

WP-21 touches `ts/reviewer/` + `qt/aqt/reviewer.py` (drill/session surface).
WP-20 touches:
- `qt/aqt/__init__.py` — adds `SpeedrunHome` to `DialogManager._dialogs`
- `qt/aqt/main.py` — adds `_setup_speedrun_home_menu` + `onSpeedrunHome`
- `qt/aqt/mediasrv.py` — adds `"speedrun-dashboard"` to `is_sveltekit_page()`
- `ts/routes/speedrun-dashboard/SpeedrunDashboard.svelte` — full redesign
- `ts/routes/speedrun-dashboard/speedrun-dashboard-base.scss` — base styles
- `qt/aqt/speedrun_home.py` — new file (no conflict risk)

**Shared files with WP-21:**
- `qt/aqt/__init__.py` and `qt/aqt/main.py` *might* also be touched by WP-21
  if it adds a reviewer dialog or menu entry. The changes are additive and in
  clearly marked blocks — a text-level merge should be clean.
- `qt/aqt/mediasrv.py` is possible if WP-21 adds a new sveltekit page route.
  Again additive; one-line list entry.
- `qt/aqt/reviewer.py` — WP-21's main target, **not touched by WP-20**.
- `ts/reviewer/` — **not touched by WP-20**.

Merge risk is **low**: all WP-20 changes are additive and isolated.
