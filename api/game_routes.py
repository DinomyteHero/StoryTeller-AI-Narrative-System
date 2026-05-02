"""
Game Engine API routes — three routes, nothing else until all three work.

POST /session              — Create session + opening narration
POST /session/{id}/turn    — Turn handler (core game loop)
GET  /session/{id}         — Load session state

POST /session/{id}/turn/stream — SSE streaming variant
"""

import json
import logging
import os
import random
import re
import threading
from dataclasses import asdict, fields
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from engine.character import Character
from engine.reconciliation import count_state_deltas
from state.telemetry import (
    emit_choice_made, emit_dice_resolved, emit_state_delta,
    emit_consequence_gap, emit_npc_disposition_shift, emit_thread_event,
)
from engine.equipment import (
    COMBAT_SKILLS,
    build_combat_damage_block,
    get_weapon_for_skill,
)
from engine.checks import (
    CheckRequest,
    DIFFICULTY_LABELS,
    build_pool,
    build_pure_force_pool,
    describe_pool_for_display,
)
from engine.force import (
    ForceResult,
    ForcePowerMilestoneChoice,
    apply_force_power_upgrade,
    apply_temptation_choice,
    build_clean_success,
    build_force_capabilities_block,
    build_force_power_milestone_choices,
    build_force_result_block,
    build_force_state_block,
    build_temptation_choice,
    build_total_failure,
    character_has_power,
    commit_force_die,
    get_available_force_dice,
    get_effective_pips_required,
    release_commitment,
    resolve_force_pips,
)
from engine.destiny import DestinyState, roll_initial_destiny
from engine.dice import DicePool, roll_pool
from engine.talents import (
    check_interventions,
    apply_intervention,
    acquire_talent,
    build_milestone_choices,
    MilestoneChoice,
)
from engine.vehicle import (
    ShipState,
    is_vehicle_skill,
    load_ship_from_spine,
    roll_vehicle_critical,
    build_vehicle_damage_block,
)
from gm.cloud_gm import (
    narrate_turn,
    narrate_turn_stream,
    _parse_response,
    CloudGMError,
    NARRATIVE_BACKEND,
)
from gm.context import (
    ArcState,
    ContextPackage,
    EmotionalState,
    NPCState,
    ThreadState,
    TurnMemory,
    build_era_voice_block,
    build_narrative_arc_block,
)
from engine.reconciliation import (
    ReconciliationResult,
    reconcile_turn,
    reconcile_turn_with_escalation,
    apply_npc_updates,
    apply_story_progress,
    apply_thread_updates,
    detect_act_boundary,
    build_anchor_instruction,
    run_between_act_pipeline,
    roll_obligation_duty,
    morality_label,
)
from gm.local_gm import (
    CheckDecision,
    SKILL_ALIASES,
    VALID_SKILLS,
    annotate_choice,
    decide_check,
    run_prose_diagnostic,
)
from state.db import get_connection
from state.memory import compress_if_needed, should_compress, compress_act_turns
from state.session import (
    create_session,
    derive_behavioral_availability,
    detect_surfaced_echoes,
    get_act_summaries,
    get_recent_narrations,
    get_recent_turns,
    get_session,
    get_turn_count,
    load_ship_state,
    load_ship_states,
    log_reputation_event,
    log_turn,
    mark_reputation_echoes_surfaced,
    select_reputation_echoes,
    save_ship_state,
    update_destiny_pool,
)

router = APIRouter()

STREAMING_ENABLED = os.getenv("STREAMING_ENABLED", "true").lower() == "true"
PROSE_DIAGNOSTIC_INLINE = os.getenv("PROSE_DIAGNOSTIC_INLINE", "false").lower() == "true"
CHOICE_ANNOTATION_ENABLED = os.getenv("CHOICE_ANNOTATION_ENABLED", "false").lower() == "true"
ANNOTATION_JOIN_TIMEOUT_SEC = float(os.getenv("ANNOTATION_JOIN_TIMEOUT_SEC", "0.2"))
RECONCILIATION_INLINE = os.getenv("RECONCILIATION_INLINE", "false").lower() == "true"
TAGGED_CHOICE_DECISIONS = os.getenv("TAGGED_CHOICE_DECISIONS", "true").lower() == "true"


# ── Phase 24: pattern-of-use tracking for talent unlocks (Mechanism 3) ──
# Maps (scene_type, skill) → pattern_id. Each occurrence bumps the counter
# on character.use_pattern_counts. When the threshold defined in
# engine.character_creation.PATTERN_THRESHOLDS is hit, the next milestone
# fires the corresponding talent unlock.
PATTERN_USE_RULES: dict[tuple[str, str], str] = {
    ("social", "negotiation"):     "consular_influence_uses",
    ("social", "charm"):           "consular_influence_uses",
    ("social", "leadership"):      "consular_influence_uses",
    ("combat", "lightsaber"):      "guardian_protection_uses",
    ("combat", "melee"):           "guardian_protection_uses",
    ("combat", "discipline"):      "guardian_protection_uses",
    ("infiltration", "perception"): "sentinel_investigation_uses",
    ("infiltration", "stealth"):    "sentinel_investigation_uses",
    ("infiltration", "skulduggery"): "sentinel_investigation_uses",
    ("introspection", "discipline"): "sentinel_investigation_uses",
}


def _track_pattern_use(character, scene_type: str | None, skill: str | None) -> None:
    """Bump a use-pattern counter when the (scene_type, skill) pair maps
    to a tracked pattern. No-op when the pair is not on the rule list."""
    if not scene_type or not skill:
        return
    key = (str(scene_type).strip().lower(), str(skill).strip().lower())
    pattern_id = PATTERN_USE_RULES.get(key)
    if not pattern_id:
        return
    from engine.character_creation import increment_use_pattern, check_pattern_unlocks, grant_pattern_unlock
    increment_use_pattern(character, pattern_id, 1)
    # Pattern unlocks are recorded immediately when the threshold is reached
    # (post-crystallization gate is enforced inside check_pattern_unlocks).
    for unlock in check_pattern_unlocks(character):
        grant_pattern_unlock(
            character, unlock["talent_id"], unlock["description"]
        )


SOCIAL_TAG_SKILLS = {"charm", "coercion", "deception", "leadership", "negotiation"}
INTRINSIC_VEHICLE_SKILLS = {
    "piloting_space", "piloting_planetary", "gunnery", "astrogation",
}
INFILTRATION_TAG_SKILLS = {
    "computers",
    "coordination",
    "skulduggery",
    "stealth",
    "streetwise",
}
EXPLORATION_TAG_SKILLS = {
    "athletics",
    "discipline",
    "lore",
    "outer_rim",
    "perception",
    "resilience",
    "survival",
    "underworld",
    "xenology",
}
SOCIAL_ACTION_CUES = (
    '"', "ask ", "tell ", "say ", "said ", "answer ", "admit ", "confess ",
    "promise ", "explain ", "truth", "lie ", "listen", "trust", "believe",
)
INTROSPECTION_ACTION_CUES = (
    "sit with", "remember", "think", "feel", "silence", "breathe",
    "meditate", "let the", "hold the",
)


