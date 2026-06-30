# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Taxonomy loader for Speedrun WP-11.

Loads ``docs/speedrun/data/taxonomy.json`` and exposes the valid tag strings.
Tags use Anki's native '::' separator (D-SR24):
    type::flaw, skill::conditional, trap::half-true

The taxonomy is the *contract*: any produced tag not in the taxonomy raises
:class:`TagValidationError` loudly.  Fail loud is intentional — a silent tag
miss would corrupt the pool query and score (D-SR17, D-SR23).

spec-ai §4 · D-SR13 · D-SR17 · D-SR24
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_TAXONOMY_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "speedrun"
    / "data"
    / "taxonomy.json"
)


class TagValidationError(ValueError):
    """Raised when a produced tag is not in the taxonomy (fail-loud contract)."""


@dataclass(frozen=True)
class Taxonomy:
    """
    Parsed taxonomy with fast membership lookup via frozensets.

    Tags are strings in the form ``prefix::slug`` per D-SR24.
    Subtypes (e.g. ``type::method-role``) are included in ``valid_type_tags``.
    """

    valid_type_tags: frozenset[str]
    valid_skill_tags: frozenset[str]
    valid_trap_tags: frozenset[str]

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def all_valid_tags(self) -> frozenset[str]:
        return self.valid_type_tags | self.valid_skill_tags | self.valid_trap_tags

    def is_type_tag(self, tag: str) -> bool:
        return tag in self.valid_type_tags

    def is_skill_tag(self, tag: str) -> bool:
        return tag in self.valid_skill_tags

    def is_trap_tag(self, tag: str) -> bool:
        return tag in self.valid_trap_tags

    # ------------------------------------------------------------------
    # Validation (fail-loud)
    # ------------------------------------------------------------------

    def validate_tag(self, tag: str) -> None:
        """Raise :class:`TagValidationError` if *tag* is not in the taxonomy."""
        if tag not in self.all_valid_tags:
            raise TagValidationError(
                f"Tag {tag!r} is not a valid taxonomy tag. "
                f"Valid tags ({len(self.all_valid_tags)} total): "
                f"{sorted(self.all_valid_tags)}"
            )

    def validate_tags(self, tags: list[str]) -> None:
        """Validate every tag in *tags*, raising on the first invalid one."""
        for tag in tags:
            self.validate_tag(tag)

    def validate_native_separator(self, tag: str) -> None:
        """
        Raise if *tag* uses ``_`` where ``::`` is expected (D-SR24 guard).

        Example: ``type_flaw`` raises; ``type::flaw`` passes.
        """
        if "::" not in tag:
            raise TagValidationError(
                f"Tag {tag!r} does not contain '::'.  Tags MUST use Anki's "
                f"native '::' separator (D-SR24).  Never normalize '::' to '_'."
            )


def load_taxonomy(path: Path | None = None) -> Taxonomy:
    """
    Load ``taxonomy.json`` and return a :class:`Taxonomy`.

    Raises :class:`FileNotFoundError` or :class:`json.JSONDecodeError` on
    malformed input — both are intentionally unhandled (fail-loud by design).
    """
    taxonomy_path = path or _DEFAULT_TAXONOMY_PATH
    data: dict = json.loads(taxonomy_path.read_text(encoding="utf-8"))

    type_tags: set[str] = set()
    skill_tags: set[str] = set()
    trap_tags: set[str] = set()

    # Axis-1 canonical types
    for qt in data.get("axis1_question_types", []):
        type_tags.add(qt["tag"])
        # Inline subtype strings listed on the parent entry
        for sub in qt.get("subtypes", []):
            if isinstance(sub, str):
                type_tags.add(sub)

    # Axis-1 subtype objects (authoritative; may overlap with above, no problem)
    for st in data.get("axis1_subtypes", []):
        type_tags.add(st["tag"])

    # Axis-2 reasoning sub-skills
    for sk in data.get("axis2_reasoning_subskills", []):
        skill_tags.add(sk["tag"])

    # Trap catalog — argument flaws + distractor traps
    trap_catalog = data.get("trap_catalog", {})
    for flaw in trap_catalog.get("argument_flaws", []):
        trap_tags.add(flaw["tag"])
    for distractor in trap_catalog.get("distractor_traps", []):
        trap_tags.add(distractor["tag"])

    return Taxonomy(
        valid_type_tags=frozenset(type_tags),
        valid_skill_tags=frozenset(skill_tags),
        valid_trap_tags=frozenset(trap_tags),
    )
