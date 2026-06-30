# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Meta-vocabulary card generator for Speedrun WP-12.

Generates flashcard Q&A pairs from a cited source text.  The LLM call is
behind a clean ``LLMClient`` protocol so the pipeline runs fully without
network/API access using ``DeterministicStubClient``.  Plug a real model by
implementing ``LLMClient`` and passing it to ``CardGenerator``.

spec-ai §5 · D-SR15 · brainlift Insight 5, J.3

AMBIGUITY SURFACED (see WP-12-log.md L1):
  The stub produces structurally correct cards by parsing the source text;
  it does NOT call any LLM.  Wire a real LLMClient before production use.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from tools.speedrun.cardcheck.injection_guard import sanitize

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class RawCard:
    """A single generated flashcard before verification."""

    question: str
    answer: str
    source_ref: str = ""
    domain: str = "unknown"
    generator_id: str = "unknown"


# ---------------------------------------------------------------------------
# LLMClient protocol — the seam for plugging a real model
# ---------------------------------------------------------------------------


@runtime_checkable
class LLMClient(Protocol):
    """
    Protocol that every LLM backend must implement.

    Implementors receive the sanitized source text and a requested card count
    and return a list of raw (unverified) cards.  They MUST NOT decide
    correctness — generate only; verification is the checker's job (D1).

    To wire a real model:
      1. Implement this protocol (e.g. ``OpenAIClient``, ``AnthropicClient``).
      2. Pass the instance to ``CardGenerator``.
      3. The real implementation should prompt the model to produce JSON with
         keys: question, answer, source_ref, domain.  Parse and return
         ``RawCard`` objects.
    """

    def generate_cards(
        self,
        source_text: str,
        n: int = 20,
    ) -> list[RawCard]:
        """Generate up to *n* meta-vocab cards from *source_text*."""
        ...


# ---------------------------------------------------------------------------
# Deterministic stub (no network, no API key required)
# ---------------------------------------------------------------------------


class DeterministicStubClient:
    """
    Deterministic stub that generates cards by parsing section headings and
    definition blocks from the source text.

    Strategy:
    - Find lines of the form ``§N.M term`` (section headings).
    - Extract the immediately following paragraph as the answer.
    - Generate one card per section, up to *n*.

    The answers come from the source text verbatim — NOT from hardcoded gold
    answers — so factual verification against the source is meaningful.
    This stub exists solely so the test suite can run without a real LLM.
    """

    generator_id: str = "deterministic-stub-v1"

    # Pattern that matches section headings like "§1.3 conclusion"
    _SECTION_RE = re.compile(
        r"^§(?P<section>[\d.]+)\s+(?P<term>.+)$",
        re.MULTILINE,
    )

    def generate_cards(
        self,
        source_text: str,
        n: int = 20,
    ) -> list[RawCard]:
        cards: list[RawCard] = []
        sections = list(self._SECTION_RE.finditer(source_text))

        for i, match in enumerate(sections):
            if len(cards) >= n:
                break

            section_id = match.group("section")
            term = match.group("term").strip()
            heading = f"§{section_id}"

            # Extract the body text between this heading and the next.
            body_start = match.end()
            body_end = sections[i + 1].start() if i + 1 < len(sections) else len(source_text)
            body = source_text[body_start:body_end].strip()

            # Skip empty or very short bodies.
            if len(body) < 20:
                continue

            # Use the first sentence/paragraph as the answer.
            # Split on blank line or sentence boundary.
            first_para = body.split("\n\n")[0].strip()
            # Collapse internal newlines within the paragraph.
            first_para = re.sub(r"\n+", " ", first_para).strip()

            question = self._make_question(term, heading)
            answer = first_para

            cards.append(
                RawCard(
                    question=question,
                    answer=answer,
                    source_ref=heading,
                    domain=self._infer_domain(section_id),
                    generator_id=self.generator_id,
                )
            )

        return cards

    @staticmethod
    def _make_question(term: str, heading: str) -> str:
        """Turn a term name into a definition question."""
        term_lower = term.lower()
        # Indicator-word sections already contain the word "indicator"
        if "indicator" in term_lower or "shows that" in term_lower or term_lower in (
            "therefore", "since", "because", "given that", "it follows that",
            "which shows that",
        ):
            return f"What does '{term}' signal in an argument? ({heading})"
        if term_lower.startswith("negation of"):
            return f"What is the {term}? ({heading})"
        return f"What is {term}? ({heading})"

    @staticmethod
    def _infer_domain(section_id: str) -> str:
        """Infer domain from section number prefix."""
        major = section_id.split(".")[0]
        return {
            "1": "argument_vocabulary",
            "2": "indicator_words",
            "3": "quantifiers",
            "4": "fallacies",
        }.get(major, "unknown")


# ---------------------------------------------------------------------------
# CardGenerator — orchestrates sanitize → generate
# ---------------------------------------------------------------------------


class CardGenerator:
    """
    Generates meta-vocabulary cards from a cited source file.

    Usage::

        gen = CardGenerator(
            source_path=Path("tools/speedrun/cardcheck/logic_meta_vocab.txt"),
            client=DeterministicStubClient(),  # swap for real client in prod
        )
        cards = gen.generate(n=20)

    The source is sanitized for injection before being passed to the client.
    The client receives ONLY the sanitized text — never the raw file bytes.
    """

    def __init__(
        self,
        source_path: Path,
        client: LLMClient | None = None,
    ) -> None:
        self.source_path = source_path
        self.client: LLMClient = client or DeterministicStubClient()

    def generate(self, n: int = 20) -> tuple[list[RawCard], list[str]]:
        """
        Read the source, sanitize it, then generate up to *n* cards.

        Returns:
            (cards, warnings)  — ``warnings`` lists any sanitization advisories.
        """
        raw_text = self.source_path.read_text(encoding="utf-8")
        sanit = sanitize(raw_text)
        cards = self.client.generate_cards(sanit.text, n=n)
        return cards, sanit.warnings

    # ------------------------------------------------------------------
    # Convenience: load gold set (held-out; for pipeline integration only)
    # ------------------------------------------------------------------

    @staticmethod
    def load_gold_set(gold_path: Path) -> list[dict[str, object]]:
        """Load the 50-item held-out gold set from *gold_path*."""
        data = json.loads(gold_path.read_text(encoding="utf-8"))
        return data["items"]  # type: ignore[return-value]
