"""Tests for emergent faction reactivity in _post_turn_world_state_hook.

The hook converts player actions into small, accumulated `delta` shifts in
`arc_state["faction_emergent"]`, which downstream rendering (in
`_build_faction_reactivity_block`) surfaces as "tightening" or "easing"
attention. The investigative-verb branch was added in the depth-pass
follow-up so 5-turn investigative play actually moves the needle.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.game_routes import _post_turn_world_state_hook


JEDI = {
    "faction_id": "jedi_praxeum",
    "name": "Jedi Praxeum",
    "alignment": "friendly",
    "trigger_keywords": ["jedi", "praxeum", "luke", "tionne", "kira"],
}
EMPIRE = {
    "faction_id": "imperial_remnant",
    "name": "Imperial Remnant",
    "alignment": "hostile",
    "trigger_keywords": ["imperial", "tannen", "tie", "stormtrooper"],
}
SPINE = {"factions": [JEDI, EMPIRE]}
ACT = {"scene_factions": []}


def _run(actions: list[str], spine=SPINE, act=ACT) -> dict:
    arc_state: dict = {}
    for action in actions:
        _post_turn_world_state_hook(
            arc_state,
            spine=spine,
            current_act=act,
            player_action=action,
        )
    return arc_state.get("faction_emergent", {})


# ── Existing combat / affiliation behavior preserved ────────────────


def test_help_friendly_faction_tightens_attention():
    emergent = _run(["I help the Jedi defend the temple."])
    assert emergent["Jedi Praxeum"]["delta"] == 0.05


def test_attack_hostile_tightens_their_attention():
    emergent = _run(["I attack the imperial patrol."])
    assert emergent["Imperial Remnant"]["delta"] == 0.05


# ── New investigative / communicative branches ──────────────────────


def test_investigative_verb_against_hostile_faction():
    emergent = _run(["I investigate the imperial signals."])
    assert "Imperial Remnant" in emergent
    assert emergent["Imperial Remnant"]["delta"] == 0.04


def test_question_npc_about_friendly_faction():
    emergent = _run(["I question Tionne about the Praxeum's old vaults."])
    # Both Jedi keywords (tionne, praxeum) match — friendly investigative shift.
    assert emergent["Jedi Praxeum"]["delta"] == 0.02


def test_warn_friendly_faction_aligns_with_them():
    emergent = _run(["I warn Luke about the threat to the Praxeum."])
    assert emergent["Jedi Praxeum"]["delta"] == 0.04


def test_report_about_hostile_faction_undermines_them():
    emergent = _run(["I report the imperial movements to New Republic intelligence."])
    assert emergent["Imperial Remnant"]["delta"] == -0.04


def test_shelter_friendly_target_registers_approval():
    emergent = _run(["I shelter the wounded Jedi student inside the cave."])
    assert emergent["Jedi Praxeum"]["delta"] == 0.03


def test_conceal_from_hostile_faction_obstructs():
    emergent = _run(["I conceal the cache from the imperial scanners."])
    assert emergent["Imperial Remnant"]["delta"] == -0.03


def test_aid_synonym_treated_as_help():
    emergent = _run(["I aid Kira through the kata."])
    # 'kira' is a Jedi trigger keyword and 'aid' is now in the friendly group.
    assert emergent["Jedi Praxeum"]["delta"] == 0.05


# ── The pre-existing-bug regression: pure investigative play moves the needle


def test_investigative_only_run_accumulates_emergent_state():
    """Five turns of investigation, no combat. Before the fix this stayed empty."""
    actions = [
        "I observe the imperial shuttle traffic from the ridge.",
        "I probe Tionne for what she knows about the Massassi ruins.",
        "I trace the imperial transponder back through the logs.",
        "I follow the imperial courier at a distance.",
        "I question Kira about her unusual blade stance.",
    ]
    emergent = _run(actions)

    # The fix is meaningful only if at least one non-zero entry survives the run.
    nonzero = {f: d for f, d in emergent.items()
               if isinstance(d, dict) and abs(d.get("delta", 0)) > 0}
    assert nonzero, f"Investigative play left faction_emergent empty: {emergent}"

    # And specifically: the imperial faction should have tightened attention
    # because the player kept brushing against imperial keywords.
    assert emergent["Imperial Remnant"]["delta"] > 0


# ── Capping and recent_action tracking ──────────────────────────────


def test_delta_capped_to_plausible_range():
    # 20x identical investigations against a hostile faction would naively reach
    # 0.04 * 20 = 0.8 — capped to 0.5.
    emergent = _run(["I investigate the imperial activity."] * 20)
    assert emergent["Imperial Remnant"]["delta"] == 0.5


def test_recent_action_recorded():
    emergent = _run(["I question Tionne about the imperial broadcasts."])
    assert "tionne" in emergent["Jedi Praxeum"]["recent_action"].lower()
    assert "imperial" in emergent["Imperial Remnant"]["recent_action"].lower()


# ── No firing when faction not in scene and no keyword match ────────


def test_no_shift_when_faction_irrelevant():
    emergent = _run(["I sit by the window and think about home."])
    assert emergent == {}
