"""
Phase 15: Force Powers and Progression — Tests

Verifies all 6 success criteria:
1. A character with Move can receive [Force:Move] tagged choices from the GM
2. A character without Move never receives Move-tagged choices
3. Force power upgrade milestones fire and produce narrative choices
   mapping to range/strength/control upgrade paths
4. Committing 1 Force die to Sense reduces available Force dice by 1
   on subsequent rolls
5. Releasing a commitment restores the die to the available pool
6. Force Rating increase through a specialization talent works via
   Category 3 milestone
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import pytest
from dataclasses import asdict

from engine.character import (
    Character, Species, Career, Characteristics, SkillRanks,
    MotivationTrack, GameLine,
)
from engine.checks import build_pool, build_pure_force_pool, CheckRequest, Difficulty
from engine.dice import DicePool, RollResult
from engine.force import (
    ForcePowerMilestoneChoice,
    apply_force_power_upgrade,
    build_force_capabilities_block,
    build_force_choice_guidance,
    build_force_power_milestone_choices,
    build_force_state_block,
    character_has_power,
    commit_force_die,
    get_available_force_dice,
    get_character_power,
    get_effective_pips_required,
    load_force_power,
    release_commitment,
)
from engine.talents import acquire_talent, MilestoneChoice
from unittest.mock import patch


# ── Fake talent library entry for Force Rating increase ───────────────

FAKE_LIBRARY = {
    "dedication_fr": {
        "name": "Dedication (Force Rating)",
        "talent_type": "passive",
        "effects": [{"type": "force_rating_increase", "modifier": 1}],
    },
}


# ── Test fixtures ──────────────────────────────────────────────────────

def make_force_character(
    force_rating=1,
    force_committed=0,
    morality=50,
    force_powers=None,
    active_commitments=None,
) -> Character:
    """Create a Force-sensitive character for testing."""
    return Character(
        name="Kael Dren",
        species=Species.HUMAN,
        career=Career.GUARDIAN,
        specializations=["guardian_protector"],
        primary_game_line=GameLine.FORCE_AND_DESTINY,
        characteristics=Characteristics(
            brawn=2, agility=2, intellect=3, cunning=2, willpower=3, presence=2,
        ),
        skills=SkillRanks(
            discipline=2, athletics=1, lightsaber=2, perception=1,
        ),
        wound_threshold=12,
        strain_threshold=14,
        soak=2,
        force_rating=force_rating,
        force_committed=force_committed,
        motivation=MotivationTrack(morality=morality),
        force_powers=force_powers or [],
        active_commitments=active_commitments or [],
    )


def make_non_force_character() -> Character:
    """Create a character with no Force sensitivity."""
    return Character(
        name="Keth Varso",
        species=Species.HUMAN,
        career=Career.SMUGGLER,
        specializations=["smuggler_pilot"],
        primary_game_line=GameLine.EDGE_OF_EMPIRE,
        characteristics=Characteristics(
            brawn=2, agility=3, intellect=3, cunning=3, willpower=2, presence=2,
        ),
        skills=SkillRanks(
            deception=2, piloting_space=2, streetwise=1,
        ),
        wound_threshold=12,
        strain_threshold=12,
        soak=2,
        force_rating=0,
    )


# ── Helper: character with Move power ────────────────────────────────

def char_with_move(upgrades=None) -> Character:
    return make_force_character(force_powers=[{
        "power_id": "move",
        "active_upgrades": upgrades or [],
    }])


def char_with_sense(upgrades=None) -> Character:
    return make_force_character(force_powers=[{
        "power_id": "sense",
        "active_upgrades": upgrades or [],
    }])


def char_with_move_and_sense() -> Character:
    return make_force_character(force_powers=[
        {"power_id": "move", "active_upgrades": []},
        {"power_id": "sense", "active_upgrades": ["control_danger_sense"]},
    ])


# ═══════════════════════════════════════════════════════════════════════
# SUCCESS CRITERION 1: Character with Move receives [Force:Move] choices
# ═══════════════════════════════════════════════════════════════════════

class TestForceCapabilitiesBlock:
    """The capabilities block informs the GM what Force powers to offer."""

    def test_move_power_appears_in_capabilities(self):
        """Character with Move → capabilities block mentions Move."""
        char = char_with_move()
        block = build_force_capabilities_block(char)
        assert "Move" in block
        assert "[Force:Move]" in block

    def test_sense_power_appears_in_capabilities(self):
        """Character with Sense → capabilities block mentions Sense."""
        char = char_with_sense()
        block = build_force_capabilities_block(char)
        assert "Sense" in block
        assert "[Force:Sense]" in block

    def test_multiple_powers_in_capabilities(self):
        """Character with both Move and Sense → both appear."""
        char = char_with_move_and_sense()
        block = build_force_capabilities_block(char)
        assert "[Force:Move]" in block
        assert "[Force:Sense]" in block

    def test_capabilities_includes_guidance(self):
        """Capabilities block includes GM choice guidance text."""
        char = char_with_move()
        block = build_force_capabilities_block(char)
        assert "telekinetic" in block.lower() or "guidance" in block.lower()

    def test_capabilities_shows_active_upgrades(self):
        """Active upgrades are listed in the capabilities block."""
        char = char_with_move(upgrades=["range_1"])
        block = build_force_capabilities_block(char)
        assert "Range" in block

    def test_dark_dominant_shows_dark_flavor(self):
        """Dark-dominant character sees dark side flavor text."""
        char = make_force_character(
            morality=30,
            force_powers=[{"power_id": "move", "active_upgrades": []}],
        )
        block = build_force_capabilities_block(char)
        assert "dark" in block.lower() or "slam" in block.lower()

    def test_light_dominant_no_dark_flavor(self):
        """Light-dominant character does not see dark side flavor."""
        char = make_force_character(
            morality=75,
            force_powers=[{"power_id": "move", "active_upgrades": []}],
        )
        block = build_force_capabilities_block(char)
        # Dark side flavor line should not be present
        assert "Dark side flavor" not in block

    def test_capabilities_warns_about_unavailable_powers(self):
        """Block contains instruction to only offer possessed powers."""
        char = char_with_move()
        block = build_force_capabilities_block(char)
        assert "Only offer Force-tagged choices for powers listed" in block


# ═══════════════════════════════════════════════════════════════════════
# SUCCESS CRITERION 2: Character without Move never receives Move tags
# ═══════════════════════════════════════════════════════════════════════

class TestNoForcePowersNoTags:
    """Characters without Force powers produce empty capability blocks."""

    def test_non_force_character_empty_block(self):
        """Non-Force-sensitive character → empty capabilities block."""
        char = make_non_force_character()
        block = build_force_capabilities_block(char)
        assert block == ""

    def test_force_sensitive_no_powers_empty_block(self):
        """Force-sensitive character with no acquired powers → empty."""
        char = make_force_character(force_rating=1, force_powers=[])
        block = build_force_capabilities_block(char)
        assert block == ""

    def test_sense_only_no_move_tag(self):
        """Character with only Sense → no Move tag in block."""
        char = char_with_sense()
        block = build_force_capabilities_block(char)
        assert "[Force:Move]" not in block
        assert "[Force:Sense]" in block

    def test_non_force_empty_choice_guidance(self):
        """Non-Force character → empty choice guidance."""
        char = make_non_force_character()
        guidance = build_force_choice_guidance(char)
        assert guidance == ""


class TestForceChoiceGuidance:
    """Check decision prompt guidance for local model."""

    def test_move_in_choice_guidance(self):
        """Character with Move → guidance lists Move with pips."""
        char = char_with_move()
        guidance = build_force_choice_guidance(char)
        assert "Move" in guidance
        assert "pips_required" in guidance

    def test_pips_increase_with_upgrades(self):
        """Control:Hurl upgrade increases Move's pip requirement."""
        char = char_with_move(upgrades=["strength_1", "control_hurl"])
        pips = get_effective_pips_required("move", char)
        assert pips == 2  # base 1 + control_hurl adds 1


