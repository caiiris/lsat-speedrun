# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
item_validator.py — deterministic (no-AI) quality gate for the LSAT Item pool.

Enforces the ``LSAT Item`` data contract (docs/speedrun/data/notetypes.md) plus
the taxonomy tag contract (docs/speedrun/data/taxonomy.json) so the Q&A database
stays internally consistent and grader-credible as it grows. **No AI / no
network** — every check is a structural or cross-reference rule (D-SR14: the app
must score with AI off; the item pool is authored + verified deterministically).

Checks (errors block; warnings advise):
  E  every required field present and non-empty
  E  SyntheticFlag == "SYNTHETIC" and Source names SYNTHETIC (D-SR11)
  E  TypeTag is a known type:: tag (or declared subtype)
  E  every SkillTag token is a known skill:: tag
  E  TrapTag empty or a known trap:: tag
  E  CorrectChoice in A-E
  E  the correct choice's WhyWrong starts with "CORRECT"; its TrapChoice is empty
  E  every *wrong* choice has a non-empty WhyWrong AND a known trap:: TrapChoice
  E  Difficulty is an int 1-5
  E  _id unique; Stimulus text unique across the pool
  W  flaw item without a TrapTag (stimulus flaw usually named for type::flaw)
  W  choice text duplicated within an item
  W  only one distinct trap category used across an item's wrong choices

Usage:
    python item_validator.py            # validate deck/items/
    python item_validator.py --items path/to/items_or_file.json
    python item_validator.py --coverage # also print per-type coverage vs floors

Exit code 0 if no errors (warnings allowed), 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from items_loader import ITEMS_DIR, count_by_type, load_items

REPO_ROOT = Path(__file__).resolve().parents[3]
TAXONOMY_JSON = REPO_ROOT / "docs" / "speedrun" / "data" / "taxonomy.json"
WEIGHTS_JSON = REPO_ROOT / "docs" / "speedrun" / "data" / "weights.json"

CHOICES = ("A", "B", "C", "D", "E")
TAG_RE = re.compile(r"^(type|skill|trap)::[a-z0-9][a-z0-9\-]*$")

REQUIRED_NONEMPTY = (
    "Stimulus", "Stem",
    "ChoiceA", "ChoiceB", "ChoiceC", "ChoiceD", "ChoiceE",
    "CorrectChoice", "TypeTag", "SkillTag", "Source", "SyntheticFlag",
)


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


# ---------------------------------------------------------------------------
# Taxonomy tag universe
# ---------------------------------------------------------------------------

@dataclass
class TagUniverse:
    type_tags: set[str]
    skill_tags: set[str]
    trap_tags: set[str]
    argument_flaw_tags: set[str]

    @classmethod
    def from_taxonomy(cls, taxonomy: dict[str, Any]) -> "TagUniverse":
        type_tags = {qt["tag"] for qt in taxonomy["axis1_question_types"]}
        type_tags |= {st["tag"] for st in taxonomy.get("axis1_subtypes", [])}
        skill_tags = {sk["tag"] for sk in taxonomy["axis2_reasoning_subskills"]}
        trap_cat = taxonomy["trap_catalog"]
        argument_flaw_tags = {t["tag"] for t in trap_cat["argument_flaws"]}
        trap_tags = argument_flaw_tags | {t["tag"] for t in trap_cat["distractor_traps"]}
        return cls(type_tags, skill_tags, trap_tags, argument_flaw_tags)


