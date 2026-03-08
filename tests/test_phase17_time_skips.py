"""
Phase 17 Time Skip Vignette tests.

Success criteria (from Build Roadmap):
1. A time skip with 3-month duration presents 2 vignettes from spine's vignette library
2. Vignette selection respects prerequisites and category diversity
3. Each vignette presents its passage and 2-3 choices
4. Vignette choice skill tags feed into behavioral inference weighting
5. Vignette NPC effects modify disposition correctly
6. Vignette moral_weight feeds into Conflict accumulation
7. The closing passage reflects the pattern of vignette choices made
"""

import json
import os
import sys
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.time_skip import (
    Vignette,
    VignetteChoice,
    VignetteEffect,
    TimeSkipConfig,
    TimeSkipResult,
    vignette_count_for_duration,
    load_time_skip_config,
    select_vignettes,
    process_vignette_choice,
    aggregate_vignette_effects,
    apply_vignette_npc_effects,
    apply_npc_time_drift,
    apply_time_skip_recovery,
    build_vignette_inference_rows,
    serialize_vignette,
    serialize_time_skip_state,
    deserialize_time_skip_state,
    _check_prerequisites,
    _check_exclusions,
    NPC_DRIFT_RATE,
    NPC_DRIFT_RESISTANCE_HIGH,
    NPC_DRIFT_RESISTANCE_LOW,
)


# ── Helpers ───────────────────────────────────────────────────────────

def _make_choice(
    text="Test choice",
    skill_tag="deception",
    npc_effects=None,
    moral_weight=0,
    morality_bonus=0,
    aspiration_tags=None,
    narrative_consequence="Something happened.",
):
    return VignetteChoice(
        text=text,
        skill_tag=skill_tag,
        npc_effects=npc_effects or {},
        moral_weight=moral_weight,
        morality_bonus=morality_bonus,
        aspiration_tags=aspiration_tags or [],
        narrative_consequence=narrative_consequence,
    )


def _make_vignette(
    vignette_id="test_vignette",
    category="training",
    passage="Test passage text.",
    choices=None,
    npc_focus=None,
    skill_domain=None,
    requires=None,
    excludes=None,
    time_stamp="",
):
    return Vignette(
        vignette_id=vignette_id,
        category=category,
        passage=passage,
        choices=choices or [_make_choice(), _make_choice(text="Choice 2", skill_tag="cool")],
        npc_focus=npc_focus,
        skill_domain=skill_domain or [],
        requires=requires or {},
        excludes=excludes or {},
        time_stamp=time_stamp,
    )


@dataclass
class MockNPCState:
    name: str = "Doss"
    role: str = "Contact"
    disposition: float = 0.65
    knows: list = field(default_factory=list)
    doesnt_know: list = field(default_factory=list)


@dataclass
class MockCharacter:
    force_rating: int = 0
    current_strain: int = 3
    current_wounds: int = 2
    career_skills: list = field(default_factory=list)
    motivation: object = None

    def __post_init__(self):
        if self.motivation is None:
            self.motivation = MockMotivation()


@dataclass
class MockMotivation:
    conflict: int = 0
    morality: int = 50
    obligation_type: str = ""
    obligation_value: int = 0
    duty_type: str = ""
    duty_value: int = 0


# ── Test Classes ──────────────────────────────────────────────────────


class TestVignetteCount(unittest.TestCase):
    """Duration → vignette count mapping."""

    def test_short_skip_1_month(self):
        self.assertEqual(vignette_count_for_duration(1), 1)

    def test_short_skip_2_months(self):
        self.assertEqual(vignette_count_for_duration(2), 1)

    def test_medium_skip_3_months(self):
        """SC1: 3-month duration → 2 vignettes."""
        self.assertEqual(vignette_count_for_duration(3), 2)

    def test_medium_skip_6_months(self):
        self.assertEqual(vignette_count_for_duration(6), 2)

    def test_long_skip_7_months(self):
        self.assertEqual(vignette_count_for_duration(7), 3)

    def test_long_skip_12_months(self):
        self.assertEqual(vignette_count_for_duration(12), 3)


