import json
import re
from pathlib import Path

import pytest

from app import LEXICON_BY_ID, VERSES
from app import app as flask_app
from bible import MAX_VERSES, MAX_WORDS, _book, _index, _lexicon

DATA = Path(__file__).resolve().parent.parent / "data" / "bible"


@pytest.fixture(scope="module")
def client():
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def test_every_book_chapter_and_verse_is_present():
    index = _index()
    assert len(index) == 66
    assert [b["testament"] for b in index].count("OT") == 39
    assert sum(len(b["chapters"]) for b in index) == 1189
    assert sum(sum(b["chapters"]) for b in index) == 31102
    names = [b["name"] for b in index]
    assert names[0] == "Genesis" and names[-1] == "Revelation" and "Song of Solomon" in names and "Psalms" in names


def test_known_verse_counts():
    by = {b["name"]: b["chapters"] for b in _index()}
    assert by["Psalms"][118] == 176 and by["Psalms"][116] == 2   # Psalm 119 and 117
    assert by["John"][2] == 36 and by["Genesis"][0] == 31 and by["3 John"] == [14]


def test_no_empty_or_stray_markup_in_any_verse():
    for b in _index():
        for ch in _book(b["slug"])["chapters"]:
            for kjv, web, ids in ch:
                assert kjv.strip() and not re.search(r"[#\[\]]|\s{2,}", kjv), (b["name"], kjv[:40])
                assert web is None or (web.strip() and not re.search(r"\s{2,}", web))
                assert len(ids) <= 10


def test_every_linked_word_resolves():
    curated = {k for k, v in LEXICON_BY_ID.items() if not v.get("brief")}
    lex = _lexicon()
    for b in _index():
        for ch in _book(b["slug"])["chapters"]:
            for _, _, ids in ch:
                for sid in ids:
                    assert sid in curated or sid in lex, sid


def test_lexicon_entries_have_the_fields_the_word_modal_needs():
    for sid, e in list(_lexicon().items())[:500]:
        assert e["strongs_id"] == sid and e["original"] and e["language"] in ("Hebrew", "Greek") and e["brief"] is True
        assert e["source"].startswith("STEPBible")


def test_curated_verses_match_the_whole_bible_text(client):
    """The hand-picked verses and the full Bible are built separately; they must agree word for word."""
    bad = []
    for v in VERSES:
        r = client.get("/api/passage", query_string={"ref": v["ref"]})
        if r.status_code != 200:
            bad.append((v["ref"], r.get_json()))
            continue
        if r.get_json()["text"] != v["text"]:
            bad.append((v["ref"], "text differs"))
    assert not bad, bad[:5]


def test_chapter_endpoint(client):
    r = client.get("/api/bible/john/3").get_json()
    assert r["book"] == "John" and r["chapter"] == 3 and len(r["verses"]) == 36
    assert r["verses"][15]["n"] == 16 and r["verses"][15]["kjv"].startswith("For God so loved the world")
    assert r["verses"][15]["web"]
    assert client.get("/api/bible/john/22").status_code == 404
    assert client.get("/api/bible/nowhere/1").status_code == 404
    assert client.get("/api/bible/john/0").status_code == 404


def test_passage_single_verse_and_range(client):
    one = client.get("/api/passage", query_string={"ref": "John 3:16"}).get_json()
    assert one["ref"] == "John 3:16" and "everlasting life" in one["text"] and one["packs"] == ["mine"]
    assert {e["strongs_id"] for e in one["lexicon"]} & {"G25", "G4100"}
    rng = client.get("/api/passage", query_string={"ref": "Psalm 23:1-3"}).get_json()
    assert rng["ref"] == "Psalm 23:1-3" and rng["text"].startswith("The LORD is my shepherd") and "for his name's sake." in rng["text"]
    assert "translations" not in rng   # Psalm 23:1 opens with a superscription in the WEB, so the range is KJV-only
    web = client.get("/api/passage", query_string={"ref": "Psalm 23:2-3"}).get_json()
    assert web["translations"]["web"].startswith("He makes me lie down")


def test_passage_naming_variants(client):
    for ref in ("Psalms 23:1", "psalm 23:1", "  Psalm 23:1  "):
        assert client.get("/api/passage", query_string={"ref": ref}).get_json()["ref"] == "Psalm 23:1"
    s = client.get("/api/passage", query_string={"ref": "Song of Solomon 2:4"}).get_json()
    assert s["ref"] == "Song of Solomon 2:4"
    assert client.get("/api/passage", query_string={"ref": "1 John 4:19"}).get_json()["ref"] == "1 John 4:19"


@pytest.mark.parametrize("ref", ["", "John", "John 3", "John 3:", "Hezekiah 1:1", "John 99:1", "John 3:99", "John 3:5-2",
                                 "Genesis 1:1-31", "<script>", "John 3:16; Mark 1:1", "A" * 200])
def test_bad_passages_are_rejected_politely(client, ref):
    r = client.get("/api/passage", query_string={"ref": ref})
    assert r.status_code == 400 and r.get_json()["error"]


def test_limits_are_enforced(client):
    too_many = client.get("/api/passage", query_string={"ref": f"Psalm 119:1-{MAX_VERSES + 1}"})
    assert too_many.status_code == 400 and "at most" in too_many.get_json()["error"]
    long_words = client.get("/api/passage", query_string={"ref": f"Revelation 1:1-{MAX_VERSES}"})
    assert long_words.status_code == 400 and str(MAX_WORDS) in long_words.get_json()["error"]
    assert client.get("/api/passage", query_string={"ref": "Psalm 23:1-6"}).status_code == 200


def test_web_only_where_it_lines_up(client):
    assert client.get("/api/bible/romans/14").get_json()["verses"][0]["web"] is None      # numbering differs
    assert client.get("/api/bible/psalms/3").get_json()["verses"][0]["web"] is None       # superscription
    assert client.get("/api/bible/romans/8").get_json()["verses"][0]["web"]


def test_whole_bible_data_files_are_reasonable_in_size():
    total = sum(p.stat().st_size for p in DATA.glob("*.json"))
    assert 8_000_000 < total < 25_000_000
    json.loads((DATA / "index.json").read_text())
