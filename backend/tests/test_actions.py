"""Consent, execution on simulated systems, retries, undo, and ownership."""
import pytest
from fastapi.testclient import TestClient
from bytebot.main import create_app
from bytebot.fixtures import FixtureProvider
from bytebot.systems import SimulatedSystems, SystemUnavailable
from test_analysis import run_case
from test_agent import load, path, API


@pytest.fixture
def client(prepared):
    with TestClient(create_app(prepared, extraction_provider=FixtureProvider(), worker_enabled=False)) as client:
        client.get(API + '/transactions')
        yield client


class FlakySystems(SimulatedSystems):
    """Fails a configurable number of calls, then behaves like the real mock."""
    def __init__(self, failures):
        self.failures = failures

    def execute(self, conn, case, action):
        if self.failures:
            self.failures -= 1
            raise SystemUnavailable('down')
        return super().execute(conn, case, action)


def consent(client, case, action, decision='approve'):
    return client.post(path(case) + f"/actions/{action['id']}/consent",
                       json={'decision': decision, 'expected_revision': case['input_revision']})


def find(state, action_type):
    return next(a for a in state['analysis']['agent']['actions'] if a['action_type'] == action_type)


def test_auto_steps_execute_with_simulated_receipts(client):
    agent = run_case(client, load(client, 'B'))['agent']
    note = next(a for a in agent['actions'] if a['action_type'] == 'notify_customer')
    assert note['state'] == 'executed' and note['actor'] == 'agent'
    assert note['system_reference'].startswith('SIM-NOTE-') and 'simulated' in note['system_label'] and note['detail']


def test_consent_executes_once_and_undo_reverses(client):
    case = load(client, 'B')
    agent = run_case(client, case)['agent']
    pending = {a['action_type']: a for a in agent['actions'] if a['state'] == 'awaiting_consent'}
    assert set(pending) == {'hold_credit', 'block_vpa', 'raise_bank_dispute'}
    hold = find(consent(client, case, pending['hold_credit']).json(), 'hold_credit')
    assert hold['state'] == 'executed' and hold['actor'] == 'customer' and hold['system_reference'].startswith('SIM-HOLD-')
    # A repeat consent is rejected and never creates a second system record.
    assert consent(client, case, pending['hold_credit']).status_code == 409
    assert find(consent(client, case, pending['block_vpa'], 'decline').json(), 'block_vpa')['state'] == 'declined'
    done = consent(client, case, pending['raise_bank_dispute']).json()
    assert done['analysis']['agent']['outcome'] == 'actions_completed'
    with client.app.state.pool.connection() as conn:
        assert conn.execute('SELECT count(*) AS n FROM simulated_records WHERE investigation_id=%s', (case['id'],)).fetchone()['n'] == 3
    # Reversible steps can be undone; a bank ticket cannot.
    undo = client.post(path(case) + f"/actions/{hold['id']}/undo", json={'expected_revision': case['input_revision']})
    assert undo.status_code == 200 and find(undo.json(), 'hold_credit')['state'] == 'compensated'
    bank = pending['raise_bank_dispute']
    assert client.post(path(case) + f"/actions/{bank['id']}/undo", json={'expected_revision': case['input_revision']}).status_code == 409
    with client.app.state.pool.connection() as conn:
        status = conn.execute('SELECT status FROM simulated_records WHERE action_id=%s', (hold['id'],)).fetchone()['status']
        audit = [r['action'] for r in conn.execute('SELECT action FROM audit_events WHERE investigation_id=%s ORDER BY id', (case['id'],))]
    assert status == 'reversed'
    assert audit.count('action_executed') == 3 and 'action_declined' in audit and 'action_compensated' in audit


def test_consent_requires_revision_ownership_and_waiting_state(client, prepared):
    case = load(client, 'F')
    agent = run_case(client, case)['agent']
    human = next(a for a in agent['actions'] if a['state'] == 'awaiting_human')
    assert consent(client, case, human).status_code == 409  # Only a person approves it.
    assert client.post(path(case) + f"/actions/{human['id']}/consent", json={'decision': 'approve', 'expected_revision': 99}).status_code == 409
    with TestClient(create_app(prepared, extraction_provider=FixtureProvider(), worker_enabled=False)) as other:
        other.get(API + '/transactions')
        assert other.post(path(case) + f"/actions/{human['id']}/consent", json={'decision': 'approve', 'expected_revision': case['input_revision']}).status_code == 404
    other_case = load(client, 'B')
    run_case(client, other_case)
    assert consent(client, other_case, human).status_code == 404  # Another case's step.


@pytest.mark.parametrize('failures,state', [(1, 'executed'), (2, 'failed')])
def test_system_outage_retries_then_fails_visibly(prepared, failures, state):
    with TestClient(create_app(prepared, extraction_provider=FixtureProvider(), worker_enabled=False,
                               systems=FlakySystems(failures))) as client:
        client.get(API + '/transactions')
        case = load(client, 'C')
        agent = run_case(client, case)['agent']  # The auto notification succeeds first.
        client.app.state.systems.failures = failures
        hold = next(a for a in agent['actions'] if a['action_type'] == 'hold_credit')
        assert find(consent(client, case, hold).json(), 'hold_credit')['state'] == state
        with client.app.state.pool.connection() as conn:
            count = conn.execute('SELECT count(*) AS n FROM simulated_records WHERE action_id=%s', (hold['id'],)).fetchone()['n']
        assert count == (1 if state == 'executed' else 0)


def test_executed_steps_survive_input_change(client):
    case = load(client, 'B')
    agent = run_case(client, case)['agent']
    consent(client, case, next(a for a in agent['actions'] if a['action_type'] == 'hold_credit'))
    client.patch(path(case) + '/context', json={'expected_revision': case['input_revision'], 'knows_sender': 'yes'})
    with client.app.state.pool.connection() as conn:
        states = {r['action_type']: r['state'] for r in conn.execute(
            'SELECT action_type,state FROM agent_actions WHERE investigation_id=%s', (case['id'],))}
    assert states['hold_credit'] == 'executed' and states['block_vpa'] == 'revoked'
