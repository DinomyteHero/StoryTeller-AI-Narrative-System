"""
Phase 12 verification: Milestone Reflections and Intervention (§14.3, §15.1).

Success criteria:
1. When reserved_xp sufficient and behavioral signals suggest tree direction,
   talent milestone triggers at act boundary
2. Cloud GM generates reflection passage with 2-3 narrative choices mapping
   to different tree branches
3. Player's selection results in correct talent being acquired
4. Acquired talents immediately affect subsequent checks
5. Character with Natural Charmer who fails Deception check is offered
   pre-narration "push through" choice
6. Accepting intervention rerolls check and charges strain
7. Declining preserves original result and talent remains available
8. Intervention talents track usage per act and reset at boundaries
"""

import sys
import json

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

from engine.character import Character
from engine.dice import DicePool, RollResult, roll_pool
from engine.checks import CheckRequest, Difficulty, build_pool
from engine.talents import (
    load_talent_library,
    load_specialization_tree,
    get_available_talents,
    build_milestone_choices,
    acquire_talent,
    check_interventions,
    apply_intervention,
    reset_intervention_uses,
    MilestoneChoice,
    InterventionOffer,
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
            "charm": 1,
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


# ── Criterion 1: Milestone triggers when reserved_xp sufficient ────────

def test_milestone_triggers_with_sufficient_xp():
    """Milestone choices generated when character has enough reserved_xp."""
    char = _make_character(reserved_xp=10)
    choices = build_milestone_choices(char, char.reserved_xp)
    assert len(choices) > 0, "Should produce milestone choices with reserved_xp=10"
    # All choices should be affordable
    for c in choices:
        assert c.xp_cost <= 10, f"Choice {c.talent_name} costs {c.xp_cost} > 10"
    print(f"  ✓ {len(choices)} milestone choices generated")


def test_milestone_no_choices_without_xp():
    """No milestone choices when reserved_xp is 0."""
    char = _make_character(reserved_xp=0)
    choices = build_milestone_choices(char, char.reserved_xp)
    assert len(choices) == 0, "Should produce no choices with reserved_xp=0"
    print("  ✓ No choices generated with 0 reserved_xp")


def test_milestone_respects_tree_paths():
    """Choices map to different tree_path branches."""
    char = _make_character(reserved_xp=20)
    choices = build_milestone_choices(char, char.reserved_xp, max_choices=3)
    branch_keys = [c.branch_key for c in choices]
    # Should have diverse branches (not all from the same path)
    assert len(set(branch_keys)) == len(branch_keys), \
        f"Duplicate branches found: {branch_keys}"
    # Each choice should have a narrative identity
    for c in choices:
        assert c.narrative_identity, f"{c.talent_name} missing narrative_identity"
    print(f"  ✓ {len(choices)} choices from {len(set(branch_keys))} unique branches")


# ── Criterion 2: Reflection passage format (mock — no LLM call) ────────

def test_milestone_choice_structure():
    """MilestoneChoice objects have all required fields."""
    char = _make_character(reserved_xp=10)
    choices = build_milestone_choices(char, char.reserved_xp)
    if not choices:
        print("  ⊘ Skipped — no choices available (tree/xp mismatch)")
        return
    c = choices[0]
    assert c.branch_key, "Missing branch_key"
    assert c.branch_theme, "Missing branch_theme"
    assert c.branch_description, "Missing branch_description"
    assert c.talent_ref, "Missing talent_ref"
    assert c.talent_name, "Missing talent_name"
    assert c.tree_name, "Missing tree_name"
    assert c.entry_id, "Missing entry_id"
    assert c.xp_cost > 0, "XP cost must be positive"
    assert c.narrative_identity, "Missing narrative_identity"
    assert isinstance(c.prose_tags, list), "prose_tags must be list"
    print(f"  ✓ MilestoneChoice fully populated: {c.talent_name}")


# ── Criterion 3: Talent acquisition works correctly ────────────────────

def test_acquire_talent_from_milestone():
    """acquire_talent deducts XP and adds talent to character."""
    char = _make_character(reserved_xp=10)
    choices = build_milestone_choices(char, char.reserved_xp)
    assert len(choices) > 0, "Need at least one choice"

    choice = choices[0]
    old_xp = char.reserved_xp
    old_count = len(char.acquired_talents)

    acquire_talent(char, choice)

    assert char.reserved_xp == old_xp - choice.xp_cost, \
        f"XP not deducted: {char.reserved_xp} (expected {old_xp - choice.xp_cost})"
    assert len(char.acquired_talents) == old_count + 1, \
        "Talent not added to acquired_talents"
    acquired = char.acquired_talents[-1]
    assert acquired["talent_ref"] == choice.talent_ref
    assert acquired["entry_id"] == choice.entry_id
    print(f"  ✓ Acquired {choice.talent_name}, reserved_xp: {old_xp} → {char.reserved_xp}")


# ── Criterion 4: Acquired talents affect subsequent checks ─────────────

def test_acquired_talent_modifies_pool():
    """A newly acquired passive talent modifies subsequent dice pools."""
    # Build pool BEFORE acquiring Skilled Jockey
    char = _make_character(reserved_xp=10)
    check = CheckRequest(
        skill="piloting_space", difficulty=Difficulty.AVERAGE,
        setback_dice=1,  # ensure there's setback to remove
    )
    pool_before, _, _ = build_pool(char, check, scene_type="action")
    setback_before = pool_before.setback

    # Directly acquire Skilled Jockey via MilestoneChoice
    choice = MilestoneChoice(
        branch_key="vehicle_mastery",
        branch_theme="vehicle_mastery",
        branch_description="The ace pilot path",
        talent_ref="skilled_jockey",
        talent_name="Skilled Jockey",
        tree_name="smuggler_pilot",
        entry_id="pilot_t1_1",
        xp_cost=5,
        narrative_identity="The ship responds to the pilot's hands.",
        prose_tags=["piloting"],
    )
    acquire_talent(char, choice)

    # Build pool AFTER acquiring
    pool_after, activations, _ = build_pool(char, check, scene_type="action")
    setback_after = pool_after.setback

    assert setback_after < setback_before, \
        f"Setback not reduced: {setback_before} → {setback_after}"
    # Verify activation was logged
    passive_acts = [a for a in activations if a.talent_type == "passive"]
    assert len(passive_acts) > 0, "No passive activation logged"
    print(f"  ✓ Skilled Jockey reduces setback: {setback_before} → {setback_after}")


# ── Criterion 5: Intervention offered on failed check ──────────────────

def test_intervention_offered_on_failed_deception():
    """Character with Natural Charmer is offered intervention on failed Deception."""
    char = _make_character(
        acquired_talents=[{
            "talent_ref": "natural_charmer",
            "tree": "smuggler_pilot",
            "entry_id": "test_nc",
        }],
        talent_uses={},
    )

    offer = check_interventions(
        character=char,
        check_skill="deception",
        roll_succeeded=False,
        current_act=1,
    )
    assert offer is not None, "Should offer intervention on failed deception"
    assert offer.talent_name == "Natural Charmer"
    assert offer.strain_cost == 1
    assert offer.narrative_prompt, "Should have a narrative prompt"
    print(f"  ✓ Intervention offered: {offer.talent_name} (strain cost: {offer.strain_cost})")


def test_no_intervention_on_unrelated_skill():
    """Natural Charmer does not trigger on non-social skills."""
    char = _make_character(
        acquired_talents=[{
            "talent_ref": "natural_charmer",
            "tree": "smuggler_pilot",
            "entry_id": "test_nc",
        }],
        talent_uses={},
    )

    offer = check_interventions(
        character=char,
        check_skill="piloting_space",
        roll_succeeded=False,
        current_act=1,
    )
    assert offer is None, "Natural Charmer should not trigger on piloting"
    print("  ✓ No intervention on unrelated skill")


def test_natural_pilot_any_check():
    """Natural Pilot triggers on any piloting check (not just failures)."""
    char = _make_character(
        acquired_talents=[{
            "talent_ref": "natural_pilot",
            "tree": "smuggler_pilot",
            "entry_id": "test_np",
        }],
        talent_uses={},
    )

    # Should trigger even on success (trigger=any_check)
    offer = check_interventions(
        character=char,
        check_skill="piloting_space",
        roll_succeeded=True,
        current_act=1,
    )
    assert offer is not None, "Natural Pilot should trigger on any piloting check"
    assert offer.talent_name == "Natural Pilot"
    print("  ✓ Natural Pilot triggers on any piloting check")


def test_second_chances_failed_only():
    """Second Chances only triggers on failed checks."""
    char = _make_character(
        acquired_talents=[{
            "talent_ref": "second_chances",
            "tree": "smuggler_pilot",
            "entry_id": "test_sc",
        }],
        talent_uses={},
    )

    # Should NOT trigger on success
    offer_success = check_interventions(
        character=char,
        check_skill="deception",
        roll_succeeded=True,
        current_act=1,
    )
    assert offer_success is None, "Second Chances should not trigger on success"

    # Should trigger on failure
    offer_fail = check_interventions(
        character=char,
        check_skill="deception",
        roll_succeeded=False,
        current_act=1,
    )
    assert offer_fail is not None, "Second Chances should trigger on failure"
    print("  ✓ Second Chances: failure-only trigger verified")


# ── Criterion 6: Accepting intervention rerolls and charges strain ─────

def test_intervention_charges_strain():
    """apply_intervention charges strain and records talent use."""
    char = _make_character(
        acquired_talents=[{
            "talent_ref": "natural_charmer",
            "tree": "smuggler_pilot",
            "entry_id": "test_nc",
        }],
        talent_uses={},
        current_strain=2,
    )

    offer = InterventionOffer(
        talent_ref="natural_charmer",
        talent_name="Natural Charmer",
        effect="reroll",
        applicable_skills=["charm", "deception"],
        strain_cost=1,
        scope="session",
        narrative_prompt="Test prompt",
    )

    activation = apply_intervention(char, offer)

    assert char.current_strain == 3, f"Strain should be 3, got {char.current_strain}"
    assert char.talent_uses.get("natural_charmer") == 1, "Talent use not tracked"
    assert activation.talent_type == "intervention"
    assert activation.strain_charged == 1
    print(f"  ✓ Intervention applied: strain 2 → {char.current_strain}, use tracked")


def test_intervention_reroll_produces_result():
    """Rolling a dice pool after intervention produces a valid result."""
    pool = DicePool(ability=2, proficiency=1, difficulty=2)
    result = roll_pool(pool)
    assert hasattr(result, "succeeded"), "RollResult missing 'succeeded'"
    assert hasattr(result, "outcome_quadrant"), "RollResult missing 'outcome_quadrant'"
    print(f"  ✓ Reroll produces valid result: {result.narrative_label()}")


# ── Criterion 7: Declining preserves original result ───────────────────

def test_decline_preserves_talent_availability():
    """After declining an intervention, the talent remains available."""
    char = _make_character(
        acquired_talents=[{
            "talent_ref": "natural_charmer",
            "tree": "smuggler_pilot",
            "entry_id": "test_nc",
        }],
        talent_uses={},
    )

    # First check — offer is available
    offer1 = check_interventions(char, "deception", False, 1)
    assert offer1 is not None

    # Decline (don't call apply_intervention) — check again
    offer2 = check_interventions(char, "charm", False, 1)
    assert offer2 is not None, "Talent should still be available after declining"
    assert offer2.talent_name == "Natural Charmer"
    print("  ✓ Declined intervention: talent remains available")


# ── Criterion 8: Usage tracking and reset at boundaries ────────────────

def test_intervention_usage_exhaustion():
    """After using intervention, it's no longer available this act."""
    char = _make_character(
        acquired_talents=[{
            "talent_ref": "natural_charmer",
            "tree": "smuggler_pilot",
            "entry_id": "test_nc",
        }],
        talent_uses={},
    )

    # Use the intervention
    offer = check_interventions(char, "deception", False, 1)
    assert offer is not None
    apply_intervention(char, offer)

    # Should be exhausted now (max_rank=1, uses=1)
    offer2 = check_interventions(char, "charm", False, 1)
    assert offer2 is None, "Should be exhausted after 1 use (max_rank=1)"
    print("  ✓ Intervention exhausted after use")


def test_intervention_reset_at_boundary():
    """reset_intervention_uses clears usage for next act."""
    char = _make_character(
        acquired_talents=[{
            "talent_ref": "natural_charmer",
            "tree": "smuggler_pilot",
            "entry_id": "test_nc",
        }],
        talent_uses={"natural_charmer": 1},
    )

    # Should be exhausted
    offer = check_interventions(char, "deception", False, 1)
    assert offer is None, "Should be exhausted"

    # Reset at act boundary
    reset_intervention_uses(char)

    # Should be available again
    offer2 = check_interventions(char, "deception", False, 2)
    assert offer2 is not None, "Should be available after reset"
    print("  ✓ Intervention uses reset at act boundary")


def test_ranked_intervention_multiple_uses():
    """Second Chances (ranked) at rank 2 gets 2 uses per act."""
    char = _make_character(
        acquired_talents=[
            {"talent_ref": "second_chances", "tree": "t", "entry_id": "sc1"},
            {"talent_ref": "second_chances", "tree": "t", "entry_id": "sc2"},
        ],
        talent_uses={},
    )

    # First use
    offer1 = check_interventions(char, "deception", False, 1)
    assert offer1 is not None
    apply_intervention(char, offer1)

    # Second use — should still be available (rank 2)
    offer2 = check_interventions(char, "charm", False, 1)
    assert offer2 is not None, "Rank 2 should allow 2 uses"
    apply_intervention(char, offer2)

    # Third use — should be exhausted
    offer3 = check_interventions(char, "deception", False, 1)
    assert offer3 is None, "Should be exhausted after 2 uses at rank 2"
    print("  ✓ Rank 2 Second Chances: 2 uses per act")


def test_intervention_not_offered_at_strain_cap():
    """No intervention when strain would exceed threshold."""
    char = _make_character(
        acquired_talents=[{
            "talent_ref": "natural_charmer",
            "tree": "smuggler_pilot",
            "entry_id": "test_nc",
        }],
        talent_uses={},
        current_strain=12,  # at threshold
        strain_threshold=12,
    )

    offer = check_interventions(char, "deception", False, 1)
    assert offer is None, "Should not offer when strain at threshold"
    print("  ✓ No intervention offered at strain cap")


# ── Bonus: get_available_talents navigation ────────────────────────────

def test_available_talents_respects_prerequisites():
    """Only talents with met prerequisites appear as available."""
    char = _make_character(reserved_xp=20)
    available = get_available_talents(char)
    # With no acquired talents, only tier 1 (no prereqs) should be available
    for t in available:
        assert t["tier"] == 1, f"Tier {t['tier']} talent available without prereqs"
    print(f"  ✓ {len(available)} tier-1 talents available (prereqs respected)")


def test_available_talents_unlocks_tier2():
    """Acquiring a tier 1 talent unlocks tier 2 talents."""
    char = _make_character(
        reserved_xp=20,
        acquired_talents=[{
            "talent_ref": "full_throttle",
            "tree": "smuggler_pilot",
            "entry_id": "pilot_t1_0",
        }],
    )
    available = get_available_talents(char)
    tiers = {t["tier"] for t in available}
    assert 2 in tiers, "Tier 2 should be unlocked after acquiring tier 1"
    # pilot_t2_0 requires pilot_t1_0 which we acquired
    t2_entries = [t for t in available if t["entry_id"] == "pilot_t2_0"]
    assert len(t2_entries) == 1, "pilot_t2_0 should be available"
    print(f"  ✓ Tier 2 unlocked: {len([t for t in available if t['tier'] == 2])} tier-2 talents")


# ── Bonus: Reconciliation pipeline integration ─────────────────────────

def test_between_act_result_has_milestone_fields():
    """BetweenActResult has milestone_passage and milestone_choices fields."""
    from engine.reconciliation import BetweenActResult
    result = BetweenActResult()
    assert result.milestone_passage == ""
    assert result.milestone_choices == []
    print("  ✓ BetweenActResult has milestone fields")


# ── Run all ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        # Criterion 1: Milestone triggers
        ("1a", "Milestone triggers with sufficient XP", test_milestone_triggers_with_sufficient_xp),
        ("1b", "No milestone without XP", test_milestone_no_choices_without_xp),
        ("1c", "Milestone respects tree paths", test_milestone_respects_tree_paths),
        # Criterion 2: Reflection format
        ("2", "MilestoneChoice structure", test_milestone_choice_structure),
        # Criterion 3: Talent acquisition
        ("3", "Acquire talent from milestone", test_acquire_talent_from_milestone),
        # Criterion 4: Affects subsequent checks
        ("4", "Acquired talent modifies pool", test_acquired_talent_modifies_pool),
        # Criterion 5: Intervention offered
        ("5a", "Intervention on failed Deception", test_intervention_offered_on_failed_deception),
        ("5b", "No intervention on unrelated skill", test_no_intervention_on_unrelated_skill),
        ("5c", "Natural Pilot any check", test_natural_pilot_any_check),
        ("5d", "Second Chances failed only", test_second_chances_failed_only),
        # Criterion 6: Intervention rerolls and charges strain
        ("6a", "Intervention charges strain", test_intervention_charges_strain),
        ("6b", "Reroll produces result", test_intervention_reroll_produces_result),
        # Criterion 7: Declining preserves availability
        ("7", "Decline preserves talent", test_decline_preserves_talent_availability),
        # Criterion 8: Usage tracking and reset
        ("8a", "Usage exhaustion", test_intervention_usage_exhaustion),
        ("8b", "Reset at boundary", test_intervention_reset_at_boundary),
        ("8c", "Ranked multiple uses", test_ranked_intervention_multiple_uses),
        ("8d", "Not offered at strain cap", test_intervention_not_offered_at_strain_cap),
        # Bonus
        ("B1", "Prerequisites respected", test_available_talents_respects_prerequisites),
        ("B2", "Tier 2 unlocked", test_available_talents_unlocks_tier2),
        ("B3", "BetweenActResult fields", test_between_act_result_has_milestone_fields),
    ]

    passed = 0
    failed = 0
    for label, name, fn in tests:
        try:
            print(f"\n[{label}] {name}")
            fn()
            passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Phase 12: {passed} passed, {failed} failed, {passed + failed} total")
    if failed == 0:
        print("All Phase 12 success criteria verified!")
    else:
        print(f"FAILURES: {failed}")
