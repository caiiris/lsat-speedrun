# WP-11 Inbox Log — AI Tagging Pipeline

> **Provisional local IDs (L1…)** — to be promoted to `decisions.md` / `backlog.md` by the
> next orchestrator pass.  Do NOT touch `backlog.md` or `decisions.md` directly.
> iris-log format · 2026-06-30 · WP-11 build agent (Sonnet 4.6)

---

## Design decisions

### L-D1 — Keyword baseline uses extended causal lexicon, not strict taxonomy key_indicators

- **Status:** resolved (WP-11)
- **File:** `tools/speedrun/tagging/baselines.py` `_KW_CAUSAL_RE`
- **Decided:** 2026-06-30
- **Chose:** The keyword baseline uses a "competent engineer" causal lexicon that includes
  "reduce/increases/responsible for/outcome/consequence" in addition to the 6 exact
  taxonomy `key_indicators`.  This makes the keyword baseline a fairer comparison point —
  it represents what a good keyword approach would produce, not the absolute floor.
  The AI stub still beats it via: (a) broader causal patterns, (b) question-type context
  for skill disambiguation, (c) choice-text scanning for trap detection.
- **Considered:** Using *only* the 6 exact taxonomy key_indicators (would make keyword
  trivially weak on causal — not a fair eval).
- **Ref:** `baselines.py:_KW_CAUSAL_RE`, spec-ai §4, D-SR14.

### L-D2 — DeterministicStubClient reads choice texts for trap detection (keyword baseline cannot)

- **Status:** resolved (WP-11, promotes to D-SR25 candidate)
- **File:** `tools/speedrun/tagging/tagger.py` `DeterministicStubClient._predict_traps`
- **Decided:** 2026-06-30
- **Chose:** The AI tagger (stub) receives full `ItemInput.choices` including wrong-choice
  text and scans each for trap patterns (too-extreme language, out-of-scope new content
  words, wrong-direction language).  The keyword baseline is restricted to `stem+stimulus`
  by definition.  This is the primary advantage of the AI tagger on the trap axis and the
  reason AI beats keyword on `trap::*` F1.
- **Considered:** Giving keyword baseline access to choice texts (would conflate the
  baselines; the whole point is that AI gets more information).
- **Ref:** `tagger.py:DeterministicStubClient`, `baselines.py:KeywordBaseline`,
  spec-ai §4 (keyword baseline on stem+stimulus).

### L-D3 — StemClassifier fallback is type::flaw (most frequent type on exam)

- **Status:** resolved (WP-11)
- **File:** `tools/speedrun/tagging/tagger.py` `StemClassifier._DEFAULT_TYPE`
- **Decided:** 2026-06-30
- **Chose:** When no stem rule matches, return `type::flaw` (most frequent exam type
  per J.1 — Flaw is currently most common, ~14%).  This is a conservative fallback
  that produces a valid taxonomy tag even for unusual stems.
- **Gaps/risks:** Unusual stems are silently downgraded to flaw — surfaced here so
  the next agent can decide whether to raise an exception instead (see L-B2).
- **Ref:** `tagger.py:StemClassifier`, brainlift J.1.

### L-D4 — Vector baseline uses kNN type vote but falls back to stem rules

- **Status:** resolved (WP-11)
- **File:** `tools/speedrun/tagging/baselines.py` `VectorKNNBaseline.predict_type`
- **Decided:** 2026-06-30
- **Chose:** `VectorKNNBaseline.predict_type()` tries kNN majority vote first; falls
  back to `StemClassifier` if no majority emerges.  This makes the vector baseline's
  type accuracy realistic (not artificially perfect) while still being sensible.
- **Ref:** `baselines.py:VectorKNNBaseline`.

---

## Ambiguities surfaced (open — need owner decision)

### L-A1 — `skill::abstraction` is poorly detectable by keyword/stub heuristics

- **Status:** known-gap
- **File:** `tools/speedrun/tagging/tagger.py` `DeterministicStubClient._predict_skills`
- **Discovered:** 2026-06-30, WP-11 stub evaluation.
- **Context:** `skill::abstraction` (stripping content to match logical form) is required
  for parallel/method question types AND for some flaw questions (e.g. hasty generalization).
  The stub correctly adds `abstraction` for parallel/method types but misses it for flaw
  questions where the flaw itself requires abstract structural reasoning.  This suppresses
  `abstraction` F1 to 0.0 on the gold set.
- **Resolution needed:** A real LLM can reason about the question structure and correctly
  add `abstraction` when appropriate.  For the stub, a flaw-question heuristic (add
  abstraction when no other skill beyond conclusion-id is detected) is a partial fix —
  already implemented as a fallback in the stub.
