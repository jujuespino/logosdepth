import re
from pathlib import Path

import pytest

from app import CSP
from app import app as flask_app

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def client():
    flask_app.config.update(TESTING=True, ACCOUNTS_ENABLED=False, BETA_ENABLED=False)
    return flask_app.test_client()


def test_about_page(client):
    r = client.get("/about")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "<h1>" in html and 'id="science"' in html
    assert "We did not find a study that tested Bible-verse memorization" in html
    assert "STEPBible" not in html and "Hebrew" not in html


def test_privacy_is_flagged_as_draft_until_reviewed(client, monkeypatch):
    assert "not yet been reviewed by a lawyer" in client.get("/privacy").get_data(as_text=True)
    monkeypatch.setenv("LEGAL_REVIEWED", "1")
    assert "not yet been reviewed" not in client.get("/privacy").get_data(as_text=True)


def test_privacy_describes_only_the_features_that_are_on(client, monkeypatch):
    html = client.get("/privacy").get_data(as_text=True)
    assert "If you sign in to sync" not in html and "usage sharing" not in html
    flask_app.config.update(ACCOUNTS_ENABLED=True, BETA_ENABLED=True)
    html = client.get("/privacy").get_data(as_text=True)
    assert "If you sign in to sync" in html and "Usage sharing is off unless you turn it on" in html
    assert "Do Not Track" in html and "180 days" in html
    flask_app.config.update(ACCOUNTS_ENABLED=False, BETA_ENABLED=False)


def test_contact_details_come_from_the_environment(client, monkeypatch):
    monkeypatch.setenv("CONTACT_EMAIL", "hello@example.org")
    monkeypatch.setenv("OPERATOR_NAME", "Example Ministry")
    html = client.get("/privacy").get_data(as_text=True)
    assert "hello@example.org" in html and "Example Ministry" in html


def test_robots_and_sitemap(client, monkeypatch):
    monkeypatch.setenv("PUBLIC_URL", "https://logos.example")
    robots = client.get("/robots.txt")
    assert robots.mimetype == "text/plain"
    body = robots.get_data(as_text=True)
    assert "Disallow: /api/" in body and "Sitemap: https://logos.example/sitemap.xml" in body
    sm = client.get("/sitemap.xml").get_data(as_text=True)
    for path in ("/", "/about", "/privacy"):
        assert f"<loc>https://logos.example{path}</loc>" in sm


def test_security_headers(client):
    r = client.get("/")
    assert r.headers["Content-Security-Policy"] == CSP
    assert "script-src 'self'" in CSP and "'unsafe-inline'" not in CSP.split("style-src")[0]
    assert "frame-ancestors 'none'" in CSP
    assert "Strict-Transport-Security" not in r.headers
    https = client.get("/", base_url="https://example.org")
    assert "max-age=31536000" in https.headers["Strict-Transport-Security"]


def test_csp_forbids_inline_script_sources():
    script_src = [d for d in CSP.split("; ") if d.startswith("script-src")][0]
    assert script_src == "script-src 'self'"


@pytest.mark.parametrize("template", ["index.html", "about.html", "privacy.html", "doc_base.html"])
def test_templates_have_no_inline_handlers_or_scripts(template):
    html = (ROOT / "templates" / template).read_text(encoding="utf-8")
    assert not re.search(r"\son[a-z]+\s*=", html), "inline event handler found (CSP would block it)"
    assert not re.search(r"<script(?![^>]*\ssrc=)", html), "inline <script> found"
    assert "javascript:" not in html


def test_js_does_not_build_inline_handlers():
    for js in (ROOT / "static" / "js").glob("*.js"):
        text = js.read_text(encoding="utf-8")
        assert not re.search(r"""\son(click|input|change)=["']""", text), f"{js.name} builds an inline handler"


def test_every_data_click_target_exists_as_a_global_function():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    js = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "static" / "js").glob("*.js"))
    names = set(re.findall(r'data-(?:click|input|change)="(\w+)"', html))
    assert names
    for name in names:
        assert re.search(rf"^(async )?function {name}\(", js, re.M), f"{name} is not a top-level function"


def test_check_deploy_script_passes_against_a_live_server():
    import sys
    import threading

    from werkzeug.serving import make_server

    sys.path.insert(0, str(ROOT / "scripts"))
    import check_deploy

    server = make_server("127.0.0.1", 0, flask_app)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        check_deploy.results.clear()
        assert check_deploy.run(f"http://127.0.0.1:{server.server_port}", allow_draft=True) is True
        check_deploy.results.clear()
        assert check_deploy.run(f"http://127.0.0.1:{server.server_port}", expect_accounts=True) is False
    finally:
        server.shutdown()
