"""
Memory compression — turns are compressed into act summaries via the LLM router.

Compression uses the configured fast LLM tier at low temperature for factual
summarization. Failed compression logs but never propagates — the game
continues with slightly larger context rather than breaking.
"""

import asyncio
import json
import logging

from gm.llm_client import TIER_FAST, call_chat
from state.db import get_connection

COMPRESSION_THRESHOLD = 8

COMPRESSION_PROMPT = """
You are summarizing turns from a narrative RPG session for long-term memory.

TURNS TO COMPRESS:
{turns_text}

Write a concise summary (100-150 words) covering:
1. What happened (key events only, no padding)
2. Which meaningful choices the player made and what they implied about character
3. What changed in the world or NPC relationships

Write in past tense. Be specific. Prioritize consequences over actions.
Do not use bullet points. Plain prose only.
"""


def should_compress(session_id: str) -> bool:
    with get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM turns WHERE session_id = ? AND compressed = 0",
            (session_id,),
        ).fetchone()[0]
    return count >= COMPRESSION_THRESHOLD


def compress_act_turns(session_id: str, act_number: int) -> None:
    """
    Compress uncompressed turns into an act summary using the fast LLM tier.
    Marks turns as compressed after writing the summary.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT turn_number, player_action, check_skill, "
            "roll_result_json, meaningful_note "
            "FROM turns WHERE session_id = ? AND compressed = 0 "
            "ORDER BY turn_number ASC",
            (session_id,),
        ).fetchall()

    if not rows:
        return

    lines = []
    for row in rows:
        line   = f"Turn {row['turn_number']}: {row['player_action']}"
        result = (json.loads(row["roll_result_json"])
                  if row["roll_result_json"] else {})
        if row["check_skill"]:
            line += f" [{row['check_skill']}: {result.get('outcome_quadrant', '?')}]"
        if row["meaningful_note"]:
            line += f" — {row['meaningful_note']}"
        lines.append(line)

    summary = call_chat(
        tier=TIER_FAST,
        purpose="memory",
        user=COMPRESSION_PROMPT.format(turns_text="\n".join(lines)),
        temperature=0.3,
        max_tokens=300,
        timeout=45.0,
        retries=2,
    )
    summary = summary.strip()

    turn_numbers = [row["turn_number"] for row in rows]
    placeholders = ",".join("?" * len(turn_numbers))

    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO act_summaries "
            "(session_id, act_number, summary, turns_covered, created_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            (session_id, act_number, summary, len(rows)),
        )
        conn.execute(
            f"UPDATE turns SET compressed = 1 "
            f"WHERE session_id = ? AND turn_number IN ({placeholders})",
            (session_id, *turn_numbers),
        )
        conn.commit()


RECAP_PROMPT = """
You are writing a "Previously on..." recap for a player returning to a
Star Wars narrative RPG mid-story.

STORY SO FAR (compressed act summaries):
{act_summaries}

MOST RECENT TURNS:
{recent_turns}

THE PLAYER IS ABOUT TO DECIDE: the choices from the last passage are
still open.

Write an 80-150 word recap in second person present tense, in the voice
of the story itself (not a TV announcer — no "previously on" phrase, no
meta language). Cover: where you are, what just happened, what pressure
or question is live right now. End at the current decision point so the
last sentence hands the moment back to the player. No bullet points.
No game terminology.
"""


def generate_resume_recap(session_id: str) -> str:
    """Build the returning-player recap from compressed memory + recent turns.

    One fast-tier call. Raises on failure — callers decide whether the
    recap is optional (the API treats it as fail-open).
    """
    from state.session import format_turn_lines, get_act_summaries, get_recent_turns

    summaries = get_act_summaries(session_id) or "The story has just begun."
    turn_lines = format_turn_lines(get_recent_turns(session_id, limit=3))

    recap = call_chat(
        tier=TIER_FAST,
        purpose="recap",
        user=RECAP_PROMPT.format(
            act_summaries=summaries,
            recent_turns="\n".join(turn_lines) or "No turns played yet.",
        ),
        temperature=0.4,
        max_tokens=300,
        timeout=20.0,
        retries=1,
    )
    return recap.strip()


async def compress_if_needed(session_id: str, act_number: int) -> None:
    """
    Non-blocking wrapper. Always call via FastAPI BackgroundTasks — never await
    inline. Errors are logged but never propagate; failed compression means
    context grows slightly, not that the game breaks.
    """
    if not should_compress(session_id):
        return
    try:
        loop = asyncio.get_running_loop()   # Python 3.10+ — not get_event_loop()
        await loop.run_in_executor(
            None, compress_act_turns, session_id, act_number
        )
    except Exception as e:
        logging.error(
            f"Memory compression failed for session {session_id}: {e}"
        )
