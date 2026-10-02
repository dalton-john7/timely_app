"""SQLite storage.

SQLite is a full SQL database kept in a single file. It needs no server, so
the project runs anywhere. The same SQL moves to SQL Server or Postgres
later with only small changes.
"""

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path.home() / ".dac_timelogger.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id   TEXT PRIMARY KEY,
    customer    TEXT,
    module      TEXT NOT NULL DEFAULT 'Other',
    subject     TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS time_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id   TEXT NOT NULL REFERENCES tickets(ticket_id),
    agent       TEXT NOT NULL,                 -- the help desk analyst
    phase       TEXT NOT NULL CHECK (phase IN ('work', 'documentation')),
    started_at  TEXT NOT NULL,                 -- UTC, 'YYYY-MM-DD HH:MM:SS'
    ended_at    TEXT,                          -- NULL while the timer runs
    source      TEXT NOT NULL DEFAULT 'manual' -- 'manual' or 'automation'
                CHECK (source IN ('manual', 'automation')),
    note        TEXT
);

-- An analyst can only run one timer at a time. A partial unique index
-- enforces that inside the database itself, so no code path (manual,
-- automation, or AI agent) can leave two timers running at once.
CREATE UNIQUE INDEX IF NOT EXISTS one_running_timer_per_agent
    ON time_entries(agent) WHERE ended_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_entries_ticket  ON time_entries(ticket_id);
CREATE INDEX IF NOT EXISTS idx_entries_started ON time_entries(started_at);
"""


def connect(path=None) -> sqlite3.Connection:
    """Open the database (creating it if needed) and apply the schema."""
    conn = sqlite3.connect(str(path or DEFAULT_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn
