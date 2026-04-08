# Storyteller V3 — Research Catalogue

**Document version:** 1.0  
**Project:** Storyteller V3  
**Last updated:** March 2026  
**Scope:** Comprehensive register of all external research reviewed for
the Storyteller V3 project. Each source is evaluated for applicability
to the Game Engine (V1) and/or Campaign Studio (post-V1), with explicit
TAKE/REJECT decisions, design impact, and document placement.

**Purpose:** This document is the project's institutional memory for
research. It answers three questions: What did we read? What did we
learn? Where did it land in the design?

**Supersedes:** STORYTELLER_V3_RESEARCH_SCOPING.md (v1.1) and
STORYTELLER_V3_SAGA_RESEARCH_FINDINGS.md. All content from both
documents has been absorbed here.

**Methodology:** Each source receives either a full review (for sources
that drove major design decisions or provided critical frameworks) or a
summary card (for supporting evidence, partial transfers, or primarily
rejected sources). Every finding is scoped to a target system with
explicit TAKE/REJECT rationale.

---

## Master Source Index

| # | Source | Type | Date | Domain | Detail Level | Primary Impact |
|---|--------|------|------|--------|-------------|----------------|
| 1 | Web World Models (Princeton) | Academic paper | Dec 2025 | Architecture | Full review | Schema validation, cloud fallback, physics-before-imagination |
| 2 | MiniMax M2-her deep dive | Industry blog | Jan 2027 | Prose quality | Full review | Prose diagnostic signal, distillation curation |
| 3 | Deng, Brucks & Toubia (Columbia) | Academic paper | Feb 2026 | Creative diversity | Full review | Persona + CoT as primary diversity intervention |
| 4 | Shahhosseini et al. (Sharif/Isfahan) | Survey paper (TMLR) | Feb 2026 | Creative generation | Full review | Writer's Room five-stage architecture, tree search |
| 5 | CrEval (Cao et al.) | Academic paper (ICLR) | 2026 | Evaluation | Summary card | Pairwise comparison methodology, 7B evaluator |
| 6 | CreativityPrism (Hou et al.) | Academic paper | Under review | Creative diversity | Summary card | Orthogonal creativity dimensions |
| 7 | Braccini, Aguzzi & Baldini (Bologna) | Academic paper (Springer) | Feb 2026 | Creative diversity | Summary card | Semantic-syntactic decoupling gap |
| 8 | MLD-EA (COLING 2025) | Academic paper | Jan 2025 | Prose quality | Summary card | Action-emotion coherence validation |
| 9 | LLM Story Network Analysis (NeurIPS) | Academic paper | Oct 2025 | Prose quality | Summary card | Positivity bias, relationship network validation |
| 10 | KG-Assisted Story Generation (IJHCI) | Academic paper | 2025 | Architecture | Summary card | Scene-type-aware context assembly |
| 11 | AI STORIES (ERC) | Research proposal | 2023 | Narrative theory | Summary card | Archetype theory, negative archetype spec |
| 12 | ASEP — Adaptive Storytelling Pipeline | GitHub framework | May 2025 | Architecture | Summary card | Rejected as architecture; patterns absorbed |
| 13 | Latitude / AI Dungeon / Voyage | Competitive landscape | 2019–2026 | Industry | Summary card | Competitive intelligence, Mode 1 minimum spec |

---

## Domain A: Architecture & Systems Design

### Source 1 — FULL REVIEW: Web World Models (Princeton, Dec 2025)

**Full title:** "Web World Models" — procedural infinite-world generation
using typed interfaces and deterministic hashing  
**Key contribution to Storyteller V3:** Three transferable architectural
principles, none requiring adoption of the paper's web-stack-specific
implementation.

#### Transferred Findings

**TAKE — JSON Schema Validation Layer (Game Engine V1)**

Runtime validation on two boundaries: (1) local model output → dice
engine, where the check decision JSON is validated against a strict
Pydantic schema before processing, with retry-then-default on failure;
(2) context package assembly → cloud model, where structural
completeness is verified before sending, with error logging and graceful
degradation on failure. The paper's core insight is that the contract
between the physics layer and the imagination layer must be enforced at
runtime, not just documented. Without validation, malformed local model
output causes silent corruption, and missing context fields cause the
cloud model to hallucinate to fill gaps.

*Target: STORYTELLER_V3_IMPLEMENTATION.md — Phase 2 and Phase 3.
Priority: V1.*

**TAKE — Cloud Failure Fallback Path (Game Engine V1)**

A defined timeout (20 seconds) and automatic per-turn degradation to
the local model when the cloud API is unavailable. The local model
receives the same context package with a simplified prompt. The player
sees no error — just a passage. A counter tracks consecutive fallbacks
and surfaces a subtle UI indicator after 3+. The rationale: during a
climactic moment, an error screen destroys immersion more than a
less-polished passage.

