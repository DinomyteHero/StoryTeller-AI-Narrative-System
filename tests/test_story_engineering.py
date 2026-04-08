"""
Tests for CS-6 Story Engineering Integration — runtime components.

Covers: Phase 1 (Dramatic Mission), Phase 2 (Pinch Points, runtime),
Phase 5 (Foreshadow, runtime), Phase 6 (Inner-Conflict Arc),
Phase 7 (Scene Purpose Validator), Phase 8 (Closure Heartbeats),
Phase 10 (Voice Mode Tags).
"""

import json
import pytest

# ═════════════════════════════════════════════════════════════════════
# Phase 1: Dramatic Mission Layer
# ═════════════════════════════════════════════════════════════════════

from engine.dramatic_mission import (
    DramaticMission,
    MissionContext,
    PART_MISSION_MAP,
    MISSION_DEFINITIONS,
    compute_valid_missions,
    get_story_part,
)


class TestGetStoryPart:
    """Test get_story_part() mapping from dramatic_function to Brooks part."""

    def test_setup_function(self):
        assert get_story_part("setup", 0.0) == "setup"
        assert get_story_part("destabilization", 0.1) == "setup"

    def test_response_function(self):
        assert get_story_part("launch", 0.3) == "response"

    def test_attack_function(self):
        assert get_story_part("midpoint_shift", 0.5) == "attack"
        assert get_story_part("escalation", 0.6) == "attack"

    def test_resolution_function(self):
        assert get_story_part("confrontation", 0.8) == "resolution"
        assert get_story_part("consequence", 0.9) == "resolution"
        assert get_story_part("resolution", 1.0) == "resolution"

    def test_fallback_by_progress(self):
        """When no dramatic_function, infer from campaign progress."""
        assert get_story_part("", 0.1) == "setup"
        assert get_story_part("", 0.3) == "response"
        assert get_story_part("", 0.6) == "attack"
        assert get_story_part("", 0.8) == "resolution"

    def test_unknown_function_falls_back(self):
        """Unknown dramatic_function should fall back to progress."""
        assert get_story_part("unknown_function", 0.1) == "setup"
        assert get_story_part("unknown_function", 0.6) == "attack"


class TestComputeValidMissions:
    """Test compute_valid_missions() constraint logic."""

    def test_setup_only_allows_setup_missions(self):
        missions = compute_valid_missions("setup", 0.1, 0.1)
        assert "stake_setup" in missions
        assert "world_normal" in missions
        assert "foreshadow" in missions
        assert "character_reveal" in missions
        assert "thread_advance" in missions
        # Resolution missions should NOT be valid in setup
        assert "collapse" not in missions
        assert "climactic_execution" not in missions
        assert "aftermath" not in missions

    def test_resolution_only_allows_resolution_missions(self):
        missions = compute_valid_missions("confrontation", 0.9, 0.9)
        assert "collapse" in missions
        assert "climactic_execution" in missions
        assert "aftermath" in missions
        assert "character_reveal" in missions
        # Setup missions should NOT be valid in resolution
        assert "stake_setup" not in missions
        assert "world_normal" not in missions

    def test_response_missions(self):
        missions = compute_valid_missions("launch", 0.3, 0.3)
        assert "response" in missions
        assert "false_progress" in missions
        assert "antagonist_pressure" in missions
        assert "foreshadow" in missions

    def test_attack_missions(self):
        missions = compute_valid_missions("midpoint_shift", 0.5, 0.5)
        assert "attack" in missions
        assert "inner_demon_test" in missions
        assert "antagonist_pressure" in missions

    def test_fallback_progress_based(self):
        """Without dramatic_function, uses overall campaign progress."""
        setup_missions = compute_valid_missions("", 0.5, 0.1)
        assert "stake_setup" in setup_missions

        resolution_missions = compute_valid_missions("", 0.5, 0.9)
        assert "collapse" in resolution_missions

    def test_all_missions_have_definitions(self):
        """Every mission enum value has a definition string."""
        for mission in DramaticMission:
            assert mission.value in MISSION_DEFINITIONS, (
                f"Mission {mission.value} has no definition"
            )


class TestMissionContext:
    """Test MissionContext Pydantic model."""

    def test_valid_mission_context(self):
        ctx = MissionContext(
            valid_missions=["response", "false_progress"],
            selected_mission="response",
            mission_instruction="React to the ambush.",
            scene_thrust_instruction="End with the character cornered.",
        )
        assert ctx.selected_mission == "response"

    def test_empty_defaults(self):
        ctx = MissionContext(valid_missions=["response"])
        assert ctx.selected_mission == ""
        assert ctx.mission_instruction == ""


