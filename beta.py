"""Beta-test tools: opt-in anonymous usage events and a feedback form.

Off by default. Set BETA_ENABLED=1 to turn on. Design rules:
  * The client sends nothing unless the learner has opted in (see static/js/analytics.js).
  * Events carry a random install id, a name from a fixed list and at most one short value. No email,
    no verse text, no IP address and no user agent is stored. Rows are deleted after RETENTION_DAYS, and
    an install can erase its own rows (opting out does this automatically).
  * Feedback is explicit: it is stored only when the learner presses Send.
Read the results with scripts/metrics.py.
"""
import os
import re
from datetime import UTC, datetime, timedelta

from flask import Blueprint, current_app, jsonify, request

from store import client_ip, db, now, rate_limited

bp = Blueprint("beta", __name__)

RETENTION_DAYS = 180
MAX_EVENTS_PER_REQUEST = 20
INSTALL_ID = re.compile(r"^[0-9a-f]{32}$")
VALUE = re.compile(r"^[a-z0-9_.:-]{1,40}$")
EVENT_NAMES = {
    "app_open", "onboarding_done", "verse_started", "typed_attempt", "review_started", "review_finished",
    "backup_downloaded", "reminder_downloaded", "app_installed", "signed_in",
}
FEEDBACK_KINDS = {"bug", "idea", "confusing", "praise", "other"}


def beta_enabled() -> bool:
    return bool(current_app.config.get("BETA_ENABLED", os.environ.get("BETA_ENABLED") == "1"))


@bp.before_request
def _guard():
    if not beta_enabled():
        return jsonify({"error": "Beta tools are not enabled on this server."}), 404
    if request.method in ("POST", "PUT", "DELETE") and request.headers.get("X-LD-CSRF") != "1":
        return jsonify({"error": "Missing CSRF header."}), 403
    return None


@bp.after_request
def _no_store(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


def _body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _clean_value(v):
    """One short, boring value: a small integer, or a lowercase token. Anything else is dropped."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int) and 0 <= v <= 100000:
        return str(v)
    if isinstance(v, str) and VALUE.match(v):
        return v
    return None


def purge_old_events(conn, today=None) -> int:
    today = today or datetime.now(UTC).date()
    cutoff = (today - timedelta(days=RETENTION_DAYS)).isoformat()
    return conn.execute("DELETE FROM events WHERE day < ?", (cutoff,)).rowcount


@bp.route("/api/events", methods=["POST"])
def events_post():
    body = _body()
    install = body.get("installId")
    items = body.get("events")
    if not isinstance(install, str) or not INSTALL_ID.match(install) or not isinstance(items, list):
        return jsonify({"error": "Bad request."}), 400
    if rate_limited(f"events:{client_ip()}", "events"):
        return jsonify({"error": "Slow down."}), 429
    day = datetime.now(UTC).date().isoformat()
    rows = []
    for item in items[:MAX_EVENTS_PER_REQUEST]:
        if isinstance(item, dict) and item.get("name") in EVENT_NAMES:
            rows.append((day, install, item["name"], _clean_value(item.get("p"))))
    conn = db()
    if rows:
        conn.executemany("INSERT INTO events (day, install_id, name, prop) VALUES (?, ?, ?, ?)", rows)
    purge_old_events(conn)
    conn.commit()
    return "", 204


@bp.route("/api/events", methods=["DELETE"])
def events_delete():
    install = _body().get("installId")
    if not isinstance(install, str) or not INSTALL_ID.match(install):
        return jsonify({"error": "Bad request."}), 400
    conn = db()
    n = conn.execute("DELETE FROM events WHERE install_id = ?", (install,)).rowcount
    conn.commit()
    return jsonify({"ok": True, "deleted": n})


@bp.route("/api/feedback", methods=["POST"])
def feedback_post():
    body = _body()
    kind = body.get("kind")
    message = body.get("message")
    contact = body.get("contact") or None
    context = body.get("context") or None
    if kind not in FEEDBACK_KINDS or not isinstance(message, str) or not 3 <= len(message.strip()) <= 2000:
        return jsonify({"error": "Please write a few words (up to 2000 characters)."}), 400
    if contact is not None and (not isinstance(contact, str) or len(contact) > 254):
        return jsonify({"error": "That contact address is too long."}), 400
    if context is not None and (not isinstance(context, str) or len(context) > 200):
        context = None
    if rate_limited(f"feedback:{client_ip()}", "feedback"):
        return jsonify({"error": "Thanks! You have sent a lot of feedback recently. Please try again later."}), 429
    conn = db()
    conn.execute(
        "INSERT INTO feedback (created_at, kind, message, contact, context) VALUES (?, ?, ?, ?, ?)",
        (now(), kind, message.strip(), contact.strip() if contact else None, context),
    )
    conn.commit()
    return jsonify({"ok": True})
