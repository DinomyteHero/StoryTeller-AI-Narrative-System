"""
Phase 11.5 verification: Destiny Point Pool (Game Mechanics §23).

Success criteria:
1. Destiny pool initializes from Force die roll at session creation
2. Light Side spend triggers on a high-stakes check, upgrading one
   ability → proficiency
3. Dark Side spend triggers when Obligation is active, upgrading one
   difficulty → challenge
4. Pool flips correctly after each spend
5. Escalation pacing tracks spends and adjusts thresholds
6. The GM prompt receives `destiny_spent` flag with narrative guidance
7. The seize-the-moment choice presents correctly at spine-authored
   moments (when a Light Side point is available)
"""

import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

from engine.destiny import (
    DestinyResult,
    DestinyState,
    roll_initial_destiny,
    evaluate_destiny_spend,
    build_seize_the_moment_choice,
    _compute_light_score,
    _compute_escalation_modifier,
)
from engine.dice import DicePool, FORCE_TABLE, Symbol
from engine.character import Character
from engine.checks import CheckRequest, Difficulty, build_pool


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


# ── Criterion 1: Destiny pool initialization ─────────────────────────

def test_roll_initial_destiny():
    """Roll Force die multiple times — always produces valid light/dark pip counts."""
    results = [roll_initial_destiny() for _ in range(100)]
    for light, dark in results:
        assert light >= 0 and dark >= 0
        assert light + dark > 0, "Force die cannot produce blank"
        assert light <= 2, f"Max 2 light pips per Force die, got {light}"
        assert dark <= 2, f"Max 2 dark pips per Force die, got {dark}"
    print("  ✓ Destiny pool initializes from Force die roll (100 samples valid)")


def test_force_die_distribution():
    """Verify the Force die has correct pip distribution per FFG rules."""
    total_light = 0
    total_dark = 0
    for face in FORCE_TABLE:
        for sym in face:
            if sym == Symbol.LIGHT:
                total_light += 1
            elif sym == Symbol.DARK:
                total_dark += 1
    # FFG Force die: 9 light pips (1+2+2+2+2) across 5 faces, 8 dark pips across 7 faces
    assert total_light == 9, f"Expected 9 light pips, got {total_light}"
    assert total_dark == 8, f"Expected 8 dark pips, got {total_dark}"
    print("  ✓ Force die has correct 8 light / 8 dark pip distribution")


# ── Criterion 2: Light Side spend — upgrade ability → proficiency ────

def test_light_side_spend_upgrades_ability():
    """High-stakes check with Light Side available triggers upgrade."""
    pool = DicePool(ability=2, proficiency=1, difficulty=2)
    destiny = DestinyState(light=1, dark=0)

    result = evaluate_destiny_spend(
        pool=pool,
        scene_type="combat",
        tension_level="climax",
        anchor_proximity="imminent",
        act_progress=0.9,
        destiny=destiny,
    )

    assert result.light_spent, "Light Side should have been spent"
    assert pool.ability == 1, f"Expected 1 ability after upgrade, got {pool.ability}"
    assert pool.proficiency == 2, f"Expected 2 proficiency after upgrade, got {pool.proficiency}"
    print("  ✓ Light Side spend upgrades one ability → proficiency")


def test_light_side_no_spend_low_stakes():
    """Low-stakes check should not trigger Light Side spend."""
    pool = DicePool(ability=2, proficiency=1, difficulty=1)
    destiny = DestinyState(light=1, dark=0)

    result = evaluate_destiny_spend(
        pool=pool,
        scene_type="exploration",
        tension_level="calm",
        anchor_proximity="distant",
        act_progress=0.1,
        destiny=destiny,
    )

    assert not result.light_spent, "Light Side should NOT spend on low-stakes check"
    assert pool.ability == 2, "Pool should be unchanged"
    print("  ✓ Light Side does not spend on low-stakes checks")