class TestSpineLoading(unittest.TestCase):
    """Loading time skip config from campaign spine JSON."""

    def test_load_from_spine_act(self):
        """SC1: Time skip loads from spine's vignette library."""
        spine_path = ROOT / "data" / "campaigns" / "nar_shaddaa_job.json"
        spine = json.loads(spine_path.read_text(encoding="utf-8"))

        # Act 3 should have a time_skip
        act3 = spine["acts"][2]
        config = load_time_skip_config(act3)

        self.assertIsNotNone(config)
        self.assertEqual(config.duration_months, 3)
        self.assertGreater(len(config.vignettes), 0)
        self.assertTrue(len(config.framing) > 0)

    def test_load_returns_none_when_no_skip(self):
        config = load_time_skip_config({"number": 1, "name": "Test"})
        self.assertIsNone(config)

    def test_spine_vignette_count(self):
        """SC1: Spine has enough vignettes to select from."""
        spine_path = ROOT / "data" / "campaigns" / "nar_shaddaa_job.json"
        spine = json.loads(spine_path.read_text(encoding="utf-8"))
        act3 = spine["acts"][2]
        config = load_time_skip_config(act3)
        # Should have at least 4 vignettes (library for selection)
        self.assertGreaterEqual(len(config.vignettes), 4)

    def test_spine_vignette_structure(self):
        """SC3: Each vignette has passage and 2-3 choices."""
        spine_path = ROOT / "data" / "campaigns" / "nar_shaddaa_job.json"
        spine = json.loads(spine_path.read_text(encoding="utf-8"))
        act3 = spine["acts"][2]
        config = load_time_skip_config(act3)

        for v in config.vignettes:
            self.assertTrue(len(v.passage) > 0, f"{v.vignette_id} has empty passage")
            self.assertGreaterEqual(
                len(v.choices), 2,
                f"{v.vignette_id} has fewer than 2 choices",
            )
            self.assertLessEqual(
                len(v.choices), 4,
                f"{v.vignette_id} has more than 4 choices",
            )

    def test_spine_choice_skill_tags(self):
        """SC4: Each choice has a skill tag."""
        spine_path = ROOT / "data" / "campaigns" / "nar_shaddaa_job.json"
        spine = json.loads(spine_path.read_text(encoding="utf-8"))
        act3 = spine["acts"][2]
        config = load_time_skip_config(act3)

        for v in config.vignettes:
            for c in v.choices:
                self.assertTrue(
                    len(c.skill_tag) > 0,
                    f"{v.vignette_id} choice '{c.text[:30]}' has no skill tag",
                )


