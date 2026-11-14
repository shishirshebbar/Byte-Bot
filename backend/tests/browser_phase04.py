"""Phase 04 browser acceptance with synthetic evidence and explicit fixture API."""
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bytebot.fixtures import SCENARIOS

BASE = os.environ.get('BYTEBOT_WEB_URL', 'http://127.0.0.1:5174').rstrip('/')
WORKSPACE = BASE + '/workspace'
OUTPUT = Path('.cache/phase04')
OUTPUT.mkdir(parents=True, exist_ok=True)


def create(context, scenario='A', index=0):
    transaction = context.request.get(BASE + '/api/v1/transactions').json()['transactions'][index]
    case = context.request.post(BASE + '/api/v1/investigations', data={'transaction_id': transaction['id']}).json()
    case = context.request.patch(BASE + '/api/v1/investigations/' + case['id'] + '/context',
        data={**SCENARIOS[scenario]['context'], 'expected_revision': case['input_revision']}).json()
    if SCENARIOS[scenario]['text']:
        response = context.request.post(BASE + '/api/v1/investigations/' + case['id'] + '/evidence',
            data={'type': 'message', 'text': SCENARIOS[scenario]['text'], 'expected_revision': case['input_revision']})
        assert response.status == 201
    return context.request.get(BASE + '/api/v1/investigations/' + case['id']).json()


