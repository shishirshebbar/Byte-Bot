import json
import os
from pathlib import Path
from time import perf_counter

from playwright.sync_api import expect, sync_playwright

ORIGIN = os.environ.get('BYTEBOT_WEB_URL', 'http://127.0.0.1:5174').rstrip('/')
ARTIFACTS = Path('.cache/paytm-presentation')
ARTIFACTS.mkdir(parents=True, exist_ok=True)
ANALYZE = 'Analyze & prepare report'


def rehearse(browser):
    context = browser.new_context(viewport={'width': 1280, 'height': 720}, accept_downloads=True)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('dialog', lambda dialog: dialog.accept())
    page.goto(ORIGIN)
    phone = page.get_by_role('main', name='Phone screen')
    panel = page.get_by_role('complementary', name='Live investigation explanation')
    controls = panel.get_by_role('region', name='Demo scenarios')
    reset = controls.get_by_role('button', name='Reset demo')
    load = controls.get_by_role('button', name='Load / reopen scenario')
    workflow = panel.get_by_role('tabpanel', name='Workflow')
    findings = panel.get_by_role('tabpanel', name='Findings')
    outcome = panel.get_by_role('tabpanel', name='Outcome')

    expect(controls.get_by_label('Scenario')).to_have_value('B')
    expect(reset).to_be_enabled()
    page.screenshot(path=ARTIFACTS / 'desktop-1280.png')
    reset.click()
    expect(controls.get_by_role('status')).to_contain_text('Demo reset')
    expect(phone.get_by_role('link', name='Meera Rao', exact=False)).to_be_visible()
    start = perf_counter()
    load.click()
    expect(phone.get_by_role('heading', name='Transaction details')).to_be_visible()
    expect(phone.get_by_text('₹5,000.00', exact=True)).to_be_visible()
    expect(workflow.get_by_role('status')).to_have_text('Case ready for review')
    page.get_by_role('button', name='Ask Byte Bot').click()
    expect(phone.get_by_role('region', name='Case review')).to_contain_text('Please return INR 5000')
    analyze = phone.get_by_role('button', name=ANALYZE)
    expect(analyze).to_be_enabled()
    analysis_start = perf_counter()
    analyze.click()
    expect(phone.get_by_role('heading', name='High concern')).to_be_visible(timeout=20_000)
    analysis_seconds = perf_counter() - analysis_start
    direct_download = phone.get_by_role('button', name='Download report', exact=True)
    expect(direct_download).to_be_enabled(timeout=20_000)
    ready_seconds = perf_counter() - analysis_start
    with page.expect_download() as download:
        direct_download.click()
    report = download.value.path().read_text(encoding='utf-8')
    assert 'High concern' in report and '₹5,000.00' in report and 'Do not contact your bank.' in report
    phone.get_by_label('Case status').select_option('Bank Contacted')
    expect(reset).to_be_disabled()
    expect(phone.get_by_text('Saved case status: Open', exact=True)).to_be_visible()
    phone.get_by_role('button', name='Save case status').click()
    expect(phone.get_by_text('Saved case status: Bank Contacted', exact=True)).to_be_visible()
    finished_seconds = perf_counter() - analysis_start
    expect(workflow.get_by_role('status')).to_have_text('Analysis complete')
    expect(workflow.get_by_text('Complete', exact=True)).to_have_count(4)
    results_url = page.url
    panel.get_by_role('tab', name='Workflow').focus()
    page.keyboard.press('ArrowRight')
    expect(findings).to_be_visible()
    expect(findings.get_by_role('heading', name='High concern')).to_be_visible()
    expect(findings.get_by_text('Do not contact your bank', exact=True)).to_be_visible()
    expect(findings.get_by_text('I will call the police', exact=True)).to_be_visible()
    expect(findings.get_by_role('link', name='Review source evidence').first).to_be_visible()
    page.screenshot(path=ARTIFACTS / 'findings.png')

    phone.get_by_role('link', name='View report', exact=True).click()
    download_action = phone.get_by_role('button', name='Download text report')
    expect(download_action).to_be_enabled()
    report_url = page.url
    panel.get_by_role('tab', name='Outcome').click()
    expect(outcome.get_by_text('Ready to download')).to_be_visible()
    expect(outcome.get_by_text('1 item')).to_be_visible()
    page.get_by_role('link', name='My Incidents', exact=True).click()
    expect(phone.get_by_text('Saved case status: Bank Contacted', exact=True)).to_be_visible()
    expect(outcome.get_by_text('Bank Contacted', exact=True)).to_be_visible()
    phone.get_by_role('link', name='View saved report').click()
    expect(download_action).to_be_visible()
    rehearsal_seconds = perf_counter() - start
    assert rehearsal_seconds < 240 and ready_seconds < 20

    page.reload()
    expect(download_action).to_be_visible()
    panel.get_by_role('tab', name='Outcome').click()
    expect(outcome.get_by_text('Bank Contacted', exact=True)).to_be_visible()
    expect(outcome.get_by_text('Ready to download')).to_be_visible()
    page.goto(results_url)
    panel.get_by_role('tab', name='Outcome').click()
    expect(outcome.get_by_text('Ready to download')).to_be_visible()
    page.goto(report_url)
    expect(download_action).to_be_visible()

    other = browser.new_context()
    foreign = other.new_page()
    foreign.goto(report_url)
    expect(foreign.get_by_role('heading', name='Report unavailable')).to_be_visible()
    expect(foreign.get_by_role('button', name='Download text report')).to_have_count(0)
    other.close()

    panel.get_by_role('tab', name='Findings').click()
    source = findings.get_by_role('link', name='Review source evidence').first
    source.click()
    expect(phone.get_by_role('region', name='Saved evidence')).to_be_visible()
    assert page.evaluate("document.activeElement.id.startsWith('evidence-')")
    evidence = phone.get_by_label('Review evidence text')
    evidence.fill('Please return INR 5000 to aarav.demo@upi.')
    expect(load).to_be_disabled()
    expect(reset).to_be_disabled()
    phone.get_by_role('button', name='Save corrected text').click()
    expect(load).to_be_enabled()
    expect(findings.get_by_text('Findings appear after Byte Bot')).to_be_visible()
    panel.get_by_role('tab', name='Outcome').click()
    expect(outcome.get_by_text('Awaiting generation')).to_be_visible()
    expect(outcome.get_by_text('Bank Contacted', exact=True)).to_be_visible()
    page.go_back()
    expect(phone.get_by_role('heading', name='Analysis needed')).to_be_visible()
    expect(direct_download).to_have_count(0)

    page.route('**/api/v1/demo/reset', lambda route: route.fulfill(
        status=503, json={'error': {'message': 'Temporary reset failure.'}},
    ))
    url = page.url
    reset.click()
    expect(controls.get_by_role('alert')).to_have_text('Temporary reset failure.')
    assert page.url == url
    expect(outcome.get_by_text('Bank Contacted', exact=True)).to_be_visible()
    page.unroute('**/api/v1/demo/reset')
    for _ in range(2):
        reset.click()
        expect(controls.get_by_role('status')).to_contain_text('Demo reset')
        expect(phone.get_by_role('heading', name='Transaction history')).to_be_visible()
        expect(load).to_be_enabled()
        expect(workflow.get_by_role('status')).to_have_text('Waiting for a case')
    assert not errors, errors
    context.close()
    return {'actions': 4, 'result_seconds': round(analysis_seconds, 2), 'report_ready_seconds': round(ready_seconds, 2),
            'finished_seconds': round(finished_seconds, 2), 'automated_rehearsal_seconds': round(rehearsal_seconds, 2)}


