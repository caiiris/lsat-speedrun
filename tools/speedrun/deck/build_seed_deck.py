# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
build_seed_deck.py — Speedrun WP-1 seed deck builder.

Creates the three Speedrun notetypes and populates the collection with:
  - LSAT Skill notes (one per taxonomy skill/trap — 38 total)
  - LSAT Item notes  (synthetic placeholders from sample_items.json, suspended)
  - LSAT Meta notes  (seed vocab/flaw/indicator cards)

All real LSAT items must come from official sources (D-SR11, F.2).
Synthetic placeholders are clearly labeled with SyntheticFlag = "SYNTHETIC".

Usage:
    python build_seed_deck.py --col /path/to/output.anki2 [--items /path/to/sample_items.json]
    python build_seed_deck.py --col :temp:  # creates a temp file, prints path

The --col argument is a path to an .anki2 collection file.  Use ":temp:" to
create a temporary file automatically (useful for testing).

Returns exit-code 0 on success, 1 on error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "docs" / "speedrun" / "data"
TAXONOMY_JSON = DATA_DIR / "taxonomy.json"
WEIGHTS_JSON = DATA_DIR / "weights.json"
DEFAULT_ITEMS_JSON = Path(__file__).parent / "sample_items.json"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DECK_NAME_ROOT = "LSAT Speedrun"
DECK_META = f"{DECK_NAME_ROOT}::Meta"
DECK_SKILLS = f"{DECK_NAME_ROOT}::Skills"
DECK_ITEMS = f"{DECK_NAME_ROOT}::Items"

NOTETYPE_META = "LSAT Meta"
NOTETYPE_SKILL = "LSAT Skill"
NOTETYPE_ITEM = "LSAT Item"

# Deck options preset assigned to the Speedrun decks. Anki's *default* preset caps
# new cards at 20/day; the seed deck has 38 skills + 13 meta, so we ship a dedicated
# preset with a higher limit. These are seed/dev defaults and are tunable in Deck
# Options; real new-card pacing is a future deck-config decision.
DECK_CONFIG_NAME = "LSAT Speedrun"
NEW_CARDS_PER_DAY = 100
REVIEWS_PER_DAY = 1000

MIN_POOL_SIZE_SEED = 3  # minimum items for a skill to be considered covered in seed deck


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CoverageReport:
    total_skills: int = 0
    covered_skills: list[str] = field(default_factory=list)
    uncovered_skills: list[str] = field(default_factory=list)
    pool_counts: dict[str, int] = field(default_factory=dict)

    @property
    def coverage_fraction(self) -> float:
        if self.total_skills == 0:
            return 0.0
        return len(self.covered_skills) / self.total_skills


# ---------------------------------------------------------------------------
# Notetype definitions
# ---------------------------------------------------------------------------

def _make_notetype_meta(col: Any) -> Any:
    """
    LSAT Meta notetype: vocab / flaw / indicator cards → Memory score.
    Fields: Front, Back, Category, Source, Notes.
    """
    m = col.models.new(NOTETYPE_META)
    for fname in ["Front", "Back", "Category", "Source", "Notes"]:
        col.models.add_field(m, col.models.new_field(fname))

    t = col.models.new_template("Recall")
    t["qfmt"] = (
        '<div class="category">{{Category}}</div>\n'
        '<div class="front">{{Front}}</div>'
    )
    t["afmt"] = (
        "{{FrontSide}}\n"
        '<hr id="answer">\n'
        '<div class="back">{{Back}}</div>\n'
        '{{#Notes}}<div class="notes">{{Notes}}</div>{{/Notes}}\n'
        '{{#Source}}<div class="source">Source: {{Source}}</div>{{/Source}}'
    )
    col.models.add_template(m, t)
    col.models.set_sort_index(m, 0)  # sort by Front
    return m


