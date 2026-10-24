# Deploying LogosDepth

The app is one Flask process plus (optionally) a SQLite file. Any host that runs Python or Docker will do. Steps below use Render because `render.yaml` is included; the same settings work on Fly.io, Railway, a VPS, or anything that runs the `Dockerfile`.

> `Dockerfile` and `render.yaml` have not been exercised on a real host yet (the build environment had no Docker daemon). The same `gunicorn` command and environment were run locally and passed `scripts/check_deploy.py`. Expect to fix small things on the first deploy.

## 1. The simplest launch (no accounts, no beta tools)

1. Create the service from this repository. Build: `pip install -r requirements.txt`. Start: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --access-logfile -`.
2. Set `TRUST_PROXY=1` (the host puts a proxy in front; this makes HTTPS detection, HSTS and per-visitor rate limits work) and `PUBLIC_URL=https://your-domain`.
3. Add your domain in the host's dashboard; HTTPS certificates are automatic on Render/Fly/Railway.
4. Run the smoke test:

```bash
python3 scripts/check_deploy.py https://your-domain --allow-draft
```

Everything the learner does is saved in their own browser. No database is needed in this mode.

## 2. Turn on accounts and sync

Needs a persistent disk (SQLite) and an email-sending service.

1. Attach a disk (Render: `render.yaml` already declares 1 GB at `/data`) and set `DATABASE_PATH=/data/logosdepth.db`.
2. Choose an SMTP provider (Postmark, Brevo, Amazon SES, Mailgun, or your domain's own SMTP). Set `MAIL_BACKEND=smtp`, `MAIL_FROM`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`. Set up SPF/DKIM for the sending domain or the emails will land in spam.
3. Set `ACCOUNTS_ENABLED=1`. Never set `AUTH_RETURN_LINK` and never leave `MAIL_BACKEND=console` on a public server (it writes sign-in links into the logs).
4. Test with your own address: request a link, sign in on two browsers, learn a verse on one, press **Sync now** on the other.
5. `python3 scripts/check_deploy.py https://your-domain --expect-accounts --allow-draft`

## 3. Turn on the beta tools

Set `BETA_ENABLED=1` (uses the same SQLite file). Read results on the server with `python3 scripts/metrics.py` and `python3 scripts/metrics.py --feedback`. On Render, open a Shell on the service; the database is at `$DATABASE_PATH`.

## 4. Backups and recovery

SQLite holds accounts, synced progress, usage events and feedback. Back it up daily with a consistent copy, not by copying the live file:

```bash
sqlite3 "$DATABASE_PATH" ".backup '/data/backup-$(date +%F).db'"
```

Copy the backup somewhere off the server (object storage, another host). Practice a restore once before you need it: stop the app, replace the file, start the app, sign in.

## 5. Monitoring

- **Uptime:** point any uptime monitor (UptimeRobot, Better Stack, the host's own) at `/healthz`.
- **Errors:** `pip install "sentry-sdk[flask]"` and set `SENTRY_DSN`. Personal data is not attached (`send_default_pii=False`). This covers server errors only; browser errors are not reported.
- **Logs:** the access log is on stdout (`--access-logfile -`).

## 6. Before you announce it

- [ ] A lawyer has reviewed `/privacy` (and you have terms of use if you want them). Then set `LEGAL_REVIEWED=1`, `OPERATOR_NAME`, `CONTACT_EMAIL`.
- [ ] You have confirmed the King James Version position for any country where you will promote the app (see `NOTICE.md`).
- [ ] `python3 scripts/check_deploy.py https://your-domain --expect-accounts --expect-beta` passes (without `--allow-draft`).
- [ ] You have installed it to your own phone's home screen (iPhone: Share → Add to Home Screen) and used it offline.
- [ ] You have restored a backup once.

## Environment reference

| Variable | Default | Meaning |
|---|---|---|
| `PORT`, `HOST` | `5000`, `127.0.0.1` | Used only by `python app.py`; gunicorn takes `--bind` |
| `FLASK_DEBUG` | off | Development only. Never on a public server |
| `TRUST_PROXY` | off | `1` when behind one reverse proxy |
| `PUBLIC_URL` | request host | Base URL for emailed links, `sitemap.xml`, `robots.txt` |
| `ACCOUNTS_ENABLED` | off | See README: Optional accounts and sync |
| `BETA_ENABLED` | off | See README: Beta tools |
| `DATABASE_PATH` | `instance/logosdepth.db` | SQLite file |
| `MAIL_BACKEND`, `MAIL_FROM`, `SMTP_*` | `console` | Email sending |
| `COOKIE_SECURE` | auto | Force the Secure cookie flag |
| `OPERATOR_NAME`, `CONTACT_EMAIL` | placeholders | Shown on `/privacy` and `/about` |
| `LEGAL_REVIEWED` | off | `1` removes the “draft” banner from `/privacy` |
| `SENTRY_DSN`, `SENTRY_ENVIRONMENT` | off | Optional server error reporting |
