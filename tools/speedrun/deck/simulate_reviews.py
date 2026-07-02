#!/usr/bin/env python3
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Simulate a study history on the Speedrun seed deck so the dashboard populates.

Demo/QA tooling: builds (or opens) a seed collection and fabricates a realistic
review history — some right, some wrong — so the three scores render with real
numbers instead of the cold-start empty/abstain state:

  - **Performance / Readiness / coverage** ← rows inserted into ``revlog`` for the
    ``LSAT Skill`` cards. The dashboard reads ``(cid, ease)`` (ease>=2 = correct);
    the give-up gate needs >=200 total attempts AND >=7/13 ``type::`` skills with
    >=5 attempts. The default run clears both, so Readiness shows a 120-180 point
    + band instead of abstaining.
  - **Memory** ← FSRS ``memory_state`` + ``last_review_time`` set on the
    ``LSAT Meta`` cards (recall computed by the engine from those).

Because a review history lives in ``revlog`` (which ``.apkg`` export does NOT
include), the shareable artifact is a **.colpkg** (full collection). Import it
into a *fresh profile* in the app (it replaces that profile's collection) to see
the populated dashboard.

    PYTHONPATH=out/pylib:pylib:tools/speedrun/deck \\
        out/pyenv/bin/python tools/speedrun/deck/simulate_reviews.py \\
        --out out/speedrun-demo-reviewed.colpkg

This fabricates data for a demo; it is not a real study session.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import tempfile
import time
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
_REPO_ROOT = _THIS_DIR.parents[2]
for _p in (_REPO_ROOT / "out" / "pylib", _REPO_ROOT / "pylib"):
    if _p.exists() and str(_p) not in sys.path:
        sys.path.append(str(_p))

DECK_ROOT = "LSAT Speedrun"
SKILL_NOTETYPE = "LSAT Skill"
META_NOTETYPE = "LSAT Meta"

# Per-type target accuracy (some strong, some weak) — makes the per-skill bars
# and the "next best skill" recommendation meaningful.
TYPE_ACCURACY = {
    "type::flaw": 0.80,
    "type::assumption": 0.70,
    "type::inference": 0.64,
    "type::strengthen": 0.74,
    "type::weaken": 0.68,
    "type::principle": 0.58,
    "type::paradox": 0.76,
    "type::parallel": 0.55,
    "type::method": 0.82,
    "type::justify": 0.62,
    "type::main-point": 0.86,
    "type::point-at-issue": 0.71,
    "type::evaluate": 0.66,
}


def _identity_tag(tags: list[str]) -> str | None:
    for t in tags:
        if t.startswith(("type::", "skill::", "trap::")):
            return t
    return None


def _build_temp_seed(min_pool: int) -> str:
    from build_seed_deck import build_seed_deck

    fd, col_path = tempfile.mkstemp(suffix=".anki2", prefix="speedrun_sim_")
    os.close(fd)
    os.unlink(col_path)
    build_seed_deck(col_path=col_path, min_pool_size=min_pool, verbose=False)
    return col_path


def _simulate(col, rng: random.Random, attempts_per_type: int) -> tuple[int, int]:
    """Insert skill revlog + set meta memory states. Returns (skill_reviews, meta_cards)."""
    from anki.cards import FSRSMemoryState

    # ── Skill reviews → revlog (Performance / Readiness / coverage) ──────────
    # Map each type:: skill to its skill card id.
    skill_nids = col.find_notes(f'note:"{SKILL_NOTETYPE}"')
    type_card: dict[str, int] = {}
    for nid in skill_nids:
        note = col.get_note(nid)
        tag = _identity_tag(list(note.tags))
        if tag and tag.startswith("type::") and tag not in type_card:
            type_card[tag] = note.cards()[0].id

    now_ms = int(time.time() * 1000)
    rid = now_ms - 400_000_000  # start well in the past; increment to stay unique
    total_reviews = 0
    for skill, acc in TYPE_ACCURACY.items():
        cid = type_card.get(skill)
        if cid is None:
            continue
        n = attempts_per_type + rng.randint(-3, 4)
        n = max(6, n)  # keep every type above the >=5 coverage threshold
        correct = round(n * acc)
        eases = [3] * correct + [1] * (n - correct)
        rng.shuffle(eases)
        for ease in eases:
            rid += rng.randint(50_000, 90_000)  # spread ids; guaranteed increasing
            col.db.execute(
                "INSERT INTO revlog (id,cid,usn,ease,ivl,lastIvl,factor,time,type) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                rid,
                cid,
                0,
                ease,
                1,
                0,
                2500,
                rng.randint(4000, 25000),
                1,
            )
            total_reviews += 1

    # ── Meta memory states (Memory) ─────────────────────────────────────────
    now_secs = int(time.time())
    meta_cids = col.find_cards(f'note:"{META_NOTETYPE}"')
    for cid in meta_cids:
        card = col.get_card(cid)
        stability_days = rng.uniform(3.0, 90.0)
        difficulty = rng.uniform(4.0, 7.0)
        elapsed_days = stability_days * rng.uniform(0.1, 1.5)
        card.memory_state = FSRSMemoryState(
            stability=stability_days, difficulty=difficulty
        )
        card.last_review_time = now_secs - int(elapsed_days * 86_400)
        col.update_card(card)

    return total_reviews, len(meta_cids)


def _print_dashboard(col) -> None:
    root_did = col.decks.id(DECK_ROOT)
    dash = col.speedrun_dashboard(root_did)
    print("\n─── Speedrun dashboard (deck: LSAT Speedrun) ──────────────────────")
    if dash.HasField("memory"):
        m = dash.memory
        print(
            f"Memory:      {m.mean_recall * 100:.0f}%  "
            f"[{m.ci_lower * 100:.0f}–{m.ci_upper * 100:.0f}%]  "
            f"over {m.card_count} meta cards"
        )
    else:
        print("Memory:      (no meta cards / no data)")
    print(
        f"Performance: {dash.overall_perf * 100:.0f}% weighted  ·  "
        f"coverage {dash.lr_coverage * 100:.0f}%  ·  {dash.total_attempts} attempts"
    )
    if dash.eligible and dash.HasField("readiness"):
        r = dash.readiness
        print(
            f"Readiness:   {r.point}  [{r.band_low}–{r.band_high}]  "
            f"confidence={r.confidence}  (next: {r.next_best})"
        )
    else:
        print("Readiness:   ABSTAIN")
        if dash.HasField("abstain"):
            for reason in dash.abstain.reasons:
                print(f"             - {reason}")
            print(f"             next best: {dash.abstain.next_best}")
    print("───────────────────────────────────────────────────────────────────\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Simulate a study history so the Speedrun dashboard populates."
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Export the reviewed collection to this .colpkg (recommended; "
        ".apkg does NOT carry review history).",
    )
    parser.add_argument(
        "--col",
        default=":temp:",
        help="Existing .anki2 to simulate on, or ':temp:' to build a fresh seed "
        "deck (default). NOTE: an existing collection is modified in place.",
    )
    parser.add_argument(
        "--attempts-per-type",
        type=int,
        default=20,
        help="Approx reviews per question type (default 20 → ~260 total, "
        "clears the >=200 Readiness gate).",
    )
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (deterministic).")
    parser.add_argument(
        "--keep-col",
        action="store_true",
        help="Keep the intermediate temp .anki2 (temp build only).",
    )
    args = parser.parse_args(argv)

    rng = random.Random(args.seed)

    built_temp = False
    if args.col == ":temp:":
        try:
            col_path = _build_temp_seed(min_pool=3)
        except ImportError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        built_temp = True
    else:
        col_path = str(Path(args.col).resolve())
        if not Path(col_path).exists():
            print(f"ERROR: collection not found: {col_path}", file=sys.stderr)
            return 1

    from anki.collection import Collection

    col = Collection(col_path)
    exported = False
    try:
        reviews, meta = _simulate(col, rng, args.attempts_per_type)
        print(f"Simulated {reviews} skill reviews; set memory state on {meta} meta cards.")
        _print_dashboard(col)
        if args.out:
            out_path = str(Path(args.out).resolve())
            # .colpkg preserves revlog (the review history); .apkg would drop it.
            col.export_collection_package(out_path, include_media=True, legacy=True)
            exported = True
            size = Path(out_path).stat().st_size / 1024 if Path(out_path).exists() else 0
            print(f"Exported colpkg -> {out_path} ({size:.0f} KiB)")
    finally:
        if not exported:
            try:
                col.close()
            except Exception:
                pass
        if built_temp and not args.keep_col:
            for suffix in ("", "-wal", "-shm"):
                try:
                    os.unlink(col_path + suffix)
                except OSError:
                    pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