def _make_notetype_skill(col: Any) -> Any:
    """
    LSAT Skill notetype: one note per skill/trap → FSRS-scheduled unit → Performance.
    Fields: SkillName, SkillType, IdentityTag, Description, KeyTechnique, CommonErrors, Notes.
    """
    m = col.models.new(NOTETYPE_SKILL)
    for fname in [
        "SkillName",
        "SkillType",
        "IdentityTag",
        "Description",
        "KeyTechnique",
        "CommonErrors",
        "Notes",
    ]:
        col.models.add_field(m, col.models.new_field(fname))

    t = col.models.new_template("Skill Review")
    t["qfmt"] = (
        '<div class="skill-type">{{SkillType}}</div>\n'
        '<div class="skill-name">{{SkillName}}</div>\n'
        '<div class="identity-tag"><code>{{IdentityTag}}</code></div>\n'
        "<hr>\n"
        '<div class="prompt">Practice: apply this skill to the drawn item.</div>'
    )
    t["afmt"] = (
        "{{FrontSide}}\n"
        '<hr id="answer">\n'
        '<div class="description">{{Description}}</div>\n'
        "{{#KeyTechnique}}"
        '<div class="technique"><strong>Key technique:</strong> {{KeyTechnique}}</div>'
        "{{/KeyTechnique}}\n"
        "{{#CommonErrors}}"
        '<div class="errors"><strong>Common errors:</strong> {{CommonErrors}}</div>'
        "{{/CommonErrors}}\n"
        '{{#Notes}}<div class="notes">{{Notes}}</div>{{/Notes}}'
    )
    col.models.add_template(m, t)
    col.models.set_sort_index(m, 0)  # sort by SkillName
    return m


def _make_notetype_item(col: Any) -> Any:
    """
    LSAT Item notetype: the pool — stimulus + 5 choices + per-choice why-wrong/trap.
    Cards are suspended immediately after creation (never directly studied).
    """
    m = col.models.new(NOTETYPE_ITEM)
    item_fields = [
        "Stimulus", "Stem",
        "ChoiceA", "ChoiceB", "ChoiceC", "ChoiceD", "ChoiceE",
        "CorrectChoice",
        "WhyWrongA", "WhyWrongB", "WhyWrongC", "WhyWrongD", "WhyWrongE",
        "TrapChoiceA", "TrapChoiceB", "TrapChoiceC", "TrapChoiceD", "TrapChoiceE",
        "TypeTag", "SkillTag", "TrapTag",
        "Difficulty", "Source", "SyntheticFlag",
    ]
    for fname in item_fields:
        col.models.add_field(m, col.models.new_field(fname))

    t = col.models.new_template("Commit-then-Reveal")
    t["qfmt"] = (
        '<div class="synthetic-flag">{{SyntheticFlag}}</div>\n'
        '<div class="stimulus">{{Stimulus}}</div>\n'
        "<hr>\n"
        '<div class="stem">{{Stem}}</div>\n'
        '<div class="choices">\n'
        '  <div class="choice"><span class="label">A.</span> {{ChoiceA}}</div>\n'
        '  <div class="choice"><span class="label">B.</span> {{ChoiceB}}</div>\n'
        '  <div class="choice"><span class="label">C.</span> {{ChoiceC}}</div>\n'
        '  <div class="choice"><span class="label">D.</span> {{ChoiceD}}</div>\n'
        '  <div class="choice"><span class="label">E.</span> {{ChoiceE}}</div>\n'
        "</div>\n"
        '<div class="type-tag"><code>{{TypeTag}}</code></div>'
    )
    t["afmt"] = (
        "{{FrontSide}}\n"
        '<hr id="answer">\n'
        '<div class="correct">Correct: <strong>{{CorrectChoice}}</strong></div>\n'
        '<div class="explanations">\n'
        "  <div>A: {{WhyWrongA}} "
        "{{#TrapChoiceA}}<code>{{TrapChoiceA}}</code>{{/TrapChoiceA}}</div>\n"
        "  <div>B: {{WhyWrongB}} "
        "{{#TrapChoiceB}}<code>{{TrapChoiceB}}</code>{{/TrapChoiceB}}</div>\n"
        "  <div>C: {{WhyWrongC}} "
        "{{#TrapChoiceC}}<code>{{TrapChoiceC}}</code>{{/TrapChoiceC}}</div>\n"
        "  <div>D: {{WhyWrongD}} "
        "{{#TrapChoiceD}}<code>{{TrapChoiceD}}</code>{{/TrapChoiceD}}</div>\n"
        "  <div>E: {{WhyWrongE}} "
        "{{#TrapChoiceE}}<code>{{TrapChoiceE}}</code>{{/TrapChoiceE}}</div>\n"
        "</div>\n"
        "{{#TrapTag}}"
        '<div class="stim-trap">Stimulus flaw: <code>{{TrapTag}}</code></div>'
        "{{/TrapTag}}\n"
        '<div class="source">{{Source}}</div>\n'
        '<div class="skill-tags"><code>{{SkillTag}}</code></div>'
    )
    col.models.add_template(m, t)
    col.models.set_sort_index(m, 0)  # sort by Stimulus
    return m