*Target: STORYTELLER_V3_IMPLEMENTATION.md — Phase 3. Priority: V1.*

**TAKE — Physics-Before-Imagination Ordering Invariant (Game Engine V1)**

Storyteller V3 already enforces this in practice: code resolves all
state transitions before the narrative model receives context. The paper
provides the formal name. Documenting it as an explicit invariant
prevents future drift.

The invariant: "The narrative model never determines mechanical
outcomes. Code resolves all state transitions — dice rolls, NPC
disposition changes, strain/wound updates, Obligation triggers — before
the narrative model receives the updated context package."

*Target: STORYTELLER_V3_IMPLEMENTATION.md — Section 0. Priority:
Documentation only.*

**TAKE — Campaign Spine JSON Schema Validation (Campaign Studio)**

Strict typed contract enforcement on Campaign Studio output. A
malformed spine (missing NPC disposition, inconsistent act numbering,
dangling NPC references) corrupts the entire campaign at runtime. More
critical than per-turn validation because a bad spine corrupts the
entire campaign rather than just one passage.

*Target: STORYTELLER_V3_GAME_MECHANICS.md — Section 12 (Deferred).
Priority: Campaign Studio design phase.*

#### Rejected Findings

**REJECT — Infinite-World Procedural Generation.** Storyteller V3 uses
authored campaign spines with SQLite persistence, solving the opposite
problem. Deterministic seeding sub-technique filed as CONSIDER for
narrow Campaign Studio applications.

**REJECT — Web Stack Specifics.** TypeScript, HTTP streaming, serverless
— implementation choices for a different tech stack. No transferable
design value.

---

### Source 12 — SUMMARY CARD: ASEP — Adaptive Storytelling Pipeline

**Type:** GitHub framework (May 2025, 1 star, 0 forks)  
**Domain:** Multi-pass LLM writing workflow for human authors

**Rejected as architecture** because ASEP is a writing-tool workflow for
human authors in a chat session, not a real-time narrative engine. Its
10+ sequential stages with human review are incompatible with real-time
game narration. The vocabulary ("characters as microservices," "Stability
Index Meter") is dramatically overengineered for what the framework
delivers.

**Patterns that transferred (adopted under different names):**
- Recursive consistency validation → Campaign Studio spine audit
- Anti-trope detection → Absorbed into prose diagnostic signal and NPC
  relationship validation
- Modular lore injection → Already present as the galactic context layer
  and NPC state cards

**Also rejected:** ASEP Trope Sniffing Daemon as a standalone runtime
system. The concept is sound but absorbed into the prose diagnostic
signal, which covers pattern detection as one of its three dimensions.

---

### Source 13 — SUMMARY CARD: Latitude / AI Dungeon / Voyage

**Type:** Competitive landscape analysis (2019–2026)  
**Domain:** AI narrative gaming market

**Rejected as design source** because Latitude's architecture is
fundamentally different — no mechanical backbone, no authored spine, no
dice system. They rely on the LLM for both state management and
narration, which is exactly the architectural anti-pattern Storyteller
V3's two-system design was built to avoid. Their
context-window-as-premium-feature monetization reveals an architecture
that hasn't solved the memory problem.

**Competitive intelligence that informed decisions:**
- The AI narrative gaming market hasn't achieved breakout scale with
  open-ended approaches — validates the authored-spine strategy
- Latitude's minimum viable creator input (themes + key characters +
  location sketches) informed the Mode 1 minimum viable spec
- The market gap between "AI chatbot RP" and "authored narrative RPG"
  is exactly where Storyteller V3 sits

---

### Source 10 — SUMMARY CARD: KG-Assisted Story Generation (Pan et al., IJHCI 2025)

**Full title:** "Guiding Generative Storytelling with Knowledge Graphs"  
**Key finding:** Structured state representations help action-oriented
narrative generation (p=0.039) but hurt introspective narrative
generation (p=0.07 trending negative).

**TAKE — Scene-Type-Aware Context Assembly (Game Engine)**

Modulate the density and type of structured state fed to the cloud model
based on the scene type tag. Kinetic scenes get full mechanical detail.
Reflective scenes get lighter mechanical scaffolding with heavier
emphasis on voice notes, throughline questions, and motivational context.
The scene type tag infrastructure already exists; the implementation is
a routing decision in `_build_prompt`, not a new system.

The paper also validates NPC state cards as structured
entity-relationship tracking (the paper's KG is a less specific version
of what NPC state cards already provide) and Campaign Studio Mode 3
collaborative editing (92.9% preference, high perceived control).

**Rejected:** Building a separate knowledge graph system. Existing NPC
state cards + character state + session persistence are architecturally
superior to the paper's flat text-description KG.