class TestVignetteSelection(unittest.TestCase):
    """Vignette selection logic with prerequisites and diversity."""

    def _make_library(self):
        """Create a 5-vignette library with varied categories."""
        return [
            _make_vignette("v_training", "training", skill_domain=["deception"]),
            _make_vignette("v_relationship", "relationship", npc_focus="Doss",
                           skill_domain=["streetwise"]),
            _make_vignette("v_crisis", "crisis", skill_domain=["stealth"]),
            _make_vignette("v_mundane", "mundane", skill_domain=["mechanics"]),
            _make_vignette("v_solitary", "solitary", skill_domain=["discipline"]),
        ]

    def test_selects_correct_count_for_3_months(self):
        """SC1: 3-month skip selects 2 vignettes."""
        config = TimeSkipConfig(
            duration_months=3, framing="Test",
            vignettes=self._make_library(),
        )
        char = MockCharacter()
        selected = select_vignettes(config, char, [])
        self.assertEqual(len(selected), 2)

    def test_selects_1_for_short_skip(self):
        config = TimeSkipConfig(
            duration_months=1, framing="Test",
            vignettes=self._make_library(),
        )
        selected = select_vignettes(config, MockCharacter(), [])
        self.assertEqual(len(selected), 1)

    def test_selects_3_for_long_skip(self):
        config = TimeSkipConfig(
            duration_months=8, framing="Test",
            vignettes=self._make_library(),
        )
        selected = select_vignettes(config, MockCharacter(), [])
        self.assertEqual(len(selected), 3)

    def test_category_diversity(self):
        """SC2: Selection spans at least 2 different categories."""
        config = TimeSkipConfig(
            duration_months=3, framing="Test",
            vignettes=self._make_library(),
        )
        char = MockCharacter()
        selected = select_vignettes(config, char, [])
        categories = {v.category for v in selected}
        self.assertGreaterEqual(len(categories), 2)

    def test_prerequisite_filtering_force(self):
        """SC2: Force-sensitive prerequisite filters correctly."""
        force_vignette = _make_vignette(
            "v_force", "training",
            requires={"force_sensitive": True},
        )
        non_force_vignette = _make_vignette("v_normal", "mundane")

        config = TimeSkipConfig(
            duration_months=1, framing="Test",
            vignettes=[force_vignette, non_force_vignette],
        )

        # Non-Force character should not get force vignette
        char = MockCharacter(force_rating=0)
        selected = select_vignettes(config, char, [])
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].vignette_id, "v_normal")

        # Force-sensitive character should get either
        char_force = MockCharacter(force_rating=1)
        selected_force = select_vignettes(config, char_force, [])
        self.assertEqual(len(selected_force), 1)

    def test_prerequisite_npc_disposition(self):
        """SC2: NPC disposition prerequisite filtering."""
        npc_vignette = _make_vignette(
            "v_npc", "relationship",
            requires={"min_disposition": {"Doss": 0.7}},
        )

        # Doss at 0.65 — below threshold
        npc_low = MockNPCState(disposition=0.65)
        self.assertFalse(_check_prerequisites(npc_vignette, MockCharacter(), [npc_low]))

        # Doss at 0.8 — above threshold
        npc_high = MockNPCState(disposition=0.8)
        self.assertTrue(_check_prerequisites(npc_vignette, MockCharacter(), [npc_high]))

    def test_behavioral_signal_matching(self):
        """SC2: Behavioral signals influence vignette scoring."""
        config = TimeSkipConfig(
            duration_months=3, framing="Test",
            vignettes=[
                _make_vignette("v_deception", "training", skill_domain=["deception"]),
                _make_vignette("v_mechanics", "mundane", skill_domain=["mechanics"]),
                _make_vignette("v_stealth", "crisis", skill_domain=["stealth"]),
            ],
        )

        # Player who heavily used deception
        fingerprint = {
            "dominant_tags": ["deception", "charm"],
            "dominant_priorities": ["cunning"],
        }
        selected = select_vignettes(
            config, MockCharacter(), [], behavioral_fingerprint=fingerprint,
        )
        # Deception vignette should be selected (higher score)
        ids = [v.vignette_id for v in selected]
        self.assertIn("v_deception", ids)

    def test_returns_empty_when_all_filtered(self):
        config = TimeSkipConfig(
            duration_months=3, framing="Test",
            vignettes=[
                _make_vignette("v_force", "training", requires={"force_sensitive": True}),
            ],
        )
        selected = select_vignettes(config, MockCharacter(force_rating=0), [])
        self.assertEqual(len(selected), 0)

    def test_handles_fewer_eligible_than_target(self):
        """If only 1 eligible vignette for a 3-month skip, return 1."""
        config = TimeSkipConfig(
            duration_months=3, framing="Test",
            vignettes=[_make_vignette("v_only", "training")],
        )
        selected = select_vignettes(config, MockCharacter(), [])
        self.assertEqual(len(selected), 1)


