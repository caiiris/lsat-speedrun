# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Pipeline report for Speedrun WP-12 card-check.

Runs generate → check → report the three counts with Wilson CIs.
Pre-set cutoffs are declared as module-level constants BEFORE any generation
is run.  Failing cards are blocked.

spec-ai §5 · D-SR15 · PRD AC 9.E(18)

CUTOFFS (declared before running — do not move below the pipeline call):
  WRONG_FACT_TOLERANCE   = 0      (0 wrong-fact cards tolerated; any → FAIL)
  MIN_USEFUL_RATE        = 0.60   (at least 60% of generated cards must be
                                   correct & useful; below → FAIL)

Confidence intervals: Wilson score interval, two-sided 95%.
CI note: with n ≤ 50 the CI half-width is wide (~±14pp at p=0.6); report
the interval honestly alongside the point estimate.
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

from tools.speedrun.cardcheck.checker import CardChecker, CheckResult, Verdict
from tools.speedrun.cardcheck.generator import CardGenerator, DeterministicStubClient, RawCard

# ---------------------------------------------------------------------------
# Pre-set cutoffs — DECLARED BEFORE RUNNING (spec-ai §5)
# ---------------------------------------------------------------------------

WRONG_FACT_TOLERANCE: int = 0
"""Maximum number of wrong-fact cards allowed.  Any wrong-fact card → FAIL."""

MIN_USEFUL_RATE: float = 0.60
"""Minimum fraction of generated cards that must be correct & useful."""

# ---------------------------------------------------------------------------
# Wilson score confidence interval
# ---------------------------------------------------------------------------

_Z95 = 1.96  # z-score for 95% confidence interval


def wilson_ci(k: int, n: int, z: float = _Z95) -> tuple[float, float]:
    """
    Wilson score interval for a proportion k/n.

    Returns (lower, upper) as fractions in [0, 1].
    Handles n == 0 by returning (0.0, 1.0).
    """
    if n == 0:
        return 0.0, 1.0
    p_hat = k / n
    denom = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denom
    margin = (z * math.sqrt(p_hat * (1 - p_hat) / n + z**2 / (4 * n**2))) / denom
    return max(0.0, center - margin), min(1.0, center + margin)


# ---------------------------------------------------------------------------
# Report dataclass
# ---------------------------------------------------------------------------


@dataclass
class PipelineReport:
    """Full report for one pipeline run."""

    n_generated: int
    n_correct_useful: int
    n_wrong_fact: int
    n_correct_bad_teaching: int
    n_duplicate: int

    # CIs (Wilson 95%)
    useful_rate: float
    useful_ci_lo: float
    useful_ci_hi: float
    wrong_rate: float
    wrong_ci_lo: float
    wrong_ci_hi: float

    # Gate results
    passed_wrong_fact_gate: bool
    passed_useful_rate_gate: bool
    overall_pass: bool

    # Blocked cards (those that failed any check)
    blocked: list[CheckResult]

    # Sanitization warnings
    sanitization_warnings: list[str]

    def __str__(self) -> str:
        lines = [
            "=" * 60,
            "  WP-12 Card-Check Pipeline Report",
            "=" * 60,
            f"  Cards generated:          {self.n_generated}",
            f"  Correct & useful:         {self.n_correct_useful}",
            f"  Wrong fact (WORST):       {self.n_wrong_fact}",
            f"  Correct, bad teaching:    {self.n_correct_bad_teaching}",
            f"  Duplicate (informational):{self.n_duplicate}",
            "",
            "  --- Rates & Wilson 95% CIs ---",
            f"  Useful rate:   {self.useful_rate:.1%}  "
            f"[{self.useful_ci_lo:.1%}, {self.useful_ci_hi:.1%}]",
            f"  Wrong rate:    {self.wrong_rate:.1%}  "
            f"[{self.wrong_ci_lo:.1%}, {self.wrong_ci_hi:.1%}]",
            "",
            "  --- Pre-set cutoffs (declared before run) ---",
            f"  Wrong-fact tolerance:     {WRONG_FACT_TOLERANCE}  "
            f"({'PASS' if self.passed_wrong_fact_gate else 'FAIL'})",
            f"  Min useful rate:          {MIN_USEFUL_RATE:.0%}  "
            f"({'PASS' if self.passed_useful_rate_gate else 'FAIL'})",
            "",
            f"  OVERALL: {'PASS ✓' if self.overall_pass else 'FAIL ✗'}",
            "",
            "  --- CI Note ---",
            f"  n={self.n_generated} is small; CI half-widths are wide (~±14pp at 60%).",
            "  Interpret point estimates with caution.",
        ]
        if self.sanitization_warnings:
            lines += ["", "  --- Sanitization Warnings ---"]
            for w in self.sanitization_warnings:
                lines.append(f"  ! {w}")
        if self.blocked:
            lines += ["", f"  --- Blocked Cards ({len(self.blocked)}) ---"]
            for r in self.blocked:
                lines.append(
                    f"  [{r.verdict.value}] Q: {r.card.question[:60]!r}"
                )
                for reason in r.reasons:
                    lines.append(f"      → {reason}")
        lines.append("=" * 60)
        return "\n".join(lines)

    def to_dict(self) -> dict[str, object]:
        return {
            "n_generated": self.n_generated,
            "n_correct_useful": self.n_correct_useful,
            "n_wrong_fact": self.n_wrong_fact,
            "n_correct_bad_teaching": self.n_correct_bad_teaching,
            "n_duplicate": self.n_duplicate,
            "useful_rate": self.useful_rate,
            "useful_ci": [self.useful_ci_lo, self.useful_ci_hi],
            "wrong_rate": self.wrong_rate,
            "wrong_ci": [self.wrong_ci_lo, self.wrong_ci_hi],
            "cutoffs": {
                "wrong_fact_tolerance": WRONG_FACT_TOLERANCE,
                "min_useful_rate": MIN_USEFUL_RATE,
            },
            "passed_wrong_fact_gate": self.passed_wrong_fact_gate,
            "passed_useful_rate_gate": self.passed_useful_rate_gate,
            "overall_pass": self.overall_pass,
            "blocked_count": len(self.blocked),
            "sanitization_warnings": self.sanitization_warnings,
        }


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------


