"""
Campaign Studio Phase CS-2 tests — Mode 3 collaborative authoring.

Tests cover:
- Deterministic seed derivation
- Gap identification (pure Python, no LLM)
- Spine finalization workflow
- Studio API routes (validation, gaps, campaign CRUD)
"""

import json
import copy
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from studio.seeding import (
    derive_stage_seed,
    generate_master_seed,
    derive_all_seeds,
    derive_seeds_with_overrides,
    build_generation_metadata,
    ALL_STAGES,
    STAGE_WORLD,
    STAGE_VOICE,
)
from studio.generate import identify_gaps, validate_and_report, finalize_spine
from studio.schema import CampaignSpine


# ── Fixtures ──────────────────────────────────────────────────────────

CAMPAIGN_DIR = Path(__file__).parent.parent / "data" / "campaigns"


@pytest.fixture
def nar_shaddaa_data() -> dict:
    """Load the Nar Shaddaa Job campaign spine JSON."""
    path = CAMPAIGN_DIR / "nar_shaddaa_job.json"
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def minimal_spine_data() -> dict:
    """A minimal but incomplete spine for gap testing."""
    return {
        "name": "Test Campaign",
        "era": "galactic_civil_war",
        "total_acts": 2,
        "throughline_question": "",
        "acts": [],
        "npc_roster": [],
        "allegiances": [],
    }


# ── Seeding Tests ─────────────────────────────────────────────────────


class TestSeeding:
    """Test deterministic seed derivation."""

    def test_derive_stage_seed_deterministic(self):
        """Same master + stage always produces same seed."""
        seed1 = derive_stage_seed(42, "world")
        seed2 = derive_stage_seed(42, "world")
        assert seed1 == seed2

    def test_derive_stage_seed_different_stages(self):
        """Different stages produce different seeds."""
        seed_world = derive_stage_seed(42, "world")
        seed_npcs = derive_stage_seed(42, "npcs")
        assert seed_world != seed_npcs

    def test_derive_stage_seed_different_masters(self):
        """Different master seeds produce different stage seeds."""
        seed1 = derive_stage_seed(42, "world")
        seed2 = derive_stage_seed(99, "world")
        assert seed1 != seed2

    def test_derive_stage_seed_bounded(self):
        """Seeds are within valid range."""
        for master in [0, 1, 2**30, 2**31 - 1]:
            for stage in ALL_STAGES:
                seed = derive_stage_seed(master, stage)
                assert 0 <= seed < 2**31

    def test_generate_master_seed(self):
        """Master seed generation produces valid range."""
        seed = generate_master_seed()
        assert 0 <= seed < 2**31

    def test_derive_all_seeds(self):
        """All stages get seeds."""
        seeds = derive_all_seeds(42)
        assert set(seeds.keys()) == set(ALL_STAGES)
        assert len(set(seeds.values())) == len(ALL_STAGES)  # All unique

    def test_derive_seeds_with_overrides(self):
        """Overrides replace derived seeds for specified stages."""
        base_seeds = derive_all_seeds(42)
        overrides = {"npcs": 12345, "voice": 67890}
        final_seeds = derive_seeds_with_overrides(42, overrides)

        assert final_seeds["npcs"] == 12345
        assert final_seeds["voice"] == 67890
        assert final_seeds["world"] == base_seeds["world"]

    def test_derive_seeds_no_overrides(self):
        """Without overrides, all seeds match derive_all_seeds."""
        base = derive_all_seeds(42)
        final = derive_seeds_with_overrides(42)
        assert base == final

    def test_build_generation_metadata(self):
        """Generation metadata has all required fields."""
        seeds = derive_all_seeds(42)
        meta = build_generation_metadata(42, seeds, "gpt-5.2", "mode3_assist")
        assert meta["master_seed"] == 42
        assert meta["stage_seeds"] == seeds
        assert meta["model_used"] == "gpt-5.2"
        assert meta["generation_mode"] == "mode3_assist"
        assert meta["timestamp"]  # Non-empty


# ── Gap Identification Tests ──────────────────────────────────────────