# ---------------------------------------------------------------------------
# Taxonomy-driven skill note data
# ---------------------------------------------------------------------------

def _load_taxonomy() -> dict[str, Any]:
    with open(TAXONOMY_JSON, encoding="utf-8") as f:
        return json.load(f)


def _skill_notes_from_taxonomy(taxonomy: dict[str, Any]) -> list[dict[str, str]]:
    """
    Build the list of LSAT Skill note field-dicts from taxonomy.json.
    One note per axis-1 question type, axis-2 sub-skill, and trap entry.
    """
    notes: list[dict[str, str]] = []

    for qt in taxonomy["axis1_question_types"]:
        notes.append(
            {
                "SkillName": qt["canonical_name"],
                "SkillType": "question-type",
                "IdentityTag": qt["tag"],
                "Description": qt["description"],
                "KeyTechnique": "",
                "CommonErrors": "",
                "Notes": (
                    f"Approx. frequency: {qt['approx_frequency_pct']}% of LR items. "
                    f"Concordance: {', '.join(qt['concordance'])}."
                    if qt.get("concordance")
                    else f"Approx. frequency: {qt['approx_frequency_pct']}% of LR items."
                ),
            }
        )

    for sk in taxonomy["axis2_reasoning_subskills"]:
        notes.append(
            {
                "SkillName": sk["name"],
                "SkillType": "reasoning-subskill",
                "IdentityTag": sk["tag"],
                "Description": sk["description"],
                "KeyTechnique": "",
                "CommonErrors": "",
                "Notes": f"Priority: {sk['priority']}.",
            }
        )

    trap_cat = taxonomy["trap_catalog"]
    for trap in trap_cat["argument_flaws"] + trap_cat["distractor_traps"]:
        notes.append(
            {
                "SkillName": trap["name"],
                "SkillType": "trap",
                "IdentityTag": trap["tag"],
                "Description": trap["description"],
                "KeyTechnique": "",
                "CommonErrors": "",
                "Notes": f"Frequency: {trap['frequency']}.",
            }
        )

    return notes


# ---------------------------------------------------------------------------
# Seed Meta content
# ---------------------------------------------------------------------------

