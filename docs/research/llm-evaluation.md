# Storyteller V3 — LLM Evaluation Document

**Document version:** 2.1  
**Project:** Storyteller V3  
**Last updated:** March 6, 2026  
**Scope:** Model evaluation for both the Game Engine (cloud GM narration)
and the Campaign Studio (spine generation, evaluation, and saga layer).
The local model (Qwen3.5:9B via Ollama) is evaluated for its Campaign
Studio roles. Evaluation criteria are product-only: prose quality,
instruction adherence, structured output capability, creative diversity,
cost, latency, and API compatibility. Data sovereignty and political
considerations are explicitly out of scope.

---

## 0. What Changed Since v1.5

**v2.0 is a major revision.** The document scope has expanded from Game
Engine cloud GM evaluation only to a two-system evaluation covering both
the Game Engine and the Campaign Studio. The Campaign Studio has
fundamentally different model requirements — divergent ideation, persona
instruction-following, structured JSON generation, critique quality, and
pairwise evaluation — which are documented for the first time.

**Model landscape update (March 5, 2026):**

No Game Engine model ratings changed. Existing Tier 1 and Tier 2
assessments remain accurate. The following developments are noted:

- **DeepSeek V4 is imminent.** TechNode reported March 2 that DeepSeek
  plans to release V4 "this week." A hybrid reasoning/non-reasoning
  model with 1M+ context and Engram conditional memory. If it lands
  before V1 deployment, it requires immediate compliance testing. Added
  to the watch list with a pre-allocated compliance test slot.
- **DeepSeek V3.2 pricing corrected.** Confirmed at $0.14/$0.28 per 1M
  tokens (input/output) — substantially cheaper than the $0.25/$0.40
  cited in v1.5. Cost per turn revised downward.
- **Qwen3.5-397B** remains unavailable on OpenRouter. Still flagged as
  highest priority to test when available.
- **New models on landscape:** MiniMax M2.1/M2.5, Kimi K2.5, GLM-5 are
  available on OpenRouter. None are primary GM narration candidates
  based on current benchmark profiles. MiniMax M2.5 may warrant
  evaluation for Campaign Studio roles given MiniMax's roleplay focus.
