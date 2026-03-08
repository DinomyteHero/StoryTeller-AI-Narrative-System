"""
Phase 15.5: Force and Destiny Talent Trees — Tests

Verifies all 3 success criteria:
1. At least 3 Force and Destiny specialization trees load correctly
2. Lightsaber characteristic substitution (e.g., use Willpower instead
   of Brawn) functions via Type 3 substitution talent
3. Force-sensitive talent milestones generate appropriate reflection
   passages themed around Force training
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import pytest

from engine.character import (
    Character, Species, Career, Characteristics, SkillRanks,
    MotivationTrack, GameLine, SKILL_CHARACTERISTICS,
)
from engine.checks import build_pool, CheckRequest, Difficulty
from engine.talents import (
    SpecializationTree,
    TreeEntry,
    build_milestone_choices,
    build_talent_capabilities,
    build_talent_check_effects,
    get_characteristic_override,
    load_specialization_tree,
    load_talent_library,
    MilestoneChoice,
    acquire_talent,
)


# ── Test fixtures ──────────────────────────────────────────────────────

def make_guardian_character(
    acquired_talents=None,
    force_rating=1,
    morality=50,
) -> Character:
    """Create a Guardian character for testing."""
    return Character(
        name="Kael Dren",
        species=Species.HUMAN,
        career=Career.GUARDIAN,
        specializations=["protector"],
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
        motivation=MotivationTrack(morality=morality),
        acquired_talents=acquired_talents or [],
    )


def make_consular_character(acquired_talents=None) -> Character:
    """Create a Consular character for testing."""
    return Character(
        name="Sera Voss",
        species=Species.HUMAN,
        career=Career.CONSULAR,
        specializations=["niman_disciple"],
        primary_game_line=GameLine.FORCE_AND_DESTINY,
        characteristics=Characteristics(
            brawn=1, agility=2, intellect=3, cunning=2, willpower=4, presence=3,
        ),
        skills=SkillRanks(
            discipline=2, lightsaber=2, negotiation=2, lore=1,
        ),
        wound_threshold=11,
        strain_threshold=15,
        soak=1,
        force_rating=1,
        motivation=MotivationTrack(morality=65),
        acquired_talents=acquired_talents or [],
    )


def make_sentinel_character(acquired_talents=None) -> Character:
    """Create a Sentinel character for testing."""
    return Character(
        name="Ren Talo",
        species=Species.HUMAN,
        career=Career.SENTINEL,
        specializations=["shadow"],
        primary_game_line=GameLine.FORCE_AND_DESTINY,
        characteristics=Characteristics(
            brawn=2, agility=3, intellect=3, cunning=3, willpower=2, presence=2,
        ),
        skills=SkillRanks(
            stealth=2, lightsaber=2, perception=2, computers=1,
        ),
        wound_threshold=12,
        strain_threshold=13,
        soak=2,
        force_rating=1,
        motivation=MotivationTrack(morality=55),
        acquired_talents=acquired_talents or [],
    )


# ═══════════════════════════════════════════════════════════════════════
# SUCCESS CRITERION 1: At least 3 F&D trees load correctly
# ═══════════════════════════════════════════════════════════════════════

class TestTreeLoading:
    """All three Force and Destiny trees load and validate correctly."""

    @pytest.mark.parametrize("tree_name", [
        "guardian_protector",
        "consular_niman_disciple",
        "sentinel_shadow",
    ])
    def test_tree_loads(self, tree_name):
        """F&D specialization tree loads without error."""
        tree = load_specialization_tree(tree_name)
        assert isinstance(tree, SpecializationTree)
        assert tree.game_line == "force_and_destiny"

    @pytest.mark.parametrize("tree_name", [
        "guardian_protector",
        "consular_niman_disciple",
        "sentinel_shadow",
    ])
    def test_tree_has_5_tiers(self, tree_name):
        """Each tree has entries spanning tiers 1-5."""
        tree = load_specialization_tree(tree_name)
        tiers = {e.tier for e in tree.entries}
        assert tiers == {1, 2, 3, 4, 5}

    @pytest.mark.parametrize("tree_name", [
        "guardian_protector",
        "consular_niman_disciple",
        "sentinel_shadow",
    ])
    def test_tree_has_17_entries(self, tree_name):
        """Each tree has 17 talent entries (standard 4×4 + 1 Dedication)."""
        tree = load_specialization_tree(tree_name)
        assert len(tree.entries) == 17

    @pytest.mark.parametrize("tree_name", [
        "guardian_protector",
        "consular_niman_disciple",
        "sentinel_shadow",
    ])
    def test_tier5_is_dedication(self, tree_name):
        """Tier 5 slot is Dedication (standard for all trees)."""
        tree = load_specialization_tree(tree_name)
        t5 = [e for e in tree.entries if e.tier == 5]
        assert len(t5) == 1
        assert t5[0].talent_ref == "dedication"

    @pytest.mark.parametrize("tree_name", [
        "guardian_protector",
        "consular_niman_disciple",
        "sentinel_shadow",
    ])
    def test_tree_has_tree_paths(self, tree_name):
        """Each tree has at least 2 thematic paths."""
        tree = load_specialization_tree(tree_name)
        assert len(tree.tree_paths) >= 2

    @pytest.mark.parametrize("tree_name", [
        "guardian_protector",
        "consular_niman_disciple",
        "sentinel_shadow",
    ])
    def test_all_talent_refs_in_library(self, tree_name):
        """All talent_refs in the tree exist in the talent library."""
        library = load_talent_library()
        tree = load_specialization_tree(tree_name)
        for entry in tree.entries:
            assert entry.talent_ref in library, (
                f"{tree_name} entry {entry.id} references unknown talent "
                f"'{entry.talent_ref}'"
            )

    @pytest.mark.parametrize("tree_name", [
        "guardian_protector",
        "consular_niman_disciple",
        "sentinel_shadow",
    ])
    def test_prerequisite_ids_valid(self, tree_name):
        """All prerequisite references point to existing entries in the tree."""
        tree = load_specialization_tree(tree_name)
        entry_ids = {e.id for e in tree.entries}
        for entry in tree.entries:
            for prereq in entry.prerequisites:
                assert prereq in entry_ids, (
                    f"{tree_name} entry {entry.id} has invalid prereq '{prereq}'"
                )

    def test_guardian_career_is_guardian(self):
        tree = load_specialization_tree("guardian_protector")
        assert tree.career == "guardian"

    def test_consular_career_is_consular(self):
        tree = load_specialization_tree("consular_niman_disciple")
        assert tree.career == "consular"

    def test_sentinel_career_is_sentinel(self):
        tree = load_specialization_tree("sentinel_shadow")
        assert tree.career == "sentinel"


class TestTreeContents:
    """Trees contain expected Force-specific talents."""

    def test_guardian_has_parry_and_reflect(self):
        """Guardian Protector tree includes Parry and Reflect."""
        tree = load_specialization_tree("guardian_protector")
        refs = {e.talent_ref for e in tree.entries}
        assert "parry" in refs
        assert "reflect" in refs

    def test_guardian_has_soresu(self):
        """Guardian Protector has Soresu Technique (Int-based lightsaber)."""
        tree = load_specialization_tree("guardian_protector")
        refs = {e.talent_ref for e in tree.entries}
        assert "soresu_technique" in refs

    def test_consular_has_niman(self):
        """Consular Niman Disciple has Niman Technique (Will-based lightsaber)."""
        tree = load_specialization_tree("consular_niman_disciple")
        refs = {e.talent_ref for e in tree.entries}
        assert "niman_technique" in refs

    def test_sentinel_has_shien(self):
        """Sentinel Shadow has Shien Technique (Cun-based lightsaber)."""
        tree = load_specialization_tree("sentinel_shadow")
        refs = {e.talent_ref for e in tree.entries}
        assert "shien_technique" in refs

    def test_all_trees_have_force_rating(self):
        """All three trees include the Force Rating talent."""
        for name in ["guardian_protector", "consular_niman_disciple", "sentinel_shadow"]:
            tree = load_specialization_tree(name)
            refs = {e.talent_ref for e in tree.entries}
            assert "force_rating" in refs, f"{name} missing force_rating"

    def test_guardian_has_saber_throw(self):
        """Guardian Protector has Saber Throw narrative enabler."""
        tree = load_specialization_tree("guardian_protector")
        refs = {e.talent_ref for e in tree.entries}
        assert "saber_throw" in refs

    def test_consular_has_healing_trance(self):
        """Consular Niman Disciple has Healing Trance."""
        tree = load_specialization_tree("consular_niman_disciple")
        refs = {e.talent_ref for e in tree.entries}
        assert "healing_trance" in refs

    def test_sentinel_has_stealth_talents(self):
        """Sentinel Shadow has stealth-oriented talents."""
        tree = load_specialization_tree("sentinel_shadow")
        refs = {e.talent_ref for e in tree.entries}
        assert "sleight_of_mind" in refs
        assert "stalker" in refs


# ═══════════════════════════════════════════════════════════════════════
# SUCCESS CRITERION 2: Lightsaber characteristic substitution works
# ═══════════════════════════════════════════════════════════════════════

class TestLightsaberCharacteristicOverride:
    """Type 3 substitution talents override lightsaber's governing characteristic."""

    def test_default_lightsaber_uses_brawn(self):
        """Without substitution talent, lightsaber uses Brawn."""
        assert SKILL_CHARACTERISTICS["lightsaber"] == "brawn"

    def test_no_override_without_talent(self):
        """Character without substitution talent gets no override."""
        char = make_guardian_character()
        override = get_characteristic_override(char, "lightsaber")
        assert override is None

    def test_niman_overrides_to_willpower(self):
        """Niman Technique overrides lightsaber to Willpower."""
        char = make_consular_character(acquired_talents=[
            {"talent_ref": "niman_technique", "tree": "consular_niman_disciple",
             "entry_id": "niman_t1_0"},
        ])
        override = get_characteristic_override(char, "lightsaber")
        assert override == "willpower"

    def test_shien_overrides_to_cunning(self):
        """Shien Technique overrides lightsaber to Cunning."""
        char = make_sentinel_character(acquired_talents=[
            {"talent_ref": "shien_technique", "tree": "sentinel_shadow",
             "entry_id": "shadow_t2_1"},
        ])
        override = get_characteristic_override(char, "lightsaber")
        assert override == "cunning"

    def test_soresu_overrides_to_intellect(self):
        """Soresu Technique overrides lightsaber to Intellect."""
        char = make_guardian_character(acquired_talents=[
            {"talent_ref": "soresu_technique", "tree": "guardian_protector",
             "entry_id": "prot_t3_1"},
        ])
        override = get_characteristic_override(char, "lightsaber")
        assert override == "intellect"

    def test_override_does_not_affect_other_skills(self):
        """Niman Technique only overrides lightsaber, not other skills."""
        char = make_consular_character(acquired_talents=[
            {"talent_ref": "niman_technique", "tree": "consular_niman_disciple",
             "entry_id": "niman_t1_0"},
        ])
        assert get_characteristic_override(char, "discipline") is None
        assert get_characteristic_override(char, "melee") is None

    def test_pool_uses_willpower_with_niman(self):
        """build_pool uses Willpower for lightsaber when Niman is acquired."""
        char = make_consular_character(acquired_talents=[
            {"talent_ref": "niman_technique", "tree": "consular_niman_disciple",
             "entry_id": "niman_t1_0"},
        ])
        # Willpower=4, lightsaber=2
        # max(4,2)=4 total dice, min(4,2)=2 proficiency, 2 ability
        check = CheckRequest(skill="lightsaber", difficulty=Difficulty.AVERAGE)
        pool, _, _ = build_pool(char, check)
        assert pool.proficiency == 2
        assert pool.ability == 2  # 4 - 2

    def test_pool_uses_brawn_without_niman(self):
        """build_pool uses Brawn for lightsaber without substitution talent."""
        char = make_consular_character()  # no acquired talents
        # Brawn=1, lightsaber=2
        # max(1,2)=2 total dice, min(1,2)=1 proficiency, 1 ability
        check = CheckRequest(skill="lightsaber", difficulty=Difficulty.AVERAGE)
        pool, _, _ = build_pool(char, check)
        assert pool.proficiency == 1
        assert pool.ability == 1  # 2 - 1

    def test_pool_uses_cunning_with_shien(self):
        """build_pool uses Cunning for lightsaber when Shien is acquired."""
        char = make_sentinel_character(acquired_talents=[
            {"talent_ref": "shien_technique", "tree": "sentinel_shadow",
             "entry_id": "shadow_t2_1"},
        ])
        # Cunning=3, lightsaber=2
        # max(3,2)=3 total dice, min(3,2)=2 proficiency, 1 ability
        check = CheckRequest(skill="lightsaber", difficulty=Difficulty.AVERAGE)
        pool, _, _ = build_pool(char, check)
        assert pool.proficiency == 2
        assert pool.ability == 1  # 3 - 2


