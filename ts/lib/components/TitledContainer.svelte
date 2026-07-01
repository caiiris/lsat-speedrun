<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import { pageTheme } from "$lib/sveltelib/theme";

    const rtl: boolean = window.getComputedStyle(document.body).direction == "rtl";

    export let id: string | undefined = undefined;
    let className: string = "";
    export { className as class };

    export let title: string;
</script>

<div
    {id}
    class="container {className}"
    class:light={!$pageTheme.isDark}
    class:dark={$pageTheme.isDark}
    class:rtl
    style:--gutter-block="2px"
    style:--container-margin="0"
>
    <div class="position-relative">
        <h1>
            {title}
        </h1>
        <div class="help-badge position-absolute" class:rtl>
            <slot name="tooltip" />
        </div>
    </div>
    <slot />
</div>

<style lang="scss">
    @use "../sass/elevation" as *;
    .container {
        width: 100%;
        background: var(--canvas-elevated);
        border: 1px solid var(--border-subtle);
        border-radius: var(--border-radius-medium, 10px);

        &.light {
            @include elevation(3);
        }
        &.dark {
            @include elevation(4);
        }

        padding: 1rem 1.75rem 0.75rem 1.25rem;
        &.rtl {
            padding: 1rem 1.25rem 0.75rem 1.75rem;
        }
        page-break-inside: avoid;
    }
    h1 {
        border-bottom: 1px solid var(--border);
        padding-bottom: 0.25em;
    }
    .help-badge {
        right: 0;
        top: 0;
        color: #555;
        &.rtl {
            right: unset;
            left: 0;
        }
    }

    :global(.night-mode) .help-badge {
        color: var(--fg);
    }

    // Speedrun WP-27 (fix): restyle graph cards to the Speedrun design language.
    // Scoped to this component but gated on the global body.speedrun-stats class
    // (set only by the Speedrun stats page), so stock Anki + other pages are
    // unaffected. Uses :global() for the ancestor and keeps .container/h1 scoped.
    :global(body.speedrun-stats) .container {
        background: #ffffff;
        border: 1px solid #dde2e9;
        border-radius: 16px;
        box-shadow: 0 2px 12px rgba(27, 36, 48, 0.07);
    }
    // Card titles match the drill's prominent heading EXACTLY (the indigo grotesk
    // prompt "In one line, what must the right answer do?" — speedrun.py): same
    // sans stack, weight 700, ~1.05rem, indigo, sentence case, normal tracking.
    :global(body.speedrun-stats) h1 {
        color: #3e3a8c;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 1.05rem;
        font-weight: 700;
        letter-spacing: normal;
        text-transform: none;
        border-bottom-color: #eceff3;
        padding-bottom: 0.4em;
    }
</style>