def _next_turn_number(session_id: str) -> int:
    """Return the next logged player turn number.

    The opening narration is turn 0. The first player choice should therefore
    be turn 1, even though COUNT(*) is already 1 after session creation.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(turn_number), -1) + 1 FROM turns WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    return int(row[0] if row else 0)


def _normalise_choice_skill_tag(tag: str) -> str | None:
    raw = tag.lower().strip().replace("-", "_").replace(" ", "_")
    if raw.startswith("skill:"):
        raw = raw.split(":", 1)[1].strip().replace("-", "_").replace(" ", "_")
    if raw in VALID_SKILLS:
        return raw
    return SKILL_ALIASES.get(raw)


def _scene_type_for_tag(skill: str, ship_state: ShipState | None) -> str:
    if skill in COMBAT_SKILLS:
        return "combat"
    if skill in INTRINSIC_VEHICLE_SKILLS:
        return "space_combat" if ship_state else "chase"
    if skill in SOCIAL_TAG_SKILLS:
        return "social"
    if skill in INFILTRATION_TAG_SKILLS:
        return "infiltration"
    if ship_state is not None and is_vehicle_skill(skill):
        return "space_combat"
    if skill == "cool":
        return "introspection"
    if skill in EXPLORATION_TAG_SKILLS:
        return "exploration"
    return "exploration"


def _infer_no_check_scene_type(player_action: str) -> str:
    text = f" {player_action.lower()} "
    if any(cue in text for cue in SOCIAL_ACTION_CUES):
        return "social"
    if any(cue in text for cue in INTROSPECTION_ACTION_CUES):
        return "introspection"
    return "exploration"


def _tagged_difficulty(
    tension_level: int | float | str | None,
    recent_failure_count: int,
) -> str:
    try:
        tension = float(tension_level or 3)
    except (TypeError, ValueError):
        tension = 3
    if recent_failure_count >= 2 or tension <= 2:
        return "easy"
    if tension >= 5:
        return "hard"
    return "average"


def _decision_from_choice_tag(
    tag: str | None,
    character: Character,
    *,
    player_action: str,
    recent_failure_count: int,
    tension_level: int | float | str | None,
    ship_state: ShipState | None,
) -> CheckDecision | None:
    """Use narrator-provided choice tags as a deterministic fast path."""
    if not TAGGED_CHOICE_DECISIONS:
        return None

    if not tag:
        return CheckDecision(
            requires_check=False,
            scene_type=_infer_no_check_scene_type(player_action),
            reasoning="Deterministic no-check choice tag: <empty>",
        )

    raw = str(tag).strip()
    normalised = raw.lower()
    if normalised in {"", "none", "null", "no_check", "no-check"}:
        return CheckDecision(
            requires_check=False,
            scene_type=_infer_no_check_scene_type(player_action),
            reasoning=f"Deterministic no-check choice tag: {raw}",
        )

    if normalised.startswith("force"):
        power = "sense"
        if ":" in raw:
            power = raw.split(":", 1)[1].strip().lower().replace(" ", "_") or power
        elif "_" in normalised:
            maybe_power = normalised.split("_", 1)[1].strip()
            if maybe_power:
                power = maybe_power

        if character.force_rating <= 0 or not character_has_power(character, power):
            return None

        return CheckDecision(
            requires_check=True,
            skill=None,
            difficulty=None,
            scene_type="exploration",
            moral_weight=1,
            force_use=True,
            force_power=power,
            force_pips_required=get_effective_pips_required(power, character),
            reasoning=f"Deterministic Force choice tag: {raw}",
        )

    skill = _normalise_choice_skill_tag(raw)
    if not skill:
        return None

    return CheckDecision(
        requires_check=True,
        skill=skill,
        difficulty=_tagged_difficulty(tension_level, recent_failure_count),
        scene_type=_scene_type_for_tag(skill, ship_state),
        moral_weight=0,
        reasoning=f"Deterministic skill choice tag: {raw}",
    )


def _fast_anchor_proximity(progress: float) -> str:
    if progress >= 0.95:
        return "reached"
    if progress >= 0.70:
        return "imminent"
    if progress >= 0.35:
        return "approaching"
    return "distant"


def _fast_progress_delta(spine_act: dict) -> float:
    expected = spine_act.get("expected_turns", [8, 12])
    if isinstance(expected, str):
        pieces = [int(p.strip()) for p in expected.split("-") if p.strip().isdigit()]
        expected = pieces if len(pieces) == 2 else [8, 12]
    if not isinstance(expected, list) or len(expected) != 2:
        expected = [8, 12]
    midpoint = max(6, sum(int(v) for v in expected) // 2)
    return max(0.06, min(0.12, 1.0 / midpoint))


def _fast_dramatic_mission(scene_type: str, player_action: str, check_result: str) -> dict:
    text = f" {player_action.lower()} {check_result.lower()} "
    if "force" in text or "sense" in text:
        mission = "foreshadow"
        sentence = "Let the Force reveal a specific but incomplete signal that points forward."
    elif scene_type == "social" and any(cue in text for cue in ("truth", "admit", "confess", "trust")):
        mission = "character_reveal"
        sentence = "Use the conversation to expose what the protagonist chooses to risk emotionally."
    elif scene_type == "social":
        mission = "response"
        sentence = "Keep the exchange dialogue-forward and let subtext carry the pressure."
    elif scene_type == "introspection":
        mission = "inner_demon_test"
        sentence = "Make the inner conflict concrete without stalling the situation."
    else:
        mission = "thread_advance"
        sentence = "Move one established question forward without resolving it too neatly."
    return {"selected_mission": mission, "mission_sentence": sentence}


def _referenced_npc_names(active_npcs: list, *texts: str) -> list[str]:
    blob = " ".join(t or "" for t in texts).lower()
    names = []
    for npc in active_npcs or []:
        name = getattr(npc, "name", "")
        if not name:
            continue
        first = name.split()[0].lower()
        full = name.lower()
        if full in blob or (len(first) > 2 and f" {first} " in f" {blob} "):
            names.append(name)
    return names


def _fast_disposition_shift(player_action: str, narration: str) -> float:
    text = f" {player_action.lower()} {narration.lower()} "
    positive = any(
        cue in text for cue in (
            "truth", "trust", "stand beside", "tell her", "tell him",
            "admit", "confess", "listen", "protect", "help",
        )
    )
    negative = any(
        cue in text for cue in (
            "lie", "take the datapad", "force her", "force him",
            "threaten", "hide it", "conceal",
        )
    )
    if positive and not negative:
        return 0.03
    if negative and not positive:
        return -0.03
    return 0.0


def _fast_knowledge_note(player_action: str) -> str:
    action = " ".join(player_action.split())
    if len(action) > 140:
        action = action[:137].rstrip() + "..."
    return f"The player chose: {action}"


VALID_RUNTIME_SCENE_TYPES = {
    "combat", "chase", "infiltration", "social",
    "exploration", "introspection", "space_combat",
}


def _clean_state_string(value, *, max_len: int = 220) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > max_len:
        text = text[: max_len - 3].rstrip() + "..."
    return text


def _clean_state_list(values, *, max_items: int = 8, max_len: int = 180) -> list[str]:
    if not isinstance(values, list):
        return []
    cleaned: list[str] = []
    for value in values:
        text = _clean_state_string(value, max_len=max_len)
        if text and text not in cleaned:
            cleaned.append(text)
        if len(cleaned) >= max_items:
            break
    return cleaned


def _npc_aliases(name: str) -> set[str]:
    lower = name.lower()
    parts = [p for p in re.split(r"\s+", lower) if p]
    aliases = {lower, *parts}
    if lower == "luke skywalker":
        aliases.update({"master skywalker", "skywalker", "luke"})
    if lower == "kira denn":
        aliases.update({"kira"})
    if lower == "captain ress tannen":
        aliases.update({"captain tannen", "tannen", "ress tannen"})
    return aliases


def _referenced_npc_names_from_text(npc_states: list[NPCState], *texts: str) -> list[str]:
    blob = f" {' '.join(t or '' for t in texts).lower()} "
    names: list[str] = []
    for npc in npc_states or []:
        if any(f" {alias} " in blob for alias in _npc_aliases(npc.name)):
            names.append(npc.name)
    return names


# NPC location-eligibility table. Maps lowercase NPC name to the set of
# location-keyword tokens where that NPC may plausibly be physically present.
# The token "*" means any location (use sparingly — only for genuinely
# roaming characters or disembodied mystic voices).
#
# This is a runtime safety filter to prevent the cloud GM from teleporting
# Praxeum NPCs into Glass Wake scenes (or vice versa). Unknown NPCs are
# not filtered, preserving compatibility with other campaigns.
_NPC_LOCATION_DOMAINS: dict[str, frozenset[str]] = {
    # Glass Wake crew and visitors
    "captain tev": frozenset({"wake", "freighter", "shadowport", "horizon", "dock"}),
    "talon karrde": frozenset({
        "wake", "freighter", "shadowport", "horizon", "dock",
        "praxeum", "yavin", "temple", "colonnade", "academy",
        "courtyard", "great temple",
    }),
    # Praxeum cohort and staff. "horizon" is included so Joran/Tarsh can
    # appear on the descent shuttle, which is the spine-authored intro.
    "joran veska": frozenset({"praxeum", "yavin", "temple", "colonnade", "academy", "horizon", "shuttle"}),
    "rann veska": frozenset({"praxeum", "yavin", "temple", "colonnade", "academy", "courtyard"}),
    "tarsh voll": frozenset({"praxeum", "yavin", "temple", "colonnade", "academy", "horizon", "shuttle", "mess"}),
    "cassen vell": frozenset({"praxeum", "yavin", "temple", "colonnade", "academy"}),
    "olm sefa": frozenset({"praxeum", "yavin", "temple", "colonnade", "academy", "archive"}),
    "inya vorn": frozenset({"praxeum", "yavin", "temple", "colonnade", "academy", "training"}),
    "lirah tann": frozenset({"praxeum", "yavin", "temple", "colonnade", "academy", "kitchen", "medbay"}),
    "vesh karro": frozenset({"praxeum", "yavin", "temple", "colonnade", "academy"}),
    "loka hask": frozenset({"praxeum", "yavin", "temple", "colonnade", "academy"}),
    "iila vand": frozenset({"praxeum", "yavin", "temple", "colonnade", "academy"}),
    "brann riako": frozenset({"praxeum", "yavin", "temple", "colonnade", "academy", "perimeter", "watch"}),
    "luke skywalker": frozenset({"praxeum", "yavin", "temple", "colonnade", "academy", "training"}),
    "tionne": frozenset({"praxeum", "yavin", "temple", "colonnade", "academy", "archive", "great temple"}),
    "kam solusar": frozenset({"praxeum", "yavin", "temple", "colonnade", "academy", "training", "sparring"}),
    "cilghal": frozenset({"praxeum", "yavin", "temple", "colonnade", "academy", "medbay"}),
    # Streen wanders the academy; his mystical drift is allowed to colour any
    # scene through audible fragments, so we permit "*" as a special case.
    "streen": frozenset({"*"}),
    "kyp durron": frozenset({"praxeum", "yavin", "temple", "colonnade", "academy", "*"}),
    "mara jade": frozenset({"*"}),
    "kyle katarn": frozenset({"praxeum", "yavin", "temple", "colonnade", "academy", "*"}),
    # Antagonist cell — off-world by default. They may appear at specific
    # mission locations from Act 2 onward, but never at the Wake or Praxeum
    # in Act 1 unless the spine explicitly stages an incursion.
    "vornn": frozenset({"maradun", "khar delba", "off-world", "tion"}),
    "captain sarek thane": frozenset({"maradun", "khar delba", "off-world", "tion", "ambush"}),
    "doctor eilana threnn": frozenset({"maradun", "khar delba", "off-world"}),
    "drel vass": frozenset({"maradun", "khar delba", "off-world", "tion"}),
    "sona kress": frozenset({"maradun", "khar delba", "off-world", "tion"}),
}


def _npc_location_eligible(npc_name: str, current_location: str) -> bool:
    """Return True if this NPC can plausibly be physically present at the
    given location.

    Prevents the cloud GM from importing Praxeum NPCs into Glass Wake scenes
    or off-world antagonists into a goodbye dinner. Falls back to permissive
    when the NPC is not in the domain table or the location is unknown — so
    new campaigns are unaffected until they author their own table.
    """
    name_key = (npc_name or "").strip().lower()
    domains = _NPC_LOCATION_DOMAINS.get(name_key)
    if not domains:
        return True
    if "*" in domains:
        return True
    loc = (current_location or "").strip().lower()
    if not loc:
        return True
    return any(token in loc for token in domains)


def _filter_npcs_by_location(
    names: list[str],
    current_location: str,
) -> list[str]:
    """Drop any names that fail the location-eligibility check."""
    if not current_location:
        return names
    return [n for n in names if _npc_location_eligible(n, current_location)]


def _normalise_present_npcs(
    values,
    npc_states: list[NPCState],
    *fallback_texts: str,
    current_location: str = "",
) -> list[str]:
    valid = {npc.name.lower(): npc.name for npc in npc_states or []}
    by_alias = {
        alias: npc.name
        for npc in npc_states or []
        for alias in _npc_aliases(npc.name)
    }
    names: list[str] = []
    for raw in values if isinstance(values, list) else []:
        text = _clean_state_string(raw, max_len=80).lower()
        name = valid.get(text) or by_alias.get(text)
        if name and name not in names:
            names.append(name)
    for name in _referenced_npc_names_from_text(npc_states, *fallback_texts):
        if name not in names:
            names.append(name)
    names = _filter_npcs_by_location(names, current_location)
    return names[:4]


def _sanitize_scene_type(
    raw_scene_type: str | None,
    *,
    skill: str | None,
    player_action: str,
    ship_state: ShipState | None,
) -> str:
    scene_type = (raw_scene_type or "").strip().lower()
    if scene_type not in VALID_RUNTIME_SCENE_TYPES:
        scene_type = ""

    if scene_type == "space_combat":
        if ship_state is not None and skill and is_vehicle_skill(skill):
            return "space_combat"
        if skill:
            return _scene_type_for_tag(skill, None)
        return _infer_no_check_scene_type(player_action)

    if skill and skill in INTRINSIC_VEHICLE_SKILLS and ship_state is None:
        return "chase"

    return scene_type or (
        _scene_type_for_tag(skill, ship_state) if skill
        else _infer_no_check_scene_type(player_action)
    )


def _sanitize_check_decision(
    decision: CheckDecision,
    *,
    player_action: str,
    ship_state: ShipState | None,
) -> CheckDecision:
    cleaned = _sanitize_scene_type(
        decision.scene_type,
        skill=decision.skill,
        player_action=player_action,
        ship_state=ship_state,
    )
    if cleaned != decision.scene_type:
        logging.info(
            "Sanitized scene_type from %s to %s for action=%r",
            decision.scene_type, cleaned, player_action[:120],
        )
        decision.scene_type = cleaned
    return decision


def _initial_scene_state(arc_state: dict, current_act: dict) -> dict:
    existing = arc_state.get("scene_state")
    if isinstance(existing, dict):
        state = dict(existing)
    else:
        state = {}

    location = (
        state.get("current_location")
        or arc_state.get("current_location")
        or current_act.get("opening_location", "")
    )
    objective = (
        state.get("current_objective")
        or current_act.get("anchor_description")
        or current_act.get("anchor")
        or "follow the immediate situation"
    )
    return {
        "current_location": _clean_state_string(location),
        "current_objective": _clean_state_string(objective),
        "present_npcs": _clean_state_list(state.get("present_npcs", []), max_items=4),
        "scene_type": _clean_state_string(state.get("scene_type", "exploration"), max_len=40),
        "immediate_pressure": _clean_state_string(state.get("immediate_pressure", "")),
        "known_facts": _clean_state_list(state.get("known_facts", []), max_items=10),
        "avoid_repeating": _clean_state_list(state.get("avoid_repeating", []), max_items=6),
        "next_beat_requirement": _clean_state_string(
            state.get("next_beat_requirement", "")
        ),
    }


def _scene_state_block(state: dict) -> str:
    lines = ["CURRENT AUTHORITATIVE SCENE STATE:"]
    lines.append(f"Location: {state.get('current_location') or 'Unknown'}")
    if state.get("current_objective"):
        lines.append(f"Objective: {state['current_objective']}")
    if state.get("present_npcs"):
        lines.append(f"Present NPCs: {', '.join(state['present_npcs'])}")
    if state.get("immediate_pressure"):
        lines.append(f"Immediate pressure: {state['immediate_pressure']}")
    if state.get("known_facts"):
        lines.append("Known facts: " + "; ".join(state["known_facts"][:5]))
    if state.get("avoid_repeating"):
        lines.append("Do not repeat: " + "; ".join(state["avoid_repeating"][:4]))
    if state.get("next_beat_requirement"):
        lines.append(f"Next beat must: {state['next_beat_requirement']}")
    return "\n".join(lines)


def _previous_final_beat(narration: str, *, max_chars: int = 700) -> str:
    text = " ".join((narration or "").split())
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _build_scene_description(
    last_turn: dict,
    player_action: str,
    arc_state: dict,
    current_act: dict,
) -> str:
    state = _initial_scene_state(arc_state, current_act)
    social_block = _active_social_scene_block(arc_state)
    description = (
        f"{_scene_state_block(state)}\n\n"
        f"PREVIOUS FINAL BEAT: {_previous_final_beat(last_turn.get('narration', ''))}\n\n"
        f"THE PLAYER CHOSE: {player_action}"
    )
    if social_block:
        description += f"\n\n{social_block}"
    return description


def _select_active_scene_npcs(
    npc_states: list[NPCState],
    arc_state: dict,
    current_act: dict,
    *texts: str,
) -> list[NPCState]:
    state = _initial_scene_state(arc_state, current_act)
    current_location = str(
        state.get("current_location")
        or arc_state.get("current_location")
        or current_act.get("opening_location", "")
        or ""
    )
    names = _normalise_present_npcs(
        state.get("present_npcs", []),
        npc_states,
        *texts,
        current_location=current_location,
    )
    if not names:
        names = _referenced_npc_names_from_text(npc_states, *texts)
        names = _filter_npcs_by_location(names, current_location)
    name_set = set(names)
    return [npc for npc in npc_states if npc.name in name_set]


def _infer_scene_location(
    text: str,
    previous_location: str,
    current_act: dict,
) -> str:
    lower = text.lower()
    if any(token in lower for token in (
        "sealed stairs", "stairwell", "lower massassi", "lower levels",
        "dark-side vergence", "dark side vergence",
    )):
        return "lower Massassi stairwell beneath the Jedi Praxeum, Yavin 4"
    if "archway" in lower and "stairs" in lower:
        return "archway above the sealed Massassi stairs, Jedi Praxeum, Yavin 4"
    if "meditation" in lower or "training floor" in lower:
        return current_act.get("opening_location", previous_location)
    if "jungle" in lower and "temple" in lower:
        return "jungle edge outside the Great Temple, Yavin 4"
    return previous_location or current_act.get("opening_location", "")


def _infer_objective(text: str, current_act: dict) -> str:
    lower = text.lower()
    if "knocking" in lower or "tapping" in lower or "metallic tap" in lower:
        return "identify the source of the metallic sound below the sealed stairs"
    if "keycard" in lower or "sealed stairs" in lower:
        return "enter the lower Massassi levels without letting Kira face the pull alone"
    if "kira" in lower and any(token in lower for token in ("calling", "calls", "pull")):
        return "understand why the lower Massassi levels are calling to Kira"
    if "luke" in lower and "massassi" in lower:
        return "learn what Luke knows about the lower Massassi levels"
    return current_act.get("anchor_description") or current_act.get("anchor", "")


def _infer_pressure(text: str) -> str:
    lower = text.lower()
    if "knocking" in lower or "tapping" in lower or "metallic tap" in lower:
        return "a metallic sound is coming from deeper in the lower Massassi levels"
    if "cold" in lower and ("dark" in lower or "vergence" in lower):
        return "the dark-side vergence beneath the temple is becoming physically present"
    if "kira" in lower and ("freeze" in lower or "afraid" in lower or "tight" in lower):
        return "Kira is close to the thing she fears and may lose her nerve"
    return ""


def _detect_known_facts(text: str) -> list[str]:
    lower = text.lower()
    facts: list[str] = []
    if "lower massassi" in lower or "sealed stairs" in lower:
        facts.append("The lower Massassi levels are reachable through sealed stairs beneath the Praxeum.")
    if "kira" in lower and any(token in lower for token in ("calling", "calls", "pull")):
        facts.append("Kira feels a personal pull from the lower Massassi levels.")
    if "keycard" in lower:
        facts.append("Luke gave the player access to the sealed lower levels.")
    if "knocking" in lower or "tapping" in lower or "metallic tap" in lower:
        facts.append("Something below the sealed stairs is making a light metallic sound.")
    return facts


def _detect_repetition_guards(recent_turns: list[TurnMemory], narration: str) -> list[str]:
    combined = " ".join(
        [getattr(t, "narration_excerpt", "") for t in recent_turns[-4:]]
        + [narration or ""]
    ).lower()
    kira_hesitation_hits = sum(
        combined.count(token)
        for token in ("kira stops", "kira goes still", "kira freezes", "shoulders are tight")
    )
    guards: list[str] = []
    if kira_hesitation_hits >= 2:
        guards.append(
            "Do not spend another beat on Kira merely hesitating; make her act, reveal something concrete, or force a choice."
        )
    return guards


def _deterministic_thread_updates(text: str) -> dict:
    lower = text.lower()
    advanced: list[str] = []
    resolved: list[str] = []
    opened: list[str] = []

    if "kira" in lower and any(token in lower for token in ("calling", "calls", "pull", "lower massassi")):
        resolved.append("Why does Kira Denn seem distracted during training?")
        opened.append("What is calling Kira from the lower Massassi levels?")
    if any(token in lower for token in ("lower massassi", "sealed stairs", "massassi levels")):
        advanced.append("What is the history of the Massassi temples beneath the Praxeum?")
    if "dark-side vergence" in lower or "dark side vergence" in lower:
        advanced.append("What does the dark side vergence in the lower ruins mean?")
    if "luke" in lower and any(token in lower for token in ("trust", "keycard", "warning")):
        advanced.append("Can the player build genuine trust with Luke Skywalker?")
    if "knocking" in lower or "tapping" in lower or "metallic tap" in lower:
        opened.append("What is making the metallic sound below the sealed stairs?")

    return {
        "threads_advanced": _clean_state_list(advanced),
        "threads_resolved": _clean_state_list(resolved),
        "threads_opened": _clean_state_list(opened),
    }


def _merge_thread_updates(*updates: dict | None) -> dict:
    merged = {
        "threads_advanced": [],
        "threads_resolved": [],
        "threads_opened": [],
    }
    for update in updates:
        if not isinstance(update, dict):
            continue
        for key in merged:
            for item in update.get(key, []) or []:
                text = _clean_state_string(item)
                if text and text not in merged[key]:
                    merged[key].append(text)
    return merged


def _apply_narration_scene_state(
    *,
    arc_state: dict,
    current_act: dict,
    npc_states: list[NPCState],
    narration_result,
    player_action: str,
    scene_type: str,
    recent_turns: list[TurnMemory],
    turn_number: int,
    skill: str | None = None,
    ship_state: ShipState | None = None,
) -> dict:
    prior = _initial_scene_state(arc_state, current_act)
    patch = getattr(narration_result, "state_patch", {}) or {}
    text = f"{player_action}\n{getattr(narration_result, 'passage', '')}"

    location = _clean_state_string(patch.get("current_location")) or _infer_scene_location(
        text, prior.get("current_location", ""), current_act
    )
    raw_present_npcs = patch.get("present_npcs", [])
    fallback_texts = (
        (text,)
        if isinstance(raw_present_npcs, list) and raw_present_npcs
        else (text, " ".join(prior.get("present_npcs", [])))
    )
    present_npcs = _normalise_present_npcs(
        raw_present_npcs,
        npc_states,
        *fallback_texts,
        current_location=location,
    )
    if not present_npcs:
        carry = list(prior.get("present_npcs", []))
        present_npcs = _filter_npcs_by_location(carry, location)

    patch_scene = _clean_state_string(patch.get("scene_type"), max_len=40)
    final_scene_type = _sanitize_scene_type(
        patch_scene or scene_type,
        skill=skill,
        player_action=player_action,
        ship_state=ship_state,
    )

    known_facts = _clean_state_list(
        prior.get("known_facts", [])
        + _clean_state_list(patch.get("known_facts", []))
        + _detect_known_facts(text),
        max_items=12,
    )
    avoid_repeating = _clean_state_list(
        prior.get("avoid_repeating", [])
        + _clean_state_list(patch.get("avoid_repeating", []), max_items=4)
        + _detect_repetition_guards(recent_turns, getattr(narration_result, "passage", "")),
        max_items=8,
    )

    objective = _clean_state_string(patch.get("current_objective")) or _infer_objective(
        text, current_act
    )
    pressure = _clean_state_string(patch.get("immediate_pressure")) or _infer_pressure(text)
    next_requirement = _clean_state_string(patch.get("next_beat_requirement"))
    if not next_requirement and avoid_repeating:
        next_requirement = avoid_repeating[-1]
    if not next_requirement and int(arc_state.get("consecutive_no_check_turns", 0) or 0) >= 2:
        next_requirement = (
            "Change the external situation with a concrete clue, pressure, location shift, or decision point."
        )

    scene_state = {
        "current_location": location,
        "current_objective": objective,
        "present_npcs": present_npcs,
        "scene_type": final_scene_type,
        "immediate_pressure": pressure,
        "known_facts": known_facts,
        "avoid_repeating": avoid_repeating,
        "next_beat_requirement": next_requirement,
    }
    arc_state["scene_state"] = scene_state
    arc_state["current_location"] = location
    arc_state["active_npc_names"] = present_npcs
    arc_state["last_scene_type"] = final_scene_type

    for npc in npc_states:
        if npc.name in present_npcs:
            npc.last_seen_turn = turn_number

    patch_updates = {
        "threads_advanced": patch.get("threads_advanced", []),
        "threads_resolved": patch.get("threads_resolved", []),
        "threads_opened": patch.get("threads_opened", []),
    }
    return _merge_thread_updates(patch_updates, _deterministic_thread_updates(text))


def _thread_states_for_context(current_act: dict, arc_state: dict) -> list[ThreadState]:
    """Assemble ThreadState objects for the narration context.

    Pulls rich state (status, progress, hot_question, fallout) from
    arc_state["thread_state"] when available; falls back to defaults so
    legacy sessions without thread_state still work. Resolved-with-fallout
    threads remain visible to the LLM (so consequences can ripple), even
    though they're tracked in closed_threads — the LLM is told their
    status is RESOLVED_PENDING_FALLOUT.
    """
    closed = set(arc_state.get("closed_threads", []))
    rich_state = arc_state.get("thread_state", {}) or {}
    seen: set[str] = set()
    threads: list[ThreadState] = []

    def _build(name: str, base: ThreadState | None = None) -> ThreadState:
        rich = rich_state.get(name, {}) or {}
        if base is not None:
            t = base
        else:
            t = ThreadState(name=name)
        if rich:
            t.status = str(rich.get("status", t.status) or t.status)
            t.hot_question = str(rich.get("hot_question", t.hot_question) or t.hot_question)
            t.progress = float(rich.get("progress", t.progress) or 0.0)
            t.last_movement_turn = int(rich.get("last_movement_turn", t.last_movement_turn) or 0)
            t.fallout_remaining_turns = int(
                rich.get("fallout_remaining_turns", t.fallout_remaining_turns) or 0
            )
        return t

    for raw in current_act.get("open_threads", []) + arc_state.get("dynamic_threads", []):
        name = raw.name if isinstance(raw, ThreadState) else str(raw)
        if not name or name in closed or name in seen:
            continue
        seen.add(name)
        threads.append(_build(name, raw if isinstance(raw, ThreadState) else None))

    # Surface resolved-pending-fallout threads so consequences can ripple.
    for name, rich in rich_state.items():
        if name in seen:
            continue
        if rich.get("status") != "resolved_pending_fallout":
            continue
        if int(rich.get("fallout_remaining_turns", 0) or 0) <= 0:
            continue
        threads.append(_build(name))
        seen.add(name)

    return threads


# Movement-keyword heuristics for fast-path contradiction tracking. These are
# deliberately broad; the fast reconciler trades precision for latency. The
# slow LLM reconciler is what calibrates accurately when RECONCILIATION_INLINE=1.
_RESIST_LIE_KEYWORDS = (
    "tell", "admit", "confess", "reveal", "say it out loud", "say it plain",
    "trust", "ask for help", "step into the light", "stand with",
    "name them", "stop hiding", "open the door", "share", "out loud",
    "show", "show your hand", "let them see", "step forward",
    "make myself visible", "make myself seen",
)
_REINFORCE_LIE_KEYWORDS = (
    "hide", "vanish", "step back", "stay quiet", "say nothing", "withhold",
    "keep it to myself", "watch from", "stay hidden", "stay invisible",
    "back off", "lie", "deceive", "deflect", "deny", "cover", "slip away",
    "ghost", "duck out", "mask",
)
_COST_PAID_KEYWORDS = (
    "she pulled away", "they noticed", "luke's eyes", "kira's eyes",
    "caught", "exposed", "the silence cost", "too late",
)


def _fast_contradiction_tracking(player_action: str, narration: str) -> dict:
    """Heuristic contradiction-tracking signal for the fast reconciler.

    The slow LLM reconciler returns this object as JSON; the fast path
    infers it from keyword presence in the player action + narration so
    `lie_grip` still moves at default settings without a per-turn LLM call.
    Defaults to `reinforced` (the protagonist defaults to their pattern
    on a routine turn) and only flips to `resisted` when an explicit
    truth-aligned action keyword fires.
    """
    haystack = f"{player_action} {narration}".lower()
    if any(kw in haystack for kw in _RESIST_LIE_KEYWORDS):
        return {
            "contradiction_engaged": True,
            "arc_movement": "resisted",
            "arc_evidence": (player_action or "")[:160],
        }
    if any(kw in haystack for kw in _COST_PAID_KEYWORDS):
        return {
            "contradiction_engaged": True,
            "arc_movement": "cost_paid",
            "arc_evidence": (narration or "")[:160],
        }
    if any(kw in haystack for kw in _REINFORCE_LIE_KEYWORDS):
        return {
            "contradiction_engaged": True,
            "arc_movement": "reinforced",
            "arc_evidence": (player_action or "")[:160],
        }
    # Default: routine engagement that defaults to reinforcement (the
    # character operating inside their pattern). Use a slightly weaker
    # weight by tagging "reinforced" anyway — lie_grip already caps at 1.0.
    return {
        "contradiction_engaged": True,
        "arc_movement": "reinforced",
        "arc_evidence": "routine — character acted from existing pattern",
    }


def _fast_reconciliation_result(**kwargs) -> ReconciliationResult:
    player_action = kwargs.get("player_action", "")
    narration = kwargs.get("narration", "")
    check_result = kwargs.get("check_result", "")
    active_npcs = kwargs.get("active_npcs", [])
    spine_act = kwargs.get("spine_act", {}) or {}
    arc = kwargs.get("arc")
    progress = float(getattr(arc, "act_progress", 0.0) or 0.0)
    scene_type = getattr(arc, "scene_type", "") or _infer_no_check_scene_type(player_action)

    delta = _fast_progress_delta(spine_act)
    new_progress = min(1.0, progress + delta)
    npc_updates = []
    referenced = _referenced_npc_names(active_npcs, player_action, narration)
    shift = _fast_disposition_shift(player_action, narration)
    for name in referenced[:2]:
        update = {
            "npc_name": name,
            "knowledge_gained": [],
            "knowledge_lost": [],
            "disposition_shift": shift,
        }
        if any(cue in player_action.lower() for cue in ("tell", "admit", "confess", "truth", "reveal")):
            update["knowledge_gained"].append(_fast_knowledge_note(player_action))
        npc_updates.append(update)

    return ReconciliationResult(
        npc_updates=npc_updates,
        thread_updates=_merge_thread_updates(
            _deterministic_thread_updates(f"{player_action}\n{narration}"),
            {"threads_advanced": [spine_act.get("anchor", "")] if spine_act.get("anchor") else []},
        ),
        story_progress={
            "anchor_proximity": _fast_anchor_proximity(new_progress),
            "progress_delta": delta,
            "reasoning": "Deterministic fast-mode coherence update.",
        },
        dramatic_mission=_fast_dramatic_mission(scene_type, player_action, check_result),
        contradiction_tracking=_fast_contradiction_tracking(player_action, narration),
    )


def _reconcile_turn_fast_or_full(**kwargs):
    """Run full LLM reconciliation only when enabled for the live hot path."""
    if RECONCILIATION_INLINE:
        return reconcile_turn_with_escalation(**kwargs)
    prior = int(kwargs.get("prior_zero_delta_count", 0) or 0)
    recon = _fast_reconciliation_result(**kwargs)
    new_zero_delta_count = 0 if count_state_deltas(recon)["total_changes"] else prior + 1
    return recon, new_zero_delta_count, False


# ── Dynamic per-turn context helpers ──────────────────────────────────
# These three hooks plug the reputation echo, behavioral availability, and
# era voice systems into every turn handler. Call sites:
#   1. _compute_dynamic_context_fields  — before ContextPackage construction
#   2. _post_narration_reputation_hook  — after narrate_turn(), before recon
#   3. _post_reconciliation_reputation_hook — after reconcile_turn()
# Keeping these as helpers (rather than inlining at each site) ensures the
# four turn handlers stay in sync as the system evolves.

def _compute_dynamic_context_fields(
    session_id:   str,
    turn_number:  int,
    arc_state:    dict,
    current_act:  dict,
    npc_states:   list,
    spine:        dict,
    character=None,
    roll_result=None,
) -> dict:
    """Compute the dynamic per-turn context fields:
      - reputation echoes (cooldown + relevance scoring)
      - behavioral availability signal (annotation history)
      - era voice block (period anchoring)
      - identity drift cue (interior-state change since last surface)
      - introspection trigger (post-Despair / post-pinch / dry-spell)

    Identity drift and introspection require `character`; when omitted (legacy
    callers, edge cases) those fields default to empty.

    Returns a dict suitable for unpacking into ContextPackage(...) kwargs.
    """
    last_echo_turn = arc_state.get("last_reputation_echo_turn", 0)
    scene_factions = current_act.get("scene_factions", []) or []
    npc_factions: list[str] = []
    for npc in npc_states:
        npc_fact = getattr(npc, "factions", None) or []
        if isinstance(npc_fact, list):
            npc_factions.extend(str(f) for f in npc_fact)

    drift_cue = ""
    introspection = ""
    if character is not None:
        from gm.context import (
            compute_identity_drift_cue,
            compute_introspection_trigger,
        )
        drift_cue, _ = compute_identity_drift_cue(
            arc_state=arc_state,
            character=character,
            turn_number=turn_number,
        )
        this_turn_has_check = (roll_result is not None)
        consecutive_no_check = int(
            arc_state.get("consecutive_no_check_turns", 0) or 0
        )
        introspection = compute_introspection_trigger(
            prev_turn_had_despair=bool(
                arc_state.get("last_turn_had_despair", False)
            ),
            prev_turn_pinch_fired=bool(
                arc_state.get("last_turn_pinch_fired", False)
            ),
            this_turn_has_check=this_turn_has_check,
            turns_this_act=int(arc_state.get("turns_this_act", 0) or 0),
            consecutive_no_check_turns=consecutive_no_check,
        )

    # CS-6 runtime wiring (Apr 2026): pinch point firing, depth card,
    # voice mode mapping. These existed as helpers but were never invoked
    # from the live turn loop until now.
    from gm.context import (
        accumulate_contradiction_arc,
        advance_tactical_state,
        build_beat_role_block,
        build_contradiction_arc_block,
        build_depth_card_block,
        build_lore_seeds_block,
        build_narrative_arc_block,
        build_tactical_state_block,
        compute_closure_heartbeat_instruction,
        compute_foreshadow_instruction,
        compute_pinch_point_instruction,
        compute_voice_mode_instruction,
        initialize_tactical_state,
        resolve_variant,
    )

    # Tactical state lifecycle (Phase D): if the player is in a combat/
    # social/chase scene, ensure a tactical_state matches. The current
    # scene_type comes from arc_state.scene_state (set by the previous
    # turn's narration patch).
    scene_state = arc_state.get("scene_state", {}) or {}
    current_scene_type = (scene_state.get("scene_type", "") or "").lower()
    tactical_state = arc_state.get("tactical_state") or {}
    if current_scene_type in ("combat", "social", "chase"):
        existing_kind = tactical_state.get("kind") if isinstance(tactical_state, dict) else None
        expected_kind = {
            "combat": "combat",
            "social": "negotiation",
            "chase":  "chase",
        }[current_scene_type]
        if existing_kind != expected_kind:
            tactical_state = initialize_tactical_state(current_scene_type)
            arc_state["tactical_state"] = tactical_state
    else:
        if tactical_state:
            arc_state["tactical_state"] = {}
            tactical_state = {}
    pinch_inst = compute_pinch_point_instruction(
        spine_act=current_act,
        act_progress=float(arc_state.get("act_progress", 0.0) or 0.0),
        pinch_point_fired=bool(arc_state.get("pinch_point_fired", False)),
    )
    depth_card = build_depth_card_block(
        spine, str(arc_state.get("variant_id", "") or "")
    )
    voice_mode = compute_voice_mode_instruction(
        str(arc_state.get("last_dramatic_mission", "") or "")
    )
    closure_heartbeat = compute_closure_heartbeat_instruction(arc_state)
    foreshadow_inst = compute_foreshadow_instruction(
        spine=spine,
        current_act_number=int(arc_state.get("current_act", 1) or 1),
        arc_state=arc_state,
    )
    variant = resolve_variant(spine, str(arc_state.get("variant_id", "") or ""))
    protagonist_contradiction = ""
    if variant:
        protagonist_contradiction = (
            variant.get("protagonist_contradiction")
            or (variant.get("depth_card") or {}).get("inner_demon")
            or ""
        )
    contradiction_arc_block = build_contradiction_arc_block(
        arc_state, protagonist_contradiction
    )

    from gm.context import select_callback_candidates
    scene_npc_names = [getattr(n, "name", "") for n in npc_states]
    callback_candidates = select_callback_candidates(
        arc_state,
        current_turn=turn_number,
        scene_npc_names=scene_npc_names,
    )

    return {
        "reputation_entries": select_reputation_echoes(
            session_id=session_id,
            current_turn=turn_number,
            last_echo_turn=last_echo_turn,
            scene_factions=scene_factions,
            current_npc_factions=npc_factions,
        ),
        "behavioral_availability": derive_behavioral_availability(session_id),
        "era_voice_block":         build_era_voice_block(spine),
        "identity_drift_cue":      drift_cue,
        "introspection_trigger":   introspection,
        "pinch_point_instruction": pinch_inst,
        "depth_card_block":        depth_card,
        "narrative_arc_block":     build_narrative_arc_block(character),
        "beat_role_block":         build_beat_role_block(
            current_act,
            float(arc_state.get("act_progress", 0.0) or 0.0),
        ),
        "voice_mode_instruction":  voice_mode,
        "closure_heartbeat_instruction": closure_heartbeat,
        "foreshadow_instruction":        foreshadow_inst,
        "contradiction_arc_block":       contradiction_arc_block,
        "memorable_moments":             callback_candidates,
        "lore_seeds_block":              build_lore_seeds_block(spine),
        "growth_recognition_block":      str(arc_state.get("pending_growth_recognition", "") or ""),
        "tactical_state_block":          build_tactical_state_block(tactical_state or {}),
        "npc_counter_move_block":        _build_npc_counter_move_block(npc_states, arc_state),
        "faction_reactivity_block":      _build_faction_reactivity_block(arc_state, spine),
        "side_content_block":            _build_side_content_block(spine, current_act, arc_state),
        "pivot_warning_block":           _build_pivot_warning_block(spine, current_act, arc_state),
    }


def _post_narration_reputation_hook(
    turn_number:        int,
    arc_state:          dict,
    reputation_entries: list,
    passage:            str,
) -> None:
    """Mark reputation echoes that surfaced in the passage + update cooldown."""
    if not reputation_entries:
        return
    surfaced_ids = detect_surfaced_echoes(passage, reputation_entries)
    if surfaced_ids:
        mark_reputation_echoes_surfaced(surfaced_ids)
        arc_state["last_reputation_echo_turn"] = turn_number


def _post_narration_drift_hook(
    turn_number: int,
    arc_state:   dict,
    character,
    drift_cue:   str,
    roll_result,
    pinch_fired_this_turn: bool,
) -> None:
    """After narration, refresh the drift baseline if a cue surfaced and
    capture the post-Despair / post-pinch flags for next turn's introspection
    trigger.
    """
    if drift_cue and character is not None:
        from gm.context import update_drift_baseline
        update_drift_baseline(arc_state, character, turn_number)

    arc_state["last_turn_had_despair"] = bool(
        roll_result is not None and getattr(roll_result, "despairs", 0) > 0
    )
    arc_state["last_turn_pinch_fired"] = bool(pinch_fired_this_turn)
    if pinch_fired_this_turn:
        arc_state["pinch_point_fired"] = True

    # Growth recognition is a one-shot — clear after surfacing.
    if arc_state.get("pending_growth_recognition"):
        arc_state["pending_growth_recognition"] = ""


def _post_reconciliation_cs6_hook(
    arc_state: dict,
    recon_result,
    turn_number: int = 0,
    foreshadow_instruction: str = "",
    spine: Optional[dict] = None,
    character=None,
) -> None:
    """After reconciliation, capture cross-turn CS-6 state.

    Maintains four pieces of state for the next turn:
      - dramatic_mission → next turn's voice mode
      - contradiction_arc → multi-turn ledger of how the protagonist relates
        to their core contradiction
      - narrative_arc.lie_grip → Brooks/Weiland lie-grip scalar updated from
        the same per-turn signal
      - foreshadow_setups_delivered / payoffs_delivered → ensure each
        foreshadow link only surfaces once
      - turns_since_last_thread_change → drives the closure heartbeat
    """
    dm = getattr(recon_result, "dramatic_mission", None) or {}
    selected = dm.get("selected_mission") if isinstance(dm, dict) else ""
    if selected:
        arc_state["last_dramatic_mission"] = selected

    # Contradiction arc accumulation (CS-6 Phase 6) + lie_grip update
    from gm.context import accumulate_contradiction_arc
    accumulate_contradiction_arc(
        arc_state=arc_state,
        contradiction_tracking=getattr(recon_result, "contradiction_tracking", {}) or {},
        turn_number=turn_number,
        character=character,
    )

    # Foreshadow setup/payoff delivery tracking (CS-6 Phase 5 — closes audit gap)
    if foreshadow_instruction and isinstance(spine, dict):
        registry = spine.get("foreshadow_registry") or []
        delivered_setups = list(arc_state.get("foreshadow_setups_delivered", []) or [])
        delivered_payoffs = list(arc_state.get("foreshadow_payoffs_delivered", []) or [])
        current_act_num = int(arc_state.get("current_act", 1) or 1)
        is_payoff = "PAYOFF" in foreshadow_instruction
        for link in registry:
            link_id = link.get("id") if isinstance(link, dict) else None
            if not link_id:
                continue
            if is_payoff:
                if (
                    link_id in delivered_setups
                    and link_id not in delivered_payoffs
                    and int(link.get("payoff_act", 0) or 0) == current_act_num
                ):
                    delivered_payoffs.append(link_id)
                    break
            else:
                if (
                    link_id not in delivered_setups
                    and int(link.get("setup_act", 0) or 0) == current_act_num
                ):
                    delivered_setups.append(link_id)
                    break
        arc_state["foreshadow_setups_delivered"] = delivered_setups
        arc_state["foreshadow_payoffs_delivered"] = delivered_payoffs

    # Closure heartbeat counter (CS-6 Phase 8 — closes audit gap)
    tu = getattr(recon_result, "thread_updates", {}) or {}
    moved = bool(
        tu.get("threads_advanced") or tu.get("threads_resolved") or tu.get("threads_opened")
    )
    if moved:
        arc_state["turns_since_last_thread_change"] = 0
    else:
        arc_state["turns_since_last_thread_change"] = (
            int(arc_state.get("turns_since_last_thread_change", 0) or 0) + 1
        )


def _build_npc_counter_move_block(npc_states: list, arc_state: dict) -> str:
    """Phase E17: suggest the most-pressuring NPC's likely next tactical move.

    Looks at the most relevant scene NPC and produces a one-line GM cue
    so NPCs feel proactive — escalating, exploiting, sustaining pressure —
    rather than just reacting to player moves.
    """
    if not npc_states:
        return ""
    # Pick the NPC with the strongest pressure signal: lowest disposition,
    # highest active emotional intensity, or hostile pressure_role.
    def _pressure_score(n) -> float:
        score = 0.0
        disp = float(getattr(n, "disposition", 0.5) or 0.5)
        score += max(0.0, 0.5 - disp) * 2.0
        es = getattr(n, "emotional_state", None)
        if es is not None and getattr(es, "is_active", lambda: False)():
            score += float(getattr(es, "intensity", 0.0) or 0.0)
        role = (getattr(n, "pressure_role", "") or "").lower()
        if role in ("tempter", "betrayer", "escalator", "skeptic", "mirror"):
            score += 0.5
        return score

    sorted_npcs = sorted(npc_states, key=_pressure_score, reverse=True)
    candidate = sorted_npcs[0]
    if _pressure_score(candidate) < 0.3:
        return ""

    name = getattr(candidate, "name", "")
    disp = float(getattr(candidate, "disposition", 0.5) or 0.5)
    es = getattr(candidate, "emotional_state", None)
    mood = (getattr(es, "mood", "") or "").lower() if es is not None else ""
    role = (getattr(candidate, "pressure_role", "") or "").lower()
    crystallized = (getattr(candidate, "crystallized_memory", "") or "").strip()

    move_options: list[str] = []
    if disp <= 0.3:
        move_options.append(f"escalate against the protagonist (verbal sharpening, naming a wound, or producing a fresh complication)")
    elif disp <= 0.5:
        move_options.append(f"test the protagonist with a pointed question or quiet refusal")
    if mood == "betrayed":
        move_options.append("withhold something the protagonist needs, or speak with a coldness they have not used before")
    elif mood == "angry":
        move_options.append("press a grievance the protagonist would rather not revisit")
    elif mood == "afraid":
        move_options.append("ask the protagonist for protection in a way that creates obligation")
    elif mood == "grateful":
        move_options.append("offer something unprompted — information, a tool, a moment of vulnerability")
    if role == "tempter":
        move_options.append("offer the protagonist a shortcut whose cost is hidden under its appeal")
    elif role == "escalator":
        move_options.append("act independently in a way that raises the time pressure on the protagonist")
    elif role == "skeptic":
        move_options.append("voice the doubt the protagonist has been suppressing")

    if not move_options:
        return ""

    crystallized_note = ""
    if crystallized:
        crystallized_note = f" (let their sharpest memory of the protagonist — '{crystallized}' — color how they make the move)"

    return (
        f"NPC COUNTER-MOVE CUE: {name} should not just react this turn — they should "
        f"{move_options[0]}{crystallized_note}. Make it concrete, not implied."
    )


def _build_faction_reactivity_block(arc_state: dict, spine: dict) -> str:
    """Phase E18: surface emergent faction state shifts caused by player action.

    Reads `arc_state["faction_emergent"]` (populated by the post-turn hook)
    and renders a one-line cue when a faction's standing toward the
    player has shifted recently.
    """
    emergent = arc_state.get("faction_emergent") or {}
    if not isinstance(emergent, dict) or not emergent:
        return ""
    cues: list[str] = []
    for faction_name, data in emergent.items():
        if not isinstance(data, dict):
            continue
        delta = float(data.get("delta", 0.0) or 0.0)
        if abs(delta) < 0.05:
            continue
        direction = "tightening" if delta > 0 else "easing"
        action = (data.get("recent_action", "") or "").strip()
        cues.append(
            f"  - {faction_name}: {direction} attention on the protagonist "
            f"({'+' if delta >= 0 else ''}{delta:.2f})"
            + (f" — triggered by {action}" if action else "")
        )
    if not cues:
        return ""
    return (
        "FACTION REACTIVITY (emergent — not authored drift):\n"
        + "\n".join(cues)
        + "\nIf a moment fits, let one of these reactivity shifts surface — through "
          "a posted notice, a guarded look, an unexpected interest, or a deliberate ignoring."
    )


def _build_side_content_block(spine: dict, current_act: dict, arc_state: dict) -> str:
    """Phase E20: surface an optional encounter the player can engage with.

    Reads `current_act["side_content"]` (a list of optional encounters
    authored in the spine). Selects one not yet engaged and renders a
    one-line offer-to-the-LLM. Keeps the world from feeling on-rails.
    """
    side_content = current_act.get("side_content") or []
    if not side_content:
        return ""
    seen = set(arc_state.get("side_content_engaged", []) or [])
    for item in side_content:
        if not isinstance(item, dict):
            continue
        cid = item.get("id")
        if not cid or cid in seen:
            continue
        title = item.get("title", "an optional encounter")
        hook = item.get("hook", "")
        return (
            f"SIDE CONTENT AVAILABLE: '{title}'. {hook} "
            f"If a natural opening arrives in this passage, you MAY plant "
            f"this hook (a sign, an overheard line, a stranger's question, "
            f"a side door) — but only if it doesn't dilute the main action. "
            f"It is fine to ignore this if the scene is already full."
        )
    return ""


def _build_pivot_warning_block(spine: dict, current_act: dict, arc_state: dict) -> str:
    """Phase E19: when the player is at a hard pivot point, mark the choices weighty.

    Pivot points are authored in the spine as `pivot_points` per act —
    moments where a choice closes off another path. When the act_progress
    crosses a pivot's trigger, this block tells the LLM to make the
    consequences explicit and irreversible-feeling.
    """
    pivots = current_act.get("pivot_points") or []
    if not pivots:
        return ""
    progress = float(arc_state.get("act_progress", 0.0) or 0.0)
    fired = set(arc_state.get("pivots_fired", []) or [])
    for p in pivots:
        if not isinstance(p, dict):
            continue
        pid = p.get("id")
        if not pid or pid in fired:
            continue
        target = float(p.get("target_progress", 0.5) or 0.5)
        if progress < target:
            continue
        description = (p.get("description") or "").strip()
        consequence = (p.get("locks_off") or "").strip()
        return (
            f"HARD PIVOT POINT: This turn the player is at a real fork in the story. "
            f"{description} The choices you offer must be genuine alternatives — picking one "
            f"should feel like closing a door on the others. "
            + (f"Specifically: choosing one path locks off {consequence}. " if consequence else "")
            + "Make the weight of the choice land in the prose. Do not let the choices feel cosmetic."
        )
    return ""


def _post_reconciliation_reputation_hook(
    session_id:   str,
    turn_number:  int,
    recon_result,
) -> None:
    """Persist a reputation event when reconciliation flagged one."""
    if recon_result.reputation_event:
        log_reputation_event(
            session_id=session_id,
            turn_number=turn_number,
            summary=recon_result.reputation_event,
            faction_tags=recon_result.faction_tags or [],
        )


def _flag_memorable_moments(
    arc_state: dict,
    turn_number: int,
    *,
    roll_result=None,
    recon_result=None,
    scene_npcs: Optional[list] = None,
    player_action: str = "",
    narration_passage: str = "",
    obligation_just_activated: bool = False,
    duty_just_activated: bool = False,
    force_temptation_accepted: bool = False,
    milestone_fired: bool = False,
) -> None:
    """Auto-flag this turn for the memorable moments ledger.

    Triggered by:
      - Triumph or Despair on the dice
      - NPC disposition shift >= 0.15 (single turn) — both warm and cold
      - Thread resolved
      - Reputation event flagged
      - Motivation activation (Obligation or Duty just turned on)
      - Force temptation accepted (a darkside choice the player made)
      - Milestone fired (talent or Force power chosen)
      - Crystallized memory imprinted on an NPC

    Each call adds 0+ moments. The arc_state ledger handles deduplication.
    """
    from gm.context import register_memorable_moment

    act_number = int(arc_state.get("current_act", 1) or 1)
    npc_names: list[str] = []
    if scene_npcs:
        npc_names = [getattr(n, "name", str(n)) for n in scene_npcs if getattr(n, "name", "")]

    def first_sentence(text: str) -> str:
        text = (text or "").strip()
        if not text:
            return ""
        match = re.search(r"^(.{1,180}?[\.!?])\s", text + " ")
        return (match.group(1) if match else text[:180]).strip()

    excerpt = first_sentence(narration_passage)

    # Triumph / Despair
    if roll_result is not None:
        if getattr(roll_result, "triumphs", 0) > 0:
            register_memorable_moment(
                arc_state,
                turn_number=turn_number,
                act_number=act_number,
                kind="triumph",
                summary=excerpt or f"Triumph on a {getattr(roll_result, 'narrative_label', lambda: 'check')()} — the moment broke open.",
                npc_names=npc_names,
                weight=1.5,
            )
        if getattr(roll_result, "despairs", 0) > 0:
            register_memorable_moment(
                arc_state,
                turn_number=turn_number,
                act_number=act_number,
                kind="despair",
                summary=excerpt or "Despair landed — the cost of this turn cuts.",
                npc_names=npc_names,
                weight=1.7,
            )

    # NPC disposition shifts and reputation event
    if recon_result is not None:
        for npc_update in getattr(recon_result, "npc_updates", []) or []:
            shift = float(npc_update.get("disposition_shift", 0) or 0)
            if abs(shift) >= 0.15:
                npc_name = npc_update.get("npc_name", "")
                kind = "trust_deepened" if shift > 0 else "trust_fractured"
                summary = (
                    f"{npc_name} {'opened up' if shift > 0 else 'pulled back'} after "
                    f"{(player_action or 'this beat').strip().rstrip('.')[:120]}."
                )
                register_memorable_moment(
                    arc_state,
                    turn_number=turn_number,
                    act_number=act_number,
                    kind=kind,
                    summary=summary,
                    npc_names=[npc_name] if npc_name else npc_names,
                    weight=1.3 + abs(shift),
                )
        for thread_name in (recon_result.thread_updates or {}).get("threads_resolved", []) or []:
            register_memorable_moment(
                arc_state,
                turn_number=turn_number,
                act_number=act_number,
                kind="thread_resolved",
                summary=f"The thread '{thread_name}' closed — its weight has shifted.",
                npc_names=npc_names,
                weight=1.4,
            )
        if getattr(recon_result, "reputation_event", None):
            register_memorable_moment(
                arc_state,
                turn_number=turn_number,
                act_number=act_number,
                kind="reputation_event",
                summary=str(recon_result.reputation_event),
                npc_names=npc_names,
                weight=1.2,
            )

    if obligation_just_activated:
        register_memorable_moment(
            arc_state,
            turn_number=turn_number,
            act_number=act_number,
            kind="obligation_activated",
            summary=excerpt or "An old debt surfaced.",
            npc_names=npc_names,
            weight=1.1,
        )
    if duty_just_activated:
        register_memorable_moment(
            arc_state,
            turn_number=turn_number,
            act_number=act_number,
            kind="duty_activated",
            summary=excerpt or "The cause demanded something.",
            npc_names=npc_names,
            weight=1.1,
        )
    if force_temptation_accepted:
        register_memorable_moment(
            arc_state,
            turn_number=turn_number,
            act_number=act_number,
            kind="darkside_choice",
            summary=excerpt or "The dark side flowed and the protagonist let it.",
            npc_names=npc_names,
            weight=1.6,
        )
    if milestone_fired:
        register_memorable_moment(
            arc_state,
            turn_number=turn_number,
            act_number=act_number,
            kind="milestone",
            summary=excerpt or "Something inside the protagonist crystallized.",
            npc_names=npc_names,
            weight=1.3,
        )


def _post_turn_world_state_hook(
    arc_state: dict,
    *,
    spine: dict,
    current_act: dict,
    player_action: str = "",
    roll_result=None,
    npc_states: Optional[list] = None,
    side_content_offered: bool = False,
    pivot_offered: bool = False,
) -> None:
    """Phase D/E: advance tactical state, update faction reactivity,
    mark side content / pivots as engaged.

    Runs after reconciliation. The four sub-systems share a hook so all
    four turn handlers stay in sync as the model evolves.
    """
    from gm.context import advance_tactical_state

    # 1. Tactical state advancement
    tactical_state = arc_state.get("tactical_state") or {}
    if tactical_state and isinstance(tactical_state, dict) and tactical_state.get("kind"):
        outcome = ""
        succeeded = False
        if roll_result is not None:
            outcome = getattr(roll_result, "outcome_quadrant", "") or ""
            succeeded = bool(getattr(roll_result, "succeeded", False))
        advance_tactical_state(
            tactical_state,
            outcome_quadrant=outcome,
            succeeded=succeeded,
            player_action=player_action,
        )
        arc_state["tactical_state"] = tactical_state

    # 2. Emergent faction reactivity
    factions = (spine or {}).get("factions") or []
    if factions and player_action:
        emergent = arc_state.setdefault("faction_emergent", {})
        action_lower = player_action.lower()
        scene_factions = (current_act or {}).get("scene_factions", []) or []
        for faction in factions:
            if not isinstance(faction, dict):
                continue
            fname = faction.get("name", "")
            if not fname:
                continue
            keywords = [str(k).lower() for k in (faction.get("trigger_keywords") or [])]
            faction_present = fname.lower() in scene_factions or any(
                k in action_lower for k in keywords
            )
            if not faction_present:
                continue
            current = emergent.get(fname, {"delta": 0.0, "recent_action": ""})
            alignment = faction.get("alignment", "neutral")
            shift = 0.0
            if any(k in action_lower for k in ("help", "save", "protect", "ally", "aid")):
                shift = 0.05 if alignment == "friendly" else -0.05
            elif any(k in action_lower for k in ("attack", "kill", "destroy", "betray", "expose")):
                shift = -0.08 if alignment == "friendly" else 0.05
            elif any(k in action_lower for k in ("report", "warn")):
                # Reporting / warning aligns with friendly factions, undermines hostile.
                shift = 0.04 if alignment == "friendly" else -0.04
            elif any(k in action_lower for k in ("shelter", "conceal")):
                # Protecting from a faction — friendly approves, hostile is obstructed.
                shift = 0.03 if alignment == "friendly" else -0.03
            elif any(k in action_lower for k in (
                "investigate", "probe", "search", "question",
                "trace", "follow", "observe",
            )):
                # Investigative attention — being noticed without confronting.
                # Hostile factions tighten faster (you're a curious unknown);
                # friendly factions register quiet alignment.
                shift = 0.04 if alignment == "hostile" else 0.02
            elif any(k in action_lower for k in ("sneak", "evade", "hide", "deceive")):
                shift = 0.02
            if shift != 0.0:
                current["delta"] = float(current.get("delta", 0.0)) + shift
                # Cap to plausible range
                current["delta"] = max(-0.5, min(0.5, current["delta"]))
                current["recent_action"] = player_action[:80]
                emergent[fname] = current
        arc_state["faction_emergent"] = emergent

    # 3. Side content engagement tracking — heuristic: look for the side
    # content title or hook tokens in the player action.
    if side_content_offered:
        side_content = (current_act or {}).get("side_content") or []
        engaged = list(arc_state.get("side_content_engaged", []) or [])
        action_lower = player_action.lower()
        for item in side_content:
            if not isinstance(item, dict):
                continue
            cid = item.get("id")
            if not cid or cid in engaged:
                continue
            title = (item.get("title", "") or "").lower()
            keywords = [str(k).lower() for k in (item.get("keywords") or [])]
            if (title and title in action_lower) or any(k in action_lower for k in keywords):
                engaged.append(cid)
        arc_state["side_content_engaged"] = engaged

    # 4. Pivot firing tracking
    if pivot_offered:
        pivots = (current_act or {}).get("pivot_points") or []
        fired = list(arc_state.get("pivots_fired", []) or [])
        progress = float(arc_state.get("act_progress", 0.0) or 0.0)
        for p in pivots:
            if not isinstance(p, dict):
                continue
            pid = p.get("id")
            if not pid or pid in fired:
                continue
            target = float(p.get("target_progress", 0.5) or 0.5)
            if progress >= target:
                fired.append(pid)
        arc_state["pivots_fired"] = fired


def _post_turn_memorable_moments_hook(
    arc_state: dict,
    turn_number: int,
    *,
    roll_result=None,
    recon_result=None,
    scene_npcs: Optional[list] = None,
    player_action: str = "",
    narration_passage: str = "",
    candidate_moments: Optional[list] = None,
    obligation_just_activated: bool = False,
    duty_just_activated: bool = False,
    force_temptation_accepted: bool = False,
    milestone_fired: bool = False,
) -> None:
    """One-stop call site for memorable-moments bookkeeping per turn.

    Order matters: detect callbacks FIRST (so a fresh moment flagged this
    turn isn't immediately marked as also referenced), then flag new
    moments from this turn's events.
    """
    if candidate_moments:
        _detect_memorable_callback_in_passage(
            arc_state, candidate_moments, narration_passage, turn_number,
        )
    _flag_memorable_moments(
        arc_state,
        turn_number,
        roll_result=roll_result,
        recon_result=recon_result,
        scene_npcs=scene_npcs,
        player_action=player_action,
        narration_passage=narration_passage,
        obligation_just_activated=obligation_just_activated,
        duty_just_activated=duty_just_activated,
        force_temptation_accepted=force_temptation_accepted,
        milestone_fired=milestone_fired,
    )


def _detect_memorable_callback_in_passage(
    arc_state: dict,
    candidates: list,
    passage: str,
    current_turn: int,
) -> None:
    """When the narration appears to use one of the offered callbacks,
    mark it surfaced so cooldown applies. Heuristic: any NPC name + a
    keyword from the moment's summary appearing in the passage.
    """
    from gm.context import mark_callback_surfaced
    text = (passage or "").lower()
    if not text or not candidates:
        return
    for moment in candidates:
        npcs = [str(n).lower() for n in (moment.get("npc_names") or [])]
        summary = (moment.get("summary") or "").lower()
        keywords = [w for w in re.findall(r"[a-z]{5,}", summary)][:5]
        npc_hit = any(name and name in text for name in npcs)
        keyword_hit = any(k in text for k in keywords)
        if npc_hit or keyword_hit:
            mark_callback_surfaced(arc_state, moment, current_turn)


@router.get("/campaigns")
async def list_campaigns():
    """List available campaigns with story-architecture summaries.

    Designed for character-creation-funnel UIs: returns the dramatic premise,
    central question, story promise, antagonistic force, era voice, and the
    available character variants (each with their pitch + narrative arc lie /
    ghost / want / need so the player can pick a character understanding the
    inner story they are signing up for, not just the species/career stats).
    """
    from pathlib import Path

    campaigns_dir = Path("data/campaigns")
    characters_dir = Path("data/characters")

    # Pre-load standalone character files keyed by id for quick lookup
    standalone: dict[str, dict] = {}
    for cpath in characters_dir.glob("*.json"):
        try:
            with open(cpath, encoding="utf-8") as f:
                standalone[cpath.stem] = json.load(f)
        except Exception:
            continue

    result = []
    for path in sorted(campaigns_dir.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            spine = json.load(f)
        sa = spine.get("story_architecture", {}) or {}
        ev = spine.get("era_voice", {}) or {}
        intended_protagonist_id = spine.get("intended_protagonist_id", "")

        characters: list[dict] = []
        seen_ids: set[str] = set()

        # Spine-side variants (allegiance.character_variants)
        for allegiance in spine.get("allegiances", []):
            for cv in allegiance.get("character_variants", []):
                cid = cv.get("id")
                if not cid or cid in seen_ids:
                    continue
                if intended_protagonist_id and cid != intended_protagonist_id:
                    seen_ids.add(cid)
                    continue
                if cv.get("player_selectable") is False:
                    seen_ids.add(cid)
                    continue
                seen_ids.add(cid)
                # Pull the standalone file (if present) for the live arc data
                live = standalone.get(cid, {})
                arc = live.get("narrative_arc") or {}
                characters.append({
                    "id":      cid,
                    "name":    live.get("name", cid.replace("_", " ").title()),
                    "pitch":   cv.get("pitch", ""),
                    "career":  cv.get("career", live.get("career", "")),
                    "species": cv.get("species", live.get("species", "")),
                    "intended_protagonist": cv.get("intended_protagonist", False),
                    "player_selectable": cv.get("player_selectable", True),
                    "supporting_only": cv.get("supporting_only", False),
                    "selection_note": cv.get("selection_note", ""),
                    "voice_notes": live.get("voice_notes", ""),
                    "narrative_arc": {
                        "lie":      arc.get("lie", ""),
                        "ghost":    arc.get("ghost", ""),
                        "truth":    arc.get("truth", ""),
                        "want":     arc.get("want", ""),
                        "need":     arc.get("need", ""),
                        "arc_type": arc.get("arc_type", ""),
                    } if arc else None,
                })

        # Standalone character files not represented in any allegiance — still
        # offer them as choices so newly-authored arcs surface in the funnel.
        for cid, live in sorted(standalone.items()):
            if cid in seen_ids:
                continue
            if intended_protagonist_id and cid != intended_protagonist_id:
                continue
            arc = live.get("narrative_arc") or {}
            characters.append({
                "id":      cid,
                "name":    live.get("name", cid.replace("_", " ").title()),
                "pitch":   "",
                "career":  live.get("career", ""),
                "species": live.get("species", ""),
                "intended_protagonist": cid == intended_protagonist_id,
                "player_selectable": True,
                "supporting_only": False,
                "selection_note": "Intended protagonist." if cid == intended_protagonist_id else "",
                "voice_notes": live.get("voice_notes", ""),
                "narrative_arc": {
                    "lie":      arc.get("lie", ""),
                    "ghost":    arc.get("ghost", ""),
                    "truth":    arc.get("truth", ""),
                    "want":     arc.get("want", ""),
                    "need":     arc.get("need", ""),
                    "arc_type": arc.get("arc_type", ""),
                } if arc else None,
            })

        result.append({
            "campaign_name": path.stem,
            "display_name":  spine.get("name", path.stem),
            "intended_protagonist_id": intended_protagonist_id,
            "era":           spine.get("era", ""),
            "era_year":      ev.get("year", ""),
            "era_voice_notes": ev.get("voice_notes", ""),
            "throughline":   spine.get("throughline_question", ""),
            # Story architecture summary — Brooks/Weiland setup
            "dramatic_premise":         sa.get("dramatic_premise", ""),
            "central_dramatic_question": sa.get("central_dramatic_question", ""),
            "story_promise":            sa.get("story_promise", ""),
            "protagonist_pressure_type": sa.get("protagonist_pressure_type", ""),
            "antagonistic_force":       sa.get("antagonistic_force", ""),
            "thematic_throughline":     sa.get("thematic_throughline", ""),
            "characters":               characters,
        })
    return result


@router.get("/characters")
async def list_characters():
    """List all standalone character files with their narrative arcs.

    Powers the character-selection step of the creation funnel. Each entry
    surfaces the lie / ghost / truth / want / need so a UI can present the
    inner story the player would be agreeing to play — the WHY beneath
    the species/career numbers.
    """
    from pathlib import Path

    characters_dir = Path("data/characters")
    out: list[dict] = []
    for cpath in sorted(characters_dir.glob("*.json")):
        try:
            with open(cpath, encoding="utf-8") as f:
                live = json.load(f)
        except Exception:
            continue
        arc = live.get("narrative_arc") or {}
        out.append({
            "id":               cpath.stem,
            "name":             live.get("name", cpath.stem.replace("_", " ").title()),
            "species":          live.get("species", ""),
            "career":           live.get("career", ""),
            "specializations":  live.get("specializations", []),
            "background_excerpt": (live.get("background", "") or "")[:520],
            "voice_notes":      live.get("voice_notes", ""),
            "throughline_question": live.get("throughline_question", ""),
            "narrative_arc": {
                "lie":      arc.get("lie", ""),
                "ghost":    arc.get("ghost", ""),
                "truth":    arc.get("truth", ""),
                "want":     arc.get("want", ""),
                "need":     arc.get("need", ""),
                "arc_type": arc.get("arc_type", "positive"),
                "lie_grip": arc.get("lie_grip", 1.0),
            } if arc else None,
        })
    return out


# Phase 8.5: Social skill → NPC emotion mapping (§25.2)
SOCIAL_EMOTION_MAP = {
    # skill: (emotion_on_failure, base_intensity)
    "deception":   ("suspicious", 0.5),
    "coercion":    ("angry", 0.6),
    "charm":       ("suspicious", 0.3),  # mild — they sense insincerity
    "negotiation": ("angry", 0.4),       # deal went sour
    "leadership":  ("conflicted", 0.4),  # doubt in the leader
}


def _apply_emotion_from_check(
    npc_states: list, skill: str, outcome_quadrant: str, turn_number: int,
) -> None:
    """Set NPC emotional state based on failed social checks (§25.2)."""
    if skill not in SOCIAL_EMOTION_MAP:
        return
    if not outcome_quadrant or not outcome_quadrant.startswith("failure"):
        return
    mood, base_intensity = SOCIAL_EMOTION_MAP[skill]
    # Boost intensity for failure_threat (worse outcome)
    intensity = base_intensity + (0.15 if outcome_quadrant == "failure_threat" else 0.0)
    # Apply to the first NPC present (social checks target scene NPCs)
    for npc in npc_states:
        npc.set_emotion(mood, intensity, f"Failed {skill} check", turn_number)
        break  # only the primary scene NPC


# ── Request / Response Models ──────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    campaign_name: str
    character_id: str


class TurnRequest(BaseModel):
    choice_index: int
    # Phase D16: Optional free-form action. When set (non-empty), the
    # player has typed their own action instead of picking from the
    # offered choices. The turn handler routes this through the local
    # check decision model so the system picks an appropriate skill
    # and difficulty. choice_index should be -1 in this case.
    free_form_action: Optional[str] = None


class InterventionRequest(BaseModel):
    accept: bool


class TemptationRequest(BaseModel):
    accept: bool


class MilestoneRequest(BaseModel):
    choice_index: int


class ForcePowerMilestoneRequest(BaseModel):
    choice_index: int


class CommitmentRequest(BaseModel):
    power_id: str
    upgrade_id: str
    release: bool = False


class VignetteRequest(BaseModel):
    choice_index: int


# ── Helper Functions ────────────────────────────────────────────────────

def load_campaign_spine(name: str) -> dict:
    """Read campaign spine JSON from data/campaigns/{name}.json."""
    # Normalize: "The Nar Shaddaa Job" -> "nar_shaddaa_job"
    filename = name.lower().replace(" ", "_")
    if filename.startswith("the_"):
        filename = filename[4:]
    path = f"data/campaigns/{filename}.json"
    try:
        # Phase 24: explicit utf-8 — campaign JSON contains non-ASCII
        # (em-dashes, etc.) and the platform default on Windows is cp1252.
        with open(path, encoding="utf-8") as f:
            spine_data = json.load(f)
    except FileNotFoundError:
        raise HTTPException(404, f"Campaign not found: {name}")

    # Optional diagnostic validation against CampaignSpine schema
    if os.getenv("VALIDATE_SPINE_ON_LOAD", "").lower() in ("1", "true"):
        try:
            from studio.schema import CampaignSpine
            CampaignSpine(**spine_data)
        except Exception as e:
            logging.warning(f"Spine validation warning for '{name}': {e}")

    return spine_data


def load_character(character_id: str) -> Character:
    """Read character JSON from data/characters/{id}.json."""
    path = f"data/characters/{character_id}.json"
    try:
        with open(path, encoding="utf-8") as f:
            return Character.model_validate_json(f.read())
    except FileNotFoundError:
        raise HTTPException(404, f"Character not found: {character_id}")


def load_character_from_variant(spine_data: dict, variant_id: str) -> Character:
    """Build a Character from a campaign spine variant.

    Uses studio/import_interface.build_default_character() which handles
    all field name translations (characteristics_base -> characteristics,
    starting_xp -> total_xp, etc.). Fallback when no standalone character
    file exists — makes Studio-generated campaigns playable without
    manual file export.
    """
    from studio.schema import CampaignSpine
    from studio.import_interface import build_default_character

    spine = CampaignSpine(**spine_data)
    char_dict = build_default_character(spine, variant_id)
    char_dict["name"] = variant_id.replace("_", " ").title()
    return Character.model_validate(char_dict)


def get_most_recent_turn(session_id: str) -> dict:
    """Return the most recent turn row from the turns table."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM turns WHERE session_id = ? "
            "ORDER BY turn_number DESC LIMIT 1",
            (session_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(400, "No turns found for this session")
    return dict(row)


def _context_audit_json(ctx: ContextPackage) -> str | None:
    """Serialize the prompt-relevant context we sent to narration."""
    def _audit_redact(value: str) -> str:
        text = _clean_state_string(value, max_len=400)
        if not text:
            return ""
        redacted = ctx._redact_future_spoilers(f"  Field: {text}").strip()
        if redacted.startswith("Field: "):
            redacted = redacted[len("Field: "):]
        return redacted.strip()

    def _audit_list(values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values or []:
            redacted = _audit_redact(value)
            if redacted and redacted not in cleaned:
                cleaned.append(redacted)
        return cleaned

    try:
        payload = {
            "location": ctx.location,
            "situation": ctx.situation,
            "scene_type": ctx.scene_type,
            "arc": {
                "campaign_name": ctx.arc.campaign_name,
                "current_act": ctx.arc.current_act,
                "act_name": ctx.arc.act_name,
                "act_progress": ctx.arc.act_progress,
                "current_anchor": ctx.arc.current_anchor,
                "next_anchor": ctx.arc.next_anchor,
                "anchor_proximity": ctx.arc.anchor_proximity,
                "turns_this_act": ctx.arc.turns_this_act,
                "tension_level": ctx.arc.tension_level,
            },
            "recent_turns": [
                {
                    "turn_number": t.turn_number,
                    "player_action": t.player_action,
                    "narration_excerpt": t.narration_excerpt,
                    "check_made": t.check_made,
                    "dice_result": t.dice_result,
                    "outcome_quadrant": t.outcome_quadrant,
                    "meaningful_choice_note": t.meaningful_choice_note,
                }
                for t in ctx.recent_turns
            ],
            "active_npcs": [
                {
                    "name": npc.name,
                    "knows": _audit_list(npc.knows),
                    "doesnt_know": _audit_list(npc.doesnt_know),
                    "disposition": npc.disposition,
                    "motivation": _audit_redact(npc.motivation),
                    "pressure_role": npc.pressure_role,
                }
                for npc in ctx.active_npcs
            ],
            "open_threads": ctx.build_open_threads_block(),
            "dice_result_block": ctx.build_dice_result_block(),
            "force_result_block": ctx.force_result_block,
            "force_check_kind": ctx.force_check_kind,
            "dramatic_mission": ctx.dramatic_mission,
        }
        return json.dumps(payload, ensure_ascii=False)
    except Exception:
        logging.exception("Failed to serialize context audit payload")
        return None


def save_npc_state(session_id: str, npc: NPCState) -> None:
    """Write one NPC state to the npc_states table."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO npc_states "
            "(session_id, npc_name, state_json, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (session_id, npc.name, json.dumps(asdict(npc)), now),
        )
        conn.commit()


def load_npc_states(session_id: str, spine: dict) -> list[NPCState]:
    """Load NPC states from DB. On first turn, initialize from spine roster."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT npc_name, state_json FROM npc_states WHERE session_id = ?",
            (session_id,),
        ).fetchall()

    if rows:
        valid_fields = {f.name for f in fields(NPCState)}
        npcs = []
        for r in rows:
            data = {k: v for k, v in json.loads(r["state_json"]).items() if k in valid_fields}
            # Deserialize emotional_state from dict to EmotionalState
            if isinstance(data.get("emotional_state"), dict):
                data["emotional_state"] = EmotionalState.from_dict(data["emotional_state"])
            npcs.append(NPCState(**data))
        return npcs

    # First turn — initialize from spine roster
    npcs = []
    for npc_data in spine.get("npc_roster", []):
        npc = NPCState(
            name=npc_data["name"],
            knows=npc_data.get("knows_at_start", []),
            doesnt_know=npc_data.get("doesnt_know_at_start", []),
            disposition=npc_data.get("disposition_start", 0.5),
            voice_notes=npc_data.get("voice_notes", ""),
            motivation=npc_data.get("motivation", ""),
            behavioral_envelope=npc_data.get("behavioral_envelope", []),
            pressure_role=npc_data.get("pressure_role", ""),
        )
        save_npc_state(session_id, npc)
        npcs.append(npc)
    return npcs


def update_session_state(
    session_id: str, character: Character, arc_state: dict
) -> None:
    """Write updated character JSON and arc state back to sessions table."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "UPDATE sessions SET character_json = ?, arc_state_json = ?, "
            "updated_at = ? WHERE id = ?",
            (character.model_dump_json(), json.dumps(arc_state), now, session_id),
        )
        conn.commit()


def resolve_initial_variations(session_id: str, spine: dict) -> None:
    """Resolve variation points with selection_method='randomly_determined'."""
    for npc_data in spine.get("npc_roster", []):
        if npc_data.get("resolution") == "randomly_determined":
            options = npc_data.get("options", [])
            if options:
                selected = random.choice(options)
                # Store the resolution in the NPC state
                with get_connection() as conn:
                    row = conn.execute(
                        "SELECT state_json FROM npc_states "
                        "WHERE session_id = ? AND npc_name = ?",
                        (session_id, npc_data["name"]),
                    ).fetchone()
                    if row:
                        state = json.loads(row["state_json"])
                        state["resolution"] = selected
                        now = datetime.now(timezone.utc).isoformat()
                        conn.execute(
                            "UPDATE npc_states SET state_json = ?, updated_at = ? "
                            "WHERE session_id = ? AND npc_name = ?",
                            (json.dumps(state), now, session_id, npc_data["name"]),
                        )
                        conn.commit()


# ── Phase 13: Annotation + Diagnostic Helpers ─────────────────────────

def _build_aspiration_echo(character, arc_state: dict) -> str:
    """Build aspiration echo instructions from behavioral inference (§14.5).

    Phase 13 starts with Force sensitivity echoes only.
    Skill growth and advancement direction echoes are reserved for future phases.
    """
    # Force sensitivity echoes (§14.4)
    if getattr(character, "latent_force_sensitive", False):
        return (
            "The character has an untapped connection to something they "
            "cannot name. In moments of stillness, danger, or deep emotion, "
            "weave a brief interiority moment — a sensation that is more "
            "than instinct, a certainty that arrives before reason. Do not "
            "name the Force. Let the character feel it as heightened "
            "awareness, inexplicable calm under pressure, or a pull toward "
            "something they cannot articulate."
        )

    # Skill growth echoes — derived from advancement_log
    adv_log = getattr(character, "advancement_log", [])
    if adv_log:
        recent = adv_log[-1]
        skill = recent.get("skill", "")
        if skill:
            return (
                f"The character has been developing their {skill.replace('_', ' ')} "
                f"capability. Occasionally weave a brief moment of interiority "
                f"where they notice this growth — not as narrated fact, but as "
                f"the character's own awareness of becoming more capable. "
                f"Make it specific to how they use {skill.replace('_', ' ')} "
                f"in their life, not a generic observation."
            )

    return ""


def _run_annotation_background(
    session_id: str,
    player_action: str,
    all_choices: list[str],
    choice_index: int,
    scene_description: str,
    npc_states: list,
    recent_turns: list,
    throughline_question: str,
    narrative_arc_block: str = "",
) -> str | None:
    """Run choice annotation and return JSON string or None.

    Called as a background thread so it doesn't block narration. When
    `narrative_arc_block` is non-empty, the annotator also classifies
    the choice as `lie | truth | neutral` against the protagonist's
    Brooks/Weiland arc.
    """
    rejected = [c for i, c in enumerate(all_choices) if i != choice_index]

    npc_summary = "\n".join(
        f"- {npc.name}: {npc.disposition_label()} ({npc.disposition:.2f})"
        for npc in npc_states[:4]
    ) if npc_states else "No NPCs present."

    recent_pattern = "\n".join(
        f"Turn {t.turn_number}: {t.player_action}"
        + (f" [{t.check_made}]" if t.check_made else "")
        for t in recent_turns[-5:]
    ) if recent_turns else "No prior turns."

    annotation = annotate_choice(
        selected_choice=player_action,
        rejected_choices=rejected,
        scene_context=scene_description,
        npc_summary=npc_summary,
        recent_pattern=recent_pattern,
        throughline_question=throughline_question,
        narrative_arc_block=narrative_arc_block,
    )

    if annotation:
        return json.dumps(annotation)
    return None


def _social_runtime_state(arc_state: dict) -> dict:
    """Mutable per-session social route state, stored inside arc_state_json."""
    runtime = arc_state.setdefault("social_runtime", {})
    for key in (
        "offered_bond_ids",
        "seen_bond_ids",
        "offered_group_scene_ids",
        "seen_group_scene_ids",
        "pending_offers",
    ):
        value = runtime.get(key)
        runtime[key] = value if isinstance(value, list) else []
    for key in ("act_bond_offer_counts", "act_group_offer_counts"):
        value = runtime.get(key)
        runtime[key] = value if isinstance(value, dict) else {}
    return runtime


def _clear_pending_social_offers(arc_state: dict) -> None:
    _social_runtime_state(arc_state)["pending_offers"] = []
    arc_state.pop("active_social_scene", None)


def _social_act_key(act_number: int) -> str:
    return str(int(act_number or 1))


def _coerce_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _append_unique(items: list, value: str) -> None:
    if value and value not in items:
        items.append(value)


def _social_id_index(items: list[dict]) -> dict[str, dict]:
    return {
        str(item.get("id")): item
        for item in items or []
        if isinstance(item, dict) and item.get("id")
    }


def _bond_pacing_plan(spine: dict, act_number: int) -> dict:
    matrix = spine.get("bond_pacing_matrix", {}) or {}
    for plan in matrix.get("act_plans", []) or []:
        if _coerce_int(plan.get("act"), -1) == act_number:
            return plan
    return {}


def _bond_act_plan(spine: dict, act_number: int) -> dict:
    for plan in spine.get("bond_act_plan", []) or []:
        if _coerce_int(plan.get("act"), -1) == act_number:
            return plan
    return {}


def _bond_event_in_act(event: dict, act_number: int) -> bool:
    window = event.get("act_window") or []
    if len(window) >= 2:
        start = _coerce_int(window[0], act_number)
        end = _coerce_int(window[1], act_number)
        return start <= act_number <= end
    event_act = _coerce_int(event.get("act"), act_number)
    return event_act == act_number


def _bond_prereqs_met(event: dict, seen_bond_ids: set[str]) -> bool:
    prereqs = event.get("prerequisites", []) or []
    return all(str(prereq) in seen_bond_ids for prereq in prereqs)


def _next_bond_event_offer(spine: dict, arc_state: dict) -> dict | None:
    act_number = _coerce_int(arc_state.get("current_act"), 1)
    plan = _bond_pacing_plan(spine, act_number)
    if not plan:
        return None

    runtime = _social_runtime_state(arc_state)
    act_key = _social_act_key(act_number)
    offer_counts = runtime["act_bond_offer_counts"]
    max_offers = _coerce_int(plan.get("max_one_on_one_offers"), 0)
    if max_offers <= 0:
        max_offers = _coerce_int(_bond_act_plan(spine, act_number).get("slots"), 0)
    if max_offers > 0 and _coerce_int(offer_counts.get(act_key), 0) >= max_offers:
        return None

    events_by_id = _social_id_index(spine.get("bond_events", []))
    matrix = spine.get("bond_pacing_matrix", {}) or {}
    hard_cut_ids = {str(item) for item in matrix.get("hard_cut_ids", []) or []}
    seen_ids = {str(item) for item in runtime["seen_bond_ids"]}
    offered_ids = {str(item) for item in runtime["offered_bond_ids"]}

    priority_ids = []
    for key in ("required_story", "priority_pool", "optional_pool"):
        priority_ids.extend(str(item) for item in plan.get(key, []) or [])
    rare_ids = [str(item) for item in plan.get("rare_pool", []) or []]

    for candidate_ids in (priority_ids, rare_ids):
        for event_id in candidate_ids:
            if event_id in seen_ids or event_id in offered_ids or event_id in hard_cut_ids:
                continue
            event = events_by_id.get(event_id)
            if not event:
                continue
            if not _bond_event_in_act(event, act_number):
                continue
            if not _bond_prereqs_met(event, seen_ids):
                continue
            return event
    return None


def _next_group_scene_offer(spine: dict, arc_state: dict) -> dict | None:
    act_number = _coerce_int(arc_state.get("current_act"), 1)
    runtime = _social_runtime_state(arc_state)
    seen_ids = {str(item) for item in runtime["seen_group_scene_ids"]}
    offered_ids = {str(item) for item in runtime["offered_group_scene_ids"]}
    scenes_by_id = _social_id_index(spine.get("group_scenes", []))

    act_plan = _bond_act_plan(spine, act_number)
    scene_ids = [str(item) for item in act_plan.get("group_scene_ids", []) or []]
    if not scene_ids:
        scene_ids = [
            str(scene.get("id"))
            for scene in spine.get("group_scenes", []) or []
            if _coerce_int(scene.get("act"), -1) == act_number and scene.get("id")
        ]

    for scene_id in scene_ids:
        if scene_id in seen_ids or scene_id in offered_ids:
            continue
        scene = scenes_by_id.get(scene_id)
        if scene:
            return scene
    return None


def _bond_offer_choice_text(event: dict) -> str:
    person = str(event.get("cohort_member") or "someone").strip()
    title = str(event.get("title") or "a quiet moment").strip()
    return f"Ask {person} for a quiet moment: {title}."


def _group_offer_choice_text(scene: dict) -> str:
    title = str(scene.get("title") or "the group scene").strip()
    return f"Listen in with the group during {title}."


def _bond_offer_payload(event: dict) -> dict:
    return {
        "kind": "bond_event",
        "id": str(event.get("id", "")),
        "title": str(event.get("title", "")),
        "choice_text": _bond_offer_choice_text(event),
        "cohort_member": str(event.get("cohort_member", "")),
        "hook": str(event.get("hook", "")),
        "choice_prompt": str(event.get("choice_prompt", "")),
        "why_this_person": str(event.get("why_this_person", "")),
        "why_now": str(event.get("why_now", "")),
        "changes_after": str(event.get("changes_after", "")),
        "bond_weight": event.get("bond_weight", 0.1),
    }


def _group_offer_payload(scene: dict) -> dict:
    return {
        "kind": "group_scene",
        "id": str(scene.get("id", "")),
        "title": str(scene.get("title", "")),
        "choice_text": _group_offer_choice_text(scene),
        "scene_type": str(scene.get("scene_type", "")),
        "participants": list(scene.get("participants", []) or []),
        "hook": str(scene.get("hook", "")),
        "function": str(scene.get("function", "")),
        "bond_payoffs": list(scene.get("bond_payoffs", []) or []),
    }


def _select_social_offers(
    spine: dict,
    arc_state: dict,
    *,
    existing_choice_count: int,
    max_total_choices: int = 4,
) -> list[dict]:
    """Pick optional social offers that fit within the live choice list."""
    room = max(0, max_total_choices - existing_choice_count)
    if room <= 0:
        return []

    offers: list[dict] = []
    bond_event = _next_bond_event_offer(spine, arc_state)
    if bond_event:
        offers.append(_bond_offer_payload(bond_event))

    if len(offers) < room:
        group_scene = _next_group_scene_offer(spine, arc_state)
        if group_scene:
            offers.append(_group_offer_payload(group_scene))

    return offers[:room]


def _mark_social_offer_displayed(runtime: dict, offer: dict, act_number: int) -> None:
    act_key = _social_act_key(act_number)
    if offer.get("kind") == "bond_event":
        _append_unique(runtime["offered_bond_ids"], offer.get("id", ""))
        counts = runtime["act_bond_offer_counts"]
    else:
        _append_unique(runtime["offered_group_scene_ids"], offer.get("id", ""))
        counts = runtime["act_group_offer_counts"]
    counts[act_key] = _coerce_int(counts.get(act_key), 0) + 1


def _append_social_offers_to_narration(
    narration_result,
    spine: dict,
    arc_state: dict,
) -> list[dict]:
    """Append optional free-time choices and persist pending offer metadata."""
    runtime = _social_runtime_state(arc_state)
    runtime["pending_offers"] = []

    choices = getattr(narration_result, "choices", None)
    skill_tags = getattr(narration_result, "skill_tags", None)
    if not isinstance(choices, list) or not isinstance(skill_tags, list):
        return []

    while len(skill_tags) < len(choices):
        skill_tags.append(None)

    offers = _select_social_offers(
        spine, arc_state, existing_choice_count=len(choices)
    )
    if not offers:
        return []

    act_number = _coerce_int(arc_state.get("current_act"), 1)
    pending = []
    for offer in offers:
        if not offer.get("id"):
            continue
        choice_index = len(choices)
        offer["choice_index"] = choice_index
        offer["act"] = act_number
        choices.append(offer["choice_text"])
        skill_tags.append(None)
        pending.append(dict(offer))
        _mark_social_offer_displayed(runtime, offer, act_number)

    runtime["pending_offers"] = pending
    return pending


def _consume_selected_social_offer(arc_state: dict, choice_index: int) -> dict | None:
    runtime = _social_runtime_state(arc_state)
    pending = list(runtime.get("pending_offers", []) or [])
    runtime["pending_offers"] = []
    arc_state.pop("active_social_scene", None)

    selected = None
    for offer in pending:
        if _coerce_int(offer.get("choice_index"), -1) == choice_index:
            selected = dict(offer)
            break
    if not selected:
        return None

    act_number = _coerce_int(
        selected.get("act"), _coerce_int(arc_state.get("current_act"), 1)
    )
    if selected.get("kind") == "bond_event":
        _append_unique(runtime["seen_bond_ids"], selected.get("id", ""))
        member = selected.get("cohort_member", "")
        if member:
            bond_points = runtime.setdefault("bond_points", {})
            try:
                weight = float(selected.get("bond_weight", 0.1) or 0.1)
            except (TypeError, ValueError):
                weight = 0.1
            prior = float(bond_points.get(member, 0.0) or 0.0)
            bond_points[member] = round(prior + weight, 3)
        runtime["last_selected_bond_id"] = selected.get("id", "")
    elif selected.get("kind") == "group_scene":
        _append_unique(runtime["seen_group_scene_ids"], selected.get("id", ""))
        runtime["last_selected_group_scene_id"] = selected.get("id", "")

    selected["selected_in_act"] = act_number
    arc_state["active_social_scene"] = selected
    return selected


def _finish_active_social_scene(arc_state: dict) -> None:
    active = arc_state.pop("active_social_scene", None)
    if active:
        runtime = _social_runtime_state(arc_state)
        runtime["last_social_scene"] = {
            "kind": active.get("kind", ""),
            "id": active.get("id", ""),
            "title": active.get("title", ""),
            "act": active.get("selected_in_act", active.get("act", "")),
        }


def _active_social_scene_block(arc_state: dict) -> str:
    active = arc_state.get("active_social_scene") or {}
    if not isinstance(active, dict) or not active.get("id"):
        return ""

    if active.get("kind") == "bond_event":
        lines = [
            "SELECTED BOND SCENE:",
            f"Bond event: {active.get('title', '')} ({active.get('id', '')})",
            f"Person: {active.get('cohort_member', '')}",
            f"Hook: {active.get('hook', '')}",
            f"Choice prompt: {active.get('choice_prompt', '')}",
            f"Why this person: {active.get('why_this_person', '')}",
            f"Why now: {active.get('why_now', '')}",
            f"What changes afterward: {active.get('changes_after', '')}",
            (
                "Run this as a focused RPG social scene. Let the player-facing "
                "choice shape the relationship; do not treat it as filler."
            ),
        ]
        return "\n".join(line for line in lines if line.strip())

    if active.get("kind") == "group_scene":
        participants = ", ".join(str(p) for p in active.get("participants", []) if p)
        payoffs = ", ".join(str(p) for p in active.get("bond_payoffs", []) if p)
        lines = [
            "SELECTED GROUP SCENE:",
            f"Group scene: {active.get('title', '')} ({active.get('id', '')})",
            f"Participants: {participants}",
            f"Hook: {active.get('hook', '')}",
            f"Function: {active.get('function', '')}",
            f"Potential bond payoffs: {payoffs}",
            (
                "Run this as party texture with clear character dynamics. "
                "Keep it playable and present-tense, not exposition."
            ),
        ]
        return "\n".join(line for line in lines if line.strip())

    return ""


# ── Routes ──────────────────────────────────────────────────────────────

@router.post("/session")
async def create_session_route(
    req: CreateSessionRequest,
    background_tasks: BackgroundTasks,
):
    """
    Create a new session and generate the opening narration.
    """
    # ── Load campaign and character data ──────────────────────────────
    spine = load_campaign_spine(req.campaign_name)
    try:
        character = load_character(req.character_id)
    except HTTPException:
        # No standalone file — build from spine variant
        try:
            character = load_character_from_variant(spine, req.character_id)
        except ValueError as e:
            raise HTTPException(404, str(e))
    act_1 = spine["acts"][0]

    # ── Roll motivation track for Act 1 (§9) ─────────────────────────
    motivation_flags = roll_obligation_duty(character)

    # ── Roll initial Destiny Pool (§23.1) ─────────────────────────────
    destiny_light, destiny_dark = roll_initial_destiny()

    # ── Initialize arc state ──────────────────────────────────────────
    arc_state = {
        "current_act": 1,
        "act_progress": 0.0,
        "anchors_completed": [],
        "closed_threads": [],
        "dynamic_threads": [],
        "current_location": act_1.get("opening_location", ""),
        "turns_this_act": 0,
        "anchor_proximity": "distant",
        "destiny_light_spent_this_act": 0,
        "destiny_dark_spent_this_act": 0,
        # CS-6 wiring (Apr 2026): persist the character_id as `variant_id`
        # so we can resolve depth_card / contradiction / voice modes back
        # to the spine variant on later turns.
        "variant_id": req.character_id,
        **motivation_flags,
    }
    _social_runtime_state(arc_state)

    # ── Create session in database ────────────────────────────────────
    session_id = create_session(
        campaign_name=req.campaign_name,
        character_json=character.model_dump_json(),
        arc_state_json=json.dumps(arc_state),
    )

    # Write initial destiny pool to session
    update_destiny_pool(session_id, destiny_light, destiny_dark)

    # ── Initialize NPC states from spine roster ───────────────────────
    for npc_data in spine.get("npc_roster", []):
        save_npc_state(session_id, NPCState(
            name=npc_data["name"],
            knows=npc_data.get("knows_at_start", []),
            doesnt_know=npc_data.get("doesnt_know_at_start", []),
            disposition=npc_data.get("disposition_start", 0.5),
            last_seen_turn=0,
            voice_notes=npc_data.get("voice_notes", ""),
            motivation=npc_data.get("motivation", ""),
            behavioral_envelope=npc_data.get("behavioral_envelope", []),
            pressure_role=npc_data.get("pressure_role", ""),
        ))

    # ── Initialize ship states from spine vehicle registry (§17) ──────
    for vehicle_entry in spine.get("vehicle_registry", []):
        ship = load_ship_from_spine(vehicle_entry)
        save_ship_state(session_id, ship)

    # ── Resolve variation points (e.g. Doss's fate) ───────────────────
    resolve_initial_variations(session_id, spine)

    # ── Build opening context package ─────────────────────────────────
    npc_states = load_npc_states(session_id, spine)
    arc_state["scene_state"] = _initial_scene_state(arc_state, act_1)
    opening_npcs = _select_active_scene_npcs(
        npc_states, arc_state, act_1, act_1.get("opening_situation", "")
    )

    # Dynamic per-turn fields. Reputation/behavioral are no-ops on turn 0
    # (cooldown + empty log); era_voice_block is the meaningful piece — it
    # anchors the opening prose to the campaign's period from the very first
    # passage.
    dyn_fields_opening = _compute_dynamic_context_fields(
        session_id, 0, arc_state, act_1, opening_npcs, spine,
        character=character, roll_result=None,
    )

    ctx = ContextPackage(
        character=character,
        arc=ArcState(
            campaign_name=spine["name"],
            current_act=1,
            total_acts=spine["total_acts"],
            act_name=act_1["name"],
            act_progress=0.0,
            current_anchor=act_1["anchor"],
            next_anchor=act_1.get("next_anchor", ""),
            anchors_completed=[],
            throughline_question=spine["throughline_question"],
            tension_level=act_1["tension"],
            open_threads=_thread_states_for_context(act_1, arc_state),
            closed_threads=[],
            anchor_description=act_1.get("anchor_description", ""),
            obligation_active=arc_state.get("obligation_active", False),
            obligation_type=arc_state.get("obligation_type", ""),
            duty_active=arc_state.get("duty_active", False),
            duty_type=arc_state.get("duty_type", ""),
            morality_label=arc_state.get("morality_label", ""),
            last_reputation_echo_turn=arc_state.get("last_reputation_echo_turn", 0),
        ),
        story_summary="",
        recent_turns=[],
        active_npcs=opening_npcs,
        location=arc_state["scene_state"]["current_location"],
        situation=(
            f"{_scene_state_block(arc_state['scene_state'])}\n\n"
            f"{act_1['opening_situation']}"
        ),
        galactic_context=act_1.get("galactic_context", ""),
        scene_type="exploration",  # opening is always exploration
        tone_instruction=(
            "This is the opening of the campaign. Establish the world, "
            "the character's voice, and the immediate situation. Ground "
            "the reader in a specific sensory moment."
        ),
        expected_turns=act_1.get("expected_turns", [8, 12]),
        **dyn_fields_opening,
    )

    # ── Generate opening narration (one cloud call) ───────────────────
    narration_result = narrate_turn(ctx)
    _post_narration_reputation_hook(
        0, arc_state,
        dyn_fields_opening["reputation_entries"], narration_result.passage,
    )
    _post_narration_drift_hook(
        turn_number=0,
        arc_state=arc_state,
        character=character,
        drift_cue=dyn_fields_opening["identity_drift_cue"],
        roll_result=None,
        pinch_fired_this_turn=False,
    )
    opening_thread_updates = _apply_narration_scene_state(
        arc_state=arc_state,
        current_act=act_1,
        npc_states=npc_states,
        narration_result=narration_result,
        player_action="[session_start]",
        scene_type="exploration",
        recent_turns=[],
        turn_number=0,
    )
    apply_thread_updates(opening_thread_updates, arc_state, act_1)
    for npc in npc_states:
        save_npc_state(session_id, npc)

    # ── Log Turn 0 ────────────────────────────────────────────────────
    log_turn(
        session_id=session_id,
        turn_number=0,
        player_action="[session_start]",
        choice_index=-1,
        narration=narration_result.passage,
        choices=narration_result.choices,
        scene_type=arc_state.get("scene_state", {}).get("scene_type", "exploration"),
        skill_tags_json=json.dumps(narration_result.skill_tags),
        context_json=_context_audit_json(ctx),
    )

    # ── Build a "who you are about to play" preamble for the funnel ──
    # Surfaces the dramatic premise + protagonist arc up-front so the player
    # commits with eyes open to the inner story they have just signed up for.
    sa = spine.get("story_architecture", {}) or {}
    arc_obj = getattr(character, "narrative_arc", None)
    arc_summary = None
    if arc_obj and (getattr(arc_obj, "lie", "") or "").strip():
        arc_summary = {
            "lie":      arc_obj.lie,
            "ghost":    arc_obj.ghost,
            "truth":    arc_obj.truth,
            "want":     arc_obj.want,
            "need":     arc_obj.need,
            "arc_type": arc_obj.arc_type,
            "lie_grip": arc_obj.lie_grip,
        }
    session_intro = {
        "campaign_display_name":     spine.get("name", req.campaign_name),
        "era":                       spine.get("era", ""),
        "dramatic_premise":          sa.get("dramatic_premise", ""),
        "central_dramatic_question": sa.get("central_dramatic_question", ""),
        "story_promise":             sa.get("story_promise", ""),
        "protagonist_pressure_type": sa.get("protagonist_pressure_type", ""),
        "antagonistic_force":        sa.get("antagonistic_force", ""),
        "throughline":               spine.get("throughline_question", ""),
        "character": {
            "name":               character.name,
            "voice_notes":        character.voice_notes,
            "throughline_question": character.throughline_question,
            "narrative_arc":      arc_summary,
        },
    }

    return {
        "session_id": session_id,
        "session_intro": session_intro,
        "opening_narration": narration_result.passage,
        "choices": narration_result.choices,
        "streaming_enabled": STREAMING_ENABLED,
    }


@router.post("/session/{session_id}/turn")
async def handle_turn(
    session_id: str,
    req: TurnRequest,
    background_tasks: BackgroundTasks,
):
    """
    Complete turn handler. Steps are sequential and must not be reordered.
    The physics-before-imagination invariant is enforced by steps 1-5
    completing before step 6 (narration).
    """
    # ── Step 0: Load session state ────────────────────────────────────
    session = get_session(session_id)
    if session is None:
        raise HTTPException(404, "Session not found")

    character = Character.model_validate_json(session["character_json"])
    arc_state = json.loads(session["arc_state_json"])
    spine = load_campaign_spine(session["campaign_name"])
    current_act = spine["acts"][arc_state["current_act"] - 1]

    # Phase 8: Obligation reduces strain threshold by 2 when active (§9)
    effective_strain_threshold = character.strain_threshold
    if arc_state.get("obligation_active"):
        effective_strain_threshold = max(1, character.strain_threshold - 2)
    # Duty increases wound threshold by 1 when active (§9)
    effective_wound_threshold = character.wound_threshold
    if arc_state.get("duty_active"):
        effective_wound_threshold = character.wound_threshold + 1

    # Phase 16: Load ship states (§17) — primary ship for vehicle checks
    ships = load_ship_states(session_id)
    primary_ship = ships[0] if ships else None

    # ── Step 1: Resolve the player's choice ───────────────────────────
    last_turn = get_most_recent_turn(session_id)
    previous_choices = json.loads(last_turn["choices_json"])
    previous_skill_tags = json.loads(last_turn.get("skill_tags_json") or "[]")

    free_form = (req.free_form_action or "").strip() if req.free_form_action else ""
    if free_form:
        # Free-form path: player typed their own action.
        # The local check decision model picks the skill and difficulty.
        # We require the action to be reasonable length to deter abuse.
        if len(free_form) > 600:
            raise HTTPException(400, "Free-form action too long (max 600 chars)")
        player_action = free_form
        selected_skill_tag = None  # let the check decision model decide
    else:
        if req.choice_index < 0 or req.choice_index >= len(previous_choices):
            raise HTTPException(400, f"Invalid choice_index: {req.choice_index}")
        player_action = previous_choices[req.choice_index]
        selected_skill_tag = (
            previous_skill_tags[req.choice_index]
            if req.choice_index < len(previous_skill_tags)
            else None
        )
    if free_form:
        _clear_pending_social_offers(arc_state)
    else:
        _consume_selected_social_offer(arc_state, req.choice_index)
    update_session_state(session_id, character, arc_state)

    # ── Step 2: Build scene description for local GM ──────────────────
    scene_description = _build_scene_description(
        last_turn, player_action, arc_state, current_act
    )

    # ── Step 3: Check decision (local model) ──────────────────────────
    recent_turns = get_recent_turns(session_id, limit=5)
    recent_failure_count = sum(
        1 for t in recent_turns[-3:]
        if t.outcome_quadrant and t.outcome_quadrant.startswith("failure")
    )

    check_decision = None if free_form else _decision_from_choice_tag(
        selected_skill_tag,
        character,
        player_action=player_action,
        recent_failure_count=recent_failure_count,
        tension_level=current_act.get("tension"),
        ship_state=primary_ship,
    )
    if check_decision is None:
        check_decision = decide_check(
            character=character,
            scene_description=scene_description,
            player_action=player_action,
            arc_state=arc_state,
            recent_failure_count=recent_failure_count,
            ship_state=primary_ship if primary_ship else None,
        )
    check_decision = _sanitize_check_decision(
        check_decision,
        player_action=player_action,
        ship_state=primary_ship,
    )

    # ── Step 4: Dice resolution (if check required) ───────────────────
    dice_pool = None
    roll_result = None
    talent_activations = []
    destiny_result = None
    force_result = None  # Phase 14: Force resolution result (§16)

    # Phase 11.5: Load destiny state (§23)
    destiny = DestinyState(
        light=session["destiny_light"],
        dark=session["destiny_dark"],
        light_spent_this_act=arc_state.get("destiny_light_spent_this_act", 0),
        dark_spent_this_act=arc_state.get("destiny_dark_spent_this_act", 0),
    )

    is_pure_force = (check_decision.requires_check
                     and check_decision.force_use
                     and not check_decision.skill)

    if check_decision.requires_check:
        if is_pure_force:
            # Pure Force action — no skill check, only Force dice (§16.1)
            dice_pool = build_pure_force_pool(
                character,
                boost_dice=check_decision.boost_dice,
                setback_dice=check_decision.setback_dice,
            )
            talent_activations = []
        else:
            check_request = CheckRequest(
                skill=check_decision.skill,
                difficulty=DIFFICULTY_LABELS[check_decision.difficulty],
                boost_dice=check_decision.boost_dice,
                setback_dice=check_decision.setback_dice,
            )

            # Check for antagonist NPC in scene (disposition < 0.3)
            npc_hostile = any(
                npc.disposition < 0.3
                for npc in _select_active_scene_npcs(
                    load_npc_states(session_id, spine),
                    arc_state,
                    current_act,
                    scene_description,
                    player_action,
                )
            )

            dice_pool, talent_activations, destiny_result = build_pool(
                character, check_request,
                scene_type=check_decision.scene_type,
                destiny_state=destiny,
                tension_level=current_act["tension"],
                anchor_proximity=arc_state.get("anchor_proximity", "distant"),
                act_progress=arc_state.get("act_progress", 0.0),
                obligation_active=arc_state.get("obligation_active", False),
                npc_disposition_below_threshold=npc_hostile,
                spine_dark_trigger=current_act.get("destiny_dark_trigger", False),
                force_use=check_decision.force_use,
                ship_state=primary_ship if check_decision.scene_type == "space_combat" else None,
            )

        roll_result = roll_pool(dice_pool)

        # Persist destiny pool changes
        if destiny_result and destiny_result.pool_modified:
            update_destiny_pool(session_id, destiny.light, destiny.dark)
            arc_state["destiny_light_spent_this_act"] = destiny.light_spent_this_act
            arc_state["destiny_dark_spent_this_act"] = destiny.dark_spent_this_act

        # Apply mechanical consequences (wounds, strain) — physics first
        if roll_result.outcome_quadrant in ("failure_threat", "success_threat"):
            if abs(roll_result.net_advantages) >= 2:
                character.current_strain = min(
                    character.current_strain + 1,
                    effective_strain_threshold,
                )

        # Phase 16: Apply vehicle damage from check results (§17.3)
        if (primary_ship and check_decision.scene_type == "space_combat"
                and check_decision.skill and is_vehicle_skill(check_decision.skill)):
            # Threat → system strain on the ship
            if roll_result.net_advantages < 0:
                primary_ship.apply_system_strain(abs(roll_result.net_advantages))
            # Failed combat check → hull trauma from enemy fire
            if not roll_result.succeeded and check_decision.skill in ("gunnery", "piloting_space", "piloting_planetary"):
                primary_ship.apply_hull_trauma(3)  # standard hit
            # Triumph → no extra vehicle effect (personal triumph)
            # Despair → vehicle critical hit
            if roll_result.despairs > 0:
                roll_vehicle_critical(primary_ship)
            save_ship_state(session_id, primary_ship)

    # ── Step 4a: Force pip resolution (Phase 14, §16.1) ───────────────
    if roll_result and check_decision.force_use and character.force_rating > 0:
        morality = character.motivation.morality
        pips_req = check_decision.force_pips_required or 1
        resolution = resolve_force_pips(roll_result, pips_req, morality)

        if resolution.force_succeeded:
            force_result = build_clean_success(
                roll_result, pips_req, morality,
                force_power=check_decision.force_power or "",
            )
        elif resolution.temptation_available:
            # ── Step 4b: Dark side temptation (§16.2) ─────────────────
            temptation = build_temptation_choice(
                resolution,
                force_power=check_decision.force_power or "",
            )
            arc_state["pending_temptation"] = {
                "check_skill": check_decision.skill,
                "check_difficulty": check_decision.difficulty,
                "scene_type": check_decision.scene_type,
                "moral_weight": check_decision.moral_weight,
                "force_use": True,
                "force_power": check_decision.force_power or "",
                "force_pips_required": pips_req,
                "is_pure_force": is_pure_force,
                "dice_pool": asdict(dice_pool),
                "roll_result": asdict(roll_result),
                "resolution": {
                    "light_pips": resolution.light_pips,
                    "dark_pips": resolution.dark_pips,
                    "pips_required": resolution.pips_required,
                    "is_dark_dominant": resolution.is_dark_dominant,
                    "is_grey": resolution.is_grey,
                    "pips_needed_from_costly_side": resolution.pips_needed_from_costly_side,
                    "conflict_cost": resolution.conflict_cost,
                    "strain_cost": resolution.strain_cost,
                },
                "talent_activations": [asdict(a) for a in talent_activations],
                "destiny_narrative_note": (
                    destiny_result.narrative_note if destiny_result else ""
                ),
                "player_action": player_action,
                "choice_index": req.choice_index,
            }
            update_session_state(session_id, character, arc_state)
            return {
                "pending": True,
                "temptation_offer": temptation,
                "dice_result": describe_pool_for_display(dice_pool),
                "roll_summary": roll_result.narrative_label() if not is_pure_force else None,
                "force_pips": {
                    "light": roll_result.light_pips,
                    "dark": roll_result.dark_pips,
                    "required": pips_req,
                },
                "session_state": {
                    "turn_number": _next_turn_number(session_id),
                    "wounds": character.current_wounds,
                    "strain": character.current_strain,
                },
            }
        else:
            force_result = build_total_failure(
                roll_result, pips_req,
                force_power=check_decision.force_power or "",
            )

    # ── Step 3.5: Intervention check (Phase 12, §15.1) ──────────────
    if roll_result and check_decision.requires_check and check_decision.skill:
        offer = check_interventions(
            character, check_decision.skill, roll_result.succeeded,
            current_act=arc_state["current_act"],
        )
        if offer:
            # Store pending state for the /intervention endpoint
            arc_state["pending_intervention"] = {
                "check_skill": check_decision.skill,
                "check_difficulty": check_decision.difficulty,
                "scene_type": check_decision.scene_type,
                "moral_weight": check_decision.moral_weight,
                "dice_pool": asdict(dice_pool),
                "roll_result": asdict(roll_result),
                "talent_ref": offer.talent_ref,
                "talent_name": offer.talent_name,
                "strain_cost": offer.strain_cost,
                "narrative_prompt": offer.narrative_prompt,
                "player_action": player_action,
                "choice_index": req.choice_index,
                "talent_activations": [asdict(a) for a in talent_activations],
                "destiny_narrative_note": (
                    destiny_result.narrative_note if destiny_result else ""
                ),
            }
            update_session_state(session_id, character, arc_state)
            return {
                "pending": True,
                "intervention_offer": {
                    "talent_name": offer.talent_name,
                    "strain_cost": offer.strain_cost,
                    "narrative_prompt": offer.narrative_prompt,
                },
                "dice_result": describe_pool_for_display(dice_pool),
                "roll_summary": roll_result.narrative_label(),
                "session_state": {
                    "turn_number": _next_turn_number(session_id),
                    "wounds": character.current_wounds,
                    "strain": character.current_strain,
                },
            }

    # Phase 9: Compute combat damage context for narration (§18)
    combat_damage_note = ""
    if (roll_result and check_decision.requires_check
            and check_decision.skill in COMBAT_SKILLS
            and roll_result.succeeded):
        weapon = get_weapon_for_skill(character.loadout, check_decision.skill)
        if weapon:
            combat_damage_note = build_combat_damage_block(roll_result, weapon)

    # Phase 16: Vehicle damage context for narration (§17.3)
    if (primary_ship and check_decision.scene_type == "space_combat"
            and roll_result and check_decision.skill):
        vehicle_damage_note = build_vehicle_damage_block(
            primary_ship, roll_result, check_decision.skill,
        )
        if vehicle_damage_note:
            combat_damage_note = (
                (combat_damage_note + "\n" if combat_damage_note else "")
                + vehicle_damage_note
            )

    # ── Phase 13: Choice annotation (background thread, §24) ─────────
    annotation_result = [None]  # mutable container for thread result

    def _annotation_thread():
        annotation_result[0] = _run_annotation_background(
            session_id=session_id,
            player_action=player_action,
            all_choices=previous_choices,
            choice_index=req.choice_index,
            scene_description=scene_description,
            npc_states=load_npc_states(session_id, spine),
            recent_turns=recent_turns,
            throughline_question=spine.get("throughline_question", ""),
            narrative_arc_block=build_narrative_arc_block(character),
        )

    annotation_thread = None
    if CHOICE_ANNOTATION_ENABLED:
        annotation_thread = threading.Thread(target=_annotation_thread, daemon=True)
        annotation_thread.start()

    # ── Phase 13: Prose diagnostic (§13) ──────────────────────────────
    recent_narrations = get_recent_narrations(session_id, limit=4)
    prose_diagnostic = None
    if PROSE_DIAGNOSTIC_INLINE and len(recent_narrations) >= 2:
        npc_states_for_diag = load_npc_states(session_id, spine)
        npc_diag_block = "\n".join(
            npc.to_prompt_block() for npc in npc_states_for_diag
        ) if npc_states_for_diag else "No NPCs."
        prose_diagnostic = run_prose_diagnostic(recent_narrations, npc_diag_block)

    # ── Phase 13: Aspiration echo (§14.5) ─────────────────────────────
    aspiration_echo = _build_aspiration_echo(character, arc_state)

    # ── Phase 14: Apply Force mechanical effects (§16) ────────────────
    if force_result:
        if force_result.conflict_earned:
            character.motivation.conflict += force_result.conflict_earned
        if force_result.strain_charged:
            character.current_strain = min(
                character.current_strain + force_result.strain_charged,
                effective_strain_threshold,
            )

    # Phase 14: Build Force context blocks for narration (§16)
    _force_state_block = build_force_state_block(character)
    _force_result_block = ""
    if force_result:
        skill_succeeded = roll_result.succeeded if (roll_result and not is_pure_force) else None
        _force_result_block = build_force_result_block(
            force_result, skill_succeeded, character.motivation.morality,
        )

    # ── Step 5: Assemble context package ──────────────────────────────
    story_summary = get_act_summaries(session_id)
    npc_states = load_npc_states(session_id, spine)
    turn_number = _next_turn_number(session_id)
    scene_state = _initial_scene_state(arc_state, current_act)
    scene_npcs = _select_active_scene_npcs(
        npc_states, arc_state, current_act, scene_description, player_action
    )

    # Phase 8.5: Decay emotions + set from dice results (§25)
    for npc in npc_states:
        npc.decay_emotion()
        npc.nudge_disposition_from_emotion()
    if roll_result and check_decision.requires_check and check_decision.skill:
        _apply_emotion_from_check(
            npc_states, check_decision.skill,
            roll_result.outcome_quadrant, turn_number,
        )

    # Check if anchor was reached on previous turn — inject anchor instruction
    anchor_inst = None
    if arc_state.get("act_progress", 0.0) >= 1.0:
        next_act_idx = arc_state["current_act"]  # 0-indexed next
        next_act = spine["acts"][next_act_idx] if next_act_idx < spine["total_acts"] else None
        anchor_inst = build_anchor_instruction(current_act, next_act)

    # Dynamic per-turn fields (reputation, behavioral, era voice, identity
    # drift, introspection trigger).
    dyn_fields = _compute_dynamic_context_fields(
        session_id, turn_number, arc_state, current_act, scene_npcs, spine,
        character=character, roll_result=roll_result,
    )

    ctx = ContextPackage(
        character=character,
        arc=ArcState(
            campaign_name=spine["name"],
            current_act=arc_state["current_act"],
            total_acts=spine["total_acts"],
            act_name=current_act["name"],
            act_progress=arc_state.get("act_progress", 0.0),
            current_anchor=current_act["anchor"],
            next_anchor=current_act.get("next_anchor", ""),
            anchors_completed=arc_state.get("anchors_completed", []),
            throughline_question=spine["throughline_question"],
            tension_level=current_act["tension"],
            open_threads=_thread_states_for_context(current_act, arc_state),
            closed_threads=arc_state.get("closed_threads", []),
            turns_this_act=arc_state.get("turns_this_act", 0),
            anchor_proximity=arc_state.get("anchor_proximity", "distant"),
            anchor_description=current_act.get("anchor_description", ""),
            obligation_active=arc_state.get("obligation_active", False),
            obligation_type=arc_state.get("obligation_type", ""),
            duty_active=arc_state.get("duty_active", False),
            duty_type=arc_state.get("duty_type", ""),
            morality_label=arc_state.get("morality_label", ""),
            last_reputation_echo_turn=arc_state.get("last_reputation_echo_turn", 0),
        ),
        story_summary=story_summary,
        recent_turns=recent_turns,
        active_npcs=scene_npcs,
        location=scene_state.get("current_location", ""),
        situation=scene_description,
        galactic_context=current_act.get("galactic_context", ""),
        scene_type=check_decision.scene_type,
        dice_pool=dice_pool,
        roll_result=roll_result,
        anchor_instruction=anchor_inst,
        expected_turns=current_act.get("expected_turns", [8, 12]),
        combat_damage_note=combat_damage_note,
        talent_activations=talent_activations,
        destiny_narrative_note=(
            destiny_result.narrative_note if destiny_result else ""
        ),
        aspiration_echo_instructions=aspiration_echo,
        prose_diagnostic=prose_diagnostic,
        force_state_block=_force_state_block,
        force_result_block=_force_result_block,
        force_check_kind=(
            "pure" if force_result and is_pure_force
            else "enhanced" if force_result else ""
        ),
        ship_state_block=(
            primary_ship.to_narration_block() if primary_ship
            and check_decision.scene_type == "space_combat" else ""
        ),
        **dyn_fields,
    )

    # ── Step 6: Narrate (cloud model — one call) ─────────────────────
    narration_result = narrate_turn(ctx)

    _post_narration_reputation_hook(
        turn_number, arc_state,
        dyn_fields["reputation_entries"], narration_result.passage,
    )
    _post_narration_drift_hook(
        turn_number=turn_number,
        arc_state=arc_state,
        character=character,
        drift_cue=dyn_fields["identity_drift_cue"],
        roll_result=roll_result,
        pinch_fired_this_turn=bool(dyn_fields["pinch_point_instruction"]),
    )
    arc_state["consecutive_no_check_turns"] = (
        0 if roll_result is not None
        else int(arc_state.get("consecutive_no_check_turns", 0) or 0) + 1
    )
    scene_thread_updates = _apply_narration_scene_state(
        arc_state=arc_state,
        current_act=current_act,
        npc_states=npc_states,
        narration_result=narration_result,
        player_action=player_action,
        scene_type=arc_state.get("scene_state", {}).get("scene_type", check_decision.scene_type),
        recent_turns=recent_turns,
        turn_number=turn_number,
        skill=check_decision.skill,
        ship_state=primary_ship,
    )

    # ── Step 7: Reconciliation (local model, fast tier with escalation) ─
    check_result_str = ""
    if roll_result:
        check_result_str = (
            f"{check_decision.skill} ({check_decision.difficulty}): "
            f"{roll_result.narrative_label()}"
        )

    recon_result, new_zero_delta_count, _escalated = _reconcile_turn_fast_or_full(
        session_id=session_id,
        turn_number=turn_number,
        prior_zero_delta_count=arc_state.get("consecutive_zero_delta_turns", 0),
        narration=narration_result.passage,
        player_action=player_action,
        check_result=check_result_str,
        active_npcs=scene_npcs,
        arc=ctx.arc,
        spine_act=current_act,
        spine=spine,
    )
    arc_state["consecutive_zero_delta_turns"] = new_zero_delta_count
    recon_result.thread_updates = _merge_thread_updates(
        recon_result.thread_updates, scene_thread_updates
    )

    _post_reconciliation_reputation_hook(session_id, turn_number, recon_result)
    _post_reconciliation_cs6_hook(
        arc_state,
        recon_result,
        turn_number=turn_number,
        foreshadow_instruction=dyn_fields.get("foreshadow_instruction", ""),
        spine=spine,
        character=character,
    )
    _post_turn_memorable_moments_hook(
        arc_state,
        turn_number,
        roll_result=roll_result,
        recon_result=recon_result,
        scene_npcs=scene_npcs,
        player_action=player_action,
        narration_passage=narration_result.passage,
        candidate_moments=dyn_fields.get("memorable_moments", []),
    )
    _post_turn_world_state_hook(
        arc_state,
        spine=spine,
        current_act=current_act,
        player_action=player_action,
        roll_result=roll_result,
        npc_states=scene_npcs,
        side_content_offered=bool(dyn_fields.get("side_content_block", "")),
        pivot_offered=bool(dyn_fields.get("pivot_warning_block", "")),
    )

    # ── Step 8: Apply state updates ──────────────────────────────────
    # NPC updates (knowledge, disposition)
    apply_npc_updates(recon_result.npc_updates, npc_states)
    for npc in npc_states:
        save_npc_state(session_id, npc)

    # Story progress (act_progress, anchor_proximity)
    arc_state["turns_this_act"] = arc_state.get("turns_this_act", 0) + 1
    apply_story_progress(recon_result.story_progress, arc_state, current_act)

    # Thread updates
    apply_thread_updates(recon_result.thread_updates, arc_state, current_act)

    # ── Step 8.5: Telemetry ──────────────────────────────────────────
    # Emit structured events for narrative analytics
    emit_choice_made(
        session_id, turn_number,
        choice_index=req.choice_index,
        choice_text=player_action,
        skill_tag=selected_skill_tag,
    )
    if roll_result:
        emit_dice_resolved(
            session_id, turn_number,
            pool=asdict(dice_pool) if dice_pool else {},
            outcome_quadrant=roll_result.outcome_quadrant,
            succeeded=roll_result.succeeded,
        )

    # Consequence contract: count state deltas from reconciliation
    deltas = count_state_deltas(recon_result)
    emit_state_delta(session_id, turn_number, deltas)
    if deltas["total_changes"] == 0:
        emit_consequence_gap(session_id, turn_number)

    # NPC disposition shift events
    for npc_update in recon_result.npc_updates:
        shift = npc_update.get("disposition_shift", 0)
        if abs(shift) > 0:
            npc_name = npc_update.get("npc_name", "")
            # Find old disposition from npc_states
            old_disp = 0.5
            for npc in npc_states:
                if npc.name == npc_name:
                    # Disposition was already applied, so reverse to get old
                    old_disp = max(0.0, min(1.0, npc.disposition - shift))
                    break
            emit_npc_disposition_shift(
                session_id, turn_number,
                npc_name=npc_name,
                old_value=old_disp,
                new_value=npc.disposition if npc.name == npc_name else old_disp + shift,
            )

    # Thread events
    for t in recon_result.thread_updates.get("threads_opened", []):
        emit_thread_event(session_id, turn_number, "opened", t)
    for t in recon_result.thread_updates.get("threads_advanced", []):
        emit_thread_event(session_id, turn_number, "progressed", t)
    for t in recon_result.thread_updates.get("threads_resolved", []):
        emit_thread_event(session_id, turn_number, "resolved", t)

    # ── Step 9: Check act boundary ───────────────────────────────────
    act_boundary_reached = detect_act_boundary(arc_state)

    # Phase 13: Wait for annotation thread to complete (§24)
    if annotation_thread:
        annotation_thread.join(timeout=ANNOTATION_JOIN_TIMEOUT_SEC)
    choice_implications_json = annotation_result[0]
    if act_boundary_reached:
        _clear_pending_social_offers(arc_state)
    else:
        _append_social_offers_to_narration(narration_result, spine, arc_state)

    # ── Step 10: Persist ─────────────────────────────────────────────
    log_turn(
        session_id=session_id,
        turn_number=turn_number,
        player_action=player_action,
        choice_index=req.choice_index,
        narration=narration_result.passage,
        choices=narration_result.choices,
        check_skill=check_decision.skill if check_decision.requires_check else None,
        check_difficulty=check_decision.difficulty if check_decision.requires_check else None,
        dice_pool_json=json.dumps(asdict(dice_pool)) if dice_pool else None,
        roll_result_json=json.dumps(asdict(roll_result)) if roll_result else None,
        context_json=_context_audit_json(ctx),
        scene_type=arc_state.get("scene_state", {}).get("scene_type", check_decision.scene_type),
        moral_weight=check_decision.moral_weight,
        skill_tags_json=json.dumps(narration_result.skill_tags),
        choice_implications=choice_implications_json,
        force_result_json=(
            json.dumps(asdict(force_result)) if force_result else None
        ),
    )
    _finish_active_social_scene(arc_state)

    # Phase 24: track pattern-of-use for talent earned-through-use unlocks
    _track_pattern_use(
        character,
        arc_state.get("scene_state", {}).get("scene_type", check_decision.scene_type),
        check_decision.skill,
    )

    # ── Step 11: Update session state ─────────────────────────────────
    update_session_state(session_id, character, arc_state)

    # ── Step 12: Background compression ───────────────────────────────
    background_tasks.add_task(
        compress_if_needed, session_id, arc_state["current_act"]
    )

    # ── Step 13: Between-act processing (if boundary reached) ────────
    # Runs synchronously — the pipeline updates DB state (act reset, NPC drift,
    # compression) and the response must reflect the new act.
    milestone_data = None
    force_power_milestone_data = None
    time_skip_data = None
    if act_boundary_reached:
        pipeline_result = run_between_act_pipeline(
            session_id, character, spine, arc_state["current_act"],
        )
        # Reload arc_state from DB — pipeline step 16 wrote the reset
        if pipeline_result.next_act_loaded:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT arc_state_json FROM sessions WHERE id = ?",
                    (session_id,),
                ).fetchone()
                if row:
                    arc_state = json.loads(row["arc_state_json"])

        # Phase 12: Store pending milestone for /milestone endpoint (§14.3)
        if pipeline_result.milestone_passage:
            milestone_data = {
                "passage": pipeline_result.milestone_passage,
                "choices": pipeline_result.milestone_choices,
            }
            arc_state["pending_milestone"] = milestone_data

        # Phase 15: Store pending Force power milestone (§16.4)
        if pipeline_result.force_power_milestone_passage:
            force_power_milestone_data = {
                "passage": pipeline_result.force_power_milestone_passage,
                "choices": pipeline_result.force_power_milestone_choices,
            }
            arc_state["pending_force_power_milestone"] = force_power_milestone_data

        # Phase 17: Store pending time skip for /vignette endpoint (§19)
        if pipeline_result.time_skip_data:
            time_skip_data = pipeline_result.time_skip_data
            arc_state["pending_time_skip"] = time_skip_data

        if milestone_data or force_power_milestone_data or time_skip_data:
            update_session_state(session_id, character, arc_state)

    # ── Return ────────────────────────────────────────────────────────
    response = {
        "narration": narration_result.passage,
        "choices": narration_result.choices,
        "dice_result": describe_pool_for_display(dice_pool) if dice_pool else None,
        "roll_summary": roll_result.narrative_label() if roll_result else None,
        "session_state": {
            "turn_number": turn_number,
            "wounds": character.current_wounds,
            "strain": character.current_strain,
            "act_progress": arc_state.get("act_progress", 0.0),
            "anchor_proximity": arc_state.get("anchor_proximity", "distant"),
            "scene_state": arc_state.get("scene_state", {}),
        },
        "used_local_narration": narration_result.used_local,
        "act_boundary": act_boundary_reached,
        "destiny": {
            "light_spent": bool(destiny_result and destiny_result.light_spent),
            "dark_spent":  bool(destiny_result and destiny_result.dark_spent),
            "light_remaining": (
                destiny_result.light_remaining if destiny_result else session["destiny_light"]
            ),
            "dark_remaining": (
                destiny_result.dark_remaining if destiny_result else session["destiny_dark"]
            ),
        },
    }
    if milestone_data:
        response["milestone"] = milestone_data
    if force_power_milestone_data:
        response["force_power_milestone"] = force_power_milestone_data
    if time_skip_data:
        response["time_skip"] = {
            "opening_passage": time_skip_data["opening_passage"],
            "duration_months": time_skip_data["duration_months"],
            "framing": time_skip_data["framing"],
            "vignettes": time_skip_data["vignettes"],
            "current_vignette_index": 0,
        }
    return response


@router.get("/session/{session_id}")
async def get_session_route(session_id: str):
    """Load session state, recent turns, and arc state."""
    session = get_session(session_id)
    if session is None:
        raise HTTPException(404, "Session not found")

    arc_state = json.loads(session["arc_state_json"])
    character = Character.model_validate_json(session["character_json"])
    recent_turns = get_recent_turns(session_id, limit=5)
    turn_count = get_turn_count(session_id)

    # Get the most recent turn for current choices
    last_turn = None
    if turn_count > 0:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT narration, choices_json, check_skill, roll_result_json "
                "FROM turns WHERE session_id = ? ORDER BY turn_number DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            if row:
                last_turn = {
                    "narration": row["narration"],
                    "choices": json.loads(row["choices_json"]),
                    "check_skill": row["check_skill"],
                    "roll_result": (
                        json.loads(row["roll_result_json"])
                        if row["roll_result_json"] else None
                    ),
                }

    return {
        "session_id": session_id,
        "campaign_name": session["campaign_name"],
        "turn_count": turn_count,
        "streaming_enabled": STREAMING_ENABLED,
        "session_state": {
            "wounds": character.current_wounds,
            "strain": character.current_strain,
            "current_act": arc_state.get("current_act", 1),
            "current_location": arc_state.get("current_location", ""),
        },
        "arc_state": arc_state,
        # Full character object — lets harnesses and the frontend read the
        # live narrative_arc (lie_grip, movements) and any state that mutates
        # turn-to-turn (Conflict, Morality, Force commitments, talents).
        "character": json.loads(character.model_dump_json()),
        "recent_turns": [
            {
                "turn_number": t.turn_number,
                "player_action": t.player_action,
                "check_made": t.check_made,
                "dice_result": t.dice_result,
                "outcome_quadrant": t.outcome_quadrant,
            }
            for t in recent_turns
        ],
        "last_turn": last_turn,
    }


@router.post("/session/{session_id}/turn/stream")
async def handle_turn_stream(
    session_id: str,
    req: TurnRequest,
):
    """
    SSE streaming variant of the turn handler.
    Streams narration text chunks, then sends a final 'done' event
    with choices, dice result, and session state.
    """
    if not STREAMING_ENABLED:
        raise HTTPException(400, "Streaming is not enabled")

    # ── Step 0: Load session state ────────────────────────────────────
    session = get_session(session_id)
    if session is None:
        raise HTTPException(404, "Session not found")

    character = Character.model_validate_json(session["character_json"])
    arc_state = json.loads(session["arc_state_json"])
    spine = load_campaign_spine(session["campaign_name"])
    current_act = spine["acts"][arc_state["current_act"] - 1]

    # Phase 8: Obligation reduces strain threshold by 2 when active (§9)
    effective_strain_threshold = character.strain_threshold
    if arc_state.get("obligation_active"):
        effective_strain_threshold = max(1, character.strain_threshold - 2)
    # Duty increases wound threshold by 1 when active (§9)
    effective_wound_threshold = character.wound_threshold
    if arc_state.get("duty_active"):
        effective_wound_threshold = character.wound_threshold + 1

    # Phase 16: Load ship states (§17) — primary ship for vehicle checks
    ships_s = load_ship_states(session_id)
    primary_ship_s = ships_s[0] if ships_s else None

    # ── Step 1: Resolve the player's choice ───────────────────────────
    last_turn = get_most_recent_turn(session_id)
    previous_choices = json.loads(last_turn["choices_json"])
    previous_skill_tags_s = json.loads(last_turn.get("skill_tags_json") or "[]")

    free_form_s = (req.free_form_action or "").strip() if req.free_form_action else ""
    if free_form_s:
        if len(free_form_s) > 600:
            raise HTTPException(400, "Free-form action too long (max 600 chars)")
        player_action = free_form_s
        selected_skill_tag_s = None
    else:
        if req.choice_index < 0 or req.choice_index >= len(previous_choices):
            raise HTTPException(400, f"Invalid choice_index: {req.choice_index}")

        player_action = previous_choices[req.choice_index]
        selected_skill_tag_s = (
            previous_skill_tags_s[req.choice_index]
            if req.choice_index < len(previous_skill_tags_s)
            else None
        )
    if free_form_s:
        _clear_pending_social_offers(arc_state)
    else:
        _consume_selected_social_offer(arc_state, req.choice_index)

    # ── Step 2: Build scene description for local GM ──────────────────
    scene_description = _build_scene_description(
        last_turn, player_action, arc_state, current_act
    )

    # ── Step 3: Check decision (local model) ──────────────────────────
    recent_turns = get_recent_turns(session_id, limit=5)
    recent_failure_count = sum(
        1 for t in recent_turns[-3:]
        if t.outcome_quadrant and t.outcome_quadrant.startswith("failure")
    )

    check_decision = None if free_form_s else _decision_from_choice_tag(
        selected_skill_tag_s,
        character,
        player_action=player_action,
        recent_failure_count=recent_failure_count,
        tension_level=current_act.get("tension"),
        ship_state=primary_ship_s,
    )
    if check_decision is None:
        check_decision = decide_check(
            character=character,
            scene_description=scene_description,
            player_action=player_action,
            arc_state=arc_state,
            recent_failure_count=recent_failure_count,
            ship_state=primary_ship_s if primary_ship_s else None,
        )
    check_decision = _sanitize_check_decision(
        check_decision,
        player_action=player_action,
        ship_state=primary_ship_s,
    )

    # ── Step 4: Dice resolution (if check required) ───────────────────
    dice_pool = None
    roll_result = None
    talent_activations = []
    destiny_result = None
    force_result = None  # Phase 14: Force resolution result (§16)

    # Phase 11.5: Load destiny state (§23)
    destiny = DestinyState(
        light=session["destiny_light"],
        dark=session["destiny_dark"],
        light_spent_this_act=arc_state.get("destiny_light_spent_this_act", 0),
        dark_spent_this_act=arc_state.get("destiny_dark_spent_this_act", 0),
    )

    is_pure_force_s = (check_decision.requires_check
                       and check_decision.force_use
                       and not check_decision.skill)

    if check_decision.requires_check:
        if is_pure_force_s:
            dice_pool = build_pure_force_pool(
                character,
                boost_dice=check_decision.boost_dice,
                setback_dice=check_decision.setback_dice,
            )
            talent_activations = []
        else:
            check_request = CheckRequest(
                skill=check_decision.skill,
                difficulty=DIFFICULTY_LABELS[check_decision.difficulty],
                boost_dice=check_decision.boost_dice,
                setback_dice=check_decision.setback_dice,
            )

            npc_hostile = any(
                npc.disposition < 0.3
                for npc in _select_active_scene_npcs(
                    load_npc_states(session_id, spine),
                    arc_state,
                    current_act,
                    scene_description,
                    player_action,
                )
            )

            dice_pool, talent_activations, destiny_result = build_pool(
                character, check_request,
                scene_type=check_decision.scene_type,
                destiny_state=destiny,
                tension_level=current_act["tension"],
                anchor_proximity=arc_state.get("anchor_proximity", "distant"),
                act_progress=arc_state.get("act_progress", 0.0),
                obligation_active=arc_state.get("obligation_active", False),
                npc_disposition_below_threshold=npc_hostile,
                spine_dark_trigger=current_act.get("destiny_dark_trigger", False),
                force_use=check_decision.force_use,
                ship_state=primary_ship_s if check_decision.scene_type == "space_combat" else None,
            )

        roll_result = roll_pool(dice_pool)

        if destiny_result and destiny_result.pool_modified:
            update_destiny_pool(session_id, destiny.light, destiny.dark)
            arc_state["destiny_light_spent_this_act"] = destiny.light_spent_this_act
            arc_state["destiny_dark_spent_this_act"] = destiny.dark_spent_this_act

        if roll_result.outcome_quadrant in ("failure_threat", "success_threat"):
            if abs(roll_result.net_advantages) >= 2:
                character.current_strain = min(
                    character.current_strain + 1,
                    effective_strain_threshold,
                )

        # Phase 16: Apply vehicle damage from check results (§17.3)
        if (primary_ship_s and check_decision.scene_type == "space_combat"
                and check_decision.skill and is_vehicle_skill(check_decision.skill)):
            if roll_result.net_advantages < 0:
                primary_ship_s.apply_system_strain(abs(roll_result.net_advantages))
            if not roll_result.succeeded and check_decision.skill in ("gunnery", "piloting_space", "piloting_planetary"):
                primary_ship_s.apply_hull_trauma(3)
            if roll_result.despairs > 0:
                roll_vehicle_critical(primary_ship_s)
            save_ship_state(session_id, primary_ship_s)

    # ── Step 4a: Force pip resolution (Phase 14, §16.1) ───────────────
    if roll_result and check_decision.force_use and character.force_rating > 0:
        morality_s = character.motivation.morality
        pips_req_s = check_decision.force_pips_required or 1
        resolution_s = resolve_force_pips(roll_result, pips_req_s, morality_s)

        if resolution_s.force_succeeded:
            force_result = build_clean_success(
                roll_result, pips_req_s, morality_s,
                force_power=check_decision.force_power or "",
            )
        elif resolution_s.temptation_available:
            temptation_s = build_temptation_choice(
                resolution_s,
                force_power=check_decision.force_power or "",
            )
            arc_state["pending_temptation"] = {
                "check_skill": check_decision.skill,
                "check_difficulty": check_decision.difficulty,
                "scene_type": check_decision.scene_type,
                "moral_weight": check_decision.moral_weight,
                "force_use": True,
                "force_power": check_decision.force_power or "",
                "force_pips_required": pips_req_s,
                "is_pure_force": is_pure_force_s,
                "dice_pool": asdict(dice_pool),
                "roll_result": asdict(roll_result),
                "resolution": {
                    "light_pips": resolution_s.light_pips,
                    "dark_pips": resolution_s.dark_pips,
                    "pips_required": resolution_s.pips_required,
                    "is_dark_dominant": resolution_s.is_dark_dominant,
                    "is_grey": resolution_s.is_grey,
                    "pips_needed_from_costly_side": resolution_s.pips_needed_from_costly_side,
                    "conflict_cost": resolution_s.conflict_cost,
                    "strain_cost": resolution_s.strain_cost,
                },
                "talent_activations": [asdict(a) for a in talent_activations],
                "destiny_narrative_note": (
                    destiny_result.narrative_note if destiny_result else ""
                ),
                "player_action": player_action,
                "choice_index": req.choice_index,
            }
            update_session_state(session_id, character, arc_state)

            def temptation_sse():
                payload = {
                    "pending": True,
                    "temptation_offer": temptation_s,
                    "dice_result": describe_pool_for_display(dice_pool),
                    "roll_summary": roll_result.narrative_label() if not is_pure_force_s else None,
                    "force_pips": {
                        "light": roll_result.light_pips,
                        "dark": roll_result.dark_pips,
                        "required": pips_req_s,
                    },
                    "session_state": {
                        "turn_number": _next_turn_number(session_id),
                        "wounds": character.current_wounds,
                        "strain": character.current_strain,
                    },
                }
                yield f"event: temptation\ndata: {json.dumps(payload)}\n\n"
            return StreamingResponse(
                temptation_sse(), media_type="text/event-stream"
            )
        else:
            force_result = build_total_failure(
                roll_result, pips_req_s,
                force_power=check_decision.force_power or "",
            )

    # ── Step 3.5: Intervention check (Phase 12, §15.1) ──────────────
    if roll_result and check_decision.requires_check and check_decision.skill:
        offer = check_interventions(
            character, check_decision.skill, roll_result.succeeded,
            current_act=arc_state["current_act"],
        )
        if offer:
            arc_state["pending_intervention"] = {
                "check_skill": check_decision.skill,
                "check_difficulty": check_decision.difficulty,
                "scene_type": check_decision.scene_type,
                "moral_weight": check_decision.moral_weight,
                "dice_pool": asdict(dice_pool),
                "roll_result": asdict(roll_result),
                "talent_ref": offer.talent_ref,
                "talent_name": offer.talent_name,
                "strain_cost": offer.strain_cost,
                "narrative_prompt": offer.narrative_prompt,
                "player_action": player_action,
                "choice_index": req.choice_index,
                "talent_activations": [asdict(a) for a in talent_activations],
                "destiny_narrative_note": (
                    destiny_result.narrative_note if destiny_result else ""
                ),
            }
            update_session_state(session_id, character, arc_state)

            # Return intervention offer as SSE — no narration yet
            def intervention_sse():
                payload = {
                    "pending": True,
                    "intervention_offer": {
                        "talent_name": offer.talent_name,
                        "strain_cost": offer.strain_cost,
                        "narrative_prompt": offer.narrative_prompt,
                    },
                    "dice_result": describe_pool_for_display(dice_pool),
                    "roll_summary": roll_result.narrative_label(),
                    "session_state": {
                        "turn_number": _next_turn_number(session_id),
                        "wounds": character.current_wounds,
                        "strain": character.current_strain,
                    },
                }
                yield f"event: intervention\ndata: {json.dumps(payload)}\n\n"
            return StreamingResponse(
                intervention_sse(), media_type="text/event-stream"
            )

    # Phase 9: Compute combat damage context for narration (§18)
    combat_damage_note = ""
    if (roll_result and check_decision.requires_check
            and check_decision.skill in COMBAT_SKILLS
            and roll_result.succeeded):
        weapon = get_weapon_for_skill(character.loadout, check_decision.skill)
        if weapon:
            combat_damage_note = build_combat_damage_block(roll_result, weapon)

    # Phase 16: Vehicle damage context for narration (§17.3)
    if (primary_ship_s and check_decision.scene_type == "space_combat"
            and roll_result and check_decision.skill):
        vehicle_damage_note_s = build_vehicle_damage_block(
            primary_ship_s, roll_result, check_decision.skill,
        )
        if vehicle_damage_note_s:
            combat_damage_note = (
                (combat_damage_note + "\n" if combat_damage_note else "")
                + vehicle_damage_note_s
            )

    # ── Phase 13: Choice annotation (background thread, §24) ─────────
    annotation_result_stream = [None]

    def _annotation_thread_stream():
        annotation_result_stream[0] = _run_annotation_background(
            session_id=session_id,
            player_action=player_action,
            all_choices=previous_choices,
            choice_index=req.choice_index,
            scene_description=scene_description,
            npc_states=load_npc_states(session_id, spine),
            recent_turns=recent_turns,
            throughline_question=spine.get("throughline_question", ""),
            narrative_arc_block=build_narrative_arc_block(character),
        )

    annotation_thread_s = None
    if CHOICE_ANNOTATION_ENABLED:
        annotation_thread_s = threading.Thread(
            target=_annotation_thread_stream, daemon=True,
        )
        annotation_thread_s.start()

    # ── Phase 13: Prose diagnostic (§13) ──────────────────────────────
    recent_narrations_s = get_recent_narrations(session_id, limit=4)
    prose_diagnostic_s = None
    if PROSE_DIAGNOSTIC_INLINE and len(recent_narrations_s) >= 2:
        npc_states_for_diag_s = load_npc_states(session_id, spine)
        npc_diag_block_s = "\n".join(
            npc.to_prompt_block() for npc in npc_states_for_diag_s
        ) if npc_states_for_diag_s else "No NPCs."
        prose_diagnostic_s = run_prose_diagnostic(recent_narrations_s, npc_diag_block_s)

    # ── Phase 13: Aspiration echo (§14.5) ─────────────────────────────
    aspiration_echo_s = _build_aspiration_echo(character, arc_state)

    # ── Phase 14: Apply Force mechanical effects (§16) ────────────────
    if force_result:
        if force_result.conflict_earned:
            character.motivation.conflict += force_result.conflict_earned
        if force_result.strain_charged:
            character.current_strain = min(
                character.current_strain + force_result.strain_charged,
                effective_strain_threshold,
            )

    _force_state_block_s = build_force_state_block(character)
    _force_result_block_s = ""
    if force_result:
        skill_succ_s = roll_result.succeeded if (roll_result and not is_pure_force_s) else None
        _force_result_block_s = build_force_result_block(
            force_result, skill_succ_s, character.motivation.morality,
        )

    # ── Step 5: Assemble context package ──────────────────────────────
    story_summary = get_act_summaries(session_id)
    npc_states = load_npc_states(session_id, spine)
    turn_number = _next_turn_number(session_id)
    scene_state_s = _initial_scene_state(arc_state, current_act)
    scene_npcs_s = _select_active_scene_npcs(
        npc_states, arc_state, current_act, scene_description, player_action
    )

    # Phase 8.5: Decay emotions + set from dice results (§25)
    for npc in npc_states:
        npc.decay_emotion()
        npc.nudge_disposition_from_emotion()
    if roll_result and check_decision.requires_check and check_decision.skill:
        _apply_emotion_from_check(
            npc_states, check_decision.skill,
            roll_result.outcome_quadrant, turn_number,
        )

    # Check if anchor was reached on previous turn
    anchor_inst = None
    if arc_state.get("act_progress", 0.0) >= 1.0:
        next_act_idx = arc_state["current_act"]
        next_act = spine["acts"][next_act_idx] if next_act_idx < spine["total_acts"] else None
        anchor_inst = build_anchor_instruction(current_act, next_act)

    dyn_fields_s = _compute_dynamic_context_fields(
        session_id, turn_number, arc_state, current_act, scene_npcs_s, spine,
        character=character, roll_result=roll_result,
    )

    ctx = ContextPackage(
        character=character,
        arc=ArcState(
            campaign_name=spine["name"],
            current_act=arc_state["current_act"],
            total_acts=spine["total_acts"],
            act_name=current_act["name"],
            act_progress=arc_state.get("act_progress", 0.0),
            current_anchor=current_act["anchor"],
            next_anchor=current_act.get("next_anchor", ""),
            anchors_completed=arc_state.get("anchors_completed", []),
            throughline_question=spine["throughline_question"],
            tension_level=current_act["tension"],
            open_threads=_thread_states_for_context(current_act, arc_state),
            closed_threads=arc_state.get("closed_threads", []),
            turns_this_act=arc_state.get("turns_this_act", 0),
            anchor_proximity=arc_state.get("anchor_proximity", "distant"),
            anchor_description=current_act.get("anchor_description", ""),
            obligation_active=arc_state.get("obligation_active", False),
            obligation_type=arc_state.get("obligation_type", ""),
            duty_active=arc_state.get("duty_active", False),
            duty_type=arc_state.get("duty_type", ""),
            morality_label=arc_state.get("morality_label", ""),
            last_reputation_echo_turn=arc_state.get("last_reputation_echo_turn", 0),
        ),
        story_summary=story_summary,
        recent_turns=recent_turns,
        active_npcs=scene_npcs_s,
        location=scene_state_s.get("current_location", ""),
        situation=scene_description,
        galactic_context=current_act.get("galactic_context", ""),
        scene_type=check_decision.scene_type,
        dice_pool=dice_pool,
        roll_result=roll_result,
        anchor_instruction=anchor_inst,
        expected_turns=current_act.get("expected_turns", [8, 12]),
        combat_damage_note=combat_damage_note,
        talent_activations=talent_activations,
        destiny_narrative_note=(
            destiny_result.narrative_note if destiny_result else ""
        ),
        aspiration_echo_instructions=aspiration_echo_s,
        prose_diagnostic=prose_diagnostic_s,
        force_state_block=_force_state_block_s,
        force_result_block=_force_result_block_s,
        force_check_kind=(
            "pure" if force_result and is_pure_force_s
            else "enhanced" if force_result else ""
        ),
        ship_state_block=(
            primary_ship_s.to_narration_block() if primary_ship_s
            and check_decision.scene_type == "space_combat" else ""
        ),
        **dyn_fields_s,
    )

    # ── Step 6: Stream narration via SSE ──────────────────────────────
    # The generator streams text chunks, then a final JSON event.
    # Runs in a threadpool via StreamingResponse (sync generator).
    DELIMITER = "---CHOICES---"
    BUFFER_SIZE = len(DELIMITER)

    def generate():
        full_text = ""
        sent_up_to = 0
        choices_detected = False

        try:
            for chunk in narrate_turn_stream(ctx):
                full_text += chunk

                if choices_detected:
                    continue

                if DELIMITER in full_text:
                    choices_detected = True
                    delimiter_pos = full_text.index(DELIMITER)
                    unsent = full_text[sent_up_to:delimiter_pos]
                    if unsent.strip():
                        yield f"data: {json.dumps({'text': unsent})}\n\n"
                    sent_up_to = len(full_text)
                else:
                    # Buffer last BUFFER_SIZE chars to avoid sending
                    # a partial delimiter across chunk boundaries
                    safe_end = len(full_text) - BUFFER_SIZE
                    if safe_end > sent_up_to:
                        to_send = full_text[sent_up_to:safe_end]
                        yield f"data: {json.dumps({'text': to_send})}\n\n"
                        sent_up_to = safe_end
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
            return

        # Flush any remaining buffered passage text
        if not choices_detected:
            remaining = full_text[sent_up_to:]
            if remaining.strip():
                yield f"data: {json.dumps({'text': remaining})}\n\n"

        # ── Parse response ────────────────────────────────────────────
        try:
            narration_result = _parse_response(
                full_text,
                used_local=(NARRATIVE_BACKEND == "local"),
            )
        except CloudGMError as e:
            logging.warning(
                "Streaming narration parse failed; falling back to robust "
                "non-stream narration for turn %s: %s",
                turn_number, e,
            )
            try:
                narration_result = narrate_turn(ctx)
            except Exception as fallback_error:
                yield (
                    "event: error\ndata: "
                    f"{json.dumps({'error': str(fallback_error)})}\n\n"
                )
                return

        _post_narration_reputation_hook(
            turn_number, arc_state,
            dyn_fields_s["reputation_entries"], narration_result.passage,
        )
        _post_narration_drift_hook(
            turn_number=turn_number,
            arc_state=arc_state,
            character=character,
            drift_cue=dyn_fields_s["identity_drift_cue"],
            roll_result=roll_result,
            pinch_fired_this_turn=bool(dyn_fields_s["pinch_point_instruction"]),
        )
        arc_state["consecutive_no_check_turns"] = (
            0 if roll_result is not None
            else int(arc_state.get("consecutive_no_check_turns", 0) or 0) + 1
        )
        scene_thread_updates_s = _apply_narration_scene_state(
            arc_state=arc_state,
            current_act=current_act,
            npc_states=npc_states,
            narration_result=narration_result,
            player_action=player_action,
            scene_type=arc_state.get("scene_state", {}).get("scene_type", check_decision.scene_type),
            recent_turns=recent_turns,
            turn_number=turn_number,
            skill=check_decision.skill,
            ship_state=primary_ship_s,
        )

        # ── Step 7: Reconciliation (local model, fast tier with escalation) ─
        check_result_str = ""
        if roll_result:
            check_result_str = (
                f"{check_decision.skill} ({check_decision.difficulty}): "
                f"{roll_result.narrative_label()}"
            )

        recon_result, new_zero_delta_count, _escalated = _reconcile_turn_fast_or_full(
            session_id=session_id,
            turn_number=turn_number,
            prior_zero_delta_count=arc_state.get("consecutive_zero_delta_turns", 0),
            narration=narration_result.passage,
            player_action=player_action,
            check_result=check_result_str,
            active_npcs=scene_npcs_s,
            arc=ctx.arc,
            spine_act=current_act,
            spine=spine,
        )
        arc_state["consecutive_zero_delta_turns"] = new_zero_delta_count
        recon_result.thread_updates = _merge_thread_updates(
            recon_result.thread_updates, scene_thread_updates_s
        )

        _post_reconciliation_reputation_hook(session_id, turn_number, recon_result)
        _post_reconciliation_cs6_hook(
            arc_state,
            recon_result,
            turn_number=turn_number,
            foreshadow_instruction=dyn_fields_s.get("foreshadow_instruction", ""),
            spine=spine,
            character=character,
        )
        _post_turn_memorable_moments_hook(
            arc_state,
            turn_number,
            roll_result=roll_result,
            recon_result=recon_result,
            scene_npcs=scene_npcs_s,
            player_action=player_action,
            narration_passage=narration_result.passage,
            candidate_moments=dyn_fields_s.get("memorable_moments", []),
        )
        _post_turn_world_state_hook(
            arc_state,
            spine=spine,
            current_act=current_act,
            player_action=player_action,
            roll_result=roll_result,
            npc_states=scene_npcs_s,
            side_content_offered=bool(dyn_fields_s.get("side_content_block", "")),
            pivot_offered=bool(dyn_fields_s.get("pivot_warning_block", "")),
        )

        # ── Step 8: Apply state updates ───────────────────────────────
        apply_npc_updates(recon_result.npc_updates, npc_states)
        for npc in npc_states:
            save_npc_state(session_id, npc)

        arc_state["turns_this_act"] = arc_state.get("turns_this_act", 0) + 1
        apply_story_progress(recon_result.story_progress, arc_state, current_act)
        apply_thread_updates(recon_result.thread_updates, arc_state, current_act)

        # ── Step 9: Check act boundary ────────────────────────────────
        act_boundary_reached = detect_act_boundary(arc_state)

        # Phase 13: Wait for annotation thread (§24)
        if annotation_thread_s:
            annotation_thread_s.join(timeout=ANNOTATION_JOIN_TIMEOUT_SEC)
        choice_implications_json_s = annotation_result_stream[0]
        if act_boundary_reached:
            _clear_pending_social_offers(arc_state)
        else:
            _append_social_offers_to_narration(narration_result, spine, arc_state)

        # ── Step 10: Persist ──────────────────────────────────────────
        log_turn(
            session_id=session_id,
            turn_number=turn_number,
            player_action=player_action,
            choice_index=req.choice_index,
            narration=narration_result.passage,
            choices=narration_result.choices,
            check_skill=(check_decision.skill
                         if check_decision.requires_check else None),
            check_difficulty=(check_decision.difficulty
                              if check_decision.requires_check else None),
            dice_pool_json=(json.dumps(asdict(dice_pool))
                            if dice_pool else None),
            roll_result_json=(json.dumps(asdict(roll_result))
                              if roll_result else None),
            context_json=_context_audit_json(ctx),
            scene_type=arc_state.get("scene_state", {}).get("scene_type", check_decision.scene_type),
            moral_weight=check_decision.moral_weight,
            skill_tags_json=json.dumps(narration_result.skill_tags),
            choice_implications=choice_implications_json_s,
            force_result_json=(
                json.dumps(asdict(force_result)) if force_result else None
            ),
        )
        _finish_active_social_scene(arc_state)

        # Phase 24: track pattern-of-use for talent earned-through-use unlocks
        _track_pattern_use(
            character,
            arc_state.get("scene_state", {}).get("scene_type", check_decision.scene_type),
            check_decision.skill,
        )

        # ── Step 11: Update session state ─────────────────────────────
        update_session_state(session_id, character, arc_state)

        # ── Step 12: Background compression ───────────────────────────
        try:
            if should_compress(session_id):
                compress_act_turns(session_id, arc_state["current_act"])
        except Exception:
            pass

        # ── Step 13: Between-act processing ───────────────────────────
        milestone_data = None
        force_power_milestone_data = None
        time_skip_data = None
        if act_boundary_reached:
            try:
                pipeline_result = run_between_act_pipeline(
                    session_id, character, spine, arc_state["current_act"],
                )
                if pipeline_result.next_act_loaded:
                    with get_connection() as conn:
                        row = conn.execute(
                            "SELECT arc_state_json FROM sessions WHERE id = ?",
                            (session_id,),
                        ).fetchone()
                        if row:
                            # Mutate in place — reassignment breaks closure scoping
                            arc_state.clear()
                            arc_state.update(json.loads(row["arc_state_json"]))

                # Phase 12: Store pending milestone (§14.3)
                if pipeline_result.milestone_passage:
                    milestone_data = {
                        "passage": pipeline_result.milestone_passage,
                        "choices": pipeline_result.milestone_choices,
                    }
                    arc_state["pending_milestone"] = milestone_data

                # Phase 15: Store pending Force power milestone (§16.4)
                if pipeline_result.force_power_milestone_passage:
                    force_power_milestone_data = {
                        "passage": pipeline_result.force_power_milestone_passage,
                        "choices": pipeline_result.force_power_milestone_choices,
                    }
                    arc_state["pending_force_power_milestone"] = force_power_milestone_data

                # Phase 17: Store pending time skip (§19)
                if pipeline_result.time_skip_data:
                    time_skip_data = pipeline_result.time_skip_data
                    arc_state["pending_time_skip"] = time_skip_data

                if milestone_data or force_power_milestone_data or time_skip_data:
                    update_session_state(session_id, character, arc_state)
            except Exception as e:
                logging.error(f"Between-act pipeline failed: {e}")

        # ── Final event with turn data ────────────────────────────────
        payload = {
            "narration": narration_result.passage,
            "choices": narration_result.choices,
            "dice_result": (describe_pool_for_display(dice_pool)
                            if dice_pool else None),
            "roll_summary": (roll_result.narrative_label()
                             if roll_result else None),
            "session_state": {
                "turn_number": turn_number,
                "wounds": character.current_wounds,
                "strain": character.current_strain,
                "act_progress": arc_state.get("act_progress", 0.0),
                "anchor_proximity": arc_state.get("anchor_proximity", "distant"),
                "scene_state": arc_state.get("scene_state", {}),
            },
            "used_local_narration": narration_result.used_local,
            "act_boundary": act_boundary_reached,
        }
        if milestone_data:
            payload["milestone"] = milestone_data
        if force_power_milestone_data:
            payload["force_power_milestone"] = force_power_milestone_data
        if time_skip_data:
            payload["time_skip"] = {
                "opening_passage": time_skip_data["opening_passage"],
                "duration_months": time_skip_data["duration_months"],
                "framing": time_skip_data["framing"],
                "vignettes": time_skip_data["vignettes"],
                "current_vignette_index": 0,
            }
        yield f"event: done\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Phase 14: Dark Side Temptation endpoint (§16.2) ─────────────────────

@router.post("/session/{session_id}/temptation")
async def handle_temptation(
    session_id: str,
    req: TemptationRequest,
    background_tasks: BackgroundTasks,
):
    """
    Handle a player's response to a dark side temptation.
    Accept: Force succeeds using costly pips (Conflict + strain or just strain).
    Reject: Force fails, no cost.
    """
    from engine.force import ForceResolution

    session = get_session(session_id)
    if session is None:
        raise HTTPException(404, "Session not found")

    character = Character.model_validate_json(session["character_json"])
    arc_state = json.loads(session["arc_state_json"])

    pending = arc_state.get("pending_temptation")
    if not pending:
        raise HTTPException(400, "No pending temptation")

    spine = load_campaign_spine(session["campaign_name"])
    current_act = spine["acts"][arc_state["current_act"] - 1]

    # Rebuild state from pending
    dice_pool = DicePool(**pending["dice_pool"])
    roll_result = _rebuild_roll_result(pending["roll_result"])
    talent_activations = [
        _rebuild_talent_activation(a) for a in pending.get("talent_activations", [])
    ]

    # Rebuild ForceResolution from stored data
    res_data = pending["resolution"]
    resolution = ForceResolution(
        light_pips=res_data["light_pips"],
        dark_pips=res_data["dark_pips"],
        pips_required=res_data["pips_required"],
        is_dark_dominant=res_data["is_dark_dominant"],
        is_grey=res_data["is_grey"],
        pips_needed_from_costly_side=res_data["pips_needed_from_costly_side"],
        conflict_cost=res_data["conflict_cost"],
        strain_cost=res_data["strain_cost"],
        morality=character.motivation.morality,
    )

    # Apply temptation choice
    force_result = apply_temptation_choice(
        resolution, req.accept,
        force_power=pending.get("force_power", ""),
    )

    # Clear pending state
    del arc_state["pending_temptation"]

    # Apply mechanical effects
    effective_strain_threshold = character.strain_threshold
    if arc_state.get("obligation_active"):
        effective_strain_threshold = max(1, character.strain_threshold - 2)

    if force_result.conflict_earned:
        character.motivation.conflict += force_result.conflict_earned
    if force_result.strain_charged:
        character.current_strain = min(
            character.current_strain + force_result.strain_charged,
            effective_strain_threshold,
        )

    # Build Force context blocks for narration
    is_pure_force = pending.get("is_pure_force", False)
    _force_state_block = build_force_state_block(character)
    skill_succeeded = roll_result.succeeded if (not is_pure_force) else None
    _force_result_block = build_force_result_block(
        force_result, skill_succeeded, character.motivation.morality,
    )

    # Compute combat damage for the result
    combat_damage_note = ""
    check_skill = pending.get("check_skill")
    if check_skill and check_skill in COMBAT_SKILLS and roll_result.succeeded:
        weapon = get_weapon_for_skill(character.loadout, check_skill)
        if weapon:
            combat_damage_note = build_combat_damage_block(roll_result, weapon)

    # Apply mechanical consequences from dice
    if roll_result.outcome_quadrant in ("failure_threat", "success_threat"):
        if abs(roll_result.net_advantages) >= 2:
            character.current_strain = min(
                character.current_strain + 1,
                effective_strain_threshold,
            )

    # Assemble context and narrate (Steps 5-6)
    story_summary = get_act_summaries(session_id)
    npc_states = load_npc_states(session_id, spine)
    turn_number = _next_turn_number(session_id)
    recent_turns = get_recent_turns(session_id, limit=5)

    for npc in npc_states:
        npc.decay_emotion()
        npc.nudge_disposition_from_emotion()
    if check_skill:
        _apply_emotion_from_check(
            npc_states, check_skill,
            roll_result.outcome_quadrant, turn_number,
        )

    player_action = pending["player_action"]
    last_turn = get_most_recent_turn(session_id)
    scene_description = _build_scene_description(
        last_turn, player_action, arc_state, current_act
    )
    ships_t = load_ship_states(session_id)
    primary_ship_t = ships_t[0] if ships_t else None
    scene_type_t = _sanitize_scene_type(
        pending.get("scene_type", "social"),
        skill=check_skill,
        player_action=player_action,
        ship_state=primary_ship_t,
    )
    scene_state_t = _initial_scene_state(arc_state, current_act)
    scene_npcs_t = _select_active_scene_npcs(
        npc_states, arc_state, current_act, scene_description, player_action
    )

    anchor_inst = None
    if arc_state.get("act_progress", 0.0) >= 1.0:
        next_act_idx = arc_state["current_act"]
        next_act = (spine["acts"][next_act_idx]
                    if next_act_idx < spine["total_acts"] else None)
        anchor_inst = build_anchor_instruction(current_act, next_act)

    dyn_fields_t = _compute_dynamic_context_fields(
        session_id, turn_number, arc_state, current_act, scene_npcs_t, spine,
        character=character, roll_result=roll_result,
    )

    ctx = ContextPackage(
        character=character,
        arc=ArcState(
            campaign_name=spine["name"],
            current_act=arc_state["current_act"],
            total_acts=spine["total_acts"],
            act_name=current_act["name"],
            act_progress=arc_state.get("act_progress", 0.0),
            current_anchor=current_act["anchor"],
            next_anchor=current_act.get("next_anchor", ""),
            anchors_completed=arc_state.get("anchors_completed", []),
            throughline_question=spine["throughline_question"],
            tension_level=current_act["tension"],
            open_threads=_thread_states_for_context(current_act, arc_state),
            closed_threads=arc_state.get("closed_threads", []),
            turns_this_act=arc_state.get("turns_this_act", 0),
            anchor_proximity=arc_state.get("anchor_proximity", "distant"),
            anchor_description=current_act.get("anchor_description", ""),
            obligation_active=arc_state.get("obligation_active", False),
            obligation_type=arc_state.get("obligation_type", ""),
            duty_active=arc_state.get("duty_active", False),
            duty_type=arc_state.get("duty_type", ""),
            morality_label=arc_state.get("morality_label", ""),
            last_reputation_echo_turn=arc_state.get("last_reputation_echo_turn", 0),
        ),
        story_summary=story_summary,
        recent_turns=recent_turns,
        active_npcs=scene_npcs_t,
        location=scene_state_t.get("current_location", ""),
        situation=scene_description,
        galactic_context=current_act.get("galactic_context", ""),
        scene_type=scene_type_t,
        dice_pool=dice_pool,
        roll_result=roll_result,
        anchor_instruction=anchor_inst,
        expected_turns=current_act.get("expected_turns", [8, 12]),
        combat_damage_note=combat_damage_note,
        talent_activations=talent_activations,
        destiny_narrative_note=pending.get("destiny_narrative_note", ""),
        force_state_block=_force_state_block,
        force_result_block=_force_result_block,
        force_check_kind=(
            "pure" if force_result and is_pure_force
            else "enhanced" if force_result else ""
        ),
        ship_state_block=(
            primary_ship_t.to_narration_block() if primary_ship_t
            and scene_type_t == "space_combat" else ""
        ),
        **dyn_fields_t,
    )

    narration_result = narrate_turn(ctx)

    _post_narration_reputation_hook(
        turn_number, arc_state,
        dyn_fields_t["reputation_entries"], narration_result.passage,
    )
    _post_narration_drift_hook(
        turn_number=turn_number,
        arc_state=arc_state,
        character=character,
        drift_cue=dyn_fields_t["identity_drift_cue"],
        roll_result=roll_result,
        pinch_fired_this_turn=bool(dyn_fields_t["pinch_point_instruction"]),
    )
    arc_state["consecutive_no_check_turns"] = (
        0 if roll_result is not None
        else int(arc_state.get("consecutive_no_check_turns", 0) or 0) + 1
    )
    scene_thread_updates_t = _apply_narration_scene_state(
        arc_state=arc_state,
        current_act=current_act,
        npc_states=npc_states,
        narration_result=narration_result,
        player_action=player_action,
        scene_type=scene_type_t,
        recent_turns=recent_turns,
        turn_number=turn_number,
        skill=check_skill,
        ship_state=primary_ship_t,
    )

    # Reconciliation (fast tier with escalation)
    check_result_str = ""
    if check_skill:
        check_difficulty = pending.get("check_difficulty", "")
        check_result_str = (
            f"{check_skill} ({check_difficulty}): "
            f"{roll_result.narrative_label()}"
        )

    recon_result, new_zero_delta_count, _escalated = _reconcile_turn_fast_or_full(
        session_id=session_id,
        turn_number=turn_number,
        prior_zero_delta_count=arc_state.get("consecutive_zero_delta_turns", 0),
        narration=narration_result.passage,
        player_action=player_action,
        check_result=check_result_str,
        active_npcs=scene_npcs_t,
        arc=ctx.arc,
        spine_act=current_act,
        spine=spine,
    )
    arc_state["consecutive_zero_delta_turns"] = new_zero_delta_count
    recon_result.thread_updates = _merge_thread_updates(
        recon_result.thread_updates, scene_thread_updates_t
    )

    _post_reconciliation_reputation_hook(session_id, turn_number, recon_result)
    _post_reconciliation_cs6_hook(
        arc_state,
        recon_result,
        turn_number=turn_number,
        foreshadow_instruction=dyn_fields_t.get("foreshadow_instruction", ""),
        spine=spine,
        character=character,
    )
    _post_turn_memorable_moments_hook(
        arc_state,
        turn_number,
        roll_result=roll_result,
        recon_result=recon_result,
        scene_npcs=scene_npcs_t,
        player_action=player_action,
        narration_passage=narration_result.passage,
        candidate_moments=dyn_fields_t.get("memorable_moments", []),
    )
    _post_turn_world_state_hook(
        arc_state,
        spine=spine,
        current_act=current_act,
        player_action=player_action,
        roll_result=roll_result,
        npc_states=scene_npcs_t,
        side_content_offered=bool(dyn_fields_t.get("side_content_block", "")),
        pivot_offered=bool(dyn_fields_t.get("pivot_warning_block", "")),
    )

    apply_npc_updates(recon_result.npc_updates, npc_states)
    for npc in npc_states:
        save_npc_state(session_id, npc)

    arc_state["turns_this_act"] = arc_state.get("turns_this_act", 0) + 1
    apply_story_progress(recon_result.story_progress, arc_state, current_act)
    apply_thread_updates(recon_result.thread_updates, arc_state, current_act)

    act_boundary_reached = detect_act_boundary(arc_state)

    log_turn(
        session_id=session_id,
        turn_number=turn_number,
        player_action=player_action,
        choice_index=pending.get("choice_index", 0),
        narration=narration_result.passage,
        choices=narration_result.choices,
        check_skill=check_skill,
        check_difficulty=pending.get("check_difficulty"),
        dice_pool_json=json.dumps(asdict(dice_pool)),
        roll_result_json=json.dumps(asdict(roll_result)),
        context_json=_context_audit_json(ctx),
        scene_type=arc_state.get("scene_state", {}).get("scene_type", scene_type_t),
        moral_weight=pending.get("moral_weight", 0),
        skill_tags_json=json.dumps(narration_result.skill_tags),
        force_result_json=json.dumps(asdict(force_result)),
    )

    update_session_state(session_id, character, arc_state)

    background_tasks.add_task(
        compress_if_needed, session_id, arc_state["current_act"]
    )

    milestone_data = None
    force_power_milestone_data = None
    time_skip_data = None
    if act_boundary_reached:
        pipeline_result = run_between_act_pipeline(
            session_id, character, spine, arc_state["current_act"],
        )
        if pipeline_result.next_act_loaded:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT arc_state_json FROM sessions WHERE id = ?",
                    (session_id,),
                ).fetchone()
                if row:
                    arc_state = json.loads(row["arc_state_json"])

        if pipeline_result.milestone_passage:
            milestone_data = {
                "passage": pipeline_result.milestone_passage,
                "choices": pipeline_result.milestone_choices,
            }
            arc_state["pending_milestone"] = milestone_data

        if pipeline_result.force_power_milestone_passage:
            force_power_milestone_data = {
                "passage": pipeline_result.force_power_milestone_passage,
                "choices": pipeline_result.force_power_milestone_choices,
            }
            arc_state["pending_force_power_milestone"] = force_power_milestone_data

        if pipeline_result.time_skip_data:
            time_skip_data = pipeline_result.time_skip_data
            arc_state["pending_time_skip"] = time_skip_data

        if milestone_data or force_power_milestone_data or time_skip_data:
            update_session_state(session_id, character, arc_state)

    response = {
        "narration": narration_result.passage,
        "choices": narration_result.choices,
        "dice_result": describe_pool_for_display(dice_pool),
        "roll_summary": roll_result.narrative_label() if not is_pure_force else None,
        "temptation_accepted": req.accept,
        "force_result": {
            "force_succeeded": force_result.force_succeeded,
            "conflict_earned": force_result.conflict_earned,
            "strain_charged": force_result.strain_charged,
        },
        "session_state": {
            "turn_number": turn_number,
            "wounds": character.current_wounds,
            "strain": character.current_strain,
            "act_progress": arc_state.get("act_progress", 0.0),
            "anchor_proximity": arc_state.get("anchor_proximity", "distant"),
            "scene_state": arc_state.get("scene_state", {}),
        },
        "used_local_narration": narration_result.used_local,
        "act_boundary": act_boundary_reached,
    }
    if milestone_data:
        response["milestone"] = milestone_data
    if force_power_milestone_data:
        response["force_power_milestone"] = force_power_milestone_data
    if time_skip_data:
        response["time_skip"] = {
            "opening_passage": time_skip_data["opening_passage"],
            "duration_months": time_skip_data["duration_months"],
            "framing": time_skip_data["framing"],
            "vignettes": time_skip_data["vignettes"],
            "current_vignette_index": 0,
        }
    return response


# ── Phase 12: Intervention endpoint (§15.1) ────────────────────────────

@router.post("/session/{session_id}/intervention")
async def handle_intervention(
    session_id: str,
    req: InterventionRequest,
    background_tasks: BackgroundTasks,
):
    """
    Handle a player's response to an intervention offer.
    Accept: reroll dice, charge strain, narrate with new result.
    Decline: narrate with original result, clear pending state.
    """
    session = get_session(session_id)
    if session is None:
        raise HTTPException(404, "Session not found")

    character = Character.model_validate_json(session["character_json"])
    arc_state = json.loads(session["arc_state_json"])

    pending = arc_state.get("pending_intervention")
    if not pending:
        raise HTTPException(400, "No pending intervention")

    spine = load_campaign_spine(session["campaign_name"])
    current_act = spine["acts"][arc_state["current_act"] - 1]

    # Rebuild dice pool and roll result from pending state
    dice_pool = DicePool(**pending["dice_pool"])
    roll_result = _rebuild_roll_result(pending["roll_result"])

    talent_activations = [
        _rebuild_talent_activation(a) for a in pending.get("talent_activations", [])
    ]

    if req.accept:
        # Apply intervention: charge strain, mark used, reroll
        from engine.talents import InterventionOffer
        offer = InterventionOffer(
            talent_ref=pending["talent_ref"],
            talent_name=pending["talent_name"],
            effect="reroll",
            applicable_skills=[pending["check_skill"]],
            strain_cost=pending["strain_cost"],
            scope="session",
            narrative_prompt=pending["narrative_prompt"],
        )
        activation = apply_intervention(character, offer)
        talent_activations.append(activation)

        # Reroll the dice pool
        roll_result = roll_pool(dice_pool)

    # Clear pending state
    del arc_state["pending_intervention"]

    # Compute combat damage for new result
    combat_damage_note = ""
    if (pending["check_skill"] in COMBAT_SKILLS and roll_result.succeeded):
        weapon = get_weapon_for_skill(character.loadout, pending["check_skill"])
        if weapon:
            combat_damage_note = build_combat_damage_block(roll_result, weapon)

    # Apply mechanical consequences
    effective_strain_threshold = character.strain_threshold
    if arc_state.get("obligation_active"):
        effective_strain_threshold = max(1, character.strain_threshold - 2)
    if roll_result.outcome_quadrant in ("failure_threat", "success_threat"):
        if abs(roll_result.net_advantages) >= 2:
            character.current_strain = min(
                character.current_strain + 1,
                effective_strain_threshold,
            )

    # Assemble context and narrate (Steps 5-6)
    story_summary = get_act_summaries(session_id)
    npc_states = load_npc_states(session_id, spine)
    turn_number = _next_turn_number(session_id)
    recent_turns = get_recent_turns(session_id, limit=5)

    for npc in npc_states:
        npc.decay_emotion()
        npc.nudge_disposition_from_emotion()
    _apply_emotion_from_check(
        npc_states, pending["check_skill"],
        roll_result.outcome_quadrant, turn_number,
    )

    player_action = pending["player_action"]
    last_turn = get_most_recent_turn(session_id)
    scene_description = _build_scene_description(
        last_turn, player_action, arc_state, current_act
    )
    ships_iv = load_ship_states(session_id)
    primary_ship_iv = ships_iv[0] if ships_iv else None
    scene_type_iv = _sanitize_scene_type(
        pending["scene_type"],
        skill=pending["check_skill"],
        player_action=player_action,
        ship_state=primary_ship_iv,
    )
    scene_state_iv = _initial_scene_state(arc_state, current_act)
    scene_npcs_iv = _select_active_scene_npcs(
        npc_states, arc_state, current_act, scene_description, player_action
    )

    anchor_inst = None
    if arc_state.get("act_progress", 0.0) >= 1.0:
        next_act_idx = arc_state["current_act"]
        next_act = (spine["acts"][next_act_idx]
                    if next_act_idx < spine["total_acts"] else None)
        anchor_inst = build_anchor_instruction(current_act, next_act)

    dyn_fields_iv = _compute_dynamic_context_fields(
        session_id, turn_number, arc_state, current_act, scene_npcs_iv, spine,
        character=character, roll_result=roll_result,
    )

    ctx = ContextPackage(
        character=character,
        arc=ArcState(
            campaign_name=spine["name"],
            current_act=arc_state["current_act"],
            total_acts=spine["total_acts"],
            act_name=current_act["name"],
            act_progress=arc_state.get("act_progress", 0.0),
            current_anchor=current_act["anchor"],
            next_anchor=current_act.get("next_anchor", ""),
            anchors_completed=arc_state.get("anchors_completed", []),
            throughline_question=spine["throughline_question"],
            tension_level=current_act["tension"],
            open_threads=_thread_states_for_context(current_act, arc_state),
            closed_threads=arc_state.get("closed_threads", []),
            turns_this_act=arc_state.get("turns_this_act", 0),
            anchor_proximity=arc_state.get("anchor_proximity", "distant"),
            anchor_description=current_act.get("anchor_description", ""),
            obligation_active=arc_state.get("obligation_active", False),
            obligation_type=arc_state.get("obligation_type", ""),
            duty_active=arc_state.get("duty_active", False),
            duty_type=arc_state.get("duty_type", ""),
            morality_label=arc_state.get("morality_label", ""),
            last_reputation_echo_turn=arc_state.get("last_reputation_echo_turn", 0),
        ),
        story_summary=story_summary,
        recent_turns=recent_turns,
        active_npcs=scene_npcs_iv,
        location=scene_state_iv.get("current_location", ""),
        situation=scene_description,
        galactic_context=current_act.get("galactic_context", ""),
        scene_type=scene_type_iv,
        dice_pool=dice_pool,
        roll_result=roll_result,
        anchor_instruction=anchor_inst,
        expected_turns=current_act.get("expected_turns", [8, 12]),
        combat_damage_note=combat_damage_note,
        talent_activations=talent_activations,
        destiny_narrative_note=pending.get("destiny_narrative_note", ""),
        ship_state_block=(
            primary_ship_iv.to_narration_block() if primary_ship_iv
            and scene_type_iv == "space_combat" else ""
        ),
        **dyn_fields_iv,
    )

    narration_result = narrate_turn(ctx)

    _post_narration_reputation_hook(
        turn_number, arc_state,
        dyn_fields_iv["reputation_entries"], narration_result.passage,
    )
    _post_narration_drift_hook(
        turn_number=turn_number,
        arc_state=arc_state,
        character=character,
        drift_cue=dyn_fields_iv["identity_drift_cue"],
        roll_result=roll_result,
        pinch_fired_this_turn=bool(dyn_fields_iv["pinch_point_instruction"]),
    )
    arc_state["consecutive_no_check_turns"] = (
        0 if roll_result is not None
        else int(arc_state.get("consecutive_no_check_turns", 0) or 0) + 1
    )
    scene_thread_updates_iv = _apply_narration_scene_state(
        arc_state=arc_state,
        current_act=current_act,
        npc_states=npc_states,
        narration_result=narration_result,
        player_action=player_action,
        scene_type=scene_type_iv,
        recent_turns=recent_turns,
        turn_number=turn_number,
        skill=pending["check_skill"],
        ship_state=primary_ship_iv,
    )

    # Reconciliation (fast tier with escalation)
    check_result_str = (
        f"{pending['check_skill']} ({pending['check_difficulty']}): "
        f"{roll_result.narrative_label()}"
    )
    recon_result, new_zero_delta_count, _escalated = _reconcile_turn_fast_or_full(
        session_id=session_id,
        turn_number=turn_number,
        prior_zero_delta_count=arc_state.get("consecutive_zero_delta_turns", 0),
        narration=narration_result.passage,
        player_action=player_action,
        check_result=check_result_str,
        active_npcs=scene_npcs_iv,
        arc=ctx.arc,
        spine_act=current_act,
        spine=spine,
    )
    arc_state["consecutive_zero_delta_turns"] = new_zero_delta_count
    recon_result.thread_updates = _merge_thread_updates(
        recon_result.thread_updates, scene_thread_updates_iv
    )

    _post_reconciliation_reputation_hook(session_id, turn_number, recon_result)
    _post_reconciliation_cs6_hook(
        arc_state,
        recon_result,
        turn_number=turn_number,
        foreshadow_instruction=dyn_fields_iv.get("foreshadow_instruction", ""),
        spine=spine,
        character=character,
    )
    _post_turn_memorable_moments_hook(
        arc_state,
        turn_number,
        roll_result=roll_result,
        recon_result=recon_result,
        scene_npcs=scene_npcs_iv,
        player_action=player_action,
        narration_passage=narration_result.passage,
        candidate_moments=dyn_fields_iv.get("memorable_moments", []),
    )
    _post_turn_world_state_hook(
        arc_state,
        spine=spine,
        current_act=current_act,
        player_action=player_action,
        roll_result=roll_result,
        npc_states=scene_npcs_iv,
        side_content_offered=bool(dyn_fields_iv.get("side_content_block", "")),
        pivot_offered=bool(dyn_fields_iv.get("pivot_warning_block", "")),
    )

    apply_npc_updates(recon_result.npc_updates, npc_states)
    for npc in npc_states:
        save_npc_state(session_id, npc)

    arc_state["turns_this_act"] = arc_state.get("turns_this_act", 0) + 1
    apply_story_progress(recon_result.story_progress, arc_state, current_act)
    apply_thread_updates(recon_result.thread_updates, arc_state, current_act)

    act_boundary_reached = detect_act_boundary(arc_state)

    log_turn(
        session_id=session_id,
        turn_number=turn_number,
        player_action=player_action,
        choice_index=pending["choice_index"],
        narration=narration_result.passage,
        choices=narration_result.choices,
        check_skill=pending["check_skill"],
        check_difficulty=pending["check_difficulty"],
        dice_pool_json=json.dumps(asdict(dice_pool)),
        roll_result_json=json.dumps(asdict(roll_result)),
        context_json=_context_audit_json(ctx),
        scene_type=arc_state.get("scene_state", {}).get("scene_type", scene_type_iv),
        moral_weight=pending["moral_weight"],
        skill_tags_json=json.dumps(narration_result.skill_tags),
    )

    update_session_state(session_id, character, arc_state)

    background_tasks.add_task(
        compress_if_needed, session_id, arc_state["current_act"]
    )

    milestone_data = None
    force_power_milestone_data = None
    time_skip_data = None
    if act_boundary_reached:
        pipeline_result = run_between_act_pipeline(
            session_id, character, spine, arc_state["current_act"],
        )
        if pipeline_result.next_act_loaded:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT arc_state_json FROM sessions WHERE id = ?",
                    (session_id,),
                ).fetchone()
                if row:
                    arc_state = json.loads(row["arc_state_json"])
        if pipeline_result.milestone_passage:
            milestone_data = {
                "passage": pipeline_result.milestone_passage,
                "choices": pipeline_result.milestone_choices,
            }
            arc_state["pending_milestone"] = milestone_data

        if pipeline_result.force_power_milestone_passage:
            force_power_milestone_data = {
                "passage": pipeline_result.force_power_milestone_passage,
                "choices": pipeline_result.force_power_milestone_choices,
            }
            arc_state["pending_force_power_milestone"] = force_power_milestone_data

        if pipeline_result.time_skip_data:
            time_skip_data = pipeline_result.time_skip_data
            arc_state["pending_time_skip"] = time_skip_data

        if milestone_data or force_power_milestone_data or time_skip_data:
            update_session_state(session_id, character, arc_state)

    response = {
        "narration": narration_result.passage,
        "choices": narration_result.choices,
        "dice_result": describe_pool_for_display(dice_pool),
        "roll_summary": roll_result.narrative_label(),
        "intervention_used": req.accept,
        "session_state": {
            "turn_number": turn_number,
            "wounds": character.current_wounds,
            "strain": character.current_strain,
            "act_progress": arc_state.get("act_progress", 0.0),
            "anchor_proximity": arc_state.get("anchor_proximity", "distant"),
            "scene_state": arc_state.get("scene_state", {}),
        },
        "act_boundary": act_boundary_reached,
    }
    if milestone_data:
        response["milestone"] = milestone_data
    if force_power_milestone_data:
        response["force_power_milestone"] = force_power_milestone_data
    if time_skip_data:
        response["time_skip"] = {
            "opening_passage": time_skip_data["opening_passage"],
            "duration_months": time_skip_data["duration_months"],
            "framing": time_skip_data["framing"],
            "vignettes": time_skip_data["vignettes"],
            "current_vignette_index": 0,
        }
    return response


# ── Phase 12: Milestone endpoint (§14.3) ───────────────────────────────

@router.post("/session/{session_id}/milestone")
async def handle_milestone(session_id: str, req: MilestoneRequest):
    """
    Handle a player's milestone talent selection at an act boundary.
    Acquires the selected talent, deducts reserved XP, persists character.
    """
    session = get_session(session_id)
    if session is None:
        raise HTTPException(404, "Session not found")

    character = Character.model_validate_json(session["character_json"])
    arc_state = json.loads(session["arc_state_json"])

    pending = arc_state.get("pending_milestone")
    if not pending:
        raise HTTPException(400, "No pending milestone")

    choices = pending.get("choices", [])
    if req.choice_index < 0 or req.choice_index >= len(choices):
        raise HTTPException(400, f"Invalid choice_index: {req.choice_index}")

    selected = choices[req.choice_index]
    talent_ref = selected.get("talent_ref", "")

    # Rebuild MilestoneChoice from stored data and library
    spine = load_campaign_spine(session["campaign_name"])
    milestone_choices = build_milestone_choices(
        character, character.reserved_xp,
    )

    # Find the matching MilestoneChoice
    matching = None
    for mc in milestone_choices:
        if mc.talent_ref == talent_ref:
            matching = mc
            break

    if not matching:
        raise HTTPException(400, f"Talent {talent_ref} not available for acquisition")

    # Acquire the talent
    acquire_talent(character, matching)

    # Clear pending milestone
    del arc_state["pending_milestone"]

    # Persist
    update_session_state(session_id, character, arc_state)

    return {
        "acquired": {
            "talent_ref": matching.talent_ref,
            "talent_name": matching.talent_name,
            "branch_theme": matching.branch_theme,
            "xp_cost": matching.xp_cost,
        },
        "character_state": {
            "reserved_xp": character.reserved_xp,
            "acquired_talents": character.acquired_talents,
            "wound_threshold": character.wound_threshold,
            "strain_threshold": character.strain_threshold,
        },
    }


@router.post("/session/{session_id}/force_power_milestone")
async def handle_force_power_milestone(session_id: str, req: ForcePowerMilestoneRequest):
    """
    Handle a player's Force power upgrade selection at an act boundary.
    Applies the selected upgrade, deducts reserved XP, persists character.
    """
    session = get_session(session_id)
    if session is None:
        raise HTTPException(404, "Session not found")

    character = Character.model_validate_json(session["character_json"])
    arc_state = json.loads(session["arc_state_json"])

    pending = arc_state.get("pending_force_power_milestone")
    if not pending:
        raise HTTPException(400, "No pending Force power milestone")

    choices = pending.get("choices", [])
    if req.choice_index < 0 or req.choice_index >= len(choices):
        raise HTTPException(400, f"Invalid choice_index: {req.choice_index}")

    selected = choices[req.choice_index]
    power_id = selected.get("power_id", "")
    upgrade_id = selected.get("upgrade_id", "")

    # Rebuild ForcePowerMilestoneChoice from stored data
    available = build_force_power_milestone_choices(
        character, character.reserved_xp,
    )

    matching = None
    for fmc in available:
        if fmc.power_id == power_id and fmc.upgrade_id == upgrade_id:
            matching = fmc
            break

    if not matching:
        raise HTTPException(
            400,
            f"Force power upgrade {power_id}:{upgrade_id} not available",
        )

    # Apply the upgrade
    apply_force_power_upgrade(character, matching)

    # Clear pending
    del arc_state["pending_force_power_milestone"]

    # Persist
    update_session_state(session_id, character, arc_state)

    return {
        "acquired": {
            "power_id": matching.power_id,
            "power_name": matching.power_name,
            "upgrade_id": matching.upgrade_id,
            "upgrade_name": matching.upgrade_name,
            "upgrade_type": matching.upgrade_type,
            "xp_cost": matching.xp_cost,
        },
        "character_state": {
            "reserved_xp": character.reserved_xp,
            "force_powers": character.force_powers,
        },
    }


@router.post("/session/{session_id}/commitment")
async def handle_commitment(session_id: str, req: CommitmentRequest):
    """
    Commit or release a Force die for a sustained power effect.
    """
    session = get_session(session_id)
    if session is None:
        raise HTTPException(404, "Session not found")

    character = Character.model_validate_json(session["character_json"])
    arc_state = json.loads(session["arc_state_json"])
    turn_number = arc_state.get("turn_number", 0)

    if req.release:
        success = release_commitment(character, req.power_id)
        if not success:
            raise HTTPException(
                400,
                f"No active commitment for power '{req.power_id}' to release",
            )
        action = "released"
    else:
        # Validate the character has the power and the upgrade is sustained
        if not character_has_power(character, req.power_id):
            raise HTTPException(400, f"Character does not have power '{req.power_id}'")

        success = commit_force_die(
            character, req.power_id, req.upgrade_id, turn_number,
        )
        if not success:
            raise HTTPException(
                400,
                "Cannot commit Force die — no available dice or already committed",
            )
        action = "committed"

    # Persist
    update_session_state(session_id, character, arc_state)

    return {
        "action": action,
        "power_id": req.power_id,
        "upgrade_id": req.upgrade_id,
        "force_committed": character.force_committed,
        "force_available": get_available_force_dice(character),
        "active_commitments": character.active_commitments,
    }


def _rebuild_roll_result(data: dict):
    """Rebuild a RollResult from serialized dict."""
    from engine.dice import RollResult
    return RollResult(**data)


def _rebuild_talent_activation(data: dict):
    """Rebuild a TalentActivation from serialized dict."""
    from engine.talents import TalentActivation
    return TalentActivation(**data)


# ── Phase 17: Vignette choice endpoint (§19.3) ──────────────────────────

@router.post("/session/{session_id}/vignette")
async def handle_vignette(session_id: str, req: VignetteRequest):
    """
    Handle a player's vignette choice during a time skip.

    Each call resolves one vignette choice, applies its effects, and either
    returns the next vignette or generates the closing passage if all
    vignettes are complete.
    """
    from engine.time_skip import (
        deserialize_time_skip_state,
        process_vignette_choice,
        aggregate_vignette_effects,
        apply_vignette_npc_effects,
        build_vignette_inference_rows,
        serialize_time_skip_state,
    )
    from gm.cloud_gm import generate_time_skip_closing

    session = get_session(session_id)
    if session is None:
        raise HTTPException(404, "Session not found")

    character = Character.model_validate_json(session["character_json"])
    arc_state = json.loads(session["arc_state_json"])

    pending = arc_state.get("pending_time_skip")
    if not pending:
        raise HTTPException(400, "No pending time skip")

    # Restore time skip state
    vignettes, effects, current_index = deserialize_time_skip_state(
        pending.get("state", pending)
    )

    if current_index >= len(vignettes):
        raise HTTPException(400, "All vignettes already completed")

    current_vignette = vignettes[current_index]

    # Validate choice
    if req.choice_index < 0 or req.choice_index >= len(current_vignette.choices):
        raise HTTPException(
            400,
            f"Invalid choice_index {req.choice_index} for vignette "
            f"with {len(current_vignette.choices)} choices",
        )

    # Process the choice
    effect = process_vignette_choice(current_vignette, req.choice_index)
    effects.append(effect)

    # Advance to next vignette
    next_index = current_index + 1
    is_complete = next_index >= len(vignettes)

    # Build response
    response = {
        "vignette_id": current_vignette.vignette_id,
        "choice_index": req.choice_index,
        "narrative_consequence": effect.narrative_consequence,
        "is_complete": is_complete,
    }

    if is_complete:
        # All vignettes done — apply accumulated effects and generate closing
        aggregated = aggregate_vignette_effects(effects)

        # Apply NPC disposition changes
        spine = load_campaign_spine(session["campaign_name"])
        npc_states = load_npc_states(session_id, spine)
        apply_vignette_npc_effects(aggregated["npc_effects"], npc_states)
        for npc in npc_states:
            save_npc_state(session_id, npc)

        # Add conflict to character's morality tracking
        character.motivation.conflict += aggregated["total_conflict"]

        # Add morality bonus
        character.motivation.morality = min(
            100, character.motivation.morality + aggregated["total_morality_bonus"]
        )

        # Generate closing passage
        closing_passage = ""
        try:
            next_act_number = arc_state.get("current_act", 1)
            next_act = spine["acts"][next_act_number - 1] if next_act_number <= spine.get("total_acts", 4) else {}

            vignette_summary = "\n".join(
                f"- {e.narrative_consequence}" for e in effects
            )
            closing_passage = generate_time_skip_closing(
                character=character,
                duration_months=pending.get("duration_months", pending.get("state", {}).get("duration_months", 1)),
                campaign_name=spine.get("name", ""),
                vignette_summary=vignette_summary,
                next_act_situation=next_act.get("opening_situation", ""),
            )
        except Exception as e:
            logging.error(f"Time skip closing generation failed: {e}")

        response["closing_passage"] = closing_passage
        response["effects_summary"] = {
            "skill_tags": aggregated["skill_tags"],
            "npc_effects": aggregated["npc_effects"],
            "total_conflict": aggregated["total_conflict"],
            "total_morality_bonus": aggregated["total_morality_bonus"],
        }

        # Clear pending time skip
        del arc_state["pending_time_skip"]
    else:
        # Return next vignette
        from engine.time_skip import serialize_vignette
        next_v = vignettes[next_index]
        response["next_vignette"] = serialize_vignette(next_v)

        # Update stored state
        config_data = pending.get("state", pending)
        from engine.time_skip import TimeSkipConfig, Vignette as _V
        # Rebuild a minimal config for serialization
        updated_state = serialize_time_skip_state(
            TimeSkipConfig(
                duration_months=config_data.get("duration_months", 1),
                framing=config_data.get("framing", ""),
                vignettes=[],  # not needed — we use all_vignettes
            ),
            vignettes, effects, next_index,
        )
        pending["state"] = updated_state
        arc_state["pending_time_skip"] = pending

    # Persist
    update_session_state(session_id, character, arc_state)

    return response
