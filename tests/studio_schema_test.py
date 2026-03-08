"""
Campaign Studio schema and validation tests — Phase CS-1.

Success criteria:
1. The Nar Shaddaa Job spine passes all four validation gates.
2. Deliberately malformed spines fail with specific, actionable errors.
"""

import json
import copy
import pytest
from pathlib import Path

from studio.schema import CampaignSpine
from studio.validate import validate_spine, ValidationReport
from studio.difficulty import compute_difficulty_curve


# ── Fixtures ──────────────────────────────────────────────────────────

CAMPAIGN_DIR = Path(__file__).parent.parent / "data" / "campaigns"


@pytest.fixture
def nar_shaddaa_data() -> dict:
    """Load the Nar Shaddaa Job campaign spine JSON."""
    path = CAMPAIGN_DIR / "nar_shaddaa_job.json"
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def nar_shaddaa_spine(nar_shaddaa_data) -> CampaignSpine:
    """Parse the Nar Shaddaa Job as a CampaignSpine model."""
    return CampaignSpine(**nar_shaddaa_data)


# ── Schema parsing tests ─────────────────────────────────────────────


class TestSchemaParsing:
    """Test that the schema correctly parses well-formed spines."""

    def test_nar_shaddaa_parses(self, nar_shaddaa_data):
        """The test campaign spine parses without error."""
        spine = CampaignSpine(**nar_shaddaa_data)
        assert spine.name == "The Nar Shaddaa Job"
        assert spine.era == "galactic_civil_war"
        assert spine.total_acts == 4
        assert len(spine.acts) == 4
        assert len(spine.allegiances) == 2

    def test_acts_sequential(self, nar_shaddaa_spine):
        """Acts are numbered sequentially starting from 1."""
        for i, act in enumerate(nar_shaddaa_spine.acts):
            assert act.number == i + 1

    def test_allegiances_have_variants(self, nar_shaddaa_spine):
        """Each allegiance contains at least one character variant."""
        for allegiance in nar_shaddaa_spine.allegiances:
            assert len(allegiance.character_variants) >= 1

    def test_npc_roster_populated(self, nar_shaddaa_spine):
        """NPC roster has entries."""
        assert len(nar_shaddaa_spine.npc_roster) >= 1

    def test_throughline_question(self, nar_shaddaa_spine):
        """Throughline question is present and ends with ?."""
        assert nar_shaddaa_spine.throughline_question.endswith("?")

    def test_variant_loadout_parsed(self, nar_shaddaa_spine):
        """Character variant loadout is correctly parsed."""
        keth = nar_shaddaa_spine.allegiances[0].character_variants[0]
        assert keth.id == "keth_varso"
        assert len(keth.starting_loadout.weapons) == 1
        assert keth.starting_loadout.armor is not None
        assert keth.starting_loadout.armor.name == "Spacer's leather jacket (armored liner)"

    def test_xp_bonus_conditions_parsed(self, nar_shaddaa_spine):
        """Act XP bonus conditions are correctly parsed."""
        act1 = nar_shaddaa_spine.acts[0]
        assert act1.xp_base == 20
        assert len(act1.xp_bonus_conditions) == 3
        assert act1.xp_bonus_conditions[0].condition_type == "anchor_engagement"

    def test_npc_relationships_parsed(self, nar_shaddaa_spine):
        """NPC relationships are correctly parsed."""
        vossk = nar_shaddaa_spine.npc_roster[0]
        assert len(vossk.npc_relationships) == 1
        assert vossk.npc_relationships[0].npc == "Doss"
        assert vossk.npc_relationships[0].weight == -0.3

    def test_variation_points_parsed(self, nar_shaddaa_spine):
        """Variation points are correctly parsed."""
        assert len(nar_shaddaa_spine.variation_points) == 1
        vp = nar_shaddaa_spine.variation_points[0]
        assert vp.id == "doss_fate"
        assert len(vp.options) == 3

    def test_factions_parsed(self, nar_shaddaa_spine):
        """Faction specs are correctly parsed."""
        assert len(nar_shaddaa_spine.factions) == 2
        vossk_cartel = nar_shaddaa_spine.factions[0]
        assert vossk_cartel.faction_id == "vossk_cartel"
        assert vossk_cartel.disposition_start == 0.45


