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

from enum import Enum
from pydantic import BaseModel, Field, field_validator
from typing import Any, Optional, Union


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


class NarrativeArcSpec(BaseModel):
    """Brooks/Weiland inner-story fields for the protagonist (Apr 2026).

    Optional — the runtime renders identically when not present, but
    populated arcs unlock the LIE / TRUTH choice-pressure cue, the
    `lie_grip` scalar, and Gate 4 arc-coherence validation.
    """
    lie:       str = ""
    ghost:     str = ""
    truth:     str = ""
    want:      str = ""
    need:      str = ""
    arc_type:  str = "positive"   # positive | flat | disillusionment | fall | corruption
    lie_grip_initial: float = Field(ge=0.0, le=1.0, default=1.0)


class PartyDossier(BaseModel):
    """Compact GM/runtime handle for core party usage."""
    rpg_function: str = ""
    act1_player_feel: str = ""
    social_bond_arc: dict[str, str] = {}
    utility: str = ""
    best_case_ending_payoff: str = ""
    worst_case_ending_payoff: str = ""
    avoid: str = ""


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
    # ── Story architecture fields (CS-5) ──
    protagonist_contradiction: str = ""  # what they believe vs who they are
    pressure_revealed_identity: str = ""  # who they become under max pressure
    # ── CS-6 Story Engineering fields ──
    contradiction_origin: str = ""  # Phase 6: WHY the contradiction exists
    depth_card: Optional["CharacterDepthCard"] = None  # Phase 9: GM-facing enrichment (class defined below)
    # ── Brooks/Weiland fields (Apr 2026 pass) ──
    narrative_arc: Optional[NarrativeArcSpec] = None
    party_dossier: Optional[PartyDossier] = None
    # Campaigns may retain support variants for Studio analysis while only
    # exposing the authored protagonist in the live play funnel.
    player_selectable: bool = True
    intended_protagonist: bool = False
    supporting_only: bool = False
    selection_note: str = ""


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
    # ── Story architecture fields (CS-5) ──
    thematic_argument: str = ""  # what this NPC's existence argues about the theme
    # ── CS-6 Story Engineering fields ──
    pressure_role: str = ""  # Phase 4: "tempter", "mirror", "skeptic", "dependent",
                              # "betrayer", "witness", "escalator", "false_ally", "catalyst"
    party_dossier: Optional[PartyDossier] = None
    # ── Canon character fields (Game Mechanics §22) ──
    canon: bool = False
    era_profile: Optional[str] = None
    canon_voice: Optional[CanonVoice] = None
    relationship_dynamics: Optional[CanonRelationshipDynamics] = None
    era_specific_notes: Optional[str] = None
    anti_stereotype_notes: Optional[str] = None
    act_overrides: dict[str, CanonActOverride] = {}
    # ── World registry (engine/world_registry.py) ──
    # Location tokens where this NPC can plausibly be physically present.
    # Lowercase substrings matched against the current location ("praxeum",
    # "yavin", "off-world"). "*" = anywhere. Empty = unconstrained — the
    # runtime never blocks an NPC the spine doesn't constrain.
    location_domains: list[str] = []


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


# ── Pinch Points (CS-6 Phase 2) ──────────────────────────────────────


class PinchPoint(BaseModel):
    """
    A direct, unfiltered reminder of the antagonistic force.
    Not an encounter — a signal. Intercepted comms, a public
    execution, an NPC being punished, a rival's success shown
    directly.
    """
    description: str = Field(min_length=20)
    delivery_method: str = ""  # "intercepted_comm", "npc_report",
                                # "environmental", "direct_witness",
                                # "consequence_shown"
    target_progress: float = Field(
        ge=0.3, le=0.7, default=0.5
    )  # When in the act it should fire (0.5 = midpoint of the act)


# ── Acts ──────────────────────────────────────────────────────────────


