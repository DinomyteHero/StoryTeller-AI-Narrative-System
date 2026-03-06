from enum import Enum                          # required — do not omit
from engine.dice import DicePool
from engine.character import Character, SKILL_CHARACTERISTICS
from dataclasses import dataclass


class Difficulty(Enum):
    SIMPLE     = 0   # no purple dice — automatic success
    EASY       = 1   # 1 purple
    AVERAGE    = 2   # 2 purple
    HARD       = 3   # 3 purple
    DAUNTING   = 4   # 4 purple
    FORMIDABLE = 5   # 5 purple


DIFFICULTY_LABELS: dict[str, Difficulty] = {
    "simple":     Difficulty.SIMPLE,
    "easy":       Difficulty.EASY,
    "average":    Difficulty.AVERAGE,
    "hard":       Difficulty.HARD,
    "daunting":   Difficulty.DAUNTING,
    "formidable": Difficulty.FORMIDABLE,
}


@dataclass
class CheckRequest:
    skill:       str
    difficulty:  Difficulty
    boost_dice:  int = 0
    setback_dice:int = 0
    force_dice:  int = 0


def _stage_1_base_pool(character: Character, check: CheckRequest) -> DicePool:
    """
    Stage 1 — Base pool construction.
    Standard FFG formula: max(characteristic, skill_rank) ability dice,
    upgrade min(characteristic, skill_rank) to proficiency. Add difficulty
    dice. Situational boost/setback from check decision.
    """
    skill_name     = check.skill.lower().replace(" ", "_").replace("-", "_")
    governing_char = SKILL_CHARACTERISTICS.get(skill_name)

    if governing_char is None:
        raise ValueError(f"Unknown skill: {check.skill!r}")

    char_value   = character.get_characteristic(governing_char)
    skill_rank   = character.get_skill_rank(skill_name)
    total_dice   = max(char_value, skill_rank)
    prof_dice    = min(char_value, skill_rank)
    ability_dice = total_dice - prof_dice

    return DicePool(
        ability=ability_dice,
        proficiency=prof_dice,
        difficulty=check.difficulty.value,
        challenge=0,
        boost=check.boost_dice,
        setback=check.setback_dice,
        force=check.force_dice,
    )


# ── Pipeline stages 2-5 (post-V1) ─────────────────────────────────────
# Each stage takes a DicePool and returns a modified DicePool.
# Stage 2: Passive talent modifiers (Phase 11)
# Stage 3: Conditional talent modifiers (Phase 11)
# Stage 4: Destiny Point modification (Phase 11.5)
# Stage 5: Force dice addition (Phase 14)
# See Game Mechanics §23.5 for the full pipeline specification.


def build_pool(character: Character, check: CheckRequest, **kwargs) -> DicePool:
    """
    Full pool modification pipeline.

    V1 runs Stage 1 only. Post-V1 phases insert stages by adding
    calls between Stage 1 and return. Each stage function accepts
    and returns a DicePool, plus whatever additional context it needs
    via kwargs.

    Pipeline order (Game Mechanics §23.5):
      Stage 1 — Base pool construction (V1)
      Stage 2 — Passive talent modifiers (post-V1)
      Stage 3 — Conditional talent modifiers (post-V1)
      Stage 4 — Destiny Point modification (post-V1)
      Stage 5 — Force dice addition (post-V1)
    """
    pool = _stage_1_base_pool(character, check)
    # Stage 2: pool = _stage_2_passive_talents(pool, talents)
    # Stage 3: pool = _stage_3_conditional_talents(pool, talents, scene_ctx)
    # Stage 4: pool = _stage_4_destiny(pool, destiny_state, arc_state)
    # Stage 5: pool = _stage_5_force(pool, character)
    return pool


def describe_pool_for_display(pool: DicePool) -> dict:
    """
    Return a display-friendly dict for the frontend dice panel.
    Only includes die types actually present (count > 0).
    """
    all_dice = [
        {"type": "proficiency", "count": pool.proficiency, "color": "yellow"},
        {"type": "ability",     "count": pool.ability,     "color": "green"},
        {"type": "challenge",   "count": pool.challenge,   "color": "red"},
        {"type": "difficulty",  "count": pool.difficulty,   "color": "purple"},
        {"type": "boost",       "count": pool.boost,        "color": "blue"},
        {"type": "setback",     "count": pool.setback,      "color": "black"},
        {"type": "force",       "count": pool.force,        "color": "white"},
    ]
    return {
        "dice": [d for d in all_dice if d["count"] > 0],
        "description": pool.description(),
    }
