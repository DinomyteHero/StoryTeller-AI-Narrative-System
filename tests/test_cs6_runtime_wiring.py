"""CS-6 runtime wiring tests — closes the gap where CS-6 features
existed as helpers but were never invoked from the live turn loop.

Covers: depth_card_block, pinch_point_instruction (per-turn computation),
voice_mode_instruction (mission-to-voice mapping), and resolve_variant.
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gm.context import (
    ArcState,
    ContextPackage,
    NPCState,
    build_depth_card_block,
    compute_pinch_point_instruction,
    compute_voice_mode_instruction,
    resolve_variant,
)
from engine.character import Character
from api.game_routes import _context_audit_json


PRAXEUM_PATH = Path("data/campaigns/shadows_of_the_praxeum.json")


@pytest.fixture
def praxeum_spine():
    return json.loads(PRAXEUM_PATH.read_text(encoding="utf-8"))


# ── resolve_variant ────────────────────────────────────────────────────

def test_resolve_variant_finds_existing(praxeum_spine):
    v = resolve_variant(praxeum_spine, "praxeum_student")
    assert v is not None
    assert v["id"] == "praxeum_student"


def test_resolve_variant_returns_none_for_missing(praxeum_spine):
    assert resolve_variant(praxeum_spine, "nonexistent_variant") is None


def test_resolve_variant_handles_empty_id(praxeum_spine):
    assert resolve_variant(praxeum_spine, "") is None


# ── depth_card_block ───────────────────────────────────────────────────

def test_depth_card_block_renders_for_praxeum_student(praxeum_spine):
    block = build_depth_card_block(praxeum_spine, "praxeum_student")
    assert "CHARACTER DEPTH CARD" in block
    # At least some of the 8 fields should be populated.
    assert any(label in block for label in (
        "INNER DEMON", "SECRET YEARNING", "SOCIAL MASK", "MORAL LINE",
    ))


def test_depth_card_block_empty_for_unknown_variant(praxeum_spine):
    assert build_depth_card_block(praxeum_spine, "ghost_variant") == ""


def test_depth_card_block_empty_when_no_depth_card(praxeum_spine):
    """If a variant has no depth_card data, return empty (graceful)."""
    spine_copy = json.loads(json.dumps(praxeum_spine))
    spine_copy["allegiances"][0]["character_variants"][0]["depth_card"] = None
    block = build_depth_card_block(spine_copy, "praxeum_student")
    assert block == ""


# ── compute_pinch_point_instruction ────────────────────────────────────

def test_pinch_point_fires_when_progress_reaches_target():
    spine_act = {
        "pinch_point": {
            "target_progress": 0.5,
            "description": "An Inquisitor walks the corridor.",
        }
    }
    inst = compute_pinch_point_instruction(spine_act, act_progress=0.55, pinch_point_fired=False)
    assert "ANTAGONIST PRESSURE BEAT" in inst
    assert "Inquisitor" in inst


def test_pinch_point_silent_before_target():
    spine_act = {
        "pinch_point": {
            "target_progress": 0.5,
            "description": "Pressure beat.",
        }
    }
    inst = compute_pinch_point_instruction(spine_act, act_progress=0.3, pinch_point_fired=False)
    assert inst == ""


def test_pinch_point_silent_when_already_fired():
    spine_act = {
        "pinch_point": {
            "target_progress": 0.5,
            "description": "Pressure beat.",
        }
    }
    inst = compute_pinch_point_instruction(spine_act, act_progress=0.9, pinch_point_fired=True)
    assert inst == ""


def test_pinch_point_silent_when_no_pinch_in_spine():
    inst = compute_pinch_point_instruction({}, act_progress=0.5, pinch_point_fired=False)
    assert inst == ""


# ── compute_voice_mode_instruction ─────────────────────────────────────

def test_voice_mode_action_for_attack_mission():
    inst = compute_voice_mode_instruction("attack")
    assert inst != ""
    assert "VOICE" in inst
    assert "Crisp" in inst or "staccato" in inst.lower()


def test_voice_mode_emotional_for_inner_demon_test():
    inst = compute_voice_mode_instruction("inner_demon_test")
    assert "VOICE" in inst
    assert "internal" in inst.lower() or "emotion" in inst.lower()


def test_voice_mode_empty_for_unknown_mission():
    assert compute_voice_mode_instruction("not_a_mission") == ""


def test_voice_mode_empty_for_empty_mission():
    """Turn 0 has no prior mission — should silently produce empty."""
    assert compute_voice_mode_instruction("") == ""


# ── Praxeum end-to-end CS-6 wiring sanity ──────────────────────────────

def test_praxeum_act1_has_pinch_point_data(praxeum_spine):
    """Sanity: the canonical campaign has at least one pinch point so
    the wiring will exercise in real play."""
    has_pinch = any(
        act.get("pinch_point") for act in praxeum_spine.get("acts", [])
    )
    assert has_pinch, "Praxeum should have at least one act with a pinch_point"


def test_literary_prompt_includes_cs6_runtime_placeholders():
    """The literary prose voice must not drop CS-6 story-engineering signals."""
    text = Path("gm/prompts/narration_literary.txt").read_text(encoding="utf-8")
    for placeholder in (
        "{depth_card_block}",
        "{pinch_point_instruction}",
        "{foreshadow_instruction}",
        "{closure_heartbeat_instruction}",
        "{dramatic_mission_block}",
        "{contradiction_arc_block}",
        "{voice_mode_instruction}",
    ):
        assert placeholder in text


def test_game_routes_initializes_npc_pressure_roles():
    """Both NPC initialization paths must carry pressure_role into NPCState."""
    text = Path("api/game_routes.py").read_text(encoding="utf-8")
    expected = 'pressure_role=npc_data.get("pressure_role", "")'
    assert text.count(expected) >= 2


def test_context_audit_serializes_npc_prompt_fields():
    """Audit snapshots should use NPCState's live knows/doesnt_know fields."""
    ctx = ContextPackage(
        character=Character(name="Test", career="mystic", species="mirialan"),
        arc=ArcState(
            campaign_name="Test",
            current_act=1,
            total_acts=5,
            act_name="Opening",
            act_progress=0.25,
            current_anchor="arrival",
            next_anchor="investigation",
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
                name="Kira Denn",
                knows=["The lower Massassi levels are dangerous."],
                doesnt_know=["Who is calling from below."],
                pressure_role="mirror",
            )
        ],
        location="Yavin 4",
        situation="Test",
    )

    payload = json.loads(_context_audit_json(ctx))

    npc = payload["active_npcs"][0]
    assert npc["knows"] == ["The lower Massassi levels are dangerous."]
    assert npc["doesnt_know"] == ["Who is calling from below."]
    assert npc["pressure_role"] == "mirror"


