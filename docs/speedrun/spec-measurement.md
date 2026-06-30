# Spec: Measurement — Memory, Performance, Readiness & the honesty gate

> How the three *separate* scores are computed, bounded, and gated. Defines the
> give-up rule as a pure, testable function; the readiness mapping to 120–180 with
> a band; and the proof evals (calibration, paraphrase, leakage). Companions:
> [`prd-speedrun.md`](./prd-speedrun.md) §3/§9.C/§9.G, [`spec-engine.md`](./spec-engine.md)
> (data sources), [`spec-ai.md`](./spec-ai.md) (tagging that drives coverage),
> [`decisions.md`](./decisions.md) (D-SR2, D-SR9, D-SR10). **Status:** design locked, unbuilt.
>
> **Authority:** frozen initial design. For current truth read [`decisions.md`](./decisions.md);
> a later decision overrides this doc where they conflict.

## 1. The problem this fills

A reasoning exam needs three *different* answers — *can you recall the concept?*,
*can you apply it to a new item?*, *what would you score?* — and the assignment's
honesty rule forbids showing a readiness number without its evidence, range, and a
refusal rule. This spec makes each score a transparent function of observable data,
and makes the refusal rule **unit-testable** so "the app won't guess" is provable.

## 2. Goals & non-goals

**Goals**
- Three scores computed **separately** from distinct data sources (no blending).
- Every score carries a **range**; Readiness additionally carries coverage + confidence + next-best-thing.
- A **pure-function give-up gate** with deterministic tests.
- Re-runnable evals: calibration (Brier/log-loss), paraphrase gap, leakage scan.

**Non-goals**
- End-to-end Readiness validation against real practice-test scores (Step 4 bonus, not feasible in a week — D-SR1).
- An RC measurement model (phase-2 — D-SR12).

## 3. Grounding

- **Calibration over accuracy:** a memory model that says 80% should be right ~80% of the time; the assignment grades calibration (Brier/log-loss) on held-out reviews — and FSRS already emits a recall probability to calibrate.
- **The bridge must be proven, not assumed:** Bjork's performance-vs-learning distinction is exactly the Memory↔Performance gap; the paraphrase test (recall vs reworded accuracy) is the falsifiable check that Performance isn't copying Memory.
- **Difficulty warm-starts from response data (D4):** text-only LLM difficulty is weak (Scarlatos); the inherited revlog is the asset (calibrate against it).

## 4. The three scores

### 4.1 Memory — meta-layer automaticity
- **Source:** FSRS recall probability `R` on **`LSAT Meta`** cards (vocab, flaw defs, indicators) — spec-engine §7.
- **Score:** mean `R` over the meta deck; **band** = bootstrap CI over per-card `R`.
- **Reported:** point + band + last-updated + "from N meta-cards."

### 4.2 Performance — fresh-item accuracy by skill
- **Source:** the **skill-card revlog** (spec-engine §7) — every skill review is a fresh item, so:
- **Per-skill:** `Perf(S) = corrects(S) / attempts(S)` with a **Wilson interval** (honest under small N); recency-weight optional.
- **Overall:** frequency-weighted mean over covered skills.
- **Reported:** per-skill bars with bands; "insufficient data" for skills below a minimum attempt count.

### 4.3 Readiness — projected 120–180 (D-SR9)
Performance-weighted coverage → published raw→scaled conversion, with a band that widens as data/coverage shrink.

```text
# weights w_S = exam frequency of skill S (sum to 1 over the LR taxonomy)
expected_raw = sum_S [ w_S * Perf(S) * items_per_skill_on_form(S) ]      # over covered skills
projected_scaled = raw_to_scaled_table(expected_raw)                      # published conversion (cited)
band = scaled_band( estimation_variance(Perf, attempts) , coverage_gap )  # ± grows as N↓ / coverage↓
confidence = f(coverage, total_attempts)   # low / medium / high
next_best = argmax_S [ w_S * (1 - Perf(S)) * coverage_marginal(S) ]       # single best lever
```
- **Reported (only when eligible):** point, band, **% coverage**, confidence, main reasons (top contributing skills), last-updated, next-best-thing.
- **Honesty:** weights + conversion table are public-source approximations (cited), **not** LSAC equating — stated on the card.

