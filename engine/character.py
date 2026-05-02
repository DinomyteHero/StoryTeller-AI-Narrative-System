from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from engine.equipment import Loadout


class GameLine(Enum):
    EDGE_OF_EMPIRE    = "edge_of_empire"
    AGE_OF_REBELLION  = "age_of_rebellion"
    FORCE_AND_DESTINY = "force_and_destiny"


class Species(Enum):
    HUMAN    = "human"
    BOTHAN   = "bothan"
    TWIL_EK  = "twi_lek"
    RODIAN   = "rodian"
    WOOKIEE  = "wookiee"
    ZABRAK   = "zabrak"
    TOGRUTA  = "togruta"
    NAUTOLAN = "nautolan"
    MIRIALAN = "mirialan"
    DROID    = "droid"


class Career(Enum):
    # Edge of the Empire
    BOUNTY_HUNTER = "bounty_hunter"
    COLONIST      = "colonist"
    EXPLORER      = "explorer"
    HIRED_GUN     = "hired_gun"
    SMUGGLER      = "smuggler"
    TECHNICIAN    = "technician"
    # Age of Rebellion
    ACE       = "ace"
    COMMANDER = "commander"
    DIPLOMAT  = "diplomat"
    ENGINEER  = "engineer"
    SOLDIER   = "soldier"
    SPY       = "spy"
    # Force and Destiny
    CONSULAR = "consular"
    GUARDIAN = "guardian"
    MYSTIC   = "mystic"
    SEEKER   = "seeker"
    SENTINEL = "sentinel"
    WARRIOR  = "warrior"
    # Phase 24 — pre-crystallization Praxeum student state
    PRAXEUM_STUDENT = "praxeum_student"
    JEDI_STUDENT    = "jedi_student"


# Pre-crystallization sentinel values. The narration prompt branches on these
# to write the protagonist as "becoming," not "being." Crystallization moves
# the character to one of the F&D careers (Guardian / Consular / Sentinel).
PRE_CRYSTALLIZATION_CAREERS = (Career.PRAXEUM_STUDENT, Career.JEDI_STUDENT)


class Characteristics(BaseModel):
    brawn:    int = Field(ge=1, le=6, default=2)
    agility:  int = Field(ge=1, le=6, default=2)
    intellect:int = Field(ge=1, le=6, default=2)
    cunning:  int = Field(ge=1, le=6, default=2)
    willpower:int = Field(ge=1, le=6, default=2)
    presence: int = Field(ge=1, le=6, default=2)


class SkillRanks(BaseModel):
    # General
    astrogation:       int = Field(ge=0, le=5, default=0)
    athletics:         int = Field(ge=0, le=5, default=0)
    charm:             int = Field(ge=0, le=5, default=0)
    coercion:          int = Field(ge=0, le=5, default=0)
    computers:         int = Field(ge=0, le=5, default=0)
    cool:              int = Field(ge=0, le=5, default=0)
    coordination:      int = Field(ge=0, le=5, default=0)
    deception:         int = Field(ge=0, le=5, default=0)
    discipline:        int = Field(ge=0, le=5, default=0)
    leadership:        int = Field(ge=0, le=5, default=0)
    mechanics:         int = Field(ge=0, le=5, default=0)
    medicine:          int = Field(ge=0, le=5, default=0)
    negotiation:       int = Field(ge=0, le=5, default=0)
    perception:        int = Field(ge=0, le=5, default=0)
    piloting_planetary:int = Field(ge=0, le=5, default=0)
    piloting_space:    int = Field(ge=0, le=5, default=0)
    resilience:        int = Field(ge=0, le=5, default=0)
    skulduggery:       int = Field(ge=0, le=5, default=0)
    stealth:           int = Field(ge=0, le=5, default=0)
    streetwise:        int = Field(ge=0, le=5, default=0)
    survival:          int = Field(ge=0, le=5, default=0)
    vigilance:         int = Field(ge=0, le=5, default=0)
    # Combat
    brawl:       int = Field(ge=0, le=5, default=0)
    gunnery:     int = Field(ge=0, le=5, default=0)
    melee:       int = Field(ge=0, le=5, default=0)
    ranged_light:int = Field(ge=0, le=5, default=0)
    ranged_heavy:int = Field(ge=0, le=5, default=0)
    # Knowledge
    core_worlds:int = Field(ge=0, le=5, default=0)
    education:  int = Field(ge=0, le=5, default=0)
    lore:       int = Field(ge=0, le=5, default=0)
    outer_rim:  int = Field(ge=0, le=5, default=0)
    underworld: int = Field(ge=0, le=5, default=0)
    warfare:    int = Field(ge=0, le=5, default=0)
    xenology:   int = Field(ge=0, le=5, default=0)
    # Force and Destiny
    lightsaber: int = Field(ge=0, le=5, default=0)