# ═══════════════════════════════════════════════════════════════════════
# SUCCESS CRITERION 3: Force power upgrade milestones produce choices
# ═══════════════════════════════════════════════════════════════════════

class TestForcePowerMilestoneChoices:
    """Milestone system generates upgrade options for Force powers."""

    def test_basic_milestone_choices(self):
        """Character with Move and reserved XP gets upgrade choices."""
        char = char_with_move()
        char.reserved_xp = 30
        choices = build_force_power_milestone_choices(char, char.reserved_xp)
        assert len(choices) > 0
        assert all(isinstance(c, ForcePowerMilestoneChoice) for c in choices)

    def test_choices_include_range_and_strength(self):
        """Available upgrades include range and strength paths."""
        char = char_with_move()
        char.reserved_xp = 30
        choices = build_force_power_milestone_choices(char, char.reserved_xp)
        types = {c.upgrade_type for c in choices}
        # Move has range, strength, and control upgrades with no prereqs
        assert "range" in types or "strength" in types or "control" in types

    def test_choices_respect_prerequisites(self):
        """Upgrades with unmet prereqs are not offered."""
        char = char_with_move()  # no upgrades yet
        char.reserved_xp = 50
        choices = build_force_power_milestone_choices(char, char.reserved_xp)
        upgrade_ids = {c.upgrade_id for c in choices}
        # range_2 requires range_1 — should not be available
        assert "range_2" not in upgrade_ids
        # strength_2 requires strength_1 — should not be available
        assert "strength_2" not in upgrade_ids

    def test_choices_with_met_prerequisites(self):
        """Upgrades with met prereqs are offered."""
        char = char_with_move(upgrades=["range_1"])
        char.reserved_xp = 50
        choices = build_force_power_milestone_choices(char, char.reserved_xp)
        upgrade_ids = {c.upgrade_id for c in choices}
        # range_2 should now be available (prereq range_1 is met)
        assert "range_2" in upgrade_ids

    def test_already_acquired_not_offered(self):
        """Already-acquired upgrades are not offered again."""
        char = char_with_move(upgrades=["range_1"])
        char.reserved_xp = 50
        choices = build_force_power_milestone_choices(char, char.reserved_xp)
        upgrade_ids = {c.upgrade_id for c in choices}
        assert "range_1" not in upgrade_ids

    def test_insufficient_xp_excludes_choices(self):
        """Upgrades costing more than reserved XP are excluded."""
        char = char_with_move()
        char.reserved_xp = 5  # too low for any upgrade (min 10 XP)
        choices = build_force_power_milestone_choices(char, char.reserved_xp)
        assert len(choices) == 0

    def test_max_choices_respected(self):
        """At most max_choices options are returned."""
        char = char_with_move()
        char.reserved_xp = 100
        choices = build_force_power_milestone_choices(
            char, char.reserved_xp, max_choices=2,
        )
        assert len(choices) <= 2

    def test_no_powers_no_choices(self):
        """Character with no Force powers → no milestone choices."""
        char = make_force_character(force_powers=[])
        choices = build_force_power_milestone_choices(char, 50)
        assert len(choices) == 0

    def test_choice_has_required_fields(self):
        """Each ForcePowerMilestoneChoice has all required fields."""
        char = char_with_move()
        char.reserved_xp = 30
        choices = build_force_power_milestone_choices(char, char.reserved_xp)
        for c in choices:
            assert c.power_id == "move"
            assert c.power_name == "Move"
            assert c.upgrade_id
            assert c.upgrade_name
            assert c.upgrade_type
            assert c.xp_cost > 0
            assert c.effect


