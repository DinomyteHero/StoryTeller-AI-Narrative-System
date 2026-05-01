"""
Context assembly for the Cloud GM.

Builds the ContextPackage that gets formatted into the narration prompt.
All narrative context — character state, arc position, NPC states, recent
turns, dice results — flows through this module.
"""

import re
from dataclasses import dataclass, field
from typing import Optional, Union
from engine.character import Character
from engine.dice import RollResult, DicePool


def compute_identity_drift_cue(
    arc_state: dict,
    character,
    turn_number: int,
    *,
    morality_threshold: int = 5,
    conflict_threshold: int = 3,
    cooldown_turns: int = 5,
) -> tuple[str, bool]:
    """Surface an interior cue when the protagonist has drifted identity-wise
    since the last surfacing.

    The system already tracks identity accumulation at act boundaries
    (motivation rolls, morality resolution). This closes the audit gap of
    drift not being *felt* turn-to-turn — when morality has shifted enough,
    or conflict has accumulated, or a motivation just activated, we drop a
    one-line interior note into the narration prompt.

    Returns:
      (cue, should_update_baseline)
      `cue` is empty when nothing surfaces.
      `should_update_baseline` is True iff the caller should refresh
      the drift baseline in arc_state after narration.
    """
    motivation = getattr(character, "motivation", None)
    if motivation is None:
        return "", False

    last_surface = int(arc_state.get("last_drift_surface_turn", 0) or 0)
    if turn_number - last_surface < cooldown_turns:
        return "", False

    current_morality = int(getattr(motivation, "morality", 50))
    current_conflict = int(getattr(motivation, "conflict", 0))

    baseline_morality = arc_state.get("drift_baseline_morality")
    if baseline_morality is None:
        # First call — seed baseline at current values, no surfacing yet.
        arc_state["drift_baseline_morality"] = current_morality
        arc_state["drift_baseline_conflict"] = current_conflict
        return "", False

    baseline_conflict = int(arc_state.get("drift_baseline_conflict", 0) or 0)
    morality_delta = current_morality - int(baseline_morality)
    conflict_delta = current_conflict - baseline_conflict

    cue = ""
    if abs(morality_delta) >= morality_threshold:
        if morality_delta < 0:
            cue = (
                "INTERIOR DRIFT: Lately the protagonist has felt their patience "
                "wear thinner — anger arrives faster, restraint feels like delay. "
                "If a beat allows it, surface this in a single line of interiority."
            )
        else:
            cue = (
                "INTERIOR DRIFT: Lately the protagonist has noticed restraint "
                "where there used to be heat. If a beat allows it, surface this "
                "in a single line of interiority — quiet, not declarative."
            )
    elif conflict_delta >= conflict_threshold:
        cue = (
            "INTERIOR DRIFT: There is a weight the protagonist is carrying that "
            "wasn't there before — choices accumulating at the edges of "
            "consciousness. If a beat allows it, surface this in a single line "
            "of interiority."
        )
    elif arc_state.get("obligation_just_activated"):
        cue = (
            "INTERIOR DRIFT: Old debts have been on the protagonist's mind. "
            "If a beat allows it, surface this in a single line of interiority — "
            "memory intruding on the present scene."
        )
    elif arc_state.get("duty_just_activated"):
        cue = (
            "INTERIOR DRIFT: The cause has been pulling at the protagonist's "
            "thoughts. If a beat allows it, surface this in a single line of "
            "interiority — purpose pressing in from elsewhere."
        )

    return cue, bool(cue)


def update_drift_baseline(
    arc_state: dict, character, turn_number: int
) -> None:
    """Refresh the drift baseline after a cue has been surfaced.

    Called from the api turn handler after narration completes when the
    cue was non-empty. Resets the comparison baseline so the next drift
    cue requires fresh accumulation.
    """
    motivation = getattr(character, "motivation", None)
    if motivation is None:
        return
    arc_state["last_drift_surface_turn"] = int(turn_number)
    arc_state["drift_baseline_morality"] = int(getattr(motivation, "morality", 50))
    arc_state["drift_baseline_conflict"] = int(getattr(motivation, "conflict", 0))
    # Clear the one-shot motivation activation flags so they don't fire twice.
    arc_state["obligation_just_activated"] = False
    arc_state["duty_just_activated"] = False


def compute_introspection_trigger(
    *,
    prev_turn_had_despair: bool,
    prev_turn_pinch_fired: bool,
    this_turn_has_check:   bool,
    turns_this_act:        int,
    consecutive_no_check_turns: int = 0,
) -> str:
    """Decide whether this turn should be quiet/introspective and return
    a tone instruction the narration prompt can consume.

    Three explicit conditions (audit closure for the open "introspection
    trigger logic" finding):

    1. **Post-Despair**: the previous turn rolled a Despair symbol — this
       turn's passage should slow down to register the cost.
    2. **Post-pinch-point**: a pinch point fired on the previous turn —
       the protagonist needs space to register the antagonist pressure
       before acting.
    3. **Mid-act dry spell**: this turn has no dice check, several turns
       into the act, and the recent run has been check-light — the
       narrative has been all conversation, an introspective beat
       re-grounds the protagonist.

    Returns an empty string when no trigger applies.
    """
    if prev_turn_had_despair:
        return (
            "INTROSPECTION TRIGGER (post-Despair): The protagonist is reeling "
            "from a critical setback on the previous beat. Slow this passage "
            "down. Open with one or two beats of interior reaction before the "
            "next exterior step. The world is quieter than it should be."
        )
    if prev_turn_pinch_fired:
        return (
            "INTROSPECTION TRIGGER (post-pinch-point): The antagonist's pressure "
            "just landed last beat. Give the protagonist a heartbeat to register "
            "what they saw before they choose how to respond. Show the cost on "
            "their face or in their thinking — not as exposition, as residue."
        )
    DRY_SPELL_TURNS = 3
    if (
        not this_turn_has_check
        and turns_this_act >= DRY_SPELL_TURNS
        and consecutive_no_check_turns >= 2
    ):
        return (
            "SCENE MOTION TRIGGER (mid-act dry spell): It has been several "
            "turns since the protagonist faced a real test of skill. Give the "
            "protagonist one brief interior beat, then change the external "
            "situation before the passage ends: an NPC interrupts, a clue "
            "surfaces, a location opens, a system fails, or pressure arrives. "
            "Do not leave the scene in the same static posture."
        )
    return ""


def resolve_variant(spine: dict, variant_id: str) -> Optional[dict]:
    """Look up a character variant by id from a campaign spine."""
    if not variant_id:
        return None
    for alg in spine.get("allegiances", []):
        for cv in alg.get("character_variants", []):
            if cv.get("id") == variant_id:
                return cv
    return None


def build_depth_card_block(spine: dict, variant_id: str) -> str:
    """Render the GM-facing CharacterDepthCard for the active variant.

    Empty when no depth card is populated. The card is GM-only enrichment —
    inner demon, secret yearning, social mask, etc. — never shown to the
    player but used by the narration model to give the protagonist
    psychological texture.
    """
    variant = resolve_variant(spine, variant_id)
    if not variant:
        return ""
    dc = variant.get("depth_card") or {}
    if not dc:
        return ""
    fields = (
        ("inner_demon",       "INNER DEMON"),
        ("secret_yearning",   "SECRET YEARNING"),
        ("lesson_not_learned", "LESSON NOT LEARNED"),
        ("worst_act",          "WORST ACT (carried forward)"),
        ("social_mask",        "SOCIAL MASK"),
        ("under_pressure",     "UNDER PRESSURE"),
        ("worldview",          "WORLDVIEW"),
        ("moral_line",         "MORAL LINE THEY WON'T CROSS"),
    )
    lines = ["CHARACTER DEPTH CARD (GM-only, do not surface to the player):"]
    for key, label in fields:
        value = (dc.get(key) or "").strip()
        if value:
            lines.append(f"  {label}: {value}")
    if len(lines) == 1:
        return ""
    lines.append(
        "Use these to color the protagonist's reactions, internal voice, "
        "and moments of friction. Never quote them; let them surface as "
        "behavior."
    )
    return "\n".join(lines)


def build_narrative_arc_block(character) -> str:
    """Render the Brooks/Weiland inner-story fields for the protagonist.

    Surfaces Lie / Ghost / Truth / Want / Need + arc_type + lie_grip to the
    narration model so prose can test the lie, echo the wound, and let the
    truth fight for ground. GM-only — never shown to the player.

    Returns empty string when narrative_arc is not populated.
    """
    arc = getattr(character, "narrative_arc", None)
    if not arc:
        return ""
    lie = (getattr(arc, "lie", "") or "").strip()
    if not lie:
        return ""
    ghost   = (getattr(arc, "ghost",  "") or "").strip()
    truth   = (getattr(arc, "truth",  "") or "").strip()
    want    = (getattr(arc, "want",   "") or "").strip()
    need    = (getattr(arc, "need",   "") or "").strip()
    arc_type = (getattr(arc, "arc_type", "positive") or "positive").strip().lower()
    grip    = float(getattr(arc, "lie_grip", 1.0))
    grip = max(0.0, min(1.0, grip))
    grip_pct = round(grip * 100)

    if   grip > 0.85: grip_label = "iron"
    elif grip > 0.55: grip_label = "loosening"
    elif grip > 0.30: grip_label = "cracking"
    else:             grip_label = "broken"

    arc_directions = {
        "positive": "Truth is winning over time. The Lie should weaken under "
                    "sustained pressure; the prose can let cracks show.",
        "flat":     "The character holds the Truth from the start. The world "
                    "tries to break them — the prose tests their conviction "
                    "rather than their belief.",
        "disillusionment": "The character will trade their Lie for a darker, "
                           "more honest Truth. Prose can let the old comfort "
                           "fall away in pieces.",
        "fall":     "The character clings harder to the Lie until it consumes "
                    "them. The prose lets each defense narrow them further.",
        "corruption": "The character is abandoning a Truth they once held for "
                      "a Lie that promises power. The prose can let small "
                      "compromises ladder.",
    }
    arc_dir = arc_directions.get(arc_type, arc_directions["positive"])

    lines = [
        "═══════════════════════════════════════════",
        "CHARACTER INNER STORY (GM-only — NEVER quote to the player):",
        "═══════════════════════════════════════════",
        f"  LIE the character believes:   {lie}",
    ]
    if ghost: lines.append(f"  GHOST (the wound behind it): {ghost}")
    if truth: lines.append(f"  TRUTH the story will teach:  {truth}")
    if want:  lines.append(f"  WANT  (the external goal):    {want}")
    if need:  lines.append(f"  NEED  (the internal need):    {need}")
    lines.append(f"  ARC TYPE: {arc_type} — {arc_dir}")
    lines.append(f"  CURRENT LIE GRIP: {grip_pct}% ({grip_label})")
    lines.append("")
    lines.append("HOW TO USE THIS:")
    lines.append("- The Lie shapes how this character interprets every "
                 "situation. It is the unconscious pattern.")
    lines.append("- The Ghost is the original wound. Reference it through "
                 "gesture, hesitation, or sensory echo — never explain it.")
    if grip_label == "iron":
        lines.append("- GRIP is iron: the character defends the Lie reflexively. "
                     "Resisting it should cost strain or feel physically wrong.")
    elif grip_label == "loosening":
        lines.append("- GRIP is loosening: small cracks show — a hesitation "
                     "before a reflexive choice, a flicker of doubt.")
    elif grip_label == "cracking":
        lines.append("- GRIP is cracking: the character glimpses the Truth in "
                     "flashes. They notice their own pattern but can't yet name it.")
    else:
        lines.append("- GRIP is broken: the character is acting on the Truth, "
                     "but the Lie still echoes — old reflexes surface under stress.")
    lines.append("- Choices should TEST the Lie. At least one choice each turn "
                 "should let the character either defend the Lie (the easier "
                 "path) or risk the Truth (the path that costs something).")
    lines.append("- Never exposit the Lie or Truth. Show them through behavior, "
                 "reaction, and the small refusals the character makes "
                 "without realizing they're refusing anything.")
    return "\n".join(lines)


