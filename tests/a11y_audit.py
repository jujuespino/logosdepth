"""Accessibility audit with axe-core across every view and key state.

  python3 app.py &           # needs a running server
  npm ci                     # provides node_modules/axe-core
  python3 tests/a11y_audit.py

Exits non-zero if any violation is found. Run with --report to print details without failing.
"""
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
AXE = (ROOT / "node_modules" / "axe-core" / "axe.min.js").read_text(encoding="utf-8")
BASE = os.environ.get("BASE", "http://localhost:5000/")
_SANDBOX = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
CHROME = os.environ.get("CHROME") or (_SANDBOX if os.path.exists(_SANDBOX) else None)
REPORT_ONLY = "--report" in sys.argv

RUN = """async () => {
  const r = await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] } });
  return r.violations.map(v => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.map(n => n.target.join(' ')).slice(0, 4), count: v.nodes.length }));
}"""

results = {}


def audit(pg, name):
    pg.evaluate(AXE)
    v = pg.evaluate(RUN)
    results[name] = v
    mark = "ok " if not v else "!! "
    print(f"{mark}{name}: {len(v)} issue type(s)")
    for x in v:
        print(f"     [{x['impact']}] {x['id']} x{x['count']}: {x['help']}  e.g. {x['nodes'][:2]}")


def type_step(pg):
    pg.evaluate('goToStep("type")')


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
    ctx = b.new_context(viewport={"width": 1280, "height": 900})
    ctx.add_init_script("try { localStorage.setItem('ld_onboarded', 'true'); } catch (e) {}")
    pg = ctx.new_page()
    pg.goto(BASE)
    pg.wait_for_selector(".verse-card, .word-card", state="attached")
    pg.wait_for_timeout(500)

    audit(pg, "memorize home")
    pg.click("#vOtherBtn")
    audit(pg, "memorize home with list open")
    pg.click('[data-view="dashboard"]')
    audit(pg, "explore")
    pg.fill("#searchInput", "love")
    pg.wait_for_selector("#resultsGrid .word-card")
    audit(pg, "search results")
    pg.click('[data-view="dashboard"]')
    pg.get_by_role("button", name="browse by category").click()
    pg.wait_for_selector(".browse-card")
    audit(pg, "browse")
    pg.click('[data-view="dashboard"]')
    pg.locator("#featuredGrid .word-card").first.click()
    pg.wait_for_selector("#wordModal:not(.hidden)")
    audit(pg, "word modal")
    pg.keyboard.press("Escape")

    pg.click('[data-view="verses"]')
    pg.wait_for_selector(".verse-card", state="attached")
    pg.evaluate('startVerse("Psalm 23:1")')
    audit(pg, "learn: read")
    pg.get_by_role("button", name="Guess it first (optional)").click()
    audit(pg, "learn: guess first")
    pg.get_by_role("button", name="Skip").click()
    pg.get_by_role("button", name="I've read it →").click()
    audit(pg, "learn: phrases (study)")
    pg.get_by_role("button", name="Cover it and type it →").click()
    audit(pg, "learn: phrases (type)")
    pg.evaluate('goToStep("fill1")')
    audit(pg, "learn: fill in")
    pg.evaluate('goToStep("order")')
    audit(pg, "learn: order")
    type_step(pg)
    audit(pg, "learn: type it")
    pg.fill("#vsInput", "the lord is my")
    pg.get_by_role("button", name="Check", exact=True).click()
    audit(pg, "learn: typed feedback")
    pg.get_by_role("button", name="Finish for today").click()
    audit(pg, "learn: result")

    pg.click('[data-view="settings"]')
    audit(pg, "settings")
    pg.get_by_role("button", name="Show the intro").click()
    audit(pg, "onboarding")
    pg.keyboard.press("Escape")

    pg.click('[data-view="game"]')
    audit(pg, "word game start")
    pg.click("#gameStart .gs-start-btn")
    pg.wait_for_selector("#flashcard")
    audit(pg, "flashcard")
    pg.evaluate("restartGame()")
    pg.click("#tabQuiz")
    pg.click("#gameStart .gs-start-btn")
    pg.wait_for_selector(".quiz-option")
    audit(pg, "quiz")

    for path, label in (("about", "about page"), ("privacy", "privacy page")):
        pg.goto(BASE + path)
        audit(pg, label)
    pg.set_viewport_size({"width": 390, "height": 844})
    pg.goto(BASE + "about")
    audit(pg, "about page (mobile)")

    pg2 = b.new_context(viewport={"width": 390, "height": 844}).new_page()
    pg2.goto(BASE)
    pg2.wait_for_selector(".word-card", state="attached")
    pg2.wait_for_timeout(300)
    audit(pg2, "mobile dashboard")
    b.close()

total = sum(len(v) for v in results.values())
print(f"\n{total} issue type(s) across {len(results)} views/states")
if REPORT_ONLY:
    (ROOT / "a11y-report.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
sys.exit(0 if (REPORT_ONLY or total == 0) else 1)
