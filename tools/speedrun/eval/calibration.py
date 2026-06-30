# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Calibration eval (spec-measurement §7, PRD §9.G).

Input: (predicted_recall_R, observed_outcome) pairs where:
  - predicted_recall_R: float in [0, 1] — FSRS recall probability
  - observed_outcome:   int in {0, 1} — 1 = correct, 0 = wrong

Outputs:
  - Reliability table: one row per bin (mean predicted R, fraction correct, N)
  - Brier score: mean((predicted_R - outcome)^2); lower is better (0 = perfect)
  - Log-loss: cross-entropy loss; lower is better
  - Optional: reliability diagram via matplotlib if available

Usage (CSV):
  python -m tools.speedrun.eval.calibration --input reviews.csv
  python -m tools.speedrun.eval.calibration --fixture          # run synthetic fixtures

CSV schema: two columns, header optional:
  predicted_r,outcome
  0.82,1
  0.34,0
  ...

JSON schema: list of {"predicted_r": float, "outcome": int} objects.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ReviewPair:
    predicted_r: float  # FSRS recall probability P(recall) in [0,1]
    outcome: int        # 1 = recalled correctly, 0 = forgot/wrong


@dataclass
class BinStats:
    bin_lower: float
    bin_upper: float
    mean_predicted: float
    fraction_correct: float
    n: int


@dataclass
class CalibrationResult:
    brier_score: float
    log_loss: float
    bins: list[BinStats]
    n_total: int

    def summary_table(self) -> str:
        header = f"{'Bin':>14}  {'Mean pred R':>11}  {'Obs frac correct':>16}  {'N':>6}"
        rows = [header, "-" * len(header)]
        for b in self.bins:
            label = f"[{b.bin_lower:.2f}, {b.bin_upper:.2f})"
            rows.append(
                f"{label:>14}  {b.mean_predicted:>11.3f}  {b.fraction_correct:>16.3f}  {b.n:>6}"
            )
        rows.append(
            f"\nBrier score : {self.brier_score:.5f}  (lower=better, 0=perfect)"
        )
        rows.append(f"Log-loss    : {self.log_loss:.5f}  (lower=better)")
        rows.append(f"N total     : {self.n_total}")
        return "\n".join(rows)


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

_EPS = 1e-15  # clip to avoid log(0)


def compute_calibration(
    pairs: Sequence[ReviewPair],
    n_bins: int = 10,
) -> CalibrationResult:
    """Bin by predicted R, compute observed fraction, Brier, log-loss."""
    if not pairs:
        raise ValueError("No review pairs provided.")

    brier_sum = 0.0
    log_loss_sum = 0.0

    bin_edges = [i / n_bins for i in range(n_bins + 1)]
    bin_preds: list[list[float]] = [[] for _ in range(n_bins)]
    bin_outcomes: list[list[int]] = [[] for _ in range(n_bins)]

    for p in pairs:
        r = float(p.predicted_r)
        o = int(p.outcome)
        if not (0.0 <= r <= 1.0):
            raise ValueError(f"predicted_r must be in [0,1], got {r!r}")
        if o not in (0, 1):
            raise ValueError(f"outcome must be 0 or 1, got {o!r}")

        # Brier and log-loss (over full dataset, not binned)
        brier_sum += (r - o) ** 2
        r_clip = max(_EPS, min(1 - _EPS, r))
        log_loss_sum += -(o * math.log(r_clip) + (1 - o) * math.log(1 - r_clip))

        # bin assignment (last bin catches r==1.0)
        idx = min(int(r * n_bins), n_bins - 1)
        bin_preds[idx].append(r)
        bin_outcomes[idx].append(o)

    n_total = len(pairs)
    brier = brier_sum / n_total
    log_loss = log_loss_sum / n_total

    bins: list[BinStats] = []
    for i in range(n_bins):
        n_bin = len(bin_preds[i])
        if n_bin == 0:
            continue
        mean_pred = sum(bin_preds[i]) / n_bin
        frac_correct = sum(bin_outcomes[i]) / n_bin
        bins.append(
            BinStats(
                bin_lower=bin_edges[i],
                bin_upper=bin_edges[i + 1],
                mean_predicted=mean_pred,
                fraction_correct=frac_correct,
                n=n_bin,
            )
        )

    return CalibrationResult(
        brier_score=brier,
        log_loss=log_loss,
        bins=bins,
        n_total=n_total,
    )


