// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

use std::collections::HashMap;
use std::collections::HashSet;

use super::DueCard;
use super::NewCard;
use super::QueueBuilder;
use crate::deckconfig::NewCardGatherPriority;
use crate::deckconfig::ReviewCardOrder;
use crate::decks::limits::LimitKind;
use crate::prelude::*;
use crate::scheduler::queue::DueCardKind;
use crate::storage::card::NewCardSorting;

impl QueueBuilder {
    pub(super) fn gather_cards(&mut self, col: &mut Collection) -> Result<()> {
        self.gather_intraday_learning_cards(col)?;
        self.gather_due_cards(col, DueCardKind::Learning)?;
        self.gather_due_cards(col, DueCardKind::Review)?;
        // Speedrun WP-4: after gathering, reorder review cards for skill interleaving.
        if self.context.sort_options.review_order == ReviewCardOrder::InterleavedSkills {
            self.interleave_review_cards_by_question_type(col)?;
        }
        self.gather_new_cards(col)?;

        Ok(())
    }

    /// Round-robin interleave review cards so no two adjacent cards share the
    /// same LSAT question type (`type::*` tag on the card's note).
    ///
    /// Algorithm:
    /// 1. Look up note tags in a single batched query.
    /// 2. Extract the first `type::*` segment from each note's tags.
    /// 3. Group cards by question type (preserving within-group order).
    /// 4. Emit one card from each non-empty group in rotation until exhausted.
    ///
    /// Cards whose notes carry no `type::*` tag form a single "untyped" group
    /// and participate in the round-robin alongside typed groups.
    fn interleave_review_cards_by_question_type(
        &mut self,
        col: &mut Collection,
    ) -> Result<()> {
        if self.review.len() < 2 {
            return Ok(());
        }

        // Deduplicate note IDs before the batched tag fetch (search_nids has a
        // PRIMARY KEY constraint so duplicates would cause a SQL error).
        let unique_note_ids: Vec<NoteId> = {
            let mut seen = HashSet::new();
            self.review
                .iter()
                .filter(|c| seen.insert(c.note_id))
                .map(|c| c.note_id)
                .collect()
        };

        let note_tags_list = col.storage.get_note_tags_by_id_list(&unique_note_ids)?;

        // Build note_id → question-type string map.
        let type_map: HashMap<NoteId, String> = note_tags_list
            .into_iter()
            .map(|nt| (nt.id, extract_question_type(&nt.tags)))
            .collect();

        // Group DueCards by question type, preserving the within-group order
        // established by the SQL fetch (due date then random, the DB fallback).
        let mut group_keys: Vec<String> = Vec::new();
        let mut groups: Vec<Vec<DueCard>> = Vec::new();
        let mut key_to_group: HashMap<String, usize> = HashMap::new();

        for card in self.review.drain(..) {
            let qtype = type_map
                .get(&card.note_id)
                .cloned()
                .unwrap_or_default();
            let idx = if let Some(&i) = key_to_group.get(&qtype) {
                i
            } else {
                let i = groups.len();
                key_to_group.insert(qtype.clone(), i);
                group_keys.push(qtype);
                groups.push(Vec::new());
                i
            };
            groups[idx].push(card);
        }

        // Round-robin across groups: one card per group per pass, skipping
        // exhausted groups, until all cards are emitted.
        let total: usize = groups.iter().map(|g| g.len()).sum();
        let mut result = Vec::with_capacity(total);
        let mut positions = vec![0usize; groups.len()];

        loop {
            let mut progress = false;
            for (g, pos) in positions.iter_mut().enumerate() {
                if *pos < groups[g].len() {
                    result.push(groups[g][*pos]);
                    *pos += 1;
                    progress = true;
                }
            }
            if !progress {
                break;
            }
        }

        self.review = result;
        Ok(())
    }

    fn gather_intraday_learning_cards(&mut self, col: &mut Collection) -> Result<()> {
        col.storage.for_each_intraday_card_in_active_decks(
            self.context.timing.next_day_at,
            |card| {
                self.get_and_update_bury_mode_for_note(card.into());
                self.learning.push(card);
            },
        )?;

        Ok(())
    }

    fn gather_due_cards(&mut self, col: &mut Collection, kind: DueCardKind) -> Result<()> {
        if self.limits.root_limit_reached(LimitKind::Review) {
            return Ok(());
        }
        col.storage.for_each_due_card_in_active_decks(
            self.context.timing,
            self.context.sort_options.review_order,
            kind,
            self.context.fsrs,
            |card| {
                if self.limits.root_limit_reached(LimitKind::Review) {
                    return Ok(false);
                }
                if !self
                    .limits
                    .limit_reached(card.current_deck_id, LimitKind::Review)?
                    && self.add_due_card(card)
                {
                    self.limits.decrement_deck_and_parent_limits(
                        card.current_deck_id,
                        LimitKind::Review,
                    )?;
                }
                Ok(true)
            },
        )
    }

