# Storyteller V3 — Comprehensive Project Backlog

**Document version:** 2.4  
**Last updated:** March 5, 2026  
**Purpose:** Single source of truth for every planned, in-progress,
deferred, and tracked item across the entire project. Nothing should
exist as a "we talked about that" item — it lives here or it doesn't
exist.

**Organizing principle:** Items are grouped by build phase, then by
priority within each phase. Every item traces back to the document
that defines it. Items with design work complete are marked as such.
Items that need design work before implementation are flagged.

**Status definitions:**

- **DONE** — completed in a specific document version
- **DESIGNED** — design work is complete; ready for implementation
- **PARTIALLY DESIGNED** — some design work exists, gaps remain
- **NEEDS DESIGN** — concept acknowledged, no detailed design yet
- **CONCEPT ONLY** — mentioned in Vision or design docs as future intent
- **FILED** — noted for future consideration, no commitment
- **NOT STARTED** — work has not begun
- **IN PROGRESS** — actively being worked on
- **RESOLVED** — decision made, no further action required
- **MONITORING** — external dependency being tracked

---

## Phase 0: Pre-Build (Planning & Preparation)

Items that needed resolution before implementation could begin.

| # | Item | Status | Design Doc | Notes |
|---|------|--------|-----------|-------|
| 0.1 | LLM Evaluation revision — expand to cover Campaign Studio model requirements, update model landscape to March 2026 | **DONE** (LLM Eval v2.0) | LLM Evaluation | Added Campaign Studio job descriptions (five roles), evaluation criteria, model assessment, compliance test protocol, and model landscape update. |
| 0.2 | Implementation doc scope statement — add explicit "this covers Game Engine only" to Section 0 | **DONE** (Impl v1.7) | Implementation | Scope statement added. Title changed from "Full Implementation Document" to "Game Engine Implementation Document." |
| 0.3 | Decision: two standalone implementation docs vs master + children | **RESOLVED** | — | Decision: two standalone documents. Game Engine Implementation (v1.7) and Campaign Studio Implementation (v1.0) now exist as separate companion documents. |
| 0.4 | Retire superseded research docs — remove RESEARCH_SCOPING.md and SAGA_RESEARCH_FINDINGS.md from project files | **READY** | Research Catalogue replaces both | Catalogue v1.0 absorbs all content. These files should be removed from the project when the next project file cleanup happens. |
| 0.5 | First campaign spine authoring — "The Nar Shaddaa Job" full spine in Campaign Studio JSON format | **IN PROGRESS** | Impl §12, CS Design §4 | A V1-scope test spine exists in Implementation §12. It uses a simplified format (no `character_variants`, `prologue_scenes`, `variation_points`, `expected_turns`, `disposition_trajectory`). This is correct for V1 since those features aren't built. A full Campaign Studio-format spine is a Phase 3 deliverable (3.0c). |
| 0.6 | Campaign Studio Design Document — version header alignment | **RESOLVED** | CS Design | Resolved by funnel pivot: CS Design is now v1.2, CS Implementation is v1.1. Both aligned. |
| 0.7 | Campaign Studio Implementation Document — initial creation | **DONE** (CS Impl v1.0) | CS Implementation | Four build phases, Pydantic schema models, validation suite, Mode 3/2/1 paths, cross-era import, saga layer pipeline, database additions, and interaction contract specified. |

---

## Phase 1: V1 Game Engine Build

The vertical slice. Implementation doc (v1.7) specifies the full build
in six sub-phases (Phase 1 through Phase 6). All items below are V1
scope.

### Phase 1 Success Criteria (Implementation §15)

All 12 must pass:

1. Player starts as Keth Varso
2. Opening passage appears in browser
3. Player selects a choice
4. Local model correctly identifies check requirement
5. Dice pool built correctly per FFG rules
6. Dice rolled, symbols correct
7. Cloud GM narrates honoring dice result
8. Dice panel shows actual roll on demand
9. New scene-specific choices appear
10. Loop repeats for 5+ turns without errors
11. Session persists across process restart
12. `NARRATIVE_BACKEND=local` runs full loop without cloud credits

### V1 Build Items — Sub-Phase 1: The Engine (Pure Python)

| # | Item | Status | Design Doc | Impl Doc | Detail |
|---|------|--------|-----------|---------|--------|
| 1.1 | FFG dice engine (`engine/dice.py`) | **DESIGNED** | — | Impl §5.1 (full code) | Symbol tables for all 7 die types, `roll_pool()`, `RollResult` with outcome quadrant classification. Verify every symbol table against physical rulebooks before proceeding. |
| 1.2 | Character model (`engine/character.py`) | **DESIGNED** | GM §9, Vision §10 | Impl §5.2 (full code) | Pydantic models for Character, Characteristics, SkillRanks, MotivationTrack. All 33 FFG skills with governing characteristics mapped. `active_injuries: list[str]` for combat narrative tracking. |
| 1.3 | Check system (`engine/checks.py`) | **DESIGNED** | GM §1, §2, §3 | Impl §5.3 (full code) | `build_pool()` from character stats and `CheckRequest`. FFG pool construction: max(char,skill) total dice, upgrade min(char,skill) to proficiency. Difficulty enum Simple through Formidable. |
| 1.4 | Test character data file (`data/characters/keth_varso.json`) | **DESIGNED** | Vision §16 | Impl §5.4 | Keth Varso, Bothan Smuggler. Cunning 4, Agility 3, Presence 3. Deception 2, Piloting_Space 2. Obligation: Debt (15). Throughline question and voice notes included. |

### V1 Build Items — Sub-Phase 2: The Local GM

| # | Item | Status | Design Doc | Impl Doc | Detail |
|---|------|--------|-----------|---------|--------|
| 1.5 | Check decision prompt (`gm/prompts/check_decision.txt`) | **DESIGNED** | GM §1, §10 | Impl §6.1 (full prompt) | Structured prompt template with character summary, story position, tension calibration, scene description, player action. Returns JSON with `requires_check`, skill, difficulty, `scene_type`, `moral_weight`, reasoning. |
| 1.6 | Local GM module (`gm/local_gm.py`) | **DESIGNED** | — | Impl §6.2 (full code) | Ollama calls to Qwen3.5:9B. JSON schema enforcement via `format` parameter. Skill normalization. 3-retry with validation. Fallback: `requires_check=false` after all retries fail. |
| 1.7 | Check decision schema validation (Pydantic) | **DESIGNED** | Research Cat. Source 1 | Impl §6.2 (note) | Production robustness upgrade: Pydantic model validation on local model output enforcing enum membership for skill, difficulty, scene_type. Same fallback behavior on failure. |
| 1.8 | Scene type classification | **DESIGNED** | GM §10 | Impl §6.1 | Six types: combat, chase, infiltration, social, exploration, introspection. Classified by local model as part of check decision. Default fallback: "social" on missing/invalid. |
| 1.9 | `moral_weight` field | **DESIGNED** | GM §9 | Impl §6.1 | Integer 0–3 in check decision response. Tracks Morality Conflict accumulation per turn. Column exists in `turns` table. |
| 1.10 | Failure recovery difficulty calibration | **DESIGNED** | GM §2 | Impl §6.2 | `decide_check()` accepts `recent_failure_count: int`. When ≥ 2, injects calibration note preferring average over hard difficulty. `{failure_calibration}` placeholder in prompt template. |

