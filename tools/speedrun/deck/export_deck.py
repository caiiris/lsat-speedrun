#!/usr/bin/env python3
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Export the Speedrun seed deck as one importable package (.apkg / .colpkg).

Additive tooling for WP-9 (installer / clean-machine demo): a freshly-installed
Speedrun app starts with an empty profile, so the "loads your exam deck and runs
a review" proof needs a single file to import. This builds (or reuses) a seed
collection and writes an importable package:

  - ``.apkg``  (default) — additive import (File -> Import); brings the decks,
    the 3 notetypes, and scheduling into the existing profile without touching
    the user's other data.
  - ``.colpkg``          — a full-collection package (replaces the collection
    on import); handy for a pristine, one-shot demo profile.

Run with the built ``anki`` lib on the path, e.g.::

    PYTHONPATH=out/pylib:pylib:tools/speedrun/deck \\
        out/pyenv/bin/python tools/speedrun/deck/export_deck.py \\
        --out out/speedrun-demo.apkg

``:temp:`` (the default ``--col``) builds a fresh synthetic seed deck and throws
the intermediate collection away; pass ``--col path.anki2`` to export a deck you
already built (e.g. one that includes locally-imported real items).
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

# Make sibling modules (build_seed_deck, items_loader) importable when this file
# is run by path rather than as part of a package.
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

# Best-effort: add the built pylib so `anki` imports even if PYTHONPATH is unset.
_REPO_ROOT = _THIS_DIR.parents[2]
for _p in (_REPO_ROOT / "out" / "pylib", _REPO_ROOT / "pylib"):
    if _p.exists() and str(_p) not in sys.path:
        sys.path.append(str(_p))


def _build_temp_seed(items: str | None, import_paths: list[str], min_pool: int) -> str:
    """Build a fresh synthetic seed deck in a temp .anki2 and return its path."""
    from build_seed_deck import build_seed_deck

    fd, col_path = tempfile.mkstemp(suffix=".anki2", prefix="speedrun_export_")
    os.close(fd)
    os.unlink(col_path)  # Collection() wants to create the file itself

    kwargs: dict = {"col_path": col_path, "min_pool_size": min_pool}
    if items:
        kwargs["items_json_path"] = items
    if import_paths:
        kwargs["import_paths"] = import_paths
    build_seed_deck(**kwargs)
    return col_path


def _export(col_path: str, out_path: str, fmt: str) -> None:
    from anki.collection import Collection, ExportAnkiPackageOptions

    col = Collection(col_path)
    try:
        if fmt == "colpkg":
            col.export_collection_package(out_path, include_media=True, legacy=True)
        else:
            col.export_anki_package(
                out_path=out_path,
                options=ExportAnkiPackageOptions(
                    with_scheduling=True,
                    with_deck_configs=True,
                    with_media=True,
                    legacy=True,
                ),
                limit=None,  # whole collection
            )
    finally:
        try:
            col.close()
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export the Speedrun seed deck as an importable package."
    )
    parser.add_argument("--out", required=True, help="Output path (.apkg or .colpkg).")
    parser.add_argument(
        "--format",
        choices=["apkg", "colpkg"],
        default=None,
        help="Package format (default: inferred from --out extension, else apkg).",
    )
    parser.add_argument(
        "--col",
        default=":temp:",
        help="Existing .anki2 to export, or ':temp:' to build a fresh synthetic "
        "seed deck (default).",
    )
    parser.add_argument(
        "--items",
        default=None,
        help="Items dir/file passed to the seed builder (temp build only).",
    )
    parser.add_argument(
        "--import",
        dest="import_paths",
        action="append",
        default=[],
        metavar="DIR",
        help="Merge a local imported item dir (repeatable; temp build only).",
    )
    parser.add_argument(
        "--min-pool",
        type=int,
        default=3,
        help="Min pool size for coverage (temp build only).",
    )
    parser.add_argument(
        "--keep-col",
        action="store_true",
        help="Keep the intermediate temp .anki2 (temp build only).",
    )
    args = parser.parse_args(argv)

    out_path = str(Path(args.out).resolve())
    fmt = args.format or ("colpkg" if out_path.endswith(".colpkg") else "apkg")

    built_temp = False
    if args.col == ":temp:":
        try:
            col_path = _build_temp_seed(args.items, args.import_paths, args.min_pool)
        except ImportError as e:
            print(
                f"ERROR: {e}\nBuild the anki wheel first ('just wheels') or set "
                "PYTHONPATH=out/pylib:pylib.",
                file=sys.stderr,
            )
            return 1
        built_temp = True
    else:
        col_path = str(Path(args.col).resolve())
        if not Path(col_path).exists():
            print(f"ERROR: collection not found: {col_path}", file=sys.stderr)
            return 1

    try:
        _export(col_path, out_path, fmt)
    except ImportError as e:
        print(
            f"ERROR: {e}\nBuild the anki wheel first ('just wheels') or set "
            "PYTHONPATH=out/pylib:pylib.",
            file=sys.stderr,
        )
        return 1
    finally:
        if built_temp and not args.keep_col:
            try:
                os.unlink(col_path)
            except OSError:
                pass

    size_kib = Path(out_path).stat().st_size / 1024 if Path(out_path).exists() else 0
    print(f"Exported {fmt} -> {out_path} ({size_kib:.0f} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
