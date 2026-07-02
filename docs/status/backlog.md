# Storyteller V3 — Comprehensive Project Backlog

**Document version:** 3.4
**Last updated:** July 2, 2026
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
| 0.4 | Retire superseded research docs — remove RESEARCH_SCOPING.md and SAGA_RESEARCH_FINDINGS.md from project files | **DONE** | Research Catalogue replaces both | Catalogue v1.0 absorbs all content. Files removed from project. |
| 0.5 | First campaign spine authoring — "The Nar Shaddaa Job" full spine in Campaign Studio JSON format | **DONE** (Milestone 1+) | Impl §12, CS Design §4 | Both `nar_shaddaa_job.json` and `echoes_of_the_force.json` now exist as full-format spines with `allegiances` array, `variation_points`, `factions`, and `vehicle_registry`. Original V1-scope simplified format has been superseded. Formal alignment check (3.0c) still not formally executed but spines are de facto aligned with the schema. |
| 0.6 | Campaign Studio Design Document — version header alignment | **RESOLVED** | CS Design | Resolved by funnel pivot: CS Design is now v1.2, CS Implementation is v1.1. Both aligned. |
| 0.7 | Campaign Studio Implementation Document — initial creation | **DONE** (CS Impl v1.0) | CS Implementation | Four build phases, Pydantic schema models, validation suite, Mode 3/2/1 paths, cross-era import, saga layer pipeline, database additions, and interaction contract specified. |

---

## Phase 1: V1 Game Engine Build

The vertical slice. Implementation doc (v1.7) specifies the full build
in six sub-phases (Phase 1 through Phase 6). All items below are V1
scope. **All V1 items are DONE — verified March 2026.**

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
| 1.1 | FFG dice engine (`engine/dice.py`) | **DONE** (Milestone 0) | — | Impl §5.1 (full code) | Symbol tables for all 7 die types, `roll_pool()`, `RollResult` with outcome quadrant classification. Verify every symbol table against physical rulebooks before proceeding. |
| 1.2 | Character model (`engine/character.py`) | **DONE** (Milestone 0) | GM §9, Vision §10 | Impl §5.2 (full code) | Pydantic models for Character, Characteristics, SkillRanks, MotivationTrack. All 33 FFG skills with governing characteristics mapped. `active_injuries: list[str]` for combat narrative tracking. |
| 1.3 | Check system (`engine/checks.py`) | **DONE** (Milestone 0) | GM §1, §2, §3 | Impl §5.3 (full code) | `build_pool()` from character stats and `CheckRequest`. FFG pool construction: max(char,skill) total dice, upgrade min(char,skill) to proficiency. Difficulty enum Simple through Formidable. |
| 1.4 | Test character data file (`data/characters/keth_varso.json`) | **DONE** (Milestone 0) | Vision §16 | Impl §5.4 | Keth Varso, Bothan Smuggler. Cunning 4, Agility 3, Presence 3. Deception 2, Piloting_Space 2. Obligation: Debt (15). Throughline question and voice notes included. |

### V1 Build Items — Sub-Phase 2: The Local GM

| # | Item | Status | Design Doc | Impl Doc | Detail |
|---|------|--------|-----------|---------|--------|
| 1.5 | Check decision prompt (`gm/prompts/check_decision.txt`) | **DONE** (Milestone 0) | GM §1, §10 | Impl §6.1 (full prompt) | Structured prompt template with character summary, story position, tension calibration, scene description, player action. Returns JSON with `requires_check`, skill, difficulty, `scene_type`, `moral_weight`, reasoning. |
| 1.6 | Local GM module (`gm/fast_gm.py`) | **DONE** (Milestone 0) | — | Impl §6.2 (full code) | Ollama calls to Qwen3.5:9B. JSON schema enforcement via `format` parameter. Skill normalization. 3-retry with validation. Fallback: `requires_check=false` after all retries fail. May 2026: local backend removed, module now cloud FAST tier. July 2026 funnel pass: transport-failure deterministic fallback (scene_type→skill table, `requires_check=true`, reasoning tagged `DETERMINISTIC_FALLBACK`); malformed JSON after retries still raises (Rule 5). |
| 1.7 | Check decision schema validation (Pydantic) | **DONE** (Milestone 0) | Research Cat. Source 1 | Impl §6.2 (note) | Production robustness upgrade: Pydantic model validation on local model output enforcing enum membership for skill, difficulty, scene_type. Same fallback behavior on failure. |
| 1.8 | Scene type classification | **DONE** (Milestone 0) | GM §10 | Impl §6.1 | Six types: combat, chase, infiltration, social, exploration, introspection. Classified by local model as part of check decision. Default fallback: "social" on missing/invalid. |
| 1.9 | `moral_weight` field | **DONE** (Milestone 0) | GM §9 | Impl §6.1 | Integer 0–3 in check decision response. Tracks Morality Conflict accumulation per turn. Column exists in `turns` table. |
| 1.10 | Failure recovery difficulty calibration | **DONE** (Milestone 0) | GM §2 | Impl §6.2 | `decide_check()` accepts `recent_failure_count: int`. When ≥ 2, injects calibration note preferring average over hard difficulty. `{failure_calibration}` placeholder in prompt template. |

### V1 Build Items — Sub-Phase 3: The Cloud GM

| # | Item | Status | Design Doc | Impl Doc | Detail |
|---|------|--------|-----------|---------|--------|
| 1.11 | Narration prompt template (`gm/prompts/narration.txt`) | **DONE** (Milestone 0) | Vision §3, GM §1 | Impl §7.1 (full prompt) | Second-person present tense. Character summary, voice, story context, NPC states, location, galactic context, dice result block, dice interpretation guide. `---CHOICES---` delimiter. 250–600 word bounds. Skill tag convention `[Deception]` stripped before player display. |
| 1.12 | Context package assembly (`gm/context.py`) | **DONE** (Milestone 0) | GM §10 | Impl §7.2 (full code) | `ContextPackage` dataclass. `NPCState` with numeric disposition (0.0–1.0), `disposition_label()`, knowledge states, `behavioral_envelope`, `voice_notes`. `ArcState` with campaign, act, tension, open threads. `TurnMemory` for recent turns. `build_dice_result_block()`, `build_npc_block()`, `build_open_threads_block()`. |
| 1.13 | Cloud GM module (`gm/cloud_gm.py`) | **DONE** (Milestone 0) | LLM Eval §14 | Impl §7.3 (full code) | OpenAI-compatible SDK. Provider-agnostic via env vars. `_build_prompt()`, `_parse_response()` with delimiter validation, word count enforcement, choice extraction and skill tag stripping. `narrate_turn()` with retry logic. `narrate_turn_stream()` for SSE. |
| 1.14 | Cloud failure fallback path | **DONE** (Milestone 0) | Research Cat. Source 1 | Impl §7.3 | `_narrate_with_local_fallback()`: simplified prompt to Ollama on cloud timeout (20s) or API error. Per-turn fallback — next turn reattempts cloud. Counter tracks consecutive fallbacks; UI indicator after 3+. Player never sees error. |
| 1.15 | Context package validation | **DONE** (Milestone 0) | Research Cat. Source 1 | Impl §7.2 (note) | Pre-cloud-submission structural checks: `situation` and `location` non-empty, `active_npcs` populated, `recent_turns` non-empty (except Turn 1), `voice_notes` populated. Validation failure = bug, log error, surface generic pause passage. |
| 1.16 | `prose_diagnostic` field reserved on ContextPackage | **DONE** (Milestone 0) | GM §13 | Impl §7.2 | Optional dict, null in V1. Schema reservation ensures future prose diagnostic signal (post-V1) is not a structural change. |
| 1.17 | Anti-positivity-bias prompt instruction | **DONE** (Milestone 0) | GM §1, Research Cat. Source 9 | Impl §7.1 | Explicit counterbalance in narration prompt YOUR TASK section: NPCs with disposition < 0.5 must exhibit friction/reluctance. Avoid uniformly warm interactions. Conflict is a feature, not a problem. |
| 1.18 | Turn-level consequence reflection instruction | **DONE** (Milestone 0) | GM §1 | Impl §7.1 | Prompt addition: "The opening of your passage must clearly reflect the player's specific choice. Do not write a passage that could follow from any choice." |
| 1.19 | Forward-echoing instruction | **DONE** (Milestone 0) | GM §4 | Impl §7.1 | Prompt addition: "When introducing environmental or NPC details, prefer details that could become relevant later over purely atmospheric ones. Plant seeds." |
| 1.20 | Consequence-at-scale instruction | **DONE** (Milestone 0) | GM §4 | Impl §7.1 | Prompt addition: "When the player makes a choice with significant implications, within 2–3 turns show at least one moment where the ripple reached beyond the immediate scene." |
| 1.21 | Risk signaling convention in choice text | **DONE** (Milestone 0) | GM §7 | Impl §7.1 | Prompt addition: "Write choices requiring a check with language that conveys uncertainty/risk. Write choices without a check with language that conveys confidence/certainty." |
| 1.22 | `sequence` field on ContextPackage | **DONE** (Milestone 0) | GM §3 | Impl §7.2 (v1.6) | `sequence: Optional[dict]` for multi-beat combat/chase tracking. Tracks which beat the player is on, prior beat outcomes, resolution conditions. |
| 1.23 | `galactic_context` field | **DONE** (Milestone 0) | GM §4 | Impl §7.2 (v1.6) | String field in `ContextPackage`. Per-act worldbuilding data from campaign spine. Injected into narration prompt alongside situation and location. |

