"""
Phase 11 verification: Talent Tree Engine (Game Mechanics §15).

Success criteria:
1. Talent library loads and specialization trees load and cross-reference correctly
2. A character with Skilled Jockey has 1 fewer setback on Piloting checks (Type 1 passive)
3. A character with Dodge in a combat scene has difficulty reduced, strain charged (Type 2 conditional)
4. Convincing Demeanor listed in check effects — Type 3 substitution verified
5. Narrative enabler talents appear in narration prompt's CHARACTER CAPABILITIES block (Type 4)
6. Talent activations are logged per turn and included in narration context
7. Pipeline has empty-but-present Stage 4 (destiny) and Stage 5 (Force dice) slots
"""

import sys
import json

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

from engine.character import Character
from engine.dice import DicePool
from engine.checks import CheckRequest, Difficulty, build_pool
from engine.talents import (
    load_talent_library,
    load_specialization_tree,
    get_talent_rank,
    get_acquired_refs,
    apply_passive_modifiers,
    apply_conditional_modifiers,
    apply_threshold_modifiers,
    build_talent_check_effects,
    build_talent_capabilities,
    build_talent_activations_block,
    TalentActivation,
)


def _make_character(**overrides) -> Character:
    """Create a test character with Keth's base stats."""
    data = {
        "name": "Keth Varso",
        "species": "bothan",
        "career": "smuggler",
        "specializations": ["pilot"],
        "primary_game_line": "edge_of_empire",
        "background": "Test character",
        "characteristics": {
            "brawn": 2, "agility": 3, "intellect": 3,
            "cunning": 4, "willpower": 2, "presence": 3,
        },
        "skills": {
            "deception": 2, "piloting_space": 2, "streetwise": 1,
            "skulduggery": 1, "coordination": 1, "perception": 1,
        },
        "wound_threshold": 12,
        "strain_threshold": 12,
        "current_wounds": 0,
        "current_strain": 0,
        "soak": 2,
        "total_xp": 110,
        "available_xp": 0,
        "motivation": {"obligation_type": "Debt", "obligation_value": 15},
        "force_rating": 0,
        "career_skills": [],
        "reserved_xp": 0,
        "advancement_log": [],
        "acquired_talents": [],
        "talent_uses": {},
    }
    data.update(overrides)
    return Character(**data)


# ── Criterion 1: Library and tree loading ─────────────────────────────

def test_library_loads():
    lib = load_talent_library()
    assert isinstance(lib, dict), "Library should be a dict"
    assert len(lib) >= 20, f"Expected ≥20 talents, got {len(lib)}"
    assert "skilled_jockey" in lib
    assert "dodge" in lib
    assert "convincing_demeanor" in lib
    assert "black_market_contacts" in lib
    assert "natural_pilot" in lib
    print("  ✓ Talent library loads with all expected entries")


def test_tree_loads_and_crossrefs():
    lib = load_talent_library()
    tree = load_specialization_tree("smuggler_pilot")

    assert tree.career == "smuggler"
    assert tree.specialization == "pilot"
    assert len(tree.entries) >= 15, f"Expected ≥15 entries, got {len(tree.entries)}"

    # Every talent_ref in the tree should exist in the library
    missing = []
    for entry in tree.entries:
        if entry.talent_ref not in lib:
            missing.append(entry.talent_ref)
    assert not missing, f"Tree refs missing from library: {missing}"

    # Tree paths exist
    assert len(tree.tree_paths) >= 2, "Expected at least 2 tree paths"
    print("  ✓ Smuggler/Pilot tree loads and all refs cross-reference to library")


def test_all_trees_load():
    for tree_name in ("smuggler_pilot", "smuggler_scoundrel", "smuggler_thief"):
        tree = load_specialization_tree(tree_name)
        assert len(tree.entries) >= 15
    print("  ✓ All three smuggler trees load successfully")


# ── Criterion 2: Skilled Jockey passive (Type 1) ─────────────────────

