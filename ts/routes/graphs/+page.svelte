<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<!--
Speedrun WP-27: Speedrun design language for the Statistics page.
When ?sr=1 is present (set by aqt/stats.py when SPEEDRUN_SHELL=True), we
add the `speedrun-stats` body class which activates the Speedrun theme block
in graphs-base.scss.  Stock Anki (no ?sr param) is completely unchanged.
-->
<script lang="ts">
    import { onMount } from "svelte";

    import AddedGraph from "./AddedGraph.svelte";
    import ButtonsGraph from "./ButtonsGraph.svelte";
    import CalendarGraph from "./CalendarGraph.svelte";
    import CardCounts from "./CardCounts.svelte";
    import DifficultyGraph from "./DifficultyGraph.svelte";
    import EaseGraph from "./EaseGraph.svelte";
    import FutureDue from "./FutureDue.svelte";
    import GraphsPage from "./GraphsPage.svelte";
    import HourGraph from "./HourGraph.svelte";
    import IntervalsGraph from "./IntervalsGraph.svelte";
    import RangeBox from "./RangeBox.svelte";
    import RetrievabilityGraph from "./RetrievabilityGraph.svelte";
    import ReviewsGraph from "./ReviewsGraph.svelte";
    import StabilityGraph from "./StabilityGraph.svelte";
    import TodayStats from "./TodayStats.svelte";
    import TrueRetention from "./TrueRetention.svelte";

    const graphs = [
        TodayStats,
        FutureDue,
        CalendarGraph,
        ReviewsGraph,
        CardCounts,
        IntervalsGraph,
        StabilityGraph,
        EaseGraph,
        DifficultyGraph,
        RetrievabilityGraph,
        TrueRetention,
        HourGraph,
        ButtonsGraph,
        AddedGraph,
    ];

    // Speedrun WP-27: gate on URL param so stock Anki is unaffected
    let isSpeedrun = false;
    onMount(() => {
        isSpeedrun = new URLSearchParams(window.location.search).has("sr");
        if (isSpeedrun) {
            document.body.classList.add("speedrun-stats");
        }
        return () => {
            document.body.classList.remove("speedrun-stats");
        };
    });
</script>

{#if isSpeedrun}
    <header class="sr-stats-header">
        <span class="sr-stats-brand">Speedrun</span>
        <span class="sr-stats-title">Statistics</span>
    </header>
{/if}

<GraphsPage
    {graphs}
    initialSearch="deck:current"
    initialDays={365}
    controller={RangeBox}
/>

<style lang="scss">
    // Speedrun WP-27: branded header strip for the stats page.
    // Only rendered when isSpeedrun = true (SPEEDRUN_SHELL path).
    .sr-stats-header {
        display: flex;
        align-items: center;
        gap: 0.6em;
        padding: 0.7em 1.5em;
        background: #ffffff;
        border-bottom: 1px solid #dde2e9;
        font-family: -apple-system, "Inter", "Helvetica Neue", Arial, sans-serif;
    }

    .sr-stats-brand {
        font-size: 0.95em;
        font-weight: 700;
        color: #3e3a8c;
        letter-spacing: -0.01em;
    }

    .sr-stats-title {
        font-size: 0.88em;
        color: #6b7280;
        font-weight: 500;
    }
</style>
