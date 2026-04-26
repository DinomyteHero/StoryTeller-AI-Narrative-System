"""Identity drift surfacing + introspection trigger — audit closure tests.

Closes two open items from the state matrix's "Identified Gaps" table:
- Identity drift surfacing (turn-to-turn drift policy)
- Introspection trigger logic (explicit conditions)
"""

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gm.context import (
    compute_identity_drift_cue,
    compute_introspection_trigger,
    update_drift_baseline,
)


def _character(morality: int = 50, conflict: int = 0):
    """Synthetic character — only exposes `motivation` since that's all the
    drift helper reads."""
    return SimpleNamespace(motivation=SimpleNamespace(
        morality=morality, conflict=conflict,
    ))


# ── Identity drift cue tests ──────────────────────────────────────────────

def test_drift_first_call_seeds_baseline_no_cue():
    """First call should seed baseline values and produce no cue."""
    arc_state = {}
    cue, surfaced = compute_identity_drift_cue(
        arc_state, _character(morality=50, conflict=0), turn_number=10,
    )
    assert cue == ""
    assert surfaced is False
    assert arc_state["drift_baseline_morality"] == 50
    assert arc_state["drift_baseline_conflict"] == 0


def test_drift_morality_drop_surfaces_dark_cue():
    """Morality dropping below threshold should surface a 'patience thinning'
    cue."""
    arc_state = {
        "drift_baseline_morality": 60,
        "drift_baseline_conflict": 0,
        "last_drift_surface_turn": 0,
    }
    cue, surfaced = compute_identity_drift_cue(
        arc_state, _character(morality=53, conflict=0), turn_number=10,
    )
    assert surfaced is True
    assert "patience" in cue.lower()


def test_drift_morality_rise_surfaces_light_cue():
    arc_state = {
        "drift_baseline_morality": 40,
        "drift_baseline_conflict": 0,
        "last_drift_surface_turn": 0,
    }
    cue, surfaced = compute_identity_drift_cue(
        arc_state, _character(morality=46, conflict=0), turn_number=10,
    )
    assert surfaced is True
    assert "restraint" in cue.lower()


def test_drift_conflict_accumulation_surfaces_weight_cue():
    arc_state = {
        "drift_baseline_morality": 50,
        "drift_baseline_conflict": 0,
        "last_drift_surface_turn": 0,
    }
    cue, surfaced = compute_identity_drift_cue(
        arc_state, _character(morality=50, conflict=4), turn_number=10,
    )
    assert surfaced is True
    assert "weight" in cue.lower()


def test_drift_cooldown_blocks_surfacing():
    arc_state = {
        "drift_baseline_morality": 60,
        "drift_baseline_conflict": 0,
        "last_drift_surface_turn": 8,
    }
    # Turn 10 is only 2 turns after last surface (cooldown=5)
    cue, surfaced = compute_identity_drift_cue(
        arc_state, _character(morality=53, conflict=0), turn_number=10,
    )
    assert cue == ""
    assert surfaced is False


def test_drift_below_threshold_no_cue():
    arc_state = {
        "drift_baseline_morality": 50,
        "drift_baseline_conflict": 0,
        "last_drift_surface_turn": 0,
    }
    cue, surfaced = compute_identity_drift_cue(
        arc_state, _character(morality=48, conflict=2), turn_number=10,
    )
    assert cue == ""
    assert surfaced is False


def test_drift_obligation_just_activated_surfaces_debt_cue():
    arc_state = {
        "drift_baseline_morality": 50,
        "drift_baseline_conflict": 0,
        "last_drift_surface_turn": 0,
        "obligation_just_activated": True,
    }
    cue, surfaced = compute_identity_drift_cue(
        arc_state, _character(), turn_number=10,
    )
    assert surfaced is True
    assert "debts" in cue.lower()


def test_update_drift_baseline_resets_state():
    arc_state = {
        "drift_baseline_morality": 60,
        "drift_baseline_conflict": 0,
        "obligation_just_activated": True,
        "duty_just_activated": True,
    }
    update_drift_baseline(arc_state, _character(morality=53, conflict=4), 12)
    assert arc_state["drift_baseline_morality"] == 53
    assert arc_state["drift_baseline_conflict"] == 4
    assert arc_state["last_drift_surface_turn"] == 12
    assert arc_state["obligation_just_activated"] is False
    assert arc_state["duty_just_activated"] is False


# ── Introspection trigger tests ───────────────────────────────────────────

def test_introspection_post_despair_fires():
    cue = compute_introspection_trigger(
        prev_turn_had_despair=True,
        prev_turn_pinch_fired=False,
        this_turn_has_check=True,
        turns_this_act=4,
        consecutive_no_check_turns=0,
    )
    assert "post-Despair" in cue


def test_introspection_post_pinch_fires():
    cue = compute_introspection_trigger(
        prev_turn_had_despair=False,
        prev_turn_pinch_fired=True,
        this_turn_has_check=True,
        turns_this_act=4,
        consecutive_no_check_turns=0,
    )
    assert "post-pinch-point" in cue


