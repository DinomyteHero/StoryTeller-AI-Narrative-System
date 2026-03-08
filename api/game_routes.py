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
from gm.local_gm import annotate_choice, decide_check, run_prose_diagnostic
from state.db import get_connection
from state.memory import compress_if_needed, should_compress, compress_act_turns
from state.session import (
    create_session,
    get_act_summaries,
    get_recent_narrations,
    get_recent_turns,
    get_session,
    get_turn_count,
    load_ship_state,
    load_ship_states,
    log_turn,
    save_ship_state,
    update_destiny_pool,
)

router = APIRouter()

STREAMING_ENABLED = os.getenv("STREAMING_ENABLED", "true").lower() == "true"


@router.get("/campaigns")
async def list_campaigns():
    """List available campaigns with their character variants."""
    from pathlib import Path

    campaigns_dir = Path("data/campaigns")
    result = []
    for path in sorted(campaigns_dir.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            spine = json.load(f)
        characters = []
        for allegiance in spine.get("allegiances", []):
            for cv in allegiance.get("character_variants", []):
                characters.append({
                    "id": cv["id"],
                    "name": cv["id"].replace("_", " ").title(),
                    "pitch": cv.get("pitch", ""),
                    "career": cv.get("career", ""),
                    "species": cv.get("species", ""),
                })
        result.append({
            "campaign_name": path.stem,
            "display_name": spine.get("name", path.stem),
            "era": spine.get("era", ""),
            "throughline": spine.get("throughline_question", ""),
            "characters": characters,
        })
    return result


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
) -> str | None:
    """Run choice annotation and return JSON string or None.

    Called as a background thread so it doesn't block narration.
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
    )

    if annotation:
        return json.dumps(annotation)
    return None


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
        **motivation_flags,
    }

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
        ))

    # ── Initialize ship states from spine vehicle registry (§17) ──────
    for vehicle_entry in spine.get("vehicle_registry", []):
        ship = load_ship_from_spine(vehicle_entry)
        save_ship_state(session_id, ship)

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

    # Phase 16: Load ship states (§17) — primary ship for vehicle checks
    ships = load_ship_states(session_id)
    primary_ship = ships[0] if ships else None

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
        ship_state=primary_ship if primary_ship else None,
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
                for npc in load_npc_states(session_id, spine)
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
                    "turn_number": get_turn_count(session_id) + 1,
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
                    "turn_number": get_turn_count(session_id) + 1,
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
        )

    annotation_thread = threading.Thread(target=_annotation_thread, daemon=True)
    annotation_thread.start()

    # ── Phase 13: Prose diagnostic (§13) ──────────────────────────────
    recent_narrations = get_recent_narrations(session_id, limit=4)
    prose_diagnostic = None
    if len(recent_narrations) >= 2:
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
    turn_number = get_turn_count(session_id) + 1

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
                if (t if isinstance(t, str) else t.name)
                not in arc_state.get("closed_threads", [])
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
        talent_activations=talent_activations,
        destiny_narrative_note=(
            destiny_result.narrative_note if destiny_result else ""
        ),
        aspiration_echo_instructions=aspiration_echo,
        prose_diagnostic=prose_diagnostic,
        force_state_block=_force_state_block,
        force_result_block=_force_result_block,
        ship_state_block=(
            primary_ship.to_narration_block() if primary_ship
            and check_decision.scene_type == "space_combat" else ""
        ),
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

    # Phase 13: Wait for annotation thread to complete (§24)
    annotation_thread.join(timeout=5.0)  # don't block more than 5s
    choice_implications_json = annotation_result[0]

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
        choice_implications=choice_implications_json,
        force_result_json=(
            json.dumps(asdict(force_result)) if force_result else None
        ),
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

    # Phase 16: Load ship states (§17) — primary ship for vehicle checks
    ships_s = load_ship_states(session_id)
    primary_ship_s = ships_s[0] if ships_s else None

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
        ship_state=primary_ship_s if primary_ship_s else None,
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
                for npc in load_npc_states(session_id, spine)
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
                        "turn_number": get_turn_count(session_id) + 1,
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
                        "turn_number": get_turn_count(session_id) + 1,
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
        )

    annotation_thread_s = threading.Thread(
        target=_annotation_thread_stream, daemon=True,
    )
    annotation_thread_s.start()

    # ── Phase 13: Prose diagnostic (§13) ──────────────────────────────
    recent_narrations_s = get_recent_narrations(session_id, limit=4)
    prose_diagnostic_s = None
    if len(recent_narrations_s) >= 2:
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
    turn_number = get_turn_count(session_id) + 1

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
                if (t if isinstance(t, str) else t.name)
                not in arc_state.get("closed_threads", [])
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
        talent_activations=talent_activations,
        destiny_narrative_note=(
            destiny_result.narrative_note if destiny_result else ""
        ),
        aspiration_echo_instructions=aspiration_echo_s,
        prose_diagnostic=prose_diagnostic_s,
        force_state_block=_force_state_block_s,
        force_result_block=_force_result_block_s,
        ship_state_block=(
            primary_ship_s.to_narration_block() if primary_ship_s
            and check_decision.scene_type == "space_combat" else ""
        ),
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

        # Phase 13: Wait for annotation thread (§24)
        annotation_thread_s.join(timeout=5.0)
        choice_implications_json_s = annotation_result_stream[0]

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
            choice_implications=choice_implications_json_s,
            force_result_json=(
                json.dumps(asdict(force_result)) if force_result else None
            ),
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
    turn_number = get_turn_count(session_id) + 1
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
    scene_description = f"THE PLAYER CHOSE: {player_action}"

    anchor_inst = None
    if arc_state.get("act_progress", 0.0) >= 1.0:
        next_act_idx = arc_state["current_act"]
        next_act = (spine["acts"][next_act_idx]
                    if next_act_idx < spine["total_acts"] else None)
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
                if (t if isinstance(t, str) else t.name)
                not in arc_state.get("closed_threads", [])
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
        scene_type=pending.get("scene_type", "social"),
        dice_pool=dice_pool,
        roll_result=roll_result,
        anchor_instruction=anchor_inst,
        expected_turns=current_act.get("expected_turns", [8, 12]),
        combat_damage_note=combat_damage_note,
        talent_activations=talent_activations,
        destiny_narrative_note=pending.get("destiny_narrative_note", ""),
        force_state_block=_force_state_block,
        force_result_block=_force_result_block,
    )

    narration_result = narrate_turn(ctx)

    # Reconciliation
    check_result_str = ""
    if check_skill:
        check_difficulty = pending.get("check_difficulty", "")
        check_result_str = (
            f"{check_skill} ({check_difficulty}): "
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
        scene_type=pending.get("scene_type", "social"),
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
    turn_number = get_turn_count(session_id) + 1
    recent_turns = get_recent_turns(session_id, limit=5)

    for npc in npc_states:
        npc.decay_emotion()
        npc.nudge_disposition_from_emotion()
    _apply_emotion_from_check(
        npc_states, pending["check_skill"],
        roll_result.outcome_quadrant, turn_number,
    )

    player_action = pending["player_action"]
    scene_description = f"THE PLAYER CHOSE: {player_action}"

    anchor_inst = None
    if arc_state.get("act_progress", 0.0) >= 1.0:
        next_act_idx = arc_state["current_act"]
        next_act = (spine["acts"][next_act_idx]
                    if next_act_idx < spine["total_acts"] else None)
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
                if (t if isinstance(t, str) else t.name)
                not in arc_state.get("closed_threads", [])
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
        scene_type=pending["scene_type"],
        dice_pool=dice_pool,
        roll_result=roll_result,
        anchor_instruction=anchor_inst,
        expected_turns=current_act.get("expected_turns", [8, 12]),
        combat_damage_note=combat_damage_note,
        talent_activations=talent_activations,
        destiny_narrative_note=pending.get("destiny_narrative_note", ""),
    )

    narration_result = narrate_turn(ctx)

    # Reconciliation
    check_result_str = (
        f"{pending['check_skill']} ({pending['check_difficulty']}): "
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
        scene_type=pending["scene_type"],
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