_BEAT_ROLE_CUES = {
    # Brooks four-part structure
    "setup":         "PART 1 — SETUP. The world is still recognizable. The hook "
                     "must seed disturbance even when nothing has officially "
                     "broken. The inciting incident sits within reach.",
    "inciting":      "INCITING INCIDENT WINDOW. The disturbance arrives on "
                     "screen this act. The status quo is no longer tenable.",
    "first_plot_point": "FIRST PLOT POINT WINDOW (~25%). The protagonist must "
                        "cross into the new world. Old options begin to close. "
                        "No going back.",
    "response":      "PART 2A — RESPONSE. The protagonist is reactive, "
                     "wandering, learning the new rules. They are still the "
                     "orphan finding their footing.",
    "pinch1":        "PINCH POINT 1 WINDOW (~37%). The antagonistic force "
                     "demonstrates power on screen and wins something — a "
                     "resource, an ally, an option.",
    "midpoint":      "MIDPOINT WINDOW (~50%). An information shift. The "
                     "protagonist moves from wanderer to warrior. Earlier "
                     "scenes are recontextualized.",
    "attack":        "PART 3 — ATTACK. The protagonist is now proactive, "
                     "initiating, but still mistaking what victory looks like. "
                     "The Lie still rules their methods.",
    "pinch2":        "PINCH POINT 2 WINDOW (~62%). The antagonistic force "
                     "wins again, harder. The cost of the Lie becomes visible.",
    "second_plot_point": "SECOND PLOT POINT WINDOW (~75%). The final piece of "
                         "information. All-is-lost. No new information enters "
                         "after this — the rest of the story is choice and "
                         "consequence.",
    "climax":        "CLIMAX. The thematic decision. The protagonist must "
                     "choose between honoring the Lie (easier mechanically) "
                     "or honoring the Truth (the harder path that costs).",
    "resolution":    "PART 4 — RESOLUTION. The new equilibrium. What the "
                     "choices built. No new pressure introduced; only "
                     "consequence and recognition.",
    "destabilization": "DESTABILIZATION. The world tilts. Routine fractures.",
    "launch":        "LAUNCH. The protagonist commits and the new arena opens.",
    "midpoint_shift": "MIDPOINT SHIFT. Information reframes the story.",
    "escalation":    "ESCALATION. Stakes raise; the antagonist tightens grip.",
    "confrontation": "CONFRONTATION. Direct collision with the antagonistic force.",
    "consequence":   "CONSEQUENCE. The cost of choices is paid.",
}


def build_beat_role_block(spine_act: dict, act_progress: float) -> str:
    """Surface the Brooks beat the act + current progress is in.

    Reads `dramatic_function` (CS-6 field) and the milestone_beat_sheet
    in story_architecture to produce a one-line "story position" cue.
    Empty when no beat data is authored.
    """
    if not spine_act:
        return ""
    function = (spine_act.get("dramatic_function") or "").strip().lower()
    mode     = (spine_act.get("protagonist_mode") or "").strip().lower()
    cue = _BEAT_ROLE_CUES.get(function, "").strip()
    lines = []
    if cue:
        lines.append(f"STORY BEAT: {cue}")
    if mode:
        mode_hint = {
            "orphan":   "Protagonist is an ORPHAN — does not yet know the rules of this world.",
            "wanderer": "Protagonist is a WANDERER — reactive, still finding footing.",
            "warrior":  "Protagonist is a WARRIOR — proactive, initiating, but methods are imperfect.",
            "martyr":   "Protagonist is a MARTYR — acting in service of something larger than themselves.",
        }.get(mode, "")
        if mode_hint:
            lines.append(f"PROTAGONIST STANCE: {mode_hint}")
    # Layer on percentile cue for the climax / lull at the very end of the act
    try:
        progress = float(act_progress or 0.0)
    except (TypeError, ValueError):
        progress = 0.0
    if progress >= 0.85:
        lines.append("ACT IS ENDING: the act-level reveal or pivot must "
                     "land within the next two turns. Land it.")
    return "\n".join(lines)


def compute_pinch_point_instruction(
    spine_act: dict,
    act_progress: float,
    pinch_point_fired: bool,
) -> str:
    """Wraps engine.reconciliation.check_pinch_point so the live turn loop
    can fire pinch points at the right narrative beat (CS-6 Phase 2).
    """
    from engine.reconciliation import check_pinch_point
    return check_pinch_point(spine_act, act_progress, pinch_point_fired) or ""


def compute_closure_heartbeat_instruction(arc_state: dict) -> str:
    """Wrap engine.reconciliation.check_closure_heartbeat for the live turn loop.

    Reads the per-thread silence counter from arc_state and produces a
    narration prompt instruction when no thread has moved for several turns.
    Returns empty string when threads moved recently or no threads are open.
    """
    from engine.reconciliation import check_closure_heartbeat
    open_threads = arc_state.get("dynamic_threads", []) or []
    silence = int(arc_state.get("turns_since_last_thread_change", 0) or 0)
    instruction = check_closure_heartbeat(
        open_threads=open_threads,
        turns_since_last_thread_change=silence,
        threads_advanced_this_turn=[],
        threads_resolved_this_turn=[],
    )
    return instruction or ""


def compute_foreshadow_instruction(
    spine: dict,
    current_act_number: int,
    arc_state: dict,
) -> str:
    """Generate setup/payoff foreshadow instruction for the live turn loop.

    Two paths surface in priority order:
      1. **Payoff** — A registered foreshadow's `payoff_act` matches the
         current act and its setup was previously delivered. Highest priority
         because payoffs are time-sensitive.
      2. **Setup** — A registered foreshadow's `setup_act` matches the
         current act and the setup hasn't been delivered yet. Lower priority,
         occasional surfacing.

    Returns empty string when nothing matches. The narration prompt placeholder
    silently disappears.
    """
    if not isinstance(spine, dict):
        return ""
    registry = spine.get("foreshadow_registry") or []
    if not registry:
        return ""

    delivered = set(arc_state.get("foreshadow_setups_delivered", []) or [])

    # Pass 1: look for a payoff opportunity (setup delivered, payoff act now)
    for link in registry:
        link_id = link.get("id") if isinstance(link, dict) else None
        if not link_id or link_id not in delivered:
            continue
        payoff_act = int(link.get("payoff_act", 0) or 0)
        if payoff_act != current_act_number:
            continue
        if link_id in (arc_state.get("foreshadow_payoffs_delivered", []) or []):
            continue
        payoff_desc = (link.get("payoff_description") or "").strip()
        payoff_type = (link.get("payoff_type") or "callback").strip()
        if not payoff_desc:
            continue
        return (
            f"FORESHADOW PAYOFF ({payoff_type.upper()}): An earlier setup "
            f"is ready to land. Weave this beat into the passage when a "
            f"natural moment arrives — not as exposition, as recognition. "
            f"The payoff: {payoff_desc} "
            f"Reveal it through behavior, image, or a single line that the "
            f"player will recognize as the answer to a question planted earlier."
        )

    # Pass 2: surface a setup that has not yet been delivered
    for link in registry:
        link_id = link.get("id") if isinstance(link, dict) else None
        if not link_id or link_id in delivered:
            continue
        setup_act = int(link.get("setup_act", 0) or 0)
        if setup_act != current_act_number:
            continue
        setup_desc = (link.get("setup_description") or "").strip()
        if not setup_desc:
            continue
        return (
            f"FORESHADOW SETUP: Plant a small detail that will pay off later. "
            f"The setup: {setup_desc} "
            f"This should not announce itself. Drop it lightly — a passing "
            f"observation, an object on a shelf, a half-heard line — so the "
            f"reader registers it without weight, then remembers it later."
        )

    return ""


# Per-movement deltas applied to the protagonist's lie_grip (Weiland arc).
# The Lie is the same construct as the campaign's protagonist_contradiction;
# the same per-turn signal that updates the contradiction arc also nudges
# the lie_grip scalar toward 0 (Truth wins) or 1 (Lie wins). Magnitudes are
# small so a full act bends the arc rather than snapping it.
_LIE_GRIP_DELTAS = {
    "reinforced":  +0.05,  # leaned into the lie
    "cost_paid":   +0.02,  # the lie's cost surfaced but the lie still rules
    "resisted":    -0.05,  # acted against the lie
    "transformed": -0.10,  # explicit movement toward the truth
}


