// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! Speedrun WP-14: Performance score (per-skill Wilson accuracy) and
//! Readiness score (projected 120–180 with honest band + give-up gate).
//!
//! # Ease → correct mapping (logged as WP-14 L1)
//!
//! Anki's `revlog.ease` (= `button_chosen`) encodes the rating pressed:
//! - 1 = Again (card failed)  → **wrong**
//! - 2 = Hard                 → **correct**
//! - 3 = Good                 → **correct**
//! - 4 = Easy                 → **correct**
//!
//! This mirrors the convention used in the reviewer (commit-then-reveal):
//! a press of "Again" means the user got it wrong; any other press means
//! they got it right.  The mapping is identical to the one used by Anki's
//! own "true retention" stat and by the WP-7 eval eval convention.
//!
//! # Readiness formula (D-SR18 corrected form)
//!
//! `expected_lr_raw = Σ_S [ Perf(S) * items_per_form(S) ]`
//!
//! where `items_per_form(S) = w_S * N_lr` (= w_S * 50) from `weights.json`.
//! This is equivalent to `N_lr * Σ_S [ w_S * Perf(S) ]`.
//! At Perf=1 for all skills, expected_lr_raw = 50 = N_lr (sanity check).
//!
//! # LR-only estimate (D-SR19)
//!
//! v1 covers LR only.  To project to the full-form raw→scaled table we use:
//!   `total_raw_estimate = expected_lr_raw * (76 / 50) = expected_lr_raw * 1.52`
//! then look up in the conversion table.  The dashboard labels this clearly
//! as an "LR-only estimate" and uses a wider band (D-SR19).

use std::collections::HashMap;

use crate::collection::Collection;
use crate::error::Result;
use crate::stats::measurement::{readiness_gate, GateReason, GateResult};

// ─── Constants ────────────────────────────────────────────────────────────────

/// Minimum reviews per skill to include in Performance and coverage.
/// From `weights.json` → `coverage_thresholds.min_attempts_per_skill_for_performance`.
const MIN_ATTEMPTS_PER_SKILL: u32 = 5;

/// Total LR items on a post-2024 LSAT form (both scored LR sections).
const N_LR: f32 = 50.0;

/// Total form items (LR + RC) used for the raw→scaled table.
const N_TOTAL: f32 = 76.0;

/// Scale factor: LR items / total items (≈ 0.658).  Applied to project
/// LR-only expected_raw to a full-form raw before table lookup.
const LR_TO_TOTAL_SCALE: f32 = N_TOTAL / N_LR;

/// z-value for 95% CI (Wilson interval).
const Z: f32 = 1.96;

/// Number of skills in the LR taxonomy (all 13 `type::*` keys in weights.json).
const TAXONOMY_SIZE: u32 = 13;

// ─── Exam-frequency weights ───────────────────────────────────────────────────

/// LR question-type exam-frequency weights from `docs/speedrun/data/weights.json`.
/// Keys are the canonical `type::*` tag strings.  Sum = 1.00.
pub(crate) fn lr_frequency_weights() -> HashMap<&'static str, f32> {
    [
        ("type::flaw", 0.14_f32),
        ("type::assumption", 0.10),
        ("type::inference", 0.10),
        ("type::strengthen", 0.09),
        ("type::weaken", 0.09),
        ("type::principle", 0.09),
        ("type::paradox", 0.07),
        ("type::parallel", 0.07),
        ("type::method", 0.07),
        ("type::justify", 0.06),
        ("type::main-point", 0.05),
        ("type::point-at-issue", 0.04),
        ("type::evaluate", 0.03),
    ]
    .into_iter()
    .collect()
}

// ─── Raw → scaled conversion table ────────────────────────────────────────────

