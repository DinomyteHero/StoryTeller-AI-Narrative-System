"""
Equipment and loadout system (Game Mechanics §18).

Pydantic models for weapon, armor, tool, and special item entries.
Utility functions for damage calculation, soak, tool requirements,
and prompt block assembly.

This module is pure Python — no LLM dependencies, no API keys.
"""

from typing import Optional
from pydantic import BaseModel, Field
from engine.dice import RollResult


# ── Pydantic models ───────────────────────────────────────────────────

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
    """Character's equipment loadout (Game Mechanics §18)."""
    weapons: list[WeaponEntry] = []
    armor: Optional[ArmorEntry] = None
    tools: list[ToolEntry] = []
    special_items: list[SpecialItem] = []


# ── Combat skills (weapon damage applies) ─────────────────────────────

COMBAT_SKILLS = {"brawl", "gunnery", "melee", "ranged_light", "ranged_heavy", "lightsaber"}

# ── Skill-to-tool-category mapping for tool gating ────────────────────

SKILL_TOOL_GATES: dict[str, str] = {
    "computers": "slicing",
    "medicine":  "medical",
    "mechanics": "mechanical",
}


# ── Damage and soak ──────────────────────────────────────────────────

def compute_weapon_damage(roll_result: RollResult, weapon: WeaponEntry) -> int:
    """
    Total damage from a successful combat check.
    FFG formula: weapon damage_bonus + net successes.
    """
    return weapon.damage_bonus + roll_result.net_successes


def compute_total_soak(armor: Optional[ArmorEntry], brawn: int) -> int:
    """Total soak: Brawn + armor soak bonus."""
    soak = brawn
    if armor:
        soak += armor.soak_bonus
    return soak


def get_weapon_for_skill(loadout: Loadout, skill: str) -> Optional[WeaponEntry]:
    """Find the weapon matching the check skill, if any."""
    for weapon in loadout.weapons:
        if weapon.skill == skill:
            return weapon
    return None


# ── Tool requirements ─────────────────────────────────────────────────

def check_tool_requirements(skill: str, tools: list[ToolEntry]) -> dict:
    """
    Evaluate whether the character has required tools for a skill.
    Returns pool modifiers and gating info.
    """
    result = {"has_required_tool": True, "setback_modifier": 0, "notes": []}

    required_category = SKILL_TOOL_GATES.get(skill)
    if not required_category:
        return result  # No tool requirement for this skill

    matching_tools = [t for t in tools if t.category == required_category]
    if not matching_tools:
        result["has_required_tool"] = False
        result["notes"].append(
            f"No {required_category} tools — {skill} checks on "
            "specialized systems are gated"
        )
        return result

    for tool in matching_tools:
        effect = tool.mechanical_effect.lower()
        if "removes 1 setback" in effect or "remove 1 setback" in effect:
            result["setback_modifier"] -= 1
        elif "removes 2 setback" in effect or "remove 2 setback" in effect:
            result["setback_modifier"] -= 2

    return result


# ── Prompt block assembly ─────────────────────────────────────────────

def build_equipment_check_summary(loadout: Loadout) -> str:
    """
    Concise equipment summary for the check decision prompt.
    Lists capability-relevant gear only.
    """
    if (not loadout.weapons and not loadout.armor
            and not loadout.tools and not loadout.special_items):
        return "No notable equipment."

    lines = []

    for w in loadout.weapons:
        skill_label = w.skill.replace("_", " ").title()
        qualities_str = (
            f", qualities: {', '.join(w.qualities)}" if w.qualities else ""
        )
        lines.append(
            f"- Armed with {w.name} ({skill_label} skill, "
            f"damage +{w.damage_bonus}, critical {w.critical_rating}"
            f"{qualities_str})"
        )

    if loadout.armor:
        a = loadout.armor
        defense_str = f", defense {a.defense}" if a.defense > 0 else ""
        lines.append(
            f"- Wearing {a.name} (soak +{a.soak_bonus}{defense_str})"
        )

    for t in loadout.tools:
        lines.append(f"- {t.name}: {t.mechanical_effect}")

    for s in loadout.special_items:
        if s.mechanical_effect:
            lines.append(f"- {s.name}: {s.mechanical_effect}")
        else:
            lines.append(f"- {s.name}")

    return "\n".join(lines)


