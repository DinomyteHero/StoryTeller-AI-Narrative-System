"""
Vehicle and starship system (Game Mechanics §17).

ShipState parallels NPCState — a persistent state card for each ship
the character operates. Three-tier damage model (operational/stressed/
critical), simplified vehicle critical hit table, and handling modifier
for pool construction.
"""

import random
from pydantic import BaseModel, Field
from typing import Optional


# ── Damage tier thresholds ─────────────────────────────────────────────
# Operational: both below 50%
# Stressed: either at 50-80%
# Critical: either above 80%, or a critical hit active

STRESSED_THRESHOLD = 0.50
CRITICAL_THRESHOLD = 0.80


class WeaponMount(BaseModel):
    """One weapon system on a ship."""
    name:      str
    skill:     str = "gunnery"        # gunnery by default
    damage:    int = 6
    arc:       str = "all"            # all / fore / aft / port / starboard
    qualities: list[str] = Field(default_factory=list)


class ShipState(BaseModel):
    """
    Persistent state card for a vehicle/starship (§17.1).

    Loaded from the campaign spine's vehicle_registry at session start,
    then persisted in the ship_states table across turns.
    """
    ship_id:                 str
    name:                    str
    ship_type:               str = ""        # e.g. "YT-2000 light freighter"
    silhouette:              int = 4
    speed:                   int = 3
    handling:                int = -1         # positive = boost, negative = setback
    hull_threshold:          int = 22
    system_strain_threshold: int = 16
    current_hull_trauma:     int = 0
    current_system_strain:   int = 0
    armor:                   int = 3
    shields:                 dict[str, int] = Field(default_factory=lambda: {"fore": 1, "aft": 1})
    weapons:                 list[WeaponMount] = Field(default_factory=list)
    active_damage:           list[str] = Field(default_factory=list)  # critical hit narrative tags
    narrative_notes:         str = ""

    # ── Damage tier ────────────────────────────────────────────────────

    def hull_ratio(self) -> float:
        if self.hull_threshold <= 0:
            return 0.0
        return self.current_hull_trauma / self.hull_threshold

    def strain_ratio(self) -> float:
        if self.system_strain_threshold <= 0:
            return 0.0
        return self.current_system_strain / self.system_strain_threshold

    def damage_tier(self) -> str:
        """Return operational / stressed / critical (§17.1)."""
        if self.active_damage:
            return "critical"
        hull_r = self.hull_ratio()
        strain_r = self.strain_ratio()
        if hull_r >= CRITICAL_THRESHOLD or strain_r >= CRITICAL_THRESHOLD:
            return "critical"
        if hull_r >= STRESSED_THRESHOLD or strain_r >= STRESSED_THRESHOLD:
            return "stressed"
        return "operational"

    def damage_setback(self) -> int:
        """Setback dice from damage tier (§17.1)."""
        tier = self.damage_tier()
        if tier == "critical":
            return 2
        if tier == "stressed":
            return 1
        return 0

    def handling_boost(self) -> int:
        """Boost dice from positive handling (§17.2)."""
        return max(0, self.handling)

    def handling_setback(self) -> int:
        """Setback dice from negative handling (§17.2)."""
        return max(0, -self.handling)

    # ── Damage application ─────────────────────────────────────────────

    def apply_hull_trauma(self, amount: int) -> None:
        """Apply hull trauma reduced by armor."""
        effective = max(0, amount - self.armor)
        self.current_hull_trauma = min(
            self.hull_threshold, self.current_hull_trauma + effective
        )

    def apply_system_strain(self, amount: int) -> None:
        """Apply system strain (no armor reduction)."""
        self.current_system_strain = min(
            self.system_strain_threshold,
            self.current_system_strain + amount,
        )

    def repair_hull(self, amount: int) -> None:
        self.current_hull_trauma = max(0, self.current_hull_trauma - amount)

    def repair_strain(self, amount: int) -> None:
        self.current_system_strain = max(0, self.current_system_strain - amount)

    def is_destroyed(self) -> bool:
        return self.current_hull_trauma >= self.hull_threshold

    # ── Prompt blocks ──────────────────────────────────────────────────

    def to_check_prompt_block(self) -> str:
        """Ship status for the check decision prompt (§17 impl notes)."""
        tier = self.damage_tier()
        weapon_list = ", ".join(
            f"{w.name} ({w.skill}, damage {w.damage})" for w in self.weapons
        ) or "None"
        damage_list = "; ".join(self.active_damage) if self.active_damage else "None"

        lines = [
            f"SHIP STATUS: {self.name} — {tier}",
            f"Handling: {self.handling:+d} | Speed: {self.speed}",
            f"Hull: {self.current_hull_trauma}/{self.hull_threshold} | "
            f"System Strain: {self.current_system_strain}/{self.system_strain_threshold}",
            f"Armor: {self.armor} | Shields: {_format_shields(self.shields)}",
            f"Weapons: {weapon_list}",
            f"Active damage: {damage_list}",
        ]
        return "\n".join(lines)

    def to_narration_block(self) -> str:
        """Ship state for the narration prompt — narrative-forward."""
        tier = self.damage_tier()
        lines = [f"SHIP: {self.name} ({self.ship_type})"]

        if tier == "operational":
            lines.append("Status: Operational — the ship is functional.")
        elif tier == "stressed":
            lines.append(
                "Status: STRESSED — describe intermittent system failures, "
                "sparks, warning lights, the sounds of a vessel being pushed "
                "past comfort."
            )
        else:
            lines.append(
                "Status: CRITICAL — the ship is in danger of being lost. "
                "Systems failing, hull integrity compromised."
            )
            if self.active_damage:
                lines.append(f"Critical damage: {'; '.join(self.active_damage)}")

        if self.narrative_notes:
            lines.append(f"Notes: {self.narrative_notes}")

        return "\n".join(lines)