def accumulate_contradiction_arc(
    arc_state: dict,
    contradiction_tracking: dict,
    turn_number: int,
    character=None,
) -> None:
    """Aggregate per-turn contradiction tracking into the per-act arc block.

    Each turn's reconciliation returns a small contradiction_tracking record
    (engaged?, arc_movement, arc_evidence). This accumulator builds a
    multi-turn ledger on `arc_state["contradiction_arc"]` so the next turn's
    narration can see how the protagonist has been relating to their core
    contradiction across the act so far.

    When `character` is provided and has a populated `narrative_arc`, the
    same movement signal nudges the protagonist's `lie_grip` scalar so the
    Brooks/Weiland arc tracks live during play.
    """
    if not isinstance(contradiction_tracking, dict):
        return
    if not contradiction_tracking.get("contradiction_engaged"):
        return
    arc = arc_state.setdefault("contradiction_arc", {})
    movements: list = arc.setdefault("movements", [])
    movement = (contradiction_tracking.get("arc_movement") or "").strip()
    evidence = (contradiction_tracking.get("arc_evidence") or "").strip()
    if not movement or movement == "none":
        return
    movements.append({
        "turn": int(turn_number),
        "movement": movement,
        "evidence": evidence,
    })
    # Keep the ledger compact — the most recent 8 entries cover roughly the
    # current act for a normal-length act (8-12 turns).
    if len(movements) > 8:
        del movements[: len(movements) - 8]
    counts = arc.setdefault("counts", {})
    counts[movement] = int(counts.get(movement, 0)) + 1
    arc["last_engaged_turn"] = int(turn_number)

    # Update lie_grip on the protagonist's narrative_arc if present. Negative
    # arcs (fall, corruption) invert the deltas — leaning into the lie still
    # raises lie_grip, but the arc *trajectory* is opposite. We apply the
    # magnitude as authored; the arc_type is informative to the prose, not a
    # math toggle on the scalar itself.
    nar = getattr(character, "narrative_arc", None) if character else None
    if not nar or not getattr(nar, "lie", ""):
        return
    delta = _LIE_GRIP_DELTAS.get(movement, 0.0)
    if delta == 0.0:
        return
    new_grip = max(0.0, min(1.0, float(nar.lie_grip) + delta))
    nar.lie_grip = new_grip
    if nar.movements is None:
        nar.movements = []
    nar.movements.append({
        "turn":   int(turn_number),
        "kind":   movement,
        "delta":  round(delta, 3),
        "grip":   round(new_grip, 3),
        "note":   evidence[:160],
    })
    # Keep telemetry compact — most recent 16 movements is enough for two acts.
    if len(nar.movements) > 16:
        del nar.movements[: len(nar.movements) - 16]


def build_contradiction_arc_block(
    arc_state: dict, protagonist_contradiction: str = ""
) -> str:
    """Render the accumulated contradiction arc as a narration prompt block.

    Empty when no movements have accumulated. The block tells the GM where
    the protagonist's relationship to their core contradiction stands so
    the prose can echo or invert the dominant pattern.
    """
    arc = arc_state.get("contradiction_arc") or {}
    movements = arc.get("movements") or []
    if not movements:
        return ""
    counts = arc.get("counts") or {}
    dominant = max(counts.items(), key=lambda kv: kv[1])[0] if counts else ""
    recent = movements[-3:]

    lines = ["CHARACTER ARC STATE (protagonist contradiction):"]
    if protagonist_contradiction:
        lines.append(f"Core contradiction: {protagonist_contradiction}")
    if dominant:
        readable = {
            "reinforced":  "leaning into the contradiction",
            "resisted":    "actively pushing against the contradiction",
            "transformed": "the contradiction has begun to evolve",
            "cost_paid":   "paying real costs for the contradiction",
        }.get(dominant, dominant)
        lines.append(f"Dominant pattern this act: {readable}.")
    if recent:
        lines.append("Recent beats showing the pattern:")
        for entry in recent:
            evidence = entry.get("evidence") or ""
            movement = entry.get("movement") or ""
            if evidence:
                lines.append(f"  - turn {entry.get('turn')}: {movement} — {evidence}")
            else:
                lines.append(f"  - turn {entry.get('turn')}: {movement}")
    lines.append(
        "Let this turn's prose acknowledge the pattern — by reinforcing it, "
        "complicating it, or showing the cost — without naming it directly."
    )
    return "\n".join(lines)


def compute_voice_mode_instruction(prior_dramatic_mission: str) -> str:
    """Map the previous turn's dramatic mission to a voice instruction
    for THIS turn's narration (CS-6 Phase 10).

    Empty when no prior mission is known (turn 0, missing reconciliation).
    """
    if not prior_dramatic_mission:
        return ""
    try:
        from engine.dramatic_mission import MISSION_TO_VOICE, VOICE_INSTRUCTIONS
    except Exception:
        return ""
    voice_mode = MISSION_TO_VOICE.get(prior_dramatic_mission)
    if not voice_mode:
        return ""
    return VOICE_INSTRUCTIONS.get(voice_mode, "")


MEMORABLE_MOMENTS_CAP = 25
MEMORABLE_MOMENTS_CALLBACK_COOLDOWN = 4


def register_memorable_moment(
    arc_state: dict,
    *,
    turn_number: int,
    kind: str,
    summary: str,
    npc_names: Optional[list] = None,
    act_number: int = 0,
    weight: float = 1.0,
) -> None:
    """Append a memorable moment to the ledger, capping the rolling window.

    Lower-weight moments are evicted first when the cap is exceeded so
    pivotal beats outlast routine ones. Idempotent: a duplicate (same
    turn + kind) is silently dropped.
    """
    summary = (summary or "").strip()
    if not summary:
        return
    moments = arc_state.setdefault("memorable_moments", [])
    for existing in moments:
        if (
            int(existing.get("turn_number", -1)) == int(turn_number)
            and existing.get("kind", "") == kind
        ):
            return
    moments.append({
        "turn_number":        int(turn_number),
        "act_number":         int(act_number),
        "kind":               kind,
        "summary":            summary,
        "npc_names":          list(npc_names or []),
        "weight":             float(weight),
        "last_callback_turn": 0,
        "callback_count":     0,
    })
    # Cap with weight-aware eviction: drop the lowest-weight oldest first.
    if len(moments) > MEMORABLE_MOMENTS_CAP:
        moments.sort(key=lambda m: (m.get("weight", 1.0), m.get("turn_number", 0)))
        del moments[: len(moments) - MEMORABLE_MOMENTS_CAP]
        moments.sort(key=lambda m: m.get("turn_number", 0))


def select_callback_candidates(
    arc_state: dict,
    *,
    current_turn: int,
    scene_npc_names: list,
    max_count: int = 2,
) -> list[dict]:
    """Pick 0-2 memorable moments that fit this scene as callback candidates.

    Selection rules:
      1. Skip moments still in cooldown (last_callback_turn within
         MEMORABLE_MOMENTS_CALLBACK_COOLDOWN turns).
      2. Prefer moments involving NPCs present in this scene — they get
         a 0.5 weight boost.
      3. Prefer moments at least 3 turns old — fresh moments are still
         in recent_turns and don't need callback.
      4. Penalize already-recalled moments (callback_count) so the same
         moment doesn't dominate the campaign.
    """
    moments = arc_state.get("memorable_moments", []) or []
    if not moments:
        return []
    scored: list[tuple[float, dict]] = []
    scene_set = {str(n).lower() for n in (scene_npc_names or [])}
    for m in moments:
        last_callback = int(m.get("last_callback_turn", 0) or 0)
        if (
            last_callback
            and current_turn - last_callback < MEMORABLE_MOMENTS_CALLBACK_COOLDOWN
        ):
            continue
        age = current_turn - int(m.get("turn_number", 0) or 0)
        if age < 3:
            continue
        score = float(m.get("weight", 1.0))
        npcs = {str(n).lower() for n in (m.get("npc_names") or [])}
        if npcs & scene_set:
            score += 0.5
        score -= 0.25 * float(m.get("callback_count", 0))
        scored.append((score, m))
    scored.sort(key=lambda kv: kv[0], reverse=True)
    return [m for _, m in scored[:max_count]]


def mark_callback_surfaced(
    arc_state: dict,
    moment: dict,
    current_turn: int,
) -> None:
    """Mark a memorable moment as referenced so cooldown applies."""
    if not isinstance(moment, dict):
        return
    target_turn = int(moment.get("turn_number", -1))
    target_kind = moment.get("kind", "")
    for m in arc_state.get("memorable_moments", []) or []:
        if (
            int(m.get("turn_number", -2)) == target_turn
            and m.get("kind", "") == target_kind
        ):
            m["last_callback_turn"] = int(current_turn)
            m["callback_count"] = int(m.get("callback_count", 0)) + 1
            break


def build_memorable_moments_block(candidates: list) -> str:
    """Render selected callback candidates for the narration prompt.

    Empty when no candidates surface. The block invites — does not
    require — the LLM to weave one moment back into this scene as
    resonance, not exposition.
    """
    if not candidates:
        return ""
    lines = ["MEMORABLE MOMENTS (callback candidates — weave at most ONE):"]
    for moment in candidates:
        turn = moment.get("turn_number", 0)
        kind = moment.get("kind", "")
        summary = moment.get("summary", "")
        npcs = moment.get("npc_names") or []
        npc_str = f" (with {', '.join(npcs)})" if npcs else ""
        lines.append(f"  - Turn {turn} [{kind}]{npc_str}: {summary}")
    lines.append(
        "If a moment naturally fits this scene, surface it through behavior, "
        "image, or a half-line of interiority — never narrate the memory in "
        "full. The protagonist remembers; the world echoes. Do NOT manufacture "
        "a callback if none fits — it's better to let a turn breathe than to "
        "force resonance."
    )
    return "\n".join(lines)


# ── Tactical scene-grammar state (Phase D — combat/negotiation/chase) ──
#
# A unified "tactical_state" lives on arc_state when the active scene_type
# is one of combat / social / chase. Each scene type has its own sub-block
# format. Initialized when the player enters that scene type, advanced
# each turn, cleared when the player leaves the scene type.
#
# Structure:
#   tactical_state = {
#     "kind": "combat" | "negotiation" | "chase",
#     "round": int,
#     ... kind-specific fields ...
#   }
#
# These give each scene type its own *grammar* — rounds in combat, stages
# in negotiation, distance bands in chase — so single-check resolution
# layers against meaningful tactical state instead of a flat one-roll-
# per-turn loop.

VALID_TACTICAL_KINDS = ("combat", "negotiation", "chase")
RANGE_BANDS = ("engaged", "short", "medium", "long", "extreme")
NEGOTIATION_STAGES = ("opening", "probing", "pressure", "give_or_break", "concluded")
CHASE_ZONES = ("sighted", "closing", "neck_and_neck", "breaking_clear", "lost_or_caught")


def initialize_tactical_state(scene_type: str, *, situation: str = "") -> dict:
    """Initialize a fresh tactical_state when entering a tactical scene type.

    Returns an empty dict for non-tactical scene types so the prompt
    block silently disappears.
    """
    s = (scene_type or "").lower()
    if s == "combat":
        return {
            "kind": "combat",
            "round": 1,
            "range_band": "medium",
            "cover": False,
            "suppressed": False,
            "ally_position": "with_protagonist",
            "enemy_actions_log": [],
        }
    if s == "social":
        return {
            "kind": "negotiation",
            "round": 1,
            "stage": "opening",
            "positions_yielded": [],
            "positions_held": [],
            "walk_away_pressure": 0.0,  # 0.0 (calm) → 1.0 (NPC walks)
            "shared_ground": [],
        }
    if s == "chase":
        return {
            "kind": "chase",
            "round": 1,
            "zone": "sighted",
            "environment_hazards": [],
            "split_attempts": 0,
        }
    return {}