def test_skilled_jockey_removes_setback():
    char = _make_character(acquired_talents=[
        {"talent_ref": "skilled_jockey", "tree": "smuggler_pilot", "entry_id": "pilot_t1_1"},
    ])

    # Build a pool with 1 setback on a piloting check
    pool = DicePool(ability=1, proficiency=2, difficulty=2, setback=1)
    activations = apply_passive_modifiers(pool, char, "piloting_space")

    assert pool.setback == 0, f"Expected 0 setback after Skilled Jockey, got {pool.setback}"
    assert len(activations) == 1
    assert activations[0].talent_name == "Skilled Jockey"
    assert activations[0].talent_type == "passive"
    print("  ✓ Skilled Jockey rank 1 removes 1 setback from Piloting checks")


def test_skilled_jockey_rank2():
    char = _make_character(acquired_talents=[
        {"talent_ref": "skilled_jockey", "tree": "smuggler_pilot", "entry_id": "pilot_t1_1"},
        {"talent_ref": "skilled_jockey", "tree": "smuggler_pilot", "entry_id": "pilot_t2_1"},
    ])

    pool = DicePool(ability=1, proficiency=2, difficulty=2, setback=2)
    activations = apply_passive_modifiers(pool, char, "piloting_space")

    assert pool.setback == 0, f"Expected 0 setback after rank 2, got {pool.setback}"
    print("  ✓ Skilled Jockey rank 2 removes 2 setback dice")


def test_skilled_jockey_no_effect_on_other_skill():
    char = _make_character(acquired_talents=[
        {"talent_ref": "skilled_jockey", "tree": "smuggler_pilot", "entry_id": "pilot_t1_1"},
    ])

    pool = DicePool(ability=2, proficiency=1, difficulty=2, setback=1)
    activations = apply_passive_modifiers(pool, char, "deception")

    assert pool.setback == 1, "Skilled Jockey should not affect Deception"
    assert len(activations) == 0
    print("  ✓ Skilled Jockey does not affect non-piloting skills")


# ── Criterion 3: Dodge conditional (Type 2) ──────────────────────────

def test_dodge_reduces_difficulty_in_combat():
    char = _make_character(acquired_talents=[
        {"talent_ref": "dodge", "tree": "smuggler_scoundrel", "entry_id": "scoundrel_t2_3"},
    ])

    pool = DicePool(ability=2, proficiency=1, difficulty=3, setback=0)
    initial_strain = char.current_strain
    activations = apply_conditional_modifiers(pool, char, "combat")

    assert pool.difficulty == 2, f"Expected 2 difficulty after Dodge, got {pool.difficulty}"
    assert char.current_strain == initial_strain + 1, "Dodge should charge 1 strain"
    assert len(activations) == 1
    assert activations[0].talent_name == "Dodge"
    assert activations[0].strain_charged == 1
    print("  ✓ Dodge reduces difficulty by 1 in combat, charges 1 strain")


def test_dodge_rank2():
    char = _make_character(acquired_talents=[
        {"talent_ref": "dodge", "tree": "smuggler_scoundrel", "entry_id": "scoundrel_t2_3"},
        {"talent_ref": "dodge", "tree": "smuggler_scoundrel", "entry_id": "scoundrel_t3_3"},
    ])

    pool = DicePool(ability=2, proficiency=1, difficulty=3, setback=0)
    activations = apply_conditional_modifiers(pool, char, "combat")

    assert pool.difficulty == 1, f"Expected 1 difficulty after Dodge rank 2, got {pool.difficulty}"
    assert char.current_strain == 2, "Dodge rank 2 should charge 2 strain"
    print("  ✓ Dodge rank 2 removes 2 difficulty dice, charges 2 strain")


def test_dodge_no_effect_in_social():
    char = _make_character(acquired_talents=[
        {"talent_ref": "dodge", "tree": "smuggler_scoundrel", "entry_id": "scoundrel_t2_3"},
    ])

    pool = DicePool(ability=2, proficiency=1, difficulty=3, setback=0)
    activations = apply_conditional_modifiers(pool, char, "social")

    assert pool.difficulty == 3, "Dodge should not fire in social scenes"
    assert char.current_strain == 0
    assert len(activations) == 0
    print("  ✓ Dodge does not activate in social scenes")


