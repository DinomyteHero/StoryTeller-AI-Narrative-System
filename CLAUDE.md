# Storyteller V3

## What This Is

An LLM-powered Star Wars narrative RPG engine using the FFG (Fantasy
Flight Games) Edge of the Empire / Age of Rebellion / Force and Destiny
dice system. The player reads prose passages, makes choices, and the
story responds — mechanically real (dice determine outcomes) and
narratively generative (an LLM writes the prose). Think "Choice of
Games meets tabletop RPG meets AI Game Master."

## Architecture

Two independent systems sharing one repo:

- **Game Engine** — the runtime. Consumes a campaign spine JSON and
  plays it. Player-facing. Latency-sensitive. One cloud LLM call per
  turn maximum.
- **Campaign Studio** — the authoring tool. Produces campaign spine
  JSON. Author-facing. Multi-pass, no latency pressure. Built in
  parallel with Game Engine post-V1 milestones (CS-1 through CS-4
  complete).

The campaign spine JSON is the interface contract between them.

## Tech Stack

- Python 3.11+, FastAPI + Uvicorn
- Local LLM: Ollama with Qwen3.5:9B (check decisions, structured JSON)
- Cloud LLM: OpenAI-compatible SDK, provider-configurable via env vars
  (OpenAI, OpenRouter, or any OpenAI-compatible endpoint). Code
  defaults to `gpt-5.2`; configure via `CLOUD_MODEL` env var.
- SQLite with WAL mode
- Pydantic v2 for all data models
- Single-file HTML frontend
- NetworkX (optional, for Campaign Studio graph validation)

## Documentation

All project documents live in `docs/`. For full orientation —
authority map, reading order, current project state, and navigation —
start with `docs/00_PROJECT_GUIDE.md`.

**For implementation, read in this order:**

1. **`docs/STORYTELLER_V3_IMPLEMENTATION.md`** — THE PRIMARY SPEC.
   Complete code-level specification for the Game Engine. V1 build
   phases 1-6 with file-by-file code. Read this entire document before
   writing any code. All code in this document has been carefully
   designed and reviewed — implement it as specified.

2. **`docs/STORYTELLER_V3_BUILD_ROADMAP.md`** — Phased build plan from
   V1 through the finished product (Milestones 0-4). Each phase has
   files, goals, dependencies, and success criteria. After V1, follow
   this.

3. **`docs/STORYTELLER_V3_GAME_MECHANICS.md`** — 27 sections of game
   design (§0-§26). Sections 0-19 and §23-§26 cover implemented
   systems (Milestones 0-3 plus time skips). Sections 20-22 cover
   systems not yet built (large-scale NPC management, canon character
   profiles, Force discovery). Reference as needed during
   implementation.

4. **`docs/STORYTELLER_V3_VISION.md`** — Creative vision. What the
   game should feel like. Read for context, not for implementation
   detail.

**Reference documents (consult when needed):**

5. **`docs/STORYTELLER_V3_CAMPAIGN_STUDIO_IMPLEMENTATION.md`** —
   Campaign Studio code spec. Contains the Pydantic spine schema
   (`studio/schema.py`) which is the interface contract. Relevant to
   Game Engine because the engine loads spines against this schema.

6. **`docs/STORYTELLER_V3_LLM_EVALUATION.md`** — Model selection
   criteria and compliance tests. Reference when configuring LLM
   providers.

7. **`docs/STORYTELLER_V3_CAMPAIGN_STUDIO.md`** — Campaign Studio
   design. Post-V1 reference.

8. **`docs/STORYTELLER_V3_RESEARCH_CATALOGUE.md`** — Research evidence
   basis. Background reading only.

9. **`docs/STORYTELLER_V3_BACKLOG.md`** — Complete item tracker.
   Reference for status of any feature.

**Orientation and audit documents:**

10. **`docs/00_PROJECT_GUIDE.md`** — Front-door orientation. Document
    authority map (four-tier architecture), reading orders, key
    invariants, quick-reference lookup.

11. **`docs/PROJECT_STATE_MATRIX.md`** — Single-page view of every
    capability: what's promised, designed, V1-scoped, and deferred.

**Specialist specs (consult when implementing the relevant phase):**

12. **`docs/CHOICE_QUALITY_VALIDATION_SPEC.md`** — Post-generation
    choice quality validator. Rubric, local model evaluator, retry
    integration. Activates late Phase 3 or Phase 7 based on
    calibration.

13. **`docs/PROLOGUE_SYSTEM_SPEC.md`** — Psychometric prologue: design
    robustness (contradictions, confidence, anti-gaming) +
    implementation plan. Phase 18.

