# Storyteller V3 — Project State Matrix

**Version:** 1.2
**Date:** March 7, 2026  
**Purpose:** Single-page view of every major capability's status.
Prevents the most common review error: mistaking a designed-but-not-
built item for a missing design, or mistaking a deferred item for an
oversight.

**How to read this document:** Each row is a capability. The four
columns after the capability name tell you: is it promised in the
Vision, is it designed, is it part of V1, and when does it get built.
"Designed" means a full spec exists and is ready for implementation.
"Reserved" means V1 includes schema fields or architecture hooks but
no active functionality.

**Authoritative source for item-level status:** Backlog v2.9.  
**Authoritative source for design specs:** Game Mechanics v1.8,
Implementation v2.5, Campaign Studio Design v1.3, Campaign Studio
Implementation v1.3, Design Gap Analysis v2.0, Deferred Design and
Logic Analysis v1.0.

---

## Core Turn Loop

| Capability | Vision | Designed | V1 | Build Phase |
|------------|--------|----------|-----|-------------|
| Prose narration (cloud GM) | §3, §7 | ✓ | ✓ Verified | Phase 3 |
| FFG dice engine (all 7 die types) | §6 | ✓ | ✓ Verified | Phase 1 |
| Check decision (local model) | §6 | ✓ | ✓ Verified | Phase 2 |
| Scene type classification | §3 | ✓ | ✓ Verified | Phase 2 |
| Context package assembly | §3 | ✓ | ✓ Verified | Phase 3 |
| Cloud failure fallback (local narration) | — | ✓ | ✓ Verified | Phase 3 |
| Turn persistence (SQLite + WAL) | §15 | ✓ | ✓ Verified | Phase 4 |
| Memory compression (act summaries) | §15 | ✓ | ✓ Verified | Phase 4 |
| API routes (session, turn, stream) | — | ✓ | ✓ Verified | Phase 5 |
| Prose reader frontend | §2, §14 | ✓ | ✓ Verified | Phase 6 |

---

## Narration Quality

| Capability | Vision | Designed | V1 | Build Phase |
|------------|--------|----------|-----|-------------|
| Second-person present tense | §3 | ✓ | ✓ Verified | Phase 3 |
| Anti-AI-slop prohibition (banned phrases) | §3 | ✓ | ✓ Verified | Phase 3 |
| Anti-positivity-bias (NPC friction) | §11 | ✓ | ✓ Verified | Phase 3 |
| Turn-level consequence reflection | §7 | ✓ | ✓ Verified | Phase 3 |
| Forward-echoing instruction | §1 | ✓ | ✓ Verified | Phase 3 |
| Consequence-at-scale instruction | §4 | ✓ | ✓ Verified | Phase 3 |
| Risk signaling in choice text | §7 | ✓ | ✓ Verified | Phase 3 |
| Scene pacing guidance | §3 | ✓ | ✓ Verified | Phase 3 |
| Introspection choice guidance | §7 | ✓ | ✓ Verified | Phase 3 |
| Style exemplars / prompt rotation | §3 | ✓ | ✓ Verified | Phase 3 |
| Scene-type-aware context routing | §3 | ✓ | Reserved | Late V1 / Phase 7 |
| Prose diagnostic signal | §3 | ✓ | Reserved | Post-V1 |
| Narration distillation (QLoRA) | — | ✓ | Reserved (data instrumentation) | Post-Milestone 1 |

---

## Choice and Player Agency

| Capability | Vision | Designed | V1 | Build Phase |
|------------|--------|----------|-----|-------------|
| 2–4 choices per turn | §7 | ✓ | ✓ Verified | Phase 3 |
| Skill-tagged choices (invisible to player) | §6, §7 | ✓ | ✓ Verified | Phase 3 |
| Character-specific choice design (prompt) | §7 | ✓ | ✓ Verified (prompt instruction) | Phase 3 |
| Conditional choice availability (behavioral) | §7 | ✓ | Not in V1 | Phase 13 |
| Semantic memory / choice annotation | §16 | ✓ | Reserved (`choice_implications`) | Phase 13 |
| Choice quality validation + repair loop | §7 | **Spec complete** | Not in V1 | Late Phase 3 / Phase 7 |

---

## NPC System

| Capability | Vision | Designed | V1 | Build Phase |
|------------|--------|----------|-----|-------------|
| NPC state cards (knowledge, disposition, motivation) | §11 | ✓ | ✓ Verified | Phase 3 |
| NPC voice notes and behavioral envelope | §11 | ✓ | ✓ Verified | Phase 3 |
| NPC knowledge update (background task) | §11 | ✓ | ✓ Verified (minimal) | Phase 4 |
| NPC emotional state | §11 | ✓ | Reserved | Phase 7 |
| NPC relationship triangles (inter-NPC disposition) | §11 | ✓ | Not in V1 | Post-Milestone 1 |
| NPC information propagation (social graph) | §11 | ✓ | Not in V1 | Post-Milestone 1 |
| NPC voice generation (prompt template) | §11 | ✓ | Not in V1 | Campaign Studio |
| Large-scale NPC management (3-tier relevance) | §11 | ✓ | Not in V1 | Phase 20 |
| Generative entity persistence | — | ✓ | Not in V1 | Post-Milestone 1 |

