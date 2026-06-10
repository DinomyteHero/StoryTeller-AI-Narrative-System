"""
Turn logging and state queries — the glue between SQLite and the GM layer.

Provides everything needed to rebuild a ContextPackage from the database.
"""

import json
import re
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
    choice_implications: str | None = None,
    force_result_json: str | None = None,
) -> None:
    """Write one completed turn to the database.

    context_json and scene_type are stored for future distillation training
    data. Pass the serialized context package as context_json so the
    distillation_pairs view can pair it with the cloud-generated narration.
    This costs nothing at write time and avoids expensive backfilling later.

    choice_implications (Phase 13, §24): JSON string containing the choice
    annotation — behavioral meaning extracted from the player's choice.

    force_result_json (Phase 14, §16): JSON string containing the Force
    resolution result — pips used, conflict earned, temptation decision.
    """
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO turns "
            "(session_id, turn_number, player_action, choice_index, "
            " check_skill, check_difficulty, dice_pool_json, roll_result_json, "
            " narration, choices_json, skill_tags_json, meaningful_note, "
            " context_json, scene_type, moral_weight, choice_implications, "
            " force_result_json, compressed, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
            (
                session_id, turn_number, player_action, choice_index,
                check_skill, check_difficulty, dice_pool_json, roll_result_json,
                narration, json.dumps(choices), skill_tags_json, meaningful_note,
                context_json, scene_type, moral_weight, choice_implications,
                force_result_json, now,
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
        narration = row["narration"] or ""
        excerpt = _build_narration_excerpt(narration)
        turns.append(TurnMemory(
            turn_number=row["turn_number"],
            player_action=row["player_action"],
            narration_excerpt=excerpt,
            check_made=row["check_skill"],
            dice_result=_dice_label_from_roll_json(result_data),
            outcome_quadrant=result_data.get("outcome_quadrant"),
            meaningful_choice_note=row["meaningful_note"] or "",
        ))
    return turns


def _split_sentences(text: str) -> list[str]:
    normalized = " ".join((text or "").split())
    if not normalized:
        return []
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", normalized)
        if sentence.strip()
    ]


def _build_narration_excerpt(
    narration: str,
    *,
    head_sentences: int = 2,
    tail_sentences: int = 4,
    max_chars: int = 1100,
) -> str:
    """Preserve both setup and final state from a generated passage."""
    sentences = _split_sentences(narration)
    if not sentences:
        return ""
    if len(sentences) <= head_sentences + tail_sentences:
        excerpt = " ".join(sentences)
    else:
        head = " ".join(sentences[:head_sentences])
        tail = " ".join(sentences[-tail_sentences:])
        excerpt = f"{head} ... FINAL BEAT: {tail}"

    if len(excerpt) <= max_chars:
        return excerpt

    tail = " ".join(sentences[-tail_sentences:])
    head_budget = max(120, max_chars - len(tail) - len(" ... FINAL BEAT: "))
    head = " ".join(sentences[:head_sentences])[:head_budget].rstrip()
    return f"{head} ... FINAL BEAT: {tail}"


def _dice_label_from_roll_json(result_data: dict) -> str | None:
    if not result_data:
        return None
    net_successes = int(result_data.get("net_successes", 0) or 0)
    net_advantages = int(result_data.get("net_advantages", 0) or 0)
    triumphs = int(result_data.get("triumphs", 0) or 0)
    despairs = int(result_data.get("despairs", 0) or 0)

    parts = []
    if net_successes > 0:
        suffix = "es" if net_successes != 1 else ""
        parts.append(f"SUCCEEDED ({net_successes} net success{suffix})")
    elif net_successes < 0:
        failures = abs(net_successes)
        suffix = "s" if failures != 1 else ""
        parts.append(f"FAILED ({failures} net failure{suffix})")
    else:
        parts.append("FAILED (tied)")

    if net_advantages > 0:
        suffix = "s" if net_advantages != 1 else ""
        parts.append(f"with {net_advantages} Advantage{suffix}")
    elif net_advantages < 0:
        threats = abs(net_advantages)
        suffix = "s" if threats != 1 else ""
        parts.append(f"with {threats} Threat{suffix}")

    if triumphs:
        parts.append(f"and {triumphs} TRIUMPH")
    if despairs:
        parts.append(f"and {despairs} DESPAIR")
    return " ".join(parts)


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


def format_turn_lines(
    turns: list[TurnMemory],
    *,
    include_checks: bool = True,
    include_narration: bool = True,
) -> list[str]:
    """Compact "Turn N: action [skill: result] / excerpt" lines for prompt
    injection. Shared by the resume recap and the epilogue story summary."""
    lines = []
    for t in turns:
        line = f"Turn {t.turn_number}: {t.player_action}"
        if include_checks and t.check_made:
            line += f" [{t.check_made}: {t.dice_result}]"
        if include_narration and t.narration_excerpt:
            line += f"\n  {t.narration_excerpt}"
        lines.append(line)
    return lines


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


