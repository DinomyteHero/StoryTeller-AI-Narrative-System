# Storyteller V3 — Project State Matrix

**Version:** 1.9
**Date:** June 9, 2026
**Purpose:** Single-page snapshot of every major capability's status.
This is a point-in-time view — for authoritative item-level status,
see `backlog.md`. Prevents the most common review error: mistaking a
designed-but-not-built item for a missing design, or mistaking a
deferred item for an oversight.

**How to read this document:** Each row is a capability. The four
columns after the capability name tell you: is it promised in the
Vision, is it designed, is it part of V1, and when does it get built.
"Designed" means a full spec exists and is ready for implementation.
"Reserved" means V1 includes schema fields or architecture hooks but
no active functionality.

**Authoritative source for item-level status:** Backlog v3.2.
**Authoritative source for design specs:** Game Mechanics v1.8,
Implementation v2.5, Campaign Studio Design v1.3, Campaign Studio
Implementation v1.3, Design Gap Analysis v2.0 (in `docs/reference/`),
Deferred Design and Logic Analysis v1.0 (in `docs/reference/`).

**Implementation status as of this version:** Milestones 0-3 complete.
Milestone 4 partial (Phase 17 complete, Phases 18-22 not started).
Campaign Studio CS-1 through CS-6 complete. April 2026 architecture
pivot collapsed local/cloud split into a fast/quality tier abstraction
via the unified `gm/llm_client.py` and wired the reputation echo,
behavioral availability, and era-voice systems end-to-end. **April 26
Depth & Enjoyment Pass** added memorable-moments ledger, multi-stage
thread state, evolving voice, growth recognition, NPC counter-moves,
emergent faction reactivity, side content + pivot points, tactical
state for combat / negotiation / chase, and free-form player input.
**June 9 2026 passes** (changelog has full detail): physics guardrails
(world-registry validation gate for LLM-proposed locations/facts,
dice-polarity Rule 4 enforcement, token usage accounting, narration
prompt split for provider prefix caching, choices-only quality repair);
experience shell (campaign completion + generated epilogue + finale UI,
resume recap, mechanically real incapacitation with incoming damage,
CoG-style stats panel / chapter indicator / destiny visibility /
milestone ceremony); Studio enrichment generation (beat_roles,
side_content, foreshadow registry, ending paths, thematic arguments,
antagonistic relationship pressure — generated and gate-validated, not
hand-authored); character creator flow (pitch → draft → save →
on-demand campaign generation).

**Codebase metrics:** ~29,200 lines application code, ~16,100 lines
test code, 39 test files. 992 tests pass + 13 cleanly skip
(RUN_LIVE_LLM-gated). Documentation: 23 active files in `docs/` plus
6 in `docs/reference/`.

---

## Core Turn Loop

| Capability | Vision | Designed | V1 | Build Phase |
|------------|--------|----------|-----|-------------|
| Prose narration (cloud GM) | §3, §7 | ✓ | ✓ Verified | Phase 3 |
| FFG dice engine (all 7 die types) | §6 | ✓ | ✓ Verified | Phase 1 |
| Check decision (fast tier) | §6 | ✓ | ✓ Verified | Phase 2 |
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
| Scene-type-aware context routing | §3 | ✓ | ✓ Built | Phase 7 |
| Prose diagnostic signal | §3 | ✓ | ✓ Built | Phase 13 |
| Narration distillation (QLoRA) | — | ✓ | Reserved (data instrumentation) | Post-Milestone 1 |

---

## Choice and Player Agency

| Capability | Vision | Designed | V1 | Build Phase |
|------------|--------|----------|-----|-------------|
| 2–4 choices per turn | §7 | ✓ | ✓ Verified | Phase 3 |
| Skill-tagged choices (invisible to player) | §6, §7 | ✓ | ✓ Verified | Phase 3 |
| Character-specific choice design (prompt) | §7 | ✓ | ✓ Verified (prompt instruction) | Phase 3 |
| Conditional choice availability (behavioral) | §7 | ✓ | Partial (vignettes/talents only) | Phase 13 |
| Semantic memory / choice annotation | §16 | ✓ | ✓ Built | Phase 13 |
| Choice quality validation + repair loop | §7 | ✓ | ✓ Built (on by default) | Depth pass (Apr 26) |
| Free-form player input (typed action) | §7 | ✓ | ✓ Built | Depth pass (Apr 26) |

---

## NPC System