def _format_shields(shields: dict[str, int]) -> str:
    if not shields:
        return "None"
    return ", ".join(f"{arc} {val}" for arc, val in shields.items() if val > 0) or "None"


# ── Vehicle critical hit table (§17.3, simplified) ────────────────────
# 10 entries. Roll 1d10 (random.randint(1, 10)).

VEHICLE_CRITICAL_TABLE: list[dict] = [
    {"roll": 1,  "name": "Rattled",                "description": "Cosmetic damage — hull scoring, sparks, but no mechanical effect.", "mechanical_effect": None},
    {"roll": 2,  "name": "Rattled",                "description": "Cosmetic damage — a panel blows off, wiring exposed.", "mechanical_effect": None},
    {"roll": 3,  "name": "Shields Disrupted",      "description": "Shield generator fluctuating — one arc loses coverage.", "mechanical_effect": "shields_reduced"},
    {"roll": 4,  "name": "Shields Disrupted",      "description": "Shield emitter overloaded — coverage drops in one arc.", "mechanical_effect": "shields_reduced"},
    {"roll": 5,  "name": "Engine Hit",             "description": "Engine coupling damaged — the ship responds slower.", "mechanical_effect": "speed_reduced"},
    {"roll": 6,  "name": "Engine Hit",             "description": "Thruster array compromised — maneuverability suffers.", "mechanical_effect": "speed_reduced"},
    {"roll": 7,  "name": "Weapon Damaged",         "description": "Weapon system offline — targeting circuits fried.", "mechanical_effect": "weapon_offline"},
    {"roll": 8,  "name": "Weapon Damaged",         "description": "Power coupling to weapon severed.", "mechanical_effect": "weapon_offline"},
    {"roll": 9,  "name": "Navigation Systems Hit", "description": "Navicomputer glitching — astrogation unreliable.", "mechanical_effect": "nav_damaged"},
    {"roll": 10, "name": "Hull Breach",            "description": "Hull integrity compromised — atmosphere venting.", "mechanical_effect": "hull_breach"},
]


