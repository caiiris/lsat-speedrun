<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

Speedrun WP-14 — Three-score dashboard: Memory · Performance · Readiness.

Honesty invariants (D-SR10, spec-measurement §6):
- The Readiness card shows NO point estimate when eligible = false.
- The Readiness card is labeled "LR-only estimate" at all times (D-SR19).
- Bands are displayed alongside every score; narrower = more data.
-->
<script lang="ts">
    import type {
        SpeedrunDashboardResponse,
        SpeedrunSkillPerf,
    } from "@generated/anki/stats_pb";

    export let data: SpeedrunDashboardResponse;

    // ── Memory helpers ────────────────────────────────────────────────────────

    function pct(v: number): string {
        return `${(v * 100).toFixed(1)}%`;
    }

    function scaledBandLabel(low: number, high: number, point: number): string {
        return `${point} (${low}–${high})`;
    }

    // ── Performance helpers ───────────────────────────────────────────────────

    const MIN_ATTEMPTS = 5; // mirrors Rust constant

    function barWidth(skill: SpeedrunSkillPerf): string {
        if (skill.attempts < MIN_ATTEMPTS) return "0%";
        return `${((skill.correct / skill.attempts) * 100).toFixed(1)}%`;
    }

    function barColor(skill: SpeedrunSkillPerf): string {
        if (skill.attempts < MIN_ATTEMPTS) return "var(--fg-subtle)";
        const p = skill.correct / skill.attempts;
        if (p >= 0.8) return "var(--state-review-count-foreground, #4caf50)";
        if (p >= 0.6) return "var(--state-learn-count-foreground, #f0a500)";
        return "var(--state-relearn-count-foreground, #f44336)";
    }

    function wilson(skill: SpeedrunSkillPerf): string {
        if (skill.attempts < MIN_ATTEMPTS) return "insufficient data (<5 reviews)";
        const lo = (skill.wilsonLow * 100).toFixed(0);
        const hi = (skill.wilsonHigh * 100).toFixed(0);
        return `95% CI: ${lo}–${hi}%`;
    }

    // ── Readiness helpers ─────────────────────────────────────────────────────

    function confidenceLabel(c: string): string {
        return { low: "Low confidence", medium: "Medium confidence", high: "High confidence" }[c] ?? c;
    }
</script>

