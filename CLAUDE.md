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
  parallel with Game Engine post-V1 milestones (CS-1 through CS-6
  complete).

The campaign spine JSON is the interface contract between them.

## Tech Stack

- Python 3.11+, FastAPI + Uvicorn
- Cloud LLM only — no local model path. Two-tier routing through
  `gm/llm_client.py`:
  - **FAST** tier: DeepSeek V4 Flash via OpenRouter (default).
    Structured JSON: check decisions, annotations, reconciliation,
    prose diagnostic, scene validation.
  - **QUALITY** tier: DeepSeek V4 Pro via OpenRouter (default). Turn
    narration, milestone reflections, time-skip prose, studio gen.
  - Provider configurable via `CLOUD_PROVIDER=openrouter|openai`.
- SQLite with WAL mode
- Pydantic v2 for all data models
- Single-file HTML frontend
- NetworkX (optional, for Campaign Studio graph validation)

## Documentation

All project documents live in `docs/`, organized into tier-based
subdirectories. Start with `docs/index.md` for full orientation.

**For implementation, read in this order:**

1. **`docs/specs/engine-implementation.md`** — THE PRIMARY SPEC.
   Complete code-level specification for the Game Engine. V1 build
   phases 1-6 with file-by-file code. Read this entire document before
   writing any code.

2. **`docs/status/roadmap.md`** — Phased build plan from V1 through
   the finished product (Milestones 0-4). Each phase has files, goals,
   dependencies, and success criteria.

3. **`docs/specs/game-mechanics.md`** — 27 sections of game design
   (§0-§26). Sections 0-19 and §23-§26 cover implemented systems.
   Sections 20-22 cover systems not yet built. Reference as needed.

4. **`docs/specs/vision.md`** — Creative vision. What the game should
   feel like. Read for context, not for implementation detail.

**Reference documents (consult when needed):**

5. **`docs/specs/studio-implementation.md`** — Campaign Studio code
   spec (CS-1 through CS-6). Contains the Pydantic spine schema
   (`studio/schema.py`) which is the interface contract.

6. **`docs/research/llm-evaluation.md`** — Model selection criteria
   and compliance tests.

7. **`docs/specs/studio-design.md`** — Campaign Studio design.

8. **`docs/research/research-catalogue.md`** — Research evidence basis.

9. **`docs/status/backlog.md`** — Complete item tracker. Single source
   of truth for status of any feature.

**Orientation and audit documents:**

10. **`docs/index.md`** — Front-door orientation. Document authority
    map (four-tier architecture), reading orders, key invariants,
    quick-reference lookup.

11. **`docs/status/state-matrix.md`** — Single-page view of every
    capability: what's promised, designed, V1-scoped, and deferred.

**Specialist specs (consult when implementing the relevant phase):**

12. **`docs/specialist/choice-quality-validation.md`** — Post-generation
    choice quality validator. Rubric, local model evaluator, retry
    integration. Activates late Phase 3 or Phase 7.

13. **`docs/specialist/prologue-system.md`** — Psychometric prologue:
    design robustness + implementation plan. Phase 18.

14. **`docs/specialist/import-package-quality.md`** — Quality standards
    for narrative compression in cross-campaign transfer. Phase 19.

15. **`docs/specialist/story-architecture.md`** — Story architecture
    vocabulary, quality rubrics, and Gate 4 evaluation design (CS-5/CS-6).

**API reference:**

16. **`docs/api/game-engine-api.md`** — Game Engine HTTP endpoints.

17. **`docs/api/studio-api.md`** — Campaign Studio HTTP endpoints.

**Reference archive (`docs/reference/`):**

18. **`docs/reference/design-gap-analysis-v2.md`** — Archived: design
    specs for 9 items, all applied to canonical docs.

19. **`docs/reference/deferred-design-analysis.md`** — Archived:
    system logic walkthrough.

20. **`docs/reference/claude-code-initial-prompt.md`** — Archived:
    superseded by this CLAUDE.md file.

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

### Phase 2: The Fast GM
Files: `gm/fast_gm.py`, `gm/prompts/check_decision.txt`
Goal: Given a scene and player action, return structured JSON check decision
via the fast tier (DeepSeek V4 Flash by default). Historically named
"local GM" when an Ollama path existed; the local backend was removed
in May 2026 in favor of cloud-only routing.

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

V1 was completed in Q1 2026 against the canonical campaign (Shadows of
the Custodian) and an active protagonist roster. The original list
(12 criteria, including a now-deleted local-backend offline mode) is
preserved in [docs/reference/](docs/reference/) for historical context.
Current invariants live under "Critical Rules" below and in the
post-V1 milestone roadmap.

## Critical Rules

**Rule 3:** `engine/` is pure Python. Zero LLM dependencies. Runnable
with no API keys.

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

