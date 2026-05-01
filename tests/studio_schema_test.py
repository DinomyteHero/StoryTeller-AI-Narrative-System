"""
Campaign Studio schema and validation tests — Phase CS-1.

Success criteria:
1. The Shadows of the Custodian spine passes all four validation gates.
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
def praxeum_data() -> dict:
    """Load the Shadows of the Custodian campaign spine JSON."""
    path = CAMPAIGN_DIR / "shadows_of_the_custodian.json"
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def praxeum_spine(praxeum_data) -> CampaignSpine:
    """Parse Shadows of the Custodian as a CampaignSpine model."""
    return CampaignSpine(**praxeum_data)


# Back-compat aliases — older tests in this file reference these names.
nar_shaddaa_data = praxeum_data
nar_shaddaa_spine = praxeum_spine


# ── Schema parsing tests ─────────────────────────────────────────────


class TestSchemaParsing:
    """Test that the schema correctly parses well-formed spines."""

    def test_nar_shaddaa_parses(self, praxeum_data):
        """The canonical campaign spine parses without error."""
        spine = CampaignSpine(**praxeum_data)
        assert spine.name == "Shadows of the Custodian"
        assert spine.era == "new_republic"
        assert spine.total_acts >= 2
        assert len(spine.acts) == spine.total_acts
        assert len(spine.allegiances) >= 2

    def test_acts_sequential(self, praxeum_spine):
        """Acts are numbered sequentially starting from 1."""
        for i, act in enumerate(praxeum_spine.acts):
            assert act.number == i + 1

    def test_allegiances_have_variants(self, praxeum_spine):
        """Each allegiance contains at least one character variant."""
        for allegiance in praxeum_spine.allegiances:
            assert len(allegiance.character_variants) >= 1

    def test_npc_roster_populated(self, praxeum_spine):
        """NPC roster has entries."""
        assert len(praxeum_spine.npc_roster) >= 1

    def test_throughline_question(self, praxeum_spine):
        """Throughline question is present and ends with ?."""
        assert praxeum_spine.throughline_question.endswith("?")

    def test_variant_loadout_parsed(self, praxeum_spine):
        """Character variant loadout is correctly parsed."""
        student = praxeum_spine.allegiances[0].character_variants[0]
        assert student.id == "clovis_beryl"
        # Clovis is a Sentinel/Shadow — loadout includes saber and hold-out blaster
        assert student.starting_loadout is not None
        assert len(student.starting_loadout.weapons) >= 1

    def test_xp_bonus_conditions_parsed(self, praxeum_spine):
        """Act XP bonus conditions are correctly parsed."""
        act1 = praxeum_spine.acts[0]
        assert act1.xp_base >= 10
        assert len(act1.xp_bonus_conditions) >= 1
        # Common condition type — every well-formed act should have it
        condition_types = {c.condition_type for c in act1.xp_bonus_conditions}
        assert "anchor_engagement" in condition_types

    def test_npc_relationships_parsed(self, praxeum_spine):
        """NPC relationships are correctly parsed."""
        # Pick the first NPC that actually has relationships defined.
        npc_with_rels = next(
            (n for n in praxeum_spine.npc_roster if n.npc_relationships),
            None,
        )
        assert npc_with_rels is not None, "Expected at least one NPC with relationships"
        rel = npc_with_rels.npc_relationships[0]
        assert rel.npc  # non-empty target name
        assert -1.0 <= rel.weight <= 1.0

    def test_variation_points_parsed(self, praxeum_spine):
        """Variation points are correctly parsed."""
        assert len(praxeum_spine.variation_points) >= 1
        vp = praxeum_spine.variation_points[0]
        assert vp.id  # non-empty id
        assert len(vp.options) >= 2

    def test_factions_parsed(self, praxeum_spine):
        """Faction specs are correctly parsed."""
        assert len(praxeum_spine.factions) >= 2
        first = praxeum_spine.factions[0]
        assert first.faction_id  # non-empty id
        assert 0.0 <= first.disposition_start <= 1.0


class TestBondEvents:
    """Bond events parse and reference real cohort members."""

    def test_bond_events_parsed(self, praxeum_spine):
        """Bond events are parsed when present."""
        if not praxeum_spine.bond_events:
            pytest.skip("Spine has no bond events")
        first = praxeum_spine.bond_events[0]
        assert first.id
        assert first.title
        assert first.cohort_member
        assert 1 <= first.act_window[0] <= first.act_window[1] <= praxeum_spine.total_acts
        assert 0.0 <= first.bond_weight <= 1.0
        assert len(first.keywords) >= 1
        assert len(first.hook) >= 20

    def test_bond_event_ids_unique(self, praxeum_spine):
        """Bond event ids are unique within the spine."""
        ids = [be.id for be in praxeum_spine.bond_events]
        assert len(ids) == len(set(ids)), "Duplicate bond event ids"

    def test_bond_event_cohort_members_in_roster(self, praxeum_spine):
        """Every bond event references an NPC in the roster."""
        roster_names = {npc.name for npc in praxeum_spine.npc_roster}
        for be in praxeum_spine.bond_events:
            assert be.cohort_member in roster_names, (
                f"Bond event {be.id} references unknown NPC {be.cohort_member!r}"
            )

    def test_bond_event_prerequisites_resolve(self, praxeum_spine):
        """Every prerequisite id refers to another bond event in the spine."""
        all_ids = {be.id for be in praxeum_spine.bond_events}
        for be in praxeum_spine.bond_events:
            for prereq in be.prerequisites:
                assert prereq in all_ids, (
                    f"Bond event {be.id} prerequisite {prereq!r} not found"
                )

    def test_bond_event_act_windows_valid(self, praxeum_spine):
        """All act_windows fall within the campaign's act range."""
        for be in praxeum_spine.bond_events:
            start, end = be.act_window
            assert 1 <= start <= end <= praxeum_spine.total_acts, (
                f"Bond event {be.id} has invalid act_window {be.act_window}"
            )

    def test_bond_event_max_weight_per_npc_capped(self, praxeum_spine):
        """No single character's bond events sum above the system cap."""
        if not praxeum_spine.bond_event_system:
            pytest.skip("Spine has no bond_event_system")
        cap = praxeum_spine.bond_event_system.max_bond_weight_per_relationship
        totals: dict[str, float] = {}
        for be in praxeum_spine.bond_events:
            totals[be.cohort_member] = totals.get(be.cohort_member, 0.0) + be.bond_weight
        for member, total in totals.items():
            assert total <= cap + 0.01, (  # tolerance for floating point
                f"{member} bond_weight total {total} exceeds cap {cap}"
            )

    def test_bond_event_system_threshold_reasonable(self, praxeum_spine):
        """Climax-protection threshold is between 0 and the per-character cap."""
        if not praxeum_spine.bond_event_system:
            pytest.skip("Spine has no bond_event_system")
        sys = praxeum_spine.bond_event_system
        assert 0.0 < sys.bond_weight_threshold_for_climax_protection <= sys.max_bond_weight_per_relationship


