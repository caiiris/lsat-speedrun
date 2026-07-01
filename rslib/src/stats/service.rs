// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
use anki_proto::stats::SkillMastery;
use anki_proto::stats::SkillMasteryResponse;
use anki_proto::stats::SpeedrunDashboardRequest;
use anki_proto::stats::SpeedrunDashboardResponse;
use anki_proto::stats::SpeedrunMemoryScore;
use anki_proto::stats::SpeedrunReadinessAbstain;
use anki_proto::stats::SpeedrunReadinessEligible;
use anki_proto::stats::SpeedrunSkillPerf;
use fsrs::FSRS;
use fsrs::FSRS5_DEFAULT_DECAY;

use crate::collection::Collection;
use crate::error;
use crate::error::Result;
use crate::revlog::RevlogReviewKind;
use crate::stats::measurement::GateReason;
use crate::stats::performance::ReadinessResult;
use crate::storage::card::data::CardData;
use crate::timestamp::TimestampSecs;

/// A skill card is "mastered" when its current FSRS recall probability is at
/// or above this threshold.  0.90 matches FSRS's default desired-retention
/// and the colloquial meaning of "mastered" — see WP-5-log.md §L1.
const MASTERY_RECALL_THRESHOLD: f32 = 0.90;

impl crate::services::StatsService for Collection {
    fn card_stats(
        &mut self,
        input: anki_proto::cards::CardId,
    ) -> error::Result<anki_proto::stats::CardStatsResponse> {
        self.card_stats(input.cid.into())
    }

    fn get_review_logs(
        &mut self,
        input: anki_proto::cards::CardId,
    ) -> error::Result<anki_proto::stats::ReviewLogs> {
        self.get_review_logs(input.cid.into())
    }

    fn graphs(
        &mut self,
        input: anki_proto::stats::GraphsRequest,
    ) -> error::Result<anki_proto::stats::GraphsResponse> {
        self.graph_data_for_search(&input.search, input.days)
    }

    fn get_graph_preferences(&mut self) -> error::Result<anki_proto::stats::GraphPreferences> {
        Ok(Collection::get_graph_preferences(self))
    }

    fn set_graph_preferences(
        &mut self,
        input: anki_proto::stats::GraphPreferences,
    ) -> error::Result<()> {
        self.set_graph_preferences(input)
    }

    /// Speedrun WP-5: per-skill mastery aggregate for the dashboard.
    ///
    /// For each LSAT Skill card in the given deck (and its child decks),
    /// computes current FSRS recall and groups results by skill identity tag.
    /// Returns `mastered` (cards with recall ≥ 0.90), `total`, and `avg_recall`
    /// per skill.  One indexed SQL query + Rust-side aggregation; see
    /// `storage/card/speedrun.rs` and `docs/speedrun/inbox/WP-5-log.md`.
    fn skill_mastery(
        &mut self,
        input: anki_proto::stats::SkillMasteryRequest,
    ) -> error::Result<anki_proto::stats::SkillMasteryResponse> {
        self.skill_mastery_impl(input.deck_id)
    }

    /// Speedrun WP-14: three-score dashboard (Memory + Performance + Readiness).
    ///
    /// Returns a combined payload with:
    /// - Memory: mean FSRS recall over LSAT Meta cards + 95% bootstrap CI.
    /// - Performance: per-skill Wilson accuracy from the skill-card revlog.
    /// - Readiness: either an Abstain payload (no point estimate) or an Eligible
    ///   payload (point + band + confidence) labeled "LR-only estimate".
    ///
    /// The dashboard MUST NOT display a Readiness number when `eligible = false`
    /// (D-SR10, spec-measurement §6).
    fn speedrun_dashboard(
        &mut self,
        input: SpeedrunDashboardRequest,
    ) -> error::Result<SpeedrunDashboardResponse> {
        self.speedrun_dashboard_impl(input.deck_id)
    }
}

