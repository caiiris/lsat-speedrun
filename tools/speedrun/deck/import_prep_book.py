#!/usr/bin/env python3
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
import_prep_book.py — import LR items from a locally owned prep-book PDF.

Extracts questions + answer key into Speedrun ``LSAT Item`` JSON for **your**
local collection. Output defaults to ``deck/imported/`` (gitignored) — never
commit imported book content to the repo.

Usage (Rotich 2024 book, Chapter 4 practice set):
    python import_prep_book.py \\
        --pdf ~/Downloads/LSAT\\ Practice\\ Tests\\ 2025-2026....pdf \\
        --book rotich-2024-ch4

Then build a local deck (does not touch the bundled synthetic pool):
    python build_seed_deck.py --col :temp: --items imported/rotich-2024-ch4

Every item carries:
  SyntheticFlag=REAL, Source=<ISBN + book + question #>, License=personal-import
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

DECK_DIR = Path(__file__).resolve().parent
IMPORTED_DIR = DECK_DIR / "imported"
REPO_ROOT = DECK_DIR.parents[2]

# Rotich (2024) — publisher states questions are original, not official LSAT.
ROTICH_2024 = {
    "slug": "rotich-2024",
    "title": "LSAT Practice Tests 2025-2026",
    "author": "Merrill Edgar Rotich",
    "isbn": "9781923370210",
    "publisher": "Merrill Edgar Rotich",
    "year": "2024",
}

# Wrong-choice trap rotation when the book gives no per-choice rationale.
_DISTRACTOR_TRAPS = (
    "trap::half-true",
    "trap::out-of-scope",
    "trap::too-extreme",
    "trap::wrong-direction",
)

# Stem keyword → type:: tag (first match wins).
_STEM_TYPE_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"main conclusion|most accurately expresses the (main )?conclusion", re.I), "type::main-point"),
    (re.compile(r"can be properly inferred|must be true|most strongly (supported|supports)", re.I), "type::inference"),
    (re.compile(r"most strengthens|most supports the argument", re.I), "type::strengthen"),
    (re.compile(r"most weakens|most undermines", re.I), "type::weaken"),
    (re.compile(r"flaw|vulnerable to criticism|error in (the )?reasoning", re.I), "type::flaw"),
    (re.compile(r"assumes|depends on|required assumption|necessary assumption", re.I), "type::assumption"),
    (re.compile(r"justify|sufficient assumption|guarantee[s]? the conclusion", re.I), "type::justify"),
    (re.compile(r"parallel|most similar in (its )?reasoning", re.I), "type::parallel"),
    (re.compile(r"proceeds by|method of reasoning|argument proceeds", re.I), "type::method"),
    (re.compile(r"resolve|reconcile|explain (the )?(discrepancy|paradox|surprising)", re.I), "type::paradox"),
    (re.compile(r"principle", re.I), "type::principle"),
    (re.compile(r"disagree|point at issue", re.I), "type::point-at-issue"),
    (re.compile(r"useful to know|evaluate|relevant to evaluating", re.I), "type::evaluate"),
]

# Default skill tags when taxonomy lookup is unavailable.
_TYPE_DEFAULT_SKILLS: dict[str, str] = {
    "type::main-point": "skill::conclusion-id",
    "type::inference": "skill::conclusion-id skill::conditional",
    "type::strengthen": "skill::causal skill::prephrase",
    "type::weaken": "skill::causal skill::prephrase",
    "type::flaw": "skill::conclusion-id skill::conditional",
    "type::assumption": "skill::conclusion-id skill::conditional",
    "type::justify": "skill::conditional skill::conclusion-id",
    "type::parallel": "skill::abstraction",
    "type::method": "skill::abstraction",
    "type::paradox": "skill::causal skill::conclusion-id",
    "type::principle": "skill::abstraction skill::conclusion-id",
    "type::point-at-issue": "skill::conclusion-id",
    "type::evaluate": "skill::causal",
}


