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
    assert body["status"] == "ok" and body["lexicon"] > 0 and body["verses"] > 0


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


def test_search_by_keyword(client):
    body = client.get("/api/search?q=love").get_json()
    assert body["results"], "expected results for 'love'"
    assert any(e["strongs_id"] == "G26" for e in body["results"])


def test_search_empty_returns_nothing(client):
    assert client.get("/api/search").get_json()["results"] == []


def test_search_language_filter(client):
    results = client.get("/api/search?q=love&lang=hebrew").get_json()["results"]
    assert results and all(e["language"] == "Hebrew" for e in results)


def test_search_category_filter(client):
    cats = client.get("/api/categories").get_json()
    name = cats[0]["name"]
    results = client.get(f"/api/search?category={name}").get_json()["results"]
    assert results and all(e["category"] == name for e in results)


def test_categories_counts_add_up(client):
    cats = client.get("/api/categories").get_json()
    for c in cats:
        assert c["count"] == c["hebrew"] + c["greek"]


def test_word_of_day_is_stable_within_a_day(client):
    a = client.get("/api/word-of-day").get_json()
    b = client.get("/api/word-of-day").get_json()
    assert a["strongs_id"] == b["strongs_id"]


def test_featured_has_entries(client):
    assert len(client.get("/api/featured").get_json()) >= 5


@pytest.mark.parametrize("lang,prefix", [("hebrew", "H"), ("greek", "G")])
def test_words_language_filter(client, lang, prefix):
    words = client.get(f"/api/words?lang={lang}").get_json()
    assert words and all(w["strongs_id"].startswith(prefix) for w in words)


def test_words_all_returns_everything(client):
    assert len(client.get("/api/words").get_json()) == client.get("/healthz").get_json()["lexicon"]


def test_verses_sorted_short_first_with_resolved_lexicon(client):
    verses = client.get("/api/verses").get_json()
    lengths = [len(v["text"].split()) for v in verses]
    assert lengths == sorted(lengths)
    john = next(v for v in verses if v["ref"] == "John 3:16")
    assert {e["strongs_id"] for e in john["lexicon"]} >= {"G26", "G4102"}
    assert all(isinstance(e, dict) for v in verses for e in v["lexicon"])


def test_unknown_route_404(client):
    assert client.get("/nope").status_code == 404
