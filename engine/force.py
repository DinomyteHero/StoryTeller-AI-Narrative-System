"""
Force dice resolution engine (Game Mechanics §16).

Handles Force pip resolution, dark side temptation detection,
committed dice management, Force power loading, Force power
upgrade milestones, and Force context assembly for GM prompts.

This module is pure Python — no LLM dependencies, no API keys.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from engine.dice import RollResult
from engine.character import Character


# ── Paths ────────────────────────────────────────────────────────────

FORCE_POWERS_DIR = Path(__file__).parent.parent / "data" / "force_powers"


# ── Data classes ──────────────────────────────────────────────────────

@dataclass
class ForceResolution:
    """Result of Force pip evaluation against power requirements."""
    light_pips:           int = 0
    dark_pips:            int = 0
    pips_required:        int = 1
    force_succeeded:      bool = False
    temptation_available: bool = False   # can succeed by using the costly side
    pips_needed_from_costly_side: int = 0
    morality:             int = 50
    is_dark_dominant:     bool = False   # Morality <= 40
    is_grey:              bool = False   # Morality 41-70
    conflict_cost:        int = 0
    strain_cost:          int = 0


@dataclass
class ForceResult:
    """Final Force result after player decision on temptation."""
    force_succeeded:      bool = False
    light_pips_used:      int = 0
    dark_pips_used:       int = 0
    conflict_earned:      int = 0
    strain_charged:       int = 0
    temptation_offered:   bool = False
    temptation_accepted:  bool = False
    narrative_note:       str = ""       # GM guidance for narrating the Force result
    force_power:          str = ""       # which power was used
    pips_required:        int = 1


# ── Core resolution ──────────────────────────────────────────────────

def get_available_force_dice(character: Character) -> int:
    """Return force_rating minus force_committed."""
    return max(0, character.force_rating - character.force_committed)


def resolve_force_pips(
    roll_result: RollResult,
    pips_required: int,
    morality: int,
) -> ForceResolution:
    """
    Evaluate Force pip sufficiency against power requirements (§16.1).

    Determines whether Force succeeds cleanly, whether dark side
    temptation is available, and computes costs for dark/light pip
    usage based on morality band.

    Light-dominant/grey (morality > 40): light pips are free, dark cost Conflict + strain.
    Dark-dominant (morality <= 40): dark pips are free, light pips cost strain.
    Grey (41-70): dark pips cost Conflict + strain but strain is reduced by 1.
    """
    light = roll_result.light_pips
    dark = roll_result.dark_pips
    is_dark_dominant = morality <= 40
    is_grey = 41 <= morality <= 70

    resolution = ForceResolution(
        light_pips=light,
        dark_pips=dark,
        pips_required=pips_required,
        morality=morality,
        is_dark_dominant=is_dark_dominant,
        is_grey=is_grey,
    )

    if is_dark_dominant:
        # Dark pips are free; light pips cost strain
        if dark >= pips_required:
            resolution.force_succeeded = True
        elif dark + light >= pips_required:
            resolution.temptation_available = True
            light_needed = pips_required - dark
            resolution.pips_needed_from_costly_side = light_needed
            resolution.strain_cost = max(1, light_needed)
            resolution.conflict_cost = 0  # using light reduces drift, no Conflict
    else:
        # Light pips are free; dark pips trigger temptation
        if light >= pips_required:
            resolution.force_succeeded = True
        elif light + dark >= pips_required:
            resolution.temptation_available = True
            dark_needed = pips_required - light
            resolution.pips_needed_from_costly_side = dark_needed
            resolution.conflict_cost = dark_needed
            resolution.strain_cost = max(1, dark_needed - 1) if is_grey else dark_needed

    return resolution


def apply_temptation_choice(
    resolution: ForceResolution,
    accepted: bool,
    force_power: str = "",
) -> ForceResult:
    """
    Finalize Force result after player's temptation decision (§16.2).

    For light-dominant/grey: accepting means using dark pips (Conflict + strain).
    For dark-dominant: accepting means using light pips (strain, no Conflict).
    Rejecting always means the Force fails.
    """
    result = ForceResult(
        temptation_offered=True,
        force_power=force_power,
        pips_required=resolution.pips_required,
    )

    if not accepted:
        result.force_succeeded = False
        result.temptation_accepted = False
        if resolution.is_dark_dominant:
            result.narrative_note = (
                "FORCE RESULT: FAILED (temptation rejected). "
                "The dark side answered eagerly but the total was not enough. "
                "The character sensed the light — quieter, harder — and chose "
                "not to reach for it. The Force did not answer on the terms "
                "they demanded of themselves. This is a dark-side-affirming moment."
            )
        else:
            result.narrative_note = (
                "FORCE RESULT: FAILED (temptation rejected). "
                "The character reached for the Force and felt it answer wrong — "
                "dark, hot, insistent. They chose to let it go rather than draw "
                "on that power. This is a light-side-affirming moment — narrate "
                "the discipline of refusal."
            )
        return result

    # Player accepted the temptation
    result.force_succeeded = True
    result.temptation_accepted = True

    if resolution.is_dark_dominant:
        # Using light pips — costs strain, no Conflict
        result.light_pips_used = resolution.pips_needed_from_costly_side
        result.dark_pips_used = resolution.dark_pips
        result.strain_charged = resolution.strain_cost
        result.narrative_note = (
            "FORCE RESULT: SUCCESS (reached for the light). "
            "The character reached past the familiar surge of the dark side "
            "for something quieter, cooler. It worked, but the effort was "
            f"exhausting (strain +{resolution.strain_cost}). Narrate the "
            "unfamiliarity and cost of reaching for the light — swimming "
            "upstream, fighting a current."
        )
    else:
        # Using dark pips — Conflict + strain
        result.dark_pips_used = resolution.pips_needed_from_costly_side
        result.light_pips_used = resolution.light_pips
        result.conflict_earned = resolution.conflict_cost
        result.strain_charged = resolution.strain_cost
        result.narrative_note = (
            f"FORCE RESULT: SUCCESS (drew on the dark side). "
            f"Dark pips used: {resolution.pips_needed_from_costly_side}. "
            f"Conflict earned: {resolution.conflict_cost}. "
            f"Strain suffered: {resolution.strain_cost}. "
            "Something tore, something shifted. The Force obeyed but the cost "
            "was felt. Narrate the wrongness of the dark current and the "
            "physical toll. Do not soften this."
        )

    return result


# ── Clean success / total failure builders ────────────────────────────

def build_clean_success(
    roll_result: RollResult,
    pips_required: int,
    morality: int,
    force_power: str = "",
) -> ForceResult:
    """Build ForceResult for clean Force success (no temptation needed)."""
    is_dark_dominant = morality <= 40

    result = ForceResult(
        force_succeeded=True,
        force_power=force_power,
        pips_required=pips_required,
    )

    if is_dark_dominant:
        result.dark_pips_used = pips_required
        result.narrative_note = (
            f"FORCE RESULT: SUCCESS (dark side, clean). "
            f"The dark side answered immediately — eager, sharp, obedient. "
            f"{pips_required} dark pip(s) channeled cleanly. No strain, no "
            f"resistance. Narrate Force use as command, not request."
        )
    else:
        result.light_pips_used = pips_required
        result.narrative_note = (
            f"FORCE RESULT: SUCCESS (light side, clean). "
            f"The light side answered cleanly — {pips_required} light pip(s) "
            f"channeled with no dark side interference. No Conflict, no strain. "
            f"Narrate Force use as natural, responsive, warm."
        )

    return result


def build_total_failure(
    roll_result: RollResult,
    pips_required: int,
    force_power: str = "",
) -> ForceResult:
    """Build ForceResult for total Force failure (insufficient total pips)."""
    total = roll_result.light_pips + roll_result.dark_pips
    return ForceResult(
        force_succeeded=False,
        force_power=force_power,
        pips_required=pips_required,
        narrative_note=(
            f"FORCE RESULT: FAILED (insufficient pips). "
            f"Total pips generated ({roll_result.light_pips} light + "
            f"{roll_result.dark_pips} dark = {total}) were insufficient "
            f"for the {pips_required} pip(s) required. The character reached "
            f"for the Force and it was not enough. No Conflict generated."
        ),
    )


# ── Temptation choice structure ──────────────────────────────────────

def build_temptation_choice(
    resolution: ForceResolution,
    force_power: str = "",
) -> dict:
    """
    Build the dark side temptation choice for the player (§16.2).

    Returns a dict with temptation structure, similar to intervention offers.
    For dark-dominant characters, the temptation is inverted (light pips cost).
    """
    if resolution.is_dark_dominant:
        return {
            "offered": True,
            "is_dark_temptation": True,
            "is_inverted": True,
            "force_power": force_power,
            "strain_cost": resolution.strain_cost,
            "conflict_cost": 0,
            "options": [
                {
                    "label": "Take what's offered — the dark side is faster.",
                    "effect": "reject",
                },
                {
                    "label": "Reach for the quiet — there's another way.",
                    "effect": "accept",
                },
            ],
        }
    else:
        return {
            "offered": True,
            "is_dark_temptation": True,
            "is_inverted": False,
            "force_power": force_power,
            "strain_cost": resolution.strain_cost,
            "conflict_cost": resolution.conflict_cost,
            "options": [
                {
                    "label": "Let it go — the Force isn't answering the way it should.",
                    "effect": "reject",
                },
                {
                    "label": "Reach deeper — whatever it costs.",
                    "effect": "accept",
                },
            ],
        }


# ── GM prompt context builders ───────────────────────────────────────

def build_force_result_block(
    force_result: ForceResult,
    skill_succeeded: Optional[bool],
    morality: int,
) -> str:
    """
    Build the FORCE RESULT block for the narration prompt (§16.1).

    When Force dice accompany a skill check, the GM gets both
    skill and Force results with four-result matrix guidance.
    For pure Force actions, skill_succeeded is None.
    """
    lines = [
        "FORCE RESULT:",
        f"  Force outcome: {'SUCCESS' if force_result.force_succeeded else 'FAILURE'}",
        f"  Pips required: {force_result.pips_required}",
    ]

    if force_result.dark_pips_used:
        lines.append(f"  Dark pips used: {force_result.dark_pips_used}")
    if force_result.light_pips_used:
        lines.append(f"  Light pips used: {force_result.light_pips_used}")
    if force_result.conflict_earned:
        lines.append(f"  Conflict earned: {force_result.conflict_earned}")
    if force_result.strain_charged:
        lines.append(f"  Strain charged: {force_result.strain_charged}")

    lines.append("")
    lines.append(force_result.narrative_note)

    # Four-result matrix guidance for Force-enhanced skill checks
    if skill_succeeded is not None:
        lines.append("")
        if skill_succeeded and force_result.force_succeeded:
            lines.append(
                "SKILL x FORCE MATRIX: Success + Force success. The best "
                "outcome — action succeeded and the Force enhancement worked. "
                "Channel power with skill and control."
            )
        elif skill_succeeded and not force_result.force_succeeded:
            lines.append(
                "SKILL x FORCE MATRIX: Success + Force failure. The action "
                "succeeded on mundane capability alone. The Force did not answer "
                "or was not needed. Narrate competence without mystical aid."
            )
        elif not skill_succeeded and force_result.force_succeeded:
            lines.append(
                "SKILL x FORCE MATRIX: Failure + Force success. The Force was "
                "present but the character could not translate it into the physical "
                "result. The Force is alive but skill was insufficient."
            )
        else:
            lines.append(
                "SKILL x FORCE MATRIX: Failure + Force failure. Complete failure. "
                "Neither the mundane nor the mystical was sufficient."
            )

    # Morality-band tonal guidance
    lines.append("")
    if morality > 70:
        lines.append(
            "FORCE TONE (light-dominant): Force use feels natural, responsive, "
            "warm. Dark side temptation emphasizes wrongness — alien, invasive."
        )
    elif morality >= 41:
        lines.append(
            "FORCE TONE (grey): Force use is uncertain, flickering. Dark side "
            "temptation emphasizes familiarity — known, not alien."
        )
    else:
        lines.append(
            "FORCE TONE (dark-dominant): Force use feels like command. Light "
            "side use emphasizes effort — swimming upstream, fighting a current."
        )

    return "\n".join(lines)


def build_force_state_block(character: Character) -> str:
    """
    Build the FORCE STATE block for the narration prompt character section.
    Returns empty string if character is not Force-sensitive.
    """
    if character.force_rating <= 0:
        return ""

    available = get_available_force_dice(character)
    morality = character.motivation.morality

    if morality > 70:
        label = "Light side dominant"
    elif morality >= 41:
        label = "Grey"
    else:
        label = "Dark side dominant"

    lines = [
        "FORCE STATE:",
        f"  Force Rating: {character.force_rating} ({available} available)",
        f"  Morality: {morality} — {label}",
        f"  Conflict this act: {character.motivation.conflict}",
    ]

    if character.force_committed > 0:
        lines.append(f"  Committed dice: {character.force_committed}")
        for c in character.active_commitments:
            lines.append(
                f"    - {c.get('power', '?')}: {c.get('narrative_note', c.get('upgrade', ''))}"
            )

    return "\n".join(lines)


# ── Force power data loading (§16.3) ─────────────────────────────────

_power_cache: dict[str, dict] = {}


def load_force_power(power_id: str) -> dict:
    """Load a Force power definition from JSON. Cached."""
    if power_id in _power_cache:
        return _power_cache[power_id]

    path = FORCE_POWERS_DIR / f"{power_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Force power data not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    _power_cache[power_id] = data
    return data


def get_character_power(character: Character, power_id: str) -> Optional[dict]:
    """Return the character's entry for a specific power, or None."""
    for p in character.force_powers:
        if p.get("power_id") == power_id:
            return p
    return None


