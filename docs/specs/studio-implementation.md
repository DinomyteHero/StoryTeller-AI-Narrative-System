# Storyteller V3 — Campaign Studio Implementation Document

**Document version:** 1.3  
**Project:** Storyteller V3  
**Last updated:** March 5, 2026  
**Build priority:** Post-V1. Do not begin until the Game Engine vertical
slice (12 success criteria) is met.

**Scope:** This document specifies the Campaign Studio — the authoring
system that produces campaign spine JSON files consumed by the Game
Engine. The companion document
`STORYTELLER_V3_IMPLEMENTATION.md` (v1.8+) specifies the Game Engine.

**Relationship to design documents:**
- **Campaign Studio Design Document (v1.3)** — defines *what* the
  system does. Read it before this document.
- **This document** — defines *how* it is built in code.
- **LLM Evaluation Document (v2.0)** — defines which models serve which
  Campaign Studio roles (Section 9).
- **Research Catalogue (v1.0)** — provides the evidence basis for
  architectural decisions.

---

## 0. Read This First

The Campaign Studio is an authoring tool, not a game. It runs at design-
time with no real-time latency constraints. This changes everything
about the architectural trade-offs compared to the Game Engine:

- **Multiple LLM calls per operation are acceptable.** The Game Engine's
  "one cloud call per turn" rule does not apply here.
- **Multi-pass generation and validation are expected.** Generate,
  critique, revise, validate — each pass can use a different model.
- **Latency tolerance is high.** A saga generation pipeline that takes
  60 seconds is fine. The user initiated it once per completed campaign.
- **The output must be mechanically perfect.** The campaign spine JSON
  must pass validation before the Game Engine touches it. A malformed
  spine corrupts the entire campaign at runtime.

**The single rule that overrides everything else:**

> The Campaign Studio produces valid campaign spines. If it produces
> anything else, it has failed.

---

## 1. Technology Stack

### Shared with Game Engine

| Layer | Technology | Purpose |
|---|---|---|
| Language | Python 3.11+ | All backend |
| Local LLM | Ollama — Qwen3.5:9B | Divergent ideation, evaluation, critique (see LLM Eval §9) |
| Cloud LLM | OpenAI-compatible SDK — provider-configurable | Spine refinement, generation, critique |
| Database | SQLite (WAL mode) via Python stdlib | Campaign persistence, saga state |
| Data models | Pydantic v2 | Validation throughout |
| Package mgmt | pyproject.toml (no Poetry) | Shared dependency management |

### Campaign Studio Specific

| Layer | Technology | Purpose |
|---|---|---|
| Validation | Pydantic v2 + custom validators | Spine schema enforcement |
| NPC graph analysis | NetworkX | Relationship network validation |
| Persona pool | JSON file | Writer's Room persona assignments |
| API | FastAPI (shared app, Studio-specific routes) | Authoring endpoints |
| Frontend | Studio UI (design TBD) | Authoring interface for Modes 3 and 2 |

**Hardware note:** The local model serves dual duty — Game Engine check
decisions at runtime AND Campaign Studio ideation/evaluation at
authoring time. These never run simultaneously (you are either playing
or authoring, not both). No additional hardware required.

---

## 2. Repository Structure

The Campaign Studio lives within the same repository as the Game Engine.
Shared infrastructure (database, LLM clients, configuration) is reused.
Studio-specific code is isolated in its own directory.

```
storyteller-v3/
├── engine/                      # Game Engine — pure Python mechanics
├── gm/                          # Game Engine — LLM orchestration
├── state/                       # Shared — persistence layer
├── api/
│   ├── main.py                  # Shared FastAPI app
│   ├── game_routes.py           # Game Engine API routes
│   └── studio_routes.py         # Campaign Studio API routes
│
├── studio/                      # Campaign Studio — all authoring code
│   ├── __init__.py
│   ├── schema.py                # Pydantic models for campaign spine JSON
│   ├── validate.py              # Validation suite (5.1–5.4)
│   ├── generate.py              # Spine generation orchestration (Modes 1–3)
│   ├── critique.py              # Debate/critique agent
│   ├── evaluate.py              # Pairwise spine evaluator
│   ├── import_interface.py      # Cross-era character import
│   ├── seeding.py               # Deterministic seed derivation + GenerationMetadata
│   ├── difficulty.py            # Spine difficulty calibration (Gate 4 integration)
│   ├── saga/                    # Saga layer pipeline
│   │   ├── __init__.py
│   │   ├── pipeline.py          # Five-stage orchestrator
│   │   ├── personas.py          # Persona pool management + subset selection
│   │   ├── diverge.py           # Stage 2 — divergent generation
│   │   ├── search.py            # Stage 3 — branching search
│   │   ├── converge.py          # Stage 4 — debate and coherence
│   │   ├── select.py            # Stage 5 — pairwise evaluation
│   │   ├── ensemble.py          # Multi-model writer assignment + parallel execution
│   │   └── evaluator.py         # Trained local evaluator (QLoRA) + calibration
│   └── prompts/
│       ├── mode3_assist.txt     # Mode 3 collaborative assistance prompt
│       ├── mode2_generate.txt   # Mode 2 thematic generation prompt
│       ├── mode1_generate.txt   # Mode 1 full blind generation prompt
│       ├── npc_voice_gen.txt    # NPC voice note generation prompt
│       ├── critique.txt         # Critique agent prompt template
│       ├── evaluate.txt         # Pairwise evaluator prompt template
│       ├── diverge.txt          # Saga Stage 2 divergent generation prompt
│       └── refine.txt           # Saga Stage 3 refinement prompt
│
├── data/
│   ├── characters/              # Shared — character data files
│   ├── campaigns/               # Shared — campaign spine files
│   ├── personas/
│   │   └── writer_room_personas.json  # 55 personas across 11 clusters
│   ├── evaluation_pairs/        # Logged pairwise comparisons for evaluator training
│   └── saga/
│       └── test_pipeline/       # Saga layer test artifacts
│
└── tests/
    ├── dice_validation.py       # Game Engine tests
    ├── studio_schema_test.py    # Spine schema validation tests
    └── saga_pipeline_test.py    # Saga pipeline integration tests
```

---

## 3. Build Phases — Strict Order

The Campaign Studio is built in four phases. Each phase produces a
working, testable system. Do not begin a phase until the prior phase
passes its success criteria.

### Phase CS-1: Schema and Validation

The foundation. Pydantic models for the campaign spine JSON and the
full validation suite. No LLM calls. Pure Python.

