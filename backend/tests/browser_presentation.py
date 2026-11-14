"""Customer phone and judge panel regression. Requires fixture extraction; synthetic data only."""
import json
import os
from pathlib import Path
from time import perf_counter
from playwright.sync_api import expect, sync_playwright
from synthetic_images import screenshot

ORIGIN = os.environ.get('BYTEBOT_WEB_URL', 'http://127.0.0.1:5174').rstrip('/')
ARTIFACTS = Path('.cache/simple-presentation')
ARTIFACTS.mkdir(parents=True, exist_ok=True)
ANALYZE = 'Analyze & prepare report'


def surfaces(page):
    return page.get_by_role('main', name='Phone screen'), page.get_by_role('complementary', name='Judge backend view')


def setup(page):
    panel = surfaces(page)[1]
    summary = panel.locator('.judge-setup > summary')
    if not panel.locator('.judge-setup').evaluate('(e) => e.open'):
        summary.click()
    expect(panel.get_by_role('button', name='Load / reopen scenario')).to_be_enabled()
    return panel.get_by_role('region', name='Demo scenarios')


def load_case(page, key='B'):
    controls = setup(page)
    controls.get_by_label('Scenario').select_option(key)
    controls.get_by_role('button', name='Load / reopen scenario').click()
    phone = surfaces(page)[0]
    expect(phone.get_by_role('heading', name='Transaction details')).to_be_visible()
    phone.get_by_role('button', name='Ask Byte Bot').click()
    expect(phone.get_by_role('region', name='Case review')).to_be_visible()
    return phone


def keyboard_activate(page, target):
    for _ in range(100):
        if target.evaluate('(e) => e === document.activeElement'):
            page.keyboard.press('Enter')
            return
        page.keyboard.press('Tab')
    expect(target).to_be_focused()


