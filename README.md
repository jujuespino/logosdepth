# LogosDepth

Memorize scripture word-for-word and keep it, using methods with strong scientific support.

## What it does

- **Memorize:** the home screen says what to do today (review what is due, or learn the next suggested verse); the Bible browser (one link) opens with every book, and the starter packs underneath. Learn a verse in short steps (Read, Phrases, Fill In, Order, Recall, Type It; an optional "guess first" comes before reading), then review it on a spaced schedule. A verse is *mastered* after you recall it unaided on three different days.
- **The whole Bible:** all 66 books (31,102 verses) in the KJV, and in the WEB wherever its numbering lines up. Browse by book and chapter (the 201 starter verses and their packs sit below the book list), tap a verse or a short range (up to 12 verses / 160 words), and learn it like any other verse; or type a reference. Passages you start appear under **My verses** and are kept on the device for offline reviews; if progress arrives from a backup or another device, the text is fetched back by reference.
- **Starter content:** 201 hand-picked verses in 14 packs (KJV, and WEB for 190 of them).
- **Works offline and installs as an app (PWA).** Settings has backup/restore of your progress (merge-safe) and a daily calendar reminder (.ics). A one-screen intro appears on first use; after the first verse is learned the app offers the calendar reminder once and, if declined, asks again every two days until it is added or the learner chooses "Don't ask again".

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
npm test                       # unit tests: grading/scheduling (recall.js), backup/merge (progress.js), reminders (reminder.js), sync (sync.js), usage events (analytics.js)
npm run lint                   # ESLint
playwright install chromium    # once
python app.py &                # the browser test needs a running server
python tests/e2e.py            # end-to-end browser test (simulates several days, offline use, backup/restore)
python tests/e2e_sync.py       # accounts, two-device sync, opt-in usage events, feedback (starts its own server on port 5057)
python tests/a11y_audit.py     # axe-core accessibility audit of every view and key state (needs npm ci)
```

CI runs all of the above on every push (`.github/workflows/ci.yml`).

## Production

The app is a standard WSGI app. A `Procfile` is included:

```bash
gunicorn app:app --bind 0.0.0.0:$PORT --workers 2
```

See [`docs/deploy.md`](docs/deploy.md) for hosting (Render blueprint and Dockerfile included), backups, monitoring, the pre-launch checklist and every environment variable; `python3 scripts/check_deploy.py <url>` smoke-tests a deployment. Public pages: `/about` (including the science), `/privacy`. The page sends a strict Content-Security-Policy (no inline scripts; event wiring is in `static/js/actions.js`).

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

### Beta tools (opt-in usage events and feedback)

Off by default. Set `BETA_ENABLED=1` to show **Settings → Help improve LogosDepth** and **Send feedback**.

- **Usage events are opt-in and anonymous.** Nothing is sent until the learner ticks the box (Settings, or the last intro step). Events are a name from a fixed list (`app_open`, `verse_started`, `typed_attempt` with `perfect|hinted|miss`, `review_started`, `review_finished`, and a few more) with at most one short value, tied to a random ID stored only in the browser. The server stores no IP address, user agent, email, verse reference or typed text. A browser Do Not Track / Global Privacy Control signal disables the feature. Turning it off deletes the ID and the server's rows for it; everything is deleted after 180 days regardless.
- **Feedback** is stored only when the learner presses Send (message, type, optional contact email).
- **Reading the results** (needs shell access to the server; there is deliberately no web admin page):

```bash
python3 scripts/metrics.py                 # day-1/3/7/14/30 retention, funnel, outcomes, daily actives
python3 scripts/metrics.py --feedback      # the feedback inbox
python3 scripts/metrics.py --json          # machine-readable
```

Retention and funnel numbers cover only installs that opted in, so treat them as a sample, not the whole user base.

## Project layout

```
app.py                  Flask app, JSON API, public pages, security headers
bible.py                The whole Bible: books, chapters and passages from data/bible/
store.py                Shared SQLite connection, schema and rate limiting for the optional server features
beta.py                 Opt-in anonymous usage events and the feedback form (BETA_ENABLED)
accounts.py             Optional accounts: email sign-in links, sync storage, export/delete (SQLite)
progress_schema.py      Server-side validation of synced progress (mirror of progress.js validate)
data/bible/             Generated: every verse of the Bible (KJV, WEB where aligned)
data/verses.json        Generated: starter verse text (KJV + WEB) and packs
data/packs.json         Curated: which verses belong to which pack
scripts/                Content pipeline (fetch_sources.sh, build_content.py), make_icons.py, metrics.py
static/js/recall.js     Typed-recall grading and spaced-review scheduling (pure functions)
static/js/progress.js   Backup/restore, validation and merge of saved progress (pure functions)
static/js/reminder.js   Daily review reminder as a calendar file (pure functions)
static/js/actions.js    Wires data-click / data-input / data-change attributes to functions (no inline handlers)
static/js/sync.js       Cross-device sync: fetch, merge, upload, retry on conflict
static/js/analytics.js  Opt-in usage events (off unless the learner turns it on)
static/js/bible.js      Bible browser, passage picker, saved passages (My verses)
static/js/verses.js     Memorization UI (learn steps, typed recall, daily review)
static/js/settings.js   Settings, onboarding, install prompt, service-worker registration
static/sw.js            Service worker template (versioned and served at /sw.js)
static/js/app.js        View switching (Memorize, Settings)
static/css, static/fonts  Styles and self-hosted fonts
templates/index.html    Single-page shell
tests/                  pytest, Node unit tests, Playwright end-to-end test
docs/                   Evidence review, source registry, deployment guide
Dockerfile, render.yaml Deployment configuration
```

## Adding or changing verses

`data/verses.json` is **generated**; edit `data/packs.json` instead and rebuild:

```bash
scripts/fetch_sources.sh                       # downloads the public datasets into scripts/sources/ (needs npm, curl)
python3 scripts/build_content.py --check       # report problems without writing
python3 scripts/build_content.py               # regenerate the data files
pytest                                         # validate
```

The build pulls verse text from public datasets rather than from memory, so wording is exact: KJV (1769) text, and the World English Bible. Verses outside 5-55 words are rejected, and WEB is omitted where it can't be aligned word-for-word (e.g. psalms whose WEB verse 1 includes the superscription).

## The whole-Bible data

`data/bible/` is **generated** by `scripts/build_bible.py` from the same public datasets as the starter verses (run `scripts/fetch_sources.sh` first): `index.json` (books and verses per chapter), one file per book (`[kjv, web|null]` per verse). WEB is left out per verse where it would not match the KJV verse (psalm superscriptions) and for the six chapters whose numbering differs (Luke 17, Acts 8/15/24, Romans 14/16). API: `GET /api/bible` (books), `/api/bible/<slug>/<chapter>`, `/api/passage?ref=Psalm 23:1-3`. `tests/test_bible.py` checks the counts and that all 201 starter verses match the whole-Bible text word for word.

## How scheduling works

After a verse is learned, it comes due on a ladder of 1, 3, 7, 14, 30, 60 and 120 days. A clean, unaided recall moves it up a step; a miss resets it to tomorrow; a recall that used a first-letter cue steps it back and does not count toward mastery. Only the first attempt each day affects the schedule. The ladder is a design choice: the research supports spacing out practice, but not a specific interval pattern.

## Status

Prototype under active development. See `NOTICE.md` for content attributions and open licensing questions.