class ActSideContent(BaseModel):
    """Optional scene beat available inside an act."""
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    hook: str = Field(min_length=20)
    keywords: list[str] = Field(min_length=1)
    phase: str = ""
    scene_type: str = ""
    spotlight: list[str] = []
    rpg_function: str = ""
    player_choice: str = ""
    payoff_or_change: str = ""
    foreshadows: list[str] = []


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
    expected_turns: Union[str, list[int]] = ""
    # ── Story architecture fields (CS-5) ──
    dramatic_function: str = ""  # setup, destabilization, launch, midpoint_shift,
                                 # escalation, confrontation, consequence, resolution
    # ── New fields (Game Mechanics v1.5) ──
    xp_base: int = Field(ge=0, default=15)
    xp_bonus_conditions: list[BonusCondition] = []
    xp_config: Optional[dict[str, Any]] = None  # alternative XP format
    destiny_dark_trigger: bool = False
    seize_the_moment: bool = False
    time_skip: Optional[dict[str, Any]] = None  # inline time skip data
    time_skip_after: Optional[TimeSkip] = None  # skip between this act
                                                 # and the next
    milestone_windows: list[MilestoneWindow] = []
    # ── CS-6 Story Engineering fields ──
    pinch_point: Optional[PinchPoint] = None  # Phase 2: antagonist pressure beat
    protagonist_mode: str = ""  # Phase 3: "orphan"|"wanderer"|"warrior"|"martyr"
    beat_roles: list[str] = []
    side_content: list[ActSideContent] = []
    # ── World registry (engine/world_registry.py) ──
    # Named places this act moves through beyond opening_location
    # ("the meditation hall", "sealed Massassi stairs"). Feeds location
    # validation (proposed locations grounded against this vocabulary)
    # and scene-location inference from narration text.
    location_vocabulary: list[str] = []


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


# ── Story Engineering models (CS-6) ──────────────────────────────────


class MilestoneBeatSheet(BaseModel):
    """
    Brooks's five structural milestones mapped onto the campaign spine.
    Each milestone is a one-sentence description of the dramatic moment,
    NOT a plot summary. It describes what changes and why it matters.
    """
    concept_question: str = Field(
        min_length=10,
        description=(
            "The 'what if?' question that makes this campaign a story, "
            "not just a setting. Format: 'What if [dramatic proposition]?'"
        )
    )
    first_plot_point: str = Field(
        min_length=20,
        description=(
            "The moment that changes everything — the protagonist's "
            "quest begins in earnest."
        )
    )
    first_plot_point_act: int = Field(ge=1)

    midpoint: str = Field(
        min_length=20,
        description=(
            "A revelation or reversal that shifts the protagonist from "
            "responder to attacker."
        )
    )
    midpoint_act: int = Field(ge=1)

    second_plot_point: str = Field(
        min_length=20,
        description=(
            "The LAST piece of new information in the story. After "
            "this, no new expository facts may enter."
        )
    )
    second_plot_point_act: int = Field(ge=1)

    pre_resolution_lull: str = ""  # Optional all-hope-is-lost beat


class ProtagonistMode(str, Enum):
    """Brooks's four-stage character arc mapped to sequential acts."""
    ORPHAN = "orphan"
    WANDERER = "wanderer"
    WARRIOR = "warrior"
    MARTYR = "martyr"


class ForeshadowLink(BaseModel):
    """
    A deliberate setup → payoff pair. The setup is planted early;
    the payoff arrives later.
    """
    id: str = Field(min_length=1)
    setup_act: int = Field(ge=1)
    setup_description: str = Field(min_length=10)
    payoff_act: int = Field(ge=1)
    payoff_description: str = Field(min_length=10)
    payoff_type: str = ""  # "revelation", "reversal", "callback", "irony"


class EndingPath(BaseModel):
    """
    A planned distinct ending for the campaign.

    branch_id must resolve to a variation_point option id so the
    climactic branch the runtime takes maps onto an authored ending.
    Authored by the architect (studio/architect.py), validated by
    Gate 4b against the generated spine's variation points.
    """
    name: str = Field(min_length=1)
    branch_id: str = Field(min_length=1)
    synopsis: str = ""
    thematic_payoff: str = ""
    carries_forward: bool = False  # does this ending feed a sequel import?


class CharacterDepthCard(BaseModel):
    """
    GM-facing character enrichment. Never shown to the player.
    Injected into the GM context for narration richness.
    """
    inner_demon: str = ""
    secret_yearning: str = ""
    lesson_not_learned: str = ""
    worst_act: str = ""
    social_mask: str = ""
    under_pressure: str = ""
    worldview: str = ""
    moral_line: str = ""


# CharacterVariant.depth_card forward-references CharacterDepthCard;
# resolve it now that the class exists so import fails loud, not at
# first instantiation.
CharacterVariant.model_rebuild()