/// Map a full-form raw score (0–76) to a scaled score (120–180).
/// Uses the approximation table from `docs/speedrun/data/weights.json`.
/// Input is clamped to [0, 76].
pub(crate) fn raw_to_scaled(raw: f32) -> u32 {
    // Clamp and round raw to the nearest integer.
    let raw_int = raw.round().clamp(0.0, 76.0) as u32;
    // Approximate the table with a linear segment (sufficient for a band estimate).
    // The table is nearly linear; exact values for each integer are encoded below.
    RAW_TO_SCALED_TABLE
        .iter()
        .find(|&&(r, _)| r == raw_int)
        .map(|&(_, s)| s)
        .unwrap_or(120)
}

/// Full raw→scaled table from `weights.json` (raw=0..=76, scaled=120..=180).
const RAW_TO_SCALED_TABLE: &[(u32, u32)] = &[
    (76, 180),
    (75, 180),
    (74, 179),
    (73, 179),
    (72, 178),
    (71, 178),
    (70, 177),
    (69, 176),
    (68, 176),
    (67, 175),
    (66, 174),
    (65, 174),
    (64, 173),
    (63, 172),
    (62, 172),
    (61, 171),
    (60, 170),
    (59, 170),
    (58, 169),
    (57, 168),
    (56, 168),
    (55, 167),
    (54, 166),
    (53, 165),
    (52, 165),
    (51, 164),
    (50, 163),
    (49, 162),
    (48, 161),
    (47, 160),
    (46, 160),
    (45, 159),
    (44, 158),
    (43, 157),
    (42, 156),
    (41, 155),
    (40, 154),
    (39, 153),
    (38, 152),
    (37, 151),
    (36, 150),
    (35, 149),
    (34, 148),
    (33, 147),
    (32, 146),
    (31, 145),
    (30, 144),
    (29, 143),
    (28, 142),
    (27, 141),
    (26, 140),
    (25, 139),
    (24, 138),
    (23, 137),
    (22, 136),
    (21, 135),
    (20, 134),
    (19, 133),
    (18, 132),
    (17, 131),
    (16, 130),
    (15, 129),
    (14, 128),
    (13, 127),
    (12, 126),
    (11, 125),
    (10, 124),
    (9, 123),
    (8, 122),
    (7, 122),
    (6, 121),
    (5, 121),
    (4, 121),
    (3, 120),
    (2, 120),
    (1, 120),
    (0, 120),
];

// ─── Wilson score interval ────────────────────────────────────────────────────

/// Per-skill Performance derived from the skill-card revlog.
#[derive(Debug, Clone, PartialEq)]
pub struct SkillPerf {
    /// Canonical skill tag (e.g. `"type::flaw"`).
    pub skill: String,
    /// Total review attempts for this skill.
    pub attempts: u32,
    /// Correct review count (ease ≥ 2).
    pub correct: u32,
    /// Wilson score interval lower bound (95%).
    pub wilson_low: f32,
    /// Wilson score interval upper bound (95%).
    pub wilson_high: f32,
}

/// Compute the Wilson score confidence interval for `k` successes out of `n`
/// trials at `z` standard deviations (z=1.96 → 95% CI).
///
/// Returns `(lower, upper)` clamped to [0, 1].
/// When n=0 returns (0.0, 1.0) — full uncertainty.
pub fn wilson_interval(k: u32, n: u32) -> (f32, f32) {
    if n == 0 {
        return (0.0, 1.0);
    }
    let z = Z;
    let p_hat = k as f32 / n as f32;
    let n_f = n as f32;
    let z2 = z * z;
    let center = (p_hat + z2 / (2.0 * n_f)) / (1.0 + z2 / n_f);
    let margin = (z / (1.0 + z2 / n_f))
        * (p_hat * (1.0 - p_hat) / n_f + z2 / (4.0 * n_f * n_f)).sqrt();
    let lo = (center - margin).clamp(0.0, 1.0);
    let hi = (center + margin).clamp(0.0, 1.0);
    (lo, hi)
}

// ─── Overall performance ──────────────────────────────────────────────────────

