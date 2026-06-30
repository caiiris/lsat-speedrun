# Speedrun — Notetype Definitions

> **Stable data contract** for WP-1. Defines fields + templates for the three
> notetypes described in spec-engine §7. Do not add, remove, or rename fields
> without a new decision entry (other WPs build on these field names).

---

## Overview

| Notetype | Role | Drives | Card state |
|---|---|---|---|
| `LSAT Meta` | Declarative vocabulary, flaw defs, indicator words | **Memory** score | Active (studied by FSRS) |
| `LSAT Skill` | One note per skill/trap → one skill card each | **Performance** score (FSRS unit) | Active (FSRS-scheduled) |
| `LSAT Item` | The item pool: full LR stimuli with 5 choices | Pool only | **Suspended** (never directly studied; drawn by the engine on demand) |

---

## 1. Notetype: `LSAT Meta`

Memory layer — automating the declarative meta-vocabulary (logic/argument terms,
named-flaw catalog, indicator and quantifier words). Insight 5 / D-SR2.

### Fields

| # | Field name | Required | Notes |
|---|---|---|---|
| 1 | `Front` | ✓ | The term, phrase, or indicator word |
| 2 | `Back` | ✓ | Definition, explanation, or usage note |
| 3 | `Category` | ✓ | One of: `vocab` \| `flaw` \| `indicator` |
| 4 | `Source` | | Citation string, e.g. `PowerScore LRB §3.2` |
| 5 | `Notes` | | Additional context, examples, caveats |

### Template: `Recall`

**Front:**
```html
<div class="category">{{Category}}</div>
<div class="front">{{Front}}</div>
```

**Back:**
```html
{{FrontSide}}
<hr id="answer">
<div class="back">{{Back}}</div>
{{#Notes}}<div class="notes">{{Notes}}</div>{{/Notes}}
{{#Source}}<div class="source">Source: {{Source}}</div>{{/Source}}
```

### Deck / tag conventions
- Deck: `LSAT Speedrun::Meta`
- Tags: `category::vocab`, `category::flaw`, `category::indicator` (mirrors the `Category` field)
- No `type::` / `skill::` / `trap::` tags needed (these are meta-layer cards)

### Seed content categories
- **vocab** (≈15 cards): premise, conclusion, assumption, inference, necessary, sufficient, argument, fact-set, contradiction, paradox, principle, analogy, contrapositives, biconditional, scope
- **flaw** (≈12 cards): one card per named flaw in `trap_catalog.argument_flaws` (taxonomy.json)
- **indicator** (≈20 cards): premise indicators (since, because, given that, for), conclusion indicators (therefore, thus, hence, so, which means), quantifiers (all, most, some, none, few)

---

## 2. Notetype: `LSAT Skill`

The **FSRS-scheduled unit**. One note = one skill/trap = one card. On a due review,
the engine draws a fresh LSAT Item from the pool and serves it (spec-engine §5.2);
the skill card's own template is secondary (a study-aid prompt, not the review surface).

### Fields

| # | Field name | Required | Notes |
|---|---|---|---|
| 1 | `SkillName` | ✓ | Human-readable name, e.g. `Flaw in Reasoning` |
| 2 | `SkillType` | ✓ | One of: `question-type` \| `reasoning-subskill` \| `trap` |
| 3 | `IdentityTag` | ✓ | Exact tag string for this skill: `type::flaw`, `skill::conditional`, `trap::sufficient-necessary`, etc. |
| 4 | `Description` | ✓ | What this skill/trap is; what you're being tested on |
| 5 | `KeyTechnique` | | PowerScore method or heuristic for this type |
| 6 | `CommonErrors` | | Cataloged error modes (K.2) for this skill |
| 7 | `Notes` | | Additional context, frequency info, references |

### Template: `Skill Review`

