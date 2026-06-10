"""Freeform archetype + custom-talent engine tests (Phase 2).

Covers:
- Character.species/career as free-form strings (and enum-input coercion).
- Per-character custom_talents resolving through the talent pipeline.
- validate_talent_definition accept/reject matrix, including dice-safety.

Pure Python — no LLM, no API keys.
"""

import pytest

from engine.character import (
    Character, Species, Career,
    species_thresholds, species_start_xp, _label,
)
from engine.dice import DicePool
import engine.talents as T


# ── Freeform identity strings ────────────────────────────────────────

def test_freeform_species_career_strings():
    c = Character(name="Vex", species="kel_dor", career="ex-imperial slicer",
                  archetype_concept="Jaded ex-Imperial slicer")
    assert c.species == "kel_dor"
    assert c.career == "ex-imperial slicer"
    # archetype_concept is the identity shown when set
    assert "Jaded ex-Imperial slicer" in c.narrative_status()


def test_enum_input_is_coerced_to_value():
    """Legacy callers passing Species/Career enum members still work."""
    c = Character(name="T", species=Species.HUMAN, career=Career.SMUGGLER)
    assert c.species == "human"
    assert c.career == "smuggler"


def test_label_helper_handles_str_and_enum():
    assert _label("ex_imperial") == "Ex Imperial"
    assert _label(Species.HUMAN) == "Human"


def test_existing_character_files_load():
    import json
    for fn in ("clovis_beryl", "praxeum_mechanic"):
        d = json.load(open(f"data/characters/{fn}.json", encoding="utf-8"))
        ch = Character.model_validate(d)
        assert isinstance(ch.species, str)
        assert isinstance(ch.career, str)
        # narrative_status must not raise and returns a string
        assert isinstance(ch.narrative_status(), str)


def test_species_tables():
    assert species_thresholds("wookiee") == (14, 8)
    assert species_thresholds("totally_made_up") == (10, 10)
    assert species_start_xp("human") == 110
    assert species_start_xp("totally_made_up") == 100


# ── Custom-talent resolution through the pipeline ────────────────────

def _slicer():
    sig = {
        "slicer_instinct": {
            "name": "Slicer Instinct",
            "talent_type": "passive",
            "ranked": True,
            "max_rank": 2,
            "effects": [{
                "type": "modify_pool",
                "target_skills": ["computers"],
                "modifier": {"boost": 1},
            }],
            "narrative_identity": "Your fingers know the system first.",
            "prose_tags": ["slicing", "instinct", "imperial"],
        }
    }
    return Character(
        name="Vex", species="kel_dor", career="slicer",
        archetype_concept="Jaded ex-Imperial slicer",
        custom_talents=sig, career_skills=["computers"], reserved_xp=30,
        strain_threshold=12, wound_threshold=12,
    )


def test_resolve_talent_defn_prefers_custom():
    c = _slicer()
    defn = T.resolve_talent_defn(c, "slicer_instinct")
    assert defn is not None and defn["name"] == "Slicer Instinct"
    assert T.resolve_talent_defn(c, "does_not_exist") is None


def test_custom_passive_fires_in_pool():
    c = _slicer()
    c.acquired_talents.append({
        "talent_ref": "slicer_instinct", "tree": "freeform",
        "entry_id": "freeform:slicer_instinct",
    })
    pool = DicePool(ability=2, difficulty=2)
    acts = T.apply_passive_modifiers(pool, c, "computers")
    assert pool.boost == 1
    assert any(a.talent_name == "Slicer Instinct" for a in acts)
    # Does NOT fire for an unrelated skill
    pool2 = DicePool(ability=2, difficulty=2)
    T.apply_passive_modifiers(pool2, c, "stealth")
    assert pool2.boost == 0


def test_custom_intervention_offered():
    sig = {
        "last_ditch": {
            "name": "Last Ditch",
            "talent_type": "intervention",
            "ranked": True, "max_rank": 1,
            "effects": [{
                "type": "intervention", "effect": "reroll",
                "trigger": "failed_check", "applicable_skills": ["computers"],
                "strain_cost": 1, "scope": "session",
                "narrative_prompt": "One more try.",
            }],
            "narrative_identity": "You never accept the first failure.",
            "prose_tags": ["grit"],
        }
    }
    c = Character(name="Vex", species="human", career="slicer",
                  custom_talents=sig, strain_threshold=12, current_strain=0)
    c.acquired_talents.append({
        "talent_ref": "last_ditch", "tree": "freeform",
        "entry_id": "freeform:last_ditch",
    })
    offer = T.check_interventions(c, "computers", roll_succeeded=False)
    assert offer is not None and offer.talent_ref == "last_ditch"