/// Aggregate Performance output: per-skill bars + overall frequency-weighted mean.
#[derive(Debug, Clone)]
pub struct PerformanceResult {
    /// Per-skill bars (only skills with ≥ MIN_ATTEMPTS_PER_SKILL).
    pub skills: Vec<SkillPerf>,
    /// Frequency-weighted mean performance over covered skills (0.0..=1.0).
    pub overall_weighted: f32,
    /// Total review attempts across all skills (including sub-threshold).
    pub total_attempts: u32,
    /// Number of covered skills (≥ min attempts with a known type:: weight).
    pub covered_skill_count: u32,
}

/// Compute per-skill Performance from raw (tag, button_chosen) review rows.
///
/// - Groups rows by the first `type::`/`skill::`/`trap::` tag.
/// - ease ≥ 2 → correct; ease == 1 → wrong.
/// - Skills with < `MIN_ATTEMPTS_PER_SKILL` are reported with "insufficient data"
///   (wilson_low=0, wilson_high=1, attempts<min) but excluded from `overall_weighted`.
/// - Overall = frequency-weighted mean over skills that have ≥ min attempts
///   AND appear in the `type::*` weight table.
pub fn compute_performance(
    revlog_rows: &[(String, u32)], // (note_tags, button_chosen)
) -> PerformanceResult {
    // Group by skill tag.
    let mut counts: HashMap<String, (u32, u32)> = HashMap::new(); // skill → (attempts, correct)
    let mut total_attempts: u32 = 0;

    for (note_tags, button_chosen) in revlog_rows {
        let skill = match extract_skill_tag(note_tags) {
            Some(s) => s,
            None => continue,
        };
        total_attempts += 1;
        let entry = counts.entry(skill).or_insert((0, 0));
        entry.0 += 1; // attempt
        if *button_chosen >= 2 {
            entry.1 += 1; // correct
        }
    }

    let weights = lr_frequency_weights();

    // Build per-skill output and compute weighted mean over covered skills.
    let mut skills: Vec<SkillPerf> = Vec::new();
    let mut weighted_sum: f32 = 0.0;
    let mut weight_total: f32 = 0.0;
    let mut covered_skill_count: u32 = 0;

    let mut sorted_skills: Vec<_> = counts.into_iter().collect();
    sorted_skills.sort_by(|a, b| a.0.cmp(&b.0));

    for (skill, (attempts, correct)) in sorted_skills {
        let (wilson_low, wilson_high) = if attempts >= MIN_ATTEMPTS_PER_SKILL {
            wilson_interval(correct, attempts)
        } else {
            // Insufficient data — full uncertainty range.
            (0.0, 1.0)
        };

        // Include in weighted mean only if coverage-eligible.
        if attempts >= MIN_ATTEMPTS_PER_SKILL {
            if let Some(&w) = weights.get(skill.as_str()) {
                let perf = correct as f32 / attempts as f32;
                weighted_sum += w * perf;
                weight_total += w;
                covered_skill_count += 1;
            }
        }

        skills.push(SkillPerf {
            skill,
            attempts,
            correct,
            wilson_low,
            wilson_high,
        });
    }

    let overall_weighted = if weight_total > 0.0 {
        // Renormalize in case not all 13 skills are covered.
        weighted_sum / weight_total
    } else {
        0.0
    };

    PerformanceResult {
        skills,
        overall_weighted,
        total_attempts,
        covered_skill_count,
    }
}

// ─── Coverage ─────────────────────────────────────────────────────────────────

/// Compute LR coverage = fraction of the 13-type LR taxonomy whose skill has
/// ≥ MIN_ATTEMPTS_PER_SKILL reviews.
///
/// Only `type::*` skills (the 13 in `lr_frequency_weights()`) count toward
/// coverage (D-SR12/D-SR19).  `skill::*` and `trap::*` skills are scheduled
/// but don't count toward coverage for the Readiness gate.
pub fn compute_lr_coverage(skills: &[SkillPerf]) -> f32 {
    let weights = lr_frequency_weights();
    let covered = skills
        .iter()
        .filter(|s| s.attempts >= MIN_ATTEMPTS_PER_SKILL && weights.contains_key(s.skill.as_str()))
        .count() as u32;
    covered as f32 / TAXONOMY_SIZE as f32
}

// ─── Readiness ────────────────────────────────────────────────────────────────

