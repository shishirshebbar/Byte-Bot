"""Phase 03 synthetic fixture browser journey; never uses protected ports."""
import json
import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bytebot.fixtures import SCENARIOS

BASE = os.environ.get('BYTEBOT_WEB_URL', 'http://127.0.0.1:5174')
OUTPUT = Path('.cache/phase03')
OUTPUT.mkdir(parents=True, exist_ok=True)


def create_case(context, scenario, index=0):
    transaction = context.request.get(BASE + '/api/v1/transactions').json()['transactions'][index]
    response = context.request.post(BASE + '/api/v1/investigations', data={'transaction_id': transaction['id']})
    assert response.status == 201
    case = response.json()
    response = context.request.patch(BASE + '/api/v1/investigations/' + case['id'] + '/context',
        data={**SCENARIOS[scenario]['context'], 'expected_revision': 0})
    assert response.status == 200
    return response.json()


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    errors, timings = [], {}
    for scenario, fixture in SCENARIOS.items():
        context = browser.new_context(viewport={'width': 1280, 'height': 900})
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        case = create_case(context, scenario)
        api = '/api/v1/investigations/' + case['id']
        intake = BASE + '/investigations/' + case['id']
        page.goto(intake)
        page.get_by_role('heading', name='Let’s understand what happened').wait_for()
        analyze = page.get_by_role('button', name='Analyze saved information', exact=True)
        if fixture['text']:
            page.get_by_label('Message text', exact=True).fill(fixture['text'])
            expect(analyze).to_be_disabled()
            page.get_by_role('button', name='Save text evidence', exact=True).click()
            page.get_by_text('Evidence saved with credential values redacted.', exact=True).wait_for()
        expect(analyze).to_be_enabled()
        start = time.monotonic()
        analyze.click()
        page.wait_for_url(intake + '/results')
        page.get_by_role('heading', name=fixture['category'], exact=True).wait_for()
        timings[scenario] = round(time.monotonic() - start, 2)
        assert timings[scenario] < 20
        assert page.get_by_text('SYNTHETIC EXTRACTION FIXTURE', exact=True).is_visible()
        assert page.get_by_role('heading', name='Findings and sources', exact=True).is_visible()
        assert page.locator('.finding-reference').count() >= 2
        assert page.get_by_text('This assessment identifies signals', exact=False).is_visible()
        assert page.get_by_text('No match found in the available demo data.', exact=False).is_visible()
        if scenario in ('B', 'C'):
            page.get_by_role('heading', name='The requested UPI ID matches the sender.', exact=False).first.wait_for()
        if scenario == 'A':
            page.get_by_role('heading', name='The requested UPI ID differs from the sender.', exact=False).first.wait_for()
            page.screenshot(path=str(OUTPUT / 'results-desktop.png'), full_page=True)
            page.set_viewport_size({'width': 390, 'height': 844})
            page.screenshot(path=str(OUTPUT / 'results-mobile.png'), full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.get_by_role('link', name='Edit saved context and evidence', exact=False).focus()
            assert page.evaluate('document.activeElement.tagName') == 'A'
        if scenario == 'E':
            page.get_by_role('heading', name='Safety warning', exact=True).wait_for()
        results_url = page.url
        page.reload()
        page.get_by_role('heading', name=fixture['category'], exact=True).wait_for()
        # Browser navigation restores saved intake and the current result.
        page.get_by_role('link', name='Edit saved context and evidence', exact=False).click()
        page.get_by_role('button', name='View current result', exact=True).wait_for()
        page.go_back()
        page.get_by_role('heading', name=fixture['category'], exact=True).wait_for()
        # An external tab changes saved input; a reload must not retrieve stale results.
        current = context.request.get(BASE + api).json()
        context.request.patch(BASE + api + '/context', data={'expected_revision': current['input_revision'], 'already_sent_money': 'yes'})
        page.reload()
        page.get_by_role('heading', name='Analysis needed', exact=True).wait_for()
        assert page.get_by_role('heading', name=fixture['category'], exact=True).count() == 0
        # Foreign session cannot read or enqueue analysis.
        other = browser.new_context()
        foreign = other.new_page()
        foreign.goto(results_url)
        foreign.get_by_text('Resource not found.', exact=True).wait_for()
        denied = other.request.post(BASE + api + '/analyze', data={'expected_revision': 0})
        assert denied.status == 404 and 'findings' not in denied.text()
        other.close()
        context.close()
    # Actual pending/failed status, with an independently supported warning.
    for index, status in ((1, 'Pending'), (2, 'Failed')):
        context = browser.new_context()
        page = context.new_page()
        case = create_case(context, 'E', index)
        api = '/api/v1/investigations/' + case['id']
        response = context.request.post(BASE + api + '/evidence', data={'type': 'message', 'text': SCENARIOS['E']['text'], 'expected_revision': case['input_revision']})
        revision = response.json()['input_revision']
        context.request.post(BASE + api + '/analyze', data={'expected_revision': revision})
        page.goto(BASE + '/investigations/' + case['id'] + '/results')
        page.get_by_role('heading', name='Unable to assess', exact=True).wait_for()
        expect(page.get_by_text(status, exact=True)).to_be_visible()
        page.get_by_role('heading', name='Safety warning', exact=True).wait_for()
        assert page.get_by_text('Do not spend the unexpected funds', exact=False).count() == 0
        context.close()
    # Controlled responses verify progress announcements and failed-run retry UI.
    context = browser.new_context()
    page = context.new_page()
    case = create_case(context, 'D')
    api = '/api/v1/investigations/' + case['id']
    run = context.request.post(BASE + api + '/analyze', data={'expected_revision': case['input_revision']}).json()
    saved = context.request.get(BASE + api).json()
    phase = ['running']
    def progress(route):
        if phase[0] == 'running':
            route.fulfill(json={**saved, 'analysis': {**run, 'state': 'running', 'stage': 'message_analysis'}})
        elif phase[0] == 'failed':
            route.fulfill(json={**saved, 'analysis': {**run, 'state': 'failed', 'error_code': 'analysis_failed'}})
        else:
            route.continue_()
    page.route('**' + api, progress)
    page.goto(BASE + '/investigations/' + case['id'] + '/results')
    page.get_by_role('heading', name='Investigation in progress', exact=True).wait_for()
    expect(page.locator('[role=status]')).to_have_text('Reviewing confirmed evidence')
    phase[0] = 'failed'
    page.get_by_role('button', name='Retry analysis', exact=True).wait_for()
    phase[0] = 'real'
    page.get_by_role('button', name='Retry analysis', exact=True).click()
    page.get_by_role('heading', name='No strong indicators found', exact=True).wait_for()
    context.close()
    assert not errors, errors
    browser.close()
    print('PASS: A–E, saved-only analysis, result reload/navigation, stage progress, retry, invalidation, foreign ownership, pending/failed warnings, keyboard, desktop/mobile; no page errors')
    print('Synthetic fixture Analyze-to-result timings (seconds):', json.dumps(timings))