impl Collection {
    fn skill_mastery_impl(&mut self, deck_id: i64) -> Result<SkillMasteryResponse> {
        use std::collections::HashMap;

        let target_deck_id = crate::decks::DeckId(deck_id);

        // Resolve deck + all children.  `deck_with_children` returns an empty
        // Vec when the deck doesn't exist, so no special-casing needed here.
        let decks = match self.storage.deck_with_children(target_deck_id) {
            Ok(d) => d,
            Err(_) => return Ok(SkillMasteryResponse::default()),
        };
        let deck_ids: Vec<crate::decks::DeckId> = decks.iter().map(|d| d.id).collect();

        if deck_ids.is_empty() {
            return Ok(SkillMasteryResponse::default());
        }

        // Single SQL round-trip: fetch skill card rows (indexed on did).
        let rows = self.storage.skill_cards_in_decks(&deck_ids)?;

        if rows.is_empty() {
            return Ok(SkillMasteryResponse::default());
        }

        // Compute now_secs once for all cards.
        let now_secs = TimestampSecs::now().0;
        let timing = self.timing_today()?;
        let today = timing.days_elapsed as i64;

        // Aggregate per skill: (mastered_count, total_count, recall_sum)
        let mut skill_agg: HashMap<String, (u32, u32, f32)> = HashMap::new();

        let fsrs = FSRS::new(None)?;

        for row in rows {
            // Extract skill identity tag (first tag matching type::, skill::, trap::).
            let skill = match extract_skill_tag(&row.note_tags) {
                Some(s) => s,
                None => continue, // skip cards with no identity tag (shouldn't happen)
            };

            // Parse FSRS memory state from the card data JSON.
            let card_data = CardData::from_str(&row.card_data_json);
            let memory_state = card_data.memory_state();

            // Compute recall.  Cards with no memory state (never reviewed) get 0.0.
            let recall: f32 = match memory_state {
                Some(state) => {
                    let elapsed_secs =
                        elapsed_seconds_for_card(&card_data, row.due, row.ivl, now_secs, today);
                    let decay = card_data.decay.unwrap_or(FSRS5_DEFAULT_DECAY);
                    fsrs.current_retrievability_seconds(state.into(), elapsed_secs, decay)
                }
                None => 0.0,
            };

            let entry = skill_agg.entry(skill).or_insert((0, 0, 0.0));
            entry.1 += 1; // total
            entry.2 += recall; // recall_sum
            if recall >= MASTERY_RECALL_THRESHOLD {
                entry.0 += 1; // mastered
            }
        }

        // Build response sorted by skill name for deterministic output.
        let mut skills: Vec<_> = skill_agg.into_iter().collect();
        skills.sort_by(|a, b| a.0.cmp(&b.0));

        let skills = skills
            .into_iter()
            .map(|(skill, (mastered, total, recall_sum))| {
                let avg_recall = if total == 0 {
                    0.0
                } else {
                    recall_sum / total as f32
                };
                SkillMastery {
                    skill,
                    mastered,
                    total,
                    avg_recall,
                }
            })
            .collect();

        Ok(SkillMasteryResponse { skills })
    }

    fn speedrun_dashboard_impl(&mut self, deck_id: i64) -> Result<SpeedrunDashboardResponse> {
        use crate::stats::performance::compute_lr_coverage;

        // ── Memory (from LSAT Meta cards) ─────────────────────────────────────
        let memory: Option<SpeedrunMemoryScore> =
            self.memory_score_impl(deck_id)?.map(|m| SpeedrunMemoryScore {
                mean_recall: m.mean_recall,
                ci_lower: m.ci_lower,
                ci_upper: m.ci_upper,
                card_count: m.card_count,
            });

        // ── Performance + Readiness (from LSAT Skill revlog) ─────────────────
        let (perf, readiness) = self.performance_and_readiness_impl(deck_id)?;

        let lr_coverage = compute_lr_coverage(&perf.skills);

        let skill_perf: Vec<SpeedrunSkillPerf> = perf
            .skills
            .iter()
            .map(|s| SpeedrunSkillPerf {
                skill: s.skill.clone(),
                attempts: s.attempts,
                correct: s.correct,
                wilson_low: s.wilson_low,
                wilson_high: s.wilson_high,
            })
            .collect();

        let (eligible, abstain, readiness_eligible) = match readiness {
            ReadinessResult::Abstain {
                reasons,
                coverage,
                total_attempts,
                next_best,
            } => {
                let reason_strs: Vec<String> = reasons
                    .iter()
                    .map(|r| match r {
                        GateReason::MinAttempts { have, need } => {
                            format!("Need ≥{need} total attempts (have {have})")
                        }
                        GateReason::MinCoverage { have, need } => {
                            format!(
                                "Need ≥{:.0}% LR coverage (have {:.0}%)",
                                need * 100.0,
                                have * 100.0
                            )
                        }
                    })
                    .collect();
                let abstain_msg = SpeedrunReadinessAbstain {
                    reasons: reason_strs,
                    coverage,
                    total_attempts,
                    next_best: next_best.unwrap_or_default(),
                };
                (false, Some(abstain_msg), None)
            }
            ReadinessResult::Eligible {
                point,
                band_low,
                band_high,
                confidence,
                coverage,
                total_attempts,
                top_skills,
                next_best,
            } => {
                let eligible_msg = SpeedrunReadinessEligible {
                    point,
                    band_low,
                    band_high,
                    confidence: confidence.to_owned(),
                    coverage,
                    total_attempts,
                    top_skills,
                    next_best: next_best.unwrap_or_default(),
                };
                (true, None, Some(eligible_msg))
            }
        };

        Ok(SpeedrunDashboardResponse {
            memory,
            skill_perf,
            overall_perf: perf.overall_weighted,
            lr_coverage,
            total_attempts: perf.total_attempts,
            eligible,
            abstain,
            readiness: readiness_eligible,
        })
    }
}

