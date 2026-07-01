<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

Speedrun WP-14: three-score dashboard page.
Route: /speedrun-dashboard/<deck_id>
-->
<script lang="ts">
    import type { PageData } from "./$types";
    import SpeedrunDashboard from "../SpeedrunDashboard.svelte";

    export let data: PageData;
</script>

<SpeedrunDashboard data={data.data} />