---

## Campaign Pacing and Structure

| Capability | Vision | Designed | V1 | Build Phase |
|------------|--------|----------|-----|-------------|
| Multi-act campaign spine | §13 | ✓ | ✓ Verified (4-act test spine) | Phase 3 |
| Galactic context layer (per act) | §4 | ✓ | ✓ Verified | Phase 3 |
| Static act tension field | §13 | ✓ | ✓ Verified | Phase 3 |
| Post-turn reconciliation (full system) | §13 | ✓ | Not in V1 (minimal NPC update only) | Phase 7 |
| Act boundary detection + transition | §13 | ✓ | Not in V1 | Phase 7 |
| Within-act pacing arc (hook → turn → cliffhanger) | §13 | ✓ | Not in V1 | Phase 7 |
| Turn counter / PacingSignal model | — | ✓ | Not in V1 | Phase 7 |
| Reputation echo delivery | §1, §11 | ✓ | Reserved (`reputation_log` table) | Phase 7 |

---

## Character Identity and Growth

| Capability | Vision | Designed | V1 | Build Phase |
|------------|--------|----------|-----|-------------|
| Pre-built character (Keth Varso) | §16 | ✓ | ✓ Verified | Phase 1 |
| Character funnel (Timeline → Allegiance → Variant) | §8 | ✓ | Not in V1 | Phase 18 |
| Psychometric prologue (3–5 scenes, 4 axes) | §8 | ✓ | Not in V1 | Phase 18 |
| Motivation tracks (Obligation, Duty, Morality) | §10 | ✓ | Reserved (fields exist, no triggers) | Phase 8 |
| Between-act processing pipeline (10 steps) | §10 | ✓ | Not in V1 | Phase 7–8 |
| Behavioral inference engine | §14 | ✓ | Not in V1 | Phase 10 |
| Character advancement (XP, skill ranks) | §14 | ✓ | Not in V1 | Phase 10 |
| Milestone reflections (talents, specializations) | §14 | ✓ | Not in V1 | Phase 12 |
| Aspiration echoes (latent Force, growth direction) | §14 | ✓ | Not in V1 | Phase 12 |
| Character voice notes (evolved through play) | §8 | ✓ | ✓ Verified (static, from spine) | Phase 3 |
| Throughline question | §8 | ✓ | ✓ Verified (static, from spine) | Phase 3 |

---

## Mechanical Systems (Post-V1)

| Capability | Vision | Designed | V1 | Build Phase |
|------------|--------|----------|-----|-------------|
| Obligation/Duty trigger system | §10 | ✓ | Not in V1 | Phase 8 |
| Morality drift + Conflict resolution | §10 | ✓ | Reserved (`moral_weight` on turns) | Phase 8 |
| Talent trees (5-type taxonomy) | §14 | ✓ | Not in V1 | Phase 11 |
| Pool modification pipeline (6-stage) | §6 | ✓ | V1 has extensible structure | Phase 11 |
| Destiny Points (light/dark pool) | §6 | ✓ | Reserved (session fields) | Phase 11.5 |
| Force dice resolution | §9 | ✓ | Reserved (dice tables include Force) | Phase 14 |
| Dark side temptation (pre-narration choice) | §9 | ✓ | Not in V1 | Phase 14 |
| Force powers (narrative-tagged choices) | §9 | ✓ | Not in V1 | Phase 15 |
| Equipment/loadout system | §11 | ✓ | Not in V1 | Phase 9 |
| Vehicle/starship encounters | §12 | ✓ | Not in V1 | Phase 16 |
| Failure recovery calibration | §6 | ✓ | ✓ Verified | Phase 2 |

---

## Cross-Campaign Continuity

| Capability | Vision | Designed | V1 | Build Phase |
|------------|--------|----------|-----|-------------|
| Import package (mechanical + narrative state) | §17 | ✓ | Not in V1 | Phase 19 |
| Specialization continuity/dormancy/evolution | §17 | ✓ | Not in V1 | Phase 19 |
| XP rebalancing on import | §17 | ✓ | Not in V1 | Phase 19 |
| Motivation track transition | §17 | ✓ | Not in V1 | Phase 19 |
| Transition passage generation | §17 | ✓ | Not in V1 | Phase 19 |
| Time skip vignettes (2–3 authored scenes) | §17 | ✓ | Not in V1 | Phase 17 |
| Character-centric campaign management | §8, §17 | ✓ | Not in V1 | Post-Milestone 1 |
| Canon character voice fidelity | §4 | ✓ | Not in V1 | Phase 21 |
| Import package quality standard | §17 | **Spec complete** | Not in V1 | Phase 19 |

---

## Campaign Studio

