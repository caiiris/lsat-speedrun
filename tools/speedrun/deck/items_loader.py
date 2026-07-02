# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
items_loader.py — load the Speedrun LSAT Item pool.

The item pool is the Q&A database that feeds ``draw_item_for_skill`` (WP-3),
the drill surface (WP-21), Performance (WP-14), and coverage/Readiness. It is
authored as **per-type JSON files** under ``deck/items/`` (one file per
``type::*`` question type, e.g. ``type-flaw.json``) so the growing pool stays
easy to author, review, and diff.

This module is the single source of truth for *reading* the pool: both the seed
builder (``build_seed_deck.py``) and the tests load items through here, so the
on-disk layout can change without touching every consumer.

All items are **SYNTHETIC** placeholders (D-SR11): real LSAT items require an
official source + redistribution licensing and must never be AI-authored.

Back-compat: ``load_items`` also accepts a single ``*.json`` file with a
top-level ``items`` array (the legacy ``sample_items.json`` shape).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DECK_DIR = Path(__file__).resolve().parent
ITEMS_DIR = DECK_DIR / "items"


def merge_item_pools(*paths: str | Path) -> dict[str, Any]:
    """Load and concatenate several item pools (e.g. synthetic + personal import).

    Raises ValueError on duplicate ``_id`` across pools.
    """
    if not paths:
        raise ValueError("merge_item_pools requires at least one path")
    items: list[dict[str, Any]] = []
    sources: dict[str, int] = {}
    seen_ids: dict[str, str] = {}

    for path in paths:
        pool = load_items(path)
        prefix = Path(path).name
        for it in pool["items"]:
            _id = it.get("_id")
            if _id:
                if _id in seen_ids:
                    raise ValueError(
                        f"duplicate item _id {_id!r} in {prefix} "
                        f"(already seen in {seen_ids[_id]})"
                    )
                seen_ids[_id] = prefix
            items.append(it)
        for name, count in pool.get("_sources", {}).items():
            sources[f"{prefix}/{name}"] = count

    return {"items": items, "_sources": sources}


def load_items(path: str | Path = ITEMS_DIR) -> dict[str, Any]:
    """Load the item pool from ``path``.

    ``path`` may be either:
      - a **directory** of per-type files (``type-*.json``), whose ``items``
        arrays are concatenated (files loaded in sorted filename order); or
      - a single **JSON file** with a top-level ``items`` array (legacy shape).

    Returns a dict ``{"items": [...], "_sources": {file: count}}``.

    Raises FileNotFoundError if ``path`` does not exist, and ValueError if a
    file is malformed or two items share an ``_id``.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"item pool path not found: {p}")

    files = _item_files(p)
    items: list[dict[str, Any]] = []
    sources: dict[str, int] = {}
    seen_ids: dict[str, str] = {}

    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as e:
            raise ValueError(f"{f.name} is not valid JSON: {e}") from e

        file_items = data.get("items", [])
        if not isinstance(file_items, list):
            raise ValueError(f"{f.name}: 'items' must be a list")

        for it in file_items:
            _id = it.get("_id")
            if _id:
                if _id in seen_ids:
                    raise ValueError(
                        f"duplicate item _id {_id!r} in {f.name} "
                        f"(already seen in {seen_ids[_id]})"
                    )
                seen_ids[_id] = f.name
            items.append(it)

        sources[f.name] = len(file_items)

    return {"items": items, "_sources": sources}


def _item_files(p: Path) -> list[Path]:
    """Return the JSON files to load, in a stable order."""
    if p.is_dir():
        files = sorted(f for f in p.glob("*.json") if not f.name.startswith("_"))
        if not files:
            raise FileNotFoundError(f"no item JSON files found in {p}")
        return files
    return [p]


def count_by_type(items: list[dict[str, Any]]) -> dict[str, int]:
    """Count items per ``TypeTag`` (for coverage reporting)."""
    counts: dict[str, int] = {}
    for it in items:
        counts[it.get("TypeTag", "")] = counts.get(it.get("TypeTag", ""), 0) + 1
    return counts
