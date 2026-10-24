#!/usr/bin/env python3
"""Render the PWA icons (static/icons/*.png): a white open book on the app's blue.

Needs Playwright with Chromium. Usage: python3 scripts/make_icons.py
"""
import os
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "static" / "icons"

# name, pixel size, maskable (full-bleed with a safe zone) vs. "any" (rounded square)
ICONS = [
    ("icon-192.png", 192, False),
    ("icon-512.png", 512, False),
    ("icon-maskable-512.png", 512, True),
    ("apple-touch-icon.png", 180, True),
]

HTML = """<!doctype html><meta charset="utf-8"><style>
html, body {{ margin: 0; background: transparent; }}
.icon {{ width: {size}px; height: {size}px; display: grid; place-items: center; box-sizing: border-box;
  background: #2563eb; border-radius: {radius}px; }}
svg {{ width: {glyph}px; height: {glyph}px; stroke: #fff; fill: none; stroke-width: 1.6;
  stroke-linecap: round; stroke-linejoin: round; }}
</style><div class="icon"><svg viewBox="0 0 24 24"><path d="M4 19.5A2.5 2.5 0 016.5 17H20"/>
<path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/></svg></div>"""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    chrome = os.environ.get("CHROME")
    sandbox = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
    exe = chrome or (sandbox if os.path.exists(sandbox) else None)
    with sync_playwright() as p, tempfile.TemporaryDirectory() as tmp:
        browser = p.chromium.launch(executable_path=exe, args=["--no-sandbox"])
        for name, size, maskable in ICONS:
            html = HTML.format(
                size=size,
                radius=0 if maskable else round(size * 0.22),
                glyph=round(size * (0.46 if maskable else 0.56)),
            )
            f = Path(tmp) / "icon.html"
            f.write_text(html, encoding="utf-8")
            page = browser.new_page(viewport={"width": size, "height": size})
            page.goto(f"file://{f}")
            page.wait_for_timeout(100)
            page.screenshot(path=str(OUT / name), omit_background=True)
            page.close()
            print("wrote", OUT / name)
        browser.close()


if __name__ == "__main__":
    main()
