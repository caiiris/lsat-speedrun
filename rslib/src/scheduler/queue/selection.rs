// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! Speedrun WP-3: Fresh-item selection for `draw_item_for_skill`.
//!
//! Spec: spec-engine §5.2 + §7
//! Decisions: D-SR4 (zero schema change; sidecar outside collection),
//!            D-SR23 (distractor traps are first-class pools),
//!            D-SR24 (native `::` tag hierarchy; double-quoted deck filter).

use std::collections::HashMap;
use std::collections::HashSet;
use std::collections::VecDeque;
use std::sync::LazyLock;
use std::sync::Mutex;

use rand::Rng;

use crate::prelude::*;

// ---------------------------------------------------------------------------
// Served-item sidecar  (D-SR4 / spec-engine §7)
//
// LOCAL · NON-SYNCED · NON-UNDOABLE · OUTSIDE the collection.
// Stored as in-process memory, keyed by (collection_path → skill_tag → log).
//
// "Best-effort": if a review is undone, an item may become re-eligible to
// draw.  This is explicitly allowed per D-SR4 and spec-engine §7 —
// no corruption, no score loss.
// ---------------------------------------------------------------------------

/// Safety cap: regardless of pool size, we never track more than this many
/// recent servings.  Keeps memory bounded for very large pools.
pub(crate) const MAX_SIDECAR_WINDOW: usize = 50;

/// Per-skill log of recently-served item note ids.
/// Oldest entry is at the front; newest is at the back.
#[derive(Debug, Default)]
pub(crate) struct SkillServedLog {
    pub(crate) entries: VecDeque<NoteId>,
}

impl SkillServedLog {
    /// Push a new entry, trimming oldest entries to stay within `cap`.
    pub(crate) fn push(&mut self, note_id: NoteId, cap: usize) {
        self.entries.push_back(note_id);
        while self.entries.len() > cap.max(1) {
            self.entries.pop_front();
        }
    }

    /// Return the `n` most-recently-served ids as a set (newest first).
    pub(crate) fn recent_set(&self, n: usize) -> HashSet<NoteId> {
        self.entries.iter().rev().take(n).copied().collect()
    }

    /// From `pool`, return the id that was served least recently (or never).
    /// "Never served" counts as the oldest.  Ties are broken by pool order.
    pub(crate) fn least_recently_served(&self, pool: &[NoteId]) -> NoteId {
        pool.iter()
            .copied()
            .min_by_key(|nid| {
                // rposition gives the LAST (most-recent) index in entries.
                // Items not present score 0 (treated as "served first" = oldest).
                self.entries
                    .iter()
                    .rposition(|s| s == nid)
                    .map(|p| p as i64 + 1)
                    .unwrap_or(0_i64)
            })
            .unwrap_or(pool[0])
    }
}

/// Process-level sidecar: collection_path → (skill_tag → log).
static SERVED_SIDECAR: LazyLock<Mutex<HashMap<String, HashMap<String, SkillServedLog>>>> =
    LazyLock::new(|| Mutex::new(HashMap::new()));

// ---------------------------------------------------------------------------
// Sidecar helpers (package-private)
// ---------------------------------------------------------------------------

pub(crate) fn sidecar_recent_set(col_key: &str, skill_tag: &str, window: usize) -> HashSet<NoteId> {
    let guard = SERVED_SIDECAR.lock().unwrap();
    guard
        .get(col_key)
        .and_then(|m| m.get(skill_tag))
        .map(|log| log.recent_set(window))
        .unwrap_or_default()
}

pub(crate) fn sidecar_least_recently_served(
    col_key: &str,
    skill_tag: &str,
    pool: &[NoteId],
) -> NoteId {
    let guard = SERVED_SIDECAR.lock().unwrap();
    guard
        .get(col_key)
        .and_then(|m| m.get(skill_tag))
        .map(|log| log.least_recently_served(pool))
        .unwrap_or(pool[0])
}

pub(crate) fn sidecar_record(col_key: &str, skill_tag: &str, note_id: NoteId, cap: usize) {
    let mut guard = SERVED_SIDECAR.lock().unwrap();
    guard
        .entry(col_key.to_string())
        .or_default()
        .entry(skill_tag.to_string())
        .or_default()
        .push(note_id, cap);
}