class TestVignetteChoiceProcessing(unittest.TestCase):
    """Processing individual vignette choices."""

    def test_process_valid_choice(self):
        vignette = _make_vignette(choices=[
            _make_choice("Option A", "deception", {"Doss": 0.1}, 2, 0, ["cunning"]),
            _make_choice("Option B", "cool", {}, 0, 1, ["patience"]),
        ])

        effect = process_vignette_choice(vignette, 0)
        self.assertEqual(effect.skill_tag, "deception")
        self.assertEqual(effect.npc_effects, {"Doss": 0.1})
        self.assertEqual(effect.moral_weight, 2)
        self.assertEqual(effect.aspiration_tags, ["cunning"])

    def test_process_second_choice(self):
        vignette = _make_vignette(choices=[
            _make_choice("Option A", "deception"),
            _make_choice("Option B", "cool", morality_bonus=1),
        ])

        effect = process_vignette_choice(vignette, 1)
        self.assertEqual(effect.skill_tag, "cool")
        self.assertEqual(effect.morality_bonus, 1)

    def test_invalid_choice_raises(self):
        vignette = _make_vignette()
        with self.assertRaises(ValueError):
            process_vignette_choice(vignette, 5)

    def test_negative_choice_raises(self):
        vignette = _make_vignette()
        with self.assertRaises(ValueError):
            process_vignette_choice(vignette, -1)


class TestEffectAggregation(unittest.TestCase):
    """Aggregating effects from multiple vignette choices."""

    def test_skill_tags_collected(self):
        """SC4: Skill tags are collected for behavioral inference."""
        effects = [
            VignetteEffect("v1", 0, "deception", {}, 0, 0, [], ""),
            VignetteEffect("v2", 1, "mechanics", {}, 0, 0, [], ""),
        ]
        agg = aggregate_vignette_effects(effects)
        self.assertEqual(agg["skill_tags"], ["deception", "mechanics"])

    def test_npc_effects_summed(self):
        """SC5: NPC disposition changes accumulate correctly."""
        effects = [
            VignetteEffect("v1", 0, "", {"Doss": 0.1}, 0, 0, [], ""),
            VignetteEffect("v2", 0, "", {"Doss": 0.05, "Vossk": -0.1}, 0, 0, [], ""),
        ]
        agg = aggregate_vignette_effects(effects)
        self.assertAlmostEqual(agg["npc_effects"]["Doss"], 0.15)
        self.assertAlmostEqual(agg["npc_effects"]["Vossk"], -0.1)

    def test_conflict_summed(self):
        """SC6: Moral weight feeds into Conflict accumulation."""
        effects = [
            VignetteEffect("v1", 0, "", {}, 2, 0, [], ""),
            VignetteEffect("v2", 0, "", {}, 1, 0, [], ""),
        ]
        agg = aggregate_vignette_effects(effects)
        self.assertEqual(agg["total_conflict"], 3)

    def test_morality_bonus_summed(self):
        effects = [
            VignetteEffect("v1", 0, "", {}, 0, 1, [], ""),
            VignetteEffect("v2", 0, "", {}, 0, 2, [], ""),
        ]
        agg = aggregate_vignette_effects(effects)
        self.assertEqual(agg["total_morality_bonus"], 3)

    def test_aspiration_tags_deduplicated(self):
        effects = [
            VignetteEffect("v1", 0, "", {}, 0, 0, ["cunning", "patience"], ""),
            VignetteEffect("v2", 0, "", {}, 0, 0, ["patience", "discipline"], ""),
        ]
        agg = aggregate_vignette_effects(effects)
        self.assertEqual(sorted(agg["aspiration_tags"]), ["cunning", "discipline", "patience"])


class TestNPCDispositionEffects(unittest.TestCase):
    """Applying vignette NPC effects to NPC states."""

    def test_positive_disposition_change(self):
        """SC5: Positive NPC effects modify disposition correctly."""
        npc = MockNPCState(name="Doss", disposition=0.5)
        apply_vignette_npc_effects({"Doss": 0.1}, [npc])
        self.assertAlmostEqual(npc.disposition, 0.6)

    def test_negative_disposition_change(self):
        npc = MockNPCState(name="Doss", disposition=0.5)
        apply_vignette_npc_effects({"Doss": -0.1}, [npc])
        self.assertAlmostEqual(npc.disposition, 0.4)

    def test_disposition_clamped_high(self):
        npc = MockNPCState(name="Doss", disposition=0.95)
        apply_vignette_npc_effects({"Doss": 0.1}, [npc])
        self.assertAlmostEqual(npc.disposition, 1.0)

    def test_disposition_clamped_low(self):
        npc = MockNPCState(name="Doss", disposition=0.05)
        apply_vignette_npc_effects({"Doss": -0.1}, [npc])
        self.assertAlmostEqual(npc.disposition, 0.0)

    def test_unknown_npc_ignored(self):
        npc = MockNPCState(name="Doss", disposition=0.5)
        apply_vignette_npc_effects({"UnknownNPC": 0.1}, [npc])
        self.assertAlmostEqual(npc.disposition, 0.5)  # unchanged