### V1 Build Items — Sub-Phase 4: State and Persistence

| # | Item | Status | Design Doc | Impl Doc | Detail |
|---|------|--------|-----------|---------|--------|
| 1.24 | SQLite database + WAL mode (`state/db.py`) | **DONE** (Milestone 0) | — | Impl §8.1 (full code) | Schema: `sessions`, `turns`, `npc_states`, `act_summaries`, `reputation_log` tables. `distillation_pairs` view. WAL mode on every connection. Foreign keys enabled. |
| 1.25 | Session management (`state/session.py`) | **DONE** (Milestone 0) | GM §6, §11 | Impl §8.2 (full code) | `create_session()`, `log_turn()` (with `context_json` and `scene_type` for distillation), `get_recent_turns()`, `get_act_summaries()`, `get_session()`, `get_turn_count()`. |
| 1.26 | Memory compression (`state/memory.py`) | **DONE** (Milestone 0) | GM §11, Vision §15 | Impl §8.3 (full code) | `compress_act_turns()` via local model. 100–150 word prose summary. `compress_if_needed()` as async BackgroundTask. Threshold: 8 uncompressed turns. Compression failure is logged, not raised. |
| 1.27 | Distillation data instrumentation | **DONE** (Milestone 0) | LLM Eval §8.4 | Impl §8.1 (v1.4) | `context_json` and `scene_type` columns on `turns` table. `distillation_pairs` SQL view pairing context packages with cloud narration. Passive instrumentation — zero runtime cost, enables future fine-tuning. |
| 1.28 | Reputation log table | **DONE** (Milestone 0) | GM §1 | Impl §8.1 (v1.6) | `reputation_log` table: session_id, turn_number, one-sentence summary of notable actions. GM prompt receives 3–5 most recent entries for occasional surfacing through NPC dialogue. |
| 1.29 | Act summary `character_drift` field | **DONE** (Milestone 0) | GM §11 | Impl §8.1 (v1.6) | `character_drift TEXT` column on `act_summaries`. One-sentence behavioral pattern observation per act, generated alongside compression summary. |

### V1 Build Items — Sub-Phase 5: API

| # | Item | Status | Design Doc | Impl Doc | Detail |
|---|------|--------|-----------|---------|--------|
| 1.30 | API routes (`api/main.py`, `api/game_routes.py`) | **DONE** (Milestone 0) | — | Impl §9 | Three routes: `POST /session`, `POST /session/{id}/turn`, `GET /session/{id}`. Streaming variant: `POST /session/{id}/turn/stream` (SSE). Background compression triggered after turn write. `used_local_narration` in response. |

### V1 Build Items — Sub-Phase 6: Frontend

| # | Item | Status | Design Doc | Impl Doc | Detail |
|---|------|--------|-----------|---------|--------|
| 1.31 | Frontend (`web/index.html`) | **DONE** (Milestone 0) | Vision §2, §14 | Impl §10 | Single-file prose reader. Dark bg, light text, 650px max width. Choices as full-width buttons (≥44px touch). Dice panel collapsed by default (FFG color-coded). Word-by-word streaming via SSE. Local narration warning when active. No avatars, maps, or character sheet in V1. Mobile readable. |

### V1 Build Items — Cross-Cutting

| # | Item | Status | Design Doc | Impl Doc | Detail |
|---|------|--------|-----------|---------|--------|
| 1.32 | Configuration / environment variables | **DONE** (Milestone 0) | LLM Eval §14 | Impl §11 | `.env.example` with NARRATIVE_BACKEND, CLOUD_PROVIDER, CLOUD_MODEL, OLLAMA_URL, LOCAL_MODEL, DB_PATH, PORT, DEV_MODE, STREAMING_ENABLED. OpenRouter model string format documented. |
| 1.33 | Test campaign spine ("The Nar Shaddaa Job") | **DONE** (Milestone 0) | Vision §16 | Impl §12 | Four-act spine with per-act galactic context, NPC roster (Vossk, Doss) with full state cards. Simplified V1 format — no character variants, prologue scenes, or variation points. |
| 1.34 | `CLAUDE.md` for Claude Code | **DONE** | Impl §3 | — | Abridged Game Engine implementation spec for Claude Code context. Covers architecture, tech stack, build phases 1-6, success criteria, critical rules (3, 4, 5, 11), physics-before-imagination invariant, repo structure, and doc reading order. |
| 1.35 | `pyproject.toml` | **DONE** (Milestone 0) | — | Impl §11 | Dependencies: fastapi, uvicorn, openai≥1.30.0, httpx, pydantic≥2.0.0, python-dotenv. Dev: pytest, ruff. |

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
| 1.45 | Choice quality validation | **DESIGNED** | Five-dimension rubric (genericity, character expression, risk spread, tactical differentiation, contextual grounding). Local model evaluator with binary yes/no questions. Two-of-five failure threshold. Shares existing retry budget. Activation contingent on calibration results from initial playtesting — if cloud model consistently produces good choices, defers to Phase 7. See `specialist/choice-quality-validation.md` v1.0. |

---

## Phase 2: Post-V1 Game Engine Enhancements

Items that require a working vertical slice before meaningful design
or implementation can begin. Ordered by estimated dependency chain.

