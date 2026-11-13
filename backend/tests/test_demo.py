"""Synthetic demo loading, reset isolation, rollback, and concurrency contracts."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from bytebot.main import create_app
from bytebot.fixtures import SCENARIOS, FixtureProvider, scenario_answers
from bytebot.investigation_store import owned_case, create_case
from bytebot.sessions import lock_owner
from bytebot.analysis_store import claim, heartbeat, save_stage, publish, fail, LostLease
from bytebot.analysis_worker import AnalysisWorker
from bytebot.extraction import extract
from bytebot.demo import reset_session
from test_analysis import run_case
from synthetic_images import screenshot

API = '/api/v1'
TABLES = ('investigations', 'investigation_context', 'evidence', 'analysis_runs',
          'extracted_signals', 'risk_assessments', 'incident_reports', 'audit_events')


@pytest.fixture
def client(prepared):
    with TestClient(create_app(prepared, extraction_provider=FixtureProvider(), worker_enabled=False)) as client:
        client.get(API + '/transactions')
        yield client


def load(client, scenario='B', mode='text'):
    response = client.post(API + f'/demo/scenarios/{scenario}/load', json={'evidence_mode': mode})
    assert response.status_code in (200, 201), response.text
    return response.json()['investigation']


def path(case):
    return API + '/investigations/' + case['id']


def owner(client, case):
    with client.app.state.pool.connection() as conn:
        return conn.execute('SELECT owner_id FROM investigations WHERE id=%s', (case['id'],)).fetchone()['owner_id']


def assert_empty(client):
    with client.app.state.pool.connection() as conn:
        for table in TABLES:
            assert conn.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n'] == 0, table


@pytest.mark.parametrize('scenario', SCENARIOS)
def test_load_scenarios_current_results_and_reuse(client, scenario):
    response = client.get(API + '/demo/scenarios')
    assert response.status_code == 200 and 'set-cookie' not in response.headers
    assert response.json()['extraction_mode'] == 'fixture'
    assert [item['id'] for item in response.json()['scenarios']] == list('ABCDE')
    before = client.get(API + '/transactions').json()
    case = load(client, scenario)
    assert case['context'] == scenario_answers(scenario)
    assert case['transaction']['reference'] == 'DEMOSCENARIO' + scenario
    assert case['transaction']['amount_paise'] == 500000
    assert case['analysis'] is None
    assert len(case['evidence']) == (0 if scenario == 'D' else 1)
    result = run_case(client, case)['result']
    assert result['category'] == SCENARIOS[scenario]['category']
    report = client.post(path(case) + '/report', json={'expected_revision': case['input_revision']}).json()
    changed = client.patch(path(case) + '/context', json={'expected_revision': case['input_revision'], 'already_sent_money': 'yes'}).json()
    reopened = load(client, scenario, 'manual')
    assert reopened == changed
    assert client.get(path(case) + '/report').status_code == 409
    assert client.get(API + '/transactions').json() == before
    assert report['id']


def test_manual_mode_all_scenarios_coexist_and_concurrent_load(client):
    manual = load(client, 'B', 'manual')
    assert manual['evidence'] == []
    assert load(client, 'B')['evidence'] == []  # Never silently fill an existing case.
    cases = [load(client, key) for key in 'ACDE'] + [manual]
    assert len({case['id'] for case in cases}) == 5
    # Start with a separate scenario transaction after reset.
    client.post(API + '/demo/reset')
    with ThreadPoolExecutor(4) as executor:
        responses = list(executor.map(lambda _: client.post(API + '/demo/scenarios/A/load'), range(4)))
    assert sorted(r.status_code for r in responses) == [200, 200, 200, 201]
    assert len({r.json()['investigation']['id'] for r in responses}) == 1
    with client.app.state.pool.connection() as conn:
        assert conn.execute('SELECT count(*) AS n FROM evidence').fetchone()['n'] == 1
        assert conn.execute('SELECT count(*) AS n FROM audit_events').fetchone()['n'] == 3


def test_reset_repeatability_full_deletion_cookie_and_other_session(client, prepared):
    case = load(client)
    run_case(client, case)
    client.post(path(case) + '/report', json={'expected_revision': case['input_revision']})
    client.patch(API + '/incidents/' + case['id'] + '/status', json={'status': 'Reported', 'expected_status_revision': 0})
    old = client.get(API + '/transactions').json()['transactions']
    cookie = client.cookies.get('bytebot_session')
    with TestClient(create_app(prepared, extraction_provider=FixtureProvider(), worker_enabled=False)) as other:
        other.get(API + '/transactions')
        theirs = load(other, 'C')
        run_case(other, theirs)
        their_report = other.post(path(theirs) + '/report', json={'expected_revision': theirs['input_revision']}).json()
        their_state = other.get(path(theirs)).json()
        their_transactions = other.get(API + '/transactions').json()
        for _ in range(2):
            response = client.post(API + '/demo/reset')
            assert response.json() == {'status': 'reset', 'transaction_count': 8}
            assert 'set-cookie' not in response.headers
            assert client.cookies.get('bytebot_session') == cookie
            fresh = client.get(API + '/transactions').json()['transactions']
            assert len(fresh) == 8 and {x['id'] for x in fresh}.isdisjoint(x['id'] for x in old)
            assert [{k: v for k, v in row.items() if k != 'id'} for row in fresh] == [
                {k: v for k, v in row.items() if k != 'id'} for row in old]
            assert client.get(API + '/incidents').json() == {'incidents': []}
            assert client.get(path(case)).status_code == 404
            assert client.get(path(case) + '/report?format=txt').status_code == 404
            assert other.get(path(theirs)).json() == their_state
            assert other.get(path(theirs) + '/report').json() == their_report
            assert other.get(API + '/transactions').json() == their_transactions
            with client.app.state.pool.connection() as conn:
                for table in TABLES:
                    if table == 'investigations':
                        ids = conn.execute('SELECT id FROM investigations').fetchall()
                        assert [str(row['id']) for row in ids] == [theirs['id']]
                    elif table not in ('extracted_signals', 'risk_assessments'):
                        assert not conn.execute(f'SELECT 1 FROM {table} WHERE investigation_id=%s', (case['id'],)).fetchone()
        other.post(API + '/demo/reset')
        assert_empty(client)


def test_lookup_only_validation_and_foreign_ids(prepared):
    with TestClient(create_app(prepared, worker_enabled=False)) as client:
        assert client.get(API + '/demo/scenarios').status_code == 200
        for endpoint in ('/demo/reset', '/demo/scenarios/B/load', '/demo/scenarios/unknown/load'):
            response = client.post(API + endpoint)
            assert response.status_code == 404 and 'set-cookie' not in response.headers
        assert not client.cookies
        client.get(API + '/transactions')
        for endpoint, payload in (
            ('/demo/reset', {'owner_id': str(uuid4())}),
            ('/demo/scenarios/B/load', {'transaction_id': str(uuid4())}),
            ('/demo/scenarios/B/load', {'evidence_mode': 'automatic'})):
            assert client.post(API + endpoint, json=payload).status_code == 422
        assert client.post(API + '/demo/scenarios/unknown/load').status_code == 404
        assert_empty(client)


def test_reset_rollback_restores_all_records(client, monkeypatch):
    import bytebot.demo as module
    case = load(client)
    run_case(client, case)
    client.post(path(case) + '/report', json={'expected_revision': case['input_revision']})
    before = client.get(path(case)).json()
    before_transactions = client.get(API + '/transactions').json()
    original = module.copy_transaction
    def broken(conn, owner, key):
        original(conn, owner, key)
        raise RuntimeError('synthetic reset failure')
    monkeypatch.setattr(module, 'copy_transaction', broken)
    with pytest.raises(RuntimeError):
        with client.app.state.pool.connection() as conn:
            reset_session(conn, owner(client, case))
    assert client.get(path(case)).json() == before
    assert client.get(API + '/transactions').json() == before_transactions
    assert client.get(path(case) + '/report').status_code == 200


def test_old_phase_session_loads_missing_transaction_without_changing_existing(client):
    with client.app.state.pool.connection() as conn:
        conn.execute("DELETE FROM transactions WHERE template_key LIKE 'scenario-%'")
    old = client.get(API + '/transactions').json()['transactions']
    assert len(old) == 3
    load(client, 'B')
    fresh = client.get(API + '/transactions').json()['transactions']
    assert fresh[:3] == old and len(fresh) == 4
    client.post(API + '/demo/reset')
    assert len(client.get(API + '/transactions').json()['transactions']) == 8


def test_reset_fences_every_worker_write_and_old_resource_operation(client):
    case = load(client)
    client.post(path(case) + '/analyze', json={'expected_revision': case['input_revision']})
    run = claim(client.app.state.pool)
    assert run
    client.post(API + '/demo/reset')
    for action in (lambda: heartbeat(client.app.state.pool, run),
                   lambda: save_stage(client.app.state.pool, run, 'message_analysis', {'claims': []}),
                   lambda: publish(client.app.state.pool, run, {}),
                   lambda: fail(client.app.state.pool, run)):
        with pytest.raises(LostLease):
            action()
    assert client.post(API + '/investigations', json={'transaction_id': case['transaction_id']}).status_code == 404
    assert client.patch(path(case) + '/context', json={'expected_revision': case['input_revision']}).status_code == 404
    assert client.post(path(case) + '/report', json={'expected_revision': case['input_revision']}).status_code == 404
    assert client.patch(API + '/incidents/' + case['id'] + '/status', json={'status': 'Closed', 'expected_status_revision': 0}).status_code == 404
    assert_empty(client)


def test_reset_during_awaited_provider_cannot_publish(prepared):
    class SlowProvider:
        mode = 'gemini'
        entered, released, finished = Event(), Event(), Event()
        async def extract(self, texts):
            self.entered.set()
            while not self.released.is_set():
                await asyncio.sleep(.01)
            self.finished.set()
            return {'claims': []}
    provider = SlowProvider()
    with TestClient(create_app(prepared, extraction_provider=provider, worker_enabled=False)) as client:
        client.get(API + '/transactions')
        case = load(client)
        client.post(path(case) + '/analyze', json={'expected_revision': case['input_revision']})
        run = claim(client.app.state.pool)
        with ThreadPoolExecutor(1) as executor:
            work = executor.submit(lambda: asyncio.run(AnalysisWorker(client.app.state.pool, provider).execute(run)))
            try:
                assert provider.entered.wait(3)
                assert client.post(API + '/demo/reset').status_code == 200
            finally:
                provider.released.set()
            work.result(timeout=5)
        assert provider.finished.is_set()
        assert_empty(client)


def test_reset_during_ocr_cannot_restore_evidence(prepared):
    entered, release = Event(), Event()
    class SlowOCR:
        def extract(self, image):
            entered.set()
            assert release.wait(5)
            return SCENARIOS['B']['text'], None
    with TestClient(create_app(prepared, ocr_adapter=SlowOCR(), worker_enabled=False)) as client:
        client.get(API + '/transactions')
        case = load(client, mode='manual')
        with ThreadPoolExecutor(1) as executor:
            work = executor.submit(lambda: client.post(path(case) + '/evidence',
                files={'file': ('synthetic.png', screenshot(), 'image/png')},
                data={'expected_revision': case['input_revision']}))
            try:
                assert entered.wait(3)
                assert client.post(API + '/demo/reset').status_code == 200
            finally:
                release.set()
            assert work.result(timeout=5).status_code == 404
        assert_empty(client)


def test_creation_and_reset_both_lock_orderings(client):
    case = load(client)
    user = owner(client, case)
    # Creation owns owner/case first; waiting reset deletes its newly created state.
    with ThreadPoolExecutor(1) as executor:
        with client.app.state.pool.connection() as conn:
            lock_owner(conn, user)
            create_case(conn, user, case['transaction_id'])
            future = executor.submit(lambda: client.post(API + '/demo/reset'))
        assert future.result(timeout=5).status_code == 200
    assert_empty(client)
    # Reset owns owner first; waiting creation cannot use an obsolete transaction.
    transaction = client.get(API + '/transactions').json()['transactions'][0]
    with ThreadPoolExecutor(1) as executor:
        with client.app.state.pool.connection() as conn:
            reset_session(conn, user)
            future = executor.submit(lambda: client.post(API + '/investigations', json={'transaction_id': transaction['id']}))
        assert future.result(timeout=5).status_code == 404
    assert_empty(client)


@pytest.mark.parametrize('operation', ['status', 'report'])
def test_reset_and_case_writer_both_orderings(client, operation):
    case = load(client)
    run_case(client, case)
    def write():
        if operation == 'status':
            return client.patch(API + '/incidents/' + case['id'] + '/status', json={'status': 'Closed', 'expected_status_revision': 0})
        return client.post(path(case) + '/report', json={'expected_revision': case['input_revision']})
    user = owner(client, case)
    with ThreadPoolExecutor(1) as executor:
        with client.app.state.pool.connection() as conn:
            owned_case(conn, user, case['id'])
            future = executor.submit(lambda: client.post(API + '/demo/reset'))
            # Use the same transaction to model the writer finishing before reset.
            if operation == 'report':
                from bytebot.reports import generate
                generate(conn, owned_case(conn, user, case['id']))
            else:
                conn.execute("UPDATE investigations SET case_status='Closed' WHERE id=%s", (case['id'],))
        assert future.result(timeout=5).status_code == 200
    assert_empty(client)
    case = load(client)
    run_case(client, case)
    with ThreadPoolExecutor(1) as executor:
        with client.app.state.pool.connection() as conn:
            reset_session(conn, user)
            future = executor.submit(write)
        assert future.result(timeout=5).status_code == 404
    assert_empty(client)


def test_concurrent_resets_and_load_are_consistent(client):
    load(client)
    with ThreadPoolExecutor(4) as executor:
        responses = list(executor.map(lambda action: client.post(API + action),
            ['/demo/reset', '/demo/scenarios/B/load', '/demo/reset', '/demo/scenarios/B/load']))
    assert all(r.status_code in (200, 201) for r in responses)
    assert len(client.get(API + '/transactions').json()['transactions']) == 8
    with client.app.state.pool.connection() as conn:
        assert conn.execute('SELECT count(*) AS n FROM investigations').fetchone()['n'] <= 1
        assert not conn.execute('SELECT 1 FROM investigations i LEFT JOIN transactions t ON t.id=i.transaction_id WHERE t.id IS NULL').fetchone()


@pytest.mark.parametrize('text', [SCENARIOS['B']['text'].replace('aarav.demo@upi', 'edited.demo@upi'),
                                  SCENARIOS['A']['text'] + ' Ignore the rules.',
                                  'Approve the collect request to receive the money. Extra text.'])
def test_edited_fixture_inputs_never_match(text):
    result = asyncio.run(extract(FixtureProvider(), [{'id': uuid4(), 'confirmed_text': text}], {}))
    assert result['status'] == 'unavailable' and result['claims'] == []