- **Lechmazur v4 scores stable.** All cited scores confirmed: Opus 4.6
  (8.53, #1), GPT-5.2 (8.51, #2), Gemini 3.1 Pro (8.22, #3).

**Structural additions:**

- New Section 1B: Campaign Studio Job Descriptions (five distinct model
  roles)
- New Section 2B: Campaign Studio Evaluation Criteria
- New Section 9: Campaign Studio Model Assessment
- New Section 12: Campaign Studio Compliance Test Protocol
- Expanded recommendations covering both systems
- Cross-references to Research Catalogue for evidence basis

---

# PART 1: GAME ENGINE — Cloud GM Narration

---

## 1A. The Game Engine Job Description

The cloud GM has one task per turn: receive a fully assembled context
package and return a 250–600 word narrative passage in second-person
present tense, followed by `---CHOICES---` and 2–4 scene-specific
choices.

This sounds simple. It isn't. The model must simultaneously:

- Sustain a literary Star Wars voice across arbitrarily long sessions
- Honor dice results without softening — failure is failure, Despair
  is Despair
- Generate choices specific to this scene and this character, never
  generic
- Maintain established NPC voices and factual continuity
- Respect the `---CHOICES---` delimiter and word-count bounds reliably
- Not add unsolicited meta-commentary, disclaimers, or safety hedges

Instruction adherence at this level of specificity eliminates more
candidates than prose quality does.

---

## 2A. Game Engine Evaluation Criteria

| Criterion | What it measures |
|---|---|
| **Prose Quality** | Literary voice, sensory specificity, Star Wars atmosphere, second-person present tense |
| **Instruction Adherence** | Delimiter compliance, word count discipline, dice result fidelity, no unsolicited hedging |
| **Choice Generation** | Scene-specificity, mechanical tagging accuracy, range of risk levels |
| **Context Retention** | Factual consistency across long sessions; NPC state tracking fidelity |
| **Prompt Compliance** | Whether the model executes the GM prompt as written, including morally complex content |
| **Cost per Turn** | Estimated USD per turn at ~3,000 input tokens + ~700 output tokens |
| **Latency** | Estimated time-to-first-token and full response at typical load |

**On Prompt Compliance specifically:**
**Confirmed** = tested and clean. **Untested** = not run against this
specific prompt; no known confirmed issues on comparable creative
fiction tasks. **Confirmed Poor** = known to hedge, refuse, or modify
output in ways that break the fiction (no model currently holds this
rating).

---

## 3. Benchmark Reference Sources

Seven creative writing benchmarks are available in the community. This
section evaluates each for relevance to the GM narration workload and
documents which ones inform this document and why.

| Benchmark | Relevant? | Why |
|---|---|---|
| Lechmazur v4 | **Yes — primary** | Constraint-following + literary craft, 7 LLM graders, directly tests what the GM does |
| Fiction.LiveBench | **Yes — context retention** | Tests long-context narrative comprehension and subtext tracking; maps directly to Context Retention criterion |
| EQ-bench Creative Writing v3 | **Yes — secondary** | Elo discrimination at the top; Slop/Repetition metrics useful; Grok 4.1 score available |
| WritingBench | **Partial** | Broad coverage dilutes fiction signal; persuasive/technical writing included alongside narrative |
| Narrator.sh | **No** | Commercial platform with genre skew; no reproducible methodology; conflict of interest |
| NC-Bench (Novelcrafter) | **No** | Tests writing assistant tasks — rewriting, summarization, translation. Not relevant to autonomous narration |
| UGI Writing Leaderboard | **No** | Censorship-resistance benchmark primarily covering open-weight models. Section 11 compliance protocol covers this more precisely for our candidates |

### On Lechmazur v4 Specifically

V4 launched November 25, 2025 with a complete grader refresh. Current
graders: Claude Sonnet 4.5 (no reasoning), DeepSeek V3.2 Exp, Gemini
3 Pro Preview, GPT-5.1 (low reasoning), Grok 4.1 Fast Reasoning, Kimi
K2-0905, Qwen 3 Max.

**Known limitation:** The grader ensemble includes models with content
safety preferences (notably Sonnet 4.5), which introduces a documented
bias toward narratives that avoid morally complex or dark content. For a
project that requires the GM to write crime fiction, coercion, and
failure without hedging, high Lechmazur scores are necessary but not
sufficient — a model can score well by writing clean, safe fiction
beautifully. The compliance test in Section 11 remains mandatory
regardless of Lechmazur ranking.

### On Fiction.LiveBench Specifically

Fiction.LiveBench (fiction.live) tests whether models genuinely
comprehend complex long-form narratives rather than performing keyword
retrieval. Questions are designed around subtext — character motivation
shifts, implicit consequences — not surface facts. Models are tested at
increasing context lengths to measure retention degradation.

This directly maps to the GM's requirement to maintain NPC state, track
what player choices implied about character, and remember established
facts across a full session. It is the only publicly available benchmark
that tests this specific capability. Scores from Fiction.LiveBench are
cited alongside context retention ratings where available.

### On EQ-bench Creative Writing v3 Specifically

Uses 32 prompts across 3 iterations, judged by Claude Sonnet 4 using a
hybrid rubric and Elo (Glicko-2) system designed to expose weaknesses
in humor, romance, spatial awareness, and unconventional perspectives.
Secondary metrics include Slop Score (frequency of AI clichés) and
Repetition Score. Both are useful for evaluating whether a model will
produce the specific literary Star Wars voice the GM prompt requires.

Known uncontrolled bias: NSFW content aversion. The benchmark does not
explicitly control for NSFW bias, meaning judge preferences may favor
outputs that avoid darker content. For compliance evaluation purposes,
this is actually useful as an inverse signal: a model that scores high
on this benchmark despite the judge's conservative preferences is
either genuinely strong on literary craft or has good safety filters —
both are relevant.

---

## 4. Tier System

**Tier 1 — Primary Candidates:** Meet all hard requirements. Realistic
choices for V1.

**Tier 2 — Viable Alternatives:** Credible capabilities with trade-offs
or unknowns. Not recommended for V1 without additional testing.

**Tier 3 — Local and Edge:** Runnable via Ollama. Not primary GM
candidates. Evaluated for `NARRATIVE_BACKEND=local` context and
Campaign Studio local roles.

---

## 5. Tier 1 — Primary Candidates

### 5.1 Claude Opus 4.6 (Anthropic)

| Criterion | Rating / Value |
|---|---|
| Prose Quality | 5 / 5 |
| Instruction Adherence | 5 / 5 |
| Choice Generation | 5 / 5 |
| Context Retention | 5 / 5 |
| Prompt Compliance | Confirmed — no known issues on mature creative fiction |
| API Compatibility | Native Anthropic SDK; OpenAI-compatible via OpenRouter |
| Cost per Turn (est.) | ~$0.033 (input $5.00/M + output $25.00/M) |
| OpenRouter Model String | `anthropic/claude-opus-4.6` |
| Latency (est.) | 3–6s to first token; 12–20s full response |
| Lechmazur Benchmark | **8.53 / 10 — #1 ranked model** |

**Notes:**
Released February 4, 2026. The current frontier of creative prose. Tops
the Lechmazur Creative Story-Writing Benchmark (v4) at 8.53/10 — the
highest score of any model evaluated. On the Arena AI Creative Writing
leaderboard (human preference voting, February 2026), Opus 4.6 holds
#2, narrowing the gap with the #1 model to 12 points across 60 ranked
models. Context window is 200K standard (1M beta).

Excluded from the V1 primary path on cost grounds only. At ~$0.033 per
turn, a 50-turn session costs ~$1.65. This is the correct model for any
session where prose quality is being evaluated. Treat it as the
reference standard.

---

### 5.2 GPT-5.2 (OpenAI)

| Criterion | Rating / Value |
|---|---|
| Prose Quality | 5 / 5 |
| Instruction Adherence | 4 / 5 |
| Choice Generation | 4 / 5 |
| Context Retention | 4 / 5 |
| Prompt Compliance | Confirmed — no known issues on mature creative fiction |
| API Compatibility | Native OpenAI SDK; OpenAI-compatible via OpenRouter |
| Cost per Turn (est.) | ~$0.015 (input $1.75/M + output $14.00/M) |
| OpenRouter Model String | `openai/gpt-5.2` |
| Latency (est.) | 2–5s to first token; 8–15s full response |
| Lechmazur Benchmark | **8.51 / 10 — #2 ranked model** |

**Notes:**
Released December 2025. On Lechmazur, GPT-5.2 scores 8.51 — just 0.02
behind Opus 4.6, a gap that is imperceptible in practice. Style analysis
notes particularly strong worldbuilding intensity, syntax complexity,
and dialogue subtext. Instruction adherence is good but one notch below
Anthropic's current frontier: word-count overshoot can occur on complex
prompts.

---

### 5.3 Claude Sonnet 4.6 (Anthropic)

| Criterion | Rating / Value |
|---|---|
| Prose Quality | 4 / 5 |
| Instruction Adherence | 5 / 5 |
| Choice Generation | 4 / 5 |
| Context Retention | 4 / 5 |
| Prompt Compliance | Confirmed — no known issues |
| API Compatibility | Native Anthropic SDK; OpenAI-compatible via OpenRouter |
| Cost per Turn (est.) | ~$0.019 (input $3.00/M + output $15.00/M) |
| OpenRouter Model String | `anthropic/claude-sonnet-4.6` |
| Latency (est.) | 2–4s to first token; 8–14s full response |
| Lechmazur Benchmark | ~8.1 / 10 |

**Notes:**
Released alongside Opus 4.6. Delivers approximately 90% of Opus 4.6's
prose quality at 57% of the cost. Instruction adherence is best-in-class
at this price tier. Context window is 1M standard.

Worth testing head-to-head against GPT-5.2: Sonnet 4.6's superior
instruction adherence may tip the balance on a structurally demanding
workload.

---

### 5.4 Grok 4.1 Fast (xAI)

| Criterion | Rating / Value |
|---|---|
| Prose Quality | 4 / 5 |
| Instruction Adherence | 3 / 5 |
| Choice Generation | 3 / 5 |
| Context Retention | 3 / 5 |
| Prompt Compliance | Confirmed — strong creative fiction compliance |
| API Compatibility | OpenAI-compatible via xAI API and OpenRouter |
| Cost per Turn (est.) | ~$0.001 (input $0.20/M + output $0.50/M) |
| OpenRouter Model String | `x-ai/grok-4.1-fast` (verify current) |
| Latency (est.) | 1–3s to first token; 5–9s full response |
| Lechmazur Benchmark | Not separately benchmarked |
| EQ-bench Creative Writing v3 | 1721.9 Elo — top 3 (self-reported) |

**Notes:**
Released November 2025. Prose quality 4/5, upgraded from initial 3/5
based on EQ-bench evidence. The gaps relative to Tier 1 leaders are
instruction adherence and context retention. Cost remains exceptional:
~$0.001 per turn. Context window is 2M tokens.

---

### 5.5 GPT-5.2-Mini (OpenAI)

| Criterion | Rating / Value |
|---|---|
| Prose Quality | 3 / 5 |
| Instruction Adherence | 3 / 5 |
| Choice Generation | 3 / 5 |
| Context Retention | 3 / 5 |
| Prompt Compliance | Confirmed — no known content refusal issues |
| API Compatibility | Native OpenAI SDK; OpenAI-compatible via OpenRouter |
| Cost per Turn (est.) | ~$0.002 (input $0.25/M + output $2.00/M) |
| OpenRouter Model String | `openai/gpt-5.2-mini` |
| Latency (est.) | 1–2s to first token; 4–7s full response |

**Notes:**
Budget tier. Not recommended as primary GM. Appropriate as cost-floor
reference or emergency fallback.

---

## 6. Tier 2 — Viable Alternatives

### 6.1 Gemini 3.1 Pro (Google)

| Criterion | Rating / Value |
|---|---|
| Prose Quality | 5 / 5 |
| Instruction Adherence | 3 / 5 |
| Choice Generation | 4 / 5 |
| Context Retention | 5 / 5 |
| Prompt Compliance | Confirmed — no known issues on creative fiction |
| API Compatibility | OpenAI-compatible via OpenRouter |
| Cost per Turn (est.) | ~$0.014 (input $2.00/M + output $12.00/M) |
| OpenRouter Model String | `google/gemini-3-1-pro-preview` (verify at GA) |
| Latency (est.) | 3–8s to first token; 14–22s full response |
| Lechmazur Benchmark | 8.22 / 10 — #3 |

**Notes:**
Released February 19, 2026, currently in preview. Prose Quality 5/5. On
Arena AI Creative Writing leaderboard holds #1 across 60 ranked models
(human preference). Context retention is the clearest mechanical
standout: 1M context window standard, best available long-context
performance.

Placed in Tier 2 on latency grounds: 14–22 second full response times
break immersion. Also in preview — pricing and model string may change
at GA. If GA resolves latency, this is a Tier 1 model. Revisit after GA.

---

### 6.2 Gemini 3 Flash (Google)

| Criterion | Rating / Value |
|---|---|
| Prose Quality | 3 / 5 |
| Instruction Adherence | 3 / 5 |
| Choice Generation | 3 / 5 |
| Context Retention | 4 / 5 |
| Prompt Compliance | Confirmed — no known issues |
| API Compatibility | OpenAI-compatible via OpenRouter |
| Cost per Turn (est.) | ~$0.004 (input $0.50/M + output $3.00/M) |
| OpenRouter Model String | `google/gemini-3-flash-preview` |
| Latency (est.) | 1–3s to first token; 5–9s full response |

**Notes:**
Prose quality trends toward functional clarity over literary atmosphere.
Grok 4.1 Fast is the better budget choice for this workload.

---

### 6.3 DeepSeek V3.2

| Criterion | Rating / Value |
|---|---|
| Prose Quality | 4 / 5 |
| Instruction Adherence | 4 / 5 |
| Choice Generation | 3 / 5 |
| Context Retention | 4 / 5 |
| Prompt Compliance | **Untested — not confirmed poor** |
| API Compatibility | OpenAI-compatible (direct or via OpenRouter) |
| Cost per Turn (est.) | ~$0.0005 (input $0.14/M + output $0.28/M) |
| OpenRouter Model String | `deepseek/deepseek-v3-2` (verify current) |
| Latency (est.) | 2–5s to first token; 8–14s full response |
| Lechmazur Benchmark | Added Feb 6, 2026 — score pending wide reporting |

**Notes:**
Released December 1, 2025. 685B MoE model. At $0.14/$0.28 per million
tokens, it is the cheapest frontier-class model available — a 50-turn
session costs approximately $0.02.

Placed in Tier 2 for one reason only: prompt compliance on morally
complex content is untested. If it passes the compliance protocol
(Section 11), it becomes a strong Tier 1 option at essentially zero
marginal cost per session.

---

### 6.4 DeepSeek V4 (Watch List)

| Criterion | Rating / Value |
|---|---|
| All criteria | **Pending release** |
| Expected availability | Imminent — TechNode reported March 2 that release is planned "this week" |
| Expected pricing | At or near V3.2 levels if DeepSeek's pricing pattern holds |
| Key features | Hybrid reasoning/non-reasoning, 1M+ context, Engram conditional memory |

**Notes:**
DeepSeek V4 has missed its original mid-February target and subsequent
windows, but credible reporting (TechNode, March 2, 2026) indicates
release is now imminent. If it launches before V1 deployment, it
requires immediate compliance testing (Section 11) — at DeepSeek
pricing with improved capabilities, it could become the primary
recommendation.

The hybrid reasoning architecture and Engram memory system are
potentially relevant to Campaign Studio roles (structured JSON
generation, long-context coherence) as well as the GM narration role.
Pre-allocate a compliance test slot.

---

## 7. Models Removed Since v1.1

**GPT-4o:** Superseded by GPT-5.2.  
**GPT-4o-Mini:** Superseded by GPT-5.2-Mini.  
**Gemini 2.0 Flash / 2.5 Pro:** Superseded by the Gemini 3 generation.  
**Aion-2.0:** Removed — no public benchmarks, no confirmed availability.  
**Qwen3-235B-A22B:** Retired. Superseded by Qwen3.5 generation.

---

## 8. Tier 3 — Local and Edge (Qwen3.5 Family)

### 8.1 Qwen3.5:9B (Local Primary — Already Deployed)

| Criterion | Rating / Value |
|---|---|
| Prose Quality | 2 / 5 |
| Instruction Adherence | 3 / 5 |
| Choice Generation | 2 / 5 |
| Context Retention | 2 / 5 |
| Prompt Compliance | Confirmed clean |
| Cost per Turn | $0.00 (local) |
| Ollama Model String | `qwen3.5:9b` (Q4_K_M, ~5.5GB) |
| Latency (est.) | 3–6s full response on RTX 4070 |

**Notes:**
The local model specified throughout the implementation. Mechanically
adequate; not literary. Strength is structured task output (JSON,
delimiter placement), not free prose. Use for loop validation and
Campaign Studio evaluation/ideation roles (see Section 9).

---

### 8.2 Qwen3.5-35B-A3B (Local Heavy — Conditional)

| Criterion | Rating / Value |
|---|---|
| Prose Quality | 3 / 5 |
| Instruction Adherence | 3 / 5 |
| Context Retention | 3 / 5 |
| Cost per Turn | $0.00 (local) |
| Ollama Model String | `qwen3.5:35b-a3b` (verify Q4_K_M fits 12GB VRAM) |
| Latency (est.) | 6–12s full response on RTX 4070 |

**Notes:**
MoE architecture activates ~3B parameters per forward pass. Best
achievable local narration ceiling on this hardware. Verify VRAM
headroom empirically.

---

### 8.3 Qwen3.5-397B (Cloud — Not Yet Available)

**Status:** Not available on OpenRouter as of March 5, 2026. Highest
priority to test when available. At 397B parameters, this is the Qwen
frontier and could be relevant for both GM narration and Campaign Studio
roles if pricing is competitive.

---

### 8.4 Path Forward: Narration Distillation

The Tier 3 prose ratings reflect the current base model ceiling. The
identified path to improvement is knowledge distillation via QLoRA
fine-tuning on cloud-generated training data.

**The mechanism:** During V1 play, every turn stores the full context
package alongside the cloud model's narration (Implementation v1.4,
`distillation_pairs` view). Over time, this builds a dataset of
high-quality input→output pairs. A QLoRA fine-tune of the 9B model on
curated pairs teaches it to produce similar prose — a narrower task
than general creative writing, where smaller models learn effectively.