def analyze(page, case, category):
    page.goto(WORKSPACE + '/investigations/' + case['id'])
    page.get_by_role('button', name='Analyze saved information', exact=True).click()
    page.get_by_role('heading', name=category, exact=True).wait_for()
    page.get_by_role('button', name='Generate / view report', exact=True).click()
    page.wait_for_url(WORKSPACE + '/investigations/' + case['id'] + '/report')
    page.get_by_role('button', name='Download text report', exact=True).wait_for()


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    errors = []
    context = browser.new_context(viewport={'width': 1280, 'height': 900}, accept_downloads=True)
    page = context.new_page()
    page.on('pageerror', lambda e: errors.append(str(e)))
    # Empty list for an initialized session; no implicit investigation or report creation.
    context.request.get(BASE + '/api/v1/transactions')
    page.goto(WORKSPACE + '/incidents')
    page.get_by_text('No investigations yet.', exact=False).wait_for()
    case = create(context)
    api = BASE + '/api/v1/investigations/' + case['id']
    report_url = WORKSPACE + '/investigations/' + case['id'] + '/report'
    page.goto(report_url)
    page.get_by_role('heading', name='Analysis needed', exact=True).wait_for()
    analyze(page, case, 'Needs verification')
    snapshot = context.request.get(api + '/report').json()
    for heading in ('Transaction facts', 'User statements', 'Confirmed redacted evidence',
                    'Validated extracted signals', 'Findings and provenance', 'Unknowns and limitations', 'Recommended next steps'):
        expect(page.get_by_role('heading', name=heading, exact=True)).to_be_visible()
    expect(page.get_by_text(snapshot['id'], exact=False).first).to_be_visible()
    expect(page.get_by_text('SYNTHETIC EXTRACTION FIXTURE', exact=True)).to_be_visible()
    with page.expect_download() as info:
        page.get_by_role('button', name='Download text report', exact=True).click()
    download = info.value
    assert download.suggested_filename == f'bytebot-report-{snapshot["id"]}.txt'
    target = OUTPUT / download.suggested_filename
    download.save_as(target)
    text = target.read_text(encoding='utf-8')
    for value in ('₹5,000.00', snapshot['id'], snapshot['generated_at'], case['transaction']['reference'],
                  SCENARIOS['A']['text'], snapshot['assessment']['category'], snapshot['assessment']['recommendations'][0]):
        assert value in text
    for finding in snapshot['assessment']['findings']:
        assert finding['source'] in text and finding['reference'] in text and finding['text'] in text
    page.reload()
    page.get_by_role('button', name='Download text report', exact=True).wait_for()
    assert context.request.get(api + '/report').json() == snapshot
    page.screenshot(path=str(OUTPUT / 'report-desktop.png'), full_page=True)
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.get_by_role('button', name='Download text report', exact=True).focus()
    expect(page.get_by_role('button', name='Download text report', exact=True)).to_be_focused()
    page.screenshot(path=str(OUTPUT / 'report-mobile.png'), full_page=True)
    # Retrieval failures show a retry path without retaining an old snapshot.
    def unavailable(route):
        route.fulfill(status=503, content_type='application/json', body='{"error":{"code":"database_unavailable","message":"Temporarily unavailable."}}')
    page.route('**/api/v1/investigations/*/report', unavailable)
    page.reload()
    page.get_by_text('Temporarily unavailable.', exact=True).wait_for()
    assert page.get_by_text(snapshot['id'], exact=False).count() == 0
    page.unroute('**/api/v1/investigations/*/report', unavailable)
    page.get_by_role('button', name='Reload report', exact=True).click()
    page.get_by_role('button', name='Download text report', exact=True).wait_for()
    page.get_by_role('link', name='My Incidents', exact=True).click()
    page.get_by_role('heading', name='My Incidents', exact=True).wait_for()
    for status in ('Bank Contacted', 'Reported', 'Awaiting Response', 'Resolved', 'Closed', 'Open'):
        page.get_by_label('Case status', exact=True).select_option(status)
        page.get_by_role('button', name='Save case status', exact=True).click()
        page.get_by_text('Saved case status: ' + status, exact=True).wait_for()
        page.reload()
        page.get_by_text('Saved case status: ' + status, exact=True).wait_for()
        assert context.request.get(api + '/report').json() == snapshot
    page.screenshot(path=str(OUTPUT / 'incidents-mobile.png'), full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    # Stale status handling has its own conflict flow and does not erase intake drafts.
    current = context.request.get(api).json()
    response = context.request.patch(BASE + '/api/v1/incidents/' + case['id'] + '/status',
        data={'status': 'Bank Contacted', 'expected_status_revision': current['status_revision']})
    assert response.status == 200
    page.get_by_label('Case status', exact=True).select_option('Reported')
    page.get_by_role('button', name='Save case status', exact=True).click()
    page.get_by_role('button', name='Reload saved status', exact=True).click()
    page.get_by_text('Saved case status: Bank Contacted', exact=True).wait_for()
    page.get_by_role('link', name='Reopen case', exact=True).click()
    page.get_by_text('Saved case status: Bank Contacted', exact=True).wait_for()
    page.goto(report_url)
    page.get_by_role('button', name='Download text report', exact=True).wait_for()
    # Other session can neither review/download nor update this case.
    foreign = browser.new_context()
    other = foreign.new_page()
    other.goto(report_url)
    other.get_by_text('Resource not found.', exact=True).wait_for()
    assert foreign.request.get(api + '/report?format=txt').status == 404
    assert foreign.request.patch(BASE + '/api/v1/incidents/' + case['id'] + '/status', data={'status': 'Closed', 'expected_status_revision': 0}).status == 404
    foreign.close()
    # An edit in another tab invalidates the report; window focus removes stale HTML.
    current = context.request.get(api).json()
    changed = context.request.patch(api + '/context', data={'already_sent_money': 'yes', 'expected_revision': current['input_revision']})
    assert changed.status == 200
    page.evaluate("window.dispatchEvent(new Event('focus'))")
    page.get_by_role('heading', name='Analysis needed', exact=True).wait_for()
    assert page.get_by_text(snapshot['id'], exact=False).count() == 0
    assert context.request.get(api + '/report?format=txt').status == 409
    assert target.read_text(encoding='utf-8') == text  # User's prior download remains.
    analyze(page, changed.json(), 'Needs verification')
    page.get_by_text('You reported sending money:', exact=False).first.wait_for()
    assert context.request.get(api + '/report').json()['id'] != snapshot['id']
    # A malicious message remains inert redacted text, including in fallback reports.
    current = context.request.get(api).json()
    payload = '<script>window.evidenceExecuted=true</script>\n\nOTP: 739182\n\npassword=canary-secret'
    response = context.request.post(api + '/evidence', data={'type': 'call_summary', 'text': payload, 'expected_revision': current['input_revision']})
    assert response.status == 201
    current = context.request.get(api).json()
    analyze(page, current, 'Needs verification')
    page.get_by_text('<script>window.evidenceExecuted=true</script>', exact=False).first.wait_for()
    assert page.evaluate('window.evidenceExecuted') is None
    assert '739182' not in page.inner_text('body') and 'canary-secret' not in page.inner_text('body')
    assert '739182' not in context.request.get(api + '/report?format=txt').text()
    # Even without a focus refresh, an old page cannot download a deleted report.
    current = context.request.get(api).json()
    item = current['evidence'][-1]
    removed = context.request.delete(api + '/evidence/' + item['id'] + f'?expected_revision={current["input_revision"]}')
    assert removed.status == 204
    page.get_by_role('button', name='Download text report', exact=True).click()
    page.get_by_role('heading', name='Analysis needed', exact=True).wait_for()
    context.close()
    # Report wording and independent warnings for pending/failed transactions.
    for index, status in ((1, 'Pending'), (2, 'Failed')):
        context = browser.new_context()
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        case = create(context, 'E', index)
        analyze(page, case, 'Unable to assess')
        expect(page.get_by_text(status, exact=True)).to_be_visible()
        page.get_by_role('heading', name='Safety warning', exact=True).wait_for()
        assert 'Do not spend' not in page.inner_text('body')
        context.close()
    assert not errors, errors
    print('Phase 04 browser passed: report/download/reopen, UTF-8, six statuses, conflicts, ownership, invalidation, post-loss, inert evidence, pending/failed, desktop/mobile/focus; no page errors.')
    browser.close()