def load_taxonomy(path: Path = TAXONOMY_JSON) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def validate_items(
    items: list[dict[str, Any]],
    universe: TagUniverse,
) -> ValidationResult:
    """Validate the full item pool against the contract. Pure function."""
    result = ValidationResult()
    seen_ids: dict[str, int] = {}
    seen_stimuli: dict[str, str] = {}

    for idx, item in enumerate(items):
        iid = str(item.get("_id") or f"index-{idx}")
        _validate_item(item, iid, universe, result)

        # cross-item uniqueness
        raw_id = item.get("_id")
        if raw_id:
            if raw_id in seen_ids:
                result.errors.append(f"{iid}: duplicate _id (also at index {seen_ids[raw_id]})")
            seen_ids[raw_id] = idx

        stim = _norm(item.get("Stimulus", ""))
        if stim:
            if stim in seen_stimuli:
                result.errors.append(
                    f"{iid}: Stimulus duplicates that of {seen_stimuli[stim]} "
                    "(each item needs a distinct stimulus)"
                )
            else:
                seen_stimuli[stim] = iid

    return result


def _validate_item(
    item: dict[str, Any],
    iid: str,
    u: TagUniverse,
    result: ValidationResult,
) -> None:
    err = lambda m: result.errors.append(f"{iid}: {m}")  # noqa: E731
    warn = lambda m: result.warnings.append(f"{iid}: {m}")  # noqa: E731

    # --- required non-empty fields
    for fname in REQUIRED_NONEMPTY:
        if not _norm(str(item.get(fname, ""))):
            err(f"missing/empty required field {fname!r}")

    # --- source / synthetic guard (D-SR11)
    flag = item.get("SyntheticFlag", "")
    source = str(item.get("Source", ""))
    if flag == "SYNTHETIC":
        if "SYNTHETIC" not in source:
            err("Source must name 'SYNTHETIC' for synthetic items (D-SR11)")
    elif flag == "REAL":
        if len(source) < 40:
            err("REAL items need a full Source citation (book, ISBN, question id)")
        if "not for redistribution" not in source.lower() and "personal import" not in source.lower():
            warn("REAL item Source should note personal-import / not-for-redistribution scope")
    else:
        err("SyntheticFlag must be 'SYNTHETIC' or 'REAL' (D-SR11)")

    # --- correct choice
    correct = item.get("CorrectChoice", "")
    if correct not in CHOICES:
        err(f"CorrectChoice must be one of A-E, got {correct!r}")
        correct = None  # can't run choice-relative checks

    # --- type tag
    type_tag = item.get("TypeTag", "")
    if type_tag and type_tag not in u.type_tags:
        err(f"TypeTag {type_tag!r} not in taxonomy")

    # --- skill tags (space-separated)
    skill_tokens = [t for t in str(item.get("SkillTag", "")).split() if t]
    if not skill_tokens:
        err("SkillTag must contain at least one skill:: tag")
    for tok in skill_tokens:
        if tok not in u.skill_tags:
            err(f"SkillTag {tok!r} not in taxonomy")

    # --- stimulus trap tag
    trap_tag = _norm(str(item.get("TrapTag", "")))
    if trap_tag and trap_tag not in u.trap_tags:
        err(f"TrapTag {trap_tag!r} not in taxonomy")
    if type_tag == "type::flaw" and not trap_tag:
        warn("type::flaw item has no TrapTag (name the stimulus flaw)")

    # --- per-choice: why-wrong + trap-choice consistency
    seen_choice_text: dict[str, str] = {}
    wrong_traps: set[str] = set()
    for letter in CHOICES:
        text = _norm(str(item.get(f"Choice{letter}", "")))
        why = _norm(str(item.get(f"WhyWrong{letter}", "")))
        trap = _norm(str(item.get(f"TrapChoice{letter}", "")))

        if text:
            if text.lower() in seen_choice_text:
                warn(f"Choice{letter} text duplicates Choice{seen_choice_text[text.lower()]}")
            else:
                seen_choice_text[text.lower()] = letter

        if trap and trap not in u.trap_tags:
            err(f"TrapChoice{letter} {trap!r} not in taxonomy")

        if correct is None:
            continue

        if letter == correct:
            if trap:
                err(f"correct choice {letter} must have an empty TrapChoice{letter} (got {trap!r})")
            if why and not why.upper().startswith("CORRECT"):
                err(f"WhyWrong{correct} (the correct choice) should start with 'CORRECT'")
            if not why:
                warn(f"WhyWrong{correct} (correct choice) is empty — add a rationale")
        else:
            if not why:
                err(f"wrong choice {letter} has empty WhyWrong{letter}")
            if not trap:
                err(f"wrong choice {letter} has empty TrapChoice{letter} (name the distractor trap)")
            elif trap in u.trap_tags:
                wrong_traps.add(trap)

    if correct is not None and len(wrong_traps) == 1:
        warn("all wrong choices share a single trap category — vary the distractor traps")

    # --- length tell: correct choice should not be markedly longer than distractors
    if correct is not None:
        cw = len(_norm(str(item.get(f"Choice{correct}", ""))).split())
        others = [
            len(_norm(str(item.get(f"Choice{c}", ""))).split())
            for c in CHOICES
            if c != correct and _norm(str(item.get(f"Choice{c}", "")))
        ]
        if others and cw and (cw / (sum(others) / len(others))) >= 1.9:
            warn("correct choice is markedly longer than the distractors (length tell — "
                 "enrich the distractors or tighten the answer)")

    # --- difficulty
    diff = item.get("Difficulty")
    if isinstance(diff, bool) or not isinstance(diff, int) or not (1 <= int(diff) <= 5):
        err(f"Difficulty must be an int 1-5, got {diff!r}")

    # --- tag format sanity (kebab-case)
    for t in [type_tag, trap_tag, *skill_tokens]:
        if t and not TAG_RE.match(t):
            err(f"tag {t!r} fails kebab-case format check")


