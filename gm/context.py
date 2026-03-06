"""
Context assembly for the Cloud GM.

Builds the ContextPackage that gets formatted into the narration prompt.
All narrative context — character state, arc position, NPC states, recent
turns, dice results — flows through this module.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from engine.character import Character
from engine.dice import RollResult, DicePool


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

    def disposition_label(self) -> str:
        """Human-readable label for prompt injection."""
        if self.disposition >= 0.8:   return "loyal"
        if self.disposition >= 0.6:   return "friendly"
        if self.disposition >= 0.4:   return "neutral"
        if self.disposition >= 0.2:   return "wary"
        return "hostile"

    def to_prompt_block(self) -> str:
        lines = [f"{self.name}:"]
        if self.knows:
            lines.append(f"  Knows: {'; '.join(self.knows)}")
        if self.doesnt_know:
            lines.append(f"  Doesn't know: {'; '.join(self.doesnt_know)}")
        lines.append(f"  Disposition: {self.disposition_label()} ({self.disposition:.2f})")
        if self.voice_notes:
            lines.append(f"  Voice: {self.voice_notes}")
        if self.motivation:
            lines.append(f"  Wants: {self.motivation}")
        if self.behavioral_envelope:
            lines.append(f"  Never: {'; '.join(self.behavioral_envelope)}")
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
    scene_type:       str = "social"   # v2.1: from check decision (Game Mechanics §10)
    tone_instruction: str = "Maintain established tone"
    prose_diagnostic: Optional[dict] = None  # v1.5: reserved for prose diagnostic signal (Game Mechanics v1.1 §13)

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
        return "\n".join(lines)

    def build_npc_block(self) -> str:
        if not self.active_npcs:
            return "No NPCs currently active in scene."
        return "\n\n".join(npc.to_prompt_block() for npc in self.active_npcs)

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
