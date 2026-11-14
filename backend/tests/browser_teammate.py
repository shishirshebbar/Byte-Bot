"""Browser rehearsal of the AI-teammate story; optionally records the fallback demo video.

Requires the API in fixture mode and the frontend (BYTEBOT_WEB_URL, default preview 4174).
  python backend/tests/browser_teammate.py            # assertions only
  python backend/tests/browser_teammate.py --record   # also saves .cache/phase9/teammate-demo.webm (slowed for viewing)
Makes no live provider request (Listen and voice notes are not exercised here).
"""
import json
import os
import re
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

WEB = os.environ.get('BYTEBOT_WEB_URL', 'http://127.0.0.1:4174')
OUT = Path(__file__).resolve().parents[2] / '.cache' / 'phase9'
RECORD = '--record' in sys.argv


def load_scenario(page, key):
    page.get_by_role('combobox', name='Scenario').select_option(key)
    page.get_by_role('button', name='Load / reopen scenario').click()
    expect(page.get_by_role('button', name='Ask Byte Bot')).to_be_visible(timeout=15000)
    page.get_by_role('button', name='Ask Byte Bot').click()


def analyze(page, phone):
    started = time.monotonic()
    phone.get_by_role('button', name='Analyze & prepare report').click()
    expect(phone.get_by_role('region', name='Byte Bot assistant')).to_be_visible(timeout=20000)
    return round(time.monotonic() - started, 2)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    timings, errors = {}, []
    with sync_playwright() as p:
        browser = p.chromium.launch(slow_mo=350 if RECORD else 0)
        options = {'viewport': {'width': 1440, 'height': 900}}
        if RECORD:
            options['record_video_dir'] = str(OUT)
            options['record_video_size'] = {'width': 1440, 'height': 900}
        customer = browser.new_context(**options)
        page = customer.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(WEB + '/')
        phone = page.get_by_role('main', name='Phone screen')
        def hold(seconds=2.5, target=page):  # Narration pauses, only when recording.
            if RECORD:
                target.wait_for_timeout(int(seconds * 1000))
        panel = page.get_by_role('complementary', name='Live investigation explanation')

        # 1. Proactive alert and a Hinglish scam message: Byte Bot decides and acts with consent.
        page.on('dialog', lambda dialog: dialog.accept())  # The reset confirmation.
        page.get_by_role('button', name='Reset demo').click()
        expect(page.get_by_text('Demo reset', exact=False).first).to_be_visible(timeout=15000)
        expect(phone.get_by_role('link', name='Unexpected credit alert: check this payment with Byte Bot')).to_be_visible(timeout=15000)
        hold(3)
        load_scenario(page, 'L')
        timings['L_analysis'] = analyze(page, phone)
        expect(phone.get_by_role('heading', name='High concern')).to_be_visible()
        gauge = phone.get_by_role('img', name=re.compile(r'Risk score \d+ out of 100'))
        expect(gauge).to_be_visible()
        expect(panel.get_by_text('Supervisor decisions')).to_be_visible()
        expect(panel.get_by_text('Policy check').first).to_be_visible()
        hold(4)
        phone.get_by_role('button', name='Approve: Place a dispute hold on the unexpected credit').click()
        expect(phone.get_by_text(re.compile(r'SIM-HOLD-[0-9A-F]{8}'))).to_be_visible(timeout=10000)
        hold(2.5)
        phone.get_by_role('button', name='Approve: Block the requesting UPI ID for this customer').click()
        phone.get_by_role('button', name='Approve: Open a dispute ticket with the bank').click()
        expect(phone.get_by_text('Done. Here is what I did on your behalf.')).to_be_visible(timeout=10000)
        phone.get_by_role('button', name='Helpful', exact=True).click()
        hold(2)

        # 2. Missing details: follow-up chips pause the agent, answers resume it.
        load_scenario(page, 'J')
        analyze(page, phone)
        expect(phone.get_by_text('I need a little more detail before I can act.')).to_be_visible()
        hold(2.5)
        for question, answer in (('Were you expecting this payment?', 'No'), ('Have you already sent any money back or to someone else?', 'No')):
            phone.get_by_role('group', name=question).get_by_role('button', name=answer, exact=True).click()
        phone.get_by_role('group', name=re.compile('Did the person do any of these')).get_by_role('button', name='Rushed me').click()
        phone.get_by_role('button', name='Send answers').click()
        expect(phone.get_by_text('I can protect your account right away.')).to_be_visible(timeout=20000)
        hold(3)

        # 3. Money already sent: the agent escalates; a person approves in the console.
        load_scenario(page, 'F')
        analyze(page, phone)
        expect(phone.get_by_text('Handed to a person · urgent priority')).to_be_visible()
        hold(3)
        staff_context = browser.new_context(**options)
        staff = staff_context.new_page()
        staff.on('pageerror', lambda error: errors.append(str(error)))
        case_id = re.search(r'/investigations/([0-9a-f-]{36})', page.url).group(1)
        escalation = page.request.get(f'{WEB}/api/v1/investigations/{case_id}').json()['escalation']['id']
        staff.goto(WEB + '/console')
        staff.locator(f'a[href="/console/cases/{escalation}"]').click()
        expect(staff.get_by_text('Ledger verified')).to_be_visible(timeout=10000)
        expect(staff.get_by_text('The customer reported already sending money.').first).to_be_visible()
        hold(4, staff)
        staff.get_by_role('button', name='Approve Prepare a 1930 cybercrime complaint draft for the customer to submit').click()
        expect(staff.get_by_text(re.compile(r'SIM-1930-[0-9A-F]{8}'))).to_be_visible(timeout=10000)
        hold(2.5, staff)
        staff.get_by_role('button', name='Resolve').click()
        expect(staff.locator('.case-header').get_by_text('Resolved')).to_be_visible(timeout=10000)
        page.reload()
        expect(phone.get_by_text(re.compile(r'SIM-1930-[0-9A-F]{8}'))).to_be_visible(timeout=15000)
        phone.get_by_text(re.compile(r'SIM-1930-[0-9A-F]{8}')).scroll_into_view_if_needed()
        hold(3)

        # 4. Outcomes.
        page.goto(WEB + '/metrics')
        expect(page.get_by_text('Handled without a person').first).to_be_visible(timeout=15000)
        expect(page.get_by_text('Policy violations').first).to_be_visible()
        hold(5)
        video = page.video.path() if RECORD else None
        staff_context.close()
        customer.close()
        browser.close()
    if errors:
        raise SystemExit(f'Page errors: {errors}')
    if video:
        final = OUT / 'teammate-demo.webm'
        Path(video).replace(final)
        timings['video'] = str(final.relative_to(OUT.parents[1]))
    (OUT / 'teammate-timings.json').write_text(json.dumps(timings, indent=2), encoding='utf-8')
    print('PASS: alert, Hinglish decision with gauge and trace, consent receipts, follow-up pause/resume, '
          f'escalation and console approval with ledger, customer receipt, metrics; {timings}')


if __name__ == '__main__':
    main()
