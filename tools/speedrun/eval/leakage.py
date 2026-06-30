# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Leakage eval (spec-measurement §7, PRD §9.G AC-26).

Purpose: scan training/item-pool texts for test-set contamination.

Two detection methods (applied in order):
  1. Exact match  — SHA-256 hash; catches identical copies.
  2. Near-duplicate — cosine similarity on character n-gram TF vectors
     (deterministic fallback that runs without any model).
     When an embedding provider is injected, it is called instead; the
     interface contract is EmbeddingProvider below.

If any hit is found, the affected score MUST be zeroed (spec-measurement §7).

Usage:
  python -m tools.speedrun.eval.leakage --train train.json --test test.json
  python -m tools.speedrun.eval.leakage --fixture

JSON schema:
  [{"id": "t001", "text": "Which one of the following..."}, ...]

Programmatic use:
  from tools.speedrun.eval.leakage import LeakageScanner, TextItem
  scanner = LeakageScanner(threshold=0.85)
  report = scanner.scan(train_items, test_items)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, Sequence


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class TextItem:
    item_id: str
    text: str


@dataclass
class LeakHit:
    test_id: str
    train_id: str
    similarity: float         # 1.0 = exact hash match; <1.0 = near-duplicate
    match_type: str           # "exact" | "near_duplicate"


@dataclass
class LeakageReport:
    hits: list[LeakHit]
    n_train: int
    n_test: int
    threshold: float
    score_zeroed: bool        # True if any hit was found (spec §7)

    @property
    def clean(self) -> bool:
        return len(self.hits) == 0

    def summary(self) -> str:
        lines = [
            f"Leakage scan: {self.n_train} train / {self.n_test} test items  "
            f"(threshold={self.threshold:.2f})",
        ]
        if self.clean:
            lines.append("Result: CLEAN — no leakage detected.")
        else:
            lines.append(
                f"Result: CONTAMINATED — {len(self.hits)} hit(s) found.  "
                "Affected scores must be zeroed."
            )
            header = f"  {'test_id':>10}  {'train_id':>10}  {'sim':>5}  {'type':>14}"
            lines.append(header)
            for h in self.hits:
                lines.append(
                    f"  {h.test_id:>10}  {h.train_id:>10}  {h.similarity:>5.3f}  {h.match_type:>14}"
                )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Embedding interface + deterministic fallback
# ---------------------------------------------------------------------------