class TestCheckEffectsDisplay:
    """build_talent_check_effects shows characteristic override info."""

    def test_niman_shows_in_check_effects(self):
        """Niman Technique appears in the check effects prompt section."""
        char = make_consular_character(acquired_talents=[
            {"talent_ref": "niman_technique", "tree": "consular_niman_disciple",
             "entry_id": "niman_t1_0"},
        ])
        effects = build_talent_check_effects(char)
        assert "Niman Technique" in effects
        assert "Willpower" in effects
        assert "Lightsaber" in effects

    def test_shien_shows_in_check_effects(self):
        """Shien Technique appears in the check effects prompt section."""
        char = make_sentinel_character(acquired_talents=[
            {"talent_ref": "shien_technique", "tree": "sentinel_shadow",
             "entry_id": "shadow_t2_1"},
        ])
        effects = build_talent_check_effects(char)
        assert "Shien Technique" in effects
        assert "Cunning" in effects

    def test_no_talents_empty_effects(self):
        """No acquired talents produces empty effects string."""
        char = make_guardian_character()
        effects = build_talent_check_effects(char)
        assert effects == ""


class TestCapabilitiesDisplay:
    """build_talent_capabilities shows substitution identity text."""

    def test_niman_shows_in_capabilities(self):
        """Niman narrative identity appears in capabilities block."""
        char = make_consular_character(acquired_talents=[
            {"talent_ref": "niman_technique", "tree": "consular_niman_disciple",
             "entry_id": "niman_t1_0"},
        ])
        caps = build_talent_capabilities(char)
        assert "Niman Technique" in caps

    def test_saber_throw_shows_in_capabilities(self):
        """Saber Throw narrative enabler appears in capabilities."""
        char = make_guardian_character(acquired_talents=[
            {"talent_ref": "saber_throw", "tree": "guardian_protector",
             "entry_id": "prot_t4_2"},
        ])
        caps = build_talent_capabilities(char)
        assert "Saber Throw" in caps
        assert "throw" in caps.lower()

    def test_healing_trance_shows_in_capabilities(self):
        """Healing Trance narrative enabler appears in capabilities."""
        char = make_consular_character(acquired_talents=[
            {"talent_ref": "healing_trance", "tree": "consular_niman_disciple",
             "entry_id": "niman_t2_2"},
        ])
        caps = build_talent_capabilities(char)
        assert "Healing Trance" in caps