- **Ref:** `tagger.py:DeterministicStubClient._predict_skills`, brainlift K.4.

### L-A2 — Gold set is small (n=10 synthetic) — real eval needs ≥50 items + real LLM

- **Status:** known-gap (per spec-ai §4; real gold set deferred to B012)
- **Discovered:** 2026-06-30, WP-11 design.
- **Context:** spec-ai §4 calls for a "held-out eval" which implies a meaningful sample.
  10 synthetic items is enough to prove the pipeline works and that the stub shows the
  right ordering (AI ≥ keyword ≥ vector on skill/trap), but it is NOT sufficient to
  report statistically meaningful F1 numbers for a real deployment.  The eval explicitly
  notes this limitation in `format_table()`.
- **Resolution needed:** Once B012 (real LLM wiring) is done and real items are available,
  extend `gold_labels.json` to ≥50 items with human-verified labels.
- **Ref:** `gold_labels.json`, `eval.py`, spec-ai §4 AC-2.

### L-A3 — `trap::irrelevant-comparison` has low recall in the stub (not detectable from text alone)

- **Status:** known-gap
- **Discovered:** 2026-06-30, tracing gold_labels.json items 4 and 5.
- **Context:** `trap::irrelevant-comparison` (comparing entities not at issue) requires
  understanding what IS at issue in the argument — this is a semantic judgment, not a
  keyword one.  The stub cannot reliably detect it from choice text patterns alone.
  Items ASSUMPTION-001 and ASSUMPTION-002 both have this trap in gold, but the stub
  typically misses it.  This reduces trap macro-F1.
- **Resolution needed:** A real LLM with argument-analysis capabilities would handle this.
- **Ref:** `tagger.py:DeterministicStubClient._predict_traps`, gold_labels.json items 4,5.

### L-A4 — Unrecognized stems fall back silently to type::flaw (should this raise?)

- **Status:** open — decision needed
- **Discovered:** 2026-06-30, WP-11 StemClassifier design.
- **Context:** Currently, stems not matching any rule return the default `type::flaw`.
  This is conservative (avoids crashes) but could silently mislabel unusual stems.
  An alternative: raise `ValueError` when no rule matches, so callers know the stem
  is unrecognized and can route to the human-verify queue.
- **Resolution needed:** Owner to decide: silent fallback vs. explicit error.
- **Ref:** `tagger.py:StemClassifier._DEFAULT_TYPE`.

---

## Bugs / issues

### L-B1 — `trap::reversal` is hard to detect in choice text without semantic parse

- **Type:** known-gap · **Status:** open
- **Discovered:** 2026-06-30, WP-11 stub testing
- **File:** `tools/speedrun/tagging/tagger.py` `DeterministicStubClient._predict_traps`
- **Context:** The `_REVERSAL_RE` regex catches obvious "if B then A" wording but misses
  the subtler reversal where a choice says "X because Y" when the stimulus said "if Y then X".
  This reduces recall for `trap::reversal` (appears in INFERENCE-002 gold).
- **Resolution:** Needs real NLP/LLM — deferred to B012 (real LLM wiring).

### L-B2 — VectorKNNBaseline requires `fit()` before `propose_tags()` — no guard against misuse

- **Type:** issue · **Status:** open
- **Discovered:** 2026-06-30
- **File:** `tools/speedrun/tagging/baselines.py` `VectorKNNBaseline.propose_tags`
- **Context:** If `propose_tags()` is called without `fit()`, it raises `RuntimeError`.
  This is documented but not enforced at construction time.  A guard in `__init__`
  (lazy initialization or an unfitted flag) would improve safety.
- **Resolution:** Low priority — acceptable for eval use; add a check if used in production.

### L-B3 — `apply_tags._find_note()` scans all LSAT Item notes (O(n) linear search)

- **Type:** refactor · **Status:** open (acceptable for seed deck size)
- **Discovered:** 2026-06-30
- **File:** `tools/speedrun/tagging/apply_tags.py` `_find_note`
- **Context:** The current implementation iterates all LSAT Item notes and compares
  the `_id` field or `id::` tag.  For a seed deck of ~50–200 items this is fast enough,
  but for a large real-LSAT collection (7,500+ items) it would be slow.  A proper
  implementation would use `col.find_notes(f'note:"LSAT Item" "_id:{item_id}"')` or
  maintain an index.
- **Resolution:** Acceptable for v1 seed-deck scale; fix before production import of
  real PrepTest collections.

---

<sub>Maintained with the iris-log skill by Iris Cai · WP-11 (AI Tagging) build agent.</sub>
