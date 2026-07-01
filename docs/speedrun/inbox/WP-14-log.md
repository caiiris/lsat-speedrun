# Speedrun WP-14 — Inbox Log

> **Provisional local IDs** (L1, L2, …) — the orchestrator merges these into
> `decisions.md` and `backlog.md` after review. Do NOT promote IDs or edit the
> canonical logs directly from this file.
>
> Work package: **WP-14 — Performance + Readiness + 3-score dashboard**  
> Date: 2026-06-30  
> Agent: Sonnet 4.6 via Cursor

---

## Decisions / alternatives / spec ambiguities

### L1 — ease → correct mapping: ease ≥ 2 = correct, ease == 1 = wrong
- **Type:** decision (local)
- **Status:** resolved
- **Context:** The spec says "per-skill accuracy = fraction-correct over the skill card revlog" but doesn't define the mapping from revlog `ease` (button_chosen) to correct/wrong. Anki's revlog stores `ease` as 1=Again, 2=Hard, 3=Good, 4=Easy.
- **Chose:** `ease ≥ 2 → correct`; `ease == 1 (Again) → wrong`. Rationale:
  1. This mirrors Anki's own "true retention" stat (see `rslib/src/stats/graphs/retention.rs`) and the WP-6 reviewer's commit-then-reveal convention: "Again" = the user didn't get it right; any other press = correct.
  2. Hard (2) counts as correct because the user demonstrated retrieval — even if slow. This is the standard flashcard convention (not penalizing effort-level, only failure).
  3. Only reviews with `ease BETWEEN 1 AND 4` are counted; manual-reschedule rows (ease=0) are excluded.
- **Risk:** Hard=correct may slightly inflate Performance for skills where users routinely press Hard. Acceptable for v1; could add a recency-weighted or hard-penalized variant in phase-2.
- **Ref:** `rslib/src/storage/card/speedrun.rs::skill_revlog_in_decks`, spec-measurement §4.2

### L2 — Combined RPC message shape: `SpeedrunDashboard` returning all three scores
- **Type:** decision (local)
- **Status:** resolved
- **Context:** The task brief says to design the combined RPC message shape and log it. Options: (a) three separate RPCs (Memory, Performance, Readiness); (b) one combined `SpeedrunDashboard` RPC.
- **Chose:** Option (b) — one combined RPC `SpeedrunDashboard(SpeedrunDashboardRequest{deck_id}) → SpeedrunDashboardResponse`. Rationale:
  1. One round-trip: the dashboard page needs all three scores simultaneously; three separate fetches add latency and complexity.
  2. The scores are computed from the same deck hierarchy; batching them in one impl shares the `deck_with_children` call.
  3. The memory_score_impl and performance_and_readiness_impl calls are already independent (they filter by different notetypes); the combined impl simply chains them.
- **Message fields:**
  - `optional SpeedrunMemoryScore memory` — absent when no Meta cards in deck.
  - `repeated SpeedrunSkillPerf skill_perf` — one per skill with `attempts, correct, wilson_low, wilson_high`.
  - `float overall_perf` — frequency-weighted mean over covered skills.
  - `float lr_coverage` — fraction of 13-type taxonomy with ≥5 attempts.
  - `uint32 total_attempts` — total skill-card reviews.
  - `bool eligible` — false when abstaining; dashboard MUST NOT show Readiness number when false (D-SR10).
  - `SpeedrunReadinessAbstain abstain` — set when eligible=false (reasons, coverage, next_best).
  - `SpeedrunReadinessEligible readiness` — set when eligible=true (point, band_low, band_high, confidence, top_skills, next_best).
- **Risk:** `eligible` boolean is the critical honesty field — callers must check it before displaying any Readiness number.
- **Ref:** spec-measurement §4/§6/§8, D-SR10

### L3 — Wilson score interval: 95% CI, z=1.96
- **Type:** decision (local)
- **Status:** resolved
- **Context:** spec-measurement §4.2 specifies a Wilson interval but does not fix the confidence level.
- **Chose:** 95% CI (z=1.96), matching the Memory bootstrap CI in WP-7 for consistency. The Wilson interval is the standard choice for small-N proportion CIs (avoids coverage failures of the Wald interval). Formula: center = (p_hat + z²/2n) / (1 + z²/n); margin = (z/(1+z²/n)) * sqrt(p_hat*(1-p_hat)/n + z²/(4n²)).
- **Risk:** At n=5 (the minimum), the Wilson interval is wide (~±35pp) — which is honest and intentional.
- **Ref:** spec-measurement §4.2, AC 1

