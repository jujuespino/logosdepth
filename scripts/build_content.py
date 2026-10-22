#!/usr/bin/env python3
"""Build data/verses.json and data/lexicon_brief.json from public datasets.

Inputs (fetch with scripts/fetch_sources.sh):
  - KJV 1769 text .................. es-kjv (public domain)
  - KJV with Strong's tags ......... CrossWire KJV via @metaxia (public domain text; tagging from CrossWire)
  - World English Bible ............ midvash/bible-data (public domain)
  - Brief lexicons ................. STEPBible TBESG / TBESH (CC BY 4.0, Tyndale House, Cambridge)
Curated input: data/packs.json (which verses, grouped into packs)
Curated lexicon: data/lexicon.json (hand-written entries; never overwritten)

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
MAX_LINKED_WORDS = 10

# Canonical OSIS abbreviations used by CrossWire and the WEB dataset, in canonical order.
OSIS = (
    "Gen Exod Lev Num Deut Josh Judg Ruth 1Sam 2Sam 1Kgs 2Kgs 1Chr 2Chr Ezra Neh Esth Job Ps Prov Eccl Song Isa Jer "
    "Lam Ezek Dan Hos Joel Amos Obad Jonah Mic Nah Hab Zeph Hag Zech Mal "
    "Matt Mark Luke John Acts Rom 1Cor 2Cor Gal Eph Phil Col 1Thess 2Thess 1Tim 2Tim Titus Phlm Heb Jas 1Pet 2Pet "
    "1John 2John 3John Jude Rev"
).split()

# WEB puts a psalm's superscription inside verse 1 ("A Psalm by David. The LORD is my shepherd..."),
# whereas the KJV numbering leaves it out. Such verses can't be matched word-for-word, so WEB is omitted.
SUPERSCRIPTION = re.compile(r"^(A Psalm|A Song|A Contemplation|A Prayer|A Miktam|A Maskil|A Praise|A Poem|By |Of David|"
                            r"For the Chief Musician|To the Chief Musician|According to|Psalm of)", re.I)

TAG = re.compile(r"strong:([HG])0*(\d+)")
STOP = set("the of and to a in that i thou ye he she it is was be by for with unto thee thy my his her their our your "
           "which shall not me him them us we they you but or as at on from this these those have hath had are were "
           "upon into out all so then also there who whom".split())
CONTENT_POS = {"N": "noun", "V": "verb", "A": "adjective"}


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


def word_ids(w):
    ids = set()
    for s in w.get("strongs") or []:
        m = re.fullmatch(r"([HG])0*(\d+)", s)
        if m:
            ids.add(f"{m.group(1)}{int(m.group(2))}")
    for p, n in TAG.findall(w.get("lemma") or ""):
        ids.add(f"{p}{int(n)}")
    return ids


def index_tagged_kjv(kjv_book_names):
    """Count underlying-word occurrences per Strong's number and collect English renderings.
    Consecutive English words sharing one tag are one underlying word. Returns verse -> ordered ids."""
    root = SRC / "node_modules/@metaxia/scriptures-source-crosswire-kjv/data/crosswire-KJV"
    counts, renderings, verse_ids = collections.Counter(), collections.defaultdict(collections.Counter), {}
    for name, osis in zip(kjv_book_names, OSIS, strict=True):
        bdir = root / osis
        for cdir in sorted((p for p in bdir.iterdir() if p.is_dir()), key=lambda p: int(p.name)):
            for vf in cdir.glob("*.json"):
                d = json.loads(vf.read_text(encoding="utf-8"))
                ordered, prev = [], None
                for w in d.get("words", []):
                    ids = word_ids(w)
                    sig = w.get("lemma") or ""
                    eng = re.sub(r"[^a-z' -]", "", (w.get("text") or "").lower()).strip()
                    if ids and sig == prev:
                        for i in ids:
                            if eng:
                                renderings[i][eng] += 1
                        continue
                    prev = sig if ids else None
                    for i in ids:
                        counts[i] += 1
                        if eng:
                            renderings[i][eng] += 1
                    ordered.extend(sorted(ids))
                verse_ids[f"{name} {cdir.name}:{vf.stem}"] = ordered
    return counts, renderings, verse_ids


def step_lookup(strongs, g, h):
    """Find the STEPBible entry for a classic Strong's number.

    STEPBible splits some numbers into lettered senses (H7462a = a place name, H7462b = "to pasture").
    Prefer single-word lemmas over compound names/phrases, then the first lettered sense."""
    src = g if strongs[0] == "G" else h
    base = f"{strongs[0]}{int(strongs[1:]):04d}"
    cands = sorted(k for k in src if k == base or (k.startswith(base) and k[len(base):].isalpha()))
    if not cands:
        return None
    simple = [k for k in cands if not re.search(r"[\s\-]", src[k]["lemma"].strip())]
    return src[(simple or cands)[0]]


def rendering_list(counter):
    out = []
    for word, n in counter.most_common(30):
        if n < 2 or word in STOP or len(word) < 3:
            continue
        out.append(word)
        if len(out) == 4:
            break
    return out


def brief_entry(sid, step, counts, renderings):
    lemma = step["lemma"].split(",")[0].strip()
    morph = (step.get("morphology") or "").split(":", 1)
    pos = "proper name" if morph[0] == "N" else CONTENT_POS.get(morph[1][:1], "") if len(morph) > 1 else ""
    gloss = (step.get("gloss") or "").strip()
    return {
        "strongs_id": sid,
        "original": lemma,
        "transliteration": (step.get("transliteration") or "").replace(".", ""),
        "language": "Greek" if sid[0] == "G" else "Hebrew",
        "part_of_speech": pos,
        "definition": re.sub(r":\s*", ", ", gloss),
        "kjv_translations": rendering_list(renderings.get(sid, collections.Counter())),
        "usage_count": counts.get(sid, 0),
        "brief": True,
        "source": "STEPBible TBESG" if sid[0] == "G" else "STEPBible TBESH",
    }


def is_content(step):
    """Keep nouns, verbs, adjectives and names; skip particles, pronouns, prepositions, conjunctions."""
    prefix = (step.get("morphology") or "").split("-")[0]  # e.g. "G:N", "H:V", "N:N"
    lang, _, pos = prefix.partition(":")
    return bool(step.get("gloss")) and lang in ("G", "H", "N", "A") and pos[:1] in CONTENT_POS


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
    counts, renderings, verse_ids = index_tagged_kjv(kjv_books)

    step_dir = SRC / "node_modules/@metaxia/scriptures-source-stepbible-lexicon/data"
    g = json.loads((step_dir / "stepbible-tbesg.json").read_text(encoding="utf-8"))
    h = json.loads((step_dir / "stepbible-tbesh.json").read_text(encoding="utf-8"))

    curated = {e["strongs_id"]: e for e in json.loads((DATA / "lexicon.json").read_text(encoding="utf-8"))}
    packs = json.loads((DATA / "packs.json").read_text(encoding="utf-8"))

    order, pack_of = [], collections.defaultdict(list)
    for p in packs:
        for ref in p["refs"]:
            if ref not in pack_of:
                order.append(ref)
            pack_of[ref].append(p["id"])

    verses, brief, problems, notes = [], {}, [], []
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

        linked, seen = [], set()
        for k in keys:
            for sid in verse_ids.get(k, []):
                if sid in seen:
                    continue
                seen.add(sid)
                if sid in curated:
                    linked.append((0, counts[sid], sid))
                    continue
                step = step_lookup(sid, g, h)
                if step and is_content(step):
                    if sid not in brief:
                        brief[sid] = brief_entry(sid, step, counts, renderings)
                    linked.append((1, counts[sid], sid))
        linked.sort()
        entry["words"] = [sid for _, _, sid in linked[:MAX_LINKED_WORDS]]
        verses.append(entry)

    used = {sid for v in verses for sid in v["words"]}
    brief_out = [brief[s] for s in sorted(used & brief.keys(), key=lambda s: (s[0], int(s[1:])))]

    print(f"verses built: {len(verses)} of {len(order)} requested | brief lexicon entries: {len(brief_out)}")
    print(f"packs: {len(packs)} | verses with WEB text: {sum('translations' in v for v in verses)}")
    for n in notes:
        print("  note:", n)
    for p in problems:
        print("  PROBLEM:", p)
    if check_only:
        return 1 if problems else 0

    for name, payload in (("verses.json", verses), ("lexicon_brief.json", brief_out)):
        (DATA / name).write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("wrote data/verses.json and data/lexicon_brief.json")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