def test_npc_prompt_redacts_future_praxeum_spoilers_before_reveal_acts():
    """Private NPC knowledge must not spoil later-act Praxeum reveals."""
    ctx = ContextPackage(
        character=Character(name="Test", career="mystic", species="mirialan"),
        arc=ArcState(
            campaign_name="Shadows of the Praxeum",
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
                    "Captain Tannen's Imperial Remnant fleet is staging.",
                ],
                motivation=(
                    "Protect Kira's parentage and understand Malakai's "
                    "connection to Tannen's fleet."
                ),
            )
        ],
        location="Yavin 4",
        situation="Opening",
    )

    block = ctx.build_npc_block()

    assert "Seren Denn" not in block
    assert "Malakai" not in block
    assert "Tannen" not in block
    assert "fleet" not in block.lower()
    assert "Private unresolved secret" in block


def test_npc_prompt_allows_praxeum_spoilers_after_reveal_acts():
    ctx = ContextPackage(
        character=Character(name="Test", career="mystic", species="mirialan"),
        arc=ArcState(
            campaign_name="Shadows of the Praxeum",
            current_act=4,
            total_acts=5,
            act_name="The Betrayal",
            act_progress=0.25,
            current_anchor="betrayal_crisis",
            next_anchor="final_convergence",
            anchors_completed=[],
            throughline_question="?",
            tension_level="critical",
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
                    "Captain Tannen's Imperial Remnant fleet is staging.",
                ],
            )
        ],
        location="Yavin 4",
        situation="Act 4",
    )

    block = ctx.build_npc_block()

    assert "Seren Denn" in block
    assert "Malakai" in block
    assert "Tannen" in block
