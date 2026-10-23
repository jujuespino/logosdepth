#!/usr/bin/env python3
"""Render the PWA icons (static/icons/*.png) from the logo mark: a gold Aleph on the app's dark background.

Needs Playwright with Chromium. Usage: python3 scripts/make_icons.py
"""
import os
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "static" / "fonts" / "noto-serif-hebrew-hebrew-400-normal.woff2"
OUT = ROOT / "static" / "icons"

# name, pixel size, maskable (full-bleed with a safe zone) vs. "any" (rounded square)
ICONS = [
    ("icon-192.png", 192, False),
    ("icon-512.png", 512, False),
    ("icon-maskable-512.png", 512, True),
    ("apple-touch-icon.png", 180, True),
]

HTML = """<!doctype html><meta charset="utf-8"><style>
@font-face {{ font-family: 'Aleph'; src: url('file://{font}') format('woff2'); }}
html, body {{ margin: 0; background: transparent; }}
.icon {{ width: {size}px; height: {size}px; display: grid; place-items: center; box-sizing: border-box;
  background: radial-gradient(circle at 30% 25%, #1c2330 0%, #0d1117 70%);
  border-radius: {radius}px; {border} }}
.glyph {{ font-family: 'Aleph', serif; color: #f0c866; font-size: {glyph}px; line-height: 1;
  transform: translateY({shift}px); text-shadow: 0 0 {glow}px rgba(212,168,67,0.35); }}
</style><div class="icon"><div class="glyph">א</div></div>"""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    chrome = os.environ.get("CHROME")
    sandbox = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
    exe = chrome or (sandbox if os.path.exists(sandbox) else None)
    with sync_playwright() as p, tempfile.TemporaryDirectory() as tmp:
        browser = p.chromium.launch(executable_path=exe, args=["--no-sandbox"])
        for name, size, maskable in ICONS:
            html = HTML.format(
                font=FONT,
                size=size,
                radius=0 if maskable else round(size * 0.22),
                border="" if maskable else f"border: {max(2, size // 64)}px solid rgba(212,168,67,0.35);",
                glyph=round(size * (0.50 if maskable else 0.62)),
                shift=round(size * 0.03),
                glow=round(size * 0.08),
            )
            f = Path(tmp) / "icon.html"
            f.write_text(html, encoding="utf-8")
            page = browser.new_page(viewport={"width": size, "height": size})
            page.goto(f"file://{f}")
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(150)
            page.screenshot(path=str(OUT / name), omit_background=True)
            page.close()
            print("wrote", OUT / name)
        browser.close()


if __name__ == "__main__":
    main()