<div class="speedrun-dashboard">
    <!-- ── Memory Card ──────────────────────────────────────────────────── -->
    <section class="score-card memory-card">
        <h2>Memory</h2>
        <p class="subtitle">FSRS recall over LSAT Meta cards (vocabulary &amp; flaw definitions)</p>

        {#if data.memory}
            {@const m = data.memory}
            <div class="score-main">
                <span class="score-value">{pct(m.meanRecall)}</span>
                <span class="score-band">CI: {pct(m.ciLower)} – {pct(m.ciUpper)}</span>
            </div>
            <p class="score-meta">From {m.cardCount} meta cards</p>
        {:else}
            <div class="no-data">
                <p>No LSAT Meta cards found in this deck.</p>
                <p class="hint">Import the seed deck or add meta cards to get started.</p>
            </div>
        {/if}
    </section>

    <!-- ── Performance Card ────────────────────────────────────────────── -->
    <section class="score-card performance-card">
        <h2>Performance</h2>
        <p class="subtitle">
            Fresh-item accuracy by skill (Wilson 95% CI)
            — overall: <strong>{pct(data.overallPerf)}</strong>
            — LR coverage: <strong>{pct(data.lrCoverage)}</strong>
        </p>

        {#if data.skillPerf.length === 0}
            <div class="no-data">
                <p>No skill-card reviews recorded yet.</p>
                <p class="hint">Complete some skill reviews to see per-skill accuracy.</p>
            </div>
        {:else}
            <div class="skill-bars">
                {#each data.skillPerf as skill (skill.skill)}
                    <div class="skill-row">
                        <div class="skill-label" title={skill.skill}>
                            {skill.skill.replace(/^type::/, "")}
                        </div>
                        <div class="bar-container" title={wilson(skill)}>
                            {#if skill.attempts >= MIN_ATTEMPTS}
                                <div
                                    class="bar-fill"
                                    style:width={barWidth(skill)}
                                    style:background={barColor(skill)}
                                ></div>
                                <!-- Wilson band overlay -->
                                <div
                                    class="wilson-low"
                                    style:left={`${(skill.wilsonLow * 100).toFixed(1)}%`}
                                ></div>
                                <div
                                    class="wilson-high"
                                    style:left={`${(skill.wilsonHigh * 100).toFixed(1)}%`}
                                ></div>
                            {:else}
                                <div class="bar-fill insufficient" style:width="100%"></div>
                            {/if}
                        </div>
                        <div class="skill-stat">
                            {#if skill.attempts >= MIN_ATTEMPTS}
                                {skill.correct}/{skill.attempts}
                            {:else}
                                <span class="insufficient-label">&lt;{MIN_ATTEMPTS} reviews</span>
                            {/if}
                        </div>
                    </div>
                {/each}
            </div>
        {/if}
    </section>

    <!-- ── Readiness Card ──────────────────────────────────────────────── -->
    <section class="score-card readiness-card" class:abstaining={!data.eligible}>
        <h2>
            Readiness
            <span class="lr-only-badge">LR-only estimate</span>
        </h2>
        <p class="subtitle">
            Projected LSAT score 120–180 via D-SR18 formula
            — total attempts: <strong>{data.totalAttempts}</strong>
        </p>

        {#if data.eligible && data.readiness}
            {@const r = data.readiness}
            <div class="score-main">
                <span class="score-value">{r.point}</span>
                <span class="score-band">{r.bandLow}–{r.bandHigh}</span>
            </div>
            <div class="readiness-meta">
                <span class="confidence-badge confidence-{r.confidence}">{confidenceLabel(r.confidence)}</span>
                <span class="coverage">LR coverage: {pct(r.coverage)}</span>
            </div>
            {#if r.topSkills.length > 0}
                <div class="top-skills">
                    <span class="label">Top contributors:</span>
                    {#each r.topSkills as skill}
                        <span class="skill-chip">{skill.replace(/^type::/, "")}</span>
                    {/each}
                </div>
            {/if}
            {#if r.nextBest}
                <div class="next-best">
                    <span class="label">Best next focus:</span>
                    <strong>{r.nextBest.replace(/^type::/, "")}</strong>
                </div>
            {/if}
            <p class="disclaimer">
                ⚠️ Approximation only — not LSAC equating. Sources: Magoosh, PowerScore LRB 2024–25.
            </p>
        {:else if data.abstain}
            {@const a = data.abstain}
            <!-- Abstain panel: NO point estimate shown (D-SR10) -->
            <div class="abstain-panel">
                <div class="abstain-icon">🔒</div>
                <h3>Not enough data for a score estimate</h3>
                <ul class="reasons">
                    {#each a.reasons as reason}
                        <li>{reason}</li>
                    {/each}
                </ul>
                <p class="coverage-progress">
                    LR coverage so far: <strong>{pct(a.coverage)}</strong>
                    of the 13-type taxonomy
                </p>
                {#if a.nextBest}
                    <div class="next-best">
                        <span class="label">Best next focus to build coverage:</span>
                        <strong>{a.nextBest.replace(/^type::/, "")}</strong>
                    </div>
                {/if}
                <p class="abstain-note">
                    Keep practicing! A projection will appear once you have
                    ≥200 total reviews and ≥50% LR coverage.
                </p>
            </div>
        {:else}
            <div class="no-data">
                <p>No skill data yet.</p>
            </div>
        {/if}
    </section>
</div>

<style lang="scss">
    .speedrun-dashboard {
        display: grid;
        gap: 1.5em;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        padding: 1.5em;

        @media (max-width: 1200px) {
            grid-template-columns: 1fr 1fr;
        }
        @media (max-width: 700px) {
            grid-template-columns: 1fr;
        }
    }

    .score-card {
        background: var(--canvas-elevated, #fff);
        border: 1px solid var(--border, #ddd);
        border-radius: 8px;
        padding: 1.25em;
        display: flex;
        flex-direction: column;
        gap: 0.75em;

        h2 {
            margin: 0;
            font-size: 1.1em;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.5em;
        }

        .subtitle {
            margin: 0;
            font-size: 0.85em;
            color: var(--fg-subtle, #666);
        }
    }

    .score-main {
        display: flex;
        align-items: baseline;
        gap: 0.75em;

        .score-value {
            font-size: 2.5em;
            font-weight: 700;
            line-height: 1;
        }

        .score-band {
            font-size: 1em;
            color: var(--fg-subtle, #666);
        }
    }

    .score-meta {
        margin: 0;
        font-size: 0.85em;
        color: var(--fg-subtle, #666);
    }

    .no-data {
        p {
            margin: 0 0 0.25em;
        }
        .hint {
            font-size: 0.85em;
            color: var(--fg-subtle, #666);
        }
    }

    // ── Performance ──────────────────────────────────────────────────────────

    .skill-bars {
        display: flex;
        flex-direction: column;
        gap: 0.4em;
    }

    .skill-row {
        display: grid;
        grid-template-columns: 9em 1fr 4em;
        align-items: center;
        gap: 0.5em;
        font-size: 0.85em;
    }

    .skill-label {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        color: var(--fg, #222);
        font-weight: 500;
    }

    .bar-container {
        position: relative;
        height: 16px;
        background: var(--canvas-inset, #f0f0f0);
        border-radius: 3px;
        overflow: hidden;
    }

    .bar-fill {
        height: 100%;
        border-radius: 3px;
        transition: width 0.3s ease;

        &.insufficient {
            background: var(--canvas-inset, #eee);
            opacity: 0.4;
        }
    }

    .wilson-low,
    .wilson-high {
        position: absolute;
        top: 0;
        bottom: 0;
        width: 2px;
        background: rgba(0, 0, 0, 0.35);
    }

    .skill-stat {
        text-align: right;
        font-size: 0.85em;
        color: var(--fg-subtle, #666);
        white-space: nowrap;
    }

    .insufficient-label {
        color: var(--fg-subtle, #888);
        font-style: italic;
    }

    // ── Readiness ─────────────────────────────────────────────────────────────

    .lr-only-badge {
        font-size: 0.65em;
        font-weight: normal;
        background: var(--state-suspended-foreground, #e0c060);
        color: var(--canvas, #fff);
        border-radius: 4px;
        padding: 2px 6px;
    }

    .readiness-meta {
        display: flex;
        gap: 1em;
        align-items: center;
        flex-wrap: wrap;
    }

    .confidence-badge {
        font-size: 0.8em;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 600;

        &.confidence-low {
            background: #fde8e8;
            color: #c0392b;
        }
        &.confidence-medium {
            background: #fef3cd;
            color: #856404;
        }
        &.confidence-high {
            background: #d4edda;
            color: #155724;
        }
    }

    .coverage {
        font-size: 0.85em;
        color: var(--fg-subtle, #666);
    }

    .top-skills,
    .next-best {
        display: flex;
        align-items: center;
        gap: 0.4em;
        flex-wrap: wrap;
        font-size: 0.85em;

        .label {
            color: var(--fg-subtle, #666);
        }
    }

    .skill-chip {
        background: var(--canvas-inset, #eee);
        border-radius: 4px;
        padding: 1px 6px;
        font-size: 0.85em;
    }

    .disclaimer {
        margin: 0;
        font-size: 0.75em;
        color: var(--fg-subtle, #888);
        border-top: 1px solid var(--border, #eee);
        padding-top: 0.5em;
    }

    // ── Abstain panel ─────────────────────────────────────────────────────────

    .abstaining {
        background: var(--canvas-inset, #f8f8f8);
        border-style: dashed;
    }

    .abstain-panel {
        display: flex;
        flex-direction: column;
        gap: 0.6em;

        .abstain-icon {
            font-size: 2em;
            line-height: 1;
        }

        h3 {
            margin: 0;
            font-size: 1em;
        }

        .reasons {
            margin: 0;
            padding-left: 1.2em;
            font-size: 0.9em;

            li {
                color: var(--state-relearn-count-foreground, #c0392b);
            }
        }

        .coverage-progress {
            margin: 0;
            font-size: 0.9em;
        }

        .abstain-note {
            margin: 0;
            font-size: 0.82em;
            color: var(--fg-subtle, #666);
        }
    }
</style>
