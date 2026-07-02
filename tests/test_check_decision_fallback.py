"""
Check-decision transport-failure fallback tests.

decide_check must never hard-block a freeform turn when the FAST tier
fails at the TRANSPORT level (timeout / connection / retries-exhausted
RuntimeError from gm.llm_client) — it falls back to a deterministic
CheckDecision mapped from the current scene_type. Rule 5 is preserved:
malformed JSON after retries (JSONDecodeError in the exception chain)
still raises LocalGMError exactly as before.
"""

import json
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from engine.character import Character
from gm.fast_gm import (
    FALLBACK_SCENE_SKILLS,
    LocalGMError,
    VALID_SCENE_TYPES,
    VALID_SKILLS,
    decide_check,
)


# ── Fixtures ──────────────────────────────────────────────────────────


def _make_character() -> Character:
    return Character(name="Test Runner", species="human", career="smuggler")


def _make_arc_state(scene_type: str | None = None) -> dict:
    arc_state = {
        "current_act": 1,
        "total_acts": 4,
        "act_name": "Act 1",
        "tension_level": "rising",
    }
    if scene_type is not None:
        arc_state["scene_state"] = {"scene_type": scene_type}
    return arc_state


class _StubTimeoutError(Exception):
    """Stands in for an SDK transport exception (e.g. APITimeoutError)."""


def _transport_error() -> RuntimeError:
    # Mirror the real chain: call_chat_json wraps call_chat's RuntimeError,
    # which wraps the provider SDK exception.
    sdk_error = _StubTimeoutError("Request timed out")
    inner = RuntimeError(
        "LLM call failed after 1 attempts "
        "(purpose=decision tier=fast model=stub): Request timed out"
    )
    inner.__cause__ = sdk_error
    outer = RuntimeError(
        "JSON LLM call failed after 3 attempts (purpose=decision): "
        f"{inner}"
    )
    outer.__cause__ = inner
    return outer


def _malformed_json_error() -> RuntimeError:
    decode_error = json.JSONDecodeError("Expecting value", "not json at all", 0)
    outer = RuntimeError(
        "JSON LLM call failed after 3 attempts (purpose=decision): "
        f"{decode_error}"
    )
    outer.__cause__ = decode_error
    return outer


def _decide(arc_state: dict):
    return decide_check(
        character=_make_character(),
        scene_description="A blaster fight erupts in the cantina.",
        player_action="I dive behind the bar and return fire.",
        arc_state=arc_state,
    )


# ── Fallback table sanity ─────────────────────────────────────────────


def test_fallback_skills_are_valid_and_cover_check_scenes():
    for scene_type, skill in FALLBACK_SCENE_SKILLS.items():
        assert scene_type in VALID_SCENE_TYPES
        assert skill in VALID_SKILLS
    # introspection is the only scene type without a mapped skill
    assert set(FALLBACK_SCENE_SKILLS) == VALID_SCENE_TYPES - {"introspection"}


# ── (a) Transport failure → deterministic fallback ────────────────────


