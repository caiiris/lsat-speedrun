#!/usr/bin/env python3
"""Speedrun WP-10 — executable sync tests (spec-sync-mobile §6).

Runs the 7b harness against a running self-hosted anki-sync-server:
  1. 10+10 offline reviews on two collection copies → merge → 20 unique revlog rows.
  2. Same-card offline conflict → both revlog entries retained.

Prerequisites:
  - `just build` (or `just build` pylib) so `import anki` works from out/pylib.
  - Sync server running: `just sync-server` (default user speedrun:speedrun).

Usage:
  python -m tools.speedrun.sync.sync_test
  python -m tools.speedrun.sync.sync_test --endpoint http://192.168.1.10:8080/
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _ensure_anki_importable() -> None:
    root = _repo_root()
    for sub in ("pylib", "out/pylib"):
        path = root / sub
        if path.is_dir():
            s = str(path)
            if s not in sys.path:
                sys.path.insert(0, s)


def _server_reachable(endpoint: str) -> bool:
    url = endpoint.rstrip("/") + "/"
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            return resp.status < 500
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _revlog_count(col) -> int:
    return col.db.scalar("select count(*) from revlog") or 0


def _card_revlog_count(col, cid: int) -> int:
    return col.db.scalar("select count(*) from revlog where cid = ?", cid) or 0


def _make_basic_deck(col, n_cards: int) -> list[int]:
    """Add *n_cards* Basic notes; return their card ids."""
    from anki.notes import Note

    nt = col.models.by_name("Basic")
    if nt is None:
        raise RuntimeError("Stock 'Basic' notetype missing")
    cids: list[int] = []
    for i in range(n_cards):
        note = Note(col, nt)
        note["Front"] = f"Q{i}"
        note["Back"] = f"A{i}"
        col.addNote(note)
        card = note.cards()[0]
        cids.append(card.id)
    return cids


def _review_card(col, cid: int, ease: int = 3) -> None:
    card = col.get_card(cid)
    col.sched.answerCard(card, ease)


def _sync_full(col, endpoint: str, user: str, password: str) -> None:
    auth = col.sync_login(user, password, endpoint)
    out = col.sync_collection(auth, sync_media=False)
    if out.required != 0:
        # 0 = no changes; other values may still be OK after first sync
        pass


def _copy_collection(src: Path, dst: Path) -> None:
    for suffix in (".anki2", ".media", ".media.db"):
        p = src.with_suffix(suffix)
        if p.exists():
            shutil.copy2(p, dst.with_suffix(suffix))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_ten_plus_ten(
    endpoint: str,
    user: str,
    password: str,
    work: Path,
) -> None:
    """Two offline clients review disjoint sets; merge yields 20 revlog rows."""
    from anki.collection import Collection

    base = work / "base"
    col = Collection(str(base))
    try:
        cids = _make_basic_deck(col, 20)
        _sync_full(col, endpoint, user, password)
    finally:
        col.close()

    col_a_path = work / "a"
    col_b_path = work / "b"
    _copy_collection(base, col_a_path)
    _copy_collection(base, col_b_path)

    col_a = Collection(str(col_a_path))
    try:
        _sync_full(col_a, endpoint, user, password)
        for cid in cids[:10]:
            _review_card(col_a, cid, ease=3)
        assert _revlog_count(col_a) == 10, "client A should have 10 reviews"
    finally:
        col_a.close()

    col_b = Collection(str(col_b_path))
    try:
        _sync_full(col_b, endpoint, user, password)
        for cid in cids[10:]:
            _review_card(col_b, cid, ease=2)
        assert _revlog_count(col_b) == 10, "client B should have 10 reviews"
    finally:
        col_b.close()

    # Reconnect: sync A then B
    col_a = Collection(str(col_a_path))
    try:
        _sync_full(col_a, endpoint, user, password)
    finally:
        col_a.close()

    col_b = Collection(str(col_b_path))
    try:
        _sync_full(col_b, endpoint, user, password)
        total = _revlog_count(col_b)
        assert total == 20, f"expected 20 merged revlog rows, got {total}"
        print(f"  PASS ten-plus-ten: {total} revlog rows after merge")
    finally:
        col_b.close()


def test_same_card_conflict(
    endpoint: str,
    user: str,
    password: str,
    work: Path,
) -> None:
    """Same card reviewed offline on both clients — both entries kept (§5)."""
    from anki.collection import Collection

    base = work / "conflict_base"
    col = Collection(str(base))
    try:
        cid = _make_basic_deck(col, 1)[0]
        _sync_full(col, endpoint, user, password)
    finally:
        col.close()

    a_path = work / "conflict_a"
    b_path = work / "conflict_b"
    _copy_collection(base, a_path)
    _copy_collection(base, b_path)

    col_a = Collection(str(a_path))
    try:
        _sync_full(col_a, endpoint, user, password)
        _review_card(col_a, cid, ease=1)  # Again
    finally:
        col_a.close()

    col_b = Collection(str(b_path))
    try:
        _sync_full(col_b, endpoint, user, password)
        _review_card(col_b, cid, ease=3)  # Good
    finally:
        col_b.close()

    col_a = Collection(str(a_path))
    try:
        _sync_full(col_a, endpoint, user, password)
    finally:
        col_a.close()

    col_b = Collection(str(b_path))
    try:
        _sync_full(col_b, endpoint, user, password)
        n = _card_revlog_count(col_b, cid)
        assert n == 2, f"expected 2 revlog rows for conflict card, got {n}"
        print(f"  PASS same-card conflict: {n} revlog rows on shared card")
    finally:
        col_b.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _credentials_from_env(env_key: str, default: str) -> tuple[str, str]:
    raw = os.environ.get(env_key, default)
    user, sep, password = raw.partition(":")
    if not sep:
        return user, user
    return user, password


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Speedrun sync test harness (WP-10)")
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("SYNC_ENDPOINT", "http://127.0.0.1:8080/"),
        help="Sync server URL (trailing slash optional)",
    )
    parser.add_argument(
        "--user",
        default=os.environ.get("SYNC_USER", "speedrun"),
        help="Sync username (from SYNC_USER1)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("SYNC_PASSWORD", "speedrun"),
        help="Sync password",
    )
    parser.add_argument(
        "--wait",
        type=float,
        default=0.0,
        help="Seconds to wait for server before failing (default: 0)",
    )
    args = parser.parse_args(argv)

    endpoint = args.endpoint if args.endpoint.endswith("/") else args.endpoint + "/"

    if args.wait > 0:
        deadline = time.time() + args.wait
        while time.time() < deadline:
            if _server_reachable(endpoint):
                break
            time.sleep(0.25)
    if not _server_reachable(endpoint):
        print(
            f"ERROR: sync server not reachable at {endpoint}\n"
            "Start one with: just sync-server",
            file=sys.stderr,
        )
        return 1

    _ensure_anki_importable()
    try:
        import anki  # noqa: F401
    except ImportError:
        print(
            "ERROR: cannot import anki — run `just build` first.",
            file=sys.stderr,
        )
        return 1

    print(f"Speedrun sync harness → {endpoint} (user={args.user})")
    with tempfile.TemporaryDirectory(prefix="speedrun-sync-") as tmp:
        work = Path(tmp)
        test_ten_plus_ten(endpoint, args.user, args.password, work)
        user2, pass2 = _credentials_from_env("SYNC_USER2", "speedrun2:speedrun2")
        test_same_card_conflict(endpoint, user2, pass2, work)

    print("All sync tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
