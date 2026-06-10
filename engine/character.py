from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum
from engine.equipment import Loadout


class GameLine(Enum):
    EDGE_OF_EMPIRE    = "edge_of_empire"
    AGE_OF_REBELLION  = "age_of_rebellion"
    FORCE_AND_DESTINY = "force_and_destiny"


# NOTE: As of the freeform-archetype work, ``Character.species`` and
# ``Character.career`` are free-form strings, not these enums. The enum
# classes are KEPT as (a) a back-compat input path — passing ``Species.HUMAN``
# still works, it is coerced to ``"human"`` — and (b) a reference set of
# canonical FFG values for soft validation / suggestion UIs. New freeform
# archetypes may use any string (e.g. ``"kel_dor"``, ``"ex-imperial slicer"``).
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


# Canonical species reference sets (membership = "is a known FFG species").
KNOWN_SPECIES: frozenset[str] = frozenset(s.value for s in Species)
KNOWN_CAREERS: frozenset[str] = frozenset(c.value for c in Career)


# Per-species base thresholds: wound/strain threshold = base + Brawn/Willpower.
# Used by the character creator to recompute derived stats deterministically
# rather than trusting LLM-supplied numbers. Unknown/freeform species fall
# back to DEFAULT_THRESHOLDS.
SPECIES_THRESHOLDS: dict[str, tuple[int, int]] = {
    # species: (wound_base, strain_base)
    "human":    (10, 10),
    "bothan":   (10, 11),
    "twi_lek":  (10, 11),
    "rodian":   (10, 10),
    "wookiee":  (14,  8),
    "zabrak":   (10, 10),
    "togruta":  (10, 10),
    "nautolan": (11, 10),
    "mirialan": (10, 11),
    "droid":    (10, 10),
}
DEFAULT_THRESHOLDS: tuple[int, int] = (10, 10)

# Per-species starting XP budget. Freeform/unknown species use the default.
SPECIES_START_XP: dict[str, int] = {
    "human":   110,
    "wookiee":  90,
    "droid":   100,
}
DEFAULT_START_XP: int = 100


def species_thresholds(species: str) -> tuple[int, int]:
    """(wound_base, strain_base) for a species string; default if unknown."""
    return SPECIES_THRESHOLDS.get(str(species).lower(), DEFAULT_THRESHOLDS)


def species_start_xp(species: str) -> int:
    """Starting XP budget for a species string; default if unknown."""
    return SPECIES_START_XP.get(str(species).lower(), DEFAULT_START_XP)


def _label(value) -> str:
    """Human-readable label for a species/career that may be a str or Enum."""
    raw = value.value if isinstance(value, Enum) else str(value)
    return raw.replace("_", " ").title()


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


class Character(BaseModel):
    name:               str
    # Free-form strings (was Species/Career enums). Enum members passed as
    # input are coerced to their .value by _coerce_identity below, so legacy
    # callers using Species.HUMAN / Career.SMUGGLER keep working.
    species:            str
    career:             str
    # Optional free player-facing identity concept, e.g.
    # "Ex-Imperial loadmaster turned reluctant courier". When set, it is the
    # label shown in narrative_status; otherwise the career label is used.
    archetype_concept:  str             = ""
    specializations:    list[str]       = Field(default_factory=list)
    primary_game_line:  GameLine        = GameLine.EDGE_OF_EMPIRE
    background:         str             = ""
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
    # Per-character freeform talent definitions, keyed by talent_ref, each in
    # the same shape as an entry in data/talent_trees/talent_library.json.
    # These shadow/extend the global library so LLM-authored "signature"
    # talents resolve through engine.talents.resolve_talent_defn().
    custom_talents:       dict[str, dict] = Field(default_factory=dict)
    throughline_question: str = ""
    voice_notes:          str = ""
    active_injuries:      list[str] = Field(default_factory=list)  # narrative injury descriptions (Game Mechanics §3)
    narrative_arc:        Optional[NarrativeArc] = None  # Brooks/Weiland arc — opt-in

    @field_validator("species", "career", mode="before")
    @classmethod
    def _coerce_identity(cls, v):
        """Accept Species/Career enum members (legacy callers) as their value."""
        return v.value if isinstance(v, Enum) else v

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

    def narrative_status(self) -> str:
        identity = self.archetype_concept.strip() or _label(self.career)
        lines = [
            f"{self.name} | "
            f"{_label(self.species)} "
            f"{identity}",
            f"Wounds: {self.current_wounds}/{self.wound_threshold} | "
            f"Strain: {self.current_strain}/{self.strain_threshold} | "
            f"Soak: {self.effective_soak()}",
        ]
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