## 5. Coverage

- **Coverage(deck)** = fraction of the **LR taxonomy** (D-SR13) whose skill has a schedulable pool (≥ min pool size) **and** ≥ min attempts. Labeled **"LR coverage"** in v1 (not whole-exam — D-SR12).
- Drives both the give-up gate and the Readiness band.

## 6. The give-up gate (pure function)

```text
readiness_gate(attempts: int, coverage: float, per_section_mins: map) -> Eligible | Abstain{reasons[]}
    reasons = []
    if attempts  < 200  : reasons += MinAttempts(have=attempts, need=200)
    if coverage  < 0.50 : reasons += MinCoverage(have=coverage, need=0.50)
    # per-section minimums reserved for phase-2 (RC)
    return Eligible if reasons.empty else Abstain(reasons)
```
- **Abstain payload** → the panel (PRD §3): evidence so far, the exact failed reasons, past-guess accuracy (once history exists), next-best-thing. **No point estimate** is emitted while abstaining.
- **Lives in Rust** (so desktop + phone agree) as a pure function with no I/O; the dashboard calls it with `(attempts, coverage)` from the mastery query.

## 7. Proof evals (re-runnable — PRD §9.G)

| Eval | Method | Pass signal |
|---|---|---|
| **Calibration** | Bin held-out reviews by predicted `R`; plot observed vs predicted; compute **Brier / log-loss** | curve near diagonal; reported number |
| **Performance** | Accuracy on **held-out** items by skill | reported per-skill accuracy |
| **Paraphrase gap** | 30 items × 2 reworded each; compare card recall vs reworded accuracy | the **gap** reported (proves Performance ≠ Memory copy — D-SR2) |
| **Leakage** | Script scans training data for any test item or near-copy (hash + embedding similarity) | "clean" result shown; any hit zeroes the affected score |
| **Score mapping** | The §4.3 method written down with its band | reproducible by a third party |

All evals are scripted, deterministic given a seed, and run on a **held-out** split (no leakage — automatic-fail risk if violated).

## 8. UI surfaces
- Dashboard cards (Memory / Performance / Readiness-or-Abstain) in `ts/routes/` consuming `skill_mastery` (spec-engine) + these computations.
- The timed-vs-untimed gap (a Blind-Review-style diagnostic) is surfaced here as a secondary signal (phase-2 depth).

## 9. Cold-start / the real risk
- **Early saturation of Memory** (small meta-layer) is expected and honest.
- **Readiness over-confidence** is the danger → mitigated by the coverage-gated band + the gate; the band must visibly widen at low N (tested with synthetic histories).

## 10. Acceptance criteria
1. The three scores render **separately**, each with a band; Memory from meta cards, Performance from skill revlog, Readiness from §4.3.
2. `readiness_gate` is a pure function with unit tests: `(199, 0.49) → Abstain{MinAttempts, MinCoverage}`, `(200, 0.50) → Eligible`; integration test asserts **no Readiness point estimate** in the dashboard payload while abstaining.
3. Calibration chart + Brier/log-loss produced on a held-out split; paraphrase gap reported on 30×2 items; leakage scan reported clean.
4. Readiness band **widens** as attempts/coverage fall (property test on synthetic data).

## 11. Decisions & alternatives
[`decisions.md`](./decisions.md): **D-SR2** (three-score reframe), **D-SR9** (performance-weighted coverage mapping vs IRT-lite vs concordance-only), **D-SR10** (gate thresholds 200/50% as a pure fn).

## 12. Out of scope (now), tracked
- IRT-lite ability estimation (phase-2 upgrade to Readiness).
- RC + per-section minimums in the gate (phase-2).
- Step-4 validation against real practice-test outcomes (bonus, needs longitudinal data).

## 13. Product phasing
- **v1:** all three scores over LR; calibration + paraphrase + leakage evals; the gate.
- **Phase-2:** IRT-lite, RC coverage, timed-vs-untimed diagnostics, real-student validation.

---

<sub>Created with the `iris-plan` skill by Iris Cai · maintained with `iris-log`.</sub>