### Mechanical Expansions

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 2.1 | Psychometric prologue system | **DESIGNED** | GM §5, CS §2.5–2.6, Prologue Inference Spec v1.0 | Requires Campaign Studio character variants and prologue scene library (Phase 3) | Three-layer inference: behavioral archetype (algorithmic), mechanical profile (hand-authored mapping table scoped by career type), narrative identity (single cloud call). 3–5 adaptive scenes. Prologue scenes drawn from career- and allegiance-scoped library. V1 uses pre-built Keth. Robustness requirements (contradiction handling, confidence scoring, anti-gaming, fallback behavior, scene library diversity) specified in Prologue Inference Spec. |
| 2.2 | Character funnel and allegiance system | **DESIGNED** | Vision §8, CS §2.5, §2.8 | Requires Campaign Studio allegiance authoring (Phase 3), frontend funnel UI (Phase 2) | Three-step funnel: Timeline → Allegiance → Variant. Campaigns define 2–4 allegiances with 2–4 variants each. Protagonist integration layer connects each variant to the fixed thematic spine. Campaign spine JSON uses `allegiances` array instead of flat `character_variants`. Frontend presents funnel as guided identity selection. |
| 2.3 | Obligation trigger system | **DONE** (Milestone 1) | GM §9 (mechanic), §26 (between-act pipeline step 8) | Phase 7 (act boundary detection) | d100 roll at act start. If ≤ Obligation value: strain threshold reduced by 2, GM receives narrative pressure instruction. Decrease via in-story actions (1–5 points). Fires as step 8 of the between-act pipeline. |
| 2.4 | Duty trigger system | **DONE** (Milestone 1) | GM §9 (mechanic), §26 (between-act pipeline step 8) | Phase 7 (act boundary detection) | Same d100 mechanism. Activation increases wound threshold by 1. GM presents competing opportunity aligned with Duty type. Increase when fulfilled. Fires as step 8 of the between-act pipeline. |
| 2.5 | Morality drift tracking | **DONE** (Milestone 1) | GM §9 (mechanic), §26 (between-act pipeline step 10) | Phase 7 (act boundary detection), `moral_weight` column exists in V1 | End-of-act resolution: Conflict earned minus 1d10. If Conflict > roll, Morality decreases. Morality labels (Light/Grey/Dark) injected into GM prompt as tone modifier. Fires as step 10 of the between-act pipeline. |
| 2.6 | Destiny Point spending mechanics | **DONE** (Milestone 1) | GM §23 (v1.6) | Pool tracked in V1 (Rule 8) | System-managed Light/Dark spending via narrative conditions. Stage 4 of the pool modification pipeline. Light Side triggered by narrative stakes and player investment. Dark Side triggered by Obligation activation, antagonist engagement, and spine-authored triggers. Optional seize-the-moment pre-roll choice at campaign climaxes. Escalation pacing maintains push-pull rhythm. |
| 2.7 | Character advancement / XP spending | **DONE** (Milestone 1) | GM §14 (v1.5) | FFG rules defined; UX designed | Behavioral inference engine for skill ranks (automatic, based on choice patterns and failure learning). Milestone reflections for talents, specializations, characteristics, Force awakening. XP earning via base-plus-performance at act boundaries. Aspiration echo infrastructure for Hybrid 3 future upgrade. |
| 2.8 | Talent trees | **DONE** (Milestone 1) | GM §15 (v1.5) | Depends on 2.7 | Five-type talent taxonomy (passive, conditional, substitution, narrative enabler, intervention). Pool modification pipeline. Pre-narration intervention step. Branch-based tree navigation through milestone reflections. Talent library with shared definitions. Phased data entry: Smuggler specs first, then by game line. |
| 2.9 | Vehicle and starship encounters | **DONE** (Milestone 3) | GM §17 (v1.5) | Parallel to combat abstraction (GM §3) | Ship state cards. Three-tier damage model (operational/stressed/critical). Encounter-level resolution. Role-determines-skill mapping. Battle context layer for large-scale engagements. Simplified vehicle critical hit table. |
| 2.10 | Equipment and inventory | **DONE** (Milestone 1) | GM §18 (v1.5) | — | Loadout model replacing item-by-item inventory. Four categories: weapons, armor, tools, special items. Acquisition/loss through narrative. Equipment effects on check decisions and narration. Lightsaber special treatment. |
| 2.11 | Faction state tracking | **DESIGNED** | Gap Analysis §Tier 3 | Phase 7 (reconciliation detects faction-relevant actions) | FactionState model: faction_id, display_name, disposition_to_player (0-1), influence (0-1), awareness_of_player (0-1), status_notes. Campaign spine gains `factions` array with per_act_drift for authored baseline changes. Reconciliation step updates faction state from narration. At act boundaries, drift applied. 1-2 sentence summary per faction injected into galactic context block. Faction states included in cross-campaign import package. Summary layer, not simulation — 3 numbers per faction plus status note. Token budget: ~90-150 tokens for 3-5 factions. |

### Prose & Narration Enhancements

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 2.12 | Prose diagnostic signal (runtime implementation) | **DONE** (Milestone 1) | GM §13 | — | Lightweight local-model call per turn. Scans last 3–4 passages for: sensory channel monotony, rhythm repetition, opener similarity, NPC action-emotion coherence drift, relationship positivity bias. Structured JSON output injected into cloud model context. Runs parallel with check decision (zero additional latency if parallelized). Dual-use as distillation curation filter. |
| 2.13 | Scene-type-aware context assembly | **DONE** (Milestone 1) | GM §10 (expanded) | Scene type classification working | Prompt assembly routing by scene type. Kinetic scenes foreground mechanical state; reflective scenes foreground motivational/relational context and reduce mechanical noise. Research-backed (Pan et al., IJHCI 2025): structured state helps action narration, hurts introspective narration. No changes to ContextPackage class. |
| 2.14 | Narration distillation pipeline (QLoRA) | **DESIGNED** | LLM Eval §8.4, Impl backlog | 500–1000 curated pairs from V1 play | QLoRA fine-tune of Qwen3.5:9B on cloud context→narration pairs. Goal: handle lower-stakes scenes (exploration, transitions) locally, reserve cloud for climactic beats. Could reduce cloud costs 50–70% per session. Scene type classification provides the routing signal. |
| 2.15 | Distillation curation dual-filter spec | **DESIGNED** | LLM Eval §8.4, Research Cat. Source 2 | Depends on 2.12 (prose diagnostic) | Filter 1: automated staleness check via prose diagnostic — excludes monotone/repetitive passages. Filter 2: mechanical fidelity — dice result honored, NPC voice consistent, word count valid, choices with delimiter. Both must pass. |
| 2.16 | Distillation evaluation failure taxonomy | **DESIGNED** | Gap Analysis §Tier 3 | Post-V1 model comparison | Five binary failure categories: (1) reference confusion — narration hallucinates entities not in context, (2) dice softening — failed checks narrated as partial successes, (3) choice genericization — choices lack scene-specific proper nouns, (4) continuity break — narration contradicts established state, (5) format violation — missing delimiters/word count/skill tags. Categories 1,2,5 fully automatable; 3,4 partially. Candidate viable if aggregate pass rate within 10% of cloud reference, dice softening ≤5%. Test set: 50+ context packages. |
| 2.17 | Session resume "Previously..." passage | **DONE** (June 2026 experience shell) | GM §6 | `state/memory.py` `generate_resume_recap` | 80–150 word fast-tier summary from compressed memory and recent turns, second-person present tense, ends at the current decision point. Cached per turn-count in arc_state; generated by `GET /session/{id}` (fail-open, `RESUME_RECAP_ENABLED`); rendered as "The story so far" card on resume. |
| 2.18 | First-check teaching moment (dice panel tooltip) | **DESIGNED** | GM §7 | — | First time a skill check occurs in a session, dice panel auto-expands with one-time tooltip explaining hidden dice. Dismissible, never appears again. Phase 6 frontend feature. |
| 2.19 | Turn counter for spine advancement | **DESIGNED** | Gap Analysis v2.0, GM §26.3 | Late-V1 or Phase 7 | PacingSignal model with deterministic pacing zone (early, on_pace, late, overdue) computed from turns_this_act and expected_turns. Removes arithmetic from local model. Zone injected into reconciliation and narration prompts with delta modifier guidance. |

### NPC System Expansions (Vision §11)

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 2.20 | NPC relationship triangles (NPC-NPC dispositions) | **DESIGNED** | Gap Analysis §Tier 5, Vision §11 | — | NPCState gains `npc_dispositions: dict[str, float]`. Campaign spine NPC entries gain `npc_relationships` with NPC-name → disposition mappings. Initialize from spine, update via reconciliation step when NPCs interact. Tier 1 NPC state cards include relationships to other Tier 1/2 NPCs. Token cost: ~10-20 tokens per NPC, negligible. Scope: player-visible social signals, not hidden simulation. |
| 2.21 | NPC emotional state (transient in-scene mood) | **DONE** (Milestone 1) | GM §25 (v1.6) | — | Nine-mood vocabulary (calm, angry, afraid, grieving, suspicious, grateful, desperate, amused, conflicted) with intensity and decay. Set by dice results, spine triggers, and GM-inferred cues. Injected into NPC prompt blocks. Sustained emotions nudge disposition. |
| 2.22 | NPC behavioral envelopes (enforcement) | **DESIGNED** | Gap Analysis §Tier 5, Vision §11 | `behavioral_envelope` field exists in V1 NPCState | Field exists and is passed to GM prompt. Compliance test Category 6 added: 5 test scenarios where narrative pressure pushes NPC toward envelope violation. Pass criterion: GM respects envelope in all 5. If any fail, add prompt reinforcement: "HARD CONSTRAINT: {npc_name} will NEVER {envelope}. Violating this is equivalent to producing incorrect dice results." Test-then-fix item. |
| 2.23 | NPC information propagation (offscreen knowledge transfer) | **DESIGNED** | Gap Analysis §Tier 5, Vision §11 | Reputation log exists in V1, Phase 7 (reconciliation) | NPCState gains `social_connections: list[str]`. Campaign spine NPC entries gain `social_connections` listing NPCs they communicate with. At act boundaries, reputation events propagate one-hop through social connections: if NPC A witnessed event and NPC B is in A's connections and appears in next act, B gains knowledge_add entry. One-hop only, act-boundary only. Lightweight social graph, not simulation. |