def _norm(s: str) -> str:
    return " ".join(str(s).split()).strip()


# ---------------------------------------------------------------------------
# Coverage report vs production floor
# ---------------------------------------------------------------------------

def coverage_lines(items: list[dict[str, Any]], universe: TagUniverse) -> list[str]:
    counts = count_by_type(items)
    try:
        with open(WEIGHTS_JSON, encoding="utf-8") as f:
            weights = json.load(f)
        floor = weights["coverage_thresholds"]["min_pool_size_production"]
    except (OSError, KeyError):
        floor = 10
    lines = [f"Per-type coverage (production floor = {floor}):"]
    covered = 0
    for tag in sorted(universe.type_tags):
        # only report top-level types (those in weights or with items)
        n = counts.get(tag, 0)
        if tag not in counts and tag not in _weight_tags():
            continue
        mark = "OK " if n >= floor else "-- "
        if n >= floor:
            covered += 1
        lines.append(f"  {mark}{tag:<26} {n}")
    lines.append(f"Total items: {len(items)}")
    return lines


def _weight_tags() -> set[str]:
    try:
        with open(WEIGHTS_JSON, encoding="utf-8") as f:
            return set(json.load(f)["lr_frequency_weights"]["weights"].keys())
    except (OSError, KeyError):
        return set()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the Speedrun LSAT Item pool.")
    parser.add_argument("--items", default=str(ITEMS_DIR), help="items dir or JSON file")
    parser.add_argument("--coverage", action="store_true", help="also print per-type coverage")
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = parser.parse_args(argv)

    universe = TagUniverse.from_taxonomy(load_taxonomy())
    pool = load_items(args.items)
    items = pool["items"]

    result = validate_items(items, universe)

    print(f"Validated {len(items)} items from {args.items}")
    if pool.get("_sources"):
        for name, n in sorted(pool["_sources"].items()):
            print(f"  {name}: {n}")

    for w in result.warnings:
        print(f"WARN  {w}")
    for e in result.errors:
        print(f"ERROR {e}")

    if args.coverage:
        print()
        for line in coverage_lines(items, universe):
            print(line)

    ok = result.ok and (not args.strict or not result.warnings)
    if ok:
        print(f"\nOK — {len(items)} items valid "
              f"({len(result.warnings)} warning(s)).")
        return 0
    print(f"\nFAIL — {len(result.errors)} error(s), {len(result.warnings)} warning(s).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
