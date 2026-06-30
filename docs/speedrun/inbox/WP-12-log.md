# WP-12 Inbox Log — AI-card-check + injection guard (meta-vocab ONLY)

> **Provisional local IDs** (L1, L2, …). Do NOT promote to backlog.md/decisions.md
> without going through the iris-log workflow. Entries are iris-log format.
> Created: 2026-06-30 by Sonnet during WP-12 implementation.

---

## Decisions

### L-D1 — Factual checker uses lexical-token overlap, not semantic verification

- **Status:** resolved (for this WP; revisit in phase-2)
- **Chose:** The `FactualChecker` in `checker.py` verifies factual correctness via
  Jaccard-like token-coverage of the card answer against the cited source section
  (`FactualChecker._COVERAGE_THRESHOLD = 0.30`). This is deterministic, requires no
  model call, and is therefore D1-compliant (AI never owns correctness).
- **Considered:** Embedding-similarity (cosine over sentence vectors) — richer signal
  but reintroduces a model call at verify time. NLI-style entailment check — similar
  issue. Key-phrase extraction with rule-based matching — more work, modest gain.
- **Gaps / risks:** Lexical overlap cannot detect **semantic inversions**: a card that
  uses the exact vocabulary of the source but asserts the opposite meaning passes the
  factual check (e.g., "correlation *proves* causation" still overlaps with the
  §4.5 section that discusses the fallacy). This is a **known-gap** (see L-B1).
  The test suite documents the limitation with a comment and tests only the
  detectable case (entirely-absent tokens).
- **Ref:** `tools/speedrun/cardcheck/checker.py:FactualChecker`, `spec-ai §5`, `D1`

### L-D2 — Real LLM client deferred; stub is sufficient for WP-12 acceptance

- **Status:** resolved (stub) / open (real client)
- **Chose:** `DeterministicStubClient` generates cards by parsing `§N.M term` headings
  from the source text and extracting the first paragraph as the answer. No API key,
  no network. Answers come verbatim from the source, making factual verification
  meaningful. A real LLM is left as a clean seam (`LLMClient` protocol in
  `generator.py`) — implement and inject it to replace the stub.
- **Considered:** Hardcoding stub answers from the gold set — rejected because it
  defeats the factual check (the checker would trivially pass cards that regurgitate
  gold answers, which are themselves grounded in the source).
- **Gaps / risks:** The stub's cards are deterministically good (they quote the source).
  A real model will generate paraphrases and riskier content — the factual/quality
  checks will be exercised more severely. **This is an explicit seam to wire later.**
  The test suite and report both run against the stub and pass; a real-model eval is
  a separate WP.
- **Ref:** `tools/speedrun/cardcheck/generator.py:DeterministicStubClient`, `spec-ai §5`

### L-D3 — Pre-set cutoffs: 0 wrong-fact tolerance, 60% min useful rate

- **Status:** resolved
- **Chose:** `WRONG_FACT_TOLERANCE = 0` and `MIN_USEFUL_RATE = 0.60`, declared as
  module constants at the top of `report.py` before any pipeline code runs.
  60% is defensible as a floor: with a small n (~30) the Wilson CI is ±~18pp, so
  60% point estimate means the true rate is likely ≥42%. The zero wrong-fact
  tolerance is the strictest gate, per spec-ai §5 ("0 wrong-fact tolerance").
- **Considered:** 70% useful-rate floor — tighter but may unnecessarily fail a
  real model that generates some borderline-quality cards. 50% floor — too lenient
  for a teaching tool; a coin-flip useful rate is not acceptable.
- **Gaps / risks:** With stub-generated cards (which quote the source verbatim) the
  pipeline achieves ~93% useful rate in the smoke test, so the 60% floor is not
  binding on the stub. It becomes binding when a real model produces more diverse output.
- **Ref:** `tools/speedrun/cardcheck/report.py:WRONG_FACT_TOLERANCE`, `spec-ai §5`

### L-D4 — Duplicate threshold: Jaccard ≥ 0.65 on question tokens

- **Status:** resolved
- **Chose:** `DuplicationChecker._DUPLICATE_THRESHOLD = 0.65`. Two questions with
  Jaccard token-similarity ≥ 0.65 are considered near-duplicates; the second is
  blocked.
