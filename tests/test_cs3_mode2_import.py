"""
Campaign Studio Phase CS-3 tests — Mode 2 thematic steering + cross-era import.

Tests cover:
- Mode 2 ThematicBrief data class
- Cross-era import interface (apply_import, build_default_character)
- Specialization mappings (continuity, dormancy, evolution)
- XP rebalancing
- Motivation track transition
- Equipment transition
- Import and default character API routes
"""

import json
import copy
import pytest
from pathlib import Path

from studio.schema import CampaignSpine
from studio.generate import ThematicBrief
from studio.import_interface import (
    ImportPackage,
    ImportResult,
    apply_import,
    build_default_character,
)


# ── Fixtures ──────────────────────────────────────────────────────────

CAMPAIGN_DIR = Path(__file__).parent.parent / "data" / "campaigns"


@pytest.fixture
def nar_shaddaa_data() -> dict:
    path = CAMPAIGN_DIR / "shadows_of_the_praxeum.json"
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def nar_shaddaa_spine(nar_shaddaa_data) -> CampaignSpine:
    return CampaignSpine(**nar_shaddaa_data)


@pytest.fixture
def spine_with_import(nar_shaddaa_data) -> dict:
    """Spine data with an import_interface configured."""
    data = copy.deepcopy(nar_shaddaa_data)
    data["import_interface"] = {
        "compatible_campaigns": ["prior_campaign"],
        "specialization_mappings": [
            {"source_spec": "pilot", "mapping": "continuity"},
            {"source_spec": "thief", "mapping": "dormancy"},
            {"source_spec": "bounty_hunter", "mapping": "evolution", "target_spec": "scoundrel"},
        ],
        "motivation_transition": {"new_track": "obligation"},
        "target_xp_range": [100, 200],
        "transition_framing": "The character arrives at Nar Shaddaa seeking a new start.",
    }
    return data


@pytest.fixture
def basic_import_package() -> ImportPackage:
    """A basic import package from a completed campaign."""
    return ImportPackage(
        name="Keth Varso",
        species="bothan",
        career="smuggler",
        specializations=["pilot"],
        characteristics={
            "brawn": 2, "agility": 3, "intellect": 3,
            "cunning": 4, "willpower": 2, "presence": 3,
        },
        skills={
            "deception": 2, "piloting_space": 2, "streetwise": 1,
            "skulduggery": 1, "coordination": 1, "perception": 1,
        },
        wound_threshold=12,
        strain_threshold=12,
        soak=2,
        total_xp=110,
        available_xp=10,
        obligation_type="Debt",
        obligation_value=15,
        advancement_log=[
            {"type": "skill", "skill": "deception", "from": 1, "to": 2}
        ],
        npc_relationship_summaries={
            "Doss": "Unreliable middleman. Keth trusted him once and may again.",
        },
        voice_notes="Dry, observational. Dark humor as a defense mechanism.",
        loadout={
            "weapons": [{"name": "DL-44", "skill": "ranged_light", "damage_bonus": 7, "critical_rating": 3}],
        },
    )


# ── ThematicBrief Tests ───────────────────────────────────────────────


class TestThematicBrief:
    """Test the Mode 2 ThematicBrief data class."""

    def test_brief_creation(self):
        brief = ThematicBrief(
            era="galactic_civil_war",
            location="Nar Shaddaa",
            tone="gritty noir",
            throughline_question="What price is freedom?",
            campaign_concept="A smuggler on the run discovers the cargo is alive.",
        )
        assert brief.era == "galactic_civil_war"
        assert brief.total_acts == 4  # default
        assert brief.moral_register == "morally gray"  # default

    def test_brief_with_all_fields(self):
        brief = ThematicBrief(
            era="old_republic",
            location="Coruscant underlevels",
            tone="political thriller",
            throughline_question="Who defines justice when the law is corrupt?",
            campaign_concept="A Senate investigator uncovers a conspiracy.",
            moral_register="shifting",
            total_acts=3,
            constraints="No Jedi or Force users. No Senate floor scenes.",
        )
        assert brief.total_acts == 3
        assert brief.moral_register == "shifting"
        assert "No Jedi" in brief.constraints


