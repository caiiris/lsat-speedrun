# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
pytest configuration for WP-12 card-check tests.

Adds the repo root to sys.path so ``tools.speedrun.cardcheck`` imports work
without installing the package.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Repo root is four levels up from this file:
# tools/speedrun/cardcheck/tests/conftest.py → root
_REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