def character_has_power(character: Character, power_id: str) -> bool:
    """Check if the character possesses a Force power."""
    return get_character_power(character, power_id) is not None


def get_effective_pips_required(power_id: str, character: Character) -> int:
    """
    Compute effective pips required for a power based on base + active upgrade
    increases. Some control upgrades increase the pip requirement.
    """
    try:
        power_data = load_force_power(power_id)
    except FileNotFoundError:
        return 1

    base = power_data.get("base_pips_required", 1)
    char_power = get_character_power(character, power_id)
    if not char_power:
        return base

    active_upgrades = char_power.get("active_upgrades", [])
    upgrades = power_data.get("upgrades", {})

    for uid in active_upgrades:
        upgrade = upgrades.get(uid, {})
        base += upgrade.get("pips_required_increase", 0)

    return base


# ── Force power capability blocks for GM prompts (§16.3) ─────────────

def build_force_capabilities_block(character: Character) -> str:
    """
    Build the FORCE POWERS section for the narration prompt.
    Informs the GM what Force powers the character possesses and their
    capabilities, so it generates appropriate Force-tagged choices.
    Returns empty string for non-Force characters or those with no powers.
    """
    if character.force_rating <= 0 or not character.force_powers:
        return ""

    lines = ["FORCE POWERS:"]
    for entry in character.force_powers:
        power_id = entry.get("power_id", "")
        try:
            power_data = load_force_power(power_id)
        except FileNotFoundError:
            continue

        name = power_data.get("name", power_id)
        capability = power_data.get("narrative_capability", "")
        guidance = power_data.get("gm_choice_guidance", "")
        dark_flavor = power_data.get("dark_side_flavor", "")

        lines.append(f"  {name}:")
        lines.append(f"    Capability: {capability}")
        lines.append(f"    Choice guidance: {guidance}")

        # Show active upgrades
        active = entry.get("active_upgrades", [])
        if active:
            upgrades = power_data.get("upgrades", {})
            active_names = [
                upgrades[uid]["name"]
                for uid in active if uid in upgrades
            ]
            if active_names:
                lines.append(f"    Upgrades: {', '.join(active_names)}")

        if character.motivation.morality <= 40 and dark_flavor:
            lines.append(f"    Dark side flavor: {dark_flavor}")

        lines.append(f"    Tag choices as: [Force:{name}]")

    lines.append("")
    lines.append(
        "  IMPORTANT: Only offer Force-tagged choices for powers listed above. "
        "The character cannot use Force powers they do not possess."
    )

    return "\n".join(lines)