| Capability | Vision | Designed | V1 | Build Phase |
|------------|--------|----------|-----|-------------|
| NPC state cards (knowledge, disposition, motivation) | §11 | ✓ | ✓ Verified | Phase 3 |
| NPC voice notes and behavioral envelope | §11 | ✓ | ✓ Verified | Phase 3 |
| NPC knowledge update (background task) | §11 | ✓ | ✓ Verified (minimal) | Phase 4 |
| NPC emotional state | §11 | ✓ | ✓ Built | Phase 8.5 |
| NPC relationship triangles (inter-NPC disposition) | §11 | ✓ | Not in V1 | Post-Milestone 1 |
| NPC information propagation (social graph) | §11 | ✓ | Not in V1 | Post-Milestone 1 |
| NPC voice generation (prompt template) | §11 | ✓ | ✓ Built | CS Phase 2 |
| Large-scale NPC management (3-tier relevance) | §11 | ✓ | Not in V1 | Phase 20 |
| Generative entity persistence | — | ✓ | Not in V1 | Post-Milestone 1 |
| NPC crystallized memory (sharpest impression) | §11 | ✓ | ✓ Built | Depth pass (Apr 26) |
| NPC counter-move cue (proactive pressure) | §11 | ✓ | ✓ Built | Depth pass (Apr 26) |
| Slowed emotion decay for high-stakes moods | §25 | ✓ | ✓ Built (incl. betrayed/awed/bonded) | Depth pass (Apr 26) |

---

## Campaign Pacing and Structure

| Capability | Vision | Designed | V1 | Build Phase |
|------------|--------|----------|-----|-------------|
| Multi-act campaign spine | §13 | ✓ | ✓ Verified (4-act test spine) | Phase 3 |
| Galactic context layer (per act) | §4 | ✓ | ✓ Verified | Phase 3 |
| Static act tension field | §13 | ✓ | ✓ Verified | Phase 3 |
| Post-turn reconciliation (full system) | §13 | ✓ | ✓ Built | Phase 7 |
| Act boundary detection + transition | §13 | ✓ | ✓ Built | Phase 7 |
| Within-act pacing arc (hook → turn → cliffhanger) | §13 | ✓ | ✓ Built | Phase 7 |
| Turn counter / PacingSignal model | — | ✓ | ✓ Built | Phase 7 |
| Reputation echo delivery (runtime) | §1, §11 | ✓ | ✓ Built | Architecture pivot (Apr 2026) |
| Behavioral availability signal (annotation history → choice weighting) | §7, §16 | ✓ | ✓ Built | Architecture pivot (Apr 2026) |
| Era voice anchoring (period-specific tone + period_avoid) | §4 | ✓ | ✓ Built | Architecture pivot (Apr 2026) |
| Memorable moments ledger + callback candidates | §16 | ✓ | ✓ Built | Depth pass (Apr 26) |
| Multi-stage thread state (dormant → resolved_pending_fallout → closed) | §13 | ✓ | ✓ Built | Depth pass (Apr 26) |
| Lore seeds (sensory/ritual/object/language anchors) | §3, §4 | ✓ | ✓ Built (Shadows authored) | Depth pass (Apr 26) |
| Tactical state — multi-round combat grammar | §3 | ✓ | ✓ Built | Depth pass (Apr 26) |
| Tactical state — multi-stage negotiation grammar | §3 | ✓ | ✓ Built | Depth pass (Apr 26) |
| Tactical state — chase distance bands | §3 | ✓ | ✓ Built | Depth pass (Apr 26) |
| Side content scaffold (optional encounters) | §13 | ✓ | ✓ Built (Shadows seeded) | Depth pass (Apr 26) |
| Hard pivot points (locks_off branching) | §13 | ✓ | ✓ Built (Shadows seeded) | Depth pass (Apr 26) |
| Emergent faction reactivity (player-action signals) | §1, §11 | ✓ | ✓ Built | Depth pass (Apr 26) |

---

## Character Identity and Growth