# ── Validation gate tests ────────────────────────────────────────────


class TestValidationGates:
    """Test that the Nar Shaddaa Job passes all validation gates."""

    def test_full_validation_passes(self, nar_shaddaa_spine):
        """The test spine passes all validation gates."""
        report = validate_spine(nar_shaddaa_spine)
        assert report.passed, f"Validation failed: {[e.message for e in report.errors]}"
        assert 1 in report.gates_passed
        assert 2 in report.gates_passed
        assert 3 in report.gates_passed
        assert 4 in report.gates_passed

    def test_difficulty_curve_computed(self, nar_shaddaa_spine):
        """Difficulty curve is computed as part of validation."""
        report = validate_spine(nar_shaddaa_spine)
        assert report.difficulty_curve is not None
        assert len(report.difficulty_curve.per_act) == 4
        assert report.difficulty_curve.curve_shape in (
            "ascending", "descending", "flat", "arc", "inverted_arc"
        )

    def test_difficulty_curve_standalone(self, nar_shaddaa_spine):
        """Difficulty curve can be computed independently."""
        curve = compute_difficulty_curve(nar_shaddaa_spine)
        assert len(curve.per_act) == 4
        for act_diff in curve.per_act:
            assert 0.0 <= act_diff.composite <= 1.0
            assert 0.0 <= act_diff.anchor_intensity <= 1.0

    def test_report_to_dict(self, nar_shaddaa_spine):
        """Validation report serializes to dict."""
        report = validate_spine(nar_shaddaa_spine)
        d = report.to_dict()
        assert isinstance(d, dict)
        assert d["passed"] is True
        assert isinstance(d["errors"], list)
        assert isinstance(d["warnings"], list)


# ── Deliberate failure tests ──────────────────────────────────────────


