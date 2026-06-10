"""
Studio enrichment generation tests — dramatic enrichment for GENERATED
campaigns (Jun 2026).

Covers the eight enrichment changes that move the canonical campaign's
hand-authored richness into the generation pipeline:

1. beat_roles per act (prompts + Gate 4b structural check)
2. side_content scene seeds per act (prompts + Gate 4 sparse warning)
3. foreshadow_registry authoring (architect + surfacing + Gate 4b)
4. ending_paths (architect + branch_id resolution + Gate 4b)
5. thematic_argument enforcement (prompts + Gate 2 warning)
6. milestone_beat_sheet surfacing (prompt block + placement sanity)
7. protagonist_contradiction testing (prompts + Gate 4b dimension)
8. NPC relationship conflict heuristics (Gate 3 anti-positivity skew)
"""

import copy
import json
from pathlib import Path

import pytest

from studio.schema import (
    CampaignSpine,
    EndingPath,
    ForeshadowLink,
    StoryArchitecture,
    VALID_BEAT_ROLES,
)
from studio.architect import generate_architecture, architecture_to_prompt_block
from studio.generate import _merge_architecture_into_spine
from studio.narrative_eval import (
    GATE_4A_DIMS,
    GATE_4B_DIMS,
    GATE_4C_DIMS,
    _check_cs6_structural,
    gate4_check,
)
from studio.validate import validate_spine


# ── Fixtures ──────────────────────────────────────────────────────────

CAMPAIGN_DIR = Path(__file__).parent.parent / "data" / "campaigns"
PROMPT_DIR = Path(__file__).parent.parent / "studio" / "prompts"


@pytest.fixture
def praxeum_data() -> dict:
    """Load the canonical campaign spine JSON (the quality bar)."""
    path = CAMPAIGN_DIR / "shadows_of_the_custodian.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def praxeum_spine(praxeum_data) -> CampaignSpine:
    return CampaignSpine(**praxeum_data)


def _spine_with(base_data: dict, **overrides) -> CampaignSpine:
    """Deep-copy the canonical spine data, apply overrides, parse."""
    data = copy.deepcopy(base_data)
    for key, val in overrides.items():
        data[key] = val
    return CampaignSpine(**data)


SAMPLE_ENDING_PATHS = [
    {
        "name": "The Open Door",
        "branch_id": "stand_with_cohort_defeat_vornn",
        "synopsis": "Clovis stands with the cohort and the Praxeum holds — at a cost nobody names aloud.",
        "thematic_payoff": "Loyalty grown into is loyalty chosen.",
        "carries_forward": True,
    },
    {
        "name": "The Long Road",
        "branch_id": "spare_vornn_at_close",
        "synopsis": "Vornn lives, and the question of what mercy costs follows the survivors off-world.",
        "thematic_payoff": "Mercy is a wager, not a verdict.",
        "carries_forward": False,
    },
]

