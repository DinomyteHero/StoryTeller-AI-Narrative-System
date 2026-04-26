"""
Post-turn state reconciliation — Game Mechanics §26.

After the cloud GM produces narration, the local model analyzes what happened
and produces structured state updates: NPC knowledge/disposition changes, story
progression, thread updates, anchor proximity detection.

The between-act pipeline runs when an act boundary is detected.
"""

import json
import logging
import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from gm.context import ArcState, NPCState, ThreadState
from gm.llm_client import TIER_FAST, TIER_QUALITY, call_chat, call_chat_json

PROMPT_PATH = Path(__file__).resolve().parent.parent / "gm" / "prompts" / "reconciliation.txt"
RECONCILIATION_TIMEOUT_SEC = float(os.getenv("RECONCILIATION_TIMEOUT_SEC", "25"))
RECONCILIATION_MAX_TOKENS = int(os.getenv("RECONCILIATION_MAX_TOKENS", "800"))
RECONCILIATION_RETRIES = int(os.getenv("RECONCILIATION_RETRIES", "1"))

# JSON schema for structured output from the fast LLM tier
RECONCILIATION_SCHEMA = {
    "type": "object",
    "properties": {
        "npc_updates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "npc_name": {"type": "string"},
                    "knowledge_gained": {"type": "array", "items": {"type": "string"}},
                    "knowledge_lost": {"type": "array", "items": {"type": "string"}},
                    "disposition_shift": {"type": "number"},
                    "emotional_state": {"type": "string"},
                },
                "required": ["npc_name"],
            },
        },
        "thread_updates": {
            "type": "object",
            "properties": {
                "threads_advanced": {"type": "array", "items": {"type": "string"}},
                "threads_resolved": {"type": "array", "items": {"type": "string"}},
                "threads_opened": {"type": "array", "items": {"type": "string"}},
            },
        },
        "story_progress": {
            "type": "object",
            "properties": {
                "anchor_proximity": {
                    "type": "string",
                    "enum": ["distant", "approaching", "imminent", "reached"],
                },
                "progress_delta": {"type": "number"},
                "reasoning": {"type": "string"},
            },
            "required": ["anchor_proximity", "progress_delta"],
        },
        "reputation_event": {
            "type": ["string", "null"],
            "description": "One-sentence summary of a publicly-visible "
                           "notable action this turn, or null. Most turns: null.",
        },
        "faction_tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Faction/location identifiers determining where "
                           "the reputation event travels.",
        },
        "contradiction_tracking": {
            "type": "object",
            "properties": {
                "contradiction_engaged": {
                    "type": "boolean",
                    "description": "Was the protagonist's core contradiction relevant to this turn?",
                },
                "arc_movement": {
                    "type": "string",
                    "enum": ["reinforced", "resisted", "transformed", "cost_paid", "none"],
                    "description": "How did the character relate to their contradiction?",
                },
                "arc_evidence": {
                    "type": "string",
                    "description": "One sentence: what specific action or choice showed this?",
                },
            },
            "required": ["contradiction_engaged"],
        },
        "dramatic_mission": {
            "type": "object",
            "properties": {
                "selected_mission": {
                    "type": "string",
                    "enum": [
                        "stake_setup", "world_normal", "foreshadow",
                        "response", "false_progress", "antagonist_pressure",
                        "attack", "inner_demon_test", "midpoint_reframe",
                        "collapse", "climactic_execution", "aftermath",
                        "character_reveal", "thread_advance",
                    ],
                },
                "mission_sentence": {
                    "type": "string",
                    "description": "One sentence describing this turn's specific narrative job",
                },
            },
            "required": ["selected_mission", "mission_sentence"],
        },
    },
    "required": ["npc_updates", "thread_updates", "story_progress"],
}


@dataclass
class ReconciliationResult:
    """Structured output from the reconciliation step."""
    npc_updates: list[dict] = field(default_factory=list)
    thread_updates: dict = field(default_factory=lambda: {
        "threads_advanced": [], "threads_resolved": [], "threads_opened": [],
    })
    story_progress: dict = field(default_factory=lambda: {
        "anchor_proximity": "distant", "progress_delta": 0.05, "reasoning": "",
    })
    dramatic_mission: dict = field(default_factory=lambda: {
        "selected_mission": "", "mission_sentence": "",
    })
    contradiction_tracking: dict = field(default_factory=lambda: {
        "contradiction_engaged": False, "arc_movement": "none", "arc_evidence": "",
    })
    # Reputation echo system (Game Mechanics §1, §11). Most turns: empty.
    # Caller (api/game_routes.py) writes to reputation_log when present.
    reputation_event: Optional[str] = None
    faction_tags: list[str] = field(default_factory=list)


@dataclass
class BetweenActResult:
    """Output from the between-act processing pipeline."""
    act_summary: str = ""
    character_drift_note: str = ""
    strain_recovered: int = 0
    wounds_recovered: int = 0
    next_act_loaded: bool = False
    obligation_result: dict = field(default_factory=dict)   # Phase 8: activation roll output
    morality_result: dict = field(default_factory=dict)     # Phase 8: morality resolution output
    xp_award: Optional[object] = None                       # Phase 10: XPAward dataclass (§14.1)
    advancement: Optional[dict] = None                      # Phase 10: skill rank increase entry (§14.2)
    milestone_passage: str = ""                             # Phase 12: reflection prose (§14.3)
    milestone_choices: list = field(default_factory=list)    # Phase 12: list of choice dicts for API
    force_power_milestone_passage: str = ""                  # Phase 15: Force power upgrade reflection (§16.4)
    force_power_milestone_choices: list = field(default_factory=list)  # Phase 15: Force power upgrade choices
    behavioral_fingerprint: Optional[dict] = None            # Phase 13: aggregated choice annotations (§24)
    time_skip_data: Optional[dict] = None                    # Phase 17: time skip config for API (§19)
    steps_completed: list[str] = field(default_factory=list)


