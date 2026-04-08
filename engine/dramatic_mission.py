"""
Dramatic mission classification for per-turn narrative purpose.

The dramatic mission tells the cloud GM what this specific turn should
accomplish narratively, beyond scene type (which controls pacing) and
act progress (which controls convergence). Mission is the *dramatic job*
of the scene.

Story Engineering principle: every scene must have a single, clear
expository mission. Part 2 scenes should feel like *response*; Part 3
scenes should feel like *attack*.

Pure Python — no LLM dependencies.
"""

from enum import Enum
from pydantic import BaseModel
from typing import Optional


class DramaticMission(str, Enum):
    """
    Turn-level dramatic mission tags, derived from Brooks's four-part
    model and scene function theory.

    The local model selects from the VALID set for the current act
    context. Not all missions are valid in all act positions.
    """
    # Part 1 (Setup) missions
    STAKE_SETUP = "stake_setup"
    WORLD_NORMAL = "world_normal"
    FORESHADOW = "foreshadow"

    # Part 2 (Response) missions
    RESPONSE = "response"
    FALSE_PROGRESS = "false_progress"
    ANTAGONIST_PRESSURE = "antagonist_pressure"

    # Part 3 (Attack) missions
    ATTACK = "attack"
    INNER_DEMON_TEST = "inner_demon_test"
    MIDPOINT_REFRAME = "midpoint_reframe"

    # Part 4 (Resolution) missions
    COLLAPSE = "collapse"
    CLIMACTIC_EXECUTION = "climactic_execution"
    AFTERMATH = "aftermath"

    # Universal (valid in any part)
    CHARACTER_REVEAL = "character_reveal"
    THREAD_ADVANCE = "thread_advance"


class MissionContext(BaseModel):
    """
    Per-turn mission assignment with constraints.
    Computed deterministically from act position, then the local model
    selects from the valid set.
    """
    valid_missions: list[str]
    selected_mission: str = ""
    mission_instruction: str = ""
    scene_thrust_instruction: str = ""


# ── Act-context → valid mission mapping ──────────────────────────────

PART_MISSION_MAP: dict[str, list[str]] = {
    "setup": [
        "stake_setup", "world_normal", "foreshadow",
        "character_reveal", "thread_advance",
    ],
    "response": [
        "response", "false_progress", "antagonist_pressure",
        "character_reveal", "thread_advance", "foreshadow",
    ],
    "attack": [
        "attack", "inner_demon_test", "midpoint_reframe",
        "antagonist_pressure", "character_reveal", "thread_advance",
    ],
    "resolution": [
        "collapse", "climactic_execution", "aftermath",
        "character_reveal",
    ],
}


# ── Dramatic function → story part mapping ───────────────────────────

FUNCTION_TO_PART: dict[str, str] = {
    "setup": "setup",
    "destabilization": "setup",
    "launch": "response",
    "midpoint_shift": "attack",
    "escalation": "attack",
    "confrontation": "resolution",
    "consequence": "resolution",
    "resolution": "resolution",
}


def get_story_part(dramatic_function: str, overall_campaign_progress: float) -> str:
    """
    Map the current act's dramatic function + progress to a Brooks
    four-part label. This determines which missions are valid.

    The dramatic_function field comes from StoryArchitecture (if
    populated). Falls back to progress-based inference.
    """
    if dramatic_function and dramatic_function in FUNCTION_TO_PART:
        return FUNCTION_TO_PART[dramatic_function]

    # Fallback: infer from overall campaign progress
    if overall_campaign_progress < 0.25:
        return "setup"
    elif overall_campaign_progress < 0.50:
        return "response"
    elif overall_campaign_progress < 0.75:
        return "attack"
    else:
        return "resolution"


def compute_valid_missions(
    dramatic_function: str,
    act_progress: float,
    overall_campaign_progress: float,
) -> list[str]:
    """
    Return the list of valid dramatic missions for this turn.
    The local model selects from this list during reconciliation.
    """
    part = get_story_part(dramatic_function, overall_campaign_progress)
    return PART_MISSION_MAP.get(part, PART_MISSION_MAP["response"])


# ── Mission definitions for prompt injection ─────────────────────────

