"""Validation of the shipped data files. Run: pytest"""
import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
LEXICON = json.loads((DATA / "lexicon.json").read_text(encoding="utf-8"))
VERSES = json.loads((DATA / "verses.json").read_text(encoding="utf-8"))

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
        assert t[-1] in ".?!;:", f"{v['ref']} doesn't end in punctuation"


def test_verse_lexicon_links_resolve():
    ids = {e["strongs_id"] for e in LEXICON}
    for v in VERSES:
        for w in v.get("words", []):
            assert w in ids, f"{v['ref']} links to unknown {w}"