### Infrastructure

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 2.24 | Semantic memory / meaningful choice extraction | **DONE** (Milestone 1) | GM §24 (v1.6) | — | Per-turn choice annotation via local model extracting behavioral meaning: intent, sacrifice, priority revealed, NPC impact, throughline relevance. Feeds enriched data to behavioral inference, character drift, aspiration echoes, and cross-campaign identity. Graceful degradation to skill-tag-only on annotation failure. |
| 2.25 | Character-centric campaign management | **DESIGNED** | Gap Analysis §Tier 2 | — | Character is the primary entity, campaigns are chapters in a character's story (aligns with Vision §8). Data model: `characters` table (character_id, display_name, variant_pitch, allegiance, era), `character_campaigns` table (character_id → campaign_spine, campaign_order, status, session_id). UI: character screen as app entry point showing character cards with name, variant pitch, current campaign, act progress, last played. Actions: Continue (active), Begin Next Chapter (completed → import flow), Create a Character (→ funnel). One active campaign per character. Character history shows ordered chapter list. **Lite version shipped (funnel pass 2026-07-02):** localStorage Continue shelf (chapter progress / ending name), fixture-filtered `GET /sessions` listing, epilogue re-entry doors incl. `prior_session_id` sequel hook. Full character/chapter data model still unbuilt. |
| 2.26 | Settings / API key management UI | **DESIGNED** | Gap Analysis §Tier 2 | — | Settings panel on campaign management screen: cloud LLM provider selection, model string, API key entry (encrypted at rest via Fernet, masked to last 4 chars in UI), local model config (Ollama endpoint, model name), narrative backend toggle. Settings persist in `settings` SQLite table, overridden by env vars. Changes take effect on next session start. "Test Connection" button for provider verification. New files: `state/settings.py`. Extend: `web/index.html`, `api/game_routes.py`. |
| 2.27 | Multi-arc campaign structure | **DESIGNED** | GM §§19-20 (v1.5), Import Package Quality Spec v1.0 | — | Time skip mechanics with vignette system for intra-campaign gaps (§19). Cross-era character progression with import packages, specialization continuity/dormancy/evolution, era transition processing (§20). Large-scale NPC management with three-tier relevance routing (§21). Canon character voice fidelity profiles (§22). Narrative compression quality standards for import packages (relationship summaries, throughline history, voice notes, memory shards) specified in Import Package Quality Spec. |
| 2.28 | Generative entity persistence | **DESIGNED** | Gap Analysis v2.0, Vision §6/§11/§12, GM §26 | Phase 7 (reconciliation), Phase 20 (NPC tiering) | Reconciliation prompt extension for entity detection (low/medium/high significance). Entity card generation prompt per type. SQLite `emergent_entities` table with per-act cap (max 3). Tier promotion logic (3→2→1 based on reference count). Reintroduction injection formats for NPCs, locations, and facts. Cross-campaign persistence for entities with reference_count ≥ 3 or tier ≤ 2. Enrichment layer — authored spine carries full load without it. Evaluate need after Milestone 1 playtesting. |

### Player Experience Funnel (July 2026 pass)

Shipped 2026-07-02 as a UX continuation of the June experience-shell
work. Full detail in the changelog entry of the same date. No engine
phases consumed; no turn-handler changes.

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 2.29 | Player funnel UX shell | **DONE** (2026-07-02) | Changelog 2026-07-02 | — | Entry hero (Play Now from `intended_protagonist`), character reveal card with stats behind disclosure, situation three-door (canonical drop-in default / surprise / steer with explicit mode), dossier wait screen with honest latency + dice primer, failure exits (generate 502→retry or canonical fallback; draft 422→fix-and-re-draft; provider-unreachable→actionable 503), incapacitation card, progressive dice disclosure, pending-decision banner, freeform ghost text + counter, stream-failure retry, sealed-endings finale, three re-entry doors, Continue shelf. All in `web/index.html` + payload additions in `api/game_routes.py`. |
| 2.30 | Funnel randomization content | **DONE** (2026-07-02) | Changelog 2026-07-02 | — | `data/funnel/spark_tables.json` (template + 12 species, 18 careers with game lines, 30 hooks, 20 flaws) and `data/funnel/premise_seeds.json` (2 eras, 13 seeds each, tones, moral registers) served by `GET /funnel/seeds`; spark picks ride the `hints` dict on `POST /character/draft` (guidance section added to `character_draft.txt`). Perceived richness is bounded by table quality — budget writing time when adding era packs. |
| 2.31 | Check-decision transport fallback | **DONE** (2026-07-02) | Changelog 2026-07-02 | — | See item 1.6 detail. 13 tests in `tests/test_check_decision_fallback.py`. |
| 2.32 | Funnel guardrails: rate limiting + conversion telemetry | **DONE** (2026-07-02) | Changelog 2026-07-02 | — | `api/ratelimit.py` per-IP sliding windows on draft (30/hr) and generate (12/hr), env-tunable, 0 disables; never-raising `funnel_event()` in `state/telemetry.py` → `funnel_events.jsonl` (draft/save/generate/session-create/epilogue). 17 contract tests in `tests/test_funnel_payloads.py`. |
| 2.33 | Funnel follow-ups | **FILED** | Changelog 2026-07-02 (known limits) | — | Pre-warm/pre-cache the canonical opening passage (true zero-wait Play Now); `duty_active` +1 threshold edge on the incapacitation banner (expose effective threshold or an `incapacitated` flag in turn payloads); add `pending_force_power_milestone` to the `pending` object; dedicated resume UI for temptation/intervention/time-skip pauses; Continue-shelf prune-on-404; SQL-side session-listing filter; `node --check` for `web/index.html` once Node is available; wire `eval/divergence.py` as a replay-divergence pre-ship check for the "1 of N endings" promise; `funnel_events.jsonl` rotation. |

---

## Phase 3: Campaign Studio Build

The authoring system. Design documented in Campaign Studio Design
Document (v1.2). Implementation specified in Campaign Studio
Implementation Document (v1.3). Six build phases: CS-1 through CS-6.
**All six CS phases are COMPLETE — CS-1 through CS-4 March 2026,
CS-5 and CS-6 April 2026.**

### Pre-Build Requirements

| # | Item | Status | Notes |
|---|------|--------|-------|
| 3.0a | Campaign Studio Implementation Document | **DONE** (CS Impl v1.1) | Four build phases, Pydantic schema (with Allegiance, IntegrationLayer, NPCOverride models), validation suite, all three mode paths, saga layer pipeline, cross-era import, database additions. Updated for character funnel pivot. |
| 3.0b | LLM Evaluation expansion for Campaign Studio roles | **DONE** (LLM Eval v2.0) | Five roles defined with model assignments: divergent ideation (local), spine refinement (cloud), critique (test both), evaluation (cloud → local after fine-tuning), generation (cloud). |
| 3.0c | Campaign spine format alignment check | **NOT STARTED** | Verify Impl §12 test spine maps cleanly to CS Design §4 schema. The V1 spine is deliberately simpler (no allegiances, variants, prologue, variation points). Document the mapping and any fields that need stub values for V1. Note: schema now uses `allegiances` array, not `character_variants`. |

### Phase CS-1: Schema and Validation

| # | Item | Design Status | Design Doc | CS Impl Doc | Detail |
|---|------|--------------|-----------|-------------|--------|
| 3.1 | Campaign spine Pydantic schema (`studio/schema.py`) | **DONE** (CS-1) | CS Design §4, CS Impl §4.1 | CS Impl §4.1 (full code) | `CampaignSpine` model with nested models for Allegiance, CharacterVariant (with IntegrationLayer, NPCOverride), PrologueSet, Act, NPC, VariationPoint, SagaMetadata. Field validators for act sequencing, track validity, allegiance-variant containment, field lengths. Both systems import from this file. |
| 3.2 | Gate 1: Schema contract validation | **DONE** (CS-1) | CS Design §5.1, Research Cat. Source 1 | CS Impl §4.2 | Pure Python. Acts sequential, NPC references resolve, axis tags present, allegiances contain ≥1 variant each, variant `allegiance` field matches containing allegiance `id`, throughline is a question, no dangling references. |
| 3.3 | Gate 2: NPC coherence validation | **DONE** (CS-1) | CS Design §5.2, Research Cat. Source 8 | CS Impl §4.2 | Per-NPC disposition trajectory analysis. Flags disposition shifts > 0.3 between acts without setup. Action-emotion chain tracing. |
| 3.4 | Gate 3: Relationship network validation | **DONE** (CS-1) | CS Design §5.3, Research Cat. Source 9 | CS Impl §4.2 | NetworkX graph analysis. Flags: mean edge weight > 0.5 (insufficient conflict), > 80% positive relationships, sparse antagonist networks. Targets human-written distribution. |
| 3.5 | Gate 4: Narrative consistency audit | **DONE** (CS-1) | CS Design §5.4, Research Cat. Source 12 | CS Impl §4.2 | Three LLM calls: narrative coherence (contradictions, dropped threads), mechanical balance (difficulty curves, scene variety), prose variety potential. Optional without cloud access; Gates 1–3 mandatory. |
| 3.6 | Schema validation tests | **DONE** (CS-1) | — | CS Impl §3 (Phase CS-1 success criteria) | Nar Shaddaa Job test spine passes all four gates. Deliberately malformed spine fails with specific error messages. |

