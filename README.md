# LogosDepth

Memorize scripture word-for-word and keep it, using methods with strong scientific support, and go deeper into the original Hebrew and Greek behind each verse.

## What it does

- **Memorize Verses:** learn a verse in short steps (Read, Phrases, Fill In, Order, Recall, Type It; an optional "guess first" comes before reading), then review it on a spaced schedule. A verse is *mastered* after you recall it unaided on three different days.
- **Content:** 137 verses in 10 packs (KJV, and WEB for 130 of them), each linked to the exact Hebrew/Greek words in it.
- **Word study:** search and browse 83 hand-written Hebrew and Greek word entries (Strong's numbers, transliteration, definitions, KJV renderings). Words found in verses but not in that set get brief entries.
- **Word Game:** flashcards and a quiz for the original-language vocabulary.
- **Works offline and installs as an app (PWA).** Settings has backup/restore of your progress (merge-safe), a daily calendar reminder (.ics), and an intro walkthrough.

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
npm test                       # unit tests: grading/scheduling (recall.js), backup/merge (progress.js), reminders (reminder.js), sync (sync.js)
npm run lint                   # ESLint
playwright install chromium    # once
python app.py &                # the browser test needs a running server
python tests/e2e.py            # end-to-end browser test (simulates several days, offline use, backup/restore)
python tests/e2e_sync.py       # accounts and two-device sync (starts its own server on port 5057)
python tests/a11y_audit.py     # axe-core accessibility audit of every view and key state (needs npm ci)
```

CI runs all of the above on every push (`.github/workflows/ci.yml`).

## Production

The app is a standard WSGI app. A `Procfile` is included:

```bash
gunicorn app:app --bind 0.0.0.0:$PORT --workers 2
```

`GET /healthz` returns `{"status": "ok"}` for uptime checks. JSON and HTML responses are gzipped when the client accepts it. Progress is stored in the browser (`localStorage`); Settings offers a downloadable backup, and optional accounts (below) sync it across devices. The service worker at `/sw.js` is versioned by a hash of the shipped assets, so every deploy refreshes installed copies.

### Optional accounts and sync

Off by default; the app is local-first and fully usable without them. Set `ACCOUNTS_ENABLED=1` to show **Settings → Sync across devices**. Sign-in is an emailed one-time link (no passwords). The server stores only the email address and one progress document per user (SQLite). The client merges before uploading (same rules as backup import), and a version number rejects stale writes so two devices saving at once never overwrite each other.

| Variable | Purpose |
|---|---|
| `ACCOUNTS_ENABLED` | `1` to turn the feature on |
| `DATABASE_PATH` | SQLite file (default `instance/logosdepth.db`; put it on a persistent disk) |
| `PUBLIC_URL` | Base URL used in emailed links, e.g. `https://example.org` |
| `MAIL_BACKEND` | `smtp` in production (`console` only logs the link, for development) |
| `MAIL_FROM`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_STARTTLS` | SMTP settings |
| `COOKIE_SECURE` | `1` to force the Secure cookie flag when TLS terminates at a proxy |

Security notes: sign-in tokens and session tokens are random, stored hashed, single-use / revocable, and expire (15 minutes / 90 days); session cookies are `HttpOnly` and `SameSite=Lax`; every write requires an `X-LD-CSRF` header; sign-in requests are rate limited per address and per IP; the response never reveals whether an address already has an account. Users can download their data, sign out everywhere, and delete their account (Settings). `AUTH_RETURN_LINK=1` exists only for automated tests and must never be set in production.

## Project layout

```
app.py                  Flask app and JSON API
accounts.py             Optional accounts: email sign-in links, sync storage, export/delete (SQLite)
progress_schema.py      Server-side validation of synced progress (mirror of progress.js validate)
data/lexicon.json       Hand-written Hebrew/Greek word entries (searchable, browsable)
data/lexicon_brief.json Generated brief entries for words linked from verses
data/verses.json        Generated: verse text (KJV + WEB), packs, linked Strong's IDs
data/packs.json         Curated: which verses belong to which pack
scripts/                Content pipeline (fetch_sources.sh, build_content.py) and make_icons.py
static/js/recall.js     Typed-recall grading and spaced-review scheduling (pure functions)
static/js/progress.js   Backup/restore, validation and merge of saved progress (pure functions)
static/js/reminder.js   Daily review reminder as a calendar file (pure functions)
static/js/sync.js       Cross-device sync: fetch, merge, upload, retry on conflict
static/js/verses.js     Memorization UI (learn steps, typed recall, daily review)
static/js/settings.js   Settings, onboarding, install prompt, service-worker registration
static/sw.js            Service worker template (versioned and served at /sw.js)
static/js/app.js        Dashboard, search, browse, word game
static/css, static/fonts  Styles and self-hosted fonts
templates/index.html    Single-page shell
tests/                  pytest, Node unit tests, Playwright end-to-end test
docs/                   Evidence review and source registry
```

## Adding or changing verses

`data/verses.json` and `data/lexicon_brief.json` are **generated**; edit `data/packs.json` instead and rebuild:

```bash
scripts/fetch_sources.sh                       # downloads the public datasets into scripts/sources/ (needs npm, curl)
python3 scripts/build_content.py --check       # report problems without writing
python3 scripts/build_content.py               # regenerate the data files
pytest                                         # validate
```

The build pulls verse text from public datasets rather than from memory, so wording is exact: KJV (1769) text, KJV with Strong's tags (to find the exact original words in each verse), the World English Bible, and the STEPBible brief lexicons. Verses outside 5-55 words are rejected, and WEB is omitted where it can't be aligned word-for-word (e.g. psalms whose WEB verse 1 includes the superscription).

## How scheduling works

After a verse is learned, it comes due on a ladder of 1, 3, 7, 14, 30, 60 and 120 days. A clean, unaided recall moves it up a step; a miss resets it to tomorrow; a recall that used a first-letter cue steps it back and does not count toward mastery. Only the first attempt each day affects the schedule. The ladder is a design choice: the research supports spacing out practice, but not a specific interval pattern.

## Status

Prototype under active development. See `NOTICE.md` for content attributions and open licensing questions.