/// Extract the first tag that matches the Speedrun identity-tag pattern
/// (`type::*`, `skill::*`, `trap::*`).  Tags are stored as ` tag1 tag2 … `
/// (space-delimited, with leading/trailing spaces — see `tags::join_tags`).
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

/// Mirror of `Card::seconds_since_last_review` — computes elapsed seconds from
/// the card data fields available in a [`SkillCardRow`], preferring the
/// `last_review_time` stored in the card data blob when present.
///
/// This replicates the exact same logic used in `stats/graphs/retrievability.rs`
/// and `storage/sqlite.rs:add_extract_fsrs_retrievability`.
///
/// `pub(super)` so `measurement.rs` (same `stats` module) can reuse it.
pub(super) fn elapsed_seconds_for_card(
    card_data: &CardData,
    due: i32,
    ivl: i32,
    now_secs: i64,
    today: i64,
) -> u32 {
    if let Some(lrt) = card_data.last_review_time {
        // Accurate: last review time is stored in card data.
        (now_secs as u32).saturating_sub(lrt.0 as u32)
    } else if due > 365_000 {
        // (Re)learning card: due is a unix timestamp in seconds.
        let last_review_ts = (due as u32).saturating_sub(ivl as u32);
        (now_secs as u32).saturating_sub(last_review_ts)
    } else {
        // Review card: due is days since collection creation.
        let review_day = (due as u32).saturating_sub(ivl as u32);
        (today as u32).saturating_sub(review_day) * 86_400
    }
}