| Capability | Vision | Designed | V1 | Build Phase |
|------------|--------|----------|-----|-------------|
| Pre-built character (Keth Varso) | §16 | ✓ | ✓ Verified | Phase 1 |
| Character funnel (Timeline → Allegiance → Variant) | §8 | ✓ | Not in V1 | Phase 18 |
| Psychometric prologue (3–5 scenes, 4 axes) | §8 | ✓ | Not in V1 | Phase 18 |
| Motivation tracks (Obligation, Duty, Morality) | §10 | ✓ | ✓ Built | Phase 8 |
| Between-act processing pipeline (16 steps) | §10 | ✓ | ✓ Built | Phase 7–8 |
| Behavioral inference engine | §14 | ✓ | ✓ Built | Phase 10 |
| Character advancement (XP, skill ranks) | §14 | ✓ | ✓ Built | Phase 10 |
| Milestone reflections (talents, specializations) | §14 | ✓ | ✓ Built | Phase 12 |
| Aspiration echoes (latent Force, growth direction) | §14 | ✓ | ✓ Built | Phase 13 |
| Character voice notes (evolved through play) | §8 | ✓ | ✓ Built (evolved_voice_block overlay) | Depth pass (Apr 26) |
| Throughline question | §8 | ✓ | ✓ Verified (static, from spine) | Phase 3 |
| Background field activated in narration prompt | §8 | ✓ | ✓ Built (Praxeum chars populated) | Depth pass (Apr 26) |
| Equipment "items of meaning" handling instruction | §11 | ✓ | ✓ Built | Depth pass (Apr 26) |
| Destiny spending visible to player (UI + required interior beat) | §6 | ✓ | ✓ Built | Depth pass (Apr 26) |
| Growth recognition (between-act behavioral surface) | §14 | ✓ | ✓ Built (was Step 13 stub) | Depth pass (Apr 26) |
| Milestone scenes (NPC-acknowledgment beat required) | §14.3 | ✓ | ✓ Built (prompt strengthened) | Depth pass (Apr 26) |

---

## Mechanical Systems (Post-V1)

| Capability | Vision | Designed | V1 | Build Phase |
|------------|--------|----------|-----|-------------|
| Obligation/Duty trigger system | §10 | ✓ | ✓ Built | Phase 8 |
| Morality drift + Conflict resolution | §10 | ✓ | ✓ Built | Phase 8 |
| Talent trees (5-type taxonomy) | §14 | ✓ | ✓ Built | Phase 11 |
| Pool modification pipeline (6-stage) | §6 | ✓ | ✓ Built | Phase 11 |
| Destiny Points (light/dark pool) | §6 | ✓ | ✓ Built | Phase 11.5 |
| Force dice resolution | §9 | ✓ | ✓ Built | Phase 14 |
| Dark side temptation (pre-narration choice) | §9 | ✓ | ✓ Built | Phase 14 |
| Force powers (narrative-tagged choices) | §9 | ✓ | ✓ Built | Phase 15 |
| Equipment/loadout system | §11 | ✓ | ✓ Built | Phase 9 |
| Vehicle/starship encounters | §12 | ✓ | ✓ Built | Phase 16 |
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
| Time skip vignettes (2–3 authored scenes) | §17 | ✓ | ✓ Built | Phase 17 |
| Character-centric campaign management | §8, §17 | ✓ | Not in V1 | Post-Milestone 1 |
| Canon character voice fidelity | §4 | ✓ | Not in V1 | Phase 21 |
| Import package quality standard | §17 | **Spec complete** | Not in V1 | Phase 19 |

---

## Campaign Studio