/// Clear all sidecar state for a given collection path.
/// Exposed for tests to ensure isolation between test cases.
#[cfg(test)]
pub(crate) fn clear_sidecar_for_col(col_key: &str) {
    let mut guard = SERVED_SIDECAR.lock().unwrap();
    guard.remove(col_key);
}

// ---------------------------------------------------------------------------
// Selection algorithm  (spec-engine §5.2)
// ---------------------------------------------------------------------------

impl Collection {
    /// Speedrun WP-3: select a fresh item note for a due skill card.
    ///
    /// Algorithm (spec-engine §5.2):
    /// 1. Resolve `skill_card_id` → identity tag (first `type::`, `skill::`, or
    ///    `trap::` tag on the skill note).
    /// 2. Search `deck:"LSAT Speedrun::Items" tag:<skill_tag>` for item notes.
    ///    Double-quoted deck filter is required — single quotes return 0
    ///    results (B021 / D-SR24).
    /// 3. Exclude items in the served-item sidecar within window W =
    ///    min(pool_size − 1, MAX_SIDECAR_WINDOW).
    /// 4. If fresh candidates exist, pick one uniformly at random (difficulty
    ///    heuristic deferred — see WP-3-log.md §L3). If ALL items were served
    ///    within W (fallback), pick least-recently-served.
    /// 5. Record the chosen item in the sidecar and return its `NoteId`.
    pub(crate) fn draw_item_for_skill_impl(&mut self, skill_card_id: CardId) -> Result<NoteId> {
        // --- Step 1: Resolve skill identity tag ---
        let card = self
            .storage
            .get_card(skill_card_id)?
            .or_invalid("skill card not found")?;
        let note = self
            .storage
            .get_note(card.note_id)?
            .or_invalid("skill note not found")?;

        // build_seed_deck.py stores the identity tag as the sole tag on a
        // skill note: `note.tags = [nd["IdentityTag"]]`.
        // Accept the first tag starting with "type::", "skill::", or "trap::".
        let skill_tag = note
            .tags
            .iter()
            .find(|t| {
                t.starts_with("type::") || t.starts_with("skill::") || t.starts_with("trap::")
            })
            .or_invalid(
                "skill note has no identity tag (expected type::, skill::, or trap:: prefix)",
            )?
            .clone();

        // --- Step 2: Search item pool ---
        // Double-quoted deck name is REQUIRED (single quotes return 0 results;
        // this was bug B021 discovered during WP-1).
        // Pass &search: TryIntoSearch is implemented for &String, not String.
        let search = format!("tag:{skill_tag} deck:\"LSAT Speedrun::Items\"");
        let pool: Vec<NoteId> = self.search_notes_unordered(&search)?;

        if pool.is_empty() {
            invalid_input!(
                "no item notes found for skill {} in deck \"LSAT Speedrun::Items\"",
                skill_tag
            );
        }

        let pool_size = pool.len();
        // W = min(pool_size − 1, MAX_SIDECAR_WINDOW) per §5.2.
        // pool_size=1 → window=0 (single-item pool, serve it every time).
        let window = pool_size.saturating_sub(1).min(MAX_SIDECAR_WINDOW);

        // --- Step 3: Exclude recently-served items ---
        let col_key = self.col_path.to_string_lossy().into_owned();
        let recent: HashSet<NoteId> = sidecar_recent_set(&col_key, &skill_tag, window);

        let candidates: Vec<NoteId> = pool
            .iter()
            .copied()
            .filter(|nid| !recent.contains(nid))
            .collect();

        // --- Step 4: Choose ---
        // Difficulty-appropriate ordering is deferred (spec-engine §5.2 warm-start
        // difficulty model not yet built).  Use uniform random among candidates.
        // See WP-3-log.md L3 for the rationale.
        let chosen = if candidates.is_empty() {
            // Fallback: all items were served within the window (defensive path;
            // triggered when sidecar state is stale or pool shrunk since last
            // recording).
            sidecar_least_recently_served(&col_key, &skill_tag, &pool)
        } else {
            let idx = rand::rng().random_range(0..candidates.len());
            candidates[idx]
        };

        // --- Step 5: Record and return ---
        // cap = window but at least 1, at most MAX_SIDECAR_WINDOW.
        let cap = window.clamp(1, MAX_SIDECAR_WINDOW);
        sidecar_record(&col_key, &skill_tag, chosen, cap);

        Ok(chosen)
    }
}

