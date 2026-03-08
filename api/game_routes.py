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
import threading
from dataclasses import asdict, fields
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from engine.character import Character
from engine.equipment import (
    COMBAT_SKILLS,
    build_combat_damage_block,
    get_weapon_for_skill,
)
from engine.checks import (
    CheckRequest,
    DIFFICULTY_LABELS,
    build_pool,
    describe_pool_for_display,
)
from engine.dice import roll_pool
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
)
from engine.reconciliation import (
    reconcile_turn,
    apply_npc_updates,
    apply_story_progress,
    apply_thread_updates,
    detect_act_boundary,
    build_anchor_instruction,
    run_between_act_pipeline,
    roll_obligation_duty,
    morality_label,
)
from gm.local_gm import decide_check
from state.db import get_connection
from state.memory import compress_if_needed, should_compress, compress_act_turns
from state.session import (
    create_session,
    get_act_summaries,
    get_recent_turns,
    get_session,
    get_turn_count,
    log_turn,
)

router = APIRouter()

STREAMING_ENABLED = os.getenv("STREAMING_ENABLED", "true").lower() == "true"

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


# ── Helper Functions ────────────────────────────────────────────────────

def load_campaign_spine(name: str) -> dict:
    """Read campaign spine JSON from data/campaigns/{name}.json."""
    # Normalize: "The Nar Shaddaa Job" -> "nar_shaddaa_job"
    filename = name.lower().replace(" ", "_").replace("the_", "")
    path = f"data/campaigns/{filename}.json"
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(404, f"Campaign not found: {name}")


