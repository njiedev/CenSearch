"""Built frontend → real local API → independent mock sites, with DOM-only checks.

No intercepted API responses, provider calls, screenshots or ground-truth reads.
"""
import argparse
from contextlib import ExitStack
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from playwright.sync_api import expect, sync_playwright
from e2e import ROOT, Recorder, wait_ready
from fixture_input import select_person
from mockweb.run import available, running, stop
from mockweb.seed import photos
from mockweb.seed_round2 import seed_round2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--photos', type=Path, required=True)
    parser.add_argument('--api-port', type=int, default=8590)
    parser.add_argument('--base-port', type=int, default=9411)
    args = parser.parse_args()
    available([args.api_port, *range(args.base_port, args.base_port + 8)])
    source = select_person(args.photos)
    output = ROOT / 'data' / ('app-e2e-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    output.mkdir(parents=True)
    seed_round2(source, output / 'mockweb', args.base_port)
    env = dict(os.environ, LIKENESS_DATA_DIR=str(output / 'backend'),
               MOCK_BASE_PORT=str(args.base_port), ALLOW_PUBLIC_CRAWL='false',
               LIKENESS_ALLOW_EXTERNAL_DELIVERY='false', LIKENESS_DEMO_CLOCK='true',
               LIKENESS_SCHEDULER_POLL='3600', OPENAI_API_KEY='', FACECHECK_API_TOKEN='',
               SERPAPI_API_KEY='', OBJ_ENDPOINT='', OBJ_BUCKET='', OBJ_ACCESS_KEY='', OBJ_SECRET_KEY='',
               LIKENESS_SMTP_RELAY=f'smtp://127.0.0.1:{args.base_port + 7}',
               LIKENESS_RDAP_BOOTSTRAP=f'http://127.0.0.1:{args.base_port + 6}/bootstrap',
               LIKENESS_SEARCH_ENDPOINT=f'http://127.0.0.1:{args.base_port + 5}/report')
    base = f'http://127.0.0.1:{args.api_port}'
    report = {'passed': False, 'provider': 'rule fallback; external services disabled',
              'screenshots': False, 'intercepted_api_responses': False}
    started = time.monotonic()
    try:
        with ExitStack() as stack:
            stack.enter_context(running(output / 'mockweb', args.base_port, output / 'logs'))
            log = stack.enter_context((output / 'api.log').open('w'))
            server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'censearch.api:app',
                '--host', '127.0.0.1', '--port', str(args.api_port)], cwd=ROOT, env=env,
                stdout=log, stderr=subprocess.STDOUT)
            stack.callback(stop, server)
            api = Recorder(base)
            stack.callback(api.client.close)
            wait_ready(api, server)
            for path in ['/', '/signup/', '/app/', '/contact/', '/legal/privacy-policy/']:
                response = api.client.get(path)
                assert response.status_code == 200, (path, response.status_code)
            report['production_routes'] = 'passed'
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                page.set_default_timeout(15000)
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(base + '/signup/?fixture=1')
                page.get_by_label('Name', exact=True).fill('Local fixture operator')
                page.locator('#su-references').set_input_files(str(photos(source / 'reference')[0]))
                page.locator('#su-originals').set_input_files(str(photos(source / 'originals')[0]))
                page.get_by_role('checkbox', name='Use these local test fixtures', exact=False).check()
                page.get_by_role('checkbox', name='Hypothetical fixture ownership', exact=False).check()
                with page.expect_response(lambda r: r.url.endswith('/api/people') and r.request.method == 'POST') as enrollment:
                    page.get_by_role('button', name='Enroll my face').click()
                assert enrollment.value.status == 201, enrollment.value.text()
                expect(page).to_have_url(base + '/app/')
                pid = page.evaluate("JSON.parse(localStorage.getItem('censearch.session')).id")
                assert api.client.get(f'/api/people/{pid}').json()['development_fixture']
                report['browser_enrollment'] = 'passed'
                page.get_by_role('button', name='Start scan', exact=True).click()
                page.get_by_role('radio', name='Name / links', exact=False).check()
                urls = [f'http://127.0.0.1:{args.base_port}/post/0001.html',
                        f'http://127.0.0.1:{args.base_port + 3}/post/0004.html']
                page.get_by_role('textbox', name='Page URLs', exact=False).fill('\n'.join(urls))
                page.get_by_role('checkbox', name='I allow this scan', exact=False).check()
                with page.expect_response(lambda r: r.url.endswith('/api/public-searches') and r.request.method == 'POST') as scan:
                    page.get_by_role('button', name='Start scan', exact=True).click()
                assert scan.value.status == 202, scan.value.text()
                run_id = scan.value.json()['id']
                expect(page.get_by_role('button', name='Select all visible')).to_be_visible(timeout=60000)
                cases = api.client.get(f'/api/cases?person_id={pid}&run_id={run_id}').json()
                assert len(cases) == 2, cases
                report['real_scan_matches'] = len(cases)
                page.get_by_role('button', name='Select all visible').click()
                page.get_by_role('button', name='Review with agent').click()
                for label, value in [('Name', 'Local fixture operator'), ('Email', 'operator@example.test'),
                                     ('Address', 'Local fixture address'), ('Phone', '555-0100'),
                                     ('Signature (type your full name)', 'Local fixture operator')]:
                    page.get_by_role('textbox', name=label, exact=True).fill(value)
                page.get_by_role('checkbox', name='I accept', exact=False).check()
                page.get_by_role('checkbox', name='Review notices before sending', exact=False).check()
                page.get_by_role('button', name='Prepare requests').click()
                expect(page.get_by_role('heading', name='Review every request')).to_be_visible(timeout=60000)
                page.locator('[data-slot=accordion-trigger]').first.click()
                expect(page.get_by_role('heading', name='Exact notice text')).to_be_visible()
                assert not any(api.client.get(f"/api/cases/{row['id']}/workflow").json()['deliveries'] for row in cases)
                report['review_before_send'] = 'passed; zero deliveries before confirmation'
                page.get_by_role('button', name='Send 2 requests', exact=True).click()
                page.get_by_role('region', name='Confirm sending').get_by_role('button', name='Send 2 requests', exact=True).click()
                expect(page.get_by_role('heading', name='Batch complete')).to_be_visible(timeout=60000)
                page.get_by_role('button', name='Back to scan', exact=True).click()
                for row in cases:
                    page.get_by_role('button', name=f"Open match {row['id']}:", exact=False).click()
                    page.get_by_role('button', name='Check removal now').click()
                    follow = page.get_by_role('region', name='Verification and follow-up')
                    expect(follow.get_by_role('status').filter(has_text='Last check:')).to_contain_text('Last check:')
                    page.keyboard.press('Escape')
                workflow = {row['id']: api.client.get(f"/api/cases/{row['id']}/workflow").json() for row in cases}
                assert {value['checks'][-1]['outcome'] for value in workflow.values()} == {'removed', 'still_present'}
                report['removal_verification'] = 'passed; removed and still-present distinguished'
                waiting = next(row for row in cases if workflow[row['id']]['checks'][-1]['outcome'] == 'still_present')
                page.get_by_role('button', name=f"Open match {waiting['id']}:", exact=False).click()
                page.get_by_role('button', name='Advance demo clock by 2 days').click()
                expect(page.get_by_role('button', name='Prepare follow-up request')).to_be_visible()
                page.get_by_label('Your name for this approval').fill('Local fixture operator')
                page.get_by_role('button', name='Prepare follow-up request').click()
                send = page.get_by_role('button', name='Send approved follow-up', exact=True)
                expect(send).to_be_disabled()
                page.get_by_role('checkbox', name='I reviewed this exact follow-up', exact=False).check()
                send.click()
                expect(send).to_have_count(0)
                page.get_by_role('button', name='Check removal now').click()
                expect(page.get_by_role('region', name='Verification and follow-up').get_by_role('status').filter(has_text='Last check:')).to_contain_text('Last check: removed')
                final = api.client.get(f"/api/cases/{waiting['id']}/workflow").json()
                assert [delivery['rung'] for delivery in final['deliveries']] == ['site', 'host']
                report['approved_host_escalation'] = 'passed; removed after host delivery'
                for width in [360, 840, 1440]:
                    page.set_viewport_size({'width': width, 'height': 1000})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                assert not errors, errors
                report['page_errors'] = errors
                report['passed'] = True
    finally:
        report['seconds'] = round(time.monotonic() - started, 2)
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
        print(f'Report: {output / "report.json"}')
    available([args.api_port, *range(args.base_port, args.base_port + 8)])
    print('PASS: all temporary servers stopped')


if __name__ == '__main__':
    main()
