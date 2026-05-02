"""Phase 25 runtime experience redesign — tests.

Covers: choice tag classifier, personality axes, codex surface logic,
stakes computation, set piece treatment, foreshadowing, achievements,
and the dashboard endpoint.
"""

import json
import pytest

from gm.choice_tags import (
    parse_choice_tags,
    ChoiceCost,
    _is_visible_cost_tag,
    _is_codex_link_tag,
    format_costs_inline,
)
from engine.character import (
    Character, OpposedPair, BeliefCommitment, default_personality_axes,
    Species, Career, GameLine, DEFAULT_OPPOSED_PAIRS,
)
from gm.runtime_experience import (
    select_available_codex_entries,
    build_codex_block,
    annotate_axis_movement,
    build_personality_axis_block,
    build_personality_locks_block,
    lookup_set_piece,
    build_set_piece_block,
    compute_stakes_level,
    build_stakes_block,
    select_foreshadowing,
    build_light_foreshadow_block,
    mark_light_foreshadow_delivered,
    evaluate_achievements,
    increment_achievement_progress,
    should_emit_goal_priming,
    build_goal_priming_block,
    build_recap,
    find_personality_lock_for_anchor,
    build_personality_lock_block,
    get_scene_treatment,
)


# ── Choice tag classifier (§2.2) ──────────────────────────────────


class TestChoiceTagClassifier:
    def test_skill_tag_stripped(self):
        display, info = parse_choice_tags("Bluff past the guards [Deception]")
        assert display == "Bluff past the guards"
        assert info.skill_tag == "Deception"
        assert info.visible_costs == []
        assert info.codex_link is None

    def test_visible_cost_tag_kept(self):
        display, info = parse_choice_tags("Push the guards aside [Force commit: 1]")
        assert "[Force commit: +1]" in display
        assert info.skill_tag is None
        assert len(info.visible_costs) == 1
        assert info.visible_costs[0].label == "Force commit"
        assert info.visible_costs[0].value == 1

    def test_negative_morality_kept(self):
        display, info = parse_choice_tags("Pull rank [Morality: -3]")
        assert "[Morality: -3]" in display
        assert len(info.visible_costs) == 1
        assert info.visible_costs[0].value == -3

    def test_codex_link_marks_choice(self):
        display, info = parse_choice_tags("The Whispering Wakes [codex:wakes]")
        assert "codex:" not in display.lower()
        assert info.codex_link == "wakes"

    def test_skill_and_cost_combine(self):
        display, info = parse_choice_tags("Slam them down [Brawl] [Strain: 2]")
        assert "[Brawl]" not in display
        assert "[Strain: +2]" in display
        assert info.skill_tag == "Brawl"
        assert info.visible_costs[0].label == "Strain"

    def test_no_tags(self):
        display, info = parse_choice_tags("Walk past the practice remote.")
        assert display == "Walk past the practice remote."
        assert info.skill_tag is None
        assert not info.visible_costs
        assert info.codex_link is None

    def test_empty_text(self):
        display, info = parse_choice_tags("")
        assert display == ""
        assert info.skill_tag is None

    def test_visible_cost_tag_helper_exact_labels(self):
        assert _is_visible_cost_tag("Strain: 2") is not None
        assert _is_visible_cost_tag("Force commit: 1") is not None
        assert _is_visible_cost_tag("Morality: -5") is not None
        assert _is_visible_cost_tag("Conflict: +3") is not None
        # Skill tags should not match
        assert _is_visible_cost_tag("Deception") is None
        assert _is_visible_cost_tag("Force") is None
        # Garbage values
        assert _is_visible_cost_tag("Strain: many") is None

    def test_codex_link_tag_helper(self):
        assert _is_codex_link_tag("codex:foo") == "foo"
        assert _is_codex_link_tag("codex_link:bar") == "bar"
        assert _is_codex_link_tag("not_codex:foo") is None
        assert _is_codex_link_tag("codex:") is None

    def test_format_costs_inline(self):
        costs = [ChoiceCost("Strain", 2), ChoiceCost("Morality", -1)]
        formatted = format_costs_inline(costs)
        assert "[Strain: +2]" in formatted
        assert "[Morality: -1]" in formatted


# ── Personality axes (§2.6) ───────────────────────────────────────