SAMPLE_ARCHITECTURE = {
    "dramatic_premise": "A smuggler discovers her regular cargo run is funding a weapons program aimed at her home sector",
    "central_dramatic_question": "Can someone who has always looked away choose to see when seeing costs everything?",
    "story_promise": "Escalating moral compromise as comfort becomes complicity and every act has a price silence never did",
    "protagonist_pressure_type": "moral",
    "antagonistic_force": "The economic machinery of Hutt-controlled shipping lanes, where everyone profits from not asking",
    "thematic_throughline": "Whether comfort earned through willful ignorance is worth what it costs others",
    "ending_payoff_sketch": "A final choice that makes the throughline unavoidable without resolving it cleanly",
    "milestone_beat_sheet": {
        "concept_question": "What if the job that keeps you fed is the weapon aimed at home?",
        "first_plot_point": "The manifest names her childhood neighborhood as the target zone — she cannot un-read it.",
        "first_plot_point_act": 1,
        "midpoint": "She learns the buyers already know she has seen the manifest — running is no longer neutral.",
        "midpoint_act": 2,
        "second_plot_point": "The last shipment's routing code proves who built the pipeline — and it was her own contact.",
        "second_plot_point_act": 3,
    },
    "foreshadow_registry": [
        {
            "id": "wrong_manifest",
            "setup_act": 1,
            "setup_description": "A manifest line item billed as 'agricultural converters' weighs three times what it should.",
            "payoff_act": 3,
            "payoff_description": "The converters were focusing arrays — the weight discrepancy was the weapon all along.",
            "payoff_type": "revelation",
        },
        {
            "id": "broker_nervous_laugh",
            "setup_act": 1,
            "setup_description": "Doss laughs at the wrong moment every time the cargo's destination comes up.",
            "payoff_act": 2,
            "payoff_description": "Doss knew the destination from the start — the laugh was guilt, not nerves.",
            "payoff_type": "reversal",
        },
        {
            "id": "docking_fee_receipt",
            "setup_act": 2,
            "setup_description": "A docking fee receipt stamped with a Hutt clan seal nobody mentions.",
            "payoff_act": 4,
            "payoff_description": "The same seal marks the weapon facility's supply gate — the receipt was a map.",
            "payoff_type": "callback",
        },
        {
            "id": "home_sector_toast",
            "setup_act": 1,
            "setup_description": "Her crew toasts 'to never going home' on the first night.",
            "payoff_act": 4,
            "payoff_description": "Going home is exactly what the finale demands of her.",
            "payoff_type": "irony",
        },
        {
            "id": "spare_part_debt",
            "setup_act": 2,
            "setup_description": "She owes a dock mechanic for a converter coil and keeps deferring payment.",
            "payoff_act": 3,
            "payoff_description": "The mechanic calls in the debt at the worst moment — as the only one who can ground her ship.",
            "payoff_type": "callback",
        },
    ],
    "ending_paths": [
        {
            "name": "The Manifest Burns",
            "branch_id": "expose_pipeline",
            "synopsis": "She exposes the pipeline and loses the lanes that fed her.",
            "thematic_payoff": "Seeing obligates action, whatever it costs.",
            "carries_forward": True,
        },
        {
            "name": "The Quiet Route",
            "branch_id": "deliver_and_vanish",
            "synopsis": "She delivers, vanishes, and lives with what arrives at home.",
            "thematic_payoff": "Comfort bought with ignorance has a ledger.",
            "carries_forward": False,
        },
    ],
}


def _mock_eval_response(with_architecture: bool = True) -> str:
    """All-pass Gate 4 LLM response (CS-5 mock pattern)."""
    dims = list(GATE_4A_DIMS) + list(GATE_4C_DIMS)
    if with_architecture:
        dims += list(GATE_4B_DIMS)
    return json.dumps(
        {dim: {"pass": True, "detail": "OK"} for dim in dims}
    )


# ── Schema tests ──────────────────────────────────────────────────────