def roll_vehicle_critical(ship: ShipState) -> dict:
    """
    Roll on the vehicle critical hit table (§17.3).

    Applies the mechanical effect to the ship state and returns the
    critical hit entry for narration context.
    """
    roll = random.randint(1, 10)
    entry = VEHICLE_CRITICAL_TABLE[roll - 1]

    # Apply mechanical effect
    effect = entry["mechanical_effect"]
    tag = f"{entry['name']}: {entry['description']}"

    if effect == "shields_reduced":
        # Reduce shields in the first arc that has any
        for arc in list(ship.shields.keys()):
            if ship.shields[arc] > 0:
                ship.shields[arc] = max(0, ship.shields[arc] - 1)
                break

    elif effect == "speed_reduced":
        ship.speed = max(0, ship.speed - 1)

    elif effect == "weapon_offline":
        # Mark first weapon as offline (via narrative tag)
        if ship.weapons:
            tag = f"{entry['name']} ({ship.weapons[0].name}): {entry['description']}"

    elif effect == "nav_damaged":
        pass  # narration-only; +1 difficulty on Astrogation handled via active_damage tag

    elif effect == "hull_breach":
        ship.hull_threshold = max(1, ship.hull_threshold - 2)

    # Add to active damage (if not cosmetic)
    if effect is not None:
        ship.active_damage.append(tag)

    return entry


# ── Vehicle-context skills ─────────────────────────────────────────────

VEHICLE_SKILLS = {
    "piloting_space", "piloting_planetary", "gunnery",
    "mechanics", "leadership", "astrogation", "computers",
}


def is_vehicle_skill(skill: str) -> bool:
    """Check if a skill is vehicle-appropriate for handling/damage modifiers."""
    return skill.lower().replace(" ", "_").replace("-", "_") in VEHICLE_SKILLS


# ── Ship state from spine ──────────────────────────────────────────────

def load_ship_from_spine(vehicle_entry: dict) -> ShipState:
    """Create a ShipState from a campaign spine vehicle_registry entry."""
    weapons = [
        WeaponMount(**w) for w in vehicle_entry.get("weapons", [])
    ]
    return ShipState(
        ship_id=vehicle_entry["ship_id"],
        name=vehicle_entry["name"],
        ship_type=vehicle_entry.get("type", ""),
        silhouette=vehicle_entry.get("silhouette", 4),
        speed=vehicle_entry.get("speed", 3),
        handling=vehicle_entry.get("handling", 0),
        hull_threshold=vehicle_entry.get("hull_threshold", 20),
        system_strain_threshold=vehicle_entry.get("system_strain_threshold", 14),
        armor=vehicle_entry.get("armor", 2),
        shields=vehicle_entry.get("shields", {}),
        weapons=weapons,
        narrative_notes=vehicle_entry.get("narrative_notes", ""),
    )


def build_vehicle_damage_block(
    ship: ShipState, roll_result, check_skill: str,
) -> str:
    """
    Build vehicle damage context for the narration prompt (§17.3).

    Called after a successful vehicle-context check to describe damage
    dealt by the ship's weapons, or after a failed check to describe
    incoming damage / system strain.
    """
    if roll_result is None:
        return ""

    lines = []

    # Successful attack — ship weapon damage
    if roll_result.succeeded and check_skill == "gunnery" and ship.weapons:
        weapon = ship.weapons[0]
        base_damage = weapon.damage + roll_result.net_successes
        lines.append(
            f"VEHICLE WEAPON DAMAGE: {weapon.name} hits for {base_damage} damage "
            f"(base {weapon.damage} + {roll_result.net_successes} successes)."
        )

    # Threat on vehicle checks → system strain
    if roll_result.net_advantages < 0:
        strain_amount = abs(roll_result.net_advantages)
        lines.append(
            f"SHIP STRAIN: The ship takes {strain_amount} system strain from "
            f"threat on the {check_skill} check."
        )

    return "\n".join(lines)
