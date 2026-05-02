"""
SQLite persistence layer with WAL mode.

WAL mode is set on every connection. This allows concurrent reads during
background compression writes, preventing locked-database errors.
"""

import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "./data/storyteller.db")
# Alias for test compatibility
_DB_PATH = DB_PATH

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
    choice_implications TEXT,
    force_result_json TEXT,
    compressed       INTEGER DEFAULT 0,
    created_at       TEXT NOT NULL
);

-- Distillation training data view (V2 — schema laid now, used later).
-- Each row pairs the full context package sent to the cloud GM with the
-- narration it produced. scene_type and dice metadata enable filtered
-- dataset construction (e.g. "only combat scenes with failures").
-- Populated automatically by log_turn.
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

CREATE TABLE IF NOT EXISTS ship_states (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    ship_id    TEXT NOT NULL,
    state_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(session_id, ship_id)
);

CREATE TABLE IF NOT EXISTS choice_quality_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    turn_number INTEGER NOT NULL,
    choices_json TEXT NOT NULL,
    evaluation_json TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    fail_count INTEGER NOT NULL,
    triggered_retry BOOLEAN NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS campaigns (
    id                TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    era               TEXT NOT NULL,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    authoring_mode    TEXT NOT NULL,
    spine_json        TEXT NOT NULL,
    validation_report TEXT,
    prior_campaign_id TEXT,
    FOREIGN KEY (prior_campaign_id) REFERENCES campaigns(id)
);
"""


def _get_db_path() -> str:
    """Return current DB path — checks module-level variables (supports test overrides)."""
    import state.db as _self
    # Check DB_PATH first (set by some tests), then _DB_PATH
    return getattr(_self, "DB_PATH", None) or _self._DB_PATH


@contextmanager
def get_connection():
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Run schema creation. Safe to call on every startup."""
    db_path = _get_db_path()
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        # Phase 13: migrate existing DBs — add choice_implications column
        try:
            conn.execute(
                "ALTER TABLE turns ADD COLUMN choice_implications TEXT"
            )
            conn.commit()
        except Exception:
            pass  # column already exists
        # Phase 14: migrate existing DBs — add Force result column
        try:
            conn.execute(
                "ALTER TABLE turns ADD COLUMN force_result_json TEXT"
            )
            conn.commit()
        except Exception:
            pass  # column already exists
        # Phase 16: migrate existing DBs — create ship_states table
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS ship_states ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "session_id TEXT NOT NULL REFERENCES sessions(id), "
                "ship_id TEXT NOT NULL, "
                "state_json TEXT NOT NULL, "
                "updated_at TEXT NOT NULL, "
                "UNIQUE(session_id, ship_id))"
            )
            conn.commit()
        except Exception:
            pass  # table already exists
        conn.commit()
