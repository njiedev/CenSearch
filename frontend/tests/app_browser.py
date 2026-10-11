"""Local browser checks. Synthetic enrollment responses; never upload fixture faces.
Run from the repo root: backend/.venv/bin/python frontend/tests/app_browser.py
"""
import asyncio
import json
import os
from pathlib import Path
from playwright.async_api import async_playwright, expect

BASE = os.environ.get('CENSEARCH_TEST_URL', 'http://127.0.0.1:5174')
SHOTS = Path('/tmp/censearch-app-shots')
SHOTS.mkdir(exist_ok=True)

async def shot(page, name):
    await page.screenshot(path=str(SHOTS / f'{name}.png'), full_page=True)
    print(f'SCREENSHOT {SHOTS / (name + ".png")}', flush=True)

async def no_overflow(page, label):
    dimensions = await page.evaluate('({width:innerWidth, scroll:document.documentElement.scrollWidth})')
    assert dimensions['scroll'] <= dimensions['width'], (label, dimensions)

async def responsive(page, label):
    for width in [360,600,840,1440]:
        await page.set_viewport_size({'width':width,'height':1000})
        await page.wait_for_timeout(60)
        await no_overflow(page, f'{label} at {width}')

async def keyboard_to(page, locator):
    for _ in range(100):
        if await locator.evaluate('(el) => el === document.activeElement'):
            assert await locator.evaluate('(el) => { const s = getComputedStyle(el); return s.outlineStyle !== "none" || s.boxShadow !== "none" }'), 'Missing focus ring'
            return
        await page.keyboard.press('Tab')
    raise AssertionError('Keyboard could not reach ' + str(locator))

async def fill_authorization(page, keyboard=False, review=True):
    if review:
        review_box = page.get_by_role('checkbox', name='Review notices before sending')
        if keyboard:
            await keyboard_to(page, review_box)
            await page.keyboard.press('Space')
        else:
            await review_box.check()
    for label, value in [('Email', 'alex@example.test'), ('Address', '123 Sample Street'), ('Phone', '555-0100')]:
        field = page.get_by_role('textbox', name=label, exact=True)
        if keyboard:
            await keyboard_to(page, field)
            await page.keyboard.insert_text(value)
        else:
            await field.fill(value)
    check = page.get_by_role('checkbox', name='I accept the legal-responsibility warning and authorize this batch.')
    if keyboard:
        await keyboard_to(page, check)
        await page.keyboard.press('Space')
        await keyboard_to(page, page.get_by_role('button', name='Prepare requests' if review else 'Review and send automatically'))
        await page.keyboard.press('Enter')
    else:
        await check.check()
        await page.get_by_role('button', name='Prepare requests' if review else 'Review and send automatically').click()

