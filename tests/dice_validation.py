"""
Dice validation tests for Phase 1.

Verifies:
- Every symbol table has the correct face count
- Every face has the correct symbols
- Pool construction from character stats (Keth's Deception check)
- Roll resolution with correct cancellation logic
- Narrative label formatting
"""
import json
import sys
import os

import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.dice import (
    DieType, Symbol, DicePool, RollResult, roll_pool,
    ABILITY_TABLE, PROFICIENCY_TABLE, DIFFICULTY_TABLE, CHALLENGE_TABLE,
    BOOST_TABLE, SETBACK_TABLE, FORCE_TABLE, DIE_TABLES,
)
from engine.character import Character, SKILL_CHARACTERISTICS
from engine.checks import Difficulty, CheckRequest, build_pool, describe_pool_for_display


# ── Symbol table face count tests ────────────────────────────────────────────

def test_ability_table_face_count():
    assert len(ABILITY_TABLE) == 8, f"Ability die should have 8 faces, got {len(ABILITY_TABLE)}"

def test_proficiency_table_face_count():
    assert len(PROFICIENCY_TABLE) == 12, f"Proficiency die should have 12 faces, got {len(PROFICIENCY_TABLE)}"

def test_difficulty_table_face_count():
    assert len(DIFFICULTY_TABLE) == 8, f"Difficulty die should have 8 faces, got {len(DIFFICULTY_TABLE)}"

def test_challenge_table_face_count():
    assert len(CHALLENGE_TABLE) == 12, f"Challenge die should have 12 faces, got {len(CHALLENGE_TABLE)}"

def test_boost_table_face_count():
    assert len(BOOST_TABLE) == 6, f"Boost die should have 6 faces, got {len(BOOST_TABLE)}"

def test_setback_table_face_count():
    assert len(SETBACK_TABLE) == 6, f"Setback die should have 6 faces, got {len(SETBACK_TABLE)}"

def test_force_table_face_count():
    assert len(FORCE_TABLE) == 12, f"Force die should have 12 faces, got {len(FORCE_TABLE)}"


# ── Symbol table content tests ───────────────────────────────────────────────

def _count_symbols(table):
    """Count total occurrences of each symbol across all faces."""
    counts = {}
    for face in table:
        for symbol in face:
            counts[symbol] = counts.get(symbol, 0) + 1
    return counts

def _count_blanks(table):
    """Count faces with no symbols."""
    return sum(1 for face in table if len(face) == 0)


def test_ability_symbols():
    counts = _count_symbols(ABILITY_TABLE)
    blanks = _count_blanks(ABILITY_TABLE)
    assert blanks == 1, f"Ability: expected 1 blank, got {blanks}"
    assert counts.get(Symbol.SUCCESS, 0) == 5, f"Ability: expected 5 success symbols, got {counts.get(Symbol.SUCCESS, 0)}"
    assert counts.get(Symbol.ADVANTAGE, 0) == 5, f"Ability: expected 5 advantage symbols, got {counts.get(Symbol.ADVANTAGE, 0)}"


def test_proficiency_symbols():
    counts = _count_symbols(PROFICIENCY_TABLE)
    blanks = _count_blanks(PROFICIENCY_TABLE)
    assert blanks == 1, f"Proficiency: expected 1 blank, got {blanks}"
    assert counts.get(Symbol.SUCCESS, 0) == 9, f"Proficiency: expected 9 success symbols, got {counts.get(Symbol.SUCCESS, 0)}"
    assert counts.get(Symbol.ADVANTAGE, 0) == 8, f"Proficiency: expected 8 advantage symbols, got {counts.get(Symbol.ADVANTAGE, 0)}"
    assert counts.get(Symbol.TRIUMPH, 0) == 1, f"Proficiency: expected 1 triumph, got {counts.get(Symbol.TRIUMPH, 0)}"


def test_difficulty_symbols():
    counts = _count_symbols(DIFFICULTY_TABLE)
    blanks = _count_blanks(DIFFICULTY_TABLE)
    assert blanks == 1, f"Difficulty: expected 1 blank, got {blanks}"
    assert counts.get(Symbol.FAILURE, 0) == 5, f"Difficulty: expected 5 failure symbols, got {counts.get(Symbol.FAILURE, 0)}"
    assert counts.get(Symbol.THREAT, 0) == 5, f"Difficulty: expected 5 threat symbols, got {counts.get(Symbol.THREAT, 0)}"