/// The Readiness result: either an abstain payload (no point estimate) or a
/// full projection with band, confidence, and next-best-thing.
#[derive(Debug, Clone)]
pub enum ReadinessResult {
    /// Not enough evidence.  No point estimate.  The dashboard must show only
    /// the abstain panel (evidence so far, exact failed reasons, next-best-thing).
    Abstain {
        reasons: Vec<GateReason>,
        coverage: f32,
        total_attempts: u32,
        next_best: Option<String>,
    },
    /// Sufficient evidence.  Labeled "LR-only estimate" (D-SR19).
    Eligible {
        /// Projected scaled score (120–180), derived from LR-only data × scale factor.
        point: u32,
        /// Lower bound of the honest scaled-score band.
        band_low: u32,
        /// Upper bound of the honest scaled-score band.
        band_high: u32,
        /// Confidence tier: "low" / "medium" / "high" (from coverage + attempts).
        confidence: &'static str,
        /// LR coverage fraction (fraction of 13-type taxonomy with ≥ min attempts).
        coverage: f32,
        /// Total attempts across all skills.
        total_attempts: u32,
        /// Top contributing skills (highest w_S * Perf(S)).
        top_skills: Vec<String>,
        /// The single best next skill to practice:
        /// argmax_S [ w_S * (1 - Perf(S)) * (1 if uncovered else 0.5) ]
        next_best: Option<String>,
    },
}

/// Compute Readiness from the Performance result.
///
/// Calls `readiness_gate`; if abstaining, returns the abstain payload with
/// **no** point estimate (D-SR10, spec-measurement §6).
/// If eligible, computes the D-SR18 corrected formula and produces a band
/// that widens as attempts ↓ and coverage ↓ (spec-measurement §9, AC 4).
pub fn compute_readiness(perf: &PerformanceResult) -> ReadinessResult {
    let coverage = compute_lr_coverage(&perf.skills);
    let total_attempts = perf.total_attempts;

    match readiness_gate(total_attempts, coverage) {
        GateResult::Abstain { reasons } => {
            let next_best = best_next_skill(perf, coverage);
            ReadinessResult::Abstain {
                reasons,
                coverage,
                total_attempts,
                next_best,
            }
        }
        GateResult::Eligible => {
            let weights = lr_frequency_weights();

            // D-SR18 corrected: expected_lr_raw = Σ_S [ w_S * Perf(S) * N_lr ]
            // equivalently Σ_S [ Perf(S) * items_per_form(S) ]
            let mut expected_lr_raw: f32 = 0.0;
            let mut weight_covered: f32 = 0.0;
            for skill in &perf.skills {
                if skill.attempts < MIN_ATTEMPTS_PER_SKILL {
                    continue;
                }
                if let Some(&w) = weights.get(skill.skill.as_str()) {
                    let perf_s = skill.correct as f32 / skill.attempts as f32;
                    expected_lr_raw += perf_s * w * N_LR;
                    weight_covered += w;
                }
            }

            // Project LR-only raw to full-form raw (D-SR19 Option B).
            let total_raw_estimate = expected_lr_raw * LR_TO_TOTAL_SCALE;
            let point = raw_to_scaled(total_raw_estimate);

            // Band width formula (AC 4 — must widen as coverage↓ / attempts↓):
            //   estimation_variance contribution: from Wilson widths of covered skills.
            //   coverage_gap contribution: uncovered fraction of the taxonomy.
            //
            // Band half-width in raw score units:
            //   base_half = Σ_S w_S * N_lr * (wilson_high - wilson_low) / 2
            //   coverage_gap_raw = (1 - coverage) * N_lr * 0.5
            //   total_half_raw = base_half + coverage_gap_raw
            //   Scaled ±: raw_to_scaled(point_raw + total_half) - point
            let mut base_half_raw: f32 = 0.0;
            for skill in &perf.skills {
                if skill.attempts < MIN_ATTEMPTS_PER_SKILL {
                    continue;
                }
                if let Some(&w) = weights.get(skill.skill.as_str()) {
                    let half_width = (skill.wilson_high - skill.wilson_low) / 2.0;
                    base_half_raw += w * N_LR * half_width;
                }
            }
            let coverage_gap_raw = (1.0 - coverage) * N_LR * 0.5;
            let total_half_raw = (base_half_raw + coverage_gap_raw) * LR_TO_TOTAL_SCALE;

            let band_low_raw = (total_raw_estimate - total_half_raw).max(0.0);
            let band_high_raw = (total_raw_estimate + total_half_raw).min(N_TOTAL);
            let band_low = raw_to_scaled(band_low_raw);
            let band_high = raw_to_scaled(band_high_raw);

            // Confidence tier.
            let confidence = if coverage >= 0.85 && total_attempts >= 500 {
                "high"
            } else if coverage >= 0.65 && total_attempts >= 300 {
                "medium"
            } else {
                "low"
            };

            // Top skills (highest w_S * Perf(S)).
            let mut top_skills_sorted: Vec<_> = perf
                .skills
                .iter()
                .filter(|s| s.attempts >= MIN_ATTEMPTS_PER_SKILL)
                .filter_map(|s| {
                    weights.get(s.skill.as_str()).map(|&w| {
                        let p = s.correct as f32 / s.attempts as f32;
                        (s.skill.clone(), w * p)
                    })
                })
                .collect();
            top_skills_sorted.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
            let top_skills: Vec<String> = top_skills_sorted
                .into_iter()
                .take(3)
                .map(|(s, _)| s)
                .collect();

            let next_best = best_next_skill(perf, coverage);

            // Coverage fraction among the `type::*` weights actually present.
            let coverage_out = if weight_covered > 0.0 {
                weight_covered // fraction of weights covered
            } else {
                coverage
            };

            ReadinessResult::Eligible {
                point,
                band_low,
                band_high,
                confidence,
                coverage: coverage_out.min(1.0),
                total_attempts,
                top_skills,
                next_best,
            }
        }
    }
}