### V1 Build Items — Sub-Phase 3: The Cloud GM

| # | Item | Status | Design Doc | Impl Doc | Detail |
|---|------|--------|-----------|---------|--------|
| 1.11 | Narration prompt template (`gm/prompts/narration.txt`) | **DESIGNED** | Vision §3, GM §1 | Impl §7.1 (full prompt) | Second-person present tense. Character summary, voice, story context, NPC states, location, galactic context, dice result block, dice interpretation guide. `---CHOICES---` delimiter. 250–600 word bounds. Skill tag convention `[Deception]` stripped before player display. |
| 1.12 | Context package assembly (`gm/context.py`) | **DESIGNED** | GM §10 | Impl §7.2 (full code) | `ContextPackage` dataclass. `NPCState` with numeric disposition (0.0–1.0), `disposition_label()`, knowledge states, `behavioral_envelope`, `voice_notes`. `ArcState` with campaign, act, tension, open threads. `TurnMemory` for recent turns. `build_dice_result_block()`, `build_npc_block()`, `build_open_threads_block()`. |
| 1.13 | Cloud GM module (`gm/cloud_gm.py`) | **DESIGNED** | LLM Eval §14 | Impl §7.3 (full code) | OpenAI-compatible SDK. Provider-agnostic via env vars. `_build_prompt()`, `_parse_response()` with delimiter validation, word count enforcement, choice extraction and skill tag stripping. `narrate_turn()` with retry logic. `narrate_turn_stream()` for SSE. |
| 1.14 | Cloud failure fallback path | **DESIGNED** | Research Cat. Source 1 | Impl §7.3 | `_narrate_with_local_fallback()`: simplified prompt to Ollama on cloud timeout (20s) or API error. Per-turn fallback — next turn reattempts cloud. Counter tracks consecutive fallbacks; UI indicator after 3+. Player never sees error. |
| 1.15 | Context package validation | **DESIGNED** | Research Cat. Source 1 | Impl §7.2 (note) | Pre-cloud-submission structural checks: `situation` and `location` non-empty, `active_npcs` populated, `recent_turns` non-empty (except Turn 1), `voice_notes` populated. Validation failure = bug, log error, surface generic pause passage. |
| 1.16 | `prose_diagnostic` field reserved on ContextPackage | **DESIGNED** | GM §13 | Impl §7.2 | Optional dict, null in V1. Schema reservation ensures future prose diagnostic signal (post-V1) is not a structural change. |
| 1.17 | Anti-positivity-bias prompt instruction | **DESIGNED** | GM §1, Research Cat. Source 9 | Impl §7.1 | Explicit counterbalance in narration prompt YOUR TASK section: NPCs with disposition < 0.5 must exhibit friction/reluctance. Avoid uniformly warm interactions. Conflict is a feature, not a problem. |
| 1.18 | Turn-level consequence reflection instruction | **DESIGNED** | GM §1 | Impl §7.1 | Prompt addition: "The opening of your passage must clearly reflect the player's specific choice. Do not write a passage that could follow from any choice." |
| 1.19 | Forward-echoing instruction | **DESIGNED** | GM §4 | Impl §7.1 | Prompt addition: "When introducing environmental or NPC details, prefer details that could become relevant later over purely atmospheric ones. Plant seeds." |
| 1.20 | Consequence-at-scale instruction | **DESIGNED** | GM §4 | Impl §7.1 | Prompt addition: "When the player makes a choice with significant implications, within 2–3 turns show at least one moment where the ripple reached beyond the immediate scene." |
| 1.21 | Risk signaling convention in choice text | **DESIGNED** | GM §7 | Impl §7.1 | Prompt addition: "Write choices requiring a check with language that conveys uncertainty/risk. Write choices without a check with language that conveys confidence/certainty." |
| 1.22 | `sequence` field on ContextPackage | **DESIGNED** | GM §3 | Impl §7.2 (v1.6) | `sequence: Optional[dict]` for multi-beat combat/chase tracking. Tracks which beat the player is on, prior beat outcomes, resolution conditions. |
| 1.23 | `galactic_context` field | **DESIGNED** | GM §4 | Impl §7.2 (v1.6) | String field in `ContextPackage`. Per-act worldbuilding data from campaign spine. Injected into narration prompt alongside situation and location. |

### V1 Build Items — Sub-Phase 4: State and Persistence

| # | Item | Status | Design Doc | Impl Doc | Detail |
|---|------|--------|-----------|---------|--------|
| 1.24 | SQLite database + WAL mode (`state/db.py`) | **DESIGNED** | — | Impl §8.1 (full code) | Schema: `sessions`, `turns`, `npc_states`, `act_summaries`, `reputation_log` tables. `distillation_pairs` view. WAL mode on every connection. Foreign keys enabled. |
| 1.25 | Session management (`state/session.py`) | **DESIGNED** | GM §6, §11 | Impl §8.2 (full code) | `create_session()`, `log_turn()` (with `context_json` and `scene_type` for distillation), `get_recent_turns()`, `get_act_summaries()`, `get_session()`, `get_turn_count()`. |
| 1.26 | Memory compression (`state/memory.py`) | **DESIGNED** | GM §11, Vision §15 | Impl §8.3 (full code) | `compress_act_turns()` via local model. 100–150 word prose summary. `compress_if_needed()` as async BackgroundTask. Threshold: 8 uncompressed turns. Compression failure is logged, not raised. |
| 1.27 | Distillation data instrumentation | **DESIGNED** | LLM Eval §8.4 | Impl §8.1 (v1.4) | `context_json` and `scene_type` columns on `turns` table. `distillation_pairs` SQL view pairing context packages with cloud narration. Passive instrumentation — zero runtime cost, enables future fine-tuning. |
| 1.28 | Reputation log table | **DESIGNED** | GM §1 | Impl §8.1 (v1.6) | `reputation_log` table: session_id, turn_number, one-sentence summary of notable actions. GM prompt receives 3–5 most recent entries for occasional surfacing through NPC dialogue. |
| 1.29 | Act summary `character_drift` field | **DESIGNED** | GM §11 | Impl §8.1 (v1.6) | `character_drift TEXT` column on `act_summaries`. One-sentence behavioral pattern observation per act, generated alongside compression summary. |

### V1 Build Items — Sub-Phase 5: API

| # | Item | Status | Design Doc | Impl Doc | Detail |
|---|------|--------|-----------|---------|--------|
| 1.30 | API routes (`api/main.py`, `api/game_routes.py`) | **DESIGNED** | — | Impl §9 | Three routes: `POST /session`, `POST /session/{id}/turn`, `GET /session/{id}`. Streaming variant: `POST /session/{id}/turn/stream` (SSE). Background compression triggered after turn write. `used_local_narration` in response. |

### V1 Build Items — Sub-Phase 6: Frontend

