// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! Speedrun WP-5 storage helper: fetch skill-card rows for the mastery aggregate.
//!
//! One indexed SQL query over `cards JOIN notes JOIN notetypes`, filtered to the
//! LSAT Skill notetype and the requested deck hierarchy.  Aggregation and FSRS
//! recall computation are done in Rust (see `rslib/src/stats/service.rs`).

use crate::decks::DeckId;
use crate::error::Result;
use crate::storage::ids_to_string;

/// Minimal projection returned by [`SqliteStorage::skill_cards_in_decks`].
///
/// Only the fields needed to compute FSRS recall and identify the skill are
/// fetched — no full card deserialisation.
pub(crate) struct SkillCardRow {
    /// Space-delimited note tag string (may include leading/trailing space).
    pub note_tags: String,
    /// Card `data` JSON blob (contains `s`, `d`, `lrt`, `decay`, …).
    pub card_data_json: String,
    /// Card due value (semantics depend on card type/queue).
    pub due: i32,
    /// Card interval in days (used to infer last-review date when `lrt` absent).
    pub ivl: i32,
}

impl super::super::SqliteStorage {
    /// Return one [`SkillCardRow`] per LSAT Skill card whose `did` is in
    /// `deck_ids` (the target deck + all child decks).
    ///
    /// Uses the existing indexes:
    /// - `ix_cards_sched (did, queue, due)` — deck filter
    /// - `ix_cards_nid`                    — cards→notes join
    /// - `idx_notes_mid`                   — notes→notetypes join
    /// - `idx_notetypes_name` (unique)     — notetype-name lookup
    ///
    /// This is the single SQL round-trip mandated by D-SR5 / spec-engine §5.4.
    /// FSRS aggregation is done in Rust from these rows.
    pub(crate) fn skill_cards_in_decks(
        &self,
        deck_ids: &[DeckId],
    ) -> Result<Vec<SkillCardRow>> {
        if deck_ids.is_empty() {
            return Ok(vec![]);
        }

        let mut sql = String::from(
            "SELECT n.tags, c.data, c.due, c.ivl \
             FROM cards c \
             JOIN notes n ON c.nid = n.id \
             WHERE c.did IN ",
        );
        ids_to_string(&mut sql, deck_ids.iter().map(|d| d.0));
        sql.push_str(
            " AND n.mid = (SELECT id FROM notetypes WHERE name = 'LSAT Skill') \
             ORDER BY c.id",
        );

        self.db
            .prepare_cached(&sql)?
            .query_and_then([], |row| {
                Ok(SkillCardRow {
                    note_tags: row.get(0)?,
                    card_data_json: row.get(1)?,
                    due: row.get(2)?,
                    ivl: row.get(3)?,
                })
            })?
            .collect()
    }
}