_SEED_META_NOTES: list[dict[str, str]] = [
    {
        "Front": "Conclusion",
        "Back": "The main claim the argument is trying to establish. Usually follows conclusion indicators (therefore, thus, hence). First move: find it.",
        "Category": "vocab",
        "Source": "PowerScore LRB; LawHub",
        "Notes": "Misidentifying the conclusion is the root cause of most LR errors (K.2).",
    },
    {
        "Front": "Premise",
        "Back": "Evidence or reasons offered in support of the conclusion. Usually follows premise indicators (because, since, given that, for).",
        "Category": "vocab",
        "Source": "PowerScore LRB",
        "Notes": "",
    },
    {
        "Front": "Assumption",
        "Back": "An unstated premise the argument depends on. A necessary assumption: if negated, the argument fails. A sufficient assumption: if true, guarantees the conclusion.",
        "Category": "vocab",
        "Source": "PowerScore LRB §7",
        "Notes": "Use the Assumption Negation Test to identify necessary assumptions.",
    },
    {
        "Front": "Sufficient condition",
        "Back": "If A is sufficient for B, then A's presence guarantees B. Written: A → B. Does NOT mean B requires A.",
        "Category": "vocab",
        "Source": "PowerScore LRB §10",
        "Notes": "Confusing sufficient with necessary is the most common LR flaw (K.2).",
    },
    {
        "Front": "Necessary condition",
        "Back": "If A is necessary for B, then B cannot occur without A. Written: B → A (or ¬A → ¬B). A's presence does NOT guarantee B.",
        "Category": "vocab",
        "Source": "PowerScore LRB §10",
        "Notes": "Indicator words: 'only if', 'requires', 'must', 'cannot…without'.",
    },
    {
        "Front": "Contrapositive",
        "Back": "Logically equivalent to a conditional: if A → B, then ¬B → ¬A. Always valid; used to make inferences from negated consequents.",
        "Category": "vocab",
        "Source": "PowerScore LRB §10",
        "Notes": "Forming the contrapositive is a core conditional-reasoning skill.",
    },
    {
        "Front": "Sufficient / Necessary Confusion (flaw)",
        "Back": "Treating a sufficient condition as necessary, or vice versa. Example: 'All A are B, therefore all B are A.' Most common LR flaw.",
        "Category": "flaw",
        "Source": "PowerScore LRB §10; Leland LSAT",
        "Notes": "Tag: trap::sufficient-necessary",
    },
    {
        "Front": "Correlation vs. Causation (flaw)",
        "Back": "Inferring that because two things correlate, one causes the other. Ignores alternate causes, common cause, and reverse causation.",
        "Category": "flaw",
        "Source": "PowerScore LRB §12",
        "Notes": "Tag: trap::correlation-causation",
    },
    {
        "Front": "Hasty Generalization (flaw)",
        "Back": "Drawing a broad conclusion from an unrepresentative or too-small sample.",
        "Category": "flaw",
        "Source": "PowerScore LRB §12",
        "Notes": "Tag: trap::hasty-generalization",
    },
    {
        "Front": "Conclusion indicator words",
        "Back": "therefore · thus · hence · so · consequently · it follows that · which means · clearly · obviously · we can conclude",
        "Category": "indicator",
        "Source": "PowerScore LRB §2",
        "Notes": "When you see these, the conclusion likely follows.",
    },
    {
        "Front": "Premise indicator words",
        "Back": "because · since · given that · for · as · in light of the fact that · the reason is · after all",
        "Category": "indicator",
        "Source": "PowerScore LRB §2",
        "Notes": "When you see these, a premise follows.",
    },
    {
        "Front": "Quantifier: 'All A are B'",
        "Back": "Universal affirmative. A → B. Contrapositive: ¬B → ¬A. Does NOT imply B → A (converse) or ¬A → ¬B (inverse).",
        "Category": "indicator",
        "Source": "PowerScore LRB §10",
        "Notes": "Confusion of converse and inverse is a very common flaw on quantifier items.",
    },
    {
        "Front": "Quantifier: 'Some A are B'",
        "Back": "Existential: at least one A is B. Does NOT imply all A are B, or most A are B. Survives chaining: if some A are B, and all B are C, then some A are C.",
        "Category": "indicator",
        "Source": "PowerScore LRB §10",
        "Notes": "Key inference rule: Some A → B + All B → C ⊢ Some A → C.",
    },
]


# ---------------------------------------------------------------------------
# Collection builder
# ---------------------------------------------------------------------------