async def sample_flow(browser):
    context = await browser.new_context(viewport={'width':1440,'height':1000})
    page = await context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    await page.goto(BASE + '/app/?sample=1')
    await expect(page.get_by_role('heading', name='What should we look for?')).to_be_visible()
    await shot(page, 'home')
    await page.get_by_role('button', name='Start scan', exact=True).click()
    await responsive(page, 'new scan form')
    await page.get_by_role('button', name='Start scan', exact=True).click()
    await expect(page.get_by_text('Enter a name, a handle, or at least one page URL.')).to_be_visible()
    await page.get_by_role('textbox', name='Full name', exact=False).fill('Alex Rivera')
    await page.get_by_role('checkbox', name='I allow this scan', exact=False).check()
    await page.get_by_role('button', name='Start scan', exact=True).click()
    await expect(page.locator('.scan-art')).to_be_visible()
    await page.wait_for_timeout(2100)
    await responsive(page, 'scanning')
    await shot(page, 'scanning')
    assert await page.locator('.scan-art').get_attribute('aria-hidden') == 'true'
    assert await page.locator('.scan-tile').count() == 6
    await expect(page.get_by_role('button', name='Review with agent')).to_be_visible(timeout=22000)
    await page.get_by_role('button', name='More filters').click()
    await page.get_by_role('searchbox', name='Search pages').fill('pixboard')
    await expect(page.locator('.filter-summary')).to_contain_text('2 of 8')
    await shot(page, 'scan-detail-filters')
    await page.keyboard.press('Escape')
    await page.get_by_role('button', name='Open match 9:', exact=False).click()
    await expect(page.get_by_role('dialog')).to_be_visible()
    await page.keyboard.press('Escape')
    await expect(page.get_by_role('button', name='search: pixboard ×')).to_be_visible()
    await expect(page.get_by_role('button', name='Open match 9: pixboard.example', exact=True)).to_be_focused()
    await page.get_by_role('button', name='Clear filters', exact=True).click()
    await page.get_by_role('button', name='Select all visible').click()
    await page.get_by_role('button', name='Review with agent').click()
    await expect(page.get_by_role('button', name='Review and send automatically')).to_be_disabled()
    await responsive(page, 'authorization')
    await fill_authorization(page)
    await expect(page.get_by_role('heading', name='Batch running')).to_be_visible()
    await responsive(page, 'preparation')
    await expect(page.get_by_role('heading', name='Review every request')).to_be_visible(timeout=12000)
    for group in ['Ready to send (3)', 'Drafted for you to send yourself (1)', 'Left alone (1)', 'Held for review (2)', 'Failed (1)']:
        await expect(page.get_by_role('heading', name=group, exact=True)).to_be_visible()
    await page.locator('.review-item [data-slot=accordion-trigger]').first.click()
    await expect(page.get_by_text('Source: rule-based fallback', exact=True).first).to_be_visible()
    await expect(page.locator('.mx-notice').first).to_contain_text('Name: Alex Rivera')
    await responsive(page, 'expanded review')
    await shot(page, 'review')
    batch_url = page.url
    await page.reload()
    await expect(page.get_by_role('heading', name='Review every request')).to_be_visible()
    assert page.url == batch_url
    await page.get_by_role('checkbox', name='Include request 9', exact=True).uncheck()
    await page.get_by_role('button', name='Send 2 requests', exact=True).click()
    await expect(page.get_by_role('region', name='Confirm sending')).to_contain_text('This cannot be undone.')
    await page.get_by_role('region', name='Confirm sending').get_by_role('button', name='Send 2 requests').click()
    await expect(page.get_by_role('heading', name='Batch complete')).to_be_visible(timeout=8000)
    await expect(page.get_by_role('heading', name='Sent (2)', exact=True)).to_be_visible()
    await responsive(page, 'batch complete')
    await expect(page.get_by_role('heading', name='Drafted for you to send yourself (2)', exact=True)).to_be_visible()
    await page.get_by_role('button', name='Back to scan', exact=True).click()
    await page.get_by_role('link', name='Settings', exact=True).click()
    await page.locator('a[href="#settings/whitelist"]').click()
    await page.get_by_role('textbox', name='Site or URL').fill('https://www.pixboard.example/gallery')
    await expect(page.get_by_text('Will save: pixboard.example')).to_be_visible()
    await page.get_by_role('button', name='Add site', exact=True).click()
    await expect(page.get_by_role('button', name='Remove pixboard.example')).to_be_visible()
    await shot(page, 'settings')
    await page.locator('[data-slot=sidebar] a[href="#scan/2"]').click()
    await expect(page.locator('.filter-summary')).to_contain_text('6 of 8')
    await page.get_by_role('button', name='More filters', exact=False).click()
    await page.get_by_role('checkbox', name='Show whitelisted (2)').check()
    await page.keyboard.press('Escape')
    await expect(page.get_by_role('checkbox', name='Select match 9', exact=True)).to_be_disabled()
    await page.get_by_role('button', name='Open match 9:', exact=False).click()
    await page.get_by_role('button', name='Remove from whitelist', exact=True).click()
    await expect(page.get_by_role('button', name='Add site to whitelist', exact=True)).to_be_visible()
    await page.keyboard.press('Escape')
    await expect(page.get_by_role('checkbox', name='Select match 9', exact=True)).to_be_enabled()
    await page.get_by_role('link', name='All scans', exact=True).click()
    await expect(page.get_by_role('table')).to_be_visible()
    await page.get_by_role('button', name='Matches ↕').click()
    await page.get_by_role('searchbox', name='Find a scan').fill('nothing-like-this')
    await expect(page.get_by_role('heading', name='No scans match your search')).to_be_visible()
    await page.get_by_role('button', name='Clear search').click()
    for width in [360,600,840,1440]:
        await page.set_viewport_size({'width':width,'height':1000})
        for route in ['home','scans','scan/2','settings']:
            await page.goto(BASE + '/app/?sample=1#' + route)
            await page.wait_for_timeout(150)
            await no_overflow(page, f'{route} at {width}')
        if width == 360:
            await page.get_by_role('button', name='Toggle navigation').click()
            await expect(page.get_by_role('dialog', name='Sidebar', exact=True)).to_be_visible()
            await page.keyboard.press('Escape')
            await expect(page.get_by_role('button', name='Toggle navigation')).to_be_focused()
    assert not errors, errors
    print('PASS sample flow, validation, filters, modal focus, preparation, reload, subset send, outcomes, whitelist, all scans, 360/600/840/1440 overflow', flush=True)
    await context.close()

