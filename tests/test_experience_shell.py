"""
Experience-shell tests — campaign completion, epilogue, resume recap,
incoming damage / incapacitation, and the dice verdict headline.

These close the "can't finish, can't return, can't see yourself" gaps:
1. BetweenActResult.campaign_complete + epilogue generation/parsing
2. Epilogue endpoint gating (not-complete → 400, cached → no LLM call)
3. Resume recap generation (mocked LLM)
4. compute_incoming_damage — failed checks in dangerous scenes cost
   wounds/strain; soak absorbs; safe scenes and successes cost nothing
5. Incapacitation: threshold crossing directive, per-act escalation,
   one-turn recovery (Game Mechanics §2)
6. Dice result block leads with the NARRATE AS verdict headline
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from engine.character import Character
from engine.checks import compute_incoming_damage
from engine.dice import RollResult


def _make_character() -> Character:
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "characters", "praxeum_student.json",
    )
    with open(path) as f:
        return Character.model_validate_json(f.read())


def _failed_roll(net_failures=2, despairs=0, net_threats=0) -> RollResult:
    return RollResult(
        net_successes=-net_failures,
        net_advantages=-net_threats,
        despairs=despairs,
        succeeded=False,
        outcome_quadrant="failure_threat" if net_threats else "failure_advantage",
    )


# ── 1. Campaign completion + epilogue generation ─────────────────────

class TestCampaignCompletion:
    def test_between_act_result_default(self):
        from engine.reconciliation import BetweenActResult
        assert BetweenActResult().campaign_complete is False

    def test_epilogue_parses_ending_header(self):
        from gm import cloud_gm
        spine = {
            "name": "Test Campaign",
            "throughline_question": "Can they go home?",
            "story_architecture": {
                "ending_paths": [
                    {"name": "The Long Road", "synopsis": "They walk away.",
                     "thematic_payoff": "Freedom costs"},
                ],
            },
        }
        with patch.object(
            cloud_gm, "_call_chat_for_epilogue",
            return_value="ENDING: The Long Road\n\nYou walk out under "
                         "two moons. The ship waits.",
        ):
            result = cloud_gm.generate_epilogue(
                _make_character(), spine, "Act 1: things happened.",
            )
        assert result["ending_name"] == "The Long Road"
        assert result["epilogue"].startswith("You walk out")
        assert "ENDING:" not in result["epilogue"]

    def test_epilogue_without_header_falls_back(self):
        from gm import cloud_gm
        with patch.object(
            cloud_gm, "_call_chat_for_epilogue",
            return_value="You walk out under two moons.",
        ):
            result = cloud_gm.generate_epilogue(
                _make_character(), {"name": "X"}, "summary",
            )
        assert result["ending_name"] == "What Comes After"
        assert result["epilogue"].startswith("You walk out")


class TestEpilogueEndpoint:
    def _client(self):
        from fastapi.testclient import TestClient
        from api.main import app
        return TestClient(app)

    def test_not_complete_returns_400(self):
        fake_session = {
            "arc_state_json": json.dumps({"current_act": 2}),
        }
        with patch("api.game_routes.get_session", return_value=fake_session):
            res = self._client().post("/session/test-id/epilogue")
        assert res.status_code == 400

    def test_cached_epilogue_returned_without_llm(self):
        cached = {
            "epilogue": "It is finished.",
            "ending_name": "The Law",
            "campaign_name": "x",
            "character_name": "y",
            "turns_played": 101,
        }
        fake_session = {
            "arc_state_json": json.dumps(
                {"campaign_complete": True, "epilogue": cached}
            ),
        }
        with patch("api.game_routes.get_session", return_value=fake_session), \
             patch("gm.cloud_gm._call_chat_for_epilogue") as mock_llm:
            res = self._client().post("/session/test-id/epilogue")
        assert res.status_code == 200
        assert res.json() == cached
        mock_llm.assert_not_called()

    def test_turn_blocked_when_complete(self):
        fake_session = {
            "arc_state_json": json.dumps({"campaign_complete": True}),
            "character_json": _make_character().model_dump_json(),
        }
        with patch("api.game_routes.get_session", return_value=fake_session):
            res = self._client().post(
                "/session/test-id/turn", json={"choice_index": 0},
            )
        assert res.status_code == 409
        assert "epilogue" in res.json()["detail"].lower()


# ── 2b. Engine-owned ending selection ─────────────────────────────────

def _branching_spine() -> dict:
    return {
        "name": "Test Campaign",
        "throughline_question": "Can they go home?",
        "variation_points": [
            {
                "id": "climax",
                "trigger_act": 4,
                "description": "The decisive choice.",
                "selection_method": "player_choice",
                "options": [
                    {"id": "walk_away", "description": "They walk away from it."},
                    {"id": "stay_and_fight", "description": "They stay and hold."},
                ],
            },
        ],
        "story_architecture": {
            "ending_paths": [
                {"name": "The Long Road", "branch_id": "walk_away",
                 "synopsis": "They walk away.", "thematic_payoff": "Freedom costs"},
                {"name": "The Stand", "branch_id": "stay_and_fight",
                 "synopsis": "They hold the line.", "thematic_payoff": "Roots cost"},
            ],
        },
    }


class TestEndingBranchClassification:
    def test_classify_returns_valid_branch(self):
        from gm import fast_gm
        with patch.object(
            fast_gm, "call_chat_json",
            return_value={"branch_id": "stay_and_fight",
                          "reasoning": "the final turns show them holding"},
        ):
            got = fast_gm.classify_ending_branch(
                _branching_spine(), "They stayed and fought at the gate.")
        assert got == "stay_and_fight"

    def test_classify_rejects_unknown_branch(self):
        from gm import fast_gm
        with patch.object(
            fast_gm, "call_chat_json",
            return_value={"branch_id": "invented_branch", "reasoning": "?"},
        ):
            assert fast_gm.classify_ending_branch(
                _branching_spine(), "summary") is None

    def test_classify_without_branch_structure_skips_llm(self):
        from gm import fast_gm
        with patch.object(fast_gm, "call_chat_json") as mock_llm:
            assert fast_gm.classify_ending_branch({"name": "X"}, "s") is None
        mock_llm.assert_not_called()

    def test_classify_fails_open_on_llm_error(self):
        from gm import fast_gm
        with patch.object(
            fast_gm, "call_chat_json", side_effect=RuntimeError("provider down"),
        ):
            assert fast_gm.classify_ending_branch(
                _branching_spine(), "summary") is None


class TestResolvedEndingEpilogue:
    def test_resolved_ending_owns_the_name(self):
        from gm import cloud_gm
        with patch.object(
            cloud_gm, "_call_chat_for_epilogue",
            return_value="ENDING: Wrong Name\n\nYou stay. The gate holds.",
        ):
            result = cloud_gm.generate_epilogue(
                _make_character(), _branching_spine(), "summary",
                resolved_ending={
                    "name": "The Stand", "branch_id": "stay_and_fight",
                    "synopsis": "They hold the line.",
                    "thematic_payoff": "Roots cost",
                },
            )
        assert result["ending_name"] == "The Stand"
        assert result["epilogue"].startswith("You stay.")

    def test_ending_state_block_appends_to_summary(self):
        from gm import cloud_gm
        captured = {}

        def capture(prompt):
            captured["prompt"] = prompt
            return "ENDING: The Stand\n\nDone."

        with patch.object(cloud_gm, "_call_chat_for_epilogue", side_effect=capture):
            cloud_gm.generate_epilogue(
                _make_character(), _branching_spine(), "summary",
                ending_state_block="WHERE THINGS STAND AT THE END:\n- Tahl: loyal",
            )
        assert "WHERE THINGS STAND AT THE END" in captured["prompt"]
        assert "- Tahl: loyal" in captured["prompt"]


class TestEpilogueRouteEndingResolution:
    def _client(self):
        from fastapi.testclient import TestClient
        from api.main import app
        return TestClient(app)

    def test_route_persists_branch_and_uses_resolved_name(self):
        fake_session = {
            "arc_state_json": json.dumps({"campaign_complete": True}),
            "character_json": _make_character().model_dump_json(),
            "campaign_name": "test_campaign",
        }
        captured = {}

        def fake_update(session_id, character, arc_state):
            captured["arc_state"] = arc_state

        with patch("api.game_routes.get_session", return_value=fake_session), \
             patch("api.game_routes.load_campaign_spine",
                   return_value=_branching_spine()), \
             patch("api.game_routes.get_act_summaries",
                   return_value="They stayed and held the gate."), \
             patch("api.game_routes.get_recent_turns", return_value=[]), \
             patch("api.game_routes.format_turn_lines", return_value=[]), \
             patch("api.game_routes.get_turn_count", return_value=42), \
             patch("api.game_routes.load_npc_states", return_value=[]), \
             patch("api.game_routes.classify_ending_branch",
                   return_value="stay_and_fight"), \
             patch("api.game_routes.update_session_state",
                   side_effect=fake_update), \
             patch("gm.cloud_gm._call_chat_for_epilogue",
                   return_value="ENDING: Renamed By Model\n\nThe gate holds."):
            res = self._client().post("/session/test-id/epilogue")

        assert res.status_code == 200
        body = res.json()
        # Engine-resolved branch is persisted and the authored name wins.
        assert body["ending_branch_id"] == "stay_and_fight"
        assert body["ending_name"] == "The Stand"
        assert captured["arc_state"]["ending_branch_id"] == "stay_and_fight"

    def test_route_falls_back_when_classification_unresolved(self):
        fake_session = {
            "arc_state_json": json.dumps({"campaign_complete": True}),
            "character_json": _make_character().model_dump_json(),
            "campaign_name": "test_campaign",
        }
        with patch("api.game_routes.get_session", return_value=fake_session), \
             patch("api.game_routes.load_campaign_spine",
                   return_value=_branching_spine()), \
             patch("api.game_routes.get_act_summaries", return_value="summary"), \
             patch("api.game_routes.get_recent_turns", return_value=[]), \
             patch("api.game_routes.format_turn_lines", return_value=[]), \
             patch("api.game_routes.get_turn_count", return_value=7), \
             patch("api.game_routes.load_npc_states", return_value=[]), \
             patch("api.game_routes.classify_ending_branch", return_value=None), \
             patch("api.game_routes.update_session_state"), \
             patch("gm.cloud_gm._call_chat_for_epilogue",
                   return_value="ENDING: The Long Road\n\nYou walk."):
            res = self._client().post("/session/test-id/epilogue")

        assert res.status_code == 200
        body = res.json()
        assert body["ending_branch_id"] is None
        # Legacy behavior: the model's matched ending stands.
        assert body["ending_name"] == "The Long Road"

    def test_ending_state_block_formats_npc_truth(self):
        from api.game_routes import _build_ending_state_block
        from gm.context import NPCState
        npcs = [
            NPCState(name="Tahl Veris", disposition=0.9,
                     crystallized_memory="Sat at the empty table first."),
            NPCState(name="Background Extra", disposition=0.5),
        ]
        block = _build_ending_state_block(_make_character(), npcs, {})
        assert "Tahl Veris" in block
        assert "loyal" in block
        assert "Sat at the empty table first." in block


# ── 3. Resume recap ──────────────────────────────────────────────────

class TestResumeRecap:
    def test_recap_uses_memory_and_recent_turns(self):
        from state import memory
        fake_turn = MagicMock()
        fake_turn.turn_number = 9
        fake_turn.player_action = "follow Kira down"
        fake_turn.check_made = "stealth"
        fake_turn.dice_result = "FAILED (1 net failure)"
        fake_turn.narration_excerpt = "The stairwell swallows the light."

        with patch("state.session.get_act_summaries",
                   return_value="Act 1: you arrived."), \
             patch("state.session.get_recent_turns",
                   return_value=[fake_turn]), \
             patch.object(memory, "call_chat",
                          return_value="You stand at the sealed stairs...") as mock_chat:
            recap = memory.generate_resume_recap("session-x")

        assert recap == "You stand at the sealed stairs..."
        prompt = mock_chat.call_args.kwargs["user"]
        assert "Act 1: you arrived." in prompt
        assert "follow Kira down" in prompt


# ── 4. Incoming damage ───────────────────────────────────────────────

class TestIncomingDamage:
    def test_combat_failure_costs_wounds_minus_soak(self):
        roll = _failed_roll(net_failures=2, despairs=1, net_threats=1)
        wounds, strain = compute_incoming_damage(roll, "combat", soak=3)
        # base 2 + failures 2 + despair 3 = 7, minus soak 3 = 4
        assert wounds == 4
        assert strain == 1

    def test_soak_can_absorb_fully(self):
        roll = _failed_roll(net_failures=1)
        wounds, _ = compute_incoming_damage(roll, "combat", soak=10)
        assert wounds == 0

    def test_success_costs_nothing(self):
        roll = RollResult(net_successes=2, succeeded=True,
                          outcome_quadrant="success_advantage")
        assert compute_incoming_damage(roll, "combat", soak=0) == (0, 0)

    def test_safe_scene_costs_nothing(self):
        roll = _failed_roll(net_failures=3, despairs=2)
        assert compute_incoming_damage(roll, "social", soak=0) == (0, 0)

    def test_no_roll_costs_nothing(self):
        assert compute_incoming_damage(None, "combat", soak=0) == (0, 0)

    def test_strain_capped(self):
        roll = _failed_roll(net_failures=1, net_threats=9)
        _, strain = compute_incoming_damage(roll, "chase", soak=0)
        assert strain == 4


# ── 5. Incapacitation flow ───────────────────────────────────────────

class TestIncapacitation:
    def _wounded_character(self, wounds):
        ch = _make_character()
        ch.current_wounds = wounds
        return ch

    def test_threshold_crossing_returns_directive(self):
        from api.game_routes import _apply_incoming_damage
        ch = self._wounded_character(wounds=0)
        ch.current_wounds = ch.wound_threshold - 1
        arc_state = {}
        roll = _failed_roll(net_failures=3, despairs=1)
        directive = _apply_incoming_damage(ch, arc_state, roll, "combat")
        assert "INCAPACITATION" in directive
        assert arc_state["incapacitated"] is True
        assert arc_state["incapacitations_this_act"] == 1
        assert ch.current_wounds == ch.wound_threshold  # clamped

    def test_second_incapacitation_escalates(self):
        from api.game_routes import (
            _apply_incapacitation_recovery,
            _apply_incoming_damage,
        )
        ch = self._wounded_character(wounds=0)
        arc_state = {}
        roll = _failed_roll(net_failures=4, despairs=2)

        ch.current_wounds = ch.wound_threshold - 1
        first = _apply_incoming_damage(ch, arc_state, roll, "combat")
        assert "SECOND" not in first
        _apply_incapacitation_recovery(ch, arc_state)
        assert ch.current_wounds < ch.wound_threshold
        assert arc_state["incapacitated"] is False

        ch.current_wounds = ch.wound_threshold - 1
        second = _apply_incoming_damage(ch, arc_state, roll, "combat")
        assert "SECOND INCAPACITATION" in second
        assert arc_state["incapacitations_this_act"] == 2

    def test_no_directive_below_threshold(self):
        from api.game_routes import _apply_incoming_damage
        ch = self._wounded_character(wounds=0)
        arc_state = {}
        roll = _failed_roll(net_failures=1)
        directive = _apply_incoming_damage(ch, arc_state, roll, "combat")
        assert directive == ""
        assert arc_state.get("incapacitated") is False

    def test_act_boundary_resets_counter(self):
        # The between-act pipeline resets incapacitations_this_act — assert
        # the reset keys exist in the step-16 next-act block.
        import inspect
        from engine import reconciliation
        source = inspect.getsource(reconciliation.run_between_act_pipeline)
        assert 'arc_state["incapacitations_this_act"] = 0' in source


# ── 6. Dice verdict headline ─────────────────────────────────────────

class TestDiceVerdictHeadline:
    def test_failure_block_leads_with_narrate_as(self):
        from gm.context import ArcState, ContextPackage
        ctx = ContextPackage(
            character=_make_character(),
            arc=ArcState(
                campaign_name="t", current_act=1, total_acts=4,
                act_name="a", act_progress=0.1, current_anchor="x",
                next_anchor="", anchors_completed=[],
                throughline_question="q", tension_level="rising",
                open_threads=[], closed_threads=[],
            ),
            story_summary="", recent_turns=[], active_npcs=[],
            location="", situation="",
            roll_result=RollResult(
                net_successes=-1, net_advantages=-1,
                succeeded=False, outcome_quadrant="failure_threat",
            ),
        )
        block = ctx.build_dice_result_block()
        lines = block.split("\n")
        assert lines[0] == "DICE CHECK RESULT:"
        assert lines[1].strip().startswith("NARRATE AS: NO, AND")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