MISSION_DEFINITIONS: dict[str, str] = {
    "stake_setup": "Establish what matters, what the character stands to lose",
    "world_normal": "Show the world before pressure — routines, relationships, the status quo",
    "foreshadow": "Plant a specific detail that will matter later",
    "response": "The character reacts to pressure — retreating, investigating, processing",
    "false_progress": "The character tries something that fails or backfires",
    "antagonist_pressure": "Show the antagonistic force directly — its power, its reach, its threat",
    "attack": "The character takes initiative — plans, acts, fights back proactively",
    "inner_demon_test": "The character's core contradiction is directly tested by the situation",
    "midpoint_reframe": "A revelation or reversal that changes how everything before is understood",
    "collapse": "All hope seems lost — the character faces their lowest point",
    "climactic_execution": "The character applies everything they've learned to act decisively",
    "aftermath": "The cost of what happened — consequences, new reality, what changed",
    "character_reveal": "Show who the character truly is through action under pressure",
    "thread_advance": "Move a specific open narrative thread forward",
}


# ── Voice mode mappings (Phase 10) ───────────────────────────────────

MISSION_TO_VOICE: dict[str, str] = {
    # Kinetic missions → staccato voice
    "attack": "action",
    "climactic_execution": "action",
    "antagonist_pressure": "action",
    # Information missions → controlled pacing voice
    "foreshadow": "revelation",
    "midpoint_reframe": "revelation",
    # Internal missions → reflective voice
    "inner_demon_test": "emotional",
    "collapse": "emotional",
    "character_reveal": "emotional",
    "aftermath": "emotional",
    # Movement missions → efficient voice
    "world_normal": "transition",
    "stake_setup": "transition",
    "thread_advance": "transition",
    # Dialogue missions → subtext voice
    "response": "confrontation",
    "false_progress": "confrontation",
}

# ── Midpoint conversion instruction (Phase 3) ────────────────────────

MIDPOINT_CONVERSION_INSTRUCTION = (
    "MIDPOINT CONVERSION ACTIVE: The protagonist has shifted from reactive "
    "to proactive. Choices in this turn should include at least one option "
    "that represents the protagonist taking initiative — planning, acting "
    "boldly, confronting directly — rather than only defensive or "
    "investigative options. The protagonist is no longer running. They are "
    "fighting back."
)

# ── No-new-exposition warning (Phase 3) ──────────────────────────────

NO_NEW_EXPOSITION_WARNING = (
    "POST-SECOND-PLOT-POINT CHECK:\n"
    "The story has passed its Second Plot Point. No new core facts, NPCs, "
    "or plot elements should be introduced. If you are opening a new thread, "
    "it should reference previously established information — not introduce "
    "something entirely new. Flag any genuinely new exposition with "
    '"WARNING: new exposition post-SPP" in your reasoning.'
)


def check_midpoint_conversion(
    protagonist_mode: str,
    current_act_number: int,
    milestone_beat_sheet: Optional[dict],
) -> Optional[str]:
    """Return midpoint conversion instruction if post-midpoint."""
    if protagonist_mode in ("warrior", "martyr"):
        return MIDPOINT_CONVERSION_INSTRUCTION

    if milestone_beat_sheet:
        midpoint_act = milestone_beat_sheet.get("midpoint_act", 999)
        if current_act_number > midpoint_act:
            return MIDPOINT_CONVERSION_INSTRUCTION

    return None


def check_no_new_exposition(
    current_act_number: int,
    milestone_beat_sheet: Optional[dict],
) -> Optional[str]:
    """Return no-new-exposition warning if post-SPP."""
    if not milestone_beat_sheet:
        return None
    spp_act = milestone_beat_sheet.get("second_plot_point_act", 999)
    if current_act_number > spp_act:
        return NO_NEW_EXPOSITION_WARNING
    return None


VOICE_INSTRUCTIONS: dict[str, str] = {
    "action": (
        "VOICE: Crisp, short sentences. Minimal adjectives. "
        "Staccato pacing. Verbs carry the weight. Compress."
    ),
    "revelation": (
        "VOICE: Build toward the information delivery moment. "
        "The surrounding prose creates anticipation. Control pacing "
        "— slow before the reveal, then let it land."
    ),
    "emotional": (
        "VOICE: Internal access. Backstory callbacks welcome. "
        "Longer sentences. Physical sensation grounds the emotion. "
        "Show what the character feels in their body, not just their mind."
    ),
    "transition": (
        "VOICE: Clean and efficient. Move the player from A to B "
        "without lingering. No wasted words. Worldbuilding earns "
        "its space only if it's sensory and fresh."
    ),
    "confrontation": (
        "VOICE: Dialogue-forward. Subtext matters more than "
        "description. Characters speak indirectly — what they "
        "don't say matters as much as what they do."
    ),
}
