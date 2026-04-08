# Changelog

All notable changes to Storyteller V3 are documented here.

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
