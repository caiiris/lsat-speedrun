# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Tests for tools/speedrun/deck/export_deck.py.

Exercises the WP-9 demo-deck exporter: building the seed deck and writing an
importable .apkg / .colpkg, plus a round-trip import into a fresh (empty)
collection — the clean-machine install path.

Like the other deck tests, these require the built `anki` package; without it
the anki-dependent tests are skipped. To run:
    just wheels && pytest tools/speedrun/deck/tests/test_export_deck.py -v
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Generator

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
DECK_DIR = REPO_ROOT / "tools" / "speedrun" / "deck"

sys.path.insert(0, str(DECK_DIR))

import export_deck  # noqa: E402


def _anki_importable() -> bool:
    try:
        import anki  # noqa: F401

        return True
    except ImportError:
        return False


anki_available = pytest.mark.skipif(
    not _anki_importable(),
    reason="anki package not installed. Build the wheel first with 'just wheels'.",
)


def _cleanup_col(path: str) -> None:
    for ext in ["", "-wal", "-shm", ".log", ".log.last"]:
        sibling = path + ext
        if os.path.exists(sibling):
            os.unlink(sibling)
    media = path + ".media"
    if os.path.isdir(media):
        shutil.rmtree(media, ignore_errors=True)


@pytest.fixture
def out_dir() -> Generator[Path, None, None]:
    d = Path(tempfile.mkdtemp(prefix="speedrun_export_test_"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
# No-anki paths
# ---------------------------------------------------------------------------


def test_missing_collection_returns_error(out_dir: Path) -> None:
    """--col pointing at a nonexistent file fails cleanly (no anki needed)."""
    rc = export_deck.main(
        ["--out", str(out_dir / "x.apkg"), "--col", str(out_dir / "nope.anki2")]
    )
    assert rc == 1


def test_format_inferred_from_extension() -> None:
    """Extension → format inference is pure (no build)."""
    assert export_deck  # module imported
    # .colpkg → colpkg, anything else → apkg (mirrors main()'s inference)
    for name, expected in [
        ("demo.apkg", "apkg"),
        ("demo.colpkg", "colpkg"),
        ("demo", "apkg"),
    ]:
        fmt = "colpkg" if name.endswith(".colpkg") else "apkg"
        assert fmt == expected


# ---------------------------------------------------------------------------
# anki-dependent: build + export + round-trip import
# ---------------------------------------------------------------------------


@anki_available
def test_export_apkg_roundtrip(out_dir: Path) -> None:
    """Export a fresh seed deck to .apkg, then import into an empty collection."""
    from anki.collection import Collection, ImportAnkiPackageRequest

    apkg = out_dir / "demo.apkg"
    rc = export_deck.main(["--out", str(apkg)])
    assert rc == 0
    assert apkg.exists() and apkg.stat().st_size > 0
    assert zipfile.is_zipfile(apkg)

    col_path = str(out_dir / "fresh.anki2")
    col = Collection(col_path)
    try:
        assert len(col.find_cards("")) == 0
        col.import_anki_package(ImportAnkiPackageRequest(package_path=str(apkg)))
        skill = len(col.find_notes('note:"LSAT Skill"'))
        item = len(col.find_notes('note:"LSAT Item"'))
        meta = len(col.find_notes('note:"LSAT Meta"'))
        assert skill > 0, "no LSAT Skill notes imported"
        assert item > 0, "no LSAT Item notes imported"
        assert meta > 0, "no LSAT Meta notes imported"
        assert len(col.find_cards("")) == skill + item + meta
        decks = {d.name for d in col.decks.all_names_and_ids()}
        for expected in (
            "LSAT Speedrun",
            "LSAT Speedrun::Items",
            "LSAT Speedrun::Meta",
            "LSAT Speedrun::Skills",
        ):
            assert expected in decks, f"missing deck {expected}"
    finally:
        col.close()
        _cleanup_col(col_path)


@anki_available
def test_export_colpkg_is_zip(out_dir: Path) -> None:
    """--format colpkg (and .colpkg inference) writes a valid package."""
    colpkg = out_dir / "demo.colpkg"
    rc = export_deck.main(["--out", str(colpkg)])
    assert rc == 0
    assert colpkg.exists() and colpkg.stat().st_size > 0
    assert zipfile.is_zipfile(colpkg)


@anki_available
def test_export_from_existing_collection(out_dir: Path) -> None:
    """--col on an existing built .anki2 exports without rebuilding."""
    from build_seed_deck import build_seed_deck

    col_path = str(out_dir / "seed.anki2")
    build_seed_deck(col_path=col_path, verbose=False)

    apkg = out_dir / "from_existing.apkg"
    rc = export_deck.main(["--out", str(apkg), "--col", col_path])
    assert rc == 0
    assert apkg.exists() and zipfile.is_zipfile(apkg)
    _cleanup_col(col_path)