class TestPersonalityAxes:
    def _make_character(self):
        c = Character(
            name="Test",
            species=Species.HUMAN,
            career=Career.SMUGGLER,
            primary_game_line=GameLine.EDGE_OF_EMPIRE,
            wound_threshold=10,
            strain_threshold=10,
            soak=2,
        )
        c.personality_axes = default_personality_axes()
        return c

    def test_default_axes_present(self):
        axes = default_personality_axes()
        # 5 axes (Light/Dark lives on morality)
        assert len(axes) == 5
        # All start at 50
        for axis in axes:
            assert axis.pole_a_value == 50

    def test_axis_pole_b_value_property(self):
        axis = OpposedPair(
            pair_id="x", pole_a_label="A", pole_b_label="B",
            pole_a_value=70,
        )
        assert axis.pole_b_value == 30

    def test_axis_dominant_pole(self):
        axis = OpposedPair(
            pair_id="x", pole_a_label="A", pole_b_label="B",
            pole_a_value=70,
        )
        assert axis.dominant_pole() == "A"
        axis.pole_a_value = 30
        assert axis.dominant_pole() == "B"
        axis.pole_a_value = 50
        assert axis.dominant_pole() == "balanced"

    def test_adjust_axis_clamps(self):
        c = self._make_character()
        c.adjust_axis("reckless_cautious", 60, "test cue")
        axis = c.find_axis("reckless_cautious")
        assert axis.pole_a_value == 100
        assert axis.last_cue == "test cue"
        c.adjust_axis("reckless_cautious", -200, "")
        assert c.find_axis("reckless_cautious").pole_a_value == 0

    def test_adjust_axis_unknown_returns_false(self):
        c = self._make_character()
        assert c.adjust_axis("not_real", 5, "") is False

    def test_annotate_axis_movement_keywords(self):
        movements = annotate_axis_movement("Charge into the fray with no plan")
        # Should detect reckless
        pair_ids = [m[0] for m in movements]
        assert "reckless_cautious" in pair_ids
        for (pair_id, delta, cue) in movements:
            if pair_id == "reckless_cautious":
                assert delta > 0  # toward Reckless
                assert "Charge" in cue

    def test_annotate_axis_no_keywords(self):
        movements = annotate_axis_movement("Take the eastern path.")
        assert movements == []

    def test_personality_axis_block_renders(self):
        c = self._make_character()
        c.adjust_axis("reckless_cautious", 30, "test")
        block = build_personality_axis_block(c)
        assert "Reckless" in block
        assert "Cautious" in block
        assert "PERSONALITY AXES" in block

    def test_personality_axis_block_empty_when_no_axes(self):
        c = self._make_character()
        c.personality_axes = []
        assert build_personality_axis_block(c) == ""


# ── Personality locks (§2.5) ─────────────────────────────────────


class TestPersonalityLocks:
    def _make_character(self):
        return Character(
            name="Test",
            species=Species.HUMAN,
            career=Career.SMUGGLER,
            primary_game_line=GameLine.EDGE_OF_EMPIRE,
            wound_threshold=10,
            strain_threshold=10,
            soak=2,
        )

    def test_add_personality_lock(self):
        c = self._make_character()
        c.add_personality_lock(
            anchor_id="long_watch",
            belief_text="I keep what is given to me.",
            voice_tag="keeper",
            locked_at_turn=5,
        )
        assert c.has_personality_lock_for("long_watch")
        assert len(c.personality_locks) == 1
        assert c.personality_locks[0].voice_tag == "keeper"

    def test_add_lock_replaces_existing_for_anchor(self):
        c = self._make_character()
        c.add_personality_lock("anchor1", "First belief", "tag1", 1)
        c.add_personality_lock("anchor1", "Replacement belief", "tag2", 2)
        assert len(c.personality_locks) == 1
        assert c.personality_locks[0].belief_text == "Replacement belief"

    def test_locks_block_renders(self):
        c = self._make_character()
        c.add_personality_lock("a1", "I keep what is given.", "keeper", 1)
        block = build_personality_locks_block(c)
        assert "I keep what is given." in block
        assert "BELIEF COMMITMENTS" in block

    def test_locks_block_empty_when_no_locks(self):
        c = self._make_character()
        assert build_personality_locks_block(c) == ""

    def test_find_personality_lock_for_anchor(self):
        spine = {
            "personality_lock_moments": [
                {"anchor_id": "long_watch", "prompt_text": "x" * 20,
                 "belief_options": [
                     {"belief_text": "x" * 10, "axis_effects": {}, "voice_tag": ""},
                     {"belief_text": "y" * 10, "axis_effects": {}, "voice_tag": ""},
                 ]},
            ]
        }
        moment = find_personality_lock_for_anchor(spine, "long_watch")
        assert moment is not None
        assert find_personality_lock_for_anchor(spine, "missing") is None

    def test_personality_lock_block_renders(self):
        moment = {
            "anchor_id": "x", "prompt_text": "Going forward...",
            "belief_options": [
                {"belief_text": "I act when I can.", "axis_effects": {}, "voice_tag": ""},
                {"belief_text": "I report this.", "axis_effects": {}, "voice_tag": ""},
            ],
        }
        block = build_personality_lock_block(moment)
        assert "PERSONALITY LOCK MOMENT" in block
        assert "I act when I can." in block
        assert "I report this." in block