class TestReconciliationWithMission:
    """Test reconciliation schema handles dramatic_mission field."""

    def test_schema_includes_dramatic_mission(self):
        from engine.reconciliation import RECONCILIATION_SCHEMA
        props = RECONCILIATION_SCHEMA["properties"]
        assert "dramatic_mission" in props
        dm_props = props["dramatic_mission"]["properties"]
        assert "selected_mission" in dm_props
        assert "mission_sentence" in dm_props

    def test_reconciliation_result_has_mission(self):
        from engine.reconciliation import ReconciliationResult
        result = ReconciliationResult()
        assert "selected_mission" in result.dramatic_mission
        assert "mission_sentence" in result.dramatic_mission

    def test_validate_result_parses_mission(self):
        from engine.reconciliation import _validate_result
        data = {
            "npc_updates": [],
            "thread_updates": {
                "threads_advanced": [],
                "threads_resolved": [],
                "threads_opened": [],
            },
            "story_progress": {
                "anchor_proximity": "distant",
                "progress_delta": 0.05,
            },
            "dramatic_mission": {
                "selected_mission": "response",
                "mission_sentence": "The character processes the ambush.",
            },
        }
        result = _validate_result(data)
        assert result.dramatic_mission["selected_mission"] == "response"
        assert "ambush" in result.dramatic_mission["mission_sentence"]

    def test_validate_result_graceful_without_mission(self):
        """Old-format reconciliation output (no dramatic_mission) still parses."""
        from engine.reconciliation import _validate_result
        data = {
            "npc_updates": [],
            "thread_updates": {
                "threads_advanced": [],
                "threads_resolved": [],
                "threads_opened": [],
            },
            "story_progress": {
                "anchor_proximity": "approaching",
                "progress_delta": 0.08,
            },
        }
        result = _validate_result(data)
        assert result.dramatic_mission["selected_mission"] == ""
        assert result.dramatic_mission["mission_sentence"] == ""


class TestContextMissionBlock:
    """Test ContextPackage.build_dramatic_mission_block()."""

    def _make_ctx(self, mission=None):
        from gm.context import ContextPackage, ArcState
        from engine.character import Character
        arc = ArcState(
            campaign_name="Test",
            current_act=1,
            total_acts=4,
            act_name="Test Act",
            act_progress=0.3,
            current_anchor="test",
            next_anchor="test2",
            anchors_completed=[],
            throughline_question="?",
            tension_level="medium",
            open_threads=[],
            closed_threads=[],
        )
        char = Character(
            name="Test",
            species="human",
            career="smuggler",
            specialization="Pilot",
        )
        return ContextPackage(
            character=char,
            arc=arc,
            story_summary="",
            recent_turns=[],
            active_npcs=[],
            location="Test",
            situation="Test",
            dramatic_mission=mission or {},
        )

    def test_block_when_populated(self):
        ctx = self._make_ctx({
            "selected_mission": "response",
            "mission_sentence": "React to the threat.",
        })
        block = ctx.build_dramatic_mission_block()
        assert "DRAMATIC MISSION FOR THIS TURN" in block
        assert "response" in block
        assert "React to the threat" in block
        assert "unresolved element" in block

    def test_block_empty_when_no_mission(self):
        ctx = self._make_ctx({})
        block = ctx.build_dramatic_mission_block()
        assert block == ""

    def test_block_empty_when_none(self):
        ctx = self._make_ctx(None)
        block = ctx.build_dramatic_mission_block()
        assert block == ""

    def test_block_empty_when_no_selected(self):
        ctx = self._make_ctx({"selected_mission": "", "mission_sentence": ""})
        block = ctx.build_dramatic_mission_block()
        assert block == ""


class TestGracefulDegradation:
    """Verify the system works correctly without story_architecture."""

    def test_compute_missions_without_architecture(self):
        """Works with empty dramatic_function and progress-based fallback."""
        missions = compute_valid_missions("", 0.0, 0.1)
        assert len(missions) > 0
        assert all(isinstance(m, str) for m in missions)

    def test_all_parts_have_missions(self):
        """Every part in PART_MISSION_MAP has at least one mission."""
        for part, missions in PART_MISSION_MAP.items():
            assert len(missions) >= 1, f"Part {part} has no missions"


# ═════════════════════════════════════════════════════════════════════
# Phase 3: Midpoint Conversion & No-New-Exposition
# ═════════════════════════════════════════════════════════════════════

from engine.dramatic_mission import (
    check_midpoint_conversion,
    check_no_new_exposition,
    MIDPOINT_CONVERSION_INSTRUCTION,
    NO_NEW_EXPOSITION_WARNING,
)


class TestMidpointConversion:
    """Test midpoint conversion instruction logic."""

    def test_warrior_mode_triggers(self):
        result = check_midpoint_conversion("warrior", 3, None)
        assert result == MIDPOINT_CONVERSION_INSTRUCTION

    def test_martyr_mode_triggers(self):
        result = check_midpoint_conversion("martyr", 4, None)
        assert result == MIDPOINT_CONVERSION_INSTRUCTION

    def test_orphan_mode_does_not_trigger(self):
        result = check_midpoint_conversion("orphan", 1, None)
        assert result is None

    def test_post_midpoint_act_triggers(self):
        mbs = {"midpoint_act": 2}
        result = check_midpoint_conversion("", 3, mbs)
        assert result == MIDPOINT_CONVERSION_INSTRUCTION

    def test_pre_midpoint_act_does_not_trigger(self):
        mbs = {"midpoint_act": 3}
        result = check_midpoint_conversion("", 2, mbs)
        assert result is None


