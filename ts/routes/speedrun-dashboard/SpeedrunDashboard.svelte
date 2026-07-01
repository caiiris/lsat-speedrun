<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

Speedrun WP-20 — Home study-plan surface.

Reshapes the WP-14 three-score dashboard into the anti-deck-list Home screen
(spec-ui §3.1, D-SR33). Design language: spec-ui §2 (cool pale paper · slate
ink · indigo accent · amber signature).

Honesty invariants (D-SR10, spec-measurement §6):
- Readiness card shows NO point estimate when eligible = false.
- Abstain panel shows evidence counts + what is missing.
- "LR-only estimate" label at all times on the Readiness card (D-SR19).
- Bands displayed alongside every score.
-->
<script lang="ts">
    import type {
        SpeedrunDashboardResponse,
        SpeedrunSkillPerf,
    } from "@generated/anki/stats_pb";

    export let data: SpeedrunDashboardResponse;

    // ── Design tokens (spec-ui §2) ────────────────────────────────────────────
    // Palette + typography defined in the scss block below.

    // ── Helpers ───────────────────────────────────────────────────────────────

    const MIN_ATTEMPTS = 5;

    function pct(v: number): string {
        return `${Math.round(v * 100)}%`;
    }

    function pctHalf(v: number): string {
        return `${(v * 100).toFixed(1)}%`;
    }

    /** Half-width of a confidence interval in percentage points, rounded. */
    function halfBand(lo: number, hi: number): number {
        return Math.round(((hi - lo) / 2) * 100);
    }

    /** Rough band for overall performance using totalAttempts + overallPerf. */
    function overallBand(): number {
        const n = data.totalAttempts;
        const p = data.overallPerf;
        if (n < 5) return 0;
        // Wald approximation for speed; Wilson is done per-skill on the Rust side.
        const hw = 1.96 * Math.sqrt((p * (1 - p)) / n);
        return Math.round(hw * 100);
    }

    /** Wilson CI half-width for a skill in percentage points. */
    function skillBand(skill: SpeedrunSkillPerf): number {
        if (skill.attempts < MIN_ATTEMPTS) return 0;
        return halfBand(skill.wilsonLow, skill.wilsonHigh);
    }

    function skillPct(skill: SpeedrunSkillPerf): number {
        if (skill.attempts < MIN_ATTEMPTS) return 0;
        return Math.round((skill.correct / skill.attempts) * 100);
    }

    function shortName(tag: string): string {
        return tag.replace(/^type::/, "");
    }

    /** Display name for a skill tag — strips prefix and title-cases. */
    function displayName(tag: string): string {
        const s = shortName(tag);
        return s.charAt(0).toUpperCase() + s.slice(1);
    }

    // ── Today's focus ─────────────────────────────────────────────────────────

    /** The recommended next focus skill (nextBest from abstain or readiness). */
    $: focusSkill =
        data.abstain?.nextBest ?? data.readiness?.nextBest ?? null;

    $: focusSkillPerf = focusSkill
        ? data.skillPerf.find((s) => s.skill === focusSkill)
        : null;

    // ── Skill map ─────────────────────────────────────────────────────────────

    // Sort: recommended first, then by performance ascending (weakest first),
    // then by attempts descending (most data first).
    $: sortedSkills = [...data.skillPerf].sort((a, b) => {
        const aIsRec = a.skill === focusSkill ? -1 : 0;
        const bIsRec = b.skill === focusSkill ? -1 : 0;
        if (aIsRec !== bIsRec) return aIsRec - bIsRec;
        if (a.attempts < MIN_ATTEMPTS && b.attempts >= MIN_ATTEMPTS) return 1;
        if (a.attempts >= MIN_ATTEMPTS && b.attempts < MIN_ATTEMPTS) return -1;
        const perfDiff = skillPct(a) - skillPct(b);
        if (perfDiff !== 0) return perfDiff;
        return b.attempts - a.attempts;
    });

    // ── Anki action bridge (WP-25) ────────────────────────────────────────────
    // Each function calls pycmd('speedrun:anki:<action>'), handled in
    // SpeedrunHomeDialog._on_bridge_cmd, which routes to the matching mw.*
    // method (opens the Anki dialog on top of Home; closing returns to Home).

    function ankiAction(action: string) {
        if (typeof window !== "undefined" && (window as any).pycmd) {
            (window as any).pycmd(`speedrun:anki:${action}`);
        } else {
            console.info("[WP-25] anki action:", action);
        }
    }

    // More menu open/close state
    let moreOpen = false;

    function toggleMore() {
        moreOpen = !moreOpen;
    }

    function closeMore() {
        moreOpen = false;
    }

    function moreAction(action: string) {
        moreOpen = false;
        ankiAction(action);
    }

    // ── Session launcher bridge (WP-22 SEAM) ─────────────────────────────────
    // WP-22 will wire these to real session flows. For now, the Start drill
    // button emits a pycmd bridge command that the Qt host can handle.
    // The handler in qt/aqt/speedrun_home.py opens the deck study path as
    // the best available entry until WP-22 ships.
    //
    // TODO(WP-22): replace with SvelteKit session route navigation once the
    //   session layer (ts/routes/speedrun-session/) exists.

    function startTargetedDrill() {
        const skill = focusSkill ?? "";
        if (typeof window !== "undefined" && (window as any).pycmd) {
            // Bridge to Qt host — handled in SpeedrunHomeDialog._on_bridge_cmd
            (window as any).pycmd(`speedrun:home:start-drill:${skill}`);
        } else {
            // Dev/HMR fallback
            console.info("[WP-22 SEAM] start-drill:", skill);
        }
    }

    function launchSession(type: "mixed" | "timed" | "blind") {
        // TODO(WP-22): navigate to ts/routes/speedrun-session/?type=...
        if (typeof window !== "undefined" && (window as any).pycmd) {
            (window as any).pycmd(`speedrun:home:session:${type}`);
        } else {
            console.info("[WP-22 SEAM] session:", type);
        }
    }

    // ── Readiness helpers ─────────────────────────────────────────────────────

    function confidenceLabel(c: string): string {
        return (
            { low: "Low", medium: "Medium", high: "High" }[c] ?? c
        );
    }