| # | Item | Status | Design Doc | Impl Doc | Detail |
|---|------|--------|-----------|---------|--------|
| 1.31 | Frontend (`web/index.html`) | **DESIGNED** | Vision §2, §14 | Impl §10 | Single-file prose reader. Dark bg, light text, 650px max width. Choices as full-width buttons (≥44px touch). Dice panel collapsed by default (FFG color-coded). Word-by-word streaming via SSE. Local narration warning when active. No avatars, maps, or character sheet in V1. Mobile readable. |

### V1 Build Items — Cross-Cutting

| # | Item | Status | Design Doc | Impl Doc | Detail |
|---|------|--------|-----------|---------|--------|
| 1.32 | Configuration / environment variables | **DESIGNED** | LLM Eval §14 | Impl §11 | `.env.example` with NARRATIVE_BACKEND, CLOUD_PROVIDER, CLOUD_MODEL, OLLAMA_URL, LOCAL_MODEL, DB_PATH, PORT, DEV_MODE, STREAMING_ENABLED. OpenRouter model string format documented. |
| 1.33 | Test campaign spine ("The Nar Shaddaa Job") | **DESIGNED** | Vision §16 | Impl §12 | Four-act spine with per-act galactic context, NPC roster (Vossk, Doss) with full state cards. Simplified V1 format — no character variants, prologue scenes, or variation points. |
| 1.34 | `CLAUDE.md` for Claude Code | **DONE** | Impl §3 | — | Abridged Game Engine implementation spec for Claude Code context. Covers architecture, tech stack, build phases 1-6, success criteria, critical rules (3, 4, 5, 11), physics-before-imagination invariant, repo structure, and doc reading order. |
| 1.35 | `pyproject.toml` | **DESIGNED** | — | Impl §11 | Dependencies: fastapi, uvicorn, openai≥1.30.0, httpx, pydantic≥2.0.0, python-dotenv. Dev: pytest, ruff. |

### V1 Pre-Deployment Tasks (Not Code)

| # | Item | Status | Detail |
|---|------|--------|--------|
| 1.36 | Cloud model compliance testing (5-category protocol) | **NOT STARTED** | LLM Eval §11. Five categories: failure narration, Despair narration, crime content, coercion content, delimiter+length. Must run on whichever model is active primary before live use. 5 test turns per category minimum. |
| 1.37 | Grok 4.1 Fast compliance test | **NOT STARTED** | LLM Eval §5.4. Planned post-credits path. Needs §11 protocol validation. Currently instruction adherence 3/5 — verify delimiter and word count discipline specifically. |
| 1.38 | DeepSeek V3.2 compliance test | **NOT STARTED** | LLM Eval §6.3. At ~$0.0005/turn, passes compliance → Tier 1 at essentially zero cost. Content sensitivity on morally complex scenes is the unknown. |
| 1.39 | Claude Sonnet 4.6 vs GPT-5.2 head-to-head | **NOT STARTED** | LLM Eval §14. Sonnet 4.6's 5/5 instruction adherence vs GPT-5.2's 5/5 prose on the specific GM narration prompt. Worth testing before committing active primary. |
| 1.40 | DeepSeek V4 — monitor for release + compliance test | **MONITORING** | LLM Eval §6.4. TechNode reported March 2 that release is imminent. Pre-allocate compliance test slot. Hybrid reasoning + Engram memory potentially relevant to both Game Engine and Campaign Studio. |
| 1.41 | Qwen3.5-397B — monitor for OpenRouter availability | **MONITORING** | LLM Eval §8.3. Highest priority cloud test when available. 397B parameters could be relevant for both GM narration and Campaign Studio roles. |
| 1.42 | Sustained play quality test (5-turn) | **NOT STARTED** | Beyond §11 structural compliance. 5-turn continuous play evaluating: prose quality degradation turn-over-turn, NPC voice consistency (does Doss still sound like Doss?), choice template repetition (do choice structures start repeating?), thread continuity (are planted seeds remembered?), negative disposition narration (are hostile NPCs written as hostile?). |
| 1.43 | 13th success criterion — prose quality | **NOT STARTED** | Per independent evaluation: the 12 success criteria are necessary but not sufficient. Criterion 13: "Does the prose make you want to read the next passage?" Evaluated subjectively during first 5-turn playtest. If no, the problem is the cloud model, not the system — swap via provider-agnostic design. |
| 1.44 | Reconciliation error budget test (Phase 7) | **NOT STARTED** | Test 9B local model on 20 representative narration excerpts for reconciliation accuracy: NPC knowledge inference, disposition shift calibration, anchor proximity judgment. Establish baseline error rate. If >20%, activate selective cloud routing (Impl §9.1 design note). |

---

## Phase 2: Post-V1 Game Engine Enhancements

Items that require a working vertical slice before meaningful design
or implementation can begin. Ordered by estimated dependency chain.

### Mechanical Expansions

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 2.1 | Psychometric prologue system | **DESIGNED** | GM §5, CS §2.5–2.6 | Requires Campaign Studio character variants and prologue scene library (Phase 3) | Three-layer inference: behavioral archetype (algorithmic), mechanical profile (hand-authored mapping table scoped by career type), narrative identity (single cloud call). 3–5 adaptive scenes. Prologue scenes drawn from career- and allegiance-scoped library. V1 uses pre-built Keth. |
| 2.2 | Character funnel and allegiance system | **DESIGNED** | Vision §8, CS §2.5, §2.8 | Requires Campaign Studio allegiance authoring (Phase 3), frontend funnel UI (Phase 2) | Three-step funnel: Timeline → Allegiance → Variant. Campaigns define 2–4 allegiances with 2–4 variants each. Protagonist integration layer connects each variant to the fixed thematic spine. Campaign spine JSON uses `allegiances` array instead of flat `character_variants`. Frontend presents funnel as guided identity selection. |
| 2.3 | Obligation trigger system | **DESIGNED** | GM §9 (mechanic), §26 (between-act pipeline step 8) | Phase 7 (act boundary detection) | d100 roll at act start. If ≤ Obligation value: strain threshold reduced by 2, GM receives narrative pressure instruction. Decrease via in-story actions (1–5 points). Fires as step 8 of the between-act pipeline. |
| 2.4 | Duty trigger system | **DESIGNED** | GM §9 (mechanic), §26 (between-act pipeline step 8) | Phase 7 (act boundary detection) | Same d100 mechanism. Activation increases wound threshold by 1. GM presents competing opportunity aligned with Duty type. Increase when fulfilled. Fires as step 8 of the between-act pipeline. |
| 2.5 | Morality drift tracking | **DESIGNED** | GM §9 (mechanic), §26 (between-act pipeline step 10) | Phase 7 (act boundary detection), `moral_weight` column exists in V1 | End-of-act resolution: Conflict earned minus 1d10. If Conflict > roll, Morality decreases. Morality labels (Light/Grey/Dark) injected into GM prompt as tone modifier. Fires as step 10 of the between-act pipeline. |
| 2.6 | Destiny Point spending mechanics | **DESIGNED** | GM §23 (v1.6) | Pool tracked in V1 (Rule 8) | System-managed Light/Dark spending via narrative conditions. Stage 4 of the pool modification pipeline. Light Side triggered by narrative stakes and player investment. Dark Side triggered by Obligation activation, antagonist engagement, and spine-authored triggers. Optional seize-the-moment pre-roll choice at campaign climaxes. Escalation pacing maintains push-pull rhythm. |
| 2.7 | Character advancement / XP spending | **DESIGNED** | GM §14 (v1.5) | FFG rules defined; UX designed | Behavioral inference engine for skill ranks (automatic, based on choice patterns and failure learning). Milestone reflections for talents, specializations, characteristics, Force awakening. XP earning via base-plus-performance at act boundaries. Aspiration echo infrastructure for Hybrid 3 future upgrade. |
| 2.8 | Talent trees | **DESIGNED** | GM §15 (v1.5) | Depends on 2.7 | Five-type talent taxonomy (passive, conditional, substitution, narrative enabler, intervention). Pool modification pipeline. Pre-narration intervention step. Branch-based tree navigation through milestone reflections. Talent library with shared definitions. Phased data entry: Smuggler specs first, then by game line. |
| 2.9 | Vehicle and starship encounters | **DESIGNED** | GM §17 (v1.5) | Parallel to combat abstraction (GM §3) | Ship state cards. Three-tier damage model (operational/stressed/critical). Encounter-level resolution. Role-determines-skill mapping. Battle context layer for large-scale engagements. Simplified vehicle critical hit table. |
| 2.10 | Equipment and inventory | **DESIGNED** | GM §18 (v1.5) | — | Loadout model replacing item-by-item inventory. Four categories: weapons, armor, tools, special items. Acquisition/loss through narrative. Equipment effects on check decisions and narration. Lightsaber special treatment. |
| 2.11 | Faction state tracking | **NEEDS DESIGN** | — | — | Wider-than-NPC tracking of faction dispositions, territorial control, resource states. Connects to galactic context layer. |