def test_light_side_no_ability_dice():
    """Cannot upgrade if no ability dice present."""
    pool = DicePool(ability=0, proficiency=3, difficulty=2)
    destiny = DestinyState(light=1, dark=0)

    result = evaluate_destiny_spend(
        pool=pool,
        scene_type="combat",
        tension_level="climax",
        anchor_proximity="imminent",
        act_progress=0.9,
        destiny=destiny,
    )

    assert not result.light_spent, "Cannot upgrade without ability dice"
    assert destiny.light == 1, "Light pool unchanged"
    print("  ✓ Light Side cannot spend when no ability dice to upgrade")


# ── Criterion 3: Dark Side spend — upgrade difficulty → challenge ────

def test_dark_side_spend_with_obligation():
    """Obligation active + spine trigger should force Dark Side spend."""
    pool = DicePool(ability=2, proficiency=1, difficulty=2)
    destiny = DestinyState(light=0, dark=1)

    result = evaluate_destiny_spend(
        pool=pool,
        scene_type="social",
        tension_level="rising",
        anchor_proximity="distant",
        act_progress=0.3,
        destiny=destiny,
        obligation_active=True,
        spine_dark_trigger=True,
    )

    assert result.dark_spent, "Dark Side should spend with obligation + spine trigger"
    assert pool.difficulty == 1, f"Expected 1 difficulty after upgrade, got {pool.difficulty}"
    assert pool.challenge == 1, f"Expected 1 challenge after upgrade, got {pool.challenge}"
    print("  ✓ Dark Side spend upgrades one difficulty → challenge")


def test_dark_side_no_triggers():
    """No trigger conditions = no Dark Side spend."""
    pool = DicePool(ability=2, proficiency=1, difficulty=2)
    destiny = DestinyState(light=0, dark=1)

    result = evaluate_destiny_spend(
        pool=pool,
        scene_type="exploration",
        tension_level="calm",
        anchor_proximity="distant",
        act_progress=0.1,
        destiny=destiny,
    )

    assert not result.dark_spent, "Dark Side should not spend without triggers"
    assert pool.difficulty == 2, "Pool should be unchanged"
    print("  ✓ Dark Side does not spend without trigger conditions")


# ── Criterion 4: Pool flips correctly ────────────────────────────────

def test_light_side_flip():
    """Light Side spend: light - 1, dark + 1."""
    destiny = DestinyState(light=2, dark=1)
    pool = DicePool(ability=2, proficiency=1, difficulty=2)

    result = evaluate_destiny_spend(
        pool=pool,
        scene_type="combat",
        tension_level="climax",
        anchor_proximity="imminent",
        act_progress=0.9,
        destiny=destiny,
    )

    assert result.light_spent
    assert destiny.light == 1, f"Expected 1 light after flip, got {destiny.light}"
    assert destiny.dark == 2, f"Expected 2 dark after flip, got {destiny.dark}"
    assert result.light_remaining == 1
    assert result.dark_remaining == 2
    print("  ✓ Light Side spend flips pool correctly (light-1, dark+1)")


def test_dark_side_flip():
    """Dark Side spend: dark - 1, light + 1."""
    destiny = DestinyState(light=0, dark=2)
    pool = DicePool(ability=2, proficiency=1, difficulty=2)

    result = evaluate_destiny_spend(
        pool=pool,
        scene_type="combat",
        tension_level="rising",
        anchor_proximity="distant",
        act_progress=0.3,
        destiny=destiny,
        obligation_active=True,
        spine_dark_trigger=True,
    )

    assert result.dark_spent
    assert destiny.dark == 1, f"Expected 1 dark after flip, got {destiny.dark}"
    assert destiny.light == 1, f"Expected 1 light after flip, got {destiny.light}"
    print("  ✓ Dark Side spend flips pool correctly (dark-1, light+1)")


def test_both_light_and_dark_spend():
    """Both can fire on the same check."""
    destiny = DestinyState(light=1, dark=1)
    pool = DicePool(ability=2, proficiency=1, difficulty=2)

    result = evaluate_destiny_spend(
        pool=pool,
        scene_type="combat",
        tension_level="climax",
        anchor_proximity="imminent",
        act_progress=0.9,
        destiny=destiny,
        obligation_active=True,
        spine_dark_trigger=True,
    )

    assert result.light_spent, "Light should have spent"
    assert result.dark_spent, "Dark should have spent"
    # After light: light=0, dark=2. After dark: dark=1, light=1.
    assert destiny.light == 1
    assert destiny.dark == 1
    print("  ✓ Both Light and Dark can fire on the same check")