class TestEnrichmentSchema:
    """New/extended models validate; canonical spine still loads."""

    def test_ending_path_model_validates(self):
        ep = EndingPath(**SAMPLE_ENDING_PATHS[0])
        assert ep.branch_id == "stand_with_cohort_defeat_vornn"
        assert ep.carries_forward is True
        assert ep.thematic_payoff

    def test_ending_path_defaults(self):
        ep = EndingPath(name="Bare", branch_id="bare_branch")
        assert ep.synopsis == ""
        assert ep.thematic_payoff == ""
        assert ep.carries_forward is False

    def test_ending_path_requires_branch_id(self):
        with pytest.raises(Exception):
            EndingPath(name="No branch", branch_id="")

    def test_architecture_carries_enrichment_fields(self):
        arch = StoryArchitecture(**SAMPLE_ARCHITECTURE)
        assert arch.milestone_beat_sheet is not None
        assert len(arch.foreshadow_registry) == 5
        assert all(isinstance(l, ForeshadowLink) for l in arch.foreshadow_registry)
        assert len(arch.ending_paths) == 2
        assert arch.ending_paths[0].branch_id == "expose_pipeline"

    def test_architecture_enrichment_fields_optional(self):
        minimal = {
            k: v for k, v in SAMPLE_ARCHITECTURE.items()
            if k not in ("milestone_beat_sheet", "foreshadow_registry", "ending_paths")
        }
        arch = StoryArchitecture(**minimal)
        assert arch.foreshadow_registry == []
        assert arch.ending_paths == []
        assert arch.milestone_beat_sheet is None

    def test_valid_beat_roles_constant(self):
        assert len(VALID_BEAT_ROLES) == 15
        for role in ("setup", "inciting", "first_plot_point", "midpoint",
                     "pinch1", "pinch2", "second_plot_point", "climax",
                     "resolution", "aftermath"):
            assert role in VALID_BEAT_ROLES

    def test_canonical_campaign_still_loads(self, praxeum_data):
        """All schema additions are optional — the hand-enriched
        canonical campaign validates unchanged."""
        spine = CampaignSpine(**praxeum_data)
        assert spine.name == "Shadows of the Custodian"
        assert spine.story_architecture is not None
        # Canonical predates architecture-level enrichment fields —
        # they default to empty without breaking the parse.
        assert spine.story_architecture.ending_paths == []
        assert spine.story_architecture.foreshadow_registry == []
        assert len(spine.foreshadow_registry) >= 5

    def test_canonical_passes_full_validation(self, praxeum_spine):
        report = validate_spine(praxeum_spine)
        assert report.passed, [e.message for e in report.errors]


# ── Gate 3: relationship conflict heuristics (pure Python) ───────────


class TestRelationshipConflictHeuristics:
    """Anti-positivity-skew checks in the Gate 3 relationship gate."""

    def test_positive_skewed_roster_flagged(self, praxeum_data):
        data = copy.deepcopy(praxeum_data)
        names = [n["name"] for n in data["npc_roster"]]
        for i, npc in enumerate(data["npc_roster"]):
            npc["disposition_start"] = 0.7  # nobody starts antagonistic
            npc["npc_relationships"] = [{
                "npc": names[(i + 1) % len(names)],
                "nature": "ally",
                "weight": 0.8,
            }]
        spine = CampaignSpine(**data)
        report = validate_spine(spine)
        codes = {w.code for w in report.warnings}
        assert "insufficient_negative_relationships" in codes
        assert "no_antagonistic_npc" in codes

    def test_conflicted_roster_passes(self, praxeum_spine):
        """The canonical roster (2 negative relationships, multiple
        NPCs with disposition_start < 0.4) is not flagged."""
        report = validate_spine(praxeum_spine)
        codes = {w.code for w in report.warnings}
        assert "insufficient_negative_relationships" not in codes
        assert "no_antagonistic_npc" not in codes

    def test_single_negative_relationship_still_flagged(self, praxeum_data):
        data = copy.deepcopy(praxeum_data)
        names = [n["name"] for n in data["npc_roster"]]
        for i, npc in enumerate(data["npc_roster"]):
            npc["npc_relationships"] = []
        data["npc_roster"][0]["npc_relationships"] = [
            {"npc": names[1], "nature": "rival", "weight": -0.5},
        ]
        spine = CampaignSpine(**data)
        report = validate_spine(spine)
        codes = {w.code for w in report.warnings}
        assert "insufficient_negative_relationships" in codes

    def test_small_roster_not_flagged(self, praxeum_data):
        """Rosters under 4 NPCs skip the conflict heuristics."""
        data = copy.deepcopy(praxeum_data)
        kept = data["npc_roster"][:3]
        kept_names = {n["name"] for n in kept}
        for npc in kept:
            npc["disposition_start"] = 0.8
            npc["npc_relationships"] = [
                r for r in npc.get("npc_relationships", [])
                if r["npc"] in kept_names and r["weight"] > 0
            ]
            npc["per_act_state"] = npc["per_act_state"][:1]
        data["npc_roster"] = kept
        # Drop roster references the smaller cast no longer supports.
        data["variation_points"] = []
        data["bond_events"] = []
        data["group_scenes"] = []
        data["bond_act_plan"] = []
        data["bond_pacing_matrix"] = None
        data["core_party"] = []
        for act in data["acts"]:
            if act.get("time_skip_after"):
                for vig in act["time_skip_after"].get("vignette_library", []):
                    if vig.get("npc_focus") not in kept_names:
                        vig["npc_focus"] = None
        spine = CampaignSpine(**data)
        report = validate_spine(spine)
        codes = {w.code for w in report.warnings}
        assert "insufficient_negative_relationships" not in codes
        assert "no_antagonistic_npc" not in codes


