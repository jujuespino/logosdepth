"""Validation of the shipped data files. Run: pytest"""
import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
VERSES = json.loads((DATA / "verses.json").read_text(encoding="utf-8"))
PACKS = json.loads((DATA / "packs.json").read_text(encoding="utf-8"))

REF = re.compile(r"^(?:[1-3] )?[A-Z][a-z]+(?: of [A-Z][a-z]+)? \d{1,3}:\d{1,3}(?:-\d{1,3})?$")


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


def test_no_original_language_data_is_shipped():
    assert not (DATA / "lexicon.json").exists() and not (DATA / "lexicon_brief.json").exists()
    assert not (DATA / "bible" / "lexicon.json").exists()
    assert all("words" not in v for v in VERSES)