*Target: STORYTELLER_V3_GAME_MECHANICS.md — Section 10. Priority:
Late-V1 or early post-V1.*

---

## Domain B: Prose Quality & Narrative Coherence

### Source 2 — FULL REVIEW: MiniMax M2-her Deep Dive (Jan 2027)

**Type:** Industry blog — technical deep dive on MiniMax's multi-agent
roleplay architecture  
**Key contribution to Storyteller V3:** The prose diagnostic signal
concept and the distillation curation specification. The blog describes
a multi-agent architecture (planning agent, segment checking agent,
refinement agent, causal denoising) that is overengineered for our use
case, but two specific patterns transferred cleanly.

#### Transferred Findings

**TAKE — Prose Diagnostic Signal (Game Engine, Deferred)**

A lightweight local-model call that runs once per turn, scanning the
last 3–4 uncompressed passages and the current NPC state cards. It
produces a structured JSON diagnostic injected into the cloud model's
context package as an anti-staleness and anti-drift signal. The cloud
model uses this diagnostic when generating the next passage.

The diagnostic checks three dimensions:

1. **Prose pattern detection** (from MiniMax): Which sensory channels
   dominated recent passages, whether paragraph rhythm has been
   repetitive, whether passage openings have been similar.

2. **NPC action-emotion coherence** (from MLD-EA, Source 8): Whether
   the most recent passage described an NPC behaving inconsistently with
   their mechanical state (e.g., hostile NPC described as cooperative).

3. **Relationship polarity tracking** (from Network Analysis, Source 9):
   Whether recent passages have been uniformly positive in NPC
   interactions despite hostile or conflicted disposition states.

Cost: One additional local model call per turn (~1000 tokens input,
~200 tokens output). On RTX 4070 with Qwen3.5:9B, adds ~1–2 seconds if
sequential, ~0 if parallelized with the check decision.

The context package schema includes a `prose_diagnostic` field (null in
V1) so the addition is not a structural change later.

*Target: STORYTELLER_V3_GAME_MECHANICS.md — Section 13. Priority:
Post-V1 (field reserved in V1).*

**TAKE — Dual-Filter Distillation Curation Spec (LLM Evaluation)**

Quality floor for the narration distillation pipeline. Two filters,
both must pass: (1) automated staleness check using the prose
diagnostic prompt — excludes passages with sensory monotony, repetitive
openers, flat rhythm, or positivity drift; (2) mechanical fidelity
check — verifies dice result honored, NPC voice consistency, word count
bounds, valid choices with delimiter. Reuses the prose diagnostic
prompt, making it a two-for-one with the runtime system.

*Target: STORYTELLER_V3_LLM_EVALUATION.md — Section 8.4. Priority:
Post-V1, before first fine-tuning run.*

#### Rejected Findings

**REJECT — M2-her as a Model Candidate.** Optimized for open-ended
roleplay chatbot interactions, not structured narrative RPG output. No
evidence of delimiter compliance, word count discipline, or mechanical
tagging. Chinese content policies may restrict morally complex Edge of
the Empire content.

**REJECT — Rewrite Agent Pattern.** MiniMax rewrites previous passages
when quality issues are detected. In Storyteller V3, the player has
already read the passage. Rewriting after the fact breaks the player's
experience. The detection component transfers; the rewrite does not.

**REJECT — User-Side Planning Agent.** MiniMax needs a planning agent
because they have no authored spine. Storyteller V3 has an authored
campaign spine with anchor beats — the spine IS the planning agent.
Partial alternative: a simple arithmetic turn counter (deterministic,
not LLM-based) filed as late-V1 consideration.

**REJECT — Statistical Feedback Denoising.** Requires millions of user
interactions for meaningful signal. Storyteller V3 has one user
initially. The quality floor concept transfers (see distillation
curation above); the statistical machinery does not.

**REJECT — Role-Play Bench Taxonomy (as runtime system).** The specific
taxonomy doesn't align with Storyteller V3's evaluation criteria.
Partially adopted: the failure taxonomy concept (binary pass/fail
failure types rather than gestalt quality ratings) is useful for
distillation evaluation.

---

### Source 8 — SUMMARY CARD: MLD-EA (COLING 2025)

**Full title:** Emotion & Action coherence in multi-turn narrative
generation  
**Key finding:** Action-emotion consistency in LLM-generated stories
degrades across turns, particularly at transition points.

**TAKE — Per-NPC Action-Emotion Chain Validation (Campaign Studio)**

When the Campaign Studio generates or validates a spine, it traces each
NPC's action chain and emotional trajectory across the full arc. Flags
any point where an NPC's behavior in an anchor beat requires an
emotional state the preceding beats do not establish.

