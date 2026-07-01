# WP-26 Log — Single-window Speedrun shell

iris-log inbox · agent: WP-26 subagent · date: 2026-07-01

---

## L1 — Approach chosen: mw.web state machine (preferred path)

**Option evaluated:** Use the `mw.web` / state-machine approach — add a new
`"speedrunHome"` state to `MainWindowState`, load `speedrun-dashboard/<deck_id>`
into `mw.web` directly, and route pycmd bridge commands through a new method on
`AnkiQt` rather than through `SpeedrunHomeDialog`.

**Why this path (not the hide-mw fallback):**
- True single window: there is exactly one `QMainWindow` (`AnkiQt`); closing it
  calls the normal `closeEvent` → `unloadProfileAndExit` → clean quit. No
  recursion guards, no mw.hide() complexity.
- State machine integration: `moveToState("speedrunHome")` gives us proper
  enter/exit hooks (`_speedrunHomeState` / `_speedrunHomeCleanup`), timer and
  refresh-timer guards (onRefreshTimer only fires for `deckBrowser` / `overview`),
  and `interactiveState()` awareness.
- Session dialogs (`SpeedrunSessionDialog`) continue opening as transient
  `QDialog` children of mw — closing them returns to the Home still in mw.web.
  No state change needed.
- `SPEEDRUN_SHELL=False` path is completely unchanged: `loadCollection()` calls
  `moveToState("deckBrowser")` as before; `onSpeedrunHome()` opens the old dialog.

---

## L2 — Files changed

| File | Change |
|------|--------|
| `qt/aqt/main.py` | Added `"speedrunHome"` to `MainWindowState` literal; changed `loadCollection()` to call `moveToState("speedrunHome")` instead of `deckBrowser` + dialog timer; removed `_speedrun_auto_open_home()`; added `_speedrunHomeState()`, `_speedrunHomeCleanup()`, `_speedrun_home_bridge_cmd()`, `_speedrun_handle_anki_action()`, `_speedrun_open_session()`, `_SPEEDRUN_ANKI_ACTIONS`; updated `onSpeedrunHome()` and `interactiveState()`. |
| `qt/aqt/mediasrv.py` | Added `"/_anki/speedrunDashboard"` to the endpoint whitelist in `_check_dynamic_request_permissions()` so the MAIN webview (which is not in `have_api_access`) can call the dashboard RPC without a 403. |
| `docs/speedrun/inbox/WP-26-log.md` | This file (created). |

**Not changed:** `speedrun_home.py`, `speedrun_session.py`, `speedrun.py`,
`webview.py`, any Rust/proto/schema files.

---

## L3 — Bridge migration

The `SpeedrunHomeDialog._on_bridge_cmd` logic (handling `speedrun:home:*` and
`speedrun:anki:*`) is duplicated onto `AnkiQt` as `_speedrun_home_bridge_cmd`
and friends. The dialog's own bridge continues to work for the
`SPEEDRUN_SHELL=False` code path (dialog is still registered in aqt.dialogs).

The duplication is intentional: `SpeedrunHomeDialog` stays fully functional for
the non-shell path; the new methods on `AnkiQt` handle the shell path. If/when
the dialog is deprecated, this is the only cleanup needed.

---

## L4 — mediasrv whitelist (B037 partial fix for mw.web)

`_check_dynamic_request_permissions()` already had a whitelist for reviewer RPCs
(`getSchedulingStatesWithContext`, `setSchedulingStates`, `i18nResources`,
`congratsInfo`). Added `speedrunDashboard` to that list.

This is surgical: only the dashboard RPC is allowed through for the MAIN
webview; the webview does not get general API access (`have_api_access`
unchanged). This satisfies the WP-26 instruction.

---

## L5 — Risks and known issues

| Risk | Severity | Notes |
|------|----------|-------|
| Stale dashboard data after a session | Low | The SvelteKit page is loaded once; after a `SpeedrunSessionDialog` closes, the data is not automatically refreshed. Future work: emit a refresh signal or reload on dialog close. |
| `onRefreshTimer` does not refresh speedrunHome | Negligible | By design — the 10-minute timer only fires for `deckBrowser` and `overview`. The dashboard uses its own RPC fetch cycle. |
| `congrats_info` moves to "overview" from mediasrv | Very low | Only fires when the main reviewer (not dialog-based) finishes a deck. In speedrunHome mode, reviewing is session-dialog-based so this path is not reachable in normal flow. |
| `d` key shortcut goes to deckBrowser | Acceptable | User can press Ctrl+Shift+H or Tools → Speedrun Home to return. Noted as acceptable per WP scope. |
| Pre-existing B023/B026 | Not introduced here | No Rust/proto changes; dashboard RPC was already in `exposed_backend_list` (B035 done). |

---

## L6 — Status

**Build:** Python import check passed (see commit notes).
`just test-py` not run (requires full build environment); linter showed no new errors.

**GUI verify steps (for owner, requires `just run`):**

1. Launch: exactly ONE window opens — the Speedrun Home dashboard.  
   No separate Anki deck-browser window.
2. Close that window → app quits cleanly (normal Anki quit flow).
3. Home buttons: "Start drill", session type buttons → `SpeedrunSessionDialog`
   opens as a transient dialog; closing returns to Home.
4. Top-bar Anki actions (Sync, Browse, Add, Stats, etc.) → correct Anki dialog
   opens on top; closing returns to Home.
5. `SPEEDRUN_SHELL = False` in `qt/aqt/main.py` → stock Anki: deck browser on
   launch, toolbar visible, no Speedrun dialog auto-opens.
6. Ctrl+Shift+H / Tools → Speedrun Home → re-enters speedrunHome state
   (reloads the dashboard page).