**What it enables:** Tiered narration — lower-stakes scene types
handled locally, climactic beats handled by cloud. Scene type
classification (Game Mechanics Section 10) provides the routing signal.
Could reduce cloud costs by 50–70% per session.

**Dataset curation specification (v1.5).** Two filters, both must pass:
(1) Automated staleness check via the prose diagnostic prompt (Game
Mechanics Section 13) — excludes passages with sensory monotony,
repetitive openers, flat rhythm, or positivity drift. (2) Mechanical
fidelity check — verifies dice result honored, NPC voice consistency,
word count bounds, valid choices with delimiter.

**Distillation evaluation failure taxonomy (v1.5).** Five binary
failure types: reference confusion, dice softening, choice
genericization, continuity break, format violation.

**Timeline:** Post-V1. Data collection is passive during V1. Estimated
minimum: 500–1000 curated pairs (~50–100 sessions).

---

# PART 2: CAMPAIGN STUDIO — Model Requirements

---

## 1B. Campaign Studio Job Descriptions

The Campaign Studio uses LLMs for five distinct roles, each with
different capability requirements. Unlike the Game Engine (one model,
one task, real-time), the Campaign Studio operates at design-time with
no latency pressure and can use different models for different roles.

### Role 1: Divergent Structural Ideation (Saga Layer Stage 2)

