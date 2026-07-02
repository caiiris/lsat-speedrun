# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""End-to-end tests: call the Speedrun Rust engine change from Python.

These exercise the brownfield Rust additions through their pylib wrappers, so
they cover the whole path (Python → generated backend → Rust) rather than the
Rust unit tests' in-crate calls:

- ``col.sched.draw_item_for_skill`` — WP-3 fresh-item selection
  (``rslib/src/scheduler/queue/selection.rs``).
- ``col.skill_mastery``            — WP-5 mastery aggregate
  (``rslib/src/stats/service.rs`` + ``storage/card/speedrun.rs``).

The engine contract they depend on (mirrors ``tools/speedrun/deck/build_seed_deck.py``):
- item pool lives in the deck ``LSAT Speedrun::Items``;
- a skill card carries its identity tag (``type::``/``skill::``/``trap::``) as a note tag;
- mastery is aggregated over cards of the ``LSAT Skill`` notetype.
"""

from __future__ import annotations

from anki.collection import Collection
from tests.shared import getEmptyCol

ITEMS_DECK = "LSAT Speedrun::Items"
SKILLS_DECK = "LSAT Speedrun::Skills"
SKILL_NOTETYPE = "LSAT Skill"
ITEM_NOTETYPE = "LSAT Item"
FLAW_TAG = "type::flaw"


def _make_notetype(col: Collection, name: str, fields: list[str]) -> object:
    """Create + register a minimal notetype with the given field names."""
    m = col.models.new(name)
    for fname in fields:
        col.models.add_field(m, col.models.new_field(fname))
    t = col.models.new_template("Card 1")
    t["qfmt"] = "{{%s}}" % fields[0]
    t["afmt"] = "{{FrontSide}}"
    col.models.add_template(m, t)
    col.models.add(m)
    created = col.models.by_name(name)
    assert created is not None, f"failed to create notetype {name}"
    return created


def _add_note(
    col: Collection, notetype: object, deck_id: int, tag: str
) -> tuple[int, int]:
    """Add a note of ``notetype`` to ``deck_id`` tagged ``tag``.

    Returns ``(card_id, note_id)``.
    """
    note = col.new_note(notetype)  # type: ignore[arg-type]
    note[note.keys()[0]] = "content"
    note.tags = [tag]
    col.add_note(note, deck_id)
    return (note.cards()[0].id, note.id)


def _setup(col: Collection) -> tuple[int, list[int], int]:
    """Build a minimal Speedrun collection.

    Returns ``(skill_card_id, item_note_ids, skills_deck_id)``.
    """
    skill_nt = _make_notetype(col, SKILL_NOTETYPE, ["SkillName", "IdentityTag"])
    item_nt = _make_notetype(col, ITEM_NOTETYPE, ["Stimulus", "TypeTag"])

    skills_did = col.decks.id(SKILLS_DECK)
    items_did = col.decks.id(ITEMS_DECK)
    assert skills_did is not None and items_did is not None

    skill_cid, _ = _add_note(col, skill_nt, skills_did, FLAW_TAG)

    item_nids = []
    for _ in range(3):
        _, nid = _add_note(col, item_nt, items_did, FLAW_TAG)
        item_nids.append(nid)

    return (skill_cid, item_nids, skills_did)


def test_draw_item_for_skill_returns_pool_member():
    """draw_item_for_skill (Rust WP-3) returns an item note from the skill pool."""
    col = getEmptyCol()
    skill_cid, item_nids, _ = _setup(col)

    drawn = col.sched.draw_item_for_skill(skill_cid)

    assert drawn in item_nids, f"drawn item {drawn} not in pool {item_nids}"


def test_draw_item_for_skill_avoids_immediate_repeat():
    """Consecutive draws don't repeat the just-served item (sidecar window)."""
    col = getEmptyCol()
    skill_cid, item_nids, _ = _setup(col)

    first = col.sched.draw_item_for_skill(skill_cid)
    second = col.sched.draw_item_for_skill(skill_cid)

    assert first in item_nids and second in item_nids
    assert first != second, "second draw repeated the immediately-served item"


def test_draw_item_for_skill_errors_on_empty_pool():
    """A skill with no items in the pool surfaces an error to Python."""
    col = getEmptyCol()
    skill_nt = _make_notetype(col, SKILL_NOTETYPE, ["SkillName", "IdentityTag"])
    _make_notetype(col, ITEM_NOTETYPE, ["Stimulus", "TypeTag"])
    skills_did = col.decks.id(SKILLS_DECK)
    col.decks.id(ITEMS_DECK)  # exists but empty
    skill_cid, _ = _add_note(col, skill_nt, skills_did, FLAW_TAG)

    try:
        col.sched.draw_item_for_skill(skill_cid)
        raise AssertionError("expected an error for an empty item pool")
    except Exception:
        pass


def test_skill_mastery_aggregates_skill_cards():
    """skill_mastery (Rust WP-5) reports the skill's card count over the deck."""
    col = getEmptyCol()
    _, _, skills_did = _setup(col)

    mastery = col.skill_mastery(skills_did)

    by_skill = {m.skill: m for m in mastery}
    assert FLAW_TAG in by_skill, f"{FLAW_TAG} missing from {list(by_skill)}"
    entry = by_skill[FLAW_TAG]
    assert entry.total == 1, f"expected 1 flaw skill card, got {entry.total}"
    # The card is unreviewed, so it has no FSRS memory state → not mastered.
    assert entry.mastered == 0


def test_skill_mastery_empty_deck_is_empty():
    """A deck with no LSAT Skill cards yields no mastery rows."""
    col = getEmptyCol()
    empty_did = col.decks.id("Some Other Deck")

    mastery = col.skill_mastery(empty_did)

    assert list(mastery) == []