// ---------------------------------------------------------------------------
// Unit tests  (spec-engine §11 AC 3)
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::tests::open_fs_test_collection;
    use crate::tests::DeckAdder;

    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------

    /// Add a note with the Basic notetype to `deck_id`, tagged with `tag`.
    /// Returns `(card_id, note_id)`.
    fn add_tagged_note(col: &mut Collection, deck_id: DeckId, tag: &str) -> (CardId, NoteId) {
        let nt_id = col
            .storage
            .get_notetype_id("Basic")
            .unwrap()
            .expect("Basic notetype must exist");
        let nt = col
            .storage
            .get_notetype(nt_id)
            .unwrap()
            .expect("Basic notetype must be loadable");
        let mut note = nt.new_note();
        note.tags = vec![tag.to_string()];
        col.add_note(&mut note, deck_id).unwrap();
        let cids = col.storage.card_ids_of_notes(&[note.id]).unwrap();
        (cids[0], note.id)
    }

    // -----------------------------------------------------------------------
    // SkillServedLog unit tests (covers sidecar logic + fallback path)
    // -----------------------------------------------------------------------

    #[test]
    fn served_log_recent_set_returns_newest_first() {
        let mut log = SkillServedLog::default();
        let n1 = NoteId(1);
        let n2 = NoteId(2);
        let n3 = NoteId(3);
        log.push(n1, 10);
        log.push(n2, 10);
        log.push(n3, 10);

        let recent = log.recent_set(2);
        assert!(recent.contains(&n3), "n3 (newest) must be in recent(2)");
        assert!(recent.contains(&n2), "n2 must be in recent(2)");
        assert!(
            !recent.contains(&n1),
            "n1 (oldest) must NOT be in recent(2)"
        );
    }

    #[test]
    fn served_log_least_recently_served_returns_never_served_item() {
        let mut log = SkillServedLog::default();
        let n1 = NoteId(1);
        let n2 = NoteId(2);
        let n3 = NoteId(3); // never served
        log.push(n1, 10);
        log.push(n2, 10);

        // n3 was never served → scored 0 → least recently served
        let pool = vec![n1, n2, n3];
        let lrs = log.least_recently_served(&pool);
        assert_eq!(lrs, n3, "never-served item should be treated as oldest");
    }

    #[test]
    fn served_log_least_recently_served_returns_oldest_among_all_served() {
        let mut log = SkillServedLog::default();
        let n1 = NoteId(10);
        let n2 = NoteId(20);
        // n1 first, n2 second → n1 is least recently served
        log.push(n1, 10);
        log.push(n2, 10);

        let pool = vec![n1, n2];
        let lrs = log.least_recently_served(&pool);
        assert_eq!(
            lrs, n1,
            "n1 was served first and should be least-recently-served"
        );
    }

    // -----------------------------------------------------------------------
    // draw_item_for_skill_impl: fresh item returned when candidates exist
    // -----------------------------------------------------------------------

    #[test]
    fn draw_returns_item_not_in_recent_window() {
        let (mut col, _tmpdir) = open_fs_test_collection("draw_fresh");
        let skill_deck = DeckAdder::new("LSAT Speedrun::Skills").add(&mut col).id;
        let items_deck = DeckAdder::new("LSAT Speedrun::Items").add(&mut col).id;

        let (skill_cid, _) = add_tagged_note(&mut col, skill_deck, "type::flaw");

        // 3 item notes tagged type::flaw
        let (_, item1) = add_tagged_note(&mut col, items_deck, "type::flaw");
        let (_, item2) = add_tagged_note(&mut col, items_deck, "type::flaw");
        let (_, item3) = add_tagged_note(&mut col, items_deck, "type::flaw");

        let col_key = col.col_path.to_string_lossy().into_owned();
        clear_sidecar_for_col(&col_key);

        // Manually mark item1 and item2 as the 2 most-recently served.
        // With pool_size=3, window = min(2, MAX) = 2.
        // After pre-seeding, recent(2) = {item1, item2}.
        // Candidate = {item3}.
        sidecar_record(&col_key, "type::flaw", item1, 2);
        sidecar_record(&col_key, "type::flaw", item2, 2);

        let drawn = col
            .draw_item_for_skill_impl(skill_cid)
            .expect("draw should succeed");

        assert_eq!(drawn, item3, "only item3 is fresh; draw must return it");
    }

    // -----------------------------------------------------------------------
    // draw_item_for_skill_impl: fallback via sidecar_least_recently_served
    // -----------------------------------------------------------------------

    #[test]
    fn sidecar_fallback_least_recently_served() {
        // This test validates the fallback branch directly via the sidecar
        // helper.  The fallback is a defensive code path that triggers when
        // the sidecar has entries for ALL pool items (e.g. after a pool shrink
        // or stale sidecar initialization).
        let col_key = "test_fallback_col";
        let skill_tag = "trap::sufficient-necessary";

        let n1 = NoteId(100);
        let n2 = NoteId(200);
        let pool = vec![n1, n2];

        // Pre-fill sidecar: n1 served first, n2 served second.
        sidecar_record(col_key, skill_tag, n1, 10);
        sidecar_record(col_key, skill_tag, n2, 10);

        // When all pool items are in the window, least-recently-served = n1.
        let lrs = sidecar_least_recently_served(col_key, skill_tag, &pool);
        assert_eq!(lrs, n1, "least-recently-served should be n1 (served first)");

        // Cleanup after test to avoid polluting other tests' state.
        {
            let mut guard = SERVED_SIDECAR.lock().unwrap();
            guard.remove(col_key);
        }
    }

    // -----------------------------------------------------------------------
    // draw_item_for_skill_impl: error when no identity tag
    // -----------------------------------------------------------------------

    #[test]
    fn draw_errors_when_skill_note_has_no_identity_tag() {
        let (mut col, _tmpdir) = open_fs_test_collection("draw_no_tag");
        let deck = DeckAdder::new("LSAT Speedrun::Skills").add(&mut col).id;
        // Tag "unrelated" has no type::, skill::, or trap:: prefix.
        let (skill_cid, _) = add_tagged_note(&mut col, deck, "unrelated");

        let result = col.draw_item_for_skill_impl(skill_cid);
        assert!(
            result.is_err(),
            "should error when skill note has no identity tag"
        );
    }

    // -----------------------------------------------------------------------
    // draw_item_for_skill_impl: error when pool is empty
    // -----------------------------------------------------------------------

    #[test]
    fn draw_errors_when_item_pool_is_empty() {
        let (mut col, _tmpdir) = open_fs_test_collection("draw_empty_pool");
        let skill_deck = DeckAdder::new("LSAT Speedrun::Skills").add(&mut col).id;
        // Create the items deck but add NO item notes.
        let _items_deck = DeckAdder::new("LSAT Speedrun::Items").add(&mut col).id;
        let (skill_cid, _) = add_tagged_note(&mut col, skill_deck, "type::flaw");

        let result = col.draw_item_for_skill_impl(skill_cid);
        assert!(
            result.is_err(),
            "should error when no items exist for the skill"
        );
    }

    // -----------------------------------------------------------------------
    // Repeated draws cycle through pool without consecutive repeats
    // -----------------------------------------------------------------------

    #[test]
    fn draw_cycles_through_pool_without_immediate_repeat() {
        let (mut col, _tmpdir) = open_fs_test_collection("draw_cycle");
        let skill_deck = DeckAdder::new("LSAT Speedrun::Skills").add(&mut col).id;
        let items_deck = DeckAdder::new("LSAT Speedrun::Items").add(&mut col).id;

        let (skill_cid, _) = add_tagged_note(&mut col, skill_deck, "skill::conditional");

        // 4-item pool → window = min(3, MAX) = 3
        let mut items = Vec::new();
        for _ in 0..4 {
            let (_, nid) = add_tagged_note(&mut col, items_deck, "skill::conditional");
            items.push(nid);
        }

        let col_key = col.col_path.to_string_lossy().into_owned();
        clear_sidecar_for_col(&col_key);

        // Draw 4 times; each successive draw must not repeat the immediately-
        // preceding item (because window ≥ 1 excludes the last served item).
        let mut last: Option<NoteId> = None;
        for i in 0..4 {
            let drawn = col
                .draw_item_for_skill_impl(skill_cid)
                .unwrap_or_else(|e| panic!("draw {} failed: {e}", i + 1));
            if let Some(prev) = last {
                assert_ne!(
                    drawn,
                    prev,
                    "draw {} repeated the immediately-prior item",
                    i + 1
                );
            }
            last = Some(drawn);
        }
    }
}