def test_introspection_dry_spell_fires():
    cue = compute_introspection_trigger(
        prev_turn_had_despair=False,
        prev_turn_pinch_fired=False,
        this_turn_has_check=False,
        turns_this_act=5,
        consecutive_no_check_turns=2,
    )
    assert "dry spell" in cue
    assert "change the external situation" in cue
    assert "same static posture" in cue


def test_introspection_dry_spell_needs_threshold():
    """One no-check turn alone shouldn't fire dry-spell."""
    cue = compute_introspection_trigger(
        prev_turn_had_despair=False,
        prev_turn_pinch_fired=False,
        this_turn_has_check=False,
        turns_this_act=5,
        consecutive_no_check_turns=1,
    )
    assert cue == ""


def test_introspection_silent_when_normal_combat_turn():
    cue = compute_introspection_trigger(
        prev_turn_had_despair=False,
        prev_turn_pinch_fired=False,
        this_turn_has_check=True,
        turns_this_act=5,
        consecutive_no_check_turns=0,
    )
    assert cue == ""


def test_introspection_despair_takes_priority_over_pinch():
    """Both signals → post-Despair wins (it's the more visceral one)."""
    cue = compute_introspection_trigger(
        prev_turn_had_despair=True,
        prev_turn_pinch_fired=True,
        this_turn_has_check=True,
        turns_this_act=4,
        consecutive_no_check_turns=0,
    )
    assert "post-Despair" in cue
    assert "post-pinch-point" not in cue


# ── Block builder tests on ContextPackage ─────────────────────────────────

def test_drift_block_omitted_in_combat_scene():
    from gm.context import ContextPackage, ArcState
    from engine.character import Character

    char = Character(name="Test", career="smuggler", species="human")
    arc = ArcState(
        campaign_name="t", current_act=1, total_acts=4, act_name="A",
        act_progress=0.0, current_anchor="x", next_anchor="y",
        anchors_completed=[], throughline_question="?", tension_level="medium",
        open_threads=[], closed_threads=[],
    )
    ctx = ContextPackage(
        character=char, arc=arc,
        story_summary="", recent_turns=[], active_npcs=[],
        location="", situation="",
        scene_type="combat",
        identity_drift_cue="INTERIOR DRIFT: test cue",
    )
    assert ctx.build_identity_drift_block() == ""


def test_drift_block_emits_in_social_scene():
    from gm.context import ContextPackage, ArcState
    from engine.character import Character

    char = Character(name="Test", career="smuggler", species="human")
    arc = ArcState(
        campaign_name="t", current_act=1, total_acts=4, act_name="A",
        act_progress=0.0, current_anchor="x", next_anchor="y",
        anchors_completed=[], throughline_question="?", tension_level="medium",
        open_threads=[], closed_threads=[],
    )
    ctx = ContextPackage(
        character=char, arc=arc,
        story_summary="", recent_turns=[], active_npcs=[],
        location="", situation="",
        scene_type="social",
        identity_drift_cue="INTERIOR DRIFT: test cue",
    )
    assert "test cue" in ctx.build_identity_drift_block()


def test_introspection_block_emits_in_any_scene():
    """Introspection trigger should fire even in combat — its signals
    (post-Despair etc.) are themselves narrative anchors."""
    from gm.context import ContextPackage, ArcState
    from engine.character import Character

    char = Character(name="Test", career="smuggler", species="human")
    arc = ArcState(
        campaign_name="t", current_act=1, total_acts=4, act_name="A",
        act_progress=0.0, current_anchor="x", next_anchor="y",
        anchors_completed=[], throughline_question="?", tension_level="medium",
        open_threads=[], closed_threads=[],
    )
    ctx = ContextPackage(
        character=char, arc=arc,
        story_summary="", recent_turns=[], active_npcs=[],
        location="", situation="",
        scene_type="combat",
        introspection_trigger="INTROSPECTION TRIGGER (post-Despair): slow down",
    )
    assert "post-Despair" in ctx.build_introspection_trigger_block()


def test_pacing_block_adds_scene_motion_governor_for_late_quiet_turns():
    from gm.context import ContextPackage, ArcState
    from engine.character import Character

    char = Character(name="Test", career="smuggler", species="human")
    arc = ArcState(
        campaign_name="t", current_act=1, total_acts=4, act_name="A",
        act_progress=0.5, current_anchor="x", next_anchor="y",
        anchors_completed=[], throughline_question="?", tension_level="medium",
        open_threads=[], closed_threads=[], turns_this_act=4,
        anchor_proximity="approaching",
    )
    ctx = ContextPackage(
        character=char, arc=arc,
        story_summary="", recent_turns=[], active_npcs=[],
        location="Temple", situation="Wait and think.",
        scene_type="introspection",
    )

    block = ctx.build_pacing_block()

    assert "SCENE MOTION GOVERNOR" in block
    assert "person, place, clue, or decision point" in block
