"""Optional accounts and cross-device sync.

Off by default (the app is local-first). Set ACCOUNTS_ENABLED=1 to turn it on. Sign-in is by emailed
one-time link, so there are no passwords to store. The server keeps one progress document per user;
the client merges before it uploads (see static/js/sync.js), and an `If-Match`-style version number
catches two devices saving at once.

Environment:
  ACCOUNTS_ENABLED   "1" to enable the /api/auth, /api/sync and /api/account routes
  DATABASE_PATH      SQLite file (default instance/logosdepth.db)
  PUBLIC_URL         Base URL used in sign-in emails (default: the request's host URL)
  MAIL_BACKEND       "console" (logs the link; development only) or "smtp"
  MAIL_FROM, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_STARTTLS   for the smtp backend
  COOKIE_SECURE      "1" to force the Secure cookie flag (otherwise set when the request is HTTPS)
  AUTH_RETURN_LINK   "1" returns the sign-in link in the API response (tests only; never in production)
"""
import hashlib
import json
import logging
import os
import re
import secrets
import smtplib
import sqlite3
import time
from email.message import EmailMessage
from pathlib import Path

from flask import Blueprint, current_app, g, jsonify, request

from progress_schema import MAX_BYTES, clean_progress

bp = Blueprint("accounts", __name__)
log = logging.getLogger("logosdepth.accounts")