**Deliverables:** `studio/schema.py`, `studio/validate.py`, tests.
**Success criteria:** The existing test campaign spine
("The Nar Shaddaa Job" from Game Engine Implementation §12) passes all
four validation gates. A deliberately malformed spine fails with
specific, actionable error messages identifying each problem.

### Phase CS-2: Mode 3 — Collaborative Authoring

The first LLM-assisted mode. Human drives, AI assists. Requires cloud
model integration for assistance tasks (galactic context drafting, NPC
voice note generation, gap identification).

**Deliverables:** `studio/generate.py` (Mode 3 path),
`studio/prompts/mode3_assist.txt`, `studio/prompts/npc_voice_gen.txt`,
`studio/seeding.py` (deterministic seed derivation for partial
regeneration), `studio/difficulty.py` (spine difficulty calibration
integrated with Gate 4), Studio API routes, minimal UI.
**Success criteria:** An author can create a new campaign spine through
the Mode 3 workflow, with AI assistance at each step, and produce a
spine that passes all validation gates. Partial regeneration via
seeding produces similar-but-varied output for held-constant stages.

### Phase CS-3: Mode 2 — Thematic Steering + Cross-Era Import

The AI generates from thematic direction. Requires the full generation
pipeline plus the cross-era character import interface.

**Deliverables:** `studio/generate.py` (Mode 2 path),
`studio/prompts/mode2_generate.txt`, `studio/import_interface.py`.
**Success criteria:** An author can provide a thematic brief and receive
a complete, validated campaign spine. A character from a completed
campaign can be imported into a new campaign spine with NPC relationship
and motivation track mapping.

### Phase CS-4: Saga Layer + Mode 1

The full Writer's Room pipeline for sequel spine generation, plus Mode 1
autonomous generation. This is the most complex phase and depends on
Phases CS-1 through CS-3.

**Deliverables:** All `studio/saga/*.py` files (including
`ensemble.py` for multi-model writer assignment and `evaluator.py` for
local evaluator integration), `data/personas/writer_room_personas.json`
(55 personas across 11 clusters — pool drafted in Gap Analysis v2.0),
`data/saga/test_pipeline/` (saga test artifact from template in Gap
Analysis v2.0), `studio/generate.py` (Mode 1 path),
`studio/prompts/mode1_generate.txt`.
**Success criteria:** The saga pipeline generates a sequel spine from a
completed campaign that passes all validation gates, and the sequel is
structurally distinct from the original campaign when run multiple times
with different persona assignments. Mode 1 produces playable spines
from minimal input. Persona pool passes the five-subset diversity
validation (≥3 of 5 subsets produce distinct sequel directions).

**Post-CS-4 optimization (not blocking):** Train the local evaluator
(QLoRA) on 600+ pairwise comparison pairs from Stage 5 runs and player
ratings. Deploy as drop-in replacement for cloud evaluator in Stage 5
when calibration threshold (80% agreement) is met. See Gap Analysis
v2.0, item 4.9.

### Phase CS-5: Narrative Quality — Story Architecture + Gate 4

**Status: COMPLETE — April 2026**

Pre-generation narrative planning layer and LLM-assisted quality
evaluation. Ensures campaign spines have dramatic DNA — not just
structural correctness — before reaching the player.

**Deliverables:**

- `studio/architect.py` (155 lines) — Pre-generation story architecture
  planning. `generate_architecture()` calls cloud LLM with campaign
  inputs (era, location, tone, optional throughline/concept/moral
  register) to produce a `StoryArchitecture` model.
  `architecture_to_prompt_block()` formats the architecture for
  injection into Mode 1/2 generation prompts. Uses deterministic seed
  derivation via `STAGE_ARCHITECT` constant.

- `studio/narrative_eval.py` (482 lines) — Gate 4 narrative evaluation
  with three sub-dimensions:
  - **4a Narrative Coherence** (LLM-assisted): thread_continuity,
    npc_trajectory_consistency, throughline_presence,
    galactic_context_relevance.
  - **4b Dramatic Quality** (conditional on `story_architecture`
    presence): premise_manifestation, cdq_testability,
    antagonistic_force_presence, npc_thematic_diversity,
    contradiction_testability.
  - **4c Anti-Genericity** (LLM-assisted): npc_distinctiveness,
    anchor_specificity, escalation_authenticity.
  `score_narrative_quality()` returns a normalized 0.0–1.0 score across
  five rubric dimensions (premise_strength, npc_thematic_diversity,
  dramatic_progression, throughline_testability, anti_genericity).