def test_dodge_not_affordable():
    char = _make_character(
        current_strain=12,  # at threshold
        acquired_talents=[
            {"talent_ref": "dodge", "tree": "smuggler_scoundrel", "entry_id": "scoundrel_t2_3"},
        ],
    )

    pool = DicePool(ability=2, proficiency=1, difficulty=3, setback=0)
    activations = apply_conditional_modifiers(pool, char, "combat")

    assert pool.difficulty == 3, "Dodge should not fire when strain unaffordable"
    assert len(activations) == 0
    print("  ✓ Dodge does not activate when strain is at threshold")


# ── Criterion 4: Convincing Demeanor (Type 3 substitution) ───────────

def test_convincing_demeanor_in_check_effects():
    char = _make_character(acquired_talents=[
        {"talent_ref": "convincing_demeanor", "tree": "smuggler_scoundrel", "entry_id": "scoundrel_t1_0"},
    ])

    effects = build_talent_check_effects(char)
    assert "Convincing Demeanor" in effects
    assert "Deception" in effects
    assert "Charm" in effects
    print("  ✓ Convincing Demeanor listed in check effects (Type 3 substitution)")


# ── Criterion 5: Narrative enablers (Type 4) in capabilities ─────────

def test_narrative_enablers_in_capabilities():
    char = _make_character(acquired_talents=[
        {"talent_ref": "black_market_contacts", "tree": "smuggler_scoundrel", "entry_id": "scoundrel_t1_1"},
        {"talent_ref": "full_throttle", "tree": "smuggler_pilot", "entry_id": "pilot_t1_0"},
    ])

    caps = build_talent_capabilities(char)
    assert "CHARACTER CAPABILITIES:" in caps
    assert "Black Market Contacts" in caps
    assert "Full Throttle" in caps
    print("  ✓ Narrative enabler talents appear in CHARACTER CAPABILITIES block")


def test_no_capabilities_when_empty():
    char = _make_character()
    caps = build_talent_capabilities(char)
    assert caps == ""
    print("  ✓ Empty capabilities when no talents acquired")


# ── Criterion 6: Activation logging and context ─────────────────────

def test_activation_block_formatting():
    activations = [
        TalentActivation(
            talent_name="Skilled Jockey",
            talent_type="passive",
            effect_description="Removed 1 setback die",
            narrative_hint="The ship responds to the pilot's hands",
        ),
        TalentActivation(
            talent_name="Dodge",
            talent_type="conditional",
            effect_description="Activated in combat scene",
            strain_charged=1,
            narrative_hint="Instinct sharpened by years of being shot at",
        ),
    ]

    block = build_talent_activations_block(activations)
    assert "TALENT ACTIVATIONS THIS TURN:" in block
    assert "Skilled Jockey" in block
    assert "Dodge" in block
    assert "1 strain" in block
    print("  ✓ Talent activations formatted correctly for narration context")


def test_full_pipeline_returns_activations():
    char = _make_character(acquired_talents=[
        {"talent_ref": "skilled_jockey", "tree": "smuggler_pilot", "entry_id": "pilot_t1_1"},
    ])

    check = CheckRequest(
        skill="piloting_space",
        difficulty=Difficulty.AVERAGE,
        setback_dice=1,
    )
    pool, activations, _ = build_pool(char, check, scene_type="chase")

    assert pool.setback == 0, "Skilled Jockey should have removed the setback"
    assert len(activations) >= 1
    assert any(a.talent_name == "Skilled Jockey" for a in activations)
    print("  ✓ Full pipeline returns activations from build_pool")


def test_empty_activation_block():
    block = build_talent_activations_block([])
    assert block == ""
    print("  ✓ Empty activation block when no talents fire")


# ── Criterion 7: Pipeline stages 4 and 5 pass-through ───────────────