# ---------------------------------------------------------------------------
# Optional reliability diagram
# ---------------------------------------------------------------------------


def plot_reliability(result: CalibrationResult, output_path: Path | None = None) -> None:
    """Plot reliability diagram if matplotlib is available; silently skip otherwise."""
    try:
        import matplotlib.pyplot as plt  # type: ignore[import]
    except ImportError:
        print("[calibration] matplotlib not available — skipping plot.", file=sys.stderr)
        return

    mean_preds = [b.mean_predicted for b in result.bins]
    fracs = [b.fraction_correct for b in result.bins]

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([0, 1], [0, 1], "k--", label="perfect calibration")
    ax.scatter(mean_preds, fracs, s=60, zorder=5, label="observed")
    ax.set_xlabel("Mean predicted recall R")
    ax.set_ylabel("Fraction correct")
    ax.set_title(
        f"Reliability diagram  (Brier={result.brier_score:.4f}, LL={result.log_loss:.4f})"
    )
    ax.legend()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"[calibration] reliability diagram saved to {output_path}")
    else:
        plt.show()
    plt.close(fig)


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def load_csv(path: Path) -> list[ReviewPair]:
    pairs: list[ReviewPair] = []
    with path.open(newline="") as fh:
        sample = fh.read(512)
        fh.seek(0)
        has_header = csv.Sniffer().has_header(sample)
        reader = csv.reader(fh)
        if has_header:
            next(reader)
        for row in reader:
            if not row:
                continue
            pairs.append(ReviewPair(predicted_r=float(row[0]), outcome=int(row[1])))
    return pairs


def load_json(path: Path) -> list[ReviewPair]:
    raw = json.loads(path.read_text())
    return [ReviewPair(predicted_r=float(r["predicted_r"]), outcome=int(r["outcome"])) for r in raw]


# ---------------------------------------------------------------------------
# Synthetic fixtures
# ---------------------------------------------------------------------------


def make_well_calibrated_fixture(seed: int = 42, n: int = 2000) -> list[ReviewPair]:
    """Near-diagonal fixture: predicted R ≈ observed fraction correct."""
    import random
    rng = random.Random(seed)
    pairs: list[ReviewPair] = []
    for _ in range(n):
        r = rng.random()
        outcome = 1 if rng.random() < r else 0
        pairs.append(ReviewPair(predicted_r=r, outcome=outcome))
    return pairs


def make_overconfident_fixture(seed: int = 42, n: int = 2000) -> list[ReviewPair]:
    """Mis-calibrated: model always predicts high recall but true recall is ~50%."""
    import random
    rng = random.Random(seed)
    pairs: list[ReviewPair] = []
    for _ in range(n):
        r = rng.uniform(0.7, 0.95)
        outcome = 1 if rng.random() < 0.5 else 0
        pairs.append(ReviewPair(predicted_r=r, outcome=outcome))
    return pairs


def run_fixtures() -> None:
    print("=== FIXTURE 1: well-calibrated ===")
    pairs_good = make_well_calibrated_fixture(seed=42)
    result_good = compute_calibration(pairs_good)
    print(result_good.summary_table())
    plot_reliability(result_good)

    print("\n=== FIXTURE 2: mis-calibrated (overconfident) ===")
    pairs_bad = make_overconfident_fixture(seed=42)
    result_bad = compute_calibration(pairs_bad)
    print(result_bad.summary_table())
    plot_reliability(result_bad)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Calibration eval: Brier score + log-loss + reliability table."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", type=Path, help="CSV or JSON input file")
    group.add_argument("--fixture", action="store_true", help="Run synthetic fixtures")
    parser.add_argument(
        "--bins", type=int, default=10, help="Number of calibration bins (default 10)"
    )
    parser.add_argument(
        "--plot", type=Path, default=None, help="Save reliability diagram to this path"
    )
    args = parser.parse_args(argv)

    if args.fixture:
        run_fixtures()
        return

    path: Path = args.input
    if path.suffix.lower() == ".json":
        pairs = load_json(path)
    else:
        pairs = load_csv(path)

    result = compute_calibration(pairs, n_bins=args.bins)
    print(result.summary_table())
    plot_reliability(result, output_path=args.plot)


if __name__ == "__main__":
    main()