    fn gather_new_cards(&mut self, col: &mut Collection) -> Result<()> {
        let salt = Self::knuth_salt(self.context.timing.days_elapsed);
        match self.context.sort_options.new_gather_priority {
            NewCardGatherPriority::Deck => {
                self.gather_new_cards_by_deck(col, NewCardSorting::LowestPosition)
            }
            NewCardGatherPriority::DeckThenRandomNotes => {
                self.gather_new_cards_by_deck(col, NewCardSorting::RandomNotes(salt))
            }
            NewCardGatherPriority::LowestPosition => {
                self.gather_new_cards_sorted(col, NewCardSorting::LowestPosition)
            }
            NewCardGatherPriority::HighestPosition => {
                self.gather_new_cards_sorted(col, NewCardSorting::HighestPosition)
            }
            NewCardGatherPriority::RandomNotes => {
                self.gather_new_cards_sorted(col, NewCardSorting::RandomNotes(salt))
            }
            NewCardGatherPriority::RandomCards => {
                self.gather_new_cards_sorted(col, NewCardSorting::RandomCards(salt))
            }
        }
    }

    fn gather_new_cards_by_deck(
        &mut self,
        col: &mut Collection,
        sort: NewCardSorting,
    ) -> Result<()> {
        for deck_id in col.storage.get_active_deck_ids_sorted()? {
            if self.limits.root_limit_reached(LimitKind::New) {
                break;
            }
            if self.limits.limit_reached(deck_id, LimitKind::New)? {
                continue;
            }
            col.storage
                .for_each_new_card_in_deck(deck_id, sort, |card| {
                    let limit_reached = self.limits.limit_reached(deck_id, LimitKind::New)?;
                    if !limit_reached && self.add_new_card(card) {
                        self.limits
                            .decrement_deck_and_parent_limits(deck_id, LimitKind::New)?;
                    }
                    Ok(!limit_reached)
                })?;
        }

        Ok(())
    }

    fn gather_new_cards_sorted(
        &mut self,
        col: &mut Collection,
        order: NewCardSorting,
    ) -> Result<()> {
        col.storage
            .for_each_new_card_in_active_decks(order, |card| {
                if self.limits.root_limit_reached(LimitKind::New) {
                    return Ok(false);
                }
                if !self
                    .limits
                    .limit_reached(card.current_deck_id, LimitKind::New)?
                    && self.add_new_card(card)
                {
                    self.limits
                        .decrement_deck_and_parent_limits(card.current_deck_id, LimitKind::New)?;
                }
                Ok(true)
            })
    }

    /// True if limit should be decremented.
    fn add_due_card(&mut self, card: DueCard) -> bool {
        let bury_this_card = self
            .get_and_update_bury_mode_for_note(card.into())
            .map(|mode| match card.kind {
                DueCardKind::Review => mode.bury_reviews,
                DueCardKind::Learning => mode.bury_interday_learning,
            })
            .unwrap_or_default();
        if bury_this_card {
            false
        } else {
            match card.kind {
                DueCardKind::Review => self.review.push(card),
                DueCardKind::Learning => self.day_learning.push(card),
            }

            true
        }
    }

    // True if limit should be decremented.
    fn add_new_card(&mut self, card: NewCard) -> bool {
        let bury_this_card = self
            .get_and_update_bury_mode_for_note(card.into())
            .map(|mode| mode.bury_new)
            .unwrap_or_default();
        // no previous siblings seen?
        if bury_this_card {
            false
        } else {
            self.new.push(card);
            true
        }
    }

    // Generates a salt for use with fnvhash. Useful to increase randomness
    // when the base salt is a small integer.
    fn knuth_salt(base_salt: u32) -> u32 {
        base_salt.wrapping_mul(2654435761)
    }
}

/// Extract the question-type label from a note's tag string.
///
/// Tags are stored as a space-separated string (e.g. `" type::flaw skill::conditional "`).
/// Returns the portion after `"type::"` for the first matching tag, or an empty
/// string if no `type::*` tag is present (untyped cards share a single group).
pub(super) fn extract_question_type(tags: &str) -> String {
    tags.split_whitespace()
        .find_map(|t| t.strip_prefix("type::").map(str::to_string))
        .unwrap_or_default()
}