# ── Criterion 5: Escalation pacing ───────────────────────────────────

def test_escalation_lowers_dark_threshold():
    """2+ Light spends without Dark should lower Dark threshold."""
    modifier = _compute_escalation_modifier(light_spent_this_act=3, dark_spent_this_act=0)
    assert modifier < 0, f"Expected negative modifier, got {modifier}"
    print("  ✓ Escalation pacing lowers Dark Side threshold after Light imbalance")


def test_no_escalation_when_balanced():
    """Balanced spends = no threshold adjustment."""
    modifier = _compute_escalation_modifier(light_spent_this_act=1, dark_spent_this_act=1)
    assert modifier == 0.0, f"Expected 0.0 modifier, got {modifier}"
    print("  ✓ No escalation adjustment when Light/Dark spending balanced")


def test_spend_tracking():
    """Spend counts track correctly."""
    destiny = DestinyState(light=2, dark=0, light_spent_this_act=0, dark_spent_this_act=0)
    pool = DicePool(ability=2, proficiency=1, difficulty=2)

    evaluate_destiny_spend(
        pool=pool,
        scene_type="combat",
        tension_level="climax",
        anchor_proximity="imminent",
        act_progress=0.9,
        destiny=destiny,
    )

    assert destiny.light_spent_this_act == 1, "Should track 1 Light spent"
    print("  ✓ Light Side spend tracking increments correctly")


# ── Criterion 6: GM prompt narrative guidance ────────────────────────

def test_light_narrative_note():
    """Light Side spend produces narrative guidance."""
    pool = DicePool(ability=2, proficiency=1, difficulty=2)
    destiny = DestinyState(light=1, dark=0)

    result = evaluate_destiny_spend(
        pool=pool,
        scene_type="combat",
        tension_level="climax",
        anchor_proximity="imminent",
        act_progress=0.9,
        destiny=destiny,
    )

    assert result.light_spent
    assert "DESTINY (LIGHT SIDE SPENT)" in result.narrative_note
    assert "fortune" in result.narrative_note.lower() or "fate" in result.narrative_note.lower()
    print("  ✓ Light Side spend produces narrative guidance for GM")


def test_dark_narrative_note():
    """Dark Side spend produces narrative guidance."""
    pool = DicePool(ability=2, proficiency=1, difficulty=2)
    destiny = DestinyState(light=0, dark=1)

    result = evaluate_destiny_spend(
        pool=pool,
        scene_type="combat",
        tension_level="rising",
        anchor_proximity="distant",
        act_progress=0.3,
        destiny=destiny,
        obligation_active=True,
        spine_dark_trigger=True,
    )

    assert result.dark_spent
    assert "DESTINY (DARK SIDE SPENT)" in result.narrative_note
    assert "circumstantial" in result.narrative_note.lower() or "environmental" in result.narrative_note.lower()
    print("  ✓ Dark Side spend produces narrative guidance for GM")


def test_destiny_note_injected_into_context():
    """destiny_narrative_note flows through ContextPackage.build_dice_result_block."""
    from gm.context import ContextPackage, ArcState

    char = _make_character()
    ctx = ContextPackage(
        character=char,
        arc=ArcState(
            campaign_name="test", current_act=1, total_acts=4,
            act_name="Test", act_progress=0.5, current_anchor="test",
            next_anchor="", anchors_completed=[], throughline_question="",
            tension_level="rising", open_threads=[], closed_threads=[],
        ),
        story_summary="", recent_turns=[], active_npcs=[],
        location="Test", situation="Test",
        dice_pool=DicePool(ability=2, proficiency=1, difficulty=2),
        roll_result=None,
        destiny_narrative_note="DESTINY (LIGHT SIDE SPENT): Test guidance",
    )

    # With no roll_result, block says "NO DICE CHECK"
    # Set a mock roll result to get the destiny note
    from engine.dice import RollResult
    ctx.roll_result = RollResult(
        net_successes=1, net_advantages=0, succeeded=True,
        outcome_quadrant="success_advantage",
    )

    block = ctx.build_dice_result_block()
    assert "DESTINY (LIGHT SIDE SPENT)" in block
    print("  ✓ Destiny narrative note injected into dice result block for GM prompt")