14. **`docs/IMPORT_PACKAGE_QUALITY_SPEC.md`** — Quality standards for
    narrative compression in cross-campaign character transfer. Phase 19.

15. **`docs/STORY_ARCHITECTURE_SPEC.md`** — Story architecture
    vocabulary, quality rubrics, and Gate 4 evaluation design (CS-5).

**Reference archive (`docs/reference/`):**

16. **`docs/reference/STORYTELLER_V3_DESIGN_GAP_ANALYSIS_V2.md`** —
    Archived: design specs for 9 items, all applied to canonical docs.

17. **`docs/reference/STORYTELLER_V3_DEFERRED_DESIGN_AND_LOGIC_ANALYSIS.md`** —
    Archived: system logic walkthrough. Section 4 remains useful for
    architecture reference.

18. **`docs/reference/CLAUDE_CODE_INITIAL_PROMPT.md`** — Archived:
    superseded by this CLAUDE.md file.

19. **`docs/reference/prose_quality_review_session_1.md`** — Archived:
    playtest transcript for prose quality benchmarking.

## The Rule That Overrides Everything

> Do not build the second thing until the first thing works.

V2 of this project failed by building infrastructure before validating
the core loop. V3 exists to correct that. If you want to add something
not in the current phase — stop. Add it to the backlog. Finish the
phase you are in.

## V1 Build Phases — Strict Order

### Phase 1: The Engine (Pure Python)
Files: `engine/dice.py`, `engine/character.py`, `engine/checks.py`
No LLM. No database. No API. Just Python.
Goal: Roll a dice pool for Keth's Deception check and get correct FFG results.
**Start here. This is the most important file in the project.**

### Phase 2: The Local GM
Files: `gm/local_gm.py`, `gm/prompts/check_decision.txt`
Goal: Given a scene and player action, return structured JSON check decision.

### Phase 3: The Cloud GM
Files: `gm/cloud_gm.py`, `gm/context.py`, `gm/prompts/narration.txt`
Goal: Given context + dice result, produce 250-600 word passage + 2-4 choices.

### Phase 4: State and Persistence
Files: `state/db.py`, `state/session.py`, `state/memory.py`
Goal: Session persists across process restarts. Turn history compresses.

### Phase 5: API
Files: `api/main.py`, `api/game_routes.py`
Goal: Three working routes. Full loop accessible via HTTP.
The turn handler (§9.1) and session creation (§9.2) orchestration flows
are fully specified — implement them as written.

### Phase 6: Frontend
Files: `web/index.html`
Goal: Readable prose UI. Choices as buttons. Dice panel expandable.

**Do not start Phase 2 until Phase 1 produces correct dice results.**
**Do not start Phase 3 until Phase 2 produces valid JSON reliably.**
And so on. The full code spec for each phase is in the Implementation doc.

## V1 Success Criteria

V1 is complete when all 12 pass:
1. Player starts as Keth Varso
2. Opening passage of The Nar Shaddaa Job appears
3. Player selects a choice
4. Local model correctly decides check/no-check
5. Dice pool built correctly per FFG rules
6. Dice rolled with correct symbols
7. Cloud GM narrates honoring the dice result
8. Dice panel shows actual roll on demand
9. New choices are scene-specific
10. Loop repeats 5+ turns without errors
11. Session persists across restart
12. `NARRATIVE_BACKEND=local` runs full loop without cloud credits

## Critical Rules

**Rule 3:** `engine/` is pure Python. Zero LLM dependencies. Runnable
with no API keys and no Ollama.

**Rule 4:** The dice are the truth. Failure is narrated as failure.
Triumph is narrated as triumph. No softening.

**Rule 5:** Fail loud. Garbage JSON after 3 retries = exception.
Missing `---CHOICES---` = exception. Surface errors.

**Rule 11:** V1 must not block post-V1 mechanics. Four constraints:
- (a) Dice engine must be data-driven (symbol tables, not hardcoded
  success/failure assumptions). Force dice already in tables.
- (b) Character schema field reservations — do not remove `force_rating`,
  `force_committed`, `total_xp`, `available_xp`, `specializations`.
  Do not assume reserved post-V1 fields don't exist.
- (c) Context assembly must be composable — optional fields that default
  to empty strings and are omitted when empty. Not monolithic string
  concatenation.
- (d) Pool modification in `build_pool()` must be a sequential pipeline
  with insertable stages, not a single function.

**Physics-before-imagination invariant:** Code resolves all mechanical
outcomes (dice, state transitions, NPC disposition changes) BEFORE the
narrative model receives the context. The LLM describes outcomes code
has already determined. It never decides them.

## Post-V1 Milestones — Current Status

