"""
CS-4 tests: Saga Layer + Mode 1.

Tests cover:
- Persona pool loading and selection
- Diversity validation
- Divergent generation (Stage 2)
- Branching search (Stage 3)
- Convergent debate (Stage 4)
- Pairwise evaluation and selection (Stage 5)
- Ensemble model assignment
- Evaluator configuration
- Pipeline orchestration
- Mode 1 generation
- API routes (mode1, saga)
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ── Fixtures ──────────────────────────────────────────────────────────


SAMPLE_PERSONAS = [
    {"id": f"p_{i}", "description": f"Persona {i} description", "cluster": f"cluster_{i % 4}"}
    for i in range(20)
]

SAMPLE_DIRECTION = {
    "throughline_question": "Can loyalty survive when both sides claim justice?",
    "primary_conflict_type": "institutional vs personal",
    "setting_description": "A contested trade hub on the rim.",
    "tone_shift": "More claustrophobic, less open-world",
    "key_thematic_elements": ["loyalty", "bureaucracy", "hidden cost"],
    "denial_constraints_applied": ["No hero's journey", "No redemption arc"],
}

SAMPLE_SKETCH = {
    "direction": SAMPLE_DIRECTION,
    "act_outlines": [
        {"number": 1, "anchor_summary": "The job offer arrives.", "tension": "rising"},
        {"number": 2, "anchor_summary": "Alliances fracture.", "tension": "critical"},
        {"number": 3, "anchor_summary": "Consequences collapse.", "tension": "climax"},
    ],
    "npc_roster_outline": [
        {"name": "Torek", "role": "Fixer", "motivation_summary": "Protect his crew"},
        {"name": "Vess", "role": "Inspector", "motivation_summary": "Enforce the system"},
        {"name": "Mira", "role": "Informant", "motivation_summary": "Escape her past"},
    ],
    "galactic_context_notes": [
        "Imperial patrols tighten around trade routes.",
        "Local governance fractures under pressure.",
        "A blockade forces hard choices.",
    ],
}

# A minimal valid spine data for scoring tests
MINIMAL_SPINE_DATA = {
    "name": "Test Campaign",
    "era": "galactic_civil_war",
    "total_acts": 3,
    "throughline_question": "What does survival cost?",
    "allegiances": [
        {
            "id": "alliance_a",
            "display_name": "Alliance A",
            "description": "The first path",
            "character_variants": [
                {
                    "id": "var_a1",
                    "display_name": "Variant A1",
                    "species": "Human",
                    "career": "Smuggler",
                    "specializations": ["Pilot"],
                    "characteristics_base": {
                        "brawn": 2, "agility": 3, "intellect": 2,
                        "cunning": 3, "willpower": 2, "presence": 2,
                    },
                    "skills_base": {"piloting_space": 1, "cool": 1},
                    "wound_threshold": 12,
                    "strain_threshold": 12,
                    "soak": 2,
                    "starting_xp": 110,
                    "voice_baseline": "Speaks low and fast.",
                    "motivation_default": {"track": "obligation"},
                    "force_sensitive": False,
                },
            ],
        },
        {
            "id": "alliance_b",
            "display_name": "Alliance B",
            "description": "The second path",
            "character_variants": [
                {
                    "id": "var_b1",
                    "display_name": "Variant B1",
                    "species": "Twi'lek",
                    "career": "Technician",
                    "specializations": ["Mechanic"],
                    "characteristics_base": {
                        "brawn": 2, "agility": 2, "intellect": 3,
                        "cunning": 2, "willpower": 3, "presence": 2,
                    },
                    "skills_base": {"mechanics": 2},
                    "wound_threshold": 11,
                    "strain_threshold": 13,
                    "soak": 2,
                    "starting_xp": 110,
                    "voice_baseline": "Measured and precise.",
                    "motivation_default": {"track": "duty"},
                    "force_sensitive": False,
                },
            ],
        },
    ],
    "acts": [
        {
            "number": 1,
            "name": "Act One",
            "tension": "rising",
            "opening_situation": "A strange signal.",
            "opening_location": "Cantina",
            "galactic_context": "The Empire expands customs enforcement.",
            "anchor": {"description": "The job arrives", "mechanical_weight": "medium"},
            "xp_base": 15,
        },
        {
            "number": 2,
            "name": "Act Two",
            "tension": "critical",
            "opening_situation": "Alliances fracture.",
            "opening_location": "Dock",
            "galactic_context": "Trade routes restricted.",
            "anchor": {"description": "Betrayal", "mechanical_weight": "high"},
            "xp_base": 20,
        },
        {
            "number": 3,
            "name": "Act Three",
            "tension": "climax",
            "opening_situation": "Final reckoning.",
            "opening_location": "Station",
            "galactic_context": "Imperial blockade.",
            "anchor": {"description": "Consequences", "mechanical_weight": "high"},
            "xp_base": 25,
        },
    ],
    "npc_roster": [
        {
            "name": "Torek",
            "role": "Fixer",
            "species": "Rodian",
            "motivation": "Protect his crew",
            "disposition_start": 0.6,
            "disposition_trajectory": [0.6, 0.5, 0.4],
            "behavioral_envelope": ["Won't betray crew", "Won't work for free"],
            "voice_notes": "Speaks in half-sentences. Nervous deflections.",
            "per_act_state": {
                "1": {"location": "cantina", "agenda": "recruit"},
                "2": {"location": "dock", "agenda": "survive"},
                "3": {"location": "station", "agenda": "escape"},
            },
        },
    ],
    "variation_points": [
        {
            "id": "vp_1",
            "description": "Who to trust",
            "trigger_act": 2,
            "options": [
                {"id": "trust_torek", "label": "Trust Torek", "consequences": "Torek helps"},
                {"id": "trust_vess", "label": "Trust Vess", "consequences": "Vess helps"},
            ],
        },
    ],
}


def _mock_llm_fn(system_prompt, user_prompt, *, seed=None, max_tokens=4000, temperature=0.7):
    """Mock LLM that returns plausible JSON for any stage."""
    if "sequel direction" in system_prompt.lower():
        return json.dumps(SAMPLE_DIRECTION)
    elif "spine sketch" in system_prompt.lower():
        return json.dumps(SAMPLE_SKETCH)
    elif "campaign spine" in system_prompt.lower() or "complete campaign" in system_prompt.lower():
        return json.dumps(MINIMAL_SPINE_DATA)
    elif "critique" in system_prompt.lower():
        return "The NPC motivations could be deeper. The pacing in Act 2 is uneven."
    else:
        return json.dumps({"result": "mock"})


# ── Persona Tests ─────────────────────────────────────────────────────


class TestPersonas:
    def test_load_persona_pool(self):
        from studio.saga.personas import load_persona_pool
        pool = load_persona_pool()
        assert len(pool) == 55
        assert all("id" in p and "description" in p and "cluster" in p for p in pool)

    def test_load_persona_pool_custom_path(self):
        from studio.saga.personas import load_persona_pool
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(SAMPLE_PERSONAS, f)
            f.flush()
            pool = load_persona_pool(Path(f.name))
        os.unlink(f.name)
        assert len(pool) == 20

    def test_select_personas_count(self):
        from studio.saga.personas import select_personas
        selected = select_personas(SAMPLE_PERSONAS, count=5, seed=42)
        assert len(selected) == 5

    def test_select_personas_deterministic(self):
        from studio.saga.personas import select_personas
        a = select_personas(SAMPLE_PERSONAS, count=5, seed=42)
        b = select_personas(SAMPLE_PERSONAS, count=5, seed=42)
        assert [p["id"] for p in a] == [p["id"] for p in b]

    def test_select_personas_cluster_diversity(self):
        from studio.saga.personas import select_personas
        selected = select_personas(SAMPLE_PERSONAS, count=4, seed=42)
        clusters = {p["cluster"] for p in selected}
        # Should have at least 3 distinct clusters from 4 available
        assert len(clusters) >= 3

    def test_select_personas_exclude(self):
        from studio.saga.personas import select_personas
        selected = select_personas(SAMPLE_PERSONAS, count=5, seed=42, exclude_ids={"p_0", "p_1"})
        ids = {p["id"] for p in selected}
        assert "p_0" not in ids
        assert "p_1" not in ids

    def test_validate_diversity(self):
        from studio.saga.personas import validate_diversity, load_persona_pool
        # Use the real 55-persona pool for diversity validation
        pool = load_persona_pool()
        result = validate_diversity(pool)
        assert result["passed"] is True
        assert result["unique_compositions"] >= 3
        assert result["total_subsets"] == 5


# ── Diverge Tests (Stage 2) ──────────────────────────────────────────


class TestDiverge:
    def test_generate_directions(self):
        from studio.saga.diverge import generate_directions
        personas = SAMPLE_PERSONAS[:3]
        directions = generate_directions(
            personas, "What is freedom worth?", "galactic_civil_war",
            directions_per_persona=2, master_seed=42, llm_call_fn=_mock_llm_fn,
        )
        assert len(directions) == 6  # 3 personas * 2 each
        for d in directions:
            assert "persona_id" in d
            assert "direction" in d
            assert "throughline_question" in d["direction"]

    def test_generate_directions_handles_failures(self):
        from studio.saga.diverge import generate_directions
        call_count = 0

        def flaky_llm(system_prompt, user_prompt, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise RuntimeError("Simulated failure")
            return json.dumps(SAMPLE_DIRECTION)

        directions = generate_directions(
            SAMPLE_PERSONAS[:2], "test?", "high_republic",
            directions_per_persona=2, llm_call_fn=flaky_llm,
        )
        # Some succeed, some fail — should get partial results
        assert len(directions) >= 1
        assert len(directions) < 4

    def test_generate_directions_empty_personas(self):
        from studio.saga.diverge import generate_directions
        directions = generate_directions(
            [], "test?", "galactic_civil_war", llm_call_fn=_mock_llm_fn,
        )
        assert directions == []


# ── Search Tests (Stage 3) ───────────────────────────────────────────


class TestSearch:
    def test_expand_to_sketches(self):
        from studio.saga.search import expand_to_sketches
        directions = [
            {"persona_id": "p_0", "direction": SAMPLE_DIRECTION},
            {"persona_id": "p_1", "direction": SAMPLE_DIRECTION},
        ]
        sketches = expand_to_sketches(
            directions, "galactic_civil_war", total_acts=3,
            search_depth=1, master_seed=42, llm_call_fn=_mock_llm_fn,
        )
        assert len(sketches) == 2
        for s in sketches:
            assert "persona_id" in s
            assert "sketch" in s

    def test_expand_to_sketches_depth_2(self):
        from studio.saga.search import expand_to_sketches
        directions = [{"persona_id": "p_0", "direction": SAMPLE_DIRECTION}]
        sketches = expand_to_sketches(
            directions, "galactic_civil_war",
            search_depth=2, master_seed=42, llm_call_fn=_mock_llm_fn,
        )
        assert len(sketches) == 2  # 1 direction * depth 2

    def test_expand_empty_directions(self):
        from studio.saga.search import expand_to_sketches
        sketches = expand_to_sketches(
            [], "galactic_civil_war", llm_call_fn=_mock_llm_fn,
        )
        assert sketches == []


# ── Converge Tests (Stage 4) ─────────────────────────────────────────


class TestConverge:
    def test_produce_draft_spines(self):
        from studio.saga.converge import produce_draft_spines
        sketches = [
            {"persona_id": "p_0", "sketch": SAMPLE_SKETCH},
        ]
        drafts = produce_draft_spines(
            sketches, "What is freedom worth?", "galactic_civil_war",
            debate_rounds=1, master_seed=42, llm_call_fn=_mock_llm_fn,
        )
        assert len(drafts) == 1
        assert "spine_data" in drafts[0]
        assert "persona_id" in drafts[0]

    def test_produce_draft_spines_multiple_rounds(self):
        from studio.saga.converge import produce_draft_spines
        sketches = [{"persona_id": "p_0", "sketch": SAMPLE_SKETCH}]
        drafts = produce_draft_spines(
            sketches, "test?", "galactic_civil_war",
            debate_rounds=2, master_seed=42, llm_call_fn=_mock_llm_fn,
        )
        assert len(drafts) == 1

    def test_produce_draft_spines_empty(self):
        from studio.saga.converge import produce_draft_spines
        drafts = produce_draft_spines(
            [], "test?", "galactic_civil_war", llm_call_fn=_mock_llm_fn,
        )
        assert drafts == []


# ── Select Tests (Stage 5) ───────────────────────────────────────────


class TestSelect:
    def test_score_spine(self):
        from studio.saga.select import _score_spine
        scores = _score_spine(MINIMAL_SPINE_DATA)
        assert 0.0 <= scores["structural_quality"] <= 1.0
        assert 0.0 <= scores["novelty"] <= 1.0
        assert 0.0 <= scores["diversity_vs_prior"] <= 1.0
        assert 0.0 <= scores["composite"] <= 1.0

    def test_score_empty_spine(self):
        from studio.saga.select import _score_spine
        scores = _score_spine({})
        assert scores["structural_quality"] == 0.0
        assert scores["composite"] == 0.0

    def test_select_best(self):
        from studio.saga.select import select_best
        drafts = [
            {"persona_id": "p_0", "spine_data": MINIMAL_SPINE_DATA},
            {"persona_id": "p_1", "spine_data": {"name": "Empty"}},
        ]
        best = select_best(drafts, top_k=1)
        assert len(best) == 1
        # The complete spine should win
        assert best[0]["persona_id"] == "p_0"

    def test_evaluate_spine_pair(self):
        from studio.saga.select import evaluate_spine_pair
        result = evaluate_spine_pair(MINIMAL_SPINE_DATA, {"name": "Empty"})
        assert result["winner"] in ("a", "b", "tie")
        assert "scores_a" in result
        assert "scores_b" in result
        assert "reasoning" in result
        # The complete spine should win
        assert result["winner"] == "a"

    def test_select_best_top_k(self):
        from studio.saga.select import select_best
        drafts = [
            {"persona_id": f"p_{i}", "spine_data": MINIMAL_SPINE_DATA}
            for i in range(5)
        ]
        best = select_best(drafts, top_k=3)
        assert len(best) == 3


# ── Ensemble Tests ───────────────────────────────────────────────────


class TestEnsemble:
    def test_assign_models_round_robin(self):
        from studio.saga.ensemble import assign_models
        pool = [
            {"model": "model_a", "provider": "openai", "weight": 1.0},
            {"model": "model_b", "provider": "openrouter", "weight": 1.0},
        ]
        assignments = assign_models(
            ["p_0", "p_1", "p_2"], model_pool=pool, strategy="round_robin",
        )
        assert len(assignments) == 3
        assert assignments[0].model == "model_a"
        assert assignments[1].model == "model_b"
        assert assignments[2].model == "model_a"

    def test_assign_models_random_deterministic(self):
        from studio.saga.ensemble import assign_models
        pool = [
            {"model": "model_a", "provider": "openai", "weight": 1.0},
            {"model": "model_b", "provider": "openrouter", "weight": 1.0},
        ]
        a = assign_models(["p_0", "p_1"], model_pool=pool, strategy="random", seed=42)
        b = assign_models(["p_0", "p_1"], model_pool=pool, strategy="random", seed=42)
        assert [x.model for x in a] == [x.model for x in b]

    def test_assign_models_default_pool(self):
        from studio.saga.ensemble import assign_models
        assignments = assign_models(["p_0", "p_1"])
        assert len(assignments) == 2
        # Both should use the default model
        assert assignments[0].provider == "openai"


# ── Evaluator Tests ──────────────────────────────────────────────────


class TestEvaluator:
    def test_evaluator_status_uncalibrated(self):
        from studio.saga.evaluator import EvaluatorConfig, get_evaluator_status
        config = EvaluatorConfig()
        status = get_evaluator_status(config)
        assert status["calibrated"] is False
        assert status["ready_for_local"] is False

    def test_evaluator_status_calibrated(self):
        from studio.saga.evaluator import EvaluatorConfig, get_evaluator_status
        config = EvaluatorConfig(
            backend="local",
            local_model="eval_model",
            calibration_score=0.85,
            total_pairs_trained=700,
        )
        status = get_evaluator_status(config)
        assert status["calibrated"] is True
        assert status["ready_for_local"] is True

    def test_should_use_local(self):
        from studio.saga.evaluator import EvaluatorConfig, should_use_local
        assert should_use_local(EvaluatorConfig()) is False
        assert should_use_local(EvaluatorConfig(
            backend="local", local_model="m", calibration_score=0.85,
        )) is True

    def test_log_evaluation_pair(self):
        from studio.saga.evaluator import log_evaluation_pair
        record = log_evaluation_pair(
            "spine a summary", "spine b summary",
            axis="structural", winner="a", confidence=0.9,
            reasoning="A is more complete",
        )
        assert "pair_id" in record
        assert record["winner"] == "a"
        assert record["axis"] == "structural"


# ── Pipeline Tests ───────────────────────────────────────────────────


class TestPipeline:
    def test_pipeline_runs_end_to_end(self):
        from studio.saga.pipeline import run_saga_pipeline
        prior = {
            "throughline_question": "What is loyalty worth?",
            "era": "galactic_civil_war",
            "total_acts": 3,
        }
        result = run_saga_pipeline(
            prior, master_seed=42, llm_call_fn=_mock_llm_fn,
        )
        assert result.master_seed == 42
        assert result.directions_generated > 0
        assert result.sketches_generated > 0
        assert result.drafts_generated > 0

    def test_pipeline_with_fallback_personas(self):
        from studio.saga.pipeline import run_saga_pipeline
        # Use a nonexistent path to trigger fallback
        result = run_saga_pipeline(
            {"throughline_question": "test?", "era": "old_republic", "total_acts": 3},
            master_seed=42,
            persona_pool_path=Path("/nonexistent/personas.json"),
            llm_call_fn=_mock_llm_fn,
        )
        assert result.directions_generated > 0

    def test_pipeline_result_structure(self):
        from studio.saga.pipeline import PipelineResult
        r = PipelineResult()
        assert r.selected_spine is None
        assert r.all_candidates == []
        assert r.master_seed == 0
        assert r.passed_validation is False


# ── Mode 1 Tests ─────────────────────────────────────────────────────


class TestMode1:
    def test_mode1_input_dataclass(self):
        from studio.generate import Mode1Input
        inputs = Mode1Input(era="galactic_civil_war", location="Nar Shaddaa")
        assert inputs.tone == "gritty"
        assert inputs.moral_register == "morally gray"

    def test_mode1_prompt_template_exists(self):
        path = Path(__file__).parent.parent / "studio" / "prompts" / "mode1_generate.txt"
        assert path.exists()
        content = path.read_text()
        assert "{era}" in content
        assert "{location}" in content

    @patch("studio.generate._call_llm")
    @patch("studio.generate._get_client")
    def test_generate_mode1(self, mock_client, mock_llm):
        from studio.generate import generate_mode1, Mode1Input
        mock_llm.return_value = json.dumps(MINIMAL_SPINE_DATA)

        inputs = Mode1Input(era="galactic_civil_war", location="Nar Shaddaa")
        spine_data, seed = generate_mode1(inputs, master_seed=42)

        assert spine_data["name"] == "Test Campaign"
        assert spine_data["era"] == "galactic_civil_war"
        assert "generation_metadata" in spine_data
        assert spine_data["generation_metadata"]["generation_mode"] == "mode1"
        assert seed == 42

    @patch("studio.generate._call_llm")
    def test_generate_mode1_strips_code_fences(self, mock_llm):
        from studio.generate import generate_mode1, Mode1Input
        fenced = f"```json\n{json.dumps(MINIMAL_SPINE_DATA)}\n```"
        mock_llm.return_value = fenced

        inputs = Mode1Input(era="old_republic", location="Coruscant")
        spine_data, _ = generate_mode1(inputs, master_seed=99)
        assert spine_data["name"] == "Test Campaign"

    @patch("studio.generate._call_llm")
    def test_generate_mode1_retries_on_bad_json(self, mock_llm):
        from studio.generate import generate_mode1, Mode1Input
        mock_llm.side_effect = [
            "not valid json",
            "still not json",
            json.dumps(MINIMAL_SPINE_DATA),
        ]

        inputs = Mode1Input(era="galactic_civil_war", location="Tatooine")
        # The inner _call_llm is mocked, but generate_mode1 has its own retry.
        # First two calls raise JSONDecodeError, third succeeds.
        spine_data, _ = generate_mode1(inputs, master_seed=42)
        assert spine_data["name"] == "Test Campaign"


# ── Route Tests ──────────────────────────────────────────────────────


class TestCS4Routes:
    @pytest.fixture
    def client(self):
        """Create a test client for the studio routes."""
        # Ensure DB tables exist
        os.environ.setdefault("STORYTELLER_DB", ":memory:")
        from fastapi.testclient import TestClient
        from api.main import app
        return TestClient(app)

    def test_mode1_route_exists(self, client):
        """Mode 1 route should exist and return 502 (LLM not available in test)."""
        resp = client.post("/studio/generate/mode1", json={
            "era": "galactic_civil_war",
            "location": "Nar Shaddaa",
        })
        # Will fail with 502 because no LLM is available, but route exists
        assert resp.status_code in (200, 502)

    def test_saga_route_requires_prior(self, client):
        """Saga route should require prior_campaign_json."""
        resp = client.post("/studio/generate/saga", json={
            "era": "galactic_civil_war",
            "location": "Nar Shaddaa",
        })
        assert resp.status_code == 400

    def test_saga_route_exists(self, client):
        """Saga route should exist and accept prior campaign."""
        resp = client.post("/studio/generate/saga", json={
            "era": "galactic_civil_war",
            "location": "Nar Shaddaa",
            "prior_campaign_json": {
                "throughline_question": "test?",
                "era": "galactic_civil_war",
                "total_acts": 3,
            },
        })
        # Will fail with 502 (no LLM) but route exists
        assert resp.status_code in (200, 502)