# ── Gate 2: thematic_argument enforcement ─────────────────────────────


class TestThematicArgumentWarning:
    def test_major_npc_without_argument_warned(self, praxeum_data):
        data = copy.deepcopy(praxeum_data)
        data["npc_roster"][0]["thematic_argument"] = ""
        data["npc_roster"][1]["thematic_argument"] = "   "
        spine = CampaignSpine(**data)
        report = validate_spine(spine)
        warns = [w for w in report.warnings
                 if w.code == "npc_missing_thematic_argument"]
        assert len(warns) == 2
        assert data["npc_roster"][0]["name"] in warns[0].message

    def test_canonical_npcs_all_argued(self, praxeum_spine):
        report = validate_spine(praxeum_spine)
        warns = [w for w in report.warnings
                 if w.code == "npc_missing_thematic_argument"]
        assert warns == []

    def test_minor_npc_not_warned(self, praxeum_data):
        """An NPC present in a single act is not 'major' — no warning."""
        data = copy.deepcopy(praxeum_data)
        npc = data["npc_roster"][0]
        npc["thematic_argument"] = ""
        npc["per_act_state"] = npc["per_act_state"][:1]
        spine = CampaignSpine(**data)
        report = validate_spine(spine)
        warns = [w for w in report.warnings
                 if w.code == "npc_missing_thematic_argument"
                 and npc["name"] in w.message]
        assert warns == []


# ── Gate 4b structural: beat roles ────────────────────────────────────


class TestBeatRolesCheck:
    def test_empty_beat_roles_flagged_on_enriched_spine(self, praxeum_data):
        data = copy.deepcopy(praxeum_data)
        data["acts"][1]["beat_roles"] = []
        spine = CampaignSpine(**data)
        warnings = _check_cs6_structural(spine)
        missing = [w for w in warnings if w["code"] == "cs6_beat_roles_missing"]
        assert len(missing) == 1
        assert "Act 2" in missing[0]["message"]

    def test_unknown_beat_role_flagged(self, praxeum_data):
        data = copy.deepcopy(praxeum_data)
        data["acts"][0]["beat_roles"] = ["setup", "the_vibes"]
        spine = CampaignSpine(**data)
        warnings = _check_cs6_structural(spine)
        unknown = [w for w in warnings if w["code"] == "cs6_beat_role_unknown"]
        assert len(unknown) == 1
        assert "the_vibes" in unknown[0]["message"]

    def test_canonical_beat_roles_clean(self, praxeum_spine):
        warnings = _check_cs6_structural(praxeum_spine)
        assert [w for w in warnings if "beat_role" in w["code"]] == []

    def test_legacy_spine_without_enrichment_skipped(self, praxeum_data):
        """No architecture beat sheet, no generation metadata, no beat
        roles anywhere — the check stays silent for legacy spines."""
        data = copy.deepcopy(praxeum_data)
        data["story_architecture"].pop("milestone_beat_sheet", None)
        data["generation_metadata"] = None
        for act in data["acts"]:
            act["beat_roles"] = []
        spine = CampaignSpine(**data)
        warnings = _check_cs6_structural(spine)
        assert [w for w in warnings if w["code"] == "cs6_beat_roles_missing"] == []