def load_character(character_id: str) -> Character:
    """Read character JSON from data/characters/{id}.json."""
    path = f"data/characters/{character_id}.json"
    try:
        with open(path) as f:
            return Character.model_validate_json(f.read())
    except FileNotFoundError:
        raise HTTPException(404, f"Character not found: {character_id}")


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
    character = load_character(req.character_id)
    act_1 = spine["acts"][0]

    # ── Roll motivation track for Act 1 (§9) ─────────────────────────
    motivation_flags = roll_obligation_duty(character)

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
        **motivation_flags,
    }

    # ── Create session in database ────────────────────────────────────
    session_id = create_session(
        campaign_name=req.campaign_name,
        character_json=character.model_dump_json(),
        arc_state_json=json.dumps(arc_state),
    )

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
        ))

    # ── Resolve variation points (e.g. Doss's fate) ───────────────────
    resolve_initial_variations(session_id, spine)

    # ── Build opening context package ─────────────────────────────────
    npc_states = load_npc_states(session_id, spine)

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
            open_threads=[
                ThreadState(name=t) for t in act_1.get("open_threads", [])
            ],
            closed_threads=[],
            anchor_description=act_1.get("anchor_description", ""),
            obligation_active=arc_state.get("obligation_active", False),
            obligation_type=arc_state.get("obligation_type", ""),
            duty_active=arc_state.get("duty_active", False),
            duty_type=arc_state.get("duty_type", ""),
            morality_label=arc_state.get("morality_label", ""),
        ),
        story_summary="",
        recent_turns=[],
        active_npcs=npc_states,
        location=arc_state["current_location"],
        situation=act_1["opening_situation"],
        galactic_context=act_1.get("galactic_context", ""),
        scene_type="exploration",  # opening is always exploration
        tone_instruction=(
            "This is the opening of the campaign. Establish the world, "
            "the character's voice, and the immediate situation. Ground "
            "the reader in a specific sensory moment."
        ),
        expected_turns=act_1.get("expected_turns", [8, 12]),
    )

    # ── Generate opening narration (one cloud call) ───────────────────
    narration_result = narrate_turn(ctx)

    # ── Log Turn 0 ────────────────────────────────────────────────────
    log_turn(
        session_id=session_id,
        turn_number=0,
        player_action="[session_start]",
        choice_index=-1,
        narration=narration_result.passage,
        choices=narration_result.choices,
        scene_type="exploration",
        skill_tags_json=json.dumps(narration_result.skill_tags),
        context_json=None,
    )

    return {
        "session_id": session_id,
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

    # ── Step 1: Resolve the player's choice ───────────────────────────
    last_turn = get_most_recent_turn(session_id)
    previous_choices = json.loads(last_turn["choices_json"])
    previous_skill_tags = json.loads(last_turn.get("skill_tags_json") or "[]")

    if req.choice_index < 0 or req.choice_index >= len(previous_choices):
        raise HTTPException(400, f"Invalid choice_index: {req.choice_index}")

    player_action = previous_choices[req.choice_index]

    # ── Step 2: Build scene description for local GM ──────────────────
    scene_description = (
        f"PREVIOUS: {last_turn['narration'][-500:]}\n\n"
        f"THE PLAYER CHOSE: {player_action}"
    )

    # ── Step 3: Check decision (local model) ──────────────────────────
    recent_turns = get_recent_turns(session_id, limit=5)
    recent_failure_count = sum(
        1 for t in recent_turns[-3:]
        if t.outcome_quadrant and t.outcome_quadrant.startswith("failure")
    )

    check_decision = decide_check(
        character=character,
        scene_description=scene_description,
        player_action=player_action,
        arc_state=arc_state,
        recent_failure_count=recent_failure_count,
    )

    # ── Step 4: Dice resolution (if check required) ───────────────────
    dice_pool = None
    roll_result = None

    if check_decision.requires_check:
        check_request = CheckRequest(
            skill=check_decision.skill,
            difficulty=DIFFICULTY_LABELS[check_decision.difficulty],
            boost_dice=check_decision.boost_dice,
            setback_dice=check_decision.setback_dice,
        )
        dice_pool = build_pool(character, check_request)
        roll_result = roll_pool(dice_pool)

        # Apply mechanical consequences (wounds, strain) — physics first
        if roll_result.outcome_quadrant in ("failure_threat", "success_threat"):
            if abs(roll_result.net_advantages) >= 2:
                character.current_strain = min(
                    character.current_strain + 1,
                    effective_strain_threshold,
                )

    # Phase 9: Compute combat damage context for narration (§18)
    combat_damage_note = ""
    if (roll_result and check_decision.requires_check
            and check_decision.skill in COMBAT_SKILLS
            and roll_result.succeeded):
        weapon = get_weapon_for_skill(character.loadout, check_decision.skill)
        if weapon:
            combat_damage_note = build_combat_damage_block(roll_result, weapon)

    # ── Step 5: Assemble context package ──────────────────────────────
    story_summary = get_act_summaries(session_id)
    npc_states = load_npc_states(session_id, spine)
    turn_number = get_turn_count(session_id) + 1

    # Phase 8.5: Decay emotions + set from dice results (§25)
    for npc in npc_states:
        npc.decay_emotion()
        npc.nudge_disposition_from_emotion()
    if roll_result and check_decision.requires_check:
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
            open_threads=[
                ThreadState(name=t) if isinstance(t, str) else t
                for t in (
                    current_act.get("open_threads", [])
                    + arc_state.get("dynamic_threads", [])
                )
            ],
            closed_threads=arc_state.get("closed_threads", []),
            turns_this_act=arc_state.get("turns_this_act", 0),
            anchor_proximity=arc_state.get("anchor_proximity", "distant"),
            anchor_description=current_act.get("anchor_description", ""),
            obligation_active=arc_state.get("obligation_active", False),
            obligation_type=arc_state.get("obligation_type", ""),
            duty_active=arc_state.get("duty_active", False),
            duty_type=arc_state.get("duty_type", ""),
            morality_label=arc_state.get("morality_label", ""),
        ),
        story_summary=story_summary,
        recent_turns=recent_turns,
        active_npcs=npc_states,
        location=arc_state.get("current_location", ""),
        situation=scene_description,
        galactic_context=current_act.get("galactic_context", ""),
        scene_type=check_decision.scene_type,
        dice_pool=dice_pool,
        roll_result=roll_result,
        anchor_instruction=anchor_inst,
        expected_turns=current_act.get("expected_turns", [8, 12]),
        combat_damage_note=combat_damage_note,
    )

    # ── Step 6: Narrate (cloud model — one call) ─────────────────────
    narration_result = narrate_turn(ctx)

    # ── Step 7: Reconciliation (local model) ─────────────────────────
    check_result_str = ""
    if roll_result:
        check_result_str = (
            f"{check_decision.skill} ({check_decision.difficulty}): "
            f"{roll_result.narrative_label()}"
        )

    recon_result = reconcile_turn(
        narration=narration_result.passage,
        player_action=player_action,
        check_result=check_result_str,
        active_npcs=npc_states,
        arc=ctx.arc,
        spine_act=current_act,
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

    # ── Step 9: Check act boundary ───────────────────────────────────
    act_boundary_reached = detect_act_boundary(arc_state)

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
        context_json=None,
        scene_type=check_decision.scene_type,
        moral_weight=check_decision.moral_weight,
        skill_tags_json=json.dumps(narration_result.skill_tags),
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

    # ── Return ────────────────────────────────────────────────────────
    return {
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
        },
        "used_local_narration": narration_result.used_local,
        "act_boundary": act_boundary_reached,
    }


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

    # ── Step 1: Resolve the player's choice ───────────────────────────
    last_turn = get_most_recent_turn(session_id)
    previous_choices = json.loads(last_turn["choices_json"])

    if req.choice_index < 0 or req.choice_index >= len(previous_choices):
        raise HTTPException(400, f"Invalid choice_index: {req.choice_index}")

    player_action = previous_choices[req.choice_index]

    # ── Step 2: Build scene description for local GM ──────────────────
    scene_description = (
        f"PREVIOUS: {last_turn['narration'][-500:]}\n\n"
        f"THE PLAYER CHOSE: {player_action}"
    )

    # ── Step 3: Check decision (local model) ──────────────────────────
    recent_turns = get_recent_turns(session_id, limit=5)
    recent_failure_count = sum(
        1 for t in recent_turns[-3:]
        if t.outcome_quadrant and t.outcome_quadrant.startswith("failure")
    )

    check_decision = decide_check(
        character=character,
        scene_description=scene_description,
        player_action=player_action,
        arc_state=arc_state,
        recent_failure_count=recent_failure_count,
    )

    # ── Step 4: Dice resolution (if check required) ───────────────────
    dice_pool = None
    roll_result = None

    if check_decision.requires_check:
        check_request = CheckRequest(
            skill=check_decision.skill,
            difficulty=DIFFICULTY_LABELS[check_decision.difficulty],
            boost_dice=check_decision.boost_dice,
            setback_dice=check_decision.setback_dice,
        )
        dice_pool = build_pool(character, check_request)
        roll_result = roll_pool(dice_pool)

        # Apply mechanical consequences (wounds, strain) — physics first
        if roll_result.outcome_quadrant in ("failure_threat", "success_threat"):
            if abs(roll_result.net_advantages) >= 2:
                character.current_strain = min(
                    character.current_strain + 1,
                    effective_strain_threshold,
                )

    # Phase 9: Compute combat damage context for narration (§18)
    combat_damage_note = ""
    if (roll_result and check_decision.requires_check
            and check_decision.skill in COMBAT_SKILLS
            and roll_result.succeeded):
        weapon = get_weapon_for_skill(character.loadout, check_decision.skill)
        if weapon:
            combat_damage_note = build_combat_damage_block(roll_result, weapon)

    # ── Step 5: Assemble context package ──────────────────────────────
    story_summary = get_act_summaries(session_id)
    npc_states = load_npc_states(session_id, spine)
    turn_number = get_turn_count(session_id) + 1

    # Phase 8.5: Decay emotions + set from dice results (§25)
    for npc in npc_states:
        npc.decay_emotion()
        npc.nudge_disposition_from_emotion()
    if roll_result and check_decision.requires_check:
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
            open_threads=[
                ThreadState(name=t) if isinstance(t, str) else t
                for t in (
                    current_act.get("open_threads", [])
                    + arc_state.get("dynamic_threads", [])
                )
            ],
            closed_threads=arc_state.get("closed_threads", []),
            turns_this_act=arc_state.get("turns_this_act", 0),
            anchor_proximity=arc_state.get("anchor_proximity", "distant"),
            anchor_description=current_act.get("anchor_description", ""),
            obligation_active=arc_state.get("obligation_active", False),
            obligation_type=arc_state.get("obligation_type", ""),
            duty_active=arc_state.get("duty_active", False),
            duty_type=arc_state.get("duty_type", ""),
            morality_label=arc_state.get("morality_label", ""),
        ),
        story_summary=story_summary,
        recent_turns=recent_turns,
        active_npcs=npc_states,
        location=arc_state.get("current_location", ""),
        situation=scene_description,
        galactic_context=current_act.get("galactic_context", ""),
        scene_type=check_decision.scene_type,
        dice_pool=dice_pool,
        roll_result=roll_result,
        anchor_instruction=anchor_inst,
        expected_turns=current_act.get("expected_turns", [8, 12]),
        combat_damage_note=combat_damage_note,
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
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
            return

        # ── Step 7: Reconciliation (local model) ─────────────────────
        check_result_str = ""
        if roll_result:
            check_result_str = (
                f"{check_decision.skill} ({check_decision.difficulty}): "
                f"{roll_result.narrative_label()}"
            )

        recon_result = reconcile_turn(
            narration=narration_result.passage,
            player_action=player_action,
            check_result=check_result_str,
            active_npcs=npc_states,
            arc=ctx.arc,
            spine_act=current_act,
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
            context_json=None,
            scene_type=check_decision.scene_type,
            moral_weight=check_decision.moral_weight,
            skill_tags_json=json.dumps(narration_result.skill_tags),
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
            },
            "used_local_narration": narration_result.used_local,
            "act_boundary": act_boundary_reached,
        }
        yield f"event: done\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
