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


# ── Saga layer intermediate schemas ──────────────────────────────────


class SequelDirection(BaseModel):
    """Lightweight creative brief. Cheap to generate and evaluate."""
    throughline_question: str
    primary_conflict_type: str
    setting_description: str  # 1-2 sentences
    tone_shift: str           # How this differs from the prior campaign
    key_thematic_elements: list[str] = Field(min_length=3, max_length=5)
    denial_constraints_applied: list[str]


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


class EvaluationResult(BaseModel):
    structural_quality: float = Field(ge=0.0, le=1.0)
    novelty: float = Field(ge=0.0, le=1.0)
    diversity_vs_prior: float = Field(ge=0.0, le=1.0)
    composite: float = Field(ge=0.0, le=1.0)


class EvaluatedSpine(BaseModel):
    spine: "CampaignSpine"
    evaluation: EvaluationResult
    validation_report: dict


# ── Saga layer configuration (Gap Analysis v2.0) ─────────────────────


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