# ── ImportPackage Tests ───────────────────────────────────────────────


class TestImportPackage:
    """Test ImportPackage creation and from_dict."""

    def test_from_dict(self):
        data = {
            "name": "Test Char",
            "species": "human",
            "career": "soldier",
            "specializations": ["commando"],
            "characteristics": {"brawn": 3, "agility": 2, "intellect": 2,
                                "cunning": 2, "willpower": 3, "presence": 2},
            "skills": {"ranged_heavy": 2},
            "wound_threshold": 14,
            "strain_threshold": 10,
            "soak": 3,
            "total_xp": 150,
            "available_xp": 20,
        }
        pkg = ImportPackage.from_dict(data)
        assert pkg.name == "Test Char"
        assert pkg.total_xp == 150
        assert pkg.force_rating == 0  # default

    def test_from_dict_with_extras(self):
        """Extra fields in dict are ignored."""
        data = {
            "name": "Test",
            "species": "twi'lek",
            "career": "spy",
            "specializations": ["infiltrator"],
            "characteristics": {"brawn": 1, "agility": 3, "intellect": 3,
                                "cunning": 4, "willpower": 2, "presence": 3},
            "skills": {},
            "wound_threshold": 10,
            "strain_threshold": 13,
            "soak": 1,
            "total_xp": 80,
            "available_xp": 0,
            "unknown_field": "should be ignored",
        }
        pkg = ImportPackage.from_dict(data)
        assert pkg.name == "Test"


# ── apply_import Tests ────────────────────────────────────────────────


