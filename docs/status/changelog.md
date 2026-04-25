# Changelog

All notable changes to Storyteller V3 are documented here.

## [Unreleased] — 2026-04-25

### Audit-finding closures (architecture pivot follow-up)

- **Opening-route era_voice gap closed.** `POST /session` was constructing
  the very first `ContextPackage` without calling `_compute_dynamic_context_fields`,
  so the opening narration of every campaign lost its `era_voice_block`
  (period anchoring) and ran with empty defaults. Fixed at
  `api/game_routes.py:608`.
- **Selective reconciliation escalation.** New `reconcile_turn_with_escalation`
  in `engine/reconciliation.py` plus an `is_silent_reconciliation` predicate.
  When the fast tier returns no NPC updates, no thread movement, and no
  reputation event for two consecutive turns, the engine reruns through the
  quality tier and emits a `reconciliation_escalated` telemetry event. The
  quality result wins if it found anything; otherwise the streak counter
  resets. Wired at all 4 turn-handler ContextPackage construction sites.
- **Identity drift surfacing policy.** New `compute_identity_drift_cue` and
  `update_drift_baseline` helpers in `gm/context.py`. Tracks morality /
  conflict / motivation-activation deltas against a per-session baseline
  and surfaces a one-line interior cue when thresholds are crossed
  (5-point morality, 3-point conflict, or fresh obligation/duty activation).
  5-turn cooldown to keep cues sparse. New `{identity_drift_block}`
  placeholder in `narration.txt` + `narration_literary.txt`.
- **Introspection trigger logic.** New `compute_introspection_trigger`
  in `gm/context.py`. Three explicit conditions: post-Despair, post-pinch
  point, mid-act dry spell. Replaces the implicit-in-prompts behavior with
  testable signal logic. New `{introspection_trigger_block}` placeholder
  in narration prompts. Wired through the four turn handlers' new
  `_post_narration_drift_hook`.
- **Path differentiation audit (backlog 3.33 / 3.34).** Added eight
  pure-Python checks to `studio/validate.py`:
  - **Gate 1 (3.33):** integration layer completeness, NPC override
    validity (must reference roster), anchor adaptation coverage,
    entry point distinctness (Jaccard < 0.7), personal stakes
    non-genericity (heuristic phrase blocklist).
  - **Gate 3 (3.34):** allegiance NPC override diversity, anchor
    adaptation similarity (Jaccard < 0.65), entry point structural
    difference (Jaccard < 0.55).
  - Helper `_jaccard_token_similarity` with stopword filtering.
- **CS-6 runtime wiring (newly discovered gap).** During the audit pass we
  found that several CS-6 features were documented as "complete" but had
  unit tests only — they were never invoked from the live turn loop in
  `api/game_routes.py`. Wired now:
  - **Pinch point firing** (`compute_pinch_point_instruction`) — every
    turn checks the act's `pinch_point` config against current progress
    and fires once per act when the target threshold is reached. Reset
    on act boundary in `run_between_act_pipeline`.
  - **Depth card block** (`build_depth_card_block`) — looks up the
    active variant's `CharacterDepthCard` from the spine and renders
    GM-only enrichment (inner demon, secret yearning, social mask, etc.)
    into the narration prompt.
  - **Voice mode mapping** (`compute_voice_mode_instruction`) — captures
    the previous turn's `dramatic_mission.selected_mission` from the
    reconciliation result, maps it through `MISSION_TO_VOICE` to a voice
    mode, and injects the corresponding `VOICE_INSTRUCTIONS` snippet
    into the next turn's narration prompt.
  - Session creation now persists `variant_id` in `arc_state` so later
    turns can resolve the active character variant.
  - Per-act state resets (`pinch_point_fired`, consecutive-zero counters)
    added to the between-act pipeline.
- **Test coverage.** 51 new tests across four files
  (`test_reconciliation_escalation.py`, `test_identity_drift_introspection.py`,
  `test_path_differentiation_audit.py`, `test_cs6_runtime_wiring.py`).
  Total: 704 pass + 12 skip + 0 fail.

### Still deferred (CS-6 wiring, partial)

The same audit found three CS-6 features that remain unwired into the
turn loop and are NOT included in this pass — each requires more design
work than a quick wrap:
- **Closure heartbeat** (`check_closure_heartbeat`) — needs accurate
  per-thread last-change tracking, which the current arc_state doesn't
  carry per-thread.
- **Foreshadow setup/payoff tracking** (`ForeshadowLink`) — requires a
  setup-delivery detector and a payoff trigger, both of which need
  spine-side authoring and runtime state.
- **Contradiction arc accumulation** — reconciliation already returns
  the per-turn signal (`contradiction_tracking`), but no runtime code
  accumulates it into a turn-to-turn `contradiction_arc_block` for the
  GM. Needs a multi-turn aggregator.
- **Doc sync.** `state-matrix.md` v1.6 → v1.7 with new Infrastructure
  section, reputation/behavioral/era-voice rows updated to ✓ Built,
  selective-escalation row added. `architecture-pivot.md` test count
  corrected to actual numbers.

### Architecture pivot — Local-first → DeepSeek V4
- Unified LLM client (`gm/llm_client.py`) with two-tier routing (fast/quality)
  and OpenRouter as the primary provider. DeepSeek V4 Flash is the default
  fast tier; DeepSeek V4 Pro is the default quality tier. Ollama remains as
  an optional offline path.
- Provider/model capability layer encodes reasoning syntax differences
  (OpenAI `reasoning_effort` vs OpenRouter `extra_body.reasoning`).
  OpenRouter `require_parameters: true` and `data_collection: deny`
  enforced by default.
- Strict `json_schema` response_format for studio JSON calls, with
  automatic fallback to `json_object` if a provider rejects it.