- `studio/prompts/architect.txt` (112 lines) — Architecture generation
  prompt with anti-default rules (no "good vs evil", no "saves the
  galaxy", villain-as-systemic-not-personal), five pressure types
  (moral, identity, loyalty, survival, ideological), and JSON output
  schema.

- `studio/prompts/narrative_eval.txt` (57 lines) — Gate 4 evaluation
  prompt requesting per-dimension pass/fail with detail explanations.

- `studio/prompts/narrative_score.txt` (54 lines) — Narrative quality
  scoring prompt with five 1-5 dimension scores.

**Schema additions (`studio/schema.py`):**

- `StoryArchitecture` model: dramatic_premise, central_dramatic_question,
  story_promise, protagonist_pressure_type (validated enum: moral /
  identity / loyalty / survival / ideological), antagonistic_force,
  thematic_throughline, ending_payoff_sketch. Validators enforce CDQ
  ends with "?" and pressure type is valid.

- `CampaignSpine.story_architecture: Optional[StoryArchitecture]` —
  Populated by `architect.py` before spine generation.

- `CharacterVariant.protagonist_contradiction` and
  `CharacterVariant.pressure_revealed_identity` — Character architecture
  fields for dramatic depth.

- `NPC.thematic_argument` — What this NPC's existence argues about
  the theme.

- `Act.dramatic_function` — Validated enum: setup, destabilization,
  launch, midpoint_shift, escalation, confrontation, consequence,
  resolution.

**Design reference:** `specialist/story-architecture.md` (vocabulary, rubrics,
Gate 4 design). Game Mechanics §25 (NPC fields). Vision §3 (prose
quality goals).

**Success criteria:**
1. `generate_architecture()` produces valid `StoryArchitecture` from
   era/location/tone input
2. Architecture is injected into Mode 1/2 generation prompts via
   `architecture_to_prompt_block()`
3. Gate 4 evaluates coherence (4a), dramatic quality (4b), and
   anti-genericity (4c) on generated spines
4. Gate 4b is conditional — skipped when `story_architecture` is absent
5. `score_narrative_quality()` returns 0.0–1.0 normalized score
6. Anti-default rules prevent generic "hero vs villain" architectures
7. Tests in `test_cs5_narrative_quality.py` pass (33 tests)

### Phase CS-6: Story Engineering Integration

**Status: COMPLETE — April 2026**

Extends the story architecture layer with structural storytelling tools:
pinch points, milestone beat sheets, protagonist mode progression,
foreshadow registries, character depth cards, NPC pressure roles, and
scene-level dramatic mission classification with voice mode guidance.

**Deliverables:**

- `engine/dramatic_mission.py` (260 lines) — Turn-level dramatic
  mission classification. Pure Python, zero LLM dependencies.
  - `DramaticMission` enum: 14 mission types across Brooks's four-part
    model (stake_setup, world_normal, foreshadow, response,
    false_progress, antagonist_pressure, attack, inner_demon_test,
    midpoint_reframe, collapse, climactic_execution, aftermath,
    character_reveal, thread_advance).
  - `MissionContext` model: valid_missions, selected_mission,
    mission_instruction, scene_thrust_instruction.
  - `PART_MISSION_MAP`: dramatic_function → valid missions mapping.
  - `MISSION_TO_VOICE` + `VOICE_INSTRUCTIONS`: mission → voice mode
    (action, revelation, emotional, transition, confrontation) with
    prose style guidance.
  - `compute_valid_missions()`: returns valid missions for current turn
    based on dramatic_function and progress.
  - `check_midpoint_conversion()` / `check_no_new_exposition()`:
    milestone beat sheet constraint enforcement.

- `engine/scene_validator.py` (122 lines) — Post-narration scene
  purpose validation. Local model call scoring narration against its
  dramatic mission on five dimensions (mission_delivery,
  pressure_progression, antagonist_relevance, character_choices, change).
  `SceneValidationResult` with composite score (1-5 scale), concern
  text, and auto-generated corrective instruction if composite <
  THRESHOLD_OK (3.0). Quality signal only — does not block delivery.

**Schema additions (`studio/schema.py`):**

- `MilestoneBeatSheet` model: concept_question ("What if...?" format),
  first_plot_point, midpoint, second_plot_point with act numbers,
  pre_resolution_lull. Brooks's five structural milestones.

- `ProtagonistMode` enum: ORPHAN → WANDERER → WARRIOR → MARTYR
  (sequential progression, no regression allowed).

- `PinchPoint` model: description, delivery_method (intercepted_comm /
  npc_report / environmental / direct_witness / consequence_shown),
  target_progress (0.3–0.7).

- `ForeshadowLink` model: id, setup_act, setup_description, payoff_act,
  payoff_description, payoff_type (revelation / reversal / callback /
  irony).

- `CharacterDepthCard` model: inner_demon, secret_yearning,
  lesson_not_learned, worst_act, social_mask, under_pressure, worldview,
  moral_line. GM-facing enrichment (never shown to player).

- `Act.pinch_point: Optional[PinchPoint]` — Direct antagonist pressure
  signal per non-setup act.
- `Act.protagonist_mode` — Sequential progression through campaign.
- `CharacterVariant.contradiction_origin` — Why the contradiction exists.
- `CharacterVariant.depth_card: Optional[CharacterDepthCard]`.
- `NPC.pressure_role` — Validated: tempter, mirror, skeptic, dependent,
  betrayer, witness, escalator, false_ally, catalyst.
- `CampaignSpine.foreshadow_registry: list[ForeshadowLink]`.
- `StoryArchitecture.milestone_beat_sheet: Optional[MilestoneBeatSheet]`.

**CS-6 deterministic validation checks** (in `narrative_eval.py`,
`_check_cs6_structural()`):
- Pinch point coverage: every mid-campaign act with dramatic_function
  must have pinch_point.
- Milestone beat sheet sequence: FPP < Midpoint < SPP.
- Milestone placement percentages: FPP 15-40%, Midpoint 35-65%,
  SPP 60-85%.
- Concept question format: starts "What if", ends "?".
- Protagonist mode progression: modes must not regress.
- NPC pressure role diversity: warns if all pressure roles identical.
- Foreshadow registry: setup_act < payoff_act ordering, coverage in
  final third.

**Design reference:** `specialist/story-architecture.md` (vocabulary extended
with CS-6 tools). `architect.txt` prompt template (pinch points and
milestone beat sheet sections).

**Success criteria:**
1. `compute_valid_missions()` returns correct missions per
   dramatic_function and Brooks part
2. Voice modes map missions to appropriate prose guidance
3. Scene validator scores narration against mission on 5 dimensions
4. All CS-6 structural checks pass on well-formed spines
5. MilestoneBeatSheet enforces sequence and placement constraints
6. Protagonist mode progression is monotonic (no regression)
7. Foreshadow registry validates setup→payoff ordering
8. Tests in `test_cs6_story_engineering.py` and
   `test_story_engineering.py` pass

---

## 4. The Interface Contract: Campaign Spine JSON

The campaign spine JSON is the output of the Campaign Studio and the
input of the Game Engine. This section specifies the contract from the
Campaign Studio's perspective — what it must produce.

The complete schema is defined in the Campaign Studio Design Document
(Section 4). The Pydantic models in `studio/schema.py` are the
authoritative code-level representation.

### 4.1 `studio/schema.py`

```python
"""
Campaign spine JSON schema — Pydantic v2 models.

These models define the interface contract between the Campaign Studio
and the Game Engine. A spine that passes validation against these models
is guaranteed to be consumable by the Game Engine.

Updated for Game Mechanics v1.5 — includes XP awards, time skip
vignettes, Force discovery, vehicle registry, equipment loadout,
canon character profiles, milestone windows, and expanded import
interface.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional


# ── Prologue ──────────────────────────────────────────────────────────


class AxisTags(BaseModel):
    approach: Optional[str] = None
    risk: Optional[str] = None
    social: Optional[str] = None
    moral: Optional[str] = None


class PrologueChoice(BaseModel):
    text: str = Field(min_length=10)
    axis_tags: AxisTags


class PrologueScene(BaseModel):
    scene_number: int = Field(ge=1)
    situation: str = Field(min_length=20)
    choices: list[PrologueChoice] = Field(min_length=2, max_length=4)


class PrologueSet(BaseModel):
    variant_id: str
    career_type: str
    allegiance: str
    scenes: list[PrologueScene] = Field(min_length=3, max_length=5)


# ── Character construction ────────────────────────────────────────────


class CharacteristicsBase(BaseModel):
    brawn: int = Field(ge=1, le=6)
    agility: int = Field(ge=1, le=6)
    intellect: int = Field(ge=1, le=6)
    cunning: int = Field(ge=1, le=6)
    willpower: int = Field(ge=1, le=6)
    presence: int = Field(ge=1, le=6)


class MotivationDefault(BaseModel):
    track: str
    possible_types: list[str] = Field(min_length=2)

    @field_validator("track")
    @classmethod
    def valid_track(cls, v: str) -> str:
        if v not in ("obligation", "duty", "morality"):
            raise ValueError(f"Invalid track: {v}")
        return v


class NPCOverride(BaseModel):
    disposition_start: float = Field(ge=0.0, le=1.0)
    relationship: str


class IntegrationLayer(BaseModel):
    """Connects a variant to the campaign's fixed thematic spine."""
    entry_point: str = Field(min_length=20)
    personal_stakes: str = Field(min_length=20)
    npc_overrides: dict[str, NPCOverride] = {}
    anchor_adaptations: dict[str, str] = {}


# ── Equipment / Loadout (Game Mechanics §18) ──────────────────────────


class WeaponEntry(BaseModel):
    name: str
    skill: str
    damage_bonus: int = Field(ge=0)
    critical_rating: int = Field(ge=1, le=6)
    qualities: list[str] = []
    narrative_note: str = ""


class ArmorEntry(BaseModel):
    name: str
    soak_bonus: int = Field(ge=0)
    defense: int = Field(ge=0, le=4)
    narrative_note: str = ""


class ToolEntry(BaseModel):
    category: str
    name: str
    mechanical_effect: str
    narrative_note: str = ""


class SpecialItem(BaseModel):
    name: str
    mechanical_effect: str = ""
    narrative_note: str = ""


class Loadout(BaseModel):
    """Character's equipment loadout. (Game Mechanics §18)"""
    weapons: list[WeaponEntry] = []
    armor: Optional[ArmorEntry] = None
    tools: list[ToolEntry] = []
    special_items: list[SpecialItem] = []


# ── Force power definitions (Game Mechanics §16) ─────────────────────


class ForcePowerStart(BaseModel):
    """A Force power the character begins with."""
    power_id: str
    name: str
    category: str
    base_pips_required: int = Field(ge=1, default=1)
    active_upgrades: list[str] = []
    narrative_capability: str
    gm_choice_guidance: str
    dark_side_flavor: str = ""


# ── Character variant ─────────────────────────────────────────────────


class CharacterVariant(BaseModel):
    id: str
    allegiance: str
    pitch: str = Field(min_length=20)
    species: str
    career: str
    career_type: str
    specializations: list[str] = Field(min_length=1)
    primary_game_line: str
    force_sensitive: bool
    motivation_default: MotivationDefault
    starting_situation: str = Field(min_length=20)
    voice_baseline: str
    background: str
    integration_layer: IntegrationLayer
    characteristics_base: CharacteristicsBase
    skills_base: dict[str, int]
    wound_threshold: int = Field(ge=1)
    strain_threshold: int = Field(ge=1)
    soak: int = Field(ge=0)
    # ── New fields (Game Mechanics v1.5) ──
    starting_loadout: Loadout = Field(default_factory=Loadout)
    starting_force_powers: list[ForcePowerStart] = []
    starting_xp: int = Field(ge=0, default=0)


class Allegiance(BaseModel):
    """Faction option within a campaign's character funnel."""
    id: str
    display_name: str
    description: str = Field(min_length=20)
    character_variants: list[CharacterVariant] = Field(
        min_length=1, max_length=4
    )


# ── NPCs ──────────────────────────────────────────────────────────────


class NPCRelationship(BaseModel):
    npc: str
    nature: str
    weight: float = Field(ge=-1.0, le=1.0)


class NPCActState(BaseModel):
    act: int
    role_in_act: str
    disposition_expected: str | float


class CanonVoice(BaseModel):
    """Extended voice profile for canon characters. (GM §22)"""
    speech_patterns: str
    thinking_style: str
    emotional_register: str


class CanonRelationshipDynamics(BaseModel):
    """How a canon character relates to specific people. (GM §22)"""
    with_player: str
    other_dynamics: dict[str, str] = {}


class CanonActOverride(BaseModel):
    """Per-act profile changes for canon characters. (GM §22)"""
    era_specific_notes: Optional[str] = None
    voice: Optional[CanonVoice] = None
    behavioral_envelope: Optional[list[str]] = None


class NPC(BaseModel):
    name: str
    role: str
    disposition_start: float = Field(ge=0.0, le=1.0)
    disposition_trajectory: str
    motivation: str
    voice_notes: str = Field(min_length=10)
    behavioral_envelope: list[str] = Field(min_length=1)
    knows_at_start: list[str]
    doesnt_know_at_start: list[str]
    per_act_state: list[NPCActState]
    npc_relationships: list[NPCRelationship] = []
    # ── Canon character fields (Game Mechanics §22) ──
    canon: bool = False
    era_profile: Optional[str] = None
    canon_voice: Optional[CanonVoice] = None
    relationship_dynamics: Optional[CanonRelationshipDynamics] = None
    era_specific_notes: Optional[str] = None
    anti_stereotype_notes: Optional[str] = None
    act_overrides: dict[str, CanonActOverride] = {}


# ── Variation points ──────────────────────────────────────────────────


class VariationOption(BaseModel):
    id: str
    description: str
    npc_state_changes: dict = {}


class VariationPoint(BaseModel):
    id: str
    trigger_act: int
    description: str
    selection_method: str
    options: list[VariationOption] = Field(min_length=2)


# ── XP and advancement (Game Mechanics §14) ───────────────────────────


class BonusCondition(BaseModel):
    """A condition that awards bonus XP at act boundary."""
    condition_type: str  # "anchor_engagement", "motivation_interaction",
                         # "skill_breadth", "failure_engagement", "custom"
    description: str
    xp_value: int = Field(ge=1, default=5)
    parameters: dict = {}  # condition-type-specific params


class MilestoneWindow(BaseModel):
    """Authored timing hint for milestone reflections."""
    act: int
    milestone_type: str  # "talent", "specialization", "force_power",
                         # "force_awakening", "career_transition"
    description: str = ""
    conditions: dict = {}


# ── Time skip vignettes (Game Mechanics §19) ──────────────────────────


class VignetteChoice(BaseModel):
    text: str
    skill_tag: str
    npc_effects: dict[str, float] = {}   # npc_name → disposition delta
    moral_weight: int = Field(ge=0, le=3, default=0)
    morality_bonus: int = Field(ge=0, le=2, default=0)
    aspiration_tags: list[str] = []
    narrative_consequence: str = Field(min_length=20)


class Vignette(BaseModel):
    vignette_id: str
    category: str  # "training", "relationship", "solitary", "crisis",
                   # "discovery", "mundane"
    npc_focus: Optional[str] = None
    skill_domain: list[str] = []
    requires: dict = {}     # prerequisite conditions
    excludes: dict = {}     # exclusion conditions
    time_stamp: str = ""    # e.g. "The second week"
    passage: str = Field(min_length=50)
    choices: list[VignetteChoice] = Field(min_length=2, max_length=3)


class TimeSkip(BaseModel):
    """Time skip data between acts. (Game Mechanics §19)"""
    duration_months: int = Field(ge=1)
    narrative_framing: str
    skip_events: list[dict] = []
    skill_decay_enabled: bool = True
    vignette_library: list[Vignette] = []
    vignette_count: Optional[int] = Field(
        ge=1, le=3, default=None
    )  # None = auto based on duration


# ── Vehicles (Game Mechanics §17) ─────────────────────────────────────


class ShipWeapon(BaseModel):
    name: str
    skill: str = "gunnery"
    damage: int = Field(ge=0)
    arc: str = "all"
    qualities: list[str] = []


class Ship(BaseModel):
    """Vehicle/starship definition for the vehicle registry."""
    ship_id: str
    name: str
    type: str
    silhouette: int = Field(ge=1, le=10)
    speed: int = Field(ge=0, le=6)
    handling: int = Field(ge=-3, le=3)
    hull_threshold: int = Field(ge=1)
    system_strain_threshold: int = Field(ge=1)
    armor: int = Field(ge=0)
    shields: dict[str, int] = {}  # arc → value
    weapons: list[ShipWeapon] = []
    narrative_notes: str = ""


# ── Acts ──────────────────────────────────────────────────────────────


class Act(BaseModel):
    number: int = Field(ge=1)
    name: str
    tension: str
    opening_situation: str = Field(min_length=20)
    opening_location: str = Field(min_length=5)
    galactic_context: str = Field(min_length=20)
    anchor: str
    next_anchor: str | None = None
    open_threads: list[str] = []
    expected_turns: str
    # ── New fields (Game Mechanics v1.5) ──
    xp_base: int = Field(ge=0, default=15)
    xp_bonus_conditions: list[BonusCondition] = []
    time_skip_after: Optional[TimeSkip] = None  # skip between this act
                                                 # and the next
    milestone_windows: list[MilestoneWindow] = []


# ── Import interface (Game Mechanics §20) ─────────────────────────────


class SpecializationMapping(BaseModel):
    """How a prior specialization maps onto the new campaign."""
    source_spec: str
    mapping: str  # "continuity", "dormancy", "evolution"
    target_spec: Optional[str] = None  # for evolution — what it becomes
    notes: str = ""


class ImportInterface(BaseModel):
    """Full cross-era import specification. (Game Mechanics §20)"""
    compatible_campaigns: list[str] = []
    specialization_mappings: list[SpecializationMapping] = []
    motivation_transition: dict = {}  # track changes at era boundary
    target_xp_range: tuple[int, int] = (0, 9999)
    imported_loadout: Optional[Loadout] = None  # replaces prior gear
    transition_framing: str = ""  # guidance for transition passage gen


# ── Saga metadata ─────────────────────────────────────────────────────


class SagaMetadata(BaseModel):
    """Optional metadata for sequel spines."""
    prior_campaign_id: str
    throughline_evolution: str
    imported_npc_mappings: dict[str, str] = {}
    required_import_fields: list[str] = []
    default_state_for_new_characters: dict = {}


# ── Faction tracking (Gap Analysis v1.1, item 2.11) ──────────────────


class FactionSpec(BaseModel):
    """Per-campaign faction definition with authored drift."""
    faction_id: str
    display_name: str
    disposition_start: float = Field(ge=0.0, le=1.0, default=0.5)
    influence_start: float = Field(ge=0.0, le=1.0, default=0.5)
    awareness_start: float = Field(ge=0.0, le=1.0, default=0.0)
    per_act_drift: dict[str, dict[str, float]] = {}  # act_num → field → delta


# ── Generation metadata (Gap Analysis v2.0, item 3.26) ───────────────


class GenerationMetadata(BaseModel):
    """Records generation parameters for reproducibility."""
    master_seed: int
    stage_seeds: dict[str, int] = {}     # stage_name → derived seed
    model_used: str = ""
    generation_mode: str = ""            # "mode1" | "mode2" | "mode3_assist"
    timestamp: str = ""


# ── Top-level spine ───────────────────────────────────────────────────


class CampaignSpine(BaseModel):
    """Top-level campaign spine — the interface contract."""
    name: str
    era: str
    total_acts: int = Field(ge=2)
    throughline_question: str
    allegiances: list[Allegiance] = Field(
        min_length=2, max_length=4
    )
    prologue_scenes: list[PrologueSet] = []
    acts: list[Act] = Field(min_length=2)
    npc_roster: list[NPC] = Field(min_length=1)
    variation_points: list[VariationPoint] = []
    saga_metadata: Optional[SagaMetadata] = None
    # ── New fields (Game Mechanics v1.5) ──
    vehicle_registry: list[Ship] = []
    force_discovery_probability: float = Field(
        ge=0.0, le=1.0, default=0.0
    )
    force_discovery_window: Optional[tuple[int, int]] = None
    force_discovery_trigger: Optional[str] = None
    import_interface: Optional[ImportInterface] = None
    # ── New fields (Gap Analysis v1.1 / v2.0) ──
    factions: list[FactionSpec] = []           # item 2.11
    generation_metadata: Optional[GenerationMetadata] = None  # item 3.26

    @field_validator("acts")
    @classmethod
    def acts_sequential(cls, v: list[Act]) -> list[Act]:
        for i, act in enumerate(v):
            if act.number != i + 1:
                raise ValueError(
                    f"Act {i+1} has number {act.number}"
                )
        return v
```

### 4.2 Validation Suite — `studio/validate.py`

Four validation gates, applied in order. A spine must pass all four
before the Game Engine can consume it.

**Gate 1 — Schema contract validation.** Pure Python. Checks: act count
matches `total_acts`, all NPC references in variation points resolve to
roster entries, all allegiances contain at least one character variant,
character variants have matching prologue scenes, variant `allegiance`
fields match their containing allegiance `id`, throughline question ends
with "?", acts are sequentially numbered. New checks for v1.5 fields:
Force-sensitive variants have `starting_force_powers` if
`force_sensitive` is true, `force_discovery_window` act range falls
within `total_acts`, vignette `npc_focus` references resolve to roster
entries, `xp_base` is positive on all acts, canon NPC entries
(`canon: true`) have `canon_voice` and `behavioral_envelope` populated,
vehicle `ship_id` values are unique, `import_interface.target_xp_range`
minimum ≤ maximum. New checks for Gap Analysis fields: faction
`faction_id` values are unique, `per_act_drift` keys are valid act
numbers, NPC `social_connections` entries reference NPCs that exist in
the roster.

**Gate 2 — NPC coherence validation.** Per-NPC disposition trajectory
analysis. Flags disposition shifts > 0.3 between consecutive acts
without setup in the `role_in_act` description.

**Gate 3 — Relationship network validation.** Checks for LLM-typical
positivity skew: flags mean relationship weight > 0.5, flags > 80%
positive relationships, flags sparse antagonist networks. Uses
NetworkX for graph analysis if available, falls back to simple
arithmetic otherwise.

**Gate 4 — Narrative consistency audit.** Three LLM calls checking
narrative coherence (contradictions, dropped threads), mechanical
balance (difficulty curves, scene variety), and prose variety potential
(setting/mood diversity). Optional when running without cloud access
(Gates 1–3 are mandatory; Gate 4 is recommended). **Difficulty
calibration** (Gap Analysis v2.0, item 3.27) runs as part of Gate 4:
four-signal per-act scoring (anchor intensity, NPC opposition,
mechanical pressure, pacing pressure) producing a `SpineDifficultyCurve`
with composite score, curve shape classification, and calibration
warnings. The difficulty calibration is pure Python (no LLM calls) and
runs even when Gate 4 LLM checks are skipped.

---

## 5. Saga Layer Intermediate Schemas

The five-stage saga pipeline uses progressively richer representations.
Each stage adds more structure. The final output is a full
`CampaignSpine`.

### Stage 2 Output — Sequel Direction

```python
class SequelDirection(BaseModel):
    """Lightweight creative brief. Cheap to generate and evaluate."""
    throughline_question: str
    primary_conflict_type: str
    setting_description: str  # 1-2 sentences
    tone_shift: str           # How this differs from the prior campaign
    key_thematic_elements: list[str] = Field(min_length=3, max_length=5)
    denial_constraints_applied: list[str]
```

### Stage 3 Output — Spine Sketch

```python
class ActOutline(BaseModel):
    number: int
    anchor_summary: str       # One sentence
    tension: str

class NPCOutline(BaseModel):
    name: str
    role: str                 # One sentence
    motivation_summary: str   # One sentence

class SpineSketch(BaseModel):
    """Expands direction into act-level structure."""
    direction: SequelDirection
    act_outlines: list[ActOutline]
    npc_roster_outline: list[NPCOutline]
    galactic_context_notes: list[str]  # Per-act, one sentence each
```

### Stage 4 Output — Draft Spine

A full `CampaignSpine` that passes Gate 1 (schema validation) but
has not yet been evaluated for quality/novelty/diversity. Format is
identical to the final spine.

### Stage 5 Output — Evaluated Spine

A `CampaignSpine` that has passed all four validation gates plus
three-axis evaluation.

```python
class EvaluationResult(BaseModel):
    structural_quality: float = Field(ge=0.0, le=1.0)
    novelty: float = Field(ge=0.0, le=1.0)
    diversity_vs_prior: float = Field(ge=0.0, le=1.0)
    composite: float = Field(ge=0.0, le=1.0)

class EvaluatedSpine(BaseModel):
    spine: CampaignSpine
    evaluation: EvaluationResult
    validation_report: dict
```

### Saga Layer Configuration (Gap Analysis v2.0)

```python
class SagaConfig(BaseModel):
    """Runtime configuration for the saga pipeline."""
    evaluator: str = "cloud"       # "cloud" | "local" | "ensemble"
    writer_count: int = Field(ge=1, default=7)
    ensemble_enabled: bool = False  # multi-model writers (item 4.10)
    model_pool: list[dict] = []    # available models for ensemble
    assignment_strategy: str = "round_robin"  # or "weighted" | "random"
    search_depth: int = Field(ge=1, default=3)   # Stage 3 branching
    debate_rounds: int = Field(ge=1, default=2)  # Stage 4 iterations

class RunDiversityMetrics(BaseModel):
    """Per-run diversity metrics for Bitter Lesson monitoring."""
    models_used: list[str]
    unique_conflict_types: int
    unique_thematic_elements: int
    pairwise_diversity_mean: float  # from Stage 5
    run_timestamp: str
```

---

## 6. Cross-Era Import Interface

`studio/import_interface.py` maps a completed character's state onto
a new campaign spine. Specified in Campaign Studio Design Document
Section 6.1 and Game Mechanics Document Section 20.

### 6.1 What Gets Imported (the Import Package)

The Game Engine exports an **import package** when a character completes
a campaign. The package contains:

**Mechanical state:** Full character sheet (characteristics, skills,
all ranks), acquired talents with source specializations, Force powers
and upgrade state, Force Rating, total/available/reserved XP, Morality
value and Conflict history, Obligation/Duty values and types,
`latent_force_sensitive` and `force_rejected_count`.

**Narrative state:** Advancement log (what changed and when), NPC
relationship summaries (one-paragraph distillations of significant
relationships), world state variables (butterfly-effect booleans),
throughline question history, character voice notes evolved through play.

**Not exported:** Turn-level history (compressed to act summaries),
full NPC state cards (compressed to relationship summaries), campaign-
specific arc state, session data.

### 6.2 What the Import Interface Does

The receiving campaign spine's `import_interface` field (see
`ImportInterface` model in schema.py) specifies:

**Specialization mappings.** How each prior specialization maps onto
the new campaign context. Three outcomes: *continuity* (remains fully
active), *dormancy* (inactive but retained — can be reactivated by
narrative trigger), *evolution* (maps to a related specialization in
the new context, preserving overlapping talent progress).

**Motivation track transition.** Whether the primary track changes
(e.g., Obligation → Morality when a smuggler accepts Force awakening),
and what happens to existing track values.

**XP rebalancing.** The `target_xp_range` defines minimum and maximum
total XP for incoming characters. Below minimum: bonus XP awarded
(representing off-screen growth during inter-campaign time skip).
Above maximum: no XP removed.

**Equipment transition.** The `imported_loadout` replaces the prior
campaign's gear, reflecting new circumstances. Prior special items
can be carried forward by including them in the imported loadout.

**Transition framing.** Guidance text for the cloud GM's transition
passage generation (Game Mechanics §20.3).

### 6.3 Default State

Any field not present in the import package receives a default from
`saga_metadata.default_state_for_new_characters`. The spine must work
for both imported and new characters. Defaults produce a character
indistinguishable from a fresh start.

**The Game Engine doesn't know the difference.** It receives a character
data dict. Whether that dict was populated by import or by defaults is
invisible to the Engine.

---

## 7. Database Additions

