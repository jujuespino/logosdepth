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


def new_page(browser, n=0, width=1280, height=900, onboarded=True, init_script=None, **ctx_opts):
    ctx = browser.new_context(viewport={'width': width, 'height': height}, **ctx_opts)
    if onboarded:  # most tests aren't about the first-run walkthrough
        ctx.add_init_script("try { localStorage.setItem('ld_onboarded', 'true'); } catch (e) {}")
    if init_script:
        ctx.add_init_script(init_script)
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


def wait_for(pg, expr, timeout=10000):
    """Poll a JS expression with evaluate(); wait_for_function evals a string, which the page's CSP forbids."""
    waited = 0
    while waited < timeout:
        if pg.evaluate(f'() => !!({expr})'):
            return
        pg.wait_for_timeout(100)
        waited += 100
    raise TimeoutError(expr)


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
    """Play the guided steps (Read, Phrases when present, Fill In, Order, Recall) through the UI."""
    pg.evaluate(f'startVerse({ref!r})')
    click_btn(pg, "I've read it →")
    while pg.evaluate('vs.steps[vs.step].id') != 'type':
        step = pg.evaluate('vs.steps[vs.step].id')
        guard = 0
        while pg.get_by_role('button', name='Next step →').count() == 0 and guard < 80:
            guard += 1
            if step == 'phrases':
                phase = pg.evaluate('vs.phr.stage')
                if phase == 'study':
                    click_btn(pg, 'Cover it and type it →')
                else:
                    pg.fill('#vsInput', pg.evaluate('vs.phrases[vs.phr.i]'))
                    click_btn(pg, 'Check')
                continue
            idx = pg.evaluate('''() => {
                if (vs.steps[vs.step].id === 'order')
                    return vs.order.bank.findIndex(c => c.key === normUnit(vs.order.units[vs.order.pos]));
                return vs.fill.bank.findIndex(c => c.key === vs.tokens[vs.fill.active].key);
            }''')
            pg.locator('#vsBank .vchip').nth(idx).click()
        check(f'{ref}: guided step {step} completes', pg.get_by_role('button', name='Next step →').count() == 1, guard)
        click_btn(pg, 'Next step →')
    check(f'{ref}: arrives at Type It', pg.evaluate('vs.steps[vs.step].id') == 'type')


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
    check('fresh state: no review card yet', pg.is_hidden('#vReviewCard'))
    check('picker lists the Start Here verses', pg.locator('.verse-card').count() >= 10)

    guided_to_typed(pg, 'Psalm 23:1')
    check('step bar matches the steps for this verse (incl. Phrases)', pg.locator('.vs-step').count() == pg.evaluate('vs.steps.length') == 6)
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
    pg.evaluate('startVerse("John 3:16"); goToStep("type")')
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
    pg.evaluate('startVerse("Psalm 56:3"); goToStep("type")')
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
    pg.evaluate('startVerse("Genesis 1:1"); goToStep("type")')
    click_btn(pg, "I don't remember")
    check('gave up: full verse shown', verse_text(pg, 'Genesis 1:1') in pg.inner_text('#vsText'))
    check('gave up: counted as miss', card(pg, 'Genesis 1:1')['lapses'] == 1)
    pg.context.close()

    pg = new_page(b)
    open_verses(pg)
    pg.evaluate('startVerse("Genesis 1:1"); goToStep("type")')
    submit(pg, 'In the begining God created the heaven and the earth.')
    check('typo accepted with spelling note', 'Check the spelling' in pg.inner_text('#vsMsg'))
    check('typo underlined', pg.locator('.d-typo').count() == 1)
    pg.context.close()

    # ───────────── Scenario 5: empty submit + Ctrl+Enter ─────────────
    pg = new_page(b)
    open_verses(pg)
    pg.evaluate('startVerse("Psalm 23:1"); goToStep("type")')
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
    pg.evaluate('startVerse("Psalm 23:1"); goToStep("type")')
    submit(pg, verse_text(pg, 'Psalm 23:1'))
    pg.evaluate('startVerse("Genesis 1:1"); goToStep("type")')
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

    # ───────────── Scenario 8: packs, translations, exact word links ─────────────
    pg = new_page(b)
    open_verses(pg)
    n_start = pg.locator('.verse-card').count()
    check('a new learner starts on the short Start Here pack', pg.input_value('#packSelect') == 'start' and 10 <= n_start <= 30, n_start)
    check('pack picker lists 10+ packs plus All', pg.locator('#packSelect option').count() >= 11, pg.locator('#packSelect option').count())
    pg.select_option('#packSelect', 'all')
    n_all = pg.locator('.verse-card').count()
    check('All shows 100+ verses', n_all >= 100, n_all)
    pg.select_option('#packSelect', 'comfort')
    n_comfort = pg.locator('.verse-card').count()
    check('pack filter narrows the list', 10 <= n_comfort < n_all, n_comfort)
    pg.reload()
    pg.wait_for_selector('.verse-card', state='attached')
    open_verses(pg)
    check('pack filter persists across reload', pg.input_value('#packSelect') == 'comfort')
    pg.select_option('#packSelect', 'all')
    check('All restores the full list', pg.locator('.verse-card').count() == n_all)

    # Translation switch: separate text and separate progress
    web_text = pg.evaluate('verseList.find(v => v.ref === "John 3:16").translations.web')
    kjv_text = verse_text(pg, 'John 3:16')
    check('WEB and KJV texts differ', web_text != kjv_text)
    pg.get_by_role('button', name='WEB', exact=True).click()
    pg.evaluate('startVerse("John 3:16")')
    check('session uses WEB text and WEB card key', pg.evaluate('vs.text') == web_text and pg.evaluate('vs.key') == 'John 3:16|web')
    check('session header shows WEB', '· WEB' in pg.inner_text('#vsRef'))
    pg.evaluate('goToStep("type")')
    submit(pg, kjv_text)
    check('KJV wording is rejected when learning WEB', 'Not yet' in pg.inner_text('#vsMsg'))
    click_btn(pg, 'Try again')
    submit(pg, web_text)
    click_btn(pg, 'Continue →')
    check('result shows (WEB)', '(WEB)' in pg.inner_text('#vrRef'), pg.inner_text('#vrRef'))
    check('progress stored under the WEB key only', card(pg, 'John 3:16|web') is not None and card(pg, 'John 3:16') is None)

    # Exact original-language words (John 3:16: loved = agapao, believeth = pisteuo; not agape/pistis)
    chips = pg.locator('#vrWords .recent-tag').all_inner_texts()
    joined = ' | '.join(chips)
    check('result lists exact words: agapao and pisteuo', 'agapaō' in joined and 'pisteuō' in joined, joined)
    check('result does not list the related-but-wrong agape/pistis', 'Agape' not in joined and 'Pistis' not in joined, joined)
    check('curated words come first', 'Aionios' in chips[0] or 'Zoe' in chips[0] or 'Theos' in chips[0], chips[:3])
    pg.locator('#vrWords .recent-tag', has_text='agapaō').click()
    check('brief entry opens in the modal', pg.is_visible('#wordModal') and 'STEPBible' in pg.inner_text('#modalExtended'))
    check('brief entry shows part of speech', 'verb' in pg.inner_text('#modalLang').lower(), pg.inner_text('#modalLang'))
    pg.keyboard.press('Escape')
    pg.locator('#vrWords .recent-tag', has_text='Theos').click()
    check('curated entry keeps its in-depth text', 'Brief entry' not in pg.inner_text('#modalExtended')
          and len(pg.inner_text('#modalExtended')) > 80)
    pg.keyboard.press('Escape')

    # KJV-only verse under WEB falls back to KJV
    pg.locator('#vResult button', has_text='All verses').click()
    check('KJV-only verse is labelled in WEB mode',
          'New · KJV only' in pg.locator('.verse-card', has_text='Psalm 23:1').first.inner_text())
    pg.evaluate('startVerse("Psalm 23:1")')
    check('fallback uses KJV text and plain key',
          pg.evaluate('vs.translation') == 'kjv' and pg.evaluate('vs.key') == 'Psalm 23:1')
    pg.evaluate('exitVerse()')

    # Review a WEB card next day
    at_day(pg, 1)
    open_verses(pg)
    check('WEB card is due next day', pg.inner_text('#vReviewTitle') == "Today's review: 1 verse due", pg.inner_text('#vReviewTitle'))
    click_btn(pg, 'Start review')
    check('review uses the WEB text', pg.evaluate('vs.text') == web_text)
    submit(pg, web_text)
    click_btn(pg, 'Next →')
    check('review summary names the translation', 'John 3:16 (WEB)' in pg.inner_text('#vrText'), pg.inner_text('#vrText'))
    check('scenario 8: no JS errors', not pg.errors, pg.errors[:2])
    pg.context.close()

    # ───────────── Scenario 9: guess-first (pretest) and phrase-by-phrase study ─────────────
    pg = new_page(b)
    open_verses(pg)
    pg.evaluate('startVerse("Psalm 23:1")')
    full = verse_text(pg, 'Psalm 23:1')
    check('guess option offered on the read step', pg.get_by_role('button', name='Guess it first (optional)').count() == 1)
    click_btn(pg, 'Guess it first (optional)')
    check('guess prompt hides the verse', pg.is_visible('#vsInput') and full not in pg.inner_text('#vsText'))
    pg.fill('#vsInput', 'The Lord is my shepherd I will not lack')
    click_btn(pg, 'Check my guess')
    check('guess feedback reports words already known', 'already had' in pg.inner_text('#vsMsg'), pg.inner_text('#vsMsg'))
    check('guess feedback marks correct words', pg.locator('#vsText .d-ok').count() >= 3)
    click_btn(pg, 'Read it →')
    check('then the verse is shown to read', full in pg.inner_text('#vsText'))
    check('guess is only offered once', pg.get_by_role('button', name='Guess it first (optional)').count() == 0)
    check('guessing leaves schedule and XP untouched', card(pg, 'Psalm 23:1') is None and xp(pg) == 0)

    click_btn(pg, "I've read it →")
    check('Phrases step follows Read', pg.evaluate('vs.steps[vs.step].id') == 'phrases')
    check('step bar lists Phrases', 'Phrases' in pg.inner_text('#vsSteps'))
    n_phr = pg.evaluate('vs.phrases.length')
    check('Psalm 23:1 splits into 2 phrases', n_phr == 2, n_phr)
    check('study stage names the phrase', 'Phrase 1 of 2' in pg.inner_text('#vsInstruction'))
    check('study stage shows the phrase', pg.evaluate('vs.phrases[0]') in pg.inner_text('#vsText'))
    click_btn(pg, 'Cover it and type it →')
    check('type stage hides the phrase', pg.evaluate('vs.phrases[0]') not in pg.inner_text('#vsText') and pg.is_visible('#vsInput'))
    pg.fill('#vsInput', 'the lord is')
    click_btn(pg, 'Check')
    check('wrong phrase is marked', 'Not yet' in pg.inner_text('#vsMsg') and pg.locator('#vsText .d-miss').count() >= 1)
    click_btn(pg, 'Try again')
    click_btn(pg, 'Show first letters')
    check('phrase hint shows first letters', pg.inner_text('#vsHint').startswith('T__ L___'), pg.inner_text('#vsHint'))
    pg.fill('#vsInput', pg.evaluate('vs.phrases[0]'))
    pg.press('#vsInput', 'Control+Enter')
    check('correct phrase moves to the next', 'Phrase 2 of 2' in pg.inner_text('#vsInstruction'))
    check('earlier phrase stays visible as context', pg.evaluate('vs.phrases[0]') in pg.inner_text('#vsText'))
    click_btn(pg, 'Cover it and type it →')
    pg.fill('#vsInput', pg.evaluate('vs.phrases[1]'))
    click_btn(pg, 'Check')
    check('finishing phrases completes the step', pg.get_by_role('button', name='Next step →').count() == 1)
    check('phrase practice does not touch schedule or XP', card(pg, 'Psalm 23:1') is None and xp(pg) == 0)
    click_btn(pg, 'Next step →')
    check('next step is Fill In', pg.evaluate('vs.steps[vs.step].id') == 'fill1')

    # A single-phrase verse skips the Phrases step (WEB Hebrews 13:8)
    pg.evaluate('exitVerse()')
    pg.get_by_role('button', name='WEB', exact=True).click()
    pg.evaluate('startVerse("Hebrews 13:8")')
    ids = pg.evaluate('vs.steps.map(s => s.id)')
    check('single-phrase verse has no Phrases step', 'phrases' not in ids and ids[0] == 'read', ids)
    check('scenario 9: no JS errors', not pg.errors, pg.errors[:2])
    pg.context.close()

    # ───────────── Scenario 10: settings, backup/restore, reset, reminder, badge ─────────────
    pg = new_page(b)
    open_verses(pg)
    pg.evaluate('startVerse("Psalm 23:1"); goToStep("type")')
    submit(pg, verse_text(pg, 'Psalm 23:1'))
    click_btn(pg, 'Continue →')
    pg.locator('#vResult button', has_text='All verses').click()
    check('learned verse is due tomorrow, so no badge yet', pg.is_hidden('#dueBadge'))
    at_day(pg, 1)
    check('badge shows 1 due', pg.inner_text('#dueBadge') == '1', pg.inner_text('#dueBadge'))
    check('tab title shows the due count', pg.title().startswith('(1)'), pg.title())
    at_day(pg, 0)

    pg.click('[data-view="settings"]')
    check('settings view opens', pg.is_visible('#view-settings'))
    with pg.expect_download() as dl:
        pg.click('#exportBtn')
    backup_path = dl.value.path()
    backup = json.load(open(backup_path))
    check('backup is a LogosDepth v1 file', backup['app'] == 'logosdepth' and backup['schemaVersion'] == 1)
    check('backup contains the learned verse', 'Psalm 23:1' in backup['data']['srs'] and backup['data']['xp'] == 25)
    check('backup message shown', 'Backup downloaded' in pg.inner_text('#backupMsg'), pg.inner_text('#backupMsg'))
    check('download is named with the date', dl.value.suggested_filename.startswith('logosdepth-progress-')
          and dl.value.suggested_filename.endswith('.json'), dl.value.suggested_filename)

    # Invalid files are rejected without touching progress
    before = pg.evaluate('localStorage.getItem("ld_verse_srs")')
    pg.set_input_files('#importFile', {'name': 'x.json', 'mimeType': 'application/json', 'buffer': b'not json at all'})
    wait_for(pg, 'document.getElementById("backupMsg").textContent.includes("not valid JSON")')
    check('garbage file rejected', 'not valid JSON' in pg.inner_text('#backupMsg'), pg.inner_text('#backupMsg'))
    pg.set_input_files('#importFile', {'name': 'x.json', 'mimeType': 'application/json',
                                       'buffer': json.dumps({'app': 'other', 'schemaVersion': 1, 'data': {}}).encode()})
    wait_for(pg, 'document.getElementById("backupMsg").textContent.includes("LogosDepth backup")')
    check('wrong-app file rejected', pg.is_hidden('#importChoice'))
    check('rejected files change nothing', pg.evaluate('localStorage.getItem("ld_verse_srs")') == before)

    # Erase, then restore (replace)
    pg.click('#resetBtn')
    check('reset asks for confirmation', pg.is_visible('#resetChoice'))
    pg.get_by_role('button', name='Cancel').last.click()
    check('cancelling keeps progress', pg.evaluate('localStorage.getItem("ld_verse_srs")') == before)
    pg.click('#resetBtn')
    pg.get_by_role('button', name='Yes, erase everything').click()
    check('erase removes all progress keys',
          pg.evaluate('["ld_verse_srs","ld_verse_xp","ld_verse_streak","ld_verse_settings"].every(k => localStorage.getItem(k) === null)'))
    pg.set_input_files('#importFile', backup_path)
    pg.wait_for_selector('#importChoice:not(.hidden)')
    check('import summary describes the backup', '1 verse' in pg.inner_text('#importSummary')
          and '25 XP' in pg.inner_text('#importSummary'), pg.inner_text('#importSummary'))
    pg.get_by_role('button', name='Replace my progress').click()
    check('replace restores the card and XP', card(pg, 'Psalm 23:1') is not None and xp(pg) == 25)

    # Merging a backup into newer local progress never loses anything
    pg.evaluate("""() => {
        const c = getCards(); c['Psalm 23:1'].days.push('2026-11-09'); c['Psalm 23:1'].lastDate = '2026-11-09';
        c['Psalm 23:1'].stage = 3; saveCards(c); vSave('ld_verse_xp', 90);
    }""")
    pg.set_input_files('#importFile', backup_path)
    pg.wait_for_selector('#importChoice:not(.hidden)')
    pg.get_by_role('button', name='Merge with my progress (recommended)').click()
    merged = card(pg, 'Psalm 23:1')
    check('merge keeps the newer schedule and all recall days', merged['stage'] == 3 and len(merged['days']) == 2, merged)
    check('merge keeps the larger XP', xp(pg) == 90, xp(pg))

    # Reminder .ics
    pg.fill('#reminderTime', '07:45')
    with pg.expect_download() as dl2:
        pg.get_by_role('button', name='Add to calendar (.ics)').click()
    ics = open(dl2.value.path(), encoding='utf-8').read()
    check('reminder is a daily 07:45 event', 'RRULE:FREQ=DAILY' in ics and 'T074500' in ics, ics[:200])
    check('reminder links back into the app', '/?view=verses' in ics.replace('\r\n ', ''))
    check('scenario 10: no JS errors', not pg.errors, pg.errors[:2])
    pg.context.close()

    # Storage blocked: banner appears and the app still works
    pg = new_page(b, init_script="Storage.prototype.setItem = function () { throw new Error('blocked'); };")
    check('blocked storage shows the banner', pg.is_visible('#storageBanner'))
    open_verses(pg)
    check('app still loads verses with storage blocked', pg.locator('.verse-card').count() >= 10)
    pg.context.close()

    # ───────────── Scenario 11: first-run onboarding ─────────────
    pg = new_page(b, onboarded=False)
    pg.wait_for_selector('#onboard:not(.hidden)')
    check('onboarding opens on first visit (Memorize is the home screen)', pg.is_visible('#onboard'))
    check('step 1 explains how it works', 'Welcome' in pg.inner_text('#onboardTitle') and 'three different days' in pg.inner_text('#onboardBody'))
    pg.get_by_role('button', name='Next →').click()
    check('step 2 offers packs', 'start' in pg.inner_text('#onboardTitle').lower() and pg.locator('.onboard-pack').count() >= 9)
    pg.locator('.onboard-pack', has_text='The Gospel').click()
    check('chosen pack is highlighted', 'active' in pg.locator('.onboard-pack', has_text='The Gospel').get_attribute('class'))
    pg.get_by_role('button', name='Next →').click()
    check('step 3 is the optional reminder', 'habit' in pg.inner_text('#onboardTitle').lower())
    pg.get_by_role('button', name='Start my first verse').click()
    check('overlay closes and a gospel verse starts', pg.is_hidden('#onboard') and pg.is_visible('#vSession'))
    started = pg.evaluate('vs.verse.packs')
    check('first verse comes from the chosen pack', 'gospel' in started, started)
    check('pack choice is remembered', pg.evaluate('getSettings().pack') == 'gospel')
    check('onboarding is remembered', pg.evaluate('localStorage.getItem("ld_onboarded")') == 'true')
    pg.evaluate('exitVerse()')
    pg.click('[data-view="dashboard"]')
    pg.click('[data-view="verses"]')
    check('onboarding does not reappear', pg.is_hidden('#onboard'))
    pg.context.close()

    pg = new_page(b, onboarded=False)
    pg.wait_for_selector('#onboard:not(.hidden)')
    pg.keyboard.press('Escape')
    check('Escape dismisses the intro and remembers it', pg.is_hidden('#onboard')
          and pg.evaluate('localStorage.getItem("ld_onboarded")') == 'true')
    pg.click('[data-view="settings"]')
    pg.get_by_role('button', name='Show the intro').click()
    check('Settings can reopen the intro', pg.is_visible('#onboard'))
    pg.context.close()

    # ───────────── Scenario 12: deep link, manifest and real offline use ─────────────
    ctx = b.new_context(viewport={'width': 1280, 'height': 900})
    ctx.add_init_script("try { localStorage.setItem('ld_onboarded', 'true'); } catch (e) {}")
    pg = ctx.new_page()
    pg.errors = []
    pg.on('pageerror', lambda e: pg.errors.append(str(e)[:160]))
    pg.goto(BASE + '?view=verses')
    pg.wait_for_selector('.verse-card', state='attached')
    check('?view=verses opens the Memorize view', pg.is_visible('#view-verses') and pg.is_hidden('#view-dashboard'))
    mani = pg.evaluate('fetch(document.querySelector("link[rel=manifest]").href).then(r => r.json())')
    check('manifest has name, standalone display and a maskable icon',
          mani['name'] == 'LogosDepth' and mani['display'] == 'standalone'
          and any(i['purpose'] == 'maskable' for i in mani['icons']), mani)
    icon_status = pg.evaluate('Promise.all(document.querySelector("link[rel=manifest]") ? ["/static/icons/icon-192.png","/static/icons/icon-512.png"].map(u => fetch(u).then(r => r.status)) : [])')
    check('manifest icons are served', icon_status == [200, 200], icon_status)
    pg.evaluate('navigator.serviceWorker.ready.then(() => true)')
    pg.reload()
    pg.wait_for_selector('.verse-card', state='attached')
    check('page is controlled by the service worker', pg.evaluate('!!navigator.serviceWorker.controller'))
    ctx.set_offline(True)
    pg.reload()
    pg.wait_for_selector('.verse-card', state='attached', timeout=15000)
    check('offline: page and verses still load', pg.locator('.verse-card').count() >= 10)
    check('offline: fonts and styles still apply', pg.evaluate('getComputedStyle(document.body).backgroundColor') == 'rgb(255, 255, 255)')
    pg.evaluate('startVerse("Psalm 23:1"); goToStep("type")')
    submit(pg, verse_text(pg, 'Psalm 23:1'))
    check('offline: can learn and grade a verse', 'Perfect recall' in pg.inner_text('#vsMsg'))
    check('offline: progress is saved locally', card(pg, 'Psalm 23:1') is not None)
    ctx.set_offline(False)
    check('scenario 12: no JS errors', not pg.errors, pg.errors[:2])
    ctx.close()

    # ───────────── Scenario 7: mobile layout with the typing UI ─────────────
    pg = new_page(b, 0, width=390, height=800)
    pg.click('.menu-toggle')
    pg.click('[data-view="verses"]')
    pg.evaluate('startVerse("Isaiah 41:10"); goToStep("type")')
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
