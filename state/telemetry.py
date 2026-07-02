"""Narrative telemetry — structured event logging per session.

Emits events as JSON lines to per-session log files in data/telemetry/.
Designed for easy parsing, grepping, and analysis by the evaluation harness.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


TELEMETRY_DIR = Path(os.getenv("TELEMETRY_DIR", "data/telemetry"))


@dataclass
class NarrativeEvent:
    session_id: str
    turn_number: int
    event_type: str
    event_data: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str)


def emit_event(event: NarrativeEvent) -> None:
    """Append an event to the session's JSONL telemetry log."""
    TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
    log_path = TELEMETRY_DIR / f"{event.session_id}.jsonl"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(event.to_json() + "\n")


def read_session_events(session_id: str) -> list[NarrativeEvent]:
    """Read all events for a session from its telemetry log."""
    log_path = TELEMETRY_DIR / f"{session_id}.jsonl"
    if not log_path.exists():
        return []
    events = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            events.append(NarrativeEvent(**data))
    return events


# ── Funnel events ────────────────────────────────────────────────────────

def funnel_event(event: str, **fields) -> None:
    """Append a player-funnel event to funnel_events.jsonl.

    Cross-session by nature (draft/save/generate happen before a session
    exists), so events go to one shared file rather than per-session logs.
    Analytics only — must never break a player-facing route, so this
    swallows every failure.
    """
    try:
        TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
        record = {"event": event, "timestamp": time.time(), **fields}
        log_path = TELEMETRY_DIR / "funnel_events.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception:
        pass


# ── Convenience emitters ─────────────────────────────────────────────────

def emit_choice_made(
    session_id: str, turn_number: int,
    choice_index: int, choice_text: str, skill_tag: str | None = None,
) -> None:
    emit_event(NarrativeEvent(
        session_id=session_id, turn_number=turn_number,
        event_type="choice_made",
        event_data={
            "choice_index": choice_index,
            "choice_text": choice_text,
            "skill_tag": skill_tag,
        },
    ))


def emit_dice_resolved(
    session_id: str, turn_number: int,
    pool: dict, outcome_quadrant: str, succeeded: bool,
) -> None:
    emit_event(NarrativeEvent(
        session_id=session_id, turn_number=turn_number,
        event_type="dice_resolved",
        event_data={
            "pool": pool,
            "outcome_quadrant": outcome_quadrant,
            "succeeded": succeeded,
        },
    ))


def emit_state_delta(
    session_id: str, turn_number: int, deltas: dict,
) -> None:
    emit_event(NarrativeEvent(
        session_id=session_id, turn_number=turn_number,
        event_type="state_delta",
        event_data=deltas,
    ))


def emit_consequence_gap(session_id: str, turn_number: int) -> None:
    emit_event(NarrativeEvent(
        session_id=session_id, turn_number=turn_number,
        event_type="consequence_gap",
        event_data={},
    ))


def emit_npc_disposition_shift(
    session_id: str, turn_number: int,
    npc_name: str, old_value: float, new_value: float, cause: str = "",
) -> None:
    emit_event(NarrativeEvent(
        session_id=session_id, turn_number=turn_number,
        event_type="npc_disposition_shift",
        event_data={
            "npc_name": npc_name,
            "old_value": round(old_value, 3),
            "new_value": round(new_value, 3),
            "cause": cause,
        },
    ))


def emit_thread_event(
    session_id: str, turn_number: int,
    event_subtype: str, thread_name: str,
) -> None:
    """Emit thread_opened, thread_progressed, thread_resolved, or thread_dropped."""
    emit_event(NarrativeEvent(
        session_id=session_id, turn_number=turn_number,
        event_type=f"thread_{event_subtype}",
        event_data={"thread_name": thread_name},
    ))


def emit_choice_quality_eval(
    session_id: str, turn_number: int, quality_data: dict,
) -> None:
    emit_event(NarrativeEvent(
        session_id=session_id, turn_number=turn_number,
        event_type="choice_quality_eval",
        event_data=quality_data,
    ))


def emit_scene_validation(
    session_id: str, turn_number: int, validation: dict,
) -> None:
    """CS-6 scene purpose validation result for the just-completed turn.

    `validation` should contain the five 1-5 dimension scores
    (mission_delivery, pressure_progression, antagonist_relevance,
    character_choices, change), the composite, the validated mission
    name, and any concern / corrective_instruction text. Quality
    signal only — emitted for eval, never blocks delivery.
    """
    emit_event(NarrativeEvent(
        session_id=session_id, turn_number=turn_number,
        event_type="scene_validation",
        event_data=validation,
    ))


def emit_act_transition(
    session_id: str, turn_number: int,
    from_act: int, to_act: int,
) -> None:
    emit_event(NarrativeEvent(
        session_id=session_id, turn_number=turn_number,
        event_type="act_transition",
        event_data={"from_act": from_act, "to_act": to_act},
    ))


def emit_session_summary(
    session_id: str, total_turns: int, stats: dict,
) -> None:
    emit_event(NarrativeEvent(
        session_id=session_id, turn_number=total_turns,
        event_type="session_summary",
        event_data=stats,
    ))