The Campaign Studio extends the shared SQLite database.

```sql
CREATE TABLE IF NOT EXISTS campaigns (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    era TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    authoring_mode TEXT NOT NULL,
    spine_json TEXT NOT NULL,
    validation_report TEXT,
    prior_campaign_id TEXT,
    FOREIGN KEY (prior_campaign_id) REFERENCES campaigns(id)
);

CREATE TABLE IF NOT EXISTS saga_runs (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    config_json TEXT NOT NULL,
    persona_assignments TEXT,
    directions_generated INTEGER,
    sketches_generated INTEGER,
    drafts_generated INTEGER,
    selected_spine_id TEXT,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
);

CREATE TABLE IF NOT EXISTS spine_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    saga_run_id TEXT NOT NULL,
    spine_a_json TEXT NOT NULL,
    spine_b_json TEXT NOT NULL,
    evaluation_json TEXT NOT NULL,
    evaluator_model TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (saga_run_id) REFERENCES saga_runs(id)
);

-- Gap Analysis v2.0: Pairwise comparison training data for local evaluator (item 4.9)
CREATE TABLE IF NOT EXISTS evaluation_pairs (
    pair_id TEXT PRIMARY KEY,
    spine_a_id TEXT NOT NULL,
    spine_b_id TEXT NOT NULL,
    spine_a_summary TEXT NOT NULL,
    spine_b_summary TEXT NOT NULL,
    axis TEXT NOT NULL,                -- 'structural' | 'novelty' | 'diversity'
    winner TEXT NOT NULL,              -- 'a' | 'b' | 'tie'
    confidence FLOAT,
    reasoning TEXT,
    source TEXT NOT NULL,              -- 'cloud_stage5' | 'player_rating'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Gap Analysis v2.0: Per-run diversity metrics for Bitter Lesson monitoring (item 4.10)
CREATE TABLE IF NOT EXISTS saga_diversity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    saga_run_id TEXT NOT NULL,
    models_used TEXT NOT NULL,          -- JSON array of model strings
    unique_conflict_types INTEGER,
    unique_thematic_elements INTEGER,
    pairwise_diversity_mean FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (saga_run_id) REFERENCES saga_runs(id)
);
```

