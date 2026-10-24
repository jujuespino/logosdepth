import gzip
import hashlib
import json
import os
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

from accounts import bp as accounts_bp
from beta import beta_enabled
from beta import bp as beta_bp
from bible import bp as bible_bp
from store import bp as store_bp

app = Flask(__name__)
if os.environ.get("TRUST_PROXY") == "1":
    # Behind one reverse proxy (Render, Fly, Heroku, nginx): use its forwarded client IP and scheme, so
    # rate limits are per visitor, cookies get the Secure flag and HSTS is sent.
    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
if os.environ.get("SENTRY_DSN"):
    try:  # optional: pip install "sentry-sdk[flask]"
        import sentry_sdk

        sentry_sdk.init(
            dsn=os.environ["SENTRY_DSN"],
            send_default_pii=False,
            traces_sample_rate=0.0,
            environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        )
    except ImportError:
        print("SENTRY_DSN is set but sentry-sdk is not installed; error reporting is off.")
app.register_blueprint(store_bp)
app.register_blueprint(accounts_bp)
app.register_blueprint(beta_bp)
app.register_blueprint(bible_bp)

DATA_DIR = Path(__file__).resolve().parent / "data"
VERSES: list[dict] = json.loads((DATA_DIR / "verses.json").read_text(encoding="utf-8"))
PACKS: list[dict] = json.loads((DATA_DIR / "packs.json").read_text(encoding="utf-8"))


@app.route("/")
def index():
    return render_template("index.html")


def _site_context() -> dict:
    return {
        "operator": os.environ.get("OPERATOR_NAME", "the site operator"),
        "contact_email": os.environ.get("CONTACT_EMAIL", ""),
        "reviewed": os.environ.get("LEGAL_REVIEWED") == "1",
        "accounts_enabled": os.environ.get("ACCOUNTS_ENABLED") == "1" or bool(app.config.get("ACCOUNTS_ENABLED")),
        "beta_enabled": beta_enabled(),
        "updated": "22 October 2026",
    }


@app.route("/about")
def about():
    return render_template("about.html", **_site_context())


@app.route("/privacy")
def privacy():
    return render_template("privacy.html", **_site_context())


@app.route("/robots.txt")
def robots():
    base = _public_base()
    lines = ["User-agent: *", "Disallow: /api/", "Allow: /", f"Sitemap: {base}/sitemap.xml", ""]
    return Response("\n".join(lines), mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap():
    base = _public_base()
    urls = "".join(f"<url><loc>{base}{path}</loc></url>" for path in ("/", "/about", "/privacy"))
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
    return Response(xml, mimetype="application/xml")


def _public_base() -> str:
    return (os.environ.get("PUBLIC_URL") or request.host_url).rstrip("/")


@app.route("/api/verses")
def verses():
    """The starter verses, easiest (shortest) first."""
    out = []
    for v in VERSES:
        out.append({
            "ref": v["ref"],
            "text": v["text"],
            "translations": v.get("translations", {}),
            "packs": v.get("packs", []),
        })
    out.sort(key=lambda v: len(v["text"].split()))
    return jsonify(out)


@app.route("/api/packs")
def packs():
    counts: dict[str, int] = {}
    for v in VERSES:
        for pid in v.get("packs", []):
            counts[pid] = counts.get(pid, 0) + 1
    return jsonify([
        {"id": p["id"], "title": p["title"], "description": p["description"], "count": counts.get(p["id"], 0)}
        for p in PACKS
    ])


STATIC_DIR = Path(__file__).resolve().parent / "static"


def _static_files() -> list[Path]:
    return sorted(p for p in STATIC_DIR.rglob("*") if p.is_file() and p.name != "sw.js")


def _asset_version() -> str:
    """Changes whenever any shipped asset changes, so installed copies update on the next visit."""
    h = hashlib.sha1()
    for p in [*_static_files(), Path(__file__).resolve().parent / "templates" / "index.html"]:
        h.update(str(p.relative_to(Path(__file__).resolve().parent)).encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


ASSET_VERSION = _asset_version()
PRECACHE_URLS = ["/", "/about", "/privacy", "/manifest.webmanifest"] + [
    "/static/" + p.relative_to(STATIC_DIR).as_posix() for p in _static_files() if p.suffix != ".txt"
]


@app.route("/manifest.webmanifest")
def web_manifest():
    manifest = {
        "id": "/",
        "name": "LogosDepth",
        "short_name": "LogosDepth",
        "description": "Memorize scripture word-for-word and keep it, with spaced reviews.",
        "start_url": "/?view=verses",
        "scope": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#ffffff",
        "categories": ["education", "lifestyle"],
        "icons": [
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {
                "src": "/static/icons/icon-maskable-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ],
    }
    return Response(json.dumps(manifest), mimetype="application/manifest+json")


@app.route("/sw.js")
def service_worker():
    """Served from the site root so the worker can control every page. Versioned by asset hash."""
    body = (STATIC_DIR / "sw.js").read_text(encoding="utf-8")
    body = body.replace("__VERSION__", ASSET_VERSION).replace("__PRECACHE__", json.dumps(PRECACHE_URLS))
    resp = Response(body, mimetype="application/javascript")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


@app.route("/api/config")
def config():
    """Tells the client which optional server features are switched on."""
    return jsonify({
        "accounts": os.environ.get("ACCOUNTS_ENABLED") == "1" or bool(app.config.get("ACCOUNTS_ENABLED")),
        "beta": beta_enabled(),
    })


@app.route("/healthz")
def healthz():
    """Liveness probe for hosting platforms and uptime monitors."""
    return jsonify({"status": "ok", "verses": len(VERSES), "packs": len(PACKS)})


CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",  # a few style="" attributes remain; scripts are the part that matters
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "manifest-src 'self'",
    "worker-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


@app.after_request
def add_headers(resp):
    resp.headers.setdefault("Content-Security-Policy", CSP)
    if request.is_secure:
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("Permissions-Policy", "camera=(), geolocation=()")
    if request.path.startswith("/static/fonts/"):
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return _gzip(resp)


_COMPRESSIBLE = {"application/json", "text/html", "application/javascript", "application/manifest+json"}


def _gzip(resp):
    """Compress JSON/HTML/JS responses when the client accepts it (the verses API is ~450 KB raw, ~80 KB gzipped)."""
    if (
        resp.direct_passthrough
        or not 200 <= resp.status_code < 300
        or "Content-Encoding" in resp.headers
        or resp.mimetype not in _COMPRESSIBLE
        or "gzip" not in request.headers.get("Accept-Encoding", "")
    ):
        return resp
    data = resp.get_data()
    if len(data) < 1024:
        return resp
    resp.set_data(gzip.compress(data, compresslevel=6))
    resp.headers["Content-Encoding"] = "gzip"
    resp.headers["Content-Length"] = str(len(resp.get_data()))
    resp.headers.add("Vary", "Accept-Encoding")
    return resp


if __name__ == "__main__":
    # Local development only. In production run under gunicorn (see Procfile);
    # debug mode must never be enabled on a public server.
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
