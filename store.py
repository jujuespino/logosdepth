"""Shared SQLite storage for the optional server features (accounts, sync, beta tools)."""
import hashlib
import os
import sqlite3
import time
from pathlib import Path

from flask import Blueprint, current_app, g, request

bp = Blueprint("store", __name__)

RATE_LIMITS = {"email": (5, 15 * 60), "ip": (30, 15 * 60), "feedback": (5, 60 * 60), "events": (120, 60)}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS login_tokens (
  token_hash TEXT PRIMARY KEY,
  email TEXT NOT NULL,
  expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS progress (
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  data TEXT NOT NULL,
  version INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS rate_events (
  bucket TEXT NOT NULL,
  ts INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS rate_events_idx ON rate_events(bucket, ts);
CREATE TABLE IF NOT EXISTS events (
  day TEXT NOT NULL,
  install_id TEXT NOT NULL,
  name TEXT NOT NULL,
  prop TEXT
);
CREATE INDEX IF NOT EXISTS events_install_idx ON events(install_id, day);
CREATE INDEX IF NOT EXISTS events_name_idx ON events(name, day);
CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY,
  created_at INTEGER NOT NULL,
  kind TEXT NOT NULL,
  message TEXT NOT NULL,
  contact TEXT,
  context TEXT
);
"""


def now() -> int:
    return int(time.time())


def _db_path() -> str:
    return current_app.config.get("DATABASE_PATH") or os.environ.get("DATABASE_PATH") or str(
        Path(current_app.root_path) / "instance" / "logosdepth.db"
    )


def db() -> sqlite3.Connection:
    if "db" not in g:
        path = _db_path()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        g.db = conn
    return g.db


@bp.teardown_app_request
def _close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def rate_limited(bucket: str, kind: str) -> bool:
    """Count this request against `bucket`; True if it is over the limit for `kind`. Shared across workers."""
    limit, window = RATE_LIMITS[kind]
    bucket = hashlib.sha256(bucket.encode()).hexdigest()  # never keep raw IPs or email addresses here
    conn = db()
    t = now()
    conn.execute("DELETE FROM rate_events WHERE ts < ?", (t - 24 * 3600,))
    n = conn.execute(
        "SELECT COUNT(*) FROM rate_events WHERE bucket = ? AND ts > ?", (bucket, t - window)
    ).fetchone()[0]
    if n >= limit:
        conn.commit()
        return True
    conn.execute("INSERT INTO rate_events (bucket, ts) VALUES (?, ?)", (bucket, t))
    conn.commit()
    return False


def client_ip() -> str:
    return request.remote_addr or "?"