# ── Gate 4 structural: side content ───────────────────────────────────


class TestSideContentCheck:
    def test_sparse_side_content_warned(self, praxeum_data):
        data = copy.deepcopy(praxeum_data)
        data["acts"][0]["side_content"] = data["acts"][0]["side_content"][:2]
        spine = CampaignSpine(**data)
        warnings = _check_cs6_structural(spine)
        sparse = [w for w in warnings if w["code"] == "cs6_side_content_sparse"]
        assert len(sparse) == 1
        assert "Act 1" in sparse[0]["message"]

    def test_canonical_side_content_clean(self, praxeum_spine):
        warnings = _check_cs6_structural(praxeum_spine)
        assert [w for w in warnings if w["code"] == "cs6_side_content_sparse"] == []


# ── Gate 4b structural: foreshadow registry density ───────────────────


class TestForeshadowDensityCheck:
    def test_sparse_registry_warned(self, praxeum_data):
        data = copy.deepcopy(praxeum_data)
        data["foreshadow_registry"] = data["foreshadow_registry"][:2]
        spine = CampaignSpine(**data)
        warnings = _check_cs6_structural(spine)
        sparse = [w for w in warnings
                  if w["code"] == "cs6_foreshadow_registry_sparse"]
        assert len(sparse) == 1

    def test_monotonic_payoff_types_warned(self, praxeum_data):
        data = copy.deepcopy(praxeum_data)
        links = copy.deepcopy(data["foreshadow_registry"][:3])
        for link in links:
            link["payoff_type"] = "callback"
        data["foreshadow_registry"] = links
        spine = CampaignSpine(**data)
        warnings = _check_cs6_structural(spine)
        mono = [w for w in warnings
                if w["code"] == "cs6_foreshadow_payoff_monotonic"]
        assert len(mono) == 1

    def test_canonical_registry_clean(self, praxeum_spine):
        warnings = _check_cs6_structural(praxeum_spine)
        assert [w for w in warnings if w["code"] in (
            "cs6_foreshadow_registry_sparse",
            "cs6_foreshadow_payoff_monotonic",
        )] == []

    def test_architecture_registry_used_when_spine_empty(self, praxeum_data):
        """Pairs authored on the architecture count when the spine-level
        registry was dropped by the generation model."""
        data = copy.deepcopy(praxeum_data)
        data["foreshadow_registry"] = []
        data["story_architecture"]["foreshadow_registry"] = (
            SAMPLE_ARCHITECTURE["foreshadow_registry"]
        )
        spine = CampaignSpine(**data)
        warnings = _check_cs6_structural(spine)
        assert [w for w in warnings if w["code"] in (
            "cs6_foreshadow_registry_sparse",
            "cs6_foreshadow_payoff_monotonic",
        )] == []


# ── Gate 4b structural: ending paths ──────────────────────────────────