def advance_tactical_state(
    tactical_state: dict,
    *,
    outcome_quadrant: str = "",
    succeeded: bool = False,
    player_action: str = "",
) -> dict:
    """Advance the tactical state by one turn based on the dice outcome.

    Returns the same dict mutated. Pure heuristic — keeps the engine
    deterministic and the LLM informed without requiring per-turn
    structured updates from the model.
    """
    if not isinstance(tactical_state, dict):
        return {}
    kind = tactical_state.get("kind")
    tactical_state["round"] = int(tactical_state.get("round", 1) or 1) + 1
    pa = (player_action or "").lower()

    if kind == "combat":
        # Range band shifts based on player intent
        if any(k in pa for k in ("close", "charge", "engage", "melee", "rush")):
            tactical_state["range_band"] = _shift_range(tactical_state.get("range_band", "medium"), -1)
        elif any(k in pa for k in ("retreat", "back away", "fall back", "withdraw")):
            tactical_state["range_band"] = _shift_range(tactical_state.get("range_band", "medium"), +1)
        # Cover acquisition
        if any(k in pa for k in ("cover", "duck", "behind", "shelter", "wall")):
            tactical_state["cover"] = True
        elif any(k in pa for k in ("expose", "open", "advance into", "move forward")):
            tactical_state["cover"] = False
        # Suppression decays on success
        if succeeded:
            tactical_state["suppressed"] = False
        elif outcome_quadrant == "failure_threat":
            tactical_state["suppressed"] = True
        return tactical_state

    if kind == "negotiation":
        # Stage progression
        stages = list(NEGOTIATION_STAGES)
        cur = tactical_state.get("stage", "opening")
        idx = stages.index(cur) if cur in stages else 0
        if outcome_quadrant in ("success_advantage", "success_threat", "failure_advantage"):
            idx = min(len(stages) - 2, idx + 1)
            tactical_state["stage"] = stages[idx]
        # Walk-away pressure rises on harsh failures
        if outcome_quadrant == "failure_threat":
            tactical_state["walk_away_pressure"] = min(
                1.0, float(tactical_state.get("walk_away_pressure", 0.0) or 0.0) + 0.2
            )
        elif succeeded and outcome_quadrant == "success_advantage":
            tactical_state["walk_away_pressure"] = max(
                0.0, float(tactical_state.get("walk_away_pressure", 0.0) or 0.0) - 0.1
            )
        return tactical_state

    if kind == "chase":
        zones = list(CHASE_ZONES)
        cur = tactical_state.get("zone", "sighted")
        idx = zones.index(cur) if cur in zones else 0
        # Player succeeds → break clear; fails → close in
        if succeeded:
            idx = min(len(zones) - 1, idx + 1)
        elif outcome_quadrant == "failure_threat":
            idx = max(0, idx - 1)
        tactical_state["zone"] = zones[idx]
        return tactical_state

    return tactical_state


def _shift_range(current: str, direction: int) -> str:
    """Move range band by +1 (away) or -1 (closer). Clamped to RANGE_BANDS."""
    bands = list(RANGE_BANDS)
    idx = bands.index(current) if current in bands else bands.index("medium")
    idx = max(0, min(len(bands) - 1, idx + direction))
    return bands[idx]


def build_tactical_state_block(tactical_state: dict) -> str:
    """Render the tactical state for the narration prompt.

    Empty when no tactical state is active. The block tells the LLM both
    *where the scene is* (state) and *how to honor it* (instructions).
    """
    if not isinstance(tactical_state, dict) or not tactical_state.get("kind"):
        return ""
    kind = tactical_state["kind"]
    rnd = int(tactical_state.get("round", 1) or 1)

    if kind == "combat":
        band = tactical_state.get("range_band", "medium")
        cover = bool(tactical_state.get("cover", False))
        suppressed = bool(tactical_state.get("suppressed", False))
        lines = [
            f"COMBAT TACTICAL STATE (round {rnd}):",
            f"  Range band: {band.upper()}  (engaged = melee, short = pistol/sidearm, medium = ranged_light, long = ranged_heavy/sniper, extreme = limit of weapons)",
            f"  Cover: {'YES — protagonist behind something solid' if cover else 'NO — exposed, no concealment'}",
            f"  Suppressed: {'YES — enemy fire pinning the protagonist (next check inherits a setback die in narration even if not mechanically applied)' if suppressed else 'no'}",
            "  Combat is multi-round. This is not the only exchange. Show enemy reactions, allies adjusting, the environment shifting between rounds.",
            "  Tactical movement (closing range, breaking cover, moving to flank) is a real choice — at least one offered choice should change tactical posture, not just attack again.",
        ]
        return "\n".join(lines)

    if kind == "negotiation":
        stage = tactical_state.get("stage", "opening")
        pressure = float(tactical_state.get("walk_away_pressure", 0.0) or 0.0)
        yielded = tactical_state.get("positions_yielded", []) or []
        held = tactical_state.get("positions_held", []) or []
        shared = tactical_state.get("shared_ground", []) or []
        pressure_label = (
            "CRITICAL — the NPC is one wrong beat from walking" if pressure >= 0.7
            else "elevated — the NPC is guarded, considering whether to continue"
            if pressure >= 0.4 else "stable — both parties are still talking"
        )
        lines = [
            f"NEGOTIATION TACTICAL STATE (exchange {rnd}):",
            f"  Stage: {stage.upper().replace('_', ' ')}",
            f"  Walk-away pressure: {pressure_label}",
        ]
        if yielded:
            lines.append(f"  Positions the NPC has yielded: {'; '.join(yielded)}")
        if held:
            lines.append(f"  Positions the NPC is still holding: {'; '.join(held)}")
        if shared:
            lines.append(f"  Shared ground established: {'; '.join(shared)}")
        lines.extend([
            "  Negotiation is multi-stage. The NPC should make a counter-move, hold a line, or test the protagonist back this turn — not just respond to the player's last beat.",
            "  When the player succeeds, the NPC may concede ONE position but reveal a new one they will not yield. When the player fails harshly, the walk-away pressure rises and one offered choice should reflect that.",
        ])
        return "\n".join(lines)

    if kind == "chase":
        zone = tactical_state.get("zone", "sighted")
        hazards = tactical_state.get("environment_hazards", []) or []
        zone_descriptions = {
            "sighted":           "The pursuer is in view but not closing fast — the protagonist has moves to make.",
            "closing":           "The gap is shrinking. Each turn matters.",
            "neck_and_neck":     "They are right behind. A wrong choice ends the chase.",
            "breaking_clear":    "The protagonist has opened daylight. One more good beat and they're gone.",
            "lost_or_caught":    "The chase resolves this turn — either escape or be caught.",
        }
        lines = [
            f"CHASE TACTICAL STATE (round {rnd}):",
            f"  Zone: {zone.upper().replace('_', ' ')} — {zone_descriptions.get(zone, '')}",
        ]
        if hazards:
            lines.append(f"  Environmental hazards in play: {'; '.join(hazards)}")
        lines.extend([
            "  The geography of the pursuit must shift between rounds. Don't replay the same alley.",
            "  At least one offered choice should let the protagonist exploit the environment (a shortcut, a hazard, a hiding spot, a misdirection) rather than just running faster.",
        ])
        return "\n".join(lines)

    return ""


def build_evolved_voice_block(character) -> str:
    """Surface in-character voice deltas the static voice_notes can't capture.

    The static voice_notes set at character creation never updates. This
    helper layers dynamic modifiers on top so the prose actually shifts
    as the character grows, breaks, or hardens. Empty string when nothing
    distinguishes the current state from the baseline.

    Inputs that influence voice:
      - Morality band (Force-sensitive only) — light vs grey vs dark
      - Conflict accumulation — internal moral pressure
      - Wounds / strain ratio — fatigue, near-incapacitation
      - Recent talent acquisitions — newly internalized identity facets
      - Active injuries — long-term physical signature
      - Force rating — increasing attunement
    """
    if character is None:
        return ""

    deltas: list[str] = []

    motivation = getattr(character, "motivation", None)
    morality = int(getattr(motivation, "morality", 50) or 50)
    conflict = int(getattr(motivation, "conflict", 0) or 0)
    force_rating = int(getattr(character, "force_rating", 0) or 0)

    if force_rating > 0:
        if morality <= 30:
            deltas.append(
                "DARK-LEANING VOICE: Sentences land harder; restraint feels "
                "like delay. Heat is closer to the surface than it used to be. "
                "When the character considers cruelty, they don't recoil from "
                "the thought as quickly as they once would have."
            )
        elif morality >= 71:
            deltas.append(
                "LIGHT-LEANING VOICE: There is a quiet centeredness to the "
                "character now — pauses where there used to be reaction, "
                "patience where there used to be reach. The character notices "
                "fear in others before they notice it in themselves."
            )
    if conflict >= 5:
        deltas.append(
            "ACCUMULATED CONFLICT: The character is carrying decisions that "
            "are not yet resolved. Let the prose show small frictions — a "
            "tightness that wasn't there, a sentence that doesn't quite finish, "
            "a half-second of silence at the wrong moment."
        )

    wounds = int(getattr(character, "current_wounds", 0) or 0)
    wound_threshold = int(getattr(character, "wound_threshold", 0) or 0)
    if wound_threshold and wounds / max(1, wound_threshold) >= 0.7:
        deltas.append(
            "BATTERED PHYSICALITY: The character is hurt. Movement carries "
            "cost. Don't narrate every wince — but let the body's negotiation "
            "with motion be felt in the prose's rhythm and detail."
        )
    strain = int(getattr(character, "current_strain", 0) or 0)
    strain_threshold = int(getattr(character, "strain_threshold", 0) or 0)
    if strain_threshold and strain / max(1, strain_threshold) >= 0.7:
        deltas.append(
            "FRAYED COMPOSURE: The character is at the edge of their patience "
            "and focus. Reactions sharper, deliberation thinner, dialogue "
            "less measured than it would be on a rested day."
        )

    injuries = list(getattr(character, "active_injuries", []) or [])
    if injuries:
        deltas.append(
            f"ACTIVE INJURIES (long-term physical signature): {'; '.join(injuries)}. "
            "Let one of these surface as small, specific behavior when "
            "appropriate — a favored hand, a hesitated step."
        )

    talents = list(getattr(character, "acquired_talents", []) or [])
    if talents:
        recent = talents[-2:]
        recent_names: list[str] = []
        for t in recent:
            name = ""
            if isinstance(t, dict):
                name = (
                    t.get("narrative_identity")
                    or t.get("display_name")
                    or t.get("name")
                    or t.get("talent_ref")
                    or ""
                )
            else:
                name = str(t)
            if name:
                recent_names.append(name.strip())
        if recent_names:
            deltas.append(
                "RECENT INTERNALIZATIONS: The character has recently grown "
                f"into: {' | '.join(recent_names)}. These are still settling — "
                "let them surface as new instinct or unfamiliar capacity, not "
                "as fluent identity yet."
            )

    if not deltas:
        return ""
    return "EVOLVED VOICE (overlay these deltas on the baseline character voice):\n\n" + "\n\n".join(deltas)