## Post-V1 Milestones — Current Status (last synced: 2026-05-02)

Follow `docs/status/roadmap.md`. Four milestones:
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
- CS-6 (Story Engineering Integration): COMPLETE
  - StoryArchitecture model + pre-generation planning layer
  - Gate 4 narrative evaluation (coherence, dramatic quality, anti-genericity)
  - Enhanced generation prompts with architectural vocabulary
  - Stage 5 LLM-based narrative quality scoring

**June 2026 passes (details in docs/status/changelog.md):**
- **Physics guardrails + cost pass** — world registry validation gate
  (`engine/world_registry.py`): LLM-proposed locations and facts must be
  grounded in spine canon, the visited-location ledger, or the delivered
  passage before entering persistent state; dice-polarity post-check
  enforces Rule 4; per-call token usage accounting; narration prompt
  split into a byte-stable system message for provider prefix caching;
  choice-quality failures repair choices only instead of regenerating
  full narration.
- **Experience shell** — campaigns end: completion state, generated
  epilogue keyed to `story_architecture.ending_paths`, finale UI;
  "story so far" recap on resume; incapacitation is mechanically real
  (incoming damage on failed dangerous-scene checks, §2 one-turn
  redirect, per-act escalation); CoG-style UI (stats panel, chapter
  indicator, destiny pool, milestone ceremony, always-visible freeform
  input).
- **Studio enrichment generation** — Mode 1/2 + architect now generate
  what previously required manual passes: per-act beat_roles, 6-12
  side_content seeds per act, foreshadow registry, ending paths,
  thematic arguments on major NPCs, antagonistic relationship pressure;
  all enforced by Gate 2/3/4 validation.
- **Character creator flow** — prose pitch → LLM draft → editable stats
  → save → on-demand campaign generation (`api/character_routes.py`,
  `gm/character_creator.py`, `studio/persist.py`,
  `POST /campaign/generate`).

**Next work:** Phase 18 (Psychometric Prologue), CS-7 (Saga Depth), or
the TurnContext refactor (collapse the four near-duplicate turn handlers
in `api/game_routes.py` around a shared context object).

## Codebase Metrics (as of June 9, 2026)

- ~29,200 lines of application code (Python + HTML)
- ~16,100 lines of test code across 39 test files
- 23 active documentation files in `docs/` + 6 archived in `docs/reference/`
- 1 authored campaign spine (Shadows of the Custodian) plus on-demand
  generated campaigns, 3 prebuilt characters plus player-created
  characters, 7 talent files (6 trees + library), 5 Force powers

## Repo Structure

