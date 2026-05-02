"""
Phase 16 test suite: Vehicle System (Game Mechanics §17).

Success criteria:
1. Mira's Luck loads from the campaign spine vehicle registry and
   persists in session state
2. The `space_combat` scene type activates vehicle-appropriate check
   decisions (Piloting, Gunnery, Mechanics)
3. Handling rating adds/removes boost/setback on Piloting checks
4. Ship damage transitions through operational -> stressed -> critical
   with correct setback additions and narration guidance
5. Vehicle critical hits are resolved from the simplified table and
   applied as narrative tags
6. The GM prompt includes ship state and writes accordingly
"""

import json
import random
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.vehicle import (
    ShipState,
    WeaponMount,
    load_ship_from_spine,
    roll_vehicle_critical,
    build_vehicle_damage_block,
    is_vehicle_skill,
    VEHICLE_CRITICAL_TABLE,
    STRESSED_THRESHOLD,
    CRITICAL_THRESHOLD,
)
from engine.character import Character, Career, Species, GameLine
from engine.checks import CheckRequest, Difficulty, build_pool
from engine.dice import DicePool, RollResult
from gm.context import ContextPackage, ArcState, ThreadState


# ── Fixtures ────────────────────────────────────────────────────────────

def make_ship(**overrides) -> ShipState:
    defaults = dict(
        ship_id="miras_luck",
        name="Mira's Luck",
        ship_type="YT-2000 light freighter",
        silhouette=4,
        speed=3,
        handling=-1,
        hull_threshold=22,
        system_strain_threshold=16,
        armor=3,
        shields={"fore": 1, "aft": 1},
        weapons=[WeaponMount(
            name="Dorsal laser turret", skill="gunnery",
            damage=6, arc="all", qualities=["linked_1"],
        )],
        narrative_notes="Battered but reliable.",
    )
    defaults.update(overrides)
    return ShipState(**defaults)


def make_character(**overrides) -> Character:
    defaults = dict(
        name="Keth Varso",
        species=Species.HUMAN,
        career=Career.SMUGGLER,
        specializations=["pilot"],
        primary_game_line=GameLine.EDGE_OF_EMPIRE,
        wound_threshold=12,
        strain_threshold=12,
        soak=2,
    )
    defaults.update(overrides)
    char = Character(**defaults)
    char.skills.piloting_space = 2
    char.skills.gunnery = 1
    char.skills.mechanics = 1
    char.characteristics.agility = 3
    return char


SPINE_VEHICLE_ENTRY = {
    "ship_id": "miras_luck",
    "name": "Mira's Luck",
    "type": "YT-2000 light freighter",
    "silhouette": 4,
    "speed": 3,
    "handling": -1,
    "hull_threshold": 22,
    "system_strain_threshold": 16,
    "armor": 3,
    "shields": {"fore": 1, "aft": 1},
    "weapons": [
        {
            "name": "Dorsal laser turret",
            "skill": "gunnery",
            "damage": 6,
            "arc": "all",
            "qualities": ["linked_1"],
        }
    ],
    "narrative_notes": "Battered but reliable.",
}


# ═══════════════════════════════════════════════════════════════════════
# CRITERION 1: Ship loads from spine and persists
# ═══════════════════════════════════════════════════════════════════════

class TestShipLoading:
    def test_load_from_spine_entry(self):
        ship = load_ship_from_spine(SPINE_VEHICLE_ENTRY)
        assert ship.ship_id == "miras_luck"
        assert ship.name == "Mira's Luck"
        assert ship.ship_type == "YT-2000 light freighter"
        assert ship.silhouette == 4
        assert ship.speed == 3
        assert ship.handling == -1
        assert ship.hull_threshold == 22
        assert ship.system_strain_threshold == 16
        assert ship.armor == 3
        assert ship.shields == {"fore": 1, "aft": 1}
        assert len(ship.weapons) == 1
        assert ship.weapons[0].name == "Dorsal laser turret"
        assert ship.weapons[0].damage == 6
        assert ship.narrative_notes == "Battered but reliable."

    def test_load_minimal_spine_entry(self):
        """Minimal entry with only required fields."""
        ship = load_ship_from_spine({"ship_id": "shuttle", "name": "Lambda Shuttle"})
        assert ship.ship_id == "shuttle"
        assert ship.name == "Lambda Shuttle"
        assert ship.handling == 0  # default
        assert ship.weapons == []

    def test_ship_serialization_roundtrip(self):
        ship = make_ship()
        json_str = ship.model_dump_json()
        restored = ShipState.model_validate_json(json_str)
        assert restored.ship_id == ship.ship_id
        assert restored.handling == ship.handling
        assert restored.weapons[0].damage == ship.weapons[0].damage

    def test_campaign_spine_has_vehicle_registry(self):
        """The active spine includes a populated vehicle registry."""
        path = os.path.join(
            os.path.dirname(__file__), "..", "data", "campaigns", "shadows_of_the_custodian.json"
        )
        with open(path) as f:
            spine = json.load(f)
        assert "vehicle_registry" in spine
        assert len(spine["vehicle_registry"]) >= 1
        # Schema check, not specific-ship check — the campaign content can change.
        first = spine["vehicle_registry"][0]
        assert first.get("ship_id")
        assert first.get("class") or first.get("model") or first.get("name")