def build_background_block(character, spine: Optional[dict] = None) -> str:
    """Surface character background as a prompt section the LLM can mine.

    The background field is canonically authored at character creation
    and never changes — but it shapes what the protagonist notices, why
    certain images recur, what they instinctively reach for. This block
    makes that available as living context, not just metadata.
    """
    if character is None:
        return ""
    background = (getattr(character, "background", "") or "").strip()
    if not background:
        return ""
    return (
        "PROTAGONIST BACKGROUND (use to shape what the character notices, "
        "what they reach for instinctively, what images recur — never quote "
        "the background back at the player as exposition):\n"
        f"{background}"
    )


def build_lore_seeds_block(spine: Optional[dict]) -> str:
    """Render the campaign-level sensory/lore seeds for atmosphere consistency.

    Spine schema (optional):
      lore_seeds: {
        sensory:  ["smell of jungle rot", "the way the temple stone is warm at midday"],
        ritual:   ["the Praxeum's morning meditation chime"],
        objects:  ["Tionne's recordings", "salvaged crystals from Yavin's ruins"],
      }
    Empty when no seeds are declared. The LLM is invited to weave these
    in occasionally so the world feels lived-in across turns.
    """
    if not isinstance(spine, dict):
        return ""
    seeds = spine.get("lore_seeds") or {}
    if not isinstance(seeds, dict) or not any(seeds.values()):
        return ""
    lines = ["LORE SEEDS (sensory anchors — weave occasionally for world consistency):"]
    for key, label in (
        ("sensory",  "Sensory"),
        ("ritual",   "Rituals"),
        ("objects",  "Significant objects"),
        ("language", "Period language / phrasing"),
    ):
        items = seeds.get(key) or []
        if not items:
            continue
        rendered = "; ".join(str(x) for x in items[:6])
        lines.append(f"  {label}: {rendered}")
    if len(lines) == 1:
        return ""
    return "\n".join(lines)


def build_era_voice_block(spine: dict) -> str:
    """Render the ERA VOICE block from spine.era_voice if present.

    Star Wars spans multiple distinct eras (High Republic, Fall of the
    Republic, Imperial Era, New Republic, Sequel Era). Each has its own
    period details, technology level, political reality, and prose
    register. When a spine declares an era, the GM gets specific
    instructions to keep the prose anchored in that moment.

    Spine schema (optional):
      era_voice: {
        era:            "Imperial Era",          # canon era name
        year:           "5 BBY",                  # ABY/BBY date
        voice_notes:    "...",                    # 1-3 sentences of tone guidance
        period_details: ["Empire is ascendant", "Rebellion is whispered"],
        period_avoid:   ["lightsabers in casual hands", "Rebels in uniform"],
      }

    Returns empty string when era_voice is missing — the GM falls back
    to the campaign-level Star Wars guidance.
    """
    if not isinstance(spine, dict):
        return ""
    era = spine.get("era_voice", {})
    if not era or not isinstance(era, dict):
        return ""

    era_name       = (era.get("era") or "").strip()
    year           = (era.get("year") or "").strip()
    voice_notes    = (era.get("voice_notes") or "").strip()
    period_details = era.get("period_details", []) or []
    period_avoid   = era.get("period_avoid", []) or []

    if not (era_name or voice_notes or period_details):
        return ""

    lines = ["ERA VOICE:"]
    if era_name:
        header = f"Era: {era_name}"
        if year:
            header += f" ({year})"
        lines.append(header)
    if voice_notes:
        lines.append(voice_notes)
    if period_details:
        lines.append("Period anchors (weave in occasionally, do not list):")
        for detail in period_details[:5]:
            lines.append(f"  - {detail}")
    if period_avoid:
        lines.append("Anachronisms to avoid:")
        for detail in period_avoid[:5]:
            lines.append(f"  - {detail}")

    return "\n".join(lines)


# Phase 8.5: Decay rates per mood (§25.3) — intensity reduction per turn.
# Updated April 2026: rates reduced for high-stakes moods so betrayal-class
# emotions don't evaporate in 7 turns. Couples with HIGH_INTENSITY_DECAY_MULT
# below — when an emotion is set with intensity >= 0.6, decay is further
# halved so deeply set emotions persist across an act, not just a scene.
MOOD_DECAY_RATES = {
    "calm": 0.0,
    "angry": 0.06,        # was 0.15 — betrayal anger now lasts ~17 turns
    "afraid": 0.05,       # was 0.10
    "grieving": 0.03,     # was 0.05 — grief lingers
    "suspicious": 0.04,   # was 0.08 — suspicion is sticky
    "grateful": 0.10,     # was 0.20 — gratitude lingers longer
    "desperate": 0.08,    # was 0.12
    "amused": 0.20,       # was 0.25 — humor still fades fast
    "conflicted": 0.03,   # was 0.05 — internal conflict resolves slowly
    # New high-stakes moods that should persist across acts
    "betrayed":   0.02,   # cuts deepest, fades slowest
    "awed":       0.04,   # genuine awe imprints
    "bonded":     0.03,   # forged trust persists
}

# When an emotion is set with intensity at or above this threshold, decay is
# multiplied by HIGH_INTENSITY_DECAY_MULT — a sharp moment lingers longer
# than a passing one.
HIGH_INTENSITY_THRESHOLD = 0.6
HIGH_INTENSITY_DECAY_MULT = 0.5

# Moods that nudge disposition negatively when sustained (3+ turns)
NEGATIVE_MOODS = {"angry", "suspicious", "afraid"}
# Moods that nudge disposition positively when sustained
POSITIVE_MOODS = {"grateful"}

# CS-6 Phase 4: Pressure role → dramatic instruction mapping
PRESSURE_ROLE_INSTRUCTIONS = {
    "tempter": "offers easy but costly shortcuts",
    "mirror": "reflects the protagonist's flaws back at them",
    "skeptic": "challenges the protagonist's assumptions",
    "dependent": "needs the protagonist, creating obligation pressure",
    "betrayer": "appears allied but serves a conflicting agenda",
    "witness": "observes and judges, creating accountability pressure",
    "escalator": "raises stakes by acting independently, creating time pressure",
    "false_ally": "genuinely wants to help but makes things worse",
    "catalyst": "forces decisions by creating time pressure",
}


def _pressure_role_instruction(role: str) -> str:
    return PRESSURE_ROLE_INSTRUCTIONS.get(role, f"applies dramatic pressure as {role}")