class TestApplyForcePowerUpgrade:
    """Applying a Force power upgrade modifies the character correctly."""

    def test_apply_upgrade_deducts_xp(self):
        """Applying an upgrade deducts from reserved_xp."""
        char = char_with_move()
        char.reserved_xp = 30
        choice = ForcePowerMilestoneChoice(
            power_id="move", power_name="Move",
            upgrade_id="range_1", upgrade_name="Range",
            upgrade_type="range", xp_cost=10,
            effect="Increase range.", narrative="Reach further.",
        )
        apply_force_power_upgrade(char, choice)
        assert char.reserved_xp == 20

    def test_apply_upgrade_adds_to_active(self):
        """Applying an upgrade adds it to the power's active_upgrades."""
        char = char_with_move()
        char.reserved_xp = 30
        choice = ForcePowerMilestoneChoice(
            power_id="move", power_name="Move",
            upgrade_id="range_1", upgrade_name="Range",
            upgrade_type="range", xp_cost=10,
            effect="Increase range.", narrative="Reach further.",
        )
        apply_force_power_upgrade(char, choice)
        power = get_character_power(char, "move")
        assert "range_1" in power["active_upgrades"]

    def test_apply_upgrade_logs_advancement(self):
        """Applying an upgrade adds to advancement_log."""
        char = char_with_move()
        char.reserved_xp = 30
        choice = ForcePowerMilestoneChoice(
            power_id="move", power_name="Move",
            upgrade_id="strength_1", upgrade_name="Strength",
            upgrade_type="strength", xp_cost=10,
            effect="Increase silhouette.", narrative="Push harder.",
        )
        apply_force_power_upgrade(char, choice)
        log = char.advancement_log[-1]
        assert log["type"] == "force_power_upgrade"
        assert log["power_id"] == "move"
        assert log["upgrade_id"] == "strength_1"
        assert log["cost"] == 10


