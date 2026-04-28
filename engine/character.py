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
    species:            Species
    career:             Career
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
    throughline_question: str = ""
    voice_notes:          str = ""
    active_injuries:      list[str] = Field(default_factory=list)  # narrative injury descriptions (Game Mechanics §3)
    narrative_arc:        Optional[NarrativeArc] = None  # Brooks/Weiland arc — opt-in

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
        lines = [
            f"{self.name} | "
            f"{self.species.value.title()} "
            f"{self.career.value.replace('_', ' ').title()}",
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