This template shows during Level-1 reviews (item-as-card mode) as a method
reminder before the commit phase. In Level-2, the drawn LSAT Item is rendered
instead; this template serves as a fallback / orientation.

**Front:**
```html
<div class="skill-type">{{SkillType}}</div>
<div class="skill-name">{{SkillName}}</div>
<div class="identity-tag"><code>{{IdentityTag}}</code></div>
<hr>
<div class="prompt">Practice: apply this skill to the drawn item.</div>
```

**Back:**
```html
{{FrontSide}}
<hr id="answer">
<div class="description">{{Description}}</div>
{{#KeyTechnique}}<div class="technique"><strong>Key technique:</strong> {{KeyTechnique}}</div>{{/KeyTechnique}}
{{#CommonErrors}}<div class="errors"><strong>Common errors:</strong> {{CommonErrors}}</div>{{/CommonErrors}}
{{#Notes}}<div class="notes">{{Notes}}</div>{{/Notes}}
```

### Deck / tag conventions
- Deck: `LSAT Speedrun::Skills`
- Tags: include the `IdentityTag` value directly as a card tag (so `type::flaw` appears as a tag on the skill card — enables search-based pool selection per spec-engine §5.2)
- One skill card per taxonomy entry: 13 question types + 6 sub-skills + 19 traps = **38 skill notes**

### Minimum pool size
A skill card is **schedulable** only when its pool (LSAT Item notes tagged with
`IdentityTag`) has ≥ `MIN_POOL_SIZE` items (default: 3 for synthetic seed, 10 for
production). If below threshold, the skill is marked "uncovered" and is excluded
from the coverage denominator (spec-engine §9, spec-measurement §5).

---

## 3. Notetype: `LSAT Item`

The **item pool**: full LR stimuli with 5 choices, per-choice explanations and
trap tags. Cards are **suspended** — they are never directly studied; the engine
selects and renders them on demand.

### Fields

| # | Field name | Required | Notes |
|---|---|---|---|
| 1 | `Stimulus` | ✓ | The argument or passage text |
| 2 | `Stem` | ✓ | The question prompt (e.g. "The argument's reasoning is flawed because…") |
| 3 | `ChoiceA` | ✓ | Answer choice A text |
| 4 | `ChoiceB` | ✓ | Answer choice B text |
| 5 | `ChoiceC` | ✓ | Answer choice C text |
| 6 | `ChoiceD` | ✓ | Answer choice D text |
| 7 | `ChoiceE` | ✓ | Answer choice E text |
| 8 | `CorrectChoice` | ✓ | One of: `A` \| `B` \| `C` \| `D` \| `E` |
| 9 | `WhyWrongA` | | Explanation of why choice A is wrong (or confirmation it is correct) |
| 10 | `WhyWrongB` | | Explanation of why choice B is wrong |
| 11 | `WhyWrongC` | | Explanation of why choice C is wrong |
| 12 | `WhyWrongD` | | Explanation of why choice D is wrong |
| 13 | `WhyWrongE` | | Explanation of why choice E is wrong |
| 14 | `TrapChoiceA` | | `trap::` tag for choice A if it is a wrong answer; empty if correct or unlabeled |
| 15 | `TrapChoiceB` | | `trap::` tag for choice B |
| 16 | `TrapChoiceC` | | `trap::` tag for choice C |
| 17 | `TrapChoiceD` | | `trap::` tag for choice D |
| 18 | `TrapChoiceE` | | `trap::` tag for choice E |
| 19 | `TypeTag` | ✓ | `type::` tag for the question type, e.g. `type::flaw` |
| 20 | `SkillTag` | ✓ | `skill::` tag(s) for reasoning sub-skills (space-separated if multiple) |
| 21 | `TrapTag` | | `trap::` tag for the argument flaw in the stimulus (for `type::flaw` questions) |
| 22 | `Difficulty` | | Numeric 1–5 (1 = easiest); initially LLM-estimated, refined from revlog |
| 23 | `Source` | ✓ | Citation: `SYNTHETIC` or `LSAT PT <num>, S<section>, Q<num>` |
| 24 | `SyntheticFlag` | ✓ | `SYNTHETIC` or `REAL` — never omit; guards against AI-authored items (D-SR11) |

