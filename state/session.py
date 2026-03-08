"""
Turn logging and state queries — the glue between SQLite and the GM layer.

Provides everything needed to rebuild a ContextPackage from the database.
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from state.db import get_connection
from gm.context import TurnMemory


def create_session(
    campaign_name:  str,
    character_json: str,
    arc_state_json: str,
) -> str:
    """Create a new session and return its ID."""
    session_id = str(uuid.uuid4())
    now        = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO sessions "
            "(id, campaign_name, character_json, arc_state_json, "
            " destiny_light, destiny_dark, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 0, 0, ?, ?)",
            (session_id, campaign_name, character_json, arc_state_json, now, now),
        )
        conn.commit()
    return session_id


def log_turn(
    session_id:       str,
    turn_number:      int,
    player_action:    str,
    choice_index:     int,
    narration:        str,
    choices:          list[str],
    check_skill:      str | None = None,
    check_difficulty: str | None = None,
    dice_pool_json:   str | None = None,
    roll_result_json: str | None = None,
    meaningful_note:  str | None = None,
    context_json:     str | None = None,
    scene_type:       str | None = None,
    moral_weight:     int = 0,
    skill_tags_json:  str | None = None,
) -> None:
    """Write one completed turn to the database.

    context_json and scene_type are stored for future distillation training
    data. When NARRATIVE_BACKEND != local, pass the serialized context
    package as context_json so the distillation_pairs view can pair it
    with the cloud-generated narration. This costs nothing at write time
    and avoids expensive backfilling later.
    """
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO turns "
            "(session_id, turn_number, player_action, choice_index, "
            " check_skill, check_difficulty, dice_pool_json, roll_result_json, "
            " narration, choices_json, skill_tags_json, meaningful_note, "
            " context_json, scene_type, moral_weight, compressed, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
            (
                session_id, turn_number, player_action, choice_index,
                check_skill, check_difficulty, dice_pool_json, roll_result_json,
                narration, json.dumps(choices), skill_tags_json, meaningful_note,
                context_json, scene_type, moral_weight, now,
            ),
        )
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id)
        )
        conn.commit()


def get_recent_turns(session_id: str, limit: int = 5) -> list[TurnMemory]:
    """Return most recent uncompressed turns in chronological order.
    Includes a narration excerpt (first 2-3 sentences) for narrative
    continuity — the cloud GM needs to know what it said, not just
    what the player did (evaluation §2.2).
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT turn_number, player_action, narration, check_skill, "
            "roll_result_json, meaningful_note "
            "FROM turns WHERE session_id = ? AND compressed = 0 "
            "ORDER BY turn_number DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()

    turns = []
    for row in reversed(rows):
        result_data = (json.loads(row["roll_result_json"])
                       if row["roll_result_json"] else {})
        # Extract first 2-3 sentences as narration excerpt
        narration = row["narration"] or ""
        sentences = narration.split(". ")
        excerpt = ". ".join(sentences[:3]).strip()
        if excerpt and not excerpt.endswith("."):
            excerpt += "."
        turns.append(TurnMemory(
            turn_number=row["turn_number"],
            player_action=row["player_action"],
            narration_excerpt=excerpt,
            check_made=row["check_skill"],
            dice_result=result_data.get("narrative_label"),
            outcome_quadrant=result_data.get("outcome_quadrant"),
            meaningful_choice_note=row["meaningful_note"] or "",
        ))
    return turns


def get_act_summaries(session_id: str) -> str:
    """
    Return all act summaries as a single story_summary string for context
    package injection. Returns empty string if no summaries exist yet.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT act_number, summary FROM act_summaries "
            "WHERE session_id = ? ORDER BY act_number ASC",
            (session_id,),
        ).fetchall()

    if not rows:
        return ""
    return "\n\n".join(f"Act {r['act_number']}: {r['summary']}" for r in rows)


def get_session(session_id: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()


def get_turn_count(session_id: str) -> int:
    with get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM turns WHERE session_id = ?", (session_id,)
        ).fetchone()[0]


def get_act_turns(session_id: str, count: int) -> list[dict]:
    """
    Return the most recent `count` turns as dicts for XP evaluation (§14.1).
    Returns columns needed by the advancement engine: check_skill,
    roll_result_json, skill_tags_json, choice_index, moral_weight.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT turn_number, check_skill, check_difficulty, "
            "roll_result_json, skill_tags_json, choice_index, moral_weight "
            "FROM turns WHERE session_id = ? "
            "ORDER BY turn_number DESC LIMIT ?",
            (session_id, count),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]