# ── Bond Events (Trails-of-Cold-Steel-style relationship deepening) ──


class BondEvent(BaseModel):
    """
    Optional one-on-one scene that deepens a specific cohort relationship
    and weights the climax mechanically. Cohort survival in the final act
    is determined by accumulated bond_weight per character.

    The runtime engine offers a bond event when:
      - the act_window includes the current act
      - all prerequisites (bond ids) have fired
      - player drift matches keywords
    """
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    cohort_member: str = Field(min_length=1)
    act_window: tuple[int, int]
    prerequisites: list[str] = []
    hook: str = Field(min_length=20)
    keywords: list[str] = Field(min_length=1)
    choice_prompt: str = ""
    why_this_person: str = ""
    why_now: str = ""
    changes_after: str = ""
    subversion_payoff: str = ""
    bond_weight: float = Field(ge=0.0, le=1.0, default=0.0)
    branch_consequences: list[str] = []


class BondEventSystem(BaseModel):
    """Configuration for the bond-event runtime."""
    purpose: str = ""
    selection_model: str = ""
    act_budgets: dict[str, int] = {}
    priority_relationships: list[str] = []
    ending_weight_notes: dict[str, str] = {}
    bond_weight_threshold_for_climax_protection: float = Field(
        ge=0.0, le=1.0, default=0.6
    )
    max_bond_weight_per_relationship: float = Field(
        ge=0.0, le=2.0, default=1.0
    )
    stacking: str = "additive"  # "additive" | "max" | "replace"


class BondPacingAct(BaseModel):
    """Offer priorities for bond events that enter play in one act."""
    act: int = Field(ge=1)
    max_one_on_one_offers: int = Field(ge=0)
    required_story: list[str] = []
    priority_pool: list[str] = []
    optional_pool: list[str] = []
    rare_pool: list[str] = []
    guidance: str = ""


class BondPacingMatrix(BaseModel):
    """Pacing/pruning layer for a large relationship-scene library."""
    policy: str = ""
    recommended_playthrough_target: list[int] = []
    hard_cut_ids: list[str] = []
    no_cut_reason: str = ""
    act_plans: list[BondPacingAct] = []


class CorePartyMember(BaseModel):
    """Player-facing party member focus for social-RPG campaign structure."""
    name: str = Field(min_length=1)
    npc_ref: str = Field(min_length=1)
    party_role: str = ""
    table_function: str = ""
    relationship_axis: str = ""
    player_facing_question: str = ""
    primary_payoff: str = ""
    bond_priority: int = Field(ge=1, le=5, default=3)
    act_focus: list[int] = []


class SupportingCastTier(BaseModel):
    """Cast triage so the runtime knows who may stay in the background."""
    tier: str = Field(min_length=1)
    purpose: str = ""
    members: list[str] = []


class BondActPlan(BaseModel):
    """Per-act free-time/bonding budget."""
    act: int = Field(ge=1)
    slots: int = Field(ge=0)
    required_story_bonds: list[str] = []
    optional_party_bonds: list[str] = []
    guest_bonds: list[str] = []
    group_scene_ids: list[str] = []
    pacing_note: str = ""


class GroupScene(BaseModel):
    """Recurring party scene that builds group texture, not just one-on-one bonds."""
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    act: int = Field(ge=1)
    scene_type: str = ""
    participants: list[str] = Field(min_length=2)
    hook: str = Field(min_length=20)
    function: str = ""
    bond_payoffs: list[str] = []


class EndingPayoff(BaseModel):
    """How a resolution converts relationship state into emotional closure."""
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    ending_type: str = ""
    requires: list[str] = []
    relationship_payoffs: dict[str, str] = {}
    emotional_contract: str = ""
    future_hook: str = ""
    avoid_feeling: str = ""


# ── Story architecture (CS-5) ────────────────────────────────────────


VALID_PRESSURE_TYPES = (
    "moral", "identity", "loyalty", "survival", "ideological",
)

VALID_DRAMATIC_FUNCTIONS = (
    "setup", "destabilization", "launch", "midpoint_shift",
    "escalation", "confrontation", "consequence", "resolution",
)

# Structural beat roles an act can carry (Act.beat_roles). Ordered by
# typical story position — acts carry 1-3 roles consistent with their
# dramatic_function.
VALID_BEAT_ROLES = (
    "setup", "inciting", "response", "false_progress", "first_plot_point",
    "pinch1", "midpoint", "pinch2", "second_plot_point", "attack",
    "confrontation", "climax", "resolution", "aftermath", "consequence",
)