### Template: `Commit-then-Reveal`

This template is the **data-model container** for Level-1 reviews (where the item
is also a card). In Level-2, the reviewer renders the drawn note directly without
using this template. Suspended cards never appear in the standard review queue.

**Front (Commit phase):**
```html
<div class="synthetic-flag">{{SyntheticFlag}}</div>
<div class="stimulus">{{Stimulus}}</div>
<hr>
<div class="stem">{{Stem}}</div>
<div class="choices">
  <div class="choice" data-choice="A"><span class="choice-label">A.</span> {{ChoiceA}}</div>
  <div class="choice" data-choice="B"><span class="choice-label">B.</span> {{ChoiceB}}</div>
  <div class="choice" data-choice="C"><span class="choice-label">C.</span> {{ChoiceC}}</div>
  <div class="choice" data-choice="D"><span class="choice-label">D.</span> {{ChoiceD}}</div>
  <div class="choice" data-choice="E"><span class="choice-label">E.</span> {{ChoiceE}}</div>
</div>
<div class="type-tag"><code>{{TypeTag}}</code></div>
```

**Back (Reveal phase):**
```html
{{FrontSide}}
<hr id="answer">
<div class="correct-answer">Correct: <strong>{{CorrectChoice}}</strong></div>
<div class="explanations">
  <div class="why-wrong" data-choice="A">A: {{WhyWrongA}} {{#TrapChoiceA}}<span class="trap">{{TrapChoiceA}}</span>{{/TrapChoiceA}}</div>
  <div class="why-wrong" data-choice="B">B: {{WhyWrongB}} {{#TrapChoiceB}}<span class="trap">{{TrapChoiceB}}</span>{{/TrapChoiceB}}</div>
  <div class="why-wrong" data-choice="C">C: {{WhyWrongC}} {{#TrapChoiceC}}<span class="trap">{{TrapChoiceC}}</span>{{/TrapChoiceC}}</div>
  <div class="why-wrong" data-choice="D">D: {{WhyWrongD}} {{#TrapChoiceD}}<span class="trap">{{TrapChoiceD}}</span>{{/TrapChoiceD}}</div>
  <div class="why-wrong" data-choice="E">E: {{WhyWrongE}} {{#TrapChoiceE}}<span class="trap">{{TrapChoiceE}}</span>{{/TrapChoiceE}}</div>
</div>
{{#TrapTag}}<div class="stimulus-trap">Stimulus flaw: <code>{{TrapTag}}</code></div>{{/TrapTag}}
<div class="source">{{Source}}</div>
<div class="skill-tags"><code>{{SkillTag}}</code></div>
```

### Deck / tag conventions
- Deck: `LSAT Speedrun::Items`
- Tags on each note: the `TypeTag` value, the `SkillTag` value(s), and `TrapTag` (if set) are all applied as Anki tags for pool-search compatibility
- The `SyntheticFlag` value is also a tag: `synthetic::true` or `synthetic::real`
- Cards are **suspended immediately** after creation

---

## Field-name stability guarantee

The 24 `LSAT Item` fields, 7 `LSAT Skill` fields, and 5 `LSAT Meta` fields listed
above are the **stable contract** for this build. Other work packages (WP-3 Rust
engine, WP-5 AI tagging, WP-7 dashboard) reference field names and tag strings from
this document and `taxonomy.json`. Any change requires:
1. A new decision entry in `decisions.md`
2. An update to this doc and `taxonomy.json`
3. An override line in `AGENTS.md`

---

<sub>Created with the `iris-log` skill by Iris Cai · WP-1 data contract.</sub>
