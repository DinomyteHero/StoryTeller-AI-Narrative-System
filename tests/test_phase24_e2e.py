"""End-to-end API test for the Phase 24 character creation pipeline.

Mocks all LLM calls so the full pipeline runs without external services:
GET /backgrounds → POST /select_background → POST /refine_character →
POST /prologue/{sid}/scene + /choose loop → POST /prologue/{sid}/finalize →
POST /session/{sid}/start_main_loop → POST /session/{sid}/turn →
POST /session/{sid}/crystallize.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

os.environ["DB_PATH"] = ""
os.environ["NARRATIVE_BACKEND"] = "local"
os.environ["STREAMING_ENABLED"] = "false"
os.environ["OLLAMA_URL"] = "http://localhost:11434"

from fastapi.testclient import TestClient

# Borrow shared mock fixtures and helpers from the V1 e2e suite
from tests.test_e2e_game_loop import (  # noqa: E402
    MOCK_NARRATION_RESPONSE,
    MOCK_NARRATION_TURN,
    _make_narration_result,
    _mock_call_chat_json,
    _mock_ollama_post,
)


@pytest.fixture(autouse=True)
def temp_db():
    db_dir = Path(os.environ.get(
        "STORYTELLER_TEST_DB_DIR",
        Path(__file__).resolve().parents[1] / "__test_dbs",
    ))
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = str(db_dir / f"phase24_e2e_{uuid.uuid4().hex}.db")

    import state.db
    original_path = state.db._DB_PATH
    original_env = os.environ.get("DB_PATH")

    os.environ["DB_PATH"] = db_path
    state.db._DB_PATH = db_path
    state.db.init_db()

    yield db_path

    state.db._DB_PATH = original_path
    if original_env is not None:
        os.environ["DB_PATH"] = original_env
    elif "DB_PATH" in os.environ:
        del os.environ["DB_PATH"]
    for suffix in ("", "-wal", "-shm"):
        try:
            Path(db_path + suffix).unlink(missing_ok=True)
        except OSError:
            pass


@pytest.fixture
def client(temp_db):
    from api.main import app
    return TestClient(app)


@pytest.fixture
def mock_llms():
    narration_count = {"n": 0}

    def mock_narrate_turn(ctx):
        narration_count["n"] += 1
        if narration_count["n"] == 1:
            return _make_narration_result(MOCK_NARRATION_RESPONSE)
        return _make_narration_result(MOCK_NARRATION_TURN)

    with patch("httpx.post", side_effect=_mock_ollama_post), \
         patch("gm.local_gm.call_chat_json", side_effect=_mock_call_chat_json), \
         patch("engine.reconciliation.call_chat_json", side_effect=_mock_call_chat_json), \
         patch("api.game_routes.narrate_turn", side_effect=mock_narrate_turn), \
         patch("gm.cloud_gm.narrate_turn", side_effect=mock_narrate_turn), \
         patch("api.game_routes.narrate_turn_stream"), \
         patch("api.game_routes.run_prose_diagnostic", return_value=None), \
         patch("api.game_routes.annotate_choice", return_value=None):
        yield


# ── Tests ────────────────────────────────────────────────────────────


class TestPhase24E2E:

    def test_get_backgrounds(self, client, mock_llms):
        res = client.get("/backgrounds?campaign_name=shadows_of_the_custodian")
        assert res.status_code == 200
        data = res.json()
        assert len(data["backgrounds"]) == 6
        assert data["display_name"] == "Shadows of the Custodian"
        assert len(data["gender_menu"]) == 7

    def test_select_background_returns_refinement_state(self, client, mock_llms):
        res = client.post("/select_background", json={
            "campaign_name": "shadows_of_the_custodian",
            "background_id": "outer_rim_refugee",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["background"]["display_name"] == "Outer Rim Refugee"
        assert "story_seed" in data
        assert len(data["gender_menu"]) == 7

    def test_select_unknown_background_404(self, client, mock_llms):
        res = client.post("/select_background", json={
            "campaign_name": "shadows_of_the_custodian",
            "background_id": "not_a_thing",
        })
        assert res.status_code == 404

    def test_refine_character_creates_session(self, client, mock_llms):
        res = client.post("/refine_character", json={
            "campaign_name": "shadows_of_the_custodian",
            "background_id": "rebel_legacy",
            "name": "Mara",
            "species_id": "human",
            "gender_id": "female",
            "appearance_flair": "Calluses from a saber she has practiced since six.",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["session_id"]
        assert data["stage"] == "identity_prologue"
        assert data["character_summary"]["name"] == "Mara"
        assert data["character_summary"]["pre_crystallization"] is True
        assert data["prologue_total_scenes"] >= 3

    def test_full_prologue_run(self, client, mock_llms):
        # Refine
        res = client.post("/refine_character", json={
            "campaign_name": "shadows_of_the_custodian",
            "background_id": "outer_rim_refugee",
            "name": "Sora",
            "gender_id": "female",
            "appearance_flair": "Loose hair, callused hands.",
        })
        sid = res.json()["session_id"]

        # Scene 1
        scene_res = client.post(f"/prologue/{sid}/scene")
        assert scene_res.status_code == 200
        assert scene_res.json()["scene"] is not None
        assert scene_res.json()["stage"] == "prologue"

        # Run all 4 scenes — pick choice 0 each time
        seen_stages = []
        for _ in range(6):
            scene_data = client.post(f"/prologue/{sid}/scene").json()
            if scene_data["stage"] != "prologue":
                seen_stages.append(scene_data["stage"])
                break
            choose_res = client.post(f"/prologue/{sid}/choose", json={
                "chosen_index": 0, "diegetic_payload": None,
            })
            assert choose_res.status_code == 200
            seen_stages.append(choose_res.json()["stage"])
            if choose_res.json()["stage"] == "complete":
                break

        # Finalize
        fin_res = client.post(f"/prologue/{sid}/finalize")
        assert fin_res.status_code == 200
        fin = fin_res.json()
        assert fin["stage"] == "main_loop_pending_opening"
        assert fin["summary"]["behavioral_archetype"]
        assert fin["character"]["pre_crystallization"] is True
        assert fin["character"]["career"] == "praxeum_student"

    def test_full_pipeline_to_main_loop_and_first_turn(self, client, mock_llms):
        # Walk through the entire pipeline
        res = client.post("/refine_character", json={
            "campaign_name": "shadows_of_the_custodian",
            "background_id": "imperial_defector",
            "name": "Cael",
            "gender_id": "male",
        })
        sid = res.json()["session_id"]

        for _ in range(6):
            stage = client.post(f"/prologue/{sid}/scene").json()["stage"]
            if stage != "prologue":
                break
            client.post(f"/prologue/{sid}/choose", json={
                "chosen_index": 0, "diegetic_payload": None,
            })

        client.post(f"/prologue/{sid}/finalize")

        start_res = client.post(f"/session/{sid}/start_main_loop")
        assert start_res.status_code == 200
        start = start_res.json()
        assert start["stage"] == "main_loop"
        assert len(start["opening_narration"]) > 100
        assert len(start["choices"]) >= 2

        # Take a turn — should work like a normal session
        turn_res = client.post(f"/session/{sid}/turn", json={"choice_index": 0})
        assert turn_res.status_code == 200

    def test_crystallize_preview_then_commit(self, client, mock_llms):
        # Build a session and walk through the prologue
        res = client.post("/refine_character", json={
            "campaign_name": "shadows_of_the_custodian",
            "background_id": "rebel_legacy",
            "name": "Riggs",
            "gender_id": "male",
        })
        sid = res.json()["session_id"]
        for _ in range(6):
            stage = client.post(f"/prologue/{sid}/scene").json()["stage"]
            if stage != "prologue":
                break
            client.post(f"/prologue/{sid}/choose", json={
                "chosen_index": 0, "diegetic_payload": None,
            })
        client.post(f"/prologue/{sid}/finalize")
        client.post(f"/session/{sid}/start_main_loop")

        # Preview
        preview = client.get(f"/session/{sid}/crystallize")
        assert preview.status_code == 200
        data = preview.json()
        assert data["already_crystallized"] is False
        assert data["mentor_npc"]
        # 3 paths visible (Shadow Sentinel masked for non-defector)
        assert len([p for p in data["paths"] if p["weight"] >= 0]) >= 3
        suggested = [p for p in data["paths"] if p["is_suggested"]]
        assert len(suggested) == 1

        # Commit Guardian (path index 0)
        commit = client.post(f"/session/{sid}/crystallize", json={
            "chosen_path_index": 0,
        })
        assert commit.status_code == 200
        result = commit.json()
        assert result["character"]["career"] == "guardian"
        assert result["character"]["crystallized"] is True

        # Re-running preview shows already_crystallized=True
        re_preview = client.get(f"/session/{sid}/crystallize")
        assert re_preview.json()["already_crystallized"] is True

        # Cannot re-crystallize
        re_commit = client.post(f"/session/{sid}/crystallize", json={
            "chosen_path_index": 0,
        })
        assert re_commit.status_code == 400

    def test_prologue_blocks_finalize_before_complete(self, client, mock_llms):
        res = client.post("/refine_character", json={
            "campaign_name": "shadows_of_the_custodian",
            "background_id": "frontier_world_native",
            "name": "Cova",
        })
        sid = res.json()["session_id"]
        # Don't make any choices
        fin = client.post(f"/prologue/{sid}/finalize")
        assert fin.status_code == 400

    def test_diegetic_appearance_flair_committed(self, client, mock_llms):
        res = client.post("/refine_character", json={
            "campaign_name": "shadows_of_the_custodian",
            "background_id": "outer_rim_refugee",
            "name": "Sora",
            # NOTE: no appearance_flair — should surface as a diegetic slot
        })
        sid = res.json()["session_id"]

        # First scene should have the appearance_flair slot
        scene_data = client.post(f"/prologue/{sid}/scene").json()
        assert scene_data["scene"]["diegetic_slot"] is not None
        assert scene_data["scene"]["diegetic_slot"]["slot_type"] == "appearance_flair"

        # Submit with a flair payload
        choose = client.post(f"/prologue/{sid}/choose", json={
            "chosen_index": 0,
            "diegetic_payload": {
                "appearance_flair": "Hair shaved short on one side; eyes that count exits.",
            },
        }).json()
        assert choose["diegetic_committed"]["slot_type"] == "appearance_flair"

    def test_unknown_campaign_returns_404(self, client, mock_llms):
        res = client.get("/backgrounds?campaign_name=does_not_exist")
        assert res.status_code == 404
