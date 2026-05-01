import json
import os
import random
from datetime import date
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "lexicon.json")
with open(DATA_PATH, "r", encoding="utf-8") as f:
    LEXICON: list[dict] = json.load(f)

# English keyword → list of entries index
ENGLISH_INDEX: dict[str, list[dict]] = {}
for entry in LEXICON:
    for kw in entry.get("english_keywords", []):
        ENGLISH_INDEX.setdefault(kw.lower().strip(), []).append(entry)

# Category → entries
CATEGORY_INDEX: dict[str, list[dict]] = {}
for entry in LEXICON:
    cat = entry.get("category", "Other")
    CATEGORY_INDEX.setdefault(cat, []).append(entry)

CATEGORIES = sorted(CATEGORY_INDEX.keys())


def _score(entry: dict, query: str) -> int:
    """Higher score = better match."""
    kws = [k.lower() for k in entry.get("english_keywords", [])]
    translit = entry.get("transliteration", "").lower()
    defn = entry.get("definition", "").lower()
    if query in kws:
        return 3
    if translit.startswith(query):
        return 2
    if query in defn or query in translit:
        return 1
    return 0


@app.route("/")
def index():
    categories = CATEGORIES
    stats = {
        "hebrew": sum(1 for e in LEXICON if e["language"] == "Hebrew"),
        "greek": sum(1 for e in LEXICON if e["language"] == "Greek"),
        "total": len(LEXICON),
    }
    return render_template("index.html", categories=categories, stats=stats)


@app.route("/api/search")
def search():
    query = request.args.get("q", "").strip().lower()
    lang = request.args.get("lang", "all")
    cat = request.args.get("category", "")

    if not query and not cat:
        return jsonify({"results": [], "query": query})

    seen: set[str] = set()
    results: list[dict] = []

    pool = LEXICON
    if cat:
        pool = CATEGORY_INDEX.get(cat, [])

    if query:
        for entry in pool:
            sid = entry["strongs_id"]
            if sid in seen:
                continue
            score = _score(entry, query)
            if score > 0:
                seen.add(sid)
                results.append((score, entry))
        results.sort(key=lambda x: -x[0])
        results = [e for _, e in results]
    else:
        results = list(pool)

    if lang != "all":
        lang_label = "Hebrew" if lang == "hebrew" else "Greek"
        results = [e for e in results if e["language"] == lang_label]

    return jsonify({"results": results[:40], "query": query})


@app.route("/api/word-of-day")
def word_of_day():
    # Deterministic daily pick based on today's date
    day_index = date.today().toordinal() % len(LEXICON)
    return jsonify(LEXICON[day_index])


@app.route("/api/categories")
def categories():
    result = []
    for cat in CATEGORIES:
        entries = CATEGORY_INDEX[cat]
        result.append({
            "name": cat,
            "count": len(entries),
            "hebrew": sum(1 for e in entries if e["language"] == "Hebrew"),
            "greek": sum(1 for e in entries if e["language"] == "Greek"),
        })
    return jsonify(result)


@app.route("/api/featured")
def featured():
    """Return a handful of notable entries for the dashboard."""
    picks = [
        "H430", "H2617", "H7965", "G26", "G4102",
        "G5485", "H3444", "G2098", "H1285", "G3875",
    ]
    out = []
    ids = {e["strongs_id"]: e for e in LEXICON}
    for sid in picks:
        if sid in ids:
            out.append(ids[sid])
    return jsonify(out)


if __name__ == "__main__":
    app.run(debug=True)