# ═══════════════════════════════════════════════════════════════════════
# SUCCESS CRITERION 4: Committing 1 Force die reduces available pool
# ═══════════════════════════════════════════════════════════════════════

class TestForceCommitment:
    """Committing Force dice reduces the available pool."""

    def test_commit_reduces_available(self):
        """Committing 1 die reduces available Force dice by 1."""
        char = char_with_sense(upgrades=["control_danger_sense"])
        assert get_available_force_dice(char) == 1
        success = commit_force_die(char, "sense", "control_danger_sense", 1)
        assert success is True
        assert get_available_force_dice(char) == 0
        assert char.force_committed == 1

    def test_commit_tracked_in_active_commitments(self):
        """Commitment is tracked in active_commitments list."""
        char = char_with_sense(upgrades=["control_danger_sense"])
        commit_force_die(char, "sense", "control_danger_sense", 5)
        assert len(char.active_commitments) == 1
        c = char.active_commitments[0]
        assert c["power"] == "sense"
        assert c["upgrade"] == "control_danger_sense"
        assert c["committed_since_turn"] == 5

    def test_commit_fails_when_no_dice_available(self):
        """Cannot commit when all Force dice are already committed."""
        char = make_force_character(force_rating=1, force_committed=1)
        char.force_powers = [{"power_id": "sense", "active_upgrades": ["control_danger_sense"]}]
        success = commit_force_die(char, "sense", "control_danger_sense", 1)
        assert success is False

    def test_commit_fails_duplicate(self):
        """Cannot commit to the same upgrade twice."""
        char = make_force_character(
            force_rating=2,
            force_powers=[{"power_id": "sense", "active_upgrades": ["control_danger_sense"]}],
        )
        commit_force_die(char, "sense", "control_danger_sense", 1)
        success = commit_force_die(char, "sense", "control_danger_sense", 2)
        assert success is False
        assert char.force_committed == 1

    def test_committed_dice_excluded_from_pool(self):
        """Force pool size reflects committed dice."""
        char = make_force_character(
            force_rating=2,
            force_committed=1,
            force_powers=[{"power_id": "sense", "active_upgrades": ["control_danger_sense"]}],
            active_commitments=[{
                "power": "sense", "upgrade": "control_danger_sense",
                "dice_committed": 1, "committed_since_turn": 1,
            }],
        )
        available = get_available_force_dice(char)
        assert available == 1  # 2 rating - 1 committed

    def test_force_state_block_shows_commitments(self):
        """Force state block mentions committed dice and details."""
        char = make_force_character(
            force_rating=2,
            force_committed=1,
            force_powers=[{"power_id": "sense", "active_upgrades": ["control_danger_sense"]}],
            active_commitments=[{
                "power": "sense", "upgrade": "control_danger_sense",
                "dice_committed": 1, "committed_since_turn": 1,
                "narrative_note": "Ongoing danger awareness",
            }],
        )
        block = build_force_state_block(char)
        assert "Committed dice: 1" in block
        assert "sense" in block