class TestSocialRpgPartyStructure:
    """Core party and bond-pacing data for the Clovis route."""

    def test_core_party_prioritizes_clovis_joran_and_rann(self, praxeum_spine):
        """The intended route has a small, explicit party focus."""
        assert praxeum_spine.intended_protagonist_id == "clovis_beryl"
        names = [member.name for member in praxeum_spine.core_party]
        assert names[0] == "Clovis Beryl"
        assert {
            "Joran Veska",
            "Rann Veska",
            "Tarsh Voll",
            "Brann Riako",
            "Cassen Vell",
            "Inya Vorn",
            "Lirah Tann",
        }.issubset(names)

        highest_priority = {
            member.name for member in praxeum_spine.core_party
            if member.bond_priority == 1
        }
        assert {"Clovis Beryl", "Joran Veska", "Rann Veska"}.issubset(
            highest_priority
        )
        assert all(member.table_function for member in praxeum_spine.core_party)

    def test_core_party_dossiers_are_complete(self, praxeum_spine):
        """Core party members should have compact GM-facing handles."""
        variants = [
            variant
            for allegiance in praxeum_spine.allegiances
            for variant in allegiance.character_variants
        ]
        clovis = next(variant for variant in variants if variant.id == "clovis_beryl")
        required_fields = (
            "rpg_function",
            "act1_player_feel",
            "utility",
            "best_case_ending_payoff",
            "worst_case_ending_payoff",
            "avoid",
        )

        assert clovis.party_dossier is not None
        for field in required_fields:
            assert getattr(clovis.party_dossier, field)
        assert set(clovis.party_dossier.social_bond_arc) == {
            "act1", "act2", "act3", "act4", "act5"
        }

        core_npcs = {
            "Joran Veska",
            "Rann Veska",
            "Tarsh Voll",
            "Brann Riako",
            "Cassen Vell",
            "Inya Vorn",
            "Lirah Tann",
        }
        by_name = {npc.name: npc for npc in praxeum_spine.npc_roster}
        for name in core_npcs:
            dossier = by_name[name].party_dossier
            assert dossier is not None, name
            for field in required_fields:
                assert getattr(dossier, field), name
            assert set(dossier.social_bond_arc) == {
                "act1", "act2", "act3", "act4", "act5"
            }

    def test_bond_act_plan_covers_every_act_with_limited_slots(self, praxeum_spine):
        """Bond pacing should support slower play without sprawling."""
        by_act = {plan.act: plan for plan in praxeum_spine.bond_act_plan}
        assert set(by_act) == set(range(1, praxeum_spine.total_acts + 1))
        assert [by_act[act].slots for act in range(1, 6)] == [2, 3, 2, 2, 1]
        assert "No new social arcs" in by_act[5].pacing_note

    def test_expected_turn_ranges_leave_room_for_social_play(self, praxeum_spine):
        """The campaign should breathe early and focus at the end."""
        ranges = [tuple(act.expected_turns) for act in praxeum_spine.acts]
        assert ranges == [(24, 32), (22, 30), (18, 24), (22, 28), (16, 22)]
        assert sum(low for low, _ in ranges) >= 100
        assert sum(high for _, high in ranges) <= 140

    def test_legends_era_voice_keeps_16_aby_constraints(
        self, praxeum_data, praxeum_spine
    ):
        """The 16 ABY pass should avoid anachronistic or overbroad anchors."""
        raw = json.dumps(praxeum_data)
        assert "six-year" not in raw
        assert "six years" not in raw
        assert "Sadow holocron" not in raw

        voice = praxeum_spine.era_voice
        assert voice is not None
        assert voice.year == "16 ABY"
        assert "five years old" in voice.voice_notes
        assert "three years from treaty peace" in voice.voice_notes
        assert any("not yet Mara Skywalker" in note for note in voice.period_details)

        npcs = {npc.name: npc for npc in praxeum_spine.npc_roster}
        assert "Sadow-line holocron fragment" in npcs["Vornn"].role
        assert any(
            "quarantined Old Sith Wars crate" in known
            for known in npcs["Luke Skywalker"].knows_at_start
        )
        assert not any(
            "sealed crate contains" in unknown
            for unknown in npcs["Luke Skywalker"].doesnt_know_at_start
        )
        assert "Mara Skywalker" in npcs["Mara Jade"].era_specific_notes
        assert "part of Luke's wider academy circle" in npcs["Kyle Katarn"].role

    def test_group_scene_references_resolve(self, praxeum_spine):
        """Group scenes should reference real scene ids and bond payoffs."""
        scene_ids = {scene.id for scene in praxeum_spine.group_scenes}
        bond_ids = {event.id for event in praxeum_spine.bond_events}

        for plan in praxeum_spine.bond_act_plan:
            for scene_id in plan.group_scene_ids:
                assert scene_id in scene_ids

        for scene in praxeum_spine.group_scenes:
            for payoff_id in scene.bond_payoffs:
                assert payoff_id in bond_ids

    def test_act_one_scene_beats_have_rpg_functions(self, praxeum_spine):
        """Act 1 should read as playable scenes, not loose notes."""
        act_one = praxeum_spine.acts[0]
        assert len(act_one.side_content) >= 12
        for beat in act_one.side_content:
            assert beat.phase
            assert beat.scene_type
            assert beat.rpg_function
            assert beat.player_choice
            assert beat.payoff_or_change

    def test_bonds_answer_why_now_and_what_changes(self, praxeum_spine):
        """Bond events should be purposeful, not nice-conversation filler."""
        assert praxeum_spine.bond_events
        for event in praxeum_spine.bond_events:
            assert event.choice_prompt
            assert event.why_this_person
            assert event.why_now
            assert event.changes_after

    def test_bond_pacing_matrix_classifies_every_event_once(self, praxeum_spine):
        """Large bond library should be curated through offer priorities."""
        matrix = praxeum_spine.bond_pacing_matrix
        assert matrix is not None
        assert matrix.recommended_playthrough_target == [12, 16]
        assert matrix.hard_cut_ids == []

        all_bond_ids = {event.id for event in praxeum_spine.bond_events}
        classified: list[str] = []
        for plan in matrix.act_plans:
            assert 0 <= plan.max_one_on_one_offers <= 3
            assert plan.guidance
            classified.extend(plan.required_story)
            classified.extend(plan.priority_pool)
            classified.extend(plan.optional_pool)
            classified.extend(plan.rare_pool)

        assert set(classified) == all_bond_ids
        assert len(classified) == len(set(classified))

    def test_bond_pacing_matrix_has_manageable_default_surface(self, praxeum_spine):
        """Required plus priority offers should stay below completionist scale."""
        matrix = praxeum_spine.bond_pacing_matrix
        assert matrix is not None

        default_surface = 0
        rare_surface = 0
        for plan in matrix.act_plans:
            default_surface += len(plan.required_story) + len(plan.priority_pool)
            rare_surface += len(plan.rare_pool)

        assert default_surface <= 26
        assert rare_surface >= 6

    def test_ending_payoff_matrix_closes_and_hooks(self, praxeum_spine):
        """Each ending should close emotionally while preserving future hooks."""
        endings = {ending.id: ending for ending in praxeum_spine.ending_payoff_matrix}
        assert set(endings) == {
            "ending_open_door",
            "ending_long_road",
            "ending_law",
            "ending_third_path",
            "ending_what_remains",
        }
        for ending in endings.values():
            assert ending.emotional_contract
            assert ending.future_hook
            assert ending.avoid_feeling
            assert {"Joran Veska", "Rann Veska", "Tarsh Voll", "Brann Riako"}.issubset(
                ending.relationship_payoffs
            )


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
        assert len(report.difficulty_curve.per_act) == nar_shaddaa_spine.total_acts
        assert report.difficulty_curve.curve_shape in (
            "ascending", "descending", "flat", "arc", "inverted_arc"
        )

    def test_difficulty_curve_standalone(self, nar_shaddaa_spine):
        """Difficulty curve can be computed independently."""
        curve = compute_difficulty_curve(nar_shaddaa_spine)
        assert len(curve.per_act) == nar_shaddaa_spine.total_acts
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
        actual = len(data["acts"])
        bogus = actual + 1  # one more than the actual count
        data["total_acts"] = bogus
        spine = CampaignSpine(**data)
        report = validate_spine(spine)
        assert not report.passed
        errors = [e for e in report.errors if e.code == "act_count_mismatch"]
        assert len(errors) == 1
        assert str(bogus) in errors[0].message

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
        # Pick the first NPC that doesn't already have canon_voice and flag it.
        target = next(
            i for i, n in enumerate(data["npc_roster"])
            if not n.get("canon_voice")
        )
        data["npc_roster"][target]["canon"] = True
        data["npc_roster"][target].pop("canon_voice", None)
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
        # Force a clearly large shift on the first NPC's act-2 state with
        # bland role text so no transition language masks the shift.
        npc = data["npc_roster"][0]
        npc["disposition_start"] = 0.8
        npc["per_act_state"][1]["disposition_expected"] = 0.05
        npc["per_act_state"][1]["role_in_act"] = "Neutral observer"
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
        # Reset every NPC's relationships, then wire each NPC to a positive
        # relationship with the next one. Yields N positive edges, zero negative.
        roster = data["npc_roster"]
        names = [n["name"] for n in roster]
        for i, npc in enumerate(roster):
            target = names[(i + 1) % len(names)]
            npc["npc_relationships"] = [
                {"npc": target, "nature": "ally", "weight": 0.7},
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