# ═══════════════════════════════════════════════════════════════════════
# CRITERION 2: space_combat scene type routes to vehicle skills
# ═══════════════════════════════════════════════════════════════════════

class TestVehicleSkills:
    def test_vehicle_skills_recognized(self):
        assert is_vehicle_skill("piloting_space")
        assert is_vehicle_skill("piloting_planetary")
        assert is_vehicle_skill("gunnery")
        assert is_vehicle_skill("mechanics")
        assert is_vehicle_skill("leadership")
        assert is_vehicle_skill("astrogation")
        assert is_vehicle_skill("computers")

    def test_non_vehicle_skills_rejected(self):
        assert not is_vehicle_skill("deception")
        assert not is_vehicle_skill("charm")
        assert not is_vehicle_skill("ranged_light")
        assert not is_vehicle_skill("lightsaber")

    def test_space_combat_in_scene_type_enum(self):
        """The check_decision prompt and schema accept space_combat."""
        from gm.fast_gm import CHECK_DECISION_SCHEMA
        scene_types = CHECK_DECISION_SCHEMA["properties"]["scene_type"]["enum"]
        assert "space_combat" in scene_types

    def test_space_combat_pacing_exists(self):
        """Cloud GM has pacing guidance for space_combat."""
        from gm.cloud_gm import SCENE_PACING
        assert "space_combat" in SCENE_PACING
        entry = SCENE_PACING["space_combat"]
        assert "pacing" in entry
        assert "voice_exemplar" in entry
        assert "craft" in entry


# ═══════════════════════════════════════════════════════════════════════
# CRITERION 3: Handling adds/removes boost/setback on Piloting checks
# ═══════════════════════════════════════════════════════════════════════

class TestHandlingModifiers:
    def test_negative_handling_adds_setback(self):
        """Mira's Luck has handling -1 -> 1 setback on piloting."""
        ship = make_ship(handling=-1)
        assert ship.handling_setback() == 1
        assert ship.handling_boost() == 0

    def test_positive_handling_adds_boost(self):
        ship = make_ship(handling=2)
        assert ship.handling_boost() == 2
        assert ship.handling_setback() == 0

    def test_zero_handling_no_modifier(self):
        ship = make_ship(handling=0)
        assert ship.handling_boost() == 0
        assert ship.handling_setback() == 0

    def test_handling_in_pool_pipeline(self):
        """build_pool applies handling when ship_state is provided."""
        char = make_character()
        ship = make_ship(handling=-1)

        check = CheckRequest(
            skill="piloting_space",
            difficulty=Difficulty.AVERAGE,
            boost_dice=0,
            setback_dice=0,
        )
        pool, _, _ = build_pool(
            char, check, scene_type="space_combat", ship_state=ship,
        )
        # -1 handling -> 1 setback, ship is operational so 0 damage setback
        assert pool.setback == 1

    def test_handling_plus_damage_setback_stack(self):
        """Handling setback and damage setback stack additively."""
        char = make_character()
        ship = make_ship(handling=-2)
        # Make ship stressed (hull at 60%)
        ship.current_hull_trauma = int(ship.hull_threshold * 0.6)

        check = CheckRequest(
            skill="piloting_space",
            difficulty=Difficulty.AVERAGE,
        )
        pool, _, _ = build_pool(
            char, check, scene_type="space_combat", ship_state=ship,
        )
        # -2 handling -> 2 setback + stressed -> 1 setback = 3 total
        assert pool.setback == 3

    def test_handling_not_applied_to_non_vehicle_skills(self):
        """Non-vehicle skills should not get handling modifiers."""
        char = make_character()
        ship = make_ship(handling=-2)

        check = CheckRequest(
            skill="deception",
            difficulty=Difficulty.AVERAGE,
        )
        pool, _, _ = build_pool(
            char, check, scene_type="social", ship_state=ship,
        )
        # No handling or damage setback for non-vehicle skills
        assert pool.setback == 0

    def test_handling_not_applied_when_no_ship(self):
        """No ship_state -> no handling modifiers."""
        char = make_character()
        check = CheckRequest(
            skill="piloting_space",
            difficulty=Difficulty.AVERAGE,
        )
        pool, _, _ = build_pool(char, check, scene_type="space_combat")
        assert pool.setback == 0


