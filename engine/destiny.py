"""
Destiny Point Pool (Game Mechanics §23).

Light Side and Dark Side Destiny Points modify the dice pool based
on narrative conditions. The pool flip mechanic creates push-pull
rhythm across the act.

This module is pure Python — no LLM dependencies, no API keys.
"""

import random
from dataclasses import dataclass, field
from engine.dice import DicePool, FORCE_TABLE, Symbol


# ── Data classes ──────────────────────────────────────────────────────

@dataclass
class DestinyResult:
    """Outcome of destiny evaluation for a single check."""
    light_spent:      bool = False
    dark_spent:       bool = False
    pool_modified:    bool = False
    narrative_note:   str = ""      # GM prompt guidance
    light_remaining:  int = 0
    dark_remaining:   int = 0


@dataclass
class DestinyState:
    """Persistent destiny pool state within an act."""
    light:                int = 0
    dark:                 int = 0
    light_spent_this_act: int = 0
    dark_spent_this_act:  int = 0

    def to_dict(self) -> dict:
        return {
            "destiny_light": self.light,
            "destiny_dark": self.dark,
            "destiny_light_spent_this_act": self.light_spent_this_act,
            "destiny_dark_spent_this_act": self.dark_spent_this_act,
        }

    @classmethod
    def from_session(cls, session: dict) -> "DestinyState":
        return cls(
            light=session.get("destiny_light", 0),
            dark=session.get("destiny_dark", 0),
            light_spent_this_act=session.get("destiny_light_spent_this_act", 0),
            dark_spent_this_act=session.get("destiny_dark_spent_this_act", 0),
        )


# ── Pool initialization ──────────────────────────────────────────────

def roll_initial_destiny() -> tuple[int, int]:
    """
    Roll one Force die to set the starting Destiny pool (§23.1).
    Returns (light_pips, dark_pips).
    """
    face = random.choice(FORCE_TABLE)
    light = sum(1 for s in face if s == Symbol.LIGHT)
    dark = sum(1 for s in face if s == Symbol.DARK)
    return light, dark


# ── Threshold and scoring ────────────────────────────────────────────

# Light Side destiny score threshold — higher = harder to trigger
_BASE_THRESHOLD = 0.55

# Scene type stakes multiplier
_SCENE_STAKES = {
    "combat":        1.3,
    "chase":         1.2,
    "infiltration":  1.1,
    "social":        0.9,
    "exploration":   0.7,
    "introspection": 0.5,
}

# Tension level base stakes
_TENSION_STAKES = {
    "calm":     0.3,
    "rising":   0.5,
    "high":     0.7,
    "critical": 0.9,
    "climax":   1.0,
}


def _compute_light_score(
    scene_type: str,
    tension_level: str,
    anchor_proximity: str,
    act_progress: float,
    ability_dice: int,
    total_positive_dice: int,
) -> float:
    """
    Compute the destiny score for Light Side spending (§23.2).
    Three factors: narrative stakes, mechanical impact, act position.
    """
    # Factor 1: Narrative stakes (scene + tension)
    scene_score = _SCENE_STAKES.get(scene_type, 0.8)
    tension_score = _TENSION_STAKES.get(tension_level, 0.5)
    stakes = (scene_score + tension_score) / 2.0

    # Anchor proximity bonus
    proximity_bonus = {
        "distant": 0.0,
        "approaching": 0.1,
        "imminent": 0.2,
        "reached": 0.3,
    }.get(anchor_proximity, 0.0)
    stakes += proximity_bonus

    # Factor 2: Mechanical impact — upgrading is more impactful
    # when you have fewer total positive dice
    if total_positive_dice > 0:
        impact = min(1.0, 1.0 / total_positive_dice)
    else:
        impact = 1.0

    # Factor 3: Act position — later in act = more destiny-worthy
    position = min(1.0, act_progress)

    # Combined score (weighted)
    return stakes * 0.45 + impact * 0.25 + position * 0.30


def _compute_escalation_modifier(
    light_spent_this_act: int,
    dark_spent_this_act: int,
) -> float:
    """
    Escalation pacing (§23.4): if player has received many Light Side
    spends without Dark Side, lower the threshold for Dark Side spending.
    Returns a modifier that adjusts the Dark Side threshold.
    """
    imbalance = light_spent_this_act - dark_spent_this_act
    if imbalance >= 2:
        # Lower Dark Side threshold (make it more likely)
        return -0.15 * imbalance
    return 0.0