SKILL_CHARACTERISTICS: dict[str, str] = {
    "astrogation":        "intellect",
    "athletics":          "brawn",
    "charm":              "presence",
    "coercion":           "willpower",
    "computers":          "intellect",
    "cool":               "presence",
    "coordination":       "agility",
    "deception":          "cunning",
    "discipline":         "willpower",
    "leadership":         "presence",
    "mechanics":          "intellect",
    "medicine":           "intellect",
    "negotiation":        "presence",
    "perception":         "cunning",
    "piloting_planetary": "agility",
    "piloting_space":     "agility",
    "resilience":         "brawn",
    "skulduggery":        "cunning",
    "stealth":            "agility",
    "streetwise":         "cunning",
    "survival":           "cunning",
    "vigilance":          "willpower",
    "brawl":              "brawn",
    "gunnery":            "agility",
    "melee":              "brawn",
    "ranged_light":       "agility",
    "ranged_heavy":       "agility",
    "core_worlds":        "intellect",
    "education":          "intellect",
    "lore":               "intellect",
    "outer_rim":          "intellect",
    "underworld":         "intellect",
    "warfare":            "intellect",
    "xenology":           "intellect",
    "lightsaber":         "brawn",
}


class MotivationTrack(BaseModel):
    obligation_type:  Optional[str] = None
    obligation_value: int = 0
    duty_type:        Optional[str] = None
    duty_value:       int = 0
    morality:         int = 50
    conflict:         int = 0


class Pronouns(BaseModel):
    """Player-chosen pronouns (Phase 24 — character creation redesign).

    The frontload offers 7 CoG-style options plus custom; the values are
    stored verbatim here so the narration model uses what the player typed.
    """
    subject:    str = "they"   # she / he / they / custom
    object:     str = "them"   # her / him / them / custom
    possessive: str = "their"  # her / his / their / custom


class NarrativeArc(BaseModel):
    """Brooks/Weiland character arc fields.

    The Lie is what the character believes wrongly about themselves or the world.
    The Ghost is the wound that planted it. The Truth is what the story will teach.
    Want is the external goal; Need is what the character actually requires inside.
    lie_grip (0..1) tracks how strongly the lie still rules — updated turn by turn
    by reconciliation from the per-turn contradiction movement signal.
    """
    lie:        str = ""
    ghost:      str = ""
    truth:      str = ""
    want:       str = ""
    need:       str = ""
    # positive | flat | disillusionment | fall | corruption
    arc_type:   str = "positive"
    lie_grip:   float = Field(ge=0.0, le=1.0, default=1.0)
    # Per-turn telemetry. Each entry: {turn, kind, weight, note}
    movements:  list[dict] = Field(default_factory=list)


class OpposedPair(BaseModel):
    """Zero-sum personality axis (Phase 25 §2.6).

    Each pair is a single 0-100 percentage. Gain in one pole reduces the
    other. pole_b_value is implicitly (100 - pole_a_value).

    Six standard axes for Star Wars campaigns:
      light_dark, lone_wolf_crew_loyalist, reckless_cautious,
      showy_quiet, direct_subtle, lawful_lawless

    `last_cue` is the most recent narration cue surfaced for hover.
    """
    pair_id:      str
    pole_a_label: str
    pole_b_label: str
    pole_a_value: int = Field(ge=0, le=100, default=50)
    last_cue:     str = ""

    @property
    def pole_b_value(self) -> int:
        return 100 - self.pole_a_value

    def dominant_pole(self) -> str:
        if self.pole_a_value > 60:
            return self.pole_a_label
        if self.pole_a_value < 40:
            return self.pole_b_label
        return "balanced"


class BeliefCommitment(BaseModel):
    """A locked-in personality belief — populated by two paths.

    Phase 24 (prologue path, CoG-style): the psychometric prologue infers
    behavioral axes and produces commitments described as multi-clause
    first-person beliefs. Sets ``axis``, ``commitment_text``, ``stat_effects``.

    Phase 25 (anchor path, §2.5): the player explicitly picks a BeliefOption
    at a PersonalityLockMoment tied to a scene anchor. Sets ``anchor_id``,
    ``belief_text``, ``voice_tag``, ``locked_at_turn``.

    Both paths write into ``Character.personality_locks``; either set of
    fields may be empty depending on which path produced the lock.
    """
    # Phase 24 fields (prologue-derived)
    axis:            str = ""
    commitment_text: str = ""
    stat_effects:    dict[str, int] = Field(default_factory=dict)
    # Phase 25 fields (anchor-locked)
    anchor_id:       str = ""
    belief_text:     str = ""
    voice_tag:       str = ""
    locked_at_turn:  int = 0