### Prose & Narration Enhancements

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 2.12 | Prose diagnostic signal (runtime implementation) | **DESIGNED** | GM §13 | — | Lightweight local-model call per turn. Scans last 3–4 passages for: sensory channel monotony, rhythm repetition, opener similarity, NPC action-emotion coherence drift, relationship positivity bias. Structured JSON output injected into cloud model context. Runs parallel with check decision (zero additional latency if parallelized). Dual-use as distillation curation filter. |
| 2.13 | Scene-type-aware context assembly | **DESIGNED** | GM §10 (expanded) | Scene type classification working | Prompt assembly routing by scene type. Kinetic scenes foreground mechanical state; reflective scenes foreground motivational/relational context and reduce mechanical noise. Research-backed (Pan et al., IJHCI 2025): structured state helps action narration, hurts introspective narration. No changes to ContextPackage class. |
| 2.14 | Narration distillation pipeline (QLoRA) | **DESIGNED** | LLM Eval §8.4, Impl backlog | 500–1000 curated pairs from V1 play | QLoRA fine-tune of Qwen3.5:9B on cloud context→narration pairs. Goal: handle lower-stakes scenes (exploration, transitions) locally, reserve cloud for climactic beats. Could reduce cloud costs 50–70% per session. Scene type classification provides the routing signal. |
| 2.15 | Distillation curation dual-filter spec | **DESIGNED** | LLM Eval §8.4, Research Cat. Source 2 | Depends on 2.12 (prose diagnostic) | Filter 1: automated staleness check via prose diagnostic — excludes monotone/repetitive passages. Filter 2: mechanical fidelity — dice result honored, NPC voice consistent, word count valid, choices with delimiter. Both must pass. |
| 2.16 | Distillation evaluation failure taxonomy | **NEEDS DESIGN** | Research Cat. (filed) | Post-V1 model comparison | Five binary failure types: reference confusion, dice softening, choice genericization, continuity break, format violation. For comparing finetuned model candidates. |
| 2.17 | Session resume "Previously..." passage | **DESIGNED** | GM §6 | — | 80–150 word cloud-generated summary from compressed memory and recent turns. Written in second-person present-tense game voice. Ends at the player's current decision point. Cached in session table. Generation is Phase 3 addition to `cloud_gm.py`; display is Phase 6 UI. |
| 2.18 | First-check teaching moment (dice panel tooltip) | **DESIGNED** | GM §7 | — | First time a skill check occurs in a session, dice panel auto-expands with one-time tooltip explaining hidden dice. Dismissible, never appears again. Phase 6 frontend feature. |
| 2.19 | Turn counter for spine advancement | **FILED** | Research Cat. (filed) | Late-V1 or post-V1 | Track turn count vs. expected_turns per act to help the system pace anchor beat advancement. Low priority. |

### NPC System Expansions (Vision §11)

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 2.20 | NPC relationship triangles (NPC-NPC dispositions) | **CONCEPT ONLY** | Vision §11 | — | NPCs have dispositions toward each other, not just the player. Creates social dynamics the player must read and navigate. Richer scenes than hub-and-spoke NPC model. |
| 2.21 | NPC emotional state (transient in-scene mood) | **DESIGNED** | GM §25 (v1.6) | — | Nine-mood vocabulary (calm, angry, afraid, grieving, suspicious, grateful, desperate, amused, conflicted) with intensity and decay. Set by dice results, spine triggers, and GM-inferred cues. Injected into NPC prompt blocks. Sustained emotions nudge disposition. |
| 2.22 | NPC behavioral envelopes (enforcement) | **PARTIALLY IMPLEMENTED** | Vision §11 | `behavioral_envelope` field exists in V1 NPCState | Field exists and is passed to GM prompt. Need to validate that the GM actually respects hard constraints under narrative pressure. May need explicit prompt reinforcement. |
| 2.23 | NPC information propagation (offscreen knowledge transfer) | **CONCEPT ONLY** | Vision §11 | Reputation log exists in V1 | Information travels between NPCs offscreen through social networks. Connects to reputation echo system. Makes the world feel like actions have reach beyond the scene where they occurred. |

### Infrastructure

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 2.24 | Semantic memory / meaningful choice extraction | **DESIGNED** | GM §24 (v1.6) | — | Per-turn choice annotation via local model extracting behavioral meaning: intent, sacrifice, priority revealed, NPC impact, throughline relevance. Feeds enriched data to behavioral inference, character drift, aspiration echoes, and cross-campaign identity. Graceful degradation to skill-tag-only on annotation failure. |
| 2.25 | Multiple save slots / campaign management UI | **NEEDS DESIGN** | Impl backlog | — | Player can have multiple active sessions/campaigns. UI for starting, resuming, and managing saves. |
| 2.26 | Settings / API key management UI | **NEEDS DESIGN** | Impl backlog | — | User-facing configuration for cloud provider, model selection, API keys. |
| 2.27 | Multi-arc campaign structure | **DESIGNED** | GM §§19-20 (v1.5) | — | Time skip mechanics with vignette system for intra-campaign gaps (§19). Cross-era character progression with import packages, specialization continuity/dormancy/evolution, era transition processing (§20). Large-scale NPC management with three-tier relevance routing (§21). Canon character voice fidelity profiles (§22). |

---

## Phase 3: Campaign Studio Build