# ── Codex surface logic (§2.1) ───────────────────────────────────


class TestCodex:
    def _make_spine(self):
        return {
            "codex": [
                {
                    "entry_id": "general",
                    "title": "General",
                    "tag": "(History Lesson)",
                    "body": "x" * 50,
                    "surface_when": {},
                },
                {
                    "entry_id": "act2_only",
                    "title": "Act 2",
                    "tag": "(History Lesson)",
                    "body": "x" * 50,
                    "surface_when": {"requires_act_minimum": 2},
                },
                {
                    "entry_id": "joran_only",
                    "title": "Joran",
                    "tag": "(Reputation)",
                    "body": "x" * 50,
                    "surface_when": {"requires_npcs": ["Joran Veska"]},
                },
                {
                    "entry_id": "praxeum_only",
                    "title": "Praxeum",
                    "tag": "(History Lesson)",
                    "body": "x" * 50,
                    "surface_when": {"requires_locations": ["temple"]},
                },
            ]
        }

    def test_act_minimum_filter(self):
        spine = self._make_spine()
        entries = select_available_codex_entries(
            spine, current_act=1, present_npcs=[], location="",
        )
        ids = [e["entry_id"] for e in entries]
        assert "general" in ids
        assert "act2_only" not in ids

    def test_npc_filter(self):
        spine = self._make_spine()
        entries = select_available_codex_entries(
            spine, current_act=2, present_npcs=["Joran Veska"], location="",
        )
        ids = [e["entry_id"] for e in entries]
        assert "joran_only" in ids

    def test_location_filter(self):
        spine = self._make_spine()
        entries = select_available_codex_entries(
            spine, current_act=2, present_npcs=[], location="The temple steps",
        )
        ids = [e["entry_id"] for e in entries]
        assert "praxeum_only" in ids

    def test_codex_block_format(self):
        spine = self._make_spine()
        entries = select_available_codex_entries(
            spine, current_act=2, present_npcs=["Joran Veska"], location="",
        )
        block = build_codex_block(entries)
        assert "AVAILABLE CODEX" in block
        assert "Joran" in block
        assert "[codex:joran_only]" in block

    def test_empty_codex_returns_empty_block(self):
        assert build_codex_block([]) == ""


# ── Set pieces + stakes (§2.8, §2.10) ────────────────────────────