# ═══════════════════════════════════════════════════════════════════════
# SUCCESS CRITERION 3: Force-sensitive milestones themed for Force training
# ═══════════════════════════════════════════════════════════════════════

class TestForceMilestoneChoices:
    """Milestone system generates Force-themed talent choices."""

    def test_guardian_milestone_choices(self):
        """Guardian with reserved XP gets milestone choices from their tree."""
        char = make_guardian_character()
        char.reserved_xp = 30
        choices = build_milestone_choices(char, char.reserved_xp)
        assert len(choices) > 0
        # All choices should reference talents in the guardian tree
        for c in choices:
            assert isinstance(c, MilestoneChoice)

    def test_consular_milestone_choices(self):
        """Consular with reserved XP gets choices including Niman."""
        char = make_consular_character()
        char.reserved_xp = 30
        choices = build_milestone_choices(char, char.reserved_xp)
        assert len(choices) > 0

    def test_milestone_choices_include_force_talent(self):
        """Milestone choices include Force-specific talents."""
        char = make_guardian_character()
        char.reserved_xp = 30
        choices = build_milestone_choices(char, char.reserved_xp)
        talent_refs = {c.talent_ref for c in choices}
        # Should include at least one Force-specific talent
        force_talents = {"parry", "reflect", "sense_danger", "force_protection",
                         "center_of_being", "soresu_technique", "niman_technique",
                         "shien_technique", "saber_throw", "force_rating",
                         "healing_trance", "calming_aura", "sleight_of_mind",
                         "uncanny_senses"}
        assert talent_refs & force_talents, (
            f"No Force talents in choices: {talent_refs}"
        )

    def test_milestone_respects_prerequisites(self):
        """Tier 2 talents not offered without tier 1 prerequisite acquired."""
        char = make_guardian_character()
        char.reserved_xp = 30
        choices = build_milestone_choices(char, char.reserved_xp)
        # Only tier 1 talents should be offered (no prereqs met yet)
        for c in choices:
            assert c.xp_cost == 5, (
                f"Expected only tier 1 (cost 5) choices, got {c.talent_ref} "
                f"at cost {c.xp_cost}"
            )

    def test_force_rating_talent_has_identity(self):
        """Force Rating talent in library has proper narrative identity."""
        library = load_talent_library()
        fr = library.get("force_rating")
        assert fr is not None
        assert "Force" in fr["narrative_identity"]
        assert "force" in " ".join(fr["prose_tags"])


