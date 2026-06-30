# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""
Speedrun WP-11 — AI tagging module.

Tags imported LSAT items on two axes + distractor traps:
  - Axis 1: question type  (deterministic stem rules, J.1)
  - Axis 2: reasoning sub-skill + trap (AI-proposed via LLMClient, human-verified)

spec-ai §4 · D-SR14 · D-SR23 (item-level trap tags) · D-SR24 (native :: tags)
"""
