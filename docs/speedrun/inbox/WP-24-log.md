# WP-24 Implementation Log — Speedrun full-window shell

> iris-log inbox entry. Merge to `decisions.md` / `backlog.md` / `AGENTS.md` after owner review.

---

## L1 — Approach chosen: auto-maximise Home dialog + hide toolbar in deckBrowser

**Decision:** Rather than rerouting the main `AnkiQt.web` webview or spawning a new
window type, WP-24 reuses the existing working `SpeedrunHomeDialog` (already tested,
API-enabled, session-wired) and makes it open automatically and maximised.  The Anki
main window continues to exist as the host for engine state, sync, and the Reviewer,
but its chrome is hidden while the Speedrun shell is active.

**What was hidden/replaced:**
- The `TopWebView` toolbar (`toolbarWeb`) is physically hidden via
  `setVisible(False)` while the main window is in `deckBrowser` state.  It is
  restored via `_deckBrowserCleanup()` before any other state transition
  (overview, review, etc.) so native Anki review is unaffected.
- The deck-browser content (in `self.web`) renders behind the maximised Home
  dialog; it is not removed but is never visible to the user.
- The window title changes from `"<profile> - Anki"` → `"<profile> - Speedrun"`.

**What was NOT changed:**
- The deck-browser, overview, reviewer, bottom toolbar — all remain intact and
  wired.  Switching `SPEEDRUN_SHELL = False` in `qt/aqt/main.py` fully restores
  stock Anki behaviour (toolbar, title, no auto-open).
- No Rust / proto / schema changes.
- `SpeedrunHomeDialog` unchanged (reused as-is, including its `SPEEDRUN_HOME`
  API-enabled webview kind).

---

## L2 — On/off flag

```python
# qt/aqt/main.py, near the top (after install_pylib_legacy())
SPEEDRUN_SHELL: bool = True   # ← set False to restore stock Anki chrome
```

When `False`: title stays "Anki", toolbar stays visible, no auto-open on launch.
Normal Anki, Browse, Sync, Add, review all work as upstream.

---

## L3 — How Sync + Browse stay reachable

The `TopWebView` toolbar (Decks / Add / Browse / Stats / Sync) is hidden while the
main window shows `deckBrowser` state with `SPEEDRUN_SHELL`.  Sync and Browse
remain reachable through:

1. **Native OS menu bar** (always visible on macOS):
   - Tools → Browse (`Ctrl+Shift+B` / shortcut key `B` on main window)
   - The `Y` keyboard shortcut (`on_sync_button_clicked`) is registered as a
     global shortcut on the main window and fires from any focused window on the
     same desktop.
2. **Tools menu → "Speedrun Home…"** — re-opens Home if accidentally closed.
3. The Speedrun Home dialog itself does not yet have a native Sync button; that
   is left for a follow-up (could be a minimal Speedrun bar added to the Home
   SvelteKit page, or a button in the Home dialog's title bar).  Documented as
   a B-list item.

---

## L4 — Files changed

| File | Change |
|---|---|
| `qt/aqt/main.py` | `SPEEDRUN_SHELL` constant; `updateTitleBar` / `loadProfile` title; `_deckBrowserState` hides toolbar; `_deckBrowserCleanup` restores it; `loadCollection` schedules auto-open; new `_speedrun_auto_open_home` method |

No other files were modified.

---

## L5 — Risks + merge notes

- **Core file touched:** `qt/aqt/main.py` is the most central file in the Qt
  codebase.  Changes are additive (new constant, new method, new `if SPEEDRUN_SHELL`
  guards).  All guards are `if SPEEDRUN_SHELL:` — easily grepped and reverted.
- **`_deckBrowserCleanup` is new:** Anki's `moveToState` dynamically dispatches
  `_{state}Cleanup`.  The new method is harmless when `SPEEDRUN_SHELL = False`
  (the body is an early-exit `if` guard).  Must verify no stock test relies on the
  absence of this method.
- **`toolbarWeb.setVisible(False)` vs CSS hide:** Using Qt's `setVisible` (not the
  CSS-based `TopWebView.hide()`) physically removes the widget from the layout so
  no residual height appears.  `setVisible(True)` in `_deckBrowserCleanup` restores
  it before any state that needs it.  If the toolbar WebView has not yet rendered
  when `setVisible(False)` is called, the behaviour is safe — Qt just keeps it
  hidden until `setVisible(True)`.
- **Timing of auto-open:** the `single_shot(200, ...)` fires ~200 ms after
  `moveToState("deckBrowser")`, which is after the collection is fully loaded
  and before the initial auto-sync result.  If sync takes a very long time, the
  Home dialog is already open but will refresh correctly when the user closes and
  re-opens it (the `SpeedrunDashboard` RPC is called on load).

---

## L6 — Status / honest gaps

- **GUI not verified headlessly** — owner must run `just run` and confirm:
  1. App opens into maximised Speedrun Home (not the deck browser).
  2. The Anki toolbar (Decks/Add/Browse/Stats/Sync) is NOT visible behind the Home.
  3. Tools menu → "Speedrun Home…" + Ctrl+Shift+H still work.
  4. Closing the Home dialog shows the main window with the deck browser (no toolbar).
  5. Starting a session from Home → drill → result → Home flow works end-to-end.
  6. Switching `SPEEDRUN_SHELL = False` restores stock Anki (smoke-test: toolbar
     visible, title "Anki", no auto-open).
- **No Sync button in Home yet** — deferred (B-list; document as B038 or similar).
- **Pre-existing B023/B026** (fmt/lint debt) are untouched.

---

<sub>WP-24 log · 2026-07-01</sub>