### Phase CS-2: Mode 3 — Full Collaboration

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 3.7 | Mode 3 collaborative authoring workflow | **DONE** (CS-2) | CS Design §3 (Mode 3) | CS-1 complete | Author drives, AI assists. Throughline→anchors→NPCs→galactic context→variants→prologue scenes→validation. |
| 3.8 | Mode 3 assistance prompt (`studio/prompts/mode3_assist.txt`) | **DONE** (CS-2) | CS Impl §3 | — | AI suggests alternatives, flags structural issues, generates galactic context drafts, drafts NPC voice notes. |
| 3.9 | Throughline question authoring tooling | **DESIGNED** | CS Design §2.1 | — | AI evaluates throughline questions against four criteria: debatable, pressurable from multiple directions, answerable through tactics, sustains 20+ hours. |
| 3.10 | Anchor beat design tooling | **DESIGNED** | CS Design §2.2 | — | Validates anchors are situations (not outcomes), work with multiple archetypes, transform the situation irreversibly. 5–8 turn spacing between anchors. |
| 3.11 | NPC relationship architecture tooling | **DESIGNED** | CS Design §2.3 | — | Validates conflict requirement, cross-cluster interactions, disposition trajectories, behavioral envelopes. |
| 3.12 | Galactic context authoring | **DESIGNED** | CS Design §2.4 | — | 2–4 sentences per act. Must be specific (not generic). At least one element per act with potential relevance. Changes between acts. |
| 3.13 | Character variant design + prologue scene design + integration layer | **DESIGNED** | CS Design §2.5, §2.6, §2.8 | — | 2–4 allegiances per campaign, 2–4 variants per allegiance. Each variant includes integration layer (entry point, personal stakes, NPC overrides, anchor adaptations). Prologue scenes drawn from career-allegiance scene library where possible. At least one non-combat variant. Cross-allegiance variants must produce structurally different experiences. |
| 3.14 | Prose variety by design checks | **DESIGNED** | CS Design §2.7 | — | Scene type diversity across acts, location variety (2–3 distinct environments per act), emotional register shifts (contrast moments). |
| 3.15 | Studio API routes (`api/studio_routes.py`) | **DONE** (CS-2) | CS Impl §2 | — | Authoring endpoints for Mode 3 workflow. |

### Phase CS-3: Mode 2 — Thematic Steering + Cross-Era Import

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 3.16 | Mode 2 generation pipeline | **DONE** (CS-3) | CS Design §3 (Mode 2) | Mode 3 working | Author provides thematic brief (era, location, tone, throughline, concept). AI generates complete spine draft. Author reviews and edits. |
| 3.17 | NPC voice generation (cloud model) | **DONE** (CS-2) | Gap Analysis §Tier 3, CS Design §8 | — | Cloud model generates NPC voice notes from NPC name, motivation, role_in_act, and behavioral_envelope. Prompt template (`studio/prompts/npc_voice_gen.txt`) requests 2-4 sentences covering vocabulary/register, verbal tics, emotional default, one distinguishing trait. Quality gate: flag notes containing zero speech-action verbs (hedges, deflects, clips, drawls, etc.) for regeneration. Integration: runs after NPC roster generation, before Gate 2 (NPC coherence). Mode 3: optional assist; Modes 2/1: automatic. |
| 3.18 | Campaign import interface (`studio/import_interface.py`) | **DONE** (CS-3) | CS Design §6.1, CS Impl §6 | Spine format finalized | Maps completed character state onto new campaign: motivation tracks, NPC relationship dispositions, world state variables. Game Engine receives a character dict indistinguishable from fresh start. |
| 3.19 | Canon as environmental constraint system | **DESIGNED** | CS Design §6.2 | — | Canon events as galactic-scale environmental anchors. Player agency at personal scale. Relationship to canon characters shaped by play history. |
| 3.20 | World state variable tracking (butterfly effect) | **DESIGNED** | CS Design §6.3 | — | Player actions create ripples at personal/social/local scale that compound across eras. Not rewriting galactic timeline — a Corellian senator remembers your name because you helped in Act 2. |

### Mode 1 — Full Blind (Long-Term Aspiration)

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 3.21 | Mode 1 generation pipeline | **DONE** (CS-4) | CS Design §3 (Mode 1) | Mode 2 working | AI generates complete campaign from minimal input. Explicitly lower quality contract. |
| 3.22 | Negative archetype specification | **DESIGNED** | Research Cat. Source 11, CS Design §3 | — | "This campaign is NOT" description. Archetype avoidance list. Without anti-default signals, LLM produces hero's journey with Dark Side antagonist and redemptive climax. |
| 3.23 | Quality contract definition | **DESIGNED** | CS Design §0 (Principle 2), §3 | — | Mode 1: playable but explicitly lower quality. May have thinner NPC networks, less surprising anchors, more predictable dynamics. Bar: "engaging and not generic." |

### Non-Linear Spine Structures (CS §7)

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 3.24 | Hub-and-spoke spine structure | **DESIGNED** | CS Design §7.1 | — | Acts tagged with prerequisites, not fixed sequence. Anchors designed around accumulated state rather than specific prior events. |
| 3.25 | Parallel tracks spine structure | **DESIGNED** | CS Design §7.2 | — | Two simultaneous story threads. `track` field per act. Convergence anchor requires both tracks at specified progress. |

### Phase CS-5: Narrative Quality — Story Architecture + Gate 4

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 3.35 | Pre-generation story architecture (`studio/architect.py`) | **DONE** (CS-5) | Story Architecture Spec, CS Impl §3 (CS-5) | CS-4 complete | `generate_architecture()` produces `StoryArchitecture` model from era/location/tone input. `architecture_to_prompt_block()` injects into Mode 1/2 generation. Anti-default rules prevent generic premises. Five pressure types: moral, identity, loyalty, survival, ideological. |
| 3.36 | Gate 4 narrative evaluation (`studio/narrative_eval.py`) | **DONE** (CS-5) | Story Architecture Spec, CS Impl §3 (CS-5) | 3.35 | Three sub-gates: 4a coherence (thread_continuity, npc_trajectory, throughline_presence, context_relevance), 4b dramatic quality (conditional on story_architecture — premise, CDQ, antagonist, NPC diversity, contradiction), 4c anti-genericity (NPC distinctiveness, anchor specificity, escalation authenticity). |
| 3.37 | Narrative quality scoring | **DONE** (CS-5) | Story Architecture Spec | 3.36 | `score_narrative_quality()` returns normalized 0.0–1.0 across five dimensions: premise_strength, npc_thematic_diversity, dramatic_progression, throughline_testability, anti_genericity. |
| 3.38 | Story architecture prompt templates | **DONE** (CS-5) | — | — | `architect.txt` (112 lines), `narrative_eval.txt` (57 lines), `narrative_score.txt` (54 lines). |
| 3.39 | StoryArchitecture schema model + related fields | **DONE** (CS-5) | Story Architecture Spec, CS Impl §4.1 | — | StoryArchitecture, CharacterVariant.protagonist_contradiction, CharacterVariant.pressure_revealed_identity, NPC.thematic_argument, Act.dramatic_function. |
| 3.40 | CS-5 test suite | **DONE** (CS-5) | — | 3.35–3.39 | `test_cs5_narrative_quality.py`: 33 tests covering architecture generation, Gate 4 evaluation, scoring, and schema validation. |