| Capability | Vision | Designed | V1 | Build Phase |
|------------|--------|----------|-----|-------------|
| Campaign spine JSON schema (Pydantic) | — | ✓ | Studio schema used by Engine | CS Phase 1 |
| Schema contract validation | — | ✓ | Not in V1 | CS Phase 1 |
| NPC coherence validation | — | ✓ | Not in V1 | CS Phase 1 |
| Relationship network validation | — | ✓ | Not in V1 | CS Phase 1 |
| Narrative consistency audit (3-dimension LLM) | — | ✓ | Not in V1 | CS Phase 1 |
| Mode 3 (human-led with AI validation) | — | ✓ | Not in V1 | CS Phase 2 |
| Mode 2 (collaborative AI + human) | — | ✓ | Not in V1 | CS Phase 3 |
| Mode 1 (fully autonomous + human review) | — | ✓ | Not in V1 | CS Phase 3 |
| Writer's Room (saga layer, 5-stage pipeline) | — | ✓ | Not in V1 | CS Phase 4 |
| Protagonist integration layer authoring | §8 | ✓ | Not in V1 | CS Phase 2 |
| Prologue scene library | §8 | ✓ | Not in V1 | CS Phase 2 |
| Cross-era import interface | §17 | ✓ | Not in V1 | CS Phase 2 |
| Deterministic seeding | — | ✓ | Not in V1 | CS Phase 2 |
| Spine difficulty calibration | — | ✓ | Not in V1 | CS Phase 3 |
| Campaign rating/feedback system | — | ✓ | Not in V1 | Post-launch |
| Trained local evaluator (QLoRA) | — | ✓ | Not in V1 | Post-CS Phase 4 |
| Multi-model ensemble (Writer's Room) | — | ✓ | Not in V1 | Post-CS Phase 4 |
| Path differentiation proof (integration audit) | §8 | Partial (3.33, 3.34) | Not in V1 | Campaign Studio |

---

## Validation and Enforcement

| Capability | Vision | Designed | V1 | Build Phase |
|------------|--------|----------|-----|-------------|
| Narration word count enforcement (250–600) | §3 | ✓ | ✓ Verified (retry loop) | Phase 3 |
| Minimum 2 choices enforcement | §7 | ✓ | ✓ Verified (retry loop) | Phase 3 |
| JSON schema enforcement (local model) | — | ✓ | ✓ Verified | Phase 2 |
| Context package pre-submission validation | — | ✓ | ✓ Verified | Phase 3 |
| 5-category compliance test protocol | — | ✓ | Not in V1 (pre-deploy test) | Phase 1 deployment |
| Behavioral envelope enforcement | §11 | ✓ | Not in V1 | Post-Milestone 1 |
| Sustained 5-turn play quality test | — | ✓ | Not in V1 | Phase 1 deployment |
| Reconciliation error budget test | — | ✓ | Not in V1 | Phase 7 |
| Prologue inference robustness | §8 | **Spec complete** | Not in V1 | Phase 18 |

---

## Identified Gaps (Audit Findings)

Items where the audit identified missing specifications that are not
explained by intentional deferral or architecture reservation.

| Gap | Category | Audit Finding | Recommendation |
|-----|----------|--------------|----------------|
| Choice quality validation | Validation / enforcement | No post-generation validator rejects weak choices before player sees them | **Spec complete** — `CHOICE_QUALITY_VALIDATION_SPEC.md` v1.0. Awaits implementation (late Phase 3 or Phase 7, contingent on calibration). |
| Prologue inference robustness | Validation / enforcement | Contradiction handling, anti-gaming, and per-axis confidence rules were under-specified | **Spec complete** — `PROLOGUE_INFERENCE_SPEC.md` v1.0. Awaits implementation (Phase 18). |
| Import package quality | Validation / enforcement | Format was specified, quality standard was not | **Spec complete** — `IMPORT_PACKAGE_QUALITY_SPEC.md` v1.0. Awaits implementation (Phase 19). |
| Path differentiation proof | Validation / enforcement | No concrete test proves allegiances produce structurally different experiences beyond narrative wrappers | Open — integration coverage audit needed in Campaign Studio validation. Backlog items 3.33 and 3.34 partially address this. |
| Identity drift surfacing | Experience surfacing | System tracks identity accumulation well at act boundaries but does not guarantee the player feels drift during turn-to-turn play | Open — requires drift surface policy (prompt engineering spec, Phase 7+). |
| Introspection trigger logic | Experience surfacing | Introspection is supported in prompts and context routing but the trigger for when a turn should become introspective is implicit | Open — requires explicit trigger conditions (Phase 7+). |

---

## Beyond Planning Horizon

| Item | Source | Status |
|------|--------|--------|
| 5.1 Complete career arcs (dozens of sessions) | Vision §17 | Aspiration — no design |
| 5.2 Character continuity across real time (years) | Vision §17 | Aspiration — no design |
| 5.3 Era-spanning play (full Legends timeline) | Vision §17 | Aspiration — no design |
| 5.4 Setting extensibility (non-Star Wars) | Vision §17 | Aspiration — no design |
| 5.5 Original worldbuilding | Vision §17 | Aspiration — no design |
| 5.6 Multiplayer | GM §12 | Aspiration — no design |
| R.1–R.7 Open research questions | Research Catalogue | Require empirical investigation |

---

*Storyteller V3 — Project State Matrix v1.2*  
*What's promised. What's designed. What's built. What's next.*