def keyboard_reach(page, target):
    for _ in range(30):
        if target.evaluate('(element) => element === document.activeElement'):
            return
        page.keyboard.press('Tab')
    expect(target).to_be_focused()


def keyboard_activate(page, target):
    keyboard_reach(page, target)
    page.keyboard.press('Enter')


def check_sizes(browser):
    for width, height in ((1440, 900), (390, 844), (320, 740)):
        context = browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce', accept_downloads=True)
        page = context.new_page()
        page.goto(ORIGIN)
        phone = page.get_by_role('main', name='Phone screen')
        load = page.get_by_role('button', name='Load / reopen scenario')
        expect(load).to_be_enabled()
        page.screenshot(path=ARTIFACTS / f'layout-{width}.png', full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert phone.evaluate('(element) => element.scrollWidth <= element.clientWidth')
        if width < 1024:
            page.keyboard.press('Tab')
            page.keyboard.press('Tab')
            expect(page.locator('.jump-controls')).to_be_focused()
            page.keyboard.press('Enter')
            assert page.evaluate('location.hash') == '#presenter-controls'
        if width == 390:
            keyboard_activate(page, load)
        else:
            load.click()
        expect(phone.get_by_role('button', name='Ask Byte Bot')).to_be_visible()
        assert phone.evaluate('(element) => element.scrollWidth <= element.clientWidth')
        if width == 390:
            keyboard_activate(page, phone.get_by_role('button', name='Ask Byte Bot'))
            analyze = phone.get_by_role('button', name=ANALYZE)
            expect(analyze).to_be_enabled()
            keyboard_activate(page, analyze)
        else:
            phone.get_by_role('button', name='Ask Byte Bot').click()
            phone.get_by_role('button', name=ANALYZE).click()
        expect(phone.get_by_role('heading', name='High concern')).to_be_visible(timeout=20_000)
        download = phone.get_by_role('button', name='Download report', exact=True)
        expect(download).to_be_enabled()
        if width == 390:
            with page.expect_download():
                keyboard_activate(page, download)
            keyboard_reach(page, phone.get_by_label('Case status'))
            page.keyboard.press('Home')
            page.keyboard.press('ArrowDown')
            page.keyboard.press('Tab')
            expect(phone.get_by_label('Case status')).to_have_value('Bank Contacted')
            keyboard_activate(page, phone.get_by_role('button', name='Save case status'))
            expect(phone.get_by_text('Saved case status: Bank Contacted', exact=True)).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert phone.evaluate('(element) => element.scrollWidth <= element.clientWidth')
        download.scroll_into_view_if_needed()
        page.screenshot(path=ARTIFACTS / f'result-{width}.png')
        context.close()


def check_report_retry(browser):
    context = browser.new_context()
    page = context.new_page()
    page.goto(ORIGIN)
    phone = page.get_by_role('main', name='Phone screen')
    page.get_by_role('button', name='Load / reopen scenario').click()
    phone.get_by_role('button', name='Ask Byte Bot').click()

    def hide_automatic_report(route):
        response = route.fetch()
        body = response.json()
        if (body.get('analysis') or {}).get('state') == 'complete':
            body['analysis']['report_id'] = None
        route.fulfill(response=response, json=body)

    get_case = '**/api/v1/investigations/*'
    page.route(get_case, hide_automatic_report)
    phone.get_by_role('button', name=ANALYZE).click()
    expect(phone.get_by_role('heading', name='High concern')).to_be_visible(timeout=20_000)
    page.get_by_role('tab', name='Outcome').click()
    panel = page.get_by_role('tabpanel', name='Outcome')
    expect(panel.get_by_text('Report needs retry')).to_be_visible()
    expect(phone.get_by_role('button', name='Download report', exact=True)).to_have_count(0)
    page.unroute(get_case)
    retry = phone.get_by_role('button', name='Retry report')
    retry.click()
    expect(phone.get_by_role('button', name='Download report', exact=True)).to_be_enabled()
    expect(panel.get_by_text('Ready to download')).to_be_visible()
    context.close()


with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    timings = [rehearse(browser) for _ in range(3)]
    check_sizes(browser)
    check_report_retry(browser)
    browser.close()
    (ARTIFACTS / 'timings.json').write_text(json.dumps(timings, indent=2) + '\n', encoding='utf-8')
    print(f'PASS: live Scenario B, report, follow-up, evidence links, ownership, invalidation, reset, layouts; {timings}')
