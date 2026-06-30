# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Tagging evaluation for Speedrun WP-11.

Computes per-axis accuracy + macro-F1 for three taggers:
  (1) AI tagger  — ``ItemTagPipeline`` with ``DeterministicStubClient``
  (2) Keyword    — ``KeywordBaseline``
  (3) Vector kNN — ``VectorKNNBaseline`` with char-3gram cosine

Evaluation is on the 10-item ``gold_labels.json`` held-out set.  The vector
baseline uses leave-one-out kNN (item excluded from its own neighbors).

Metrics:
  - Type axis (single-label): accuracy + F1 (= accuracy for single label)
  - Skill axis (multi-label): macro-F1 across skill labels present in gold
  - Trap axis (multi-label): macro-F1 across trap labels present in gold

Usage (stdout report):
    python -m tools.speedrun.tagging.eval

Programmatic use:
    from tools.speedrun.tagging.eval import run_eval, EvalReport
    report = run_eval()  # deterministic; no LLM required
    print(report.format_table())

spec-ai §4, AC-2 · D-SR14 (beats keyword + vector)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from tools.speedrun.tagging.baselines import (
    GoldItem,
    KeywordBaseline,
    VectorKNNBaseline,
)
from tools.speedrun.tagging.tagger import (
    DeterministicStubClient,
    ItemInput,
    ItemTagPipeline,
    StemClassifier,
)
from tools.speedrun.tagging.taxonomy_loader import load_taxonomy

GOLD_PATH = Path(__file__).parent / "gold_labels.json"


# ---------------------------------------------------------------------------
# Gold set loader
# ---------------------------------------------------------------------------