```
storyteller-v3/
├── CLAUDE.md              ← you are here
├── README.md              # Project overview and getting started
├── pyproject.toml
├── .env.example
├── docs/                  # Project documentation (29 files across 6 subdirectories)
│   ├── index.md                               # Start here — orientation
│   ├── specs/                                 # Tier 1: Core specifications
│   │   ├── vision.md                          # Creative vision
│   │   ├── game-mechanics.md                  # Game design (27 sections)
│   │   ├── engine-implementation.md           # Primary spec — Game Engine
│   │   ├── studio-design.md                   # Campaign Studio design
│   │   └── studio-implementation.md           # Campaign Studio code spec (CS-1–CS-6)
│   ├── status/                                # Tier 2: Planning and tracking
│   │   ├── roadmap.md                         # Phase plan
│   │   ├── backlog.md                         # Item tracker (source of truth)
│   │   ├── state-matrix.md                    # Capability dashboard
│   │   ├── architecture-pivot.md              # Architecture pivot notes
│   │   └── changelog.md                       # Release history
│   ├── research/                              # Tier 3: Research and evaluation
│   │   ├── llm-evaluation.md                  # Model selection
│   │   ├── research-catalogue.md              # Research evidence
│   │   ├── brooks-weiland-pass-2026-04.md     # Narrative pass review
│   │   └── depth-pass-stress-test-2026-04.md  # Depth pass stress test
│   ├── specialist/                            # Tier 4: Specialist specs
│   │   ├── choice-quality-validation.md       # Choice quality (Phase 7)
│   │   ├── prologue-system.md                 # Prologue system (Phase 18)
│   │   ├── import-package-quality.md          # Import quality (Phase 19)
│   │   ├── content-packs.md                   # Content pack system
│   │   ├── era-packs.md                       # Era pack design
│   │   └── story-architecture.md              # Story architecture (CS-5/CS-6)
│   ├── api/                                   # API reference
│   │   ├── game-engine-api.md                 # Game Engine endpoints
│   │   └── studio-api.md                      # Campaign Studio endpoints
│   └── reference/                             # Archived/reference-only
│       ├── README.md
│       ├── design-gap-analysis-v2.md
│       ├── deferred-design-analysis.md
│       ├── consolidation-report.md
│       ├── claude-code-initial-prompt.md
│       └── prose-quality-review-1.md
├── engine/                # Pure Python — dice, character, checks
│   ├── dice.py            # FFG dice system — 7 die types, symbol tables
│   ├── character.py       # Character model — Pydantic, 33 skills
│   ├── checks.py          # 6-stage pool pipeline + incoming damage (§2)
│   ├── equipment.py       # Loadout system — weapons, armor, tools
│   ├── advancement.py     # XP and behavioral inference
│   ├── talents.py         # Talent tree engine — 5-type taxonomy + freeform talents
│   ├── destiny.py         # Destiny Point pool — light/dark spending
│   ├── reconciliation.py  # Post-turn reconciliation + 16-step pipeline + completion
│   ├── force.py           # Force dice, powers, temptation
│   ├── vehicle.py         # Vehicle/starship system
│   ├── time_skip.py       # Time skip vignettes
│   ├── world_registry.py  # Validation gate for LLM-proposed narrative state:
│   │                      #   location grounding, visited-location ledger,
│   │                      #   fact grounding, spine-derived NPC domains
│   ├── dramatic_mission.py # CS-6: Dramatic mission classification + voice modes
│   └── scene_validator.py # CS-6: Scene purpose validation model
├── gm/                    # LLM orchestration — fast + quality cloud tiers
│   ├── llm_client.py      # Two-tier routing, retry/backoff, token usage accounting
│   ├── fast_gm.py         # Check decisions, annotations, diagnostics,
│   │                      #   scene validation, dice-polarity post-check
│   ├── cloud_gm.py        # Narration (system+user prompt split), milestones,
│   │                      #   time skips, epilogue, choice repair
│   ├── context.py         # Context package assembly
│   ├── character_creator.py # Prose pitch → LLM draft → deterministic assembly
│   ├── choice_validator.py # CS-6: Post-generation choice quality validator
│   └── prompts/           # Prompt templates (13 files)
│       ├── check_decision.txt
│       ├── narration_system.txt   # Static narration system prompt (prefix-cacheable)
│       ├── narration.txt          # Dynamic narration turn context
│       ├── narration_literary.txt # Literary voice variant (single-message)
│       ├── character_draft.txt
│       ├── choice_annotation.txt
│       ├── epilogue.txt
│       ├── reconciliation.txt
│       ├── milestone_reflection.txt
│       ├── force_power_milestone.txt
│       ├── time_skip_opening.txt
│       └── time_skip_closing.txt
├── state/                 # SQLite persistence + telemetry
│   ├── db.py              # Database schema and connections
│   ├── session.py         # Turn logging, state queries, turn-line formatting
│   ├── memory.py          # Episodic compression + resume recap
│   └── telemetry.py       # Narrative event logging — JSON-lines per session
├── api/                   # FastAPI routes
│   ├── main.py            # App bootstrap and frontend serving
│   ├── game_routes.py     # Game Engine routes + /epilogue + /campaign/generate
│   ├── character_routes.py # /character/draft, /character/save, /character/{id}
│   └── studio_routes.py   # Campaign Studio routes
├── web/                   # Single-file frontend
│   └── index.html         # Prose reader UI + character creator + stats panel +
│                          #   milestone ceremony + finale/epilogue + resume recap
├── studio/                # Campaign Studio
│   ├── schema.py          # Spine schema — interface contract
│   ├── validate.py        # Four-gate validation + anti-positivity heuristics
│   ├── generate.py        # Modes 1, 2, 3 generation + architecture merge
│   ├── architect.py       # Pre-generation story architecture (CS-5/CS-6)
│   ├── narrative_eval.py  # Gate 4 narrative evaluation + enrichment checks
│   ├── persist.py         # Write generated spines to data/campaigns/
│   ├── seeding.py         # Deterministic seed derivation
│   ├── difficulty.py      # Spine difficulty calibration
│   ├── import_interface.py # Cross-era character import
│   ├── prompts/           # Studio prompt templates (7 files)
│   │   ├── mode1_generate.txt
│   │   ├── mode2_generate.txt
│   │   ├── mode3_assist.txt
│   │   ├── npc_voice_gen.txt
│   │   ├── architect.txt        # CS-5: architecture generation
│   │   ├── narrative_eval.txt   # CS-5: Gate 4 evaluation
│   │   └── narrative_score.txt  # CS-5: Stage 5 scoring
│   └── saga/              # Saga layer pipeline — CS-4 (1,143 lines)
│       ├── pipeline.py    # 5-stage orchestrator
│       ├── personas.py    # Persona pool management
│       ├── diverge.py     # Stage 2: direction generation
│       ├── search.py      # Stage 3: sketch expansion
│       ├── converge.py    # Stage 4: debate and refinement
│       ├── select.py      # Stage 5: pairwise selection
│       ├── ensemble.py    # Multi-model writer assignment
│       └── evaluator.py   # Trained local evaluator
├── eval/                  # Evaluation harness (1,640 lines)
│   ├── harness.py         # Scripted play sessions + quality measurement
│   ├── metrics.py         # Tier 1 (no LLM) + Tier 2 quality metrics
│   ├── divergence.py      # Cross-session replayability analysis
│   ├── golden_scenarios.py # Fixed-seed reproducible test scenarios
│   ├── policies.py        # Automated choice selection strategies
│   └── reporter.py        # Console + JSON report generation
├── data/
│   ├── characters/        # praxeum_student.json, praxeum_mechanic.json, clovis_beryl.json
│   ├── campaigns/         # shadows_of_the_custodian.json (canonical campaign)
│   ├── talent_trees/      # 6 specialization trees + talent_library.json
│   ├── force_powers/      # 5 powers (enhance, heal_harm, influence, move, sense)
│   └── personas/          # writer_room_personas.json (55 personas)
└── tests/                 # 39 test files (~16,100 lines)
    ├── __init__.py
    ├── dice_validation.py
    ├── studio_schema_test.py
    ├── test_campaign_generate.py         # POST /campaign/generate flow
    ├── test_character_creator.py         # Pitch → draft → assembly → save
    ├── test_content_packs.py             # Content pack loader + validation
    ├── test_cs2_mode3.py
    ├── test_cs3_mode2_import.py
    ├── test_cs4_saga.py
    ├── test_cs5_narrative_quality.py     # CS-5: 33 tests
    ├── test_cs6_runtime_wiring.py        # CS-6: runtime integration into game loop
    ├── test_cs6_story_engineering.py     # CS-6: Campaign Studio tests
    ├── test_e2e_game_loop.py
    ├── test_era_packs.py                 # Era-specific pack composition
    ├── test_experience_shell.py          # Completion, epilogue, recap, damage,
    │                                     #   incapacitation, dice verdict headline
    ├── test_faction_reactivity.py        # NPC faction stance and reaction logic
    ├── test_freeform_talents.py          # Custom signature-talent validation
    ├── test_identity_drift_introspection.py # Identity drift detection
    ├── test_latency_hot_path.py          # Hot-path latency budget enforcement
    ├── test_llm_client_backoff.py        # LLM retry/backoff (429 handling)
    ├── test_llm_client_serialization.py  # LLM request-body shape + RUN_LIVE_LLM gate
    ├── test_path_differentiation_audit.py # Choice path differentiation audit
    ├── test_phase10_advancement.py
    ├── test_phase115_destiny.py
    ├── test_phase11_talents.py
    ├── test_phase12_milestones.py
    ├── test_phase13_choice_quality.py
    ├── test_phase14_force.py
    ├── test_phase155_fd_trees.py
    ├── test_phase15_force_powers.py
    ├── test_phase16_vehicles.py
    ├── test_phase17_time_skips.py
    ├── test_physics_guardrails.py        # World registry, fact grounding,
    │                                     #   polarity wiring, choice repair,
    │                                     #   prompt split, usage accounting
    ├── test_reconciliation_escalation.py # Reconciliation escalation rules
    ├── test_scene_validator_wiring.py     # CS-6: scene validator runtime integration
    ├── test_spine_world_derivation.py    # Spine-derived NPC domains + act vocabulary
    ├── test_story_coherence_state.py     # Cross-turn coherence checks
    ├── test_story_engineering.py         # CS-6: Game Engine story-engineering tests
    └── test_studio_enrichment_generation.py # Studio enrichment generation + gates
```

**Note:** `data/evaluation_pairs/` and `data/canon_profiles/` directories
are mentioned in design docs for future phases but do not yet exist in
the repo. They will be created when Phase 21 (canon profiles) and the
trained local evaluator (post-CS-4) are implemented.

**Evaluation harness:** `eval/` contains the quality measurement
framework — scripted play sessions, golden scenarios, divergence
analysis, and narrative metrics (Tier 1 heuristic + Tier 2
LLM-assisted). Telemetry data is emitted by `state/telemetry.py` and
consumed by the eval metrics pipeline.

**Documentation structure:** Docs are organized into tier-based
subdirectories (`specs/`, `status/`, `research/`, `specialist/`,
`api/`, `reference/`). See `docs/index.md` for the four-tier document
architecture.

Game Engine scope: `engine/`, `gm/`, `state/`, `api/game_routes.py`,
`web/`. Do not modify `studio/` when working on the Game Engine
(except importing from `studio/schema.py` for spine loading).