The authoring system. Design documented in Campaign Studio Design
Document (v1.2). Implementation specified in Campaign Studio
Implementation Document (v1.1). Four build phases: CS-1 through CS-4.

**Build priority:** Post-V1. Do not begin until the Game Engine
vertical slice (12 success criteria) is met.

### Pre-Build Requirements

| # | Item | Status | Notes |
|---|------|--------|-------|
| 3.0a | Campaign Studio Implementation Document | **DONE** (CS Impl v1.1) | Four build phases, Pydantic schema (with Allegiance, IntegrationLayer, NPCOverride models), validation suite, all three mode paths, saga layer pipeline, cross-era import, database additions. Updated for character funnel pivot. |
| 3.0b | LLM Evaluation expansion for Campaign Studio roles | **DONE** (LLM Eval v2.0) | Five roles defined with model assignments: divergent ideation (local), spine refinement (cloud), critique (test both), evaluation (cloud → local after fine-tuning), generation (cloud). |
| 3.0c | Campaign spine format alignment check | **NOT STARTED** | Verify Impl §12 test spine maps cleanly to CS Design §4 schema. The V1 spine is deliberately simpler (no allegiances, variants, prologue, variation points). Document the mapping and any fields that need stub values for V1. Note: schema now uses `allegiances` array, not `character_variants`. |

### Phase CS-1: Schema and Validation

| # | Item | Design Status | Design Doc | CS Impl Doc | Detail |
|---|------|--------------|-----------|-------------|--------|
| 3.1 | Campaign spine Pydantic schema (`studio/schema.py`) | **DESIGNED** | CS Design §4, CS Impl §4.1 | CS Impl §4.1 (full code) | `CampaignSpine` model with nested models for Allegiance, CharacterVariant (with IntegrationLayer, NPCOverride), PrologueSet, Act, NPC, VariationPoint, SagaMetadata. Field validators for act sequencing, track validity, allegiance-variant containment, field lengths. Both systems import from this file. |
| 3.2 | Gate 1: Schema contract validation | **DESIGNED** | CS Design §5.1, Research Cat. Source 1 | CS Impl §4.2 | Pure Python. Acts sequential, NPC references resolve, axis tags present, allegiances contain ≥1 variant each, variant `allegiance` field matches containing allegiance `id`, throughline is a question, no dangling references. |
| 3.3 | Gate 2: NPC coherence validation | **DESIGNED** | CS Design §5.2, Research Cat. Source 8 | CS Impl §4.2 | Per-NPC disposition trajectory analysis. Flags disposition shifts > 0.3 between acts without setup. Action-emotion chain tracing. |
| 3.4 | Gate 3: Relationship network validation | **DESIGNED** | CS Design §5.3, Research Cat. Source 9 | CS Impl §4.2 | NetworkX graph analysis. Flags: mean edge weight > 0.5 (insufficient conflict), > 80% positive relationships, sparse antagonist networks. Targets human-written distribution. |
| 3.5 | Gate 4: Narrative consistency audit | **DESIGNED** | CS Design §5.4, Research Cat. Source 12 | CS Impl §4.2 | Three LLM calls: narrative coherence (contradictions, dropped threads), mechanical balance (difficulty curves, scene variety), prose variety potential. Optional without cloud access; Gates 1–3 mandatory. |
| 3.6 | Schema validation tests | **DESIGNED** | — | CS Impl §3 (Phase CS-1 success criteria) | Nar Shaddaa Job test spine passes all four gates. Deliberately malformed spine fails with specific error messages. |

### Phase CS-2: Mode 3 — Full Collaboration

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 3.7 | Mode 3 collaborative authoring workflow | **DESIGNED** | CS Design §3 (Mode 3) | CS-1 complete | Author drives, AI assists. Throughline→anchors→NPCs→galactic context→variants→prologue scenes→validation. |
| 3.8 | Mode 3 assistance prompt (`studio/prompts/mode3_assist.txt`) | **DESIGNED** | CS Impl §3 | — | AI suggests alternatives, flags structural issues, generates galactic context drafts, drafts NPC voice notes. |
| 3.9 | Throughline question authoring tooling | **DESIGNED** | CS Design §2.1 | — | AI evaluates throughline questions against four criteria: debatable, pressurable from multiple directions, answerable through tactics, sustains 20+ hours. |
| 3.10 | Anchor beat design tooling | **DESIGNED** | CS Design §2.2 | — | Validates anchors are situations (not outcomes), work with multiple archetypes, transform the situation irreversibly. 5–8 turn spacing between anchors. |
| 3.11 | NPC relationship architecture tooling | **DESIGNED** | CS Design §2.3 | — | Validates conflict requirement, cross-cluster interactions, disposition trajectories, behavioral envelopes. |
| 3.12 | Galactic context authoring | **DESIGNED** | CS Design §2.4 | — | 2–4 sentences per act. Must be specific (not generic). At least one element per act with potential relevance. Changes between acts. |
| 3.13 | Character variant design + prologue scene design + integration layer | **DESIGNED** | CS Design §2.5, §2.6, §2.8 | — | 2–4 allegiances per campaign, 2–4 variants per allegiance. Each variant includes integration layer (entry point, personal stakes, NPC overrides, anchor adaptations). Prologue scenes drawn from career-allegiance scene library where possible. At least one non-combat variant. Cross-allegiance variants must produce structurally different experiences. |
| 3.14 | Prose variety by design checks | **DESIGNED** | CS Design §2.7 | — | Scene type diversity across acts, location variety (2–3 distinct environments per act), emotional register shifts (contrast moments). |
| 3.15 | Studio API routes (`api/studio_routes.py`) | **DESIGNED** | CS Impl §2 | — | Authoring endpoints for Mode 3 workflow. |

### Phase CS-3: Mode 2 — Thematic Steering + Cross-Era Import

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 3.16 | Mode 2 generation pipeline | **DESIGNED** | CS Design §3 (Mode 2) | Mode 3 working | Author provides thematic brief (era, location, tone, throughline, concept). AI generates complete spine draft. Author reviews and edits. |
| 3.17 | NPC voice generation (cloud model) | **CONCEPT ONLY** | CS Design §8 (deferred) | — | Cloud model generates NPC voice notes from brief character descriptions. Useful for Modes 1 and 2 where author doesn't hand-write every NPC's speech patterns. |
| 3.18 | Campaign import interface (`studio/import_interface.py`) | **DESIGNED** | CS Design §6.1, CS Impl §6 | Spine format finalized | Maps completed character state onto new campaign: motivation tracks, NPC relationship dispositions, world state variables. Game Engine receives a character dict indistinguishable from fresh start. |
| 3.19 | Canon as environmental constraint system | **DESIGNED** | CS Design §6.2 | — | Canon events as galactic-scale environmental anchors. Player agency at personal scale. Relationship to canon characters shaped by play history. |
| 3.20 | World state variable tracking (butterfly effect) | **DESIGNED** | CS Design §6.3 | — | Player actions create ripples at personal/social/local scale that compound across eras. Not rewriting galactic timeline — a Corellian senator remembers your name because you helped in Act 2. |

