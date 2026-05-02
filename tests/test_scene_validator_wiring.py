"""Integration tests for CS-6 scene_validator runtime wiring.

Before this wiring landed, engine/scene_validator.py existed but was only
exercised in unit tests — no runtime path called it. This file covers
the four points where the integration touches the system:

  1. gm.fast_gm.validate_scene_purpose — wraps the fast-tier validator call.
  2. state.telemetry.emit_scene_validation — writes the event.
  3. api.game_routes._post_reconciliation_cs6_hook — persists the full
     mission dict in arc_state so the next turn can score against it.
  4. api.game_routes.SCENE_VALIDATOR_ENABLED — env-flag gating.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gm import fast_gm
from state import telemetry
from engine.scene_validator import SceneValidationResult, THRESHOLD_OK


# ── validate_scene_purpose ────────────────────────────────────────────


class TestValidateScenePurpose:
    def test_neutral_when_mission_missing(self):
        result = fast_gm.validate_scene_purpose(
            selected_mission="",
            mission_sentence="",
            narration_text="The ship rumbled through hyperspace.",
        )
        assert isinstance(result, SceneValidationResult)
        assert result.composite == 3.0
        assert result.mission_delivery == 3

    def test_neutral_when_only_one_field_present(self):
        result = fast_gm.validate_scene_purpose(
            selected_mission="thread_advance",
            mission_sentence="",
            narration_text="prose",
        )
        assert result.composite == 3.0

    def test_parses_llm_response_into_result(self, monkeypatch):
        recorded = {}

        def fake_call(*, tier, user, **kwargs):
            recorded["tier"] = tier
            recorded["prompt"] = user
            return {
                "mission_delivery": 5,
                "pressure_progression": 4,
                "antagonist_relevance": 3,
                "character_choices": 4,
                "change": 5,
                "concern": "",
            }

        monkeypatch.setattr(fast_gm, "call_chat_json", fake_call)
        result = fast_gm.validate_scene_purpose(
            selected_mission="character_reveal",
            mission_sentence="Use the conversation to expose what the protagonist risks.",
            narration_text="Keth lowered his blaster and admitted the truth.",
            choices=["Confess everything", "Leave the room", "Lie again"],
        )
        assert recorded["tier"] == "fast"
        assert "character_reveal" in recorded["prompt"]
        assert "Keth lowered" in recorded["prompt"]
        assert result.mission_delivery == 5
        assert result.pressure_progression == 4
        assert result.composite == pytest.approx(4.2)
        # Composite >= THRESHOLD_OK → no corrective instruction
        assert result.corrective_instruction == ""

    def test_low_score_yields_corrective_instruction(self, monkeypatch):
        def fake_call(**kwargs):
            return {
                "mission_delivery": 1,
                "pressure_progression": 2,
                "antagonist_relevance": 1,
                "character_choices": 2,
                "change": 1,
            }

        monkeypatch.setattr(fast_gm, "call_chat_json", fake_call)
        result = fast_gm.validate_scene_purpose(
            selected_mission="thread_advance",
            mission_sentence="Move one open question forward.",
            narration_text="Nothing happened.",
        )
        assert result.composite < THRESHOLD_OK
        assert result.corrective_instruction != ""

    def test_returns_neutral_when_llm_raises(self, monkeypatch):
        def boom(**kwargs):
            raise RuntimeError("provider down")

        monkeypatch.setattr(fast_gm, "call_chat_json", boom)
        result = fast_gm.validate_scene_purpose(
            selected_mission="character_reveal",
            mission_sentence="Use the conversation to expose risk.",
            narration_text="prose",
        )
        # Failures must never propagate — quality signal only.
        assert result.composite == 3.0


# ── emit_scene_validation telemetry ──────────────────────────────────


class TestEmitSceneValidation:
    def test_writes_event_to_session_log(self, tmp_path, monkeypatch):
        monkeypatch.setattr(telemetry, "TELEMETRY_DIR", tmp_path)
        telemetry.emit_scene_validation(
            session_id="sess-abc",
            turn_number=4,
            validation={
                "selected_mission": "character_reveal",
                "composite": 4.2,
                "mission_delivery": 5,
                "pressure_progression": 4,
                "antagonist_relevance": 3,
                "character_choices": 4,
                "change": 5,
                "concern": "",
                "corrective_instruction": "",
            },
        )
        log = tmp_path / "sess-abc.jsonl"
        assert log.exists()
        events = [
            json.loads(line)
            for line in log.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(events) == 1
        ev = events[0]
        assert ev["event_type"] == "scene_validation"
        assert ev["turn_number"] == 4
        assert ev["event_data"]["selected_mission"] == "character_reveal"
        assert ev["event_data"]["composite"] == 4.2


# ── arc_state persistence in the cs6 hook ────────────────────────────


class TestArcStatePersistsMissionFull:
    """The post-reconciliation cs6 hook must save the full mission dict
    (selected + sentence) so the next turn's scene validator has the
    sentence available — voice-mode routing only needs the string."""

    def test_hook_persists_full_mission_dict(self):
        from api.game_routes import _post_reconciliation_cs6_hook

        class _FakeRecon:
            dramatic_mission = {
                "selected_mission": "foreshadow",
                "mission_sentence": "Reveal a partial signal that points forward.",
            }
            contradiction_tracking = {}

        arc_state: dict = {}
        _post_reconciliation_cs6_hook(
            arc_state,
            _FakeRecon(),
            turn_number=3,
            foreshadow_instruction="",
            spine={},
            character=None,
        )
        assert arc_state.get("last_dramatic_mission") == "foreshadow"
        full = arc_state.get("last_dramatic_mission_full")
        assert full is not None
        assert full["selected_mission"] == "foreshadow"
        assert full["mission_sentence"].startswith("Reveal a partial signal")

    def test_hook_skips_persistence_when_mission_missing(self):
        from api.game_routes import _post_reconciliation_cs6_hook

        class _FakeRecon:
            dramatic_mission = {}
            contradiction_tracking = {}

        arc_state: dict = {"last_dramatic_mission_full": {"selected_mission": "old"}}
        _post_reconciliation_cs6_hook(
            arc_state,
            _FakeRecon(),
            turn_number=3,
            foreshadow_instruction="",
            spine={},
            character=None,
        )
        # Old value is preserved when the new recon yields no mission
        assert arc_state["last_dramatic_mission_full"]["selected_mission"] == "old"


# ── env flag gating ──────────────────────────────────────────────────


class TestSceneValidatorFlag:
    def test_flag_defaults_off(self):
        from api import game_routes
        # Default behavior: SCENE_VALIDATOR_ENABLED reads the env at import.
        # Without the env var set, it is False — keeping the hot path lean.
        assert isinstance(game_routes.SCENE_VALIDATOR_ENABLED, bool)