class TestNoNewExposition:
    """Test no-new-exposition warning logic."""

    def test_post_spp_triggers(self):
        mbs = {"second_plot_point_act": 3}
        result = check_no_new_exposition(4, mbs)
        assert result == NO_NEW_EXPOSITION_WARNING

    def test_pre_spp_does_not_trigger(self):
        mbs = {"second_plot_point_act": 3}
        result = check_no_new_exposition(2, mbs)
        assert result is None

    def test_no_mbs_does_not_trigger(self):
        result = check_no_new_exposition(4, None)
        assert result is None


# ═════════════════════════════════════════════════════════════════════
# Phase 6: Contradiction Tracking
# ═════════════════════════════════════════════════════════════════════


class TestContradictionTracking:
    """Test contradiction tracking in reconciliation."""

    def test_reconciliation_result_has_contradiction(self):
        from engine.reconciliation import ReconciliationResult
        result = ReconciliationResult()
        assert "contradiction_engaged" in result.contradiction_tracking
        assert result.contradiction_tracking["arc_movement"] == "none"

    def test_validate_result_parses_contradiction(self):
        from engine.reconciliation import _validate_result
        data = {
            "npc_updates": [],
            "thread_updates": {"threads_advanced": [], "threads_resolved": [], "threads_opened": []},
            "story_progress": {"anchor_proximity": "distant", "progress_delta": 0.05},
            "contradiction_tracking": {
                "contradiction_engaged": True,
                "arc_movement": "resisted",
                "arc_evidence": "The character accepted help.",
            },
        }
        result = _validate_result(data)
        assert result.contradiction_tracking["contradiction_engaged"] is True
        assert result.contradiction_tracking["arc_movement"] == "resisted"


# ═════════════════════════════════════════════════════════════════════
# Phase 7: Scene Purpose Validator
# ═════════════════════════════════════════════════════════════════════

from engine.scene_validator import SceneValidationResult, build_validator_prompt


class TestSceneValidator:
    """Test scene purpose validation data model."""

    def test_from_dict_high_scores(self):
        result = SceneValidationResult.from_dict({
            "mission_delivery": 5,
            "pressure_progression": 4,
            "antagonist_relevance": 4,
            "character_choices": 5,
            "change": 4,
        })
        assert result.composite >= 4.0
        assert result.corrective_instruction == ""

    def test_from_dict_low_scores(self):
        result = SceneValidationResult.from_dict({
            "mission_delivery": 1,
            "pressure_progression": 2,
            "antagonist_relevance": 1,
            "character_choices": 2,
            "change": 1,
        })
        assert result.composite < 3.0
        assert "low-purpose" in result.corrective_instruction

    def test_from_dict_clamps_values(self):
        result = SceneValidationResult.from_dict({
            "mission_delivery": 10,  # above max
            "pressure_progression": -1,  # below min
            "antagonist_relevance": 3,
            "character_choices": 3,
            "change": 3,
        })
        assert result.mission_delivery == 5
        assert result.pressure_progression == 1

    def test_build_prompt(self):
        prompt = build_validator_prompt(
            selected_mission="response",
            mission_sentence="React to pressure.",
            narration_text="Some narration text.",
            choices_text="Choice A; Choice B",
        )
        assert "response" in prompt
        assert "React to pressure" in prompt
        assert "MISSION DELIVERY" in prompt


# ═════════════════════════════════════════════════════════════════════
# Phase 10: Voice Mode Tags
# ═════════════════════════════════════════════════════════════════════

from engine.dramatic_mission import MISSION_TO_VOICE, VOICE_INSTRUCTIONS


class TestVoiceModeTags:
    """Test voice mode mapping completeness."""

    def test_all_voice_modes_have_instructions(self):
        for mission, voice_mode in MISSION_TO_VOICE.items():
            assert voice_mode in VOICE_INSTRUCTIONS, (
                f"Voice mode '{voice_mode}' for mission '{mission}' has no instruction"
            )

    def test_all_voice_modes_are_strings(self):
        for voice_mode, instruction in VOICE_INSTRUCTIONS.items():
            assert isinstance(instruction, str)
            assert len(instruction) > 10

    def test_variety_across_missions(self):
        """At least 3 different voice modes used across all missions."""
        unique_modes = set(MISSION_TO_VOICE.values())
        assert len(unique_modes) >= 3


class TestDramaticMissionEnum:
    """Test DramaticMission enum completeness."""

    def test_all_enum_values_in_part_map(self):
        """Every enum value appears in at least one part's mission list."""
        all_mapped = set()
        for missions in PART_MISSION_MAP.values():
            all_mapped.update(missions)
        for mission in DramaticMission:
            assert mission.value in all_mapped, (
                f"Mission {mission.value} not in any part's mission list"
            )

    def test_enum_is_string(self):
        """DramaticMission values are plain strings."""
        assert DramaticMission.RESPONSE.value == "response"
        assert DramaticMission.ATTACK.value == "attack"