def is_silent_reconciliation(recon: ReconciliationResult) -> bool:
    """Detect a silent reconciliation result — one that the local model
    returned but provided no actionable signal: no NPC updates, no thread
    movement, no reputation event.

    Used by the selective escalation pathway. Distinct from
    `count_state_deltas` because the default `progress_delta=0.05` would
    otherwise mask a no-op result as a one-delta turn. Two consecutive
    silent results suggest the local model has stopped reading the prompt;
    we then rerun through the quality tier.
    """
    if recon.npc_updates:
        return False
    tu = recon.thread_updates or {}
    if any(tu.get(k) for k in ("threads_advanced", "threads_resolved", "threads_opened")):
        return False
    if recon.reputation_event:
        return False
    return True


def count_state_deltas(recon: ReconciliationResult) -> dict:
    """Count meaningful state changes from a reconciliation result.

    Returns a dict summarizing what changed this turn. Used by the
    consequence contract and narrative telemetry.
    """
    deltas = {
        "npc_shifts": 0,
        "npc_knowledge_changes": 0,
        "threads_advanced": 0,
        "threads_resolved": 0,
        "threads_opened": 0,
        "progress_delta": 0.0,
        "total_changes": 0,
    }

    for npc in recon.npc_updates:
        shift = abs(npc.get("disposition_shift", 0))
        knowledge = len(npc.get("knowledge_gained", [])) + len(npc.get("knowledge_lost", []))
        emotion = 1 if npc.get("emotional_state") else 0
        if shift > 0:
            deltas["npc_shifts"] += 1
        deltas["npc_knowledge_changes"] += knowledge
        deltas["total_changes"] += (1 if shift > 0 else 0) + knowledge + emotion

    tu = recon.thread_updates
    deltas["threads_advanced"] = len(tu.get("threads_advanced", []))
    deltas["threads_resolved"] = len(tu.get("threads_resolved", []))
    deltas["threads_opened"] = len(tu.get("threads_opened", []))
    deltas["total_changes"] += (
        deltas["threads_advanced"] + deltas["threads_resolved"] + deltas["threads_opened"]
    )

    sp = recon.story_progress
    deltas["progress_delta"] = sp.get("progress_delta", 0.0)
    if deltas["progress_delta"] > 0:
        deltas["total_changes"] += 1

    return deltas


def morality_label(morality: int) -> str:
    """Return the GM prompt label for the current Morality value (§9)."""
    if morality >= 71:
        return ("Light side dominant — moments of calm, instinctive compassion, "
                "the Force responds gently")
    elif morality >= 41:
        return ("Grey — conflicted, the Force is present but uncertain, "
                "both impulses are real")
    else:
        return ("Dark side dominant — anger is efficient, the Force responds "
                "to demand, compassion feels like weakness")


def roll_obligation_duty(character) -> dict:
    """
    Roll d100 for Obligation/Duty activation at an act boundary (§9).
    Returns dict with activation flags to merge into arc_state.
    """
    result = {}
    motivation = character.motivation

    # Obligation (Edge of the Empire)
    if motivation.obligation_type and motivation.obligation_value > 0:
        roll = random.randint(1, 100)
        activated = roll <= motivation.obligation_value
        result["obligation_active"] = activated
        result["obligation_type"] = motivation.obligation_type
        logging.info(
            f"Obligation roll: {roll} vs {motivation.obligation_value} "
            f"({motivation.obligation_type}) — {'ACTIVATED' if activated else 'inactive'}"
        )

    # Duty (Age of Rebellion)
    if motivation.duty_type and motivation.duty_value > 0:
        roll = random.randint(1, 100)
        activated = roll <= motivation.duty_value
        result["duty_active"] = activated
        result["duty_type"] = motivation.duty_type
        logging.info(
            f"Duty roll: {roll} vs {motivation.duty_value} "
            f"({motivation.duty_type}) — {'ACTIVATED' if activated else 'inactive'}"
        )

    # Morality label (always present if morality is tracked)
    result["morality_label"] = morality_label(motivation.morality)

    return result


def resolve_morality(session_id: str, character, completed_act_number: int) -> dict:
    """
    End-of-act Morality resolution (§9).
    Sums moral_weight across the act's turns as Conflict, rolls 1d10,
    adjusts Morality on the character. Returns summary dict.
    """
    from state.db import get_connection

    # Sum moral_weight for turns in this act
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(moral_weight), 0) FROM turns "
            "WHERE session_id = ? AND moral_weight > 0",
            (session_id,),
        ).fetchone()
        conflict_earned = row[0] if row else 0

    # Add any existing conflict on the character
    total_conflict = conflict_earned + character.motivation.conflict

    # Roll 1d10
    roll = random.randint(1, 10)

    old_morality = character.motivation.morality
    if total_conflict > roll:
        character.motivation.morality = max(0, old_morality - (total_conflict - roll))
    else:
        character.motivation.morality = min(100, old_morality + (roll - total_conflict))

    # Reset conflict accumulator
    character.motivation.conflict = 0

    new_label = morality_label(character.motivation.morality)

    logging.info(
        f"Morality resolution: conflict={total_conflict}, roll={roll}, "
        f"morality {old_morality} -> {character.motivation.morality} ({new_label})"
    )

    return {
        "conflict_earned": conflict_earned,
        "total_conflict": total_conflict,
        "roll": roll,
        "old_morality": old_morality,
        "new_morality": character.motivation.morality,
        "label": new_label,
    }


def check_pinch_point(
    spine_act: dict,
    act_progress: float,
    pinch_point_fired: bool,
) -> Optional[str]:
    """
    CS-6 Phase 2: Check if a pinch point should fire this turn.

    Returns a pinch point instruction if conditions are met.
    Returns None otherwise.
    """
    pp_data = spine_act.get("pinch_point")
    if not pp_data:
        return None
    if pinch_point_fired:
        return None

    target = pp_data.get("target_progress", 0.5)
    if act_progress < target:
        return None

    description = pp_data.get("description", "")
    return (
        f"ANTAGONIST PRESSURE BEAT: Before or during this turn's "
        f"narration, show the antagonistic force directly. "
        f"{description} "
        f"This should be visceral and immediate — not reported "
        f"secondhand. The player should feel the weight of what "
        f"they're up against."
    )