@dataclass
class EmotionalState:
    """Transient emotional overlay on an NPC (§25)."""
    mood:        str = "calm"       # constrained vocabulary above
    intensity:   float = 0.0       # 0.0 to 1.0
    source:      str = ""          # what caused this emotion
    set_at_turn: int = 0           # when it was set
    decay_rate:  float = 0.0       # intensity drop per turn (auto-set from mood)
    sustained_turns: int = 0       # consecutive turns in non-calm state

    def is_active(self) -> bool:
        return self.mood != "calm" and self.intensity >= 0.1

    def to_dict(self) -> dict:
        return {
            "mood": self.mood, "intensity": self.intensity,
            "source": self.source, "set_at_turn": self.set_at_turn,
            "decay_rate": self.decay_rate, "sustained_turns": self.sustained_turns,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EmotionalState":
        if not d:
            return cls()
        return cls(
            mood=d.get("mood", "calm"),
            intensity=d.get("intensity", 0.0),
            source=d.get("source", ""),
            set_at_turn=d.get("set_at_turn", 0),
            decay_rate=d.get("decay_rate", MOOD_DECAY_RATES.get(d.get("mood", "calm"), 0.0)),
            sustained_turns=d.get("sustained_turns", 0),
        )


@dataclass
class NPCState:
    name:                str
    knows:               list[str] = field(default_factory=list)
    doesnt_know:         list[str] = field(default_factory=list)
    disposition:         float = 0.5   # 0.0 (hostile) to 1.0 (loyal)
    last_seen_turn:      int = 0
    voice_notes:         str = ""
    motivation:          str = ""
    behavioral_envelope: list[str] = field(default_factory=list)  # hard "never" constraints
    emotional_state:     EmotionalState = field(default_factory=EmotionalState)  # Phase 8.5 (§25)
    # The single sharpest impression this NPC carries of the protagonist.
    # Set by crystallize_memory() when a turn produces a defining moment
    # (betrayal, sacrifice, unexpected mercy, witnessed cruelty). Does not
    # decay. Surfaces in the NPC prompt block so the LLM can let this
    # memory color speech, behavior, and silence in every future scene.
    crystallized_memory:      str = ""
    crystallized_memory_turn: int = 0

    def disposition_label(self) -> str:
        """Human-readable label for prompt injection."""
        if self.disposition >= 0.8:   return "loyal"
        if self.disposition >= 0.6:   return "friendly"
        if self.disposition >= 0.4:   return "neutral"
        if self.disposition >= 0.2:   return "wary"
        return "hostile"

    def set_emotion(self, mood: str, intensity: float, source: str, turn: int):
        """Set a new emotional state (§25.2). Replaces current emotion.

        High-intensity emotions decay slower (HIGH_INTENSITY_DECAY_MULT)
        so a sharply set emotion lingers across an act, not just a scene.
        """
        clamped = min(1.0, max(0.0, intensity))
        decay = MOOD_DECAY_RATES.get(mood, 0.10)
        if clamped >= HIGH_INTENSITY_THRESHOLD:
            decay *= HIGH_INTENSITY_DECAY_MULT
        self.emotional_state = EmotionalState(
            mood=mood, intensity=clamped,
            source=source, set_at_turn=turn, decay_rate=decay,
            sustained_turns=0,
        )

    def decay_emotion(self):
        """Apply one turn of emotional decay (§25.3)."""
        es = self.emotional_state
        if not es.is_active():
            return
        es.intensity = max(0.0, es.intensity - es.decay_rate)
        es.sustained_turns += 1
        if es.intensity < 0.1:
            self.emotional_state = EmotionalState()  # reset to calm

    def crystallize_memory(self, memory: str, turn: int) -> None:
        """Imprint a sharp, non-decaying impression of the player.

        Used when an event is significant enough to permanently shape this
        NPC's view of the protagonist (a betrayal, a sacrifice, a moment of
        unexpected mercy). The latest crystallized memory replaces any prior
        one — an NPC has one sharpest impression at a time, not a stack.
        """
        memory = (memory or "").strip()
        if not memory:
            return
        self.crystallized_memory = memory
        self.crystallized_memory_turn = int(turn)

    def nudge_disposition_from_emotion(self):
        """If sustained 3+ turns in non-calm state, nudge disposition (§25.5)."""
        es = self.emotional_state
        if es.sustained_turns < 3 or not es.is_active():
            return
        if es.mood in NEGATIVE_MOODS:
            self.disposition = max(0.0, self.disposition - 0.02)
        elif es.mood in POSITIVE_MOODS:
            self.disposition = min(1.0, self.disposition + 0.02)

    # CS-6 Phase 4: NPC pressure role
    pressure_role: str = ""

    def to_prompt_block(self) -> str:
        lines = [f"{self.name}:"]
        if self.knows:
            lines.append(f"  Knows: {'; '.join(self.knows)}")
        if self.doesnt_know:
            lines.append(f"  Doesn't know: {'; '.join(self.doesnt_know)}")
        lines.append(f"  Disposition: {self.disposition_label()} ({self.disposition:.2f})")
        # Phase 8.5: emotional state overlay (§25.4)
        if self.emotional_state.is_active():
            es = self.emotional_state
            lines.append(f"  Currently: {es.mood} (intensity {es.intensity:.1f}) — {es.source}")
        # Crystallized memory — the sharpest impression this NPC holds of
        # the protagonist. Persists across the campaign. Tells the LLM how
        # this NPC's silence, posture, and cadence should color when
        # they're around the player.
        if self.crystallized_memory:
            lines.append(
                f"  Sharpest memory of protagonist: {self.crystallized_memory} "
                f"(let this color tone, posture, and silence — never quote it directly)"
            )
        if self.voice_notes:
            lines.append(f"  Voice: {self.voice_notes}")
        if self.motivation:
            lines.append(f"  Wants: {self.motivation}")
        if self.behavioral_envelope:
            lines.append(f"  Never: {'; '.join(self.behavioral_envelope)}")
        # CS-6 Phase 4: pressure role instruction
        if self.pressure_role:
            lines.append(f"  Pressure role: {self.pressure_role.upper()} — {_pressure_role_instruction(self.pressure_role)}")
        return "\n".join(lines)


@dataclass
class TurnMemory:
    turn_number:            int
    player_action:          str
    narration_excerpt:      str = ""     # v2.4: first 2-3 sentences of passage (evaluation §2.2)
    check_made:             Optional[str] = None
    dice_result:            Optional[str] = None
    outcome_quadrant:       Optional[str] = None
    meaningful_choice_note: str = ""


VALID_THREAD_STATUSES = (
    "dormant",                  # known to exist, no recent movement
    "active",                   # currently being explored
    "hot",                      # the player is pressing on it right now
    "approaching_resolution",   # close to closing — pieces are converging
    "resolved_pending_fallout", # closed, but consequences still rippling
    "closed",                   # fully closed, no longer surfaces
)


@dataclass
class ThreadState:
    """Stateful thread tracking — name + what's known/unknown + status.

    Status promotion (April 2026): a binary open/closed model couldn't
    distinguish "the player just discovered the body" from "the player
    has been ignoring this for 6 turns." Multi-stage status lets the
    narration prompt see thread momentum and lets the LLM lay
    consequences from `resolved_pending_fallout` threads even after
    they've left the immediate spotlight.
    """
    name:           str
    player_knows:   list[str] = field(default_factory=list)
    player_unknown: list[str] = field(default_factory=list)
    status:         str = "active"          # see VALID_THREAD_STATUSES
    hot_question:   str = ""                # one-line: "what is at stake right now?"
    progress:       float = 0.0             # 0.0 (just opened) → 1.0 (resolved)
    last_movement_turn: int = 0
    fallout_remaining_turns: int = 0        # decrements while resolved_pending_fallout

    def status_label(self) -> str:
        """Human-readable status for the prompt block."""
        return {
            "dormant":                  "DORMANT (no recent movement)",
            "active":                   "ACTIVE",
            "hot":                      "HOT (player is pressing this now)",
            "approaching_resolution":   "APPROACHING RESOLUTION",
            "resolved_pending_fallout": "RESOLVED (consequences still rippling)",
            "closed":                   "CLOSED",
        }.get(self.status, self.status.upper())


@dataclass
class MemorableMoment:
    """A scene worth referencing later in the campaign.

    Auto-flagged when a turn crosses one of several emotional/mechanical
    thresholds (Triumph, Despair, large disposition shift, thread resolved,
    motivation activation, force temptation accepted, milestone fired).
    The narration prompt receives a callback candidate so the LLM can
    weave intimate or weighty earlier moments back into present scenes —
    not as exposition, as resonance.
    """
    turn_number:  int
    act_number:   int = 0
    kind:         str = ""              # "triumph", "despair", "betrayal", "intimacy", ...
    summary:      str = ""              # one sentence — the moment in present-tense flavor
    npc_names:    list[str] = field(default_factory=list)
    weight:       float = 1.0           # 0.0–2.0, controls callback priority
    last_callback_turn: int = 0         # cooldown so the same moment doesn't repeat
    callback_count: int = 0


@dataclass
class ArcState:
    campaign_name:        str
    current_act:          int
    total_acts:           int
    act_name:             str
    act_progress:         float
    current_anchor:       str
    next_anchor:          str
    anchors_completed:    list[str]
    throughline_question: str
    tension_level:        str
    open_threads:         list[ThreadState]  # v2.4: structured threads with state (evaluation §2.2)
    closed_threads:       list[str]
    turns_this_act:       int = 0            # v2.5: incremented each turn, reset at act boundary (§26)
    anchor_proximity:     str = "distant"    # v2.5: distant/approaching/imminent/reached (§26.3)
    anchor_description:   str = ""           # v2.5: narrative description of the anchor beat (§26.4)
    # Phase 8: Motivation track (§9)
    obligation_active:    bool = False
    obligation_type:      str = ""           # e.g. "Debt", "Family"
    duty_active:          bool = False
    duty_type:            str = ""
    morality_label:       str = ""           # "Light side dominant" / "Grey" / "Dark side dominant"
    # CS-6 Phase 2: Pinch point tracking
    pinch_point_fired:    bool = False        # Reset at act boundary
    # CS-6 Phase 5: Foreshadow tracking
    foreshadow_setups_delivered: list = field(default_factory=list)  # IDs of delivered setups
    # Reputation echo cooldown (Game Mechanics §1, §11). Tracks the turn on
    # which a reputation echo was last surfaced — used to enforce a 3-turn
    # gap so the system doesn't feel systematic.
    last_reputation_echo_turn: int = 0
    # CS-6 Phase 6: Inner-conflict tracking
    contradiction_arc: dict = field(default_factory=dict)  # ContradictionArcState accumulation
    # CS-6 Phase 8: Closure heartbeats
    turns_since_last_thread_change: int = 0  # Reset when any thread changes
    # Memorable moments ledger — a curated list of past beats the LLM can
    # callback to in future scenes. Stored as a list of dicts (serializable
    # to JSON for arc_state persistence). MemorableMoment dataclass above
    # describes the schema. Capped to a rolling window so memory doesn't
    # grow without bound — see register_memorable_moment.
    memorable_moments: list = field(default_factory=list)


@dataclass
class ContextPackage:
    character:        Character
    arc:              ArcState
    story_summary:    str
    recent_turns:     list[TurnMemory]
    active_npcs:      list[NPCState]
    location:         str
    situation:        str
    galactic_context: str = ""         # v1.6: per-act worldbuilding (Game Mechanics §4, Campaign Studio §4.4)
    sequence:         Optional[dict] = None  # v1.6: multi-beat sequence state (Game Mechanics §3) — null for normal turns
    dice_pool:        Optional[DicePool]   = None
    roll_result:      Optional[RollResult] = None
    scene_type:         str = "social"   # v2.1: from check decision (Game Mechanics §10)
    tone_instruction:   str = "Maintain established tone"
    prose_diagnostic:   Optional[dict] = None  # v1.5: reserved for prose diagnostic signal (Game Mechanics v1.1 §13)
    anchor_instruction: Optional[str] = None   # v2.5: set when act_progress >= 1.0 (§26.4)
    expected_turns:     Union[list[int], str] = field(default_factory=lambda: [8, 12])  # v2.5: [min, max] from spine or "8-12" string
    combat_damage_note: str = ""               # v3.0: Phase 9 — weapon damage context for combat checks (§18)
    talent_activations: list = field(default_factory=list)  # Phase 11: TalentActivation records for this turn (§15)
    destiny_narrative_note: str = ""           # Phase 11.5: narrative guidance when Destiny Points spent (§23)
    aspiration_echo_instructions: str = ""     # Phase 13: interiority guidance from behavioral inference (§14.5)
    # prose_diagnostic already declared above   # Phase 13: prose quality signal (§13)
    force_result_block: str = ""              # Phase 14: Force result context for narration (§16)
    force_check_kind:   str = ""              # "pure" for Force-only rolls, "enhanced" for skill+Force
    force_state_block:  str = ""              # Phase 14: Force state context for narration (§16)
    ship_state_block:   str = ""              # Phase 16: Ship state context for narration (§17)
    dramatic_mission:   dict = field(default_factory=dict)  # CS-6 Phase 1: mission from reconciliation
    pinch_point_instruction: str = ""   # CS-6 Phase 2: injected when pinch point fires
    foreshadow_instruction: str = ""    # CS-6 Phase 5: injected for setup delivery
    contradiction_arc_block: str = ""   # CS-6 Phase 6: character arc state
    closure_heartbeat_instruction: str = ""  # CS-6 Phase 8: thread heartbeat
    depth_card_block: str = ""          # CS-6 Phase 9: character depth card
    voice_mode_instruction: str = ""    # CS-6 Phase 10: voice mode tag
    # Reputation echoes — 0-3 selected entries from the reputation_log,
    # injected into narration for occasional "the world remembers" beats.
    # Populated by api/game_routes.py via state.session.select_reputation_echoes
    # before context assembly. Empty list = nothing to surface this turn.
    reputation_entries: list[dict] = field(default_factory=list)
    # Behavioral availability constraints from Phase 13 annotation history.
    # When non-empty, instructs the GM to weight choices toward the
    # protagonist's revealed priorities, gating identity-incoherent options.
    behavioral_availability: dict = field(default_factory=dict)
    # Star Wars era voice block — populated from spine.era_voice (if present)
    # to enforce era-specific tone, period detail, and canon coherence.
    era_voice_block: str = ""
    # Identity drift cue — a one-line interior note surfaced when the
    # protagonist's morality / conflict / aspiration has shifted enough since
    # last surfacing to warrant a turn-to-turn reveal. Most turns: empty.
    # Populated by api/game_routes.py before context assembly; the emit-side
    # policy lives in compute_identity_drift_cue() below.
    identity_drift_cue: str = ""
    # Introspection trigger — when set, the narration prompt receives an
    # explicit instruction to make this turn quieter and more interior. Set
    # by api/game_routes.py from compute_introspection_trigger() based on
    # post-Despair, post-pinch-point, and dry-spell conditions.
    introspection_trigger: str = ""
    # Memorable-moments callback candidates — 0-2 dicts selected from the
    # arc-state ledger. When non-empty, the narration prompt invites the
    # LLM to weave one back into the scene as resonance.
    memorable_moments: list[dict] = field(default_factory=list)
    # Pre-rendered lore seeds block for atmosphere consistency. Populated
    # from spine.lore_seeds — sensory anchors, rituals, significant objects,
    # period language. Used to keep the world feeling consistent across turns.
    lore_seeds_block: str = ""
    # One-shot growth recognition produced by the between-act pipeline. The
    # narration prompt receives this on the first turn of a new act, then it
    # is cleared so the recognition doesn't echo turn after turn.
    growth_recognition_block: str = ""
    # Pre-rendered tactical state block (Phase D). Active when the player is
    # in a multi-round combat / negotiation / chase. Empty for routine scenes.
    tactical_state_block: str = ""
    # Pre-rendered NPC counter-move block (Phase E17). Suggests the next
    # tactical or social move the most-pressuring NPC is likely to take.
    npc_counter_move_block: str = ""
    # Pre-rendered faction reactivity block (Phase E18). Surfaces emergent
    # faction state shifts caused by recent player actions.
    faction_reactivity_block: str = ""
    # Pre-rendered side-content offer block (Phase E20). Surfaces an
    # optional encounter the player can engage with this turn.
    side_content_block: str = ""
    # Pre-rendered hard-pivot warning (Phase E19). When the player is at a
    # spine pivot point, prompts the LLM to make the choices feel weighty
    # and the consequences explicit.
    pivot_warning_block: str = ""
    # Brooks/Weiland inner-story block — Lie/Ghost/Truth/Want/Need + lie_grip.
    # Empty when the active character has no narrative_arc populated.
    narrative_arc_block: str = ""
    # Brooks beat-role + protagonist-stance cue derived from the active act's
    # dramatic_function and protagonist_mode. Empty when act has no role data.
    beat_role_block: str = ""

    def build_dice_result_block(self) -> str:
        if self.roll_result is None:
            return "NO DICE CHECK THIS TURN — narrate the action directly."
        if self.force_check_kind == "pure":
            force_failed = (
                "FORCE OUTCOME: FAILURE" in self.force_result_block.upper()
                or "FORCE RESULT: FAILED" in self.force_result_block.upper()
            )
            lines = [
                "FORCE DICE RESULT (PURE FORCE ACTION):",
                f"  Pool: {self.dice_pool.description() if self.dice_pool else 'unknown'}",
                f"  Light pips: {self.roll_result.light_pips}",
                f"  Dark pips: {self.roll_result.dark_pips}",
                "  This is not a normal skill check. Do not interpret zero "
                "successes as mundane failure.",
                "  The FORCE RESULT block below is authoritative for whether "
                "the power worked. If the Force succeeded, narrate success "
                "with limited or costly information if appropriate, but do "
                "not describe the Force itself as failing.",
            ]
            lines.append("")
            lines.append("DICE TRUTH CONTRACT:")
            if force_failed:
                lines.extend([
                    "  FORCE FAILURE: The power does not deliver the requested read.",
                    "  Do not identify hidden intent, truth, lies, exact location,",
                    "  hidden cause, or a concealed actor. You may show only vague",
                    "  pressure, unease, sensory static, or danger at the edge of",
                    "  perception. Do not add the withheld secret to known_facts.",
                ])
            else:
                lines.extend([
                    "  FORCE SUCCESS: The power may reveal the requested sense-data,",
                    "  but keep the scope proportional to the power and the current",
                    "  act. Success can clarify; it should not solve the whole thread",
                    "  unless an explicit beat or act anchor says so.",
                ])
            if self.destiny_narrative_note:
                lines.append("")
                lines.append(self.destiny_narrative_note)
            return "\n".join(lines)
        lines = [
            "DICE CHECK RESULT:",
            f"  Pool: {self.dice_pool.description() if self.dice_pool else 'unknown'}",
            f"  Result: {self.roll_result.narrative_label()}",
            f"  Outcome quadrant: {self.roll_result.outcome_quadrant}",
        ]
        if self.roll_result.triumphs:
            lines.append(
                f"  TRIUMPH x{self.roll_result.triumphs}: "
                "Include a significant critical positive effect"
            )
        if self.roll_result.despairs:
            lines.append(
                f"  DESPAIR x{self.roll_result.despairs}: "
                "Include a significant critical negative effect"
            )
        if abs(self.roll_result.net_advantages) >= 3:
            side = ("advantages" if self.roll_result.net_advantages > 0
                    else "threats")
            lines.append(
                f"  Strong {side} ({abs(self.roll_result.net_advantages)}): "
                "This should be notably impactful in the narrative"
            )
        lines.append("")
        lines.append("DICE TRUTH CONTRACT:")
        if self.roll_result.succeeded:
            lines.append(
                "  SUCCESS: The player's stated goal happens. Threat may add "
                "cost, exposure, delay, or complication, but it cannot erase "
                "the achieved core outcome."
            )
        else:
            lines.extend([
                "  FAILURE: The player's stated goal does not happen. Do not",
                "  grant the core information, concession, access, safety, or",
                "  positional advantage the player attempted to win.",
            ])
            if self.roll_result.outcome_quadrant == "failure_advantage":
                lines.extend([
                    "  FAILURE + ADVANTAGE: Give a lesser peripheral benefit only:",
                    "  a vague clue, safer footing, narrowed suspicion, emotional",
                    "  tell, or useful delay. The main answer remains withheld.",
                ])
            else:
                lines.extend([
                    "  FAILURE + THREAT: The attempt fails and the scene gets worse.",
                    "  Increase pressure without revealing the secret for free.",
                ])
            if self.scene_type.lower() == "social":
                lines.extend([
                    "  SOCIAL FAILURE: NPCs do not directly answer the asked question",
                    "  or reveal the withheld secret. They deflect, go guarded, give",
                    "  an incomplete answer, or demand proof/action before disclosure.",
                ])
        # Phase 9: weapon damage context for combat checks (§18)
        if self.combat_damage_note:
            lines.append("")
            lines.append(self.combat_damage_note)
        # Soak info for incoming damage narration
        soak = self.character.effective_soak()
        if soak > 0:
            lines.append(f"  Character soak: {soak} (incoming wounds reduced by this amount)")
        # Phase 11.5: Destiny Point narrative guidance (§23)
        if self.destiny_narrative_note:
            lines.append("")
            lines.append(self.destiny_narrative_note)
        return "\n".join(lines)

    def build_npc_block(self) -> str:
        if not self.active_npcs:
            return "No NPCs currently active in scene."
        blocks = [self._redact_future_spoilers(npc.to_prompt_block())
                  for npc in self.active_npcs]
        return (
            "SPOILER CONTROL: NPC private knowledge is behavioral context, "
            "not permission to reveal it. Do not disclose private facts unless "
            "the current act, situation, recent turns, or explicit beat "
            "instruction has already surfaced them to the player.\n\n"
            + "\n\n".join(blocks)
        )

    def _redact_future_spoilers(self, block: str) -> str:
        """Hide campaign-defining future reveals from early-act NPC context.

        The NPC roster stores private knowledge so characters can behave
        consistently, but live narration must not blurt later-act reveals just
        because an NPC knows them. This guard keeps the current Star Wars
        campaign's major secrets behind their act gates while preserving
        generic behavioral pressure for the narrator.
        """
        act = int(self.arc.current_act or 1)
        redacted_lines: list[str] = []
        emitted: set[str] = set()

        def add_once(key: str, line: str) -> None:
            if key not in emitted:
                redacted_lines.append(line)
                emitted.add(key)

        for line in block.splitlines():
            lower = line.lower()
            if act < 3 and any(
                token in lower for token in (
                    "seren denn", "kira's parent", "kira’s parent",
                    "parentage", "dead parent",
                )
            ):
                add_once(
                    "kira_parent_secret",
                    "  Private unresolved secret: Kira has a concealed "
                    "family-history wound. Before Act 3, imply pressure and "
                    "avoid naming the person or explaining parentage.",
                )
                continue
            if act < 3 and any(
                token in lower for token in (
                    "malakai", "surviving inquisitor", "inquisitor",
                )
            ):
                add_once(
                    "malakai_secret",
                    "  Private unresolved secret: An outside manipulator may "
                    "be involved. Before Act 3, do not name that figure or "
                    "reveal an Inquisitor connection.",
                )
                continue
            if act < 4 and any(
                token in lower for token in (
                    "tannen", "imperial remnant fleet", "task force",
                    "fleet", "intelligence source", "intelligence to",
                )
            ):
                add_once(
                    "fleet_secret",
                    "  Private unresolved secret: A wider Imperial threat may "
                    "exist. Before Act 4, do not mention the commander, "
                    "military movement, or leaked academy intelligence.",
                )
                continue
            redacted_lines.append(line)

        return "\n".join(redacted_lines)

    def build_pacing_block(self) -> str:
        """Assemble the PACING block for the narration prompt (§26.6)."""
        if self.anchor_instruction:
            return self.anchor_instruction

        progress_pct = int(self.arc.act_progress * 100)
        turns = self.expected_turns
        if isinstance(turns, str):
            parts = [int(x.strip()) for x in turns.split("-") if x.strip().isdigit()]
            turns = parts if len(parts) == 2 else [8, 12]
        expected_mid = sum(turns) // 2

        lines = [
            "PACING:",
            f"Act progress: {progress_pct}%",
            f"Turns in act: {self.arc.turns_this_act} of ~{expected_mid}",
            f"Next structural beat: {self.arc.anchor_description or self.arc.next_anchor}",
            f"Proximity: {self.arc.anchor_proximity}",
        ]

        if self.arc.turns_this_act >= 3 and self.scene_type in (
            "introspection", "exploration",
        ):
            lines.append(
                "SCENE MOTION GOVERNOR: This act has enough setup to start "
                "moving. If the player chose reflection or waiting, honor it "
                "briefly, then introduce a concrete external development before "
                "the passage ends. At least two choices should move to a person, "
                "place, clue, or decision point rather than staying in place."
            )

        if progress_pct <= 30:
            lines.append(
                "This is early in the act. Establish the situation, introduce "
                "complications, let the player explore. Do not rush toward the "
                "anchor. There is time for character moments, world detail, and setup."
            )
        elif progress_pct <= 70:
            lines.append(
                "The act is developing. Threads should be converging. "
                "Complications are mounting. The player should feel increasing "
                "pressure from the situation, but the anchor is not imminent. "
                "Maintain tension without premature resolution."
            )
        elif progress_pct <= 90:
            lines.append(
                "The act is approaching its anchor beat. Begin converging "
                "threads. Increase urgency. The choices should narrow toward "
                "the conditions that will trigger the anchor. The player should "
                "sense that something is about to change."
            )
        else:
            lines.append(
                "The anchor beat is imminent. The next 1-2 turns should bring "
                "the current threads to a convergence point. The choices should "
                "be consequential — the player is making the decisions that "
                "determine how they enter the anchor situation."
            )

        # HARD scene-close override. When the anchor is imminent we have
        # observed the model treating the soft pacing prose as suggestion and
        # holding the scene open for many turns. This block is a non-soft
        # instruction that must override the softer guidance above.
        if str(self.arc.anchor_proximity).lower() == "imminent":
            lines.append(
                "HARD SCENE-CLOSE RULE (overrides any softer pacing note "
                "above): the current scene must close in this passage. Pick "
                "ONE closure and execute it visibly in the prose:\n"
                "  1. Resolve the dramatic question of the scene with a "
                "concrete answer or commitment.\n"
                "  2. Transition the player to a new physical location — by "
                "the last paragraph they are elsewhere, even if mid-step.\n"
                "  3. Cut to a hard external development that breaks the "
                "current frame (an arrival, a departure, a comm, a hatch "
                "opening fully, a saber igniting, a ship lifting).\n"
                "You may NOT continue the same dialogue beat into another "
                "turn. You may NOT end on the same standoff, the same hatch "
                "in motion, or the same NPC mid-question. The current "
                "frame is closed by the end of this passage. The state_patch "
                "current_location, present_npcs, and immediate_pressure must "
                "reflect the new frame, not the one that just ended."
            )

        # Stall detection: scene is dragging past expected turns even though
        # the anchor is not yet imminent. Push the GM to escalate motion.
        elif (
            isinstance(turns, list) and len(turns) == 2
            and self.arc.turns_this_act > turns[1]
        ):
            lines.append(
                "SCENE STALL DETECTED: this act has run past its expected "
                "turn budget without reaching the anchor. The current scene "
                "is over-extended. Within this passage, introduce a concrete "
                "external development that forces the scene to advance — a "
                "new arrival, a hard pressure, a location change, a "
                "thread closure. Do not continue the same conversational "
                "loop. End the passage in a different frame than it began."
            )

        return "\n".join(lines)

    def build_motivation_block(self) -> str:
        """Assemble the MOTIVATION block for the narration prompt (§9)."""
        lines = []
        if self.arc.obligation_active and self.arc.obligation_type:
            lines.append(
                f"OBLIGATION ACTIVE — {self.arc.obligation_type}\n"
                f"The character's Obligation ({self.arc.obligation_type}) is active this "
                f"act. Weave pressure related to {self.arc.obligation_type} into the "
                f"narrative — not as a direct confrontation, but as environmental "
                f"tightening. The character feels it before they understand its source."
            )
        if self.arc.duty_active and self.arc.duty_type:
            lines.append(
                f"DUTY ACTIVE — {self.arc.duty_type}\n"
                f"The character's Duty ({self.arc.duty_type}) is active. Present an "
                f"opportunity aligned with {self.arc.duty_type} that competes with the "
                f"character's current objective. The opportunity is real and meaningful "
                f"— but pursuing it costs something."
            )
        if self.arc.morality_label:
            lines.append(f"MORALITY: {self.arc.morality_label}")
        return "\n\n".join(lines)

    def build_aspiration_echo_block(self) -> str:
        """Assemble aspiration echo block (Phase 13, §14.5).

        Returns empty string when no echo is active — the prompt placeholder
        simply vanishes.  Scene-type-aware: foregrounded in introspection
        and social, backgrounded in combat/chase, omitted in multi-beat
        action.
        """
        if not self.aspiration_echo_instructions:
            return ""

        # Omit in high-action scenes where pacing cannot accommodate interiority
        if self.scene_type in ("combat", "chase"):
            return ""

        return (
            "ASPIRATION ECHOES (interiority guidance):\n"
            f"{self.aspiration_echo_instructions}\n\n"
            "Do not include aspiration echo interiority in every passage. "
            "These moments should feel organic and occasional, not systematic. "
            "When you include one, make it brief — a sentence or two of "
            "interiority, not a paragraph."
        )

    def build_prose_diagnostic_block(self) -> str:
        """Assemble prose diagnostic injection (Phase 13, §13).

        When the diagnostic is populated, injects an anti-staleness signal
        into the cloud model's context.  When null/empty, returns empty
        string so the placeholder vanishes.
        """
        if not self.prose_diagnostic:
            return ""

        import json
        return (
            "PROSE DIAGNOSTIC (for your reference — do not mention this "
            "to the player):\n"
            "The diagnostic below identifies patterns in recent passages. "
            "Vary your approach to address any flagged issues.\n\n"
            f"{json.dumps(self.prose_diagnostic, indent=2)}"
        )

    def build_dramatic_mission_block(self) -> str:
        """Assemble the DRAMATIC MISSION block for the narration prompt (CS-6 Phase 1).

        Returns empty string when no mission is available — the prompt
        placeholder simply vanishes.
        """
        if not self.dramatic_mission:
            return ""
        selected = self.dramatic_mission.get("selected_mission", "")
        sentence = self.dramatic_mission.get("mission_sentence", "")
        if not selected:
            return ""

        return (
            f"DRAMATIC MISSION FOR THIS TURN:\n"
            f"Mission: {selected}\n"
            f"Job: {sentence}\n\n"
            f"End this passage with an unresolved element — a question unanswered, "
            f"a threat glimpsed, a revelation half-delivered — that makes the player "
            f"want to see what happens next."
        )

    def build_open_threads_block(self) -> str:
        if not self.arc.open_threads:
            return "None established yet."
        lines = []
        for t in self.arc.open_threads:
            status = getattr(t, "status", "active")
            label = t.status_label() if hasattr(t, "status_label") else status.upper()
            line = f"- {t.name} [{label}]"
            hot_q = getattr(t, "hot_question", "") or ""
            if hot_q:
                line += f"\n  Hot question: {hot_q}"
            progress = float(getattr(t, "progress", 0.0) or 0.0)
            if progress > 0.0:
                line += f"\n  Progress: {int(progress * 100)}%"
            if t.player_knows:
                line += f"\n  Player knows: {'; '.join(t.player_knows)}"
            if t.player_unknown:
                line += f"\n  Player does NOT know: {'; '.join(t.player_unknown)}"
            if status == "resolved_pending_fallout":
                line += (
                    "\n  Fallout: this thread closed but its consequences are "
                    "still rippling — let an NPC, a rumor, or an environmental "
                    "detail show how the world is metabolizing what happened."
                )
            elif status == "hot":
                line += (
                    "\n  Pressure: the player is pressing this right now — "
                    "this turn should advance, complicate, or invert the question."
                )
            elif status == "approaching_resolution":
                line += (
                    "\n  Convergence: the pieces are aligning — choices should "
                    "feel like they could resolve or shatter this thread soon."
                )
            elif status == "dormant":
                line += (
                    "\n  Quiet: this thread hasn't moved recently. Consider a "
                    "quiet reminder if a natural moment arrives — not exposition."
                )
            lines.append(line)
        return "\n".join(lines)

    def build_memorable_moments_block(self) -> str:
        """Render the memorable-moments callback block.

        Suppressed in high-action scenes (combat, chase, space_combat) where
        callbacks would disrupt pacing. Empty when no candidates were
        selected upstream.
        """
        if not self.memorable_moments:
            return ""
        if self.scene_type in ("combat", "chase", "space_combat"):
            return ""
        return build_memorable_moments_block(self.memorable_moments)

    def build_reputation_block(self) -> str:
        """Render the REPUTATION ECHOES block, or empty string if nothing surfaces.

        Most turns produce nothing. When entries are present, the GM is
        instructed to reference at most one — through NPC dialogue, an
        overheard line, a wanted poster, a stranger's grateful look, or
        environmental detail. The point is the world remembering, not
        the engine reciting.
        """
        if not self.reputation_entries:
            return ""
        lines = ["REPUTATION ECHOES (use sparingly — not every turn):"]
        lines.append(
            "The character's actions have traveled beyond the scenes where "
            "they occurred. People in this world may have heard about:"
        )
        for entry in self.reputation_entries:
            summary = entry.get("summary", "")
            turn = entry.get("turn_number", 0)
            tags = entry.get("faction_tags", [])
            age_note = f"~{max(0, self.arc.turns_this_act - turn)} turns ago"
            tag_note = f" ({', '.join(tags)})" if tags else ""
            lines.append(f'- "{summary}"{tag_note}, {age_note}')
        lines.append(
            "Pick AT MOST one, and only if it fits naturally — through NPC "
            "dialogue, overheard conversation, a reaction from someone who "
            "recognizes the character, or environmental detail (a wanted "
            "poster, a grateful look from a stranger). Most turns should NOT "
            "include a reputation echo. When you do, it should feel like a "
            "surprise — the world remembering something the player did."
        )
        return "\n".join(lines)

    def build_behavioral_availability_block(self) -> str:
        """Render the CHOICE AVAILABILITY constraint block (Phase 13 annotation).

        Empty when no behavioral signal is present (early-game, before
        annotation history accumulates). When present, instructs the GM to
        weight choices toward the protagonist's revealed priorities.
        """
        ba = self.behavioral_availability or {}
        priorities = ba.get("dominant_priorities", []) or []
        avoid      = ba.get("incoherent_priorities", []) or []
        tags       = ba.get("recurring_tags", []) or []
        strength   = ba.get("pattern_strength", 0.0)

        if not priorities and not avoid and not tags:
            return ""

        lines = ["BEHAVIORAL CHOICE WEIGHTING (from prior turns):"]
        if priorities:
            lines.append(
                "The protagonist has consistently revealed: "
                f"{', '.join(priorities)}. At least one choice must reflect "
                "this established identity — not as the safe option, but as "
                "the option that genuinely fits who they are."
            )
        if tags:
            lines.append(
                "Recurring behavioral tags: "
                f"{', '.join(tags)}. Use these as flavor on the "
                "identity-coherent choice."
            )
        if avoid and strength >= 0.6:
            lines.append(
                "Choices that contradict the protagonist's established "
                f"pattern ({', '.join(avoid)}) should be available but "
                "framed as costly — they require the character to deliberately "
                "act against their own grain. Do NOT silently omit them."
            )
        return "\n".join(lines)

    def build_identity_drift_block(self) -> str:
        """Render the identity drift cue when one was surfaced this turn.

        Empty when nothing surfaces. Suppressed in high-action scenes so the
        cue doesn't disrupt pacing — drift surfaces best in quieter beats.
        """
        if not self.identity_drift_cue:
            return ""
        if self.scene_type in ("combat", "chase"):
            return ""
        return self.identity_drift_cue

    def build_introspection_trigger_block(self) -> str:
        """Render the explicit introspection trigger instruction when active.

        Empty when no trigger fires. Unlike drift, this CAN apply in any
        scene — the trigger conditions (post-Despair, post-pinch-point) are
        themselves narrative anchors that warrant a quieter beat regardless
        of scene type.
        """
        return self.introspection_trigger or ""
