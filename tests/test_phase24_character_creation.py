"""Phase 24 — Character Creation Redesign tests.

Pure-Python coverage of the new flow: backgrounds, refinement, identity
prologue, archetype inference, profession crystallization, and the
talent earned-through-use mechanism.

These tests use no LLMs — the prologue runner is server-side state, the
archetype inference is deterministic, and the crystallization suggestion
algorithm is a pure function. The full end-to-end API path with mocked
LLMs is exercised in `tests/test_phase24_e2e.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.character import (
    BeliefCommitment,
    Career,
    Character,
    Pronouns,
    PRE_CRYSTALLIZATION_CAREERS,
    Species,
)
from engine.character_creation import (
    ARCHETYPE_DEFINITIONS,
    GENDER_MENU,
    PATTERN_THRESHOLDS,
    PRONOUN_PRESETS,
    PrologueChoiceRecord,
    PrologueState,
    RefinementChoice,
    apply_crystallization_choice,
    apply_diegetic_payload,
    apply_skill_tilt,
    build_baseline_character,
    check_pattern_unlocks,
    compute_crystallization_suggestion,
    derive_personality_locks,
    finalize_prologue,
    grant_pattern_unlock,
    increment_use_pattern,
    infer_archetype_from_choices,
    initialize_prologue_state,
    lookup_background,
    record_prologue_choice,
    render_prologue_scene,
    resolve_pronouns,
)
from studio.schema import (
    Background,
    BeliefCommitmentSpec,
    CampaignSpine,
    IdentityPrologueArc,
    ProfessionCrystallization,
    ProfessionPath,
)


SHADOWS_PATH = Path("data/campaigns/shadows_of_the_custodian.json")


@pytest.fixture(scope="module")
def shadows_spine():
    return json.loads(SHADOWS_PATH.read_text(encoding="utf-8"))


# ── Schema sanity ────────────────────────────────────────────────────


class TestSchema:

    def test_spine_validates_with_phase24_fields(self, shadows_spine):
        spine = CampaignSpine(**shadows_spine)
        assert len(spine.backgrounds) == 6
        assert spine.identity_prologue is not None
        assert spine.profession_crystallization is not None
        assert len(spine.identity_prologue.scene_library) == 4
        assert len(spine.profession_crystallization.paths) == 4

    def test_six_backgrounds_have_unique_ids(self, shadows_spine):
        ids = [bg["background_id"] for bg in shadows_spine["backgrounds"]]
        assert len(set(ids)) == len(ids) == 6
        assert "outer_rim_refugee" in ids
        assert "imperial_defector" in ids
        assert "rebel_legacy" in ids
        assert "discovered_late" in ids
        assert "frontier_world_native" in ids
        assert "reformed_smuggler" in ids

    def test_each_background_has_pre_filled_relationship(self, shadows_spine):
        for bg in shadows_spine["backgrounds"]:
            rel = bg.get("pre_filled_relationship")
            assert rel
            assert rel["npc_name"]
            assert rel["npc_role"]
            assert 0.0 <= rel["initial_disposition"] <= 1.0

    def test_each_prologue_scene_has_all_six_variants(self, shadows_spine):
        bg_ids = {bg["background_id"] for bg in shadows_spine["backgrounds"]}
        for scene in shadows_spine["identity_prologue"]["scene_library"]:
            variants = scene.get("background_variants", {})
            assert set(variants.keys()) >= bg_ids, (
                f"scene {scene['scene_id']} is missing variants for "
                f"{bg_ids - set(variants.keys())}"
            )

    def test_crystallization_has_three_default_paths_plus_optional(self, shadows_spine):
        paths = shadows_spine["profession_crystallization"]["paths"]
        # 3 default (guardian/consular/sentinel) + 1 background-specific (Shadow Sentinel)
        assert len(paths) == 4
        bg_specific = [p for p in paths if p.get("background_specific_id")]
        assert len(bg_specific) == 1
        assert bg_specific[0]["background_specific_id"] == "imperial_defector"


# ── Character schema sanity ──────────────────────────────────────────


class TestCharacterSchema:

    def test_default_career_is_praxeum_student(self):
        c = Character()
        assert c.career == Career.PRAXEUM_STUDENT
        assert c.is_pre_crystallization()
        assert c.crystallized is False

    def test_pre_crystallization_careers_list(self):
        assert Career.PRAXEUM_STUDENT in PRE_CRYSTALLIZATION_CAREERS
        assert Career.JEDI_STUDENT in PRE_CRYSTALLIZATION_CAREERS
        assert Career.GUARDIAN not in PRE_CRYSTALLIZATION_CAREERS

    def test_existing_character_files_still_load(self):
        with open("data/characters/praxeum_student.json", encoding="utf-8") as f:
            c = Character.model_validate_json(f.read())
        assert c.name == "Praxeum Student"
        # Mystic + crystallized=False but career not in PRE_CRYSTALLIZATION → not pre
        assert c.is_pre_crystallization() is False
        assert c.species == Species.MIRIALAN

    def test_optional_name_species(self):
        c = Character()
        assert c.name is None
        assert c.species is None
        # display_name still works
        assert c.display_name() == "the protagonist"
        assert c.display_species() == "Unknown"


# ── Refinement / build_baseline_character ────────────────────────────


class TestBuildBaselineCharacter:

    def test_full_refinement(self, shadows_spine):
        ref = RefinementChoice(
            background_id="outer_rim_refugee",
            name="Sora",
            species_id="human",
            gender_id="female",
            appearance_flair="Loose hair, callused hands.",
        )
        char = build_baseline_character(shadows_spine, ref)
        assert char.name == "Sora"
        assert char.species == Species.HUMAN
        assert char.career == Career.PRAXEUM_STUDENT
        assert char.is_pre_crystallization()
        assert char.background == "outer_rim_refugee"
        assert "outer_rim_refugee" not in char.background_summary  # is the seed text
        assert "Imperial occupation" in char.background_summary
        assert char.gender == "female"
        assert char.pronouns is not None
        assert char.pronouns.subject == "she"
        assert char.appearance_flair == "Loose hair, callused hands."
        # Tilt applied
        assert char.skills.resilience >= 1
        assert char.skills.vigilance >= 1
        assert char.skills.survival >= 1

    def test_default_name_picked_when_not_supplied(self, shadows_spine):
        ref = RefinementChoice(background_id="imperial_defector")
        char = build_baseline_character(shadows_spine, ref)
        # Auto-picked from default_names list
        assert char.name in {"Cael", "Nyx", "Vell", "Doran", "Ardin"}

    def test_baseline_force_rating_and_loadout(self, shadows_spine):
        ref = RefinementChoice(background_id="rebel_legacy")
        char = build_baseline_character(shadows_spine, ref)
        assert char.force_rating == 1
        assert len(char.force_powers) == 1
        assert char.force_powers[0]["power_id"] == "sense"
        assert len(char.loadout.weapons) >= 1
        assert char.loadout.armor is not None

    def test_pronouns_resolution_from_menu(self):
        p = resolve_pronouns("non_binary", None)
        assert p is not None
        assert p.subject == "they"

    def test_pronouns_resolution_with_custom(self):
        custom = Pronouns(subject="ze", object="zir", possessive="zir")
        p = resolve_pronouns("custom", custom)
        assert p is not None
        assert p.subject == "ze"
        assert p.object == "zir"

    def test_skip_all_optional_fields(self, shadows_spine):
        ref = RefinementChoice(background_id="frontier_world_native")
        char = build_baseline_character(shadows_spine, ref)
        # Name auto-picked, species defaults, gender unset
        assert char.name is not None
        assert char.species is not None  # defaults to first listed
        assert char.gender is None
        assert char.pronouns is None

    def test_unknown_background_raises(self, shadows_spine):
        ref = RefinementChoice(background_id="not_a_real_background")
        with pytest.raises(KeyError):
            build_baseline_character(shadows_spine, ref)


# ── Prologue runner ──────────────────────────────────────────────────


class TestPrologueRunner:

    def _full_run(self, shadows_spine, background_id, *, choice_index_each=0):
        ref = RefinementChoice(background_id=background_id, name="Test")
        char = build_baseline_character(shadows_spine, ref)
        state = initialize_prologue_state(shadows_spine, char)
        steps = []
        for _ in range(8):  # safety bound
            scene = render_prologue_scene(shadows_spine, state, char.background)
            if scene is None:
                break
            steps.append(scene["scene_id"])
            res = record_prologue_choice(shadows_spine, state, choice_index_each)
            assert res["committed"]
            if state.stage == "complete":
                break
        return char, state, steps

    def test_renders_correct_background_variant(self, shadows_spine):
        char, state, steps = self._full_run(shadows_spine, "outer_rim_refugee")
        assert state.stage == "complete"
        assert len(steps) == 4

    def test_each_background_runs_to_completion(self, shadows_spine):
        for bg_id in (
            "outer_rim_refugee", "imperial_defector", "rebel_legacy",
            "discovered_late", "frontier_world_native", "reformed_smuggler",
        ):
            _, state, steps = self._full_run(shadows_spine, bg_id)
            assert state.stage == "complete", f"background {bg_id} did not complete"
            assert len(state.history) == 4

    def test_record_prologue_choice_invalid_index(self, shadows_spine):
        ref = RefinementChoice(background_id="rebel_legacy")
        char = build_baseline_character(shadows_spine, ref)
        state = initialize_prologue_state(shadows_spine, char)
        # First scene has 3 choices
        res = record_prologue_choice(shadows_spine, state, 99)
        assert res["committed"] is False
        assert res["reason"] == "invalid_choice_index"

    def test_diegetic_slot_appearance_flair(self, shadows_spine):
        ref = RefinementChoice(
            background_id="outer_rim_refugee", appearance_flair=None
        )
        char = build_baseline_character(shadows_spine, ref)
        state = initialize_prologue_state(shadows_spine, char)
        assert "appearance_flair" in state.diegetic_slots_pending

        scene = render_prologue_scene(shadows_spine, state, char.background)
        assert scene is not None
        assert scene["diegetic_slot"] is not None
        assert scene["diegetic_slot"]["slot_type"] == "appearance_flair"

        res = record_prologue_choice(
            shadows_spine, state, 0,
            {"appearance_flair": "A lopsided fringe and the silence of someone who has counted exits."}
        )
        assert res["committed"]
        assert res["diegetic_committed"]["slot_type"] == "appearance_flair"

        apply_diegetic_payload(
            char,
            res["diegetic_committed"]["slot_type"],
            res["diegetic_committed"]["payload"],
        )
        assert "lopsided" in (char.appearance_flair or "")
        assert "appearance_flair" not in state.diegetic_slots_pending


# ── Behavioral inference ─────────────────────────────────────────────


class TestArchetypeInference:

    def test_warm_diplomat_archetype(self):
        history = [
            PrologueChoiceRecord("s1", 0, {"social": "open", "moral": "honest"}),
            PrologueChoiceRecord("s2", 0, {"social": "open", "moral": "honest"}),
            PrologueChoiceRecord("s3", 0, {"social": "warm"}),
        ]
        arch_id, defn = infer_archetype_from_choices(history)
        assert arch_id == "the_warm_diplomat"
        assert defn["compatible_profession"] == "consular"

    def test_pattern_reader_archetype(self):
        history = [
            PrologueChoiceRecord("s1", 1, {"approach": "indirect", "social": "guarded"}),
            PrologueChoiceRecord("s2", 1, {"approach": "indirect", "social": "guarded"}),
            PrologueChoiceRecord("s3", 1, {"social": "guarded"}),
        ]
        arch_id, defn = infer_archetype_from_choices(history)
        assert arch_id == "the_pattern_reader"
        assert defn["compatible_profession"] == "sentinel"

    def test_steady_hand_archetype(self):
        history = [
            PrologueChoiceRecord("s1", 0, {"approach": "direct", "moral": "principled"}),
            PrologueChoiceRecord("s2", 0, {"approach": "direct", "moral": "principled"}),
        ]
        arch_id, defn = infer_archetype_from_choices(history)
        assert arch_id == "the_steady_hand"
        assert defn["compatible_profession"] == "guardian"

    def test_empty_history_falls_back(self):
        arch_id, _ = infer_archetype_from_choices([])
        assert arch_id == "the_quiet_listener"

    def test_personality_locks_derivation(self):
        history = [
            PrologueChoiceRecord("s1", 0, {"approach": "direct"}),
            PrologueChoiceRecord("s2", 0, {"social": "warm"}),
            PrologueChoiceRecord("s3", 0, {"approach": "direct"}),
        ]
        locks = derive_personality_locks(history)
        # First-occurrence-per-axis policy → 2 locks (approach + social)
        axes = sorted(l.axis for l in locks)
        assert "approach" in axes
        assert "social" in axes
        assert all(l.commitment_text for l in locks)


# ── Finalize prologue ────────────────────────────────────────────────


class TestFinalizePrologue:

    def test_finalize_writes_to_character(self, shadows_spine):
        ref = RefinementChoice(background_id="outer_rim_refugee", name="Sora")
        char = build_baseline_character(shadows_spine, ref)
        state = PrologueState(
            stage="complete",
            history=[
                PrologueChoiceRecord("s1", 0, {"social": "open", "moral": "honest"}),
                PrologueChoiceRecord("s2", 0, {"social": "open", "moral": "honest"}),
                PrologueChoiceRecord("s3", 0, {"social": "warm"}),
            ],
        )
        summary = finalize_prologue(shadows_spine, char, state)
        assert summary["behavioral_archetype"] == "the_warm_diplomat"
        assert char.behavioral_archetype == "the_warm_diplomat"
        assert len(char.personality_locks) >= 1
        # Background tilt + archetype tilt both present
        assert char.skill_tilt.get("resilience", 0) >= 1
        assert char.skill_tilt.get("charm", 0) >= 1


# ── Crystallization ──────────────────────────────────────────────────


class TestCrystallization:

    def test_imperial_defector_unlocks_shadow_sentinel(self, shadows_spine):
        ref = RefinementChoice(background_id="imperial_defector", name="Cael")
        char = build_baseline_character(shadows_spine, ref)
        char.behavioral_archetype = "the_pattern_reader"

        sug = compute_crystallization_suggestion(shadows_spine, char)
        assert sug.suggested_path_index >= 0
        # All 4 paths visible (non-imperial would mask the 4th)
        assert all(w >= 0 for w in sug.weights[:3])
        assert sug.weights[3] >= 0  # Shadow Sentinel visible for imperial defector

    def test_non_imperial_masks_shadow_sentinel(self, shadows_spine):
        ref = RefinementChoice(background_id="outer_rim_refugee")
        char = build_baseline_character(shadows_spine, ref)
        char.behavioral_archetype = "the_pattern_reader"
        sug = compute_crystallization_suggestion(shadows_spine, char)
        # 4th (Shadow Sentinel) should be masked
        assert sug.weights[3] == -1

    def test_suggestion_weights_strong_fit(self, shadows_spine):
        # Refugee's strong fit is consular; with warm_diplomat archetype
        # consular should dominate.
        ref = RefinementChoice(background_id="outer_rim_refugee")
        char = build_baseline_character(shadows_spine, ref)
        char.behavioral_archetype = "the_warm_diplomat"
        sug = compute_crystallization_suggestion(shadows_spine, char)
        # paths order: guardian, consular, sentinel, shadow_sentinel
        assert sug.weights[1] > sug.weights[0]
        assert sug.weights[1] > sug.weights[2]
        assert sug.suggested_path_index == 1

    def test_apply_crystallization(self, shadows_spine):
        ref = RefinementChoice(background_id="rebel_legacy")
        char = build_baseline_character(shadows_spine, ref)
        assert char.is_pre_crystallization()
        result = apply_crystallization_choice(shadows_spine, char, 0)  # Guardian
        assert result["career"] == "guardian"
        assert char.career == Career.GUARDIAN
        assert char.crystallized
        assert "guardian_protector" in char.specializations
        assert not char.is_pre_crystallization()

    def test_apply_crystallization_invalid_index(self, shadows_spine):
        ref = RefinementChoice(background_id="rebel_legacy")
        char = build_baseline_character(shadows_spine, ref)
        with pytest.raises(ValueError):
            apply_crystallization_choice(shadows_spine, char, 99)

    def test_apply_crystallization_blocks_masked_path(self, shadows_spine):
        ref = RefinementChoice(background_id="outer_rim_refugee")
        char = build_baseline_character(shadows_spine, ref)
        # Path 3 is Shadow Sentinel — blocked for non-imperial-defector
        with pytest.raises(ValueError):
            apply_crystallization_choice(shadows_spine, char, 3)


# ── Pattern unlocks (Mechanism 3) ────────────────────────────────────


class TestPatternUnlocks:

    def test_pattern_increment_and_unlock(self, shadows_spine):
        ref = RefinementChoice(background_id="outer_rim_refugee")
        char = build_baseline_character(shadows_spine, ref)
        # Pre-crystallization: pattern unlocks should not fire even at threshold
        for _ in range(5):
            increment_use_pattern(char, "consular_influence_uses")
        assert check_pattern_unlocks(char) == []

        # Crystallize as consular, then unlocks should fire
        apply_crystallization_choice(shadows_spine, char, 1)  # Consular
        unlocks = check_pattern_unlocks(char)
        assert any(u["talent_id"] == "consular.hard_pressed_influence" for u in unlocks)

        grant_pattern_unlock(
            char,
            "consular.hard_pressed_influence",
            "test grant",
        )
        # Already-acquired talent should not re-unlock
        unlocks = check_pattern_unlocks(char)
        assert not any(u["talent_id"] == "consular.hard_pressed_influence" for u in unlocks)

    def test_unrelated_career_does_not_get_unlocks(self, shadows_spine):
        ref = RefinementChoice(background_id="rebel_legacy")
        char = build_baseline_character(shadows_spine, ref)
        # Crystallize as guardian
        apply_crystallization_choice(shadows_spine, char, 0)
        # Bump consular-pattern; should not unlock anything for guardian
        for _ in range(10):
            increment_use_pattern(char, "consular_influence_uses")
        unlocks = check_pattern_unlocks(char)
        assert not any("consular" in u["talent_id"] for u in unlocks)


# ── Apply skill tilt ─────────────────────────────────────────────────


def test_apply_skill_tilt_clamps_and_accumulates():
    char = Character()
    char.skills.resilience = 3
    apply_skill_tilt(char, {"resilience": 1, "education": -1})
    assert char.skills.resilience == 4
    assert char.skills.education == 0  # clamped at 0
    # Tilt vector accumulated
    apply_skill_tilt(char, {"resilience": 1})
    assert char.skill_tilt["resilience"] == 2


# ── Sanity on the gender menu ────────────────────────────────────────


def test_gender_menu_seven_options():
    assert len(GENDER_MENU) == 7
    assert any(g["id"] == "custom" for g in GENDER_MENU)


def test_pronoun_presets_well_formed():
    for key in ("she_her", "he_him", "they_them"):
        assert key in PRONOUN_PRESETS
        for field in ("subject", "object", "possessive"):
            assert PRONOUN_PRESETS[key][field]
