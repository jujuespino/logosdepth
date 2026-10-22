"""End-to-end browser test. Needs: flask server on BASE, playwright, chromium.

  python3 app.py &            # in another shell
  python3 tests/e2e.py        # set CHROME=/path/to/chrome to use a specific browser
Optional: SHOTS=/some/dir to save screenshots.
"""
import json
import os
from datetime import datetime, timedelta

from playwright.sync_api import sync_playwright

_SANDBOX_CHROME = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
# Use $CHROME if set, else this sandbox's browser if present, else Playwright's bundled Chromium.
CHROME = os.environ.get('CHROME') or (_SANDBOX_CHROME if os.path.exists(_SANDBOX_CHROME) else None)
BASE = os.environ.get('BASE', 'http://localhost:5000/')
SHOTS = os.environ.get('SHOTS')
D0 = datetime(2026, 11, 2, 10, 0)

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


def day(n):
    return (D0 + timedelta(days=n)).strftime('%Y-%m-%d')


def new_page(browser, n=0, width=1280, height=900):
    ctx = browser.new_context(viewport={'width': width, 'height': height})
    pg = ctx.new_page()
    pg.errors = []
    pg.on('pageerror', lambda e: pg.errors.append(str(e)[:160]))
    pg.on('console', lambda m: pg.errors.append('console:' + m.text[:160])
          if m.type == 'error' and 'ERR_' not in m.text else None)
    pg.clock.set_fixed_time(D0 + timedelta(days=n))
    pg.goto(BASE)
    pg.wait_for_selector('.verse-card', state='attached')
    return pg


def at_day(pg, n):
    """Jump the browser clock to day n and reload (storage persists)."""
    pg.clock.set_fixed_time(D0 + timedelta(days=n))
    pg.reload()
    pg.wait_for_selector('.verse-card', state='attached')


def open_verses(pg):
    pg.click('[data-view="verses"]')


def card(pg, ref):
    raw = pg.evaluate('localStorage.getItem("ld_verse_srs")')
    return (json.loads(raw) if raw else {}).get(ref)


def xp(pg):
    return pg.evaluate('getXp()')


def verse_text(pg, ref):
    return pg.evaluate(f'verseList.find(v => v.ref === {ref!r}).text')


def click_btn(pg, name):
    pg.get_by_role('button', name=name, exact=True).click()


def guided_to_typed(pg, ref):
    """Play Read -> Fill In -> Order -> Recall through the UI, arriving at Type It."""
    pg.evaluate(f'startVerse({ref!r})')
    click_btn(pg, "I've read it →")
    for _ in range(3):
        step = pg.evaluate('VERSE_STEPS[vs.step].id')
        guard = 0
        while pg.get_by_role('button', name='Next step →').count() == 0 and guard < 80:
            guard += 1
            idx = pg.evaluate('''() => {
                if (VERSE_STEPS[vs.step].id === 'order')
                    return vs.order.bank.findIndex(c => c.key === normUnit(vs.order.units[vs.order.pos]));
                return vs.fill.bank.findIndex(c => c.key === vs.tokens[vs.fill.active].key);
            }''')
            pg.locator('#vsBank .vchip').nth(idx).click()
        check(f'{ref}: guided step {step} completes', pg.get_by_role('button', name='Next step →').count() == 1, guard)
        click_btn(pg, 'Next step →')
    check(f'{ref}: arrives at Type It', pg.evaluate('VERSE_STEPS[vs.step].id') == 'type')


