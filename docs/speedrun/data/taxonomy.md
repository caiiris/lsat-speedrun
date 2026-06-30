# Speedrun — LR Taxonomy

> **Stable data contract** for WP-1 and all downstream work packages.  
> Authority: D-SR13 (PowerScore-based, two axes + trap catalog).  
> Source of truth for tag strings. Do not change tag slugs without a new decision entry.

## Tag namespace summary

| Axis | Prefix | Example |
|---|---|---|
| Question type (axis 1) | `type::` | `type::flaw` |
| Reasoning sub-skill (axis 2) | `skill::` | `skill::conditional` |
| Flaw / distractor trap | `trap::` | `trap::sufficient-necessary` |

---

## Axis 1 — Question Types (~13)

These map onto the PowerScore classification, which is industry-consensus (J.1).
Exact names here are the canonical Speedrun names; the concordance column records
major aliases across other publishers.

| # | Canonical name | Tag slug | Concordance | Notes |
|---|---|---|---|---|
| 1 | Must Be True / Inference | `inference` | "Identify an Entailment" (Khan), "Fill-In" (Loophole), "Inference" (LSAT Trainer) | Deduction from given facts |
| 2 | Main Point | `main-point` | "Conclusion" (some), "Main Conclusion" | Find the primary conclusion of the argument |
| 3 | Point at Issue | `point-at-issue` | Includes Point of Agreement variant | Two speakers disagree about X |
| 4 | Method of Reasoning | `method` | "Method of Argument"; "Role of a Statement" is a **subtype** (`type::method role`) | How does the argument work? |
| 5 | Flaw in Reasoning | `flaw` | "Error in Reasoning"; "Parallel Flaw" is a **subtype** (`type::parallel flaw`) | Most frequent type (≈14%) |
| 6 | Parallel Reasoning | `parallel` | Includes Parallel Flaw subtype | Map to abstract logical form |
| 7 | Strengthen | `strengthen` | "Support"; "Justify" subtypes handled separately | Which choice most strengthens? |
| 8 | Assumption (Necessary) | `assumption` | "Defender/Supporter" method (PowerScore) | What must be assumed for the argument to work? |
| 9 | Justify the Conclusion | `justify` | "Sufficient Assumption"; "SA" questions | Which choice, if true, makes conclusion follow? |
| 10 | Weaken | `weaken` | "Undermine" | Which choice most undermines? |
| 11 | Evaluate the Argument | `evaluate` | "Assess the Impact" | Which question most helps evaluate? |
| 12 | Resolve the Discrepancy | `paradox` | "Paradox"; "Explain"; "Reconcile" | Which resolves the apparent contradiction? |
| 13 | Principle | `principle` | PowerScore: an "overlay"; subtypes: `principle-identify` / `principle-apply` | Identify or apply a general rule |

**Tag strings:** `type::inference`, `type::main-point`, `type::point-at-issue`,
`type::method`, `type::flaw`, `type::parallel`, `type::strengthen`,
`type::assumption`, `type::justify`, `type::weaken`, `type::evaluate`,
`type::paradox`, `type::principle`.

**Subtypes** (supplementary tags added alongside the primary type tag):
- `type::method-role` — Role of a Statement variant of Method questions
- `type::parallel-flaw` — Parallel Flaw variant of Parallel questions
- `type::principle-identify` — identify-a-principle variant
- `type::principle-apply` — apply-a-principle variant

### Ambiguity note (A1)
PowerScore counts Principle as an "overlay" (not a standalone type) and Role as a
subtype of Method. This taxonomy promotes Principle to a full type (13) and Role to
a subtype, which is consistent with Magoosh/frequency data but diverges from strict
PowerScore. Recorded as L3 in `docs/speedrun/inbox/WP-1-log.md`.

---

## Axis 2 — Reasoning Sub-Skills

Cross-cutting skills beneath the question-type axis. Fuzzier than axis 1 — AI-assisted
tagging then human-verified (D-SR14). Priority notes come from K.4.

| # | Name | Tag slug | Priority | Notes |
|---|---|---|---|---|
| 1 | Conclusion / Premise Identification | `conclusion-id` | **Critical** | Cascades: misID → assumption / flaw / strengthen failures |
| 2 | Conditional Reasoning | `conditional` | **High** | Sufficient/necessary, if/then, contrapositive chains; most common flaw source |
| 3 | Causal Reasoning | `causal` | **High** | Strengthen/weaken levers on causal arguments (alternate cause, reverse causation, etc.) |
| 4 | Prephrasing | `prephrase` | Medium | Generating a prediction before reading choices (generation step, K.1) |
| 5 | Formal-Logic Quantifiers | `quantifier` | Low | all/most/some/none inference rules; rare on the test |
| 6 | Abstraction | `abstraction` | High (hardest) | Stripping content to match logical form — parallel reasoning, abstract-flaw identification |

