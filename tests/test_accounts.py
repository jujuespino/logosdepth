import copy

import pytest

import accounts
from app import app as flask_app

H = {"X-LD-CSRF": "1"}


def doc(srs=None, xp=0, streak=None):
    return {
        "app": "logosdepth",
        "schemaVersion": 1,
        "data": {"srs": srs or {}, "xp": xp, "streak": streak or {"last": "", "count": 0}, "settings": {}},
    }


CARD = {"stage": 1, "due": "2026-01-05", "days": ["2026-01-02"], "lapses": 0, "lastDate": "2026-01-02"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_RETURN_LINK", "1")
    monkeypatch.setenv("MAIL_BACKEND", "console")
    flask_app.config.update(ACCOUNTS_ENABLED=True, DATABASE_PATH=str(tmp_path / "t.db"), TESTING=True)
    yield flask_app.test_client()
    flask_app.config.update(ACCOUNTS_ENABLED=False, DATABASE_PATH=None)


def sign_in(client, email="a@example.com"):
    r = client.post("/api/auth/request", json={"email": email}, headers=H)
    assert r.status_code == 200
    token = r.get_json()["link"].split("login=")[1]
    v = client.post("/api/auth/verify", json={"token": token}, headers=H)
    assert v.status_code == 200
    return token


def test_disabled_by_default():
    flask_app.config.update(ACCOUNTS_ENABLED=False)
    c = flask_app.test_client()
    assert c.get("/api/auth/me").status_code == 404
    assert c.get("/api/config").get_json() == {"accounts": False}


def test_config_reports_enabled(client):
    assert client.get("/api/config").get_json() == {"accounts": True}


def test_csrf_header_required(client):
    assert client.post("/api/auth/request", json={"email": "a@example.com"}).status_code == 403


def test_bad_email_rejected(client):
    for bad in ["", "nope", "a@b", "a b@example.com", "x" * 300 + "@example.com"]:
        assert client.post("/api/auth/request", json={"email": bad}, headers=H).status_code == 400


def test_sign_in_flow_sets_hardened_cookie(client):
    r = client.post("/api/auth/request", json={"email": "A@Example.com "}, headers=H)
    token = r.get_json()["link"].split("login=")[1]
    assert client.get("/api/auth/me").get_json()["signedIn"] is False
    v = client.post("/api/auth/verify", json={"token": token}, headers=H)
    cookie = v.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie
    me = client.get("/api/auth/me").get_json()
    assert me == {"signedIn": True, "email": "a@example.com"}


def test_link_is_single_use(client):
    token = sign_in(client)
    other = flask_app.test_client()
    r = other.post("/api/auth/verify", json={"token": token}, headers=H)
    assert r.status_code == 400


def test_expired_link_rejected(client, monkeypatch):
    r = client.post("/api/auth/request", json={"email": "a@example.com"}, headers=H)
    token = r.get_json()["link"].split("login=")[1]
    real = accounts._now
    monkeypatch.setattr(accounts, "_now", lambda: real() + accounts.LOGIN_TTL + 5)
    assert client.post("/api/auth/verify", json={"token": token}, headers=H).status_code == 400


def test_garbage_token_rejected(client):
    assert client.post("/api/auth/verify", json={"token": "x" * 500}, headers=H).status_code == 400
    assert client.post("/api/auth/verify", json={"token": "nope"}, headers=H).status_code == 400
    assert client.post("/api/auth/verify", json={}, headers=H).status_code == 400


def test_rate_limit_per_email(client):
    codes = [client.post("/api/auth/request", json={"email": "a@example.com"}, headers=H).status_code for _ in range(7)]
    assert codes[:5] == [200] * 5
    assert codes[5:] == [429, 429]


def test_sync_requires_sign_in(client):
    assert client.get("/api/sync").status_code == 401
    assert client.put("/api/sync", json={"baseVersion": 0, "progress": doc()}, headers=H).status_code == 401


def test_sync_roundtrip_and_versions(client):
    sign_in(client)
    first = client.get("/api/sync").get_json()
    assert first["version"] == 0 and first["progress"]["data"]["srs"] == {}

    r = client.put("/api/sync", json={"baseVersion": 0, "progress": doc({"John 3:16": CARD}, xp=40)}, headers=H)
    assert r.get_json()["version"] == 1
    got = client.get("/api/sync").get_json()
    assert got["version"] == 1 and got["progress"]["data"]["xp"] == 40
    assert got["progress"]["data"]["srs"]["John 3:16"]["stage"] == 1

    r = client.put("/api/sync", json={"baseVersion": 1, "progress": doc({"John 3:16": CARD}, xp=50)}, headers=H)
    assert r.get_json()["version"] == 2


def test_stale_write_returns_conflict_with_current_copy(client):
    sign_in(client)
    client.put("/api/sync", json={"baseVersion": 0, "progress": doc(xp=10)}, headers=H)
    client.put("/api/sync", json={"baseVersion": 1, "progress": doc(xp=20)}, headers=H)
    r = client.put("/api/sync", json={"baseVersion": 1, "progress": doc(xp=99)}, headers=H)
    assert r.status_code == 409
    body = r.get_json()
    assert body["version"] == 2 and body["progress"]["data"]["xp"] == 20
    # first write when something is already stored is also a conflict, never an overwrite
    assert client.put("/api/sync", json={"baseVersion": 0, "progress": doc(xp=1)}, headers=H).status_code == 409


def test_sync_sanitizes_input(client):
    sign_in(client)
    bad = doc({"ok": CARD, "bad": {"stage": 99}, "__proto__": CARD, "k" * 100: CARD}, xp=-5)
    bad["data"]["settings"] = {"translation": "evil", "pack": "start", "extra": 1}
    client.put("/api/sync", json={"baseVersion": 0, "progress": bad}, headers=H)
    d = client.get("/api/sync").get_json()["progress"]["data"]
    assert list(d["srs"]) == ["ok"]
    assert d["xp"] == 0 and d["settings"] == {"pack": "start"}


def test_sync_rejects_foreign_documents(client):
    sign_in(client)
    for payload in [{"baseVersion": 0, "progress": {"app": "other"}}, {"baseVersion": 0}, {"progress": doc()},
                    {"baseVersion": "0", "progress": doc()}, {"baseVersion": -1, "progress": doc()}]:
        assert client.put("/api/sync", json=payload, headers=H).status_code == 400


def test_users_cannot_see_each_other(client):
    sign_in(client, "a@example.com")
    client.put("/api/sync", json={"baseVersion": 0, "progress": doc(xp=77)}, headers=H)
    other = flask_app.test_client()
    r = other.post("/api/auth/request", json={"email": "b@example.com"}, headers=H)
    other.post("/api/auth/verify", json={"token": r.get_json()["link"].split("login=")[1]}, headers=H)
    assert other.get("/api/sync").get_json()["progress"]["data"]["xp"] == 0


def test_logout_invalidates_session(client):
    sign_in(client)
    saved = client.get_cookie("ld_session").value
    client.post("/api/auth/logout", headers=H)
    assert client.get("/api/auth/me").get_json()["signedIn"] is False
    client.set_cookie("ld_session", saved)
    assert client.get("/api/auth/me").get_json()["signedIn"] is False


def test_logout_all_ends_other_sessions(client):
    sign_in(client)
    second = flask_app.test_client()
    r = second.post("/api/auth/request", json={"email": "a@example.com"}, headers=H)
    second.post("/api/auth/verify", json={"token": r.get_json()["link"].split("login=")[1]}, headers=H)
    assert second.get("/api/auth/me").get_json()["signedIn"] is True
    client.post("/api/auth/logout-all", headers=H)
    assert second.get("/api/auth/me").get_json()["signedIn"] is False


def test_export_then_delete_account(client):
    sign_in(client)
    client.put("/api/sync", json={"baseVersion": 0, "progress": doc({"John 3:16": CARD}, xp=5)}, headers=H)
    exp = client.get("/api/account/export").get_json()
    assert exp["email"] == "a@example.com" and exp["progress"]["data"]["xp"] == 5

    assert client.delete("/api/account").status_code == 403  # needs the CSRF header
    assert client.delete("/api/account", headers=H).status_code == 200
    assert client.get("/api/auth/me").get_json()["signedIn"] is False

    # Signing in again creates a brand-new, empty account: nothing was kept.
    sign_in(client)
    assert client.get("/api/sync").get_json()["version"] == 0
    with flask_app.app_context():
        conn = accounts.db()
        assert conn.execute("SELECT COUNT(*) FROM progress").fetchone()[0] == 0


def test_responses_are_not_cached(client):
    assert "no-store" in client.get("/api/auth/me").headers["Cache-Control"]


def test_input_not_mutated():
    from progress_schema import clean_progress
    original = doc({"x": CARD})
    snapshot = copy.deepcopy(original)
    clean_progress(original)
    assert original == snapshot