Follow `docs/STORYTELLER_V3_BUILD_ROADMAP.md`. Four milestones:
- Milestone 1: Full single-campaign experience (Phases 7-13) — **COMPLETE**
- Milestone 2: Force-sensitive campaigns (Phases 14-15.5) — **COMPLETE**
- Milestone 3: Vehicles and space (Phase 16) — **COMPLETE**
- Milestone 4: Multi-campaign saga (Phases 17-22) — **PARTIAL**
  - Phase 17 (Time Skip Vignettes): COMPLETE
  - Phases 18-22: NOT STARTED

Campaign Studio (parallel track):
- CS-1 (Schema & Validation): COMPLETE
- CS-2 (Mode 3 Collaborative Authoring): COMPLETE
- CS-3 (Mode 2 Thematic Steering + Import): COMPLETE
- CS-4 (Saga Layer + Mode 1): COMPLETE
- CS-5 (Narrative Quality): COMPLETE
  - StoryArchitecture model + pre-generation planning layer
  - Gate 4 narrative evaluation (coherence, dramatic quality, anti-genericity)
  - Enhanced generation prompts with architectural vocabulary
  - Stage 5 LLM-based narrative quality scoring

**Next work:** CS-6 (Saga Depth) or Phase 18 (Psychometric Prologue).

## Codebase Metrics (as of April 3, 2026)

- ~15,700 lines of application code (Python + HTML)
- ~9,000 lines of test code across 17 test files
- 15 active documentation files in `docs/` + 4 archived in `docs/reference/`
- 2 campaign spines, 2 characters, 6 talent trees, 5 Force powers

## Repo Structure

