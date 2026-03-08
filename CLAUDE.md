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
  (OpenAI, OpenRouter, or any OpenAI-compatible endpoint)
- SQLite with WAL mode
- Pydantic v2 for all data models
- Single-file HTML frontend

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

10. **`docs/STORYTELLER_V3_DEFERRED_DESIGN_AND_LOGIC_ANALYSIS.md`** —
    System logic walkthrough verifying all data flows, integration
    points, invariants, and token budgets. Reference during
    implementation to understand how components connect.

11. **`docs/STORYTELLER_V3_DESIGN_GAP_ANALYSIS_V2.md`** — Full design
    specifications for every item across the project not covered in
    Game Mechanics or Implementation. Reference when implementing any
    post-V1 item. v2.0 is the only current source — v1.1 is
    superseded.

**Orientation and audit documents:**

12. **`docs/00_PROJECT_GUIDE.md`** — Front-door orientation. Document
    authority map, reading orders, current project state, key
    invariants, quick-reference lookup.

13. **`docs/PROJECT_STATE_MATRIX.md`** — Single-page view of every
    capability: what's promised, designed, V1-scoped, and deferred.

**Validation and quality specs (post-V1 reference):**

14. **`docs/CHOICE_QUALITY_VALIDATION_SPEC.md`** — Post-generation
    choice quality validator. Rubric, local model evaluator, retry
    integration. Activates late Phase 3 or Phase 7 based on
    calibration.

15. **`docs/PROLOGUE_INFERENCE_SPEC.md`** — Robustness rules for the
    psychometric prologue: contradiction handling, confidence scoring,
    anti-gaming, fallback behavior, scene library diversity. Phase 18.

16. **`docs/IMPORT_PACKAGE_QUALITY_SPEC.md`** — Quality standards for
    narrative compression in cross-campaign character transfer:
    relationship summaries, throughline history, voice notes, memory
    shards. Phase 19.

**Additional documents (generated during development):**

17. **`docs/PHASE_18_IMPLEMENTATION_PLAN.md`** — Implementation plan
    for the psychometric prologue (Phase 18).

18. **`docs/CLAUDE_CODE_INITIAL_PROMPT.md`** — Post-milestone
    documentation sync prompt (this audit task).

19. **`docs/prose_quality_review_session_1.md`** — Prose quality
    review notes from playtesting session.

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

**Next work:** Phase 18 (Psychometric Prologue) or Phases 20-22.

## Repo Structure

```
storyteller-v3/
├── CLAUDE.md              ← you are here
├── pyproject.toml
├── .env.example
├── docs/                  # All project documentation
│   ├── 00_PROJECT_GUIDE.md                     # Start here — orientation
│   ├── PROJECT_STATE_MATRIX.md                 # What's promised/designed/built
│   ├── STORYTELLER_V3_IMPLEMENTATION.md        # Primary spec
│   ├── STORYTELLER_V3_BUILD_ROADMAP.md         # Phase plan
│   ├── STORYTELLER_V3_GAME_MECHANICS.md        # Game design
│   ├── STORYTELLER_V3_VISION.md                # Creative vision
│   ├── STORYTELLER_V3_CAMPAIGN_STUDIO.md       # Studio design
│   ├── STORYTELLER_V3_CAMPAIGN_STUDIO_IMPLEMENTATION.md
│   ├── STORYTELLER_V3_LLM_EVALUATION.md
│   ├── STORYTELLER_V3_RESEARCH_CATALOGUE.md
│   ├── STORYTELLER_V3_DEFERRED_DESIGN_AND_LOGIC_ANALYSIS.md
│   ├── STORYTELLER_V3_DESIGN_GAP_ANALYSIS_V2.md
│   ├── STORYTELLER_V3_BACKLOG.md
│   ├── CHOICE_QUALITY_VALIDATION_SPEC.md       # Post-V1 quality spec
│   ├── PROLOGUE_INFERENCE_SPEC.md              # Post-V1 robustness spec
│   ├── IMPORT_PACKAGE_QUALITY_SPEC.md          # Post-V1 quality spec
│   ├── PHASE_18_IMPLEMENTATION_PLAN.md         # Phase 18 plan
│   ├── CLAUDE_CODE_INITIAL_PROMPT.md           # Doc sync prompt
│   └── prose_quality_review_session_1.md       # Playtest notes
├── engine/                # Pure Python — dice, character, checks
│   ├── dice.py            # FFG dice system (Phase 1)
│   ├── character.py       # Character model (Phase 1)
│   ├── checks.py          # 6-stage pool pipeline (Phase 1)
│   ├── equipment.py       # Loadout system (Phase 9)
│   ├── advancement.py     # XP and behavioral inference (Phase 10)
│   ├── talents.py         # Talent tree engine (Phase 11)
│   ├── destiny.py         # Destiny Point pool (Phase 11.5)
│   ├── reconciliation.py  # Post-turn reconciliation (Phase 7/13)
│   ├── force.py           # Force dice and powers (Phase 14-15)
│   ├── vehicle.py         # Vehicle/starship system (Phase 16)
│   └── time_skip.py       # Time skip vignettes (Phase 17)
├── gm/                    # LLM orchestration — local + cloud GM
│   ├── local_gm.py        # Check decisions, annotations, diagnostics
│   ├── cloud_gm.py        # Narration, milestones, time skips
│   ├── context.py         # Context package assembly
│   └── prompts/           # Prompt templates
│       ├── check_decision.txt
│       ├── narration.txt
│       ├── choice_annotation.txt
│       ├── reconciliation.txt
│       ├── milestone_reflection.txt
│       ├── force_power_milestone.txt
│       ├── time_skip_opening.txt
│       └── time_skip_closing.txt
├── state/                 # SQLite persistence
│   ├── db.py              # Database schema and connections
│   ├── session.py         # Turn logging and state queries
│   └── memory.py          # Episodic compression
├── api/                   # FastAPI routes
│   ├── main.py            # App bootstrap and frontend serving
│   ├── game_routes.py     # Game Engine routes
│   └── studio_routes.py   # Campaign Studio routes
├── web/                   # Single-file frontend
│   └── index.html
├── studio/                # Campaign Studio
│   ├── schema.py          # Spine schema — interface contract
│   ├── validate.py        # Four-gate validation suite
│   ├── generate.py        # Modes 1, 2, 3 generation
│   ├── seeding.py         # Deterministic seed derivation
│   ├── difficulty.py      # Spine difficulty calibration
│   ├── import_interface.py # Cross-era character import
│   ├── prompts/           # Studio prompt templates
│   │   ├── mode1_generate.txt
│   │   ├── mode2_generate.txt
│   │   ├── mode3_assist.txt
│   │   └── npc_voice_gen.txt
│   └── saga/              # Saga layer pipeline (CS-4)
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
│   ├── personas/          # writer_room_personas.json (55 personas)
│   ├── evaluation_pairs/  # Pairwise comparison training data
│   └── canon_profiles/    # Phase 21: canon character profiles (not yet populated)
└── tests/                 # 17 test files covering Phases 1-17 + Studio
```

Game Engine scope: `engine/`, `gm/`, `state/`, `api/game_routes.py`,
`web/`. Do not modify `studio/` when working on the Game Engine
(except importing from `studio/schema.py` for spine loading).