| Capability | Vision | Designed | V1 | Build Phase |
|------------|--------|----------|-----|-------------|
| Campaign spine JSON schema (Pydantic) | — | ✓ | ✓ Built | CS Phase 1 |
| Schema contract validation | — | ✓ | ✓ Built | CS Phase 1 |
| NPC coherence validation | — | ✓ | ✓ Built | CS Phase 1 |
| Relationship network validation | — | ✓ | ✓ Built | CS Phase 1 |
| Narrative consistency audit (LLM-assisted, 3 sub-gates) | — | ✓ | ✓ Built | CS Phase 5 |
| Mode 3 (human-led with AI validation) | — | ✓ | ✓ Built | CS Phase 2 |
| Mode 2 (collaborative AI + human) | — | ✓ | ✓ Built | CS Phase 3 |
| Mode 1 (fully autonomous + human review) | — | ✓ | ✓ Built | CS Phase 4 |
| Writer's Room (saga layer, 5-stage pipeline) | — | ✓ | ✓ Built | CS Phase 4 |
| Protagonist integration layer authoring | §8 | ✓ | ✓ Built | CS Phase 2 |
| Prologue scene library | §8 | ✓ | ✓ Built | CS Phase 2 |
| Cross-era import interface | §17 | ✓ | ✓ Built | CS Phase 3 |
| Deterministic seeding | — | ✓ | ✓ Built | CS Phase 2 |
| Spine difficulty calibration | — | ✓ | ✓ Built | CS Phase 2 |
| Campaign rating/feedback system | — | ✓ | Not in V1 | Post-launch |
| Trained local evaluator (QLoRA) | — | ✓ | Not in V1 | Post-CS Phase 4 |
| Multi-model ensemble (Writer's Room) | — | ✓ | Not in V1 | Post-CS Phase 4 |
| Story architecture planning (dramatic premise, CDQ) | — | ✓ | ✓ Built | CS Phase 5 |
| Gate 4 narrative evaluation (coherence, quality, freshness) | — | ✓ | ✓ Built | CS Phase 5 |
| Stage 5 LLM-based narrative quality scoring | — | ✓ | ✓ Built | CS Phase 5 |
| Dramatic mission classification + voice modes | — | ✓ | ✓ Built | CS Phase 6 |
| Scene purpose validation model | — | ✓ | ✓ Built | CS Phase 6 |
| Enhanced generation prompts with architectural vocabulary | — | ✓ | ✓ Built | CS Phase 6 |
| Path differentiation proof (integration audit) | §8 | Partial (3.33, 3.34) | Not in V1 | Campaign Studio |

---

## Validation and Enforcement

| Capability | Vision | Designed | V1 | Build Phase |
|------------|--------|----------|-----|-------------|
| Narration word count enforcement (250–800) | §3 | ✓ | ✓ Verified (retry loop) | Phase 3 |
| Minimum 2 choices enforcement | §7 | ✓ | ✓ Verified (retry loop) | Phase 3 |
| JSON schema enforcement (fast tier) | — | ✓ | ✓ Verified | Phase 2 |
| Context package pre-submission validation | — | ✓ | ✓ Verified | Phase 3 |
| 5-category compliance test protocol | — | ✓ | Not in V1 (pre-deploy test) | Phase 1 deployment |
| Behavioral envelope enforcement | §11 | ✓ | Not in V1 | Post-Milestone 1 |
| Sustained 5-turn play quality test | — | ✓ | Not in V1 | Phase 1 deployment |
| Reconciliation error budget test | — | ✓ | ✓ Built | Phase 7 |
| Selective reconciliation escalation (zero-delta detection) | — | ✓ | ✓ Built | Architecture pivot (Apr 2026) |
| Prologue inference robustness | §8 | **Spec complete** | Not in V1 | Phase 18 |

---

## Infrastructure

| Capability | Vision | Designed | V1 | Build Phase |
|------------|--------|----------|-----|-------------|
| Unified LLM client (`gm/llm_client.py`) | — | ✓ | ✓ Built | Architecture pivot (Apr 2026) |
| Two-tier routing (fast=Flash, quality=Pro) | — | ✓ | ✓ Built | Architecture pivot (Apr 2026) |
| Provider/model capability registry (reasoning syntax) | — | ✓ | ✓ Built | Architecture pivot (Apr 2026) |
| OpenRouter `require_parameters` + `data_collection=deny` | — | ✓ | ✓ Built | Architecture pivot (Apr 2026) |
| Strict `json_schema` response_format with json_object fallback | — | ✓ | ✓ Built | Architecture pivot (Apr 2026) |
| `/health` endpoint surfacing routing config | — | ✓ | ✓ Built | Architecture pivot (Apr 2026) |
| Ollama optional offline path | — | ✗ | ✗ Removed (May 2026) | Phase 2 — see [architecture-pivot.md](architecture-pivot.md) §"Stage 4" |
| Identity drift surfacing policy (turn-to-turn) | §8, §10 | ✓ | ✓ Built | Audit closure (Apr 2026) |
| Introspection trigger conditions (explicit) | §7 | ✓ | ✓ Built | Audit closure (Apr 2026) |
| Path differentiation validation (Gate 1/3 extensions) | §8 | ✓ | ✓ Built | Audit closure (Apr 2026) |
| CS-6 pinch point firing (runtime) | — | ✓ | ✓ Built | Audit closure (Apr 2026) |
| CS-6 depth card injection (runtime) | — | ✓ | ✓ Built | Audit closure (Apr 2026) |
| CS-6 voice mode mapping (mission → voice) | — | ✓ | ✓ Built | Audit closure (Apr 2026) |

---

## Identified Gaps (Audit Findings)

Items where the audit identified missing specifications that are not
explained by intentional deferral or architecture reservation.

| Gap | Category | Audit Finding | Recommendation |
|-----|----------|--------------|----------------|
| Choice quality validation | Validation / enforcement | No post-generation validator rejects weak choices before player sees them | **Closed (Apr 26)** — `gm/choice_validator.py` enabled by default (`CHOICE_QUALITY_INLINE` flipped to `true`). Five-dimension rubric runs inline; one repair attempt on 2+ failed dimensions; fail-open if evaluator errors. |
| Prologue inference robustness | Validation / enforcement | Contradiction handling, anti-gaming, and per-axis confidence rules were under-specified | **Spec complete** — `specialist/prologue-system.md` v1.0. Awaits implementation (Phase 18). |
| Import package quality | Validation / enforcement | Format was specified, quality standard was not | **Spec complete** — `specialist/import-package-quality.md` v1.0. Awaits implementation (Phase 19). |
| Path differentiation proof | Validation / enforcement | No concrete test proves allegiances produce structurally different experiences beyond narrative wrappers | **Closed (Apr 2026)** — backlog 3.33 and 3.34 implemented in `studio/validate.py` (Gate 1 integration layer + Gate 3 allegiance diversity, 8 pure-Python checks via Jaccard token similarity). |
| Identity drift surfacing | Experience surfacing | System tracks identity accumulation well at act boundaries but does not guarantee the player feels drift during turn-to-turn play | **Closed (Apr 2026)** — `compute_identity_drift_cue` in `gm/context.py` surfaces a one-line interior cue when morality / conflict / motivation deltas cross thresholds (5-turn cooldown). Wired at all 4 turn handlers. |
| Introspection trigger logic | Experience surfacing | Introspection is supported in prompts and context routing but the trigger for when a turn should become introspective is implicit | **Closed (Apr 2026)** — `compute_introspection_trigger` in `gm/context.py` has three explicit conditions: post-Despair, post-pinch-point, mid-act dry spell. |
| Missing data directories | Infrastructure | `data/evaluation_pairs/` and `data/canon_profiles/` referenced in design docs but directories do not exist in repo | Future — create when Phase 21 or trained evaluator work begins. No impact on current functionality. |
| CS-6 closure heartbeat runtime | Runtime wiring | `check_closure_heartbeat` exists with unit tests but is not called from the live turn loop | **Closed (Apr 26)** — `compute_closure_heartbeat_instruction` in `gm/context.py`; counter on `arc_state.turns_since_last_thread_change` reset by `_post_reconciliation_cs6_hook`. |
| CS-6 foreshadow setup/payoff runtime | Runtime wiring | `ForeshadowLink` schema + setup/payoff tracking authored but no runtime detector | **Closed (Apr 26)** — `compute_foreshadow_instruction` walks `spine.foreshadow_registry`; payoff prioritized over setup; delivered IDs persisted on `arc_state.foreshadow_setups_delivered` / `foreshadow_payoffs_delivered`. |
| CS-6 contradiction arc accumulation runtime | Runtime wiring | Reconciliation returns per-turn `contradiction_tracking` but nothing aggregates it into `contradiction_arc_block` | **Closed (Apr 26)** — `accumulate_contradiction_arc` + `build_contradiction_arc_block` in `gm/context.py`; ledger capped at 8 entries; dominant movement surfaces in narration prompt. |
| Player-felt depth gaps (April 26 audit) | Experience surfacing | Engine tracks rich state but player rarely felt it (single-check collapse, cosmetic choices, world forgets, identity is a spreadsheet, NPCs are stat blocks, authored treadmill, sparse backstory) | **Closed (Apr 26)** — Depth & Enjoyment Pass A–F: memorable moments, multi-stage thread state, evolving voice, growth recognition, NPC counter-moves, faction reactivity, side content + pivot points, tactical state for combat / negotiation / chase, free-form input, lore seeds, deepened character backgrounds. See changelog 2026-04-26. |

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

---

## Revision History

**v1.8 — Depth & Enjoyment Pass (April 26, 2026)**

Synced after the depth-and-enjoyment six-phase pass that closed the
April 26 player-felt-experience audit. New rows added across Choice
and Player Agency (free-form input, choice quality on by default), NPC
System (crystallized memory, counter-move cue, slowed high-stakes mood
decay), Campaign Pacing and Structure (memorable moments, multi-stage
thread state, lore seeds, tactical state for combat / negotiation /
chase, side content scaffold, hard pivot points, emergent faction
reactivity), and Character Identity and Growth (evolved voice block,
background activation, items of meaning, destiny visibility, growth
recognition, milestone scenes with acknowledgment beat).

Three open audit findings closed: choice quality validation (now on by
default), CS-6 closure heartbeat runtime (wired), CS-6 foreshadow
setup/payoff runtime (wired), CS-6 contradiction arc accumulation
runtime (wired). New "Player-felt depth gaps" finding added and closed
in the same pass.

Self-playtest verified: 10 turns through Act 1 of Shadows, no crashes
after two bugfixes (scene_npcs variable mismatch in three handlers,
sqlite3.Row .get() error in destiny block). Reached act boundary on
turn 10 with 23 threads tracked, 2 memorable moments captured (1
callback already surfaced), 2 foreshadow setups delivered, 1 side
content engaged, tactical-state negotiation grammar activated and
cleared correctly across scene-type shifts. Opening passage threaded
5+ lore seeds and the protagonist background into the prose without
prompting.

**v1.7 — Architecture pivot + audit closures (April 25, 2026)**

Synced after the DeepSeek V4 architecture pivot and a follow-up audit
closure pass. Reputation echo runtime, behavioral availability, and
era-voice anchoring promoted from "schema only" / unlisted to
✓ Built across the matrix. New Infrastructure section captures the
unified LLM client (`gm/llm_client.py`), tier model, provider/model
capability registry, OpenRouter provider preferences, strict
`json_schema` response_format, and `/health` routing endpoint.

Three open audit findings closed: identity drift surfacing
(`compute_identity_drift_cue`), introspection trigger logic
(`compute_introspection_trigger`), and path differentiation
(backlog 3.33 + 3.34, eight new pure-Python checks in `studio/validate.py`).

CS-6 runtime wiring discovered as a hidden gap — three features
(pinch point, depth card, voice mode) had unit tests but were never
invoked from `api/game_routes.py`. Now wired and tested. Three more
CS-6 features (closure heartbeat, foreshadow, contradiction arc
accumulation) remain unwired and are tracked as new audit findings.

Selective reconciliation escalation added to the validation table.
Test counts updated: 704 pass + 12 cleanly skip + 0 fail (was 653 +
12 + 0 immediately post-pivot; +51 tests across four new files).

**v1.6 — CS-6 and metrics update (April 8, 2026)**

Added CS-5 and CS-6 capability rows to Campaign Studio section (story
architecture planning, Gate 4 evaluation, Stage 5 scoring, dramatic
mission classification, scene purpose validation, enhanced generation
prompts). Updated codebase metrics (18,600 app lines, 10,300 test
lines, 20 test files). Updated Campaign Studio status to CS-1 through
CS-6 complete. Added eval harness to metrics awareness.

**v1.5 — Audit verification corrections (April 3, 2026)**

Corrected four overclaimed statuses found during code-level audit
verification:
- Gate 4 narrative audit: phase corrected from CS-1 to CS-5 (now
  implemented via studio/narrative_eval.py)
- Reputation echo delivery: changed from "Built" to "Schema only
  (runtime pending)" — DB table exists but no runtime injection code
- Conditional choice availability: changed from "Built" to "Partial
  (vignettes/talents only)" — regular per-turn choices have no gating
- Word count enforcement: corrected range from 250-600 to 250-800
  (matches actual code in gm/cloud_gm.py)

**v1.4 — Documentation audit sync (March 17, 2026)**

Added codebase metrics to header. Backlog reference updated to v3.2.
Added missing data directories gap to Identified Gaps table. Verified
all capability statuses against actual codebase — no status changes
needed (all claims from v1.3 are accurate).

**v1.3 — Post-milestone implementation status sync (March 8, 2026)**

Updated all capability rows to reflect actual implementation state
after completion of Milestones 0-3, Phase 17, and Campaign Studio
CS-1 through CS-4. Changed 30+ rows from "Not in V1" / "Reserved"
to "✓ Built" with correct build phase. Added implementation status
summary to header.

**v1.2 — Initial matrix (March 7, 2026)**

Initial comprehensive capability matrix.

---

*Storyteller V3 — Project State Matrix v1.7*
*What's promised. What's designed. What's built. What's next.*