def run_pipeline(
    source_path: Path,
    gold_path: Path,
    n_generate: int = 30,
    client: object | None = None,
) -> tuple[PipelineReport, list[RawCard]]:
    """
    Run the full generate → check → report pipeline.

    Parameters:
        source_path: Path to the cited source text file.
        gold_path: Path to the 50-item gold_set.json (used to load the
                   source reference but NOT to feed answers into the generator).
        n_generate: How many cards to request from the generator.
        client: LLMClient instance; defaults to DeterministicStubClient.

    Returns:
        (report, accepted_cards)

    Blocked cards are included in ``report.blocked`` but NOT in
    ``accepted_cards``.
    """
    # Validate gold set integrity first.
    gold_items = CardGenerator.load_gold_set(gold_path)
    if len(gold_items) != 50:
        raise ValueError(
            f"Gold set integrity check failed: expected 50 items, "
            f"got {len(gold_items)}."
        )

    # Generate.
    gen = CardGenerator(
        source_path=source_path,
        client=client,  # type: ignore[arg-type]
    )
    cards, warnings = gen.generate(n=n_generate)

    # Load source for checker.
    from tools.speedrun.cardcheck.injection_guard import sanitize
    raw_source = source_path.read_text(encoding="utf-8")
    clean_source = sanitize(raw_source).text

    # Check.
    checker = CardChecker(source_text=clean_source)
    results = checker.check_all(cards)
    counts = checker.summary(results)

    n = len(results)
    n_useful = counts["correct_useful"]
    n_wrong = counts["wrong_fact"]
    n_bad = counts["correct_bad_teaching"]
    n_dup = counts["duplicate"]

    useful_rate = n_useful / n if n else 0.0
    wrong_rate = n_wrong / n if n else 0.0

    useful_ci = wilson_ci(n_useful, n)
    wrong_ci = wilson_ci(n_wrong, n)

    passed_wrong = n_wrong <= WRONG_FACT_TOLERANCE
    passed_useful = useful_rate >= MIN_USEFUL_RATE
    overall_pass = passed_wrong and passed_useful

    blocked = [r for r in results if not r.passed]
    accepted = [r.card for r in results if r.passed]

    report = PipelineReport(
        n_generated=n,
        n_correct_useful=n_useful,
        n_wrong_fact=n_wrong,
        n_correct_bad_teaching=n_bad,
        n_duplicate=n_dup,
        useful_rate=useful_rate,
        useful_ci_lo=useful_ci[0],
        useful_ci_hi=useful_ci[1],
        wrong_rate=wrong_rate,
        wrong_ci_lo=wrong_ci[0],
        wrong_ci_hi=wrong_ci[1],
        passed_wrong_fact_gate=passed_wrong,
        passed_useful_rate_gate=passed_useful,
        overall_pass=overall_pass,
        blocked=blocked,
        sanitization_warnings=warnings,
    )
    return report, accepted


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    base = Path(__file__).parent
    source_path = base / "logic_meta_vocab.txt"
    gold_path = base / "gold_set.json"

    print(f"Source: {source_path}")
    print(f"Gold set: {gold_path}")
    print(f"Pre-set cutoffs: wrong_fact_tolerance={WRONG_FACT_TOLERANCE}, "
          f"min_useful_rate={MIN_USEFUL_RATE:.0%}")
    print()

    report, accepted = run_pipeline(
        source_path=source_path,
        gold_path=gold_path,
        n_generate=30,
    )

    print(report)
    print()
    print(f"Accepted cards: {len(accepted)}")

    # Optionally dump JSON report.
    if "--json" in sys.argv:
        out = base / "pipeline_report.json"
        out.write_text(json.dumps(report.to_dict(), indent=2))
        print(f"JSON report written to {out}")

    sys.exit(0 if report.overall_pass else 1)


if __name__ == "__main__":
    main()