class TestGapIdentification:
    """Test pure Python gap identification (no LLM calls)."""

    def test_complete_spine_has_no_errors(self, nar_shaddaa_data):
        """A complete spine has no error-level gaps."""
        gaps = identify_gaps(nar_shaddaa_data)
        errors = [g for g in gaps if g["severity"] == "error"]
        assert len(errors) == 0

    def test_missing_throughline(self, minimal_spine_data):
        """Flags missing throughline question."""
        gaps = identify_gaps(minimal_spine_data)
        tl_gaps = [g for g in gaps if "throughline" in g["field"].lower()]
        assert len(tl_gaps) == 1
        assert tl_gaps[0]["severity"] == "error"

    def test_no_acts(self, minimal_spine_data):
        """Flags no acts defined."""
        gaps = identify_gaps(minimal_spine_data)
        act_gaps = [g for g in gaps if g["field"] == "acts"]
        assert len(act_gaps) == 1
        assert act_gaps[0]["severity"] == "error"

    def test_no_npcs(self, minimal_spine_data):
        """Flags no NPCs defined."""
        gaps = identify_gaps(minimal_spine_data)
        npc_gaps = [g for g in gaps if g["field"] == "npc_roster"]
        assert len(npc_gaps) == 1
        assert npc_gaps[0]["severity"] == "error"

    def test_no_allegiances(self, minimal_spine_data):
        """Flags no allegiances defined."""
        gaps = identify_gaps(minimal_spine_data)
        alleg_gaps = [g for g in gaps if g["field"] == "allegiances"]
        assert len(alleg_gaps) == 1

    def test_one_allegiance(self, minimal_spine_data):
        """Flags only 1 allegiance."""
        minimal_spine_data["allegiances"] = [
            {"id": "solo", "display_name": "Solo", "description": "x" * 20, "character_variants": []}
        ]
        gaps = identify_gaps(minimal_spine_data)
        alleg_gaps = [g for g in gaps if g["field"] == "allegiances"]
        assert len(alleg_gaps) == 1
        assert "at least 2" in alleg_gaps[0]["message"]

    def test_act_count_mismatch(self, minimal_spine_data):
        """Flags total_acts vs actual act count mismatch."""
        minimal_spine_data["total_acts"] = 3
        minimal_spine_data["acts"] = [
            {"number": 1, "name": "Act 1", "tension": "rising",
             "opening_situation": "x" * 20, "opening_location": "place",
             "galactic_context": "x" * 20, "anchor": "a", "expected_turns": "5-8"}
        ]
        gaps = identify_gaps(minimal_spine_data)
        count_gaps = [g for g in gaps if g["field"] == "total_acts"]
        assert len(count_gaps) == 1
        assert count_gaps[0]["severity"] == "error"

    def test_npc_missing_voice_notes(self):
        """Flags NPCs without voice notes."""
        spine_data = {
            "npc_roster": [
                {"name": "Test NPC", "role": "test", "motivation": "test"}
            ],
        }
        gaps = identify_gaps(spine_data)
        voice_gaps = [g for g in gaps if "voice_notes" in g["field"]]
        assert len(voice_gaps) == 1

    def test_npc_missing_behavioral_envelope(self):
        """Flags NPCs without behavioral envelope."""
        spine_data = {
            "npc_roster": [
                {"name": "Test NPC", "role": "test", "motivation": "test",
                 "voice_notes": "Speaks slowly and deliberately."}
            ],
        }
        gaps = identify_gaps(spine_data)
        envelope_gaps = [g for g in gaps if "behavioral_envelope" in g["field"]]
        assert len(envelope_gaps) == 1


# ── Validate and Report Tests ────────────────────────────────────────


class TestValidateAndReport:
    """Test the validate_and_report wrapper."""

    def test_valid_spine_passes(self, nar_shaddaa_data):
        """A valid spine returns a passing report."""
        report = validate_and_report(nar_shaddaa_data)
        assert report.passed

    def test_invalid_data_raises(self):
        """Invalid data raises ValueError."""
        with pytest.raises(ValueError, match="schema parsing"):
            validate_and_report({"name": "Incomplete"})


# ── Finalize Tests ────────────────────────────────────────────────────