class TestSetPieceAndStakes:
    def test_lookup_set_piece(self):
        spine = {
            "set_pieces": [
                {"anchor_id": "long_watch", "scene_title": "The Long Watch",
                 "word_budget_multiplier": 1.5, "visual_treatment": "scene_break",
                 "choice_count_recommendation": 5},
            ]
        }
        sp = lookup_set_piece(spine, "long_watch")
        assert sp is not None
        assert sp["scene_title"] == "The Long Watch"
        assert lookup_set_piece(spine, "missing") is None

    def test_set_piece_block(self):
        sp = {
            "anchor_id": "x", "scene_title": "The Watch",
            "word_budget_multiplier": 1.6,
            "visual_treatment": "scene_break",
            "choice_count_recommendation": 4,
        }
        block = build_set_piece_block(sp)
        assert "SET PIECE" in block
        assert "The Watch" in block
        assert "1.60x" in block

    def test_compute_stakes_levels(self):
        # critical
        assert compute_stakes_level(
            is_set_piece=False, is_personality_lock=False,
            relationship_at_threshold=False, achievement_imminent=False,
            death_or_irreversible_risk=True,
        ) == "critical"
        # high — set piece
        assert compute_stakes_level(
            is_set_piece=True, is_personality_lock=False,
            relationship_at_threshold=False, achievement_imminent=False,
            death_or_irreversible_risk=False,
        ) == "high"
        # high — personality lock
        assert compute_stakes_level(
            is_set_piece=False, is_personality_lock=True,
            relationship_at_threshold=False, achievement_imminent=False,
            death_or_irreversible_risk=False,
        ) == "high"
        # normal
        assert compute_stakes_level(
            is_set_piece=False, is_personality_lock=False,
            relationship_at_threshold=False, achievement_imminent=False,
            death_or_irreversible_risk=False,
        ) == "normal"

    def test_stakes_block_critical(self):
        block = build_stakes_block("critical")
        assert "CRITICAL" in block

    def test_stakes_block_normal_empty(self):
        assert build_stakes_block("normal") == ""

    def test_get_scene_treatment_with_set_piece(self):
        spine = {
            "set_pieces": [
                {"anchor_id": "long_watch", "scene_title": "The Long Watch",
                 "word_budget_multiplier": 1.5, "visual_treatment": "title_card",
                 "choice_count_recommendation": 5},
            ]
        }
        treatment = get_scene_treatment(spine, "long_watch", "high")
        assert treatment is not None
        assert treatment["scene_title"] == "The Long Watch"
        assert treatment["visual_treatment"] == "title_card"
        assert treatment["stakes_level"] == "high"

    def test_get_scene_treatment_no_set_piece_normal_stakes(self):
        treatment = get_scene_treatment({}, "any", "normal")
        assert treatment is None

    def test_get_scene_treatment_high_stakes_no_set_piece(self):
        # Even without a set piece, high stakes returns a treatment
        treatment = get_scene_treatment({}, "any", "critical")
        assert treatment is not None
        assert treatment["stakes_level"] == "critical"


# ── Foreshadowing (§2.9) ─────────────────────────────────────────


class TestForeshadowing:
    def _make_spine(self):
        return {
            "acts": [
                {
                    "number": 1, "name": "Act 1", "anchor": "a1",
                    "foreshadowing_plants": [
                        {"plant_act": 1, "payoff_act": 3,
                         "plant_concept": "An object on a shelf — a small carved bird.",
                         "payoff_concept": "The carved bird breaks during the climax."},
                    ],
                },
                {"number": 2, "name": "Act 2", "anchor": "a2",
                 "foreshadowing_plants": []},
                {"number": 3, "name": "Act 3", "anchor": "a3",
                 "foreshadowing_plants": []},
            ]
        }

    def test_select_plant_in_plant_act(self):
        spine = self._make_spine()
        arc_state = {}
        entry, kind = select_foreshadowing(spine, arc_state, current_act=1)
        assert entry is not None
        assert kind == "plant"

    def test_select_payoff_after_plant(self):
        spine = self._make_spine()
        arc_state = {}
        # First plant
        entry, kind = select_foreshadowing(spine, arc_state, current_act=1)
        mark_light_foreshadow_delivered(arc_state, entry, kind)
        # Now in payoff act
        entry2, kind2 = select_foreshadowing(spine, arc_state, current_act=3)
        assert entry2 is not None
        assert kind2 == "payoff"

    def test_select_no_plant_in_unrelated_act(self):
        spine = self._make_spine()
        arc_state = {}
        entry, kind = select_foreshadowing(spine, arc_state, current_act=2)
        assert entry is None
        assert kind == ""

    def test_plant_block_renders(self):
        entry = {"plant_concept": "A carved bird on a shelf",
                 "payoff_concept": "The bird breaks."}
        block = build_light_foreshadow_block(entry, "plant")
        assert "PLANT" in block
        assert "carved bird" in block

    def test_payoff_block_renders(self):
        entry = {"plant_concept": "A carved bird on a shelf",
                 "payoff_concept": "The bird breaks."}
        block = build_light_foreshadow_block(entry, "payoff")
        assert "PAYOFF" in block
        assert "bird breaks" in block


# ── Achievements (§2.7) ──────────────────────────────────────────