async def keyboard_flow(browser):
    context = await browser.new_context(viewport={'width':1440,'height':1000}, reduced_motion='reduce')
    page = await context.new_page()
    await page.goto(BASE + '/app/?sample=1')
    await keyboard_to(page, page.get_by_role('button', name='Start scan', exact=True))
    assert await page.get_by_role('button', name='Start scan', exact=True).evaluate('(el) => getComputedStyle(el).animationName') == 'none'
    await page.keyboard.press('Enter')
    await keyboard_to(page, page.get_by_role('textbox', name='Full name', exact=False))
    await page.keyboard.insert_text('Alex Rivera')
    await keyboard_to(page, page.get_by_role('checkbox', name='I allow this scan', exact=False))
    await page.keyboard.press('Space')
    await keyboard_to(page, page.get_by_role('button', name='Start scan', exact=True))
    await page.keyboard.press('Enter')
    await expect(page.locator('.scan-art')).to_be_visible()
    assert await page.locator('.scan-tile').first.evaluate('(el) => getComputedStyle(el).display') == 'none'
    before = await page.locator('.scan-eye .logo-pupil').get_attribute('cx')
    await page.wait_for_timeout(500)
    assert before == await page.locator('.scan-eye .logo-pupil').get_attribute('cx')
    assert await page.locator('.scan-eye animate').count() == 0
    await expect(page.get_by_role('button', name='Select all visible')).to_be_visible(timeout=22000)
    await keyboard_to(page, page.get_by_role('checkbox', name='Select match 9', exact=True))
    await page.keyboard.press('Space')
    await keyboard_to(page, page.get_by_role('button', name='Review with agent'))
    await page.keyboard.press('Enter')
    await fill_authorization(page, keyboard=True)
    await expect(page.get_by_role('heading', name='Review every request')).to_be_visible(timeout=12000)
    await keyboard_to(page, page.locator('.review-item [data-slot=accordion-trigger]').first)
    await page.keyboard.press('Enter')
    await expect(page.locator('.mx-notice')).to_be_visible()
    await keyboard_to(page, page.get_by_role('button', name='Send 1 requests', exact=True))
    await page.keyboard.press('Enter')
    await keyboard_to(page, page.locator('.confirmation').get_by_role('button', name='Send 1 requests'))
    await page.keyboard.press('Enter')
    await expect(page.get_by_role('heading', name='Batch complete')).to_be_visible(timeout=8000)
    print('PASS keyboard-only main flow and visible focus; reduced-motion border, hidden tiles and still pupil', flush=True)
    await context.close()