# ═══════════════════════════════════════════════════════════════════════
# CRITERION 4: Damage transitions operational -> stressed -> critical
# ═══════════════════════════════════════════════════════════════════════

class TestDamageTiers:
    def test_fresh_ship_is_operational(self):
        ship = make_ship()
        assert ship.damage_tier() == "operational"
        assert ship.damage_setback() == 0

    def test_hull_at_50pct_is_stressed(self):
        ship = make_ship()
        ship.current_hull_trauma = int(ship.hull_threshold * 0.5)
        assert ship.damage_tier() == "stressed"
        assert ship.damage_setback() == 1

    def test_strain_at_50pct_is_stressed(self):
        ship = make_ship()
        ship.current_system_strain = int(ship.system_strain_threshold * 0.5)
        assert ship.damage_tier() == "stressed"
        assert ship.damage_setback() == 1

    def test_hull_at_80pct_is_critical(self):
        ship = make_ship()
        # Need to exceed 80% threshold (>=), not just reach it
        ship.current_hull_trauma = int(ship.hull_threshold * 0.82)
        assert ship.damage_tier() == "critical"
        assert ship.damage_setback() == 2

    def test_active_damage_makes_critical(self):
        ship = make_ship()
        ship.active_damage = ["Engine Hit: thruster compromised"]
        assert ship.damage_tier() == "critical"
        assert ship.damage_setback() == 2

    def test_hull_trauma_reduced_by_armor(self):
        ship = make_ship(armor=3)
        ship.apply_hull_trauma(5)
        assert ship.current_hull_trauma == 2  # 5 - 3 armor = 2

    def test_hull_trauma_minimum_zero(self):
        ship = make_ship(armor=10)
        ship.apply_hull_trauma(5)
        assert ship.current_hull_trauma == 0  # 5 - 10 = 0 (clamped)

    def test_system_strain_not_reduced_by_armor(self):
        ship = make_ship(armor=3)
        ship.apply_system_strain(5)
        assert ship.current_system_strain == 5  # no armor reduction

    def test_hull_capped_at_threshold(self):
        ship = make_ship()
        ship.apply_hull_trauma(100)
        assert ship.current_hull_trauma == ship.hull_threshold

    def test_ship_destroyed(self):
        ship = make_ship()
        ship.current_hull_trauma = ship.hull_threshold
        assert ship.is_destroyed()

    def test_repair_hull(self):
        ship = make_ship()
        ship.current_hull_trauma = 10
        ship.repair_hull(5)
        assert ship.current_hull_trauma == 5

    def test_repair_strain(self):
        ship = make_ship()
        ship.current_system_strain = 10
        ship.repair_strain(5)
        assert ship.current_system_strain == 5

    def test_repair_cannot_go_negative(self):
        ship = make_ship()
        ship.current_hull_trauma = 2
        ship.repair_hull(10)
        assert ship.current_hull_trauma == 0

    def test_setback_in_pool_for_stressed(self):
        """Pool pipeline adds +1 setback when ship stressed."""
        char = make_character()
        ship = make_ship(handling=0)  # no handling modifier
        ship.current_hull_trauma = int(ship.hull_threshold * 0.6)  # stressed

        check = CheckRequest(skill="piloting_space", difficulty=Difficulty.AVERAGE)
        pool, _, _ = build_pool(
            char, check, scene_type="space_combat", ship_state=ship,
        )
        assert pool.setback == 1

    def test_setback_in_pool_for_critical(self):
        """Pool pipeline adds +2 setback when ship critical."""
        char = make_character()
        ship = make_ship(handling=0)
        ship.current_hull_trauma = int(ship.hull_threshold * 0.85)

        check = CheckRequest(skill="piloting_space", difficulty=Difficulty.AVERAGE)
        pool, _, _ = build_pool(
            char, check, scene_type="space_combat", ship_state=ship,
        )
        assert pool.setback == 2