# ═══════════════════════════════════════════════════════════════════════
# SUCCESS CRITERION 5: Releasing commitment restores dice
# ═══════════════════════════════════════════════════════════════════════

class TestForceRelease:
    """Releasing a commitment restores Force dice to the available pool."""

    def test_release_restores_available(self):
        """Releasing a commitment restores 1 available Force die."""
        char = make_force_character(
            force_rating=2,
            force_committed=1,
            force_powers=[{"power_id": "sense", "active_upgrades": ["control_danger_sense"]}],
            active_commitments=[{
                "power": "sense", "upgrade": "control_danger_sense",
                "dice_committed": 1, "committed_since_turn": 1,
            }],
        )
        assert get_available_force_dice(char) == 1
        success = release_commitment(char, "sense")
        assert success is True
        assert get_available_force_dice(char) == 2
        assert char.force_committed == 0
        assert len(char.active_commitments) == 0

    def test_release_nonexistent_fails(self):
        """Releasing a commitment for a power with no commitment fails."""
        char = char_with_sense()
        success = release_commitment(char, "sense")
        assert success is False

    def test_release_wrong_power_fails(self):
        """Releasing a commitment for a different power fails."""
        char = make_force_character(
            force_rating=2,
            force_committed=1,
            force_powers=[
                {"power_id": "sense", "active_upgrades": ["control_danger_sense"]},
                {"power_id": "move", "active_upgrades": []},
            ],
            active_commitments=[{
                "power": "sense", "upgrade": "control_danger_sense",
                "dice_committed": 1, "committed_since_turn": 1,
            }],
        )
        success = release_commitment(char, "move")
        assert success is False
        assert char.force_committed == 1

    def test_commit_then_release_roundtrip(self):
        """Full commit → release roundtrip restores original state."""
        char = make_force_character(
            force_rating=2,
            force_powers=[{"power_id": "sense", "active_upgrades": ["control_danger_sense"]}],
        )
        original_available = get_available_force_dice(char)
        assert original_available == 2

        commit_force_die(char, "sense", "control_danger_sense", 1)
        assert get_available_force_dice(char) == 1

        release_commitment(char, "sense")
        assert get_available_force_dice(char) == 2
        assert char.force_committed == 0
        assert len(char.active_commitments) == 0


# ═══════════════════════════════════════════════════════════════════════
# SUCCESS CRITERION 6: Force Rating increase via talent milestone
# ═══════════════════════════════════════════════════════════════════════

def _make_fr_milestone_choice() -> MilestoneChoice:
    """Build a MilestoneChoice for Force Rating increase (with mock library)."""
    return MilestoneChoice(
        branch_key="mastery",
        branch_theme="mastery",
        branch_description="Path of mastery",
        talent_ref="dedication_fr",
        talent_name="Dedication (Force Rating)",
        tree_name="guardian_protector",
        entry_id="t5_dedication_fr",
        xp_cost=25,
        narrative_identity="Force mastery",
        prose_tags=["force"],
    )


class TestForceRatingIncrease:
    """Force Rating can increase through a talent with force_rating_increase effect."""

    @patch("engine.talents._get_library", return_value=FAKE_LIBRARY)
    def test_acquire_force_rating_talent(self, mock_lib):
        """Acquiring a talent with force_rating_increase effect increases FR."""
        char = make_force_character(force_rating=1)
        char.reserved_xp = 25
        acquire_talent(char, _make_fr_milestone_choice())

        assert char.force_rating == 2
        assert get_available_force_dice(char) == 2

    @patch("engine.talents._get_library", return_value=FAKE_LIBRARY)
    def test_force_rating_increase_logged(self, mock_lib):
        """Force Rating increase is recorded in advancement_log."""
        char = make_force_character(force_rating=1)
        char.reserved_xp = 25
        acquire_talent(char, _make_fr_milestone_choice())

        fr_logs = [l for l in char.advancement_log if l["type"] == "force_rating_increase"]
        assert len(fr_logs) == 1
        assert fr_logs[0]["old_rating"] == 1
        assert fr_logs[0]["new_rating"] == 2

    @patch("engine.talents._get_library", return_value=FAKE_LIBRARY)
    def test_force_rating_increase_with_commitment(self, mock_lib):
        """FR increase while dice are committed: available increases."""
        char = make_force_character(
            force_rating=1,
            force_committed=1,
            force_powers=[{"power_id": "sense", "active_upgrades": ["control_danger_sense"]}],
            active_commitments=[{
                "power": "sense", "upgrade": "control_danger_sense",
                "dice_committed": 1, "committed_since_turn": 1,
            }],
        )
        assert get_available_force_dice(char) == 0

        char.reserved_xp = 25
        acquire_talent(char, _make_fr_milestone_choice())

        assert char.force_rating == 2
        assert get_available_force_dice(char) == 1  # 2 - 1 committed