### Mode 1 — Full Blind (Long-Term Aspiration)

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 3.21 | Mode 1 generation pipeline | **DESIGNED** | CS Design §3 (Mode 1) | Mode 2 working | AI generates complete campaign from minimal input. Explicitly lower quality contract. |
| 3.22 | Negative archetype specification | **DESIGNED** | Research Cat. Source 11, CS Design §3 | — | "This campaign is NOT" description. Archetype avoidance list. Without anti-default signals, LLM produces hero's journey with Dark Side antagonist and redemptive climax. |
| 3.23 | Quality contract definition | **DESIGNED** | CS Design §0 (Principle 2), §3 | — | Mode 1: playable but explicitly lower quality. May have thinner NPC networks, less surprising anchors, more predictable dynamics. Bar: "engaging and not generic." |

### Non-Linear Spine Structures (CS §7)

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 3.24 | Hub-and-spoke spine structure | **DESIGNED** | CS Design §7.1 | — | Acts tagged with prerequisites, not fixed sequence. Anchors designed around accumulated state rather than specific prior events. |
| 3.25 | Parallel tracks spine structure | **DESIGNED** | CS Design §7.2 | — | Two simultaneous story threads. `track` field per act. Convergence anchor requires both tracks at specified progress. |

### Campaign Studio Deferred Items (CS §8)

| # | Item | Design Status | Design Doc | Detail |
|---|------|--------------|-----------|--------|
| 3.26 | Deterministic seeding for reproducible generation | **CONSIDER** | CS Design §8 | Enables partial re-generation ("like the world, want different NPCs"). Value depends on Studio UX decisions. |
| 3.27 | Spine difficulty calibration | **CONCEPT ONLY** | CS Design §8 | Estimate difficulty curve before runtime from anchor beats, expected check difficulties, NPC opposition patterns. |
| 3.28 | Campaign rating and feedback system | **CONCEPT ONLY** | CS Design §8 | Player ratings inform Mode 1/2 generation. Requires player base. |

### Character Funnel Items (Vision §8, CS §2.5, §2.8)

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 3.29 | Protagonist integration layer authoring workflow | **DESIGNED** | CS Design §2.8 | Mode 3 working | Authoring fixed thematic spine and per-allegiance integration layers: entry points, personal stakes, NPC relationship overrides, anchor beat adaptations. Anchors must be abstract enough to survive all integration variants. |
| 3.30 | Prologue scene library system | **DESIGNED** | CS Design §2.6, GM §5 | Schema finalized | Career- and allegiance-scoped scene library. `career_type` and `allegiance` tags. `library_reusable` flag. Recommended: 3 library scenes per career-allegiance combo + 2 campaign-specific per variant. Reduces authoring overhead as funnel combinatorial space grows. |
| 3.31 | Career-type mapping table library | **DESIGNED** | GM §5 | Schema finalized | Layer 2 behavioral-cluster-to-mechanical-profile mapping tables scoped by career type. Reusable across campaigns. One table per FFG career covers all variants of that career regardless of allegiance or campaign. |
| 3.32 | Character funnel frontend UI | **NEEDS DESIGN** | Vision §8 | Phase 2 frontend foundation | Three-step guided selection: Timeline → Allegiance → Variant. Each step presents narrative-quality descriptions, not mechanical labels. Must feel like entering a story, not configuring a character sheet. |
| 3.33 | Integration layer validation | **NEEDS DESIGN** | CS Design §2.8 | Gate 1 extended | Validate that every allegiance has at least one fully authored integration layer. Verify NPC overrides reference valid roster entries. Verify anchor adaptations cover all required anchors. |
| 3.34 | Allegiance diversity validation | **NEEDS DESIGN** | CS Design §2.5 | Gate 3 extended | Validate cross-allegiance diversity: different allegiances must produce structurally different protagonist experiences, not cosmetic reskins. Flag allegiances with >80% NPC disposition overlap or identical anchor adaptations. |

---

## Phase 4: Saga Layer Build

The sequel spine generation system. Design documented in Campaign
Studio Design §6.4. Implementation in CS Implementation §5.
Depends on Campaign Studio being operational (Phase 3).

### Pre-Build Requirements

| # | Item | Status | Detail |
|---|------|--------|--------|
| 4.0a | Saga layer test artifacts | **NOT STARTED** | Worked example of full pipeline with a completed campaign and generated sequel. |
| 4.0b | `saga_metadata` schema fields | **DESIGNED** | CS Impl §4.1. `SagaMetadata` model: prior_campaign_id, throughline_evolution, imported_npc_mappings, required_import_fields, default_state_for_new_characters. |
| 4.0c | Writer's Room intermediate schemas | **DESIGNED** | CS Impl §5. `SequelDirection` (Stage 2), `SpineSketch` with `ActOutline`/`NPCOutline` (Stage 3), draft `CampaignSpine` (Stage 4), `EvaluatedSpine` with `EvaluationResult` (Stage 5). |
| 4.0d | Persona pool curation and validation (50+ personas) | **NOT STARTED** | CS Design §8 (deferred). Ordinary, heterogeneous personas. Must NOT be Star Wars-specific or narrative archetypes. Empirically validate that different subsets produce different sequel directions. |

### Saga Layer Pipeline

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 4.1 | Stage 1 — Persona assignment system | **DESIGNED** | CS Design §6.4.2, Research Cat. Source 3 | 4.0d (persona pool) | Assign heterogeneous ordinary personas from pool. Personas partition knowledge space (2.6x default diversity). |
| 4.2 | Stage 2 — Divergent generation with denial constraints + CoT | **DESIGNED** | CS Design §6.4.2, Research Cat. Sources 3, 4 | 4.0c (schemas) | Persona-primed writers generate sequel directions. CoT breaks within-session fixation. Critical: prior campaign NOT provided as input here. Denial constraints: no repeat of prior conflict type, resolution structure, or obvious extension. Local model viable (no proprietary advantage on divergent thinking). |
| 4.3 | Stage 3 — Branching search over candidates | **DESIGNED** | CS Design §6.4.2, Research Cat. Source 4 | 4.0c | Tree/beam search: expand promising candidates, evaluate, expand further, prune weak branches. 4–7x single-pass quality. Backtracking supported. Configurable depth. |
| 4.4 | Stage 4 — Debate/critique convergence with prior campaign | **DESIGNED** | CS Design §6.4.2, Research Cat. Source 4 | — | Prior campaign enters HERE (not earlier). Critic agent challenges coherence, structural quality, thematic consistency. Debate/critique loop: critic challenges → writer revises → critic re-evaluates. Statistically significant improvements over single-agent. |
| 4.5 | Stage 5 — Three-axis pairwise evaluation | **DESIGNED** | CS Design §6.4.2, Research Cat. Sources 5, 6 | — | Pairwise comparison (not isolated scoring). Three axes: structural quality, novelty, diversity. ICC 0.59 → 0.75 with pairwise. Top candidate selected (Mode 3: player reviews top 2–3; Mode 1: top candidate used directly). |
| 4.6 | Saga layer + Mode 3 integration | **DESIGNED** | CS Design §6.4.5 | 4.1–4.5 working | Writer's Room generates 2–3 candidates. Player reviews, selects, modifies through collaborative editing. |
| 4.7 | Saga layer + Mode 2 integration | **DESIGNED** | CS Design §6.4.5 | 4.6 working | Player provides thematic direction as additional Stage 2 constraint. |
| 4.8 | Saga layer + Mode 1 integration | **DESIGNED** | CS Design §6.4.5 | 4.7 working | Writer's Room generates and selects autonomously. Explicitly lower quality contract. |

