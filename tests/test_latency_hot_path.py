"""Latency hot-path tests for live turn routing.

These cover the local deterministic work that keeps common turns to one
foreground LLM call: narrator choice tags become mechanics directly, and
recoverable choice formatting does not force a second narration call.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.game_routes import (
    _decision_from_choice_tag,
    _reconcile_turn_fast_or_full,
    load_character,
)
from gm.context import ArcState
from gm.cloud_gm import _parse_response
from gm.llm_client import _prepare_kwargs


def test_narration_prompts_require_concrete_terms_for_major_mysteries():
    repo_root = Path(__file__).resolve().parents[1]

    for prompt in [
        repo_root / "gm" / "prompts" / "narration.txt",
        repo_root / "gm" / "prompts" / "narration_literary.txt",
    ]:
        text = prompt.read_text(encoding="utf-8")

        assert "concrete referent" in text
        assert "lower dark" in text
        assert "dark-side vergence beneath the Great Temple" in text
        assert "lower Massassi levels" in text


def test_force_choice_tag_becomes_pure_force_decision():
    character = load_character("clovis_beryl")

    decision = _decision_from_choice_tag(
        "force:sense",
        character,
        player_action="Reach out with the Force.",
        recent_failure_count=0,
        tension_level=3,
        ship_state=None,
    )

    assert decision is not None
    assert decision.requires_check is True
    assert decision.skill is None
    assert decision.difficulty is None
    assert decision.force_use is True
    assert decision.force_power == "sense"
    assert decision.force_pips_required >= 1


def test_empty_choice_tag_is_no_check_decision():
    character = load_character("clovis_beryl")

    decision = _decision_from_choice_tag(
        None,
        character,
        player_action="Let the silence hold.",
        recent_failure_count=0,
        tension_level=3,
        ship_state=None,
    )

    assert decision is not None
    assert decision.requires_check is False
    assert decision.skill is None
    assert decision.force_use is False
    assert decision.scene_type == "introspection"


def test_empty_dialogue_choice_tag_uses_social_scene_type():
    character = load_character("clovis_beryl")

    decision = _decision_from_choice_tag(
        None,
        character,
        player_action='Tell Kira the truth. "I should have told you sooner."',
        recent_failure_count=0,
        tension_level=3,
        ship_state=None,
    )

    assert decision is not None
    assert decision.requires_check is False
    assert decision.scene_type == "social"


def test_unknown_choice_tag_falls_back_to_decision_model():
    character = load_character("clovis_beryl")

    decision = _decision_from_choice_tag(
        "mystery_skill",
        character,
        player_action="Try something undefined.",
        recent_failure_count=0,
        tension_level=3,
        ship_state=None,
    )

    assert decision is None


def test_parse_response_recovers_bare_bullet_choices():
    passage = " ".join(["word"] * 160)
    raw = (
        f"{passage}\n\n"
        "- Reach out with the Force [Force:Sense]\n"
        "- Tell Luke the incomplete truth\n"
        "- Search the room yourself [Perception]\n"
    )

    result = _parse_response(raw)

    assert result.choices == [
        "Reach out with the Force",
        "Tell Luke the incomplete truth",
        "Search the room yourself",
    ]
    assert result.skill_tags == ["force:sense", None, "perception"]


def test_parse_response_strips_descriptive_force_tag():
    passage = " ".join(["word"] * 160)
    raw = (
        f"{passage}\n\n---CHOICES---\n"
        "1. Tell her the truth [Force:Sense -- gauge whether she believes you]\n"
        "2. Stay silent\n"
    )

    result = _parse_response(raw)

    assert result.choices[0] == "Tell her the truth"
    assert result.skill_tags[0] == "force:sense"


def test_parse_response_strips_em_dash_force_tag_description():
    passage = " ".join(["word"] * 160)
    raw = (
        f"{passage}\n\n---CHOICES---\n"
        '1. "Fall into step beside her." [Force:Sense — read her emotional state]\n'
        "2. Let her go.\n"
    )

    result = _parse_response(raw)

    assert result.choices[0] == "Fall into step beside her."
    assert result.skill_tags[0] == "force:sense"


def test_parse_response_trims_regular_skill_tag_description():
    passage = " ".join(["word"] * 160)
    raw = (
        f"{passage}\n\n---CHOICES---\n"
        "1. Move quietly through the jungle [Coordination to move quietly through the jungle]\n"
        "2. Stay with Luke.\n"
    )

    result = _parse_response(raw)

    assert result.choices[0] == "Move quietly through the jungle"
    assert result.skill_tags[0] == "coordination"


def test_kimi_narration_disables_hidden_reasoning():
    kwargs = _prepare_kwargs(
        model="moonshotai/kimi-k2.6",
        messages=[{"role": "user", "content": "test"}],
        temperature=0.4,
        max_tokens=100,
        timeout=5.0,
        seed=None,
        response_format=None,
        extra=None,
    )

    assert kwargs["extra_body"]["reasoning"] == {"enabled": False}


def test_openrouter_provider_routing_env(monkeypatch):
    import importlib
    import gm.llm_client as llm_client

    monkeypatch.setenv("NARRATIVE_BACKEND", "cloud")
    monkeypatch.setenv("CLOUD_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_PROVIDER_ORDER", "deepseek,siliconflow")
    monkeypatch.setenv("OPENROUTER_PROVIDER_IGNORE", "novita")
    monkeypatch.setenv("OPENROUTER_ALLOW_FALLBACKS", "true")
    reloaded = importlib.reload(llm_client)

    try:
        kwargs = reloaded._prepare_kwargs(
            model="deepseek/deepseek-v4-flash",
            messages=[{"role": "user", "content": "test"}],
            temperature=0.4,
            max_tokens=100,
            timeout=5.0,
            seed=None,
            response_format=None,
            extra=None,
        )

        provider = kwargs["extra_body"]["provider"]
        assert provider["order"] == ["deepseek", "siliconflow"]
        assert provider["ignore"] == ["novita"]
        assert provider["allow_fallbacks"] is True
    finally:
        importlib.reload(llm_client)


def test_parse_response_strips_choice_annotation_parenthetical():
    passage = " ".join(["word"] * 160)
    raw = (
        f"{passage}\n\n---CHOICES---\n"
        "1. Hold the meditation posture.** (Refusing to let worry pull you out of discipline.)\n"
        "2. Reach out with the Force.** (An active sensing attempt. [Force:Sense])\n"
    )

    result = _parse_response(raw)

    assert result.choices == [
        "Hold the meditation posture.",
        "Reach out with the Force.",
    ]
    assert result.skill_tags == [None, "force:sense"]


def test_fast_reconciliation_updates_progress_and_mission():
    arc = ArcState(
        campaign_name="Shadows of the Custodian",
        current_act=1,
        total_acts=5,
        act_name="The New Students",
        act_progress=0.30,
        current_anchor="Kira's secret surfaces",
        next_anchor="Night whispers",
        anchors_completed=[],
        throughline_question="What will the student do with dangerous truth?",
        tension_level="3",
        open_threads=[],
        closed_threads=[],
    )

    recon, zero_count, escalated = _reconcile_turn_fast_or_full(
        session_id="test",
        turn_number=3,
        prior_zero_delta_count=4,
        narration="Kira listens as the truth lands between you.",
        player_action='Tell Kira the truth. "I should have told you sooner."',
        check_result="",
        active_npcs=[],
        arc=arc,
        spine_act={"expected_turns": [8, 12], "anchor": "Kira's secret surfaces"},
        spine={},
    )

    assert escalated is False
    assert zero_count == 0
    assert recon.story_progress["progress_delta"] > 0
    assert recon.story_progress["anchor_proximity"] == "approaching"
    assert recon.dramatic_mission["selected_mission"] == "character_reveal"