---

## 8. Configuration

```bash
# .env additions for Campaign Studio
SAGA_NUM_WRITERS=5
SAGA_DIRECTIONS_PER_WRITER=2
SAGA_SEARCH_DEPTH=3
SAGA_DEBATE_ROUNDS=2
SAGA_TOP_K=3
PERSONA_POOL_PATH=data/personas/writer_room_personas.json
EVALUATOR_BACKEND=cloud                 # cloud | local | ensemble (item 4.9)
EVALUATOR_MODEL=                        # local model for trained evaluator
# Multi-model ensemble (item 4.10) — optional, default single-model
ENSEMBLE_ENABLED=false
ENSEMBLE_ASSIGNMENT=round_robin         # round_robin | weighted | random
# Model pool configured in studio/saga/ensemble.py DEFAULT_MODEL_POOL
```

---

## 9. Interaction with Game Engine

### 9.1 The Contract

The campaign spine JSON is the only runtime dependency between the two
systems. The Campaign Studio produces it; the Game Engine consumes it.

**Campaign Studio guarantees:** Every spine passes all four validation
gates before being stored.

**Game Engine guarantees:** The engine loads any spine that passes
Pydantic validation. It does not re-run the Studio's validation suite.

### 9.2 Shared Infrastructure

| Component | How shared |
|---|---|
| SQLite database | Same file — Studio adds its own tables |
| Ollama client | Same connection — never simultaneous |
| OpenRouter client | Same SDK, same API key |
| Configuration (.env) | Same file — Studio vars prefixed with `SAGA_` |
| Data directory | `data/campaigns/` holds all spines |
| Talent trees | `data/talent_trees/` — Game Engine loads at runtime |
| Force powers | `data/force_powers/` — Game Engine loads at runtime |
| Canon profiles | `data/canon_profiles/` — referenced by spine NPC entries |

