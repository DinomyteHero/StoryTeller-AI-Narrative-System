"""
CS-5 Test Suite — Campaign Studio Narrative Quality.

Tests the story architecture layer, Gate 4 narrative evaluation,
enhanced generation pipeline, and narrative quality scoring for
Stage 5 selection.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from studio.schema import (
    CampaignSpine,
    StoryArchitecture,
    CharacterVariant,
    NPC,
    Act,
    VALID_PRESSURE_TYPES,
    VALID_DRAMATIC_FUNCTIONS,
)
from studio.architect import (
    generate_architecture,
    architecture_to_prompt_block,
)
from studio.narrative_eval import (
    evaluate_narrative,
    gate4_check,
    score_narrative_quality,
    GATE_4A_DIMS,
    GATE_4B_DIMS,
    GATE_4C_DIMS,
)
from studio.seeding import STAGE_ARCHITECT, ALL_STAGES, derive_stage_seed
from studio.saga.select import _score_spine, select_best


# ── Fixtures ────────────────────────────────────────────────────────────


SAMPLE_ARCHITECTURE = {
    "dramatic_premise": "A smuggler discovers her regular cargo run is funding a weapons program that will destroy her home sector",
    "central_dramatic_question": "Can someone who has always looked away choose to see when seeing costs everything?",
    "story_promise": "Escalating moral compromise as comfort becomes complicity, and every choice to act has a price that silence never did",
    "protagonist_pressure_type": "moral",
    "antagonistic_force": "The economic machinery of Hutt-controlled shipping lanes, where everyone profits from not asking questions",
    "thematic_throughline": "Whether comfort earned through willful ignorance is worth what it costs others",
    "ending_payoff_sketch": "The protagonist faces a choice that makes the throughline unavoidable — not between good and evil, but between the life they built and the truth they can no longer ignore",
}


def _make_sample_spine(with_architecture: bool = False) -> dict:
    """Build a minimal valid spine dict for testing."""
    spine = {
        "name": "Shadows Over Nar Shaddaa",
        "era": "galactic_civil_war",
        "total_acts": 3,
        "throughline_question": "Can trust survive when everyone has a price?",
        "allegiances": [
            {
                "id": "smuggler",
                "display_name": "Smuggler's Guild",
                "description": "Independent operators surviving on the fringes of Imperial control",
                "character_variants": [{
                    "id": "keth",
                    "allegiance": "smuggler",
                    "pitch": "A Bothan smuggler whose network of contacts is both an asset and a liability",
                    "species": "Bothan",
                    "career": "Smuggler",
                    "career_type": "scoundrel",
                    "specializations": ["Scoundrel"],
                    "primary_game_line": "eote",
                    "force_sensitive": False,
                    "motivation_default": {"track": "obligation", "possible_types": ["debt", "favor"]},
                    "starting_situation": "Keth has been running cargo for three years without asking questions — until today",
                    "voice_baseline": "Quick, deflecting, uses humor as armor",
                    "background": "Former intelligence operative turned independent",
                    "integration_layer": {
                        "entry_point": "Keth's regular contact offers a job that pays triple normal rates for one simple delivery",
                        "personal_stakes": "The cargo manifest names Keth's childhood neighborhood as the target zone",
                    },
                    "characteristics_base": {"brawn": 2, "agility": 3, "intellect": 3, "cunning": 4, "willpower": 2, "presence": 2},
                    "skills_base": {"deception": 2, "streetwise": 2, "piloting_space": 1},
                    "wound_threshold": 12,
                    "strain_threshold": 14,
                    "soak": 2,
                    "protagonist_contradiction": "Believes he's a survivor who doesn't need anyone — actually terrified of being alone",
                    "pressure_revealed_identity": "Under maximum pressure, Keth discovers he will sacrifice profit for people — the opposite of what he's told himself for years",
                }],
            },
            {
                "id": "rebel",
                "display_name": "Rebel Sympathizers",
                "description": "Those who have chosen sides in the growing conflict against the Empire",
                "character_variants": [{
                    "id": "sera",
                    "allegiance": "rebel",
                    "pitch": "A former Imperial bureaucrat whose conscience finally caught up with her compliance",
                    "species": "Human",
                    "career": "Spy",
                    "career_type": "infiltrator",
                    "specializations": ["Infiltrator"],
                    "primary_game_line": "aor",
                    "force_sensitive": False,
                    "motivation_default": {"track": "duty", "possible_types": ["intelligence", "sabotage"]},
                    "starting_situation": "Sera defected six months ago and still flinches at every Imperial patrol",
                    "voice_baseline": "Measured, precise, occasionally cracks into raw emotion",
                    "background": "Ten years in Imperial logistics gave her the skills and the guilt",
                    "integration_layer": {
                        "entry_point": "Sera intercepts intelligence about a shipment that could expose an Imperial supply chain vulnerability",
                        "personal_stakes": "The supply chain she's trying to disrupt is one she personally built during her Imperial service",
                    },
                    "characteristics_base": {"brawn": 2, "agility": 2, "intellect": 4, "cunning": 3, "willpower": 3, "presence": 2},
                    "skills_base": {"computers": 2, "deception": 1, "knowledge_core": 2},
                    "wound_threshold": 11,
                    "strain_threshold": 14,
                    "soak": 2,
                    "protagonist_contradiction": "Believes defection redeemed her — actually running from the scale of what she enabled",
                    "pressure_revealed_identity": "Under pressure, Sera confronts that leaving the Empire was the easy part; dismantling what she built is the real cost",
                }],
            },
        ],
        "acts": [
            {
                "number": 1,
                "name": "The Routine",
                "tension": "rising",
                "dramatic_function": "setup",
                "opening_situation": "A standard cargo pickup at Docking Bay 94 turns strange when Keth's contact is visibly afraid",
                "opening_location": "Nar Shaddaa, Docking Bay 94",
                "galactic_context": "Imperial customs has tripled patrols in the Y'Toub system after a rebel cell was discovered operating from a nearby moon",
                "anchor": "Keth discovers the cargo manifest contains classified weapon components bound for a facility in his home sector",
                "next_anchor": "The investigation reveals who is funding the operation",
                "open_threads": ["cargo_origin", "contact_fear", "home_sector_threat"],
                "expected_turns": "4-6",
                "xp_base": 15,
                "xp_bonus_conditions": [],
            },
            {
                "number": 2,
                "name": "The Network",
                "tension": "critical",
                "dramatic_function": "launch",
                "opening_situation": "Following the cargo trail leads into the heart of Hutt commercial operations where everyone profits from not asking questions",
                "opening_location": "Nar Shaddaa, Corellian Sector",
                "galactic_context": "The Empire is offering bounties for information about smuggling operations, turning neighbors into informants",
                "anchor": "Keth must choose between exposing the weapons pipeline (destroying his livelihood) or delivering the cargo (funding the weapon)",
                "next_anchor": "The consequences of Act 2's choice cascade into a confrontation",
                "open_threads": ["cargo_origin", "home_sector_threat", "hutt_complicity"],
                "expected_turns": "5-7",
                "xp_base": 15,
                "xp_bonus_conditions": [],
            },
            {
                "number": 3,
                "name": "The Price",
                "tension": "climax",
                "dramatic_function": "confrontation",
                "opening_situation": "The weapon facility is operational and Keth's home sector is in the blast radius of a test firing",
                "opening_location": "Nar Shaddaa / Home Sector Transit",
                "galactic_context": "Imperial forces are closing in on suspected rebel activity, creating a shrinking window for action of any kind",
                "anchor": "Keth faces the full cost of his choice — whatever he decided in Act 2 has created consequences he cannot escape",
                "open_threads": ["home_sector_threat"],
                "expected_turns": "4-6",
                "xp_base": 20,
                "xp_bonus_conditions": [],
            },
        ],
        "npc_roster": [
            {
                "name": "Doss Korr",
                "role": "Cargo broker and longtime contact",
                "disposition_start": 0.7,
                "disposition_trajectory": "Starts friendly, becomes increasingly desperate as he realizes he's complicit",
                "motivation": "Protect his family by staying useful to the Hutts — not by being moral but by being necessary",
                "voice_notes": "Talks fast, nervous laugh, deflects serious questions with irrelevant details about cargo manifests",
                "behavioral_envelope": ["Will never directly betray Keth but will withhold information to protect himself", "Cannot bring himself to harm children — this is his hard limit"],
                "knows_at_start": ["The cargo is weapons-related", "The Hutts are the real clients"],
                "doesnt_know_at_start": ["The target is Keth's home sector"],
                "per_act_state": [
                    {"act": 1, "role_in_act": "Initial contact and reluctant informant", "disposition_expected": 0.7},
                    {"act": 2, "role_in_act": "Caught between Keth and the Hutts", "disposition_expected": 0.5},
                    {"act": 3, "role_in_act": "Must choose which side of complicity to stand on", "disposition_expected": "variable"},
                ],
                "npc_relationships": [
                    {"npc": "Venna Tal", "nature": "supplier and rival", "weight": -0.3},
                ],
                "thematic_argument": "Complicity is survivable — the system is too big to fight, so the best you can do is protect your own",
            },
            {
                "name": "Venna Tal",
                "role": "Hutt logistics coordinator",
                "disposition_start": 0.3,
                "disposition_trajectory": "Cold professional who becomes threatening when the operation is endangered",
                "motivation": "Advance her position in Hutt hierarchy through operational excellence — people are logistics problems to solve",
                "voice_notes": "Speaks in precise, clipped sentences. Never raises her voice. Silence is her weapon.",
                "behavioral_envelope": ["Will never negotiate from weakness", "Will sacrifice anyone except her Hutt patron", "Respects competence even in adversaries"],
                "knows_at_start": ["Full scope of the weapons operation", "Multiple smuggler networks involved"],
                "doesnt_know_at_start": ["Keth's personal connection to the target sector"],
                "per_act_state": [
                    {"act": 1, "role_in_act": "Unseen presence orchestrating the operation", "disposition_expected": 0.3},
                    {"act": 2, "role_in_act": "Direct antagonist when the operation is threatened", "disposition_expected": 0.2},
                    {"act": 3, "role_in_act": "Final obstacle — but one who respects Keth's choice even as she opposes it", "disposition_expected": 0.2},
                ],
                "npc_relationships": [
                    {"npc": "Doss Korr", "nature": "subordinate she tolerates", "weight": -0.3},
                ],
                "thematic_argument": "The system works because it works — morality is a luxury that the powerful don't need and the powerless can't afford",
            },
            {
                "name": "Mira Saan",
                "role": "Rebel intelligence analyst with local ties",
                "disposition_start": 0.5,
                "disposition_trajectory": "Wary alliance that deepens if Keth proves willing to act, collapses if he prioritizes self-interest",
                "motivation": "Stop the weapons program because she lost family to a similar weapon — but also because destroying it proves her defection meant something",
                "voice_notes": "Quiet, observational, long pauses before speaking. Delivers devastating truths in the same flat tone as small talk.",
                "behavioral_envelope": ["Will not compromise the rebel cell for any individual", "Cannot lie convincingly — her honesty is both strength and vulnerability"],
                "knows_at_start": ["The weapons program exists", "Imperial supply chain vulnerabilities"],
                "doesnt_know_at_start": ["The full network of smugglers involved", "Doss's family situation"],
                "per_act_state": [
                    {"act": 1, "role_in_act": "Approaches Keth with incomplete intelligence", "disposition_expected": 0.5},
                    {"act": 2, "role_in_act": "Tests whether Keth will act or just talk", "disposition_expected": 0.5},
                    {"act": 3, "role_in_act": "Offers partnership but only on terms of genuine commitment", "disposition_expected": "variable"},
                ],
                "npc_relationships": [
                    {"npc": "Doss Korr", "nature": "distrusts as complicit", "weight": -0.5},
                    {"npc": "Venna Tal", "nature": "target and opposite", "weight": -0.8},
                ],
                "thematic_argument": "Seeing the truth obligates action — once you know, silence becomes a choice, and choices have weight",
            },
        ],
        "variation_points": [
            {
                "id": "cargo_decision",
                "trigger_act": 2,
                "description": "What does Keth do with the weapon components?",
                "selection_method": "player_choice",
                "options": [
                    {"id": "deliver", "description": "Complete the delivery as contracted", "npc_state_changes": {}},
                    {"id": "divert", "description": "Divert the cargo to rebel contacts", "npc_state_changes": {}},
                    {"id": "destroy", "description": "Destroy the cargo and disappear", "npc_state_changes": {}},
                ],
            },
        ],
    }

    if with_architecture:
        spine["story_architecture"] = SAMPLE_ARCHITECTURE

    return spine


def _mock_llm_eval_response(all_pass: bool = True, fail_dims: list = None):
    """Build a mock LLM eval response."""
    fail_dims = fail_dims or []
    result = {}
    all_dims = list(GATE_4A_DIMS) + list(GATE_4C_DIMS) + list(GATE_4B_DIMS)
    for dim in all_dims:
        if dim in fail_dims:
            result[dim] = {"pass": False, "detail": f"Failed: {dim} check not met"}
        else:
            result[dim] = {"pass": True, "detail": f"Passed: {dim} check met"}
    return json.dumps(result)


def _mock_llm_score_response(scores: dict = None):
    """Build a mock LLM scoring response."""
    defaults = {
        "premise_strength": 4,
        "npc_thematic_diversity": 4,
        "dramatic_progression": 3,
        "throughline_testability": 4,
        "anti_genericity": 4,
    }
    if scores:
        defaults.update(scores)
    return json.dumps(defaults)


# ── Schema Tests ────────────────────────────────────────────────────────


class TestStoryArchitectureSchema:
    """Test the StoryArchitecture Pydantic model."""

    def test_valid_architecture(self):
        arch = StoryArchitecture(**SAMPLE_ARCHITECTURE)
        assert arch.dramatic_premise == SAMPLE_ARCHITECTURE["dramatic_premise"]
        assert arch.protagonist_pressure_type == "moral"

    def test_all_pressure_types_valid(self):
        for pt in VALID_PRESSURE_TYPES:
            arch = StoryArchitecture(
                dramatic_premise="A test premise that is long enough to pass",
                central_dramatic_question="Is this valid?",
                story_promise="A test promise that is long enough to pass validation",
                protagonist_pressure_type=pt,
                antagonistic_force="A systemic force that creates sustained pressure on everyone",
                thematic_throughline="A recurring idea explored from angles",
            )
            assert arch.protagonist_pressure_type == pt

    def test_invalid_pressure_type_rejected(self):
        with pytest.raises(Exception):
            StoryArchitecture(
                dramatic_premise="A test premise that is long enough to pass",
                central_dramatic_question="Is this valid?",
                story_promise="A test promise that is long enough to pass validation",
                protagonist_pressure_type="invalid_type",
                antagonistic_force="A systemic force that creates sustained pressure on everyone",
                thematic_throughline="A recurring idea explored from angles",
            )

    def test_cdq_must_end_with_question_mark(self):
        with pytest.raises(Exception):
            StoryArchitecture(
                dramatic_premise="A test premise that is long enough to pass",
                central_dramatic_question="This is not a question",
                story_promise="A test promise that is long enough to pass validation",
                protagonist_pressure_type="moral",
                antagonistic_force="A systemic force that creates sustained pressure on everyone",
                thematic_throughline="A recurring idea explored from angles",
            )

    def test_dramatic_premise_min_length(self):
        with pytest.raises(Exception):
            StoryArchitecture(
                dramatic_premise="Too short",
                central_dramatic_question="Valid?",
                story_promise="A test promise that is long enough to pass validation",
                protagonist_pressure_type="moral",
                antagonistic_force="A systemic force that creates sustained pressure on everyone",
                thematic_throughline="Valid theme",
            )


class TestSchemaNewFields:
    """Test new optional fields on existing models."""

    def test_spine_with_architecture(self):
        spine_data = _make_sample_spine(with_architecture=True)
        spine = CampaignSpine(**spine_data)
        assert spine.story_architecture is not None
        assert spine.story_architecture.protagonist_pressure_type == "moral"

    def test_spine_without_architecture(self):
        spine_data = _make_sample_spine(with_architecture=False)
        spine = CampaignSpine(**spine_data)
        assert spine.story_architecture is None

    def test_existing_spines_still_parse(self):
        """Ensure backward compatibility — new fields don't break existing spines."""
        import os
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data", "campaigns",
        )
        if not os.path.exists(data_dir):
            pytest.skip("Campaign data directory not found")

        spine_path = os.path.join(data_dir, "shadows_of_the_custodian.json")
        if not os.path.exists(spine_path):
            pytest.skip("shadows_of_the_custodian.json not found")

        with open(spine_path) as f:
            data = json.load(f)
        spine = CampaignSpine(**data)
        # The active campaign exercises the new CS-5 fields, so architecture
        # is populated rather than None — the backward-compat point is just
        # that the spine parses cleanly with or without these fields present.
        if spine.story_architecture is not None:
            assert spine.story_architecture.dramatic_premise
        # dramatic_function and thematic_argument are optional strings
        for act in spine.acts:
            assert isinstance(act.dramatic_function, str)
        for npc in spine.npc_roster:
            assert isinstance(npc.thematic_argument, str)

    def test_variant_has_contradiction_field(self):
        spine_data = _make_sample_spine()
        spine = CampaignSpine(**spine_data)
        variant = spine.allegiances[0].character_variants[0]
        assert variant.protagonist_contradiction != ""
        assert "survivor" in variant.protagonist_contradiction.lower()

    def test_act_has_dramatic_function_field(self):
        spine_data = _make_sample_spine()
        spine = CampaignSpine(**spine_data)
        assert spine.acts[0].dramatic_function == "setup"
        assert spine.acts[1].dramatic_function == "launch"
        assert spine.acts[2].dramatic_function == "confrontation"

    def test_npc_has_thematic_argument_field(self):
        spine_data = _make_sample_spine()
        spine = CampaignSpine(**spine_data)
        for npc in spine.npc_roster:
            assert npc.thematic_argument != ""

    def test_dramatic_function_constants_defined(self):
        assert "setup" in VALID_DRAMATIC_FUNCTIONS
        assert "confrontation" in VALID_DRAMATIC_FUNCTIONS
        assert "resolution" in VALID_DRAMATIC_FUNCTIONS
        assert len(VALID_DRAMATIC_FUNCTIONS) == 8