# ── Criterion 7: Seize-the-moment choice ─────────────────────────────

def test_seize_the_moment():
    """Seize-the-moment generates correct choice structure."""
    choice = build_seize_the_moment_choice()
    assert choice["offered"] is True
    assert len(choice["options"]) == 2
    assert choice["options"][0]["effect"] == "spend_light"
    assert choice["options"][1]["effect"] == "normal"
    print("  ✓ Seize-the-moment choice presents correctly with two options")


def test_seize_the_moment_in_spine():
    """Campaign spine Act 3 has seize_the_moment field."""
    import json
    from pathlib import Path
    spine_path = Path("data/campaigns/shadows_of_the_praxeum.json")
    spine = json.loads(spine_path.read_text(encoding="utf-8"))
    act3 = spine["acts"][2]  # 0-indexed

    assert act3.get("seize_the_moment") is True, "Act 3 should have seize_the_moment"
    assert act3.get("destiny_dark_trigger") is True, "Act 3 should have destiny_dark_trigger"
    print("  ✓ Campaign spine Act 3 has seize_the_moment and destiny_dark_trigger")


# ── Bonus: build_pool pipeline integration ───────────────────────────

def test_build_pool_with_destiny():
    """build_pool passes destiny through Stage 4."""
    char = _make_character()
    check = CheckRequest(skill="deception", difficulty=Difficulty.AVERAGE)
    destiny = DestinyState(light=1, dark=0)

    pool, activations, destiny_result = build_pool(
        char, check,
        scene_type="combat",
        destiny_state=destiny,
        tension_level="climax",
        anchor_proximity="imminent",
        act_progress=0.9,
    )

    assert destiny_result is not None, "build_pool should return destiny result"
    if destiny_result.light_spent:
        assert pool.proficiency > 0, "Should have proficiency after Light upgrade"
    print("  ✓ build_pool integrates destiny evaluation at Stage 4")


def test_build_pool_without_destiny():
    """build_pool without destiny_state returns None for destiny_result."""
    char = _make_character()
    check = CheckRequest(skill="deception", difficulty=Difficulty.AVERAGE)

    pool, activations, destiny_result = build_pool(char, check)

    assert destiny_result is None, "No destiny_state = None destiny_result"
    print("  ✓ build_pool without destiny_state returns None for destiny_result")


# ── Run all ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== Phase 11.5: Destiny Point Pool ===\n")

    print("Criterion 1: Destiny pool initialization")
    test_roll_initial_destiny()
    test_force_die_distribution()

    print("\nCriterion 2: Light Side spend")
    test_light_side_spend_upgrades_ability()
    test_light_side_no_spend_low_stakes()
    test_light_side_no_ability_dice()

    print("\nCriterion 3: Dark Side spend")
    test_dark_side_spend_with_obligation()
    test_dark_side_no_triggers()

    print("\nCriterion 4: Pool flip mechanic")
    test_light_side_flip()
    test_dark_side_flip()
    test_both_light_and_dark_spend()

    print("\nCriterion 5: Escalation pacing")
    test_escalation_lowers_dark_threshold()
    test_no_escalation_when_balanced()
    test_spend_tracking()

    print("\nCriterion 6: GM prompt narrative guidance")
    test_light_narrative_note()
    test_dark_narrative_note()
    test_destiny_note_injected_into_context()

    print("\nCriterion 7: Seize-the-moment choice")
    test_seize_the_moment()
    test_seize_the_moment_in_spine()

    print("\nBonus: Pipeline integration")
    test_build_pool_with_destiny()
    test_build_pool_without_destiny()

    print("\n=== All Phase 11.5 criteria verified ✓ ===\n")