class TestAchievements:
    def _make_character(self):
        c = Character(
            name="Test",
            species=Species.HUMAN,
            career=Career.SMUGGLER,
            primary_game_line=GameLine.EDGE_OF_EMPIRE,
            wound_threshold=10,
            strain_threshold=10,
            soak=2,
        )
        return c

    def test_anchor_achievement_awarded(self):
        c = self._make_character()
        spine = {
            "achievements": [
                {"achievement_id": "ach_arrivals",
                 "title": "Arrived", "description": "...",
                 "visibility": "always_visible",
                 "earn_condition": {
                     "condition_type": "spine_anchor",
                     "parameters": {"anchor_id": "arrivals"},
                 }},
            ]
        }
        arc_state = {"anchors_reached": ["arrivals"]}
        earned = evaluate_achievements(spine, c, arc_state)
        assert "ach_arrivals" in earned
        assert "ach_arrivals" in c.achievements_earned

    def test_idempotent_award(self):
        c = self._make_character()
        c.achievements_earned = ["ach_a"]
        spine = {
            "achievements": [
                {"achievement_id": "ach_a",
                 "title": "x", "description": "x",
                 "visibility": "always_visible",
                 "earn_condition": {
                     "condition_type": "spine_anchor",
                     "parameters": {"anchor_id": "a"},
                 }},
            ]
        }
        arc_state = {"anchors_reached": ["a"]}
        earned = evaluate_achievements(spine, c, arc_state)
        assert earned == []
        # Still only one entry
        assert c.achievements_earned == ["ach_a"]

    def test_pattern_achievement(self):
        c = self._make_character()
        increment_achievement_progress(c, "ach_pacifist", 3)
        spine = {
            "achievements": [
                {"achievement_id": "ach_pacifist",
                 "title": "x", "description": "x",
                 "visibility": "hidden_until_earned",
                 "earn_condition": {
                     "condition_type": "pattern",
                     "parameters": {"achievement_id": "ach_pacifist", "count": 3},
                 }},
            ]
        }
        earned = evaluate_achievements(spine, c, {})
        assert "ach_pacifist" in earned

    def test_relationship_achievement(self):
        c = self._make_character()
        spine = {
            "achievements": [
                {"achievement_id": "ach_close",
                 "title": "x", "description": "x",
                 "visibility": "progress_visible",
                 "earn_condition": {
                     "condition_type": "relationship",
                     "parameters": {"npc_name": "Joran Veska",
                                    "disposition_minimum": 0.85},
                 }},
            ]
        }
        arc_state = {"npc_states": [{"name": "Joran Veska", "disposition": 0.9}]}
        earned = evaluate_achievements(spine, c, arc_state)
        assert "ach_close" in earned

    def test_unknown_condition_type_safe(self):
        c = self._make_character()
        spine = {
            "achievements": [
                {"achievement_id": "ach_unknown",
                 "title": "x", "description": "x",
                 "visibility": "always_visible",
                 "earn_condition": {"condition_type": "unknown", "parameters": {}}},
            ]
        }
        earned = evaluate_achievements(spine, c, {})
        assert "ach_unknown" not in earned


# ── Goal-priming (§3.2) ──────────────────────────────────────────


class TestGoalPriming:
    def test_act_close_triggers(self):
        assert should_emit_goal_priming(
            is_act_close=True, is_personality_lock_close=False,
            is_prologue_close=False,
        )

    def test_no_trigger(self):
        assert not should_emit_goal_priming(
            is_act_close=False, is_personality_lock_close=False,
            is_prologue_close=False,
        )

    def test_block_text(self):
        block = build_goal_priming_block("act close")
        assert "GOAL PRIMING" in block
        assert "act close" in block


# ── Recap (§3.7) ─────────────────────────────────────────────────


class TestRecap:
    def test_recap_with_turns(self):
        from gm.context import TurnMemory
        turns = [
            TurnMemory(turn_number=1, player_action="Walk", check_made=None,
                       dice_result=None, outcome_quadrant=None),
        ]
        recap = build_recap({}, turns, last_turn={"narration": "x"})
        assert recap is not None
        assert "Walk" in recap["summary"]

    def test_recap_no_turns(self):
        assert build_recap({}, [], None) is None


# ── Spine schema integration ─────────────────────────────────────


