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
            "INTROSPECTION TRIGGER (mid-act dry spell): It has been several "
            "turns since the protagonist faced a real test of skill. Use this "
            "passage to re-ground them — a moment of stillness, a glance back "
            "at a thread they've been carrying, or a small physical action "
            "that registers as character rather than plot."
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


# Phase 8.5: Decay rates per mood (§25.3) — intensity reduction per turn
MOOD_DECAY_RATES = {
    "calm": 0.0,
    "angry": 0.15,
    "afraid": 0.10,
    "grieving": 0.05,
    "suspicious": 0.08,
    "grateful": 0.20,
    "desperate": 0.12,
    "amused": 0.25,
    "conflicted": 0.05,
}

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

    def disposition_label(self) -> str:
        """Human-readable label for prompt injection."""
        if self.disposition >= 0.8:   return "loyal"
        if self.disposition >= 0.6:   return "friendly"
        if self.disposition >= 0.4:   return "neutral"
        if self.disposition >= 0.2:   return "wary"
        return "hostile"

    def set_emotion(self, mood: str, intensity: float, source: str, turn: int):
        """Set a new emotional state (§25.2). Replaces current emotion."""
        decay = MOOD_DECAY_RATES.get(mood, 0.10)
        self.emotional_state = EmotionalState(
            mood=mood, intensity=min(1.0, max(0.0, intensity)),
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


@dataclass
class ThreadState:
    """Stateful thread tracking — name + what's known/unknown."""
    name:           str
    player_knows:   list[str] = field(default_factory=list)
    player_unknown: list[str] = field(default_factory=list)


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

    def build_dice_result_block(self) -> str:
        if self.roll_result is None:
            return "NO DICE CHECK THIS TURN — narrate the action directly."
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
        return "\n\n".join(npc.to_prompt_block() for npc in self.active_npcs)

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
            line = f"- {t.name}"
            if t.player_knows:
                line += f"\n  Player knows: {'; '.join(t.player_knows)}"
            if t.player_unknown:
                line += f"\n  Player does NOT know: {'; '.join(t.player_unknown)}"
            lines.append(line)
        return "\n".join(lines)

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
