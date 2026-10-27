#!/usr/bin/env python3
"""Build data/verses.json (the starter verses) from public datasets.

Inputs (fetch with scripts/fetch_sources.sh):
  - KJV 1769 text .................. es-kjv (public domain)
  - World English Bible ............ midvash/bible-data (public domain)
Curated input: data/packs.json (which verses, grouped into packs)

Usage:  python3 scripts/build_content.py [--check]
        --check  report problems without writing files
Set CONTENT_SRC to read the datasets from somewhere other than scripts/sources.
"""
import collections
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(os.environ.get("CONTENT_SRC", ROOT / "scripts" / "sources"))
DATA = ROOT / "data"

MIN_WORDS, MAX_WORDS = 5, 55

# WEB puts a psalm's superscription inside verse 1 ("A Psalm by David. The LORD is my shepherd..."),
# whereas the KJV numbering leaves it out. Such verses can't be matched word-for-word, so WEB is omitted.
SUPERSCRIPTION = re.compile(r"^(A Psalm|A Song|A Contemplation|A Prayer|A Miktam|A Maskil|A Praise|A Poem|By |Of David|"
                            r"For the Chief Musician|To the Chief Musician|According to|Psalm of)", re.I)


def load_kjv_text():
    raw = (SRC / "node_modules/es-kjv/json/verses-1769.js").read_text(encoding="utf-8")
    return json.loads(raw.split("export default", 1)[1].strip().rstrip(";"))


def clean_kjv(t):
    return re.sub(r"\s+", " ", t.replace("#", "").replace("[", "").replace("]", "")).strip()


def load_web(book_names):
    web = json.loads((SRC / "web.json").read_text(encoding="utf-8"))
    out = {}
    for name, book in zip(book_names, web["books"], strict=True):
        for ci, ch in enumerate(book["chapters"], 1):
            for v in ch["verses"]:
                out[f"{name} {ci}:{v['number']}"] = re.sub(r"\s+", " ", v["text"]).strip()
    return out


def kjv_keys(ref):
    """'Psalm 23:1' -> ['Psalms 23:1'];  'John 3:16-17' -> ['John 3:16', 'John 3:17']"""
    book, rest = ref.rsplit(" ", 1)
    book = {"Psalm": "Psalms"}.get(book, book)
    ch, vs = rest.split(":")
    a, _, b = vs.partition("-")
    return [f"{book} {ch}:{i}" for i in range(int(a), int(b or a) + 1)]


def main():
    check_only = "--check" in sys.argv
    kjv = load_kjv_text()
    kjv_books = list(dict.fromkeys(k.rsplit(" ", 1)[0] for k in kjv))
    assert len(kjv_books) == 66, len(kjv_books)
    web = load_web(kjv_books)
    packs = json.loads((DATA / "packs.json").read_text(encoding="utf-8"))

    order, pack_of = [], collections.defaultdict(list)
    for p in packs:
        for ref in p["refs"]:
            if ref not in pack_of:
                order.append(ref)
            pack_of[ref].append(p["id"])

    verses, problems, notes = [], [], []
    for ref in order:
        keys = kjv_keys(ref)
        missing = [k for k in keys if k not in kjv]
        if missing:
            problems.append(f"{ref}: not in KJV dataset ({missing[0]})")
            continue
        text = " ".join(clean_kjv(kjv[k]) for k in keys)
        n = len(text.split())
        if not MIN_WORDS <= n <= MAX_WORDS:
            problems.append(f"{ref}: {n} words (allowed {MIN_WORDS}-{MAX_WORDS})")
            continue
        entry = {"ref": ref, "text": text, "packs": pack_of[ref]}
        if not all(k in web for k in keys):
            problems.append(f"{ref}: missing from WEB dataset (KJV only)")
        elif SUPERSCRIPTION.match(web[keys[0]]):
            notes.append(f"{ref}: WEB verse starts with a superscription; WEB omitted")
        else:
            entry["translations"] = {"web": " ".join(web[k] for k in keys)}
        verses.append(entry)

    print(f"verses built: {len(verses)} of {len(order)} requested")
    print(f"packs: {len(packs)} | verses with WEB text: {sum('translations' in v for v in verses)}")
    for n in notes:
        print("  note:", n)
    for p in problems:
        print("  PROBLEM:", p)
    if check_only:
        return 1 if problems else 0

    (DATA / "verses.json").write_text(json.dumps(verses, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("wrote data/verses.json")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