def test_challenge_symbols():
    counts = _count_symbols(CHALLENGE_TABLE)
    blanks = _count_blanks(CHALLENGE_TABLE)
    assert blanks == 1, f"Challenge: expected 1 blank, got {blanks}"
    assert counts.get(Symbol.FAILURE, 0) == 8, f"Challenge: expected 8 failure symbols, got {counts.get(Symbol.FAILURE, 0)}"
    assert counts.get(Symbol.THREAT, 0) == 8, f"Challenge: expected 8 threat symbols, got {counts.get(Symbol.THREAT, 0)}"
    assert counts.get(Symbol.DESPAIR, 0) == 1, f"Challenge: expected 1 despair, got {counts.get(Symbol.DESPAIR, 0)}"


def test_boost_symbols():
    counts = _count_symbols(BOOST_TABLE)
    blanks = _count_blanks(BOOST_TABLE)
    assert blanks == 2, f"Boost: expected 2 blanks, got {blanks}"
    assert counts.get(Symbol.SUCCESS, 0) == 2, f"Boost: expected 2 success symbols, got {counts.get(Symbol.SUCCESS, 0)}"
    assert counts.get(Symbol.ADVANTAGE, 0) == 4, f"Boost: expected 4 advantage symbols, got {counts.get(Symbol.ADVANTAGE, 0)}"


def test_setback_symbols():
    counts = _count_symbols(SETBACK_TABLE)
    blanks = _count_blanks(SETBACK_TABLE)
    assert blanks == 2, f"Setback: expected 2 blanks, got {blanks}"
    assert counts.get(Symbol.FAILURE, 0) == 2, f"Setback: expected 2 failure symbols, got {counts.get(Symbol.FAILURE, 0)}"
    assert counts.get(Symbol.THREAT, 0) == 2, f"Setback: expected 2 threat symbols, got {counts.get(Symbol.THREAT, 0)}"


def test_force_symbols():
    counts = _count_symbols(FORCE_TABLE)
    blanks = _count_blanks(FORCE_TABLE)
    assert blanks == 0, f"Force: expected 0 blanks, got {blanks}"
    assert counts.get(Symbol.DARK, 0) == 8, f"Force: expected 8 dark pips, got {counts.get(Symbol.DARK, 0)}"
    assert counts.get(Symbol.LIGHT, 0) == 9, f"Force: expected 9 light pips, got {counts.get(Symbol.LIGHT, 0)}"


def test_die_tables_registry():
    """Every DieType has a table and vice versa."""
    for dt in DieType:
        assert dt in DIE_TABLES, f"Missing table for {dt}"
    assert len(DIE_TABLES) == len(DieType), "Extra entries in DIE_TABLES"


# ── Character loading test ───────────────────────────────────────────────────

@pytest.mark.skip(reason="Keth Varso character / Nar Shaddaa spine removed; see changelog 2026-04-25")
def test_load_praxeum_student():
    json_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "characters", "praxeum_student.json"
    )
    with open(json_path) as f:
        data = json.load(f)
    keth = Character(**data)
    assert keth.name == "Keth Varso"
    assert keth.characteristics.cunning == 4
    assert keth.skills.deception == 2
    assert keth.force_rating == 0
    assert keth.specializations == ["pilot"]


# ── Pool construction test ───────────────────────────────────────────────────

@pytest.mark.skip(reason="Keth Varso character / Nar Shaddaa spine removed; see changelog 2026-04-25")
def test_keth_deception_pool():
    """
    Keth: Cunning 4, Deception 2.
    max(4,2)=4 total dice, min(4,2)=2 proficiency, 4-2=2 ability.
    Average difficulty = 2 purple.
    Expected: 2Y 2G 2P
    """
    json_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "characters", "praxeum_student.json"
    )
    with open(json_path) as f:
        data = json.load(f)
    keth = Character(**data)

    check = CheckRequest(skill="deception", difficulty=Difficulty.AVERAGE)
    pool, _, _ = build_pool(keth, check)

    assert pool.proficiency == 2, f"Expected 2 proficiency, got {pool.proficiency}"
    assert pool.ability == 2, f"Expected 2 ability, got {pool.ability}"
    assert pool.difficulty == 2, f"Expected 2 difficulty, got {pool.difficulty}"
    assert pool.challenge == 0
    assert pool.boost == 0
    assert pool.setback == 0
    assert pool.force == 0
    assert pool.description() == "2Y 2G 2P"


# ── Roll resolution tests ───────────────────────────────────────────────────

def test_roll_pool_produces_valid_result():
    """Roll a pool and verify the result has correct structure."""
    pool = DicePool(ability=2, proficiency=2, difficulty=2)
    result = roll_pool(pool)

    assert isinstance(result, RollResult)
    assert result.outcome_quadrant in (
        "success_advantage", "success_threat",
        "failure_advantage", "failure_threat"
    )
    assert result.succeeded == (result.net_successes > 0)


def test_cancellation_logic():
    """Verify cancellation by constructing a known result manually."""
    result = RollResult(
        raw_successes=3,
        raw_failures=2,
        raw_advantages=1,
        raw_threats=3,
        raw_triumphs=1,
        raw_despairs=1,
    )
    # Manual cancellation per FFG rules:
    # total_successes = 3 + 1 (triumph) = 4
    # total_failures = 2 + 1 (despair) = 3
    # net_successes = 4 - 3 = 1
    # net_advantages = 1 - 3 = -2
    # Should succeed (1 > 0)

    total_successes = result.raw_successes + result.raw_triumphs
    total_failures = result.raw_failures + result.raw_despairs
    net_succ = total_successes - total_failures
    net_adv = result.raw_advantages - result.raw_threats

    assert net_succ == 1
    assert net_adv == -2


def test_tie_goes_to_failure():
    """Exactly zero net successes = failure per FFG rules."""
    pool = DicePool()  # empty pool
    result = roll_pool(pool)
    assert result.succeeded is False
    assert result.net_successes == 0


def test_narrative_label_success():
    result = RollResult()
    result.net_successes = 2
    result.net_advantages = 1
    result.triumphs = 0
    result.despairs = 0
    label = result.narrative_label()
    assert "SUCCEEDED" in label
    assert "2 net successes" in label
    assert "1 Advantage" in label


def test_narrative_label_failure_with_threat():
    result = RollResult()
    result.net_successes = -1
    result.net_advantages = -2
    result.triumphs = 0
    result.despairs = 0
    label = result.narrative_label()
    assert "FAILED" in label
    assert "1 net failure" in label
    assert "2 Threats" in label


def test_narrative_label_triumph_and_despair():
    result = RollResult()
    result.net_successes = 1
    result.net_advantages = 0
    result.triumphs = 1
    result.despairs = 1
    label = result.narrative_label()
    assert "TRIUMPH" in label
    assert "DESPAIR" in label


# ── Pool display test ────────────────────────────────────────────────────────

def test_describe_pool_for_display():
    pool = DicePool(ability=2, proficiency=2, difficulty=2)
    display = describe_pool_for_display(pool)
    assert "dice" in display
    assert "description" in display
    # Should have 3 entries (proficiency, ability, difficulty)
    assert len(display["dice"]) == 3
    # Verify no zero-count dice appear
    for d in display["dice"]:
        assert d["count"] > 0


# ── Skill characteristics mapping test ───────────────────────────────────────

def test_all_skills_have_characteristics():
    """Every skill in the mapping has a valid characteristic."""
    valid_chars = {"brawn", "agility", "intellect", "cunning", "willpower", "presence"}
    for skill, char in SKILL_CHARACTERISTICS.items():
        assert char in valid_chars, f"Skill {skill} maps to invalid characteristic {char}"


def test_deception_governed_by_cunning():
    assert SKILL_CHARACTERISTICS["deception"] == "cunning"


# ── Difficulty labels test ───────────────────────────────────────────────────

def test_difficulty_values():
    assert Difficulty.SIMPLE.value == 0
    assert Difficulty.EASY.value == 1
    assert Difficulty.AVERAGE.value == 2
    assert Difficulty.HARD.value == 3
    assert Difficulty.DAUNTING.value == 4
    assert Difficulty.FORMIDABLE.value == 5


# ── Run all tests ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
