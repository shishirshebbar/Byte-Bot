"""Phase 05 selector/reset acceptance and fresh-reset screenshot rehearsal."""
import json
import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bytebot.fixtures import SCENARIOS
from synthetic_images import scenario_screenshot

BASE = os.environ.get('BYTEBOT_WEB_URL', 'http://127.0.0.1:5174').rstrip('/')
WORKSPACE = BASE + '/workspace'
OUTPUT = Path('.cache/phase05')
OUTPUT.mkdir(parents=True, exist_ok=True)


def history(page):
    page.goto(WORKSPACE)
    expect(page.locator('a.transaction')).to_have_count(8)
    expect(page.get_by_role('button', name='Load / reopen scenario', exact=True)).to_be_enabled()


def reset(page):
    page.once('dialog', lambda dialog: dialog.accept())
    page.get_by_role('button', name='Reset demo', exact=True).click()
    page.get_by_text('Demo reset. Your eight synthetic transactions are restored.', exact=True).wait_for()
    expect(page.locator('a.transaction')).to_have_count(8)


def open_case(page):
    ask = page.get_by_role('button', name='Ask Byte Bot', exact=True)
    ask.focus()
    page.keyboard.press('Enter')
    page.get_by_role('heading', name='Let’s understand what happened', exact=True).wait_for()
    return page.url.rsplit('/', 1)[1]


def analyze(page, category):
    button = page.get_by_role('button', name='Analyze saved information', exact=True)
    expect(button).to_be_enabled()
    button.focus()
    start = time.monotonic()
    page.keyboard.press('Enter')
    page.get_by_role('heading', name=category, exact=True).wait_for()
    elapsed = round(time.monotonic() - start, 2)
    assert elapsed < 20, elapsed
    return elapsed


def tab_to(page, target):
    """Traverse actual tab order instead of assigning programmatic focus."""
    target.wait_for()
    for _ in range(100):
        if target.evaluate('(node) => node === document.activeElement'):
            assert target.evaluate('(node) => getComputedStyle(node).outlineStyle') != 'none'
            return
        page.keyboard.press('Tab')
    raise AssertionError('Action was not reachable in keyboard tab order')


