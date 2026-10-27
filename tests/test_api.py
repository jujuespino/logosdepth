"""API tests using Flask's test client. Run: pytest"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import app  # noqa: E402


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    return app.test_client()


def test_index_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"LogosDepth" in r.data


def test_health(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.get_json()
    assert body["status"] == "ok" and body["verses"] > 0 and body["packs"] > 0


def test_security_headers(client):
    h = client.get("/").headers
    assert h["X-Content-Type-Options"] == "nosniff"
    assert h["X-Frame-Options"] == "DENY"
    assert "Referrer-Policy" in h


def test_fonts_are_cached_long_term(client):
    r = client.get("/static/fonts/inter-latin-400-normal.woff2")
    assert r.status_code == 200
    assert "immutable" in r.headers["Cache-Control"]


def test_no_external_requests_in_page(client):
    html = client.get("/").get_data(as_text=True)
    assert "fonts.googleapis.com" not in html and "fonts.gstatic.com" not in html


def test_verses_sorted_short_first(client):
    verses = client.get("/api/verses").get_json()
    lengths = [len(v["text"].split()) for v in verses]
    assert lengths == sorted(lengths)
    john = next(v for v in verses if v["ref"] == "John 3:16")
    assert john["translations"]["web"] and "kjv" not in john["translations"]
    assert "start" in john["packs"]
    assert not any("lexicon" in v or "align" in v for v in verses), "no original-language data is served"


def test_removed_word_study_routes_are_gone(client):
    for path in ("/api/search?q=love", "/api/word-of-day", "/api/categories", "/api/featured", "/api/words"):
        assert client.get(path).status_code == 404, path


def test_verses_without_web_still_served(client):
    verses = client.get("/api/verses").get_json()
    psalm = next(v for v in verses if v["ref"] == "Psalm 23:1")
    assert psalm["text"].startswith("The LORD is my shepherd")
    assert "web" not in psalm["translations"]


def test_packs_endpoint(client):
    packs = client.get("/api/packs").get_json()
    assert len(packs) >= 8
    start = next(p for p in packs if p["id"] == "start")
    assert start["count"] >= 10
    total = len(client.get("/api/verses").get_json())
    assert all(0 < p["count"] <= total for p in packs)


def test_unknown_route_404(client):
    assert client.get("/nope").status_code == 404


# ── PWA, service worker, compression ──
def test_manifest(client):
    r = client.get("/manifest.webmanifest")
    assert r.status_code == 200 and r.mimetype == "application/manifest+json"
    m = r.get_json()
    assert m["name"] == "LogosDepth" and m["display"] == "standalone" and m["start_url"].startswith("/")
    assert {i["purpose"] for i in m["icons"]} >= {"any", "maskable"}
    for icon in m["icons"]:
        assert client.get(icon["src"]).status_code == 200, icon["src"]


def test_service_worker_is_versioned_and_scoped_to_root(client):
    import app as app_module

    r = client.get("/sw.js")
    body = r.get_data(as_text=True)
    assert r.status_code == 200 and r.mimetype == "application/javascript"
    assert r.headers["Service-Worker-Allowed"] == "/" and r.headers["Cache-Control"] == "no-cache"
    assert app_module.ASSET_VERSION in body
    assert "__VERSION__" not in body and "__PRECACHE__" not in body
    precache = app_module.PRECACHE_URLS
    assert "/" in precache and "/static/css/style.css" in precache and "/static/js/verses.js" in precache
    assert "/static/sw.js" not in precache, "the worker must not precache itself"
    assert all(client.get(u).status_code == 200 for u in precache), "every precached URL must exist"


def test_asset_version_changes_when_an_asset_changes(tmp_path, monkeypatch):
    import app as app_module

    before = app_module._asset_version()
    assert before == app_module.ASSET_VERSION
    extra = app_module.STATIC_DIR / "css" / "_probe.css"
    extra.write_text("/* probe */")
    try:
        assert app_module._asset_version() != before
    finally:
        extra.unlink()
    assert app_module._asset_version() == before


def test_json_is_gzipped_when_accepted(client):
    import gzip
    import json

    r = client.get("/api/verses", headers={"Accept-Encoding": "gzip, deflate"})
    assert r.headers["Content-Encoding"] == "gzip" and "Accept-Encoding" in r.headers["Vary"]
    assert len(r.get_data()) < 150_000
    assert len(json.loads(gzip.decompress(r.get_data()))) >= 100
    assert int(r.headers["Content-Length"]) == len(r.get_data())


def test_no_compression_without_accept_header_or_for_tiny_bodies(client):
    assert "Content-Encoding" not in client.get("/api/verses").headers
    assert "Content-Encoding" not in client.get("/healthz", headers={"Accept-Encoding": "gzip"}).headers
