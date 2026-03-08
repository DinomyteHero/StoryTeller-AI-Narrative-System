"""
XP earning and behavioral inference (Game Mechanics §14.1-14.2).

Awards XP at act boundaries based on performance. The behavioral inference
engine analyzes player choice patterns and allocates XP to skill rank
increases automatically.

This module is pure Python — no LLM dependencies, no API keys.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional


# ── FFG XP cost tables ───────────────────────────────────────────────

def skill_rank_cost(new_rank: int, is_career: bool) -> int:
    """FFG skill rank XP cost: 5 × new_rank for career, +5 for non-career."""
    base = 5 * new_rank
    return base if is_career else base + 5


# ── Skill category mapping (for skill_breadth condition) ─────────────

SKILL_CATEGORIES: dict[str, str] = {
    # Combat
    "brawl": "combat", "gunnery": "combat", "melee": "combat",
    "ranged_light": "combat", "ranged_heavy": "combat", "lightsaber": "combat",
    # Social
    "charm": "social", "coercion": "social", "deception": "social",
    "leadership": "social", "negotiation": "social",
    # Knowledge
    "core_worlds": "knowledge", "education": "knowledge", "lore": "knowledge",
    "outer_rim": "knowledge", "underworld": "knowledge", "warfare": "knowledge",
    "xenology": "knowledge",
    # Technical
    "astrogation": "technical", "computers": "technical",
    "mechanics": "technical", "medicine": "technical",
    # Physical
    "athletics": "physical", "coordination": "physical",
    "resilience": "physical", "stealth": "physical", "survival": "physical",
    # Awareness
    "cool": "awareness", "discipline": "awareness",
    "perception": "awareness", "vigilance": "awareness",
    # Piloting
    "piloting_planetary": "piloting", "piloting_space": "piloting",
    # Underworld
    "skulduggery": "underworld_ops", "streetwise": "underworld_ops",
}


# ── Constants ────────────────────────────────────────────────────────

DEFAULT_BASE_XP = 20
BONUS_XP_PER_CONDITION = 5
XP_RESERVATION_RATIO = 0.4   # 40% reserved for milestones
RESERVED_XP_CAP = 60

# Behavioral inference weights (§14.2)
ASPIRATION_WEIGHT = 0.50
FAILURE_WEIGHT = 0.35
COMPETENCE_WEIGHT = 0.15
MIN_SCORE_THRESHOLD = 0.15
MAX_INFERENCE_RANK = 3


# ── Data classes ─────────────────────────────────────────────────────

@dataclass
class XPAward:
    """Breakdown of XP earned at an act boundary."""
    base_xp: int = 0
    bonus_conditions_met: list[str] = field(default_factory=list)
    bonus_xp: int = 0
    total_xp: int = 0
    inference_xp: int = 0   # after milestone reservation
    reserved_xp: int = 0


@dataclass
class SkillSignal:
    """Weighted behavioral signal for a single skill."""
    skill: str
    aspiration_score: float = 0.0
    failure_score: float = 0.0
    competence_score: float = 0.0
    weighted_total: float = 0.0


# ── XP Earning (§14.1) ──────────────────────────────────────────────

def award_act_xp(
    act_config: dict,
    turn_rows: list[dict],
    character,       # engine.character.Character
    arc_state: dict,
) -> XPAward:
    """
    Evaluate XP at act boundary (§14.1).
    Returns XPAward with base, bonus, reservation, and inference pool.
    """
    xp_config = act_config.get("xp_config", {})
    base = xp_config.get("base_xp", DEFAULT_BASE_XP)
    conditions = xp_config.get("bonus_conditions", [])

    met = []
    for cond in conditions:
        if _evaluate_condition(cond, turn_rows, character, arc_state):
            met.append(cond)

    bonus = len(met) * BONUS_XP_PER_CONDITION
    total = base + bonus

    # Milestone reservation (§14.2)
    current_reserved = getattr(character, "reserved_xp", 0)
    if current_reserved >= RESERVED_XP_CAP:
        reserved = 0
    else:
        reserved = min(
            int(total * XP_RESERVATION_RATIO),
            RESERVED_XP_CAP - current_reserved,
        )

    inference_pool = total - reserved

    logging.info(
        f"XP award: base={base}, bonus={bonus} ({met}), "
        f"total={total}, inference={inference_pool}, reserved={reserved}"
    )

    return XPAward(
        base_xp=base,
        bonus_conditions_met=met,
        bonus_xp=bonus,
        total_xp=total,
        inference_xp=inference_pool,
        reserved_xp=reserved,
    )


def _evaluate_condition(
    condition: str,
    turn_rows: list[dict],
    character,
    arc_state: dict,
) -> bool:
    """Evaluate a single bonus condition against the turn log."""
    if condition == "anchor_engagement":
        # Player reached the act's anchor beat
        return arc_state.get("act_progress", 0.0) >= 1.0

    elif condition == "skill_breadth":
        # 3+ different skill categories used in checks
        categories = set()
        for t in turn_rows:
            skill = t.get("check_skill")
            if skill and skill in SKILL_CATEGORIES:
                categories.add(SKILL_CATEGORIES[skill])
        return len(categories) >= 3

    elif condition == "motivation_interaction":
        # At least one action with moral_weight >= 2
        return any(t.get("moral_weight", 0) >= 2 for t in turn_rows)

    elif condition == "failure_engagement":
        # Failed a check and continued pursuing the goal (next 1-2 turns)
        for i, t in enumerate(turn_rows):
            rr_json = t.get("roll_result_json")
            if not rr_json:
                continue
            rr = json.loads(rr_json) if isinstance(rr_json, str) else rr_json
            if not rr.get("succeeded", True):
                # Player continued playing after failure
                if i + 1 < len(turn_rows):
                    return True
        return False

    return False


# ── Behavioral Inference (§14.2) ─────────────────────────────────────

def compute_behavioral_signals(
    turn_rows: list[dict],
) -> list[SkillSignal]:
    """
    Analyze the act's turn log for three behavioral signals (§14.2):
      1. Choice aspiration (50%) — skill tags on selected choices
      2. Failure learning (35%) — failed checks
      3. Practiced competence (15%) — successful checks

    Returns SkillSignal list sorted by weighted total (descending).
    """
    total_turns = len(turn_rows)
    if total_turns == 0:
        return []

    # Accumulate per-skill data
    skill_data: dict[str, dict] = {}

    # Signal 1: Choice Aspiration — skill tags on the player's selected choice
    for t in turn_rows:
        tags_json = t.get("skill_tags_json")
        if not tags_json:
            continue
        tags = json.loads(tags_json) if isinstance(tags_json, str) else tags_json
        choice_idx = t.get("choice_index", 0)
        if isinstance(tags, list) and 0 <= choice_idx < len(tags):
            tag = tags[choice_idx]
            if tag:
                skill_data.setdefault(tag, {
                    "aspirations": 0, "failures": 0,
                    "successes": 0, "threat_successes": 0,
                })
                skill_data[tag]["aspirations"] += 1

    # Signals 2 & 3: Failure Learning and Practiced Competence
    for t in turn_rows:
        skill = t.get("check_skill")
        if not skill:
            continue
        rr_json = t.get("roll_result_json")
        if not rr_json:
            continue
        rr = json.loads(rr_json) if isinstance(rr_json, str) else rr_json

        skill_data.setdefault(skill, {
            "aspirations": 0, "failures": 0,
            "successes": 0, "threat_successes": 0,
        })

        if not rr.get("succeeded", True):
            skill_data[skill]["failures"] += 1
        elif rr.get("outcome_quadrant") == "success_threat":
            skill_data[skill]["threat_successes"] += 1
        else:
            skill_data[skill]["successes"] += 1

    # Compute weighted scores
    signals = []
    for skill, data in skill_data.items():
        # Aspiration: frequency as fraction of total turns
        aspiration_freq = data["aspirations"] / total_turns
        if aspiration_freq >= 0.30:
            asp_score = 1.0
        elif aspiration_freq >= 0.15:
            asp_score = 0.5
        else:
            asp_score = 0.0

        # Failure: full weight for failures, half for threat successes
        fail_count = data["failures"] + data["threat_successes"] * 0.5
        fail_score = min(1.0, fail_count / max(1, total_turns * 0.2))

        # Competence: small credit for clean successes
        comp_score = min(1.0, data["successes"] / max(1, total_turns * 0.3))

        weighted = (
            asp_score * ASPIRATION_WEIGHT
            + fail_score * FAILURE_WEIGHT
            + comp_score * COMPETENCE_WEIGHT
        )

        signals.append(SkillSignal(
            skill=skill,
            aspiration_score=asp_score,
            failure_score=fail_score,
            competence_score=comp_score,
            weighted_total=weighted,
        ))

    signals.sort(key=lambda s: s.weighted_total, reverse=True)
    return signals


def select_and_apply_advancement(
    signals: list[SkillSignal],
    character,       # engine.character.Character
    inference_xp: int,
    act_number: int,
) -> Optional[dict]:
    """
    Select the highest-scoring affordable skill rank increase (§14.2).
    Applies it to the character and returns the advancement log entry.
    Returns None if no advancement is made.

    Constraints:
    - Max +1 rank per act (enforced by running once per act)
    - Max rank 3 via inference alone
    - Below minimum score threshold: no spend
    - Career skill tiebreaker when scores within 10%
    """
    career_skills = set(getattr(character, "career_skills", []))

    # Apply career skill tiebreaker: when two skills are within 10%,
    # prefer the career skill. We do this by giving career skills a
    # tiny boost for sorting purposes only (doesn't change stored score).
    def sort_key(s: SkillSignal):
        bonus = 0.001 if s.skill in career_skills else 0.0
        return s.weighted_total + bonus

    sorted_signals = sorted(signals, key=sort_key, reverse=True)

    for signal in sorted_signals:
        if signal.weighted_total < MIN_SCORE_THRESHOLD:
            break  # Below threshold — bank XP

        current_rank = character.get_skill_rank(signal.skill)
        new_rank = current_rank + 1

        # Max rank 3 via inference
        if new_rank > MAX_INFERENCE_RANK:
            continue

        is_career = signal.skill in career_skills
        cost = skill_rank_cost(new_rank, is_career)

        if cost > inference_xp:
            continue

        # Apply the advancement
        setattr(character.skills, signal.skill, new_rank)
        character.available_xp -= cost

        entry = {
            "type": "skill_rank",
            "skill": signal.skill,
            "old_rank": current_rank,
            "new_rank": new_rank,
            "cost": cost,
            "act": act_number,
            "is_career": is_career,
            "signal_score": round(signal.weighted_total, 3),
        }
        character.advancement_log.append(entry)

        logging.info(
            f"Behavioral inference: {signal.skill} {current_rank}->{new_rank} "
            f"(cost {cost} XP, score {signal.weighted_total:.3f}, "
            f"{'career' if is_career else 'non-career'})"
        )
        return entry

    logging.info(
        "Behavioral inference: no advancement — "
        "scores below threshold or insufficient XP"
    )
    return None