class TestTransportFallback:
    @patch("gm.fast_gm.call_chat_json")
    def test_combat_scene_falls_back_to_ranged_light(self, mock_llm):
        mock_llm.side_effect = _transport_error()
        decision = _decide(_make_arc_state("combat"))
        assert decision.requires_check is True
        assert decision.skill == "ranged_light"
        assert decision.difficulty == "average"
        assert decision.scene_type == "combat"
        assert decision.moral_weight == 0
        assert decision.force_use is False
        assert decision.boost_dice == 0
        assert decision.setback_dice == 0

    @patch("gm.fast_gm.call_chat_json")
    def test_social_scene_falls_back_to_charm(self, mock_llm):
        mock_llm.side_effect = _transport_error()
        decision = _decide(_make_arc_state("social"))
        assert decision.requires_check is True
        assert decision.skill == "charm"
        assert decision.difficulty == "average"
        assert decision.scene_type == "social"

    @patch("gm.fast_gm.call_chat_json")
    def test_space_combat_scene_falls_back_to_piloting_space(self, mock_llm):
        mock_llm.side_effect = _transport_error()
        decision = _decide(_make_arc_state("space_combat"))
        assert decision.requires_check is True
        assert decision.skill == "piloting_space"
        assert decision.scene_type == "space_combat"

    @patch("gm.fast_gm.call_chat_json")
    def test_missing_scene_type_defaults_to_exploration(self, mock_llm):
        mock_llm.side_effect = _transport_error()
        decision = _decide(_make_arc_state())
        assert decision.requires_check is True
        assert decision.skill == "perception"
        assert decision.scene_type == "exploration"

    @patch("gm.fast_gm.call_chat_json")
    def test_unknown_scene_type_defaults_to_exploration(self, mock_llm):
        mock_llm.side_effect = _transport_error()
        decision = _decide(_make_arc_state("montage_of_feelings"))
        assert decision.requires_check is True
        assert decision.skill == "perception"
        assert decision.scene_type == "exploration"

    @patch("gm.fast_gm.call_chat_json")
    def test_last_scene_type_used_when_scene_state_absent(self, mock_llm):
        mock_llm.side_effect = _transport_error()
        arc_state = _make_arc_state()
        arc_state["last_scene_type"] = "infiltration"
        decision = _decide(arc_state)
        assert decision.requires_check is True
        assert decision.skill == "stealth"
        assert decision.scene_type == "infiltration"


# ── (b) Introspection → no check ─────────────────────────────────────


class TestIntrospectionFallback:
    @patch("gm.fast_gm.call_chat_json")
    def test_introspection_requires_no_check(self, mock_llm):
        mock_llm.side_effect = _transport_error()
        decision = _decide(_make_arc_state("introspection"))
        assert decision.requires_check is False
        assert decision.skill is None
        assert decision.scene_type == "introspection"
        assert decision.moral_weight == 0
        assert decision.force_use is False


# ── (c) Rule 5: malformed JSON still raises ──────────────────────────


class TestMalformedJsonStillRaises:
    @patch("gm.fast_gm.call_chat_json")
    def test_json_decode_failure_raises_local_gm_error(self, mock_llm):
        mock_llm.side_effect = _malformed_json_error()
        with pytest.raises(LocalGMError, match="Check decision failed after"):
            _decide(_make_arc_state("combat"))

    @patch("gm.fast_gm.call_chat_json")
    def test_deep_chained_json_decode_failure_raises(self, mock_llm):
        # JSONDecodeError buried one level deeper in the chain still counts
        decode_error = json.JSONDecodeError("Expecting value", "garbage", 0)
        inner = RuntimeError("wrapped once")
        inner.__cause__ = decode_error
        outer = RuntimeError("JSON LLM call failed after 3 attempts")
        outer.__cause__ = inner
        mock_llm.side_effect = outer
        with pytest.raises(LocalGMError):
            _decide(_make_arc_state("combat"))

    @patch("gm.fast_gm.call_chat_json")
    def test_validation_failure_still_raises(self, mock_llm):
        # Parsed-but-invalid data (unknown skill) is not a transport failure
        mock_llm.return_value = {
            "requires_check": True,
            "skill": "not_a_real_skill",
            "difficulty": "average",
            "scene_type": "combat",
            "reasoning": "test",
        }
        with pytest.raises(LocalGMError, match="validation failed"):
            _decide(_make_arc_state("combat"))


# ── (d) Fallback reasoning is tagged for telemetry ────────────────────


class TestFallbackReasoningTag:
    @patch("gm.fast_gm.call_chat_json")
    def test_reasoning_tagged_with_root_error_class(self, mock_llm):
        mock_llm.side_effect = _transport_error()
        decision = _decide(_make_arc_state("chase"))
        assert decision.skill == "coordination"
        assert "DETERMINISTIC_FALLBACK" in decision.reasoning
        assert "_StubTimeoutError" in decision.reasoning
        assert "scene_type=chase" in decision.reasoning

    @patch("gm.fast_gm.call_chat_json")
    def test_unchained_runtime_error_tags_its_own_class(self, mock_llm):
        mock_llm.side_effect = RuntimeError("bare transport failure")
        decision = _decide(_make_arc_state("social"))
        assert "DETERMINISTIC_FALLBACK" in decision.reasoning
        assert "RuntimeError" in decision.reasoning