def pdf_to_text(pdf_path: Path) -> str:
    try:
        out = subprocess.run(
            ["pdftotext", str(pdf_path), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit("pdftotext not found — install poppler (brew install poppler)") from exc
    return out.stdout


def infer_type_tag(stem: str) -> str:
    norm = re.sub(r"\s+", " ", stem)
    for pattern, tag in _STEM_TYPE_RULES:
        if pattern.search(norm):
            return tag
    return "type::inference"


def parse_rotich_ch4_answer_key(text: str) -> dict[int, tuple[str, str]]:
    """Parse 'Answer with Detailed Explanations' for Chapter 4 (Q1–100)."""
    normalized = re.sub(r"Q\s*\n\s*uestion", "Question", text)
    start = normalized.find("Answer with Detailed Explanations", 50_000)
    if start < 0:
        return {}
    end = normalized.find("Question 101:", start)
    if end < 0:
        end = start + 30_000
    block = normalized[start:end]

    answers: dict[int, tuple[str, str]] = {}
    for m in re.finditer(
        r"Question\s+(\d+):\s*([A-E])\s*\nExplanation:\s*(.*?)(?=Question\s+\d+:|$)",
        block,
        re.S,
    ):
        num = int(m.group(1))
        if 1 <= num <= 100:
            answers[num] = (m.group(2).upper(), " ".join(m.group(3).split()))
    return answers


def _split_stimulus_stem(body: str) -> tuple[str, str]:
    """Heuristic: stem starts at a 'Which one' / 'The argument' / similar question line."""
    stem_markers = [
        r"Which one of the following",
        r"The .{0,80} reasoning is most vulnerable",
        r"The .{0,80} can be properly inferred",
        r"The .{0,80} most (strengthens|weakens|supports|undermines)",
        r"The answer to which of the following",
        r"best describes the flaw",
        r"disagree over whether",
    ]
    for marker in stem_markers:
        m = re.search(marker, body, re.I | re.S)
        if m:
            return body[: m.start()].strip(), body[m.start() :].strip()
    # Fallback: last paragraph before (A)
    parts = re.split(r"\n\s*\(A\)", body, maxsplit=1)
    if len(parts) == 2:
        head = parts[0].strip()
        lines = head.splitlines()
        if len(lines) >= 2:
            return "\n".join(lines[:-1]).strip(), lines[-1].strip()
    return body.strip(), "Which one of the following is most strongly supported by the argument?"


def _parse_choices(stem_and_choices: str) -> tuple[str, dict[str, str]]:
    """Return (stem_without_choices, {A: text, ...})."""
    text = re.sub(r"\s*\(A\)\s+", "\n(A) ", stem_and_choices.strip())
    parts = re.split(r"\(([A-E])\)\s*", text, maxsplit=10)
    if len(parts) < 11:
        raise ValueError("no choices parsed")
    stem = parts[0].strip()
    choices: dict[str, str] = {}
    for i in range(1, len(parts), 2):
        letter = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        choices[letter] = " ".join(body.split()).strip()
    if len(choices) < 5:
        raise ValueError("no choices parsed")
    return stem, choices


def parse_rotich_ch4_questions(text: str) -> list[dict[str, Any]]:
    """Parse Chapter 4 practice set (questions 1–100)."""
    start = text.find("Questions 1–100")
    if start < 0:
        start = text.find("100 Logical Reasoning questions")
    if start < 0:
        raise ValueError("LR practice block (Questions 1–100) not found in PDF text")
    end = text.find("QUESTIONS 101–200", start)
    if end < 0:
        end = text.find("\nQuestion 101\n", start + 5000)
    chunk = text[start : end if end > start else None]

    answers = parse_rotich_ch4_answer_key(text)
    raw_blocks = re.split(r"\nQuestion\s+(\d+)\s*\n", chunk)
    # raw_blocks: [preamble, num1, body1, num2, body2, ...]
    items: list[dict[str, Any]] = []
    i = 1
    while i + 1 < len(raw_blocks):
        qnum = int(raw_blocks[i])
        if qnum > 100:
            break
        body = raw_blocks[i + 1].strip()
        i += 2
        if not body or qnum not in answers:
            continue
        try:
            stimulus, rest = _split_stimulus_stem(body)
            stem, choices = _parse_choices(rest)
        except ValueError:
            print(f"WARN  skip Q{qnum}: parse error", file=sys.stderr)
            continue

        correct, explanation = answers[qnum]
        type_tag = infer_type_tag(stem)
        meta = ROTICH_2024
        source = (
            f"{meta['author']}, {meta['title']} ({meta['year']}), "
            f"ISBN {meta['isbn']}, Ch.4 Q{qnum} — publisher-original practice item; "
            f"personal import from locally owned materials; not for redistribution."
        )
        item_id = f"ROTICH-2024-CH4-{qnum:03d}"

        wrong_traps = list(_DISTRACTOR_TRAPS)
        item: dict[str, Any] = {
            "_id": item_id,
            "SyntheticFlag": "REAL",
            "TypeTag": type_tag,
            "SkillTag": _TYPE_DEFAULT_SKILLS.get(type_tag, "skill::conclusion-id"),
            "TrapTag": "trap::scope-shift" if type_tag == "type::flaw" else "",
            "Difficulty": 3,
            "Source": source,
            "License": "personal-import-not-for-redistribution",
            "Stimulus": stimulus,
            "Stem": stem,
            "CorrectChoice": correct,
        }
        trap_idx = 0
        for letter in "ABCDE":
            item[f"Choice{letter}"] = choices.get(letter, "")
            if letter == correct:
                item[f"WhyWrong{letter}"] = f"CORRECT. {explanation}"
                item[f"TrapChoice{letter}"] = ""
            else:
                trap = wrong_traps[trap_idx % len(wrong_traps)]
                trap_idx += 1
                item[f"WhyWrong{letter}"] = (
                    f"Incorrect. Book explanation for Q{qnum}: {explanation} "
                    f"(per-choice rationale not in source — review against key.)"
                )
                item[f"TrapChoice{letter}"] = trap

        items.append(item)
    return items


def write_by_type(items: list[dict[str, Any]], out_dir: Path, book_slug: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    by_type: dict[str, list[dict[str, Any]]] = {}
    for it in items:
        tag = it["TypeTag"].replace("type::", "")
        by_type.setdefault(tag, []).append(it)

    for slug, group in sorted(by_type.items()):
        path = out_dir / f"type-{slug}.json"
        payload = {
            "_disclaimer": (
                "IMPORTED FROM LOCALLY OWNED PREP BOOK — NOT FOR REDISTRIBUTION. "
                "Do not commit this directory to git."
            ),
            "_type": f"type::{slug}",
            "_format_version": "2.0",
            "_import_source": book_slug,
            "items": group,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"  wrote {path.name}: {len(group)} items")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import prep-book LR items (local use only).")
    parser.add_argument("--pdf", required=True, type=Path, help="Path to prep book PDF on your machine")
    parser.add_argument(
        "--book",
        default="rotich-2024-ch4",
        choices=["rotich-2024-ch4"],
        help="Which book/format to parse",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=IMPORTED_DIR / "rotich-2024-ch4",
        help="Output directory (default: deck/imported/…, gitignored)",
    )
    args = parser.parse_args(argv)

    if not args.pdf.is_file():
        print(f"PDF not found: {args.pdf}", file=sys.stderr)
        return 1

    print(f"Reading {args.pdf.name} …")
    text = pdf_to_text(args.pdf)

    if args.book == "rotich-2024-ch4":
        items = parse_rotich_ch4_questions(text)
    else:
        print(f"Unknown book format: {args.book}", file=sys.stderr)
        return 1

    if not items:
        print("No items parsed — check PDF path and format.", file=sys.stderr)
        return 1

    print(f"Parsed {len(items)} items → {args.out}/")
    write_by_type(items, args.out, args.book)

    print(
        "\nNext (local only — imported content stays out of git):\n"
        f"  python item_validator.py --items {args.out}\n"
        f"  python build_seed_deck.py --col :temp: --items {args.out}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
