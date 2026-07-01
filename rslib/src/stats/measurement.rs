// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! Speedrun WP-7: Memory score and the readiness give-up gate.
//!
//! Two independent deliverables in this module:
//!
//! 1. [`readiness_gate`] — a **pure function** with no I/O that decides whether
//!    the user has accumulated enough evidence to display a Readiness estimate.
//!    Lives in Rust so the desktop app and the AnkiDroid companion agree on the
//!    threshold — see spec-measurement §6 and D-SR10.
//!
//! 2. [`compute_memory_score`] — computes **Memory** (mean FSRS recall over
//!    `LSAT Meta` cards) with a 95% percentile-bootstrap confidence interval.
//!    [`Collection::memory_score_impl`] is the I/O wrapper that fetches the
//!    per-card rows from storage and calls this pure computation.
//!
//! # Exposure note (WP-14)
//!
//! The Memory computation is fully implemented and unit-tested here but is
//! intentionally **not** wired to a protobuf RPC or Python pylib call in WP-7.
//! Adding a `MetaMemory` RPC requires regenerating all language bindings (a
//! full `just build`), which carries coordination risk while WP-6 is running
//! in parallel on the same tree.  WP-14 (Performance + Readiness + dashboard),
//! which already depends on WP-7, will add the RPC at that point.
//! See `docs/speedrun/inbox/WP-7-log.md §L1`.

use rand::rngs::StdRng;
use rand::Rng as _;
use rand::SeedableRng;

use crate::collection::Collection;
use crate::error::Result;
use crate::storage::card::data::CardData;
use crate::timestamp::TimestampSecs;

// ─── Gate ─────────────────────────────────────────────────────────────────────

/// A reason the readiness gate refused to emit a Readiness estimate.
///
/// Each variant carries the observed value (`have`) and the required threshold
/// (`need`) so the dashboard can display a concrete "you need X more attempts"
/// message per PRD §3.
#[derive(Debug, Clone, PartialEq)]
pub enum GateReason {
    /// Total attempt count is below the minimum required.
    MinAttempts { have: u32, need: u32 },
    /// Coverage fraction is below the minimum required.
    ///
    /// Coverage = fraction of the LR taxonomy whose skill has ≥ min pool size
    /// **and** ≥ min attempts (spec-measurement §5).
    MinCoverage { have: f32, need: f32 },
    // Phase-2: per-section minimums (RC + LG) are reserved and NOT implemented
    // here.  When added, extend this enum with a `MinSectionAttempts` variant
    // and update `readiness_gate` to accept `per_section_mins: &HashMap<…, u32>`.
}

/// The result of [`readiness_gate`].
#[derive(Debug, Clone, PartialEq)]
pub enum GateResult {
    /// The user has enough evidence; the dashboard may show a Readiness point
    /// estimate with its band.
    Eligible,
    /// Not enough evidence.  The payload lists every failed threshold.  The
    /// dashboard **must not** emit a Readiness point estimate while abstaining
    /// (D-SR10, spec-measurement §6, PRD §3).
    Abstain { reasons: Vec<GateReason> },
}

/// **Pure give-up gate** — no I/O, no side-effects; lives in Rust so desktop
/// and AnkiDroid agree (D-SR10).
///
/// Returns [`GateResult::Eligible`] if and only if **both** thresholds are
/// simultaneously met:
/// - `attempts >= 200`
/// - `coverage >= 0.50`
///
/// Otherwise returns [`GateResult::Abstain`] with every failed threshold in
/// `reasons`.  The caller must show the abstain payload (evidence so far, exact
/// failed reasons, next-best-thing) instead of a point estimate.
///
/// # Phase-2 note
/// Per-section minimums (RC) are reserved and are NOT checked here.
pub fn readiness_gate(attempts: u32, coverage: f32) -> GateResult {
    let mut reasons = Vec::new();
    if attempts < 200 {
        reasons.push(GateReason::MinAttempts {
            have: attempts,
            need: 200,
        });
    }
    if coverage < 0.50 {
        reasons.push(GateReason::MinCoverage {
            have: coverage,
            need: 0.50,
        });
    }
    if reasons.is_empty() {
        GateResult::Eligible
    } else {
        GateResult::Abstain { reasons }
    }
}