def build_force_choice_guidance(character: Character) -> str:
    """
    Build the FORCE POWERS section for the check decision prompt.
    Informs the local model what Force powers the character has so it
    can correctly set force_use, force_power, and force_pips_required.
    Returns empty string for non-Force characters or those with no powers.
    """
    if character.force_rating <= 0 or not character.force_powers:
        return ""

    lines = ["FORCE POWERS AVAILABLE:"]
    for entry in character.force_powers:
        power_id = entry.get("power_id", "")
        try:
            power_data = load_force_power(power_id)
        except FileNotFoundError:
            continue

        name = power_data.get("name", power_id)
        pips = get_effective_pips_required(power_id, character)
        lines.append(f"  - {name} (pips_required: {pips})")

    return "\n".join(lines)


# ── Commitment management (§16.5) ────────────────────────────────────

def commit_force_die(
    character: Character,
    power_id: str,
    upgrade_id: str,
    turn_number: int = 0,
) -> bool:
    """
    Commit a Force die to a sustained effect. Returns True if successful.
    Fails if insufficient available Force dice or already committed to this upgrade.
    """
    available = get_available_force_dice(character)
    if available <= 0:
        logging.warning(
            f"Cannot commit Force die: 0 available "
            f"(rating {character.force_rating}, committed {character.force_committed})"
        )
        return False

    # Check if already committed to this exact upgrade
    for c in character.active_commitments:
        if c.get("power") == power_id and c.get("upgrade") == upgrade_id:
            logging.info(f"Already committed to {power_id}:{upgrade_id}")
            return False

    # Look up narrative note from power data
    narrative_note = ""
    try:
        power_data = load_force_power(power_id)
        commitment_opt = power_data.get("commitment_option", {})
        if commitment_opt.get("upgrade_id") == upgrade_id:
            narrative_note = commitment_opt.get("narrative_note", "")
        else:
            upgrade_def = power_data.get("upgrades", {}).get(upgrade_id, {})
            narrative_note = upgrade_def.get("effect", "")
    except FileNotFoundError:
        pass

    character.force_committed += 1
    character.active_commitments.append({
        "power": power_id,
        "upgrade": upgrade_id,
        "dice_committed": 1,
        "committed_since_turn": turn_number,
        "narrative_note": narrative_note,
    })

    logging.info(
        f"Committed Force die: {power_id}:{upgrade_id} "
        f"(now {character.force_committed} committed, "
        f"{get_available_force_dice(character)} available)"
    )
    return True