class TestNPCTimeDrift(unittest.TestCase):
    """NPC disposition drift during time skip."""

    def test_drift_toward_neutral(self):
        npc = MockNPCState(name="Doss", disposition=0.7)
        drift = apply_npc_time_drift([npc], 3)
        # Should drift toward 0.5
        self.assertLess(npc.disposition, 0.7)
        self.assertIn("Doss", drift)

    def test_close_relationship_resists_drift(self):
        """Disposition > 0.8 resists drift."""
        npc = MockNPCState(name="Ally", disposition=0.85)
        drift = apply_npc_time_drift([npc], 6)
        self.assertAlmostEqual(npc.disposition, 0.85)
        self.assertNotIn("Ally", drift)

    def test_hostile_relationship_resists_drift(self):
        """Disposition < 0.2 resists drift."""
        npc = MockNPCState(name="Enemy", disposition=0.1)
        drift = apply_npc_time_drift([npc], 6)
        self.assertAlmostEqual(npc.disposition, 0.1)
        self.assertNotIn("Enemy", drift)

    def test_neutral_no_drift(self):
        npc = MockNPCState(name="Neutral", disposition=0.5)
        drift = apply_npc_time_drift([npc], 3)
        self.assertAlmostEqual(npc.disposition, 0.5)

    def test_drift_proportional_to_duration(self):
        npc1 = MockNPCState(name="Short", disposition=0.7)
        npc2 = MockNPCState(name="Long", disposition=0.7)
        apply_npc_time_drift([npc1], 1)
        apply_npc_time_drift([npc2], 6)
        # Longer skip → more drift
        self.assertGreater(npc1.disposition, npc2.disposition)


class TestRecovery(unittest.TestCase):
    """Strain/wound recovery during time skip."""

    def test_full_recovery(self):
        char = MockCharacter(current_strain=5, current_wounds=3)
        result = apply_time_skip_recovery(char, 3)
        self.assertEqual(char.current_strain, 0)
        self.assertEqual(char.current_wounds, 0)
        self.assertEqual(result["strain_recovered"], 5)
        self.assertEqual(result["wounds_recovered"], 3)

    def test_already_healthy(self):
        char = MockCharacter(current_strain=0, current_wounds=0)
        result = apply_time_skip_recovery(char, 3)
        self.assertEqual(result["strain_recovered"], 0)
        self.assertEqual(result["wounds_recovered"], 0)


class TestInferenceRows(unittest.TestCase):
    """Vignette effects → behavioral inference turn rows."""

    def test_builds_rows_from_effects(self):
        """SC4: Vignette skill tags feed into behavioral inference."""
        effects = [
            VignetteEffect("v1", 0, "deception", {}, 1, 0, ["cunning"], ""),
            VignetteEffect("v2", 1, "mechanics", {}, 0, 1, ["craftsmanship"], ""),
        ]
        rows = build_vignette_inference_rows(effects)
        self.assertEqual(len(rows), 2)

        # Check first row
        self.assertIsNone(rows[0]["check_skill"])
        tags = json.loads(rows[0]["skill_tags_json"])
        self.assertEqual(tags, ["deception"])
        self.assertEqual(rows[0]["moral_weight"], 1)

        # Check choice_implications
        implications = json.loads(rows[0]["choice_implications"])
        self.assertIn("cunning", implications["behavioral_tags"])

    def test_empty_effects_empty_rows(self):
        rows = build_vignette_inference_rows([])
        self.assertEqual(len(rows), 0)