def build_seed_deck(
    col_path: str,
    items_json_path: str | Path = DEFAULT_ITEMS_JSON,
    min_pool_size: int = MIN_POOL_SIZE_SEED,
    verbose: bool = True,
) -> CoverageReport:
    """
    Build the Speedrun seed deck in the collection at col_path.

    Creates notetypes, skill notes, item notes (suspended), and meta notes.
    Returns a CoverageReport indicating which skills have sufficient pool coverage.

    Raises ImportError if the anki package is not available.
    Raises FileNotFoundError if required JSON files are missing.
    """
    # Late import so the module is importable even without the anki wheel.
    try:
        from anki.collection import Collection
    except ImportError as e:
        raise ImportError(
            "The anki package is not installed. Build the Anki wheel first "
            "('just wheels') or install it, then re-run this script."
        ) from e

    if not TAXONOMY_JSON.exists():
        raise FileNotFoundError(f"taxonomy.json not found: {TAXONOMY_JSON}")
    if not Path(items_json_path).exists():
        raise FileNotFoundError(f"items JSON not found: {items_json_path}")

    taxonomy = _load_taxonomy()

    with open(items_json_path, encoding="utf-8") as f:
        items_data = json.load(f)

    col = Collection(col_path)
    try:
        _populate_collection(col, taxonomy, items_data, min_pool_size, verbose)
        report = _build_coverage_report(col, taxonomy, min_pool_size)
    finally:
        col.close()

    return report


def _populate_collection(
    col: Any,
    taxonomy: dict[str, Any],
    items_data: dict[str, Any],
    min_pool_size: int,
    verbose: bool,
) -> None:
    # ------------------------------------------------------------------ decks
    meta_did = col.decks.id(DECK_META)
    skills_did = col.decks.id(DECK_SKILLS)
    items_did = col.decks.id(DECK_ITEMS)

    # ------------------------------------------- deck options preset (>20/day)
    # The default preset caps new cards at 20/day; assign a Speedrun preset with
    # a higher limit so all skills/meta cards are available.
    conf_id = col.decks.add_config_returning_id(DECK_CONFIG_NAME)
    conf = col.decks.get_config(conf_id)
    assert conf is not None, "Failed to create Speedrun deck config"
    conf["new"]["perDay"] = NEW_CARDS_PER_DAY
    conf["rev"]["perDay"] = REVIEWS_PER_DAY
    col.decks.update_config(conf)
    for did in (meta_did, skills_did, items_did):
        deck = col.decks.get(did)
        assert deck is not None
        deck["conf"] = conf_id
        col.decks.save(deck)
    if verbose:
        print(f"  Set '{DECK_CONFIG_NAME}' preset: {NEW_CARDS_PER_DAY} new/day, {REVIEWS_PER_DAY} rev/day.")

    # ------------------------------------------------------------ notetypes
    nt_meta = _make_notetype_meta(col)
    col.models.add(nt_meta)
    nt_meta = col.models.by_name(NOTETYPE_META)
    assert nt_meta is not None, "Failed to create LSAT Meta notetype"

    nt_skill = _make_notetype_skill(col)
    col.models.add(nt_skill)
    nt_skill = col.models.by_name(NOTETYPE_SKILL)
    assert nt_skill is not None, "Failed to create LSAT Skill notetype"

    nt_item = _make_notetype_item(col)
    col.models.add(nt_item)
    nt_item = col.models.by_name(NOTETYPE_ITEM)
    assert nt_item is not None, "Failed to create LSAT Item notetype"

    # -------------------------------------------------- LSAT Skill notes
    skill_note_dicts = _skill_notes_from_taxonomy(taxonomy)
    added_skills = 0
    for nd in skill_note_dicts:
        note = col.new_note(nt_skill)
        for fname, val in nd.items():
            note[fname] = val
        # Apply the IdentityTag as a card tag for pool-search compatibility.
        # Anki uses :: as the native tag-hierarchy separator (rslib/src/tags),
        # so store tags with :: intact (D-SR24 / B009).
        note.tags = [nd["IdentityTag"]]
        col.add_note(note, skills_did)
        added_skills += 1
    if verbose:
        print(f"  Added {added_skills} LSAT Skill notes.")

    # ------------------------------------------------- LSAT Item notes (suspended)
    items = items_data.get("items", [])
    added_items = 0
    for item_dict in items:
        # Guard: reject items missing SyntheticFlag or with SyntheticFlag != SYNTHETIC
        if item_dict.get("SyntheticFlag") != "SYNTHETIC":
            raise ValueError(
                f"Item {item_dict.get('_id', '?')} is missing SyntheticFlag=SYNTHETIC. "
                "Real LSAT items must not be included in the seed deck (D-SR11)."
            )
        note = col.new_note(nt_item)
        for fname in [f["name"] for f in nt_item["flds"]]:
            note[fname] = str(item_dict.get(fname, ""))

        # Apply taxonomy tags for pool-search compatibility.
        tags = []
        for tag_field in ("TypeTag", "SkillTag", "TrapTag"):
            raw = item_dict.get(tag_field, "")
            tags.extend(t for t in raw.split() if t)
        tags.append("synthetic::true")
        note.tags = tags

        col.add_note(note, items_did)

        # Suspend all cards for this item note (it's a pool, not a study deck).
        cards = note.cards()
        if cards:
            col.sched.suspend_cards([c.id for c in cards])
        added_items += 1
    if verbose:
        print(f"  Added {added_items} LSAT Item notes (all suspended).")

    # -------------------------------------------------- LSAT Meta notes
    added_meta = 0
    for nd in _SEED_META_NOTES:
        note = col.new_note(nt_meta)
        for fname, val in nd.items():
            note[fname] = val
        category_tag = f"category::{nd['Category']}"
        note.tags = [category_tag]
        col.add_note(note, meta_did)
        added_meta += 1
    if verbose:
        print(f"  Added {added_meta} LSAT Meta notes.")