### L4 — Band formula: base_half_raw (Wilson widths) + coverage_gap_raw
- **Type:** decision (local)
- **Status:** resolved
- **Context:** spec-measurement §4.3 says "band grows as N↓ / coverage↓" but does not specify the formula. The task requires AC 4 (band widens as attempts/coverage fall).
- **Chose:** Two additive components:
  1. `base_half_raw = Σ_S w_S * N_lr * (wilson_high_S - wilson_low_S) / 2` — proportional to the CI width of covered skills. Shrinks as N↑ (more data → narrower Wilson intervals).
  2. `coverage_gap_raw = (1 - coverage) * N_lr * 0.5` — grows as coverage↓ (missing skills inflate uncertainty). Coefficient 0.5 means uncovered skills add ±25% of N_lr to the LR-raw band.
  3. Both are scaled by `LR_TO_TOTAL_SCALE = 76/50 ≈ 1.52` to project to the full-form raw→scaled table.
  4. `band_low = raw_to_scaled(total_raw_estimate - total_half_raw)`, `band_high = raw_to_scaled(total_raw_estimate + total_half_raw)`.
- **Monotonicity:** As N increases per skill, Wilson widths shrink → `base_half_raw` shrinks → band narrows. As coverage increases, `coverage_gap_raw` shrinks → band narrows. The two tests `readiness_band_widens_as_attempts_fall` and `readiness_band_widens_as_coverage_falls` verify this.
- **Risk:** The coverage_gap coefficient (0.5) is a judgment call. A coefficient of 1.0 would widen the band to the full N_lr at 0% coverage (very conservative); 0.5 is intermediate. Tunable.
- **Ref:** spec-measurement §4.3, §9, AC 4

### L5 — Confidence tiers: high (≥85% cov, ≥500 att), medium (≥65% cov, ≥300 att), else low
- **Type:** decision (local)
- **Status:** resolved
- **Context:** spec-measurement §4.3 says confidence = f(coverage, total_attempts) returning low/medium/high. No thresholds specified.
- **Chose:** Three tiers based on coverage × attempts jointly:
  - `high`: coverage ≥ 85% AND attempts ≥ 500
  - `medium`: coverage ≥ 65% AND attempts ≥ 300
  - `low`: otherwise (including immediately after gate: coverage ≥ 50%, attempts ≥ 200)
- **Rationale:** At gate thresholds (200/50%), users are eligible but have limited data → "low". They need substantially more data to reach "medium" or "high". The tiers are tunable constants in `performance.rs`.
- **Risk:** These are informed judgment calls, not calibrated from real data. Should revisit with WP-17 (ablation data) or real user studies.
- **Ref:** spec-measurement §4.3

### L6 — LR-only projection: expected_lr_raw * (76/50)
- **Type:** decision (confirming D-SR19 / weights.json `readiness_formula_note`)
- **Status:** resolved
- **Context:** v1 has no RC data. Need to project LR-only expected_raw to the full-form raw→scaled table (which covers 0–76 total items).
- **Chose:** `total_raw_estimate = expected_lr_raw * (76/50)`, i.e. assume LR performance scales uniformly to the rest of the exam (Option B from `weights.json`). Labeled "LR-only estimate" in the UI badge and proto field names.
- **Rationale:** This is the honest conservative default. The wider band covers the RC uncertainty (via `coverage_gap_raw` applied to full `N_lr`, not reduced). D-SR19 explicitly chose Option B.
- **Ref:** `weights.json` `readiness_formula_note`, D-SR19

### L7 — Dashboard UI scope: functional, faithful, minimal
- **Type:** decision (local, scope)
- **Status:** resolved
- **Context:** The task says "land at least a functional, correct route; if time is tight, keep the UI minimal but faithful to the honesty rules."
- **Chose:** Functional, correct route (`ts/routes/speedrun-dashboard/`) with three Svelte cards (Memory, Performance, Readiness-or-Abstain). Per-skill bars with Wilson CI markers. Abstain panel with no Readiness number. "LR-only estimate" badge always visible on Readiness card.
- **Deferred:** Interactive deck-picker (hardcoded deck_id in route param), dark-mode polish, animations, i18n strings (dashboard uses English literals), calibration/paraphrase chart integration. The honesty invariants are all present; the polish is deferred.
- **Ref:** spec-measurement §8, PRD §9.C