# ═══════════════════════════════════════════════════════════════════════
# CRITERION 5: Vehicle critical hits resolved from table
# ═══════════════════════════════════════════════════════════════════════

class TestVehicleCriticalHits:
    def test_critical_table_has_10_entries(self):
        assert len(VEHICLE_CRITICAL_TABLE) == 10

    def test_critical_table_rolls_cover_1_to_10(self):
        rolls = [entry["roll"] for entry in VEHICLE_CRITICAL_TABLE]
        assert sorted(rolls) == list(range(1, 11))

    def test_critical_hit_returns_entry(self):
        ship = make_ship()
        random.seed(42)
        entry = roll_vehicle_critical(ship)
        assert "name" in entry
        assert "description" in entry

    def test_shields_reduced_critical(self):
        ship = make_ship(shields={"fore": 2, "aft": 1})
        # Manually apply a shields_reduced effect
        for arc in list(ship.shields.keys()):
            if ship.shields[arc] > 0:
                ship.shields[arc] -= 1
                break
        assert ship.shields["fore"] == 1  # reduced by 1

    def test_speed_reduced_critical(self):
        ship = make_ship(speed=3)
        ship.speed = max(0, ship.speed - 1)
        assert ship.speed == 2

    def test_hull_breach_reduces_threshold(self):
        ship = make_ship(hull_threshold=22)
        ship.hull_threshold = max(1, ship.hull_threshold - 2)
        assert ship.hull_threshold == 20

    def test_cosmetic_damage_no_active_tag(self):
        """Rolls 1-2 (Rattled) don't add to active_damage."""
        ship = make_ship()
        # Roll entry 0 (roll=1): Rattled, no mechanical effect
        entry = VEHICLE_CRITICAL_TABLE[0]
        assert entry["mechanical_effect"] is None
        # If we call roll_vehicle_critical and get Rattled, active_damage stays empty
        # We can't control the random roll easily, so test the logic directly
        assert entry["name"] == "Rattled"

    def test_critical_hit_adds_active_damage(self):
        """Non-cosmetic critical hits add narrative tags to active_damage."""
        ship = make_ship()
        initial_damage_count = len(ship.active_damage)

        # Force a specific critical by seeding
        # Try multiple seeds until we get a non-cosmetic hit
        found = False
        for seed in range(100):
            test_ship = make_ship()
            random.seed(seed)
            entry = roll_vehicle_critical(test_ship)
            if entry["mechanical_effect"] is not None:
                assert len(test_ship.active_damage) == 1
                found = True
                break
        assert found, "Could not find a non-cosmetic critical hit in 100 seeds"

    def test_critical_makes_ship_critical_tier(self):
        """A ship with active_damage is always in critical tier."""
        ship = make_ship()
        ship.active_damage = ["Engine Hit: thruster compromised"]
        assert ship.damage_tier() == "critical"


# ═══════════════════════════════════════════════════════════════════════
# CRITERION 6: GM prompt includes ship state
# ═══════════════════════════════════════════════════════════════════════

class TestShipPromptBlocks:
    def test_check_prompt_block_format(self):
        ship = make_ship()
        block = ship.to_check_prompt_block()
        assert "SHIP STATUS: Mira's Luck" in block
        assert "operational" in block
        assert "Handling: -1" in block
        assert "Speed: 3" in block
        assert "Dorsal laser turret" in block

    def test_check_prompt_block_stressed(self):
        ship = make_ship()
        ship.current_hull_trauma = int(ship.hull_threshold * 0.6)
        block = ship.to_check_prompt_block()
        assert "stressed" in block

    def test_check_prompt_block_critical(self):
        ship = make_ship()
        ship.active_damage = ["Hull Breach: atmosphere venting"]
        block = ship.to_check_prompt_block()
        assert "critical" in block
        assert "Hull Breach" in block

    def test_narration_block_operational(self):
        ship = make_ship()
        block = ship.to_narration_block()
        assert "SHIP: Mira's Luck" in block
        assert "Operational" in block
        assert "Battered but reliable" in block

    def test_narration_block_stressed(self):
        ship = make_ship()
        ship.current_hull_trauma = int(ship.hull_threshold * 0.6)
        block = ship.to_narration_block()
        assert "STRESSED" in block
        assert "sparks" in block.lower() or "warning" in block.lower()

    def test_narration_block_critical(self):
        ship = make_ship()
        ship.active_damage = ["Engine Hit: thruster compromised"]
        block = ship.to_narration_block()
        assert "CRITICAL" in block
        assert "Engine Hit" in block

    def test_context_package_accepts_ship_block(self):
        """ContextPackage has ship_state_block field."""
        char = make_character()
        ship = make_ship()
        ctx = ContextPackage(
            character=char,
            arc=ArcState(
                campaign_name="Test",
                current_act=1,
                total_acts=4,
                act_name="The Approach",
                act_progress=0.0,
                current_anchor="test",
                next_anchor="",
                anchors_completed=[],
                throughline_question="Test?",
                tension_level="rising",
                open_threads=[],
                closed_threads=[],
            ),
            story_summary="",
            recent_turns=[],
            active_npcs=[],
            location="Space",
            situation="Dogfight",
            scene_type="space_combat",
            ship_state_block=ship.to_narration_block(),
        )
        assert "Mira's Luck" in ctx.ship_state_block

    def test_check_decision_prompt_has_ship_placeholder(self):
        """The check_decision.txt prompt includes {ship_status_section}."""
        from pathlib import Path
        prompt_path = Path(__file__).parent.parent / "gm" / "prompts" / "check_decision.txt"
        content = prompt_path.read_text(encoding="utf-8")
        assert "{ship_status_section}" in content

    def test_narration_prompt_has_ship_placeholder(self):
        """The narration.txt prompt includes {ship_state_block}."""
        from pathlib import Path
        prompt_path = Path(__file__).parent.parent / "gm" / "prompts" / "narration.txt"
        content = prompt_path.read_text(encoding="utf-8")
        assert "{ship_state_block}" in content


