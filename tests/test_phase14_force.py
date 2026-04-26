"""
Phase 14: Force Dice Resolution — Tests

Verifies all 8 success criteria:
1. Force Rating 1 character rolls 1 Force die on force_use check
2. Light pips >= requirement → Force succeeds, no Conflict
3. Light pips insufficient, light + dark >= requirement → temptation presented
4. Player accepts temptation → Force succeeds, Conflict + strain
5. Player rejects temptation → Force fails, no Conflict
6. Dark-dominant (Morality < 40) → dark pips free, light pips cost strain
7. Four-result matrix produces correct narration guidance
8. Check decision prompt includes FORCE POWERS section (structural)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch
from dataclasses import asdict

from engine.dice import DicePool, RollResult, roll_pool
from engine.character import (
    Character, Species, Career, Characteristics, SkillRanks,
    MotivationTrack, GameLine,
)
from engine.checks import build_pool, build_pure_force_pool, CheckRequest, Difficulty
from engine.force import (
    ForceResolution,
    ForceResult,
    apply_temptation_choice,
    build_clean_success,
    build_force_result_block,
    build_force_state_block,
    build_temptation_choice,
    build_total_failure,
    get_available_force_dice,
    resolve_force_pips,
)
from gm.context import ArcState, ContextPackage
from gm.local_gm import CheckDecision, _validate_decision


# ── Test fixtures ──────────────────────────────────────────────────────

def make_force_character(
    force_rating=1,
    force_committed=0,
    morality=50,
    conflict=0,
) -> Character:
    """Create a Force-sensitive character for testing."""
    return Character(
        name="Kael Dren",
        species=Species.HUMAN,
        career=Career.GUARDIAN,
        specializations=["guardian_protector"],
        primary_game_line=GameLine.FORCE_AND_DESTINY,
        characteristics=Characteristics(
            brawn=2, agility=2, intellect=3, cunning=2, willpower=3, presence=2,
        ),
        skills=SkillRanks(
            discipline=2, athletics=1, lightsaber=2, perception=1,
        ),
        wound_threshold=12,
        strain_threshold=14,
        soak=2,
        force_rating=force_rating,
        force_committed=force_committed,
        motivation=MotivationTrack(morality=morality, conflict=conflict),
    )


def make_roll_result(light=0, dark=0, successes=0, failures=0) -> RollResult:
    """Create a RollResult with specified Force pip values."""
    net = successes - failures
    return RollResult(
        raw_successes=successes,
        raw_failures=failures,
        raw_light=light,
        raw_dark=dark,
        net_successes=net,
        light_pips=light,
        dark_pips=dark,
        succeeded=net > 0,
        outcome_quadrant=(
            "success_advantage" if net > 0 else "failure_threat"
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# SUCCESS CRITERION 1: Force Rating 1 rolls 1 Force die
# ═══════════════════════════════════════════════════════════════════════

class TestForceDiceInPool:
    def test_force_rating_1_adds_1_force_die(self):
        """A Force Rating 1 character gets 1 Force die in pool."""
        char = make_force_character(force_rating=1)
        check = CheckRequest(
            skill="discipline", difficulty=Difficulty.AVERAGE,
        )
        pool, _, _ = build_pool(char, check, force_use=True)
        assert pool.force == 1

    def test_force_rating_2_adds_2_force_dice(self):
        char = make_force_character(force_rating=2)
        check = CheckRequest(
            skill="discipline", difficulty=Difficulty.AVERAGE,
        )
        pool, _, _ = build_pool(char, check, force_use=True)
        assert pool.force == 2

    def test_committed_dice_reduce_available(self):
        char = make_force_character(force_rating=2, force_committed=1)
        check = CheckRequest(
            skill="discipline", difficulty=Difficulty.AVERAGE,
        )
        pool, _, _ = build_pool(char, check, force_use=True)
        assert pool.force == 1

    def test_no_force_dice_without_force_use(self):
        """Force-sensitive character without force_use gets no Force dice."""
        char = make_force_character(force_rating=1)
        check = CheckRequest(
            skill="discipline", difficulty=Difficulty.AVERAGE,
        )
        pool, _, _ = build_pool(char, check)
        assert pool.force == 0

    def test_non_force_character_no_dice(self):
        """Non-Force character gets no Force dice even with force_use."""
        char = make_force_character(force_rating=0)
        check = CheckRequest(
            skill="discipline", difficulty=Difficulty.AVERAGE,
        )
        pool, _, _ = build_pool(char, check, force_use=True)
        assert pool.force == 0

    def test_pure_force_pool_only_force_dice(self):
        """Pure Force pool has only Force + boost + setback, no skill dice."""
        char = make_force_character(force_rating=2)
        pool = build_pure_force_pool(char, boost_dice=1)
        assert pool.force == 2
        assert pool.boost == 1
        assert pool.ability == 0
        assert pool.proficiency == 0
        assert pool.difficulty == 0
        assert pool.challenge == 0

    def test_get_available_force_dice(self):
        char = make_force_character(force_rating=3, force_committed=1)
        assert get_available_force_dice(char) == 2

    def test_get_available_force_dice_zero_floor(self):
        char = make_force_character(force_rating=1, force_committed=2)
        assert get_available_force_dice(char) == 0


# ═══════════════════════════════════════════════════════════════════════
# SUCCESS CRITERION 2: Light pips >= requirement → clean success
# ═══════════════════════════════════════════════════════════════════════

class TestCleanSuccess:
    def test_light_pips_sufficient(self):
        """Light pips >= required → Force succeeds, no temptation."""
        roll = make_roll_result(light=2, dark=1)
        res = resolve_force_pips(roll, pips_required=1, morality=60)
        assert res.force_succeeded is True
        assert res.temptation_available is False

    def test_clean_success_no_conflict(self):
        roll = make_roll_result(light=2, dark=0)
        result = build_clean_success(roll, pips_required=1, morality=60)
        assert result.force_succeeded is True
        assert result.conflict_earned == 0
        assert result.strain_charged == 0
        assert result.temptation_offered is False

    def test_clean_success_light_dominant_narrative(self):
        roll = make_roll_result(light=2, dark=0)
        result = build_clean_success(roll, pips_required=1, morality=60)
        assert "light side" in result.narrative_note.lower()
        assert "SUCCESS" in result.narrative_note


# ═══════════════════════════════════════════════════════════════════════
# SUCCESS CRITERION 3: Temptation presented when pips mixed
# ═══════════════════════════════════════════════════════════════════════

class TestTemptationAvailability:
    def test_light_insufficient_but_total_sufficient(self):
        """Temptation fires when light < required but light + dark >= required."""
        roll = make_roll_result(light=0, dark=2)
        res = resolve_force_pips(roll, pips_required=1, morality=60)
        assert res.force_succeeded is False
        assert res.temptation_available is True
        assert res.pips_needed_from_costly_side == 1

    def test_temptation_choice_structure(self):
        """Temptation choice has correct structure."""
        roll = make_roll_result(light=0, dark=2)
        res = resolve_force_pips(roll, pips_required=1, morality=60)
        choice = build_temptation_choice(res, force_power="move")
        assert choice["offered"] is True
        assert choice["is_dark_temptation"] is True
        assert choice["is_inverted"] is False
        assert len(choice["options"]) == 2
        assert choice["options"][0]["effect"] == "reject"
        assert choice["options"][1]["effect"] == "accept"

    def test_total_insufficient_no_temptation(self):
        """No temptation when total pips < required."""
        roll = make_roll_result(light=0, dark=0)
        res = resolve_force_pips(roll, pips_required=1, morality=60)
        assert res.force_succeeded is False
        assert res.temptation_available is False


# ═══════════════════════════════════════════════════════════════════════
# SUCCESS CRITERION 4: Accept temptation → succeed + costs
# ═══════════════════════════════════════════════════════════════════════

class TestTemptationAccept:
    def test_accept_light_dominant_earns_conflict(self):
        """Accepting costs Conflict equal to dark pips used."""
        roll = make_roll_result(light=0, dark=2)
        res = resolve_force_pips(roll, pips_required=1, morality=60)
        result = apply_temptation_choice(res, accepted=True)
        assert result.force_succeeded is True
        assert result.temptation_accepted is True
        assert result.conflict_earned == 1  # needed 1 dark pip
        assert result.strain_charged == 1

    def test_accept_light_dominant_2_pips_needed(self):
        """Two dark pips needed = 2 Conflict + 2 strain."""
        roll = make_roll_result(light=0, dark=3)
        res = resolve_force_pips(roll, pips_required=2, morality=75)
        result = apply_temptation_choice(res, accepted=True)
        assert result.force_succeeded is True
        assert result.conflict_earned == 2
        assert result.strain_charged == 2

    def test_accept_grey_reduced_strain(self):
        """Grey characters (41-70) get strain -1 (min 1)."""
        roll = make_roll_result(light=0, dark=3)
        res = resolve_force_pips(roll, pips_required=2, morality=50)
        result = apply_temptation_choice(res, accepted=True)
        assert result.conflict_earned == 2
        assert result.strain_charged == 1  # 2-1=1 (grey reduction)

    def test_accept_narrative_mentions_dark_side(self):
        roll = make_roll_result(light=0, dark=2)
        res = resolve_force_pips(roll, pips_required=1, morality=60)
        result = apply_temptation_choice(res, accepted=True)
        assert "dark side" in result.narrative_note.lower()


# ═══════════════════════════════════════════════════════════════════════
# SUCCESS CRITERION 5: Reject temptation → Force fails, no Conflict
# ═══════════════════════════════════════════════════════════════════════

class TestTemptationReject:
    def test_reject_force_fails(self):
        roll = make_roll_result(light=0, dark=2)
        res = resolve_force_pips(roll, pips_required=1, morality=60)
        result = apply_temptation_choice(res, accepted=False)
        assert result.force_succeeded is False
        assert result.temptation_accepted is False
        assert result.conflict_earned == 0
        assert result.strain_charged == 0

    def test_reject_narrative_affirming(self):
        roll = make_roll_result(light=0, dark=2)
        res = resolve_force_pips(roll, pips_required=1, morality=60)
        result = apply_temptation_choice(res, accepted=False)
        assert "light-side-affirming" in result.narrative_note.lower()


# ═══════════════════════════════════════════════════════════════════════
# SUCCESS CRITERION 6: Dark-dominant character polarity inversion
# ═══════════════════════════════════════════════════════════════════════

class TestDarkDominant:
    def test_dark_pips_free_for_dark_dominant(self):
        """Dark-dominant: dark pips >= required → clean success."""
        roll = make_roll_result(light=0, dark=2)
        res = resolve_force_pips(roll, pips_required=1, morality=30)
        assert res.force_succeeded is True
        assert res.is_dark_dominant is True
        assert res.temptation_available is False

    def test_light_pips_cost_strain_for_dark_dominant(self):
        """Dark-dominant: using light pips costs strain, not Conflict."""
        roll = make_roll_result(light=2, dark=0)
        res = resolve_force_pips(roll, pips_required=1, morality=30)
        # Dark pips insufficient (0), but light available
        assert res.force_succeeded is False
        assert res.temptation_available is True
        assert res.strain_cost >= 1
        assert res.conflict_cost == 0  # no Conflict for using light side

    def test_dark_dominant_temptation_inverted(self):
        """Dark-dominant temptation is inverted."""
        roll = make_roll_result(light=2, dark=0)
        res = resolve_force_pips(roll, pips_required=1, morality=30)
        choice = build_temptation_choice(res)
        assert choice["is_inverted"] is True

    def test_dark_dominant_accept_costs_strain_not_conflict(self):
        """Accepting inverted temptation (reaching for light): strain, no Conflict."""
        roll = make_roll_result(light=2, dark=0)
        res = resolve_force_pips(roll, pips_required=1, morality=30)
        result = apply_temptation_choice(res, accepted=True)
        assert result.force_succeeded is True
        assert result.conflict_earned == 0
        assert result.strain_charged >= 1

    def test_dark_dominant_reject_force_fails(self):
        """Rejecting inverted temptation: Force fails (dark pips insufficient)."""
        roll = make_roll_result(light=2, dark=0)
        res = resolve_force_pips(roll, pips_required=1, morality=30)
        result = apply_temptation_choice(res, accepted=False)
        assert result.force_succeeded is False
        assert result.conflict_earned == 0
        assert result.strain_charged == 0

    def test_dark_dominant_clean_success_narrative(self):
        roll = make_roll_result(light=0, dark=2)
        result = build_clean_success(roll, pips_required=1, morality=30)
        assert "dark side" in result.narrative_note.lower()
        assert "command" in result.narrative_note.lower() or "eager" in result.narrative_note.lower()


# ═══════════════════════════════════════════════════════════════════════
# SUCCESS CRITERION 7: Four-result matrix
# ═══════════════════════════════════════════════════════════════════════

class TestFourResultMatrix:
    def test_skill_success_force_success(self):
        force_result = ForceResult(force_succeeded=True, pips_required=1)
        block = build_force_result_block(force_result, skill_succeeded=True, morality=60)
        assert "Success + Force success" in block

    def test_skill_success_force_failure(self):
        force_result = ForceResult(force_succeeded=False, pips_required=1)
        block = build_force_result_block(force_result, skill_succeeded=True, morality=60)
        assert "Success + Force failure" in block

    def test_skill_failure_force_success(self):
        force_result = ForceResult(force_succeeded=True, pips_required=1)
        block = build_force_result_block(force_result, skill_succeeded=False, morality=60)
        assert "Failure + Force success" in block

    def test_skill_failure_force_failure(self):
        force_result = ForceResult(force_succeeded=False, pips_required=1)
        block = build_force_result_block(force_result, skill_succeeded=False, morality=60)
        assert "Failure + Force failure" in block

    def test_pure_force_no_matrix(self):
        """Pure Force action (no skill) → no four-result matrix."""
        force_result = ForceResult(force_succeeded=True, pips_required=1)
        block = build_force_result_block(force_result, skill_succeeded=None, morality=60)
        assert "MATRIX" not in block

    def test_pure_force_context_does_not_emit_skill_failure(self):
        """Pure Force dice must not look like a failed mundane check."""
        char = make_force_character(force_rating=1)
        arc = ArcState(
            campaign_name="Test",
            current_act=1,
            total_acts=4,
            act_name="Opening",
            act_progress=0.4,
            current_anchor="test",
            next_anchor="next",
            anchors_completed=[],
            throughline_question="?",
            tension_level="rising",
            open_threads=[],
            closed_threads=[],
        )
        ctx = ContextPackage(
            character=char,
            arc=arc,
            story_summary="",
            recent_turns=[],
            active_npcs=[],
            location="Yavin 4",
            situation="Reach out with Sense.",
            dice_pool=DicePool(force=1),
            roll_result=make_roll_result(light=1, dark=0),
            force_result_block=build_force_result_block(
                ForceResult(force_succeeded=True, pips_required=1),
                skill_succeeded=None,
                morality=60,
            ),
            force_check_kind="pure",
        )

        block = ctx.build_dice_result_block()

        assert "FORCE DICE RESULT (PURE FORCE ACTION)" in block
        assert "DICE CHECK RESULT" not in block
        assert "FAILED" not in block
        assert "FORCE RESULT block below is authoritative" in block

    def test_morality_band_tone_light(self):
        force_result = ForceResult(force_succeeded=True, pips_required=1)
        block = build_force_result_block(force_result, skill_succeeded=None, morality=80)
        assert "light-dominant" in block

    def test_morality_band_tone_grey(self):
        force_result = ForceResult(force_succeeded=True, pips_required=1)
        block = build_force_result_block(force_result, skill_succeeded=None, morality=50)
        assert "grey" in block.lower()

    def test_morality_band_tone_dark(self):
        force_result = ForceResult(force_succeeded=True, pips_required=1)
        block = build_force_result_block(force_result, skill_succeeded=None, morality=20)
        assert "dark-dominant" in block


# ═══════════════════════════════════════════════════════════════════════
# SUCCESS CRITERION 8: Check decision prompt includes FORCE POWERS
# ═══════════════════════════════════════════════════════════════════════

class TestCheckDecisionForceFields:
    def test_validate_decision_force_enhanced(self):
        """Check decision with force_use produces correct CheckDecision."""
        data = {
            "requires_check": True,
            "skill": "athletics",
            "difficulty": "hard",
            "force_use": True,
            "force_pips_required": 1,
            "scene_type": "combat",
            "moral_weight": 1,
            "reasoning": "Force-enhanced leap",
        }
        decision = _validate_decision(data)
        assert decision.requires_check is True
        assert decision.force_use is True
        assert decision.force_pips_required == 1
        assert decision.skill == "athletics"

    def test_validate_decision_pure_force(self):
        """Pure Force action: force_use=true, no skill/difficulty."""
        data = {
            "requires_check": True,
            "force_use": True,
            "force_pips_required": 2,
            "scene_type": "social",
            "moral_weight": 2,
            "reasoning": "Mind trick",
        }
        decision = _validate_decision(data)
        assert decision.requires_check is True
        assert decision.force_use is True
        assert decision.skill is None
        assert decision.force_pips_required == 2

    def test_validate_decision_no_force(self):
        """Non-Force check: force_use defaults to False."""
        data = {
            "requires_check": True,
            "skill": "deception",
            "difficulty": "average",
            "scene_type": "social",
            "moral_weight": 0,
            "reasoning": "Lying",
        }
        decision = _validate_decision(data)
        assert decision.force_use is False
        assert decision.force_pips_required == 0

    def test_prompt_includes_force_section(self):
        """Check decision prompt template has {force_section} placeholder."""
        from pathlib import Path
        prompt_path = Path(__file__).parent.parent / "gm" / "prompts" / "check_decision.txt"
        content = prompt_path.read_text(encoding="utf-8")
        assert "{force_section}" in content


# ═══════════════════════════════════════════════════════════════════════
# Context builders
# ═══════════════════════════════════════════════════════════════════════

class TestForceContextBuilders:
    def test_force_state_block_force_sensitive(self):
        char = make_force_character(force_rating=2, force_committed=1, morality=75)
        block = build_force_state_block(char)
        assert "Force Rating: 2 (1 available)" in block
        assert "Light side dominant" in block
        assert "Committed dice: 1" in block

    def test_force_state_block_non_force(self):
        char = make_force_character(force_rating=0)
        block = build_force_state_block(char)
        assert block == ""

    def test_total_failure_narrative(self):
        roll = make_roll_result(light=0, dark=0)
        result = build_total_failure(roll, pips_required=1)
        assert result.force_succeeded is False
        assert "insufficient" in result.narrative_note.lower()
        assert result.conflict_earned == 0


# ═══════════════════════════════════════════════════════════════════════
# Integration: Force dice actually roll
# ═══════════════════════════════════════════════════════════════════════

class TestForceDiceRoll:
    def test_force_pool_generates_pips(self):
        """Rolling Force dice produces light and/or dark pips."""
        char = make_force_character(force_rating=2)
        pool = build_pure_force_pool(char)
        assert pool.force == 2
        result = roll_pool(pool)
        total_pips = result.light_pips + result.dark_pips
        assert total_pips > 0  # 2 Force dice always generate at least 1 pip

    def test_force_enhanced_pool_has_skill_and_force_dice(self):
        """Force-enhanced check has both skill dice and Force dice."""
        char = make_force_character(force_rating=1)
        check = CheckRequest(
            skill="discipline", difficulty=Difficulty.AVERAGE,
        )
        pool, _, _ = build_pool(char, check, force_use=True)
        # Should have skill dice (Willpower 3, Discipline 2)
        assert pool.ability + pool.proficiency > 0
        # Should have difficulty dice
        assert pool.difficulty == 2  # AVERAGE
        # Should have 1 Force die
        assert pool.force == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
