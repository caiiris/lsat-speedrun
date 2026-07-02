#!/usr/bin/env python3
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
derive_patterns.py — abstract imported items to content-free logical skeletons.

Copyright note: this reads locally-imported prep-book items (gitignored) and
emits ONLY their unprotectable logical *form* — type / skill / trap / a coarse
logical-pattern label — with **all stimulus and answer-choice prose stripped
out**. The output is an authoring reference ("what patterns to drill"), not a
transformation of the source text. Fresh synthetic items are then hand-authored
against these skeletons, sharing only the (uncopyrightable) logical form.

Output defaults to deck/imported/patterns.json (gitignored). Do not commit it.

Usage:
    python derive_patterns.py                       # scan deck/imported/*/
    python derive_patterns.py --src imported/rotich-2024-ch4
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

DECK_DIR = Path(__file__).resolve().parent
IMPORTED_DIR = DECK_DIR / "imported"

# Coarse, content-free logical-form labels keyed off the book's own explanation
# vocabulary. These are *ideas* (unprotectable), not source expression.
_FORM_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"modus tollens|not\b.*→.*not|no .*→ not", re.I), "conditional:modus-tollens"),
    (re.compile(r"modus ponens|valid .*(if|conditional)", re.I), "conditional:modus-ponens"),
    (re.compile(r"necess\w+ (vs\.?|not) .*suffic|suffic\w+ .*necess", re.I), "conditional:sufficient-necessary"),
    (re.compile(r"correlation.*caus|caus.*correlation|reverse caus", re.I), "causal:correlation-causation"),
    (re.compile(r"other factor|alternative|another (cause|factor)", re.I), "causal:alternate-cause"),
    (re.compile(r"sample|representative|generaliz", re.I), "induction:sample"),
    (re.compile(r"universal|all .*are|every", re.I), "syllogism:universal"),
    (re.compile(r"analog", re.I), "analogy"),
    (re.compile(r"weaken|undermin", re.I), "impact:weaken"),
    (re.compile(r"strengthen|support", re.I), "impact:strengthen"),
]


def classify_form(explanation: str) -> str:
    for pattern, label in _FORM_RULES:
        if pattern.search(explanation):
            return label
    return "unclassified"


def skeleton_of(item: dict[str, Any]) -> dict[str, Any]:
    """Return a content-free skeleton: type / skill / trap / form + trap shape.

    Deliberately excludes Stimulus, Stem, and all Choice/WhyWrong prose.
    """
    correct = item.get("CorrectChoice", "")
    # The correct choice's WhyWrong holds the book's pattern description; keep only
    # the derived label, never the text.
    expl = str(item.get(f"WhyWrong{correct}", ""))
    trap_shape = [
        item.get(f"TrapChoice{c}", "")
        for c in "ABCDE"
        if item.get(f"TrapChoice{c}", "")
    ]
    return {
        "type": item.get("TypeTag", ""),
        "skill": item.get("SkillTag", ""),
        "stimulus_flaw": item.get("TrapTag", ""),
        "logical_form": classify_form(expl),
        "distractor_traps": trap_shape,
        "n_choices": sum(1 for c in "ABCDE" if item.get(f"Choice{c}")),
    }


def derive(src: Path) -> dict[str, Any]:
    skeletons: list[dict[str, Any]] = []
    for jf in sorted(src.rglob("type-*.json")):
        with open(jf, encoding="utf-8") as f:
            data = json.load(f)
        for item in data.get("items", []):
            skeletons.append(skeleton_of(item))

    by_type = Counter(s["type"] for s in skeletons)
    by_form = Counter(s["logical_form"] for s in skeletons)
    by_skill = Counter(tok for s in skeletons for tok in s["skill"].split())

    return {
        "_note": (
            "Content-free logical skeletons derived from locally-owned prep books. "
            "No source prose. Authoring reference only; keep out of git."
        ),
        "_source_dir": str(src),
        "counts_by_type": dict(by_type.most_common()),
        "counts_by_form": dict(by_form.most_common()),
        "counts_by_skill": dict(by_skill.most_common()),
        "skeletons": skeletons,
    }