DEFAULT_OPPOSED_PAIRS: list[tuple[str, str, str]] = [
    # (pair_id, pole_a_label, pole_b_label)
    # light_dark is *not* in this list because morality (0-100) on
    # MotivationTrack already represents that axis. Keeping it separate
    # avoids double-bookkeeping. The dashboard renders morality as the
    # "Light / Dark" axis alongside these five new ones.
    ("lone_wolf_crew_loyalist",  "Lone Wolf",  "Crew Loyalist"),
    ("reckless_cautious",         "Reckless",   "Cautious"),
    ("showy_quiet",               "Showy",      "Quiet"),
    ("direct_subtle",             "Direct",     "Subtle"),
    ("lawful_lawless",            "Lawful",     "Lawless"),
]


def default_personality_axes() -> list[OpposedPair]:
    """Build a fresh set of opposed-pair axes initialized to neutral 50/50.

    Phase 25 §2.6 — five Star Wars-flavored axes. Light/Dark lives on
    MotivationTrack.morality and is shown as a sixth axis on the dashboard.
    """
    return [
        OpposedPair(
            pair_id=pair_id,
            pole_a_label=pole_a,
            pole_b_label=pole_b,
            pole_a_value=50,
        )
        for (pair_id, pole_a, pole_b) in DEFAULT_OPPOSED_PAIRS
    ]