def check_closure_heartbeat(
    open_threads: list,
    turns_since_last_thread_change: int,
    threads_advanced_this_turn: list,
    threads_resolved_this_turn: list,
) -> Optional[str]:
    """
    CS-6 Phase 8: If no threads have advanced or resolved in the last
    N turns, inject a thread-progression instruction.
    """
    HEARTBEAT_INTERVAL = 4

    if threads_advanced_this_turn or threads_resolved_this_turn:
        return None

    if turns_since_last_thread_change < HEARTBEAT_INTERVAL:
        return None

    if not open_threads:
        return None

    thread_names = [t.name if hasattr(t, "name") else str(t) for t in open_threads[:3]]
    return (
        f"THREAD HEARTBEAT: It has been {turns_since_last_thread_change} "
        f"turns since any narrative thread advanced. The following threads "
        f"are open: {', '.join(thread_names)}. This turn should "
        f"escalate, invert, or resolve at least one of them. Stories must "
        f"progress, not just accumulate."
    )


def reconcile_turn(
    narration: str,
    player_action: str,
    check_result: str,
    active_npcs: list[NPCState],
    arc: ArcState,
    spine_act: dict,
    max_retries: int = 2,
    spine: Optional[dict] = None,
    tier: str = TIER_FAST,
) -> ReconciliationResult:
    """
    Orchestrate the local model reconciliation call and parse the response.

    Runs AFTER narration, BEFORE turn logging. Produces structured state
    updates that are applied to NPC states, arc state, and thread lists.
    """
    npc_block = "\n".join(npc.to_prompt_block() for npc in active_npcs) if active_npcs else "No NPCs in scene."

    open_threads_block = "\n".join(
        f"- {t.name}" for t in arc.open_threads
    ) if arc.open_threads else "None established yet."

    raw_expected = spine_act.get("expected_turns", [8, 12])
    if isinstance(raw_expected, str):
        # Parse "8-12" format to [8, 12]
        parts = [int(x.strip()) for x in raw_expected.split("-") if x.strip().isdigit()]
        expected_turns = parts if len(parts) == 2 else [8, 12]
    elif isinstance(raw_expected, list):
        expected_turns = [int(x) if isinstance(x, (int, float)) else 8 for x in raw_expected]
    else:
        expected_turns = [8, 12]
    expected_mid = sum(expected_turns) // 2

    # CS-6 Phase 1: Compute valid dramatic missions from act context
    dramatic_mission_block = ""
    try:
        from engine.dramatic_mission import compute_valid_missions, MISSION_DEFINITIONS
        dramatic_function = spine_act.get("dramatic_function", "")
        total_acts = (spine or {}).get("total_acts", arc.total_acts)
        overall_progress = (arc.current_act - 1 + arc.act_progress) / max(total_acts, 1)
        valid_missions = compute_valid_missions(
            dramatic_function, arc.act_progress, overall_progress,
        )
        mission_defs = "\n".join(
            f"- {m}: {MISSION_DEFINITIONS.get(m, '')}" for m in valid_missions
        )
        dramatic_mission_block = (
            f"\nDRAMATIC MISSION:\n"
            f"Valid missions for this turn: {', '.join(valid_missions)}\n"
            f"Select ONE mission that best fits what should happen next in the story.\n"
            f"Write one sentence describing the specific narrative job of the next turn.\n\n"
            f"Mission definitions:\n{mission_defs}\n"
        )
    except Exception as e:
        logging.warning(f"Dramatic mission computation skipped: {e}")

    # CS-6 Phase 6: Contradiction tracking block
    contradiction_tracking_block = ""
    try:
        # Get protagonist_contradiction from spine's character variant
        protagonist_contradiction = ""
        contradiction_origin = ""
        allegiances = (spine or {}).get("allegiances", [])
        for allg in allegiances:
            for cv in allg.get("character_variants", []):
                pc = cv.get("protagonist_contradiction", "")
                co = cv.get("contradiction_origin", "")
                if pc:
                    protagonist_contradiction = pc
                    contradiction_origin = co
                    break
            if protagonist_contradiction:
                break

        if protagonist_contradiction:
            contradiction_tracking_block = (
                f'\nPROTAGONIST CONTRADICTION: "{protagonist_contradiction}"\n'
            )
            if contradiction_origin:
                contradiction_tracking_block += f'Origin: "{contradiction_origin}"\n'
            contradiction_tracking_block += (
                "\nWas this contradiction relevant to what just happened? If yes:\n"
                '- "reinforced": The character acted FROM the contradiction\n'
                '- "resisted": The character actively fought the contradiction\n'
                '- "transformed": The character found a new relationship with it\n'
                '- "cost_paid": The contradiction caused a tangible negative consequence\n'
                '- "none": The contradiction wasn\'t relevant this turn.'
            )
    except Exception as e:
        logging.warning(f"Contradiction tracking block skipped: {e}")

    # CS-6 Phase 3: No-new-exposition warning
    no_new_exposition_block = ""
    try:
        from engine.dramatic_mission import check_no_new_exposition
        story_arch = (spine or {}).get("story_architecture")
        mbs = story_arch.get("milestone_beat_sheet") if story_arch else None
        note = check_no_new_exposition(arc.current_act, mbs)
        if note:
            no_new_exposition_block = note
    except Exception as e:
        logging.warning(f"No-new-exposition check skipped: {e}")

    template = PROMPT_PATH.read_text(encoding="utf-8")
    prompt = template.format(
        player_action=player_action,
        check_result=check_result or "No dice check this turn.",
        narration=narration,
        npc_states=npc_block,
        anchor_name=spine_act.get("anchor", "unknown"),
        anchor_description=spine_act.get("anchor_description", ""),
        act_progress=f"{arc.act_progress:.0%}",
        turns_this_act=arc.turns_this_act,
        expected_turns=expected_mid,
        open_threads=open_threads_block,
        dramatic_mission_block=dramatic_mission_block,
        contradiction_tracking_block=contradiction_tracking_block,
        no_new_exposition_block=no_new_exposition_block,
    )

    try:
        data = call_chat_json(
            tier=tier,
            purpose="reconciliation",
            user=prompt,
            schema=RECONCILIATION_SCHEMA,
            temperature=0.1,
            max_tokens=RECONCILIATION_MAX_TOKENS,
            timeout=RECONCILIATION_TIMEOUT_SEC,
            retries=max(1, min(max_retries + 1, RECONCILIATION_RETRIES)),
        )
        return _validate_result(data)
    except Exception as e:
        # Graceful degradation: state updates are non-critical (mechanical
        # outcomes are already resolved by code). Returning defaults lets the
        # turn complete; the next turn re-attempts reconciliation fresh.
        logging.error(f"Reconciliation failed after {max_retries + 1} attempts: {e}")
        return ReconciliationResult()