</script>

<div class="sr-home">
    <!-- ── Top header ────────────────────────────────────────────────────── -->
    <header class="sr-home-header">
        <span class="sr-brand">Speedrun</span>

        <!-- ── Anki action controls (WP-25) ─────────────────────────────── -->
        <nav class="sr-anki-actions" aria-label="Anki tools">
            <button
                class="sr-action-btn"
                on:click={() => ankiAction("sync")}
                title="Sync with AnkiWeb"
                aria-label="Sync"
            >
                <svg class="sr-action-icon" viewBox="0 0 20 20" aria-hidden="true">
                    <path d="M4 10a6 6 0 0 1 10.9-3.4"/>
                    <polyline points="13,3 15.9,6.6 12.3,7.5"/>
                    <path d="M16 10a6 6 0 0 1-10.9 3.4"/>
                    <polyline points="7,17 4.1,13.4 7.7,12.5"/>
                </svg>
                <span class="sr-action-label">Sync</span>
            </button>

            <button
                class="sr-action-btn"
                on:click={() => ankiAction("browse")}
                title="Browse cards"
                aria-label="Browse"
            >
                <svg class="sr-action-icon" viewBox="0 0 20 20" aria-hidden="true">
                    <rect x="3" y="4" width="14" height="12" rx="1.5"/>
                    <line x1="3" y1="8" x2="17" y2="8"/>
                    <line x1="7" y1="4" x2="7" y2="16"/>
                </svg>
                <span class="sr-action-label">Browse</span>
            </button>

            <button
                class="sr-action-btn"
                on:click={() => ankiAction("add")}
                title="Add a new card"
                aria-label="Add"
            >
                <svg class="sr-action-icon" viewBox="0 0 20 20" aria-hidden="true">
                    <rect x="3" y="4" width="14" height="12" rx="1.5"/>
                    <line x1="10" y1="8" x2="10" y2="14"/>
                    <line x1="7" y1="11" x2="13" y2="11"/>
                </svg>
                <span class="sr-action-label">Add</span>
            </button>

            <button
                class="sr-action-btn"
                on:click={() => ankiAction("stats")}
                title="View statistics"
                aria-label="Stats"
            >
                <svg class="sr-action-icon" viewBox="0 0 20 20" aria-hidden="true">
                    <rect x="3" y="11" width="3" height="5" rx="1"/>
                    <rect x="8.5" y="7" width="3" height="9" rx="1"/>
                    <rect x="14" y="4" width="3" height="12" rx="1"/>
                </svg>
                <span class="sr-action-label">Stats</span>
            </button>

            <!-- More menu -->
            <div class="sr-more-wrap">
                <button
                    class="sr-action-btn sr-action-btn--more"
                    on:click={toggleMore}
                    aria-haspopup="true"
                    aria-expanded={moreOpen}
                    title="More Anki tools"
                    aria-label="More"
                >
                    <svg class="sr-action-icon" viewBox="0 0 20 20" aria-hidden="true">
                        <circle cx="5" cy="10" r="1.5"/>
                        <circle cx="10" cy="10" r="1.5"/>
                        <circle cx="15" cy="10" r="1.5"/>
                    </svg>
                    <span class="sr-action-label">More</span>
                </button>

                {#if moreOpen}
                    <!-- svelte-ignore a11y-click-events-have-key-events -->
                    <!-- svelte-ignore a11y-no-static-element-interactions -->
                    <div class="sr-more-backdrop" on:click={closeMore}></div>
                    <ul class="sr-more-menu" role="menu">
                        <li role="none">
                            <button role="menuitem" on:click={() => moreAction("import")}>
                                <svg viewBox="0 0 20 20" aria-hidden="true">
                                    <polyline points="10,3 10,13"/>
                                    <polyline points="6,9 10,13 14,9"/>
                                    <rect x="3" y="15" width="14" height="2" rx="1"/>
                                </svg>
                                Import…
                            </button>
                        </li>
                        <li role="none">
                            <button role="menuitem" on:click={() => moreAction("export")}>
                                <svg viewBox="0 0 20 20" aria-hidden="true">
                                    <polyline points="10,13 10,3"/>
                                    <polyline points="6,7 10,3 14,7"/>
                                    <rect x="3" y="15" width="14" height="2" rx="1"/>
                                </svg>
                                Export…
                            </button>
                        </li>
                        <li class="sr-more-divider" role="none"></li>
                        <li role="none">
                            <button role="menuitem" on:click={() => moreAction("deck-options")}>
                                <svg viewBox="0 0 20 20" aria-hidden="true">
                                    <circle cx="10" cy="10" r="2.5"/>
                                    <path d="M10 3v2M10 15v2M3 10h2M15 10h2M5.1 5.1l1.4 1.4M13.5 13.5l1.4 1.4M5.1 14.9l1.4-1.4M13.5 6.5l1.4-1.4"/>
                                </svg>
                                Deck options…
                            </button>
                        </li>
                        <li role="none">
                            <button role="menuitem" on:click={() => moreAction("prefs")}>
                                <svg viewBox="0 0 20 20" aria-hidden="true">
                                    <path d="M10 2a8 8 0 1 0 0 16A8 8 0 0 0 10 2z"/>
                                    <line x1="10" y1="8" x2="10" y2="12"/>
                                    <circle cx="10" cy="6" r="0.8" fill="currentColor"/>
                                </svg>
                                Preferences…
                            </button>
                        </li>
                    </ul>
                {/if}
            </div>
        </nav>
    </header>

    <!-- ── Score cards ───────────────────────────────────────────────────── -->
    <section class="sr-score-row" aria-label="Your scores">
        <!-- Memory card -->
        <div class="sr-card sr-card--memory">
            <div class="sr-card-eyebrow">
                <svg class="sr-card-icon" viewBox="0 0 20 20" aria-hidden="true">
                    <path d="M10 2a6 6 0 0 1 6 6c0 2.5-1.5 4.7-3.7 5.6L12 16H8l-.3-2.4A6 6 0 0 1 10 2z"/>
                    <circle cx="10" cy="17" r="1.3"/>
                </svg>
                Memory
            </div>
            {#if data.memory}
                {@const m = data.memory}
                {@const band = halfBand(m.ciLower, m.ciUpper)}
                <div class="sr-score-main">
                    <span class="sr-score-value">{pct(m.meanRecall)}</span>
                    <span class="sr-band-chip">±{band}</span>
                </div>
                <div class="sr-card-sub">meta vocabulary · {m.cardCount} cards</div>
            {:else}
                <div class="sr-card-empty">No meta cards yet</div>
                <div class="sr-card-sub">Import the seed deck to get started</div>
            {/if}
        </div>

        <!-- Performance card -->
        <div class="sr-card sr-card--perf">
            <div class="sr-card-eyebrow">
                <svg class="sr-card-icon" viewBox="0 0 20 20" aria-hidden="true">
                    <polyline points="2,14 7,9 11,12 18,5"/>
                    <line x1="14" y1="5" x2="18" y2="5"/>
                    <line x1="18" y1="5" x2="18" y2="9"/>
                </svg>
                Performance
            </div>
            <div class="sr-score-main">
                <span class="sr-score-value">{pct(data.overallPerf)}</span>
                {#if data.totalAttempts >= 5}
                    <span class="sr-band-chip">±{overallBand()}</span>
                {/if}
            </div>
            <div class="sr-card-sub">fresh-item accuracy · LR</div>
        </div>

        <!-- Readiness card — MUST check eligible before showing any number (D-SR10) -->
        <div class="sr-card sr-card--readiness" class:sr-card--abstaining={!data.eligible}>
            <div class="sr-card-eyebrow">
                <svg class="sr-card-icon" viewBox="0 0 20 20" aria-hidden="true">
                    <rect x="4" y="9" width="12" height="9" rx="1.5"/>
                    <path d="M7 9V6a3 3 0 0 1 6 0v3"/>
                </svg>
                Readiness
                <span class="sr-lr-badge">LR-only</span>
            </div>

            {#if data.eligible && data.readiness}
                {@const r = data.readiness}
                <div class="sr-score-main">
                    <span class="sr-score-value">{r.point}</span>
                    <span class="sr-band-chip">{r.bandLow}–{r.bandHigh}</span>
                </div>
                <div class="sr-card-sub">
                    {confidenceLabel(r.confidence)} confidence · {pctHalf(r.coverage)} covered
                </div>
                <p class="sr-disclaimer">Approximation only — not LSAC equating.</p>
            {:else if data.abstain}
                {@const a = data.abstain}
                <!-- Abstain panel: no point estimate (D-SR10) -->
                <div class="sr-abstain">
                    <p class="sr-abstain-title">Not enough evidence yet</p>
                    <table class="sr-abstain-table">
                        <tbody>
                            <tr>
                                <td>Attempts</td>
                                <td class="sr-abstain-val">{data.totalAttempts} / 200</td>
                            </tr>
                            <tr>
                                <td>LR coverage</td>
                                <td class="sr-abstain-val">{pctHalf(a.coverage)}</td>
                            </tr>
                        </tbody>
                    </table>
                    <p class="sr-abstain-note">
                        Keep drilling — a projected 120–180 score unlocks at 200 attempts.
                    </p>
                </div>
            {:else}
                <div class="sr-card-empty">No skill data yet</div>
            {/if}
        </div>
    </section>

    <!-- ── Today's focus ─────────────────────────────────────────────────── -->
    <section class="sr-focus" aria-label="Today's focus">
        <div class="sr-focus-content">
            <p class="sr-focus-label">Today's focus</p>
            {#if focusSkill}
                <h2 class="sr-focus-heading">{displayName(focusSkill)} family</h2>
                <p class="sr-focus-sub">
                    Your weakest high-frequency skill
                    {#if focusSkillPerf && focusSkillPerf.attempts >= MIN_ATTEMPTS}
                        · {skillPct(focusSkillPerf)}% accuracy so far
                    {/if}
                </p>
            {:else if data.totalAttempts === 0}
                <h2 class="sr-focus-heading">Start with any skill</h2>
                <p class="sr-focus-sub">Complete a few reviews and we'll personalise your focus.</p>
            {:else}
                <h2 class="sr-focus-heading">Keep building coverage</h2>
                <p class="sr-focus-sub">Cover more question types to unlock a recommended focus.</p>
            {/if}
        </div>
        <div class="sr-focus-cta">
            <button class="sr-btn-primary" on:click={startTargetedDrill}>
                Start targeted drill
                <svg viewBox="0 0 20 20" aria-hidden="true" class="sr-btn-arrow">
                    <line x1="4" y1="10" x2="16" y2="10"/>
                    <polyline points="11,5 16,10 11,15"/>
                </svg>
            </button>
            <p class="sr-cta-meta">~10 items · ~12 min</p>
        </div>
    </section>

    <!-- ── Session launchers ──────────────────────────────────────────────── -->
    <!--
    WP-22 SEAM: these buttons emit bridge commands handled by SpeedrunHomeDialog.
    Replace with SvelteKit route navigation once ts/routes/speedrun-session/ exists.
    -->
    <section class="sr-launchers" aria-label="Choose a session">
        <button
            class="sr-launcher"
            on:click={() => launchSession("mixed")}
            title="Interleave question types to build flexibility (WP-22)"
        >
            <span class="sr-launcher-icon" aria-hidden="true">
                <svg viewBox="0 0 20 20">
                    <path d="M3 6h4l2 2-2 2H3m14-4h-4l-2 2 2 2h4M7 14h6"/>
                    <line x1="10" y1="10" x2="10" y2="14"/>
                </svg>
            </span>
            <span class="sr-launcher-text">
                <strong>Mixed set</strong>
                <span>Interleave question types<br>to build flexibility.</span>
            </span>
            <span class="sr-launcher-arrow" aria-hidden="true">→</span>
        </button>

        <button
            class="sr-launcher"
            on:click={() => launchSession("timed")}
            title="Simulate test conditions and pacing (WP-22)"
        >
            <span class="sr-launcher-icon" aria-hidden="true">
                <svg viewBox="0 0 20 20">
                    <circle cx="10" cy="11" r="7"/>
                    <line x1="10" y1="4" x2="10" y2="2"/>
                    <line x1="10" y1="11" x2="13" y2="8"/>
                </svg>
            </span>
            <span class="sr-launcher-text">
                <strong>Timed section</strong>
                <span>Simulate test conditions<br>and pacing.</span>
            </span>
            <span class="sr-launcher-arrow" aria-hidden="true">→</span>
        </button>

        <button
            class="sr-launcher"
            on:click={() => launchSession("blind")}
            title="Review without answers to strengthen recall (WP-22)"
        >
            <span class="sr-launcher-icon" aria-hidden="true">
                <svg viewBox="0 0 20 20">
                    <ellipse cx="10" cy="10" rx="8" ry="5"/>
                    <circle cx="10" cy="10" r="2.5"/>
                    <line x1="3" y1="3" x2="17" y2="17" class="sr-eye-slash"/>
                </svg>
            </span>
            <span class="sr-launcher-text">
                <strong>Blind review</strong>
                <span>Review without answers<br>to strengthen recall.</span>
            </span>
            <span class="sr-launcher-arrow" aria-hidden="true">→</span>
        </button>
    </section>

    <!-- ── Skill map ──────────────────────────────────────────────────────── -->
    <section class="sr-skillmap" aria-label="Skill map">
        <header class="sr-skillmap-header">
            <span class="sr-skillmap-title">Skill map</span>
            <span class="sr-skillmap-subtitle">Performance by LR question type</span>
            <span class="sr-skillmap-ci-label">Performance (±95% CI)</span>
        </header>

        {#if sortedSkills.length === 0}
            <p class="sr-skillmap-empty">
                No skill reviews yet. Complete some drills to see your performance map.
            </p>
        {:else}
            <div class="sr-skillmap-rows">
                {#each sortedSkills as skill (skill.skill)}
                    {@const isRecommended = skill.skill === focusSkill}
                    {@const p = skillPct(skill)}
                    {@const band = skillBand(skill)}
                    {@const hasData = skill.attempts >= MIN_ATTEMPTS}
                    <div class="sr-skillmap-row" class:sr-skillmap-row--rec={isRecommended}>
                        <span class="sr-skill-tag">{skill.skill.startsWith("type::") ? skill.skill : `type::${shortName(skill.skill)}`}</span>
                        <div class="sr-bar-track" title="{hasData ? `${p}% · 95% CI ±${band}%` : 'Insufficient data (<5 reviews)'}">
                            {#if hasData}
                                <div
                                    class="sr-bar-fill"
                                    style:width="{p}%"
                                ></div>
                                <!-- Wilson CI tick marks -->
                                <div
                                    class="sr-bar-ci sr-bar-ci-lo"
                                    style:left="{(skill.wilsonLow * 100).toFixed(1)}%"
                                ></div>
                                <div
                                    class="sr-bar-ci sr-bar-ci-hi"
                                    style:left="{(skill.wilsonHigh * 100).toFixed(1)}%"
                                ></div>
                            {:else}
                                <div class="sr-bar-fill sr-bar-fill--empty" style:width="100%"></div>
                            {/if}
                        </div>
                        <span class="sr-skill-pct">
                            {#if hasData}
                                {p}%
                            {:else}
                                —
                            {/if}
                        </span>
                        <span class="sr-skill-ci">
                            {#if hasData && band > 0}
                                (±{band})
                            {:else if !hasData}
                                <span class="sr-skill-ci--none">&lt;5 reviews</span>
                            {/if}
                        </span>
                        <span class="sr-skill-badge">
                            {#if isRecommended}
                                <span class="sr-rec-badge" aria-label="Recommended">★ Recommended</span>
                            {/if}
                        </span>
                    </div>
                {/each}
            </div>
        {/if}
    </section>
</div>

<style lang="scss">
    // ── Design tokens (spec-ui §2) ────────────────────────────────────────────
    $bg:           #F5F7FA;
    $ink:          #1B2430;
    $indigo:       #3E3A8C;
    $indigo-mid:   #5752B3;
    $indigo-light: #EEEDF8;
    $success:      #2E7D5B;
    $error:        #B4472E;
    $amber:        #C99A2E;
    $amber-light:  #FEF8E7;
    $border:       #DDE2E9;
    $muted:        #6B7280;
    $surface:      #FFFFFF;

    // Font stacks (spec-ui §2)
    $grotesk: -apple-system, "Inter", "Helvetica Neue", Arial, sans-serif;
    $serif:   "Georgia", "Palatino Linotype", "Book Antiqua", serif;
    $mono:    "JetBrains Mono", "Fira Code", "Cascadia Code", "Courier New", monospace;

    // ── Root ─────────────────────────────────────────────────────────────────

    .sr-home {
        font-family: $grotesk;
        font-size: 14px;
        color: $ink;
        background: $bg;
        min-height: 100vh;
        padding: 0 0 3em;
    }

    // ── Header ────────────────────────────────────────────────────────────────

    .sr-home-header {
        display: flex;
        align-items: center;
        padding: 0.75em 2em;
        border-bottom: 1px solid $border;
        background: $surface;
        gap: 1em;
    }

    .sr-brand {
        font-family: $grotesk;
        font-size: 1.15em;
        font-weight: 700;
        color: $indigo;
        letter-spacing: -0.01em;
        flex-shrink: 0;
    }

    // ── Anki action controls (WP-25) ──────────────────────────────────────────

    .sr-anki-actions {
        display: flex;
        align-items: center;
        gap: 0.25em;
        margin-left: auto;
    }

    .sr-action-btn {
        display: inline-flex;
        flex-direction: column;
        align-items: center;
        gap: 0.2em;
        background: transparent;
        border: 1px solid transparent;
        border-radius: 7px;
        padding: 0.35em 0.65em;
        font-family: $grotesk;
        font-size: 0.72em;
        font-weight: 500;
        color: $muted;
        cursor: pointer;
        transition: background 0.12s, border-color 0.12s, color 0.12s;
        white-space: nowrap;

        &:hover {
            background: $indigo-light;
            border-color: $indigo-light;
            color: $indigo;

            .sr-action-icon {
                stroke: $indigo;
            }
        }

        &:focus-visible {
            outline: 2px solid $indigo;
            outline-offset: 2px;
        }

        &--more {
            // slight emphasis on the ellipsis button
        }
    }

    .sr-action-icon {
        width: 17px;
        height: 17px;
        stroke: $muted;
        stroke-width: 1.6;
        fill: none;
        stroke-linecap: round;
        stroke-linejoin: round;
        transition: stroke 0.12s;
    }

    .sr-action-label {
        line-height: 1;
    }

    // More dropdown
    .sr-more-wrap {
        position: relative;
    }

    .sr-more-backdrop {
        position: fixed;
        inset: 0;
        z-index: 99;
    }

    .sr-more-menu {
        position: absolute;
        right: 0;
        top: calc(100% + 6px);
        z-index: 100;
        background: $surface;
        border: 1px solid $border;
        border-radius: 9px;
        box-shadow: 0 4px 18px rgba(27, 36, 48, 0.13);
        padding: 0.4em 0;
        list-style: none;
        margin: 0;
        min-width: 170px;

        li button {
            display: flex;
            align-items: center;
            gap: 0.6em;
            width: 100%;
            background: transparent;
            border: none;
            padding: 0.6em 1.1em;
            font-family: $grotesk;
            font-size: 0.88em;
            color: $ink;
            cursor: pointer;
            text-align: left;

            svg {
                width: 15px;
                height: 15px;
                stroke: $muted;
                stroke-width: 1.6;
                fill: none;
                stroke-linecap: round;
                stroke-linejoin: round;
                flex-shrink: 0;
            }

            &:hover {
                background: $indigo-light;
                color: $indigo;

                svg {
                    stroke: $indigo;
                }
            }
        }
    }

    .sr-more-divider {
        height: 1px;
        background: $border;
        margin: 0.3em 0;
    }

    // ── Score cards ───────────────────────────────────────────────────────────

    .sr-score-row {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1em;
        padding: 1.25em 2em;

        @media (max-width: 800px) {
            grid-template-columns: 1fr;
        }
    }

    .sr-card {
        background: $surface;
        border: 1px solid $border;
        border-radius: 10px;
        padding: 1.25em 1.4em;
        display: flex;
        flex-direction: column;
        gap: 0.5em;
    }

    .sr-card--abstaining {
        border-style: dashed;
        background: #FAFBFC;
    }

    .sr-card-eyebrow {
        display: flex;
        align-items: center;
        gap: 0.45em;
        font-size: 0.9em;
        font-weight: 600;
        color: $ink;
    }

    .sr-card-icon {
        width: 18px;
        height: 18px;
        stroke: $indigo;
        stroke-width: 1.8;
        fill: none;
        stroke-linecap: round;
        stroke-linejoin: round;
        flex-shrink: 0;
    }

    .sr-lr-badge {
        margin-left: auto;
        font-size: 0.72em;
        font-weight: 500;
        background: #EEF2FF;
        color: $indigo;
        border-radius: 4px;
        padding: 1px 6px;
    }

    .sr-score-main {
        display: flex;
        align-items: baseline;
        gap: 0.55em;
    }

    .sr-score-value {
        font-family: $grotesk;
        font-size: 2.6em;
        font-weight: 700;
        color: $indigo;
        line-height: 1;
        letter-spacing: -0.02em;
    }

    .sr-band-chip {
        font-size: 0.85em;
        font-weight: 500;
        background: $indigo-light;
        color: $indigo;
        border-radius: 5px;
        padding: 2px 7px;
        white-space: nowrap;
    }

    .sr-card-sub {
        font-size: 0.82em;
        color: $muted;
        margin-top: 0.15em;
    }

    .sr-card-empty {
        font-size: 0.9em;
        color: $muted;
        font-style: italic;
    }

    .sr-disclaimer {
        margin: 0.5em 0 0;
        font-size: 0.75em;
        color: $muted;
        border-top: 1px solid $border;
        padding-top: 0.5em;
    }

    // Abstain panel
    .sr-abstain {
        display: flex;
        flex-direction: column;
        gap: 0.5em;
    }

    .sr-abstain-title {
        margin: 0;
        font-size: 1em;
        font-weight: 600;
        color: $ink;
    }

    .sr-abstain-table {
        border-collapse: collapse;
        font-size: 0.88em;
        width: 100%;

        td {
            padding: 2px 0;
            color: $muted;
        }

        .sr-abstain-val {
            text-align: right;
            color: $ink;
            font-weight: 500;
        }
    }

    .sr-abstain-note {
        margin: 0;
        font-size: 0.82em;
        color: $muted;
    }

    // ── Today's focus ─────────────────────────────────────────────────────────

    .sr-focus {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1.5em;
        margin: 0 2em 1em;
        background: $surface;
        border: 1px solid $border;
        border-radius: 10px;
        padding: 1.5em 2em;

        @media (max-width: 700px) {
            flex-direction: column;
            align-items: flex-start;
        }
    }

    .sr-focus-content {
        display: flex;
        flex-direction: column;
        gap: 0.3em;
        flex: 1;
    }

    .sr-focus-label {
        margin: 0;
        font-size: 0.78em;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: $indigo;
    }

    .sr-focus-heading {
        margin: 0;
        font-family: $serif;
        font-size: 1.9em;
        font-weight: 700;
        color: $ink;
        line-height: 1.15;
        letter-spacing: -0.01em;
    }

    .sr-focus-sub {
        margin: 0;
        font-size: 0.88em;
        color: $muted;
    }

    .sr-focus-cta {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.5em;
        flex-shrink: 0;
    }

    .sr-btn-primary {
        display: inline-flex;
        align-items: center;
        gap: 0.5em;
        background: $indigo;
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        padding: 0.75em 1.5em;
        font-family: $grotesk;
        font-size: 1em;
        font-weight: 600;
        cursor: pointer;
        transition: background 0.15s;
        white-space: nowrap;

        &:hover {
            background: $indigo-mid;
        }

        &:focus-visible {
            outline: 3px solid $amber;
            outline-offset: 2px;
        }
    }

    .sr-btn-arrow {
        width: 18px;
        height: 18px;
        stroke: currentColor;
        stroke-width: 2;
        fill: none;
        stroke-linecap: round;
        stroke-linejoin: round;
    }

    .sr-cta-meta {
        margin: 0;
        font-size: 0.8em;
        color: $muted;
    }

    // ── Session launchers ─────────────────────────────────────────────────────

    .sr-launchers {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1em;
        padding: 0 2em 1em;

        @media (max-width: 700px) {
            grid-template-columns: 1fr;
        }
    }

    .sr-launcher {
        display: flex;
        align-items: flex-start;
        gap: 0.9em;
        background: $surface;
        border: 1px solid $border;
        border-radius: 10px;
        padding: 1.1em 1.2em;
        cursor: pointer;
        text-align: left;
        font-family: $grotesk;
        font-size: 0.9em;
        color: $ink;
        transition: border-color 0.15s, box-shadow 0.15s;

        &:hover {
            border-color: $indigo;
            box-shadow: 0 0 0 3px $indigo-light;
        }

        &:focus-visible {
            outline: 3px solid $amber;
            outline-offset: 2px;
        }
    }

    .sr-launcher-icon {
        flex-shrink: 0;
        width: 36px;
        height: 36px;
        background: $indigo-light;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;

        svg {
            width: 18px;
            height: 18px;
            stroke: $indigo;
            stroke-width: 1.8;
            fill: none;
            stroke-linecap: round;
            stroke-linejoin: round;
        }
    }

    .sr-launcher-text {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 0.2em;

        strong {
            font-weight: 600;
            font-size: 1em;
        }

        span {
            font-size: 0.83em;
            color: $muted;
            line-height: 1.4;
        }
    }

    .sr-launcher-arrow {
        color: $muted;
        font-size: 1.1em;
        margin-left: auto;
        align-self: center;
    }

    .sr-eye-slash {
        stroke: $muted;
        stroke-width: 1.5;
    }

    // ── Skill map ─────────────────────────────────────────────────────────────

    .sr-skillmap {
        margin: 0 2em;
        background: $surface;
        border: 1px solid $border;
        border-radius: 10px;
        padding: 1.25em 1.5em;
    }

    .sr-skillmap-header {
        display: flex;
        align-items: baseline;
        gap: 0.6em;
        margin-bottom: 1em;
        border-bottom: 1px solid $border;
        padding-bottom: 0.6em;
    }

    .sr-skillmap-title {
        font-size: 1em;
        font-weight: 700;
        color: $ink;
    }

    .sr-skillmap-subtitle {
        font-size: 0.85em;
        color: $muted;
        flex: 1;
    }

    .sr-skillmap-ci-label {
        font-size: 0.8em;
        color: $muted;
        white-space: nowrap;
    }

    .sr-skillmap-empty {
        color: $muted;
        font-size: 0.9em;
        padding: 1em 0;
    }

    .sr-skillmap-rows {
        display: flex;
        flex-direction: column;
        gap: 0.35em;
    }

    .sr-skillmap-row {
        display: grid;
        grid-template-columns: 13em 1fr 3.5em 4em 8em;
        align-items: center;
        gap: 0.6em;
        padding: 0.3em 0.5em;
        border-radius: 5px;

        &--rec {
            background: $amber-light;
        }

        @media (max-width: 900px) {
            grid-template-columns: 10em 1fr 3em 3em 6em;
        }
        @media (max-width: 600px) {
            grid-template-columns: 9em 1fr 3em 3em 0;
        }
    }

    .sr-skill-tag {
        font-family: $mono;
        font-size: 0.8em;
        color: $ink;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .sr-bar-track {
        position: relative;
        height: 14px;
        background: #EFF1F5;
        border-radius: 3px;
        overflow: hidden;
    }

    .sr-bar-fill {
        height: 100%;
        background: $indigo;
        border-radius: 3px;
        transition: width 0.4s ease;

        &--empty {
            background: #E5E7EB;
            opacity: 0.5;
        }
    }

    .sr-bar-ci {
        position: absolute;
        top: 0;
        bottom: 0;
        width: 2px;
        background: rgba(27, 36, 48, 0.3);
        border-radius: 1px;
    }

    .sr-skill-pct {
        text-align: right;
        font-size: 0.88em;
        font-weight: 600;
        color: $ink;
    }

    .sr-skill-ci {
        font-size: 0.8em;
        color: $muted;
        text-align: right;
    }

    .sr-skill-ci--none {
        font-style: italic;
        font-size: 0.85em;
    }

    .sr-skill-badge {
        display: flex;
        align-items: center;
    }

    // The signature amber element — reserved for recommendation (spec-ui §2)
    .sr-rec-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.3em;
        background: $amber;
        color: #FFFFFF;
        font-size: 0.73em;
        font-weight: 700;
        letter-spacing: 0.02em;
        border-radius: 5px;
        padding: 2px 7px;
        white-space: nowrap;
    }
</style>