### 9.3 What Is NOT Shared

| Component | Game Engine | Campaign Studio |
|---|---|---|
| LLM prompts | `gm/prompts/` | `studio/prompts/` |
| API routes | `api/game_routes.py` | `api/studio_routes.py` |
| Core logic | `engine/`, `gm/` | `studio/` |
| Build phases | Phases 1–6 | Phases CS-1 through CS-4 |

---

## 10. Critical Implementation Rules

1. **A spine that fails validation never reaches the Game Engine.**

2. **The prior campaign is context for convergence, not input for
   divergence.** The completed campaign enters at Stage 4. It is NOT
   provided to Stage 2. Seeding does not recover knowledge partitioning
   (Research Catalogue Source 3).

3. **Personas must be ordinary, not narrative archetypes.** "A retired
   politician" works. "A creative storyteller" does not.

4. **The pipeline degrades gracefully.** Every configurable parameter
   works at 1.

5. **Validation is not optional.** Every code path that produces a
   spine ends with `validate_spine()`.

6. **The evaluator backend is swappable.** `cloud` or `local` via
   configuration.

---

## 11. Success Criteria — Campaign Studio Complete

1. Mode 3 spine passes all validation gates and plays in the Engine
2. Mode 2 spine from a thematic brief passes validation and plays
3. Character import works with NPC relationships and motivation tracks
4. Saga pipeline generates structurally distinct sequels across runs
5. Mode 1 generates playable spines from minimal input
6. No invalid spines can reach the Game Engine

---

## 12. Revision History

**v1.3 — Design gap analysis v2.0 integration (March 2026)**

Schema, deliverable, and infrastructure updates from Gap Analysis v1.1
and v2.0. Key changes:

