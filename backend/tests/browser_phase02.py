"""Phase 02 browser acceptance with live API and CPU OCR; synthetic data only."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from synthetic_images import screenshot

OUTPUT = Path('.cache/phase02')
OUTPUT.mkdir(parents=True, exist_ok=True)
BASE = os.environ.get('BYTEBOT_WEB_URL', 'http://127.0.0.1:5174')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={'width': 1280, 'height': 900})
    page = context.new_page()
    page.set_default_timeout(10000)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script('''window.blobAudit = { created: [], revoked: [] };
      const create = URL.createObjectURL.bind(URL), revoke = URL.revokeObjectURL.bind(URL);
      URL.createObjectURL = value => { const url = create(value); window.blobAudit.created.push(url); return url; };
      URL.revokeObjectURL = url => { window.blobAudit.revoked.push(url); revoke(url); };''')
    page.goto(BASE)
    page.get_by_role('link', name='Aarav Sharma', exact=False).click()
    page.get_by_role('button', name='Ask Byte Bot', exact=True).click()
    page.get_by_role('heading', name='Let’s understand what happened').wait_for()
    case_url = page.url
    case_id = case_url.rsplit('/', 1)[1]
    api = '/api/v1/investigations/' + case_id
    page.get_by_label('Were you expecting this payment?').select_option('no')
    page.get_by_label('Do you know the sender?', exact=True).select_option('no')
    page.get_by_label('Has anyone asked you to return the money?').select_option('yes')
    page.get_by_label('Have you already sent money in response?').select_option('no')
    page.get_by_label('WhatsApp', exact=True).check()
    page.get_by_label('Where did they ask you to send money?').select_option('different_vpa')
    page.get_by_label('Requested UPI ID (optional)').fill('another.demo@upi')
    page.get_by_label('Urgent response', exact=True).check()
    page.get_by_role('button', name='Save answers', exact=True).click()
    page.get_by_text('Answers saved.', exact=True).wait_for()
    page.reload()
    assert page.get_by_label('Were you expecting this payment?').input_value() == 'no'
    assert page.get_by_label('WhatsApp', exact=True).is_checked()
    assert page.get_by_label('Requested UPI ID (optional)').input_value() == 'another.demo@upi'
    page.get_by_label('Message text', exact=True).fill('Please return INR 5000 today. OTP: 739182')
    page.get_by_role('button', name='Save text evidence', exact=True).click()
    page.get_by_text('Evidence saved with credential values redacted.', exact=True).wait_for()
    assert '739182' not in page.locator('body').inner_text()
    assert '739182' not in page.get_by_label('Review evidence text', exact=True).input_value()
    page.get_by_label('Evidence type', exact=True).select_option('call_summary')
    page.get_by_label('What did the caller say?', exact=True).fill('Caller asked me to return funds urgently.')
    page.get_by_role('button', name='Save text evidence', exact=True).click()
    page.get_by_role('heading', name='Typed call summary', exact=True).wait_for()
    page.get_by_label('Screenshot (PNG or JPEG', exact=False).set_input_files({'name': 'synthetic.png', 'mimeType': 'image/png', 'buffer': screenshot()})
    page.get_by_alt_text('Browser-local screenshot preview').wait_for()
    page.get_by_role('button', name='Upload and read screenshot').click()
    page.get_by_text('Screenshot processed. Review and confirm its text.', exact=True).wait_for(timeout=30000)
    assert '5000' in page.get_by_label('Review screenshot text', exact=True).input_value()
    page.get_by_text('This screenshot is excluded from future analysis until you confirm its text.', exact=True).wait_for()
    expect(page.get_by_role('button', name='Analyze saved information', exact=True)).to_be_disabled()
    page.get_by_label('Review screenshot text', exact=True).fill('Please return INR 5000 today to another.demo@upi')
    page.get_by_role('button', name='Confirm reviewed text', exact=True).click()
    page.get_by_text('Reviewed text confirmed and saved.', exact=True).wait_for()
    page.screenshot(path=str(OUTPUT / 'investigation-desktop.png'), full_page=True)
    page.reload()
    assert page.get_by_label('Review screenshot text', exact=True).input_value() == 'Please return INR 5000 today to another.demo@upi'
    # A blank real image must offer manual correction, never fabricated text.
    page.get_by_label('Screenshot (PNG or JPEG', exact=False).set_input_files({'name': 'blank.png', 'mimeType': 'image/png', 'buffer': screenshot(False)})
    page.get_by_role('button', name='Upload and read screenshot').click()
    page.get_by_text('No readable text was found.', exact=False).wait_for(timeout=30000)
    page.get_by_label('Review screenshot text', exact=True).nth(1).fill('Manually transcribed synthetic message.')
    page.get_by_role('button', name='Confirm reviewed text', exact=True).click()
    page.get_by_text('Reviewed text confirmed and saved.', exact=True).wait_for()
    last = page.locator('.evidence-item').last
    last.get_by_role('button', name='Remove evidence').click()
    page.get_by_text('Evidence removed from this case.', exact=True).wait_for()
    assert page.get_by_alt_text('Browser-local screenshot preview').count() == 0
    assert page.evaluate('blobAudit.created.every(url => blobAudit.revoked.includes(url))')
    # Save conflicts preserve local drafts and offer explicit recovery.
    page.get_by_label('Do you know the sender?', exact=True).select_option('yes')
    state = context.request.get(BASE + api).json()
    response = context.request.patch(BASE + api + '/context', data={'expected_revision': state['input_revision'], 'repayment_requested': 'unknown'})
    assert response.status == 200
    page.get_by_role('button', name='Save answers', exact=True).click()
    page.get_by_role('button', name='Reload saved case', exact=True).wait_for()
    assert page.get_by_label('Do you know the sender?', exact=True).input_value() == 'yes'
    page.once('dialog', lambda dialog: dialog.accept())
    page.get_by_role('button', name='Reload saved case', exact=True).click()
    page.get_by_role('heading', name='Let’s understand what happened').wait_for()
    assert page.get_by_label('Do you know the sender?', exact=True).input_value() == 'no'
    # Unsaved navigation can be cancelled.
    page.get_by_label('Were you expecting this payment?').select_option('yes')
    page.once('dialog', lambda dialog: dialog.dismiss())
    with page.expect_event('dialog'):
        page.get_by_role('link', name='Byte Bot', exact=True).click()
    page.wait_for_url(case_url)
    assert page.get_by_label('Were you expecting this payment?').input_value() == 'yes'
    page.once('dialog', lambda dialog: dialog.dismiss())
    with page.expect_event('dialog'):
        page.evaluate('history.back()')
    page.wait_for_url(case_url)
    assert page.get_by_label('Were you expecting this payment?').input_value() == 'yes'
    page.get_by_label('Were you expecting this payment?').select_option('no')
    # Foreign direct links reveal no evidence or transaction facts.
    other = browser.new_context()
    foreign = other.new_page()
    foreign.goto(case_url)
    foreign.get_by_role('heading', name='Investigation unavailable').wait_for()
    assert foreign.get_by_text('another.demo@upi', exact=False).count() == 0
    other.close()
    page.set_viewport_size({'width': 390, 'height': 844})
    page.screenshot(path=str(OUTPUT / 'investigation-mobile.png'), full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.get_by_label('Were you expecting this payment?').focus()
    assert page.evaluate('document.activeElement.tagName') == 'SELECT'
    # Remove each method and verify durable absence after reload.
    while page.get_by_role('button', name='Remove evidence', exact=True).count():
        page.get_by_role('button', name='Remove evidence', exact=True).first.click()
        page.get_by_text('Evidence removed from this case.', exact=True).wait_for()
        page.wait_for_function('!document.querySelector("button:disabled.secondary")')
    page.reload()
    page.get_by_text('No evidence added. Your saved answers remain available.', exact=True).wait_for()
    # All transaction statuses remain eligible for intake with accurate wording.
    for sender, wording in [('Meera Rao', 'Funds are not confirmed as received.'), ('Kabir Shah', 'Funds were not received.')]:
        page.goto(BASE)
        page.get_by_role('link', name=sender, exact=False).click()
        page.get_by_role('button', name='Ask Byte Bot', exact=True).click()
        page.get_by_text(wording, exact=False).wait_for()
    assert not errors, errors
    browser.close()
    print('PASS: saved intake/reload, paste/call/real OCR, correction/confirmation, blank-image manual fallback, removal, object-URL cleanup, conflict recovery, unsaved-link warning, foreign ownership, desktop/mobile, keyboard focus, all statuses; no page errors')