class TestEndingPathsCheck:
    def test_valid_ending_paths_pass(self, praxeum_data):
        data = copy.deepcopy(praxeum_data)
        data["story_architecture"]["ending_paths"] = SAMPLE_ENDING_PATHS
        spine = CampaignSpine(**data)
        warnings = _check_cs6_structural(spine)
        assert [w for w in warnings if "ending_path" in w["code"]] == []

    def test_dangling_branch_id_flagged(self, praxeum_data):
        data = copy.deepcopy(praxeum_data)
        paths = copy.deepcopy(SAMPLE_ENDING_PATHS)
        paths[1]["branch_id"] = "option_that_does_not_exist"
        data["story_architecture"]["ending_paths"] = paths
        spine = CampaignSpine(**data)
        warnings = _check_cs6_structural(spine)
        dangling = [w for w in warnings
                    if w["code"] == "cs6_ending_path_dangling_branch"]
        assert len(dangling) == 1
        assert "option_that_does_not_exist" in dangling[0]["message"]

    def test_fewer_than_two_endings_flagged(self, praxeum_data):
        data = copy.deepcopy(praxeum_data)
        data["story_architecture"]["ending_paths"] = SAMPLE_ENDING_PATHS[:1]
        spine = CampaignSpine(**data)
        warnings = _check_cs6_structural(spine)
        sparse = [w for w in warnings
                  if w["code"] == "cs6_ending_paths_sparse"]
        assert len(sparse) == 1

    def test_generated_spine_without_endings_flagged(self, praxeum_data):
        data = copy.deepcopy(praxeum_data)
        data["generation_metadata"] = {
            "master_seed": 42,
            "generation_mode": "mode1",
        }
        spine = CampaignSpine(**data)
        warnings = _check_cs6_structural(spine)
        sparse = [w for w in warnings
                  if w["code"] == "cs6_ending_paths_sparse"]
        assert len(sparse) == 1

    def test_hand_authored_spine_without_endings_skipped(self, praxeum_spine):
        """The canonical spine encodes endings in ending_payoff_matrix;
        absence of architecture ending_paths is not flagged."""
        warnings = _check_cs6_structural(praxeum_spine)
        assert [w for w in warnings if "ending_path" in w["code"]] == []


# ── Gate 4b structural: milestone placement sanity ────────────────────


class TestMilestonePlacementSanity:
    def test_late_first_plot_point_flagged(self, praxeum_data):
        data = copy.deepcopy(praxeum_data)
        mbs = data["story_architecture"]["milestone_beat_sheet"]
        mbs["first_plot_point_act"] = 3  # 60% of 5 acts — past the 40% line
        spine = CampaignSpine(**data)
        warnings = _check_cs6_structural(spine)
        placement = [w for w in warnings
                     if w["code"] == "cs6_milestone_placement"
                     and "First Plot Point" in w["message"]]
        assert len(placement) == 1

    def test_canonical_milestones_sane(self, praxeum_spine):
        """FPP act 1/5 (20%), midpoint 3/5 (60%), SPP 4/5 (80%) — all
        inside the sane windows; zero structural warnings overall."""
        warnings = _check_cs6_structural(praxeum_spine)
        assert warnings == []


# ── Prompt contract tests ─────────────────────────────────────────────


class TestPromptContracts:
    """Generation prompts carry the enrichment instructions verbatim."""

    def _read(self, name: str) -> str:
        return (PROMPT_DIR / name).read_text(encoding="utf-8")

    @pytest.mark.parametrize("prompt_file", [
        "mode1_generate.txt", "mode2_generate.txt",
    ])
    def test_mode_prompts_carry_enrichment_instructions(self, prompt_file):
        text = self._read(prompt_file)
        assert "beat_roles" in text
        assert "side_content" in text
        assert "thematic_argument" in text
        assert "antagonistic" in text
        assert "ending" in text
        assert "foreshadow_registry" in text
        assert "protagonist_contradiction" in text
        # The full 15-role vocabulary is spelled out
        for role in ("false_progress", "first_plot_point", "pinch1",
                     "second_plot_point", "aftermath"):
            assert role in text
        # Side content volume and hook contract
        assert "6 to 12" in text
        assert "20 characters" in text
        # Endings connect to variation points
        assert "branch_id" in text
        assert "variation_point" in text
        # Conflict requirements
        assert "negative-weight" in text

    def test_mode_prompts_demand_competing_arguments(self):
        for prompt_file in ("mode1_generate.txt", "mode2_generate.txt"):
            text = self._read(prompt_file)
            assert "EVERY major NPC" in text
            assert "competing answers" in text

    def test_mode_prompts_test_contradiction_with_example(self):
        for prompt_file in ("mode1_generate.txt", "mode2_generate.txt"):
            text = self._read(prompt_file)
            assert "Act 2 or later" in text
            assert "Example:" in text

    def test_mode_prompts_align_anchors_with_milestones(self):
        for prompt_file in ("mode1_generate.txt", "mode2_generate.txt"):
            text = self._read(prompt_file)
            assert "milestone beat sheet" in text
            assert "point of no return" in text

    def test_architect_prompt_authors_foreshadow_and_endings(self):
        text = self._read("architect.txt")
        assert "FORESHADOW REGISTRY" in text
        assert "at least 5" in text
        assert "ENDING PATHS" in text
        assert "2-4 distinct endings" in text
        assert "branch_id" in text
        assert "carries_forward" in text
        assert "milestone_beat_sheet" in text
        for payoff_type in ("revelation", "reversal", "callback", "irony"):
            assert payoff_type in text


