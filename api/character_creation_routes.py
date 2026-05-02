"""Character creation API — Phase 24.

These routes back the new front-loaded flow:

  GET  /game/backgrounds                 — list backgrounds for a campaign
  POST /game/select_background           — pick a background, return refinement state
  POST /game/refine_character            — submit refinement, get a draft session
  POST /game/prologue/{sid}/scene        — fetch the next prologue scene
  POST /game/prologue/{sid}/choose       — submit a prologue choice
  POST /game/prologue/{sid}/finalize     — close the prologue, start the game
  POST /game/{sid}/crystallize           — commit the profession choice

The prologue itself runs server-side as a state machine inside arc_state.
The opening narration of the campaign is generated only once the prologue
finalizes — until then, the player is in a draft pre-session that has not
yet incurred a cloud GM call.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from engine.character import Character, Pronouns
from engine.character_creation import (
    GENDER_MENU,
    PRONOUN_PRESETS,
    PrologueState,
    RefinementChoice,
    apply_crystallization_choice,
    apply_diegetic_payload,
    build_baseline_character,
    compute_crystallization_suggestion,
    finalize_prologue,
    initialize_prologue_state,
    lookup_background,
    lookup_npc_seed,
    record_prologue_choice,
    render_prologue_scene,
    resolve_pronouns,
)
from state.db import get_connection
from state.session import create_session, get_session


router = APIRouter()


# ── Request / response models ────────────────────────────────────────


class SelectBackgroundRequest(BaseModel):
    campaign_name: str
    background_id: str


class CustomPronouns(BaseModel):
    subject: str = "they"
    object: str = "them"
    possessive: str = "their"


class RefineRequest(BaseModel):
    campaign_name:        str
    background_id:        str
    name:                 Optional[str] = None
    species_id:           Optional[str] = None
    gender_id:            Optional[str] = None
    custom_pronouns:      Optional[CustomPronouns] = None
    skill_tilt_override:  Optional[dict[str, int]] = None
    appearance_flair:     Optional[str] = None


class PrologueChooseRequest(BaseModel):
    chosen_index:        int
    diegetic_payload:    Optional[dict] = None


class CrystallizeRequest(BaseModel):
    chosen_path_index: int


# ── Helpers ──────────────────────────────────────────────────────────


def _load_spine(campaign_name: str) -> dict:
    """Load a campaign spine. Mirrors api.game_routes.load_campaign_spine
    so we don't have to import from there (which would create a cycle
    once main.py wires both routers)."""
    filename = (campaign_name or "").lower().replace(" ", "_")
    if filename.startswith("the_"):
        filename = filename[4:]
    path = f"data/campaigns/{filename}.json"
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(404, f"Campaign not found: {campaign_name}")


def _load_session_with_character(session_id: str) -> tuple[dict, Character, dict, dict]:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(404, "Session not found")
    character = Character.model_validate_json(session["character_json"])
    arc_state = json.loads(session["arc_state_json"])
    spine = _load_spine(session["campaign_name"])
    return session, character, arc_state, spine


def _save_session_state(
    session_id: str, character: Character, arc_state: dict
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "UPDATE sessions SET character_json = ?, arc_state_json = ?, "
            "updated_at = ? WHERE id = ?",
            (
                character.model_dump_json(),
                json.dumps(arc_state),
                now,
                session_id,
            ),
        )
        conn.commit()


def _serialize_background(bg: dict) -> dict:
    """Trim a background entry down to player-facing fields."""
    return {
        "background_id": bg.get("background_id"),
        "display_name":  bg.get("display_name"),
        "story_seed":    bg.get("story_seed"),
        "default_names": list(bg.get("default_names", [])),
        "default_species": list(bg.get("default_species", [])),
        "default_skill_tilt": dict(bg.get("default_skill_tilt", {})),
        "pre_filled_relationship": dict(bg.get("pre_filled_relationship", {})),
        "unique_unlocks": [
            {"unlock_id": u.get("unlock_id"), "description": u.get("description")}
            for u in bg.get("unique_unlocks", [])
        ],
        "profession_affinities": dict(bg.get("profession_affinities", {})),
    }


def _populate_pre_filled_relationship(
    arc_state: dict, spine: dict, character: Character
) -> None:
    """Stash the background-pre-filled relationship into arc_state so the
    NPC-state init pass picks it up when the prologue finalizes.

    Format: arc_state['identity_prologue_seeded_relationship'] = {
      "npc_name": ..., "disposition_start": ..., "relationship": ...,
    }
    """
    bg_id = character.background or ""
    try:
        bg = lookup_background(spine, bg_id)
    except KeyError:
        return
    seed = bg.get("pre_filled_relationship") or {}
    if not seed:
        return
    arc_state["identity_prologue_seeded_relationship"] = {
        "npc_name":           seed.get("npc_name", ""),
        "npc_role":           seed.get("npc_role", ""),
        "initial_disposition": float(seed.get("initial_disposition", 0.5)),
        "relationship_summary": seed.get("relationship_summary", ""),
    }


def _make_refinement(req: RefineRequest) -> RefinementChoice:
    custom = None
    if req.custom_pronouns:
        custom = Pronouns(
            subject=req.custom_pronouns.subject,
            object=req.custom_pronouns.object,
            possessive=req.custom_pronouns.possessive,
        )
    return RefinementChoice(
        background_id=req.background_id,
        name=req.name,
        species_id=req.species_id,
        gender_id=req.gender_id,
        custom_pronouns=custom,
        skill_tilt_override=req.skill_tilt_override,
        appearance_flair=req.appearance_flair,
    )


# ── Routes ───────────────────────────────────────────────────────────


@router.get("/backgrounds")
async def list_backgrounds(campaign_name: str):
    """Return the list of backgrounds available for the campaign."""
    spine = _load_spine(campaign_name)
    backgrounds = spine.get("backgrounds", []) or []
    return {
        "campaign_name": campaign_name,
        "display_name":  spine.get("name", campaign_name),
        "era":           spine.get("era", ""),
        "backgrounds":   [_serialize_background(b) for b in backgrounds],
        "gender_menu":   GENDER_MENU,
        "pronoun_presets": PRONOUN_PRESETS,
    }


@router.post("/select_background")
async def select_background(req: SelectBackgroundRequest):
    """Return the refinement-screen state for a chosen background."""
    spine = _load_spine(req.campaign_name)
    try:
        bg = lookup_background(spine, req.background_id)
    except KeyError:
        raise HTTPException(404, f"Unknown background: {req.background_id}")

    return {
        "background": _serialize_background(bg),
        "story_seed": bg.get("story_seed", ""),
        "default_loadout_summary": (
            "Praxeum training robes, training lightsaber, archive datapad, "
            "two stimpacks. Background flavour woven through later additions."
        ),
        "gender_menu":     GENDER_MENU,
        "pronoun_presets": PRONOUN_PRESETS,
    }


@router.post("/refine_character")
async def refine_character(req: RefineRequest):
    """Build a draft Character from the refinement screen and create a
    session in the 'identity_prologue' stage. Does NOT generate any
    cloud narration yet — the prologue runs server-side as a state
    machine, and the opening cloud call happens at finalize_prologue.
    """
    spine = _load_spine(req.campaign_name)
    try:
        lookup_background(spine, req.background_id)
    except KeyError:
        raise HTTPException(404, f"Unknown background: {req.background_id}")

    # Build the character from the background + refinement picks
    refinement = _make_refinement(req)
    character = build_baseline_character(spine, refinement)

    # Initialize prologue state inside arc_state
    prologue_state = initialize_prologue_state(spine, character)
    arc_state: dict = {
        "stage": "identity_prologue",
        "current_act": 1,
        "act_progress": 0.0,
        "anchors_completed": [],
        "closed_threads": [],
        "dynamic_threads": [],
        "current_location": "Aboard the Horizon, descending toward Yavin 4",
        "turns_this_act": 0,
        "anchor_proximity": "distant",
        "destiny_light_spent_this_act": 0,
        "destiny_dark_spent_this_act": 0,
        "variant_id": refinement.background_id,
        "background_id": refinement.background_id,
        "identity_prologue_state": prologue_state.to_dict(),
    }
    _populate_pre_filled_relationship(arc_state, spine, character)

    # Persist a session
    session_id = create_session(
        campaign_name=req.campaign_name,
        character_json=character.model_dump_json(),
        arc_state_json=json.dumps(arc_state),
    )

    return {
        "session_id":              session_id,
        "stage":                   "identity_prologue",
        "character_summary": {
            "name":                 character.name,
            "species":              character.species.value if character.species else None,
            "career":               character.career.value,
            "background":           character.background,
            "appearance_flair":     character.appearance_flair,
            "skill_tilt":           dict(character.skill_tilt),
            "pre_crystallization":  character.is_pre_crystallization(),
        },
        "prologue_pending_slots":  list(prologue_state.diegetic_slots_pending),
        "prologue_total_scenes":   len(
            (spine.get("identity_prologue") or {}).get("scene_library", [])
        ),
    }


@router.post("/prologue/{session_id}/scene")
async def fetch_prologue_scene(session_id: str):
    """Return the current prologue scene rendered for the player's
    background."""
    _, character, arc_state, spine = _load_session_with_character(session_id)
    state_dict = arc_state.get("identity_prologue_state") or {}
    state = PrologueState.from_dict(state_dict)
    if state.stage != "prologue":
        return {"stage": state.stage, "scene": None}
    scene = render_prologue_scene(spine, state, character.background)
    return {
        "stage":              state.stage,
        "scene":              scene,
        "history_length":     len(state.history),
        "expected_total":     len(
            (spine.get("identity_prologue") or {}).get("scene_library", [])
        ),
    }


@router.post("/prologue/{session_id}/choose")
async def submit_prologue_choice(session_id: str, req: PrologueChooseRequest):
    """Apply one prologue choice. Returns the next-scene snapshot."""
    _, character, arc_state, spine = _load_session_with_character(session_id)
    state_dict = arc_state.get("identity_prologue_state") or {}
    state = PrologueState.from_dict(state_dict)
    if state.stage != "prologue":
        raise HTTPException(400, "Prologue is not active for this session")

    res = record_prologue_choice(
        spine, state, req.chosen_index, req.diegetic_payload
    )
    if not res.get("committed"):
        raise HTTPException(400, res.get("reason", "invalid_choice"))

    # If a diegetic slot was committed this turn, fold it onto the character
    diegetic = res.get("diegetic_committed") or {}
    if diegetic:
        apply_diegetic_payload(
            character, diegetic.get("slot_type", ""), diegetic.get("payload", {})
        )

    arc_state["identity_prologue_state"] = state.to_dict()
    _save_session_state(session_id, character, arc_state)

    next_scene = (
        render_prologue_scene(spine, state, character.background)
        if state.stage == "prologue"
        else None
    )
    return {
        "stage":              state.stage,
        "next_scene":         next_scene,
        "diegetic_committed": diegetic,
        "character_summary": {
            "name":             character.name,
            "appearance_flair": character.appearance_flair,
            "pronouns":         character.pronouns.model_dump() if character.pronouns else None,
        },
    }


@router.post("/prologue/{session_id}/finalize")
async def finalize_prologue_route(session_id: str):
    """Compute archetype + tilt + locks, write them to the character,
    and switch the session to the regular game loop. Does NOT generate
    cloud narration on its own — the caller is expected to immediately
    follow up with the existing /game/session-start flow.
    """
    _, character, arc_state, spine = _load_session_with_character(session_id)
    state_dict = arc_state.get("identity_prologue_state") or {}
    state = PrologueState.from_dict(state_dict)
    if state.stage != "complete":
        raise HTTPException(
            400, "Prologue is not complete; finish all scenes first."
        )

    summary = finalize_prologue(spine, character, state)

    arc_state["stage"] = "main_loop_pending_opening"
    arc_state["identity_prologue_state"] = state.to_dict()
    arc_state["prologue_summary"] = summary

    _save_session_state(session_id, character, arc_state)

    return {
        "stage":            arc_state["stage"],
        "session_id":       session_id,
        "summary":          summary,
        "character": {
            "name":                 character.name,
            "species":              character.species.value if character.species else None,
            "career":               character.career.value,
            "behavioral_archetype": character.behavioral_archetype,
            "background":           character.background,
            "skill_tilt":           dict(character.skill_tilt),
            "personality_locks": [
                {"axis": l.axis, "commitment_text": l.commitment_text}
                for l in character.personality_locks
            ],
            "pre_crystallization": character.is_pre_crystallization(),
        },
    }


@router.get("/session/{session_id}/crystallize")
async def crystallize_preview(session_id: str):
    """Return the suggested path + reasoning without committing it."""
    _, character, arc_state, spine = _load_session_with_character(session_id)
    cryst = spine.get("profession_crystallization") or {}
    if not cryst:
        raise HTTPException(404, "Campaign has no crystallization beat.")
    suggestion = compute_crystallization_suggestion(spine, character)
    paths = []
    bg_id = character.background or ""
    for i, p in enumerate(cryst.get("paths", [])):
        if p.get("background_specific_id") and p.get("background_specific_id") != bg_id:
            continue
        paths.append({
            "index":         i,
            "career_id":     p.get("career_id"),
            "display_name":  p.get("display_name"),
            "summary":       p.get("summary"),
            "talent_tree_id": p.get("talent_tree_id"),
            "background_specific": bool(p.get("background_specific_id")),
            "weight":        suggestion.weights[i] if i < len(suggestion.weights) else 0,
            "reasoning":     suggestion.reasoning[i] if i < len(suggestion.reasoning) else "",
            "is_suggested":  i == suggestion.suggested_path_index,
        })
    mentor = cryst.get("background_overrides", {}).get(bg_id) or cryst.get("mentor_npc", "Master")
    return {
        "session_id":              session_id,
        "anchor_act":              cryst.get("anchor_act", 3),
        "mentor_npc":              mentor,
        "scene_seed":              cryst.get("scene_seed", ""),
        "paths":                   paths,
        "suggested_path_index":    suggestion.suggested_path_index,
        "already_crystallized":    bool(character.crystallized),
        "current_career":          character.career.value,
    }


@router.post("/session/{session_id}/start_main_loop")
async def start_main_loop(session_id: str):
    """Boot the regular game loop on a session whose prologue has finalized.

    This is the bridge between the character-creation pipeline and the
    existing /session/{id}/turn handler. It generates the opening
    narration via the cloud GM and persists Turn 0, after which the
    frontend can call /session/{id}/turn as normal.
    """
    session, character, arc_state, spine = _load_session_with_character(session_id)
    if arc_state.get("stage") != "main_loop_pending_opening":
        raise HTTPException(
            400,
            f"Session is not ready for the main loop "
            f"(stage={arc_state.get('stage')})",
        )

    # Defer imports to runtime to avoid an import cycle with game_routes,
    # which itself imports modules that overlap with this router.
    from api.game_routes import (
        _initial_scene_state,
        _select_active_scene_npcs,
        _compute_dynamic_context_fields,
        _post_narration_drift_hook,
        _post_narration_reputation_hook,
        _apply_narration_scene_state,
        _context_audit_json,
        _thread_states_for_context,
        save_npc_state,
        load_npc_states,
        load_ship_from_spine,
        save_ship_state,
        resolve_initial_variations,
    )
    from gm.cloud_gm import narrate_turn
    from gm.context import (
        ArcState,
        ContextPackage,
        NPCState,
    )
    from engine.destiny import roll_initial_destiny
    from engine.reconciliation import roll_obligation_duty, apply_thread_updates
    from state.session import log_turn, update_destiny_pool

    act_1 = spine["acts"][0]

    # Apply Phase 8 motivation roll (hadn't fired yet because we deferred)
    motivation_flags = roll_obligation_duty(character)
    arc_state.update(motivation_flags)

    # Roll initial Destiny Pool
    destiny_light, destiny_dark = roll_initial_destiny()
    update_destiny_pool(session_id, destiny_light, destiny_dark)

    # Initialize NPC states from spine roster (only if not already populated)
    existing_states = load_npc_states(session_id, spine)
    seed_rel = arc_state.get("identity_prologue_seeded_relationship") or {}
    seeded_name = (seed_rel.get("npc_name") or "").strip()
    have_seed = any(
        npc.name.lower() == seeded_name.lower() for npc in existing_states
    ) if seeded_name else True
    if not have_seed and seeded_name:
        # The background's pre-filled NPC isn't in the spine roster — add a
        # minimal NPCState so the runtime knows about them. Their full profile
        # can be authored later.
        save_npc_state(session_id, NPCState(
            name=seeded_name,
            knows=[],
            doesnt_know=[],
            disposition=float(seed_rel.get("initial_disposition", 0.5)),
            voice_notes=seed_rel.get("relationship_summary", ""),
            motivation="",
            behavioral_envelope=[],
        ))

    # Initialize ship states from spine vehicle registry
    for vehicle_entry in spine.get("vehicle_registry", []):
        ship = load_ship_from_spine(vehicle_entry)
        save_ship_state(session_id, ship)

    # Resolve any spine-side variation points
    resolve_initial_variations(session_id, spine)

    # Build opening context package
    npc_states = load_npc_states(session_id, spine)
    arc_state["scene_state"] = _initial_scene_state(arc_state, act_1)
    opening_npcs = _select_active_scene_npcs(
        npc_states, arc_state, act_1, act_1.get("opening_situation", "")
    )

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
        story_summary=_post_prologue_story_summary(arc_state, character),
        recent_turns=[],
        active_npcs=opening_npcs,
        location=arc_state["scene_state"]["current_location"],
        situation=(
            f"{act_1['opening_situation']}\n\n"
            f"PROLOGUE OUTPUT:\n"
            f"{_format_prologue_summary(arc_state)}"
        ),
        galactic_context=act_1.get("galactic_context", ""),
        scene_type="exploration",
        tone_instruction=(
            "This is the opening of the main story, immediately following "
            "the Identity Prologue. The protagonist is a Praxeum student "
            "with a behavioral archetype but no committed discipline. "
            "Reference emergent leanings, not committed paths. Establish "
            "the world and the next concrete moment."
        ),
        expected_turns=act_1.get("expected_turns", [8, 12]),
        **dyn_fields_opening,
    )

    # Make the spine available to gm/cloud_gm._build_prompt for background_id
    # → story_seed resolution (Phase 24).
    ctx._spine_for_prompt = spine
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

    # Switch the session to the regular main-loop stage.
    arc_state["stage"] = "main_loop"
    _save_session_state(session_id, character, arc_state)

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

    return {
        "session_id":         session_id,
        "stage":              arc_state["stage"],
        "opening_narration":  narration_result.passage,
        "choices":            narration_result.choices,
    }


def _format_prologue_summary(arc_state: dict) -> str:
    """Format the prologue summary for the opening narration prompt."""
    summary = arc_state.get("prologue_summary") or {}
    if not summary:
        return "(prologue summary unavailable)"
    locks = summary.get("personality_locks") or []
    locks_block = "\n".join(
        f"  - {l.get('axis')}: {l.get('commitment_text')}"
        for l in locks
    )
    return (
        f"Behavioral archetype: {summary.get('behavioral_archetype', '')}\n"
        f"Archetype description: {summary.get('archetype_description', '')}\n"
        f"Personality locks (CoG-style multi-clause beliefs):\n"
        f"{locks_block or '  (none)'}"
    )


def _post_prologue_story_summary(arc_state: dict, character: Character) -> str:
    """Build a compact summary of what happened in the prologue, suitable
    for the cloud GM's story_summary slot at Turn 0."""
    state_dict = arc_state.get("identity_prologue_state") or {}
    history = state_dict.get("history") or []
    if not history:
        return ""
    lines = [
        "IDENTITY PROLOGUE COMPLETE — the protagonist arrived at Yavin 4 "
        "and went through four formative scenes.",
    ]
    for h in history:
        sid = h.get("scene_id", "?")
        tags = h.get("axis_tags") or {}
        formatted = ", ".join(f"{k}:{v}" for k, v in tags.items())
        lines.append(f"  · scene {sid}: {formatted}")
    arch = (arc_state.get("prologue_summary") or {}).get("behavioral_archetype", "")
    if arch:
        lines.append(f"Inferred behavioral archetype: {arch}")
    if character.background:
        lines.append(f"Background: {character.background}")
    return "\n".join(lines)


@router.post("/session/{session_id}/crystallize")
async def crystallize_commit(session_id: str, req: CrystallizeRequest):
    """Commit the profession crystallization choice."""
    _, character, arc_state, spine = _load_session_with_character(session_id)
    if character.crystallized:
        raise HTTPException(400, "Profession already crystallized.")
    cryst = spine.get("profession_crystallization") or {}
    if not cryst:
        raise HTTPException(404, "Campaign has no crystallization beat.")

    try:
        result = apply_crystallization_choice(
            spine, character, req.chosen_path_index
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    arc_state["crystallization_committed_turn"] = arc_state.get("turns_this_act", 0)
    _save_session_state(session_id, character, arc_state)

    return {
        "session_id":     session_id,
        "result":         result,
        "character": {
            "career":         character.career.value,
            "specializations": list(character.specializations),
            "crystallized":   character.crystallized,
        },
    }
