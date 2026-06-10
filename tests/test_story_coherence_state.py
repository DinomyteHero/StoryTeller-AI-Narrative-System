"""Regression tests for live story coherence state.

These cover the failure mode seen in playtest: the prose moved the scene,
but runtime context kept sending older location/NPC/thread assumptions back
to the narrator.
"""

import json
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.game_routes import (
    _apply_narration_scene_state,
    _build_scene_description,
    _context_audit_json,
    _deterministic_thread_updates,
    _sanitize_check_decision,
    _select_active_scene_npcs,
)
from engine.character import Character
from engine.dice import DicePool, RollResult
from gm.cloud_gm import _parse_response
from gm.context import ArcState, ContextPackage, NPCState, TurnMemory
from gm.fast_gm import CheckDecision


def _act():
    return {
        "name": "The New Students",
        "anchor": "Kira's distraction surfaces",
        "anchor_description": "Discover why Kira is drawn below the temple.",
        "opening_location": "upper meditation level of the Jedi Praxeum, Yavin 4",
        "open_threads": [
            "Why does Kira Denn seem distracted during training?",
            "What is the history of the Massassi temples beneath the Praxeum?",
        ],
    }


def test_scene_type_sanitizer_rejects_impossible_space_combat():
    decision = CheckDecision(
        requires_check=True,
        skill="leadership",
        difficulty="average",
        scene_type="space_combat",
    )

    cleaned = _sanitize_check_decision(
        decision,
        player_action='Tell Luke, "Kira needs help now."',
        ship_state=None,
    )

    assert cleaned.scene_type == "social"


def test_scene_description_starts_from_authoritative_scene_state():
    arc_state = {
        "current_location": "upper meditation level of the Jedi Praxeum, Yavin 4",
        "scene_state": {
            "current_location": "lower Massassi stairwell beneath the Jedi Praxeum, Yavin 4",
            "current_objective": "find what is calling Kira",
            "present_npcs": ["Kira Denn"],
            "immediate_pressure": "a metallic tapping continues below the stairs",
            "known_facts": ["Kira feels a pull from the lower Massassi levels."],
            "avoid_repeating": ["Do not replay Kira freezing in the doorway."],
            "next_beat_requirement": "Reveal a concrete clue.",
        },
    }

    description = _build_scene_description(
        {"narration": "Kira stopped at the archway."},
        "Step down beside Kira.",
        arc_state,
        _act(),
    )

    assert "CURRENT AUTHORITATIVE SCENE STATE" in description
    assert "lower Massassi stairwell" in description
    assert "Present NPCs: Kira Denn" in description
    assert "Reveal a concrete clue." in description


def test_active_npcs_are_filtered_to_present_or_referenced_characters():
    npcs = [
        NPCState(name="Kira Denn"),
        NPCState(name="Luke Skywalker"),
        NPCState(name="Tionne Solusar"),
    ]
    arc_state = {"scene_state": {"present_npcs": ["Kira Denn"]}}

    active = _select_active_scene_npcs(
        npcs,
        arc_state,
        _act(),
        "Kira hears the tapping below.",
    )

    assert [npc.name for npc in active] == ["Kira Denn"]


def test_narration_state_patch_updates_location_npcs_and_threads():
    npcs = [NPCState(name="Kira Denn"), NPCState(name="Luke Skywalker")]
    arc_state = {
        "current_location": "upper meditation level of the Jedi Praxeum, Yavin 4",
        "scene_state": {
            "current_location": "upper meditation level of the Jedi Praxeum, Yavin 4",
            "present_npcs": ["Luke Skywalker"],
            "known_facts": [],
        },
        "consecutive_no_check_turns": 1,
    }
    result = SimpleNamespace(
        passage=(
            "You and Kira enter the lower Massassi stairwell. The sealed stairs "
            "end at a cold landing, and Kira admits the lower Massassi levels "
            "have been calling to her since training began."
        ),
        state_patch={
            "current_location": "lower Massassi stairwell beneath the Jedi Praxeum, Yavin 4",
            "current_objective": "learn what is calling Kira",
            "present_npcs": ["Kira Denn"],
            "scene_type": "exploration",
            "known_facts": ["Kira feels called by something below the temple."],
        },
    )

    updates = _apply_narration_scene_state(
        arc_state=arc_state,
        current_act=_act(),
        npc_states=npcs,
        narration_result=result,
        player_action="Follow Kira down the sealed stairs.",
        scene_type="exploration",
        recent_turns=[],
        turn_number=4,
    )

    assert arc_state["current_location"].startswith("lower Massassi stairwell")
    assert arc_state["scene_state"]["present_npcs"] == ["Kira Denn"]
    assert npcs[0].last_seen_turn == 4
    assert "Why does Kira Denn seem distracted during training?" in updates["threads_resolved"]
    assert "What is calling Kira from the lower Massassi levels?" in updates["threads_opened"]