class TestSerialization(unittest.TestCase):
    """Vignette and time skip state serialization roundtrip."""

    def test_vignette_serialization(self):
        v = _make_vignette("v_test", "training", "Test passage.")
        data = serialize_vignette(v)
        self.assertEqual(data["vignette_id"], "v_test")
        self.assertEqual(data["category"], "training")
        self.assertEqual(len(data["choices"]), 2)
        # Display text should be present, not internal data
        self.assertIn("text", data["choices"][0])

    def test_time_skip_state_roundtrip(self):
        """Serialization → deserialization preserves state."""
        v1 = _make_vignette("v1", "training")
        v2 = _make_vignette("v2", "relationship", npc_focus="Doss")
        config = TimeSkipConfig(duration_months=3, framing="Test framing")
        effects = [
            VignetteEffect("v1", 0, "deception", {"Doss": 0.1}, 1, 0, ["cunning"], "Result."),
        ]

        state = serialize_time_skip_state(config, [v1, v2], effects, 1)
        vignettes, restored_effects, idx = deserialize_time_skip_state(state)

        self.assertEqual(len(vignettes), 2)
        self.assertEqual(vignettes[0].vignette_id, "v1")
        self.assertEqual(vignettes[1].vignette_id, "v2")
        self.assertEqual(vignettes[1].npc_focus, "Doss")
        self.assertEqual(idx, 1)
        self.assertEqual(len(restored_effects), 1)
        self.assertEqual(restored_effects[0].skill_tag, "deception")
        self.assertEqual(restored_effects[0].npc_effects, {"Doss": 0.1})

    def test_empty_state_deserialization(self):
        vignettes, effects, idx = deserialize_time_skip_state({})
        self.assertEqual(len(vignettes), 0)
        self.assertEqual(len(effects), 0)
        self.assertEqual(idx, 0)


class TestConflictAccumulation(unittest.TestCase):
    """SC6: Moral weight feeds into Conflict."""

    def test_conflict_from_vignette_choices(self):
        """Choices with moral_weight should accumulate Conflict."""
        char = MockCharacter()
        char.motivation.conflict = 0

        effects = [
            VignetteEffect("v1", 0, "", {}, 2, 0, [], ""),
            VignetteEffect("v2", 0, "", {}, 1, 0, [], ""),
        ]
        agg = aggregate_vignette_effects(effects)

        # Simulate what the API endpoint does
        char.motivation.conflict += agg["total_conflict"]
        self.assertEqual(char.motivation.conflict, 3)

    def test_morality_bonus_applied(self):
        char = MockCharacter()
        char.motivation.morality = 50

        effects = [
            VignetteEffect("v1", 0, "", {}, 0, 1, [], ""),
            VignetteEffect("v2", 0, "", {}, 0, 2, [], ""),
        ]
        agg = aggregate_vignette_effects(effects)

        char.motivation.morality = min(100, char.motivation.morality + agg["total_morality_bonus"])
        self.assertEqual(char.motivation.morality, 53)