```
storyteller-v3/
├── CLAUDE.md              ← you are here
├── README.md              # Project overview and getting started
├── pyproject.toml
├── .env.example
├── docs/                  # Project documentation (15 active + 4 archived)
│   ├── 00_PROJECT_GUIDE.md                     # Start here — orientation
│   ├── PROJECT_STATE_MATRIX.md                 # What's promised/designed/built
│   ├── STORYTELLER_V3_IMPLEMENTATION.md        # Primary spec — Game Engine
│   ├── STORYTELLER_V3_BUILD_ROADMAP.md         # Phase plan
│   ├── STORYTELLER_V3_GAME_MECHANICS.md        # Game design (27 sections)
│   ├── STORYTELLER_V3_VISION.md                # Creative vision
│   ├── STORYTELLER_V3_CAMPAIGN_STUDIO.md       # Studio design
│   ├── STORYTELLER_V3_CAMPAIGN_STUDIO_IMPLEMENTATION.md  # Studio code spec
│   ├── STORYTELLER_V3_LLM_EVALUATION.md        # Model selection
│   ├── STORYTELLER_V3_RESEARCH_CATALOGUE.md    # Research evidence
│   ├── STORYTELLER_V3_BACKLOG.md               # Item tracker (source of truth)
│   ├── CHOICE_QUALITY_VALIDATION_SPEC.md       # Specialist: choice quality
│   ├── PROLOGUE_SYSTEM_SPEC.md                 # Specialist: prologue (Phase 18)
│   ├── IMPORT_PACKAGE_QUALITY_SPEC.md          # Specialist: import quality
│   ├── STORY_ARCHITECTURE_SPEC.md              # Specialist: CS-5 narrative quality
│   └── reference/                              # Archived/reference-only
│       ├── README.md
│       ├── STORYTELLER_V3_DESIGN_GAP_ANALYSIS_V2.md
│       ├── STORYTELLER_V3_DEFERRED_DESIGN_AND_LOGIC_ANALYSIS.md
│       ├── CLAUDE_CODE_INITIAL_PROMPT.md
│       └── prose_quality_review_session_1.md
├── engine/                # Pure Python — dice, character, checks (5,106 lines)
│   ├── dice.py            # FFG dice system — 7 die types, symbol tables (270 lines)
│   ├── character.py       # Character model — Pydantic, 33 skills (220 lines)
│   ├── checks.py          # 6-stage pool pipeline (197 lines)
│   ├── equipment.py       # Loadout system — weapons, armor, tools (287 lines)
│   ├── advancement.py     # XP and behavioral inference (462 lines)
│   ├── talents.py         # Talent tree engine — 5-type taxonomy (797 lines)
│   ├── destiny.py         # Destiny Point pool — light/dark spending (275 lines)
│   ├── reconciliation.py  # Post-turn reconciliation + 16-step pipeline (952 lines)
│   ├── force.py           # Force dice, powers, temptation (732 lines)
│   ├── vehicle.py         # Vehicle/starship system (303 lines)
│   └── time_skip.py       # Time skip vignettes (611 lines)
├── gm/                    # LLM orchestration — local + cloud GM (1,805 lines)
│   ├── local_gm.py        # Check decisions, annotations, diagnostics (478 lines)
│   ├── cloud_gm.py        # Narration, milestones, time skips (946 lines)
│   ├── context.py         # Context package assembly (381 lines)
│   └── prompts/           # Prompt templates (8 files)
│       ├── check_decision.txt
│       ├── narration.txt
│       ├── choice_annotation.txt
│       ├── reconciliation.txt
│       ├── milestone_reflection.txt
│       ├── force_power_milestone.txt
│       ├── time_skip_opening.txt
│       └── time_skip_closing.txt
├── state/                 # SQLite persistence (547 lines)
│   ├── db.py              # Database schema and connections (183 lines)
│   ├── session.py         # Turn logging and state queries (244 lines)
│   └── memory.py          # Episodic compression (120 lines)
├── api/                   # FastAPI routes (3,253 lines)
│   ├── main.py            # App bootstrap and frontend serving (71 lines)
│   ├── game_routes.py     # Game Engine routes (2,685 lines)
│   └── studio_routes.py   # Campaign Studio routes (497 lines)
├── web/                   # Single-file frontend
│   └── index.html         # Prose reader UI (788 lines)
├── studio/                # Campaign Studio (~4,200 lines)
│   ├── schema.py          # Spine schema — interface contract (~570 lines)
│   ├── validate.py        # Four-gate validation suite (~500 lines)
│   ├── generate.py        # Modes 1, 2, 3 generation (~750 lines)
│   ├── architect.py       # Pre-generation story architecture (CS-5)
│   ├── narrative_eval.py  # Gate 4 narrative evaluation (CS-5)
│   ├── seeding.py         # Deterministic seed derivation (111 lines)
│   ├── difficulty.py      # Spine difficulty calibration (353 lines)
│   ├── import_interface.py # Cross-era character import (404 lines)
│   ├── prompts/           # Studio prompt templates (7 files)
│   │   ├── mode1_generate.txt
│   │   ├── mode2_generate.txt
│   │   ├── mode3_assist.txt
│   │   ├── npc_voice_gen.txt
│   │   ├── architect.txt        # CS-5: architecture generation
│   │   ├── narrative_eval.txt   # CS-5: Gate 4 evaluation
│   │   └── narrative_score.txt  # CS-5: Stage 5 scoring
│   └── saga/              # Saga layer pipeline — CS-4 (1,090 lines)
│       ├── pipeline.py    # 5-stage orchestrator
│       ├── personas.py    # Persona pool management
│       ├── diverge.py     # Stage 2: direction generation
│       ├── search.py      # Stage 3: sketch expansion
│       ├── converge.py    # Stage 4: debate and refinement
│       ├── select.py      # Stage 5: pairwise selection
│       ├── ensemble.py    # Multi-model writer assignment
│       └── evaluator.py   # Trained local evaluator
├── data/
│   ├── characters/        # keth_varso.json, talia_ren.json
│   ├── campaigns/         # nar_shaddaa_job.json, echoes_of_the_force.json
│   ├── talent_trees/      # 6 specialization trees + talent_library.json
│   ├── force_powers/      # 5 powers (enhance, heal_harm, influence, move, sense)
│   └── personas/          # writer_room_personas.json (55 personas)
└── tests/                 # 17 test files (~9,000 lines)
    ├── dice_validation.py
    ├── studio_schema_test.py
    ├── test_cs2_mode3.py
    ├── test_cs3_mode2_import.py
    ├── test_cs4_saga.py
    ├── test_cs5_narrative_quality.py  # CS-5: 33 tests
    ├── test_e2e_game_loop.py
    ├── test_phase10_advancement.py
    ├── test_phase115_destiny.py
    ├── test_phase11_talents.py
    ├── test_phase12_milestones.py
    ├── test_phase13_choice_quality.py
    ├── test_phase14_force.py
    ├── test_phase155_fd_trees.py
    ├── test_phase15_force_powers.py
    ├── test_phase16_vehicles.py
    └── test_phase17_time_skips.py
```

**Note:** `data/evaluation_pairs/` and `data/canon_profiles/` directories
are mentioned in design docs for future phases but do not yet exist in
the repo. They will be created when Phase 21 (canon profiles) and the
trained local evaluator (post-CS-4) are implemented.

**Documentation structure:** Active specs live in `docs/`. Archived
audit artifacts and historical references live in `docs/reference/`.
See `docs/00_PROJECT_GUIDE.md` for the four-tier document architecture.

Game Engine scope: `engine/`, `gm/`, `state/`, `api/game_routes.py`,
`web/`. Do not modify `studio/` when working on the Game Engine
(except importing from `studio/schema.py` for spine loading).