def load_gold(path: Path = GOLD_PATH) -> list[dict]:
    """Load and return the list of gold-labeled items."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["items"]


def gold_to_item_input(g: dict) -> ItemInput:
    return ItemInput(
        item_id=g["id"],
        stimulus=g["stimulus"],
        stem=g["stem"],
        choices=g["choices"],
        correct_choice=g["correct_choice"],
    )


def gold_to_knn_item(g: dict) -> GoldItem:
    return GoldItem(
        item_id=g["id"],
        text=f"{g['stimulus']} {g['stem']}",
        type_tags=[g["gold_type"]],
        skill_tags=list(g["gold_skills"]),
        trap_tags=list(g["gold_traps"]),
    )


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------


@dataclass
class LabelMetrics:
    """Per-label precision/recall/F1."""

    label: str
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) > 0 else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


def compute_multilabel_metrics(
    predictions: list[list[str]],
    gold: list[list[str]],
) -> dict[str, LabelMetrics]:
    """
    Compute per-label TP/FP/FN across a list of (predicted, gold) label sets.

    Only labels appearing in any gold set are included (unknown predicted
    labels are counted as FPs without a corresponding metric entry).
    """
    # Collect all gold labels
    all_gold_labels: set[str] = set()
    for g in gold:
        all_gold_labels.update(g)

    metrics: dict[str, LabelMetrics] = {lbl: LabelMetrics(lbl) for lbl in all_gold_labels}

    for pred_set, gold_set in zip(predictions, gold):
        ps = set(pred_set)
        gs = set(gold_set)

        for lbl in all_gold_labels:
            in_pred = lbl in ps
            in_gold = lbl in gs
            m = metrics[lbl]
            if in_pred and in_gold:
                m.tp += 1
            elif in_pred and not in_gold:
                m.fp += 1
            elif not in_pred and in_gold:
                m.fn += 1

    return metrics


def macro_f1(metrics: dict[str, LabelMetrics]) -> float:
    """Macro-F1: average per-label F1 (only over labels present in gold)."""
    if not metrics:
        return 0.0
    return sum(m.f1 for m in metrics.values()) / len(metrics)


def accuracy(predictions: list[str], gold: list[str]) -> float:
    """Exact-match accuracy for single-label predictions."""
    if not predictions:
        return 0.0
    return sum(p == g for p, g in zip(predictions, gold)) / len(predictions)


# ---------------------------------------------------------------------------
# Per-method evaluation runner
# ---------------------------------------------------------------------------


@dataclass
class AxisResult:
    """Metrics for one axis (type / skill / trap) for one method."""

    accuracy: float = 0.0    # meaningful for type (single-label); else 0
    macro_f1: float = 0.0
    per_label: dict[str, LabelMetrics] = field(default_factory=dict)


@dataclass
class MethodResult:
    """All-axis results for one tagging method."""

    name: str
    type_axis: AxisResult = field(default_factory=AxisResult)
    skill_axis: AxisResult = field(default_factory=AxisResult)
    trap_axis: AxisResult = field(default_factory=AxisResult)


def _run_ai_tagger(gold_items: list[dict]) -> MethodResult:
    """Run the AI tagger (DeterministicStubClient) on all gold items."""
    pipeline = ItemTagPipeline(
        client=DeterministicStubClient(),
        taxonomy=load_taxonomy(),
    )
    type_preds: list[str] = []
    skill_preds: list[list[str]] = []
    trap_preds: list[list[str]] = []

    for g in gold_items:
        tagged = pipeline.tag(gold_to_item_input(g))
        type_preds.append(tagged.type_tags[0] if tagged.type_tags else "")
        skill_preds.append(tagged.skill_tags)
        trap_preds.append(tagged.trap_tags)

    type_gold = [g["gold_type"] for g in gold_items]
    skill_gold = [list(g["gold_skills"]) for g in gold_items]
    trap_gold = [list(g["gold_traps"]) for g in gold_items]

    skill_metrics = compute_multilabel_metrics(skill_preds, skill_gold)
    trap_metrics = compute_multilabel_metrics(trap_preds, trap_gold)

    type_acc = accuracy(type_preds, type_gold)
    type_met = compute_multilabel_metrics(
        [[t] for t in type_preds], [[t] for t in type_gold]
    )

    return MethodResult(
        name="AI Tagger (stub)",
        type_axis=AxisResult(
            accuracy=type_acc,
            macro_f1=macro_f1(type_met),
            per_label=type_met,
        ),
        skill_axis=AxisResult(
            accuracy=0.0,
            macro_f1=macro_f1(skill_metrics),
            per_label=skill_metrics,
        ),
        trap_axis=AxisResult(
            accuracy=0.0,
            macro_f1=macro_f1(trap_metrics),
            per_label=trap_metrics,
        ),
    )


def _run_keyword_baseline(gold_items: list[dict]) -> MethodResult:
    """Run the keyword baseline on all gold items."""
    baseline = KeywordBaseline()
    stem_clf = StemClassifier()
    type_preds: list[str] = []
    skill_preds: list[list[str]] = []
    trap_preds: list[list[str]] = []

    for g in gold_items:
        item = gold_to_item_input(g)
        question_type = stem_clf.classify(item.stem)
        proposal = baseline.propose_tags(item, question_type)
        type_preds.append(question_type)
        skill_preds.append(proposal.skill_tags)
        trap_preds.append(proposal.trap_tags)

    type_gold = [g["gold_type"] for g in gold_items]
    skill_gold = [list(g["gold_skills"]) for g in gold_items]
    trap_gold = [list(g["gold_traps"]) for g in gold_items]

    skill_metrics = compute_multilabel_metrics(skill_preds, skill_gold)
    trap_metrics = compute_multilabel_metrics(trap_preds, trap_gold)
    type_acc = accuracy(type_preds, type_gold)
    type_met = compute_multilabel_metrics(
        [[t] for t in type_preds], [[t] for t in type_gold]
    )

    return MethodResult(
        name="Keyword Baseline",
        type_axis=AxisResult(
            accuracy=type_acc,
            macro_f1=macro_f1(type_met),
            per_label=type_met,
        ),
        skill_axis=AxisResult(
            accuracy=0.0,
            macro_f1=macro_f1(skill_metrics),
            per_label=skill_metrics,
        ),
        trap_axis=AxisResult(
            accuracy=0.0,
            macro_f1=macro_f1(trap_metrics),
            per_label=trap_metrics,
        ),
    )


def _run_vector_baseline(gold_items: list[dict]) -> MethodResult:
    """Run the vector kNN baseline (leave-one-out) on all gold items."""
    knn = VectorKNNBaseline(k=3)
    knn_items = [gold_to_knn_item(g) for g in gold_items]
    knn.fit(knn_items)

    type_preds: list[str] = []
    skill_preds: list[list[str]] = []
    trap_preds: list[list[str]] = []

    for g in gold_items:
        item = gold_to_item_input(g)
        type_preds.append(knn.predict_type(item))
        proposal = knn.propose_tags(item, "")
        skill_preds.append(proposal.skill_tags)
        trap_preds.append(proposal.trap_tags)

    type_gold = [g["gold_type"] for g in gold_items]
    skill_gold = [list(g["gold_skills"]) for g in gold_items]
    trap_gold = [list(g["gold_traps"]) for g in gold_items]

    skill_metrics = compute_multilabel_metrics(skill_preds, skill_gold)
    trap_metrics = compute_multilabel_metrics(trap_preds, trap_gold)
    type_acc = accuracy(type_preds, type_gold)
    type_met = compute_multilabel_metrics(
        [[t] for t in type_preds], [[t] for t in type_gold]
    )

    return MethodResult(
        name="Vector kNN (char-3gram)",
        type_axis=AxisResult(
            accuracy=type_acc,
            macro_f1=macro_f1(type_met),
            per_label=type_met,
        ),
        skill_axis=AxisResult(
            accuracy=0.0,
            macro_f1=macro_f1(skill_metrics),
            per_label=skill_metrics,
        ),
        trap_axis=AxisResult(
            accuracy=0.0,
            macro_f1=macro_f1(trap_metrics),
            per_label=trap_metrics,
        ),
    )


# ---------------------------------------------------------------------------
# Top-level eval runner + report
# ---------------------------------------------------------------------------


@dataclass
class EvalReport:
    """Results from all three methods."""

    ai: MethodResult
    keyword: MethodResult
    vector: MethodResult
    n_items: int

    def ai_beats_both(self) -> bool:
        """
        True if the AI tagger has higher skill macro-F1 AND trap macro-F1
        than both baselines.  This is the spec-ai §4 AC-2 criterion.
        """
        ai_skill = self.ai.skill_axis.macro_f1
        ai_trap = self.ai.trap_axis.macro_f1
        kw_skill = self.keyword.skill_axis.macro_f1
        kw_trap = self.keyword.trap_axis.macro_f1
        vec_skill = self.vector.skill_axis.macro_f1
        vec_trap = self.vector.trap_axis.macro_f1
        return (ai_skill >= kw_skill and ai_skill >= vec_skill and
                ai_trap >= kw_trap and ai_trap >= vec_trap)

    def format_table(self) -> str:
        """Return a side-by-side comparison table (plain text)."""
        sep = "-" * 72

        def row(name: str, m: MethodResult) -> str:
            ta = m.type_axis
            sa = m.skill_axis
            ra = m.trap_axis
            return (
                f"  {name:<26}"
                f"  {ta.accuracy:>6.2%}  {ta.macro_f1:>6.2%}"
                f"  {sa.macro_f1:>8.2%}"
                f"  {ra.macro_f1:>7.2%}"
            )

        lines = [
            "",
            "WP-11 Tagging Eval — side-by-side (spec-ai §4 AC-2, D-SR14)",
            sep,
            f"  {'Method':<26}  {'Type Acc':>8}  {'Type F1':>7}  {'Skill F1':>8}  {'Trap F1':>7}",
            sep,
            row("AI Tagger (stub)", self.ai),
            row("Keyword Baseline", self.keyword),
            row("Vector kNN (char-3gram)", self.vector),
            sep,
            f"  n_items={self.n_items}  (synthetic gold set; real eval needs ≥50 items + real LLM)",
            f"  AI beats both baselines on skill+trap: {'YES ✓' if self.ai_beats_both() else 'NO ✗  ← BUG'}",
            "",
        ]

        # Per-label detail for skill
        lines.append("  Skill axis — per-label F1:")
        all_skill_labels = sorted(
            set(self.ai.skill_axis.per_label)
            | set(self.keyword.skill_axis.per_label)
            | set(self.vector.skill_axis.per_label)
        )
        for lbl in all_skill_labels:
            ai_f = self.ai.skill_axis.per_label.get(lbl, LabelMetrics(lbl)).f1
            kw_f = self.keyword.skill_axis.per_label.get(lbl, LabelMetrics(lbl)).f1
            vc_f = self.vector.skill_axis.per_label.get(lbl, LabelMetrics(lbl)).f1
            lines.append(f"    {lbl:<30}  AI={ai_f:.2f}  KW={kw_f:.2f}  VEC={vc_f:.2f}")

        lines.append("")
        lines.append("  Trap axis — per-label F1:")
        all_trap_labels = sorted(
            set(self.ai.trap_axis.per_label)
            | set(self.keyword.trap_axis.per_label)
            | set(self.vector.trap_axis.per_label)
        )
        for lbl in all_trap_labels:
            ai_f = self.ai.trap_axis.per_label.get(lbl, LabelMetrics(lbl)).f1
            kw_f = self.keyword.trap_axis.per_label.get(lbl, LabelMetrics(lbl)).f1
            vc_f = self.vector.trap_axis.per_label.get(lbl, LabelMetrics(lbl)).f1
            lines.append(f"    {lbl:<30}  AI={ai_f:.2f}  KW={kw_f:.2f}  VEC={vc_f:.2f}")

        lines.append("")
        lines.append("  Limitations (see WP-11-log.md):")
        lines.append("  - Stub ≠ real LLM; skill/trap heuristics are approximate.")
        lines.append("  - Gold set is synthetic (n=10); real eval needs n≥50 + real LLM (B012).")
        lines.append("  - trap::abstraction not in trap catalog (axis-2 skill, not trap).")
        lines.append(sep)
        return "\n".join(lines)


def run_eval(gold_path: Path = GOLD_PATH) -> EvalReport:
    """
    Run the full evaluation and return an :class:`EvalReport`.

    Fully deterministic — no LLM required.
    """
    gold_items = load_gold(gold_path)
    ai_result = _run_ai_tagger(gold_items)
    kw_result = _run_keyword_baseline(gold_items)
    vec_result = _run_vector_baseline(gold_items)
    return EvalReport(
        ai=ai_result,
        keyword=kw_result,
        vector=vec_result,
        n_items=len(gold_items),
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    report = run_eval()
    print(report.format_table())
    import sys
    sys.exit(0 if report.ai_beats_both() else 1)
