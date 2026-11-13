import os
from pathlib import Path
from playwright.sync_api import sync_playwright

Path('.cache/phase01').mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={'width': 1280, 'height': 900})
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(os.environ.get('BYTEBOT_WEB_URL', 'http://127.0.0.1:5174'))
    page.get_by_role('link', name='Aarav Sharma', exact=False).wait_for()
    page.screenshot(path='.cache/phase01/history-desktop.png', full_page=True)
    ids = []
    for sender, status, wording in [('Aarav Sharma', 'Successful', 'Received from'), ('Meera Rao', 'Pending', 'Funds are not confirmed as received.'), ('Kabir Shah', 'Failed', 'Funds were not received.')]:
        page.get_by_role('link', name=sender, exact=False).click()
        page.get_by_text(wording, exact=False).wait_for()
        assert page.locator('.status').inner_text() == status
        ids.append(page.url)
        page.reload()
        page.get_by_text(wording, exact=False).wait_for()
        page.get_by_role('link', name='All transactions').click()
    page.go_back()
    page.get_by_text('Funds were not received.', exact=False).wait_for()
    page.go_forward()
    page.get_by_role('heading', name='Transaction history').wait_for()
    page.set_viewport_size({'width': 390, 'height': 844})
    page.screenshot(path='.cache/phase01/history-mobile.png', full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.get_by_role('link', name='Meera Rao', exact=False).click()
    page.get_by_text('Funds are not confirmed as received.', exact=False).wait_for()
    page.screenshot(path='.cache/phase01/detail-mobile.png', full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.keyboard.press('Tab')
    assert page.evaluate('document.activeElement.tagName') == 'A'
    other = browser.new_context()
    second = other.new_page()
    second.goto(ids[0])
    second.get_by_role('heading', name='Transaction unavailable').wait_for()
    page.route('**/api/v1/transactions', lambda route: route.fulfill(status=503, content_type='application/json', body='{"error":{"code":"database_unavailable","message":"Temporarily unavailable."}}'))
    page.goto(os.environ.get('BYTEBOT_WEB_URL', 'http://127.0.0.1:5174'))
    page.get_by_role('button', name='Try again').wait_for()
    page.unroute('**/api/v1/transactions')
    page.get_by_role('button', name='Try again').click()
    page.get_by_role('link', name='Aarav Sharma', exact=False).wait_for()
    assert not errors, errors
    browser.close()
    print('PASS: statuses, reload, navigation, mobile overflow, keyboard focus, cross-session unavailable, API failure/retry; no page errors')
