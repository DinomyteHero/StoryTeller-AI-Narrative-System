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


# ── Pipeline stages 2-5 (Game Mechanics §23.5) ────────────────────────
# Stage 1: Base pool construction (V1)
# Stage 2: Passive talent modifiers (Phase 11)
# Stage 3: Conditional talent modifiers (Phase 11)
# Stage 4: Destiny Point modification (Phase 11.5) — empty slot
# Stage 5: Force dice addition (Phase 14) — empty slot


def build_pool(
    character: Character,
    check: CheckRequest,
    scene_type: str = "",
    **kwargs,
) -> tuple[DicePool, list, "DestinyResult | None"]:
    """
    Full pool modification pipeline (Game Mechanics §23.5).

    Returns (pool, talent_activations, destiny_result) — the modified
    dice pool, a list of TalentActivation records for narration context,
    and the destiny evaluation result (None if no destiny state passed).

    Pipeline order:
      Stage 1 — Base pool construction
      Stage 2 — Passive talent modifiers (§15.3)
      Stage 3 — Conditional talent modifiers (§15.3)
      Stage 4 — Destiny Point modification (Phase 11.5)
      Stage 5 — Force dice addition (Phase 14 — pass-through)
    """
    from engine.talents import apply_passive_modifiers, apply_conditional_modifiers

    pool = _stage_1_base_pool(character, check)
    activations = []

    # Stage 2: Passive talent modifiers
    skill_name = check.skill.lower().replace(" ", "_").replace("-", "_")
    passive_acts = apply_passive_modifiers(pool, character, skill_name)
    activations.extend(passive_acts)

    # Stage 3: Conditional talent modifiers
    conditional_acts = apply_conditional_modifiers(
        pool, character, scene_type, check_skill=skill_name,
    )
    activations.extend(conditional_acts)

    # Stage 4: Destiny Point modification (Phase 11.5)
    destiny_result = None
    destiny_state = kwargs.get("destiny_state")
    if destiny_state is not None:
        from engine.destiny import evaluate_destiny_spend
        destiny_result = evaluate_destiny_spend(
            pool=pool,
            scene_type=scene_type,
            tension_level=kwargs.get("tension_level", "rising"),
            anchor_proximity=kwargs.get("anchor_proximity", "distant"),
            act_progress=kwargs.get("act_progress", 0.0),
            destiny=destiny_state,
            obligation_active=kwargs.get("obligation_active", False),
            npc_disposition_below_threshold=kwargs.get("npc_disposition_below_threshold", False),
            spine_dark_trigger=kwargs.get("spine_dark_trigger", False),
        )

    # Stage 5: Force dice addition (Phase 14 — pass-through)
    # pool = _stage_5_force(pool, character)

    return pool, activations, destiny_result


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