Example: NPC Vossk betrays in Act 3, but his trajectory shows
increasing cooperation through Acts 1–2 with no inflection point. The
validator flags: "Vossk's Act 3 betrayal requires a disposition shift
not established in Acts 1–2."

Also contributed dimension 2 of the prose diagnostic signal (NPC
action-emotion coherence at runtime).

**Rejected:** Plutchik's eight basic emotions — too coarse for the
nuance needed in Star Wars underworld narratives. A character can feel
simultaneously resigned, defiant, darkly amused, and grudgingly
respectful. The coherence principle transfers; the specific taxonomy
does not.

*Target: STORYTELLER_V3_GAME_MECHANICS.md — Section 12 (Deferred).
Priority: Campaign Studio design phase.*

---

### Source 9 — SUMMARY CARD: LLM Story Network Analysis (Nonaka & Perry, NeurIPS Oct 2025)

**Full title:** Character relationship network analysis across 1,200+
LLM-generated and human-written stories  
**Key finding:** LLM character relationship networks are systematically
biased toward positive dynamics (avg edge weight 0.235–0.659 for LLMs
vs −0.061 for human-written stories, p < 0.01 across almost all
metrics).

**TAKE — Anti-Positivity-Bias Prompt Instruction (Game Engine V1)**

An explicit instruction in the GM narration prompt counteracting the
documented tendency toward uniformly positive NPC interactions. The
instruction gives the cloud model explicit permission and direction to
write conflict, friction, and tension between characters whose
mechanical states warrant it.

*Target: STORYTELLER_V3_GAME_MECHANICS.md — Section 1. Priority: Phase
3 prompt authoring.*

**TAKE — NPC Relationship Network Validation (Campaign Studio)**

After spine generation, construct the NPC relationship graph and
validate it does not exhibit LLM-typical positivity-skew and
homogeneous clustering. Checks positive-relationship density (mean >
0.5 flagged), homogeneous clustering (allies-only and enemies-only
clusters flagged), and negative relationship density (sparse antagonist
networks flagged).

*Target: STORYTELLER_V3_GAME_MECHANICS.md — Section 12 (Deferred).
Priority: Campaign Studio design phase.*

Also contributed dimension 3 of the prose diagnostic signal
(relationship polarity tracking at runtime).

---

### Source 11 — SUMMARY CARD: AI STORIES (Rettberg, ERC 2023)

**Full title:** AI STORIES research proposal — hypothesis that LLMs
replicate deep narrative archetypes from training data  
**Type:** Research proposal (no empirical results)

**Rejected as actionable design** because this is an unproven hypothesis,
not a completed study. The hypothesis is compelling and theoretically
grounded but produces no data to act on.

**What transferred:** Theoretical framing for why prompt compliance and
anti-archetype prompting are structural requirements. LLMs trained on
predominantly American English-language fiction default toward positive
resolution, unambiguous moral framing, and familiar Star Wars
archetypes (Wookiees → Chewbacca, Hutts → Jabba). This informs prompt
engineering awareness and the Mode 1 negative archetype specification.

**TAKE — Negative Archetype Specification for Mode 1 (Campaign Studio)**

Mode 1 minimum viable input must include a "this campaign is NOT"
description and archetype avoidance list. Without explicit anti-
archetype signals, generated NPCs collapse into training-data
stereotypes and generated narratives default to hero's journey
structures.

*Target: STORYTELLER_V3_GAME_MECHANICS.md — Section 12 (Deferred).
Priority: Campaign Studio design phase.*

---

## Domain C: LLM Creative Diversity

This domain addresses the central question of the saga layer: can LLMs
generate creatively diverse sequel spines across playthroughs? Four
papers converge on a mechanistic understanding of the LLM diversity
deficit and empirically validated interventions.

### Source 3 — FULL REVIEW: Deng, Brucks & Toubia (Columbia, Feb 2026)

**Full title:** "Examining and Addressing Barriers to Diversity in
LLM-Generated Ideas"  
**Venue:** arXiv (2602.20408v1)  
**Key contribution:** The single most actionable paper in the project.
Decomposes the LLM diversity gap into two independently targetable
mechanisms from cognitive psychology, with empirically validated
interventions that surpass human diversity.

#### Core Framework

Two mechanisms explain why LLM idea diversity falls short of human
diversity:

1. **Fixation** (individual-level): Early outputs constrain subsequent
   generation. Operates through autoregressive token conditioning at
   inference time and RLHF-reinforced typicality bias from post-training.

2. **Knowledge Aggregation** (collective-level): LLMs collapse millions
   of distinct human mental models into a single unified probability
   distribution during pre-training. RLHF further compresses toward
   aggregate preferences. Independent sessions sample from this same
   centralized distribution rather than from idiosyncratic knowledge-
   space regions.

#### Study Results