def release_commitment(character: Character, power_id: str) -> bool:
    """
    Release a committed Force die for a power. Returns True if released.
    If multiple commitments exist for the same power, releases the first.
    """
    for i, c in enumerate(character.active_commitments):
        if c.get("power") == power_id:
            dice = c.get("dice_committed", 1)
            character.force_committed = max(0, character.force_committed - dice)
            character.active_commitments.pop(i)
            logging.info(
                f"Released Force commitment: {power_id} "
                f"(now {character.force_committed} committed, "
                f"{get_available_force_dice(character)} available)"
            )
            return True
    return False


# ── Force power upgrade milestones (§16.4) ────────────────────────────

@dataclass
class ForcePowerMilestoneChoice:
    """One option in a Force power upgrade milestone reflection."""
    power_id:       str
    power_name:     str
    upgrade_id:     str
    upgrade_name:   str
    upgrade_type:   str        # "range", "strength", "control", "magnitude", "duration"
    xp_cost:        int
    effect:         str
    narrative:      str        # reflection prose direction


def build_force_power_milestone_choices(
    character: Character,
    reserved_xp: int,
    max_choices: int = 3,
) -> list[ForcePowerMilestoneChoice]:
    """
    Generate Force power upgrade milestone choices (§16.4).

    Finds available upgrades across all character's Force powers.
    Returns up to max_choices options, prioritizing powers the character
    has actually used (future: behavioral signals), then cheapest upgrades.
    """
    if not character.force_powers:
        return []

    choices: list[ForcePowerMilestoneChoice] = []

    for entry in character.force_powers:
        power_id = entry.get("power_id", "")
        active = set(entry.get("active_upgrades", []))

        try:
            power_data = load_force_power(power_id)
        except FileNotFoundError:
            continue

        upgrades = power_data.get("upgrades", {})

        for uid, upgrade in upgrades.items():
            # Skip already acquired
            if uid in active:
                continue

            # Check prerequisites
            prereqs = upgrade.get("prerequisites", [])
            if not all(p in active for p in prereqs):
                continue

            # Check affordability
            cost = upgrade.get("xp_cost", 10)
            if cost > reserved_xp:
                continue

            choices.append(ForcePowerMilestoneChoice(
                power_id=power_id,
                power_name=power_data.get("name", power_id),
                upgrade_id=uid,
                upgrade_name=upgrade.get("name", uid),
                upgrade_type=upgrade.get("type", "control"),
                xp_cost=cost,
                effect=upgrade.get("effect", ""),
                narrative=upgrade.get("narrative", ""),
            ))

    # Sort by cost (cheapest first)
    choices.sort(key=lambda c: c.xp_cost)
    return choices[:max_choices]


def apply_force_power_upgrade(
    character: Character,
    choice: ForcePowerMilestoneChoice,
) -> None:
    """
    Apply a Force power upgrade to the character.
    Deducts reserved_xp and adds the upgrade to the power's active_upgrades.
    """
    character.reserved_xp = max(0, character.reserved_xp - choice.xp_cost)

    for entry in character.force_powers:
        if entry.get("power_id") == choice.power_id:
            if "active_upgrades" not in entry:
                entry["active_upgrades"] = []
            entry["active_upgrades"].append(choice.upgrade_id)
            break

    character.advancement_log.append({
        "type": "force_power_upgrade",
        "power_id": choice.power_id,
        "upgrade_id": choice.upgrade_id,
        "upgrade_name": choice.upgrade_name,
        "cost": choice.xp_cost,
    })

    logging.info(
        f"Force power upgrade: {choice.power_name} -> {choice.upgrade_name} "
        f"(cost {choice.xp_cost} reserved XP)"
    )
