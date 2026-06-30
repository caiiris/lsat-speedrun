# LSAT Speedrun BrainLift

*Iris Cai*

## Owners

- Iris Cai

## Purpose

### Purpose statement

A research-grounded theory of how an LSAT prep tool should build *reasoning skill* instead of rote recall, used to design an app for college students. The modern LSAT (post-2024, with Logic Games removed) mostly measures fluid relational reasoning, working-memory management, and cognitive endurance; content knowledge matters little. The study methods with the strongest evidence (interleaving, Blind Review, spaced retrieval) center on disciplined retrieval and metacognition more than on flashcard memorization. The tool should follow what learning science supports while staying inside what AI can do safely. For example, it should not try to generate LSAT items on its own.

### Target learner / persona

A college student preparing for the LSAT.
The neuroplasticity research suggests early adulthood is a favorable window for this kind of training, which fits a college-age audience.

### Scope & phasing

- **LR-first (the core build).** Logical Reasoning is the cleanest part to tag and space, since it comes in discrete stimuli with a stem-derivable type taxonomy and a known flaw catalog, and it breaks down naturally into SRS units. It also has the most clearly defined expert method (see Category K), which makes it the right place to start.
- **RC is phase 2, using the same engine.** RC questions are also keyed MCQs with catalogable traps, and they overlap heavily with LR (the sections correlate ∼0.74; inference, main-point, and strengthen/weaken questions appear in both). The RC-specific work is mostly treating the passage as shared context for a question cluster and handling local dependency (E.1). So RC question practice extends the LR engine and can wait for phase 2.
- **Daily reading is the fluency substrate beneath both sections.** The daily active-reading module (I.4) trains the reading skill (structure, register, working-memory load) that RC and LR both rest on. It does not stand in for RC question types. Source it from RC-style passages so it pre-trains the RC substrate and feeds the vocab deck from day one, and keep "daily reading" distinct from "covering RC."

## DOK 4: Spiky Points of View

### The Spiky POV: Don't train reading comprehension for the LSAT. Train *reading*.