LOGIN_TTL = 15 * 60
SESSION_TTL = 90 * 24 * 3600
COOKIE = "ld_session"
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")
RATE_LIMITS = {"email": (5, 15 * 60), "ip": (30, 15 * 60)}

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
"""


def enabled() -> bool:
    return current_app.config.get("ACCOUNTS_ENABLED", os.environ.get("ACCOUNTS_ENABLED") == "1")


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


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> int:
    return int(time.time())


# ─── Guards ──────────────────────────────────────────
@bp.before_request
def _guard():
    if not enabled():
        return jsonify({"error": "Accounts are not enabled on this server."}), 404
    if request.method in ("POST", "PUT", "DELETE"):
        # A custom header cannot be sent cross-site without a CORS preflight (which we never allow),
        # so requiring it blocks cross-site request forgery on top of SameSite=Lax cookies.
        if request.headers.get("X-LD-CSRF") != "1":
            return jsonify({"error": "Missing CSRF header."}), 403
    return None


@bp.after_request
def _no_store(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


def _rate_limited(bucket: str, kind: str) -> bool:
    limit, window = RATE_LIMITS[kind]
    conn = db()
    now = _now()
    conn.execute("DELETE FROM rate_events WHERE ts < ?", (now - 24 * 3600,))
    n = conn.execute(
        "SELECT COUNT(*) FROM rate_events WHERE bucket = ? AND ts > ?", (bucket, now - window)
    ).fetchone()[0]
    if n >= limit:
        conn.commit()
        return True
    conn.execute("INSERT INTO rate_events (bucket, ts) VALUES (?, ?)", (bucket, now))
    conn.commit()
    return False


def _client_ip() -> str:
    return request.remote_addr or "?"


# ─── Mail ────────────────────────────────────────────
def send_login_email(email: str, link: str) -> None:
    backend = os.environ.get("MAIL_BACKEND", "console")
    if backend == "smtp":
        msg = EmailMessage()
        msg["Subject"] = "Your LogosDepth sign-in link"
        msg["From"] = os.environ.get("MAIL_FROM", "LogosDepth <no-reply@localhost>")
        msg["To"] = email
        msg.set_content(
            "Use this link to sign in to LogosDepth. It works once and expires in 15 minutes:\n\n"
            f"{link}\n\n"
            "If you did not ask for this, you can ignore this email; nothing will happen."
        )
        with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "587")), timeout=15) as s:
            if os.environ.get("SMTP_STARTTLS", "1") == "1":
                s.starttls()
            if os.environ.get("SMTP_USER"):
                s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
            s.send_message(msg)
    else:
        # Development only: anyone who can read the logs could sign in as this address.
        log.warning("MAIL_BACKEND=console; sign-in link for %s: %s", email, link)


# ─── Auth ────────────────────────────────────────────
def _current_user():
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    row = db().execute(
        "SELECT u.id, u.email FROM sessions s JOIN users u ON u.id = s.user_id "
        "WHERE s.token_hash = ? AND s.expires_at > ?",
        (_hash(token), _now()),
    ).fetchone()
    return row


def _json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


@bp.route("/api/auth/request", methods=["POST"])
def auth_request():
    email = str(_json_body().get("email", "")).strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 254:
        return jsonify({"error": "Please enter a valid email address."}), 400
    if _rate_limited(f"email:{email}", "email") or _rate_limited(f"ip:{_client_ip()}", "ip"):
        return jsonify({"error": "Too many requests. Please wait a few minutes and try again."}), 429

    token = secrets.token_urlsafe(32)
    conn = db()
    conn.execute("DELETE FROM login_tokens WHERE expires_at < ?", (_now(),))
    conn.execute(
        "INSERT INTO login_tokens (token_hash, email, expires_at) VALUES (?, ?, ?)",
        (_hash(token), email, _now() + LOGIN_TTL),
    )
    conn.commit()

    base = (os.environ.get("PUBLIC_URL") or request.host_url).rstrip("/")
    link = f"{base}/?login={token}"
    try:
        send_login_email(email, link)
    except Exception:
        log.exception("Could not send sign-in email")
        return jsonify({"error": "We could not send the email. Please try again later."}), 502
    # Same response whether or not the address already has an account.
    out = {"ok": True}
    if os.environ.get("AUTH_RETURN_LINK") == "1":
        out["link"] = link
    return jsonify(out)


@bp.route("/api/auth/verify", methods=["POST"])
def auth_verify():
    token = str(_json_body().get("token", ""))
    if not token or len(token) > 200:
        return jsonify({"error": "This sign-in link is not valid."}), 400
    conn = db()
    # Single use: delete in the same statement that reads it.
    row = conn.execute(
        "DELETE FROM login_tokens WHERE token_hash = ? RETURNING email, expires_at", (_hash(token),)
    ).fetchone()
    if not row or row["expires_at"] < _now():
        conn.commit()
        return jsonify({"error": "This sign-in link has expired or was already used. Please request a new one."}), 400
    email = row["email"]
    conn.execute("INSERT OR IGNORE INTO users (email, created_at) VALUES (?, ?)", (email, _now()))
    user_id = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()["id"]
    session = secrets.token_urlsafe(32)
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (_now(),))
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (_hash(session), user_id, _now(), _now() + SESSION_TTL),
    )
    conn.commit()
    resp = jsonify({"ok": True, "email": email})
    resp.set_cookie(
        COOKIE, session, max_age=SESSION_TTL, httponly=True, samesite="Lax",
        secure=request.is_secure or os.environ.get("COOKIE_SECURE") == "1",
    )
    return resp


@bp.route("/api/auth/me")
def auth_me():
    user = _current_user()
    return jsonify({"signedIn": bool(user), "email": user["email"] if user else None})


@bp.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    token = request.cookies.get(COOKIE)
    if token:
        db().execute("DELETE FROM sessions WHERE token_hash = ?", (_hash(token),))
        db().commit()
    resp = jsonify({"ok": True})
    resp.delete_cookie(COOKIE)
    return resp


@bp.route("/api/auth/logout-all", methods=["POST"])
def auth_logout_all():
    user = _current_user()
    if not user:
        return jsonify({"error": "Not signed in."}), 401
    db().execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))
    db().commit()
    resp = jsonify({"ok": True})
    resp.delete_cookie(COOKIE)
    return resp


# ─── Sync ────────────────────────────────────────────
def _empty_progress():
    streak = {"last": "", "count": 0}
    return {"app": "logosdepth", "schemaVersion": 1, "data": {"srs": {}, "xp": 0, "streak": streak, "settings": {}}}


def _stored(user_id: int):
    row = db().execute("SELECT data, version, updated_at FROM progress WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return _empty_progress(), 0, None
    return json.loads(row["data"]), row["version"], row["updated_at"]


@bp.route("/api/sync", methods=["GET"])
def sync_get():
    user = _current_user()
    if not user:
        return jsonify({"error": "Not signed in."}), 401
    doc, version, updated = _stored(user["id"])
    return jsonify({"progress": doc, "version": version, "updatedAt": updated})


@bp.route("/api/sync", methods=["PUT"])
def sync_put():
    user = _current_user()
    if not user:
        return jsonify({"error": "Not signed in."}), 401
    if request.content_length and request.content_length > MAX_BYTES:
        return jsonify({"error": "Progress data is too large."}), 413
    body = _json_body()
    base = body.get("baseVersion")
    if isinstance(base, bool) or not isinstance(base, int) or base < 0:
        return jsonify({"error": "baseVersion is required."}), 400
    data, err = clean_progress(body.get("progress"))
    if err:
        return jsonify({"error": err}), 400

    doc = {"app": "logosdepth", "schemaVersion": 1, "data": data}
    conn = db()
    now = _now()
    if base == 0:
        cur = conn.execute(
            "INSERT OR IGNORE INTO progress (user_id, data, version, updated_at) VALUES (?, ?, 1, ?)",
            (user["id"], json.dumps(doc, separators=(",", ":")), now),
        )
    else:
        cur = conn.execute(
            "UPDATE progress SET data = ?, version = version + 1, updated_at = ? WHERE user_id = ? AND version = ?",
            (json.dumps(doc, separators=(",", ":")), now, user["id"], base),
        )
    conn.commit()
    if cur.rowcount != 1:
        # Another device saved first: hand back the current copy so the client can merge and retry.
        current, version, updated = _stored(user["id"])
        return jsonify({"error": "conflict", "progress": current, "version": version, "updatedAt": updated}), 409
    return jsonify({"ok": True, "version": base + 1, "updatedAt": now})


# ─── Account (privacy) ───────────────────────────────
@bp.route("/api/account/export")
def account_export():
    user = _current_user()
    if not user:
        return jsonify({"error": "Not signed in."}), 401
    doc, version, updated = _stored(user["id"])
    created = db().execute("SELECT created_at FROM users WHERE id = ?", (user["id"],)).fetchone()["created_at"]
    resp = jsonify(
        {"email": user["email"], "createdAt": created, "progress": doc, "version": version, "updatedAt": updated}
    )
    resp.headers["Content-Disposition"] = 'attachment; filename="logosdepth-account.json"'
    return resp


@bp.route("/api/account", methods=["DELETE"])
def account_delete():
    user = _current_user()
    if not user:
        return jsonify({"error": "Not signed in."}), 401
    conn = db()
    conn.execute("DELETE FROM login_tokens WHERE email = ?", (user["email"],))
    conn.execute("DELETE FROM users WHERE id = ?", (user["id"],))  # sessions and progress cascade
    conn.commit()
    resp = jsonify({"ok": True})
    resp.delete_cookie(COOKIE)
    return resp
