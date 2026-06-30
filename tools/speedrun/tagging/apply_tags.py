# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Apply verified tags to LSAT Item notes in an Anki collection (WP-11).

Writes ``type::``, ``skill::``, and ``trap::`` tags to notes whose
notetype name is ``LSAT Item``.  Only applies tags that have been
**verified** (``TaggedItem.verified == True``); unverified AI proposals are
skipped with a warning.

Guard: when the ``anki`` package is not importable (e.g. in a vanilla Python
env without the built wheel), the module still imports and the public API is
available — but every entry point raises :class:`AnkiUnavailableError` with
an informative message.  This mirrors the ``anki_available`` pattern in
``tools/speedrun/deck/tests/test_build_deck.py`` (L2 in WP-1-log.md).

Usage::

    from tools.speedrun.tagging.apply_tags import apply_verified_tags
    from tools.speedrun.tagging.tagger import TaggedItem

    # Build/confirm TaggedItem instances first, then:
    apply_verified_tags(col, tagged_items)

spec-ai §4 · D-SR14 (generate-then-verify) · D-SR24 (native :: tags)
"""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import TYPE_CHECKING

from tools.speedrun.tagging.tagger import TaggedItem

# ---------------------------------------------------------------------------
# Anki availability guard (mirrors WP-1 @anki_available pattern)
# ---------------------------------------------------------------------------

try:
    import anki  # noqa: F401
    from anki.collection import Collection

    _ANKI_AVAILABLE = True
except ImportError:
    _ANKI_AVAILABLE = False
    Collection = None  # type: ignore[assignment,misc]


class AnkiUnavailableError(RuntimeError):
    """
    Raised when an ``anki``-dependent function is called without the package.

    Build the wheel first::

        just wheels

    Then re-run.  See L2 in docs/speedrun/inbox/WP-1-log.md.
    """


NOTETYPE_ITEM = "LSAT Item"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def anki_available() -> bool:
    """Return True if the ``anki`` package is importable."""
    return _ANKI_AVAILABLE


def apply_verified_tags(
    col: "Collection",  # type: ignore[type-arg]
    tagged_items: list[TaggedItem],
    *,
    dry_run: bool = False,
) -> dict[str, list[str]]:
    """
    Write verified tags to LSAT Item notes in *col*.

    Matches each :class:`~tools.speedrun.tagging.tagger.TaggedItem` by
    ``item_id`` (compared against note field ``_id`` or the note's GUID if
    ``_id`` is absent).

    Parameters
    ----------
    col:
        An open :class:`anki.collection.Collection`.
    tagged_items:
        List of :class:`~tools.speedrun.tagging.tagger.TaggedItem` instances.
        Items with ``verified=False`` are skipped with a warning.
    dry_run:
        If True, compute what would change but do not modify the collection.

    Returns
    -------
    dict mapping ``item_id`` → list of tags that were applied (or would be).
    """
    if not _ANKI_AVAILABLE:
        raise AnkiUnavailableError(
            "The 'anki' package is not installed. Run 'just wheels' first. "
            "See L2 in docs/speedrun/inbox/WP-1-log.md."
        )

    applied: dict[str, list[str]] = {}

    for tagged in tagged_items:
        if not tagged.verified:
            warnings.warn(
                f"Skipping unverified tags for item {tagged.item_id!r}. "
                "Call ItemTagPipeline.confirm() first.",
                UserWarning,
                stacklevel=2,
            )
            continue

        note = _find_note(col, tagged.item_id)
        if note is None:
            warnings.warn(
                f"No LSAT Item note found for id={tagged.item_id!r}; skipping.",
                UserWarning,
                stacklevel=2,
            )
            continue

        new_tags = tagged.type_tags + tagged.skill_tags + tagged.trap_tags
        if not dry_run:
            _apply_tags_to_note(col, note, new_tags)
        applied[tagged.item_id] = new_tags

    return applied


def _find_note(col: "Collection", item_id: str):  # type: ignore[return]
    """
    Look up an LSAT Item note by its ``_id`` field value or note GUID.

    Returns the note object or None if not found.
    """
    # Search by the special field used by WP-1: _id is stored as a note field
    # or as a tag of the form id::<value>.  Try field search first.
    nids = col.find_notes(f'note:"{NOTETYPE_ITEM}"')
    for nid in nids:
        note = col.get_note(nid)
        # Check for an _id field (WP-1 format)
        if "_id" in note.keys() and note["_id"] == item_id:
            return note
        # Fallback: check tags for id::<item_id>
        for tag in note.tags:
            if tag == f"id::{item_id}":
                return note
    return None


def _apply_tags_to_note(col: "Collection", note, new_tags: list[str]) -> None:
    """Add *new_tags* to *note*, avoiding duplicates. Saves the note."""
    existing = set(note.tags)
    for tag in new_tags:
        if tag not in existing:
            note.tags.append(tag)
            existing.add(tag)
    col.update_note(note)