class TestDeliberateFailures:
    """Test that malformed spines fail with specific error messages."""

    def test_act_count_mismatch(self, nar_shaddaa_data):
        """Fails when total_acts doesn't match actual act count."""
        data = copy.deepcopy(nar_shaddaa_data)
        data["total_acts"] = 5  # But only 4 acts
        spine = CampaignSpine(**data)
        report = validate_spine(spine)
        assert not report.passed
        errors = [e for e in report.errors if e.code == "act_count_mismatch"]
        assert len(errors) == 1
        assert "5" in errors[0].message

    def test_throughline_no_question_mark(self, nar_shaddaa_data):
        """Fails when throughline_question doesn't end with ?."""
        data = copy.deepcopy(nar_shaddaa_data)
        data["throughline_question"] = "This is a statement not a question"
        spine = CampaignSpine(**data)
        report = validate_spine(spine)
        assert not report.passed
        errors = [e for e in report.errors if e.code == "throughline_no_question_mark"]
        assert len(errors) == 1

    def test_variant_allegiance_mismatch(self, nar_shaddaa_data):
        """Fails when variant allegiance doesn't match containing allegiance."""
        data = copy.deepcopy(nar_shaddaa_data)
        data["allegiances"][0]["character_variants"][0]["allegiance"] = "wrong_faction"
        spine = CampaignSpine(**data)
        report = validate_spine(spine)
        assert not report.passed
        errors = [e for e in report.errors if e.code == "variant_allegiance_mismatch"]
        assert len(errors) == 1
        assert "wrong_faction" in errors[0].message

    def test_acts_not_sequential_rejected_by_pydantic(self, nar_shaddaa_data):
        """Pydantic rejects non-sequential act numbers."""
        data = copy.deepcopy(nar_shaddaa_data)
        data["acts"][1]["number"] = 5  # Should be 2
        with pytest.raises(Exception):  # Pydantic validation error
            CampaignSpine(**data)

    def test_npc_relationship_not_in_roster(self, nar_shaddaa_data):
        """Fails when NPC relationship references non-existent NPC."""
        data = copy.deepcopy(nar_shaddaa_data)
        data["npc_roster"][0]["npc_relationships"].append({
            "npc": "Ghost NPC",
            "nature": "unknown",
            "weight": 0.5,
        })
        spine = CampaignSpine(**data)
        report = validate_spine(spine)
        assert not report.passed
        errors = [e for e in report.errors if e.code == "npc_relationship_not_in_roster"]
        assert len(errors) == 1
        assert "Ghost NPC" in errors[0].message

    def test_duplicate_faction_id(self, nar_shaddaa_data):
        """Fails when faction IDs are duplicated."""
        data = copy.deepcopy(nar_shaddaa_data)
        data["factions"].append(copy.deepcopy(data["factions"][0]))
        spine = CampaignSpine(**data)
        report = validate_spine(spine)
        assert not report.passed
        errors = [e for e in report.errors if e.code == "duplicate_faction_id"]
        assert len(errors) == 1

    def test_faction_drift_invalid_act(self, nar_shaddaa_data):
        """Fails when per_act_drift references non-existent act number."""
        data = copy.deepcopy(nar_shaddaa_data)
        data["factions"][0]["per_act_drift"]["99"] = {"disposition": 0.1}
        spine = CampaignSpine(**data)
        report = validate_spine(spine)
        assert not report.passed
        errors = [e for e in report.errors if e.code == "faction_drift_invalid_act"]
        assert len(errors) == 1
        assert "99" in errors[0].message

    def test_force_discovery_window_out_of_range(self, nar_shaddaa_data):
        """Fails when force_discovery_window exceeds act range."""
        data = copy.deepcopy(nar_shaddaa_data)
        data["force_discovery_window"] = [1, 10]  # Only 4 acts
        spine = CampaignSpine(**data)
        report = validate_spine(spine)
        assert not report.passed
        errors = [e for e in report.errors if e.code == "force_discovery_window_out_of_range"]
        assert len(errors) == 1

    def test_import_xp_range_inverted(self, nar_shaddaa_data):
        """Fails when import interface XP range is inverted."""
        data = copy.deepcopy(nar_shaddaa_data)
        data["import_interface"] = {
            "target_xp_range": [500, 100],  # min > max
        }
        spine = CampaignSpine(**data)
        report = validate_spine(spine)
        assert not report.passed
        errors = [e for e in report.errors if e.code == "import_xp_range_inverted"]
        assert len(errors) == 1

    def test_canon_npc_missing_voice(self, nar_shaddaa_data):
        """Fails when canon NPC lacks canon_voice."""
        data = copy.deepcopy(nar_shaddaa_data)
        data["npc_roster"][0]["canon"] = True
        # No canon_voice set
        spine = CampaignSpine(**data)
        report = validate_spine(spine)
        assert not report.passed
        errors = [e for e in report.errors if e.code == "canon_npc_missing_voice"]
        assert len(errors) == 1

    def test_duplicate_ship_id(self, nar_shaddaa_data):
        """Fails when vehicle registry has duplicate ship IDs."""
        data = copy.deepcopy(nar_shaddaa_data)
        ship = {
            "ship_id": "miras_luck",
            "name": "Mira's Luck",
            "type": "light_freighter",
            "silhouette": 4,
            "speed": 3,
            "handling": 0,
            "hull_threshold": 22,
            "system_strain_threshold": 14,
            "armor": 3,
        }
        data["vehicle_registry"] = [ship, copy.deepcopy(ship)]
        spine = CampaignSpine(**data)
        report = validate_spine(spine)
        assert not report.passed
        errors = [e for e in report.errors if e.code == "duplicate_ship_id"]
        assert len(errors) == 1

    def test_pydantic_rejects_too_few_allegiances(self, nar_shaddaa_data):
        """Pydantic rejects fewer than 2 allegiances."""
        data = copy.deepcopy(nar_shaddaa_data)
        data["allegiances"] = [data["allegiances"][0]]  # Only 1
        with pytest.raises(Exception):
            CampaignSpine(**data)

    def test_pydantic_rejects_missing_required_fields(self):
        """Pydantic rejects spine missing required fields."""
        with pytest.raises(Exception):
            CampaignSpine(**{"name": "Incomplete"})


# ── Gate 2: NPC coherence tests ───────────────────────────────────────