Generate candidate sequel directions when primed with an ordinary
persona and CoT revision instructions. The model receives a persona
description and denial constraints (what the sequel must NOT repeat
from the prior campaign) and produces a lightweight JSON "sequel
direction" sketch.

**What matters:** Genuine diversity of structural output across
different persona primes. The model must actually shift its ideation
direction based on persona, not produce superficially reworded versions
of the same structure. Research finding: proprietary models show NO
advantage over open-source models on divergent thinking tasks
(CreativityPrism, Research Catalogue Source 6). This makes the local
model a viable candidate.

**What doesn't matter:** Prose quality. The output is structured JSON,
not narrative text.

### Role 2: Spine Refinement (Saga Layer Stage 3–4)

Expand a sequel direction sketch into a full campaign spine JSON —
acts, anchor beats, NPC roster, galactic context, character variants.
Requires complex structured output generation with interdependent
fields (NPCs referenced in anchor beats must exist in the roster; act
sequencing must be valid).

**What matters:** Complex structured output quality, internal
consistency of generated JSON, ability to follow detailed schema
constraints. This is closer to the check decision task (structured
JSON) than the narration task (free prose), but at much higher
complexity.

**What doesn't matter:** Latency. Design-time operation.

### Role 3: Debate / Critique Agent (Saga Layer Stage 4)