// ─── Memory score ─────────────────────────────────────────────────────────────

/// Memory score: mean FSRS recall probability over `LSAT Meta` cards + a
/// 95% percentile-bootstrap confidence interval.
///
/// Reported to the dashboard as "point + band + N meta-cards" per
/// spec-measurement §4.1.
#[derive(Debug, Clone, PartialEq)]
pub struct MemoryScore {
    /// Arithmetic mean of per-card FSRS recall probabilities `∈ [0, 1]`.
    pub mean_recall: f32,
    /// 2.5th percentile of the bootstrap distribution of the mean.
    pub ci_lower: f32,
    /// 97.5th percentile of the bootstrap distribution of the mean.
    pub ci_upper: f32,
    /// Number of `LSAT Meta` cards in the queried deck (including unreviewed).
    pub card_count: u32,
}

/// Compute the Memory score from a slice of per-card FSRS recall values
/// (each `∈ [0.0, 1.0]`).  This is a **pure function** — all I/O is
/// handled by [`Collection::memory_score_impl`].
///
/// `bootstrap_seed` makes the CI reproducible (use `0` or any fixed constant
/// in production; use a known seed in tests).
///
/// Returns `None` when `recalls` is empty (no Meta cards in the deck).
pub fn compute_memory_score(recalls: &[f32], bootstrap_seed: u64) -> Option<MemoryScore> {
    if recalls.is_empty() {
        return None;
    }
    let n = recalls.len();
    let mean = recalls.iter().sum::<f32>() / n as f32;

    // 1 000 percentile-bootstrap resamples of the mean; see WP-7-log.md §L2.
    const BOOTSTRAP_SAMPLES: usize = 1_000;
    let (ci_lower, ci_upper) = bootstrap_ci_mean(recalls, BOOTSTRAP_SAMPLES, bootstrap_seed);

    Some(MemoryScore {
        mean_recall: mean,
        ci_lower,
        ci_upper,
        card_count: n as u32,
    })
}

/// 95% percentile bootstrap CI for the mean of `data`.
///
/// Draws `n_samples` resamples of length `data.len()` with replacement,
/// computes the mean of each, and returns the 2.5th / 97.5th percentiles.
fn bootstrap_ci_mean(data: &[f32], n_samples: usize, seed: u64) -> (f32, f32) {
    let n = data.len();
    let mut rng = StdRng::seed_from_u64(seed);
    let mut boot_means: Vec<f32> = Vec::with_capacity(n_samples);
    for _ in 0..n_samples {
        let sum: f32 = (0..n).map(|_| data[rng.random_range(0..n)]).sum();
        boot_means.push(sum / n as f32);
    }
    boot_means.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let lo_idx = ((n_samples as f32) * 0.025) as usize;
    let hi_idx = (((n_samples as f32) * 0.975) as usize).min(n_samples - 1);
    (boot_means[lo_idx], boot_means[hi_idx])
}

// ─── Collection I/O wrapper ──────────────────────────────────────────────────