def reconcile_turn_with_escalation(
    *,
    session_id: str,
    turn_number: int,
    prior_zero_delta_count: int,
    narration: str,
    player_action: str,
    check_result: str,
    active_npcs: list[NPCState],
    arc: ArcState,
    spine_act: dict,
    spine: Optional[dict] = None,
    max_retries: int = 2,
) -> tuple[ReconciliationResult, int, bool]:
    """Reconcile with selective escalation when the fast tier silently
    returns zero state deltas for two turns in a row.

    Reconciliation is allowed to be sparse — many turns are quiet, and a
    zero-delta result is legitimate. But two consecutive empty results
    suggest the local model has drifted away from the prompt, so we rerun
    once through the quality tier and emit a telemetry event so the eval
    harness can flag the pattern.

    Returns:
      (result, new_consecutive_zero_delta_count, escalated)
    """
    # First attempt — fast tier (the configured default for reconciliation).
    result = reconcile_turn(
        narration=narration,
        player_action=player_action,
        check_result=check_result,
        active_npcs=active_npcs,
        arc=arc,
        spine_act=spine_act,
        max_retries=max_retries,
        spine=spine,
        tier=TIER_FAST,
    )
    silent = is_silent_reconciliation(result)
    fast_deltas = count_state_deltas(result)

    # Two-strike escalation: only escalate when the prior turn was also empty.
    # Single empty results are normal and don't warrant the higher cost.
    if silent and prior_zero_delta_count >= 1:
        try:
            from state.telemetry import NarrativeEvent, emit_event
        except Exception:
            NarrativeEvent = None  # type: ignore
            emit_event = None      # type: ignore

        quality_result = reconcile_turn(
            narration=narration,
            player_action=player_action,
            check_result=check_result,
            active_npcs=active_npcs,
            arc=arc,
            spine_act=spine_act,
            max_retries=max_retries,
            spine=spine,
            tier=TIER_QUALITY,
        )
        quality_silent = is_silent_reconciliation(quality_result)

        if NarrativeEvent and emit_event:
            try:
                emit_event(NarrativeEvent(
                    session_id=session_id,
                    turn_number=turn_number,
                    event_type="reconciliation_escalated",
                    event_data={
                        "prior_zero_delta_count": prior_zero_delta_count,
                        "fast_silent":            True,
                        "quality_silent":         quality_silent,
                        "recovered":              not quality_silent,
                    },
                ))
            except Exception as e:
                logging.warning(f"reconciliation_escalated telemetry failed: {e}")

        # If the quality run found something the fast tier missed, it wins.
        # Otherwise the streak is real (genuinely quiet turn) — keep the
        # fast result and reset the counter so we don't escalate every turn.
        if not quality_silent:
            return quality_result, 0, True
        return result, 0, True

    new_count = (prior_zero_delta_count + 1) if silent else 0
    return result, new_count, False


def _validate_result(data: dict) -> ReconciliationResult:
    """Validate and normalize the reconciliation JSON."""
    npc_updates = []
    for npc in data.get("npc_updates", []):
        if not isinstance(npc, dict) or "npc_name" not in npc:
            continue
        # Clamp disposition_shift to [-0.2, 0.2]
        shift = float(npc.get("disposition_shift", 0.0))
        shift = max(-0.2, min(0.2, shift))
        npc_updates.append({
            "npc_name": npc["npc_name"],
            "knowledge_gained": npc.get("knowledge_gained", []),
            "knowledge_lost": npc.get("knowledge_lost", []),
            "disposition_shift": shift,
        })

    thread_raw = data.get("thread_updates", {})
    thread_updates = {
        "threads_advanced": thread_raw.get("threads_advanced", []),
        "threads_resolved": thread_raw.get("threads_resolved", []),
        "threads_opened": thread_raw.get("threads_opened", []),
    }

    progress_raw = data.get("story_progress", {})
    proximity = progress_raw.get("anchor_proximity", "distant")
    if proximity not in ("distant", "approaching", "imminent", "reached"):
        proximity = "distant"

    delta = float(progress_raw.get("progress_delta", 0.05))
    delta = max(0.0, min(0.25, delta))

    story_progress = {
        "anchor_proximity": proximity,
        "progress_delta": delta,
        "reasoning": progress_raw.get("reasoning", ""),
    }

    # CS-6 Phase 1: Parse dramatic mission (graceful degradation if absent)
    dramatic_mission_raw = data.get("dramatic_mission", {})
    dramatic_mission = {
        "selected_mission": dramatic_mission_raw.get("selected_mission", ""),
        "mission_sentence": dramatic_mission_raw.get("mission_sentence", ""),
    }

    # CS-6 Phase 6: Parse contradiction tracking (graceful degradation if absent)
    ct_raw = data.get("contradiction_tracking", {})
    contradiction_tracking = {
        "contradiction_engaged": bool(ct_raw.get("contradiction_engaged", False)),
        "arc_movement": ct_raw.get("arc_movement", "none"),
        "arc_evidence": ct_raw.get("arc_evidence", ""),
    }

    # Reputation event — most turns this is null
    rep_raw = data.get("reputation_event")
    reputation_event = rep_raw.strip() if isinstance(rep_raw, str) and rep_raw.strip() else None
    raw_tags = data.get("faction_tags", [])
    faction_tags = [str(t).strip() for t in raw_tags if isinstance(t, (str, int))] if isinstance(raw_tags, list) else []

    return ReconciliationResult(
        npc_updates=npc_updates,
        thread_updates=thread_updates,
        story_progress=story_progress,
        dramatic_mission=dramatic_mission,
        contradiction_tracking=contradiction_tracking,
        reputation_event=reputation_event,
        faction_tags=faction_tags,
    )