def update_destiny_pool(session_id: str, light: int, dark: int) -> None:
    """Write updated Destiny Point pool values to the sessions table (§23)."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "UPDATE sessions SET destiny_light = ?, destiny_dark = ?, "
            "updated_at = ? WHERE id = ?",
            (light, dark, now, session_id),
        )
        conn.commit()


def get_recent_narrations(session_id: str, limit: int = 4) -> list[str]:
    """Return the most recent narration passages for prose diagnostic (§13).

    Unlike get_recent_turns(), this queries ALL turns regardless of
    compression status.  Compression marks turns as summarised for
    context-building but does not delete the narration text — and the
    prose diagnostic needs the raw text to detect staleness / repetition.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT narration FROM turns "
            "WHERE session_id = ? "
            "ORDER BY turn_number DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    return [row["narration"] for row in reversed(rows) if row["narration"]]


def save_ship_state(session_id: str, ship) -> None:
    """Write one ShipState to the ship_states table (§17)."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO ship_states "
            "(session_id, ship_id, state_json, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (session_id, ship.ship_id, ship.model_dump_json(), now),
        )
        conn.commit()


def load_ship_states(session_id: str) -> list:
    """Load all ship states for a session. Returns list of ShipState objects."""
    from engine.vehicle import ShipState
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT ship_id, state_json FROM ship_states WHERE session_id = ?",
            (session_id,),
        ).fetchall()
    return [ShipState.model_validate_json(row["state_json"]) for row in rows]


def load_ship_state(session_id: str, ship_id: str):
    """Load a single ship state by ID. Returns ShipState or None."""
    from engine.vehicle import ShipState
    with get_connection() as conn:
        row = conn.execute(
            "SELECT state_json FROM ship_states "
            "WHERE session_id = ? AND ship_id = ?",
            (session_id, ship_id),
        ).fetchone()
    if row is None:
        return None
    return ShipState.model_validate_json(row["state_json"])


def get_act_turns(session_id: str, count: int) -> list[dict]:
    """
    Return the most recent `count` turns as dicts for XP evaluation (§14.1).
    Returns columns needed by the advancement engine: check_skill,
    roll_result_json, skill_tags_json, choice_index, moral_weight,
    choice_implications (Phase 13, §24).
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT turn_number, check_skill, check_difficulty, "
            "roll_result_json, skill_tags_json, choice_index, moral_weight, "
            "choice_implications "
            "FROM turns WHERE session_id = ? "
            "ORDER BY turn_number DESC LIMIT ?",
            (session_id, count),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def log_choice_quality(
    session_id: str,
    turn_number: int,
    choices_json: str,
    evaluation_json: str,
    passed: bool,
    fail_count: int,
    triggered_retry: bool,
) -> None:
    """Log a choice quality evaluation result."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO choice_quality_log "
            "(session_id, turn_number, choices_json, evaluation_json, "
            "passed, fail_count, triggered_retry) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, turn_number, choices_json, evaluation_json,
             passed, fail_count, triggered_retry),
        )
        conn.commit()


# ── Reputation echo system (Game Mechanics §1, §11, §21.4) ───────────
#
# Reputation events are public-visible actions captured during reconciliation.
# Selected entries surface in later narration as "people in this world have
# heard about this." Cooldown of 3 turns + relevance scoring prevents the
# system from feeling systematic.

def log_reputation_event(
    session_id:    str,
    turn_number:   int,
    summary:       str,
    faction_tags:  list[str],
) -> None:
    """Persist a reputation event captured during reconciliation.

    Only call when reconciliation produced a non-null reputation_event —
    most turns produce none. faction_tags identify where the event travels
    (e.g. ["smuggler_network", "nar_shaddaa_promenade"]).
    """
    if not summary:
        return
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO reputation_log "
            "(session_id, turn_number, summary, faction_tags, "
            " surfaced_count, created_at) "
            "VALUES (?, ?, ?, ?, 0, ?)",
            (session_id, turn_number, summary, json.dumps(faction_tags or []), now),
        )
        conn.commit()


def select_reputation_echoes(
    session_id:           str,
    current_turn:         int,
    last_echo_turn:       int,
    scene_factions:       list[str],
    current_npc_factions: list[str],
    cooldown:             int = 3,
    max_entries:          int = 3,
    min_score:            int = 4,
) -> list[dict]:
    """Pick 0..max_entries reputation entries to inject into narration.

    Scoring:
      +3 faction match (entry tags overlap scene/NPC factions)
      +2/+1 recency (< 5 turns / < 15 turns)
      +2/+1 novelty (surfaced_count == 0 / == 1)

    Returns a list of dicts: {id, summary, turn_number, faction_tags, score}.
    Returns [] during cooldown — the engine only echoes occasionally to
    keep the world from feeling like every NPC is talking about the player.
    """
    if current_turn - last_echo_turn < cooldown:
        return []

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, turn_number, summary, faction_tags, surfaced_count "
            "FROM reputation_log "
            "WHERE session_id = ? "
            "ORDER BY turn_number DESC LIMIT 50",
            (session_id,),
        ).fetchall()

    relevant_factions = set(scene_factions) | set(current_npc_factions)
    scored: list[dict] = []
    for row in rows:
        try:
            tags = json.loads(row["faction_tags"]) if row["faction_tags"] else []
        except (json.JSONDecodeError, TypeError):
            tags = []

        score = 0
        if relevant_factions and (set(tags) & relevant_factions):
            score += 3

        age = current_turn - row["turn_number"]
        if age < 5:
            score += 2
        elif age < 15:
            score += 1

        surfaced = row["surfaced_count"] or 0
        if surfaced == 0:
            score += 2
        elif surfaced == 1:
            score += 1

        if score >= min_score:
            scored.append({
                "id":           row["id"],
                "summary":      row["summary"],
                "turn_number":  row["turn_number"],
                "faction_tags": tags,
                "score":        score,
            })

    scored.sort(key=lambda e: e["score"], reverse=True)
    return scored[:max_entries]


def mark_reputation_echoes_surfaced(echo_ids: list[int]) -> None:
    """Increment surfaced_count for entries that the narration referenced."""
    if not echo_ids:
        return
    with get_connection() as conn:
        for echo_id in echo_ids:
            conn.execute(
                "UPDATE reputation_log SET surfaced_count = surfaced_count + 1 "
                "WHERE id = ?",
                (echo_id,),
            )
        conn.commit()


def detect_surfaced_echoes(passage: str, candidates: list[dict]) -> list[int]:
    """Return ids of echo candidates whose summary keywords appear in the passage.

    Heuristic: extract distinctive nouns (length >= 5, not stopwords) from
    each candidate summary and check substring presence in the passage.
    Single match is enough — the world referencing the event in any form
    counts as surfaced. No LLM call.
    """
    if not candidates or not passage:
        return []
    passage_lower = passage.lower()
    stop = {"have", "with", "from", "their", "into", "that", "this", "they",
            "them", "would", "could", "after", "before", "while", "about"}
    surfaced: list[int] = []
    for entry in candidates:
        summary = (entry.get("summary") or "").lower()
        keywords = [
            w.strip(".,;:'\"")
            for w in summary.split()
            if len(w) >= 5 and w.strip(".,;:'\"") not in stop
        ]
        # Require 2 distinct keyword hits to avoid coincidental matches
        hits = sum(1 for kw in keywords if kw and kw in passage_lower)
        if hits >= 2:
            surfaced.append(entry["id"])
    return surfaced


def derive_behavioral_availability(session_id: str, n_turns: int = 8) -> dict:
    """Aggregate Phase 13 choice annotations into a behavioral signal.

    Analyzes the most recent `n_turns` of choice_implications (JSON in the
    turns table) and returns:
      - dominant_priorities: priorities revealed in 30%+ of recent choices
      - recurring_tags:      behavioral tags appearing in 40%+ of recent choices
      - incoherent_priorities: priorities chosen but flagged as throughline-incoherent
      - pattern_strength:    0.0-1.0; how consistent the protagonist's choices are
    Returns an empty dict if insufficient annotation history.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT choice_implications FROM turns "
            "WHERE session_id = ? AND choice_implications IS NOT NULL "
            "ORDER BY turn_number DESC LIMIT ?",
            (session_id, n_turns),
        ).fetchall()

    if len(rows) < 3:
        return {}

    priority_counts: dict[str, int] = {}
    tag_counts:      dict[str, int] = {}
    incoherent_set:  set[str] = set()

    for row in rows:
        try:
            ann = json.loads(row["choice_implications"])
        except (json.JSONDecodeError, TypeError):
            continue
        priority = (ann.get("priority_revealed") or "").strip()
        if priority:
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
            if ann.get("throughline_relevance") == "low":
                incoherent_set.add(priority)
        for tag in ann.get("behavioral_tags", []) or []:
            t = str(tag).strip()
            if t:
                tag_counts[t] = tag_counts.get(t, 0) + 1

    total = len(rows)
    dominant = [p for p, c in priority_counts.items() if c / total >= 0.30]
    recurring = [t for t, c in tag_counts.items() if c / total >= 0.40]

    # Pattern strength: how concentrated the priorities are
    if priority_counts:
        max_count = max(priority_counts.values())
        pattern_strength = max_count / total
    else:
        pattern_strength = 0.0

    return {
        "dominant_priorities":   dominant,
        "recurring_tags":        recurring,
        "incoherent_priorities": sorted(incoherent_set & set(dominant)),
        "pattern_strength":      round(pattern_strength, 2),
    }