# ── Freeform milestone choices ───────────────────────────────────────

def test_freeform_milestone_choices_rank_signature_first():
    c = _slicer()
    choices = T.build_milestone_choices(c, reserved_xp=30, max_choices=3)
    assert choices, "freeform character should get milestone choices"
    # signature talent (custom + concept affinity) ranks first
    assert choices[0].talent_ref == "slicer_instinct"
    assert all(ch.tree_name == "freeform" for ch in choices)


def test_freeform_acquire_records_freeform_tree():
    c = _slicer()
    choices = T.build_milestone_choices(c, reserved_xp=30, max_choices=3)
    pick = next(ch for ch in choices if ch.talent_ref == "slicer_instinct")
    T.acquire_talent(c, pick)
    rec = c.acquired_talents[-1]
    assert rec["tree"] == "freeform"
    assert rec["entry_id"] == "freeform:slicer_instinct"


def test_custom_threshold_talent_applies_on_acquire():
    sig = {
        "tough_hide": {
            "name": "Tough Hide",
            "talent_type": "passive", "ranked": False, "max_rank": 1,
            "effects": [{"type": "modify_threshold",
                         "target": "wound_threshold", "modifier": 2}],
            "narrative_identity": "You shrug off what would fell others.",
            "prose_tags": ["tough"],
        }
    }
    c = Character(name="Brak", species="wookiee", career="enforcer",
                  custom_talents=sig, reserved_xp=20,
                  wound_threshold=14, strain_threshold=8)
    choices = T.build_milestone_choices(c, reserved_xp=20, max_choices=3)
    pick = next(ch for ch in choices if ch.talent_ref == "tough_hide")
    T.acquire_talent(c, pick)
    assert c.wound_threshold == 16  # 14 base + 2


# ── validate_talent_definition matrix ────────────────────────────────

def test_validate_accepts_each_type():
    good = {
        "passive": {"name": "P", "talent_type": "passive", "max_rank": 1,
                    "effects": [{"type": "modify_pool",
                                 "target_skills": ["stealth"],
                                 "modifier": {"boost": 1}}]},
        "conditional": {"name": "C", "talent_type": "conditional", "max_rank": 1,
                        "effects": [{"type": "conditional",
                                     "condition": {"scene_types": ["combat"]},
                                     "modifier": {"boost": 1}}]},
        "substitution": {"name": "S", "talent_type": "substitution", "max_rank": 1,
                         "effects": [{"type": "substitution",
                                      "original_skills": ["charm"],
                                      "substitute_skill": "deception"}]},
        "narrative_enabler": {"name": "N", "talent_type": "narrative_enabler",
                              "max_rank": 1,
                              "effects": [{"type": "narrative_enabler",
                                           "description": "Knows a guy."}]},
        "intervention": {"name": "I", "talent_type": "intervention", "max_rank": 1,
                         "effects": [{"type": "intervention", "effect": "reroll",
                                      "strain_cost": 1, "scope": "session",
                                      "applicable_skills": ["computers"]}]},
    }
    for ttype, defn in good.items():
        ok, errs = T.validate_talent_definition(defn)
        assert ok, f"{ttype} should validate, got {errs}"


@pytest.mark.parametrize("defn", [
    {"name": "", "talent_type": "passive", "max_rank": 1,
     "effects": [{"type": "modify_pool", "modifier": {"boost": 1}}]},   # empty name
    {"name": "X", "talent_type": "bogus", "max_rank": 1,
     "effects": [{"type": "modify_pool", "modifier": {"boost": 1}}]},   # bad type
    {"name": "X", "talent_type": "passive", "max_rank": 1, "effects": []},  # no effects
    {"name": "X", "talent_type": "passive", "max_rank": 1,
     "effects": [{"type": "modify_pool", "modifier": {"wild": 1}}]},    # bad die
    {"name": "X", "talent_type": "passive", "max_rank": 1,
     "effects": [{"type": "modify_pool", "modifier": {"boost": 9}}]},   # over magnitude
    {"name": "X", "talent_type": "passive", "max_rank": 1,
     "effects": [{"type": "modify_pool", "target_skills": ["not_a_skill"],
                  "modifier": {"boost": 1}}]},                          # bad skill
    {"name": "X", "talent_type": "conditional", "max_rank": 1,
     "effects": [{"type": "modify_pool", "modifier": {"boost": 1}}]},   # type mismatch
    {"name": "X", "talent_type": "passive", "max_rank": 9,
     "effects": [{"type": "modify_pool", "modifier": {"boost": 1}}]},   # bad max_rank
])
def test_validate_rejects_malformed(defn):
    ok, errs = T.validate_talent_definition(defn)
    assert not ok and errs