class Character(BaseModel):
    # Phase 24: name / species become optional — the prologue's diegetic
    # customization beats fill them if the player skipped refinement.
    name:               Optional[str]      = None
    species:            Optional[Species]  = None
    career:             Career             = Career.PRAXEUM_STUDENT
    specializations:    list[str]       = Field(default_factory=list)
    primary_game_line:  GameLine        = GameLine.EDGE_OF_EMPIRE
    # Phase 24: `background` now stores the background_id (e.g.
    # "outer_rim_refugee"). Free-text biographical seed lives in
    # `background_summary` so existing prose-rich character files remain
    # backward-compatible — the loader carries either form.
    background:         str             = ""
    background_summary: str             = ""
    gender:             Optional[str]   = None  # Phase 24: optional gender
    pronouns:           Optional[Pronouns] = None  # Phase 24: filled at refinement / prologue
    appearance_flair:   str             = ""  # Phase 24: optional flavor text
    characteristics:    Characteristics = Field(default_factory=Characteristics)
    skills:             SkillRanks      = Field(default_factory=SkillRanks)
    wound_threshold:    int = 0
    strain_threshold:   int = 0
    current_wounds:     int = 0
    current_strain:     int = 0
    soak:               int = 0
    total_xp:           int = 0
    available_xp:       int = 0
    motivation:         MotivationTrack = Field(default_factory=MotivationTrack)
    force_rating:       int = 0
    force_committed:    int = 0
    loadout:              Loadout = Field(default_factory=Loadout)  # Phase 9: equipment (Game Mechanics §18)
    career_skills:        list[str] = Field(default_factory=list)   # Phase 10: career + specialization skills (§14.2)
    reserved_xp:          int = 0                                   # Phase 10: XP banked for milestones (§14.2)
    advancement_log:      list[dict] = Field(default_factory=list)  # Phase 10: record of all advancement events (§14.2)
    acquired_talents:     list[dict] = Field(default_factory=list)  # Phase 11: acquired talent entries (§15)
    talent_uses:          dict[str, int] = Field(default_factory=dict)  # Phase 11: intervention usage per act (§15.1)
    force_powers:         list[dict] = Field(default_factory=list)      # Phase 15: acquired Force powers (§16.3)
    active_commitments:   list[dict] = Field(default_factory=list)      # Phase 15: committed Force dice (§16.5)
    throughline_question: str = ""
    voice_notes:          str = ""
    active_injuries:      list[str] = Field(default_factory=list)  # narrative injury descriptions (Game Mechanics §3)
    narrative_arc:        Optional[NarrativeArc] = None  # Brooks/Weiland arc — opt-in
    # ── Phase 24: Character Creation Redesign ──
    behavioral_archetype: Optional[str] = None  # inferred archetype from prologue
    skill_tilt:           dict[str, int] = Field(default_factory=dict)  # background tilt + archetype adjustment
    crystallized:         bool = False  # True after profession crystallization beat
    # Counter dict tracking pattern-of-use for Mechanism-3 talent unlocks.
    # Keys are pattern_ids (e.g. "consular_influence_uses"), values are int counts.
    use_pattern_counts:   dict[str, int] = Field(default_factory=dict)
    # ── Phase 25 runtime experience fields ──
    personality_axes:     list[OpposedPair] = Field(default_factory=list)       # §2.6
    # personality_locks is shared by both Phase 24 (prologue-derived,
    # axis-based) and Phase 25 (anchor-locked from PersonalityLockMoment).
    # The unified BeliefCommitment carries fields for both paths.
    personality_locks:    list[BeliefCommitment] = Field(default_factory=list)  # §2.5
    codex_read:           list[str] = Field(default_factory=list)               # entry_ids
    achievements_earned:  list[str] = Field(default_factory=list)               # achievement_ids
    achievement_progress: dict[str, int] = Field(default_factory=dict)          # achievement_id → count
    relationship_slot_assignments: dict[str, str] = Field(default_factory=dict)  # slot_idx → npc_name

    def get_characteristic(self, name: str) -> int:
        return getattr(self.characteristics, name)

    def get_skill_rank(self, skill_name: str) -> int:
        return getattr(self.skills, skill_name, 0)

    def is_incapacitated(self) -> bool:
        return self.current_wounds >= self.wound_threshold

    def effective_soak(self) -> int:
        """Total soak: base soak (Brawn) + armor soak bonus (§18)."""
        armor_bonus = self.loadout.armor.soak_bonus if self.loadout.armor else 0
        return self.soak + armor_bonus

    def is_pre_crystallization(self) -> bool:
        """True when the protagonist has not yet committed to a discipline.

        Pre-crystallization characters narrate as 'becoming,' not 'being';
        their specialization tree is closed; the narration prompt receives
        a flag to write them as a Praxeum student.
        """
        return (
            self.career in PRE_CRYSTALLIZATION_CAREERS
            and not self.crystallized
        )

    def display_name(self) -> str:
        return self.name or "the protagonist"

    def display_species(self) -> str:
        if self.species is None:
            return "Unknown"
        return self.species.value.replace("_", " ").title()

    def display_career(self) -> str:
        if self.is_pre_crystallization():
            return "Jedi Praxeum Student"
        return self.career.value.replace("_", " ").title()

    def find_axis(self, pair_id: str) -> Optional["OpposedPair"]:
        """Look up a personality axis by its pair_id."""
        for axis in self.personality_axes:
            if axis.pair_id == pair_id:
                return axis
        return None

    def adjust_axis(self, pair_id: str, delta: int, cue: str = "") -> bool:
        """Apply a clamped delta to pole_a_value of a personality axis.

        Returns True if a delta was applied (axis exists and delta != 0).
        Stores the cue string for hover display in the dashboard.
        """
        axis = self.find_axis(pair_id)
        if axis is None or delta == 0:
            return False
        axis.pole_a_value = max(0, min(100, axis.pole_a_value + delta))
        if cue:
            axis.last_cue = cue
        return True

    def has_personality_lock_for(self, anchor_id: str) -> bool:
        return any(lock.anchor_id == anchor_id for lock in self.personality_locks)

    def add_personality_lock(
        self, anchor_id: str, belief_text: str, voice_tag: str = "",
        locked_at_turn: int = 0,
    ) -> None:
        """Persist a chosen BeliefOption.

        Idempotent — re-locking the same anchor replaces the prior belief.
        """
        # remove any pre-existing lock for this anchor
        self.personality_locks = [
            lock for lock in self.personality_locks
            if lock.anchor_id != anchor_id
        ]
        self.personality_locks.append(BeliefCommitment(
            anchor_id=anchor_id,
            belief_text=belief_text,
            voice_tag=voice_tag,
            locked_at_turn=locked_at_turn,
        ))

    def narrative_status(self) -> str:
        lines = [
            f"{self.display_name()} | "
            f"{self.display_species()} "
            f"{self.display_career()}",
            f"Wounds: {self.current_wounds}/{self.wound_threshold} | "
            f"Strain: {self.current_strain}/{self.strain_threshold} | "
            f"Soak: {self.effective_soak()}",
        ]
        if self.is_pre_crystallization():
            lines.append(
                "Pre-crystallization — discipline not yet committed. "
                "Narrate as becoming, not being."
            )
        if self.behavioral_archetype:
            lines.append(f"Behavioral archetype: {self.behavioral_archetype}")
        if self.active_injuries:
            lines.append(f"Injuries: {'; '.join(self.active_injuries)}")
        if self.motivation.obligation_value > 0:
            lines.append(
                f"Obligation: {self.motivation.obligation_value} "
                f"({self.motivation.obligation_type})"
            )
        if self.motivation.duty_value > 0:
            lines.append(
                f"Duty: {self.motivation.duty_value} "
                f"({self.motivation.duty_type})"
            )
        if self.force_rating > 0:
            lines.append(
                f"Force Rating: {self.force_rating} | "
                f"Morality: {self.motivation.morality}"
            )
        return "\n".join(lines)