- **Considered:** Cosine over TF-IDF vectors (more sensitive to rare tokens, more
  complex). Edit-distance (good for spelling variants, not for semantic duplicates).
  0.65 was chosen because it catches paraphrase-level duplication ("What is a
  conclusion?" vs "What is a conclusion in an argument?") while allowing clearly
  distinct questions about the same concept.
- **Gaps / risks:** Very short questions can have high Jaccard by accident. The minimum
  question length check in QualityChecker mitigates this.
- **Ref:** `tools/speedrun/cardcheck/checker.py:DuplicationChecker`

---

## Bugs / Issues

### L-B1 — Factual checker does not catch semantic inversions (known-gap)

- **Type:** issue · **Status:** known-gap · **Severity:** medium
- **Discovered:** 2026-06-30 by Sonnet during WP-12 test authoring
- **Ref:** `tools/speedrun/cardcheck/checker.py:FactualChecker.check`,
  `tools/speedrun/cardcheck/tests/test_checker.py:TestWrongFactCard`
- **Context:** A card answer that uses the same vocabulary as the cited source section
  but asserts the opposite claim passes the lexical-coverage factual check. Example:
  "Correlation definitively *proves* causation" uses tokens ("correlation", "causation",
  "events", "alternative", "explanations") all present in §4.5, so coverage ≥ 30%.
  The semantic claim is wrong; the token check cannot detect it.
- **Resolution:** Not fixed in WP-12 (D1 forbids a model-judged verify; a symbolic
  negation-detector would help but is non-trivial). Test suite documents this with a
  comment and tests only the detectable case. Promote to backlog before phase-2 AI
  eval work if a real model is wired.
- **Mitigation in place:** The test for `test_wrong_fact_card_is_blocked` uses an
  answer with entirely foreign tokens (about photosynthesis/chlorophyll) that
  correctly fails the checker. The limitation is commented inline.

### L-B2 — DeterministicStub produces near-duplicate questions for similar section headings

- **Type:** bug · **Status:** known-gap · **Severity:** low
- **Discovered:** 2026-06-30 by Sonnet during pipeline smoke test
- **Ref:** `tools/speedrun/cardcheck/generator.py:DeterministicStubClient._make_question`
- **Context:** Sections with structurally similar headings generate questions with high
  Jaccard similarity. In the smoke test, `§2.1 conclusion indicators` and `§2.2 premise
  indicators` both generate questions of the form "What does '… indicators' signal in
  an argument? (§N.M)" — Jaccard 0.73, caught and blocked by DuplicationChecker.
  Similarly §3.3 and §3.4 (negation questions). The dedup checker correctly blocks the
  second card in each pair.
- **Resolution:** Not a bug in the checker (it works correctly). A real LLM would
  generate more diverse phrasings. The stub's mechanical question templates are the
  root cause; acceptable for WP-12 stub purposes. Not a correctness failure — the
  blocked cards show up in the report as `[duplicate]`.

---

## Ambiguities surfaced

### L-A1 — Source text scope: one file vs. multi-document corpus

- **Spec ref:** spec-ai §5 says "one cited source (e.g., a logic-textbook chapter / LSAC
  concept descriptions)." `logic_meta_vocab.txt` is a self-authored summary grounded
  in the cited references (LSAC/LawHub, PowerScore, Hurley, Copi & Cohen; brainlift
  J.3, Insight 5). The citations are stated in the file header.
- **Ambiguity:** Is a self-authored summary of multiple cited sources sufficient, or
  must the source be a verbatim excerpt from a single published text?
- **Disposition:** Implemented the smallest defensible thing: a single `.txt` file with
  explicit citations in its header, covering the three domain clusters (argument
  vocabulary, indicator words, quantifiers + fallacies). This is the cited source for
  both the generator and checker. A real implementation should use a canonical primary
  source (e.g., an LSAC concept-description page, or a specific chapter DOI).

### L-A2 — LLM client is not wired; real-model eval not run

- **Spec ref:** spec-ai §5 says "generate from a cited source, run vs the 50-item gold
  set." The gold set is built and the pipeline structure is in place, but the eval
  against the gold set itself (matching generated Q&A pairs against gold Q&A pairs)
  is not implemented — only the checker (factual / dedup / quality) is.
- **Ambiguity:** Does "run vs the 50-item gold set" mean (a) use the gold set as a held-
  out reference for factual verification, or (b) generate cards and measure recall
  against the gold set (how many gold items did the generator cover)?
- **Disposition:** Implemented interpretation (a): the gold set's `source_ref` fields
  point to the same sections the checker uses for factual verification. The gold set
  is also integrity-tested (37 tests, all pass). Interpretation (b) would require a
  semantic matching step between generated cards and gold Q&A pairs, which needs an
  embeddings/LLM layer not available without a real client. Surface this for the wiring
  task.

---

<sub>Maintained with the iris-log skill by Iris Cai.</sub>