def patterns_from_apex_pdf(pdf_path: Path) -> dict[str, Any]:
    """Extract *pattern-only* skeletons from the APEX book's LR answer explanations.

    IMPORTANT: reads the copyrighted PDF transiently and persists **no source
    prose** — only the abstract logical-form label per question (an unprotectable
    idea). Skips Analytical Reasoning (§1, off-format per D-SR1) and Reading
    Comprehension (§4, phase-2); keeps the two Logical Reasoning sections (§2, §3).
    """
    from import_prep_book import pdf_to_text  # local, avoids import cycle at load

    text = pdf_to_text(pdf_path)
    # LR explanation blocks (answer-key rationales), located by section header.
    lr_bounds: list[tuple[int, int, int]] = []
    headers = [(m.start(), int(m.group(1)))
               for m in re.finditer(r"Section\s*([1-4])\b", text) if m.start() > 300_000]
    headers.sort()
    for i, (pos, sec) in enumerate(headers):
        end = headers[i + 1][0] if i + 1 < len(headers) else len(text)
        if sec in (2, 3):  # Logical Reasoning only
            lr_bounds.append((sec, pos, end))

    skeletons: list[dict[str, Any]] = []
    for sec, start, end in lr_bounds:
        block = text[start:end]
        # Each rationale begins "<n>. <Letter>: <explanation>"; classify the form
        # from the explanation, then discard the text.
        for m in re.finditer(r"(?:^|\n)\s*(\d{1,2})[.,]\s*([A-E])[:.]\s*(.*?)(?=\n\s*\d{1,2}[.,]\s*[A-E][:.]|\Z)",
                             block, re.S):
            qnum, letter, expl = int(m.group(1)), m.group(2), m.group(3)
            skeletons.append({
                "source": "apex-2019 (official LSAC test, personal-use ref)",
                "section": sec,
                "q": qnum,
                "answer": letter,
                "logical_form": classify_form(expl),  # label only; expl discarded
            })

    by_form = Counter(s["logical_form"] for s in skeletons)
    return {
        "_note": (
            "Pattern-only skeletons from APEX (official LSAC LR sections), read "
            "transiently. NO source prose stored (only abstract logical-form "
            "labels — unprotectable ideas). Authoring reference; keep out of git."
        ),
        "_source": "APEX Test Prep, The LSAT Tutor (2019), ISBN 9781628458244 — "
                   "official LSAC practice test; LSAC is the copyright owner; personal-use reference only.",
        "counts_by_form": dict(by_form.most_common()),
        "n": len(skeletons),
        "skeletons": skeletons,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Derive content-free logical skeletons.")
    parser.add_argument("--src", type=Path, default=IMPORTED_DIR, help="imported/ dir to scan")
    parser.add_argument("--pdf", type=Path, help="Extract pattern-only skeletons directly from a book PDF")
    parser.add_argument("--book", choices=["apex-2019"], help="PDF book format for --pdf mode")
    parser.add_argument("--out", type=Path, default=IMPORTED_DIR / "patterns.json")
    args = parser.parse_args(argv)

    if args.pdf:
        if args.book != "apex-2019":
            print("--pdf requires --book apex-2019")
            return 1
        if not args.pdf.is_file():
            print(f"PDF not found: {args.pdf}")
            return 1
        result = patterns_from_apex_pdf(args.pdf)
        out = args.out if args.out != IMPORTED_DIR / "patterns.json" else IMPORTED_DIR / "patterns-apex.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"Extracted {result['n']} pattern-only skeletons (no prose) → {out}")
        print("\nLogical-form distribution (LR sections 2 & 3):")
        for form, n in result["counts_by_form"].items():
            print(f"  {n:>3}  {form}")
        return 0

    if not args.src.exists():
        print(f"No imported items at {args.src} — run import_prep_book.py first.")
        return 1

    result = derive(args.src)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Derived {len(result['skeletons'])} skeletons → {args.out}")
    print("\nLogical-form distribution (drives what to author):")
    for form, n in result["counts_by_form"].items():
        print(f"  {n:>3}  {form}")
    print("\nSkill distribution:")
    for skill, n in result["counts_by_skill"].items():
        print(f"  {n:>3}  {skill}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