def apply_npc_updates(
    updates: list[dict], npc_states: list[NPCState]
) -> list[NPCState]:
    """Apply knowledge changes and disposition shifts to NPC state cards."""
    npc_map = {npc.name: npc for npc in npc_states}

    for update in updates:
        name = update.get("npc_name")
        if name not in npc_map:
            continue

        npc = npc_map[name]

        # Knowledge gained
        for fact in update.get("knowledge_gained", []):
            if fact and fact not in npc.knows:
                npc.knows.append(fact)

        # Knowledge lost (remove from knows, optionally add to doesnt_know)
        for fact in update.get("knowledge_lost", []):
            if fact in npc.knows:
                npc.knows.remove(fact)
            if fact and fact not in npc.doesnt_know:
                npc.doesnt_know.append(fact)

        # Disposition shift — clamp to [0.0, 1.0]
        shift = update.get("disposition_shift", 0.0)
        npc.disposition = max(0.0, min(1.0, npc.disposition + shift))

        # Phase 8.5: GM-inferred emotional state (§25.2)
        inferred_mood = update.get("emotional_state", "calm")
        if inferred_mood and inferred_mood != "calm":
            from gm.context import MOOD_DECAY_RATES
            if inferred_mood in MOOD_DECAY_RATES:
                # Only override if no stronger emotion already set by dice
                if not npc.emotional_state.is_active() or npc.emotional_state.intensity < 0.4:
                    npc.set_emotion(inferred_mood, 0.4, "GM narration", 0)

    return npc_states


def apply_story_progress(
    progress: dict, arc_state: dict, spine_act: dict
) -> dict:
    """Update act_progress and anchor_proximity in the arc state dict."""
    proximity = progress.get("anchor_proximity", "distant")
    delta = progress.get("progress_delta", 0.05)

    if proximity == "reached":
        arc_state["act_progress"] = 1.0
    else:
        arc_state["act_progress"] = min(1.0, arc_state.get("act_progress", 0.0) + delta)

    arc_state["anchor_proximity"] = proximity
    return arc_state


def apply_thread_updates(
    thread_updates: dict, arc_state: dict, spine_act: dict
) -> dict:
    """Manage open/closed thread lists in the arc state."""
    open_threads = list(arc_state.get("dynamic_threads", []))
    closed_threads = list(arc_state.get("closed_threads", []))

    # Threads resolved — move from open to closed
    for thread_name in thread_updates.get("threads_resolved", []):
        if thread_name not in closed_threads:
            closed_threads.append(thread_name)
        # Remove from dynamic threads if present
        open_threads = [t for t in open_threads if t != thread_name]

    # Threads advanced — promote spine threads into dynamic_threads so they
    # persist across act boundaries even if the next act's spine has no threads
    spine_threads = spine_act.get("open_threads", [])
    for thread_name in thread_updates.get("threads_advanced", []):
        if thread_name in spine_threads and thread_name not in open_threads:
            open_threads.append(thread_name)

    # Threads opened — add new threads
    for thread_name in thread_updates.get("threads_opened", []):
        if thread_name not in open_threads:
            open_threads.append(thread_name)

    arc_state["dynamic_threads"] = open_threads
    arc_state["closed_threads"] = closed_threads
    return arc_state


def detect_act_boundary(arc_state: dict) -> bool:
    """Returns True when act_progress >= 1.0."""
    return arc_state.get("act_progress", 0.0) >= 1.0


def build_anchor_instruction(spine_act: dict, next_act: Optional[dict]) -> str:
    """Build the anchor instruction that replaces the pacing block when anchor is reached."""
    anchor_desc = spine_act.get("anchor_description", spine_act.get("anchor", ""))
    next_situation = next_act.get("opening_situation", "") if next_act else ""

    return (
        f"ANCHOR BEAT — MAJOR STORY MOMENT\n"
        f"The situation has shifted irreversibly. {anchor_desc}\n"
        f"Write the transition into this new reality. The player should feel "
        f"that they have crossed a threshold.\n"
        f"{'Next situation: ' + next_situation if next_situation else ''}"
    ).strip()