class TestFinalize:
    """Test the finalize_spine workflow."""

    def test_finalize_valid_spine(self, nar_shaddaa_data):
        """Finalize a valid spine successfully."""
        spine, report = finalize_spine(nar_shaddaa_data)
        assert report.passed
        assert isinstance(spine, CampaignSpine)
        assert spine.name == "The Nar Shaddaa Job"

    def test_finalize_with_seed(self, nar_shaddaa_data):
        """Finalize attaches generation metadata when seed provided."""
        spine, report = finalize_spine(
            nar_shaddaa_data,
            master_seed=42,
            model_used="gpt-5.2",
        )
        assert spine.generation_metadata is not None
        assert spine.generation_metadata.master_seed == 42
        assert spine.generation_metadata.model_used == "gpt-5.2"
        assert spine.generation_metadata.generation_mode == "mode3_assist"

    def test_finalize_without_seed(self, nar_shaddaa_data):
        """Finalize without seed leaves generation_metadata as None."""
        spine, report = finalize_spine(nar_shaddaa_data)
        assert spine.generation_metadata is None

    def test_finalize_invalid_spine_raises(self, nar_shaddaa_data):
        """Finalize raises ValueError for invalid spines."""
        data = copy.deepcopy(nar_shaddaa_data)
        data["total_acts"] = 99  # Mismatch
        with pytest.raises(ValueError, match="validation"):
            finalize_spine(data)


# ── Studio API Route Tests ────────────────────────────────────────────


class TestStudioRoutes:
    """Test Studio API routes using FastAPI test client."""

    @pytest.fixture
    def client(self):
        """FastAPI test client."""
        from fastapi.testclient import TestClient
        from api.main import app
        return TestClient(app)

    def test_validate_valid_spine(self, client, nar_shaddaa_data):
        """POST /studio/spine/validate with valid spine."""
        resp = client.post("/studio/spine/validate", json={"spine_data": nar_shaddaa_data})
        assert resp.status_code == 200
        data = resp.json()
        assert data["passed"] is True

    def test_validate_invalid_spine(self, client):
        """POST /studio/spine/validate with invalid spine."""
        resp = client.post("/studio/spine/validate", json={"spine_data": {"name": "bad"}})
        assert resp.status_code == 200
        data = resp.json()
        assert data["passed"] is False
        assert len(data["errors"]) > 0

    def test_gaps_endpoint(self, client):
        """POST /studio/spine/gaps identifies structural gaps."""
        resp = client.post("/studio/spine/gaps", json={
            "spine_data": {"name": "Test", "acts": [], "npc_roster": [], "allegiances": []}
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0

    def test_gaps_complete_spine(self, client, nar_shaddaa_data):
        """POST /studio/spine/gaps with complete spine has no errors."""
        resp = client.post("/studio/spine/gaps", json={"spine_data": nar_shaddaa_data})
        assert resp.status_code == 200
        data = resp.json()
        errors = [g for g in data["gaps"] if g["severity"] == "error"]
        assert len(errors) == 0

    def test_finalize_endpoint(self, client, nar_shaddaa_data):
        """POST /studio/spine/finalize with valid spine."""
        resp = client.post("/studio/spine/finalize", json={
            "spine_data": nar_shaddaa_data,
            "master_seed": 42,
            "model_used": "test-model",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["validation_report"]["passed"] is True
        assert data["spine"]["generation_metadata"]["master_seed"] == 42

    def test_finalize_invalid_spine(self, client, nar_shaddaa_data):
        """POST /studio/spine/finalize with invalid spine returns 422."""
        bad = copy.deepcopy(nar_shaddaa_data)
        bad["total_acts"] = 99
        resp = client.post("/studio/spine/finalize", json={"spine_data": bad})
        assert resp.status_code == 422

    def test_campaign_crud(self, client, nar_shaddaa_data):
        """Store, list, and retrieve a campaign."""
        # Store
        resp = client.post("/studio/campaigns", json={
            "spine_data": nar_shaddaa_data,
            "authoring_mode": "mode3",
        })
        assert resp.status_code == 200
        campaign_id = resp.json()["campaign_id"]

        # List
        resp = client.get("/studio/campaigns")
        assert resp.status_code == 200
        campaigns = resp.json()["campaigns"]
        assert any(c["id"] == campaign_id for c in campaigns)

        # Retrieve
        resp = client.get(f"/studio/campaigns/{campaign_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "The Nar Shaddaa Job"
        assert data["spine"]["name"] == "The Nar Shaddaa Job"

    def test_campaign_not_found(self, client):
        """GET /studio/campaigns/{id} with non-existent ID returns 404."""
        resp = client.get("/studio/campaigns/nonexistent-id")
        assert resp.status_code == 404

    def test_store_invalid_campaign(self, client):
        """POST /studio/campaigns with invalid spine returns 422."""
        resp = client.post("/studio/campaigns", json={
            "spine_data": {"name": "bad"},
            "authoring_mode": "mode3",
        })
        assert resp.status_code == 422