class TestApplyImport:
    """Test cross-era character import."""

    def test_basic_import(self, spine_with_import, basic_import_package):
        spine = CampaignSpine(**spine_with_import)
        result = apply_import(basic_import_package, spine, "clovis_beryl")

        assert result.character_data["name"] == "Keth Varso"
        assert result.character_data["species"] == "bothan"
        assert "pilot" in result.character_data["specializations"]
        assert len(result.applied_mappings) > 0

    def test_specialization_continuity(self, spine_with_import, basic_import_package):
        """Pilot specialization mapped as continuity."""
        spine = CampaignSpine(**spine_with_import)
        result = apply_import(basic_import_package, spine, "clovis_beryl")

        assert "pilot" in result.character_data["specializations"]
        continuity_mappings = [m for m in result.applied_mappings if "continuity" in m]
        assert len(continuity_mappings) >= 1

    def test_specialization_evolution(self, spine_with_import):
        """Bounty_hunter specialization evolves to scoundrel."""
        pkg = ImportPackage(
            name="Hunter", species="human", career="bounty_hunter",
            specializations=["bounty_hunter"],
            characteristics={"brawn": 3, "agility": 3, "intellect": 2,
                             "cunning": 3, "willpower": 2, "presence": 2},
            skills={"ranged_heavy": 2},
            wound_threshold=14, strain_threshold=12, soak=3,
            total_xp=120, available_xp=0,
        )
        spine = CampaignSpine(**spine_with_import)
        result = apply_import(pkg, spine, "clovis_beryl")

        assert "scoundrel" in result.character_data["specializations"]
        evolution_mappings = [m for m in result.applied_mappings if "evolution" in m]
        assert len(evolution_mappings) >= 1

    def test_specialization_dormancy(self, spine_with_import):
        """Thief specialization becomes dormant."""
        pkg = ImportPackage(
            name="Thief", species="human", career="smuggler",
            specializations=["thief"],
            characteristics={"brawn": 2, "agility": 4, "intellect": 2,
                             "cunning": 3, "willpower": 2, "presence": 2},
            skills={"skulduggery": 2},
            wound_threshold=11, strain_threshold=13, soak=2,
            total_xp=100, available_xp=0,
        )
        spine = CampaignSpine(**spine_with_import)
        result = apply_import(pkg, spine, "clovis_beryl")

        dormancy_mappings = [m for m in result.applied_mappings if "dormancy" in m]
        assert len(dormancy_mappings) >= 1

    def test_xp_rebalancing_below_minimum(self, spine_with_import):
        """Characters below target_xp_range get bonus XP."""
        pkg = ImportPackage(
            name="Low XP", species="human", career="smuggler",
            specializations=["pilot"],
            characteristics={"brawn": 2, "agility": 3, "intellect": 2,
                             "cunning": 3, "willpower": 2, "presence": 2},
            skills={"piloting_space": 1},
            wound_threshold=11, strain_threshold=11, soak=2,
            total_xp=50, available_xp=0,  # Below minimum of 100
        )
        spine = CampaignSpine(**spine_with_import)
        result = apply_import(pkg, spine, "clovis_beryl")

        assert result.character_data["total_xp"] == 100  # Bumped to minimum
        assert result.xp_adjusted == 50  # 100 - 50 bonus
        assert result.character_data["available_xp"] >= 50

    def test_xp_above_maximum_preserved(self, spine_with_import):
        """Characters above target_xp_range keep their XP (never removed)."""
        pkg = ImportPackage(
            name="High XP", species="human", career="smuggler",
            specializations=["pilot"],
            characteristics={"brawn": 2, "agility": 3, "intellect": 2,
                             "cunning": 3, "willpower": 2, "presence": 2},
            skills={"piloting_space": 3},
            wound_threshold=11, strain_threshold=11, soak=2,
            total_xp=300, available_xp=20,  # Above maximum of 200
        )
        spine = CampaignSpine(**spine_with_import)
        result = apply_import(pkg, spine, "clovis_beryl")

        assert result.character_data["total_xp"] == 300  # Preserved
        assert len(result.warnings) >= 1  # Warning about being above max

    def test_motivation_transition(self, spine_with_import, basic_import_package):
        """Motivation track transitions correctly."""
        spine = CampaignSpine(**spine_with_import)
        result = apply_import(basic_import_package, spine, "clovis_beryl")

        assert result.character_data["motivation"]["track"] == "obligation"
        transition_mappings = [m for m in result.applied_mappings if "track" in m.lower()]
        assert len(transition_mappings) >= 1

    def test_narrative_state_carried_forward(self, spine_with_import, basic_import_package):
        """NPC relationships and voice notes carry forward."""
        spine = CampaignSpine(**spine_with_import)
        result = apply_import(basic_import_package, spine, "clovis_beryl")

        assert "Doss" in result.character_data["npc_relationship_summaries"]
        assert result.character_data["voice_notes"] != ""

    def test_no_import_interface_raises(self, nar_shaddaa_data, basic_import_package):
        """Raises ValueError when spine has no import_interface."""
        spine = CampaignSpine(**nar_shaddaa_data)
        with pytest.raises(ValueError, match="no import_interface"):
            apply_import(basic_import_package, spine, "clovis_beryl")

    def test_invalid_variant_raises(self, spine_with_import, basic_import_package):
        """Raises ValueError when variant_id doesn't exist."""
        spine = CampaignSpine(**spine_with_import)
        with pytest.raises(ValueError, match="not found"):
            apply_import(basic_import_package, spine, "nonexistent_variant")


# ── build_default_character Tests ─────────────────────────────────────


