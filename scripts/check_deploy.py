#!/usr/bin/env python3
"""Smoke-test a running deployment.

  python3 scripts/check_deploy.py https://your-site.example [--expect-accounts] [--expect-beta] [--allow-draft]

Checks health, the security headers, the public pages, the PWA files and (optionally) that accounts and
beta tools are switched on. Exits non-zero if anything fails, so it can run in CI after a deploy.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


def get(base, path):
    req = urllib.request.Request(base + path, headers={"User-Agent": "logosdepth-check/1"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def run(base, expect_accounts=False, expect_beta=False, allow_draft=False):
    base = base.rstrip("/")
    https = base.startswith("https://")

    status, _, body = get(base, "/healthz")
    health = json.loads(body) if status == 200 else {}
    check("healthz is ok", status == 200 and health.get("status") == "ok", status)
    check("content is loaded", health.get("verses", 0) >= 100 and health.get("packs", 0) >= 5, health)

    status, headers, body = get(base, "/")
    h = {k.lower(): v for k, v in headers.items()}
    check("home page loads", status == 200 and b"LogosDepth" in body, status)
    check("Content-Security-Policy is set", "script-src 'self'" in h.get("content-security-policy", ""))
    check("X-Content-Type-Options is set", h.get("x-content-type-options") == "nosniff")
    check("framing is denied", h.get("x-frame-options") == "DENY")
    if https:
        check("HSTS is sent over HTTPS (is TRUST_PROXY=1 set?)", "max-age" in h.get("strict-transport-security", ""))
    else:
        print("SKIP HSTS check (not an https URL; production must use https)")

    for path, needle in (("/about", b"The science"), ("/privacy", b"Privacy"), ("/robots.txt", b"Sitemap"),
                         ("/sitemap.xml", b"<urlset"), ("/manifest.webmanifest", b"LogosDepth")):
        status, _, body = get(base, path)
        check(f"{path} is served", status == 200 and needle in body, status)

    status, headers, body = get(base, "/sw.js")
    check("service worker is served from the root", status == 200 and b"CACHE" in body.upper(), status)
    cache = {k.lower(): v for k, v in headers.items()}.get("cache-control", "")
    check("service worker is not cached", "no-cache" in cache)

    status, _, body = get(base, "/api/config")
    cfg = json.loads(body) if status == 200 else {}
    if expect_accounts:
        check("accounts are enabled", cfg.get("accounts") is True, cfg)
    if expect_beta:
        check("beta tools are enabled", cfg.get("beta") is True, cfg)
    if not expect_accounts and not expect_beta:
        print(f"INFO accounts={cfg.get('accounts')} beta={cfg.get('beta')}")

    status, _, body = get(base, "/privacy")
    if allow_draft:
        print("SKIP privacy-review gate (--allow-draft)")
    else:
        check("privacy page is no longer marked as a draft (LEGAL_REVIEWED=1)", b"not yet been reviewed" not in body)
    return all(results)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--expect-accounts", action="store_true")
    ap.add_argument("--expect-beta", action="store_true")
    ap.add_argument("--allow-draft", action="store_true", help="do not fail while /privacy is still a draft")
    a = ap.parse_args()
    ok = run(a.url, a.expect_accounts, a.expect_beta, a.allow_draft)
    print("\nAll checks passed." if ok else "\nSome checks failed.")
    sys.exit(0 if ok else 1)