### Saga Layer Deferred

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 4.9 | Trained local evaluator for spine quality | **CONCEPT ONLY** | CS Design §8, Research Cat. Source 5 | Corpus of generated spines with quality annotations | CrEval shows trained 7B evaluator outperforms frontier models at creativity judgment. Requires data from actual saga runs. Architecture supports evaluator swap via config. |
| 4.10 | Multi-model ensemble (different LLMs as different writers) | **CONCEPT ONLY** | CS Design §8, Research Cat. Source 7 | Persona + CoT validated on single model first | Different cloud models as different "writers" via OpenRouter. Research shows ensembles approach human variability. Scaling lever, not prerequisite. |

---

## Phase 5: Long-Term Aspirations

Items acknowledged in the Vision Document that are beyond the current
planning horizon. No design work and no target timeline.

| # | Item | Source | Detail |
|---|------|--------|--------|
| 5.1 | Complete career arcs (dozens of sessions) | Vision §17 | Character progression from small-time to significant over many sessions. Mechanical progression maps to narrative arc. Requires 2.7 (advancement), 2.8 (talents). |
| 5.2 | Character continuity across real time (years) | Vision §17 | The game remembers who a character was. Throughline questions from years ago still visible in today's choices. Requires robust long-term memory system. |
| 5.3 | Era-spanning play (full Legends timeline) | Vision §17 | Clone Wars → Galactic Civil War → NJO → LOTF → FOTJ. Cross-era character import (3.18). Multiple era campaign spines. |
| 5.4 | Setting extensibility (non-Star Wars) | Vision §17 | Rules layer is FFG-specific; narrative and memory layers are setting-agnostic. Original SF, supernatural drama, espionage, historical fiction. Requires 2.11 (RulesSystem abstraction — currently deferred as "no premature abstraction" per Rule 7). |
| 5.5 | Original worldbuilding (new planets, factions, species) | Vision §17 | Generative systems from designer-provided seeds. Same systems that populate Nar Shaddaa's docks can populate any setting. |
| 5.6 | Multiplayer | GM §12 | Fundamentally different design problem. Shared universe, cooperative, or competitive play. Deferred entirely. |

---

## Open Research Questions (from Research Catalogue)

Empirical investigation needed during implementation, not further desk
research.

| # | Question | Relevant Phase | Research Cat. Ref |
|---|----------|---------------|-------------------|
| R.1 | How does persona + CoT perform on narrative structure generation specifically? Tested on product ideation; mechanism should generalize but unverified. | Phase 4 | Open Q1 |
| R.2 | What is the optimal number of writers in the Writer's Room? Quality-vs-cost tradeoff curve unknown. | Phase 4 | Open Q2 |
| R.3 | How effective is the local model as a spine evaluator on project-specific tasks? CrEval shows 7B can outperform frontier, but on their benchmark. | Phase 4 | Open Q3 |
| R.4 | Does the semantic-syntactic decoupling gap affect spine-level diversity or only prose-level diversity? | Phase 4 | Open Q4 |
| R.5 | How do denial constraints interact with personas? Both are Stage 2 interventions. | Phase 4 | Open Q5 |
| R.6 | What is the right size and composition for the persona pool? 50+ working minimum. | Phase 4 | Open Q6 |
| R.7 | Does the Bitter Lesson apply to the Writer's Room within the project's timeline? If base models become more diverse, multi-agent overhead may reduce. | Phase 4 | Open Q7 |

---

## Pending Decisions

| # | Decision | Options | Status | Blocking |
|---|----------|---------|--------|----------|
| D.1 | Two standalone implementation docs vs master + children | Two standalone | **RESOLVED** — two standalone docs (Impl v1.7, CS Impl v1.0) | — |
| D.2 | Active primary cloud model for V1 | GPT-5.2 (current), Claude Sonnet 4.6 (contender) | **OPEN** — pending head-to-head (item 1.39) | Phase 1 deployment |
| D.3 | Campaign Studio Design doc version header | v1.1 (file) vs v1.2 (referenced by CS Impl) | **RESOLVED** — CS Design is now v1.2 (funnel pivot). CS Impl is v1.1. Both aligned. | — |

---

## Alignment Notes

Issues identified during the March 5, 2026 cross-document review:

1. **V1 test spine vs Campaign Studio schema.** The Implementation §12
   test spine is a simplified format (no allegiances, character_variants,
   prologue_scenes, variation_points, expected_turns,
   disposition_trajectory). This is correct for V1 since those features
   aren't built. Once `studio/schema.py` exists (Phase CS-1), the Game
   Engine should load spines via the `CampaignSpine` Pydantic model. The
   V1 spine will need stub values for new fields (including the
   `allegiances` array introduced by the funnel pivot), or the schema
   needs optional fields with defaults for V1 compatibility. Tracked as
   item 3.0c.

2. **Campaign Studio Design version header.** ~~File says v1.1. Campaign
   Studio Implementation doc references v1.2.~~ **RESOLVED:** CS Design
   is now v1.2 (funnel pivot). CS Implementation is now v1.1. Both
   aligned.

3. **Retired research docs.** RESEARCH_SCOPING.md and
   SAGA_RESEARCH_FINDINGS.md are superseded by Research Catalogue v1.0.
   Should be removed from project files. Tracked as item 0.4.

4. **CLAUDE.md content.** Referenced in repo structure (Impl §3) but
   content not authored. Tracked as item 1.34.

5. **V1 prompt additions completeness.** Items 1.17–1.21 capture five
   specific prompt additions from Game Mechanics (anti-positivity,
   consequence reflection, forward-echoing, consequence-at-scale, risk
   signaling). All are Phase 3 narration prompt template work. None
   were previously tracked as individual items.

6. **V1 spine format and funnel.** The V1 test spine has no allegiance
   structure (Keth Varso is pre-built). This is correct — the funnel is
   post-V1. But the Game Engine's spine loading should be designed to
   accept both the V1 simplified format and the full allegiance-based
   format, to avoid a breaking migration when the Campaign Studio ships.
   Tracked as item 3.0c.

---

## Document Status Summary

| Document | Version | Status | Next Action |
|----------|---------|--------|-------------|
| Vision | v3.1 | **CURRENT** | Character funnel pivot applied. Source of truth for experience goals. |
| Game Mechanics | v1.8 | **CURRENT** | 27 sections (0-26). Reputation echo delivery and conditional choice availability designed. |
| Implementation (Game Engine) | v2.4 | **CURRENT** | Evaluation risk mitigations applied. Prompt rotation, memory enrichment, thread state, style exemplars. |
| LLM Evaluation | v2.0 | **CURRENT** | Monitor DeepSeek V4 and Qwen3.5-397B. |
| Campaign Studio Design | v1.2 | **CURRENT** | Character funnel pivot applied. Allegiance schema, integration layer, scene library defined. |
| Campaign Studio Implementation | v1.1 | **CURRENT** | Schema models updated for funnel pivot. |
| Research Catalogue | v1.0 | **CURRENT** | No pending additions. |
| This Backlog | v2.7 | **CURRENT** | Evaluation risk mitigations tracked. Expanded compliance tests added. |