impl Collection {
    /// Compute the Memory score for `LSAT Meta` cards in `deck_id` (and all
    /// child decks).
    ///
    /// Mirrors the structure of `skill_mastery_impl` in `stats/service.rs`:
    /// one indexed SQL round-trip to fetch per-card data, then FSRS recall
    /// computed in Rust, then [`compute_memory_score`] for the aggregate.
    ///
    /// Returns `None` when the deck has no Meta cards (cold start / wrong
    /// deck ID).
    ///
    /// **Not yet exposed as a protobuf RPC.**  See module-level doc comment and
    /// `docs/speedrun/inbox/WP-7-log.md §L1`.
    pub fn memory_score_impl(&mut self, deck_id: i64) -> Result<Option<MemoryScore>> {
        use fsrs::FSRS;
        use fsrs::FSRS5_DEFAULT_DECAY;

        let target_deck_id = crate::decks::DeckId(deck_id);
        let decks = match self.storage.deck_with_children(target_deck_id) {
            Ok(d) => d,
            Err(_) => return Ok(None),
        };
        let deck_ids: Vec<crate::decks::DeckId> = decks.iter().map(|d| d.id).collect();
        if deck_ids.is_empty() {
            return Ok(None);
        }

        let rows = self.storage.meta_cards_in_decks(&deck_ids)?;
        if rows.is_empty() {
            return Ok(None);
        }

        let now_secs = TimestampSecs::now().0;
        let timing = self.timing_today()?;
        let today = timing.days_elapsed as i64;

        let fsrs = FSRS::new(None)?;

        let recalls: Vec<f32> = rows
            .iter()
            .map(|row| {
                let card_data = CardData::from_str(&row.card_data_json);
                match card_data.memory_state() {
                    Some(state) => {
                        let elapsed = crate::stats::service::elapsed_seconds_for_card(
                            &card_data,
                            row.due,
                            row.ivl,
                            now_secs,
                            today,
                        );
                        let decay = card_data.decay.unwrap_or(FSRS5_DEFAULT_DECAY);
                        fsrs.current_retrievability_seconds(state.into(), elapsed, decay)
                    }
                    None => 0.0, // unreviewed Meta card → recall 0.0 (honest cold-start)
                }
            })
            .collect();

        // Use a fixed bootstrap seed; the CI is an estimate either way.
        Ok(compute_memory_score(&recalls, 0xDEAD_BEEF_1234_5678))
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::decks::DeckId;
    use crate::error::Result as AnkiResult;
    use crate::prelude::*;

    // ── readiness_gate — exact AC 2 cases (spec-measurement §10 AC 2) ────────

    /// AC 2 (required): `(199, 0.49)` → Abstain with **both** MinAttempts and
    /// MinCoverage reasons.
    #[test]
    fn gate_both_fail_abstains_with_both_reasons() {
        match readiness_gate(199, 0.49) {
            GateResult::Abstain { reasons } => {
                assert!(
                    reasons
                        .iter()
                        .any(|r| matches!(r, GateReason::MinAttempts { have: 199, .. })),
                    "expected MinAttempts(199) in reasons, got {:?}",
                    reasons
                );
                assert!(
                    reasons
                        .iter()
                        .any(|r| matches!(r, GateReason::MinCoverage { .. })),
                    "expected MinCoverage in reasons, got {:?}",
                    reasons
                );
            }
            GateResult::Eligible => panic!("(199, 0.49) must Abstain, got Eligible"),
        }
    }

    /// AC 2 (required): `(200, 0.50)` → Eligible.
    #[test]
    fn gate_exact_thresholds_eligible() {
        assert_eq!(
            readiness_gate(200, 0.50),
            GateResult::Eligible,
            "(200, 0.50) must be Eligible"
        );
    }

    // ── Boundary tests ─────────────────────────────────────────────────────────

    /// Attempts = 199, coverage OK → Abstain with MinAttempts only.
    #[test]
    fn gate_attempts_199_abstains_only_min_attempts() {
        match readiness_gate(199, 0.60) {
            GateResult::Abstain { reasons } => {
                assert_eq!(reasons.len(), 1, "expected exactly 1 reason, got {:?}", reasons);
                assert!(
                    matches!(reasons[0], GateReason::MinAttempts { have: 199, need: 200 }),
                    "wrong reason: {:?}",
                    reasons[0]
                );
            }
            GateResult::Eligible => panic!("199 attempts must Abstain"),
        }
    }

    /// Attempts = 200, coverage OK → Eligible.
    #[test]
    fn gate_attempts_200_eligible() {
        assert_eq!(readiness_gate(200, 0.55), GateResult::Eligible);
    }

    /// Coverage = 0.49, attempts OK → Abstain with MinCoverage only.
    #[test]
    fn gate_coverage_049_abstains_only_min_coverage() {
        match readiness_gate(250, 0.49) {
            GateResult::Abstain { reasons } => {
                assert_eq!(reasons.len(), 1, "expected exactly 1 reason, got {:?}", reasons);
                assert!(
                    matches!(reasons[0], GateReason::MinCoverage { .. }),
                    "wrong reason: {:?}",
                    reasons[0]
                );
            }
            GateResult::Eligible => panic!("0.49 coverage must Abstain"),
        }
    }

    /// Coverage = 0.50, attempts OK → Eligible.
    #[test]
    fn gate_coverage_050_eligible() {
        assert_eq!(readiness_gate(250, 0.50), GateResult::Eligible);
    }

    /// Zero attempts, zero coverage → Abstain with exactly 2 reasons.
    #[test]
    fn gate_zero_zero_abstains_both() {
        match readiness_gate(0, 0.0) {
            GateResult::Abstain { reasons } => {
                assert_eq!(reasons.len(), 2, "expected 2 reasons, got {:?}", reasons);
            }
            GateResult::Eligible => panic!("(0, 0.0) must Abstain"),
        }
    }

    /// Large values well above both thresholds → Eligible.
    #[test]
    fn gate_above_both_thresholds_eligible() {
        assert_eq!(readiness_gate(10_000, 1.0), GateResult::Eligible);
    }

    // ── compute_memory_score ─────────────────────────────────────────────────

    /// Empty recalls → None (no Meta cards).
    #[test]
    fn memory_score_empty_returns_none() {
        assert!(compute_memory_score(&[], 42).is_none());
    }

    /// Single card at recall 0.8: mean = 0.8; CI brackets mean (degenerate).
    #[test]
    fn memory_score_single_card_brackets_mean() {
        let score = compute_memory_score(&[0.8], 42).unwrap();
        assert!(
            (score.mean_recall - 0.8).abs() < 1e-5,
            "mean = {}",
            score.mean_recall
        );
        assert_eq!(score.card_count, 1);
        assert!(
            score.ci_lower <= score.mean_recall + 1e-5,
            "ci_lower {} > mean {}",
            score.ci_lower,
            score.mean_recall
        );
        assert!(
            score.ci_upper >= score.mean_recall - 1e-5,
            "ci_upper {} < mean {}",
            score.ci_upper,
            score.mean_recall
        );
    }

    /// Known input [0.4, 0.6, 0.8]: mean = 0.6; bootstrap CI brackets mean.
    /// This is the AC 1 "known recall → assert mean + band brackets it" test.
    #[test]
    fn memory_score_known_input_mean_and_ci() {
        let recalls = [0.4_f32, 0.6, 0.8];
        let score = compute_memory_score(&recalls, 12345).unwrap();

        assert!(
            (score.mean_recall - 0.6).abs() < 1e-5,
            "expected mean 0.6, got {}",
            score.mean_recall
        );
        assert_eq!(score.card_count, 3);

        // CI must bracket the mean (key property per spec-measurement §4.1).
        assert!(
            score.ci_lower <= score.mean_recall,
            "CI lower {} must be ≤ mean {}",
            score.ci_lower,
            score.mean_recall
        );
        assert!(
            score.ci_upper >= score.mean_recall,
            "CI upper {} must be ≥ mean {}",
            score.ci_upper,
            score.mean_recall
        );
    }

    /// Uniform 0.9 across 10 cards: mean = 0.9; CI collapses to the mean.
    #[test]
    fn memory_score_uniform_high_recall_narrow_ci() {
        let recalls: Vec<f32> = vec![0.9; 10];
        let score = compute_memory_score(&recalls, 99).unwrap();
        assert!(
            (score.mean_recall - 0.9).abs() < 1e-5,
            "mean = {}",
            score.mean_recall
        );
        // All bootstrap resamples have mean 0.9 exactly → CI collapses.
        assert!(
            (score.ci_lower - 0.9).abs() < 1e-5,
            "ci_lower = {}",
            score.ci_lower
        );
        assert!(
            (score.ci_upper - 0.9).abs() < 1e-5,
            "ci_upper = {}",
            score.ci_upper
        );
    }

    // ── Collection::memory_score_impl integration test ────────────────────────

    /// Add an "LSAT Meta" notetype + three Meta notes to a fresh in-memory
    /// collection; assert Memory score mean and CI bracket it.
    ///
    /// Recall at elapsed = 0 s with any positive stability ≈ 1.0.
    /// Recall for an unreviewed card = 0.0.
    /// Three cards: two mastered (recall ≈ 1.0), one unreviewed (recall = 0.0).
    /// Expected mean ≈ 2/3 ≈ 0.667.
    #[test]
    fn memory_score_impl_aggregate_correctness() -> AnkiResult<()> {
        use crate::card::FsrsMemoryState;

        let mut col = Collection::new();

        // Rename the built-in "Basic" notetype to "LSAT Meta" so the storage
        // query finds it (mirrors the WP-5 test pattern).
        let nt_arc = col.get_notetype_by_name("Basic")?.unwrap();
        let mut nt = (*nt_arc).clone();
        nt.name = "LSAT Meta".into();
        col.update_notetype(&mut nt, false)?;
        let nt = col.get_notetype_by_name("LSAT Meta")?.unwrap();

        // Add three Meta notes.
        let mut note_a = nt.new_note();
        col.add_note(&mut note_a, DeckId(1))?;
        let mut note_b = nt.new_note();
        col.add_note(&mut note_b, DeckId(1))?;
        let mut note_c = nt.new_note(); // will remain unreviewed
        col.add_note(&mut note_c, DeckId(1))?;

        let now = TimestampSecs::now();
        let mastered_state = FsrsMemoryState {
            stability: 30.0,
            difficulty: 5.0,
        };

        let set_mastered = |col: &mut Collection, nid: NoteId| -> AnkiResult<()> {
            let cards = col.storage.all_cards_of_note(nid)?;
            for mut card in cards {
                card.memory_state = Some(mastered_state);
                card.last_review_time = Some(now);
                col.storage.update_card(&card)?;
            }
            Ok(())
        };

        set_mastered(&mut col, note_a.id)?;
        set_mastered(&mut col, note_b.id)?;
        // note_c: left unreviewed → recall 0.0

        let score = col
            .memory_score_impl(1)?
            .expect("deck 1 has Meta cards");

        assert_eq!(score.card_count, 3, "expected 3 Meta cards");

        // mean ≈ (1.0 + 1.0 + 0.0) / 3 ≈ 0.667
        assert!(
            score.mean_recall >= 0.60 && score.mean_recall <= 0.70,
            "mean_recall = {} (expected ≈ 0.667)",
            score.mean_recall
        );

        // Bootstrap CI must bracket the mean.
        assert!(
            score.ci_lower <= score.mean_recall,
            "ci_lower {} > mean {}",
            score.ci_lower,
            score.mean_recall
        );
        assert!(
            score.ci_upper >= score.mean_recall,
            "ci_upper {} < mean {}",
            score.ci_upper,
            score.mean_recall
        );

        Ok(())
    }

    /// Empty deck → memory_score_impl returns None.
    #[test]
    fn memory_score_impl_empty_deck_returns_none() -> AnkiResult<()> {
        let mut col = Collection::new();
        // Default collection has no "LSAT Meta" notetype, so no Meta cards.
        let result = col.memory_score_impl(1)?;
        assert!(
            result.is_none(),
            "expected None for deck with no Meta cards"
        );
        Ok(())
    }
}