def _build_coverage_report(
    col: Any,
    taxonomy: dict[str, Any],
    min_pool_size: int,
) -> CoverageReport:
    """
    For each skill in axis1_question_types, count how many LSAT Item notes are
    tagged with its type:: tag. Mark as covered if count >= min_pool_size.
    """
    report = CoverageReport()
    for qt in taxonomy["axis1_question_types"]:
        tag = qt["tag"]
        report.total_skills += 1
        # Search for notes in the Items deck tagged with this type tag.
        # Anki uses :: as the native tag-hierarchy separator (rslib/src/tags),
        # so tags are stored and searched with :: intact (D-SR24 / B009).
        # Anki search uses DOUBLE quotes for phrases; Python's !r emits single
        # quotes, which Anki mis-parses → 0 results (B021).
        note_ids = col.find_notes(f'tag:{tag} deck:"{DECK_ITEMS}"')
        count = len(note_ids)
        report.pool_counts[tag] = count
        if count >= min_pool_size:
            report.covered_skills.append(tag)
        else:
            report.uncovered_skills.append(tag)
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Speedrun seed deck.")
    parser.add_argument(
        "--col",
        required=True,
        help="Path to output .anki2 collection file, or ':temp:' to auto-create.",
    )
    parser.add_argument(
        "--items",
        default=str(DEFAULT_ITEMS_JSON),
        help="Path to sample_items.json (default: tools/speedrun/deck/sample_items.json).",
    )
    parser.add_argument(
        "--min-pool",
        type=int,
        default=MIN_POOL_SIZE_SEED,
        help=f"Minimum pool size for a skill to be 'covered' (default: {MIN_POOL_SIZE_SEED}).",
    )
    args = parser.parse_args(argv)

    col_path = args.col
    if col_path == ":temp:":
        fd, col_path = tempfile.mkstemp(suffix=".anki2", prefix="speedrun_seed_")
        os.close(fd)
        os.unlink(col_path)
        print(f"Using temp collection: {col_path}")

    print(f"Building seed deck → {col_path}")
    try:
        report = build_seed_deck(
            col_path=col_path,
            items_json_path=args.items,
            min_pool_size=args.min_pool,
        )
    except ImportError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(
        f"\nCoverage: {len(report.covered_skills)}/{report.total_skills} skills "
        f"({report.coverage_fraction:.0%}) have ≥{args.min_pool} items."
    )
    if report.uncovered_skills:
        print("Uncovered skills (below min pool size):")
        for tag in report.uncovered_skills:
            count = report.pool_counts.get(tag, 0)
            print(f"  {tag}: {count} items")
    else:
        print("All tracked skills are covered.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