### L8 — Coverage counts only `type::*` tags (not `skill::` or `trap::`)
- **Type:** decision (confirming D-SR12/D-SR19)
- **Status:** resolved
- **Context:** The LR taxonomy has 13 `type::*` question types that correspond to exam-frequency weights. The skill deck also contains `skill::*` (axis-2 sub-skills) and `trap::*` (trap catalog) notes, which don't have weights in `weights.json`.
- **Chose:** Coverage = fraction of the 13 `type::*` skills with ≥5 attempts. `skill::*` and `trap::*` reviews contribute to Performance (per-skill bars are shown for all) but do NOT count toward LR coverage or the gate.
- **Risk:** The gate could in principle count `skill::` coverage, but the spec (§5) and D-SR12 focus on the "LR taxonomy" which maps to `type::*`. Consistent with `weights.json` key set.
- **Ref:** spec-measurement §5, D-SR12, `weights.json` `lr_frequency_weights`

### L9 — D-SR29 exposure (Memory bootstrap band) — deferred as planned
- **Type:** decision (confirming B031 deferral from D-SR29)
- **Status:** resolved
- **Context:** D-SR29 (referenced as B031 in the task brief) noted that WP-7's Memory bootstrap band is built but not exposed to Python/dashboard. This is WP-14's responsibility.
- **Resolved:** The `SpeedrunDashboardResponse.memory` field carries `mean_recall`, `ci_lower`, `ci_upper`, `card_count` — full exposure of the bootstrap band to the dashboard. B031 is resolved by this WP.
- **Ref:** D-SR29, `docs/speedrun/inbox/WP-7-log.md §L1`, `rslib/src/stats/measurement.rs`

---

## Bugs found

### L10 — Pre-existing: `skills.list()` in the `skill_mastery_impl` returns SkillMastery (not skill revlog)
- **Type:** design gap (not a bug)
- **Status:** noted, not a bug
- **Context:** `skill_mastery` (WP-5) returns FSRS recall over skill *cards* (current memory state), not accuracy over the revlog. Performance requires the revlog (correct/attempt counts per review). These are correctly separate queries.
- **Resolution:** WP-14 adds `skill_revlog_in_decks` as a new storage query, keeping the two computations orthogonal. No collision with WP-5.
- **Ref:** `rslib/src/storage/card/speedrun.rs`

### L11 — `SkillRevlogRow.button_chosen` field name vs SQL column `ease`
- **Type:** naming clarification (not a bug)
- **Status:** resolved
- **Context:** The SQL revlog table uses `ease` as the column name (Anki legacy); the `RevlogEntry` Rust struct uses `button_chosen` as the field name. The `SkillRevlogRow` struct introduced by WP-14 uses `button_chosen` as the field name for clarity, selecting from `r.ease` in SQL.
- **Resolution:** The SQL query is `SELECT n.tags, r.ease` mapping to `SkillRevlogRow.button_chosen`. This is explicit and correct. The naming is logged here to avoid future confusion.
- **Ref:** `rslib/src/storage/card/speedrun.rs`, `rslib/src/storage/revlog/add.sql`

### L12 — Pre-existing: B023/B026 (dprint + ruff/mypy on tools/) are not WP-14 failures
- **Type:** pre-existing lint/fmt issues
- **Status:** not WP-14's responsibility
- **Context:** The task brief notes B023 (dprint doc formatting) and B026 (ruff/mypy on `tools/speedrun/`) as pre-existing failures that should not be attributed to WP-14. Confirmed: WP-14 touches `rslib/`, `proto/`, `pylib/anki/collection.py`, and `ts/routes/speedrun-dashboard/` only. No `tools/speedrun/` changes.
- **Ref:** `docs/speedrun/backlog.md` B023/B026

---

## `weights.json` fields relied upon
- `lr_frequency_weights.weights` — the 13 `type::*` → weight mappings used in Performance (overall weighted mean) and Readiness (expected_lr_raw formula).
- `lr_frequency_weights._form_lr_items` (= 50) — `N_lr` used in D-SR18 formula.
- `raw_to_scaled_conversion.table` — the 77-entry (raw=0..=76, scaled=120..=180) lookup table, hardcoded in `performance.rs::RAW_TO_SCALED_TABLE`.
- `raw_to_scaled_conversion._total_form_items` (= 76) — `N_TOTAL` used in the LR→full-form projection.
- `coverage_thresholds.min_attempts_per_skill_for_performance` (= 5) — `MIN_ATTEMPTS_PER_SKILL` constant.
- `readiness_formula_note.recommended_v1` (= "Option B") — LR-only estimate with wider band.