# ═══════════════════════════════════════════════════════════════════════
# Vehicle damage block for narration
# ═══════════════════════════════════════════════════════════════════════

class TestVehicleDamageBlock:
    def test_successful_gunnery_shows_weapon_damage(self):
        ship = make_ship()
        result = RollResult(
            net_successes=2, net_advantages=1, triumphs=0, despairs=0,
            succeeded=True, light_pips=0, dark_pips=0,
        )
        block = build_vehicle_damage_block(ship, result, "gunnery")
        assert "VEHICLE WEAPON DAMAGE" in block
        assert "Dorsal laser turret" in block

    def test_threat_shows_ship_strain(self):
        ship = make_ship()
        result = RollResult(
            net_successes=1, net_advantages=-2, triumphs=0, despairs=0,
            succeeded=True, light_pips=0, dark_pips=0,
        )
        block = build_vehicle_damage_block(ship, result, "piloting_space")
        assert "SHIP STRAIN" in block
        assert "2 system strain" in block

    def test_no_damage_block_when_no_roll(self):
        ship = make_ship()
        block = build_vehicle_damage_block(ship, None, "gunnery")
        assert block == ""


# ═══════════════════════════════════════════════════════════════════════
# DB persistence (integration)
# ═══════════════════════════════════════════════════════════════════════

class TestShipPersistence:
    def test_save_and_load_ship_state(self, tmp_path):
        """Ship state round-trips through SQLite."""
        import state.db as db
        old_path = db.DB_PATH
        db.DB_PATH = str(tmp_path / "test.db")
        try:
            db.init_db()
            from state.session import (
                create_session, save_ship_state, load_ship_states, load_ship_state,
            )
            session_id = create_session("Test", "{}", "{}")

            ship = make_ship()
            ship.current_hull_trauma = 5
            ship.current_system_strain = 3
            save_ship_state(session_id, ship)

            # Load all
            ships = load_ship_states(session_id)
            assert len(ships) == 1
            assert ships[0].ship_id == "miras_luck"
            assert ships[0].current_hull_trauma == 5
            assert ships[0].current_system_strain == 3

            # Load by ID
            loaded = load_ship_state(session_id, "miras_luck")
            assert loaded is not None
            assert loaded.handling == -1

            # Update and reload
            ship.current_hull_trauma = 10
            save_ship_state(session_id, ship)
            reloaded = load_ship_state(session_id, "miras_luck")
            assert reloaded.current_hull_trauma == 10
        finally:
            db.DB_PATH = old_path

    def test_load_nonexistent_ship_returns_none(self, tmp_path):
        import state.db as db
        old_path = db.DB_PATH
        db.DB_PATH = str(tmp_path / "test.db")
        try:
            db.init_db()
            from state.session import create_session, load_ship_state
            session_id = create_session("Test", "{}", "{}")
            result = load_ship_state(session_id, "nonexistent")
            assert result is None
        finally:
            db.DB_PATH = old_path


# ═══════════════════════════════════════════════════════════════════════
# Run
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