# ── Core evaluation ──────────────────────────────────────────────────

def evaluate_destiny_spend(
    pool: DicePool,
    scene_type: str,
    tension_level: str,
    anchor_proximity: str,
    act_progress: float,
    destiny: DestinyState,
    obligation_active: bool = False,
    npc_disposition_below_threshold: bool = False,
    spine_dark_trigger: bool = False,
) -> DestinyResult:
    """
    Stage 4 of pool modification pipeline (§23.5).

    Evaluates Light Side and Dark Side spending conditions.
    Modifies pool in place if triggered. Returns DestinyResult
    with narrative guidance for GM prompt.

    Both Light and Dark can fire on the same check.
    """
    result = DestinyResult(
        light_remaining=destiny.light,
        dark_remaining=destiny.dark,
    )

    # ── Light Side evaluation ────────────────────────────────────
    if destiny.light > 0:
        total_positive = pool.ability + pool.proficiency
        score = _compute_light_score(
            scene_type, tension_level, anchor_proximity,
            act_progress, pool.ability, total_positive,
        )

        if score >= _BASE_THRESHOLD and pool.ability > 0:
            # Upgrade one ability → proficiency
            pool.ability -= 1
            pool.proficiency += 1
            destiny.light -= 1
            destiny.dark += 1
            destiny.light_spent_this_act += 1

            result.light_spent = True
            result.pool_modified = True
            result.light_remaining = destiny.light
            result.dark_remaining = destiny.dark
            result.narrative_note = (
                "DESTINY (LIGHT SIDE SPENT — REQUIRED BEAT): This check was "
                "touched by fate. You MUST include exactly one sentence of "
                "interior recognition where the protagonist NOTICES that "
                "something just went better than it should have — a held breath, "
                "a flicker of disbelief, an instinct that arrived a half-second "
                "before it should have. The player needs to feel the universe "
                "step in. Do not narrate this as skill or competence. Frame it "
                "as fortune the character can feel. One sentence, no more."
            )

    # ── Dark Side evaluation ─────────────────────────────────────
    if destiny.dark > 0:
        dark_threshold = 0.6  # base threshold for Dark Side
        dark_score = 0.0

        # Condition 1: Obligation active (§23.3)
        if obligation_active:
            dark_score += 0.4

        # Condition 2: Antagonist engagement
        if npc_disposition_below_threshold:
            dark_score += 0.3

        # Condition 3: Spine-authored trigger
        if spine_dark_trigger:
            dark_score += 0.5

        # Escalation pacing — adjust threshold based on Light/Dark imbalance
        escalation = _compute_escalation_modifier(
            destiny.light_spent_this_act, destiny.dark_spent_this_act,
        )
        dark_threshold += escalation

        if dark_score >= dark_threshold and pool.difficulty > 0:
            # Upgrade one difficulty → challenge
            pool.difficulty -= 1
            pool.challenge += 1
            destiny.dark -= 1
            destiny.light += 1
            destiny.dark_spent_this_act += 1

            result.dark_spent = True
            result.pool_modified = True
            result.light_remaining = destiny.light
            result.dark_remaining = destiny.dark

            dark_note = (
                "DESTINY (DARK SIDE SPENT — REQUIRED BEAT): Fate worked "
                "against the character this time. You MUST include exactly "
                "one sentence where the protagonist NOTICES the world tilting "
                "wrong — a sudden chill, a piece of equipment betraying them, "
                "a coincidence that lands the wrong way. The player needs to "
                "feel the galaxy push back. Frame the difficulty as "
                "environmental or circumstantial, not as character incompetence. "
                "One sentence, no more."
            )
            if result.narrative_note:
                result.narrative_note += "\n\n" + dark_note
            else:
                result.narrative_note = dark_note

    return result


# ── Seize-the-moment choice generation (§23.4) ──────────────────────

def build_seize_the_moment_choice() -> dict:
    """
    Generate the seize-the-moment pre-roll narrative choice.
    Returns a dict with the two options. Only called when
    seize_the_moment is true in spine AND light > 0.
    """
    return {
        "offered": True,
        "options": [
            {
                "label": "Trust the moment — everything on this one.",
                "effect": "spend_light",
            },
            {
                "label": "Stay steady — no need to overcommit.",
                "effect": "normal",
            },
        ],
    }