def test_repetition_guard_prevents_another_static_kira_hesitation_beat():
    npcs = [NPCState(name="Kira Denn")]
    recent = [
        TurnMemory(1, "Wait.", "Kira stops at the archway."),
        TurnMemory(2, "Ask Kira.", "Kira goes still before answering."),
    ]
    arc_state = {"scene_state": {"present_npcs": ["Kira Denn"]}}
    result = SimpleNamespace(
        passage="Kira freezes again in the doorway.",
        state_patch={},
    )

    _apply_narration_scene_state(
        arc_state=arc_state,
        current_act=_act(),
        npc_states=npcs,
        narration_result=result,
        player_action="Watch Kira.",
        scene_type="exploration",
        recent_turns=recent,
        turn_number=3,
    )

    assert any(
        "Do not spend another beat on Kira merely hesitating" in guard
        for guard in arc_state["scene_state"]["avoid_repeating"]
    )


def test_thread_updates_advance_massassi_mystery_without_repeating_old_question():
    updates = _deterministic_thread_updates(
        "Kira says the lower Massassi levels have been calling to her."
    )

    assert "Why does Kira Denn seem distracted during training?" in updates["threads_resolved"]
    assert "What is calling Kira from the lower Massassi levels?" in updates["threads_opened"]
    assert "What is the history of the Massassi temples beneath the Praxeum?" in updates["threads_advanced"]


def test_context_audit_redacts_future_spoiler_fields():
    ctx = ContextPackage(
        character=Character(name="Test", career="mystic", species="mirialan"),
        arc=ArcState(
            campaign_name="Shadows of the Custodian",
            current_act=1,
            total_acts=5,
            act_name="The New Students",
            act_progress=0.25,
            current_anchor="academy_arrival",
            next_anchor="night_investigation",
            anchors_completed=[],
            throughline_question="?",
            tension_level="low",
            open_threads=[],
            closed_threads=[],
        ),
        story_summary="",
        recent_turns=[],
        active_npcs=[
            NPCState(
                name="Luke Skywalker",
                knows=[
                    "Kira Denn is the daughter of Jedi Knight Seren Denn.",
                    "A surviving Inquisitor named Malakai is near Yavin 4.",
                ],
                motivation="Protect Kira from Malakai and Seren Denn's past.",
            )
        ],
        location="Yavin 4",
        situation="Opening",
    )

    payload = json.loads(_context_audit_json(ctx))
    dumped = json.dumps(payload)

    assert "Seren Denn" not in dumped
    assert "Malakai" not in dumped
    assert "Private unresolved secret" in dumped


def test_parse_response_extracts_hidden_state_patch():
    passage = " ".join(["word"] * 160)
    raw = (
        f"{passage}\n\n---CHOICES---\n"
        "1. Follow Kira down the sealed stairs.\n"
        "2. Ask Luke for the truth. [Leadership]\n"
        "---STATE_PATCH---\n"
        '{"current_location":"lower Massassi stairwell beneath the Jedi Praxeum, Yavin 4",'
        '"present_npcs":["Kira Denn"],"scene_type":"exploration",'
        '"known_facts":["Kira can hear something below."]}'
    )

    result = _parse_response(raw)

    assert result.choices == [
        "Follow Kira down the sealed stairs.",
        "Ask Luke for the truth.",
    ]
    assert result.skill_tags == [None, "leadership"]
    assert result.state_patch["current_location"].startswith("lower Massassi")
    assert result.state_patch["present_npcs"] == ["Kira Denn"]


def test_failed_social_dice_block_withholds_core_answer():
    ctx = ContextPackage(
        character=Character(name="Test", career="mystic", species="mirialan"),
        arc=ArcState(
            campaign_name="Shadows of the Custodian",
            current_act=1,
            total_acts=5,
            act_name="The New Students",
            act_progress=0.25,
            current_anchor="academy_arrival",
            next_anchor="night_investigation",
            anchors_completed=[],
            throughline_question="?",
            tension_level="rising",
            open_threads=[],
            closed_threads=[],
        ),
        story_summary="",
        recent_turns=[],
        active_npcs=[NPCState(name="Kira Denn")],
        location="Yavin 4",
        situation="Ask Kira what she is hiding.",
        scene_type="social",
        dice_pool=DicePool(ability=2, difficulty=2),
        roll_result=RollResult(
            net_successes=0,
            net_advantages=1,
            succeeded=False,
            outcome_quadrant="failure_advantage",
        ),
    )

    block = ctx.build_dice_result_block()

    assert "FAILURE: The player's stated goal does not happen" in block
    assert "The main answer remains withheld" in block
    assert "SOCIAL FAILURE" in block
    assert "reveal the withheld secret" in block