# ── Architect surfacing tests ─────────────────────────────────────────


class TestArchitectSurfacing:
    def test_prompt_block_includes_milestones(self):
        arch = StoryArchitecture(**SAMPLE_ARCHITECTURE)
        block = architecture_to_prompt_block(arch)
        assert "Milestone beat sheet" in block
        assert "First Plot Point (act 1)" in block
        assert "Midpoint (act 2)" in block
        assert "Second Plot Point (act 3)" in block
        assert "point of no return" in block

    def test_prompt_block_includes_foreshadow_pairs(self):
        arch = StoryArchitecture(**SAMPLE_ARCHITECTURE)
        block = architecture_to_prompt_block(arch)
        assert "Planned foreshadowing" in block
        assert "[wrong_manifest]" in block
        assert "foreshadow_registry" in block

    def test_prompt_block_includes_ending_paths(self):
        arch = StoryArchitecture(**SAMPLE_ARCHITECTURE)
        block = architecture_to_prompt_block(arch)
        assert "Ending paths" in block
        assert "expose_pipeline" in block
        assert "The Manifest Burns" in block

    def test_prompt_block_requirements_cover_enrichment(self):
        arch = StoryArchitecture(**SAMPLE_ARCHITECTURE)
        block = architecture_to_prompt_block(arch)
        assert "beat_roles" in block
        assert "side_content" in block
        assert "thematic_argument" in block
        assert "antagonistic" in block
        assert "protagonist_contradiction" in block

    def test_prompt_block_omits_absent_sections(self):
        minimal = {
            k: v for k, v in SAMPLE_ARCHITECTURE.items()
            if k not in ("milestone_beat_sheet", "foreshadow_registry", "ending_paths")
        }
        block = architecture_to_prompt_block(StoryArchitecture(**minimal))
        assert "Milestone beat sheet" not in block
        assert "Planned foreshadowing" not in block
        assert "Ending paths" not in block

    def test_generate_architecture_parses_enriched_output(self):
        arch = generate_architecture(
            era="galactic_civil_war",
            location="Nar Shaddaa",
            tone="gritty",
            master_seed=42,
            llm_call_fn=lambda *a, **kw: json.dumps(SAMPLE_ARCHITECTURE),
        )
        assert isinstance(arch, StoryArchitecture)
        assert len(arch.foreshadow_registry) == 5
        assert len(arch.ending_paths) == 2
        assert arch.milestone_beat_sheet is not None


# ── Generation merge tests ────────────────────────────────────────────