def keyboard_click(page, target):
    tab_to(page, target)
    page.keyboard.press('Enter')


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={'width': 1280, 'height': 900}, accept_downloads=True)
    page = context.new_page()
    page.set_default_timeout(12000)
    errors, timings, cases = [], {}, {}
    page.on('pageerror', lambda e: errors.append(str(e)))
    history(page)
    expect(page.get_by_text('Synthetic fixture mode:', exact=False)).to_be_visible()
    # Native selector, checkbox, and action are reachable using only the keyboard.
    selector = page.get_by_label('Scenario', exact=True)
    selector.focus()
    assert page.evaluate('getComputedStyle(document.activeElement).outlineStyle') != 'none'
    page.keyboard.press('Home')
    expect(selector).to_have_value('A')
    page.keyboard.press('Tab')
    expect(page.get_by_label('Enter evidence manually', exact=False)).to_be_focused()
    page.keyboard.press('Tab')
    expect(page.get_by_role('button', name='Load / reopen scenario')).to_be_focused()
    page.screenshot(path=str(OUTPUT / 'history-desktop.png'), full_page=True)
    page.keyboard.press('Enter')
    page.get_by_role('heading', name='Transaction details', exact=True).wait_for()
    for scenario in 'ABCDE':
        if scenario != 'A':
            history(page)
            page.get_by_label('Scenario', exact=True).select_option(scenario)
            page.get_by_role('button', name='Load / reopen scenario', exact=True).click()
        case_id = open_case(page)
        cases[scenario] = case_id
        fixture = SCENARIOS[scenario]
        if fixture['text']:
            expect(page.get_by_label('Review evidence text', exact=True)).to_have_value(fixture['text'])
        timings[scenario] = analyze(page, fixture['category'])
        expect(page.get_by_text('SYNTHETIC EXTRACTION FIXTURE', exact=True)).to_be_visible()
        assert page.locator('.finding-reference').count() >= 2
        if scenario in ('B', 'C'):
            expect(page.get_by_role('heading', name='The requested UPI ID matches the sender.', exact=False).first).to_be_visible()
        if scenario == 'E':
            expect(page.get_by_role('heading', name='Safety warning', exact=True)).to_be_visible()
        # Reopening must preserve the current completed run.
        current = context.request.get(BASE + '/api/v1/investigations/' + case_id).json()
        loaded = context.request.post(BASE + f'/api/v1/demo/scenarios/{scenario}/load').json()['investigation']
        assert loaded == current
    # Another browser's state survives every reset in the main browser.
    other = browser.new_context()
    other.request.get(BASE + '/api/v1/transactions')
    foreign_case = other.request.post(BASE + '/api/v1/demo/scenarios/C/load').json()['investigation']
    other_state = other.request.get(BASE + '/api/v1/investigations/' + foreign_case['id']).json()
    history(page)
    before = context.request.get(BASE + '/api/v1/transactions').json()
    page.once('dialog', lambda dialog: dialog.dismiss())
    page.get_by_role('button', name='Reset demo', exact=True).click()
    assert context.request.get(BASE + '/api/v1/transactions').json() == before
    # Reset failure preserves the screen/state and permits retry.
    page.route('**/api/v1/demo/reset', lambda route: route.fulfill(status=503, json={'error': {'message': 'Synthetic reset failure.'}}))
    page.once('dialog', lambda dialog: dialog.accept())
    page.get_by_role('button', name='Reset demo', exact=True).click()
    expect(page.get_by_role('alert')).to_have_text('Synthetic reset failure.')
    assert context.request.get(BASE + '/api/v1/transactions').json() == before
    page.unroute('**/api/v1/demo/reset')
    reset(page)
    assert context.request.get(BASE + '/api/v1/incidents').json() == {'incidents': []}
    assert other.request.get(BASE + '/api/v1/investigations/' + foreign_case['id']).json() == other_state
    for case_id in cases.values():
        assert context.request.get(BASE + '/api/v1/investigations/' + case_id).status == 404
    page.goto(WORKSPACE + '/investigations/' + cases['B'])
    page.get_by_role('heading', name='Investigation unavailable', exact=True).wait_for()
    # Fresh-reset four-minute rehearsal with a real CPU OCR screenshot.
    rehearsal_start = time.monotonic()
    history(page)
    page.get_by_label('Scenario', exact=True).select_option('B')
    page.get_by_label('Enter evidence manually', exact=False).check()
    page.get_by_role('button', name='Load / reopen scenario', exact=True).click()
    case_id = open_case(page)
    expect(page.get_by_label('Where did they ask you to send money?')).to_have_value('same_sender')
    expect(page.get_by_label('Review evidence text', exact=True)).to_have_count(0)
    screenshot = scenario_screenshot('B')
    (OUTPUT / 'scenario-b.png').write_bytes(screenshot)
    page.get_by_label('Screenshot (PNG or JPEG', exact=False).set_input_files({'name': 'scenario-b.png', 'mimeType': 'image/png', 'buffer': screenshot})
    page.get_by_role('button', name='Upload and read screenshot', exact=True).click()
    page.get_by_text('Screenshot processed. Review and confirm its text.', exact=True).wait_for(timeout=30000)
    reviewed = page.get_by_label('Review screenshot text', exact=True)
    ocr_text = reviewed.input_value()
    assert '5000' in ocr_text and 'police' in ocr_text.lower() and 'bank' in ocr_text.lower(), ocr_text
    expect(page.get_by_role('button', name='Analyze saved information', exact=True)).to_be_disabled()
    # Human review removes OCR line breaks/corrects identifiers to canonical input.
    reviewed.fill(SCENARIOS['B']['text'])
    page.get_by_role('button', name='Confirm reviewed text', exact=True).click()
    page.get_by_text('Reviewed text confirmed and saved.', exact=True).wait_for()
    timings['B_reviewed_screenshot'] = analyze(page, 'High concern')
    expect(page.get_by_role('heading', name='The requested UPI ID matches the sender.', exact=False).first).to_be_visible()
    page.get_by_role('button', name='Generate / view report', exact=True).click()
    page.get_by_role('button', name='Download text report', exact=True).wait_for()
    report_url = page.url
    with page.expect_download() as info:
        page.get_by_role('button', name='Download text report', exact=True).click()
    target = OUTPUT / info.value.suggested_filename
    info.value.save_as(target)
    downloaded = target.read_text(encoding='utf-8')
    assert 'High concern' in downloaded and '₹5,000.00' in downloaded and SCENARIOS['B']['text'] in downloaded
    page.get_by_role('link', name='My Incidents', exact=True).click()
    page.get_by_label('Case status', exact=True).select_option('Bank Contacted')
    page.get_by_role('button', name='Save case status', exact=True).click()
    page.get_by_text('Case status saved.', exact=True).wait_for()
    page.get_by_role('link', name='View saved report', exact=True).click()
    page.get_by_role('button', name='Download text report', exact=True).wait_for()
    rehearsal_seconds = round(time.monotonic() - rehearsal_start, 2)
    assert rehearsal_seconds < 240
    # Desktop/mobile report and incident controls remain reachable without overflow.
    for route in ('/incidents', '/', '/investigations/' + case_id + '/report'):
        page.set_viewport_size({'width': 390, 'height': 844})
        page.goto(WORKSPACE + ('' if route == '/' else route))
        if route == '/':
            expect(page.get_by_role('button', name='Reset demo', exact=True)).to_be_enabled()
            page.screenshot(path=str(OUTPUT / 'history-mobile.png'), full_page=True)
        elif route == '/incidents':
            expect(page.get_by_label('Case status', exact=True)).to_be_visible()
        else:
            expect(page.get_by_role('button', name='Download text report', exact=True)).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.keyboard.press('Tab')
        assert page.evaluate('document.activeElement.tagName') in ('A', 'BUTTON', 'SELECT', 'INPUT')
    report_tab = context.new_page()
    report_tab.goto(report_url)
    report_tab.get_by_role('button', name='Download text report', exact=True).wait_for()
    history(page)
    reset(page)
    report_tab.evaluate('window.dispatchEvent(new Event("focus"))')
    report_tab.get_by_role('heading', name='Report unavailable', exact=True).wait_for()
    expect(report_tab.get_by_role('button', name='Download text report', exact=True)).to_have_count(0)
    assert target.read_text(encoding='utf-8') == downloaded
    # Repeat reset, and recover from a scenario-loading error.
    reset(page)
    page.get_by_label('Scenario', exact=True).select_option('A')
    page.route('**/api/v1/demo/scenarios/A/load', lambda route: route.fulfill(status=503, json={'error': {'message': 'Synthetic load failure.'}}))
    page.get_by_role('button', name='Load / reopen scenario', exact=True).click()
    expect(page.get_by_role('alert')).to_have_text('Synthetic load failure.')
    page.unroute('**/api/v1/demo/scenarios/A/load')
    page.get_by_role('button', name='Load / reopen scenario', exact=True).click()
    page.get_by_role('button', name='Ask Byte Bot', exact=True).wait_for()
    # Catalog failure does not create a case and has a working retry.
    page.route('**/api/v1/demo/scenarios', lambda route: route.fulfill(status=503, json={'error': {'message': 'Synthetic catalog failure.'}}))
    page.goto(WORKSPACE)
    page.get_by_role('button', name='Retry scenarios', exact=True).wait_for()
    page.unroute('**/api/v1/demo/scenarios')
    page.get_by_role('button', name='Retry scenarios', exact=True).click()
    expect(page.get_by_label('Scenario', exact=True)).to_be_visible()
    # Entire mobile D journey follows real tab order, with no mouse or focus API.
    tab_to(page, page.get_by_label('Scenario', exact=True))
    page.keyboard.press('Home')
    for _ in range(3):
        page.keyboard.press('ArrowDown')
    expect(page.get_by_label('Scenario', exact=True)).to_have_value('D')
    keyboard_click(page, page.get_by_role('button', name='Load / reopen scenario', exact=True))
    keyboard_click(page, page.get_by_role('button', name='Ask Byte Bot', exact=True))
    keyboard_click(page, page.get_by_role('button', name='Analyze saved information', exact=True))
    page.get_by_role('heading', name='No strong indicators found', exact=True).wait_for()
    keyboard_click(page, page.get_by_role('button', name='Generate / view report', exact=True))
    tab_to(page, page.get_by_role('button', name='Download text report', exact=True))
    with page.expect_download() as keyboard_download:
        page.keyboard.press('Enter')
    keyboard_download.value.save_as(OUTPUT / 'keyboard-report.txt')
    keyboard_click(page, page.get_by_role('link', name='My Incidents', exact=True))
    # A from the error-retry test also exists; D is the only completed case.
    card = page.get_by_role('article', name='Incident from Scenario D sender', exact=True)
    tab_to(page, card.get_by_label('Case status', exact=True))
    page.keyboard.press('ArrowDown')
    expect(card.get_by_label('Case status', exact=True)).to_have_value('Bank Contacted')
    keyboard_click(page, card.get_by_role('button', name='Save case status', exact=True))
    card.get_by_text('Case status saved.', exact=True).wait_for()
    keyboard_click(page, card.get_by_role('link', name='View saved report', exact=True))
    page.get_by_role('button', name='Download text report', exact=True).wait_for()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert not errors, errors
    (OUTPUT / 'timings.json').write_text(json.dumps({'provider_mode': 'fixture', 'analysis_seconds': timings,
        'automated_rehearsal_seconds': rehearsal_seconds, 'desktop': '1280x900', 'mobile': '390x844'}, indent=2) + '\n')
    other.close()
    context.close()
    browser.close()
    print('PASS: selector A–E, keyboard/focus, saved-case reuse, reset cancel/failure/retry/repeat/isolation, old URLs/report invalidation, real screenshot review, report download, follow-up, mobile, catalog/load errors; no page errors')
    print('Fixture analysis timings:', json.dumps(timings))
    print(f'Fresh-reset automated screenshot rehearsal: {rehearsal_seconds}s (includes CPU OCR; excludes human narration)')