def test_failed_pure_force_block_forbids_exact_read():
    ctx = ContextPackage(
        character=Character(name="Test", career="mystic", species="mirialan"),
        arc=ArcState(
            campaign_name="Shadows of the Custodian",
            current_act=1,
            total_acts=5,
            act_name="The New Students",
            act_progress=0.25,
            current_anchor="academy_arrival",
            next_anchor="night_investigation",
            anchors_completed=[],
            throughline_question="?",
            tension_level="rising",
            open_threads=[],
            closed_threads=[],
        ),
        story_summary="",
        recent_turns=[],
        active_npcs=[NPCState(name="Kira Denn")],
        location="Yavin 4",
        situation="Sense what waits below.",
        scene_type="exploration",
        dice_pool=DicePool(force=1),
        roll_result=RollResult(
            light_pips=0,
            dark_pips=0,
            succeeded=False,
            outcome_quadrant="failure_advantage",
        ),
        force_check_kind="pure",
        force_result_block="FORCE RESULT:\n  Force outcome: FAILURE",
    )

    block = ctx.build_dice_result_block()

    assert "FORCE FAILURE" in block
    assert "Do not identify hidden intent" in block
    assert "Do not add the withheld secret to known_facts" in block


def test_parse_response_strips_accidental_wrapped_narration_quotes():
    inner = (
        "You ask Kira why she held back, and the question lands harder than "
        "you meant it to. "
        + "The stairwell stays cold, the sealed stones hold their silence, "
        "and Kira looks at the floor before she answers. " * 18
    )
    raw = (
        f'"{inner}"\n\n---CHOICES---\n'
        "1. Give Kira room to answer.\n"
        "2. Ask Luke to step in. [Leadership]\n"
    )

    result = _parse_response(raw)

    assert result.passage.startswith("You ask Kira")
    assert not result.passage.startswith('"')
    assert not result.passage.endswith('"')


def test_parse_response_preserves_dialogue_paragraph_quotes():
    dialogue = (
        '"Come on," she says. "If you keep staring at exits, Luke will make '
        'you meditate at one. The training remote is already watching you, '
        'and I refuse to lose a sparring partner to architecture."'
    )
    body = (
        "The upper training level smells of rain-damp robes, old stone, "
        "and the faint ozone leak from the practice remotes. Students spread "
        "into pairs while the noon maintenance bell waits to interrupt them. "
        "The common-room map remains behind you, three inks arguing about "
        "the shape of a home nobody fully understands. " * 10
    )
    raw = (
        f"{body}\n\n{dialogue}\n\n---CHOICES---\n"
        "1. Let the sparring begin.\n"
        "2. Ask about the corridor directly.\n"
    )

    result = _parse_response(raw)

    assert dialogue in result.passage


def test_parse_response_strips_wrapped_third_person_action_paragraph():
    inner = (
        "The drag stops below. "
        + "The chain waits against the lower stair, metal touching stone while "
        "Kira keeps her hand close to the wall and refuses to look down. " * 18
    )
    raw = (
        f'"{inner}"\n\n---CHOICES---\n'
        "1. Hold the landing and listen.\n"
        "2. Ask Kira what she recognizes. [Charm]\n"
    )

    result = _parse_response(raw)

    assert result.passage.startswith("The drag stops below.")
    assert not result.passage.startswith('"')
    assert not result.passage.endswith('"')


def test_prompts_include_reveal_pacing_contract():
    prompts_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "gm",
        "prompts",
    )
    # Clean voice sends system + user templates; literary is single-file.
    with open(os.path.join(prompts_dir, "narration_system.txt"), encoding="utf-8") as f:
        clean = f.read()
    with open(os.path.join(prompts_dir, "narration.txt"), encoding="utf-8") as f:
        clean += f.read()
    with open(os.path.join(prompts_dir, "narration_literary.txt"), encoding="utf-8") as f:
        literary = f.read()

    assert "REVEAL PACING" in clean
    assert "On any failure, the core attempted goal remains denied" in clean
    assert "REVEAL PACING" in literary
    assert "On any failure, the core attempted goal remains denied" in literary
