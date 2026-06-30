# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Paraphrase eval (spec-measurement §7, PRD §9.G, D-SR2).

Purpose: prove that Performance ≠ Memory copy.

Input: items, each with:
  - item_id: str
  - base_outcome:  int in {0,1}  — recall on the original card (Memory proxy)
  - variant_outcomes: list[int]  — outcomes on 2 reworded variants (Performance proxy)

For each item we compute the *gap* = base_outcome - mean(variant_outcomes).
  - A positive gap means the student recalled the original but failed variants
    → rote memory, not transferable skill (the problem D-SR2 guards against).
  - A gap near 0 → either consistent mastery or consistent failure.

The overall gap (mean across items) quantifies how much Performance diverges
from Memory.  A significant positive gap is the expected finding; a gap ≈ 0
still satisfies the spec (it means the student *does* have transferable skill).

Usage (JSON):
  python -m tools.speedrun.eval.paraphrase --input items.json
  python -m tools.speedrun.eval.paraphrase --fixture

JSON schema: list of objects:
  [
    {
      "item_id": "q001",
      "base_outcome": 1,
      "variant_outcomes": [1, 0]
    },
    ...
  ]

CSV schema: item_id, base_outcome, variant_outcome_1, variant_outcome_2, ...
  q001,1,1,0
  q002,0,0,0
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ParaphraseItem:
    item_id: str
    base_outcome: int            # 1 = correct on original card
    variant_outcomes: list[int]  # outcomes on reworded variants (≥1 required)


@dataclass
class ItemGap:
    item_id: str
    base_outcome: int
    variant_mean: float
    gap: float         # base_outcome - variant_mean (positive → rote memory)
    n_variants: int


@dataclass
class ParaphraseResult:
    item_gaps: list[ItemGap]
    overall_gap: float            # mean gap across items (positive = memory copy risk)
    base_accuracy: float          # fraction of items with base_outcome == 1
    variant_accuracy: float       # mean(variant_outcomes) across all items
    n_items: int
    n_variants_total: int

    def summary_table(self) -> str:
        header = f"{'item_id':>12}  {'base':>4}  {'var_mean':>8}  {'gap':>6}  {'N_var':>5}"
        rows = [header, "-" * len(header)]
        for g in self.item_gaps:
            rows.append(
                f"{g.item_id:>12}  {g.base_outcome:>4}  {g.variant_mean:>8.3f}  "
                f"{g.gap:>+6.3f}  {g.n_variants:>5}"
            )
        rows.append(
            f"\nBase accuracy     : {self.base_accuracy:.3f}"
        )
        rows.append(
            f"Variant accuracy  : {self.variant_accuracy:.3f}"
        )
        rows.append(
            f"Overall gap (mean): {self.overall_gap:+.3f}"
            "  (+ve → rote memory risk; ≈0 → transferable skill)"
        )
        rows.append(f"N items / variants: {self.n_items} / {self.n_variants_total}")
        return "\n".join(rows)


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------


