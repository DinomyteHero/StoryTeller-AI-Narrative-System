"""
SQLite persistence layer with WAL mode.

WAL mode is set on every connection. This allows concurrent reads during
background compression writes, preventing locked-database errors.
"""

import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "./data/storyteller.db")

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS sessions (
    id             TEXT PRIMARY KEY,
    campaign_name  TEXT NOT NULL,
    character_json TEXT NOT NULL,
    arc_state_json TEXT NOT NULL,
    destiny_light  INTEGER DEFAULT 0,
    destiny_dark   INTEGER DEFAULT 0,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS turns (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id       TEXT    NOT NULL REFERENCES sessions(id),
    turn_number      INTEGER NOT NULL,
    player_action    TEXT    NOT NULL,
    choice_index     INTEGER,
    check_skill      TEXT,
    check_difficulty TEXT,
    dice_pool_json   TEXT,
    roll_result_json TEXT,
    narration        TEXT NOT NULL,
    choices_json     TEXT NOT NULL,
    skill_tags_json  TEXT,
    meaningful_note  TEXT,
    context_json     TEXT,
    scene_type       TEXT,
    moral_weight     INTEGER DEFAULT 0,
    compressed       INTEGER DEFAULT 0,
    created_at       TEXT NOT NULL
);

-- Distillation training data view (V2 — schema laid now, used later).
-- Each row pairs the full context package sent to the cloud GM with the
-- narration it produced. scene_type and dice metadata enable filtered
-- dataset construction (e.g. "only combat scenes with failures").
-- Populated automatically by log_turn when NARRATIVE_BACKEND != local.
CREATE VIEW IF NOT EXISTS distillation_pairs AS
SELECT
    t.session_id,
    t.turn_number,
    t.context_json,
    t.narration,
    t.scene_type,
    t.check_skill,
    t.check_difficulty,
    t.roll_result_json,
    t.created_at
FROM turns t
WHERE t.context_json IS NOT NULL
ORDER BY t.created_at;

CREATE TABLE IF NOT EXISTS npc_states (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    npc_name   TEXT NOT NULL,
    state_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(session_id, npc_name)
);

CREATE TABLE IF NOT EXISTS act_summaries (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     TEXT    NOT NULL REFERENCES sessions(id),
    act_number     INTEGER NOT NULL,
    summary        TEXT    NOT NULL,
    meaningful_choices TEXT,
    character_drift    TEXT,
    turns_covered  INTEGER NOT NULL,
    created_at     TEXT    NOT NULL,
    UNIQUE(session_id, act_number)
);

CREATE TABLE IF NOT EXISTS reputation_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     TEXT NOT NULL REFERENCES sessions(id),
    turn_number    INTEGER NOT NULL,
    summary        TEXT NOT NULL,
    faction_tags   TEXT,
    surfaced_count INTEGER DEFAULT 0,
    created_at     TEXT NOT NULL
);
"""


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Run schema creation. Safe to call on every startup."""
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        conn.commit()