---

## Revision History

**v2.7 — Evaluation risk mitigations (March 2026)**

1. **Three new compliance test items added.** 1.42 (sustained 5-turn
   play quality test), 1.43 (13th success criterion — prose quality),
   1.44 (reconciliation error budget test for Phase 7).

2. **Implementation v2.4.** Prompt constraint rotation, memory cliff
   mitigation (narration excerpts + thread state), choice quality
   example, style exemplars, selective cloud routing design.

**v2.6 — Final pre-build sweep (March 2026)**

1. **Items 2.3, 2.4, 2.5 upgraded to DESIGNED.** Obligation, Duty, and
   Morality trigger systems were PARTIALLY DESIGNED before GM §26
   specified the between-act pipeline. Now that §26 includes the full
   pipeline with motivation rolls (step 8) and Morality resolution
   (step 10), plus Build Roadmap Phase 8 has explicit success criteria,
   all three are fully designed. Zero PARTIALLY DESIGNED items remain.

2. **Implementation v2.3.** Opening narration scene_type fixed,
   skill_tags_json folded into log_turn, §14 backlog cleaned up.

**v2.5 — Deferral design completion + logic analysis (March 2026)**

1. **Document Status Summary updated.** Game Mechanics corrected to v1.8
   (reputation echo delivery §1.1, conditional choice availability §24.4,
   §26 subsection numbering fixed). Implementation corrected to v2.2
   (skill_tags_json column, reputation_log schema updates).

2. **Deferred Design and Logic Analysis document added to project.**
   System logic walkthrough verifying all data flows, integration points,
   invariant preservation, and token budgets. Referenced in CLAUDE.md
   and CLAUDE_CODE_INITIAL_PROMPT.md.

**v2.4 — Pre-build audit fixes (March 2026)**

1. **Document Status Summary updated.** Game Mechanics corrected to v1.7
   (was v1.4). Implementation corrected to v2.0 (was v1.7). Backlog
   version corrected.

2. **Item 1.34 updated to DONE.** CLAUDE.md content is complete and
   covers architecture, tech stack, build phases, success criteria,
   critical rules, and doc reading order.

**v2.3 — Retrofit-risk items designed (March 2026)**

Three additional items moved from unresolved to DESIGNED following
Game Mechanics v1.6:

1. **Item 2.6 updated to DESIGNED.** Destiny Point spending mechanics
   now fully specified in GM §23.
2. **Item 2.21 updated to DESIGNED.** NPC emotional state now fully
   specified in GM §25.
3. **Item 2.24 updated to DESIGNED.** Semantic memory / meaningful
   choice extraction now fully specified in GM §24.

**v2.2 — Game Mechanics v1.5 design completion (March 2026)**

Nine mechanical systems previously marked NEEDS DESIGN now have full
design specifications in Game Mechanics Document v1.5 (Sections 14–22):

1. **Items 2.7, 2.8, 2.9, 2.10 updated to DESIGNED.** Character
   advancement (§14), talent trees (§15), vehicle encounters (§17),
   equipment/inventory (§18). Each item description updated with
   design summary and Game Mechanics section reference.

2. **Item 2.27 updated to DESIGNED.** Multi-arc campaign structure now
   covered by: time skip vignettes (§19), cross-era character
   progression (§20), large-scale NPC management (§21), canon character
   voice fidelity (§22).

3. **Force mechanics (§16) designed.** Not previously tracked as a
   separate backlog item — was implicit in talent trees and character
   advancement. Now fully specified: Force dice resolution, dark side
   temptation, Force powers, committed Force dice, dark side spiral.

4. **Implementation Document updated (v1.8).** Rule 11 added for V1
   forward-compatibility. Backlog reorganized with tier-based
   implementation order.

**v2.1 — Character funnel pivot (March 2026)**

Updates following the character funnel design pivot (Vision v3.1, Game
Mechanics v1.4, CS Design v1.2, CS Impl v1.1). Key changes:

1. **Item 2.2 rewritten.** "Multiple career/species options" (NEEDS
   DESIGN) replaced with "Character funnel and allegiance system"
   (DESIGNED). Three-step funnel with protagonist integration layer.

2. **Item 2.1 updated.** Prologue scene library and career-type-scoped
   mapping tables referenced.

3. **Six new funnel-specific items added.** 3.29 (protagonist integration
   layer authoring), 3.30 (prologue scene library), 3.31 (career-type
   mapping table library), 3.32 (funnel frontend UI), 3.33 (integration
   layer validation), 3.34 (allegiance diversity validation).

4. **Phase CS-1 items updated.** Items 3.0a, 3.0c, 3.1, 3.2, 3.13
   updated for allegiance schema and integration layer.

5. **Document Status Summary updated.** All five updated documents
   reflected with new versions.

6. **Alignment Notes updated.** Item 2 (version header) marked RESOLVED.
   Item 6 added: V1 spine format forward compatibility with allegiance
   structure.

7. **Pending Decisions updated.** D.3 marked RESOLVED.

**v2.0 — Full alignment review and revision (March 5, 2026)**

Major revision following comprehensive cross-document review of all
eight project files. Key changes:

1. **Completed items marked DONE.** Items 0.1 (LLM Eval v2.0), 0.2
   (Impl scope statement v1.7), 0.3 (two standalone docs decision),
   3.0a (CS Implementation v1.0), 3.0b (LLM Eval Campaign Studio
   expansion) all marked as completed.

2. **Missing items added.** 22 new items that were designed in Game
   Mechanics or Implementation but not previously tracked: five
   narration prompt additions (1.17–1.21), context package fields
   (1.22–1.23), session resume passage (2.17), first-check tooltip
   (2.18), CLAUDE.md (1.34), Obligation/Duty trigger systems (2.3–2.4),
   Morality drift (2.5), DeepSeek V4 monitoring (1.40), Qwen3.5-397B
   monitoring (1.41), and others.

3. **Document Status Summary updated.** All versions corrected to
   current state. Campaign Studio Design version discrepancy flagged.

4. **Alignment Notes section added.** Five cross-document alignment
   issues documented with tracking references.

5. **Pending Decisions updated.** D.1 marked RESOLVED. D.3 added for
   CS Design version header discrepancy.

6. **Detail columns added.** Every item now includes a Detail field
   with specific technical description of what the item entails.

7. **Saga layer pre-build items updated.** 4.0b and 4.0c marked
   DESIGNED (schemas exist in CS Impl §4.1 and §5).

**v1.0 — Initial document (March 2026)**

Created from comprehensive cross-document alignment review. Inventoried
every planned, deferred, and tracked item across all project documents.

---

*Storyteller V3 — Comprehensive Project Backlog v2.7*
*Everything planned. Nothing floating.*