impl From<RevlogReviewKind> for i32 {
    fn from(kind: RevlogReviewKind) -> Self {
        (match kind {
            RevlogReviewKind::Learning => anki_proto::stats::revlog_entry::ReviewKind::Learning,
            RevlogReviewKind::Review => anki_proto::stats::revlog_entry::ReviewKind::Review,
            RevlogReviewKind::Relearning => anki_proto::stats::revlog_entry::ReviewKind::Relearning,
            RevlogReviewKind::Filtered => anki_proto::stats::revlog_entry::ReviewKind::Filtered,
            RevlogReviewKind::Manual => anki_proto::stats::revlog_entry::ReviewKind::Manual,
            RevlogReviewKind::Rescheduled => {
                anki_proto::stats::revlog_entry::ReviewKind::Rescheduled
            }
        }) as i32
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod test {
    use super::*;
    use crate::card::FsrsMemoryState;
    use crate::decks::DeckId;
    use crate::prelude::*;
    use crate::search::SortMode;

    #[test]
    fn stats() -> Result<()> {
        let mut col = Collection::new();

        let nt = col.get_notetype_by_name("Basic")?.unwrap();
        let mut note = nt.new_note();
        col.add_note(&mut note, DeckId(1))?;

        let cid = col.search_cards("", SortMode::NoOrder)?[0];
        let _report = col.card_stats(cid)?;

        Ok(())
    }

    /// Verify that `extract_skill_tag` correctly extracts identity tags.
    #[test]
    fn test_extract_skill_tag() {
        assert_eq!(
            extract_skill_tag(" type::assumption "),
            Some("type::assumption".to_owned())
        );
        assert_eq!(
            extract_skill_tag(" skill::conditional-reasoning "),
            Some("skill::conditional-reasoning".to_owned())
        );
        assert_eq!(
            extract_skill_tag(" trap::sufficient-necessary "),
            Some("trap::sufficient-necessary".to_owned())
        );
        // non-identity tags → None
        assert_eq!(extract_skill_tag(" category::vocab "), None);
        assert_eq!(extract_skill_tag(""), None);
        // synthetic::true tag should not match
        assert_eq!(extract_skill_tag(" synthetic::true "), None);
        // multiple tags — pick first matching
        assert_eq!(
            extract_skill_tag(" category::x type::flaw "),
            Some("type::flaw".to_owned())
        );
    }

    /// Verify that skill_mastery returns empty for a deck with no skill cards.
    #[test]
    fn test_skill_mastery_empty_deck() -> Result<()> {
        let mut col = Collection::new();
        // Add a note to the default deck (Basic notetype, not LSAT Skill)
        let nt = col.get_notetype_by_name("Basic")?.unwrap();
        let mut note = nt.new_note();
        col.add_note(&mut note, DeckId(1))?;

        let resp = col
            .skill_mastery_impl(1)
            .expect("skill_mastery should succeed on deck with no skill cards");
        assert!(
            resp.skills.is_empty(),
            "expected empty response for non-skill deck"
        );
        Ok(())
    }

    /// Mastery aggregate correctness: two skills, known FSRS recall values.
    ///
    /// Creates a minimal in-memory collection with an "LSAT Skill" notetype,
    /// adds three skill notes across two skills, sets known FSRS memory states,
    /// and asserts the mastery aggregate is correct.
    ///
    /// Recall at elapsed = 0 s with any positive stability = 1.0 (mastered).
    /// Recall for an unreviewed card (no memory state) = 0.0 (not mastered).
    ///
    /// Index coverage: the query uses ix_cards_sched (did,queue,due),
    /// ix_cards_nid, idx_notes_mid, idx_notetypes_name — all existing indexes,
    /// no per-card SQL loops.  Single set-based SQL aggregate + Rust aggregation.
    #[test]
    fn test_skill_mastery_aggregate() -> Result<()> {
        let mut col = Collection::new();

        // Rename the built-in "Basic" notetype to "LSAT Skill" so the query
        // can find it by name.  `get_notetype_by_name` returns Arc<Notetype>,
        // so we must clone to get a mutable owned value.
        let nt_arc = col.get_notetype_by_name("Basic")?.unwrap();
        let mut nt_owned = (*nt_arc).clone();
        nt_owned.name = "LSAT Skill".into();
        col.update_notetype(&mut nt_owned, false)?;
        let nt = col.get_notetype_by_name("LSAT Skill")?.unwrap();

        // ── Add three skill notes across two skills ───────────────────────────
        // Skill A: type::assumption  (1 card, will be mastered)
        let mut note_a = nt.new_note();
        note_a.tags = vec!["type::assumption".to_owned()];
        col.add_note(&mut note_a, DeckId(1))?;

        // Skill B: type::flaw  (2 cards — one mastered, one unreviewed)
        let mut note_b1 = nt.new_note();
        note_b1.tags = vec!["type::flaw".to_owned()];
        col.add_note(&mut note_b1, DeckId(1))?;

        let mut note_b2 = nt.new_note();
        note_b2.tags = vec!["type::flaw".to_owned()];
        col.add_note(&mut note_b2, DeckId(1))?;

        // ── Set FSRS memory states ────────────────────────────────────────────
        // last_review_time = now → elapsed = 0 s → recall = 1.0 → mastered.
        let now = TimestampSecs::now();
        let mastered_state = FsrsMemoryState {
            stability: 30.0,
            difficulty: 5.0,
        };

        let set_mastered = |col: &mut Collection, nid: NoteId| -> Result<()> {
            let cards = col.storage.all_cards_of_note(nid)?;
            for mut card in cards {
                card.memory_state = Some(mastered_state);
                card.last_review_time = Some(now);
                col.storage.update_card(&card)?;
            }
            Ok(())
        };

        set_mastered(&mut col, note_a.id)?;
        set_mastered(&mut col, note_b1.id)?;
        // note_b2: deliberately left as new card (no memory state → recall = 0.0)

        // ── Run skill_mastery on deck 1 ───────────────────────────────────────
        let resp = col
            .skill_mastery_impl(1)
            .expect("skill_mastery should succeed");

        assert_eq!(
            resp.skills.len(),
            2,
            "expected 2 skills, got {:?}",
            resp.skills
        );

        let skill_map: std::collections::HashMap<&str, &SkillMastery> = resp
            .skills
            .iter()
            .map(|s| (s.skill.as_str(), s))
            .collect();

        // type::assumption: 1 card, recall ≈ 1.0 → mastered = 1, total = 1
        let s_a = skill_map
            .get("type::assumption")
            .expect("type::assumption missing");
        assert_eq!(s_a.total, 1, "assumption total");
        assert_eq!(s_a.mastered, 1, "assumption mastered");
        assert!(
            s_a.avg_recall >= 0.99,
            "assumption avg_recall expected ≈1.0, got {}",
            s_a.avg_recall
        );

        // type::flaw: 2 cards — 1 mastered (recall≈1.0), 1 unreviewed (recall=0.0)
        let s_b = skill_map.get("type::flaw").expect("type::flaw missing");
        assert_eq!(s_b.total, 2, "flaw total");
        assert_eq!(s_b.mastered, 1, "flaw mastered (one unreviewed card)");
        // avg_recall ≈ (1.0 + 0.0) / 2 = 0.5
        assert!(
            s_b.avg_recall >= 0.45 && s_b.avg_recall <= 0.55,
            "flaw avg_recall expected ≈0.5, got {}",
            s_b.avg_recall
        );

        Ok(())
    }
}