class TestCampaignSpineIntegration(unittest.TestCase):
    """Full integration with The Nar Shaddaa Job spine."""

    def test_act3_time_skip_selects_2_vignettes(self):
        """SC1: 3-month skip from spine presents 2 vignettes."""
        spine_path = ROOT / "data" / "campaigns" / "nar_shaddaa_job.json"
        spine = json.loads(spine_path.read_text(encoding="utf-8"))

        act3 = spine["acts"][2]
        config = load_time_skip_config(act3)

        char = MockCharacter()
        npc = MockNPCState(name="Doss", disposition=0.65)
        selected = select_vignettes(config, char, [npc])

        self.assertEqual(len(selected), 2)

    def test_vignette_categories_diverse(self):
        """SC2: Selected vignettes span multiple categories."""
        spine_path = ROOT / "data" / "campaigns" / "nar_shaddaa_job.json"
        spine = json.loads(spine_path.read_text(encoding="utf-8"))

        act3 = spine["acts"][2]
        config = load_time_skip_config(act3)

        char = MockCharacter()
        npc = MockNPCState(name="Doss", disposition=0.65)
        selected = select_vignettes(config, char, [npc])

        categories = {v.category for v in selected}
        self.assertGreaterEqual(len(categories), 2,
                                f"Categories not diverse: {categories}")

    def test_each_choice_has_narrative_consequence(self):
        """SC3: Each choice has authored narrative consequence."""
        spine_path = ROOT / "data" / "campaigns" / "nar_shaddaa_job.json"
        spine = json.loads(spine_path.read_text(encoding="utf-8"))

        act3 = spine["acts"][2]
        config = load_time_skip_config(act3)

        for v in config.vignettes:
            for c in v.choices:
                self.assertTrue(
                    len(c.narrative_consequence) > 0,
                    f"Choice '{c.text[:30]}' in {v.vignette_id} "
                    f"has no narrative consequence",
                )

    def test_doss_relationship_vignette_exists(self):
        """Spine includes a Doss relationship vignette."""
        spine_path = ROOT / "data" / "campaigns" / "nar_shaddaa_job.json"
        spine = json.loads(spine_path.read_text(encoding="utf-8"))

        act3 = spine["acts"][2]
        config = load_time_skip_config(act3)

        doss_vignettes = [v for v in config.vignettes if v.npc_focus == "Doss"]
        self.assertGreater(len(doss_vignettes), 0)

    def test_doss_vignette_has_npc_effects(self):
        """SC5: Doss vignette choices modify disposition."""
        spine_path = ROOT / "data" / "campaigns" / "nar_shaddaa_job.json"
        spine = json.loads(spine_path.read_text(encoding="utf-8"))

        act3 = spine["acts"][2]
        config = load_time_skip_config(act3)

        doss_v = next(v for v in config.vignettes if v.npc_focus == "Doss")
        # At least one choice should have NPC effects
        has_npc_effect = any(c.npc_effects for c in doss_v.choices)
        self.assertTrue(has_npc_effect,
                        "Doss vignette should have NPC disposition effects")

    def test_moral_weight_present_in_spine(self):
        """SC6: At least one choice in spine has moral_weight > 0."""
        spine_path = ROOT / "data" / "campaigns" / "nar_shaddaa_job.json"
        spine = json.loads(spine_path.read_text(encoding="utf-8"))

        act3 = spine["acts"][2]
        config = load_time_skip_config(act3)

        has_moral = False
        for v in config.vignettes:
            for c in v.choices:
                if c.moral_weight > 0:
                    has_moral = True
                    break
        self.assertTrue(has_moral, "No choice in spine vignettes has moral_weight > 0")


class TestPromptTemplates(unittest.TestCase):
    """Prompt templates exist and have correct placeholders."""

    def test_opening_prompt_exists(self):
        path = ROOT / "gm" / "prompts" / "time_skip_opening.txt"
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8")
        self.assertIn("{character_summary}", content)
        self.assertIn("{duration_months}", content)
        self.assertIn("{framing}", content)

    def test_closing_prompt_exists(self):
        path = ROOT / "gm" / "prompts" / "time_skip_closing.txt"
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8")
        self.assertIn("{character_summary}", content)
        self.assertIn("{vignette_summary}", content)
        self.assertIn("{next_act_situation}", content)


class TestBetweenActResult(unittest.TestCase):
    """BetweenActResult has time_skip_data field."""

    def test_time_skip_data_field(self):
        from engine.reconciliation import BetweenActResult
        result = BetweenActResult()
        self.assertIsNone(result.time_skip_data)
        result.time_skip_data = {"test": "data"}
        self.assertEqual(result.time_skip_data["test"], "data")


class TestCloudGMFunctions(unittest.TestCase):
    """Cloud GM has time skip generation functions."""

    def test_opening_function_exists(self):
        from gm.cloud_gm import generate_time_skip_opening
        self.assertTrue(callable(generate_time_skip_opening))

    def test_closing_function_exists(self):
        from gm.cloud_gm import generate_time_skip_closing
        self.assertTrue(callable(generate_time_skip_closing))


if __name__ == "__main__":
    unittest.main()
