---
name: logosdepth
description: How to work on the LogosDepth scripture-memorization app (Flask backend, vanilla JS/CSS PWA). Use this whenever you change code, add or remove a feature, run or write tests, touch Bible text or translations, or commit and push in this repo, and whenever someone asks whether an idea belongs in the app. It holds the product rules (free, no ads, calm, memorize-only), the technical constraints that are easy to break (CSP, sync schema, service worker), the exact test commands with their gotchas, and the git rules for the shared PR.
---

# Working on LogosDepth

LogosDepth helps people memorize scripture word for word and keep it: learn a verse in short steps, type it from memory, get spaced reviews. It is a Flask app serving a single-page vanilla JS/CSS PWA. Read `README.md` for the feature list and file map; this skill covers the rules that are not obvious from the code.

## Product rules (and why)

- **Memorize-only.** The Hebrew/Greek word study, Explore, and the Word Game were removed on purpose. Do not bring original-language features back unless the owner asks.
- **Free, no ads, no tracking by default.** Usage analytics are opt-in and anonymous; the server accepts only a fixed list of event names (`beta.py`), so a new `track(...)` call needs the server list updated or it is dropped. Sharing a link sends nothing to the server.
- **Calm and simple.** White, quiet interface; no confetti-heavy rewards, leaderboards, or competition. When adding UI, prefer removing something over adding a screen. The result screen is already near its limit of buttons.
- **Evidence-backed learning only.** Typed recall and spacing are the core levers. Do not add features that reward recognition over recall (for example, practice drills never change the schedule or clear a trouble-spot word; only a correct typed recall does). The movement prompts were cut for lack of evidence; do not reintroduce them.
- **Only public-domain Bible text.** KJV and WEB are bundled. NIV, ESV, CSB, NLT and NASB cannot be bundled (they need publisher licences); the Berean Standard Bible is public domain and is the candidate next translation. Never paste copyrighted verse text into data files, tests or docs.

## Technical constraints that are easy to break

- **No inline scripts or handlers.** The CSP is `script-src 'self'`. Wire behaviour with `data-click` / `data-input` / `data-change` attributes handled by `static/js/actions.js`; the target must be a global function.
- **JS files are plain `<script>` tags sharing one global scope.** A new file needs a `<script>` tag in `templates/index.html` (order matters: pure modules before the UI that uses them) and a `/* global ... */` comment in any file that uses its globals, or `npm run lint` fails. Pure logic (`recall.js`, `progress.js`, `reminder.js`, `share.js`) is exported for Node and unit-tested; keep new logic pure when you can.
- **Progress data is validated twice.** Any new field on a saved card must be handled in `Progress.cleanCard` (`static/js/progress.js`), in `progress_schema.py`, and in `Recall.mergeCards` if it has to merge across devices. Unknown fields are dropped silently, which looks like "the feature works until you sync".
- **Storage is optional.** Every `localStorage` read/write must survive being blocked or full (`vLoad` / `vSave` do this).
- **Service worker.** Only `/` gets the cached app shell; `/about` and `/privacy` are separate documents served network-first. Anything under `static/` is precached and versioned by a hash of the files, so changing a static file updates installed copies automatically.
- **Generated data.** `data/verses.json` is built from `data/packs.json`; `data/bible/` is built by `scripts/build_bible.py`. Edit the source and rebuild (`scripts/fetch_sources.sh`, `scripts/build_content.py`, `scripts/build_bible.py`); do not hand-edit generated files. `pytest` checks every starter verse matches the whole-Bible text word for word.
- **Docs follow the code.** When behaviour changes, update `README.md` (and `NOTICE.md` or `templates/about.html` if sources or claims change) in the same commit.

## Running and testing

Use `/usr/bin/python3` (the default `python3` may be a different version). Everything CI runs, run before you push:

```bash
/usr/bin/python3 -m pytest -q          # Python unit/API tests
/usr/bin/python3 -m ruff check .       # Python lint
npm run lint && npm test               # ESLint + Node unit tests
```

Browser tests need the app running on port 5000:

```bash
(nohup /usr/bin/python3 app.py >/tmp/srv.log 2>&1 &); sleep 2; curl -s localhost:5000/healthz
/usr/bin/python3 tests/e2e.py          # end-to-end, ~200+ checks, takes a few minutes
/usr/bin/python3 tests/a11y_audit.py   # axe-core accessibility audit, must report 0 issues
/usr/bin/python3 tests/e2e_sync.py     # accounts and sync
```

Gotchas that have cost time before:

- **Restarting the server:** find the PID and `kill <pid>`. Do not use `pkill -f` or `pgrep -f` with a pattern that also appears in your own command line; it kills the shell.
- **Stale server:** an old server on port 5000 serves old code, and a refused connection in a test usually means you killed it. Check `/healthz` first.
- **The CSP forbids string `eval`,** so Playwright's `wait_for_function("...")` fails. Use the `wait_for(pg, expr)` helper in `tests/e2e.py`.
- **Tests use a fixed clock** (`page.clock.set_fixed_time`) so scheduling over days is testable; use `at_day(pg, n)` to jump days.
- **CSS `text-transform: uppercase`** makes `inner_text` return capitals; use `text_content` when asserting on eyebrow labels.
- If Chromium is not found, the audit and e2e scripts fall back to `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`; do not run `playwright install`.
- Ask for a screenshot check of any UI change at phone width (about 430px) as well as desktop.

## Git and collaboration rules

- Work on the branch the session names and push to it; the existing pull request updates automatically. Do **not** open a new pull request unless the owner asks.
- Never force-push or rewrite history without the owner's approval.
- End every commit message with the attribution lines the session instructions provide. Do not put model names, session links or other tooling identifiers anywhere else in the repo (code, comments, docs).
- Keep planning material out of the repo: roadmaps, legal and licensing research, interview kits, launch checklists. Put those in the scratchpad or a Drive doc.
- Ask before anything outward-facing or hard to undo: publishing, deleting data, changing licences, sending content to an external service.

## Before you call a change done

1. All of the commands above pass; the new behaviour has a unit test and, if it is UI, an end-to-end scenario.
2. You looked at a screenshot of the new screen on a phone-sized viewport.
3. `README.md` describes the feature; no stale mentions of removed features.
4. The commit message explains what changed and why, with the attribution lines.