class EmbeddingProvider(Protocol):
    """
    Optional embedding backend.  Must be deterministic given the same text.
    If not provided, the scanner uses char-ngram TF cosine (see below).
    """

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per text."""
        ...


def _tokenize_ngrams(text: str, n: int = 3) -> list[str]:
    """Lowercased char n-grams over alphanumeric runs."""
    cleaned = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    tokens = cleaned.split()
    ngrams: list[str] = []
    for tok in tokens:
        if len(tok) < n:
            ngrams.append(tok)
        else:
            for i in range(len(tok) - n + 1):
                ngrams.append(tok[i : i + n])
    return ngrams


def _tfidf_vector(text: str, n: int = 3) -> Counter[str]:
    return Counter(_tokenize_ngrams(text, n))


def _cosine(a: Counter[str], b: Counter[str]) -> float:
    dot = sum(a[k] * b[k] for k in a if k in b)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _embed_ngram(texts: list[str]) -> list[Counter[str]]:
    return [_tfidf_vector(t) for t in texts]


def _cosine_vectors(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


class LeakageScanner:
    """
    Scans test items against training items for exact and near-duplicate leakage.

    Parameters
    ----------
    threshold : float
        Cosine similarity threshold for near-duplicate detection (default 0.85).
        Tune lower to be more aggressive, higher to reduce false positives.
    embedding_provider : EmbeddingProvider | None
        Optional embedding model.  When None, char-3gram TF cosine is used
        (deterministic, no model dependency).
    ngram_n : int
        Character n-gram length for the fallback vectorizer (default 3).
    """

    def __init__(
        self,
        threshold: float = 0.85,
        embedding_provider: EmbeddingProvider | None = None,
        ngram_n: int = 3,
    ) -> None:
        self.threshold = threshold
        self.embedding_provider = embedding_provider
        self.ngram_n = ngram_n

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.strip().encode()).hexdigest()

    def scan(
        self,
        train_items: Sequence[TextItem],
        test_items: Sequence[TextItem],
    ) -> LeakageReport:
        hits: list[LeakHit] = []

        # --- Phase 1: exact hash match ---
        train_hashes: dict[str, str] = {
            self._hash(item.text): item.item_id for item in train_items
        }
        test_after_exact: list[TextItem] = []

        for test_item in test_items:
            h = self._hash(test_item.text)
            if h in train_hashes:
                hits.append(
                    LeakHit(
                        test_id=test_item.item_id,
                        train_id=train_hashes[h],
                        similarity=1.0,
                        match_type="exact",
                    )
                )
            else:
                test_after_exact.append(test_item)

        # --- Phase 2: near-duplicate similarity ---
        if test_after_exact:
            if self.embedding_provider is not None:
                all_texts = [i.text for i in train_items] + [i.text for i in test_after_exact]
                all_vecs = self.embedding_provider.encode(all_texts)
                train_vecs = all_vecs[: len(train_items)]
                test_vecs = all_vecs[len(train_items) :]

                for ti, test_item in enumerate(test_after_exact):
                    best_sim = 0.0
                    best_train_id = ""
                    for ti2, train_item in enumerate(train_items):
                        sim = _cosine_vectors(test_vecs[ti], train_vecs[ti2])
                        if sim > best_sim:
                            best_sim = sim
                            best_train_id = train_item.item_id
                    if best_sim >= self.threshold:
                        hits.append(
                            LeakHit(
                                test_id=test_item.item_id,
                                train_id=best_train_id,
                                similarity=best_sim,
                                match_type="near_duplicate",
                            )
                        )
            else:
                # Deterministic fallback: char-ngram cosine
                train_counters = _embed_ngram([i.text for i in train_items])
                test_counters = _embed_ngram([i.text for i in test_after_exact])

                for ti, test_item in enumerate(test_after_exact):
                    best_sim = 0.0
                    best_train_id = ""
                    for ti2, train_item in enumerate(train_items):
                        sim = _cosine(test_counters[ti], train_counters[ti2])
                        if sim > best_sim:
                            best_sim = sim
                            best_train_id = train_item.item_id
                    if best_sim >= self.threshold:
                        hits.append(
                            LeakHit(
                                test_id=test_item.item_id,
                                train_id=best_train_id,
                                similarity=best_sim,
                                match_type="near_duplicate",
                            )
                        )

        return LeakageReport(
            hits=hits,
            n_train=len(train_items),
            n_test=len(test_items),
            threshold=self.threshold,
            score_zeroed=len(hits) > 0,
        )


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def load_json(path: Path) -> list[TextItem]:
    raw = json.loads(path.read_text())
    return [TextItem(item_id=str(r["id"]), text=str(r["text"])) for r in raw]


# ---------------------------------------------------------------------------
# Synthetic fixture with a planted near-duplicate
# ---------------------------------------------------------------------------


def make_fixture() -> tuple[list[TextItem], list[TextItem]]:
    """
    Returns (train, test) with:
    - One exact duplicate (item_id "leak_exact"): same text in both.
    - One near-duplicate (item_id "leak_near"): train text with minor wording change.
    - Several clean items that should NOT be flagged.
    """
    train = [
        TextItem(
            "tr001",
            "Which one of the following most accurately expresses the main conclusion "
            "of the argument above?",
        ),
        TextItem(
            "tr002",
            "The argument assumes without justification that the observed correlation "
            "between exercise and mood is not caused by a third factor.",
        ),
        TextItem(
            "tr003",
            "If all mammals are warm-blooded and all whales are mammals, "
            "then all whales are warm-blooded.",
        ),
        TextItem(
            "tr004",
            "An editorial claims that the new policy will reduce crime; "
            "however the statistics cited are from a single city over six months.",
        ),
        # planted exact duplicate source
        TextItem(
            "tr005",
            "The politician argued that since voter turnout increased, "
            "public support for the new law must also have increased.",
        ),
        # planted near-duplicate source (minor edit in test below)
        TextItem(
            "tr006",
            "Researchers found that students who slept eight hours performed better "
            "on memory tests than those who slept six hours.",
        ),
    ]

    test = [
        # clean items
        TextItem(
            "te001",
            "Which of the following, if true, most strengthens the argument?",
        ),
        TextItem(
            "te002",
            "The senator's position is inconsistent because she previously opposed "
            "the very type of legislation she now endorses.",
        ),
        # exact duplicate of tr005
        TextItem(
            "leak_exact",
            "The politician argued that since voter turnout increased, "
            "public support for the new law must also have increased.",
        ),
        # near-duplicate of tr006 — same sentence with a single minor edit ("only" inserted).
        # Note: the char-ngram fallback is designed for minor-edit near-copies; full
        # synonym paraphrase (e.g. "students" → "pupils") yields lower cosine and
        # requires an EmbeddingProvider for reliable detection.
        TextItem(
            "leak_near",
            "Researchers found that students who slept eight hours performed better "
            "on memory tests than those who slept only six hours.",
        ),
    ]
    return train, test


def run_fixture() -> None:
    print("=== FIXTURE: leakage scan (planted exact + near duplicate) ===")
    train, test = make_fixture()
    scanner = LeakageScanner(threshold=0.85)
    report = scanner.scan(train, test)
    print(report.summary())
    assert not report.clean, "Fixture must detect at least one leak"
    assert any(h.test_id == "leak_exact" and h.match_type == "exact" for h in report.hits), \
        "Exact duplicate not detected"
    assert any(h.test_id == "leak_near" for h in report.hits), \
        "Near-duplicate not detected"
    print("\nAll fixture assertions passed.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Leakage eval: detect exact and near-duplicate contamination."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--fixture", action="store_true", help="Run synthetic fixture")
    group.add_argument("--train", type=Path, help="Training set JSON")
    parser.add_argument("--test", type=Path, help="Test set JSON (required with --train)")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="Cosine similarity threshold for near-duplicates (default 0.85)",
    )
    args = parser.parse_args(argv)

    if args.fixture:
        run_fixture()
        return

    if args.test is None:
        parser.error("--test is required when --train is specified")

    train_items = load_json(args.train)
    test_items = load_json(args.test)
    scanner = LeakageScanner(threshold=args.threshold)
    report = scanner.scan(train_items, test_items)
    print(report.summary())
    if not report.clean:
        import sys
        sys.exit(1)


if __name__ == "__main__":
    main()