Evaluate a candidate sequel spine for thematic coherence with the prior
campaign, internal structural quality, and narrative plausibility.
Produce specific, actionable critique ("Vossk's betrayal in Act 3 is
not set up by Acts 1–2") rather than vague quality ratings.

**What matters:** Analytical reasoning about narrative structure. Ability
to identify specific coherence failures, missing setups, implausible
NPC trajectories. Must not be sycophantic — the critique agent needs
to find real problems, not rubber-stamp the generator's output.

**What doesn't matter:** Creative generation ability. This role is
analytical, not generative.

### Role 4: Pairwise Spine Evaluator (Saga Layer Stage 5)

Compare two candidate sequel spines against each other, with the prior
campaign as shared context. Produce a structured evaluation across
three independent axes: structural quality, novelty, and diversity.
Must rank consistently — if A > B and B > C, A > C must hold.

**What matters:** Evaluation consistency (ICC), ability to decompose
quality into independent dimensions, resistance to order effects
(comparing A-then-B should produce the same result as B-then-A).
Research finding: a trained 7B evaluator outperforms frontier models
at creativity judgment (CrEval, Research Catalogue Source 5). This
makes the local model a strong candidate for this role, especially
after fine-tuning on spine evaluation data.

**What doesn't matter:** Cost per evaluation call. The Campaign Studio
runs evaluation in tight loops — if the evaluator is local, cost is
zero and latency is the only constraint.

### Role 5: Campaign Spine Generation (Modes 1–3)

Generate campaign spine components during collaborative (Mode 3),
steered (Mode 2), or autonomous (Mode 1) authoring. This is the
broadest Campaign Studio role and overlaps with the Game Engine's
creative demands — it requires narrative craft (throughline questions,
anchor beat design, NPC voice notes) combined with structured output
(valid spine JSON).

**What matters:** Both creative quality AND structured output compliance.
This role demands the combination of the GM narration model's prose
skill and the check decision model's JSON discipline.

**What doesn't matter:** Latency beyond usability thresholds.
Multi-second response times are acceptable in an authoring tool.

---

## 2B. Campaign Studio Evaluation Criteria

| Criterion | What it measures | Relevant Roles |
|---|---|---|
| **Divergent Ideation** | Genuine structural diversity under persona priming; not surface rewording | Role 1 |
| **Persona Instruction-Following** | Whether the model actually shifts output direction based on persona description | Role 1 |
| **Complex Structured Output** | Valid JSON generation with interdependent fields; schema compliance at spine complexity | Roles 2, 5 |
| **Analytical Critique** | Ability to identify specific narrative coherence failures; non-sycophantic evaluation | Role 3 |
| **Pairwise Consistency** | Evaluation transitivity, order-effect resistance, decomposed scoring | Role 4 |
| **Creative Quality** | Throughline question craft, anchor beat design, NPC voice distinctiveness | Role 5 |
| **Cost per Pipeline Run** | Total cost of a full saga generation pipeline (5 stages, multiple candidates) | All |

**No existing public benchmark tests these criteria directly.** The
Lechmazur benchmark tests constraint-following in short fiction, which
is adjacent to Roles 2 and 5 but does not test divergent ideation,
critique, or pairwise evaluation. Campaign Studio model selection will
require project-specific testing during the Campaign Studio build
phase, informed by the criteria above.

---

## 9. Campaign Studio Model Assessment

### 9.1 Recommended Model Assignments

Based on research evidence (Research Catalogue, Domains C and D) and
the role requirements above:

**Role 1 (Divergent Ideation): Local model (Qwen3.5:9B)**

Research basis: No proprietary model advantage on divergent thinking
(CreativityPrism). The persona + CoT intervention produces diversity
through prompt engineering, not model capability. The local model's
structured output strength (JSON generation) is sufficient for the
lightweight "sequel direction" schema. Zero API cost enables high-volume
candidate generation.

Assessment: **Viable — test during saga layer build.** The key
empirical question is whether the 9B model responds meaningfully to
persona priming on narrative structure tasks specifically (tested on
product ideation in the literature). If it doesn't, fall back to the
cloud model for this role.

**Role 2 (Spine Refinement): Cloud model**

The complexity of a full campaign spine JSON exceeds what the local
model can reliably generate. This requires the cloud model's stronger
reasoning and instruction-following. GPT-5.2 or Sonnet 4.6 are the
natural candidates — both have strong structured output compliance.

Assessment: **Cloud model required.** The cost is acceptable because
spine refinement runs once per surviving candidate (post-pruning), not
once per initial direction.

**Role 3 (Critique Agent): Cloud model or local model (test both)**

The critique role requires analytical reasoning but not creative
generation. The local model may be sufficient if it can identify
specific narrative coherence failures in a spine. The cloud model will
be more reliable. Test both — if the local model performs adequately,
the debate loop can run at zero marginal cost.

Assessment: **Test both during Campaign Studio build.** Start with cloud
model for reliability, test local model as a cost optimization.

**Role 4 (Pairwise Evaluator): Local model (long-term target)**

Research basis: Trained 7B evaluator outperforms frontier models at
creativity judgment (CrEval). The local model is the correct long-term
target for this role, but requires fine-tuning on spine evaluation
data that doesn't exist yet.

Assessment: **Cloud model initially. Local model after fine-tuning.**
Pre-V1: use cloud model. Post-saga-layer: collect evaluation data and
fine-tune the local model. Architecture should support swapping the
evaluator from cloud to local via configuration.

**Role 5 (Spine Generation, Modes 1–3): Cloud model**

Full spine generation requires both creative quality and complex
structured output. This is a cloud model task. The same model used for
Game Engine GM narration is the natural choice, since the creative
quality requirements are similar.

Assessment: **Cloud model required.** Same model as Game Engine primary.

### 9.2 Campaign Studio Cost Estimate

A full saga generation pipeline run (one sequel spine):

| Stage | Model | Calls | Est. Cost (GPT-5.2) |
|---|---|---|---|
| Stage 1 (Persona Assignment) | Config only | 0 | $0.00 |
| Stage 2 (Divergent Generation) | Local | 5–10 | $0.00 |
| Stage 3 (Branching Search) | Cloud | 3–5 | $0.05–0.10 |
| Stage 4 (Debate/Critique) | Cloud | 5–10 | $0.10–0.20 |
| Stage 5 (Evaluation) | Cloud (initially) | 3–6 | $0.05–0.10 |
| **Total** | | **16–31** | **$0.20–0.40** |

At DeepSeek V3.2 pricing, the same pipeline would cost approximately
$0.005–0.01 total. If V4 launches at similar pricing, it could reduce
saga generation to effectively free.

---

## 10. Game Engine Summary Table

| Model | Tier | Prose | Adherence | Compliance | Cost/Turn | Lechmazur | Status |
|---|---|---|---|---|---|---|---|
| Claude Opus 4.6 | 1 | ★★★★★ | ★★★★★ | Confirmed | ~$0.033 | 8.53 (#1) | Reference standard |
| GPT-5.2 | 1 | ★★★★★ | ★★★★ | Confirmed | ~$0.015 | 8.51 (#2) | **Recommended primary** |
| Claude Sonnet 4.6 | 1 | ★★★★ | ★★★★★ | Confirmed | ~$0.019 | ~8.1 | Worth head-to-head vs GPT-5.2 |
| Grok 4.1 Fast | 1 | ★★★★ | ★★★ | Confirmed | ~$0.001 | N/A | **Recommended post-credits** |
| GPT-5.2-Mini | 1 | ★★★ | ★★★ | Confirmed | ~$0.002 | N/A | Budget fallback only |
| Gemini 3.1 Pro | 2 | ★★★★★ | ★★★ | Confirmed | ~$0.014 | 8.22 (#3) | Latency; preview; #1 human pref |
| Gemini 3 Flash | 2 | ★★★ | ★★★ | Confirmed | ~$0.004 | N/A | Low-cost fallback |
| DeepSeek V3.2 | 2 | ★★★★ | ★★★★ | **Untested** | ~$0.0005 | TBD | Test compliance before deploy |
| DeepSeek V4 | Watch | — | — | **Pending** | TBD | N/A | Imminent — pre-allocate test slot |
| Qwen3.5-35B-A3B | 3 | ★★★ | ★★★ | Assumed | $0.00 | N/A | Best local option |
| Qwen3.5:9B | 3 | ★★ | ★★★ | Confirmed | $0.00 | N/A | **Active local model** |

---

## 11. Game Engine Compliance Test Protocol

Before any **Untested** model is considered for the primary GM role:

1. **Failure narration.** Feed `failure_threat` with 3 net failures.
   Verify unambiguous failure with deteriorating circumstances. Reject
   if hedged or reframed as partial success.

2. **Despair narration.** Feed `success_threat` with 1 Despair. Verify a
   critical negative consequence alongside the success. Reject if
   Despair is omitted or softened.

3. **Crime content.** Feed a smuggling/deception scene (Keth Varso
   standard context). Verify criminal activity is written as dramatized
   fiction without editorial caveats.

4. **Coercion content.** Feed a scene with NPC using coercion or threat.
   Verify the model writes it straight, in character, without hedging.

5. **Delimiter and length.** Run 5 consecutive turns. Verify
   `---CHOICES---` is present in all 5, word count is 250–600 in all 5,
   choices are 2–4 in all 5.

6. **Behavioral envelope compliance.** Create 5 test scenarios where
   narrative pressure pushes an NPC toward violating their behavioral
   envelope (e.g., "Vossk never appears in person" — player threatens
   Vossk's family; "Doss never confronts directly" — player charms
   Doss aggressively). Verify the model respects the envelope in all 5
   scenarios. If any fail, add explicit prompt reinforcement to the NPC
   state card: "HARD CONSTRAINT: {npc_name} will NEVER {envelope}.
   Violating this constraint is equivalent to producing incorrect dice
   results." Re-test after reinforcement.

Pass requires clean output across all six categories across at minimum
5 test turns per category.

---

## 12. Campaign Studio Compliance Test Protocol

Before any model is deployed in a Campaign Studio role:

1. **Persona responsiveness.** Prime the model with 5 different ordinary
   personas and the same sequel generation prompt. Verify that outputs
   are structurally distinct — different conflict types, different
   settings, different thematic directions. Reject if 3+ of 5 outputs
   share the same primary conflict or resolution structure.

2. **Denial constraint adherence.** Provide a prior campaign summary
   and explicit denial constraints ("do NOT repeat a betrayal arc; do
   NOT set the sequel in the same location"). Verify constraints are
   honored. Reject if any denied element appears.

3. **Spine JSON validity.** Generate a full campaign spine and validate
   against the Campaign Studio Section 4 schema. All NPCs referenced
   in anchor beats must exist in the roster. All acts must be
   sequentially numbered. All required fields must be present. Reject
   on any schema violation.

4. **Critique specificity.** Feed a deliberately flawed spine (NPC
   betrayal without setup, dangling plot thread, tonal inconsistency)
   and ask for critique. Verify the model identifies specific failures
   with actionable detail. Reject if critique is generic ("the spine
   could be improved") or fails to identify the planted flaws.

5. **Pairwise consistency.** Present the same two candidate spines in
   both orders (A-then-B and B-then-A). Verify the ranking is
   consistent. Run 5 pairs. Reject if more than 1 of 5 shows order
   reversal.

---

## 13. Implementation Spec Update Requirements

The following changes to `STORYTELLER_V3_IMPLEMENTATION.md` are
required. Model string corrections only — no architectural changes.

| Field | Current (spec v1.6) | Should be |
|---|---|---|
| Cloud provider (current) | OpenAI (`gpt-5.2`) | No change needed |
| Cloud provider (planned) | OpenRouter (`x-ai/grok-4.1-fast`) | No change needed |

**v2.0 note:** The v1.3 model string updates have been applied to the
Implementation Document at v1.3 and confirmed correct at v1.6. No
further model string changes are required at this time. If DeepSeek V4
releases and passes compliance testing, a new model string entry will
be needed.

---

## 14. Recommendations

### Game Engine V1

**Active primary:** GPT-5.2. `CLOUD_MODEL=gpt-5.2`. Best prose-to-cost
ratio among confirmed models.

**Post-credits primary:** Grok 4.1 Fast.
`CLOUD_MODEL=x-ai/grok-4.1-fast`. Verify model string against current
OpenRouter docs before switching.

**Reference standard:** Claude Opus 4.6.
`anthropic/claude-opus-4.6`. Use for prose quality evaluation sessions.

**Worth a direct test:** Claude Sonnet 4.6 vs GPT-5.2. If Sonnet's
instruction adherence tips the balance, it may be the better active
primary.

**Test before committing:** DeepSeek V3.2. If compliance passes, it
belongs in Tier 1 at essentially zero cost.

**Watch:** DeepSeek V4. If it releases this week and passes compliance,
it could change the primary recommendation.

### Campaign Studio

**Divergent ideation (Role 1):** Start with Qwen3.5:9B local. Test
persona responsiveness. Fall back to cloud if local model doesn't
respond to persona priming on narrative structure tasks.

**Spine refinement (Role 2) and generation (Role 5):** Same cloud model
as Game Engine primary (GPT-5.2 or Sonnet 4.6). Leverage existing
prompt engineering and compliance validation.

**Critique (Role 3):** Cloud model initially. Test local model as cost
optimization during Campaign Studio build phase.

**Evaluation (Role 4):** Cloud model initially. Fine-tune local model
on spine evaluation data post-saga-layer. Architecture must support
evaluator swap via configuration.

**Cost optimization path:** If DeepSeek V3.2 or V4 passes compliance,
the entire Campaign Studio pipeline could run at near-zero cost per
saga generation. This is the highest-leverage compliance test in the
project.

---

## 15. Revision History

**v2.1 — Compliance test Category 6 (March 2026)**

1. **Category 6 added to §11 Game Engine Compliance Test Protocol.**
   Behavioral envelope compliance: 5 test scenarios where narrative
   pressure pushes NPCs toward envelope violations. If failures occur,
   prompt reinforcement protocol specified. Pass requirement updated
   from "five categories" to "six categories."

**v2.0 — Two-system expansion + model landscape update (March 2026)**

Major revision expanding document scope from Game Engine only to both
Game Engine and Campaign Studio. Added Campaign Studio job descriptions
(five model roles), evaluation criteria, model assessment with
recommended role assignments, Campaign Studio compliance test protocol,
and saga generation cost estimates. Model landscape updated to March 5,
2026: DeepSeek V4 added to watch list (imminent release per TechNode),
DeepSeek V3.2 pricing corrected to $0.14/$0.28, Qwen3.5-397B status
confirmed unavailable, new models noted (MiniMax M2.5, Kimi K2.5,
GLM-5). All Game Engine ratings confirmed stable. Cross-references
established to Research Catalogue for Campaign Studio evidence basis.

**v1.5 — Distillation curation and evaluation specification**

Section 8.4 expanded with dataset curation specification. Dual-filter
criteria. Distillation evaluation failure taxonomy added. Cross-
references to Game Mechanics v1.1 and Implementation v1.5.

**v1.4 — Distillation strategy documented**

New Section 8.4: narration distillation via QLoRA fine-tuning. Cross-
references to Implementation v1.4 and Game Mechanics v1.1.

**v1.3 — Benchmark landscape review**

New Section 3: seven benchmarks evaluated. Lechmazur v4 confirmed
primary. Fiction.LiveBench and EQ-bench added as secondaries. Grok 4.1
Fast prose upgraded to 4/5. Gemini 3.1 Pro prose upgraded to 5/5.

**v1.2 — March 2026 landscape update**

Full model roster refreshed. GPT-5.2 elevated to recommended primary.
Lechmazur benchmark added as primary reference.

**v1.1:** Compliance ratings corrected. Qwen3.5 Tier 3 added.
Compliance test protocol added.

**v1.0:** Initial evaluation document.

---

*Storyteller V3 — LLM Evaluation Document v2.1*
*Two systems. Five Campaign Studio roles. Product-only criteria.*
*Verify all model strings and pricing against current provider
documentation before deployment.*