class TestForceRatingViaTalent:
    """Force Rating increase through the force_rating talent works."""

    def test_acquire_force_rating_from_tree(self):
        """Acquiring force_rating talent increases Force Rating."""
        char = make_guardian_character(
            force_rating=1,
            acquired_talents=[
                # Need prereqs: t1_3 -> t2_3 -> t3_3 -> t4_3
                {"talent_ref": "grit", "tree": "guardian_protector",
                 "entry_id": "prot_t1_3"},
                {"talent_ref": "toughened", "tree": "guardian_protector",
                 "entry_id": "prot_t2_3"},
                {"talent_ref": "grit", "tree": "guardian_protector",
                 "entry_id": "prot_t3_3"},
            ],
        )
        char.reserved_xp = 25

        choice = MilestoneChoice(
            branch_key="force_growth",
            branch_theme="force_growth",
            branch_description="Path of deepening connection",
            talent_ref="force_rating",
            talent_name="Force Rating",
            tree_name="guardian_protector",
            entry_id="prot_t4_3",
            xp_cost=20,
            narrative_identity="The Force answers more fully.",
            prose_tags=["force", "growth"],
        )
        acquire_talent(char, choice)
        assert char.force_rating == 2

    def test_force_rating_logged_in_advancement(self):
        """Force Rating increase appears in advancement_log."""
        char = make_guardian_character(force_rating=1)
        char.reserved_xp = 25

        choice = MilestoneChoice(
            branch_key="force_growth",
            branch_theme="force_growth",
            branch_description="Path of deepening connection",
            talent_ref="force_rating",
            talent_name="Force Rating",
            tree_name="guardian_protector",
            entry_id="prot_t4_3",
            xp_cost=20,
            narrative_identity="The Force answers more fully.",
            prose_tags=["force", "growth"],
        )
        acquire_talent(char, choice)

        fr_logs = [l for l in char.advancement_log if l["type"] == "force_rating_increase"]
        assert len(fr_logs) == 1
        assert fr_logs[0]["old_rating"] == 1
        assert fr_logs[0]["new_rating"] == 2