# ── Architect Tests ─────────────────────────────────────────────────────


class TestArchitect:
    """Test the pre-generation architecture planning layer."""

    def test_generate_architecture_with_mock_llm(self):
        mock_response = json.dumps(SAMPLE_ARCHITECTURE)

        arch = generate_architecture(
            era="galactic_civil_war",
            location="Nar Shaddaa",
            tone="gritty",
            master_seed=42,
            llm_call_fn=lambda *a, **kw: mock_response,
        )

        assert isinstance(arch, StoryArchitecture)
        assert arch.protagonist_pressure_type == "moral"
        assert arch.central_dramatic_question.endswith("?")

    def test_architecture_to_prompt_block(self):
        arch = StoryArchitecture(**SAMPLE_ARCHITECTURE)
        block = architecture_to_prompt_block(arch)

        assert "STORY ARCHITECTURE" in block
        assert arch.dramatic_premise in block
        assert arch.antagonistic_force in block
        assert "dramatic_function" in block
        assert "protagonist_contradiction" in block
        assert "thematic_argument" in block

    def test_architect_seed_determinism(self):
        seed_a = derive_stage_seed(42, STAGE_ARCHITECT)
        seed_b = derive_stage_seed(42, STAGE_ARCHITECT)
        seed_c = derive_stage_seed(99, STAGE_ARCHITECT)

        assert seed_a == seed_b  # Same master seed → same architect seed
        assert seed_a != seed_c  # Different master → different seed

    def test_stage_architect_in_all_stages(self):
        assert STAGE_ARCHITECT in ALL_STAGES

    def test_architecture_with_mode2_fields(self):
        mock_response = json.dumps(SAMPLE_ARCHITECTURE)

        arch = generate_architecture(
            era="galactic_civil_war",
            location="Nar Shaddaa",
            tone="gritty",
            throughline_question="Can trust survive betrayal?",
            campaign_concept="A smuggler's moral erosion",
            moral_register="morally gray",
            master_seed=42,
            llm_call_fn=lambda *a, **kw: mock_response,
        )

        assert isinstance(arch, StoryArchitecture)

    def test_architecture_retries_on_bad_json(self):
        call_count = 0

        def flaky_llm(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return "not valid json"
            return json.dumps(SAMPLE_ARCHITECTURE)

        arch = generate_architecture(
            era="galactic_civil_war",
            location="Nar Shaddaa",
            tone="gritty",
            master_seed=42,
            llm_call_fn=flaky_llm,
        )

        assert isinstance(arch, StoryArchitecture)
        assert call_count == 3

    def test_architecture_fails_after_max_retries(self):
        with pytest.raises(RuntimeError, match="Architecture generation failed"):
            generate_architecture(
                era="galactic_civil_war",
                location="Nar Shaddaa",
                tone="gritty",
                master_seed=42,
                llm_call_fn=lambda *a, **kw: "not json",
                max_retries=2,
            )


# ── Narrative Evaluation Tests ──────────────────────────────────────────


class TestNarrativeEvaluation:
    """Test Gate 4 narrative evaluation."""

    def test_evaluate_narrative_all_pass(self):
        spine_data = _make_sample_spine(with_architecture=True)
        spine = CampaignSpine(**spine_data)

        mock_response = _mock_llm_eval_response(all_pass=True)
        results = evaluate_narrative(
            spine, llm_call_fn=lambda *a, **kw: mock_response,
        )

        # All dimensions should be present
        for dim in GATE_4A_DIMS:
            assert dim in results
            assert results[dim]["pass"] is True
        for dim in GATE_4C_DIMS:
            assert dim in results
            assert results[dim]["pass"] is True
        for dim in GATE_4B_DIMS:
            assert dim in results
            assert results[dim]["pass"] is True

    def test_evaluate_narrative_without_architecture(self):
        spine_data = _make_sample_spine(with_architecture=False)
        spine = CampaignSpine(**spine_data)

        # Only 4a and 4c dimensions in the response
        gate_4a_4c_response = {}
        for dim in list(GATE_4A_DIMS) + list(GATE_4C_DIMS):
            gate_4a_4c_response[dim] = {"pass": True, "detail": "OK"}
        mock_response = json.dumps(gate_4a_4c_response)

        results = evaluate_narrative(
            spine, llm_call_fn=lambda *a, **kw: mock_response,
        )

        for dim in GATE_4A_DIMS:
            assert dim in results
        for dim in GATE_4C_DIMS:
            assert dim in results

    def test_gate4_check_no_errors_all_pass(self):
        spine_data = _make_sample_spine(with_architecture=True)
        spine = CampaignSpine(**spine_data)

        mock_response = _mock_llm_eval_response(all_pass=True)
        errors, warnings = gate4_check(
            spine, llm_call_fn=lambda *a, **kw: mock_response,
        )

        assert len(errors) == 0
        assert len(warnings) == 0

    def test_gate4_check_warnings_on_single_failure(self):
        spine_data = _make_sample_spine()
        spine = CampaignSpine(**spine_data)

        mock_response = _mock_llm_eval_response(
            fail_dims=["thread_continuity"],
        )
        errors, warnings = gate4_check(
            spine, llm_call_fn=lambda *a, **kw: mock_response,
        )

        assert len(errors) == 0
        assert len(warnings) == 1
        assert "thread_continuity" in warnings[0]["code"]

    def test_gate4_check_error_on_three_coherence_failures(self):
        spine_data = _make_sample_spine()
        spine = CampaignSpine(**spine_data)

        mock_response = _mock_llm_eval_response(
            fail_dims=[
                "thread_continuity",
                "npc_trajectory_consistency",
                "throughline_presence",
            ],
        )
        errors, warnings = gate4_check(
            spine, llm_call_fn=lambda *a, **kw: mock_response,
        )

        assert len(errors) == 1
        assert "coherence" in errors[0]["code"]
        assert len(warnings) == 3  # Each failure is also a warning

    def test_gate4_check_error_on_three_genericity_failures(self):
        spine_data = _make_sample_spine()
        spine = CampaignSpine(**spine_data)

        mock_response = _mock_llm_eval_response(
            fail_dims=[
                "npc_distinctiveness",
                "anchor_specificity",
                "escalation_authenticity",
            ],
        )
        errors, warnings = gate4_check(
            spine, llm_call_fn=lambda *a, **kw: mock_response,
        )

        assert len(errors) == 1
        assert "genericity" in errors[0]["code"]


# ── Narrative Scoring Tests ─────────────────────────────────────────────


class TestNarrativeScoring:
    """Test Stage 5 narrative quality scoring."""

    def test_score_narrative_quality_good(self):
        spine_data = _make_sample_spine()
        mock_response = _mock_llm_score_response({
            "premise_strength": 5,
            "npc_thematic_diversity": 5,
            "dramatic_progression": 5,
            "throughline_testability": 5,
            "anti_genericity": 5,
        })

        score = score_narrative_quality(
            spine_data, llm_call_fn=lambda *a, **kw: mock_response,
        )
        assert score == 1.0  # All 5s → (5-1)/4 = 1.0

    def test_score_narrative_quality_poor(self):
        spine_data = _make_sample_spine()
        mock_response = _mock_llm_score_response({
            "premise_strength": 1,
            "npc_thematic_diversity": 1,
            "dramatic_progression": 1,
            "throughline_testability": 1,
            "anti_genericity": 1,
        })

        score = score_narrative_quality(
            spine_data, llm_call_fn=lambda *a, **kw: mock_response,
        )
        assert score == 0.0  # All 1s → (1-1)/4 = 0.0

    def test_score_narrative_quality_mixed(self):
        spine_data = _make_sample_spine()
        mock_response = _mock_llm_score_response({
            "premise_strength": 4,
            "npc_thematic_diversity": 3,
            "dramatic_progression": 4,
            "throughline_testability": 3,
            "anti_genericity": 4,
        })

        score = score_narrative_quality(
            spine_data, llm_call_fn=lambda *a, **kw: mock_response,
        )
        # Mean = (4+3+4+3+4)/5 = 3.6, normalized = (3.6-1)/4 = 0.65
        assert 0.6 <= score <= 0.7

    def test_score_narrative_quality_fallback_on_bad_json(self):
        spine_data = _make_sample_spine()
        score = score_narrative_quality(
            spine_data, llm_call_fn=lambda *a, **kw: "not json",
        )
        assert score == 0.5  # Fallback neutral


# ── Stage 5 Enhanced Selection Tests ────────────────────────────────────


class TestStage5Enhancement:
    """Test enhanced Stage 5 selection with narrative scoring."""

    def test_score_spine_structural_only(self):
        spine_data = _make_sample_spine()
        scores = _score_spine(spine_data)

        assert "structural_quality" in scores
        assert "novelty" in scores
        assert "diversity_vs_prior" in scores
        assert "composite" in scores
        assert "narrative_quality" not in scores
        assert 0.0 <= scores["composite"] <= 1.0

    def test_score_spine_with_narrative(self):
        spine_data = _make_sample_spine()
        mock_response = _mock_llm_score_response()

        scores = _score_spine(
            spine_data,
            use_narrative_scoring=True,
            llm_call_fn=lambda *a, **kw: mock_response,
        )

        assert "narrative_quality" in scores
        assert "structural_quality" in scores
        assert 0.0 <= scores["narrative_quality"] <= 1.0
        assert 0.0 <= scores["composite"] <= 1.0

    def test_narrative_scoring_changes_composite(self):
        spine_data = _make_sample_spine()

        # Without narrative scoring
        scores_struct = _score_spine(spine_data)

        # With narrative scoring (high quality)
        high_response = _mock_llm_score_response({
            "premise_strength": 5,
            "npc_thematic_diversity": 5,
            "dramatic_progression": 5,
            "throughline_testability": 5,
            "anti_genericity": 5,
        })
        scores_high = _score_spine(
            spine_data,
            use_narrative_scoring=True,
            llm_call_fn=lambda *a, **kw: high_response,
        )

        # With narrative scoring (low quality)
        low_response = _mock_llm_score_response({
            "premise_strength": 1,
            "npc_thematic_diversity": 1,
            "dramatic_progression": 1,
            "throughline_testability": 1,
            "anti_genericity": 1,
        })
        scores_low = _score_spine(
            spine_data,
            use_narrative_scoring=True,
            llm_call_fn=lambda *a, **kw: low_response,
        )

        # High narrative quality should produce higher composite
        assert scores_high["composite"] > scores_low["composite"]

    def test_select_best_with_narrative_scoring(self):
        spine_a = _make_sample_spine()
        spine_b = _make_sample_spine()
        spine_b["name"] = "Alternative Campaign"

        call_count = 0

        def mock_llm(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 1:
                return _mock_llm_score_response({"premise_strength": 5, "anti_genericity": 5})
            return _mock_llm_score_response({"premise_strength": 2, "anti_genericity": 2})

        drafts = [
            {"spine_data": spine_a, "label": "a"},
            {"spine_data": spine_b, "label": "b"},
        ]

        result = select_best(
            drafts,
            top_k=1,
            use_narrative_scoring=True,
            llm_call_fn=mock_llm,
        )

        assert len(result) == 1
        assert "scores" in result[0]
        assert "narrative_quality" in result[0]["scores"]