1. **Two new Pydantic models added.** `FactionSpec` (item 2.11 —
   faction_id, disposition/influence/awareness starts, per_act_drift)
   and `GenerationMetadata` (item 3.26 — master_seed, stage_seeds,
   model_used, generation_mode, timestamp).

2. **`CampaignSpine` extended.** New fields: `factions: list[FactionSpec]`
   (default empty), `generation_metadata: Optional[GenerationMetadata]`
   (default None).

3. **Saga layer configuration models added.** `SagaConfig` (evaluator
   backend, writer count, ensemble settings, search depth, debate
   rounds) and `RunDiversityMetrics` (models used, conflict types,
   thematic elements, pairwise diversity mean) added to §5.

4. **Gate 1 validation expanded.** New checks: faction_id uniqueness,
   per_act_drift key validity, social_connections NPC reference
   resolution.

5. **Gate 4 extended.** Difficulty calibration (item 3.27) integrated
   as a pure-Python component of Gate 4: four-signal per-act scoring,
   SpineDifficultyCurve, curve shape classification, calibration
   warnings. Runs even when Gate 4 LLM checks are skipped.

6. **Repository structure updated.** New files: `studio/seeding.py`,
   `studio/difficulty.py`, `studio/saga/ensemble.py`,
   `studio/saga/evaluator.py`, `studio/prompts/npc_voice_gen.txt`.
   `data/personas/pool.json` renamed to
   `data/personas/writer_room_personas.json`. Added
   `data/evaluation_pairs/`.

7. **CS-2 deliverables expanded.** Added `studio/seeding.py`,
   `studio/difficulty.py`, `studio/prompts/npc_voice_gen.txt`.
   Success criteria updated for seeding partial regeneration.

8. **CS-4 deliverables expanded.** Added `studio/saga/ensemble.py`,
   `studio/saga/evaluator.py`. Persona pool filename and count
   specified (55 across 11 clusters). Saga test artifact template
   referenced. Post-CS-4 local evaluator training documented.

9. **Database additions.** Two new tables: `evaluation_pairs` (pairwise
   comparison training data for local evaluator, item 4.9) and
   `saga_diversity_log` (per-run metrics for ensemble monitoring,
   item 4.10).

10. **Configuration updated.** Persona pool path corrected. Ensemble
    settings added (ENSEMBLE_ENABLED, ENSEMBLE_ASSIGNMENT).

**v1.2 — Game Mechanics v1.5 spine schema expansion (March 2026)**

Major schema update aligning the campaign spine interface contract with
nine new Game Mechanics Document sections (14–22). Key changes:

1. **15 new Pydantic models added.** `Loadout` (with `WeaponEntry`,
   `ArmorEntry`, `ToolEntry`, `SpecialItem`), `ForcePowerStart`,
   `BonusCondition`, `MilestoneWindow`, `Vignette` (with
   `VignetteChoice`), `TimeSkip`, `Ship` (with `ShipWeapon`),
   `ImportInterface` (with `SpecializationMapping`), `CanonVoice`,
   `CanonRelationshipDynamics`, `CanonActOverride`.

2. **`CharacterVariant` extended.** New fields: `starting_loadout`
   (Loadout), `starting_force_powers` (list of ForcePowerStart),
   `starting_xp` (int).

3. **`Act` extended.** New fields: `xp_base` (int, default 15),
   `xp_bonus_conditions` (list of BonusCondition),
   `time_skip_after` (optional TimeSkip — contains vignette library),
   `milestone_windows` (list of MilestoneWindow).

4. **`NPC` extended for canon characters.** New fields: `canon` (bool),
   `era_profile` (str), `canon_voice` (CanonVoice),
   `relationship_dynamics` (CanonRelationshipDynamics),
   `era_specific_notes` (str), `anti_stereotype_notes` (str),
   `act_overrides` (dict of act → CanonActOverride).

5. **`CampaignSpine` extended.** New fields: `vehicle_registry`
   (list of Ship), `force_discovery_probability` (float),
   `force_discovery_window` (tuple), `force_discovery_trigger` (str),
   `import_interface` (ImportInterface).

6. **Gate 1 validation expanded.** New checks for: Force-sensitive
   variant Force power presence, Force discovery window range, vignette
   NPC focus resolution, XP base positivity, canon NPC profile
   completeness, vehicle ID uniqueness, import interface range validity.

7. **Section 6 expanded.** Cross-era import interface rewritten with
   full import package specification, specialization mapping types
   (continuity/dormancy/evolution), XP rebalancing, equipment
   transition, and transition framing. References Game Mechanics §20.

8. **Shared infrastructure table updated.** New data directories:
   `data/talent_trees/`, `data/force_powers/`, `data/canon_profiles/`.

9. **Cross-references updated.** CS Design Document v1.3,
   Implementation Document v1.8.

**v1.1 — Character funnel pivot (March 2026)**

Schema model updates for the character funnel (Timeline → Allegiance →
Variant). Key changes:

1. **New `Allegiance` model.** Contains `id`, `display_name`, `description`,
   and nested `character_variants` list. Campaign spines now organize
   variants within allegiances.

2. **`CampaignSpine` updated.** Top-level `character_variants` replaced with
   `allegiances: list[Allegiance]` (min 2, max 4).

3. **`CharacterVariant` updated.** New fields: `allegiance` (str), `career_type`
   (str), `integration_layer` (IntegrationLayer). The integration layer
   connects the variant to the fixed thematic spine with entry point, personal
   stakes, NPC overrides, and anchor adaptations.

4. **New `IntegrationLayer` and `NPCOverride` models.** `IntegrationLayer`
   contains `entry_point`, `personal_stakes`, `npc_overrides` (dict of
   NPC name → NPCOverride), and `anchor_adaptations` (dict of anchor →
   narrative event).

5. **`PrologueSet` updated.** New fields: `career_type` (str), `allegiance`
   (str) for scene library matching.

6. **Validation Gate 1 updated.** New checks: allegiance-variant containment
   consistency, variant `allegiance` field matches containing allegiance `id`.

**v1.0 — Initial document (March 2026)**

Created from Campaign Studio Design Document (v1.2), LLM Evaluation
Document (v2.0), and Research Catalogue (v1.0). Specifies four build
phases, Pydantic schema models, validation suite, Mode 3/2/1 generation
paths, cross-era import interface, saga layer pipeline with intermediate
schemas, database additions, configuration, and interaction contract
with the Game Engine.

---

*Storyteller V3 — Campaign Studio Implementation Document v1.3*
*The system that creates the stories the Engine tells.*