# ═══════════════════════════════════════════════════════════════════════
# POWER DATA LOADING
# ═══════════════════════════════════════════════════════════════════════

class TestPowerDataLoading:
    """Force power JSON files load and parse correctly."""

    @pytest.mark.parametrize("power_id", [
        "move", "sense", "influence", "enhance", "heal_harm",
    ])
    def test_power_loads(self, power_id):
        """All 5 Force power data files load without error."""
        data = load_force_power(power_id)
        assert data["power_id"] == power_id
        assert "name" in data
        assert "base_pips_required" in data
        assert "upgrades" in data

    def test_move_has_expected_upgrades(self):
        """Move has range, strength, and control upgrade paths."""
        data = load_force_power("move")
        upgrade_types = {u["type"] for u in data["upgrades"].values()}
        assert "range" in upgrade_types
        assert "strength" in upgrade_types
        assert "control" in upgrade_types

    def test_sense_has_commitment_option(self):
        """Sense has a commitment option (danger sense)."""
        data = load_force_power("sense")
        assert "commitment_option" in data
        assert data["commitment_option"]["upgrade_id"] == "control_danger_sense"

    def test_heal_harm_higher_base_pips(self):
        """Heal/Harm requires 2 base pips (more powerful)."""
        data = load_force_power("heal_harm")
        assert data["base_pips_required"] == 2

    def test_upgrade_prerequisites_valid(self):
        """All prerequisite references point to existing upgrades."""
        for power_id in ["move", "sense", "influence", "enhance", "heal_harm"]:
            data = load_force_power(power_id)
            upgrade_ids = set(data["upgrades"].keys())
            for uid, upgrade in data["upgrades"].items():
                for prereq in upgrade.get("prerequisites", []):
                    assert prereq in upgrade_ids, (
                        f"{power_id}.{uid} has invalid prereq '{prereq}'"
                    )


class TestCharacterPowerQueries:
    """character_has_power and get_character_power work correctly."""

    def test_has_power_true(self):
        char = char_with_move()
        assert character_has_power(char, "move") is True

    def test_has_power_false(self):
        char = char_with_move()
        assert character_has_power(char, "sense") is False

    def test_get_power_returns_entry(self):
        char = char_with_move(upgrades=["range_1"])
        entry = get_character_power(char, "move")
        assert entry is not None
        assert "range_1" in entry["active_upgrades"]

    def test_get_power_none_when_missing(self):
        char = char_with_move()
        assert get_character_power(char, "influence") is None


class TestEffectivePips:
    """get_effective_pips_required reflects base + upgrade increases."""

    def test_base_pips_no_upgrades(self):
        char = char_with_move()
        assert get_effective_pips_required("move", char) == 1

    def test_pips_increase_from_control_hurl(self):
        """Control:Hurl adds 1 pip requirement."""
        char = char_with_move(upgrades=["strength_1", "control_hurl"])
        assert get_effective_pips_required("move", char) == 2

    def test_pips_for_unowned_power(self):
        """Power not owned by character → base pips only."""
        char = make_non_force_character()
        pips = get_effective_pips_required("move", char)
        assert pips == 1  # just the base

    def test_sense_strength_increases_pips(self):
        """Sense strength_1 (Read Thoughts) increases pips by 1."""
        char = char_with_sense(upgrades=["range_1", "strength_1"])
        pips = get_effective_pips_required("sense", char)
        assert pips == 2  # base 1 + strength_1 adds 1