class TestGate2NPCCoherence:
    """Test NPC disposition trajectory analysis."""

    def test_large_disposition_shift_warned(self, nar_shaddaa_data):
        """Warns about large disposition shifts without transition language."""
        data = copy.deepcopy(nar_shaddaa_data)
        # Force a large shift without transition words
        data["npc_roster"][0]["per_act_state"][1]["disposition_expected"] = 0.9
        data["npc_roster"][0]["per_act_state"][1]["role_in_act"] = "Neutral observer"
        spine = CampaignSpine(**data)
        report = validate_spine(spine)
        warnings = [w for w in report.warnings if w.code == "large_disposition_shift"]
        assert len(warnings) >= 1

    def test_shift_with_transition_language_ok(self, nar_shaddaa_data):
        """No warning when large shift has transition language."""
        data = copy.deepcopy(nar_shaddaa_data)
        data["npc_roster"][0]["per_act_state"][1]["disposition_expected"] = 0.9
        data["npc_roster"][0]["per_act_state"][1]["role_in_act"] = "Dramatic betrayal reveals true allegiance"
        spine = CampaignSpine(**data)
        report = validate_spine(spine)
        shift_warnings = [w for w in report.warnings if w.code == "large_disposition_shift"]
        # The specific shift from act 1→2 should not be warned about
        vossk_warns = [w for w in shift_warnings if "Vossk" in w.message and "act 1 to act 2" in w.message]
        assert len(vossk_warns) == 0


# ── Gate 3: Relationship network tests ────────────────────────────────


class TestGate3RelationshipNetwork:
    """Test relationship network positivity skew detection."""

    def test_balanced_relationships_pass(self, nar_shaddaa_spine):
        """The test spine's relationships pass without errors."""
        report = validate_spine(nar_shaddaa_spine)
        gate3_errors = [e for e in report.errors if e.gate == 3]
        assert len(gate3_errors) == 0

    def test_all_positive_relationships_warned(self, nar_shaddaa_data):
        """Warns when all NPC relationships are positive."""
        data = copy.deepcopy(nar_shaddaa_data)
        # Make all relationships positive
        for npc in data["npc_roster"]:
            for rel in npc.get("npc_relationships", []):
                rel["weight"] = 0.8
        # Add more positive relationships to trigger the ratio check
        data["npc_roster"][0]["npc_relationships"] = [
            {"npc": "Doss", "nature": "friend", "weight": 0.7},
        ]
        data["npc_roster"][1]["npc_relationships"] = [
            {"npc": "Vossk the Patient", "nature": "ally", "weight": 0.6},
        ]
        spine = CampaignSpine(**data)
        report = validate_spine(spine)
        skew_warnings = [w for w in report.warnings if "positiv" in w.code.lower()]
        assert len(skew_warnings) >= 1


# ── Difficulty curve tests ────────────────────────────────────────────


class TestDifficultyCurve:
    """Test difficulty curve computation."""

    def test_curve_shape_for_nar_shaddaa(self, nar_shaddaa_spine):
        """The Nar Shaddaa Job has a recognizable difficulty curve."""
        curve = compute_difficulty_curve(nar_shaddaa_spine)
        assert curve.curve_shape in ("ascending", "arc", "descending", "flat", "inverted_arc")
        # The climax (act 3) should be the most intense
        composites = [a.composite for a in curve.per_act]
        assert composites[2] > composites[0], "Climax act should be harder than opening"

    def test_per_act_scores_bounded(self, nar_shaddaa_spine):
        """All per-act scores are between 0 and 1."""
        curve = compute_difficulty_curve(nar_shaddaa_spine)
        for act_diff in curve.per_act:
            assert 0.0 <= act_diff.anchor_intensity <= 1.0
            assert 0.0 <= act_diff.npc_opposition <= 1.0
            assert 0.0 <= act_diff.mechanical_pressure <= 1.0
            assert 0.0 <= act_diff.pacing_pressure <= 1.0
            assert 0.0 <= act_diff.composite <= 1.0

    def test_curve_serialization(self, nar_shaddaa_spine):
        """Difficulty curve serializes to dict cleanly."""
        curve = compute_difficulty_curve(nar_shaddaa_spine)
        d = curve.to_dict()
        assert "per_act" in d
        assert "overall_composite" in d
        assert "curve_shape" in d
        assert isinstance(d["per_act"], list)