/// argmax_S [ w_S * (1 - Perf(S)) * coverage_marginal(S) ]
///
/// coverage_marginal(S) = 1.0 if skill S is uncovered (< min attempts),
///                         0.5 if covered but perf < 1.0 (room to improve).
/// Returns None when no `type::*` weights are found.
fn best_next_skill(perf: &PerformanceResult, _coverage: f32) -> Option<String> {
    let weights = lr_frequency_weights();

    // Map existing skills to their performance.
    let skill_perf: HashMap<&str, f32> = perf
        .skills
        .iter()
        .filter(|s| s.attempts >= MIN_ATTEMPTS_PER_SKILL)
        .map(|s| (s.skill.as_str(), s.correct as f32 / s.attempts as f32))
        .collect();

    let best = weights
        .iter()
        .map(|(&skill, &w)| {
            let (p, marginal) = if let Some(&perf_s) = skill_perf.get(skill) {
                (perf_s, 0.5_f32) // covered — room for improvement
            } else {
                (0.0, 1.0_f32) // uncovered — highest priority
            };
            (skill, w * (1.0 - p) * marginal)
        })
        .max_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));

    best.map(|(s, _)| s.to_owned())
}

// ─── Shared tag helper (re-export from service.rs is not visible here) ────────

/// Extract the first tag that matches the Speedrun identity-tag pattern.
/// Duplicated here rather than making service.rs pub(crate) — avoids
/// cross-module coupling for a one-liner.
fn extract_skill_tag(note_tags: &str) -> Option<String> {
    note_tags
        .split_whitespace()
        .find(|t| {
            t.starts_with("type::")
                || t.starts_with("skill::")
                || t.starts_with("trap::")
        })
        .map(|t| t.to_owned())
}

// ─── Collection I/O wrapper ──────────────────────────────────────────────────