- `/health` endpoint surfaces the active routing config.

### Reputation echo, behavioral availability, era voice — wired end-to-end
- Reputation echo system fully wired: reconciliation captures
  `reputation_event` + `faction_tags`, the engine writes to
  `reputation_log`, eligible entries surface in narration with a 3-turn
  cooldown.
- Behavioral availability signal derived from Phase 13 annotation history
  injects choice-weighting guidance into narration.
- `EraVoice` schema field added to `CampaignSpine`; the active campaign
  populates it with New Republic / Praxeum-era anchoring.

### Campaign repository narrowed to Shadows of the Praxeum
- Deleted: `data/campaigns/nar_shaddaa_job.json`,
  `data/campaigns/echoes_of_the_force.json`,
  `data/characters/keth_varso.json`, `data/characters/talia_ren.json`.
- Materialized: `data/characters/praxeum_student.json` and
  `praxeum_mechanic.json` from the Praxeum spine variants so existing
  test fixtures still load a standalone character file.
- Tests, eval scenarios, and docs updated to reference the canonical
  Praxeum campaign. Tests that exercised Nar-Shaddaa-specific
  features (time skip vignettes) now skip cleanly when the active
  campaign doesn't carry that data — the engine-level behavior is
  still covered by synthetic-fixture tests.

## [0.1.0] — 2026-04-08

Initial public version. All Game Engine milestones 0-3 complete,
Campaign Studio CS-1 through CS-6 complete.

### Game Engine — V1 Core (Phases 1-6)

- **Phase 1:** FFG dice system with all 7 die types, character model
  (Pydantic, 33 skills), 6-stage pool construction pipeline
- **Phase 2:** Local GM via Ollama — structured JSON check decisions
- **Phase 3:** Cloud GM — prose narration (250-800 words), 2-4
  choices, NPC state cards, context package assembly
- **Phase 4:** SQLite persistence with WAL mode, turn logging,
  episodic memory compression
- **Phase 5:** FastAPI routes — session creation, turn handling,
  SSE streaming
- **Phase 6:** Single-file HTML prose reader UI

### Game Engine — Milestone 1: Full Campaign (Phases 7-13)

- **Phase 7:** Post-turn reconciliation, act boundary detection,
  pacing arc system
- **Phase 8:** Motivation tracks (Obligation, Duty, Morality) with
  trigger systems and between-act processing
- **Phase 8.5:** NPC emotional state system
- **Phase 9:** Equipment and loadout system (weapons, armor, tools)
- **Phase 10:** XP earning and behavioral inference engine
- **Phase 11:** Talent tree engine (5-type taxonomy, 6 specializations)
- **Phase 11.5:** Destiny Point pool (light/dark spending)
- **Phase 12:** Milestone reflections and talent acquisition
- **Phase 13:** Semantic memory, choice annotation, prose diagnostics

### Game Engine — Milestone 2: Force (Phases 14-15.5)

- **Phase 14:** Force dice resolution, dark side temptation,
  conflict tracking
- **Phase 15:** Force powers (enhance, heal/harm, influence, move,
  sense) with narrative-tagged choices
- **Phase 15.5:** Force and Destiny specialization trees

### Game Engine — Milestone 3: Vehicles (Phase 16)

- **Phase 16:** Vehicle and starship encounter system

### Game Engine — Milestone 4 Partial (Phase 17)

- **Phase 17:** Time skip vignettes (authored between-era scenes)

### Campaign Studio — CS-1 through CS-4 (March 2026)

- **CS-1:** Pydantic spine schema, 4-gate validation suite
  (schema contract, NPC coherence, relationship network, narrative
  consistency)
- **CS-2:** Mode 3 collaborative authoring, NPC voice generation,
  deterministic seeding, difficulty calibration, studio API routes
- **CS-3:** Mode 2 thematic steering, cross-era character import
  interface
- **CS-4:** 5-stage saga pipeline (Writer's Room), Mode 1 autonomous
  generation, 55-persona pool across 11 clusters

### Campaign Studio — CS-5: Narrative Quality (April 2026)

- Pre-generation story architecture planning (`studio/architect.py`)
- Gate 4 narrative evaluation: coherence, dramatic quality,
  anti-genericity (`studio/narrative_eval.py`)
- Narrative quality scoring (0.0-1.0 normalized)
- StoryArchitecture schema model with five pressure types
- Anti-default rules preventing generic "hero vs villain" architectures

### Campaign Studio — CS-6: Story Engineering (April 2026)

- Dramatic mission classification with 14 mission types across
  Brooks's four-part model (`engine/dramatic_mission.py`)
- Scene purpose validation with 5-dimension scoring
  (`engine/scene_validator.py`)
- MilestoneBeatSheet, PinchPoint, ForeshadowLink, CharacterDepthCard,
  ProtagonistMode schema models
- NPC pressure roles (9 types)
- Deterministic structural validation checks
- Voice mode prose guidance system
- Shadows of the Praxeum campaign

### Quality and Evaluation (April 2026)

- Narrative telemetry event system (`state/telemetry.py`)
- Evaluation harness with golden scenarios and automated policies
- Quality metrics (Tier 1 heuristic + Tier 2 LLM-assisted)
- Cross-session divergence analysis
- Prose voice evaluation benchmarking

### Documentation (March-April 2026)

- 15 active documentation files across four tiers
- 6 archived reference documents
- Four-tier document architecture with authority resolution rules
- Comprehensive project guide and state matrix

### Content

- **The Nar Shaddaa Job** — smuggler campaign (Keth Varso)
- **Echoes of the Force** — Force-sensitive campaign (Talia Ren)
- **Shadows of the Praxeum** — Jedi academy campaign
- 6 talent specialization trees, 5 Force powers, 55 Writer's Room
  personas