def rehearse(browser):
    context = browser.new_context(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('dialog', lambda dialog: dialog.accept())
    page.goto(ORIGIN)
    phone, panel = surfaces(page)
    expect(phone.get_by_role('heading', name="Let's make it simple.")).to_be_visible()
    expect(panel.get_by_text('The customer is browsing')).to_be_visible()
    expect(page.get_by_role('tab')).to_have_count(0)
    expect(phone.get_by_text('Demo controls')).to_have_count(0)
    phone.get_by_role('button', name='Scan & Pay', exact=True).click()
    expect(phone.get_by_role('status')).to_contain_text('No money can be moved')
    phone.get_by_role('button', name='Dismiss prototype notice').click()
    page.screenshot(path=ARTIFACTS / 'home-1440.png')
    phone.get_by_role('link', name='Balance & History', exact=True).click()
    expect(phone.get_by_role('heading', name='Balance & History')).to_be_visible()
    phone.get_by_label('Search transactions').fill('Meera')
    expect(phone.locator('.tx-row')).to_have_count(1)
    phone.locator('.tx-row').click()
    expect(phone.get_by_text('Funds are not confirmed as received.', exact=False)).to_be_visible()
    page.go_back()
    expect(phone.get_by_role('heading', name='Balance & History')).to_be_visible()

    controls = setup(page)
    controls.get_by_role('button', name='Reset demo').click()
    expect(phone.get_by_role('heading', name="Let's make it simple.")).to_be_visible()
    phone = load_case(page)
    controls = setup(page)
    load = controls.get_by_role('button', name='Load / reopen scenario')
    reset = controls.get_by_role('button', name='Reset demo')
    expect(panel.get_by_text('Ready for customer review', exact=True)).to_be_visible()
    expect(phone.get_by_role('textbox', name='Review evidence text')).to_have_count(0)
    phone.get_by_role('button', name='Review or edit answers', exact=True).click()
    question = phone.get_by_role('region', name='Payment context')
    question.get_by_role('button', name='Yes', exact=True).click()
    expect(load).to_be_disabled()
    question.get_by_role('button', name='No', exact=True).click()
    question.get_by_role('button', name='Next', exact=True).click()
    question.get_by_role('button', name='Yes', exact=True).click()
    for _ in range(5):
        question.get_by_role('button', name='Next', exact=True).click()
    question.get_by_role('button', name='Save answers', exact=True).click()
    expect(phone.get_by_text('Answers saved.', exact=True)).to_be_visible()
    expect(load).to_be_enabled()
    expect(question.get_by_role('heading', name='Your answers')).to_be_visible()
    case_id = page.url.rsplit('/', 1)[-1]
    saved = page.request.get(f'{ORIGIN}/api/v1/investigations/{case_id}').json()
    assert saved['context']['expected_payment'] == 'no' and saved['context']['knows_sender'] == 'yes'
    page.screenshot(path=ARTIFACTS / 'review-1440.png')
    started = perf_counter()
    phone.get_by_role('button', name=ANALYZE).click()
    expect(phone.get_by_role('heading', name='High concern')).to_be_visible(timeout=20000)
    expect(phone.get_by_role('button', name='Download report', exact=True)).to_be_enabled()
    seconds = round(perf_counter() - started, 2)
    assert seconds < 20
    expect(panel.get_by_text('Analysis complete', exact=True)).to_be_visible()
    trace = page.request.get(f'{ORIGIN}/api/v1/investigations/{case_id}').json()['analysis']['agent']['trace']
    expect(panel.get_by_role('list', name='Backend decision timeline').get_by_role('listitem')).to_have_count(len(trace))
    expect(panel.get_by_text('Policy check', exact=True)).to_be_visible()
    assert panel.locator('time').count() == len(trace)
    expect(phone.get_by_text('foundation-rules', exact=False)).to_have_count(0)
    consent = phone.get_by_role('button', name='Approve: Place a dispute hold on the unexpected credit')
    consent.click()
    expect(panel.get_by_text('SIM-HOLD-', exact=False)).to_be_visible()
    expect(phone.get_by_text('SIM-HOLD-', exact=False)).to_have_count(0)
    with page.expect_download() as downloaded:
        phone.get_by_role('button', name='Download report', exact=True).click()
    report = downloaded.value.path().read_text(encoding='utf-8')
    assert 'High concern' in report and 'Do not contact your bank.' in report
    phone.get_by_label('Case status').select_option('Bank Contacted')
    expect(reset).to_be_disabled()
    phone.get_by_role('button', name='Save case status').click()
    expect(panel.get_by_text('Bank Contacted', exact=True)).to_be_visible()
    result_url = page.url
    phone.locator('.back').scroll_into_view_if_needed()
    page.screenshot(path=ARTIFACTS / 'result-1440.png')
    phone.get_by_role('link', name='View report', exact=True).click()
    expect(phone.get_by_role('button', name='Download text report')).to_be_enabled()
    report_url = page.url
    page.reload()
    expect(panel.get_by_text('Ready to download', exact=True)).to_be_visible()
    page.get_by_role('navigation', name='Phone navigation').get_by_role('link', name='Byte Bot cases').click()
    expect(phone.get_by_text('Saved case status: Bank Contacted', exact=True)).to_be_visible()
    phone.get_by_role('link', name='View saved report').click()
    expect(phone.get_by_role('button', name='Download text report')).to_be_enabled()
    other = browser.new_context()
    foreign = other.new_page()
    foreign.goto(report_url)
    expect(foreign.get_by_role('heading', name='Report unavailable')).to_be_visible()
    other.close()
    panel.locator('.judge-details > summary').click()
    panel.get_by_role('link', name='Review source evidence').first.click()
    expect(phone.get_by_label('Review evidence text')).to_be_visible()
    assert page.evaluate("document.activeElement.id.startsWith('evidence-')")
    setup(page)
    phone.get_by_label('Review evidence text').fill('Please return INR 5000 to aarav.demo@upi.')
    expect(load).to_be_disabled()
    phone.get_by_role('button', name='Save corrected text').click()
    expect(panel.get_by_text('Ready for customer review', exact=True)).to_be_visible()
    expect(panel.get_by_text('Not requested', exact=True)).to_be_visible()
    page.goto(result_url)
    expect(phone.get_by_role('heading', name='Analysis needed')).to_be_visible()
    expect(phone.get_by_role('button', name='Download report', exact=True)).to_have_count(0)
    controls = setup(page)
    page.route('**/api/v1/demo/reset', lambda route: route.fulfill(status=503, json={'error': {'message': 'Temporary reset failure.'}}))
    url = page.url
    controls.get_by_role('button', name='Reset demo').click()
    expect(controls.get_by_role('alert')).to_have_text('Temporary reset failure.')
    assert page.url == url
    page.unroute('**/api/v1/demo/reset')
    controls.get_by_role('button', name='Reset demo').click()
    expect(phone.get_by_role('heading', name="Let's make it simple.")).to_be_visible()
    expect(panel.get_by_text('The customer is browsing')).to_be_visible()
    controls.get_by_label('Scenario').select_option('claim')
    controls.get_by_role('button', name='Load / reopen scenario').click()
    phone.get_by_role('button', name='Check my payments').click()
    expect(panel.get_by_text('Payment claim checked', exact=True)).to_be_visible()
    page.get_by_role('navigation', name='Phone navigation').get_by_role('link', name='Home', exact=True).click()
    expect(panel.get_by_text('The customer is browsing')).to_be_visible()
    assert not errors, errors
    context.close()
    return {'result_and_report_seconds': seconds}


def sizes(browser):
    for width, height in ((1280, 720), (390, 844), (320, 740)):
        context = browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce')
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(ORIGIN)
        phone, panel = surfaces(page)
        expect(phone.get_by_role('heading', name="Let's make it simple.")).to_be_visible()
        page.screenshot(path=ARTIFACTS / f'home-{width}.png', full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert phone.evaluate('(e) => e.scrollWidth <= e.clientWidth')
        if width >= 1024:
            assert page.evaluate('document.documentElement.scrollHeight <= innerHeight')
        if width == 390:
            keyboard_activate(page, panel.locator('.judge-setup > summary'))
            expect(panel.locator('.judge-setup')).to_have_attribute('open', '')
            keyboard_activate(page, panel.get_by_role('button', name='Load / reopen scenario'))
            keyboard_activate(page, phone.get_by_role('button', name='Ask Byte Bot'))
            keyboard_activate(page, phone.get_by_role('button', name=ANALYZE))
        else:
            load_case(page)
            phone.get_by_role('button', name=ANALYZE).click()
        expect(phone.get_by_role('heading', name='High concern')).to_be_visible(timeout=20000)
        phone.locator('.back').scroll_into_view_if_needed()
        panel.locator('.judge-case').scroll_into_view_if_needed()
        page.screenshot(path=ARTIFACTS / f'result-{width}.png', full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert phone.evaluate('(e) => e.scrollWidth <= e.clientWidth')
        assert not errors, errors
        context.close()


def report_retry(browser):
    context = browser.new_context()
    page = context.new_page()
    page.goto(ORIGIN)
    phone = load_case(page)
    def hide_report(route):
        response = route.fetch()
        body = response.json()
        if (body.get('analysis') or {}).get('state') == 'complete':
            body['analysis']['report_id'] = None
        route.fulfill(response=response, json=body)
    pattern = '**/api/v1/investigations/*'
    page.route(pattern, hide_report)
    phone.get_by_role('button', name=ANALYZE).click()
    expect(phone.get_by_role('button', name='Retry report')).to_be_visible(timeout=20000)
    expect(surfaces(page)[1].get_by_text('Needs retry', exact=True)).to_be_visible()
    page.unroute(pattern)
    phone.get_by_role('button', name='Retry report').click()
    expect(phone.get_by_role('button', name='Download report', exact=True)).to_be_enabled()
    context.close()


def attachments(browser):
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    page.goto(ORIGIN)
    controls = setup(page)
    controls.get_by_label('Enter evidence manually', exact=False).check()
    phone = load_case(page)
    phone.get_by_role('button', name='Add evidence', exact=True).click()
    expect(phone.get_by_label('Evidence type', exact=True)).to_have_count(1)
    assert not phone.get_by_label('Evidence type', exact=True).is_visible()
    phone.get_by_label('Message text', exact=True).fill('Please return INR 5000 today.')
    phone.get_by_role('group', name='Attachment type').get_by_role('button', name='Call summary', exact=True).click()
    expect(phone.get_by_label('What did the caller say?', exact=True)).to_have_value('Please return INR 5000 today.')
    phone.get_by_role('button', name='Save text evidence', exact=True).click()
    expect(phone.get_by_role('heading', name='Typed call summary', exact=True)).to_be_visible()
    phone.get_by_role('group', name='Attachment type').get_by_role('button', name='Screenshot', exact=True).click()
    assert not phone.get_by_label('What did the caller say?', exact=True).is_visible()
    phone.get_by_label('Screenshot (PNG or JPEG', exact=False).set_input_files({'name': 'synthetic-blank.png', 'mimeType': 'image/png', 'buffer': screenshot(readable=False)})
    expect(phone.get_by_alt_text('Browser-local screenshot preview')).to_be_visible()
    phone.get_by_role('button', name='Upload and read screenshot').click()
    expect(phone.get_by_text('No readable text was found.', exact=True)).to_be_visible(timeout=60000)
    expect(phone.get_by_role('button', name=ANALYZE)).to_be_disabled()
    phone.get_by_label('Review screenshot text', exact=True).fill('Please return INR 5000 today.')
    phone.get_by_role('button', name='Confirm reviewed text', exact=True).click()
    expect(phone.get_by_role('button', name=ANALYZE)).to_be_enabled()
    page.screenshot(path=ARTIFACTS / 'evidence-390.png', full_page=True)
    phone.get_by_role('button', name='Close preview', exact=True).click()
    expect(phone.get_by_alt_text('Browser-local screenshot preview')).to_have_count(0)
    context.close()


with sync_playwright() as p:
    browser = p.chromium.launch()
    timing = rehearse(browser)
    sizes(browser)
    report_retry(browser)
    attachments(browser)
    browser.close()
    (ARTIFACTS / 'timing.json').write_text(json.dumps(timing, indent=2), encoding='utf-8')
    print(f'PASS: Paytm home, guided intake, judge timeline, consent, report, status, ownership, invalidation, reset, claim, keyboard and layouts; {timing}')