class StoryArchitecture(BaseModel):
    """Pre-generation narrative design brief.

    Captures the dramatic architecture that the spine should embody.
    Generated by studio/architect.py before spine generation, then
    validated against the resulting spine by Gate 4b.
    """
    dramatic_premise: str = Field(min_length=20)
    central_dramatic_question: str
    story_promise: str = Field(min_length=20)
    protagonist_pressure_type: str
    antagonistic_force: str = Field(min_length=20)
    thematic_throughline: str = Field(min_length=10)
    ending_payoff_sketch: str = ""
    # ── CS-6 Story Engineering fields ──
    milestone_beat_sheet: Optional[MilestoneBeatSheet] = None  # Phase 3
    # ── Studio enrichment generation (Jun 2026) ──
    # Planned setup → payoff pairs the generated acts must respect.
    # Surfaced into the spine-level foreshadow_registry by generate.py.
    foreshadow_registry: list[ForeshadowLink] = []
    # 2-4 planned distinct endings; each branch_id must resolve to a
    # variation_point option id in the generated spine (Gate 4b).
    ending_paths: list[EndingPath] = []

    @field_validator("protagonist_pressure_type")
    @classmethod
    def valid_pressure_type(cls, v: str) -> str:
        if v and v not in VALID_PRESSURE_TYPES:
            raise ValueError(
                f"Invalid pressure type '{v}'. "
                f"Must be one of: {', '.join(VALID_PRESSURE_TYPES)}"
            )
        return v

    @field_validator("central_dramatic_question")
    @classmethod
    def cdq_is_question(cls, v: str) -> str:
        if v and not v.strip().endswith("?"):
            raise ValueError("central_dramatic_question must end with '?'")
        return v


# ── Top-level spine ───────────────────────────────────────────────────


class EraVoice(BaseModel):
    """Star Wars era anchoring for narration prompts.

    Each Star Wars era has its own technology level, political reality,
    and prose register. When a spine declares an era_voice, the narration
    GM gets period-specific instructions to keep prose anchored. Optional —
    the campaign-level Star Wars guidance still applies when omitted.
    """
    era:            str = ""        # canonical era name (e.g. "Imperial Era")
    year:           str = ""        # ABY/BBY date (e.g. "5 BBY")
    voice_notes:    str = ""        # 1-3 sentences of tone guidance for the era
    period_details: list[str] = []  # weave-in cues (Empire is ascendant, Rebellion is whispered)
    period_avoid:   list[str] = []  # anachronisms to avoid (Sequel-era tech in Imperial setting)


class CampaignSpine(BaseModel):
    """Top-level campaign spine — the interface contract."""
    name: str
    era: str
    total_acts: int = Field(ge=2)
    throughline_question: str
    intended_protagonist_id: str = ""
    core_party: list[CorePartyMember] = []
    supporting_cast_tiers: list[SupportingCastTier] = []
    bond_act_plan: list[BondActPlan] = []
    bond_pacing_matrix: Optional[BondPacingMatrix] = None
    group_scenes: list[GroupScene] = []
    ending_payoff_matrix: list[EndingPayoff] = []
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
    # ── Story architecture (CS-5) ──
    story_architecture: Optional[StoryArchitecture] = None
    # ── CS-6 Story Engineering fields ──
    foreshadow_registry: list[ForeshadowLink] = []  # Phase 5
    # ── Star Wars era voice anchoring ──
    era_voice: Optional[EraVoice] = None
    # ── Bond-event runtime (Trails-of-Cold-Steel pattern) ──
    bond_events: list[BondEvent] = []
    bond_event_system: Optional[BondEventSystem] = None
    # ── Runtime visibility ──
    # When False the campaign is hidden from the player-facing picker
    # (GET /campaigns) but stays loadable for tests, reference, and direct
    # session creation. Generated campaigns default True; archived
    # hand-authored campaigns set this False.
    player_facing: bool = True

    @field_validator("acts")
    @classmethod
    def acts_sequential(cls, v: list[Act]) -> list[Act]:
        for i, act in enumerate(v):
            if act.number != i + 1:
                raise ValueError(
                    f"Act {i+1} has number {act.number}"
                )
        return v
