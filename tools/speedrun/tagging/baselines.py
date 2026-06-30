# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Keyword and vector baselines for WP-11 tagging evaluation.

Two baselines are required by spec-ai §4 to validate that the AI tagger
beats simpler alternatives:

(a) ``KeywordBaseline`` — lexicon rules on stem+stimulus **only** (no choice
    text, no question-type context).  Uses exact key_indicators from the
    taxonomy for skills and a limited trap heuristic on stimulus text.

(b) ``VectorKNNBaseline`` — char-3gram TF-cosine kNN over item embeddings
    (the ``EmbeddingProvider`` protocol).  Runs fully deterministic via
    ``CharNgramProvider``; a real sentence-embedding model can be injected.
    Uses leave-one-out evaluation when training = test set (gold-only mode).

Neither baseline scans choice texts for trap detection — that is the AI
tagger's primary advantage on the trap axis.

spec-ai §4 · D-SR14 · D-SR22 (char-3gram fallback) · brainlift J.2/K.4

DESIGN DECISION (see WP-11-log.md L-D2):
  The keyword baseline uses an extended causal lexicon (beyond the 6 exact
  taxonomy key_indicators) to be a fair but weaker comparison — it represents
  what a competent keyword engineer would build, not the minimum possible.
  The AI stub still beats it via question-type context + choice scanning.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from tools.speedrun.tagging.tagger import (
    ItemInput,
    LLMTagProposal,
    StemClassifier,
    TaggerLLMClient,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


_STOP_WORDS = frozenset(
    "a an the is are was were be been being have has had do does did "
    "will would could should may might shall of in on at to for with "
    "and or but not it its this that these those if then by from up "
    "what which who when where why how very also just already still "
    "than such more most some all any no none each every".split()
)


def _content_words(text: str) -> frozenset[str]:
    tokens = re.findall(r"[a-z]+", text.lower())
    return frozenset(t for t in tokens if t not in _STOP_WORDS and len(t) > 2)


# ---------------------------------------------------------------------------
# (a) Keyword baseline
# ---------------------------------------------------------------------------

# Extended causal lexicon — a "competent keyword engineer" would include these
# common causal expressions, not just the 6 exact taxonomy key_indicators.
_KW_CAUSAL_RE = re.compile(
    r"\b(causes?|cause[sd]|led? to|leads? to|results? in|due to|because of|"
    r"effect of|responsible for|reduces?|reduction|increases?|produces?|"
    r"creates?|prevents?|decreases?|consequence|outcome)\b",
    re.I,
)

# Conditional lexicon — exact taxonomy key_indicators only
_KW_CONDITIONAL_RE = re.compile(
    r"\b(if\b|only if|unless|whenever|all\b.{0,30}who|all\b.{0,30}that|"
    r"none\b|no\b\s+\w+\s+(?:is|are|was|were|can|will)|every\b)\b",
    re.I,
)

# Quantifier lexicon (stimulus-level, for inference questions)
_KW_QUANTIFIER_RE = re.compile(
    r"\b(some of|most of|all of|none of|a few|several|majority|minority|"
    r"at least one|no\b\s+\w+\s+(?:is|are|have|has))\b",
    re.I,
)

# Conclusion indicator (strict — keyword baseline only)
_KW_CONCLUSION_RE = re.compile(
    r"\b(therefore|thus|hence|so\b|clearly|consequently|it follows|"
    r"must be|which means|since\b|shows? that|as a result|in conclusion)\b",
    re.I,
)

# Trap detection on stimulus only (weak — stimulus rarely reveals trap type)
_KW_TRAP_EXTREME_RE = re.compile(
    r"\b(always|never|all\b|none\b|every\b|no one|everyone|will always|"
    r"will never|must always|under any circumstances)\b",
    re.I,
)


class KeywordBaseline:
    """
    Keyword-rule baseline tagger.

    Implements :class:`TaggerLLMClient` so it can be swapped into
    :class:`~tools.speedrun.tagging.tagger.ItemTagPipeline` for eval.

    Key limitation (by design — this IS the baseline):
    - Only reads **stem + stimulus** (no choice text).
    - No question-type context used for skill disambiguation.
    - Trap detection from stimulus is extremely weak.

    These limitations are what the AI tagger improves upon.
    """

    client_id: str = "keyword-baseline-v1"

    def propose_tags(
        self,
        item: ItemInput,
        question_type: str,
    ) -> LLMTagProposal:
        skill_tags = self._predict_skills(item)
        trap_tags = self._predict_traps(item)
        return LLMTagProposal(skill_tags=skill_tags, trap_tags=trap_tags)

    def _predict_skills(self, item: ItemInput) -> list[str]:
        text = f"{item.stem} {item.stimulus}"
        skills: set[str] = set()

        if _KW_CONCLUSION_RE.search(text):
            skills.add("skill::conclusion-id")

        if _KW_CONDITIONAL_RE.search(text):
            skills.add("skill::conditional")

        if _KW_CAUSAL_RE.search(text):
            skills.add("skill::causal")

        if _KW_QUANTIFIER_RE.search(text):
            skills.add("skill::quantifier")

        # Always emit conclusion-id as the default anchor skill
        skills.add("skill::conclusion-id")

        return sorted(skills)

    def _predict_traps(self, item: ItemInput) -> list[str]:
        """Trap detection from stimulus text only — intentionally weak."""
        text = item.stimulus
        traps: set[str] = set()

        if _KW_TRAP_EXTREME_RE.search(text):
            traps.add("trap::too-extreme")

        return sorted(traps)


# ---------------------------------------------------------------------------
# (b) Vector kNN baseline
# ---------------------------------------------------------------------------


@runtime_checkable
class EmbeddingProvider(Protocol):
    """
    Protocol for text embedding backends.

    Implementors receive a list of texts and return a corresponding list of
    dense float vectors (one per text).  All vectors must have the same
    dimension.

    Wiring a real model (e.g. ``sentence-transformers``):
    1. Implement this protocol.
    2. Pass the instance to :class:`VectorKNNBaseline`.
    """

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one dense vector per text in *texts*."""
        ...


class CharNgramProvider:
    """
    Deterministic char-n-gram TF embedding provider (no model required).

    Builds a vocabulary over ALL texts passed in a single :meth:`embed` call,
    then returns dense TF vectors of dimension ``|vocab|``.

    This is identical in spirit to the char-3gram cosine fallback used in
    ``tools/speedrun/eval/leakage.py`` (D-SR22) — implemented independently
    to avoid cross-module coupling.

    ``n=3`` is the default (char trigrams).  Lower ``n`` is coarser;
    higher ``n`` is too sparse for short texts.
    """

    def __init__(self, n: int = 3) -> None:
        self.n = n

    def _ngrams(self, text: str) -> Counter[str]:
        t = text.lower()
        return Counter(t[i : i + self.n] for i in range(max(0, len(t) - self.n + 1)))

    def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Build a shared vocabulary then return TF vectors.

        The vocabulary is built fresh on every call (stateless).  This means
        the embedding dimension depends on the texts passed — consistent for a
        single call, but not cross-call comparable.  For kNN evaluation, always
        embed the full corpus in one call.
        """
        counters = [self._ngrams(t) for t in texts]

        # Build vocabulary over all texts
        all_ngrams: set[str] = set()
        for c in counters:
            all_ngrams.update(c.keys())
        vocab = {ng: i for i, ng in enumerate(sorted(all_ngrams))}
        dim = len(vocab)

        # Build TF vectors
        vectors: list[list[float]] = []
        for c in counters:
            total = max(sum(c.values()), 1)
            vec = [0.0] * dim
            for ng, cnt in c.items():
                vec[vocab[ng]] = cnt / total
            vectors.append(vec)
        return vectors


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two same-length float vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass
class GoldItem:
    """A gold-labeled item used as a kNN training point."""

    item_id: str
    text: str          # stimulus + stem (the embedding input)
    type_tags: list[str]
    skill_tags: list[str]
    trap_tags: list[str]


class VectorKNNBaseline:
    """
    Vector kNN baseline tagger.

    Implements :class:`TaggerLLMClient` for eval only.

    Embeds items via :class:`EmbeddingProvider` (default: char-3gram cosine).
    For leave-one-out evaluation (gold set only), pass the full gold corpus to
    :meth:`fit`; at tag time, the query item is excluded from its own neighbors.

    k=3 by default; increase for larger training sets.

    Note: this baseline is deliberately simple.  kNN over char-trigrams does
    not understand semantics and will struggle to align item *content* with
    skill *labels* — which is the point: it represents the "vector" baseline
    that the AI tagger should beat.
    """

    client_id: str = "vector-knn-baseline-v1"

    def __init__(
        self,
        provider: EmbeddingProvider | None = None,
        k: int = 3,
    ) -> None:
        self._provider: EmbeddingProvider = provider or CharNgramProvider()
        self.k = k
        self._gold: list[GoldItem] = []
        self._embeddings: list[list[float]] = []

    def fit(self, gold_items: list[GoldItem]) -> None:
        """
        Pre-embed the training corpus.

        Must be called before :meth:`propose_tags`.  Embeds all items at once
        (so vocabulary is shared — required for cosine to be meaningful).
        """
        self._gold = list(gold_items)
        texts = [g.text for g in gold_items]
        self._embeddings = self._provider.embed(texts)

    def propose_tags(
        self,
        item: ItemInput,
        question_type: str,
    ) -> LLMTagProposal:
        """
        Tag *item* using kNN vote on the fitted gold corpus.

        The item is embedded alongside the corpus for a single consistent
        vocabulary.  If *item.item_id* is in the corpus, it is excluded from
        its own neighbors (leave-one-out).
        """
        if not self._gold:
            raise RuntimeError("Call fit() before propose_tags().")

        # Re-embed corpus + query together for consistent vocabulary
        query_text = f"{item.stimulus} {item.stem}"
        all_texts = [g.text for g in self._gold] + [query_text]
        all_vecs = self._provider.embed(all_texts)
        query_vec = all_vecs[-1]
        corpus_vecs = all_vecs[:-1]

        # Compute similarities (excluding self)
        sims: list[tuple[float, int]] = []
        for idx, vec in enumerate(corpus_vecs):
            if self._gold[idx].item_id == item.item_id:
                continue  # leave-one-out
            sim = _cosine(query_vec, vec)
            sims.append((sim, idx))

        sims.sort(reverse=True)
        neighbors = sims[: self.k]

        # Majority vote across neighbors
        skill_votes: Counter[str] = Counter()
        trap_votes: Counter[str] = Counter()
        type_votes: Counter[str] = Counter()

        for _sim, idx in neighbors:
            for s in self._gold[idx].skill_tags:
                skill_votes[s] += 1
            for t in self._gold[idx].trap_tags:
                trap_votes[t] += 1
            for tt in self._gold[idx].type_tags:
                type_votes[tt] += 1

        # Accept labels with majority vote (> k/2)
        threshold = max(1, self.k // 2)
        skill_tags = [s for s, cnt in skill_votes.items() if cnt > threshold]
        trap_tags = [t for t, cnt in trap_votes.items() if cnt > threshold]

        # Use stem classifier for type (kNN type is unreliable on small corpus)
        # NOTE: this is a deliberate design choice — the vector baseline uses
        # stem rules for type (same as keyword) so the differentiation is
        # purely on skill/trap prediction.
        stem_clf = StemClassifier()
        type_from_knn = [t for t, cnt in type_votes.items() if cnt > threshold]
        if not type_from_knn:
            type_from_knn = [stem_clf.classify(item.stem)]

        return LLMTagProposal(
            skill_tags=sorted(skill_tags),
            trap_tags=sorted(trap_tags),
        )

    def predict_type(self, item: ItemInput) -> str:
        """
        Predict type via kNN majority vote.

        Used by eval.py to separately evaluate type prediction.
        """
        if not self._gold:
            raise RuntimeError("Call fit() before predict_type().")

        query_text = f"{item.stimulus} {item.stem}"
        all_texts = [g.text for g in self._gold] + [query_text]
        all_vecs = self._provider.embed(all_texts)
        query_vec = all_vecs[-1]
        corpus_vecs = all_vecs[:-1]

        sims = []
        for idx, vec in enumerate(corpus_vecs):
            if self._gold[idx].item_id == item.item_id:
                continue
            sims.append((_cosine(query_vec, vec), idx))
        sims.sort(reverse=True)
        neighbors = sims[: self.k]

        type_votes: Counter[str] = Counter()
        for _sim, idx in neighbors:
            for tt in self._gold[idx].type_tags:
                type_votes[tt] += 1

        if type_votes:
            return type_votes.most_common(1)[0][0]
        # Fallback to stem rules
        return StemClassifier().classify(item.stem)
