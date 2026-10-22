"""End-to-end test of accounts and cross-device sync. Starts its own accounts-enabled server.

  python3 tests/e2e_sync.py        # set CHROME=/path/to/chrome to use a specific browser
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
_SANDBOX_CHROME = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
CHROME = os.environ.get('CHROME') or (_SANDBOX_CHROME if os.path.exists(_SANDBOX_CHROME) else None)
PORT = os.environ.get('SYNC_PORT', '5057')
BASE = f'http://127.0.0.1:{PORT}/'
EMAIL = 'reader@example.com'
AXE = ROOT / 'node_modules' / 'axe-core' / 'axe.min.js'
AXE_RUN = '''async () => (await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa', 'best-practice']}}))
  .violations.map(v => v.id + ' ' + v.nodes.map(n => n.target.join(' ')).join(', '))'''

fails = []
passes = 0


def check(name, cond, extra=''):
    global passes
    if cond:
        passes += 1
        print('PASS', name)
    else:
        fails.append(name)
        print('FAIL', name, f'[{extra}]' if extra else '')


def start_server(tmp):
    env = dict(os.environ, ACCOUNTS_ENABLED='1', AUTH_RETURN_LINK='1', MAIL_BACKEND='console',
               DATABASE_PATH=os.path.join(tmp, 'sync.db'), PORT=PORT, HOST='127.0.0.1')
    proc = subprocess.Popen([sys.executable, str(ROOT / 'app.py')], env=env, cwd=ROOT,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            urllib.request.urlopen(BASE + 'healthz', timeout=1)
            return proc
        except OSError:
            time.sleep(0.2)
    proc.kill()
    raise SystemExit('server did not start')


def device(browser):
    ctx = browser.new_context(viewport={'width': 1280, 'height': 900}, accept_downloads=True)
    ctx.add_init_script("try { localStorage.setItem('ld_onboarded', 'true'); } catch (e) {}")
    pg = ctx.new_page()
    pg.errors = []
    pg.on('pageerror', lambda e: pg.errors.append(str(e)[:160]))
    pg.on('console', lambda m: pg.errors.append('console:' + m.text[:160])
          if m.type == 'error' and 'ERR_' not in m.text and '401' not in m.text and '404' not in m.text else None)
    pg.goto(BASE + '?view=settings')
    pg.wait_for_selector('.verse-card', state='attached')
    return pg


def srs(pg):
    raw = pg.evaluate('localStorage.getItem("ld_verse_srs")')
    return json.loads(raw) if raw else {}


def learn(pg, ref):
    pg.click('[data-view="verses"]')
    pg.evaluate(f'startVerse({ref!r}); goToStep("type")')
    pg.fill('#vsInput', pg.evaluate(f'verseList.find(v => v.ref === {ref!r}).text'))
    pg.get_by_role('button', name='Check', exact=True).click()
    pg.click('[data-view="settings"]')


def request_link(pg):
    pg.fill('#syncEmail', EMAIL)
    with pg.expect_response('**/api/auth/request') as r:
        pg.get_by_role('button', name='Email me a sign-in link').click()
    return r.value.json()['link']


def axe_issues(pg):
    pg.evaluate(AXE.read_text(encoding='utf-8'))
    return pg.evaluate(AXE_RUN)


def msg(pg):
    return pg.inner_text('#syncMsg')


with tempfile.TemporaryDirectory() as tmp:
    server = start_server(tmp)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path=CHROME, args=['--no-sandbox'])

            # ── Device A: starts as a guest with progress, then signs in ──
            a = device(b)
            check('sync card is shown when the server has accounts', a.is_visible('#syncCard'))
            check('signed-out form is shown first', a.is_visible('#syncEmail') and not a.is_visible('#syncSignedIn'))
            check('a11y: signed-out sync card has no axe violations', not axe_issues(a), axe_issues(a))
            learn(a, 'Psalm 23:1')
            check('A: guest has local progress', 'Psalm 23:1' in srs(a))

            link = request_link(a)
            check('A: told to check email', 'sign-in link is on its way' in msg(a), msg(a))
            a.goto(link)
            a.wait_for_selector('#syncSignedIn:not(.hidden)')
            check('A: signed in as the right address', EMAIL in a.inner_text('#syncWho'))
            check('a11y: signed-in sync card has no axe violations', not axe_issues(a), axe_issues(a))
            check('A: token removed from the address bar', 'login=' not in a.url, a.url)
            a.wait_for_function('document.getElementById("syncMsg").textContent.startsWith("Synced")')
            check('A: guest progress uploaded on first sign-in', 'Synced: 1 verse' in msg(a), msg(a))

            # ── Device B: fresh browser, signs in, receives A's progress ──
            bdev = device(b)
            check('B: starts empty', srs(bdev) == {})
            link_b = request_link(bdev)
            bdev.goto(link_b)
            bdev.wait_for_function('document.getElementById("syncMsg").textContent.startsWith("Synced")')
            check('B: received the verse learned on A', 'Psalm 23:1' in srs(bdev), list(srs(bdev)))
            check('B: XP carried over', bdev.evaluate('getXp()') == a.evaluate('getXp()') and a.evaluate('getXp()') > 0)

            # ── Both learn different verses, then sync; nothing is lost ──
            learn(bdev, 'John 3:16')
            learn(a, 'Romans 8:1')
            bdev.click('#syncNowBtn')
            bdev.wait_for_function('document.getElementById("syncMsg").textContent.startsWith("Synced")')
            a.click('#syncNowBtn')
            a.wait_for_function('document.getElementById("syncMsg").textContent.includes("3 verse")')
            bdev.click('#syncNowBtn')
            bdev.wait_for_function('document.getElementById("syncMsg").textContent.includes("3 verse")')
            want = {'Psalm 23:1', 'John 3:16', 'Romans 8:1'}
            check('A has all three verses', want <= set(srs(a)), list(srs(a)))
            check('B has all three verses', want <= set(srs(bdev)), list(srs(bdev)))

            # ── Links are single use ──
            c = device(b)
            c.goto(link)
            c.wait_for_function('document.getElementById("syncMsg").textContent.length > 0')
            check('reusing a sign-in link fails with a clear message', 'expired or was already used' in msg(c), msg(c))
            check('...and does not sign in', c.is_visible('#syncEmail'))
            c.errors.clear()  # the browser logs the expected 400 from the rejected link

            # ── Sign out keeps local progress; session cookie is gone ──
            a.get_by_role('button', name='Sign out', exact=True).click()
            a.wait_for_selector('#syncEmail', state='visible')
            check('sign out keeps local progress', want <= set(srs(a)))
            check('sign out shows the form again', a.is_visible('#syncEmail'))
            a.reload()
            a.wait_for_selector('.verse-card', state='attached')
            a.click('[data-view="settings"]')
            check('still signed out after reload', a.is_visible('#syncEmail'))

            # ── Export and delete account (from B) ──
            with bdev.expect_download() as dl:
                bdev.get_by_role('button', name='Download my account data').click()
            exported = json.loads(Path(dl.value.path()).read_text())
            check('account export has email and progress',
                  exported['email'] == EMAIL and want <= set(exported['progress']['data']['srs']))

            bdev.get_by_role('button', name='Delete my account…').click()
            bdev.get_by_role('button', name='Yes, delete my account').click()
            bdev.wait_for_selector('#syncEmail', state='visible')
            check('delete: confirmed in the UI', 'deleted' in msg(bdev), msg(bdev))
            check('delete: device progress is kept', want <= set(srs(bdev)))

            # a fresh sign-in with the same address starts from nothing on the server
            link2 = request_link(bdev)
            bdev.goto(link2)
            bdev.wait_for_function('document.getElementById("syncMsg").textContent.startsWith("Synced")')
            fresh = json.loads(urllib.request.urlopen(BASE + 'healthz').read())
            check('server stayed healthy', fresh['status'] == 'ok')

            for name, pg in [('A', a), ('B', bdev), ('C', c)]:
                check(f'{name}: no JS errors', not pg.errors, pg.errors[:2])
            b.close()
    finally:
        server.terminate()

print(f'\n{passes} passed, {len(fails)} failed')
print('FAILED:', fails if fails else 'none')
raise SystemExit(1 if fails else 0)
