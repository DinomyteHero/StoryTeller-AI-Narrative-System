"""
Spine-derived world tables — NPC location domains and act location
vocabulary flow from the campaign spine into the runtime, replacing
canonical-campaign-only hardcoded tables.

Covers:
1. Schema — NPC.location_domains and Act.location_vocabulary fields
2. Derivation — npc_location_domains() from the roster
3. Domain table resolution — spine-authored first, hardcoded fallback
   for the canonical campaign, permissive for unauthored new campaigns
4. Eligibility filtering with a derived table
5. Location vocabulary + text matching from per-act authored locations
6. Scene-location inference for non-canonical campaigns
7. End-to-end through _apply_narration_scene_state with a new campaign
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from engine.world_registry import (
    location_vocabulary,
    match_location_from_text,
    npc_location_domains,
)
from gm.context import NPCState


# ── Fixtures ──────────────────────────────────────────────────────────

NEW_SPINE = {
    "name": "Echoes of Tion",
    "acts": [
        {
            "number": 1,
            "name": "Landfall",
            "opening_location": "Veshok orbital ring, customs deck",
            "location_vocabulary": [
                "the meditation hall",
                "Veshok undercity market",
            ],
        },
    ],
    "npc_roster": [
        {"name": "Dock Boss Reel", "location_domains": ["customs", "orbital"]},
        {"name": "Mira Senn"},
        {"name": "The Broker", "location_domains": ["*"]},
    ],
}

CANONICAL_SPINE = {
    "name": "Shadows of the Custodian",
    "acts": [],
    "npc_roster": [
        {"name": "New Authored NPC", "location_domains": ["praxeum"]},
    ],
}


def _act(spine=NEW_SPINE):
    return spine["acts"][0]


# ── 1. Schema fields ─────────────────────────────────────────────────

class TestSchemaFields:
    def _minimal_npc(self, **overrides):
        from studio.schema import NPC, NPCActState
        defaults = dict(
            name="Dock Boss Reel",
            role="fixer",
            disposition_start=0.4,
            disposition_trajectory="warms if paid on time",
            motivation="keep the docks quiet and profitable",
            voice_notes="short sentences, dockside slang",
            behavioral_envelope=["transactional"],
            knows_at_start=[],
            doesnt_know_at_start=[],
            per_act_state=[NPCActState(
                act=1, role_in_act="gatekeeper", disposition_expected=0.4,
            )],
        )
        defaults.update(overrides)
        return NPC(**defaults)

    def test_npc_accepts_location_domains(self):
        npc = self._minimal_npc(location_domains=["customs", "orbital"])
        assert npc.location_domains == ["customs", "orbital"]

    def test_npc_location_domains_defaults_empty(self):
        assert self._minimal_npc().location_domains == []

    def test_act_accepts_location_vocabulary(self):
        from studio.schema import Act
        act = Act(
            number=1,
            name="Landfall",
            tension="rising",
            opening_situation="The customs deck is jammed with refugees.",
            opening_location="Veshok orbital ring, customs deck",
            galactic_context="The Tion fringe tightens under new tariffs.",
            anchor="clear_customs",
            location_vocabulary=["the meditation hall"],
        )
        assert act.location_vocabulary == ["the meditation hall"]

    def test_act_location_vocabulary_defaults_empty(self):
        from studio.schema import Act
        act = Act(
            number=1,
            name="Landfall",
            tension="rising",
            opening_situation="The customs deck is jammed with refugees.",
            opening_location="Veshok orbital ring, customs deck",
            galactic_context="The Tion fringe tightens under new tariffs.",
            anchor="clear_customs",
        )
        assert act.location_vocabulary == []


# ── 2. Derivation from roster ────────────────────────────────────────

class TestNpcLocationDomains:
    def test_derives_authored_domains(self):
        domains = npc_location_domains(NEW_SPINE)
        assert domains["dock boss reel"] == frozenset({"customs", "orbital"})
        assert domains["the broker"] == frozenset({"*"})

    def test_unauthored_npc_absent(self):
        domains = npc_location_domains(NEW_SPINE)
        assert "mira senn" not in domains

    def test_empty_spine_yields_empty(self):
        assert npc_location_domains(None) == {}
        assert npc_location_domains({"npc_roster": []}) == {}


# ── 3. Domain table resolution ───────────────────────────────────────

class TestDomainTableResolution:
    def test_no_spine_falls_back_to_hardcoded(self):
        from api.game_routes import _NPC_LOCATION_DOMAINS, _npc_domain_table_for_spine
        assert _npc_domain_table_for_spine(None) == _NPC_LOCATION_DOMAINS

    def test_canonical_campaign_keeps_hardcoded_and_overlays(self):
        from api.game_routes import _npc_domain_table_for_spine
        table = _npc_domain_table_for_spine(CANONICAL_SPINE)
        assert "vornn" in table                       # hardcoded entry survives
        assert table["new authored npc"] == frozenset({"praxeum"})

    def test_new_campaign_uses_only_spine_data(self):
        from api.game_routes import _npc_domain_table_for_spine
        table = _npc_domain_table_for_spine(NEW_SPINE)
        assert "vornn" not in table                   # canonical table not leaked
        assert table["dock boss reel"] == frozenset({"customs", "orbital"})

    def test_unauthored_new_campaign_is_permissive(self):
        from api.game_routes import _npc_domain_table_for_spine
        assert _npc_domain_table_for_spine(
            {"name": "Fresh Campaign", "npc_roster": [{"name": "Anyone"}]}
        ) == {}


# ── 4. Eligibility with a derived table ──────────────────────────────

class TestEligibilityFiltering:
    def test_constrained_npc_blocked_off_domain(self):
        from api.game_routes import _npc_domain_table_for_spine, _npc_location_eligible
        table = _npc_domain_table_for_spine(NEW_SPINE)
        assert not _npc_location_eligible(
            "Dock Boss Reel", "the meditation hall", table,
        )

    def test_constrained_npc_allowed_on_domain(self):
        from api.game_routes import _npc_domain_table_for_spine, _npc_location_eligible
        table = _npc_domain_table_for_spine(NEW_SPINE)
        assert _npc_location_eligible(
            "Dock Boss Reel", "Veshok orbital ring, customs deck", table,
        )

    def test_wildcard_and_unauthored_are_permissive(self):
        from api.game_routes import _npc_domain_table_for_spine, _npc_location_eligible
        table = _npc_domain_table_for_spine(NEW_SPINE)
        assert _npc_location_eligible("The Broker", "anywhere at all", table)
        assert _npc_location_eligible("Mira Senn", "anywhere at all", table)

    def test_filter_uses_derived_table(self):
        from api.game_routes import _filter_npcs_by_location, _npc_domain_table_for_spine
        table = _npc_domain_table_for_spine(NEW_SPINE)
        kept = _filter_npcs_by_location(
            ["Dock Boss Reel", "Mira Senn"], "the meditation hall", table,
        )
        assert kept == ["Mira Senn"]


# ── 5. Vocabulary + text matching ────────────────────────────────────

class TestActLocationVocabulary:
    def test_vocabulary_includes_per_act_entries(self):
        vocab = location_vocabulary(NEW_SPINE, {})
        assert "meditation" in vocab
        assert "undercity" in vocab
        assert "veshok" in vocab          # from opening_location too

    def test_match_finds_authored_location_in_text(self):
        matched = match_location_from_text(
            "You cross into the meditation hall and kneel on cold stone.",
            NEW_SPINE, _act(),
        )
        assert matched == "the meditation hall"

    def test_match_prefers_most_specific(self):
        matched = match_location_from_text(
            "From the meditation hall you descend toward the Veshok "
            "undercity market and its noise.",
            NEW_SPINE, _act(),
        )
        assert matched == "Veshok undercity market"   # 3 tokens beats 2

    def test_no_match_returns_empty(self):
        assert match_location_from_text(
            "A quiet stretch of empty corridor.", NEW_SPINE, _act(),
        ) == ""


# ── 6. Scene-location inference for new campaigns ────────────────────

class TestSceneLocationInference:
    def test_infers_from_spine_vocabulary(self):
        from api.game_routes import _infer_scene_location
        location = _infer_scene_location(
            "You push through the crowd into the Veshok undercity market.",
            "Veshok orbital ring, customs deck",
            _act(),
            spine=NEW_SPINE,
        )
        assert location == "Veshok undercity market"

    def test_falls_back_to_previous_when_nothing_matches(self):
        from api.game_routes import _infer_scene_location
        location = _infer_scene_location(
            "You wait. Nothing changes.",
            "Veshok orbital ring, customs deck",
            _act(),
            spine=NEW_SPINE,
        )
        assert location == "Veshok orbital ring, customs deck"


# ── 7. End-to-end through the scene-state gate ───────────────────────

class TestNewCampaignScenePatchGate:
    def _apply(self, state_patch, passage):
        from api.game_routes import _apply_narration_scene_state
        from gm.cloud_gm import NarrationResult
        arc_state = {"current_location": "Veshok orbital ring, customs deck"}
        nr = NarrationResult(
            passage=passage,
            choices=["Go on", "Hold back"],
            skill_tags=[None, None],
            state_patch=state_patch,
        )
        npc_states = [
            NPCState(name="Dock Boss Reel", disposition=0.4),
            NPCState(name="Mira Senn", disposition=0.6),
        ]
        _apply_narration_scene_state(
            arc_state=arc_state,
            current_act=_act(),
            npc_states=npc_states,
            narration_result=nr,
            player_action="head for the meditation hall",
            scene_type="exploration",
            recent_turns=[],
            turn_number=4,
            spine=NEW_SPINE,
        )
        return arc_state

    def test_authored_location_accepted_and_domain_filter_applied(self):
        arc_state = self._apply(
            {
                "current_location": "the meditation hall",
                "present_npcs": ["Dock Boss Reel", "Mira Senn"],
            },
            "Mira Senn follows you into the meditation hall. The noise of "
            "the customs deck fades behind the stone.",
        )
        scene = arc_state["scene_state"]
        # Location authored in act vocabulary → accepted, recorded as canon.
        assert scene["current_location"] == "the meditation hall"
        ledger = arc_state["visited_locations"]
        assert ledger[0]["name"] == "the meditation hall"
        assert ledger[0]["source"] == "canon"
        # Dock Boss Reel is domain-bound to customs/orbital → filtered out.
        assert "Mira Senn" in scene["present_npcs"]
        assert "Dock Boss Reel" not in scene["present_npcs"]

    def test_invented_location_still_rejected_for_new_campaign(self):
        arc_state = self._apply(
            {"current_location": "the lost city of Atlantis"},
            "You stay where you are, watching the customs queue crawl.",
        )
        assert "atlantis" not in (
            arc_state["scene_state"]["current_location"].lower()
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