class TestArchitectureMerge:
    def test_attaches_when_spine_lacks_architecture(self):
        spine_data = {"name": "Test"}
        _merge_architecture_into_spine(spine_data, copy.deepcopy(SAMPLE_ARCHITECTURE))
        assert spine_data["story_architecture"]["dramatic_premise"]
        # Planned pairs surfaced to the spine-level registry
        assert len(spine_data["foreshadow_registry"]) == 5

    def test_backfills_planning_fields_only(self):
        spine_data = {
            "name": "Test",
            "story_architecture": {
                "dramatic_premise": "The generation model's own premise, kept as-is",
                "ending_paths": [SAMPLE_ENDING_PATHS[0]],
            },
        }
        _merge_architecture_into_spine(spine_data, copy.deepcopy(SAMPLE_ARCHITECTURE))
        sa = spine_data["story_architecture"]
        # Existing fields are not overwritten
        assert sa["dramatic_premise"].startswith("The generation model's")
        assert sa["ending_paths"] == [SAMPLE_ENDING_PATHS[0]]
        # Missing planning fields are backfilled from the architect
        assert sa["milestone_beat_sheet"]["first_plot_point_act"] == 1
        assert len(sa["foreshadow_registry"]) == 5
        assert len(spine_data["foreshadow_registry"]) == 5

    def test_existing_spine_registry_not_overwritten(self):
        existing_link = {
            "id": "model_authored",
            "setup_act": 1,
            "setup_description": "Already planted by the generation model.",
            "payoff_act": 2,
            "payoff_description": "Already paid off by the generation model.",
            "payoff_type": "callback",
        }
        spine_data = {"name": "Test", "foreshadow_registry": [existing_link]}
        _merge_architecture_into_spine(spine_data, copy.deepcopy(SAMPLE_ARCHITECTURE))
        assert spine_data["foreshadow_registry"] == [existing_link]

    def test_noop_without_architecture(self):
        spine_data = {"name": "Test"}
        _merge_architecture_into_spine(spine_data, None)
        assert "story_architecture" not in spine_data
        assert "foreshadow_registry" not in spine_data


# ── Gate 4 integration (mocked LLM) ───────────────────────────────────


class TestGate4Integration:
    def test_structural_warnings_surface_through_gate4_check(self, praxeum_data):
        """gate4_check (LLM dims mocked all-pass) still reports the new
        deterministic enrichment warnings."""
        data = copy.deepcopy(praxeum_data)
        data["acts"][2]["beat_roles"] = []
        data["acts"][2]["side_content"] = []
        data["story_architecture"]["ending_paths"] = [
            dict(SAMPLE_ENDING_PATHS[0], branch_id="dangling_branch"),
        ]
        spine = CampaignSpine(**data)

        errors, warnings = gate4_check(
            spine, llm_call_fn=lambda *a, **kw: _mock_eval_response(),
        )
        assert errors == []
        codes = {w["code"] for w in warnings}
        assert "cs6_beat_roles_missing" in codes
        assert "cs6_side_content_sparse" in codes
        assert "cs6_ending_paths_sparse" in codes
        assert "cs6_ending_path_dangling_branch" in codes

    def test_clean_canonical_spine_produces_no_enrichment_warnings(
        self, praxeum_spine,
    ):
        errors, warnings = gate4_check(
            praxeum_spine, llm_call_fn=lambda *a, **kw: _mock_eval_response(),
        )
        assert errors == []
        # The canonical spine carries one pre-existing arc-coherence
        # warning (a 53-char ghost) — assert only that NO enrichment
        # check fires against the hand-enriched quality bar.
        enrichment_codes = {
            "cs6_beat_roles_missing", "cs6_beat_role_unknown",
            "cs6_side_content_sparse", "cs6_foreshadow_registry_sparse",
            "cs6_foreshadow_payoff_monotonic", "cs6_ending_paths_sparse",
            "cs6_ending_path_dangling_branch",
        }
        assert {w["code"] for w in warnings} & enrichment_codes == set()

    def test_contradiction_testability_dimension_present(self):
        """Item 7: the Gate 4b rubric evaluates protagonist
        contradiction testing as its own dimension."""
        assert "contradiction_testability" in GATE_4B_DIMS
        assert "npc_thematic_diversity" in GATE_4B_DIMS
