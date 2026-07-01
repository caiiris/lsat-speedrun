// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// Speedrun WP-14: dashboard page loader.

import type { PageLoad } from "./$types";
import { speedrunDashboard } from "@generated/backend";

export const load: PageLoad = async ({ params }) => {
    const deckId = parseInt(params.deckId ?? "1", 10);
    const data = await speedrunDashboard({ deckId });
    return { data };
};
