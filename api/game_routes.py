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
from dataclasses import asdict
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from engine.character import Character
from engine.checks import (
    CheckRequest,
    DIFFICULTY_LABELS,
    build_pool,
    describe_pool_for_display,
)
from engine.dice import roll_pool
from gm.cloud_gm import narrate_turn, NARRATIVE_BACKEND
from gm.context import (
    ArcState,
    ContextPackage,
    NPCState,
    ThreadState,
    TurnMemory,
)
from gm.local_gm import decide_check
from state.db import get_connection
from state.memory import compress_if_needed
from state.session import (
    create_session,
    get_act_summaries,
    get_recent_turns,
    get_session,
    get_turn_count,
    log_turn,
)

router = APIRouter()

OLLAMA_URL  = os.getenv("OLLAMA_URL", "http://localhost:11434")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "qwen3.5:9b")


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
        return [NPCState(**json.loads(r["state_json"])) for r in rows]

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


NPC_KNOWLEDGE_PROMPT = """You are analyzing a narrative passage from an RPG session to determine what NPCs learned.

PASSAGE:
{narration}

CURRENT NPC STATES:
{npc_states}

For each NPC present in the scene, list any NEW information they learned from this passage.
Return a JSON array. Each element: {{"npc_name": "...", "learned": ["fact 1", "fact 2"]}}
If no NPC learned anything new, return an empty array: []
Return ONLY valid JSON, no explanation."""


async def update_npc_knowledge(
    session_id: str, narration: str, npc_states: list[NPCState]
) -> None:
    """V1 minimal reconciliation — update NPC knowledge via local model."""
    if not npc_states:
        return
    try:
        npc_block = "\n".join(
            f"- {npc.name}: knows {npc.knows}" for npc in npc_states
        )
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": LOCAL_MODEL,
                    "prompt": NPC_KNOWLEDGE_PROMPT.format(
                        narration=narration, npc_states=npc_block
                    ),
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 200},
                },
                timeout=30.0,
            )
            response.raise_for_status()
            raw = response.json()["response"].strip()

            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            updates = json.loads(raw)
            if not isinstance(updates, list):
                return

            for update in updates:
                npc_name = update.get("npc_name")
                learned = update.get("learned", [])
                if not npc_name or not learned:
                    continue
                # Find and update the NPC
                with get_connection() as conn:
                    row = conn.execute(
                        "SELECT state_json FROM npc_states "
                        "WHERE session_id = ? AND npc_name = ?",
                        (session_id, npc_name),
                    ).fetchone()
                    if row:
                        state = json.loads(row["state_json"])
                        existing_knows = state.get("knows", [])
                        for fact in learned:
                            if fact not in existing_knows:
                                existing_knows.append(fact)
                        state["knows"] = existing_knows
                        now = datetime.now(timezone.utc).isoformat()
                        conn.execute(
                            "UPDATE npc_states SET state_json = ?, updated_at = ? "
                            "WHERE session_id = ? AND npc_name = ?",
                            (json.dumps(state), now, session_id, npc_name),
                        )
                        conn.commit()
    except Exception as e:
        logging.error(f"NPC knowledge update failed: {e}")


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

    # ── Initialize arc state ──────────────────────────────────────────
    arc_state = {
        "current_act": 1,
        "act_progress": 0.0,
        "anchors_completed": [],
        "closed_threads": [],
        "dynamic_threads": [],
        "current_location": act_1.get("opening_location", ""),
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
        context_json=(json.dumps(asdict(ctx))
                      if NARRATIVE_BACKEND != "local" else None),
    )

    return {
        "session_id": session_id,
        "opening_narration": narration_result.passage,
        "choices": narration_result.choices,
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
                    character.strain_threshold,
                )

    # ── Step 5: Assemble context package ──────────────────────────────
    story_summary = get_act_summaries(session_id)
    npc_states = load_npc_states(session_id, spine)

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
    )

    # ── Step 6: Narrate (cloud model — one call) ─────────────────────
    narration_result = narrate_turn(ctx)

    # ── Step 7: Persist ──────────────────────────────────────────────
    turn_number = get_turn_count(session_id) + 1

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
        context_json=(json.dumps(asdict(ctx))
                      if NARRATIVE_BACKEND != "local" else None),
        scene_type=check_decision.scene_type,
        moral_weight=check_decision.moral_weight,
        skill_tags_json=json.dumps(narration_result.skill_tags),
    )

    # ── Step 8: Update session state ──────────────────────────────────
    update_session_state(session_id, character, arc_state)

    # ── Step 9: Background tasks ──────────────────────────────────────
    background_tasks.add_task(
        compress_if_needed, session_id, arc_state["current_act"]
    )

    # ── Step 10: NPC state update (V1 minimal reconciliation) ────────
    background_tasks.add_task(
        update_npc_knowledge, session_id, narration_result.passage, npc_states
    )

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
        },
        "used_local_narration": narration_result.used_local,
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
