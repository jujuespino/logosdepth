#!/usr/bin/env python3
"""Build the whole-Bible data in data/bible/ from the same public datasets as build_content.py.

Outputs (all generated; do not edit by hand):
  data/bible/index.json            books in canonical order: name, ref name, slug, testament, verses per chapter
  data/bible/<slug>.json           one file per book: chapters -> verses -> [kjv, web|null, [ids], "token:idIndex,..."]
  data/bible/lexicon.json          brief word entries for every Strong's id referenced (excluding the curated 83)

Run scripts/fetch_sources.sh first. Usage:  python3 scripts/build_bible.py [--check]
Rules: KJV (1769) is complete. WEB is included per verse only when it lines up with the KJV numbering:
chapters whose verse numbering differs are left KJV-only, and WEB verses that open with a psalm
superscription are omitted (same rules as the curated verses). Up to 10 linked words per verse, curated words
first. The fourth item of each verse says which words of the KJV text carry which linked word, so the app can show
the Hebrew or Greek word behind an English word.
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


def norm(w):
    return re.sub(r"[^a-z0-9']", "", w.lower().replace("\u2019", "'"))


def tagged_words(name, osis_name_map, chapter, verse):
    """The CrossWire words (English text + Strong's ids) for one verse, in order."""
    root = bc.SRC / "node_modules/@metaxia/scriptures-source-crosswire-kjv/data/crosswire-KJV"
    f = root / osis_name_map / str(chapter) / f"{verse}.json"
    return json.loads(f.read_text(encoding="utf-8")).get("words", [])


def align(kjv_text, words, keep_ids):
    """Match each tagged English word to a token of the verse text (tokens = whitespace-separated words).

    Returns [(token_index, strongs_id)] for ids in keep_ids. Words are matched left to right; a tag that can't
    be found within a few tokens is skipped, so one odd word never throws the rest of the verse out of step."""
    tokens = [norm(t) for t in kjv_text.split()]
    ptr, pairs, matched, total = 0, [], 0, 0
    for w in words:
        sub = [norm(x) for x in (w.get("text") or "").split()]
        sub = [x for x in sub if x]
        ids = [i for i in bc.word_ids(w) if i in keep_ids]
        for x in sub:
            total += 1
            k = next((j for j in range(ptr, min(ptr + 6, len(tokens))) if tokens[j] == x), None)
            if k is None:
                continue
            matched += 1
            ptr = k + 1
            for i in ids:
                pairs.append((k, i))
    return pairs, matched, total


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def main():
    check_only = "--check" in sys.argv
    kjv = bc.load_kjv_text()
    books = list(dict.fromkeys(k.rsplit(" ", 1)[0] for k in kjv))
    assert len(books) == 66, len(books)
    web = bc.load_web(books)
    counts, renderings, verse_ids = bc.index_tagged_kjv(books)

    step_dir = bc.SRC / "node_modules/@metaxia/scriptures-source-stepbible-lexicon/data"
    g = json.loads((step_dir / "stepbible-tbesg.json").read_text(encoding="utf-8"))
    h = json.loads((step_dir / "stepbible-tbesh.json").read_text(encoding="utf-8"))
    curated = {e["strongs_id"] for e in json.loads((bc.DATA / "lexicon.json").read_text(encoding="utf-8"))}

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

    brief, index, stats, used = {}, [], {"verses": 0, "web": 0, "words": 0, "matched": 0, "tokens": 0}, set()
    osis_of = dict(zip(books, bc.OSIS, strict=True))
    OUT.mkdir(parents=True, exist_ok=True)
    for bi, name in enumerate(books):
        chapters = []
        nchap = max(ch for (b, ch) in kc if b == name)
        for ch in range(1, nchap + 1):
            verses = []
            for v in kc[(name, ch)]:
                key = f"{name} {ch}:{v}"
                text = bc.clean_kjv(kjv[key])
                w = web.get(key)
                if (name, ch) in mismatched or not w or bc.SUPERSCRIPTION.match(w):
                    w = None
                linked, seen = [], set()
                for sid in verse_ids.get(key, []):
                    if sid in seen:
                        continue
                    seen.add(sid)
                    if sid in curated:
                        linked.append((0, counts[sid], sid))
                        continue
                    step = bc.step_lookup(sid, g, h)
                    if step and bc.is_content(step):
                        if sid not in brief:
                            brief[sid] = bc.brief_entry(sid, step, counts, renderings)
                        linked.append((1, counts[sid], sid))
                linked.sort()
                ids = [sid for _, _, sid in linked[:bc.MAX_LINKED_WORDS]]
                used.update(ids)
                words_tagged = tagged_words(name, osis_of[name], ch, v)
                pairs, matched, total = align(text, words_tagged, set(ids))
                stats["matched"] += matched
                stats["tokens"] += total
                al = ",".join(f"{k}:{ids.index(i)}" for k, i in pairs)
                verses.append([text, re.sub(r"\s+", " ", w).strip() if w else None, ids, al])
                stats["verses"] += 1
                stats["web"] += bool(w)
                stats["words"] += len(ids)
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

    lexicon = [brief[s] for s in sorted(used & brief.keys(), key=lambda s: (s[0], int(s[1:])))]
    print(f"books: {len(index)} | verses: {stats['verses']} (KJV) | with WEB: {stats['web']} | "
          f"linked words: {stats['words']} | lexicon entries: {len(lexicon)}")
    print(f"alignment: {stats['matched']} of {stats['tokens']} tagged English words matched to verse tokens "
          f"({100 * stats['matched'] / stats['tokens']:.1f}%)")
    print(f"WEB left out for {len(mismatched)} chapters with different numbering: {sorted(mismatched)}")
    assert stats["verses"] == 31102
    if check_only:
        return 0
    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (OUT / "lexicon.json").write_text(json.dumps(lexicon, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
