<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import * as tr from "@generated/ftl";
    import type { Writable } from "svelte/store";

    import { daysToRevlogRange, RevlogRange } from "./graph-helpers";
    import InputBox from "./InputBox.svelte";

    enum SearchRange {
        Deck = 1,
        Collection = 2,
        Custom = 3,
    }

    export let loading: boolean;

    export let days: Writable<number>;
    export let search: Writable<string>;

    // Speedrun WP-27: when opened from the shell (?sr=1), the deck/collection
    // scope toggle is meaningless — Speedrun is effectively one study plan, and
    // "deck:current" can even scope to an empty "Default" deck (→ no data). So
    // we hide the toggle + search box and always show all of the user's study.
    const isSpeedrun =
        typeof window !== "undefined" &&
        new URLSearchParams(window.location.search).has("sr");

    let revlogRange = daysToRevlogRange($days);
    let searchRange: SearchRange;

    if ($search === "deck:current") {
        searchRange = SearchRange.Deck;
    } else if ($search === "") {
        searchRange = SearchRange.Collection;
    } else {
        searchRange = SearchRange.Custom;
    }

    if (isSpeedrun) {
        // Show everything the learner has studied, regardless of selected deck.
        searchRange = SearchRange.Collection;
    }

    let displayedSearch = $search;

    $: {
        switch (searchRange) {
            case SearchRange.Deck:
                $search = displayedSearch = "deck:current";
                break;
            case SearchRange.Collection:
                $search = displayedSearch = "";
                break;
        }
    }

    $: {
        switch (revlogRange) {
            case RevlogRange.Year:
                $days = 365;
                break;
            case RevlogRange.All:
                $days = 0;
                break;
        }
    }

    function updateSearch(): void {
        $search = displayedSearch;
    }

    const year = tr.statisticsRange1YearHistory();
    const searchLabel = tr.statisticsRangeSearch();
    const all = tr.statisticsRangeAllHistory();
    const deck = tr.statisticsRangeDeck();
    const collection = tr.statisticsRangeCollection();
</script>

<div class="range-box">
    <div class="spin" class:loading>◐</div>

    <!-- Speedrun hides the deck/collection scope toggle + search box (jargon,
         and meaningless for a single study plan); stock Anki keeps them. -->
    {#if !isSpeedrun}
        <InputBox>
            <label>
                <input type="radio" bind:group={searchRange} value={SearchRange.Deck} />
                {deck}
            </label>
            <label>
                <input
                    type="radio"
                    bind:group={searchRange}
                    value={SearchRange.Collection}
                />
                {collection}
            </label>

            <!-- This form is an external API and care should be taken when changed -
	other clients e.g. AnkiDroid programmatically update this form by id -->
            <input
                type="text"
                id="statisticsSearchText"
                bind:value={displayedSearch}
                on:change={updateSearch}
                on:focus={() => {
                    searchRange = SearchRange.Custom;
                }}
                placeholder={searchLabel}
            />
        </InputBox>
    {/if}

    <InputBox>
        <label>
            <input type="radio" bind:group={revlogRange} value={RevlogRange.Year} />
            {year}
        </label>
        <label>
            <input type="radio" bind:group={revlogRange} value={RevlogRange.All} />
            {all}
        </label>
    </InputBox>
</div>

<div class="range-box-pad"></div>

<style lang="scss">
    label {
        display: inline-flex;
        align-items: center;
    }

    input[type="radio"] {
        margin-inline-end: 0.3em;
    }

    .range-box {
        position: sticky;
        z-index: 1;
        top: 0;
        width: 100vw;
        color: var(--fg);
        background: var(--canvas);
        padding: 0.5em;
        border-bottom: 1px solid var(--border);

        @media print {
            position: absolute;
        }
    }

    @keyframes spin {
        0% {
            -webkit-transform: rotate(0deg);
        }
        100% {
            -webkit-transform: rotate(360deg);
        }
    }

    .spin {
        display: inline-block;
        position: absolute;
        font-size: 2em;
        animation: spin;
        animation-duration: 1s;
        animation-iteration-count: infinite;
        z-index: -1;

        opacity: 0;

        &.loading {
            opacity: 0.5;
            z-index: 1;
            transition: opacity var(--transition-slow);
        }
    }

    .range-box-pad {
        height: 1.5em;
    }
</style>
