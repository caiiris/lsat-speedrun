# Speedrun — Proof-eval harnesses

Standalone, seeded, held-out evaluation tools for the three proof evals
defined in `spec-measurement §7` and `PRD §9.G`.  They run today against
synthetic fixtures and wire to real engine outputs later (wiring points are
called out per eval below).

All evals are:
- **Deterministic** given a seed (seeded `random.Random`, no global state).
- **Purely additive** — no Anki source files are touched.
- **Self-contained** — only stdlib + optional matplotlib for one chart.

---

## Quick start

```bash
# From the repo root
cd /path/to/anki

# Run all tests
python -m pytest tools/speedrun/eval/tests/ -v

# Run a synthetic fixture directly
python -m tools.speedrun.eval.calibration --fixture
python -m tools.speedrun.eval.paraphrase --fixture
python -m tools.speedrun.eval.leakage --fixture
```

---

## `calibration.py` — Memory model calibration

**Spec ref:** `spec-measurement §7 (Calibration row)`, `PRD AC-3`

### What it measures
Bins held-out reviews by the FSRS predicted recall probability `R` and
checks whether the observed fraction-correct in each bin matches.  Reports
**Brier score** and **log-loss** (both lower = better).

### Input schema

**CSV** (two columns, header optional):
```
predicted_r,outcome
0.82,1
0.34,0
```

**JSON** (list of objects):
```json
[
  {"predicted_r": 0.82, "outcome": 1},
  {"predicted_r": 0.34, "outcome": 0}
]
```

| Field | Type | Meaning |
|---|---|---|
| `predicted_r` | float ∈ [0, 1] | FSRS `R` (recall probability) from `revlog.ease_factor` or the mastery-query RPC |
| `outcome` | int ∈ {0, 1} | 1 = answered correctly, 0 = wrong/again |

### Wiring to real engine
- **Source of `predicted_r`:** the mastery-query RPC (spec-engine §7) returns
  per-skill and per-card recall probability.  Alternatively read directly from
  `revlog` using the FSRS state snapshot stored in `Card.custom_data`.
- **Source of `outcome`:** `revlog.ease` ≥ 2 → 1, else 0  (Anki convention:
  rating 1 = Again, 2 = Hard, 3 = Good, 4 = Easy).
- **Held-out split:** create a time-based split (e.g. last 20% of each card's
  reviews) before running; the script enforces no split itself.

### CLI
```bash
python -m tools.speedrun.eval.calibration --input reviews.csv [--bins 10] [--plot diagram.png]
python -m tools.speedrun.eval.calibration --fixture
```

---

## `paraphrase.py` — Recall-vs-reworded accuracy gap

**Spec ref:** `spec-measurement §7 (Paraphrase gap row)`, `D-SR2`, `PRD AC-25`

### What it measures
For each item, computes `gap = base_outcome − mean(variant_outcomes)`.
- Positive gap → student recalled original wording but failed paraphrases
  → rote memory, not transferable skill.
- Gap ≈ 0 → either genuine transfer or consistent failure.

The overall mean gap across all items is the headline number.

### Input schema

**JSON** (preferred):
```json
[
  {
    "item_id": "q001",
    "base_outcome": 1,
    "variant_outcomes": [1, 0]
  }
]
```

**CSV** (item_id, base_outcome, variant_outcome_1, variant_outcome_2, …):
```
q001,1,1,0
q002,0,0,0
```

| Field | Type | Meaning |
|---|---|---|
| `item_id` | str | Unique item identifier (maps to note ID or pool item ID) |
| `base_outcome` | int ∈ {0, 1} | Outcome on the original card text |
| `variant_outcomes` | list[int ∈ {0,1}] | Outcomes on ≥ 1 reworded variants (spec requires ≥ 2) |

### Wiring to real engine
- **Source of `base_outcome`:** skill-card revlog for the original item text
  (spec-engine §7).  The skill card's `note_id` links to the item pool.
- **Source of `variant_outcomes`:** a separate set of tagged "variant" items
  in the pool, linked to the same skill card by a shared `skill_id` custom
  field in `Card.custom_data`.
- The spec requires 30 items × 2 variants; assemble the JSON from the skill
  revlog by querying items where `custom_data.variant_of` is set.

### CLI
```bash
python -m tools.speedrun.eval.paraphrase --input items.json
python -m tools.speedrun.eval.paraphrase --fixture
```

---

## `leakage.py` — Training / test contamination scan

**Spec ref:** `spec-measurement §7 (Leakage row)`, `PRD AC-26`

### What it measures
Scans a test set against a training / item-pool set for:
1. **Exact duplicates** — SHA-256 hash match (after stripping whitespace).
2. **Near-duplicates** — cosine similarity on character 3-gram TF vectors
   (deterministic fallback, no model required).  An optional
   `EmbeddingProvider` protocol can inject a model-backed encoder.

Any hit → `score_zeroed = True` (spec §7 requirement).

### Input schema

**JSON** (same format for train and test):
```json
[
  {"id": "t001", "text": "Which one of the following..."},
  {"id": "t002", "text": "The argument assumes without justification..."}
]
```

| Field | Type | Meaning |
|---|---|---|
| `id` | str | Unique identifier (note ID, pool item ID, or eval item label) |
| `text` | str | The full question stem (or stem + answer choices if testing full item) |

### Threshold
Default `threshold=0.85`.  Lower values catch more paraphrases at the cost of
false positives.  Tune on a small human-labeled set before a real eval run.

### Injecting an embedding provider
```python
from tools.speedrun.eval.leakage import LeakageScanner, EmbeddingProvider

class MyEncoder:
    def encode(self, texts: list[str]) -> list[list[float]]:
        ...  # call your model

scanner = LeakageScanner(threshold=0.85, embedding_provider=MyEncoder())
report = scanner.scan(train_items, test_items)
```

### Wiring to real engine
- **Training set:** all items in the skill-card pool (exported from the
  collection's notes table where `tags` contains the Speedrun skill tag).
- **Test set:** the held-out eval split (items withheld from the scheduler
  and used only for the held-out Performance eval).
- Run before scoring.  If `report.score_zeroed` is True, remove affected
  test items and log the contamination count.

### CLI
```bash
python -m tools.speedrun.eval.leakage --train train.json --test test.json [--threshold 0.85]
python -m tools.speedrun.eval.leakage --fixture
# exits with code 1 if any leakage is found
```

---

## Running the tests

```bash
# From the repo root:
python -m pytest tools/speedrun/eval/tests/ -v

# Or just the calibration tests:
python -m pytest tools/speedrun/eval/tests/test_calibration.py -v
```

All tests are deterministic (seeded) and rely only on stdlib.  They do not
touch the Anki database, build system, or network.

---

*Part of the Speedrun proof-eval harness (WP-16). Maintained with the
`iris-log` skill by Iris Cai.*
