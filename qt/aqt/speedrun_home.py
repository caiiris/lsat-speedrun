# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Speedrun WP-20 — Home study-plan dialog.

Opens the Speedrun Home screen (spec-ui §3.1) in a resizable Qt dialog.
The page is the SvelteKit route at /speedrun-dashboard/<deck_id>, which
renders SpeedrunDashboard.svelte (the WP-20 Home study-plan surface).

Entry point: open() classmethod — add to Tools menu from main.py.

Bridge commands received from the web page (pycmd calls):
  speedrun:home:start-drill:<skill>
      Opens a targeted-drill session (WP-22) for <skill>.
  speedrun:home:session:<type>
      Opens a session of the specified type: mixed | timed | blind.
"""
from __future__ import annotations

from collections.abc import Callable

import aqt
import aqt.main
from aqt.qt import (
    QDialog,
    Qt,
)
from aqt.utils import (
    disable_help_button,
    restoreGeom,
    saveGeom,
    tr,
)
from aqt.webview import AnkiWebView, AnkiWebViewKind

# Name used for geometry save/restore
_GEOM_KEY = "speedrunHome"

# Deck name to look up when no explicit deck_id is provided
_SPEEDRUN_DECK_NAME = "LSAT Speedrun"


def _find_speedrun_deck_id(mw: aqt.main.AnkiQt) -> int:
    """Return the deck_id for the LSAT Speedrun deck, or 1 as fallback."""
    if not mw.col:
        return 1
    try:
        deck = mw.col.decks.get_current()
        # Prefer a deck whose name starts with the Speedrun name
        for d in mw.col.decks.all_names_and_ids():
            if d.name.startswith(_SPEEDRUN_DECK_NAME):
                return int(d.id)
        # Fallback: whatever is current
        if deck:
            return int(deck["id"])
    except Exception:
        pass
    return 1


class SpeedrunHomeDialog(QDialog):
    """
    Resizable dialog that hosts the Speedrun Home study-plan screen.

    The web content lives in the SvelteKit route
    ``speedrun-dashboard/<deck_id>``; this class handles the Qt side and
    the pycmd bridge (WP-22 seam).
    """

    def __init__(self, mw: aqt.main.AnkiQt) -> None:
        super().__init__(mw, Qt.WindowType.Window)
        mw.garbage_collect_on_dialog_finish(self)
        self.mw = mw
        self.name = _GEOM_KEY

        self.setWindowTitle("Speedrun — Home")
        disable_help_button(self)
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        restoreGeom(self, self.name, default_size=(1040, 720))

        from aqt.qt import QVBoxLayout

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.web = AnkiWebView(kind=AnkiWebViewKind.MAIN)
        layout.addWidget(self.web)
        self.web.set_bridge_command(self._on_bridge_cmd, self)

        self._load()
        self.show()
        self.activateWindow()

    # ------------------------------------------------------------------
    # Loading

    def _load(self) -> None:
        deck_id = _find_speedrun_deck_id(self.mw)
        self.web.load_sveltekit_page(f"speedrun-dashboard/{deck_id}")

    # ------------------------------------------------------------------
    # Bridge command handler

    def _on_bridge_cmd(self, cmd: str) -> bool:
        """Handle pycmd() calls from the Home screen web page."""
        if cmd.startswith("speedrun:home:start-drill:"):
            focus_skill = cmd[len("speedrun:home:start-drill:"):]
            self._open_session("targeted", focus_skill)
            return True

        if cmd.startswith("speedrun:home:session:"):
            session_type = cmd[len("speedrun:home:session:"):]
            self._open_session(session_type, "")
            return True

        return False

    def _open_session(self, mode: str, focus_skill: str) -> None:
        """Open a SpeedrunSessionDialog for the given mode and focus skill."""
        from aqt.speedrun_session import SpeedrunSessionDialog  # noqa: PLC0415

        deck_id = _find_speedrun_deck_id(self.mw)
        SpeedrunSessionDialog.open(
            self.mw,
            mode=mode,
            focus_skill=focus_skill,
            deck_id=deck_id,
        )

    # ------------------------------------------------------------------
    # Lifecycle

    def reject(self) -> None:
        saveGeom(self, self.name)
        self.web.cleanup()
        self.web = None  # type: ignore[assignment]
        aqt.dialogs.markClosed("SpeedrunHome")
        QDialog.reject(self)

    def closeWithCallback(self, callback: Callable[[], None]) -> None:
        self.reject()
        callback()

    # ------------------------------------------------------------------
    # Class-level convenience

    @classmethod
    def open(cls, mw: aqt.main.AnkiQt) -> "SpeedrunHomeDialog":
        """Open the Home dialog (or raise it if already open)."""
        return aqt.dialogs.open("SpeedrunHome", mw)