### Phase CS-6: Story Engineering Integration

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 3.41 | Dramatic mission classification (`engine/dramatic_mission.py`) | **DONE** (CS-6) | CS Impl §3 (CS-6) | CS-5 complete | 14 mission types across Brooks's four-part model. PART_MISSION_MAP, MISSION_TO_VOICE, VOICE_INSTRUCTIONS. `compute_valid_missions()`, `check_midpoint_conversion()`, `check_no_new_exposition()`. Pure Python. |
| 3.42 | Scene purpose validation (`engine/scene_validator.py`) | **DONE** (CS-6) | CS Impl §3 (CS-6) | 3.41 | Post-narration local model call scoring 5 dimensions (mission_delivery, pressure_progression, antagonist_relevance, character_choices, change). Quality signal only. |
| 3.43 | MilestoneBeatSheet schema model | **DONE** (CS-6) | Story Architecture Spec | — | concept_question, first/second plot points with act numbers, midpoint, pre_resolution_lull. Sequence + placement % validation. |
| 3.44 | PinchPoint, ForeshadowLink, CharacterDepthCard models | **DONE** (CS-6) | Story Architecture Spec | — | Structural storytelling schemas: antagonist pressure signals, setup→payoff pairs, GM-facing character enrichment. |
| 3.45 | ProtagonistMode enum + progression validation | **DONE** (CS-6) | CS Impl §3 (CS-6) | — | ORPHAN→WANDERER→WARRIOR→MARTYR. Monotonic progression enforced. |
| 3.46 | NPC.pressure_role field | **DONE** (CS-6) | CS Impl §3 (CS-6) | — | Nine validated roles: tempter, mirror, skeptic, dependent, betrayer, witness, escalator, false_ally, catalyst. Diversity warning if all roles identical. |
| 3.47 | CS-6 deterministic structural checks | **DONE** (CS-6) | CS Impl §3 (CS-6) | 3.43–3.46 | Pinch point coverage, beat sheet sequence, placement percentages, concept question format, protagonist regression, pressure role diversity, foreshadow ordering + final-third coverage. |
| 3.48 | CS-6 test suites | **DONE** (CS-6) | — | 3.41–3.47 | `test_cs6_story_engineering.py` (Campaign Studio tests) + `test_story_engineering.py` (Game Engine tests). |

### Evaluation Harness and Telemetry

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 3.49 | Narrative telemetry event system (`state/telemetry.py`) | **DONE** | — | Phase 4 (state persistence) | Structured JSON-lines event logging per session. Emitters: choice_made, dice_resolved, state_delta, npc_disposition_shift, thread_event, choice_quality_eval, act_transition, session_summary. |
| 3.50 | Evaluation harness (`eval/harness.py`) | **DONE** | — | 3.49 | Scripted play sessions with golden scenarios and configurable policies. Runs automated turns and collects quality metrics. |
| 3.51 | Quality metrics (`eval/metrics.py`) | **DONE** | — | 3.49 | Tier 1 (heuristic, no LLM): slop rate, word count, choice distinctness. Tier 2 (LLM-assisted): deeper quality analysis. |
| 3.52 | Divergence analysis (`eval/divergence.py`) | **DONE** | — | 3.50 | Cross-session structural replayability measurement. Compares narrative outcomes across different policies/seeds. |
| 3.53 | Golden scenarios + policies (`eval/golden_scenarios.py`, `eval/policies.py`) | **DONE** | — | 3.50 | Fixed-seed reproducible test scenarios with configurable automated choice selection strategies. |
| 3.54 | Evaluation reporter (`eval/reporter.py`) | **DONE** | — | 3.50–3.52 | Human-readable console + machine-readable JSON report generation. |

### Campaign Studio Deferred Items (CS §8)

| # | Item | Design Status | Design Doc | Detail |
|---|------|--------------|-----------|--------|
| 3.26 | Deterministic seeding for reproducible generation | **DONE** (CS-2) | Gap Analysis v2.0, CS Design §8 | Per-stage seed derivation from master seed via SHA-256. GenerationMetadata model stored alongside spines. Partial regeneration UX: "regenerate NPCs," "regenerate structure," "full regenerate." Seed parameter passed via OpenAI-compatible and Ollama APIs. Effectiveness caveat documented (seed is "best effort" across providers). |
| 3.27 | Spine difficulty calibration | **DONE** (CS-2) | Gap Analysis v2.0, CS Design §8 | Four-signal per-act difficulty scoring: anchor intensity (30%), NPC opposition (25%), mechanical pressure (25%), pacing pressure (20%). SpineDifficultyCurve with composite score 1.0–5.0, curve shape classification (flat/rising/spiked/valley), and calibration warnings. Runs during Gate 4 in `studio/validate.py`. Pure Python, no LLM calls. |
| 3.28 | Campaign rating and feedback system | **DESIGNED** | Gap Analysis v2.0, CS Design §8 | Post-completion rating collection (1-5 overall, optional 3-dimension breakdown: story/characters/pacing, optional free-text). `campaign_ratings` SQLite table. Exemplar selection for Mode 1/2 generation prompts from highly-rated spines. Failure pattern detection across low-rated campaigns. Non-intrusive UI integration at campaign completion. |

### Character Funnel Items (Vision §8, CS §2.5, §2.8)

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 3.29 | Protagonist integration layer authoring workflow | **DESIGNED** | CS Design §2.8 | Mode 3 working | Authoring fixed thematic spine and per-allegiance integration layers: entry points, personal stakes, NPC relationship overrides, anchor beat adaptations. Anchors must be abstract enough to survive all integration variants. |
| 3.30 | Prologue scene library system | **DESIGNED** | CS Design §2.6, GM §5 | Schema finalized | Career- and allegiance-scoped scene library. `career_type` and `allegiance` tags. `library_reusable` flag. Recommended: 3 library scenes per career-allegiance combo + 2 campaign-specific per variant. Reduces authoring overhead as funnel combinatorial space grows. |
| 3.31 | Career-type mapping table library | **DESIGNED** | GM §5 | Schema finalized | Layer 2 behavioral-cluster-to-mechanical-profile mapping tables scoped by career type. Reusable across campaigns. One table per FFG career covers all variants of that career regardless of allegiance or campaign. |
| 3.32 | Character funnel frontend UI | **DESIGNED** | Gap Analysis §Tier 2, Vision §8 | Phase 2 frontend foundation | Three-step full-screen panel flow: Step 1 Timeline (campaign selection, skip if only one spine), Step 2 Allegiance (2-4 cards with narrative descriptions, no mechanical info), Step 3 Variant (2-4 cards with narrative pitches, career/species NOT shown — player chooses story, not build). Back navigation at each step. On variant selection, transitions to prologue (same UI as main game loop). Endpoint: `GET /api/funnel/{campaign_id}`. Design constraint from Vision §8: "Must feel like entering a story, not configuring a character sheet." |
| 3.33 | Integration layer validation | **DESIGNED** | Gap Analysis §Tier 2, CS Design §2.8 | Gate 1 extended | Five checks added to Gate 1 in `studio/validate.py`: (1) integration layer completeness — entry_point, personal_stakes non-empty, anchor_adaptations has ≥1 entry per anchor, (2) NPC override reference validity — all overridden NPCs exist in roster, (3) anchor adaptation coverage — warn on missing adaptations, (4) entry point distinctness — flag identical entry points within same allegiance, (5) personal stakes non-generic — flag <20 chars or generic phrases. Pure Python, no LLM calls. |
| 3.34 | Allegiance diversity validation | **DESIGNED** | Gap Analysis §Tier 2, CS Design §2.5 | Gate 3 extended | Three checks added to Gate 3 in `studio/validate.py`: (1) NPC disposition overlap — flag allegiance pairs with >80% near-identical disposition modifiers, (2) anchor adaptation similarity — flag pairs with >60% identical adaptation strings, (3) entry point structural difference — flag if all allegiances enter through same NPC and location. Jaccard similarity on word sets, no NLP libraries needed. |

---

## Phase 4: Saga Layer Build

The sequel spine generation system. Design documented in Campaign
Studio Design §6.4. Implementation in CS Implementation §5.
**COMPLETE — CS-4, March 2026.**

### Pre-Build Requirements