**Tag strings:** `skill::conclusion-id`, `skill::conditional`, `skill::causal`,
`skill::prephrase`, `skill::quantifier`, `skill::abstraction`.

---

## Trap Catalog

A **finite enumerable catalog** of named traps (J.2 / App-design stance D5).
Two sub-categories: **argument flaws** (in the stimulus — what `type::flaw` questions
ask about) and **distractor traps** (wrong-answer patterns in answer choices).

Tags use a unified `trap::` prefix; the sub-category is documented in the catalog
and in the `TrapCategory` field of each trap entry.

### Sub-catalog A: Argument Flaws (in stimulus)

| # | Name | Tag slug | Notes |
|---|---|---|---|
| F1 | Sufficient / Necessary Confusion | `sufficient-necessary` | Most common flaw on the exam; conflates "if A then B" with "if B then A" |
| F2 | Correlation vs. Causation | `correlation-causation` | Assumes correlation implies causation |
| F3 | Circular Reasoning | `circular` | Conclusion restates or presupposes a premise (begging the question) |
| F4 | Equivocation | `equivocation` | Key term shifts meaning between premise and conclusion |
| F5 | Part-to-Whole / Whole-to-Part | `part-whole` | What is true of parts must be true of the whole (or vice versa) |
| F6 | Hasty Generalization | `hasty-generalization` | Sample is unrepresentative; conclusion over-generalizes |
| F7 | False Dichotomy | `false-dichotomy` | Presents two options as exhaustive when others exist |
| F8 | Straw Man | `straw-man` | Misrepresents opponent's position then attacks the misrepresentation |
| F9 | Ad Hominem | `ad-hominem` | Attacks the source/speaker rather than the argument |
| F10 | Appeal to Inappropriate Authority | `appeal-authority` | Cites authority without warrant for the specific claim |
| F11 | Analogical Flaw | `false-analogy` | Analogy between situations that differ in a relevant respect |
| F12 | Scope Shift | `scope-shift` | Conclusion concerns a different entity/property than what premises support |

### Sub-catalog B: Distractor / Answer-Choice Traps

| # | Name | Tag slug | Notes |
|---|---|---|---|
| D1 | Half-True | `half-true` | Choice is partially correct but incomplete or imprecise |
| D2 | Too Extreme | `too-extreme` | Goes beyond what premises support (uses absolute language where stimulus is hedged) |
| D3 | Out of Scope | `out-of-scope` | Introduces concept not in the stimulus |
| D4 | Contradicts Text | `contradicts` | Directly contradicts stated or inferable facts |
| D5 | Wrong Direction | `wrong-direction` | Strengthens when asked to weaken, or vice versa |
| D6 | Reversal | `reversal` | Confuses sufficient and necessary in the answer choice itself |
| D7 | Irrelevant Comparison | `irrelevant-comparison` | Compares things that are not at issue |

**Tag strings (all):**
`trap::sufficient-necessary`, `trap::correlation-causation`, `trap::circular`,
`trap::equivocation`, `trap::part-whole`, `trap::hasty-generalization`,
`trap::false-dichotomy`, `trap::straw-man`, `trap::ad-hominem`,
`trap::appeal-authority`, `trap::false-analogy`, `trap::scope-shift`,
`trap::half-true`, `trap::too-extreme`, `trap::out-of-scope`,
`trap::contradicts`, `trap::wrong-direction`, `trap::reversal`,
`trap::irrelevant-comparison`.

---

## Tagging rules

1. Every LSAT Item note carries **exactly one** `type::` tag (the question type).
2. Every LSAT Item note carries **one or more** `skill::` tags (the reasoning sub-skills exercised).
3. Wrong answer choices carry a `trap::` tag for each distractor trap; the stimulus
   flaw (for `type::flaw` questions) also carries a `trap::` tag.
4. Every LSAT Skill note carries exactly one identity tag: a `type::`, `skill::`, or `trap::` tag.
5. Tag strings are **kebab-case, lowercase**. No spaces inside a tag value.

---

<sub>Created with the `iris-log` skill by Iris Cai · WP-1 data contract.</sub>
