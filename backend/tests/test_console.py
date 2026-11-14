"""Human console: separate session, escalated-only access, approvals, notes, resolution."""
import pytest
from fastapi.testclient import TestClient
from bytebot.main import create_app
from bytebot.fixtures import FixtureProvider
from test_analysis import run_case
from test_agent import load, path, API

CONSOLE = API + '/console'


@pytest.fixture
def app(prepared):
    return create_app(prepared, extraction_provider=FixtureProvider(), worker_enabled=False)


@pytest.fixture
def clients(app):
    with TestClient(app) as customer, TestClient(app) as staff:
        customer.get(API + '/transactions')
        assert staff.post(CONSOLE + '/session', json={'name': 'Asha (demo agent)'}).status_code == 200
        yield customer, staff


def escalation_id(customer, case):
    return customer.get(path(case)).json()['escalation']['id']


def test_console_requires_its_own_session(app, clients):
    customer, _ = clients
    case = load(customer, 'F')
    run_case(customer, case)
    eid = escalation_id(customer, case)
    # The customer cookie never opens the console, and the console cookie never opens customer data.
    assert customer.get(CONSOLE + '/queue').status_code == 401
    assert customer.get(CONSOLE + f'/cases/{eid}').status_code == 401
    with TestClient(app) as staff_only:
        staff_only.post(CONSOLE + '/session')
        assert staff_only.get(path(case)).status_code == 404
        assert staff_only.get(API + '/transactions').status_code == 200  # A fresh customer session, not the case owner.


def test_queue_shows_only_escalated_cases_with_masked_customer(clients):
    customer, staff = clients
    calm = load(customer, 'C')
    run_case(customer, calm)
    loss = load(customer, 'F')
    run_case(customer, loss)
    big = load(customer, 'K')
    run_case(customer, big)
    cases = staff.get(CONSOLE + '/queue').json()['cases']
    assert {c['investigation_id'] for c in cases} == {loss['id'], big['id']}
    assert [c['priority'] for c in cases] == ['urgent', 'high']  # Highest priority first.
    assert cases[0]['category'] == 'High concern' and cases[0]['awaiting_human'] >= 2
    detail = staff.get(CONSOLE + f"/cases/{cases[0]['id']}").json()
    assert detail['transaction']['customer_vpa'] == 're•••@upi'
    assert 'recipient.demo@upi' not in str(detail)
    assert detail['analysis']['agent']['trace'] and detail['evidence'][0]['text']
    assert [r['code'] for r in detail['escalation']['reasons']] == ['customer_reported_loss']
    # A case that was never escalated cannot be opened by guessing IDs.
    assert staff.get(CONSOLE + f"/cases/{calm['id']}").status_code == 404


def test_human_approval_executes_and_customer_sees_receipt(clients):
    customer, staff = clients
    case = load(customer, 'F')
    run_case(customer, case)
    eid = escalation_id(customer, case)
    actions = staff.get(CONSOLE + f'/cases/{eid}').json()['analysis']['agent']['actions']
    draft = next(a for a in actions if a['action_type'] == 'draft_cybercrime_complaint')
    hold = next(a for a in actions if a['action_type'] == 'hold_credit')
    approved = staff.post(CONSOLE + f"/cases/{eid}/actions/{draft['id']}", json={'decision': 'approve'})
    assert approved.status_code == 200
    detail = approved.json()
    assert detail['escalation']['state'] == 'assigned' and detail['escalation']['assignee'] == 'Asha (demo agent)'
    done = next(a for a in detail['analysis']['agent']['actions'] if a['id'] == draft['id'])
    assert done['state'] == 'executed' and done['actor'] == 'human' and done['system_reference'].startswith('SIM-1930-')
    assert staff.post(CONSOLE + f"/cases/{eid}/actions/{draft['id']}", json={'decision': 'approve'}).status_code == 409
    rejected = staff.post(CONSOLE + f"/cases/{eid}/actions/{hold['id']}", json={'decision': 'reject'}).json()
    assert next(a for a in rejected['analysis']['agent']['actions'] if a['id'] == hold['id'])['state'] == 'declined'
    # The customer cannot approve human-only steps, but sees the person's result.
    mine = customer.get(path(case)).json()
    assert next(a for a in mine['analysis']['agent']['actions'] if a['id'] == draft['id'])['actor'] == 'human'
    assert mine['escalation']['assignee'] == 'Asha (demo agent)'
    activity = [(e['action'], e['actor']) for e in detail['activity']]
    assert ('action_executed', 'human') in activity and ('escalation_assigned', 'human') in activity


def test_notes_are_redacted_and_resolution_closes_handoff(clients):
    customer, staff = clients
    case = load(customer, 'H')
    run_case(customer, case)
    eid = escalation_id(customer, case)
    noted = staff.post(CONSOLE + f'/cases/{eid}/notes', json={'text': 'Called customer. Their OTP 482913 was never shared.'}).json()
    assert '482913' not in str(noted['notes']) and noted['notes'][0]['author'] == 'Asha (demo agent)'
    resolved = staff.post(CONSOLE + f'/cases/{eid}/resolve', json={'note': 'Confirmed scam attempt; customer safe.'}).json()
    assert resolved['escalation']['state'] == 'resolved' and len(resolved['notes']) == 2
    assert staff.post(CONSOLE + f'/cases/{eid}/resolve', json={}).status_code == 409
    mine = customer.get(path(case)).json()
    assert mine['escalation']['state'] == 'resolved'
    assert mine['analysis']['agent']['outcome'] != 'escalated'
    # The customer can still ask for a person again, which opens a new handoff.
    again = customer.post(path(case) + '/escalate').json()['escalation']
    assert again['id'] != eid and again['state'] == 'open'
    feed = staff.get(CONSOLE + '/notifications').json()['notifications']
    assert {'escalation_resolved', 'note_added', 'escalation_opened'} <= {n['action'] for n in feed}


def test_integrations_and_undo(clients):
    customer, staff = clients
    items = staff.get(CONSOLE + '/integrations').json()['integrations']
    assert {'paytm_upi_sandbox', 'bank_dispute_desk', 'cybercrime_1930_draft', 'notification_service', 'gemini', 'sarvam'} <= {i['key'] for i in items}
    case = load(customer, 'K')
    run_case(customer, case)
    eid = escalation_id(customer, case)
    hold = next(a for a in staff.get(CONSOLE + f'/cases/{eid}').json()['analysis']['agent']['actions'] if a['action_type'] == 'hold_credit')
    staff.post(CONSOLE + f"/cases/{eid}/actions/{hold['id']}", json={'decision': 'approve'})
    undone = staff.post(CONSOLE + f"/cases/{eid}/actions/{hold['id']}/undo").json()
    assert next(a for a in undone['analysis']['agent']['actions'] if a['id'] == hold['id'])['state'] == 'compensated'