| # | Item | Status | Detail |
|---|------|--------|--------|
| 4.0a | Saga layer test artifacts | **DESIGNED** (template) | Gap Analysis v2.0. Full markdown template specified with concrete sections for every pipeline stage (character export package → import summary → persona assignment → 7 SequelDirections → SpineSketch expansion → critique/debate → pairwise evaluation → validated spine). Partial artifact path using hypothetical Keth Varso completion data allows pipeline logic validation pre-Milestone 1. Full artifact with real play data requires Milestone 1 completion. |
| 4.0b | `saga_metadata` schema fields | **DESIGNED** | CS Impl §4.1. `SagaMetadata` model: prior_campaign_id, throughline_evolution, imported_npc_mappings, required_import_fields, default_state_for_new_characters. |
| 4.0c | Writer's Room intermediate schemas | **DESIGNED** | CS Impl §5. `SequelDirection` (Stage 2), `SpineSketch` with `ActOutline`/`NPCOutline` (Stage 3), draft `CampaignSpine` (Stage 4), `EvaluatedSpine` with `EvaluationResult` (Stage 5). |
| 4.0d | Persona pool curation and validation (50+ personas) | **DESIGNED** (pool drafted) | Gap Analysis v2.0. 55 personas across 11 thematic clusters drafted with full text. Tag distribution verified across age decades, risk tolerance, introversion/extroversion, care/justice/utilitarian ethics. Subset selection algorithm with cluster and age diversity constraints. Five-subset validation protocol specified (target: ≥3 of 5 subsets produce distinct sequel directions). Stored in `data/personas/writer_room_personas.json`. Validation execution requires working Stage 2 code. |

### Saga Layer Pipeline

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 4.1 | Stage 1 — Persona assignment system | **DONE** (CS-4) | CS Design §6.4.2, Research Cat. Source 3 | 4.0d (persona pool) | Assign heterogeneous ordinary personas from pool. Personas partition knowledge space (2.6x default diversity). |
| 4.2 | Stage 2 — Divergent generation with denial constraints + CoT | **DONE** (CS-4) | CS Design §6.4.2, Research Cat. Sources 3, 4 | 4.0c (schemas) | Persona-primed writers generate sequel directions. CoT breaks within-session fixation. Critical: prior campaign NOT provided as input here. Denial constraints: no repeat of prior conflict type, resolution structure, or obvious extension. Local model viable (no proprietary advantage on divergent thinking). |
| 4.3 | Stage 3 — Branching search over candidates | **DONE** (CS-4) | CS Design §6.4.2, Research Cat. Source 4 | 4.0c | Tree/beam search: expand promising candidates, evaluate, expand further, prune weak branches. 4–7x single-pass quality. Backtracking supported. Configurable depth. |
| 4.4 | Stage 4 — Debate/critique convergence with prior campaign | **DONE** (CS-4) | CS Design §6.4.2, Research Cat. Source 4 | — | Prior campaign enters HERE (not earlier). Critic agent challenges coherence, structural quality, thematic consistency. Debate/critique loop: critic challenges → writer revises → critic re-evaluates. Statistically significant improvements over single-agent. |
| 4.5 | Stage 5 — Three-axis pairwise evaluation | **DONE** (CS-4) | CS Design §6.4.2, Research Cat. Sources 5, 6 | — | Pairwise comparison (not isolated scoring). Three axes: structural quality, novelty, diversity. ICC 0.59 → 0.75 with pairwise. Top candidate selected (Mode 3: player reviews top 2–3; Mode 1: top candidate used directly). |
| 4.6 | Saga layer + Mode 3 integration | **DONE** (CS-4) | CS Design §6.4.5 | 4.1–4.5 working | Writer's Room generates 2–3 candidates. Player reviews, selects, modifies through collaborative editing. |
| 4.7 | Saga layer + Mode 2 integration | **DONE** (CS-4) | CS Design §6.4.5 | 4.6 working | Player provides thematic direction as additional Stage 2 constraint. |
| 4.8 | Saga layer + Mode 1 integration | **DONE** (CS-4) | CS Design §6.4.5 | 4.7 working | Writer's Room generates and selects autonomously. Explicitly lower quality contract. |

### Saga Layer Deferred

| # | Item | Design Status | Design Doc | Dependencies | Detail |
|---|------|--------------|-----------|-------------|--------|
| 4.9 | Trained local evaluator for spine quality | **DESIGNED** | Gap Analysis v2.0, CS Design §8, Research Cat. Source 5 | Corpus of 600+ pairwise comparisons from Stage 5 runs and player ratings | QLoRA fine-tune of local model on pairwise evaluation task. Three axes: structural quality, novelty, diversity. SpineSummary compression format for training context. `evaluation_pairs` table logs training data from cloud Stage 5 and player ratings. 80% agreement calibration threshold against cloud reference. Drop-in replacement via `SagaConfig.evaluator` setting (cloud/local/ensemble). |
| 4.10 | Multi-model ensemble (different LLMs as different writers) | **DESIGNED** | Gap Analysis v2.0, CS Design §8, Research Cat. Source 7 | Persona + CoT validated on single model first | Model-aware WriterConfig per writer with model/provider assignment. EnsembleConfig with configurable model pool and three assignment strategies (round_robin, weighted, random). Parallel asyncio execution in Stage 2. RunDiversityMetrics logging for Bitter Lesson monitoring. Graceful degradation to single-model on provider unavailability. Optional — default is single-model baseline. |

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

3. **Retired research docs.** ~~RESEARCH_SCOPING.md and
   SAGA_RESEARCH_FINDINGS.md are superseded by Research Catalogue v1.0.
   Should be removed from project files. Tracked as item 0.4.~~
   **RESOLVED:** Files removed from project. Item 0.4 marked DONE.

4. **CLAUDE.md content.** ~~Referenced in repo structure (Impl §3) but
   content not authored. Tracked as item 1.34.~~ **RESOLVED:** CLAUDE.md
   authored (item 1.34 DONE in v2.4) and updated with project guide
   reference and five new spec documents in v3.0.

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

7. **Phase 8 dependency gap.** ~~Phase 8 (Motivation Track Wiring) lists
   dependencies as "V1 complete" but should also list "Phase 7 complete."~~
   **RESOLVED:** Build Roadmap Phase 8 already correctly lists "V1
   complete, Phase 7 complete" as dependencies. The Deferred Design and
   Logic Analysis §4.4 identified this as a potential gap, but the Build
   Roadmap was already correct at v1.0.