**Study 1 — Establishing the gap:**
99 humans vs 99 independent GPT-4o sessions, each generating 10 fitness
product ideas. Humans produced 28 unique categories / 206 unique
combinations vs LLM's 22 categories / 88 combinations. Fixation is
symmetric (β_human = 1.035, β_LLM = 1.013, p = 0.51). Knowledge
partitioning is where the gap lives: first-idea unique categories 14.51
vs 8.37 (p < .001), pairwise distance 2.41 vs 1.51 (p < .001).

**Study 2 — Seeding doesn't work:**
Diverse human-generated first ideas as seeds produced ZERO improvement
in downstream diversity (p = 0.95 on categories, p = 0.89 on
combinations, p = 0.49 on pairwise distance). The LLM's unified
associative structure reasserts itself regardless of starting point.

**Study 3 — Personas recover partitioning:**
Ordinary personas (retired politician, veterinary technician, Zumba-
loving college student) produced 210 unique combinations vs 164 for
creative entrepreneurs vs 206 for humans vs 88 for default LLM.
Between-participant semantic variation: ordinary personas 0.635 (2.6x
default LLM's 0.241), exceeding humans (0.545). But ordinary personas
increase within-session fixation (β from 1.013 to 0.876, p < .001).

**Study 4 — CoT breaks fixation:**
Chain-of-thought prompting steepened LLM diversity accumulation (β from
1.013 to 1.363, p < .001) with ZERO effect on humans. Combined persona
+ CoT: 248 unique combinations vs 197 for humans — surpasses human
diversity by 26%.

**Temperature is a dead end:** Marginal gain at 1.5, garbled at 2.0.
Does not address either mechanism.

#### Key Data Points

| Intervention | Fixation Effect | Knowledge Partitioning | Overall Diversity |
|---|---|---|---|
| Human Seeding | No effect | No effect | No effect |
| Creative Entrepreneur Personas | No effect | Partial improvement | Below human |
| Ordinary Personas | Increases fixation | Strong improvement | Near-human |
| Chain-of-Thought | Reduces fixation | Modest improvement | Moderate |
| **Ordinary Personas + CoT** | **Mitigates fixation** | **Maintains strong partitioning** | **Surpasses humans 26%** |

Fixation slopes: β_human = 1.035, β_default = 1.013, β_persona = 0.876,
β_CoT = 1.363, β_persona+CoT = 1.086  
Between-participant variation: Human = 0.545, Default = 0.241,
Persona = 0.635, Entrepreneur = 0.429, CoT = 0.318  
Model: GPT-4o. Authors argue findings generalize — mechanisms are
architectural fundamentals shared across all current LLMs.

#### Design Impact

**TAKE — Persona + CoT as primary diversity intervention (Campaign
Studio saga layer, Stage 1 + Stage 2).** Each writer gets an ordinary
persona; CoT revision pass checks for distinctness.

**TAKE — Seeding is not a diversity mechanism (Campaign Studio saga
layer, architectural constraint).** Prior campaign serves as coherence
context, not diversity seed.

**TAKE — Temperature is a dead end (confirmed).** No temperature-based
diversity strategies anywhere in the architecture.

---

### Source 6 — SUMMARY CARD: CreativityPrism (Hou et al., under review)

**Full title:** Holistic LLM creativity framework across quality,
novelty, and diversity  
**Key finding:** Quality, novelty, and diversity are orthogonal
creativity dimensions — being good at one does NOT predict the others.
Novelty metrics show weak or negative correlations with quality and
diversity.

**Additional findings:** Proprietary models dominate creative writing by
~15% but show NO advantage in divergent thinking — the dimension most
relevant to generating surprising narrative structures.

**TAKE — Three-axis independent evaluation (Campaign Studio saga layer,
Stage 5).** Sequel spine evaluation must independently assess structural
quality, novelty, and diversity. A single quality score is insufficient.

**TAKE — Local model for divergent structural ideation (Campaign Studio
saga layer, Stage 2).** The divergent thinking parity suggests Qwen can
handle structural variation generation at near-parity with cloud models.

---

### Source 5 — SUMMARY CARD: CrEval (Cao et al., ICLR 2026)

**Full title:** Pairwise creativity evaluation with shared context  
**Key findings:** Context-aware pairwise comparison improves evaluation
consistency from ICC 0.59 to 0.75. DPO-based creativity enhancement
does not degrade reasoning. A trained 7B evaluator outperforms frontier
models at creativity judgment.

**TAKE — Pairwise comparison with prior campaign as shared context
(Campaign Studio saga layer, Stage 5).** Candidates compared against
each other, not rated in isolation, with the completed campaign as
evaluation frame.

**TAKE — Local model as spine quality evaluator (Campaign Studio saga
layer, long-term).** The Qwen local model could serve as a pairwise
evaluator. Requires training data from actual spine generation. Not V1;
architecture reserves the capability.

**REJECT — DPO fine-tuning (both systems, V1).** Outside scope — we
consume cloud models as-is via OpenRouter.

---

### Source 7 — SUMMARY CARD: Braccini, Aguzzi & Baldini (Bologna, Feb 2026)

**Full title:** "Unraveling Creativity Through Variability" — semantic
and syntactic variability across 15 LLMs vs humans  
**Venue:** Technology, Knowledge and Learning (Springer)

**Key findings:**
- Intra-question (same prompt) variability gap is much larger than
  inter-question gap — same-prompt generation is the worst case for LLM
  diversity, which is exactly the saga generation scenario
- Humans can independently vary meaning and expression (semantic-
  syntactic decoupling); LLMs cannot — when semantic similarity is high,
  syntactic similarity tracks high
- Larger models are LESS variable, not more — scaling increases
  capability but decreases variability
- Ensemble of different models approaches human variability

**TAKE — Larger models less variable (Campaign Studio saga layer,
architectural constraint).** Reinforces that the Writer's Room is
mandatory. The frontier cloud model is exactly the worst case for
natural diversity.

**TAKE — Semantic-syntactic decoupling gap (Game Engine, background
validation).** Validates the six prose degradation prevention systems.
No new design change; strengthens existing rationale.

**TAKE — Multi-model ensemble as diversity scaling lever (Campaign Studio
saga layer, long-term).** Using different cloud models as different
writers via OpenRouter. Not V1; persona + CoT on a single model is the
proven minimum.

---

## Domain D: Creative Generation Methods & Architecture

### Source 4 — FULL REVIEW: Shahhosseini et al. (Sharif/Isfahan, TMLR Feb 2026)

**Full title:** "Large Language Models for Scientific Idea Generation: A
Creativity-Centered Survey"  
**Venue:** Transactions on Machine Learning Research (published Feb 2026)  
**Type:** 75-page survey — synthesis, not original experimental data  
**Key contribution:** Comprehensive taxonomy of LLM creative generation
methods organized through two cognitive science frameworks, providing
the architectural blueprint for the Writer's Room pipeline.

#### Key Frameworks

**Boden's Creativity Taxonomy — three levels:**
- **Combinatorial:** Novel recombinations of existing concepts. Most
  current LLM methods. Adequate for incremental sequels, insufficient
  for genuinely surprising ones.
- **Exploratory:** Structured search within a conceptual space.
  Achievable through inference-time scaling and multi-agent systems.
  The minimum level saga sequel generation should target.
- **Transformational:** Altering the conceptual space itself. Only
  multi-agent debate shows early empirical signals.

**Rhodes' 4Ps Framework — four creativity dimensions:**
- Person (system capabilities), Process (search/interaction mechanisms),
  Press (environment/context), Product (evaluable output)
- Current methods concentrate on Process and Press; Person and Product
  are underexplored.

#### Five-Family Method Taxonomy

1. **Knowledge augmentation** (Press → combinatorial): RAG and knowledge
   graphs ground outputs but can suppress diversity. GoAI study: graph-
   based retrieval achieves novelty 3.83 vs vanilla prompting 2.44.

2. **Prompt-based steering** (Press/Process → combinatorial+): Personas,
   constraints, structured scaffolds, multilingual prompting. Persona-
   based achieves novelty 4.23 vs generic 4.1 vs default 3.78. Cross-
   lingual prompting outperforms temperature for diversity.

3. **Inference-time search** (Process → exploratory): Local, beam, and
   tree search. Tree-of-Thought achieves rewards 9.91–13.8 vs 2.04–2.27
   for single-pass CoT. Monte Carlo Thought Search: 12.47–15.6. Massive
   empirical gains at compute cost — acceptable for design-time saga
   generation.

4. **Multi-agent collaboration** (Process → potentially
   transformational): VirSci: multi-agent outperforms single-agent on
   human-rated novelty (3.78 vs 3.10–3.22), feasibility (5.24 vs
   4.78–4.94), effectiveness (4.95 vs 4.43–4.77). AI co-scientist
   independently rediscovered an unpublished gene-transfer mechanism.

5. **Parameter adaptation** (Person): SFT, RL, DPO/CrPO/DivPO.
   CycleResearcher: 5.15–5.38 vs 4.31 baseline, 24–35% acceptance vs
   0%. CrPO: novelty 6.8–7.9 vs SFT ~5.7. Outside V1 scope (we
   consume models as-is).

#### Additional Findings

**Knowledge augmentation suppresses diversity:** Higher retrieval
quality reduces output diversity as models overfit to retrieved passages.
Reinforces Paper 3's seeding dead-end from a completely independent
angle.

**RLHF creates a safe attractor basin:** Alignment training reduces
output entropy. Even "be radically original" prompts cannot escape this
basin. This is architectural, not a prompting problem.

**Constraint-based / denial prompting:** Systematically forbidding
common solutions pushes LLMs into novel output regions. Complementary
to personas.

**MAS fragility caveat (Bitter Lesson):** Hand-tuned multi-agent
orchestration is brittle and advantages diminish as base models improve.
MAS best suited where interaction itself is the primary source of value.

#### Design Impact

**TAKE — Tree/branching search over candidate spines (Campaign Studio
saga layer, Stage 3).** 4–7x single-pass rewards. Design-time compute
makes this feasible.

**TAKE — Debate/critique phase with critic agent (Campaign Studio saga
layer, Stage 4).** Generator-discriminator loop with persona-primed
writers generating, critic challenging coherence and quality.

**TAKE — Graceful degradation (Campaign Studio saga layer, architectural
principle).** Writer's Room works with N ≥ 1 writers. Do not hard-wire
agent count. MAS overhead can reduce as models improve.

**TAKE — Denial constraints against prior campaign repetition (Campaign
Studio saga layer, Stage 2).** Forbid repeating prior campaign's conflict
type, resolution structure, and most obvious sequel direction.

**TAKE — Prior campaign is context for convergence, not input for
divergence (Campaign Studio saga layer, architectural constraint).**
Knowledge augmentation suppresses diversity; prior campaign enters at
Stage 4 (evaluation), not Stage 2 (generation).

**TAKE — RLHF attractor basin makes Writer's Room architecturally
necessary (Campaign Studio saga layer, architectural constraint).**
The multi-stage pipeline is required to overcome a fundamental property
of aligned models, not merely to optimize outcomes.

**REJECT — Multilingual prompting.** Interesting but impractical for
English-output saga generation. Persona intervention achieves stronger
partitioning.

---

## Cross-Cutting Synthesis

### Theme 1: The LLM Diversity Deficit

Sources 3, 4, 6, 7, and 9 converge: LLMs produce less diverse outputs
than humans, the deficit is mechanistically understood, and it is worse
for same-prompt generation (exactly the saga generation scenario).

The mechanisms are: knowledge aggregation during pre-training collapses
diverse human mental models into a centralized distribution (Source 3);
RLHF further compresses toward aggregate preferences (Sources 3, 4);
autoregressive decoding causes within-session fixation (Source 3);
semantic and syntactic similarity are coupled in LLMs but decoupled in
humans (Source 7); and larger, more capable models are less variable
(Sources 4, 7).

The interventions that work: ordinary personas recover knowledge
partitioning (2.6x default, exceeding humans); CoT breaks fixation;
combined persona + CoT surpasses human diversity by 26% (Source 3).
Tree search achieves 4–7x single-pass quality (Source 4). Multi-agent
debate produces statistically significant improvements (Source 4).

The interventions that don't work: temperature (Sources 3, 7), seeding
with diverse starting points (Source 3), "be creative" instructions
(Source 4).

### Theme 2: Evaluation Requires Decomposition

Sources 1, 5, 6, and 4 converge: creative output cannot be assessed
with a single quality score. Quality, novelty, and diversity are
orthogonal (Source 6). Pairwise comparison with shared context
outperforms isolated scoring (Source 5). Evaluation is the field's most
critical bottleneck (Source 4). A trained small model can outperform
frontier models at creativity judgment (Source 5).

### Theme 3: LLM Prose Has Systematic Biases

Sources 2, 8, 9, and 11 converge: LLM-generated narrative exhibits
measurable, consistent biases — positivity in NPC relationships (Source
9, statistically significant across 1,200+ stories), action-emotion
incoherence at transition points (Source 8), sensory channel monotony
and rhythm repetition (Source 2), and gravitational pull toward familiar
narrative archetypes (Source 11, theoretical).

These biases are addressed by: the prose diagnostic signal (Source 2,
combining detection from Sources 8 and 9), the anti-positivity-bias
prompt instruction (Source 9), the six prose degradation prevention
systems, and anti-archetype specifications (Source 11).

### Theme 4: The Two-System Advantage

Sources 1, 4, 10, 12, and 13 converge: the separation between Game
Engine (runtime, latency-sensitive, single-pass) and Campaign Studio
(design-time, multi-pass, no latency pressure) is validated by the
research landscape.

Runtime prose generation cannot use tree search, multi-agent debate, or
multi-pass validation — latency prohibits it. But design-time spine
generation can use all of these. The Campaign Studio's advantage is
design-time compute. This separation enables the Writer's Room
architecture (Source 4), recursive consistency validation (Source 12),
NPC relationship network validation (Source 9), and scene-type-aware
context optimization (Source 10).

### Theme 5: The Physics-Before-Imagination Invariant

Sources 1 and 10 converge: the mechanical layer must resolve before the
narrative layer generates. Source 1 provides the formal name and
architectural justification. Source 10 provides empirical evidence that
structured state helps action-oriented narration but hurts introspective
narration — confirming that the relationship between mechanics and
narrative requires careful, scene-type-aware management.

---

## Design Impact Registry

### Changes Applied to Project Documents

| Source | Target Document | Section | Change | Version |
|--------|----------------|---------|--------|---------|
| 1 (WWM) | Implementation | Section 0 | Physics-before-imagination invariant | v1.5 |
| 1 (WWM) | Implementation | Phase 2, 3 | Schema validation, cloud fallback | v1.5 |
| 2 (MiniMax) | Game Mechanics | Section 13 | Prose diagnostic signal (field reserved) | v1.1 |
| 2 (MiniMax) | LLM Evaluation | Section 8.4 | Distillation curation spec | v1.5 |
| 9 (Network) | Game Mechanics | Section 1 | Anti-positivity-bias prompt | v1.1 |
| 10 (KG) | Game Mechanics | Section 10 | Scene-type-aware context assembly | v1.2 |
| 3, 4, 5, 6, 7 | Campaign Studio | Section 6.4 | Saga layer: Writer's Room architecture | v1.1 |
| 3, 4 | Campaign Studio | Section 8 | Saga-related deferred items | v1.1 |

### Changes Deferred (Campaign Studio Design Phase)

| Source | Finding | Deferred Item |
|--------|---------|---------------|
| 8 (MLD-EA) | Per-NPC action-emotion chain | Campaign spine NPC coherence validation |
| 9 (Network) | Relationship graph validation | Campaign spine relationship network validation |
| 11 (AI STORIES) | Archetype avoidance | Mode 1 negative archetype specification |
| 12 (ASEP) | Recursive validation | Campaign spine consistency audit |
| 1 (WWM) | Typed interfaces | Campaign spine JSON schema validation |
| 3, 4 | Multi-model ensemble | Saga layer diversity scaling lever |
| 5 (CrEval) | Trained evaluator | Local model spine quality evaluator |
| 3, 4 | Persona pool | Saga layer persona pool curation |

### Items Filed but Not Committed

| Source | Item | Status |
|--------|------|--------|
| 1 (WWM) | Deterministic seeding | CONSIDER — depends on Campaign Studio UX decisions |
| 2 (MiniMax) | Turn counter for spine advancement | Late-V1 or post-V1 consideration |
| 2 (MiniMax) | Failure taxonomy for distillation eval | Post-V1, when comparing finetuned models |

---

## Open Research Questions

**1. How does persona + CoT perform on narrative structure generation
specifically?** Deng et al. tested on product ideation. The mechanism
(knowledge partitioning + fixation breaking) should generalize, but
empirical validation on campaign spine generation is needed during saga
layer implementation.

**2. What is the optimal number of writers in the Writer's Room?** The
architecture supports N ≥ 1 but the quality-vs-cost tradeoff curve is
unknown. Empirical testing needed: does going from 3 to 5 to 10 writers
produce meaningfully more diverse sequel candidates, or does diversity
plateau?

**3. How effective is the local model as a spine evaluator?** CrEval
shows a 7B evaluator can outperform frontier models at creativity
judgment, but on their specific benchmark. Evaluation on campaign spine
quality requires project-specific testing.

**4. Does the semantic-syntactic decoupling gap affect spine-level
diversity or only prose-level diversity?** Braccini et al. measured at
the text expression level. Spine diversity operates at the narrative
structure level. These may be different phenomena with different
interventions required.

**5. How do denial constraints interact with personas?** Both are Stage
2 interventions. If denial constraints are too aggressive, they may
counteract the persona's natural ideation direction. The interaction
needs empirical testing.

**6. What is the right size and composition for the persona pool?** 50+
is the working minimum based on the need for combinatorial variety
across saga generation runs. The pool needs validation: do different
subsets actually produce different sequel directions?

**7. Does the Bitter Lesson apply to the Writer's Room within the
project's timeline?** If base models become significantly more diverse
in 2026–2027, the multi-agent overhead may become unnecessary. The
graceful degradation principle handles this, but monitoring model
diversity improvements is warranted.

---

## Revision History

**v1.0 — Initial document (March 2026)**

Created as a comprehensive research catalogue absorbing all content from
STORYTELLER_V3_RESEARCH_SCOPING.md (v1.1, 8 sources) and
STORYTELLER_V3_SAGA_RESEARCH_FINDINGS.md (5 papers). Thirteen total
sources catalogued across four research domains with full reviews for
four high-impact sources and summary cards for nine supporting sources.
Includes cross-cutting synthesis across five themes, complete design
impact registry, and seven open research questions.

---

*Storyteller V3 — Research Catalogue v1.0*
*What we read. What we learned. Where it landed.*
