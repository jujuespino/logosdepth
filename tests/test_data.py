"""Validation of the shipped data files. Run: pytest"""
import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
LEXICON = json.loads((DATA / "lexicon.json").read_text(encoding="utf-8"))
BRIEF = json.loads((DATA / "lexicon_brief.json").read_text(encoding="utf-8"))
VERSES = json.loads((DATA / "verses.json").read_text(encoding="utf-8"))
PACKS = json.loads((DATA / "packs.json").read_text(encoding="utf-8"))

HEBREW = re.compile(r"[֐-׿]")
GREEK = re.compile(r"[Ͱ-Ͽἀ-῿]")
REF = re.compile(r"^(?:[1-3] )?[A-Z][a-z]+(?: of [A-Z][a-z]+)? \d{1,3}:\d{1,3}(?:-\d{1,3})?$")


def test_lexicon_required_fields():
    required = ["strongs_id", "original", "transliteration", "language", "category", "definition", "english_keywords"]
    for e in LEXICON:
        for field in required:
            assert e.get(field), f"{e.get('strongs_id')} missing {field}"
        assert isinstance(e["english_keywords"], list) and e["english_keywords"]


def test_lexicon_ids_unique_and_match_language():
    ids = [e["strongs_id"] for e in LEXICON]
    assert len(ids) == len(set(ids)), "duplicate Strong's IDs"
    for e in LEXICON:
        assert e["language"] in ("Hebrew", "Greek"), e["strongs_id"]
        assert e["strongs_id"][0] == e["language"][0], f"{e['strongs_id']} prefix vs {e['language']}"
        assert re.fullmatch(r"[HG]\d{1,4}", e["strongs_id"]), e["strongs_id"]


def test_lexicon_script_matches_language():
    for e in LEXICON:
        pattern = HEBREW if e["language"] == "Hebrew" else GREEK
        assert pattern.search(e["original"]), f"{e['strongs_id']} original script doesn't match language"


def test_lexicon_numbers_sane():
    for e in LEXICON:
        if "usage_count" in e:
            assert isinstance(e["usage_count"], int) and e["usage_count"] >= 0, e["strongs_id"]


def test_verse_refs_unique_and_well_formed():
    refs = [v["ref"] for v in VERSES]
    assert len(refs) == len(set(refs)), "duplicate verse references"
    for r in refs:
        assert REF.match(r), f"odd reference format: {r}"


def test_verse_texts_clean():
    texts = [v["text"] for v in VERSES]
    assert len(texts) == len(set(texts)), "duplicate verse texts"
    for v in VERSES:
        t = v["text"]
        assert t == t.strip(), v["ref"]
        assert "  " not in t, f"{v['ref']} has a double space"
        assert "\n" not in t, v["ref"]
        assert len(t.split()) >= 5, f"{v['ref']} is very short"
        assert t[-1] in ".?!;:)", f"{v['ref']} doesn't end in punctuation"


def test_verse_lexicon_links_resolve():
    ids = {e["strongs_id"] for e in LEXICON} | {e["strongs_id"] for e in BRIEF}
    for v in VERSES:
        assert len(v["words"]) <= 10, v["ref"]
        assert len(v["words"]) == len(set(v["words"])), f"{v['ref']} has duplicate word links"
        for w in v["words"]:
            assert w in ids, f"{v['ref']} links to unknown {w}"


def test_at_least_100_verses():
    assert len(VERSES) >= 100


def test_translations_are_clean_when_present():
    for v in VERSES:
        web = v.get("translations", {}).get("web")
        if web is None:
            continue
        assert web == web.strip() and "  " not in web, v["ref"]
        assert len(web.split()) >= 5, v["ref"]
        assert not re.match(r"(?i)^(A Psalm|A Song|By |For the Chief Musician)", web), f"{v['ref']} WEB has a superscription"


def test_brief_entries_complete_and_distinct_from_curated():
    curated = {e["strongs_id"] for e in LEXICON}
    seen = set()
    for e in BRIEF:
        sid = e["strongs_id"]
        assert sid not in curated, f"{sid} is both curated and brief"
        assert sid not in seen, f"duplicate brief entry {sid}"
        seen.add(sid)
        assert re.fullmatch(r"[HG]\d{1,4}", sid), sid
        for field in ("original", "transliteration", "definition", "language", "source"):
            assert e.get(field), f"{sid} missing {field}"
        assert e["brief"] is True and e["usage_count"] >= 0
        assert e["language"] == ("Hebrew" if sid[0] == "H" else "Greek")


def test_every_brief_entry_is_linked_from_a_verse():
    linked = {w for v in VERSES for w in v["words"]}
    assert {e["strongs_id"] for e in BRIEF} <= linked


def test_packs_reference_existing_verses_and_agree_with_verse_tags():
    refs = {v["ref"] for v in VERSES}
    pack_ids = {p["id"] for p in PACKS}
    assert len(pack_ids) == len(PACKS), "duplicate pack ids"
    for p in PACKS:
        assert p["title"] and p["description"]
        for r in p["refs"]:
            assert r in refs, f"pack {p['id']} lists {r}, which has no verse"
    for v in VERSES:
        assert v["packs"], f"{v['ref']} is in no pack"
        for pid in v["packs"]:
            assert pid in pack_ids
            assert v["ref"] in next(p for p in PACKS if p["id"] == pid)["refs"]


def test_lexicon_regression_hamartia_is_g266():
    by = {e["strongs_id"]: e for e in LEXICON}
    assert "G265" not in by and by["G266"]["transliteration"] == "Hamartia"