def test_pipeline_stages_4_5_passthrough():
    """Verify that build_pool's source code has Stage 4 and Stage 5 slots."""
    import inspect
    source = inspect.getsource(build_pool)

    assert "Stage 4" in source, "Stage 4 (Destiny) slot must be present in pipeline"
    assert "Stage 5" in source, "Stage 5 (Force dice) slot must be present in pipeline"
    assert "Phase 11.5" in source, "Stage 4 should reference Phase 11.5"
    assert "Phase 14" in source, "Stage 5 should reference Phase 14"
    print("  ✓ Pipeline has Stage 4 (Destiny) and Stage 5 (Force dice) pass-through slots")


# ── Bonus: threshold modifiers ───────────────────────────────────────

def test_grit_increases_strain_threshold():
    char = _make_character(acquired_talents=[
        {"talent_ref": "grit", "tree": "smuggler_pilot", "entry_id": "pilot_t2_3"},
    ])

    apply_threshold_modifiers(char)
    assert char.strain_threshold == 13, f"Expected 13 strain threshold with Grit, got {char.strain_threshold}"
    print("  ✓ Grit increases strain threshold by 1")


def test_toughened_increases_wound_threshold():
    char = _make_character(acquired_talents=[
        {"talent_ref": "toughened", "tree": "smuggler_pilot", "entry_id": "pilot_t3_3"},
    ])

    apply_threshold_modifiers(char)
    assert char.wound_threshold == 13, f"Expected 13 wound threshold with Toughened, got {char.wound_threshold}"
    print("  ✓ Toughened increases wound threshold by 1")


# ── Bonus: talent rank computation ───────────────────────────────────

def test_talent_rank():
    char = _make_character(acquired_talents=[
        {"talent_ref": "dodge", "tree": "smuggler_scoundrel", "entry_id": "scoundrel_t2_3"},
        {"talent_ref": "dodge", "tree": "smuggler_scoundrel", "entry_id": "scoundrel_t3_3"},
        {"talent_ref": "skilled_jockey", "tree": "smuggler_pilot", "entry_id": "pilot_t1_1"},
    ])

    assert get_talent_rank(char, "dodge") == 2
    assert get_talent_rank(char, "skilled_jockey") == 1
    assert get_talent_rank(char, "natural_pilot") == 0
    print("  ✓ Talent rank computation correct across multiple acquisitions")


def test_acquired_refs():
    char = _make_character(acquired_talents=[
        {"talent_ref": "dodge", "tree": "smuggler_scoundrel", "entry_id": "scoundrel_t2_3"},
        {"talent_ref": "skilled_jockey", "tree": "smuggler_pilot", "entry_id": "pilot_t1_1"},
    ])

    refs = get_acquired_refs(char)
    assert refs == {"dodge", "skilled_jockey"}
    print("  ✓ Acquired refs set computed correctly")


# ── Run all ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== Phase 11: Talent Tree Engine ===\n")

    print("Criterion 1: Library and tree loading")
    test_library_loads()
    test_tree_loads_and_crossrefs()
    test_all_trees_load()

    print("\nCriterion 2: Skilled Jockey passive (Type 1)")
    test_skilled_jockey_removes_setback()
    test_skilled_jockey_rank2()
    test_skilled_jockey_no_effect_on_other_skill()

    print("\nCriterion 3: Dodge conditional (Type 2)")
    test_dodge_reduces_difficulty_in_combat()
    test_dodge_rank2()
    test_dodge_no_effect_in_social()
    test_dodge_not_affordable()

    print("\nCriterion 4: Convincing Demeanor (Type 3 substitution)")
    test_convincing_demeanor_in_check_effects()

    print("\nCriterion 5: Narrative enablers (Type 4) in capabilities")
    test_narrative_enablers_in_capabilities()
    test_no_capabilities_when_empty()

    print("\nCriterion 6: Activation logging and context")
    test_activation_block_formatting()
    test_full_pipeline_returns_activations()
    test_empty_activation_block()

    print("\nCriterion 7: Pipeline stages 4+5 pass-through")
    test_pipeline_stages_4_5_passthrough()

    print("\nBonus: Threshold modifiers")
    test_grit_increases_strain_threshold()
    test_toughened_increases_wound_threshold()

    print("\nBonus: Talent rank computation")
    test_talent_rank()
    test_acquired_refs()

    print("\n=== All Phase 11 criteria verified ✓ ===\n")