async def response_checks(browser):
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(BASE + '/app/')
    await expect(page).to_have_url(BASE + '/signup.html')
    # Synthetic, local enrollment response. The uploaded bytes are not a face.
    await page.route('**/api/people', lambda route: route.fulfill(json={'person': {'id':'test-person','name':'Browser Test'},'photos':[]}))
    await page.route('**/api/people/test-person', lambda route: route.fulfill(json={'id':'test-person','name':'Browser Test'}))
    await page.route('**/api/people/test-person/scans', lambda route: route.fulfill(json=[]))
    await page.route('**/api/people/test-person/whitelist', lambda route: route.fulfill(json={'domains':[]}))
    await page.route('**/api/cases?**', lambda route: route.fulfill(json=[]))
    await page.get_by_role('textbox', name='Name', exact=True).fill('Browser Test')
    await page.locator('#su-references').set_input_files({'name':'synthetic.png','mimeType':'image/png','buffer':bytes.fromhex('89504e470d0a1a0a')})
    await page.get_by_role('checkbox', name='I agree', exact=False).check()
    await page.get_by_role('button', name='Enroll my face').click()
    await expect(page).to_have_url(BASE + '/app/')
    await expect(page.get_by_role('heading', name='What should we look for?')).to_be_visible()
    assert await page.evaluate("JSON.parse(localStorage.getItem('censearch.session')).id") == 'test-person'
    await expect(page.locator('.sample-label')).to_have_count(0)
    await page.get_by_role('button', name='View all scans').click()
    await expect(page.get_by_role('heading', name='No scans yet')).to_be_visible()
    # Real session must never silently become sample, even after reloading.
    await page.unroute('**/api/people/test-person/scans')
    await page.route('**/api/people/test-person/scans', lambda route: route.abort())
    await page.reload()
    await expect(page.get_by_role('alert')).to_contain_text('Connection lost')
    await expect(page.locator('.sample-label')).to_have_count(0)
    await page.unroute('**/api/people/test-person')
    await page.route('**/api/people/test-person', lambda route: route.fulfill(status=404,json={'detail':'Person not found'}))
    await page.reload()
    await expect(page).to_have_url(BASE + '/signup.html')
    assert await page.evaluate("localStorage.getItem('censearch.session')") is None
    print('PASS no-session redirect, synthetic signup handoff, empty scans, mid-session network failure stays real, missing-person signout', flush=True)
    await context.close()
    for status, body, fallback in [(502,'',True),(504,'',True),(500,'',False),(503,'{"detail":"Unavailable"}',False),(502,'{"detail":"Upstream failed"}',False)]:
        context = await browser.new_context()
        page = await context.new_page()
        await page.add_init_script("if (!sessionStorage.getItem('test.seeded')) { localStorage.setItem('censearch.session', JSON.stringify({id:'test',name:'Test'})); sessionStorage.setItem('test.seeded','1') }")
        async def respond(route):
            await route.fulfill(status=status, body=body)
        await page.route('**/api/**', respond)
        await page.goto(BASE + '/app/')
        if fallback:
            await expect(page.locator('.sample-label')).to_be_visible()
            await expect(page.get_by_role('heading', name='What should we look for?')).to_be_visible()
        else:
            await expect(page.get_by_role('alert')).to_be_visible()
            await expect(page.locator('.sample-label')).to_have_count(0)
        await context.close()
    print('PASS first-call proxy 502/504 fallback and reachable 500/503/JSON-502 errors', flush=True)

