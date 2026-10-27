import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

import store
from app import app as flask_app

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import metrics  # noqa: E402

H = {"X-LD-CSRF": "1"}
ID = "a" * 32
ID2 = "b" * 32


@pytest.fixture
def client(tmp_path):
    flask_app.config.update(BETA_ENABLED=True, DATABASE_PATH=str(tmp_path / "b.db"), TESTING=True)
    yield flask_app.test_client()
    flask_app.config.update(BETA_ENABLED=False, DATABASE_PATH=None)


def rows(client, sql):
    with flask_app.app_context():
        return [tuple(r) for r in store.db().execute(sql).fetchall()]


def test_disabled_by_default():
    flask_app.config.update(BETA_ENABLED=False)
    c = flask_app.test_client()
    assert c.post("/api/events", json={}, headers=H).status_code == 404
    assert c.post("/api/feedback", json={}, headers=H).status_code == 404
    assert c.get("/api/config").get_json()["beta"] is False


def test_config_reports_beta(client):
    assert client.get("/api/config").get_json()["beta"] is True


def test_requires_csrf_header(client):
    assert client.post("/api/events", json={"installId": ID, "events": []}).status_code == 403
    assert client.post("/api/feedback", json={"kind": "bug", "message": "hello there"}).status_code == 403


def test_events_stored_with_allowlisted_names_and_clean_values(client):
    r = client.post("/api/events", headers=H, json={"installId": ID, "events": [
        {"name": "app_open"},
        {"name": "typed_attempt", "p": "perfect"},
        {"name": "review_finished", "p": 4},
        {"name": "typed_attempt", "p": "John 3:16 is my favorite verse"},   # free text: value dropped
        {"name": "steal_cookies", "p": "x"},                                # unknown name: row dropped
        {"name": "app_open", "p": True},                                    # bool is not a value
        "not a dict",
    ]})
    assert r.status_code == 204
    got = rows(client, "SELECT name, prop FROM events ORDER BY rowid")
    assert got == [("app_open", None), ("typed_attempt", "perfect"), ("review_finished", "4"),
                   ("typed_attempt", None), ("app_open", None)]


def test_events_store_no_identifying_columns(client):
    client.post("/api/events", headers={**H, "User-Agent": "SecretBrowser/1.0"},
                json={"installId": ID, "events": [{"name": "app_open"}]},
                environ_overrides={"REMOTE_ADDR": "203.0.113.9"})
    with flask_app.app_context():
        cols = [r[1] for r in store.db().execute("PRAGMA table_info(events)")]
        assert cols == ["day", "install_id", "name", "prop"]
        dump = " ".join(str(tuple(r)) for t in ("events", "rate_events") for r in store.db().execute(f"SELECT * FROM {t}"))
    assert "203.0.113.9" not in dump and "SecretBrowser" not in dump


def test_bad_install_ids_and_payloads_rejected(client):
    for body in [{}, {"installId": "short", "events": []}, {"installId": ID}, {"installId": "G" * 32, "events": []},
                 {"installId": ID, "events": "nope"}, {"installId": 5, "events": []}]:
        assert client.post("/api/events", headers=H, json=body).status_code == 400


def test_at_most_20_events_per_request(client):
    client.post("/api/events", headers=H, json={"installId": ID, "events": [{"name": "app_open"}] * 50})
    assert rows(client, "SELECT COUNT(*) FROM events")[0][0] == 20


def test_events_rate_limited(client):
    codes = {client.post("/api/events", headers=H, json={"installId": ID, "events": []}).status_code for _ in range(125)}
    assert 429 in codes


def test_install_can_erase_its_own_events_only(client):
    for i in (ID, ID2):
        client.post("/api/events", headers=H, json={"installId": i, "events": [{"name": "app_open"}]})
    r = client.delete("/api/events", headers=H, json={"installId": ID})
    assert r.get_json() == {"ok": True, "deleted": 1}
    assert rows(client, "SELECT install_id FROM events") == [(ID2,)]


def test_old_events_are_purged(client):
    with flask_app.app_context():
        conn = store.db()
        old = (date.today() - timedelta(days=200)).isoformat()
        conn.execute("INSERT INTO events (day, install_id, name) VALUES (?, ?, 'app_open')", (old, ID2))
        conn.commit()
    client.post("/api/events", headers=H, json={"installId": ID, "events": [{"name": "app_open"}]})
    assert rows(client, "SELECT install_id FROM events") == [(ID,)]


def test_feedback_roundtrip_and_validation(client):
    ok = client.post("/api/feedback", headers=H, json={"kind": "idea", "message": "  Please add Psalm 1  ",
                                                         "contact": "me@example.com", "context": "view=verses"})
    assert ok.status_code == 200
    assert rows(client, "SELECT kind, message, contact, context FROM feedback") == [
        ("idea", "Please add Psalm 1", "me@example.com", "view=verses")]
    for bad in [{"kind": "spam", "message": "hello there"}, {"kind": "bug", "message": "hi"},
                {"kind": "bug", "message": "x" * 2001}, {"kind": "bug"}, {"kind": "bug", "message": "hello", "contact": "x" * 300}]:
        assert client.post("/api/feedback", headers=H, json=bad).status_code == 400


def test_feedback_rate_limited(client):
    codes = [client.post("/api/feedback", headers=H, json={"kind": "bug", "message": "something broke"}).status_code
             for _ in range(7)]
    assert codes[:5] == [200] * 5 and codes[5:] == [429, 429]


# ── metrics script ──
def seed(conn, installs):
    conn.executescript(store.SCHEMA)
    for install, days in installs.items():
        for d, names in days.items():
            for n in names:
                name, _, prop = n.partition(":")
                conn.execute("INSERT INTO events (day, install_id, name, prop) VALUES (?, ?, ?, ?)",
                             (d, install, name, prop or None))
    conn.commit()


def test_metrics_retention_and_funnel():
    today = date(2026, 11, 20)
    d = lambda n: (today - timedelta(days=n)).isoformat()  # noqa: E731
    conn = sqlite3.connect(":memory:")
    seed(conn, {
        "i1": {d(10): ["app_open", "onboarding_done", "verse_started", "typed_attempt:perfect"],
               d(9): ["app_open", "review_started", "review_finished:2"], d(3): ["app_open"]},
        "i2": {d(10): ["app_open", "verse_started", "typed_attempt:miss"]},
        "i3": {d(0): ["app_open"]},                      # too new for any retention window
    })
    rep = metrics.compute(conn, today)
    assert rep["installs_opted_in"] == 3
    assert rep["retention"]["day1"] == {"eligible": 2, "returned": 1, "rate": 0.5}
    assert rep["retention"]["day7"] == {"eligible": 2, "returned": 1, "rate": 0.5}
    assert rep["retention"]["day30"]["eligible"] == 0 and rep["retention"]["day30"]["rate"] is None
    f = {x["step"]: x["installs"] for x in rep["funnel"]}
    assert f["opened the app"] == 3 and f["started a verse"] == 2
    assert f["recalled a verse perfectly"] == 1 and f["finished a daily review"] == 1
    assert rep["typed_attempt_outcomes"] == {"perfect": 1, "miss": 1}
    assert rep["daily_active"][-1] == {"day": today.isoformat(), "active": 1}
    assert "Funnel" in metrics.render(rep)


def test_metrics_handles_empty_database():
    conn = sqlite3.connect(":memory:")
    seed(conn, {})
    rep = metrics.compute(conn, date(2026, 11, 20))
    assert rep["installs_opted_in"] == 0 and rep["retention"]["day1"]["rate"] is None
    assert "n/a" in metrics.render(rep)