def run_between_act_pipeline(
    session_id: str,
    character,  # engine.character.Character
    spine: dict,
    completed_act_number: int,
) -> BetweenActResult:
    """
    The between-act processing pipeline (§26.5).

    16 steps. Steps that depend on unbuilt systems (XP, behavioral inference,
    milestones, obligation, morality, destiny, growth passage, time skip) are
    stubbed and will be wired in later phases.
    """
    from state.db import get_connection
    from state.memory import compress_act_turns

    result = BetweenActResult()
    next_act_number = completed_act_number + 1
    total_acts = spine.get("total_acts", 4)

    # ── Step 1: Act summary compression ──────────────────────────────
    try:
        compress_act_turns(session_id, completed_act_number)
        result.steps_completed.append("act_summary_compression")
        logging.info(f"Between-act step 1: compressed act {completed_act_number}")
    except Exception as e:
        logging.error(f"Between-act step 1 failed: {e}")

    # ── Step 2: Character drift note ─────────────────────────────────
    # Behavioral pattern observation — uses local model
    try:
        drift_note = _generate_character_drift_note(session_id, completed_act_number)
        result.character_drift_note = drift_note
        result.steps_completed.append("character_drift_note")
        logging.info(f"Between-act step 2: drift note generated")
    except Exception as e:
        logging.error(f"Between-act step 2 failed: {e}")

    # ── Steps 3-4: XP award and reservation (§14.1) ─────────────────
    turn_rows = []
    try:
        from state.session import get_act_turns
        from engine.advancement import award_act_xp, RESERVED_XP_CAP

        # Read arc_state from DB to get turns_this_act
        with get_connection() as conn:
            row = conn.execute(
                "SELECT arc_state_json FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        arc_state = json.loads(row["arc_state_json"]) if row else {}
        turns_count = arc_state.get("turns_this_act", 10)

        act_config = spine["acts"][completed_act_number - 1]
        turn_rows = get_act_turns(session_id, turns_count)

        xp_award = award_act_xp(act_config, turn_rows, character, arc_state)

        # Apply XP to character
        character.total_xp += xp_award.total_xp
        character.available_xp += xp_award.inference_xp
        character.reserved_xp = min(
            character.reserved_xp + xp_award.reserved_xp,
            RESERVED_XP_CAP,
        )

        result.xp_award = xp_award
        result.steps_completed.append("xp_award")
        result.steps_completed.append("xp_reservation")
        logging.info(
            f"Between-act steps 3-4: awarded {xp_award.total_xp} XP "
            f"(inference={xp_award.inference_xp}, reserved={xp_award.reserved_xp})"
        )
    except Exception as e:
        logging.error(f"Between-act steps 3-4 failed: {e}")
        result.steps_completed.append("xp_award_failed")

    # ── Step 5: Behavioral inference (§14.2) ──────────────────────────
    # Phase 13: Parse annotations from turn rows for enriched inference
    parsed_annotations = []
    for t in turn_rows:
        ci = t.get("choice_implications")
        if ci:
            try:
                parsed_annotations.append(
                    json.loads(ci) if isinstance(ci, str) else ci
                )
            except (json.JSONDecodeError, TypeError):
                pass

    try:
        from engine.advancement import compute_behavioral_signals, select_and_apply_advancement

        signals = compute_behavioral_signals(
            turn_rows,
            annotations=parsed_annotations if parsed_annotations else None,
        )
        advancement = select_and_apply_advancement(
            signals, character, character.available_xp, completed_act_number,
        )
        result.advancement = advancement
        result.steps_completed.append("behavioral_inference")
    except Exception as e:
        logging.error(f"Between-act step 5 failed: {e}")
        result.steps_completed.append("behavioral_inference_failed")

    # ── Step 6: Choice annotation aggregation (Phase 13, §24) ────────
    try:
        from engine.advancement import aggregate_behavioral_fingerprint

        fingerprint = aggregate_behavioral_fingerprint(turn_rows)
        result.behavioral_fingerprint = fingerprint
        if fingerprint:
            result.steps_completed.append("behavioral_fingerprint")
            logging.info(
                f"Between-act step 6: behavioral fingerprint — "
                f"priorities={fingerprint['dominant_priorities']}, "
                f"strength={fingerprint['pattern_strength']}"
            )
        else:
            result.steps_completed.append("behavioral_fingerprint_insufficient_data")
    except Exception as e:
        logging.error(f"Between-act step 6 failed: {e}")
        result.steps_completed.append("behavioral_fingerprint_failed")

    # ── Step 7: Milestone eligibility check (Phase 12, §14.3) ────────
    milestone_eligible = False
    try:
        from engine.talents import build_milestone_choices
        milestone_choices = build_milestone_choices(character, character.reserved_xp)
        milestone_eligible = len(milestone_choices) > 0
        result.steps_completed.append(
            "milestone_eligible" if milestone_eligible else "milestone_no_choices"
        )
    except Exception as e:
        logging.error(f"Between-act step 7 failed: {e}")
        result.steps_completed.append("milestone_check_failed")

    # ── Step 8: Obligation/Duty activation roll for NEXT act (§9) ────
    try:
        motivation_flags = roll_obligation_duty(character)
        result.obligation_result = motivation_flags
        result.steps_completed.append("obligation_duty_roll")
        logging.info(f"Between-act step 8: motivation roll — {motivation_flags}")
    except Exception as e:
        logging.error(f"Between-act step 8 failed: {e}")
        result.obligation_result = {}
        result.steps_completed.append("obligation_duty_roll_failed")

    # ── Step 9: Strain and wound recovery ────────────────────────────
    strain_before = character.current_strain
    wounds_before = character.current_wounds
    # Partial recovery — not full unless time skip follows
    character.current_strain = max(0, character.current_strain - 2)
    character.current_wounds = max(0, character.current_wounds - 1)
    result.strain_recovered = strain_before - character.current_strain
    result.wounds_recovered = wounds_before - character.current_wounds
    result.steps_completed.append("strain_wound_recovery")
    logging.info(f"Between-act step 9: recovered {result.strain_recovered} strain, {result.wounds_recovered} wounds")

    # ── Step 10: Morality resolution for COMPLETED act (§9) ──────────
    try:
        morality_result = resolve_morality(session_id, character, completed_act_number)
        result.morality_result = morality_result
        result.steps_completed.append("morality_resolution")
        logging.info(f"Between-act step 10: morality resolution — {morality_result}")
    except Exception as e:
        logging.error(f"Between-act step 10 failed: {e}")
        result.morality_result = {}
        result.steps_completed.append("morality_resolution_failed")

    # ── Step 11: NPC relationship drift ──────────────────────────────
    # Minor disposition adjustments for NPCs not seen during the act
    try:
        _apply_npc_relationship_drift(session_id, completed_act_number)
        result.steps_completed.append("npc_relationship_drift")
        logging.info("Between-act step 11: NPC relationship drift applied")
    except Exception as e:
        logging.error(f"Between-act step 11 failed: {e}")

    # ── Step 12: Destiny Pool regeneration (Phase 11.5, §23.1) ───────
    try:
        from engine.destiny import roll_initial_destiny
        from state.session import update_destiny_pool
        new_light, new_dark = roll_initial_destiny()
        update_destiny_pool(session_id, new_light, new_dark)
        # Reset per-act spend tracking in arc_state
        with get_connection() as conn:
            row = conn.execute(
                "SELECT arc_state_json FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if row:
                arc = json.loads(row["arc_state_json"])
                arc["destiny_light_spent_this_act"] = 0
                arc["destiny_dark_spent_this_act"] = 0
                conn.execute(
                    "UPDATE sessions SET arc_state_json = ? WHERE id = ?",
                    (json.dumps(arc), session_id),
                )
                conn.commit()
        result.steps_completed.append("destiny_pool_regenerated")
    except Exception as e:
        logging.error(f"Between-act step 12 failed: {e}")
        result.steps_completed.append("destiny_pool_failed")

    # ── Step 13: Growth passage generation (Phase 8+) ────────────────
    result.steps_completed.append("growth_passage_stub")

    # ── Step 14: Milestone reflection + intervention reset (Phase 12) ─
    # 14a: Reset intervention talent uses at act boundary (§15.1)
    try:
        from engine.talents import reset_intervention_uses
        reset_intervention_uses(character)
        result.steps_completed.append("intervention_uses_reset")
    except Exception as e:
        logging.error(f"Between-act step 14a (intervention reset) failed: {e}")

    # 14b: Generate milestone reflection if eligible (§14.3)
    if milestone_eligible:
        try:
            from gm.cloud_gm import generate_milestone_reflection
            from state.session import get_act_summaries

            act_summary = get_act_summaries(session_id)
            milestone_result = generate_milestone_reflection(
                character=character,
                choices=milestone_choices,
                campaign_name=spine.get("name", ""),
                current_act=completed_act_number,
                total_acts=total_acts,
                act_summary=act_summary,
            )
            result.milestone_passage = milestone_result.passage
            result.milestone_choices = [
                {
                    "display": (milestone_result.choices[i]
                                if i < len(milestone_result.choices) else ""),
                    "talent_ref": (milestone_result.skill_tags[i]
                                   if i < len(milestone_result.skill_tags) else ""),
                    "branch_theme": (milestone_choices[i].branch_theme
                                     if i < len(milestone_choices) else ""),
                    "xp_cost": (milestone_choices[i].xp_cost
                                if i < len(milestone_choices) else 0),
                }
                for i in range(len(milestone_choices))
            ]
            result.steps_completed.append("milestone_reflection")
            logging.info(
                f"Between-act step 14b: milestone reflection with "
                f"{len(milestone_choices)} choices"
            )
        except Exception as e:
            logging.error(f"Between-act step 14b (milestone reflection) failed: {e}")
            result.steps_completed.append("milestone_reflection_failed")
    else:
        result.steps_completed.append("milestone_skipped")

    # ── Step 14c: Force power milestone check (Phase 15, §16.4) ───────
    if character.force_rating > 0 and character.force_powers:
        try:
            from engine.force import build_force_power_milestone_choices
            fp_choices = build_force_power_milestone_choices(
                character, character.reserved_xp,
            )
            if fp_choices:
                from gm.cloud_gm import generate_force_power_milestone_reflection
                from state.session import get_act_summaries

                act_summary = get_act_summaries(session_id)
                fp_result = generate_force_power_milestone_reflection(
                    character=character,
                    choices=fp_choices,
                    campaign_name=spine.get("name", ""),
                    current_act=completed_act_number,
                    total_acts=total_acts,
                    act_summary=act_summary,
                )
                result.force_power_milestone_passage = fp_result.passage
                result.force_power_milestone_choices = [
                    {
                        "display": (fp_result.choices[i]
                                    if i < len(fp_result.choices) else ""),
                        "force_tag": (fp_result.skill_tags[i]
                                      if i < len(fp_result.skill_tags) else ""),
                        "power_name": fp_choices[i].power_name if i < len(fp_choices) else "",
                        "upgrade_name": fp_choices[i].upgrade_name if i < len(fp_choices) else "",
                        "xp_cost": fp_choices[i].xp_cost if i < len(fp_choices) else 0,
                    }
                    for i in range(len(fp_choices))
                ]
                result.steps_completed.append("force_power_milestone_reflection")
                logging.info(
                    f"Between-act step 14c: Force power milestone with "
                    f"{len(fp_choices)} choices"
                )
            else:
                result.steps_completed.append("force_power_milestone_no_choices")
        except Exception as e:
            logging.error(f"Between-act step 14c (Force power milestone) failed: {e}")
            result.steps_completed.append("force_power_milestone_failed")

    # ── Step 15: Time skip preparation (Phase 17, §19) ─────────────
    try:
        from engine.time_skip import (
            load_time_skip_config,
            select_vignettes,
            apply_time_skip_recovery,
            apply_npc_time_drift,
            serialize_time_skip_state,
            serialize_vignette,
        )
        # Time skip config lives on the NEXT act (the act we're entering)
        next_act_config = (spine["acts"][next_act_number - 1]
                           if next_act_number <= total_acts else {})
        ts_config = load_time_skip_config(next_act_config)

        if ts_config and ts_config.vignettes:
            # Load NPC states for prerequisite checks and selection scoring
            from state.db import get_connection as _gc
            with _gc() as conn:
                npc_rows = conn.execute(
                    "SELECT npc_name, state_json FROM npc_states WHERE session_id = ?",
                    (session_id,),
                ).fetchall()
            from gm.context import NPCState as _NPC, EmotionalState as _ES
            npc_states_for_skip = []
            for r in npc_rows:
                ns = json.loads(r["state_json"])
                npc_states_for_skip.append(_NPC(
                    name=r["npc_name"],
                    disposition=ns.get("disposition", 0.5),
                    knows=ns.get("knows", []),
                    doesnt_know=ns.get("doesnt_know", []),
                    last_seen_turn=ns.get("last_seen_turn", 0),
                    voice_notes=ns.get("voice_notes", ""),
                    motivation=ns.get("motivation", ""),
                    behavioral_envelope=ns.get("behavioral_envelope", []),
                    emotional_state=_ES.from_dict(ns.get("emotional_state", {})),
                ))

            # Select vignettes based on behavioral fingerprint
            selected = select_vignettes(
                ts_config, character, npc_states_for_skip,
                behavioral_fingerprint=result.behavioral_fingerprint,
            )

            if selected:
                # Full recovery during time skip
                recovery = apply_time_skip_recovery(character, ts_config.duration_months)
                result.strain_recovered = recovery["strain_recovered"]
                result.wounds_recovered = recovery["wounds_recovered"]

                # NPC relationship drift
                apply_npc_time_drift(npc_states_for_skip, ts_config.duration_months)

                # Generate opening passage
                opening_passage = ""
                try:
                    from gm.cloud_gm import generate_time_skip_opening
                    from state.session import get_act_summaries
                    act_summary = get_act_summaries(session_id)
                    opening_passage = generate_time_skip_opening(
                        character=character,
                        duration_months=ts_config.duration_months,
                        framing=ts_config.framing,
                        campaign_name=spine.get("name", ""),
                        act_summary=act_summary,
                    )
                except Exception as e:
                    logging.error(f"Time skip opening generation failed: {e}")
                    opening_passage = ts_config.framing  # fallback to authored framing

                # Prepare time skip data for API — vignettes are interactive,
                # so we store the state and let the API handle sequencing
                result.time_skip_data = {
                    "opening_passage": opening_passage,
                    "duration_months": ts_config.duration_months,
                    "framing": ts_config.framing,
                    "vignettes": [serialize_vignette(v) for v in selected],
                    "state": serialize_time_skip_state(ts_config, selected, [], 0),
                }
                result.steps_completed.append("time_skip_prepared")
                logging.info(
                    f"Between-act step 15: time skip prepared — "
                    f"{ts_config.duration_months} months, "
                    f"{len(selected)} vignettes"
                )
            else:
                result.steps_completed.append("time_skip_no_eligible_vignettes")
        else:
            result.steps_completed.append("time_skip_none_defined")
    except Exception as e:
        logging.error(f"Between-act step 15 failed: {e}")
        result.steps_completed.append("time_skip_failed")

    # ── Step 16: Load next act ───────────────────────────────────────
    if next_act_number <= total_acts:
        next_act = spine["acts"][next_act_number - 1]
        with get_connection() as conn:
            row = conn.execute(
                "SELECT arc_state_json FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if row:
                arc_state = json.loads(row["arc_state_json"])
                arc_state["current_act"] = next_act_number
                arc_state["act_progress"] = 0.0
                arc_state["anchor_proximity"] = "distant"
                arc_state["turns_this_act"] = 0
                arc_state["current_location"] = next_act.get("opening_location", "")
                arc_state["anchors_completed"] = arc_state.get("anchors_completed", [])
                arc_state["anchors_completed"].append(
                    spine["acts"][completed_act_number - 1].get("anchor", "")
                )
                # CS-6 per-act resets: pinch point can fire once per act,
                # consecutive_zero_delta is per-act, foreshadow setups
                # delivered are per-spine but turn counters reset.
                arc_state["pinch_point_fired"] = False
                arc_state["consecutive_zero_delta_turns"] = 0
                arc_state["consecutive_no_check_turns"] = 0
                arc_state["last_turn_pinch_fired"] = False
                arc_state["last_turn_had_despair"] = False
                # Carry forward dynamic threads that weren't resolved
                # (closed_threads and dynamic_threads persist as-is)

                # Phase 8: Write motivation flags for next act
                arc_state.update(result.obligation_result)

                from datetime import datetime, timezone
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    "UPDATE sessions SET arc_state_json = ?, character_json = ?, "
                    "updated_at = ? WHERE id = ?",
                    (json.dumps(arc_state), character.model_dump_json(), now, session_id),
                )
                conn.commit()

        result.next_act_loaded = True
        result.steps_completed.append("load_next_act")
        logging.info(f"Between-act step 16: loaded act {next_act_number}")
    else:
        result.steps_completed.append("campaign_complete")
        logging.info("Between-act: campaign complete, no next act to load")

    return result


def _generate_character_drift_note(session_id: str, act_number: int) -> str:
    """Generate a brief behavioral observation about the character's choices this act."""
    from state.session import get_recent_turns

    turns = get_recent_turns(session_id, limit=20)
    if not turns:
        return ""

    actions = "\n".join(
        f"Turn {t.turn_number}: {t.player_action}"
        + (f" [{t.check_made}: {t.outcome_quadrant}]" if t.check_made else "")
        for t in turns
    )

    prompt = (
        f"Based on these player choices from Act {act_number} of a Star Wars RPG, "
        f"write ONE sentence noting a behavioral pattern or character tendency you observed. "
        f"Be specific. Do not moralize.\n\n"
        f"CHOICES:\n{actions}\n\n"
        f"ONE SENTENCE:"
    )

    note = call_chat(
        tier=TIER_FAST,
        purpose="drift",
        user=prompt,
        temperature=0.3,
        max_tokens=100,
        timeout=30.0,
        retries=2,
    )
    return note.strip()


def _apply_npc_relationship_drift(session_id: str, act_number: int) -> None:
    """Minor disposition adjustments for NPCs not interacted with during the act."""
    from state.db import get_connection
    from dataclasses import fields as dc_fields

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT npc_name, state_json FROM npc_states WHERE session_id = ?",
            (session_id,),
        ).fetchall()

    if not rows:
        return

    # NPCs with disposition far from 0.5 drift slightly back toward neutral
    # This represents the natural cooling of relationships over time
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    for row in rows:
        state = json.loads(row["state_json"])
        disp = state.get("disposition", 0.5)
        # Drift 0.02 toward 0.5
        if disp > 0.55:
            state["disposition"] = disp - 0.02
        elif disp < 0.45:
            state["disposition"] = disp + 0.02

        with get_connection() as conn:
            conn.execute(
                "UPDATE npc_states SET state_json = ?, updated_at = ? "
                "WHERE session_id = ? AND npc_name = ?",
                (json.dumps(state), now, session_id, row["npc_name"]),
            )
            conn.commit()
