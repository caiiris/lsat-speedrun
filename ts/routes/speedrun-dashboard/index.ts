// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Speedrun WP-14: three-score dashboard entry point.
//
// Called from the Qt desktop app via the mediasrv page mechanism.
// Usage: import { setupSpeedrunDashboard } from this module; call with a deck_id.

import "./speedrun-dashboard-base.scss";

import { speedrunDashboard } from "@generated/backend";
import type { SpeedrunDashboardResponse } from "@generated/anki/stats_pb";

import SpeedrunDashboard from "./SpeedrunDashboard.svelte";

/**
 * Mount the Speedrun three-score dashboard into `document.body`.
 *
 * @param deckId  The ID of the root Speedrun deck (all child decks are included).
 * @returns       The mounted Svelte component.
 */
export async function setupSpeedrunDashboard(deckId: number): Promise<SpeedrunDashboard> {
    const data: SpeedrunDashboardResponse = await speedrunDashboard({ deckId });

    return new SpeedrunDashboard({
        target: document.body,
        props: { data },
    });
}
