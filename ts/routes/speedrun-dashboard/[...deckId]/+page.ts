// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Speedrun WP-14: dashboard page loader.

import type { PageLoad } from "./$types";
import { speedrunDashboard } from "@generated/backend";

export const load: PageLoad = async ({ params }) => {
    // deck_id is an int64 in the proto → the generated client expects a bigint.
    // Passing a plain number throws at request-build time and blanks the page.
    const parsed = parseInt(params.deckId ?? "1", 10);
    const deckId = BigInt(Number.isFinite(parsed) ? parsed : 1);
    const data = await speedrunDashboard({ deckId });
    return { data };
};