**Stop drilling reading comprehension.** Logical Reasoning is ∼66% of the scored test (two sections to RC's one), and its question types are well-defined and close to deterministic, derivable from the stem and convergent across prep companies into roughly 13 types with a teachable method. That's where structured practice and an SRS engine get purchase, whereas RC is fuzzier and gives the least return per hour when drilled in isolation. Splitting time evenly over-invests in the smaller, softer half. (PowerScore / Killoran & Denning; LSAC format; Insight 3; App-design stance D3.)

**Reading comprehension is a knowledge problem: reading widely fixes it better than drilling problems.** LSAT takers are overwhelmingly humanities majors, and what usually sinks them on a dense biochemistry, economics, or philosophy passage is unfamiliarity with the register and content, which burns the working memory they should spend on the reasoning. The cure is broad background familiarity, built by reading widely across unfamiliar domains so fewer passages are foreign in the first place. The evidence supports the mechanism: in Recht & Leslie's "baseball study" (1988) topic knowledge mattered more than measured reading ability, a 2021 review of 23 studies agrees, and Cunningham & Stanovich (1998) show reading volume itself builds the vocabulary and knowledge comprehension rests on, even controlling for intelligence. So train the reader: make wide reading across domains a daily produce-after-reading habit, which an SRS queue is built to sustain, and let comprehension follow.

- Why it's spiky: it rejects two defaults at once, the "grind RC questions" default and the "reading ability is fixed, so cram a content glossary" default. It also resolves an apparent tension with Insight 5 (the test is self-contained, so content knowledge earns no points directly). Reading widely isn't there to supply facts for answering questions; it lowers parsing load so working memory goes to the reasoning (Sweller CLT; Bunge fluency/efficiency). The point is reading as load-reduction.
- Caveat: the direct evidence comes from general reading science (mostly K-12 and developmental), not from LSAT-specific trials, so applying it to the LSAT is the argued conviction. The CLT mechanism (familiarity frees working memory) and the LR-leverage math make it a defensible bet, and the daily-reading module is cheap to run. (Recht & Leslie 1988; Cunningham & Stanovich 1998; Sweller; Bunge & Mackey; Insights 5, 6.)

## Experts

### 1. Dr. Silvia Bunge & Dr. Allyson Mackey (UC Berkeley)

- Who: Cognitive neuroscientists; Bunge Laboratory, UC Berkeley.
- Focus: Neuroplasticity from intensive reasoning training. A DTI and fMRI study of ∼100 hours of LSAT prep showed white-matter changes, and related eye-tracking work looked at visual-cognitive efficiency in relational reasoning.
- Why follow: Evidence that LSAT prep physically reshapes fronto-parietal reasoning networks and that gains transfer to novel relational tasks. This grounds the claim that the tool trains fluid reasoning rather than only test familiarity.
- Where: Frontiers in Neuroanatomy (2012); npj Science of Learning (2018).

### 2. John Sweller

- Who: Educational psychologist; originator of Cognitive Load Theory.
- Focus: Intrinsic, extraneous, and germane cognitive load, and how schemas form.
- Why follow: Explains why automating recognition of logical structures frees working memory, and why extraneous load (bad UI, anxiety, time pressure) directly costs accuracy. This informs minimal-friction design.

### 3. Daniel Kahneman & Amos Tversky

- Who: Cognitive psychologists; Dual-Process Theory.
- Focus: System 1 (fast, intuitive, bias-prone) versus System 2 (slow, analytical).
- Why follow: The LSAT is engineered to exploit System 1 through distractor answers, and effective prep trains System 2 until it runs at System 1 speed. This frames what "getting better" actually means.

### 4. Philip Johnson-Laird (Mental Model Theory)

- Who: Cognitive scientist; originator of Mental Model Theory (MMT).
- Focus: Deduction as a largely nonverbal process of building and manipulating spatial mental models in working memory, instead of applying formal logical rules.
- Why follow: Suggests the biggest gains come from training underlying executive functions (updating working memory, sustaining focus, inhibiting heuristics) rather than from teaching "logic rules." This informs what practice should exercise.

### 5. Steven C. Hayes (Relational Frame Theory)

- Who: Psychologist; originator of Relational Frame Theory (RFT), the basis for SMART training.
- Focus: Arbitrarily Applicable Relational Responding (AARR), which covers mutual entailment, combinatorial entailment, and transformation of stimulus functions; and SMART (Strengthening Mental Abilities with Relational Training).
- Why follow: AARR maps closely onto LR demands, and intensive relational training has shown IQ and non-verbal reasoning gains, which supports the idea that these skills are trainable. One caveat: far-transfer effects diminish in older adults, so the early-adulthood window matters.

### 6. Roediger & Karpicke; Bjork & Bjork; Slamecka & Graf; Rohrer & Taylor (spacing / retrieval / generation / interleaving)

- Who: The canonical learning-science researchers behind the mechanisms an SRS app rests on.
- Focus: Testing effect and retrieval practice (Roediger & Karpicke, 2006); desirable difficulties and storage-vs-retrieval strength (Bjork & Bjork); the generation effect (Slamecka & Graf, 1978); interleaving and the discriminative-contrast benefit (Rohrer & Taylor).
- Why follow: These justify the whole engine: why retrieval beats rereading, why interleaving beats blocked drilling, and why the student has to produce something (the basis for the daily reading module's "produce a structural map" step). The generation effect is the main reason reading practice can't be passive.
- Where: Science 2006 (test-enhanced learning); JEP:HLM 1978 (generation effect).

### 7. Liangming Pan et al. — Logic-LM (neurosymbolic reasoning)

- Who: NLP researchers; "Logic-LM: Empowering LLMs with Symbolic Solvers for Faithful Logical Reasoning" (EMNLP Findings 2023, arXiv:2305.12295).
- Focus: The LLM translates a problem into a symbolic form, then a deterministic solver (Z3, etc.) computes the answer. The paper reports +39.2% over standard prompting and +18.4% over CoT.
- Why follow: A foundational pattern for moving correctness off the model and onto a verifier. It grounds the "code/solver owns correctness" stance for any formalizable content.
- Where: arXiv:2305.12295.

### 8. Mohammad Raza & Natasa Milic-Frayling — Semantic Self-Verification (verified-subset architecture)

- Who: QCRI researchers; "Instantiation-based Formalization of Logical Reasoning Tasks" / SSV (arXiv:2501.16961, 2025).
- Focus: The model generates concrete test-case instantiations, the solver checks that the formalization is consistent with them, and it returns a near-certain `isVerified` flag. Across logical-reasoning benchmarks, verification precision is around 100% on the subset it can verify, and it stays near 97% even on weaker models, which supports tiered cheap-then-expensive routing.
- Why follow: A blueprint for a high-precision correctness signal and the "auto-serve only the verified subset, route the rest to a human" design. One caveat: it only works for content that formalizes cleanly into solver constraints. Current LR/RC (argument structure, unstated assumptions, natural-language nuance) doesn't, so use it where it fits and rely on the answer key elsewhere.
- Where: arXiv:2501.16961.

### 9. Miles Turpin et al.; Anthropic (chain-of-thought faithfulness)

- Who: "Language Models Don't Always Say What They Think" (arXiv:2305.04388, 2023); Anthropic, "Reasoning Models Don't Always Say What They Think" (2025).
- Focus: A model's stated chain-of-thought can be plausible while still being unfaithful, meaning it doesn't reflect the actual cause of the answer. Biasing cues can shift answers while the explanation hides the influence.
- Why follow: The central caveat for an education product where the explanation is the deliverable. It's the reason to ground every generated explanation in the verified answer or a human rationale rather than in the model's free narration.
- Where: arXiv:2305.04388.

### 10. David Killoran & Jon Denning (PowerScore) — LR method authority

- Who: Authors of the PowerScore LSAT Logical Reasoning Bible (25+ years; the de facto standard LR methodology).
- Focus: The "Primary Objectives" method (classify the stimulus, identify the conclusion, paraphrase, prephrase, read all five choices, split Contenders from Losers, then return to the stimulus), the 13-type classification, and named per-type techniques (Assumption Negation, Justify Formula, Supporter/Defender, the Fact Test).
- Why follow: The most-used expert framework for how to attack LR. It's the scaffold the app's tutoring and diagnosis should encode, and the source of the question-type taxonomy and the prephrasing (predict-before-you-read) step.
- Where: PowerScore LSAT Logical Reasoning Bible (2024–25 / 2026–27 eds.); PowerScore LSAT blog/forum.

### 11. Recht & Leslie; Cunningham & Stanovich (reading science — background knowledge & print exposure)

- Who: The reading-comprehension researchers behind the "knowledge drives comprehension" and "reading volume drives verbal skill" findings.
- Focus: Recht & Leslie (1988), the "baseball study," found that topic background knowledge predicted comprehension and recall more than measured reading ability did, so knowledge can compensate for weaker reading skill; a 2021 review of 23 studies (Smith et al.) corroborates this. Cunningham & Stanovich (1991; "What Reading Does for the Mind," 1998; "Where does knowledge come from?", 1993) found that print exposure and reading volume uniquely predict vocabulary, general knowledge, and verbal skill, even after controlling for general intelligence.
- Why follow: The empirical backbone of the Spiky POV's second move. Comprehension is downstream of knowledge and reading volume, so the lever for RC is reading widely rather than RC drills. Note that applying these to the LSAT is an extrapolation, since they're general and developmental-reading studies, made via the CLT load-reduction mechanism.
- Where: Journal of Educational Psychology (Recht & Leslie 1988; Cunningham & Stanovich 1991, 1993); American Educator (Cunningham & Stanovich 1998).

## DOK 3: Insights

- **Insight 1 — For LR/RC the binding reliability question shifts from "can the AI solve it" to "is the AI's explanation faithful," which is a softer and more guardable bar.** Since the key is known, the model's job is explaining and diagnosing, which can be grounded in the keyed answer, checked for giveaway, and where it matters anchored to a human rationale. Its free narration still isn't trustworthy on its own. (Turpin et al.; Anthropic 2025; Phung et al. validator 60–66% to 94–98%; the GPT-4-ITS 35% giveaway result.)
- **Insight 2 — The flashcard is the wrong primitive for a reasoning test, so space the skill and the trap instead of the literal item.** Naive SRS on a real LR item trains "the answer is C," which is performance rather than learning. The fix is to make the spaced unit a question-type, reasoning-skill, or trap, and to serve a fresh item when it comes due, which delivers interleaving for free. (Anki-frustration source; Rohrer & Taylor interleaving; Bjork performance-vs-learning; the bug-library.)
- **Insight 3 — LR is well-defined enough to tag and space, but on two axes rather than one.** Question type is close to deterministic (derivable from the stem) and converges across every major prep company (about 13 types; Flaw most common; Assumption, Flaw, and Inference together around 40%, and adding Strengthen, Weaken, Paradox, and Principle around 75%). The underlying skill (conditional, causal, or formal reasoning) is real but cross-cutting and fuzzy. So tag question type cheaply and reliably, and tag reasoning-type and trap with AI-assisted-then-human-verified labels. (PowerScore; Magoosh; Resolution Test Prep concordance; Cambridge LSAT; LawHub.)
- **Insight 4 — The flaw catalog is a behavior-first misconception engine.** LR distractors form a small, enumerable catalog of known traps. Tag each choice with its trap type once, offline, and a wrong answer becomes an automatic misconception signal with no live AI judgment, the same structure as the Probability Pirates bug library. (Brown & Burton bug-library lineage; the LR flaw-catalog sources.)
- **Insight 5 — The only flashcard-appropriate layer is the declarative meta-vocabulary, not the content.** The LSAT is self-contained: no science or philosophy term bank earns points, and outside knowledge can actively hurt. The finite logic and argument vocabulary (premise, assumption, conclusion, necessary versus sufficient), the named-flaw catalog, and the indicator and quantifier words are prerequisite, declarative, and best made automatic, which is what classic SRS is for. LSAC's own line is that you need the plain-English concepts, not the labels like "ad hominem" or "syllogism." (LSAC/LawHub; Kaplan; CLT, where automaticity frees working memory.)
- **Insight 6 — "Read widely" is a trainable daily habit, and the daily queue is Anki's core strength, but only if the student produces something after reading.** The loop is a domain-rotating daily passage, then a produced structural map (the generation effect), then light formative feedback, then a vocab harvest feeding the SRS deck. Passive reading is the nodding-is-not-knowing trap, whereas the produced map is the learning event. AI-generated passages are low-risk for reading practice, whereas AI-decided answers to attached questions are not. (Slamecka & Graf generation effect; Rohrer & Taylor; Bunge & Mackey; Sweller; the QG-reliability research.)

### App-design stances (build decisions, not reading-derived insights)

> *How to design the app, distilled into convictions. These are build decisions rather than conclusions drawn from the literature, so they sit in their own group.*

- **D1 — AI never owns correctness; its only roles are parsing, phrasing, feature extraction, and diagnosis grounded in a key.** The app must never let the model decide whether an answer is right or act as the final judge of free text. Every LR/RC item ships with a published official key, so correctness is a deterministic lookup, and the research shows models can't reliably verify their own reasoning anyway. Code and the key own correctness; the model only phrases prose around verified ground truth. The central line is augmentation over automation. (Insight 1; SSV; CoT-faithfulness; generation-vs-verification asymmetry.)
- **D2 — The spaced unit is the skill or trap, not the literal item.** Putting real LR items in a normal SRS deck trains recall of "the answer is C," which is performance rather than learning. Schedule a question-type, reasoning-skill, or trap instead, and serve a fresh item when it comes due, which also buys interleaving, the format LR/RC actually need. The brownfield move, stated plainly: keep Anki's scheduler and change what gets scheduled. (Insights 2, 3, 4.)
- **D3 — Build LR first; RC is a phase-2 extension of the same engine; daily reading is the fluency substrate beneath both.** LR carries ∼66% of the score, breaks down most cleanly into taggable SRS units, and has the most clearly defined expert method, so it's the right place to start. RC questions reuse the same keyed-MCQ, trap-tag, and Blind-Review machinery (the sections correlate ∼0.74), and they only add passage-as-cluster-context and local-dependency handling, so they extend the engine rather than form a parallel track. The daily-reading module trains the reading substrate (structure, register, working-memory load) that RC and LR both rest on, so keep "daily reading" distinct from "covering RC." (PowerScore; Manhattan RC↔LR correlation; Insights 2, 6.)
- **D4 — The inherited Anki review log is a psychometric asset; difficulty calibration starts warm rather than cold.** Direct text-only LLM difficulty estimates correlate weakly and compress the extremes, while the reliable methods use real response data. Anki already logs every review, and FSRS fits it into a per-user model of stability and difficulty. So let the LLM make a first guess and refine it against real responses, treating the inherited log as the data the difficulty literature keeps asking for. (Scarlatos/QDET; Jain extreme-compression; SMART; IRT.)
- **D5 — The expert pain points give a ready-made list of diagnosable error modes for the AI tutor to target, and several are taggable signals rather than just "wrong."** They include conclusion-misidentification (which cascades into assumption and flaw failures), contender-lock, first-seeming-right selection, skimming under time, and sufficient/necessary confusion (the most common flaw). Some are behaviorally detectable, where the chosen trap points to a specific flaw; others surface only in produced Blind-Review reasoning. The expert method itself (classify, find the conclusion, prephrase, eliminate, confirm) is a scaffold the app can prompt. The "accuracy first, speed follows mastery" principle says coach accuracy and surface the timed-vs-untimed gap rather than drilling raw speed. (PowerScore; LSATHacks; LSAT Demon; Impetus; Leland.)

## DOK 2: Knowledge Tree

### Category A: Modern LSAT structure & recent changes (2024–2026)

#### A.1: Current section composition

- DOK 1 — Facts:
  - Four 35-minute multiple-choice sections; only three scored. Plus a separately administered Argumentative Writing component.
  - Scored: two Logical Reasoning (LR) sections (∼48–52 questions total) and one Reading Comprehension (RC) section (∼26–28 questions).
  - One unscored "variable"/experimental section (LR or RC), indistinguishable from scored sections; placement not disclosed; used to calibrate future items.
  - Total MC ∼140 minutes; demands sustained cognitive endurance.
- DOK 2 — Summary: LR now dominates (∼66% of scaled score). The hidden experimental section means you must perform across the whole exam; stamina is part of the construct.

#### A.2: Elimination of Logic Games (Analytical Reasoning) & the ADA mandate

- DOK 1 — Facts:
  - Analytical Reasoning (Logic Games), 1982–Aug 2024, relied on spatial diagramming.
  - 2019 ADA settlement (disadvantaged blind candidates) → LSAC phased it out; replaced by a 2nd scored LR section from Aug 2024.
  - Psychometric research (hundreds of thousands of sessions): near-zero impact on scoring distribution and predictive validity.
  - Cognitive shift: spatial/diagrammatic pathways no longer rewarded; exam now almost exclusively rewards textual parsing + rapid verbal deduction.
- DOK 2 — Summary: The exam pivoted from spatial puzzles to verbal/relational logic. Logic-Games-era prep is obsolete.

### Category B: Cognitive processes the LSAT targets

#### B.1: Working memory & Cognitive Load Theory

- DOK 1 — Facts:
  - Working memory = limited-capacity active workspace; TBRS model: performance inversely related to load (attention captured by processing decays memory traces).
  - CLT (Sweller): intrinsic (inherent difficulty), extraneous (wasted: UI, distraction, anxiety, time pressure, un-automated strategy), germane (productive schema building) load.
  - Cognitive overload = total demand exceeds WM limits → processing stalls. Spending ∼15 sec recalling a question strategy depletes WM needed to hold the argument's variables.
  - Pupil dilation (task-invoked pupillary response) correlates with high load.
  - Mastery = automate strategies so extraneous load → ∼0, freeing 100% of WM for intrinsic difficulty.
- DOK 2 — Summary: Design must minimize extraneous load and build automatic schema; automaticity is the explicit goal.

#### B.2: Dual-process theory & System 1 subversion

- DOK 1 — Facts:
  - System 1 (fast/intuitive/bias-prone) vs. System 2 (slow/analytical/effortful).
  - LSAT engineered to overwhelm System 1 via "trap" distractors (biases, semantic proximity, real-world assumptions).
  - ∼1:20 per LR question makes pure unpracticed System 2 mathematically unsustainable; goal is to internalize System 2 operations as automated System 1 patterns (e.g. contrapositive becomes reflexive as myelination increases).
- DOK 2 — Summary: The mistake mechanism is intuition firing before analysis; training compresses deliberate analysis into fast, accurate reflex.

#### B.3: LR question types & their cognitive functions

- DOK 1 — Facts:
  - ∼24–26 stimuli per scored LR section; ∼1:20 each.
  - Types: Must Be True/Inference (deduction), Strengthen/Weaken (induction, find the assumption), Flaw (abstract the fallacy), Assumption (necessary/sufficient), Parallel Reasoning (map structure), Principle Application (rule extraction & application).
- DOK 2 — Summary: Each type maps to a distinct reasoning skill, which gives a natural skill taxonomy for adaptive practice and interleaving.

#### B.4: Reading Comprehension demands

- DOK 1 — Facts:
  - 3 single passages (∼500 words) + 1 comparative-reading set; 26–28 questions; item clusters of ∼5–8 questions per passage.
  - Tests structural reading + perspective tracking (not fact retrieval/vocabulary); requires predictive reading and holding macro-structure in WM while answering micro-level inferences.
- DOK 2 — Summary: RC is a WM + structure-tracking task analogous to briefing appellate decisions; clustering matters for both pedagogy and scoring (see E.1).

### Category C: Neuroscience of preparation (neuroplasticity)

#### C.1: White-matter microstructure (Bunge/Mackey DTI)

- DOK 1 — Facts:
  - ∼100 hrs of intensive prep over 3 months strengthens frontoparietal-network circuitry; changes absent in age/IQ-matched controls who didn't train.
  - DTI: decreased radial diffusivity (frontal-connecting white matter) and mean diffusivity (frontal + parietal white matter), consistent with increased myelination (faster signal transmission).
  - Largest score gains correlated with greatest mean-diffusivity decrease in the retrolenticular part of the right internal capsule (bridges posterior cortices and thalamus).
- DOK 2 — Summary: Good evidence that fluid reasoning is malleable in adults, which supports the claim that the tool trains underlying capacity well beyond test-taking tricks.

#### C.2: Functional efficiency & hemispheric compensation (fMRI)

- DOK 1 — Facts:
  - Deduction/language is left-hemisphere-dominant; spatial cognition right-hemisphere.
  - With training: increased frontal–parietal AND left–right hemispheric connectivity (recruiting right-hemisphere circuitry to support left-dominant deduction).
  - Reduced activation in lateral PFC (RLPFC) and IPS during reasoning → greater metabolic efficiency (faster, more accurate, less effort).
- DOK 2 — Summary: Improvement shows up as greater efficiency and the recruitment of compensatory circuitry, which goes beyond familiarity.

#### C.3: Ocular metrics & encoding efficiency (eye-tracking)

- DOK 1 — Facts:
  - Eye movements track closer to "speed of thought" than fMRI BOLD.
  - On transitive inference: ∼23 eye movements per 7-sec window; after practice, statistically significant reduction in time encoding/integrating relevant info, fixating on logical fulcrums and discarding irrelevant data.
  - Gains transferred to novel non-verbal relational tasks (domain-general).
- DOK 2 — Summary: The trained skill is faster relational encoding that generalizes, which supports practicing relational integration directly.

### Category D: Cognitive theories of deduction & relational intelligence

#### D.1: Mental Model Theory (MMT)

- DOK 1 — Facts:
  - Deduction is largely nonverbal: humans build/manipulate spatial mental models of premises rather than applying formal rules.
  - Ability to build/sustain superior mental models correlates with higher verbal-deduction accuracy.
  - Biggest gains come from training executive functions (updating WM, sustaining focus, inhibiting heuristic responses), not just teaching the "mental model" concept.
- DOK 2 — Summary: Argues that practice should load and train executive function rather than only present rules, a design principle for the tool.

#### D.2: Relational Frame Theory (RFT) & SMART training

- DOK 1 — Facts:
  - RFT core = Arbitrarily Applicable Relational Responding (AARR): deriving relations from contextual cues, not physical properties.
  - AARR properties mirror LR: mutual entailment (A>B ⇒ B<A), combinatorial entailment (A>B, B>C ⇒ A>C), transformation of stimulus functions.
  - SMART (Strengthening Mental Abilities with Relational Training) uses multiple-exemplar training of frames (same/different, before/after, contains/within); shown to raise IQ and non-verbal reasoning in children/young adults.
  - Far-transfer effects diminish in older adults; the neuroplasticity window favors early adulthood.
- DOK 2 — Summary: Relational reasoning is trainable via structured drilling; supports a relational-reasoning training component and matters for the college-age audience.

### Category E: Psychometrics — scoring, equating, validity

#### E.1: Item Response Theory & local dependency

- DOK 1 — Facts:
  - LSAT uses IRT (not Classical Test Theory, which is sample-dependent). P(correct|θ) = f(θ, a, b, c).
  - Parameters: a (discrimination), b (difficulty = ability for 50% correct), c (pseudo-guessing).
  - Local independence assumed, but RC clusters (5–8 questions/passage) create Local Dependency (LD): misreading a passage's purpose raises error probability across its items.
  - To preserve scale reliability and accurate SEM, psychometricians use random-effects models + Bayesian estimation; variable section field-tests items.
  - (Emerging: Federated IRT (FedIRT) for decentralized, privacy-preserving estimation, not yet deployed for the LSAT.)
- DOK 2 — Summary: Item difficulty and discrimination are item properties rather than cohort-relative, which gives a principled basis for adaptive difficulty. Clustering complicates both scoring and practice design.

#### E.2: True-score equating & the score scale

- DOK 1 — Facts:
  - NOT curved against same-day cohort; cohort has zero bearing on your score.
  - IRT true-score equating + NEAT (anchor items) link forms to a common ability scale; raw → fixed 120–180.
  - No guessing penalty; reported with percentile (prior 3 yrs) and a score band = ±SEM.
- DOK 2 — Summary: Equating makes a 160 mean the same across administrations; useful framing for in-app scoring/diagnostics.

### Category F: AI / LLMs and the LSAT

#### F.1: LLM scores vs. true reasoning ("Language-Thought Gap")

- DOK 1 — Facts:
  - Benchmarked models: GPT-4 ∼163 (∼88th pct); GPT-3.5 ∼149 (∼40th pct); Claude 3.5 and Gemini also benchmarked.
  - LLMs are next-token probability engines → lack genuine logical comprehension; absorb semantic biases; suffer "semantic drift" and hallucinated steps on multi-step FOL.
  - LSAT-style logic is used by researchers to test/train LLM compositional reasoning.
- DOK 2 — Summary: High scores can come from memorized linguistic structure rather than real deduction, so treat any AI feature with caution.

#### F.2: Risk of LLM question generation

- DOK 1 — Facts:
  - Relying on LLMs to author custom LSAT items is high-risk: AI can't reliably architect the layered traps/deductions human writers engineer.
  - AI is useful for personalized analytics, pacing dashboards, and baseline explanations; human-authored prep remains the gold standard for strategy.
- DOK 2 — Summary: Use AI at the edges (analytics, explanations) rather than as the item author, which mirrors "don't let the model own correctness."

#### F.3: First-Order Logic, symbolic solvers & neurosymbolic AI

- DOK 1 — Facts:
  - LR's backbone is First-Order Logic (FOL): quantified variables, universal (\forall) and existential (\exists) quantifiers, predicates; difficulty comes from FOL obfuscated inside dense natural language.
  - Neurosymbolic approaches (Logic-LM, SymbCoT, HBLR): LLM acts only as semantic parser → translates prompt into symbolic FOL → deterministic theorem prover (Z3, Prover9, Pyke) computes the answer.
  - Humans must do BOTH roles (semantic translator + symbolic solver) on limited biological hardware, and this dual processing is a primary source of test fatigue.
  - For humans, studying formal FOL is often counterproductive: LSAT conditional logic is relatively remedial; strict FOL adds extraneous load and slows you down.
- DOK 2 — Summary: Symbolic verification is promising for tooling (deterministic answer-checking); formal-logic coursework is the wrong study path for learners. The parser/solver split mirrors the human cognitive burden.

#### F.4: LLM difficulty estimation (for tagging scraped/imported items)

- DOK 1 — Facts:
  - Direct text-only difficulty prediction (QDET) correlates weakly with real difficulty (Scarlatos et al. 2025); CoT doesn't fix it.
  - LLMs align with 2-parameter IRT on reading items but compress the extremes, rating easy items too hard and hard items too easy (Jain et al.).
  - Better methods: LLM feature-extraction (linguistic complexity, distractor plausibility) → tree-based regressor (Razavi & Powers 2025); comparative "which of two is harder" prompting beats absolute scoring (Raina & Gales 2024); simulated-student responses fit to IRT reach AUC 0.77–0.90, and weaker-math models better simulate struggling students ("Take Out Your Calculators" arXiv:2601.09953; SMART arXiv:2507.05129).
- DOK 2 — Summary: Tag difficulty by comparative ranking or simulated-student-IRT rather than absolute prompts, expect extreme compression, and calibrate against real response data (which a brownfield Anki app already logs; see App-design stance D4).

#### F.5: LLM explanation / hint / feedback reliability

- DOK 1 — Facts:
  - GPT-4 in an intelligent tutor: ∼35% of hints too general, incorrect, or giving away the answer; LLM auto-evaluation of feedback validity right only ∼35% of the time (Stamper/Pardos group, IJAIED 2025).
  - A simulated-student validator step lifts hint precision from 60–66% to 94–98% (Phung et al., LAK 2024).
  - LLM-generated feedback shows small, selective gains mainly when learners actively engage; availability ≠ benefit (Thomas et al., arXiv:2506.17006).
  - Chain-of-thought can be plausible while not reflecting the actual cause of the answer (Turpin et al., arXiv:2305.04388; Anthropic 2025).
- DOK 2 — Summary: Explanations and hints are usable but only via generate-then-verify: ground them in the keyed answer, run a giveaway or simulated-student check, and don't trust free narration. Drive actual use, since provision on its own isn't enough.

#### F.6: Neurosymbolic verification & the "verified-subset" architecture

- DOK 1 — Facts:
  - Logic-LM (Pan et al.): NL→symbolic→solver, +39.2% over prompting (arXiv:2305.12295).
  - SSV (Raza & Milic-Frayling, arXiv:2501.16961): model generates test-case instantiations, solver checks consistency, returns near-certain `isVerified`. ∼100% precision on the subset it verifies across benchmarks; ∼97% even on weaker models → tiered cheap-then-expensive routing.
  - Generation-vs-verification asymmetry: models generate better than they verify; "fake verification" is common (arXiv:2602.07594, 2512.02304). RLVR works where correctness is programmatically checkable.
- DOK 2 — Summary: For *formalizable* conditional-logic content, a solver-backed near-100%-precision signal is achievable; design pattern: auto-serve only the verified subset, route the rest to humans. Caveat: current LR/RC don't formalize cleanly into solver constraints, so use this pattern where it fits and rely on the answer key elsewhere.

### Category G: Admissions landscape & alternatives

#### G.2: Equity & score gaps

- DOK 1 — Facts:
  - 2019 data: average ∼142 for Black test-takers vs. ∼153 for White and Asian test-takers.
  - Critics: heavy reward for expensive, hundreds-of-hours prep may reflect systemic inequality, not innate ability.
- DOK 2 — Summary: Access/cost is a live equity concern; an affordable, science-based tool is a meaningful angle.

### Category H: Study methodology & learning science

#### H.1: Interleaved vs. blocked practice

- DOK 1 — Facts:
  - Blocked practice (same question type repeatedly) creates a temporary fluency spike and false mastery, since the learner skips the meta-task of choosing the right strategy.
  - Interleaving (mixing types randomly) forces retrieval of the right strategy; works via the discriminative-contrast hypothesis (contrasting adjacent prompt types).
  - Interleaving feels harder and lowers immediate performance, but yields far better long-term retention and generalization, with delayed scores up to ∼76% higher than blocked practice.
- DOK 2 — Summary: Interleaving builds the diagnosis-of-problem step on top of execution, a core argument for the app's practice-mixing engine over blocked drills.

#### H.2: Metacognition & the Blind Review method

- DOK 1 — Facts:
  - Phase 1 — Timed execution (35 min), flagging any question below 100% certainty (System 1 load).
  - Phase 2 — Untimed blind review BEFORE checking answers: re-solve flagged items, writing explicit justifications for the right answer and exactly why each other choice is false (System 2).
  - Phase 3 — Score both passes + metacognitive analysis. Big timed-vs-untimed gap ⇒ speed/WM problem; low in both ⇒ conceptual/schema gap needing remediation.
  - Advanced learners keep error journals tracking flaw types (toward "six sigma" accuracy).
- DOK 2 — Summary: Separates execution from analysis; the diagnostic signal is the timed-vs-untimed gap. Strong candidate to operationalize in software (plus an error-journal/misconception tracker).

#### H.3: Spaced repetition & retrieval practice

- DOK 1 — Facts:
  - Spacing increases intervals between reviews, recalling material as it begins to fade → strengthens pathways, moves knowledge short-term → long-term.
  - Retrieval practice = recalling without notes/cues; combined with spacing, hardwires foundational logic rules (contrapositives, conditional vs. biconditional) for instant access under stress.
  - Repeated full timed PrepTests alone don't drive gains, since they measure current ability and reinforce existing habits without fixing deficits.
- DOK 2 — Summary: Retrieval + spacing + interleaving beat passive repetition; this is the SRS rationale and the core mechanic for the app.

### Category I: Anki, flashcards & audience fit

#### I.1: Anki UI & flashcard limits

- DOK 1 — Facts:
  - Students report Anki's UI as unintuitive/rigid.
  - Isolated flashcards can fail to build the cognitive schema a fluid-reasoning test needs (vs. rote facts).
  - Reported need for non-flashcard methods: interleaved practice + deep untimed analytical breakdowns (Blind Review).
- DOK 2 — Summary: Straight flashcards are a poor fit for a reasoning test; the opportunity is SRS principles applied to reasoning practice, with better UX than Anki.

#### I.2: Brownfield realities (what the platform already gives you)

- DOK 1 — Facts:
  - Native "upload-your-own" import; FSRS scheduler; per-card review logging (ease, lapses, interval history); flexible HTML/JS note types.
  - A "card" can be a full stimulus + question + 5 choices, with the back revealing the keyed answer, per-choice "why wrong," and trap tag, and can run a mini Blind-Review flow (commit, then reveal).
- DOK 2 — Summary: Inherit the scheduler, logging, import, and note-types; change what gets scheduled (the skill or trap rather than the literal item) and enrich imported cards instead of authoring from scratch. The review log is response data for difficulty calibration (App-design stance D4).

#### I.3: How people currently practice LR/RC

- DOK 1 — Facts:
  - Backbone = official LSAC PrepTests (50+ free on lawhub.lsac.org; current-format tests numbered 101–158; ∼7,500 LSAT questions exist historically); drill by type → timed sections → full timed tests.
  - Blind Review is the most-recommended review method and is largely AI-light (the student produces the reasoning).
  - Published explanations cover right AND wrong answers (e.g. LSATHacks ∼4,700 questions); paid platforms add video/adaptive/analytics (7Sage, LSAT Demon, Blueprint, LSAT Lab, Kaplan, PowerScore, Manhattan).
  - Every LR/RC item is single-best-answer MCQ with an official key → correctness is a lookup, not a model judgment.
- DOK 2 — Summary: The practice loop already works without AI, so the app's value is the tutoring, diagnosis, and scheduling layer on top of keyed items rather than solving or grading.

#### I.4: Daily active-reading as a trainable habit

- DOK 1 — Facts:
  - "Read widely" is standard RC advice (Manhattan: read The Economist/The Atlantic for register and structure), though it builds fluency over time more than points.
  - Reading science backs the deeper claim that comprehension is downstream of *knowledge* and *reading volume*: Recht & Leslie (1988, the "baseball study") found topic background knowledge predicted comprehension more than measured reading ability (knowledge compensates for weaker reading skill); a 2021 review of 23 studies (Smith et al.) corroborates. Cunningham & Stanovich (1991; 1998) found print exposure / reading volume uniquely predicts vocabulary, general knowledge, and verbal skill even controlling for IQ. (General and developmental-reading studies, applied to the LSAT by extrapolation via the CLT load-reduction mechanism.)
  - The daily-queue habit is Anki's core strength; a read-something-daily module is platform-native.
  - Effective loop: domain-rotating daily passage (interleaving) → produced structural map (main point, what each \P{} does, author stance/opposing views) → non-gating formative feedback → harvest unfamiliar terms into the SRS vocab deck.
  - Two things to train here, not one: (1) comprehension of dense, sustained, unfamiliar prose, and (2) reading speed and fluency plus section stamina (LSAT RC runs about 3–10× the passage length of the current digital SAT, with 5–8 questions per passage versus 1, under tighter time). Speed is mostly emergent from fluency, so train baseline reading rate on appropriately-leveled wide reading rather than by skimming actual LSAT passages (skimming is the trap RC punishes). Pacing, triage, and stamina are the genuinely trainable timing pieces, best surfaced through the timed-vs-untimed gap (Blind Review, H.2; stance D5). Keep this secondary, since comprehension is the lever and speed follows.
- DOK 2 — Summary: Active daily reading with a produced artifact trains the structural-reading skill RC tests and feeds the vocab deck; passive reading is the nodding-is-not-knowing trap. Wide reading is the lever (more than RC drilling) because it builds the broad background familiarity and vocabulary that comprehension rests on, which lowers parsing load so working memory goes to reasoning. That is the empirical basis for the Spiky POV's second move (Recht & Leslie; Cunningham & Stanovich; CLT). It also builds reading speed and stamina as a minor secondary byproduct, not a separate "speed-drill" module.

### Category J: The LR/RC skill taxonomy, the flaw catalog & the self-contained test

#### J.1: LR question-type taxonomy — convergence and divergence

- DOK 1 — Facts:
  - ∼13 recurring question types, stable across decades; every major company recognizes essentially the same set (PowerScore, etc.).
  - Names diverge: "Must Be True" = "Inference" (LSAT Trainer) = "Identify an Entailment" (Khan) = Inference/Fill-in (Loophole); a cross-publisher concordance exists (Resolution Test Prep).
  - It's industry consensus, not an official LSAC taxonomy; Khan Academy is the only material built in direct LSAC collaboration. PowerScore treats Principle as an overlay and Role as a subtype of Method.
  - Frequency is lopsided: Flaw is currently most common; Assumption+Flaw+Inference ≈ 40%; +Strengthen/Weaken/Paradox/Principle ≈ 75% (Magoosh, ∼55 tests).
  - Question *type* is defined by the stem (objective, often stem-derivable); reasoning *type* (conditional / causal / formal-logic) is a cross-cutting second axis.
- DOK 2 — Summary: Well-defined enough to tag and space, though you have to pick and own a taxonomy and tag on two axes (the reliable question-type from the stem, and the fuzzier reasoning-type or trap, AI-assisted then verified). RC has a smaller agreed set too (main point, primary purpose, author's attitude, detail, inference, structure/function, application, comparative).

#### J.2: The flaw "bug library"

- DOK 1 — Facts:
  - LR turns on a small enumerable set of fallacies: correlation-vs-causation, circular reasoning, sufficient/necessary confusion, equivocation, ad hominem, part-to-whole, with a long tail learned in context.
  - RC distractors are similarly catalogable: half-true, too extreme/unsupported, out of scope, contradicts text, doesn't answer the question.
- DOK 2 — Summary: A finite trap catalog enables behavior-first misconception tracking. Tag each distractor's trap once, offline, and a wrong answer maps to a known flaw with no live AI judgment (Brown & Burton bug-library lineage).

#### J.3: The self-contained test & the vocabulary question

- DOK 1 — Facts:
  - The LSAT tests no outside content knowledge; inferences follow only from the given facts, and outside knowledge can hurt (Kaplan; on RC, an outside-knowledge-dependent choice is usually wrong, per Shemmassian).
  - Science passages have dense technical vocabulary but the test never tests science itself; "focus on argument structure, not terminology" (Test Ninjas).
  - LSAC's line: you do NOT need terms like "ad hominem" or "syllogism," but you DO need the concepts argument/premise/assumption/conclusion (LawHub).
- DOK 2 — Summary: No science or philosophy content-vocabulary earns points (a myth). The learnable, flashcard-appropriate set is the finite logic and argument meta-vocabulary, the flaw catalog, and the indicator and quantifier words, all declarative knowledge you want automatic (CLT). Broad reading helps by reducing extraneous load through fluency, and the daily-reading module handles that rather than a content deck.

### Category K: LR deep dive — method, pain points & cognitive sub-skills

#### K.1: The expert method (convergent across companies)

- DOK 1 — Facts:
  - PowerScore "Primary Objectives" (Killoran/Denning): read the stimulus → identify the conclusion → paraphrase → *prephrase* (predict the answer before reading choices) → read all five → split into Contenders/Losers → return to the stimulus to decide. 13 types, each with a named sub-method (Conclusion Identification, Assumption Negation, Justify Formula, Supporter/Defender, the Fact Test).
  - First move is always to classify the stimulus: argument (conclusion + premises) vs. set of facts (Thinking LSAT; PowerScore). Arguments → find the conclusion and test whether premises support it; fact sets → find what's provable.
  - The leverage is in the stimulus, not the answers: experts report understanding the stimulus fully and then spending only ∼5–15 sec on the choices ("if you know the stimulus, the answers are easy," per LSATHacks).
- DOK 2 — Summary: A fixed scaffold the app can prompt (classify, conclusion, prephrase, eliminate, confirm). Prephrasing is a generation step, a natural in-app interaction and a learning event rather than plain answer-picking.

#### K.2: Pain points & common error modes (the diagnostic targets)

- DOK 1 — Facts:
  - Misidentifying the conclusion cascades into assumption/flaw/strengthen-weaken failure (the assumption is the premise→conclusion gap), per Impetus.
  - Picking the first answer that "seems right" without reading all five; getting stuck between two Contenders and re-reading the *answers* instead of returning to the *stimulus* (TestMax; JD Advising).
  - Skimming under time pressure → falling for traps; speed-over-accuracy is the root error (Impetus; Manhattan; LSAT Demon).
  - Confusing sufficient vs. necessary conditions is the single most common flaw and trips novices most (Leland).
  - In flaw questions: fixating on the conclusion while neglecting the premises; treating all irrelevant info as "the flaw."
  - Diagnosing weakness by "which type I miss most" is misleading (rare types distort the count); look at structure comprehension and accuracy-per-attempt (Impetus).
- DOK 2 — Summary: A ready-made list of error modes beyond right/wrong. Some are behaviorally detectable (the trap chosen → a specific flaw); others surface only in produced Blind-Review reasoning. This is the target list for AI diagnosis and trap tagging (App-design stance D5).

#### K.3: Timing, triage & accuracy-first

- DOK 1 — Facts:
  - Early questions are easier than late ones; every question is worth the same, so don't rush the easy points (PowerScore tutors). Common plan: ∼Q1–15 in ∼20 min, Q15–25 in ∼15 min.
  - Accuracy-over-speed is near-universal ("put a sticky note over the clock"); 80–90% of speed problems are solved by getting *better at LR*, not separate "speed training" (LSATHacks; LSAT Demon).
  - Triage: skip-and-return on the hardest items; always bubble a guess (no wrong-answer penalty).
  - The timed-vs-untimed accuracy gap diagnoses the bottleneck (working-memory/processing-speed vs. conceptual); this is the Blind Review signal (H.2).
- DOK 2 — Summary: Speed is an output of mastery and automaticity (CLT) rather than an input. The app should coach accuracy first and surface the timed-vs-untimed gap instead of drilling raw speed.

#### K.4: Cognitive sub-skills (the second tagging axis, concretely)

- DOK 1 — Facts:
  - Conclusion/premise identification; prephrasing/prediction; answer classification (Contender vs. Loser).
  - Conditional reasoning: sufficient/necessary, if/then, contrapositive chains.
  - Causal reasoning: the strengthen/weaken levers on causal arguments (alternate cause, reverse causation, etc.).
  - Formal logic: quantifier inference (all/most/some/none), rare and low priority.
  - Abstraction: stripping content to match logical form (parallel reasoning, abstract flaw), the hardest cluster.
- DOK 2 — Summary: The cross-cutting reasoning sub-skills beneath the question-type axis (Insight 3). Conclusion-ID and conditional reasoning are the most foundational/high-leverage; formal-logic quantifiers the lowest. A concrete sub-skill tag set for the app's second axis.

## DOK 1: Facts (consolidated)

#### Modern LSAT structure (2024–2026)

- Four 35-min MC sections; three scored (2 LR + 1 RC), one unscored variable; plus Argumentative Writing.
- LR ≈ 66% of scaled score; ∼1:20 per LR question; RC = 3 single passages + 1 comparative set, 26–28 questions, ∼5–8 questions/passage.
- Logic Games eliminated Aug 2024 (2019 ADA suit) → 2nd LR section, near-zero scoring impact.

#### Cognitive science

- CLT (Sweller): intrinsic/extraneous/germane load; automaticity frees WM; overload stalls processing.
- TBRS model: performance inversely related to load.
- Dual-process (Kahneman & Tversky): distractors exploit System 1; train System 2 to System 1 speed.
- Mental Model Theory: deduction = nonverbal spatial models; train executive functions.
- Relational Frame Theory / SMART: AARR (mutual + combinatorial entailment, transformation of functions); relational training raises IQ/non-verbal reasoning; far-transfer weakens with age.

#### Neuroscience of prep (Bunge/Mackey)

- ∼100 hrs → ↓radial & mean diffusivity (↑myelination) in frontoparietal white matter; biggest gains ↔ retrolenticular right internal capsule.
- fMRI: ↑frontal–parietal & left–right connectivity, ↓lateral-PFC/IPS activation (efficiency + hemispheric compensation).
- Eye-tracking: faster relevant-info encoding (∼23 movements/7 sec baseline), transfers to novel relational tasks.

#### Psychometrics

- IRT (a discrimination, b difficulty, c pseudo-guessing); RC clusters → local dependency, handled via random-effects/Bayesian methods.
- True-score equating + NEAT anchors; fixed 120–180; no guessing penalty; score band = ±SEM; not cohort-curved.
- FedIRT = emerging privacy-preserving estimation (not deployed for LSAT).

#### AI / LLMs

- GPT-4 ∼163 (88th pct), GPT-3.5 ∼149 (40th pct); Claude 3.5 & Gemini benchmarked. "Language-Thought Gap"; semantic drift on multi-step FOL. (These GPT-4/3.5 figures are from 2023–24 models.)
- LLM item generation high-risk; AI better for analytics/explanations than authoring. Surface metrics can't judge a question's solvability/validity (EQGBench); verifiable QG = generate autograded code + validators (PrairieLearn).
- Neurosymbolic (Logic-LM +39.2%; SSV near-100% precision on its verified subset): LLM parses/instantiates → solver verifies. Generation > verification (models can't reliably self-check). Verified-subset + tiered routing as design patterns.
- Explanations: ∼35% of raw GPT-4 tutor hints fail (too general/wrong/giveaway); simulated-student validator → 94–98% precision. CoT can be unfaithful, so verify against the key and don't trust narration.
- Difficulty: text-only prediction weak + compresses extremes; comparative ranking, feature+regressor, and simulated-student-IRT (AUC 0.77–0.90) work better; calibrate against real response data.

#### Study methodology

- Interleaving > blocked (discriminative-contrast; delayed scores up to ∼76% higher; feels harder).
- Blind Review (timed+flag → untimed re-solve with justifications → score both + metacognition); timed-vs-untimed gap diagnoses speed vs. concept.
- Spacing + retrieval practice hardwire logic rules; repeated full PrepTests alone don't drive gains; error journals for flaw tracking.
- Typical prep 150–300 hrs over 3–4 months.

#### Admissions landscape

- Equity: 2019 avg ∼142 (Black) vs. ∼153 (White/Asian); prep cost a systemic concern.

#### Audience / Anki

- Anki UI unintuitive/rigid; isolated flashcards weak for a fluid-reasoning test; demand for interleaving + Blind Review.
- Brownfield: FSRS scheduler + per-card review logs + upload-your-own import + HTML/JS note types already exist.

#### Skill taxonomy & vocabulary

- ∼13 LR question types, stable, converge across companies; names diverge; industry consensus (Khan = LSAC-collaborated). Flaw most common; Assumption+Flaw+Inference ≈40%, +Strengthen/Weaken/Paradox/Principle ≈75%.
- Two axes: question type (stem-derivable, reliable) vs. reasoning type (conditional/causal/formal, cross-cutting, fuzzy). Flaw catalog = finite trap library → behavior-first misconceptions.
- Self-contained test: no outside content knowledge (can hurt). LSAC: need premise/assumption/conclusion concepts, not "ad hominem"/"syllogism" labels. Flashcard-appropriate set = logic meta-vocabulary + flaw catalog + indicator/quantifier words; broad reading aids fluency, not points.

#### Current LR/RC practice

- 50+ official PrepTests on LawHub (current format 101–158; ∼7,500 historical questions); drill→timed→full tests. Blind Review is the dominant review method. Published right+wrong explanations (LSATHacks); platforms: 7Sage, LSAT Demon, Blueprint, LSAT Lab, Kaplan, PowerScore, Manhattan. Every item is keyed MCQ → correctness is a lookup.

#### LR method & pain points (LR-first; RC = phase-2 extension of same engine; daily reading = fluency substrate)

- Expert method (PowerScore Primary Objectives): classify stimulus (argument vs. facts) → ID conclusion → paraphrase → prephrase → read all 5 → Contenders/Losers → return to stimulus. Leverage is in the stimulus (answers take ∼5–15 sec once it's understood).
- Common errors: conclusion-misID (cascades to assumption/flaw), first-seeming-right, contender-lock (re-read answers not stimulus), skimming under time, sufficient/necessary confusion (most common flaw).
- Timing/triage: early Qs easier; accuracy > speed; ∼80–90% of speed issues solved by mastery; skip-and-return + always guess; timed-vs-untimed gap = the diagnostic.
- Sub-skills (2nd tagging axis): conclusion/premise ID, prephrasing, conditional (sufficient/necessary, contrapositive), causal (strengthen/weaken levers), formal-logic quantifiers (low priority), abstraction (parallel/flaw, hardest).
