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

import httpx

from gm.context import ArcState, NPCState, ThreadState

PROMPT_PATH = Path(__file__).resolve().parent.parent / "gm" / "prompts" / "reconciliation.txt"
OLLAMA_URL  = os.getenv("OLLAMA_URL", "http://localhost:11434")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "qwen3.5:9b")

# JSON schema for structured output from the local model
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
    steps_completed: list[str] = field(default_factory=list)


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


def reconcile_turn(
    narration: str,
    player_action: str,
    check_result: str,
    active_npcs: list[NPCState],
    arc: ArcState,
    spine_act: dict,
    max_retries: int = 2,
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

    expected_turns = spine_act.get("expected_turns", [8, 12])
    expected_mid = sum(expected_turns) // 2

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
    )

    last_error = None
    for _ in range(max_retries + 1):
        try:
            is_qwen = "qwen" in LOCAL_MODEL.lower()
            msg = f"/no_think\n{prompt}" if is_qwen else prompt

            response = httpx.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": LOCAL_MODEL,
                    "prompt": msg,
                    "stream": False,
                    "format": RECONCILIATION_SCHEMA,
                    "options": {"temperature": 0.1, "num_predict": 500},
                },
                timeout=30.0,
            )
            response.raise_for_status()
            resp_json = response.json()
            raw_text = resp_json["response"].strip()

            # Handle thinking mode producing empty response
            if not raw_text and resp_json.get("thinking", "").strip():
                raw_text = resp_json["thinking"].strip()

            # Strip markdown code fences
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
                raw_text = raw_text.strip()

            data = json.loads(raw_text)
            return _validate_result(data)

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            last_error = e
        except httpx.HTTPError as e:
            logging.error(f"Reconciliation Ollama error: {e}")
            last_error = e

    logging.error(f"Reconciliation failed after {max_retries + 1} attempts: {last_error}")
    return ReconciliationResult()  # graceful degradation — return defaults


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

    return ReconciliationResult(
        npc_updates=npc_updates,
        thread_updates=thread_updates,
        story_progress=story_progress,
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
    try:
        from engine.advancement import compute_behavioral_signals, select_and_apply_advancement

        signals = compute_behavioral_signals(turn_rows)
        advancement = select_and_apply_advancement(
            signals, character, character.available_xp, completed_act_number,
        )
        result.advancement = advancement
        result.steps_completed.append("behavioral_inference")
    except Exception as e:
        logging.error(f"Between-act step 5 failed: {e}")
        result.steps_completed.append("behavioral_inference_failed")

    # ── Step 6: Choice annotation aggregation (Phase 13+) ────────────
    result.steps_completed.append("choice_annotation_stub")

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

    # ── Step 15: Time skip sequence (Phase 8+) ───────────────────────
    result.steps_completed.append("time_skip_stub")

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

    is_qwen = "qwen" in LOCAL_MODEL.lower()
    msg = f"/no_think\n{prompt}" if is_qwen else prompt

    response = httpx.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": LOCAL_MODEL,
            "prompt": msg,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 100},
        },
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()["response"].strip()


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