def compute_paraphrase_gap(items: Sequence[ParaphraseItem]) -> ParaphraseResult:
    if not items:
        raise ValueError("No paraphrase items provided.")

    item_gaps: list[ItemGap] = []
    all_base: list[int] = []
    all_variants: list[int] = []

    for item in items:
        if item.base_outcome not in (0, 1):
            raise ValueError(
                f"base_outcome must be 0 or 1 for item {item.item_id!r}, "
                f"got {item.base_outcome!r}"
            )
        if not item.variant_outcomes:
            raise ValueError(f"Item {item.item_id!r} has no variant outcomes.")
        for v in item.variant_outcomes:
            if v not in (0, 1):
                raise ValueError(
                    f"variant_outcome must be 0 or 1 for item {item.item_id!r}, got {v!r}"
                )

        variant_mean = sum(item.variant_outcomes) / len(item.variant_outcomes)
        gap = item.base_outcome - variant_mean

        item_gaps.append(
            ItemGap(
                item_id=item.item_id,
                base_outcome=item.base_outcome,
                variant_mean=variant_mean,
                gap=gap,
                n_variants=len(item.variant_outcomes),
            )
        )
        all_base.append(item.base_outcome)
        all_variants.extend(item.variant_outcomes)

    overall_gap = sum(g.gap for g in item_gaps) / len(item_gaps)
    base_accuracy = sum(all_base) / len(all_base)
    variant_accuracy = sum(all_variants) / len(all_variants)

    return ParaphraseResult(
        item_gaps=item_gaps,
        overall_gap=overall_gap,
        base_accuracy=base_accuracy,
        variant_accuracy=variant_accuracy,
        n_items=len(items),
        n_variants_total=len(all_variants),
    )


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def load_json(path: Path) -> list[ParaphraseItem]:
    raw = json.loads(path.read_text())
    return [
        ParaphraseItem(
            item_id=str(r["item_id"]),
            base_outcome=int(r["base_outcome"]),
            variant_outcomes=[int(v) for v in r["variant_outcomes"]],
        )
        for r in raw
    ]


def load_csv(path: Path) -> list[ParaphraseItem]:
    items: list[ParaphraseItem] = []
    with path.open(newline="") as fh:
        reader = csv.reader(fh)
        first = next(reader, None)
        if first is None:
            return items
        # Check if first row is a header
        try:
            int(first[1])
            rows = [first]
        except (ValueError, IndexError):
            rows = []
        rows.extend(reader)
        for row in rows:
            if not row:
                continue
            item_id = row[0].strip()
            base = int(row[1])
            variants = [int(v) for v in row[2:] if v.strip() != ""]
            items.append(
                ParaphraseItem(item_id=item_id, base_outcome=base, variant_outcomes=variants)
            )
    return items


# ---------------------------------------------------------------------------
# Synthetic fixture
# ---------------------------------------------------------------------------


def make_fixture(seed: int = 42, n_items: int = 30, n_variants: int = 2) -> list[ParaphraseItem]:
    """
    30 items × 2 variants (per spec-measurement §7).

    Two cohorts, seeded deterministically:
    - Items q001–q015: student recalled original (base=1) but ~50% on variants
      → positive gap; rote-memory risk.
    - Items q016–q030: student recalled both original and variants consistently
      → gap ≈ 0; transferable skill.
    """
    import random
    rng = random.Random(seed)
    items: list[ParaphraseItem] = []

    for i in range(1, n_items // 2 + 1):
        # Rote-memory cohort: base correct, variants only 50%
        variants = [1 if rng.random() < 0.5 else 0 for _ in range(n_variants)]
        items.append(ParaphraseItem(
            item_id=f"q{i:03d}",
            base_outcome=1,
            variant_outcomes=variants,
        ))

    for i in range(n_items // 2 + 1, n_items + 1):
        # Transferable-skill cohort: base and variants both ~85% correct
        base = 1 if rng.random() < 0.85 else 0
        variants = [1 if rng.random() < 0.85 else 0 for _ in range(n_variants)]
        items.append(ParaphraseItem(
            item_id=f"q{i:03d}",
            base_outcome=base,
            variant_outcomes=variants,
        ))

    return items


def run_fixture() -> None:
    print("=== FIXTURE: paraphrase gap (30 items × 2 variants) ===")
    items = make_fixture(seed=42)
    result = compute_paraphrase_gap(items)
    print(result.summary_table())


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Paraphrase eval: recall-vs-reworded accuracy gap."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", type=Path, help="JSON or CSV input file")
    group.add_argument("--fixture", action="store_true", help="Run synthetic fixture")
    args = parser.parse_args(argv)

    if args.fixture:
        run_fixture()
        return

    path: Path = args.input
    if path.suffix.lower() == ".json":
        items = load_json(path)
    else:
        items = load_csv(path)

    result = compute_paraphrase_gap(items)
    print(result.summary_table())


if __name__ == "__main__":
    main()