8. **Character-centric management principle.** Vision §8 states the game
   develops around the player character ("A tabletop GM asks 'who do you
   want to play?' and reshapes the adventure around the answer"). The
   cross-era import system (GM §20) is character-centric. This implies
   the primary management entity should be the character, not the
   campaign session. Item 2.25 has been revised accordingly. Consider
   making the character-centric principle explicit in Vision §8 or §17.

---

## Document Status Summary

| Document | Version | Status | Next Action |
|----------|---------|--------|-------------|
| Vision | v3.1 | **CURRENT** | Character funnel pivot applied. Consider adding explicit character-centric management principle (Alignment Note 8). |
| Game Mechanics | v1.8 | **CURRENT** | 27 sections (0-26). Reputation echo delivery and conditional choice availability designed. |
| Implementation (Game Engine) | v2.5 | **CURRENT** | §14 backlog updated: 2.19, 2.28, 3.28 added to designed items; distillation pipeline moved to designed; Gap Analysis references corrected. |
| Build Roadmap | v1.3 | **CURRENT** | Phase 21 directory reference corrected. Milestones 0-3 complete. Phase 17 complete. |
| LLM Evaluation | v2.0 | **NEEDS UPDATE** | Add Category 6 (behavioral envelope compliance) to §11 test protocol. Monitor DeepSeek V4 and Qwen3.5-397B. |
| Campaign Studio Design | v1.3 | **CURRENT** | Game Mechanics v1.5 cross-references applied. |
| Campaign Studio Implementation | v1.3 | **CURRENT** | FactionSpec and GenerationMetadata schema models added. Gate 1 and Gate 4 validation expanded. CS-2/CS-4 deliverables updated. Saga config, ensemble, and evaluator training infrastructure specified. |
| Research Catalogue | v1.0 | **CURRENT** | No pending additions. |
| Design Gap Analysis | v2.0 | **CURRENT** (in `docs/reference/`) | Full design specs for all project items. v1.1 items applied. v2.0 adds: 2.19, 2.28, 3.26, 3.27, 3.28, 4.9, 4.10, 4.0a, 4.0d. Zero CONCEPT ONLY / FILED / CONSIDER items remain. |
| Deferred Design and Logic Analysis | v1.0 | **CURRENT** (in `docs/reference/`) | Turn loop verification, data flow analysis, invariant proofs, token budgets, post-V1 integration points. |
| Project Guide | v2.0 | **CURRENT** | Four-tier document architecture. Reading orders, authority map, invariants, quick reference. |
| Project State Matrix | v1.5 | **CURRENT** | Capability dashboard. CS-1 through CS-5 completion reflected. |
| Choice Quality Validation Spec | v1.0 | **CURRENT** | Post-generation choice quality validator. Activation contingent on calibration from initial playtesting. |
| Prologue System Spec | v1.0 | **CURRENT** | Merged from Prologue Inference Spec + Phase 18 Implementation Plan. Design robustness + implementation roadmap. |
| Import Package Quality Spec | v1.0 | **CURRENT** | Quality standards for narrative compression in cross-campaign import. Extends GM §20 and CS Impl §6. |
| This Backlog | v3.4 | **CURRENT** | Player funnel pass sync (2026-07-02). Items 2.29–2.33 added, 1.6/2.25 annotated. |

---

## Revision History

**v3.4 — Player funnel pass sync (July 2, 2026)**

1. **New section: Player Experience Funnel (July 2026 pass).** Items
   2.29–2.32 record the shipped funnel work (UX shell, randomization
   content, check-decision transport fallback, guardrails); 2.33 files
   the deliberate follow-ups from the pass.
2. **Item 1.6 annotated** with the cloud-only migration and the July
   2026 transport-failure fallback semantics.
3. **Item 2.25 annotated** — lite character-centric management shipped
   (Continue shelf, `GET /sessions`, re-entry doors); full data model
   remains DESIGNED.
4. Header/version drift corrected (v3.3 was never logged here; this
   entry supersedes it).

**v3.2 — Documentation audit sync (March 17, 2026)**

1. **Item 0.5 marked DONE.** Campaign spines now exist in full
   CS-format with `allegiances`, `variation_points`, `factions`, and
   `vehicle_registry`. Both `nar_shaddaa_job.json` and
   `echoes_of_the_force.json` are active.

2. **Document Status Summary updated.** Project Guide v1.3, Project
   State Matrix v1.4, Build Roadmap v1.3, this Backlog v3.2. Choice
   Quality, Prologue Inference, and Import Package specs changed from
   NEW to CURRENT.

3. **Codebase-documentation discrepancies corrected.** Phase 21
   `data/canon_profiles/` directory reference corrected (does not exist
   yet). Cloud model reference clarified (`gpt-5.2` in code, `gpt-4.1`
   in `.env.example`).

**v3.1 — Post-milestone implementation status sync (March 2026)**

1. **Phase 1 items (1.1–1.35) marked DONE (Milestone 0).** All V1
   build items are implemented and verified.

2. **Phase 2 mechanical items marked DONE.** Items 2.3–2.10 (Obligation,
   Duty, Morality, Destiny, advancement, talents, vehicles, equipment)
   marked DONE with milestone attribution. Items 2.12–2.13 (prose
   diagnostic, scene-type assembly) marked DONE. Items 2.21, 2.24
   (NPC emotional state, semantic memory) marked DONE.

3. **Phase 3 Campaign Studio items marked DONE.** Items 3.1–3.8,
   3.15–3.18, 3.21, 3.26–3.27 marked DONE with CS phase attribution.

4. **Phase 4 Saga Layer items marked DONE.** Items 4.1–4.8 marked
   DONE (CS-4).

5. **Document Status Summary updated.** Build Roadmap v1.2, Project
   Guide v1.2, Project State Matrix v1.3 reflected.

**v3.0 — Gap audit integration (March 2026)**

1. **Five new project documents added.** Project Guide v1.1
   (front-door orientation), Project State Matrix v1.1 (capability
   status view), Choice Quality Validation Spec v1.0 (post-generation
   choice validator), Prologue Inference Spec v1.0 (prologue
   robustness rules), Import Package Quality Spec v1.0 (narrative
   compression quality standards). All produced from the gap audit
   findings.

2. **Item 0.4 marked DONE.** Superseded research documents
   (RESEARCH_SCOPING.md, SAGA_RESEARCH_FINDINGS.md) removed from
   project files. Alignment Note 3 marked RESOLVED.

3. **Item 1.45 added.** Choice quality validation (DESIGNED). Five-
   dimension rubric, local model evaluator, shared retry budget,
   calibration protocol. Activation contingent on initial playtesting
   results. See Choice Quality Validation Spec v1.0.

4. **Item 2.1 updated.** Prologue Inference Spec v1.0 added to design
   doc references. Robustness requirements (contradiction handling,
   confidence scoring, anti-gaming, fallback behavior, scene library
   diversity) now specified.

5. **Item 2.27 updated.** Import Package Quality Spec v1.0 added to
   design doc references. Narrative compression quality standards for
   import packages now specified.

6. **Document Status Summary updated.** Five new documents added.
   Deferred Design and Logic Analysis listed (was missing). Backlog
   version bumped to v3.0.

**v2.9 — Design gap analysis v2.0 completion (March 2026)**

1. **Nine items upgraded to DESIGNED.** 2.19 (turn counter — PacingSignal
   model with deterministic zones), 2.28 (generative entity persistence —
   upgraded from CONCEPT ONLY with full reconciliation prompt, DB schema,
   tier promotion, and cross-campaign persistence), 3.26 (deterministic
   seeding — per-stage seed derivation, partial regeneration UX), 3.27
   (spine difficulty calibration — four-signal scoring, curve shape
   classification, Gate 4 integration), 3.28 (campaign rating/feedback —
   rating collection, exemplar selection, failure pattern detection),
   4.9 (trained local evaluator — QLoRA training spec, calibration
   protocol, drop-in replacement), 4.10 (multi-model ensemble —
   WriterConfig, assignment strategies, diversity metrics logging).

2. **Two pre-build items upgraded to DESIGNED (template/drafted).**
   4.0a (saga test artifacts — full template specified, partial artifact
   path documented), 4.0d (persona pool — 55 personas across 11 clusters
   drafted with tag distribution verification, subset selection algorithm,
   five-subset validation protocol).

3. **Zero undesigned items remain.** Every item that can be designed
   without runtime data now has a full design specification. Only Phase 5
   long-term aspirations (5.1–5.6) and open research questions (R.1–R.7)
   remain without design, as intended.

4. **Document Status Summary updated.** Design Gap Analysis upgraded to
   v2.0. Backlog version corrected to v2.9.

**v2.8 — Design gap analysis integration (March 2026)**

1. **Design Gap Analysis document created.** Comprehensive audit of all
   items not fully designed across the project. Full design specs
   provided for 14 items. Added to project as a companion design
   document.

2. **Eleven items upgraded to DESIGNED.** 2.11 (faction state tracking),
   2.16 (distillation evaluation taxonomy), 2.20 (NPC relationship
   triangles), 2.22 (behavioral envelope enforcement — compliance test
   protocol), 2.23 (NPC information propagation), 2.25 (character-
   centric campaign management — revised from session-centric), 2.26
   (settings/API key UI), 3.17 (NPC voice generation — prompt template),
   3.32 (character funnel frontend UI), 3.33 (integration layer
   validation — 5 checks), 3.34 (allegiance diversity validation —
   3 checks).

3. **New item 2.28 added.** Generative entity persistence (CONCEPT
   ONLY). Emergent NPCs, locations, and facts promoted from prose to
   persistent world state via reconciliation step extension. Evaluate
   need after Milestone 1 playtesting.

4. **Item 2.25 revised.** Renamed from "Multiple save slots / campaign
   management UI" to "Character-centric campaign management." Data
   model changed: character is primary entity, campaigns are chapters.
   Aligns with Vision §8 and cross-era import design (GM §20).

5. **Items 4.0a and 4.0d expanded.** Design approaches documented for
   saga layer test artifacts and persona pool curation.

6. **Alignment Notes 7, 8 added.** Phase 8 dependency gap (requires
   Build Roadmap fix). Character-centric management principle (consider
   Vision Document update).

7. **Document Status Summary updated.** Design Gap Analysis added.
   Build Roadmap and LLM Evaluation flagged as NEEDS UPDATE.
   CS Design corrected to v1.3, CS Implementation to v1.2.

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
   and CLAUDE_CODE_INITIAL_PROMPT.md (now in `docs/reference/`).

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

*Storyteller V3 — Comprehensive Project Backlog v3.1*
*Everything planned. Nothing floating.*