def submit(pg, text):
    pg.fill('#vsInput', text)
    click_btn(pg, 'Check')


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, args=['--no-sandbox'])

    # ───────────── Navigation + word game regression ─────────────
    pg = new_page(b)
    for view in ['game', 'verses', 'browse', 'search', 'dashboard']:
        pg.click(f'[data-view="{view}"]')
        visible = [v for v in ['game', 'verses', 'browse', 'search', 'dashboard'] if pg.is_visible(f'#view-{v}')]
        check(f'nav -> {view}', visible == [view], visible)
    pg.click('[data-view="game"]')
    pg.click('#gameStart .gs-start-btn')
    pg.click('#flashcard')
    pg.wait_for_timeout(600)
    pg.click('.fc-btn-yes')
    check('flashcard scores', int(pg.inner_text('#gameScore')) >= 10)
    pg.evaluate('restartGame()')
    pg.click('#tabQuiz')
    pg.click('#gameStart .gs-start-btn')
    pg.wait_for_selector('.quiz-option')
    check('quiz has 4 options', pg.locator('.quiz-option').count() == 4)
    check('regression: no JS errors', not pg.errors, pg.errors[:2])
    pg.context.close()

    # ───────────── Scenario 1: learn + clean typed recall (day 0) ─────────────
    pg = new_page(b)
    open_verses(pg)
    check('fresh state: review button hidden', pg.is_hidden('#vReviewBtn'))
    check('fresh state: card says Spaced reviews', pg.inner_text('#vReviewTitle') == 'Spaced reviews')
    check('picker lists 25+ verses', pg.locator('.verse-card').count() >= 25)

    guided_to_typed(pg, 'Psalm 23:1')
    check('step bar shows 5 steps', pg.locator('.vs-step').count() == 5)
    # Case/punctuation don't matter
    submit(pg, 'the lord is my shepherd i shall not want')
    check('clean pass message', 'Perfect recall' in pg.inner_text('#vsMsg'))
    click_btn(pg, 'Continue →')
    check('result: recalled from memory', pg.inner_text('#vrTitle') == 'Recalled from memory!')
    check('result: 1 of 3 recall days', pg.inner_text('#vrStars') == '●○○', pg.inner_text('#vrStars'))
    check('result: +25 XP', '+25 XP' in pg.inner_text('#vrXp'), pg.inner_text('#vrXp'))
    check('result: next review tomorrow', 'Next review tomorrow' in pg.inner_text('#vrXp'))
    check('result: 2 more days to master', '2 more recall days' in pg.inner_text('#vrXp'))
    c = card(pg, 'Psalm 23:1')
    check('card stored: stage 0, due tomorrow, 1 day',
          c and c['stage'] == 0 and c['due'] == day(1) and c['days'] == [day(0)], c)
    check('xp = 25', xp(pg) == 25, xp(pg))
    pg.locator('#vResult button', has_text='All verses').click()
    check('picker: caught-up card', pg.inner_text('#vReviewTitle') == "You're all caught up")
    check('picker: next review tomorrow', 'tomorrow' in pg.inner_text('#vReviewSub'))
    check('picker: verse shows review tomorrow', 'review tomorrow' in pg.inner_text('#verseGrid'))
    if SHOTS:
        pg.screenshot(path=f'{SHOTS}/picker_after_learning.png')
    check('scenario 1: no JS errors', not pg.errors, pg.errors[:2])
    pg.context.close()

    # ───────────── Scenario 2: miss, feedback diff, same-day retry ─────────────
    pg = new_page(b)
    open_verses(pg)
    pg.evaluate('startVerse("John 3:16"); vs.step = 4; renderStep()')
    full = verse_text(pg, 'John 3:16')
    submit(pg, full.replace('only begotten ', ''))
    check('miss message', 'Not yet' in pg.inner_text('#vsMsg'))
    check('miss: missing words shown in red', pg.locator('.d-miss').count() >= 1)
    check('miss: offers Try again + Finish', pg.get_by_role('button', name='Try again').count() == 1
          and pg.get_by_role('button', name='Finish for today').count() == 1)
    c = card(pg, 'John 3:16')
    check('miss recorded: stage 0, lapse 1, no recall day',
          c['stage'] == 0 and c['lapses'] == 1 and c['days'] == [], c)
    check('miss earns no XP', xp(pg) == 0, xp(pg))
    if SHOTS:
        pg.screenshot(path=f'{SHOTS}/typed_miss.png')
    click_btn(pg, 'Try again')
    check('retry: input cleared and enabled', pg.input_value('#vsInput') == '' and pg.is_enabled('#vsInput'))
    submit(pg, full)
    check('retry pass: not counted notice', 'already practiced this verse today' in pg.inner_text('#vsMsg'))
    c2 = card(pg, 'John 3:16')
    check('retry did not change schedule', c2 == c, (c, c2))
    check('retry earns no XP', xp(pg) == 0, xp(pg))
    click_btn(pg, 'Continue →')
    check('result reflects first (missed) attempt', 'Good start' in pg.inner_text('#vrTitle'), pg.inner_text('#vrTitle'))
    check('result: 0 of 3 days', pg.inner_text('#vrStars') == '○○○')
    pg.context.close()

    # ───────────── Scenario 3: hinted pass doesn't count as recall ─────────────
    pg = new_page(b)
    open_verses(pg)
    pg.evaluate('startVerse("Psalm 56:3"); vs.step = 4; renderStep()')
    click_btn(pg, 'Show first letters')
    hint = pg.inner_text('#vsHint')
    check('hint shows first letters', hint.startswith('W___ t___'), hint)
    submit(pg, verse_text(pg, 'Psalm 56:3'))
    check('hinted pass message', 'Recalled with a cue' in pg.inner_text('#vsMsg'))
    c = card(pg, 'Psalm 56:3')
    check('hinted pass: no recall day, stage 0', c['days'] == [] and c['stage'] == 0, c)
    check('hinted pass earns 5 XP', xp(pg) == 5, xp(pg))
    pg.context.close()

    # ───────────── Scenario 4: "I don't remember" + typo tolerance ─────────────
    pg = new_page(b)
    open_verses(pg)
    pg.evaluate('startVerse("Genesis 1:1"); vs.step = 4; renderStep()')
    click_btn(pg, "I don't remember")
    check('gave up: full verse shown', verse_text(pg, 'Genesis 1:1') in pg.inner_text('#vsText'))
    check('gave up: counted as miss', card(pg, 'Genesis 1:1')['lapses'] == 1)
    pg.context.close()

    pg = new_page(b)
    open_verses(pg)
    pg.evaluate('startVerse("Genesis 1:1"); vs.step = 4; renderStep()')
    submit(pg, 'In the begining God created the heaven and the earth.')
    check('typo accepted with spelling note', 'Check the spelling' in pg.inner_text('#vsMsg'))
    check('typo underlined', pg.locator('.d-typo').count() == 1)
    pg.context.close()

    # ───────────── Scenario 5: empty submit + Ctrl+Enter ─────────────
    pg = new_page(b)
    open_verses(pg)
    pg.evaluate('startVerse("Psalm 23:1"); vs.step = 4; renderStep()')
    click_btn(pg, 'Check')
    check('empty submit asks for input', 'Type what you remember' in pg.inner_text('#vsMsg'))
    check('empty submit records nothing', card(pg, 'Psalm 23:1') is None)
    pg.fill('#vsInput', verse_text(pg, 'Psalm 23:1'))
    pg.press('#vsInput', 'Control+Enter')
    check('Ctrl+Enter submits', 'Perfect recall' in pg.inner_text('#vsMsg'))
    pg.context.close()

    # ───────────── Scenario 6: spaced reviews and mastery over several days ─────────────
    pg = new_page(b, 0)
    open_verses(pg)
    # Day 0: learn Psalm 23:1 (pass) and Genesis 1:1 (miss)
    pg.evaluate('startVerse("Psalm 23:1"); vs.step = 4; renderStep()')
    submit(pg, verse_text(pg, 'Psalm 23:1'))
    pg.evaluate('startVerse("Genesis 1:1"); vs.step = 4; renderStep()')
    submit(pg, 'In the beginning God made the heaven and the earth.')
    check('day0: Genesis miss recorded', card(pg, 'Genesis 1:1')['lapses'] == 1)

    # Day 1: both due
    at_day(pg, 1)
    open_verses(pg)
    check('day1: review card shows 2 due', pg.inner_text('#vReviewTitle') == "Today's review: 2 verses due",
          pg.inner_text('#vReviewTitle'))
    check('day1: both cards flagged Due today', pg.locator('.verse-status.due').count() == 2)
    if SHOTS:
        pg.screenshot(path=f'{SHOTS}/review_due.png')
    click_btn(pg, 'Start review')
    check('review: step bar shows Review 1 of 2', pg.inner_text('#vsSteps') == 'Review 1 of 2', pg.inner_text('#vsSteps'))
    check('review: typing area visible, no guided steps', pg.is_visible('#vsInput') and pg.locator('.vs-step').count() == 1)
    seen = []
    for _ in range(3):  # 2 verses + 1 requeued miss
        ref = pg.evaluate('vs.verse.ref')
        seen.append(ref)
        full = verse_text(pg, ref)
        if ref == 'Genesis 1:1' and seen.count(ref) == 1:
            submit(pg, 'In the beginning God created the heaven')   # incomplete: miss
        else:
            submit(pg, full)
        click_btn(pg, 'Next →')
        if pg.is_visible('#vResult'):
            break
    check('review: missed verse was requeued once', seen.count('Genesis 1:1') == 2 and seen.count('Psalm 23:1') == 1, seen)
    check('review: finished on result screen', pg.is_visible('#vResult') and pg.inner_text('#vrTitle') == 'Review complete')
    check('review: summary 1 / 2 recalled', pg.inner_text('#vrStars') == '1 / 2', pg.inner_text('#vrStars'))
    summ = pg.inner_text('#vrText')
    check('review summary lists next dates',
          'Psalm 23:1 — ✓ recalled · next in 3 days' in summ and 'Genesis 1:1 — missed · next tomorrow' in summ, summ)
    p23, gen = card(pg, 'Psalm 23:1'), card(pg, 'Genesis 1:1')
    check('day1: Psalm stage 1, due day4, 2 recall days',
          p23['stage'] == 1 and p23['due'] == day(4) and p23['days'] == [day(0), day(1)], p23)
    check('day1: Genesis reset, due day2, retry did not add a recall day',
          gen['stage'] == 0 and gen['due'] == day(2) and gen['days'] == [], gen)
    check('xp after day1 = 25 + 20', xp(pg) == 45, xp(pg))
    check('review result hides learn-only buttons', pg.is_hidden('#vrNext') and pg.is_hidden('#vrAgain'))
    check('review: not due again same day',
          not pg.evaluate('Recall.dueRefs(getCards(), Recall.dateKey()).length'))
    pg.locator('#vResult button', has_text='All verses').click()
    check('after review: caught up', pg.inner_text('#vReviewTitle') == "You're all caught up")

    # Day 4: Genesis (overdue) + Psalm due -> Psalm reaches 3 recall days = mastered
    at_day(pg, 4)
    open_verses(pg)
    check('day4: 2 due', pg.inner_text('#vReviewTitle') == "Today's review: 2 verses due", pg.inner_text('#vReviewTitle'))
    click_btn(pg, 'Start review')
    for _ in range(2):
        submit(pg, verse_text(pg, pg.evaluate('vs.verse.ref')))
        click_btn(pg, 'Next →')
    check('day4: perfect review', pg.inner_text('#vrStars') == '2 / 2')
    p23, gen = card(pg, 'Psalm 23:1'), card(pg, 'Genesis 1:1')
    check('day4: Psalm mastered (3 days), stage 2, due day11',
          len(p23['days']) == 3 and p23['stage'] == 2 and p23['due'] == day(11), p23)
    check('day4: Genesis 1 recall day, stage 1', len(gen['days']) == 1 and gen['stage'] == 1, gen)
    check('xp after day4 = 45 + 25 + 20', xp(pg) == 90, xp(pg))
    pg.locator('#vResult button', has_text='All verses').click()
    check('picker: Mastered count 1/', pg.inner_text('#vMastered').startswith('1/'), pg.inner_text('#vMastered'))
    grid = pg.inner_text('#verseGrid')
    check('picker: Psalm shows Mastered + next review', 'Mastered · review in 7 days' in grid, grid[:300])
    if SHOTS:
        pg.screenshot(path=f'{SHOTS}/picker_mastered.png')
    check('scenario 6: no JS errors', not pg.errors, pg.errors[:2])
    pg.context.close()

    # ───────────── Scenario 7: mobile layout with the typing UI ─────────────
    pg = new_page(b, 0, width=390, height=800)
    pg.click('.menu-toggle')
    pg.click('[data-view="verses"]')
    pg.evaluate('startVerse("Isaiah 41:10"); vs.step = 4; renderStep()')
    pg.fill('#vsInput', 'Fear thou not; for I am with thee')
    if SHOTS:
        pg.screenshot(path=f'{SHOTS}/mobile_typing.png')
    click_btn(pg, 'Check')
    if SHOTS:
        pg.screenshot(path=f'{SHOTS}/mobile_feedback.png')
    check('mobile: no horizontal overflow',
          not pg.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth'))
    check('mobile: no JS errors', not pg.errors, pg.errors[:2])
    pg.context.close()

    b.close()

print(f'\n{passes} passed, {len(fails)} failed')
print('FAILED:', fails if fails else 'none')
raise SystemExit(1 if fails else 0)