class TestBuildDefaultCharacter:
    """Test default character creation from variants."""

    def test_default_from_keth(self, nar_shaddaa_spine):
        """Build default character from the clovis_beryl variant."""
        char = build_default_character(nar_shaddaa_spine, "clovis_beryl")
        assert char["species"] == "human"
        assert char["career"] == "sentinel"
        assert char["primary_game_line"] == "force_and_destiny"
        assert char["force_sensitive"] is True
        assert char["force_rating"] == 1
        assert char["total_xp"] == 110
        assert char["characteristics"]["willpower"] == 3
        assert char["motivation"]["track"] == "morality"

    def test_default_from_renn(self, nar_shaddaa_spine):
        """Build default character from the tarsh_voll variant."""
        char = build_default_character(nar_shaddaa_spine, "tarsh_voll")
        assert char["species"] == "human"
        assert char["career"] == "sentinel"
        assert char["primary_game_line"] == "force_and_destiny"
        assert char["force_sensitive"] is True
        assert char["total_xp"] == 100
        assert char["characteristics"]["intellect"] == 3

    def test_default_has_loadout(self, nar_shaddaa_spine):
        """Default character includes starting loadout."""
        char = build_default_character(nar_shaddaa_spine, "clovis_beryl")
        assert "loadout" in char
        # Mystics may carry no weapons by default — check shape, not content.
        assert isinstance(char["loadout"], dict)

    def test_default_has_voice_notes(self, nar_shaddaa_spine):
        """Default character includes voice baseline."""
        char = build_default_character(nar_shaddaa_spine, "clovis_beryl")
        assert char["voice_notes"] != ""

    def test_invalid_variant_raises(self, nar_shaddaa_spine):
        """Raises ValueError for nonexistent variant."""
        with pytest.raises(ValueError, match="not found"):
            build_default_character(nar_shaddaa_spine, "nonexistent")

    def test_default_name_empty(self, nar_shaddaa_spine):
        """Default character has empty name (player sets it)."""
        char = build_default_character(nar_shaddaa_spine, "clovis_beryl")
        assert char["name"] == ""


# ── API Route Tests ───────────────────────────────────────────────────


class TestCS3Routes:
    """Test CS-3 API routes."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from api.main import app
        return TestClient(app)

    def test_import_default_route(self, client, nar_shaddaa_data):
        """POST /studio/import/default builds a default character."""
        resp = client.post("/studio/import/default", json={
            "spine_data": nar_shaddaa_data,
            "variant_id": "clovis_beryl",
        })
        assert resp.status_code == 200
        char = resp.json()["character_data"]
        assert char["species"] == "human"
        assert char["career"] == "sentinel"

    def test_import_default_invalid_variant(self, client, nar_shaddaa_data):
        """POST /studio/import/default with bad variant returns 400."""
        resp = client.post("/studio/import/default", json={
            "spine_data": nar_shaddaa_data,
            "variant_id": "nonexistent",
        })
        assert resp.status_code == 400

    def test_import_apply_route(self, client, spine_with_import):
        """POST /studio/import/apply processes an import package."""
        package = {
            "name": "Keth Varso",
            "species": "bothan",
            "career": "smuggler",
            "specializations": ["pilot"],
            "characteristics": {"brawn": 2, "agility": 3, "intellect": 3,
                                "cunning": 4, "willpower": 2, "presence": 3},
            "skills": {"deception": 2, "piloting_space": 2},
            "wound_threshold": 12,
            "strain_threshold": 12,
            "soak": 2,
            "total_xp": 110,
            "available_xp": 10,
        }
        resp = client.post("/studio/import/apply", json={
            "import_package": package,
            "spine_data": spine_with_import,
            "variant_id": "clovis_beryl",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["character_data"]["name"] == "Keth Varso"
        assert len(data["applied_mappings"]) > 0

    def test_import_apply_no_interface(self, client, nar_shaddaa_data):
        """POST /studio/import/apply without import_interface returns 400."""
        package = {
            "name": "Test", "species": "human", "career": "soldier",
            "specializations": ["commando"],
            "characteristics": {"brawn": 3, "agility": 2, "intellect": 2,
                                "cunning": 2, "willpower": 3, "presence": 2},
            "skills": {}, "wound_threshold": 14, "strain_threshold": 10,
            "soak": 3, "total_xp": 100, "available_xp": 0,
        }
        resp = client.post("/studio/import/apply", json={
            "import_package": package,
            "spine_data": nar_shaddaa_data,
            "variant_id": "clovis_beryl",
        })
        assert resp.status_code == 400