def build_equipment_narration_block(loadout: Loadout) -> str:
    """
    Full equipment block for the narration prompt.
    Includes narrative notes for prose flavor.
    """
    if (not loadout.weapons and not loadout.armor
            and not loadout.tools and not loadout.special_items):
        return "No notable equipment."

    sections = []

    if loadout.weapons:
        weapon_lines = []
        for w in loadout.weapons:
            line = f"- {w.name}"
            if w.narrative_note:
                line += f": {w.narrative_note}"
            quals = ", ".join(w.qualities) if w.qualities else ""
            line += f"\n  (Damage +{w.damage_bonus}, critical {w.critical_rating}"
            if quals:
                line += f", {quals}"
            line += ")"
            weapon_lines.append(line)
        sections.append("Weapons:\n" + "\n".join(weapon_lines))

    if loadout.armor:
        a = loadout.armor
        line = f"- {a.name}"
        if a.narrative_note:
            line += f": {a.narrative_note}"
        line += f"\n  (Soak +{a.soak_bonus}"
        if a.defense > 0:
            line += f", defense {a.defense}"
        line += ")"
        sections.append("Armor:\n" + line)

    if loadout.tools:
        tool_lines = []
        for t in loadout.tools:
            line = f"- {t.name}"
            if t.narrative_note:
                line += f": {t.narrative_note}"
            tool_lines.append(line)
        sections.append("Gear:\n" + "\n".join(tool_lines))

    if loadout.special_items:
        item_lines = []
        for s in loadout.special_items:
            line = f"- {s.name}"
            if s.narrative_note:
                line += f": {s.narrative_note}"
            item_lines.append(line)
        sections.append("Special:\n" + "\n".join(item_lines))

    return "\n\n".join(sections)


def build_combat_damage_block(
    roll_result: RollResult, weapon: WeaponEntry, target_soak: int = 0,
) -> str:
    """
    Build damage narration context for successful combat checks.
    The GM uses this to calibrate wound narration.
    """
    total_damage = compute_weapon_damage(roll_result, weapon)
    effective = max(0, total_damage - target_soak)

    lines = [
        f"COMBAT OUTCOME: {weapon.name}",
        f"  Raw damage: {weapon.damage_bonus} (weapon) + "
        f"{roll_result.net_successes} (successes) = {total_damage}",
    ]
    if target_soak > 0:
        lines.append(
            f"  Target soak: {target_soak} — effective damage: {effective}"
        )
    if weapon.qualities:
        lines.append(f"  Available qualities: {', '.join(weapon.qualities)}")
    if roll_result.net_advantages > 0:
        lines.append(
            f"  Advantages available ({roll_result.net_advantages}): "
            "may trigger weapon qualities in narration"
        )

    return "\n".join(lines)


def update_loadout(loadout: Loadout, event: dict) -> Loadout:
    """
    Process loadout changes: acquire, lose, or consume items.
    Returns a new Loadout with the change applied.
    """
    event_type = event.get("type")
    data = loadout.model_dump()

    if event_type == "acquire_weapon":
        data["weapons"].append(event["weapon"])
    elif event_type == "lose_weapon":
        data["weapons"] = [
            w for w in data["weapons"] if w["name"] != event["name"]
        ]
    elif event_type == "acquire_armor":
        data["armor"] = event["armor"]
    elif event_type == "lose_armor":
        data["armor"] = None
    elif event_type == "acquire_tool":
        data["tools"].append(event["tool"])
    elif event_type == "lose_tool":
        data["tools"] = [
            t for t in data["tools"] if t["name"] != event["name"]
        ]
    elif event_type == "acquire_special":
        data["special_items"].append(event["item"])
    elif event_type == "lose_special":
        data["special_items"] = [
            s for s in data["special_items"] if s["name"] != event["name"]
        ]

    return Loadout.model_validate(data)