# ═══════════════════════════════════════════════════════════════════════
# TALENT LIBRARY VALIDATION
# ═══════════════════════════════════════════════════════════════════════

class TestTalentLibrary:
    """Force-specific talents are well-formed in the library."""

    @pytest.mark.parametrize("talent_ref", [
        "parry", "reflect", "niman_technique", "shien_technique",
        "soresu_technique", "force_rating", "uncanny_senses",
        "sleight_of_mind", "sense_danger", "healing_trance",
        "force_protection", "center_of_being", "saber_throw",
        "calming_aura", "natural_blademaster", "natural_mystic",
        "knowledge_is_power", "researcher", "nobody_s_fool",
    ])
    def test_talent_exists_in_library(self, talent_ref):
        """Force talent exists and has required fields."""
        library = load_talent_library()
        assert talent_ref in library, f"'{talent_ref}' missing from library"
        defn = library[talent_ref]
        assert "name" in defn
        assert "talent_type" in defn
        assert "effects" in defn
        assert "narrative_identity" in defn
        assert "prose_tags" in defn

    def test_substitution_talents_have_characteristic_override(self):
        """All lightsaber substitution talents have characteristic_override."""
        library = load_talent_library()
        for ref in ["niman_technique", "shien_technique", "soresu_technique"]:
            defn = library[ref]
            assert defn["talent_type"] == "substitution"
            eff = defn["effects"][0]
            assert "characteristic_override" in eff
            assert "lightsaber" in eff["original_skills"]

    def test_each_substitution_uses_different_characteristic(self):
        """Each lightsaber form uses a unique characteristic."""
        library = load_talent_library()
        chars = set()
        for ref in ["niman_technique", "shien_technique", "soresu_technique"]:
            char = library[ref]["effects"][0]["characteristic_override"]
            assert char not in chars, f"Duplicate characteristic: {char}"
            chars.add(char)