async def failures_and_compatibility(browser):
    context = await browser.new_context(viewport={'width':360,'height':1000})
    page = await context.new_page()
    await page.goto(BASE + '/app/?sample=1#new')
    await page.get_by_role('textbox', name='Full name', exact=False).fill('Alex Rivera')
    await page.get_by_role('checkbox', name='I allow this scan', exact=False).check()
    await page.get_by_role('button', name='Start scan', exact=True).click()
    await page.wait_for_timeout(2300)
    await page.get_by_role('button', name='Cancel scan').click()
    await expect(page.get_by_role('heading', name='Scan cancelled')).to_be_visible()
    await page.get_by_role('button', name='Open partial results').click()
    await expect(page.locator('.filter-summary')).to_contain_text('1 of 1')
    await no_overflow(page, 'cancelled partial results')
    await page.goto(BASE + '/matches.html')
    await expect(page.get_by_role('heading', name='Matches (8)')).to_be_visible()
    await page.get_by_role('button', name='Select all', exact=True).click()
    await page.get_by_role('button', name='Auto review / send').click()
    await expect(page.get_by_role('heading', name='Authorize automatic requests')).to_be_visible()
    for label, value in [('Email','alex@example.test'),('Address','123 Sample St'),('Phone','555-0100')]:
        await page.get_by_role('textbox', name=label, exact=True).fill(value)
    await page.get_by_role('checkbox', name='I accept', exact=False).check()
    await page.get_by_role('button', name='Run batch').click()
    await expect(page.get_by_role('heading', name='Batch finished')).to_be_visible(timeout=15000)
    await context.close()
    print('PASS cancel with partial results and original matches.html mock batch', flush=True)

    context = await browser.new_context(viewport={'width':1440,'height':1000})
    page = await context.new_page()
    await page.add_init_script("if (!sessionStorage.getItem('test.seeded')) { localStorage.setItem('censearch.session', JSON.stringify({id:'test',name:'Test'})); sessionStorage.setItem('test.seeded','1') }")
    await page.route('**/api/people/test', lambda route: route.fulfill(json={'id':'test','name':'Test','consent':'Synthetic test consent','created_at':'2026-10-11T00:00:00Z','development_fixture':False,'references':[],'originals':[],'active_reference_count':0}))
    await page.route('**/api/people/test/scans', lambda route: route.fulfill(json=[]))
    await page.route('**/api/cases?**', lambda route: route.fulfill(json=[]))
    async def whitelist(route):
        if route.request.method == 'PUT':
            await route.fulfill(status=422, json={'detail':'Invalid whitelist entry'})
        else:
            await route.fulfill(json={'domains':['keep.example']})
    await page.route('**/api/people/test/whitelist', whitelist)
    await page.goto(BASE + '/app/#settings/whitelist')
    await page.get_by_role('button', name='Remove keep.example').click()
    await expect(page.get_by_role('alert')).to_contain_text('Invalid whitelist entry')
    await expect(page.get_by_role('button', name='Remove keep.example')).to_be_visible()
    await page.get_by_role('textbox', name='Site or URL').fill('bad-entry')
    await page.get_by_role('button', name='Add site', exact=True).click()
    await expect(page.get_by_role('alert')).to_contain_text('Enter a valid domain or public URL.')
    await page.get_by_role('link', name='New scan', exact=True).click()
    await page.get_by_role('radio', name='Name / links', exact=False).check()
    await page.get_by_role('textbox', name='Full name', exact=False).fill('alex@example.test')
    await page.get_by_role('button', name='Start scan', exact=True).click()
    await expect(page.get_by_text('Use a name only, without email addresses, URLs or image data.')).to_be_visible()
    await page.get_by_role('textbox', name='Full name', exact=False).fill('Alex Rivera')
    await page.get_by_role('checkbox', name='I allow this scan', exact=False).check()
    for status, message in [(409,'Busy'),(422,'Invalid page URL'),(404,'Search person missing')]:
        async def reject(route):
            await route.fulfill(status=status, json={'detail':message})
        await page.route('**/api/public-searches', reject)
        await page.get_by_role('button', name='Start scan', exact=True).click()
        await expect(page.get_by_role('alert')).to_contain_text('Another operation is running' if status == 409 else message)
        await expect(page.locator('.sample-label')).to_have_count(0)
        await page.unroute('**/api/public-searches')
    # Delete confirmation must precede the only DELETE, and success clears the session.
    deletes = []
    async def person(route):
        if route.request.method == 'DELETE':
            deletes.append(route.request.method)
            await route.fulfill(json={'deleted':'test'})
        else:
            await route.fulfill(json={'id':'test','name':'Test','consent':'Synthetic test consent','created_at':'2026-10-11T00:00:00Z','development_fixture':False,'references':[],'originals':[],'active_reference_count':0})
    await page.unroute('**/api/people/test')
    await page.route('**/api/people/test', person)
    await page.get_by_role('link', name='Settings', exact=True).click()
    await page.get_by_role('button', name='Delete my enrollment').click()
    assert not deletes
    await expect(page.locator('.confirmation')).to_contain_text('This cannot be undone.')
    await page.get_by_role('button', name='Delete enrollment permanently').click()
    await expect(page).to_have_url(BASE + '/')
    assert deletes == ['DELETE']
    assert await page.evaluate("localStorage.getItem('censearch.session')") is None
    await context.close()
    print('PASS optimistic whitelist rollback, invalid domains/text, scan 409/422/404, confirmed deletion and signout (intercepted API)', flush=True)