class TestSpineSchemaIntegration:
    def test_shadows_spine_phase25_content_loads(self):
        from studio.schema import CampaignSpine
        with open("data/campaigns/shadows_of_the_custodian.json") as f:
            spine = json.load(f)
        parsed = CampaignSpine(**spine)
        # Phase 25 content should be present
        assert len(parsed.codex) > 0
        assert len(parsed.achievements) > 0
        assert len(parsed.glossary) > 0
        assert len(parsed.set_pieces) > 0
        assert len(parsed.personality_lock_moments) > 0
        assert parsed.expected_relationship_count > 0
        # Acts have foreshadowing + visible titles
        assert any(act.title_visible for act in parsed.acts)
        assert any(act.foreshadowing_plants for act in parsed.acts)


# ── Cost-tag application (post-turn) ─────────────────────────────


class TestCostApplication:
    def test_strain_cost_applied(self):
        from api.game_routes import _apply_visible_cost
        c = Character(
            name="Test",
            species=Species.HUMAN,
            career=Career.SMUGGLER,
            primary_game_line=GameLine.EDGE_OF_EMPIRE,
            wound_threshold=10,
            strain_threshold=10,
            soak=2,
        )
        _apply_visible_cost(c, {}, {"label": "Strain", "value": 3})
        assert c.current_strain == 3

    def test_morality_cost_applied(self):
        from api.game_routes import _apply_visible_cost
        c = Character(
            name="Test",
            species=Species.HUMAN,
            career=Career.SMUGGLER,
            primary_game_line=GameLine.EDGE_OF_EMPIRE,
            wound_threshold=10,
            strain_threshold=10,
            soak=2,
        )
        c.motivation.morality = 50
        _apply_visible_cost(c, {}, {"label": "Morality", "value": -10})
        assert c.motivation.morality == 40

    def test_obligation_cost_applied(self):
        from api.game_routes import _apply_visible_cost
        c = Character(
            name="Test",
            species=Species.HUMAN,
            career=Career.SMUGGLER,
            primary_game_line=GameLine.EDGE_OF_EMPIRE,
            wound_threshold=10,
            strain_threshold=10,
            soak=2,
        )
        c.motivation.obligation_value = 10
        _apply_visible_cost(c, {}, {"label": "Obligation", "value": 5})
        assert c.motivation.obligation_value == 15

    def test_strain_clamped_to_threshold(self):
        from api.game_routes import _apply_visible_cost
        c = Character(
            name="Test",
            species=Species.HUMAN,
            career=Career.SMUGGLER,
            primary_game_line=GameLine.EDGE_OF_EMPIRE,
            wound_threshold=10,
            strain_threshold=10,
            soak=2,
        )
        c.current_strain = 8
        _apply_visible_cost(c, {}, {"label": "Strain", "value": 5})
        assert c.current_strain == 10  # clamped


# ── Cloud GM parser integration (§2.2/§2.3) ──────────────────────


class TestCloudGMParser:
    def test_parser_kept_visible_costs(self, monkeypatch):
        monkeypatch.setenv("NARRATION_MIN_WORDS", "20")
        # Force module-level constant refresh
        import importlib
        import gm.cloud_gm
        importlib.reload(gm.cloud_gm)
        from gm.cloud_gm import _parse_response

        raw = (
            "The cantina door slides open. " * 10
            + "\n\n---CHOICES---\n"
            "- Match the wrong name [Deception]\n"
            "- Push them aside [Force commit: 1]\n"
            "- Stand up and walk out [Cool]\n"
            "- The Whispering Wakes [codex:wakes]\n"
        )
        result = _parse_response(raw, used_local=True)
        assert len(result.choices) == 4
        # First choice: skill stripped
        assert "Deception" not in result.choices[0]
        assert result.skill_tags[0] == "deception"
        # Second choice: cost retained
        assert "Force commit" in result.choices[1]
        assert result.visible_costs[1][0]["label"] == "Force commit"
        # Fourth choice: codex link
        assert result.codex_links[3] == "wakes"

    def test_one_choice_pacing_continuation_allowed(self, monkeypatch):
        monkeypatch.setenv("NARRATION_MIN_WORDS", "20")
        import importlib
        import gm.cloud_gm
        importlib.reload(gm.cloud_gm)
        from gm.cloud_gm import _parse_response

        raw = (
            "The carriage rolls on. " * 30
            + "\n\n---CHOICES---\n"
            "- Continue\n"
        )
        result = _parse_response(raw, used_local=True)
        assert len(result.choices) == 1
        assert result.choices[0].lower().startswith("continue")
