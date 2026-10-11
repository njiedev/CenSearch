"""Local profile and whitelist integration using synthetic, face-free images.
Run: backend/.venv/bin/python frontend/tests/profile_browser.py
"""
import asyncio
from profile_fixture import profile_fixture
from playwright.async_api import async_playwright, expect



async def main(BASE, PHOTO):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            page = await browser.new_page(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            await page.add_init_script("localStorage.setItem('censearch.session', JSON.stringify({id:'profile-test', name:'Profile test'}));")
            await page.goto(BASE + '/app/#settings')
            await expect(page.get_by_role('heading', name='Profile test', exact=True)).to_be_visible()
            await expect(page.locator('.profile-photo')).to_have_count(3)
            await page.wait_for_function('Array.from(document.querySelectorAll(".profile-photo img")).every(img => img.complete && img.naturalWidth > 0)')
            for width in (360, 600, 840, 1440):
                await page.set_viewport_size({'width': width, 'height': 1000})
                assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
            await page.screenshot(path='/tmp/censearch-profile-desktop.png', full_page=True)
            await page.get_by_role('radio', name='Originals I own').check()
            await page.locator('#profile-files').set_input_files(str(PHOTO))
            await expect(page.get_by_role('button', name='Add photos', exact=True)).to_be_disabled()
            await page.get_by_role('checkbox', name='I own the copyright to these photos.').check()
            await page.get_by_role('button', name='Add photos', exact=True).click()
            await expect(page.get_by_role('status')).to_contain_text('1 photo added.')
            await expect(page.locator('.profile-photo')).to_have_count(4)
            await page.reload()
            await expect(page.locator('.profile-photo')).to_have_count(4)
            await page.get_by_role('button', name='Remove test.png', exact=True).click()
            await expect(page.get_by_role('region', name='Confirm removing test.png')).to_be_visible()
            await page.get_by_role('button', name='Keep photo', exact=True).click()
            await expect(page.locator('.profile-photo')).to_have_count(4)
            await page.get_by_role('button', name='Remove test.png', exact=True).click()
            await page.get_by_role('button', name='Remove photo permanently').click()
            await expect(page.locator('.profile-photo')).to_have_count(3)
            await page.get_by_role('button', name='Remove test-face-placeholder-1.png', exact=True).click()
            await page.get_by_role('button', name='Remove photo permanently').click()
            await expect(page.locator('.profile-photo')).to_have_count(2)
            await expect(page.get_by_role('button', name='Remove test-face-placeholder-0.png')).to_be_disabled()
            await page.locator('#profile-files').set_input_files(str(PHOTO))
            await page.get_by_role('button', name='Add photos', exact=True).click()
            await expect(page.get_by_role('alert')).to_contain_text('Exactly one quality-passing face required')
            await expect(page.locator('.profile-photo')).to_have_count(2)
            print('PASS photos: render, add, reload persistence, cancel removal, remove, last-face gate, invalid-face rejection')
            await page.locator('a[href="#settings/whitelist"]').click()
            await page.get_by_role('textbox', name='Site or URL').fill('https://WWW.Example.com/a')
            await expect(page.get_by_text('Will save: example.com')).to_be_visible()
            await page.get_by_role('button', name='Add site', exact=True).click()
            await expect(page.get_by_role('button', name='Remove example.com', exact=True)).to_be_visible()
            await page.reload()
            await expect(page.get_by_role('button', name='Remove example.com', exact=True)).to_be_visible()
            await page.get_by_role('textbox', name='Site or URL').fill('ftp://example.com')
            await page.get_by_role('button', name='Add site', exact=True).click()
            await expect(page.get_by_role('alert')).to_contain_text('Enter a valid domain')
            await page.locator('a[href="#scan/1"]').first.click()
            await page.get_by_role('button', name='More filters', exact=False).click()
            await expect(page.get_by_role('checkbox', name='Show whitelisted (1)')).to_be_visible()
            await page.get_by_role('checkbox', name='Show whitelisted (1)').check()
            await page.keyboard.press('Escape')
            await expect(page.get_by_role('checkbox', name='Select match 1', exact=True)).to_be_disabled()
            await expect(page.get_by_role('checkbox', name='Select match 2', exact=True)).to_be_enabled()
            await page.get_by_role('link', name='Settings', exact=True).click()
            await page.locator('a[href="#settings/whitelist"]').click()
            await page.get_by_role('button', name='Remove example.com', exact=True).click()
            await expect(page.get_by_text('No sites on your whitelist yet.', exact=False)).to_be_visible()
            await page.locator('a[href="#scan/1"]').first.click()
            await expect(page.get_by_role('checkbox', name='Select match 1', exact=True)).to_be_enabled()
            print('PASS whitelist: normalized save, reload persistence, invalid input, subdomain excluded, lookalike domain selectable, removal restores eligibility')
            await page.get_by_role('link', name='Settings', exact=True).click()
            for width in (360, 600, 840, 1440):
                await page.set_viewport_size({'width': width, 'height': 1000})
                assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
            await page.set_viewport_size({'width': 360, 'height': 1000})
            await page.screenshot(path='/tmp/censearch-profile-mobile.png', full_page=True)
            await page.locator('a[href="#settings/whitelist"]').focus()
            await page.keyboard.press('Enter')
            await expect(page.get_by_role('textbox', name='Site or URL')).to_be_visible()
            await page.get_by_role('textbox', name='Site or URL').focus()
            await page.keyboard.type('a' * 63 + '.' + 'b' * 63 + '.example.com')
            await page.keyboard.press('Tab')
            await page.keyboard.press('Enter')
            await expect(page.locator('.domain-list li')).to_have_count(1)
            assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            await page.screenshot(path='/tmp/censearch-whitelist-mobile.png', full_page=True)
            assert not errors, errors
            print('PASS UI: 360/600/840/1440 widths, keyboard whitelist add, long domain, reduced motion, no page errors')
        finally:
            await browser.close()

with profile_fixture() as (base, photo):
    asyncio.run(main(base, photo))