async def long_text_and_history(browser):
    context = await browser.new_context(viewport={'width':360,'height':1000})
    page = await context.new_page()
    await page.goto(BASE + '/app/?sample=1')
    await page.get_by_role('button', name='Start scan', exact=True).click()
    await page.get_by_role('textbox', name='Full name', exact=False).fill('Temporary')
    await page.get_by_role('checkbox', name='I allow this scan', exact=False).check()
    await page.get_by_role('button', name='Start scan', exact=True).click()
    await page.get_by_role('button', name='Cancel scan').click()
    await expect(page.get_by_role('heading', name='Scan cancelled')).to_be_visible()
    await page.evaluate("""(() => {
      const data = JSON.parse(sessionStorage.getItem('censearch.sample.v1'));
      data.scans.find(s => s.run_id === 1).label = 'A very long scan label '.repeat(20);
      data.cases[1][0].page_url = 'https://' + 'longhost'.repeat(7) + '.example/' + 'long-path/'.repeat(100);
      sessionStorage.setItem('censearch.sample.v1', JSON.stringify(data));
    })()""")
    await page.goto(BASE + '/app/?sample=1#scan/1')
    await expect(page.get_by_role('button', name='Review with agent')).to_be_visible()
    await no_overflow(page, 'long scan label and URL at 360')
    await page.get_by_role('button', name='Open match 1:', exact=False).click()
    await expect(page.get_by_role('dialog')).to_be_visible()
    fonts = await page.locator('.mx-zoom-section h3').evaluate_all('(els) => els.map(el => getComputedStyle(el).fontFamily)')
    assert all('Pixel' not in font for font in fonts), fonts
    assert await page.locator('.mx-zoom-panel').evaluate('(el) => el.scrollWidth <= el.clientWidth')
    await page.keyboard.press('Escape')
    await page.goto(BASE + '/app/?sample=1#home')
    await page.get_by_role('button', name='View all scans').click()
    await expect(page.get_by_role('heading', name='All scans', exact=True)).to_be_visible()
    await page.go_back()
    await expect(page.get_by_role('heading', name='What should we look for?')).to_be_visible()
    await page.go_forward()
    await expect(page.get_by_role('heading', name='All scans', exact=True)).to_be_visible()
    await page.reload()
    await expect(page.get_by_role('heading', name='All scans', exact=True)).to_be_visible()
    await context.close()
    print('PASS long labels/URLs, app modal fonts, browser back/forward and reload routing', flush=True)

async def automatic_email_flow(browser):
    context = await browser.new_context(viewport={'width':1440,'height':1000}, reduced_motion='reduce')
    page = await context.new_page()
    posts = []
    page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
    await page.goto(BASE + '/app/?sample=1#scan/1')
    await page.get_by_role('button', name='Select all visible').click()
    await page.get_by_role('button', name='Review with agent').click()
    await expect(page.get_by_role('heading', name='Authorize automatic requests')).to_be_visible()
    await expect(page.get_by_role('checkbox', name='Review notices before sending')).not_to_be_checked()
    await expect(page.get_by_text('Sample mode: deliveries are simulated. No email is sent.')).to_be_visible()
    await expect(page.get_by_role('button', name='Review and send automatically')).to_be_disabled()
    await responsive(page, 'automatic authorization')
    await fill_authorization(page, keyboard=True, review=False)
    await expect(page.get_by_role('heading', name='Batch running')).to_be_visible()
    await expect(page.get_by_role('heading', name='Batch complete')).to_be_visible(timeout=15000)
    await expect(page.get_by_role('heading', name='Sent (3)', exact=True)).to_be_visible()
    await expect(page.get_by_role('heading', name='Held for review (2)', exact=True)).to_be_visible()
    await expect(page.get_by_role('heading', name='Failed (1)', exact=True)).to_be_visible()
    await expect(page.get_by_role('region', name='Confirm sending')).to_have_count(0)
    await page.locator('.review-item [data-slot=accordion-trigger]').last.click()
    await expect(page.get_by_text('Simulated email delivery. No network request was sent.').last).to_be_visible()
    await responsive(page, 'automatic outcomes')
    await page.reload()
    await expect(page.get_by_role('heading', name='Batch complete')).to_be_visible()
    assert not posts, posts
    await context.close()
    print('PASS automatic batch default, one authorization, keyboard submission, exact outcomes, reload, responsive layout, no real network deliveries', flush=True)

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            await automatic_email_flow(browser)
            await sample_flow(browser)
            await keyboard_flow(browser)
            await response_checks(browser)
            await failures_and_compatibility(browser)
            await long_text_and_history(browser)
        finally:
            await browser.close()
    print('ALL BROWSER CHECKS PASSED', flush=True)

if __name__ == '__main__':
    asyncio.run(main())
