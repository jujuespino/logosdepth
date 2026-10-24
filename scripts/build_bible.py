#!/usr/bin/env python3
"""Build the whole-Bible data in data/bible/ from the same public datasets as build_content.py.

Outputs (all generated; do not edit by hand):
  data/bible/index.json     books in canonical order: name, ref name, slug, testament, verses per chapter
  data/bible/<slug>.json    one file per book: chapters -> verses -> [kjv, web|null]

Run scripts/fetch_sources.sh first. Usage:  python3 scripts/build_bible.py [--check]
Rules: KJV (1769) is complete. WEB is included per verse only when it lines up with the KJV numbering:
chapters whose verse numbering differs are left KJV-only, and WEB verses that open with a psalm
superscription are omitted (same rules as the starter verses).
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_content as bc  # noqa: E402

OUT = bc.DATA / "bible"
REF_NAME = {"Psalms": "Psalm", "Solomon's Song": "Song of Solomon"}
DISPLAY = {"Psalms": "Psalms", "Solomon's Song": "Song of Solomon"}
NEW_TESTAMENT_FROM = "Matthew"


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def main():
    check_only = "--check" in sys.argv
    kjv = bc.load_kjv_text()
    books = list(dict.fromkeys(k.rsplit(" ", 1)[0] for k in kjv))
    assert len(books) == 66, len(books)
    web = bc.load_web(books)

    # chapters whose WEB numbering differs from the KJV: keep them KJV-only
    def chapter_numbers(source):
        out = {}
        for key in source:
            book, cv = key.rsplit(" ", 1)
            ch, v = cv.split(":")
            out.setdefault((book, int(ch)), []).append(int(v))
        return {k: sorted(v) for k, v in out.items()}
    kc, wc = chapter_numbers(kjv), chapter_numbers(web)
    mismatched = {k for k in kc if wc.get(k) != kc[k]}

    index, stats = [], {"verses": 0, "web": 0}
    OUT.mkdir(parents=True, exist_ok=True)
    for bi, name in enumerate(books):
        chapters = []
        nchap = max(ch for (b, ch) in kc if b == name)
        for ch in range(1, nchap + 1):
            verses = []
            for v in kc[(name, ch)]:
                key = f"{name} {ch}:{v}"
                w = web.get(key)
                if (name, ch) in mismatched or not w or bc.SUPERSCRIPTION.match(w):
                    w = None
                verses.append([bc.clean_kjv(kjv[key]), re.sub(r"\s+", " ", w).strip() if w else None])
                stats["verses"] += 1
                stats["web"] += bool(w)
            chapters.append(verses)
        slug = slugify(DISPLAY.get(name, name))
        index.append({
            "name": DISPLAY.get(name, name), "ref_name": REF_NAME.get(name, name), "slug": slug,
            "testament": "NT" if bi >= books.index(NEW_TESTAMENT_FROM) else "OT",
            "chapters": [len(c) for c in chapters],
        })
        if not check_only:
            payload = {"book": DISPLAY.get(name, name), "chapters": chapters}
            (OUT / f"{slug}.json").write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print(f"books: {len(index)} | verses: {stats['verses']} (KJV) | with WEB: {stats['web']}")
    print(f"WEB left out for {len(mismatched)} chapters with different numbering: {sorted(mismatched)}")
    assert stats["verses"] == 31102
    if check_only:
        return 0
    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
