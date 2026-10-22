# LogosDepth

Memorize scripture word-for-word and keep it, using methods with strong scientific support, and go deeper into the original Hebrew and Greek behind each verse.

## What it does

- **Memorize Verses:** learn a verse in five short steps (Read, Fill In, Order, Recall, Type It), then review it on a spaced schedule. A verse is *mastered* after you recall it unaided on three different days.
- **Word study:** search and browse 83 Hebrew and Greek words (Strong's numbers, transliteration, definitions, KJV renderings), linked from the verses you learn.
- **Word Game:** flashcards and a quiz for the original-language vocabulary.

The learning design follows the evidence summarized in [`docs/memory-science.md`](docs/memory-science.md); sources are catalogued in [`docs/sources.md`](docs/sources.md).

## Run it locally

Requirements: Python 3.11+ and Node 20+ (Node is only needed for the JS tests and lint).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python app.py                  # http://127.0.0.1:5000
```

Environment variables (all optional): `HOST` (default `127.0.0.1`), `PORT` (default `5000`), `FLASK_DEBUG=1` (development only; never enable on a public server).

## Tests and linting

```bash
pytest                         # API and data-validation tests
ruff check .                   # Python lint
npm ci                         # once
npm test                       # unit tests for grading and scheduling (static/js/recall.js)
npm run lint                   # ESLint
playwright install chromium    # once
python app.py &                # the browser test needs a running server
python tests/e2e.py            # end-to-end browser test (simulates several days)
```

CI runs all of the above on every push (`.github/workflows/ci.yml`).

## Production

The app is a standard WSGI app. A `Procfile` is included:

```bash
gunicorn app:app --bind 0.0.0.0:$PORT --workers 2
```

`GET /healthz` returns `{"status": "ok"}` for uptime checks. Progress is currently stored in the browser (`localStorage`); there are no accounts yet.

## Project layout

```
app.py                  Flask app and JSON API
data/lexicon.json       Hebrew/Greek word entries
data/verses.json        Memorization verses (ref, text, linked Strong's IDs)
static/js/recall.js     Typed-recall grading and spaced-review scheduling (pure functions)
static/js/verses.js     Memorization UI (learn steps, typed recall, daily review)
static/js/app.js        Dashboard, search, browse, word game
static/css, static/fonts  Styles and self-hosted fonts
templates/index.html    Single-page shell
tests/                  pytest, Node unit tests, Playwright end-to-end test
docs/                   Evidence review and source registry
```

## Adding a verse

Add an object to `data/verses.json`:

```json
{"ref": "Psalm 23:1", "text": "The LORD is my shepherd; I shall not want.", "words": ["H3068"]}
```

- `text` must be copied from a trusted source for the translation you use (see `NOTICE.md`).
- `words` lists Strong's IDs from `data/lexicon.json`; unknown IDs fail the data tests.
- Run `pytest` to validate.

## How scheduling works

After a verse is learned, it comes due on a ladder of 1, 3, 7, 14, 30, 60 and 120 days. A clean, unaided recall moves it up a step; a miss resets it to tomorrow; a recall that used a first-letter cue steps it back and does not count toward mastery. Only the first attempt each day affects the schedule. The ladder is a design choice: the research supports spacing out practice, but not a specific interval pattern.

## Status

Prototype under active development. See `NOTICE.md` for content attributions and open licensing questions.