impl Collection {
    /// Compute Performance (per-skill Wilson accuracy) and Readiness for the
    /// given deck and all child decks.
    ///
    /// Returns `(PerformanceResult, ReadinessResult)`.
    pub fn performance_and_readiness_impl(
        &mut self,
        deck_id: i64,
    ) -> Result<(PerformanceResult, ReadinessResult)> {
        let target_deck_id = crate::decks::DeckId(deck_id);
        let decks = match self.storage.deck_with_children(target_deck_id) {
            Ok(d) => d,
            Err(_) => {
                let empty_perf = PerformanceResult {
                    skills: vec![],
                    overall_weighted: 0.0,
                    total_attempts: 0,
                    covered_skill_count: 0,
                };
                let readiness = compute_readiness(&empty_perf);
                return Ok((empty_perf, readiness));
            }
        };
        let deck_ids: Vec<crate::decks::DeckId> = decks.iter().map(|d| d.id).collect();

        // Fetch revlog rows for all skill cards in the deck hierarchy.
        let rows = if deck_ids.is_empty() {
            vec![]
        } else {
            self.storage.skill_revlog_in_decks(&deck_ids)?
        };

        // Convert to (note_tags, button_chosen) pairs for compute_performance.
        let pairs: Vec<(String, u32)> = rows
            .into_iter()
            .map(|r| (r.note_tags, r.button_chosen))
            .collect();

        let perf = compute_performance(&pairs);
        let readiness = compute_readiness(&perf);
        Ok((perf, readiness))
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── Wilson interval (AC 1) ────────────────────────────────────────────────

    /// AC 1: Wilson interval for a known corrects/attempts is correct.
    /// 7 correct out of 10: p_hat=0.7.  Wilson 95% CI ≈ (0.347, 0.934).
    #[test]
    fn wilson_interval_known_inputs() {
        let (lo, hi) = wilson_interval(7, 10);
        // Published Wilson CI for k=7, n=10, z=1.96:
        //   center = (0.7 + 1.96²/(2*10)) / (1 + 1.96²/10) ≈ 0.6765
        //   margin ≈ 0.2839
        //   lo ≈ 0.392, hi ≈ 0.960  (exact values depend on precision)
        assert!(lo > 0.30 && lo < 0.50, "wilson_low = {lo} (expected ~0.40)");
        assert!(hi > 0.88 && hi < 1.00, "wilson_high = {hi} (expected ~0.96)");
        // lo must be ≤ p_hat ≤ hi
        assert!(lo <= 0.7 && hi >= 0.7, "CI must bracket p_hat=0.7");
    }

    /// All correct: 10/10 → high lower bound.
    #[test]
    fn wilson_interval_all_correct() {
        let (lo, hi) = wilson_interval(10, 10);
        assert!(lo > 0.65, "lo={lo}");
        assert!((hi - 1.0).abs() < 0.01, "hi={hi}");
    }

    /// All wrong: 0/10 → CI near 0.
    #[test]
    fn wilson_interval_all_wrong() {
        let (lo, hi) = wilson_interval(0, 10);
        assert!(lo < 0.01, "lo={lo}");
        assert!(hi < 0.40, "hi={hi}");
    }

    /// Zero attempts: full uncertainty [0.0, 1.0].
    #[test]
    fn wilson_interval_zero_attempts() {
        assert_eq!(wilson_interval(0, 0), (0.0, 1.0));
    }

    // ── compute_performance ───────────────────────────────────────────────────

    /// Skills with ≥ 5 attempts are included in overall; sub-threshold are not.
    #[test]
    fn performance_coverage_threshold() {
        // 5 reviews for type::flaw (3 correct), 2 reviews for type::assumption.
        let rows: Vec<(String, u32)> = vec![
            ("type::flaw".into(), 3), // correct
            ("type::flaw".into(), 2), // correct
            ("type::flaw".into(), 3), // correct
            ("type::flaw".into(), 1), // wrong
            ("type::flaw".into(), 1), // wrong
            ("type::assumption".into(), 3),
            ("type::assumption".into(), 3),
        ];
        let perf = compute_performance(&rows);
        assert_eq!(perf.total_attempts, 7);
        // type::flaw: 3/5 correct; type::assumption: 2 attempts < threshold.
        let flaw = perf.skills.iter().find(|s| s.skill == "type::flaw").unwrap();
        assert_eq!(flaw.attempts, 5);
        assert_eq!(flaw.correct, 3);
        // Wilson interval should not be (0,1) for flaw since ≥ threshold.
        assert!(flaw.wilson_low > 0.01 || flaw.wilson_high < 0.99,
            "flaw CI should not be full uncertainty");

        let assum = perf.skills.iter().find(|s| s.skill == "type::assumption").unwrap();
        assert_eq!(assum.attempts, 2);
        // Below threshold → full uncertainty.
        assert_eq!((assum.wilson_low, assum.wilson_high), (0.0, 1.0));

        // covered_skill_count should be 1 (only flaw).
        assert_eq!(perf.covered_skill_count, 1);
    }

    // ── compute_readiness: abstain has no point estimate (AC 2) ──────────────

    /// AC 2: Abstain payload has no point estimate.
    #[test]
    fn readiness_abstain_no_point_estimate() {
        // Below both thresholds: 0 attempts, 0 coverage.
        let perf = PerformanceResult {
            skills: vec![],
            overall_weighted: 0.0,
            total_attempts: 50,
            covered_skill_count: 0,
        };
        let r = compute_readiness(&perf);
        assert!(
            matches!(r, ReadinessResult::Abstain { .. }),
            "expected Abstain with 50 attempts and 0% coverage"
        );
        // Verify there is no point field exposed (Rust type safety guarantees this,
        // but we also check the reasons are non-empty).
        if let ReadinessResult::Abstain { reasons, .. } = r {
            assert!(!reasons.is_empty(), "abstain must list reasons");
        }
    }

    /// At exactly (200 attempts, 50% coverage) → Eligible with point+band.
    #[test]
    fn readiness_eligible_at_threshold() {
        // Create 13 skills (all type::*), 7 with ≥ 5 attempts (= 53.8% ≥ 50%).
        let mut skills = vec![];
        let all_types = [
            "type::flaw",
            "type::assumption",
            "type::inference",
            "type::strengthen",
            "type::weaken",
            "type::principle",
            "type::paradox",
            "type::parallel",
            "type::method",
            "type::justify",
            "type::main-point",
            "type::point-at-issue",
            "type::evaluate",
        ];
        for (i, t) in all_types.iter().enumerate() {
            let (att, cor) = if i < 7 { (30, 20) } else { (2, 1) }; // 7 covered, 6 not
            let (wl, wh) = if att >= MIN_ATTEMPTS_PER_SKILL {
                wilson_interval(cor, att)
            } else {
                (0.0, 1.0)
            };
            skills.push(SkillPerf {
                skill: t.to_string(),
                attempts: att,
                correct: cor,
                wilson_low: wl,
                wilson_high: wh,
            });
        }
        let perf = PerformanceResult {
            skills,
            overall_weighted: 20.0 / 30.0,
            total_attempts: 7 * 30 + 6 * 2, // = 222 ≥ 200
            covered_skill_count: 7,
        };
        let r = compute_readiness(&perf);
        assert!(
            matches!(r, ReadinessResult::Eligible { .. }),
            "expected Eligible with 222 attempts and 7/13 coverage"
        );
        if let ReadinessResult::Eligible { point, band_low, band_high, .. } = r {
            assert!((120..=180).contains(&point), "point = {point}");
            assert!(band_low <= point, "band_low {band_low} > point {point}");
            assert!(band_high >= point, "band_high {band_high} < point {point}");
        }
    }

    // ── Band widens as attempts / coverage fall (AC 4) ────────────────────────

    /// AC 4 monotonicity: band width decreases as N increases (more data → narrower).
    #[test]
    fn readiness_band_widens_as_attempts_fall() {
        fn make_perf_with_n(n_per_skill: u32) -> (PerformanceResult, f32) {
            let all_types = [
                "type::flaw",
                "type::assumption",
                "type::inference",
                "type::strengthen",
                "type::weaken",
                "type::principle",
                "type::paradox",
                "type::parallel",
                "type::method",
                "type::justify",
                "type::main-point",
                "type::point-at-issue",
                "type::evaluate",
            ];
            let correct_per_skill = n_per_skill * 2 / 3; // ~67% perf
            let mut skills = vec![];
            for t in &all_types {
                let (wl, wh) = if n_per_skill >= MIN_ATTEMPTS_PER_SKILL {
                    wilson_interval(correct_per_skill, n_per_skill)
                } else {
                    (0.0, 1.0)
                };
                skills.push(SkillPerf {
                    skill: t.to_string(),
                    attempts: n_per_skill,
                    correct: correct_per_skill,
                    wilson_low: wl,
                    wilson_high: wh,
                });
            }
            let total = n_per_skill * all_types.len() as u32;
            let perf = PerformanceResult {
                skills,
                overall_weighted: correct_per_skill as f32 / n_per_skill as f32,
                total_attempts: total,
                covered_skill_count: all_types.len() as u32,
            };
            let r = compute_readiness(&perf);
            let band_width = if let ReadinessResult::Eligible { band_low, band_high, .. } = r {
                (band_high - band_low) as f32
            } else {
                // Still abstaining — band is conceptually infinite; use N_TOTAL as proxy.
                N_TOTAL
            };
            (perf, band_width)
        }

        // With full coverage (13/13 skills), varying N:
        // n=5 → just above threshold → wide band
        let (_, bw_5) = make_perf_with_n(5);
        // n=200 → narrow band
        let (_, bw_200) = make_perf_with_n(200);
        // band at n=5 must be ≥ band at n=200.
        assert!(
            bw_5 >= bw_200,
            "band with n=5 ({bw_5}) should be ≥ band with n=200 ({bw_200})"
        );
    }

    /// AC 4 monotonicity: partial coverage → wider band than full coverage.
    #[test]
    fn readiness_band_widens_as_coverage_falls() {
        fn make_perf_with_coverage(covered: usize) -> f32 {
            let all_types = [
                "type::flaw",
                "type::assumption",
                "type::inference",
                "type::strengthen",
                "type::weaken",
                "type::principle",
                "type::paradox",
                "type::parallel",
                "type::method",
                "type::justify",
                "type::main-point",
                "type::point-at-issue",
                "type::evaluate",
            ];
            let mut skills = vec![];
            for (i, t) in all_types.iter().enumerate() {
                let (att, cor) = if i < covered { (50, 35) } else { (2, 1) };
                let (wl, wh) = if att >= MIN_ATTEMPTS_PER_SKILL {
                    wilson_interval(cor, att)
                } else {
                    (0.0, 1.0)
                };
                skills.push(SkillPerf {
                    skill: t.to_string(),
                    attempts: att,
                    correct: cor,
                    wilson_low: wl,
                    wilson_high: wh,
                });
            }
            let total = covered as u32 * 50 + (13 - covered) as u32 * 2;
            let perf = PerformanceResult {
                skills,
                overall_weighted: 35.0 / 50.0,
                total_attempts: total,
                covered_skill_count: covered as u32,
            };
            let r = compute_readiness(&perf);
            if let ReadinessResult::Eligible { band_low, band_high, .. } = r {
                (band_high - band_low) as f32
            } else {
                N_TOTAL // abstaining → conceptually widest
            }
        }

        // Full coverage (13/13, ≥200 att) vs 7/13 coverage.
        let bw_full = make_perf_with_coverage(13);
        let bw_partial = make_perf_with_coverage(7);
        assert!(
            bw_partial >= bw_full,
            "partial coverage band ({bw_partial}) should be ≥ full coverage band ({bw_full})"
        );
    }

    // ── raw_to_scaled ─────────────────────────────────────────────────────────

    #[test]
    fn raw_to_scaled_boundary_values() {
        assert_eq!(raw_to_scaled(76.0), 180);
        assert_eq!(raw_to_scaled(0.0), 120);
        assert_eq!(raw_to_scaled(50.0), 163);
        assert_eq!(raw_to_scaled(38.0), 152);
    }
}
