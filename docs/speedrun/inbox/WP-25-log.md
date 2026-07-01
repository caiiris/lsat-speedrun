# WP-25 log — Speedrun Home as self-sufficient Anki hub

> iris-log inbox entry. Promote to decisions.md / AGENTS.md / backlog.md after review.

## L1 — Design: top-bar action controls in Home header

**Decision (WP-25):** Added eight Anki actions to the Speedrun Home header as
a compact nav bar, keeping the "Speedrun" wordmark on the left and placing the
controls flush right. Primary buttons: **Sync · Browse · Add · Stats** (visible
at all times). Secondary: **More** dropdown containing **Import · Export · Deck
options · Preferences**.

**Rationale:** The user must never need to leave the Home dialog to reach any
Anki function. Opening a dialog from the top bar keeps the Home window alive
underneath; closing the Anki dialog returns the user immediately to Home.

**Design choices:**
- Controls use the same design-token set as the rest of Home (spec-ui §2):
  `$indigo` hover, `$indigo-light` background tint, `$muted` at rest.
- Icon + label stacked vertically (column flex) at 0.72em — unobtrusive but
  readable. No colour at rest; indigo on hover.
- The "More" dropdown uses a fixed-position backdrop div to close on outside
  click (no JS library needed; self-contained in Svelte `{#if}` block).
- Amber is deliberately **not** used here (reserved for the trap-diagnosis
  "Name the trap" chip per spec-ui §2).

**Files changed (Svelte):**
- `ts/routes/speedrun-dashboard/SpeedrunDashboard.svelte`
  - Added `ankiAction()`, `toggleMore()`, `closeMore()`, `moreAction()`
    functions + `let moreOpen = false` state.
  - Updated `<header class="sr-home-header">`: added `<nav class="sr-anki-actions">`.
  - Added CSS: `.sr-anki-actions`, `.sr-action-btn`, `.sr-action-icon`,
    `.sr-action-label`, `.sr-more-wrap`, `.sr-more-backdrop`, `.sr-more-menu`,
    `.sr-more-divider`.

## L2 — Bridge: `speedrun:anki:*` pycmd routing

**Decision:** `SpeedrunHomeDialog._on_bridge_cmd` now handles the prefix
`speedrun:anki:<action>` by dispatching to `_handle_anki_action(action)`,
which looks the action up in `_ANKI_ACTIONS` (a class-level `dict[str, str]`)
and calls `getattr(mw, method_name)()`. Graceful no-op for unknown actions.

**Action → method map:**
| action       | mw method                  |
|---|---|
| sync         | `on_sync_button_clicked()` |
| browse       | `onBrowse()`               |
| add          | `onAddCard()`              |
| stats        | `onStats()`                |
| import       | `onImport()`               |
| export       | `onExport()`               |
| deck-options | `onDeckConf()`             |
| prefs        | `onPrefs()`                |

**Invariant:** Home dialog is **never** closed by any of these actions. The Anki
dialog opens on top; closing it returns focus to Home.

**Files changed (Python):**
- `qt/aqt/speedrun_home.py`
  - Updated module docstring to include `speedrun:anki:*` protocol.
  - Added `speedrun:anki:` branch to `_on_bridge_cmd`.
  - Added `_ANKI_ACTIONS: dict[str, str]` class attribute.
  - Added `_handle_anki_action(self, action: str) -> bool`.

## L3 — Re-hide deck-browser toolbar under SPEEDRUN_SHELL

**Decision:** Reverts WP-24/B039 change in `qt/aqt/main.py
_deckBrowserState`. Now sets `self.toolbarWeb.setVisible(False)` (not True)
when `SPEEDRUN_SHELL=True`, and does the same in `_deckBrowserCleanup`.

**Rationale:** Since WP-25 surfaces all Anki actions from the Home top bar,
the user no longer needs the Anki toolbar visible through the maximised Home
dialog. Re-hiding it restores the clean shell look. The SPEEDRUN_SHELL=False
path is fully unchanged (stock Anki toolbar visible as normal).

**Files changed (Python):**
- `qt/aqt/main.py` — `_deckBrowserState` and `_deckBrowserCleanup`.

## Status / honest assessment

**Build:** `just lint` running (Python ruff clean on changed files; pre-existing
`tr` unused-import in `speedrun_home.py` is B023/B026 debt, not introduced by
WP-25). Import check: `aqt.main, aqt.speedrun_home` imports cleanly against
the `main`-branch build artifacts.

**GUI verification required (owner):** Cannot be headlessly tested. Owner must:
1. `just run` → Home opens maximised.
2. Click each top-bar button: Sync, Browse, Add, Stats — verify Anki dialog
   opens on top; closing returns to Home.
3. Open "More" dropdown — verify all four items (Import, Export, Deck options,
   Preferences) work the same way.
4. Verify the deck browser (behind the Home) never shows the Anki toolbar.
5. Close Home → verify full stock Anki deck browser appears (toolbar visible).
6. Ctrl+Shift+H / Tools → "Speedrun Home…" → re-opens Home.

**What could not be surfaced (no GUI harness):**
- Exact pixel appearance of the top bar (button sizes, hover states, dropdown
  positioning) — must be checked in `just run`.
- Whether `onDeckConf()` called without arguments correctly opens the deck
  options for the current deck (the method accepts an optional `deck` arg).
- Whether the More dropdown backdrop (fixed-position div) behaves correctly
  inside a Qt WebEngine webview (fixed positioning may behave differently
  than in a browser).

**Merge risk:**
- `main.py` (low): only 2 lines changed in `_deckBrowserState` /
  `_deckBrowserCleanup`; no new imports or interface changes.
- `speedrun_home.py` (low): additive — new `_ANKI_ACTIONS` dict +
  `_handle_anki_action` method + docstring + one branch in `_on_bridge_cmd`.
- `SpeedrunDashboard.svelte` (medium): ~200 lines of new HTML+CSS in the
  `<header>` and `<style>` blocks; no changes to existing sections.

**Suggested decisions to record after GUI verify:**
- D-SR37: WP-25 — Speedrun Home top bar is the one Anki surface; deck-browser
  toolbar hidden under SPEEDRUN_SHELL.
