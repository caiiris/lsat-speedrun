# Speedrun — design iterations log

> Test-/feedback-driven changes to the product surface. Append-only; newest last
> within each entry. Decisions that come out of an iteration graduate to
> [`decisions.md`](./decisions.md); this log captures the *why it changed* trail.
> IDs are `DI-SR<N>`, monotonic (**next free: DI-SR14**).

---

### DI-SR13 — AnkiDroid: port the desktop session layer (mixed / timed / blind) to mobile

- **Surface:** new `SpeedrunSessionActivity` (full-screen WebView), launched from the mobile Home's three "Or choose a session" cards.
- **Trigger (owner):** *"do those three"* — after the Home redesign (DI-SR12) shipped only scores + a single reviewer "Start drill", the owner wanted the desktop Home's mixed/timed/blind sessions on the phone too.
- **What shipped:** a self-contained bounded-session engine (mobile port of `SpeedrunSessionDialog`, D-SR44) that reuses `SpeedrunReviewSession` + `SpeedrunHtml` for the drill and adds session chrome (`SpeedrunSessionHtml`): a sticky **progress/timer header** ("Timed section · Q 3/25 · progress bar · m:ss elapsed"; amber+bold clock for timed, muted otherwise) and a **scored result screen** (donut, "Where you slipped" with trap chips, all-questions strip with flag-to-revisit stars, "Blind review your N misses →" CTA, Another drill / Back to study plan).
- **Mode behaviour:** mixed = 10 items, prephrase on; timed = 25 items, choices-only, prominent clock; blind = 25 items (or the prior session's misses), choices-only, untimed. Each answer goes through `col.sched.answerCard(card, rating)` so FSRS/undo/sync stay intact; session accuracy is display-only (the three scores still come from the engine).
- **Bridge:** the drill HTML already emits `window.location.href='speedrun:…'` commands (`prephrase:reveal/skip`, `commit:<A-E>`, `trap:<tag>`, `continue`); the activity's `WebViewClient` intercepts them, plus result-screen commands (`flag:<n>` toggles a star via `evaluateJavascript`, `blind-review`, `another-drill`, `home`). Prephrase text is read back with `evaluateJavascript`.
- **Verified on emulator (Pixel, arm64), end-to-end:** launched Timed → header + amber clock ticking, choices-only; committed B → reveal verdict + why-wrong/why-correct + name-the-trap chips + skill-tag rail; "Next question →" advanced to Q 2/25 and recorded the answer; auto-answered through → result screen (2/21, clay donut, slips with trap chips, all-21 strip); tapped a flag star (→ amber ★); "Blind review your 19 misses →" restarted an untimed 1/19 blind session; result CTAs return to the Home.
- **Files:** `~/dev/droid/Anki-Android/AnkiDroid/.../speedrun/{SpeedrunSessionActivity,SpeedrunSessionHtml}.kt` (new), `SpeedrunReviewSession.kt`, `SpeedrunDashboardHtml.kt`, `SpeedrunScoresActivity.kt`, `AndroidManifest.xml`.
- **Not ported:** the **targeted** (per-focus-skill) session — mobile still has only mixed/timed/blind + the reviewer "Start drill". A per-skill mobile filter is future work.

### DI-SR12 — AnkiDroid: redesign the mobile Home (Speedrun scores) to mirror the desktop dashboard

- **Surface:** `SpeedrunScoresActivity` — the mobile "home page" reached from the deck-picker overflow ("Speedrun scores").
- **Trigger (owner):** *"the phone ui looks so awful… make it more similar to desktop"* → *"its mainly the home page that needs redesigning."* The scores screen was a plain vertical stack of `TextView`s (a debug-dump look: `"Memory\n92% recall (90–94% band)\n13 meta cards"`, etc.) — no relation to the desktop Home's designed 3-score dashboard.
- **Fix:** replaced the `TextView` layout with a single full-bleed `WebView` that renders an HTML dashboard (`SpeedrunDashboardHtml`) reflowed to one column for phones, using the same design tokens as the desktop `SpeedrunDashboard.svelte` (spec-ui §2: paper `#F5F7FA`, ink `#1B2430`, indigo `#3E3A8C` accent, amber `#C99A2E` signature). Ports the desktop's structure: brand header + deck name, three score cards (Memory / Performance / Readiness) with the big indigo value + band chip + sub-label and the LR-only badge, a "Today's focus" card, and the full Skill map (per-type bars with Wilson-CI tick marks, `±CI` labels, weakest-first sort, amber-highlighted ★ recommended row).
- **Honesty invariants preserved (D-SR10):** no Readiness point unless `eligible` (abstain panel shows attempts/coverage + "unlocks at 200 attempts"); bands shown alongside every score; `<5`-review skills render as an empty greyed bar labeled `<5`. Logic mirrors the Svelte helpers (`pct`/`halfBand`/`overallBand` Wald/`skillPct`/`sortedSkills`).
- **Working "Start drill" button (follow-up, same session):** owner asked *"now where are my buttons to drill"* — the first cut shipped read-only. Added the desktop's indigo "Start drill →" CTA to the Today's-focus card as an `<a href="speedrun://drill">` (no JS needed) intercepted by the activity's `WebViewClient.shouldOverrideUrlLoading`. On tap it selects the **`LSAT Speedrun::Skills`** subdeck (not the parent — the parent also serves plain Meta *vocab* cards, which are "Show answer" cards, not the drill) and opens the reviewer, honouring `Prefs.isNewStudyScreenEnabled` exactly like `IntentHandler.handleReviewIntent`. Verified: lands straight in a commit-then-reveal drill (stimulus + PREPHRASE box + "Reveal choices"/Skip + hidden choices).
- **Follow-up (DI-SR13):** the mixed/timed/blind session launchers were subsequently built as `SpeedrunSessionActivity` (D-SR44). Targeted-by-skill remains the one unported mode.
- **Gotchas fixed while building:** decimal formatting forced to `Locale.US` (a locale comma would emit invalid CSS like `left:12,3%`); `<meta viewport>` so the WebView lays out at device width; loaded via `loadDataWithBaseURL(null, …)`.
- **Verified on emulator (Pixel, arm64):** renders the full dashboard against the seeded collection — Memory 92% ±2 / Performance 69% ±6 / Readiness 165 · 152–175 (Low confidence, 100% covered, "not LSAC equating" disclaimer), Today's focus = Principle family (57%), and all 13 `type::*` skill-map rows with CI ticks. Matches the desktop visual language.
- **Files:** `~/dev/droid/Anki-Android/AnkiDroid/.../speedrun/SpeedrunDashboardHtml.kt` (new), `.../speedrun/SpeedrunScoresActivity.kt` (WebView load), `.../res/layout/activity_speedrun_scores.xml` (WebView).

### DI-SR11 — AnkiDroid: hide the Show-answer bar + ease buttons during a Speedrun drill (match desktop flow)

- **Surface:** AnkiDroid new study screen (`ReviewerFragment`/`ReviewerViewModel`), Speedrun drill.
- **Trigger (owner):** the mobile reveal showed both our "Next question →" *and* AnkiDroid's Again/Hard/Good/Easy; the question side showed a "Show answer" bar. Desktop has none of these — the MC commit is the graded signal.
- **Why off-model:** the Speedrun drill is self-grading — committing a choice sets the rating (`ratingForCommitted` → Good/Again) which "Next question →" (`speedrun:continue` → `answerCard`) applies. The ease buttons let the user override with self-rated ease, and the "Show answer" bar is a no-op path for a drill (you reveal by committing). Both are redundant/confusing.
- **Fix:** added `ReviewerViewModel.speedrunDrillActiveFlow` (set from `speedrunSession.isActive` right after `prepare` in `loadCard`); the fragment collects it and hides `binding.answerArea` (a single view that renders *both* the Show-answer bar and the ease buttons) while a drill card is showing. Non-drill cards are unaffected.
- **Verified on emulator:** question side has no Show-answer bar (reveal via "Reveal choices"/commit); reveal side has no ease buttons, only "Next question →", which advances the queue and applies the MC-derived rating. Matches the desktop single-flow drill.
- **Files:** `~/dev/droid/Anki-Android/AnkiDroid/.../ui/windows/reviewer/ReviewerViewModel.kt` (flow), `.../ReviewerFragment.kt` (`setupAnswerButtons`).

### DI-SR10 — AnkiDroid: kill the "box in a box" so the drill reads like the desktop panel

- **Surface:** AnkiDroid new study screen, Speedrun drill CSS (`SpeedrunHtml.sharedCss` phone media query).
- **Trigger (owner):** "the phone ui looks so awful … make it look more similar to desktop."
- **Root cause:** the host reviewer already draws a white **card frame** around the WebView (Frame style: Card). Our drill then nested *another* surface inside it — `.sr-drill` grey `#F5F7FA` background → `.sr-main` white bordered/rounded card — so the phone showed a card-in-a-card with wasted top margin and squeezed width. Desktop renders our single `.sr-main` card directly on the paper background, so it never had the nesting.
- **Fix:** in the `@media (max-width:640px)` block, made `.sr-drill` background transparent (no paper layer, minimal padding) and `.sr-main` borderless/transparent/zero-padding, so content sits directly on the reviewer's own frame — one clean panel, full width, matching the desktop single-panel feel. Rail cards keep a subtle `#f6f7fb` fill so they still read as distinct when stacked below. Verified on the emulator across prephrase / choices / reveal.
- **Files:** `~/dev/droid/Anki-Android/AnkiDroid/.../speedrun/SpeedrunHtml.kt`.
- **Still open (see below / backlog):** the reveal view shows both our "Next question →" (applies the MC-derived rating) *and* AnkiDroid's Again/Hard/Good/Easy (self-rated ease) — redundant and off-model; desktop has no ease buttons. And mobile has **no drill-mode picker** (targeted-skill / mixed / timed / blind) — those live only in the desktop Home (WP-20/22/25), never ported to Android.

### DI-SR9 — AnkiDroid: prephrase self-check buttons dead (innerHTML `<script>` never runs)

- **Surface:** AnkiDroid new study screen, Speedrun reveal view — the "👍 Yes / 👎 Not quite" PREPHRASE SELF-CHECK buttons.
- **Trigger (owner, emulator):** "the yes and no are not clickable on android."
- **Root cause:** the buttons called `srSelfCheck('yes'|'no')`, a function defined in an inline `<script>` appended to the self-check HTML. The new study screen injects the drill via `document.getElementById('qa').innerHTML = …`, and **`<script>` tags don't execute when inserted via `innerHTML`** — so `srSelfCheck` was never defined and the clicks were no-ops. (Inline `onclick` attributes *do* run when added via innerHTML, which is why the choice/commit/trap buttons — all `window.location.href='speedrun:…'` — worked.) Same root cause as the never-running prephrase autofocus `<script>`.
- **Fix:** inlined the toggle logic straight into the buttons' `onclick` attributes and dropped the `<script>` (`SpeedrunHtml.buildPrephraseSelfCheck`). Verified on the emulator: typed a prediction → reveal → commit → **Yes** now reveals "Nice — your prediction was on track."
- **Files:** `~/dev/droid/Anki-Android/AnkiDroid/.../speedrun/SpeedrunHtml.kt` (`buildPrephraseSelfCheck`).

### DI-SR8 — AnkiDroid: prephrase typing hijacked by reviewer key-shortcuts (new study screen)

- **Surface:** AnkiDroid new study screen (`ReviewerFragment`/`ReviewerViewModel`), Speedrun prephrase `<input>`.
- **Trigger (owner, on emulator w/ hardware keyboard):** "android currently doesn't allow type or scroll." On-device triage:
  - **Scroll** already works on the new screen — a vertical swipe on a long choices/reveal view scrolls natively (the reviewer's touch listeners are `{passive:true}`, so they never block native scroll). No change needed.
  - **Typing** was broken: the prephrase input *focused* fine (cursor + IME widget), but each keystroke fired a **reviewer shortcut** instead of entering text — e.g. `a` opened the Note editor, other keys jumped to Statistics.
- **Root cause:** `ReviewerFragment.dispatchKeyEvent()` only bailed out (letting the key reach the focused view) for the **native** type-answer `EditText` (`typeAnswerEditText.isFocused`). For a text input *inside the card WebView* it fell through to `bindingMap.onKeyDown()`, which consumed the key as a shortcut before the WebView saw it. The `ReviewerViewModel.isInputFocused` flag (set by the `focusin`/`focusout` posts from `ankidroid-reviewer.js`) already tracked WebView-input focus but was only consulted in `processAction`, which `dispatchKeyEvent` bypasses.
- **Fix:** exposed `ReviewerViewModel.isInputFocused` (public read) and added it to the `dispatchKeyEvent` early-return guard, mirroring the `typeAnswerEditText` exemption. Verified end-to-end on the emulator: typed *"saves money longterm"* into the prephrase field → **Reveal choices** → commit **C** → the **PREPHRASE SELF-CHECK** shows *Your prediction: "saves money longterm"*, correct grading + answer buttons intact.
- **Files:** `~/dev/droid/Anki-Android/AnkiDroid/.../ui/windows/reviewer/ReviewerViewModel.kt` (expose flag), `.../ReviewerFragment.kt` (`dispatchKeyEvent` guard).
- **Note (B051):** this fix is **new-study-screen only**. The legacy `Reviewer` has no WebView-input focus signal (its `answerFieldIsFocused()` checks the native EditText), so prephrase typing there is still hijacked — steer mobile Speedrun to the new study screen (`newReviewerOptions`).

### DI-SR7 — AnkiDroid: scores scoped to LSAT Speedrun + new-study-screen drill verified (closes B050)

- **Surface:** AnkiDroid `SpeedrunScoresActivity` + new-study-screen reviewer (`ReviewerViewModel`, `newReviewerOptions` on).
- **Trigger:** the two DI-SR6 follow-ups (B050), verified on the arm64 Pixel emulator.
- **Fix 1 (scores scope):** `SpeedrunScoresActivity` scored `decks.current()` — usually the empty **Default** deck (reported "No LSAT Meta cards" / 0%). Now resolves the Speedrun deck like desktop `_find_speedrun_deck_id`: `decks.idForName("LSAT Speedrun")` → `allNamesAndIds().firstOrNull { startsWith }` → `current()` fallback. On-device the panel header now reads **"LSAT Speedrun"** with 13 meta cards / 8 attempts / `type::flaw` next (the dashboard RPC aggregates the deck's subtree, so Meta cards under `LSAT Speedrun::Meta` count).
- **Fix 2 (new study screen):** **no code change needed.** Enabled `newReviewerOptions` and re-ran the drill: prephrase → **Reveal choices** → commit **D** → "✓ Correct! You chose D." + per-choice rationale + Again/Hard/Good/Easy all render. The new reviewer injects the drill via `eval` into the **already-loaded** persistent WebView's `#qa`, so it never hits the null-WebView path the legacy `Reviewer` did — the `recreateWebView()` guard from DI-SR6 Fix 1 is legacy-only by design.
- **Files:** `~/dev/droid/Anki-Android/AnkiDroid/.../speedrun/SpeedrunScoresActivity.kt` (deck resolution).

### DI-SR6 — AnkiDroid drill rendered blank + desktop-layout cramped on phone (on-emulator verify)

- **Surface:** AnkiDroid legacy `Reviewer` WebView (skill/drill cards).
- **Trigger (on-device verify, arm64 Pixel emulator):** after wiring the self-hosted sync so the LSAT deck was on the phone, opening a **Skills** card showed a **completely blank card frame** (Meta vocab cards rendered fine). Not a renderer crash — a `uiautomator` dump showed `id/flashcard` had **no WebView child at all**, and logcat confirmed the drill HTML *was* generated (`AndroidCardRenderContext: content card = …sr-prephrase-input…`).
- **Root cause:** the normal `displayCardQuestion()` path calls `setInterface()` → `recreateWebView()`, which **creates and attaches** the card WebView (`cardFrame.addView(webView)`); `loadContentIntoCard()` is a no-op when the WebView is null. The Speedrun drill path (`Reviewer.displayCardQuestion` → `displaySpeedrunHtml()` → `updateCard()`) `return`ed **before** ever calling `super`/`setInterface`, so on the first card of a session (WebView destroyed on leaving the reviewer) there was no WebView to load into.
- **Fix 1 (blank):** `displaySpeedrunHtml()` now calls `recreateWebView()` before rendering, mirroring the normal path (`AbstractFlashcardViewer.kt`). Verified end-to-end on the emulator: prephrase → **Reveal choices** → commit **D** → graded reveal ("✓ Correct! You chose D." + per-choice "Why correct").
- **Fix 2 (layout):** the desktop **two-column** drill (`.sr-main` + fixed `width:220px` `.sr-rail`) squeezed the stimulus to ~one word per line on a phone. Added a `@media (max-width:640px)` rule in `SpeedrunHtml.kt` that stacks the rail below the main column (`flex-direction:column; .sr-rail{width:auto}`); desktop two-column unchanged.
- **Files:** `~/dev/droid/Anki-Android/AnkiDroid/.../AbstractFlashcardViewer.kt` (`displaySpeedrunHtml`), `.../speedrun/SpeedrunHtml.kt` (`sharedCss` media query).
- **Follow-up (B050, resolved in DI-SR7):** `SpeedrunScoresActivity` showed scores for the **Default** deck (empty → "No LSAT Meta cards"), not `LSAT Speedrun`; the new-study-screen (`ReviewerViewModel`) drill path was not yet re-verified on device.

### DI-SR5 — AnkiDroid Speedrun drill surface (WP-8/WP-15)

- **Surface:** AnkiDroid reviewer + deck picker scores.
- **Trigger:** WP-8/15 — phone showed stock Anki UI with only the backend swapped.
- **Changes:** Ported commit-then-reveal to Kotlin (`SpeedrunHtml.kt`,
  `SpeedrunReviewSession.kt`); hooked legacy `Reviewer.kt` + new study screen;
  `SpeedrunScoresActivity` (three-score + abstain); `just sync-server` +
  `tools/speedrun/sync/sync_test.py`.
- **Files:** `~/dev/droid/Anki-Android/.../speedrun/*`, `libanki` wrappers,
  `tools/speedrun/sync/`.

### DI-SR4 — Home: session cards made obviously clickable + actions moved above stats

- **Surface:** Speedrun Home (`ts/routes/speedrun-dashboard/SpeedrunDashboard.svelte`).
- **Trigger (owner, live GUI):** *"it's not obvious I can click the Mixed set / Timed section cards… it should be swapped with the stats."*
- **Changes:**
  1. **Clickability.** The Mixed/Timed/Blind cards were `<button>`s but read as flat panels. Added an **"OR CHOOSE A SESSION"** eyebrow label above them, a resting drop-shadow, a hover **lift** (`translateY(-2px)`) + stronger shadow, and a bolder **indigo arrow** that slides right on hover (was a muted grey `→`).
  2. **Actions-first reorder (owner chose "sessions up, scores down").** Home now stacks **Today's focus → session launchers → the 3 score cards (Memory/Performance/Readiness) → Skill map**, i.e. the two "stats" sections drop below the actionable ones. Implemented by making `.sr-home` a flex column and giving `.sr-score-row { order: 4 }` and `.sr-skillmap { order: 5 }` — no markup moved (lower-risk than relocating the ~90-line score block). Header stays first; all other sections keep DOM order.
- **Note:** this pushes the signature three-score cards below the fold-ish; it was the owner's explicit call (actionable prominence > score prominence on the home).
- **Tests/lint:** svelte lint clean. **Needs owner live-GUI confirm** (CSS-only reorder + affordance).
- **Ref:** D-SR33/D-SR35 (home = study-plan + sessions), spec-ui §3.1.

### DI-SR3 — Drill hides the question type/skill until commit; prephrase prompt reworded

- **Surface:** the LR drill (`qt/aqt/speedrun.py` — `build_prephrase_html`, `build_choices_html`, `_rail_tip_html`).
- **Trigger (owner, on live GUI after the B036 fix):** *"the UI shouldn't show what flaw family it is in"* and *"'what must the right answer do' isn't correct phrasing unless you're asking the thinking process."*
- **Changes:**
  1. **Type/skill withheld pre-commit.** The `type::flaw` chip under the stimulus and the right-rail taxonomy card (`type::…` / `skill::…`) were shown during prephrase **and** choices — a spoiler, since identifying the question type from the stem is itself the skill (and on a *mixed* set it gives the game away). Removed both from the pre-commit views; the tags are now revealed only in `build_reveal_html` as post-answer feedback. The rail keeps a **generic, non-spoiling tip** ("read the stem, name the type in your head, then predict…"); the tip no longer names the skill ("as your score rises").
  2. **Prephrase prompt reworded.** "In one line, what must the right answer do?" → **"In one line, predict what the correct answer must say."** ("do" fit strengthen/weaken/assumption but not flaw/inference/main-point; the new wording is type-neutral and clearly a *prediction* — the generation step, not the answer). Placeholder → "e.g. jot your prediction before you look…".
  3. **Elapsed clock now ticks live** (owner: *"time is also not running?"*). `_build_progress_header` previously injected a JS ticker only for **timed** mode; other drills showed a **static** elapsed snapshot that only updated on page transitions (so it looked frozen while sitting on a question). Now all modes render a live JS ticker, **seeded with an `elapsed_seconds` ms offset** (`Date.now() - offset`) so the clock is continuous across prephrase→choices→reveal→next (also fixes the timed clock, which previously reset to 0 each question). Timed = amber/bold, others = muted.
  4. **Reveal-screen fixes (owner, round 2):**
     - *"type::flaw still shows up"* — the reveal still rendered the raw `type::flaw` chip under the verdict and a `type::flaw skill::conclusion-id skill::abstraction` rail card. Removed both; replaced with a plain-English **"WHAT THIS TESTED"** card (e.g. "Flaw" · "Conclusion ID, Abstraction") via new `_human_tag` / `_reveal_tested_html`. No raw `type::`/`skill::` code strings anywhere in the user-facing UI now.
     - *"if you got it wrong it shouldn't ask 'did your prediction match'"* — the prephrase self-check showed 👍/👎 "Did your prediction match the key?" even on a miss. Now gated on `is_correct`: **correct** → keep the yes/no self-check; **wrong** → drop it, show the prediction + a reflective "compare with the correct answer — where did your reasoning diverge?" prompt.
     - *"name the trap is not intuitive"* — clearer copy ("Answer C is a classic wrong-answer trap. Diagnose your miss: tap the trap type you think it is."), references the committed letter, and the clickable chips now carry `cursor:pointer` (they had no pointer affordance).
     - Tests: added pre-commit-hidden / reveal-human-readable / self-check-gating cases; 66 qt Speedrun tests green, lint clean.
  5. **Trap slugs explained + realigned to taxonomy (owner: *"the traps are two-word slugs and not intuitive"*).** Added `TRAP_DESCRIPTIONS` — a one-line plain-language gloss per trap (e.g. *Half true → "Partly right, but leaves out or distorts a key part."*). Now surfaced in three places: the per-choice "Trap category" line (label + gloss), a `title` tooltip on each chip, and the post-tap result which names **and defines** the actual trap on the chosen answer. **Bug found + fixed while doing this:** `TRAP_DISPLAY_NAMES` had drifted from `taxonomy.json` — it was missing `contradicts`, `wrong-direction`, `false-dichotomy`, `appeal-authority`, `false-analogy` (all used by real items → they rendered as bare title-cased slugs with no gloss) and carried five tags that don't exist in the taxonomy (`false-dilemma`, `appeal-to-authority`, `ambiguity`, `missing-link`, `negation-error`). Both maps are now exactly the taxonomy's 19 canonical slugs; verified every trap used by the item pool has a label + gloss. 67 tests green, lint clean.
- **Not changed:** the targeted-drill **session header** ("Flaw family · drill") still names the focus, because a targeted drill is a deliberate single-skill practice the learner explicitly chose (mixed/timed headers don't name a type). Can be genericized later if a fully "blind" drill mode is wanted.
- **Tests:** added `test_question_type_and_skill_hidden_precommit` + `test_type_revealed_after_commit`; 63 qt Speedrun tests green, lint clean. **Needs owner live-GUI confirm.**
- **Ref:** refines D-SR34 / spec-ui §3.2 (the rail's taxonomy tags now belong to the reveal, not the commit phase).

### DI-SR2 — Synthetic item-pool quality audit: fixed answer-position + length tells

- **Surface:** the synthetic LSAT Item pool (`tools/speedrun/deck/items/type-*.json`, 155 items).
- **Trigger:** owner asked to "audit the synthetic pool and ensure the questions are creative, high quality."
- **What the audit found (programmatic scan across all 155 items):**
  1. **Answer-position skew (serious, gameable):** correct answers were **A=97 / B=38 / C=14 / D=6 / E=0** — 63% "A" and **"E" never correct**; five files (evaluate, justify, paradox, principle, weaken) were **100% "A"**. A test-taker could game the pool by always guessing A.
  2. **Length tell (serious):** the correct choice was the **longest option in 80%** of items; **15 items ≥1.8×** the mean distractor length (worst 2.3×) — pick-the-wordiest scored ~80%.
  3. Substantive writing was otherwise **sound** — spot-read principle/weaken/flaw items: valid logic, plausible half-true/scope distractors, varied topics. Minor topic over-use (museum 11, company 13). Difficulty narrow (L2–L3; only 4×L1, 2×L4, 0×L5).
- **Fixes applied:**
  - **Rebalanced positions** via a deterministic per-`_id` reshuffle (moved each `Choice`/`WhyWrong`/`TrapChoice` triple together, rewrote `CorrectChoice`; content unchanged). Now **A=35 / B=37 / C=25 / D=23 / E=35**. (Confirmed no answer-letter cross-references in any choice/explanation text first.)
  - **Enriched thin distractors** in the 9 worst length-tell items (evaluate-006/010, flaw-006/011, justify-007, method-008, parallel-008, principle-011, weaken-008) — made wrong answers fuller/more plausible rather than trimming the correct answer.
  - **Added a durable validator guard** (`item_validator.py`): warns when the correct choice is ≥1.9× the mean distractor length, so future items can't regress. Pool now validates **0 errors / 0 warnings**; 85 deck tests green.
- **Residual (accepted / follow-up):** median correct/distractor length ratio is **1.37×** (mild, arguably realistic) and "strictly longest" is still 78% by ≤1–2 words — not practically gameable and now guarded at the 1.9× threshold.
- **Constraint honored:** all changes are to *our own synthetic content*; reorder is position-only (no logic change); validator addition is additive.
- **Follow-up done (same session):** authored **8 hard (L4–L5) items** on fresh, single-field topics with light domain framing — astronomy (light-travel time), historical linguistics (living/dead language equivocation), marine ecology (otter/kelp/urchin trophic cascade), archaeology (sealed-chamber quantifier chain), behavioral economics (loss-aversion deposit vs. reward), paleontology (volcanism-vs-extinction causation), materials/geometry (three-step categorical chain), philosophy of mind (causation vs. coercion). Pool now **163 items**; difficulty spread **L1×4 / L2×83 / L3×66 / L4×6 / L5×4** (was 0×L5); positions stay balanced **A35 B38 C28 D26 E36**; 0 warnings, 85 tests green. Topic reuse (museum/company) not added to. Deeper difficulty (more L4–L5) and further topic diversification remain ongoing authoring work.

### DI-SR1 — Stats page reskin, converging on the drill's visual language

- **Surface:** desktop Statistics page (`ts/routes/graphs/`), shown via the
  Speedrun Home "Stats" action. Gated on `body.speedrun-stats` (set only by the
  Speedrun shell, `?sr=1`) so stock Anki is untouched.
- **Goal:** the Stats page should read as the *same app* as the practice-questions
  (drill) UI — same palette, type, cards — not as raw Anki charts.

**Iteration trail (owner feedback each round):**

1. **CSS-only reskin (WP-27).** Overrode Anki's CSS tokens (`--canvas`,
   `--border`, `--fg`, radius) + styled `TitledContainer`/`RangeBox` under
   `body.speedrun-stats`. → *"see how nothing changed"*: token overrides didn't
   penetrate Svelte-scoped components.
2. **Scoped component styling.** Moved card/heading styles directly into
   `TitledContainer.svelte` via `:global(body.speedrun-stats) …`. → *"mildly
   better? but the font is bad… make it similar to the practice questions UI."*
3. **Typography pass.** Card titles → Georgia serif; body → grotesk. → *"these
   two clearly have a different style."*
4. **Chart recolor + heading regrammar (this round).** Owner granted full
   permission to change Anki fonts/colors ("just don't randomly delete their
   stuff"). Root causes of the residual mismatch were (a) the **hardcoded D3
   chart colors** (bright-blue pie, multicolor legend) that CSS can't reach, and
   (b) **serif card titles**, a treatment that never appears in the drill.
   - **Card Counts** pie + legend → `speedrunBarColours` (indigo/amber/clay/
     green/muted), `ts/routes/graphs/card-counts.ts`.
   - **Reviews** bars/series → indigo·green·amber·clay light→saturated ramps,
     `ts/routes/graphs/reviews.ts` (`binColor`).
   - Card titles: Georgia serif → the drill's **mono uppercase eyebrow**
     (matching `type::flaw` / `PREPHRASE`), `TitledContainer.svelte` +
     `graphs-base.scss` (kept in sync).
   - `--state-new/learn/review` tokens → drill palette (TodayStats numbers).
5. **Heading font correction.** → *"the font is horrible"*: uppercase bare
   monospace reads clunky for section titles. Root fix: match the drill's
   **prominent grotesk heading exactly** — the indigo prompt "In one line, what
   must the right answer do?" (`speedrun.py`): stack `-apple-system,
   BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`, weight 700, ~1.05rem,
   indigo, sentence case, normal tracking. Also aligned the **body font stack**
   to the same (dropped "Inter", which was rendering differently from the drill).
   (Earlier "grotesk bad" round used an Inter stack + tight tracking + small size
   — the family wasn't the problem; the treatment was.)

6. **Deck scoping removed entirely for Speedrun stats** (owner thread: *"what is deck vs collection?"* → *"what does 'this deck' mean?"* → *"oh, you pick a deck at the bottom — make it obvious"* → chose **auto-show-all, no deck-picking**). The *deck concept itself* has no meaning in Speedrun's one-study-plan model, and `deck:current` can scope to an empty "Default" deck (→ NO DATA). Final decision: the Speedrun stats **always show all the learner's study, with no deck controls at all**:
   - `RangeBox.svelte` (`?sr=1`): hide the deck/collection radios + `deck:current` search box; force scope to the whole collection.
   - `stats.py` (`SPEEDRUN_SHELL`): hide the Qt `DeckChooser` footer button (`f.deckArea`) — it was the *other* deck picker and would otherwise be a prominent dead control once scope is forced.
   - Stock Anki (no `?sr` / `SPEEDRUN_SHELL=False`): both controls untouched (incl. the `statisticsSearchText` id AnkiDroid relies on).
   - Svelte + Qt lint clean; needs `just rebuild-web` + live-GUI confirm.

- **Palette source of truth:** `spec-ui.md §2` / `qt/aqt/speedrun.py` constants
  (`_C_INDIGO #3E3A8C`, `_C_GREEN #2E7D5B`, `_C_CLAY #B4472E`, `_C_AMBER #C99A2E`,
  paper `#F5F7FA`, ink `#1B2430`).
- **Remaining (B042):** calendar heatmap + the less-visible graphs (intervals,
  ease, difficulty, retrievability, stability, hourly, buttons, added, future-due)
  still use Anki's default d3 colors — mostly empty on the demo deck; retheme the
  same way (class-gated) when polishing.
- **Constraint honored:** additive + reversible; no Anki stats content/graphs
  removed; stock Anki unaffected (no `speedrun-stats` class → default colors).
