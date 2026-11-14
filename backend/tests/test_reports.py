"""Phase 04 report, follow-up, privacy, ownership and atomic invalidation checks."""
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4
import psycopg
import pytest
from fastapi.testclient import TestClient
from bytebot.main import create_app
from bytebot import reports
from bytebot.analysis_store import claim
from bytebot.analysis_worker import AnalysisWorker
from bytebot.fixtures import FixtureProvider
from bytebot.migrate import migrate
from bytebot.seeds import seed
from bytebot.audit import STATUSES, record
from bytebot.investigation_store import owned_case, bump
from bytebot.reports import generate
from test_analysis import new_case, run_case, BASE


@pytest.fixture
def client(prepared):
    with TestClient(create_app(prepared, extraction_provider=FixtureProvider(), worker_enabled=False)) as client:
        yield client


def report_case(client, scenario='A', index=0):
    case = new_case(client, scenario, index)
    run_case(client, case)
    return case


def report_url(case):
    return BASE + case['id'] + '/report'


def generate_report(client, case):
    response = client.post(report_url(case), json={'expected_revision': case['input_revision']})
    assert response.status_code == 201, response.text
    return response.json()


def events(client, case):
    with client.app.state.pool.connection() as conn:
        return conn.execute('SELECT * FROM audit_events WHERE investigation_id=%s ORDER BY id', (case['id'],)).fetchall()


@pytest.mark.parametrize('approval_stage', ['queued', 'running', 'complete'])
def test_approved_report_reuses_the_run_and_survives_reopen(client, approval_stage):
    case = new_case(client, 'B')
    url = BASE + case['id']
    body = {'expected_revision': case['input_revision']}
    pool = client.app.state.pool
    queue = client.post(url + '/analyze', json=body).json()
    assert queue['state'] == 'queued' and not queue['prepare_report'] and queue['report_id'] is None
    run = claim(pool) if approval_stage != 'queued' else None
    worker = AnalysisWorker(pool, client.app.state.extractor)
    if approval_stage == 'complete':
        asyncio.run(worker.execute(run))
        saved = client.get(url).json()['analysis']
        assert saved['state'] == 'complete' and not saved['prepare_report'] and saved['report_id'] is None
        assert client.get(report_url(case)).status_code == 404
    with ThreadPoolExecutor(3) as executor:
        responses = list(executor.map(lambda _: client.post(url + '/analyze', json={**body, 'prepare_report': True}), range(3)))
    assert all(r.status_code == 202 and r.json()['prepare_report'] and r.json()['run_id'] == queue['run_id'] for r in responses)
    assert client.post(url + '/analyze', json=body).json()['prepare_report']
    if approval_stage != 'complete':
        run = run or claim(pool)
        asyncio.run(worker.execute(run))
    saved = client.get(url).json()['analysis']
    report = client.get(report_url(case)).json()
    assert saved['report_id'] == report['id'] and saved['result'] == report['assessment']
    assert saved['run_id'] == report['run_id'] == queue['run_id']
    assert [(e['action'], e['actor']) for e in events(client, case) if e['action'] in ('analysis_completed', 'report_generated')] == [
        ('analysis_completed', 'system'), ('report_generated', 'system')]
    assert client.post(report_url(case), json=body).status_code == 200
    assert '₹5,000.00' in client.get(report_url(case) + '?format=txt').text


def test_automatic_report_failure_keeps_assessment_and_allows_retry(client, monkeypatch):
    case = new_case(client, 'B')
    url = BASE + case['id']
    body = {'expected_revision': case['input_revision']}
    assert client.post(url + '/analyze', json={**body, 'prepare_report': True}).status_code == 202
    pool = client.app.state.pool
    original = reports.record

    def reject_system_audit(*args, actor=None, **kwargs):
        if actor == 'system':
            # Fail after the report row was inserted. The savepoint must
            # roll it back without rolling back the assessment.
            args[0].execute('SELECT 1 / 0')
        return original(*args, actor=actor, **kwargs)

    monkeypatch.setattr(reports, 'record', reject_system_audit)
    asyncio.run(AnalysisWorker(pool, client.app.state.extractor).execute(claim(pool)))
    saved = client.get(url).json()['analysis']
    assert saved['prepare_report'] and saved['state'] == 'complete' and saved['report_id'] is None
    assert saved['result']['category'] == 'High concern'
    assert client.get(report_url(case)).status_code == 404
    report = generate_report(client, case)
    assert client.get(url).json()['analysis']['report_id'] == report['id']
    assert [e['actor'] for e in events(client, case) if e['action'] == 'report_generated'] == ['user']


@pytest.mark.parametrize('clear_case', ['edit', 'reset'])
def test_approved_report_is_fenced_with_the_analysis(client, prepared, clear_case):
    case = new_case(client, 'B')
    url = BASE + case['id']
    body = {'expected_revision': case['input_revision']}
    assert client.post(url + '/analyze', json={**body, 'prepare_report': 'true'}).status_code == 422
    assert client.post(report_url(case), json={**body, 'prepare_report': True}).status_code == 422
    assert client.post(url + '/analyze', json={**body, 'prepare_report': True}).status_code == 202
    pool = client.app.state.pool
    run = claim(pool)
    with TestClient(create_app(prepared, worker_enabled=False)) as other:
        other.get('/api/v1/transactions')
        assert other.post(url + '/analyze', json={**body, 'prepare_report': True}).status_code == 404
        assert other.get(report_url(case)).status_code == 404
    if clear_case == 'edit':
        assert client.patch(url + '/context', json={**body, 'knows_sender': 'yes'}).json()['analysis'] is None
        assert client.post(url + '/analyze', json={**body, 'prepare_report': True}).status_code == 409
    else:
        assert client.post('/api/v1/demo/reset').status_code == 200
    asyncio.run(AnalysisWorker(pool, client.app.state.extractor).execute(run))
    assert client.get(report_url(case)).status_code == (409 if clear_case == 'edit' else 404)
    assert all(e['action'] != 'report_generated' for e in events(client, case))


def test_complete_report_utf8_and_idempotency(client):
    case = report_case(client)
    url = report_url(case)
    assert client.get(url).status_code == 404
    report = generate_report(client, case)
    assert report['transaction'] == case['transaction']
    assert report['user_statements'] == case['context']
    assert report['evidence'][0]['text'] == case['evidence'][0]['confirmed_text']
    assert report['extracted_signals'] and report['unknowns']
    assert all(s['evidence_id'] == case['evidence'][0]['id'] for s in report['extracted_signals'])
    assert report['assessment']['category'] == 'Needs verification'
    assert report['assessment']['provider_mode'] == 'fixture'
    assert report['generated_at'] and report['id'] and report['status_at_generation'] == 'Open'
    assert client.get(url).json() == report
    again = client.post(url, json={'expected_revision': case['input_revision']})
    assert again.status_code == 200 and again.json() == report
    txt = client.get(url + '?format=txt')
    assert txt.status_code == 200
    assert txt.headers['content-type'] == 'text/plain; charset=utf-8'
    assert txt.headers['cache-control'] == 'no-store'
    assert txt.headers['x-content-type-options'] == 'nosniff'
    assert txt.headers['content-disposition'] == f'attachment; filename="bytebot-report-{report["id"]}.txt"'
    text = txt.content.decode('utf-8')
    for value in (report['id'], report['generated_at'], case['transaction']['reference'],
                  '₹5,000.00', report['evidence'][0]['text'], 'SYNTHETIC EXTRACTION FIXTURE',
                  'UNKNOWNS AND LIMITATIONS', 'RECOMMENDED NEXT STEPS', 'VALIDATED EXTRACTED SIGNALS'):
        assert value in text
    for f in report['assessment']['findings']:
        assert f['text'] in text and f['source'] in text and f['reference'] in text
    assert client.get(url + '?format=pdf').status_code == 422
    assert len([e for e in events(client, case) if e['action'] == 'report_generated']) == 1


def test_status_lifecycle_concurrency_and_report_immutability(client):
    case = report_case(client, 'D')
    report = generate_report(client, case)
    url = '/api/v1/incidents/' + case['id'] + '/status'
    revision = 0
    for value in STATUSES:
        response = client.patch(url, json={'status': value, 'expected_status_revision': revision})
        assert response.status_code == 200, response.text
        if value != 'Open':
            revision += 1
        assert response.json()['status_revision'] == revision
        reopened = client.post('/api/v1/investigations', json={'transaction_id': case['transaction_id']}).json()
        assert reopened['case_status'] == value and reopened['status_revision'] == revision
        assert reopened['input_revision'] == case['input_revision']
        assert reopened['analysis']['result'] == report['assessment']
        assert client.get(report_url(case)).json() == report
    assert len([e for e in events(client, case) if e['action'] == 'status_updated']) == 5
    with ThreadPoolExecutor(2) as pool:
        responses = list(pool.map(lambda value: client.patch(url, json={'status': value, 'expected_status_revision': revision}), ['Open', 'Reported']))
    assert sorted(r.status_code for r in responses) == [200, 409]
    stale = next(r for r in responses if r.status_code == 409)
    assert stale.json()['error']['code'] == 'stale_status'
    for payload in ({'status': 'Sent', 'expected_status_revision': 0}, {'status': 'Open', 'expected_status_revision': True},
                    {'status': 'Open', 'expected_status_revision': -1}, {'status': 'Open', 'expected_status_revision': 0, 'text': 'extra'}):
        assert client.patch(url, json=payload).status_code == 422


def test_list_is_owned_includes_unanalyzed_and_drops_stale_category(client, prepared):
    client.get('/api/v1/transactions')
    assert client.get('/api/v1/incidents').json() == {'incidents': []}
    case = report_case(client, 'D')
    other_case = new_case(client, index=1)
    rows = client.get('/api/v1/incidents').json()['incidents']
    assert [r['id'] for r in rows] == [other_case['id'], case['id']]
    assert rows[0]['category'] is None and rows[1]['category'] == 'No strong indicators found'
    client.patch(BASE + case['id'] + '/context', json={'knows_sender': 'unknown', 'expected_revision': case['input_revision']})
    assert all(r['category'] is None for r in client.get('/api/v1/incidents').json()['incidents'])
    with TestClient(create_app(prepared, worker_enabled=False)) as other:
        assert other.get('/api/v1/incidents').status_code == 404
        other.get('/api/v1/transactions')
        assert other.get('/api/v1/incidents').json() == {'incidents': []}


@pytest.mark.parametrize('operation', ['context', 'edit', 'delete', 'add'])
def test_input_changes_physically_erase_reports(client, operation):
    case = report_case(client)
    report = generate_report(client, case)
    # No-op input writes must preserve both result and report.
    same = client.patch(BASE + case['id'] + '/context', json={**case['context'], 'expected_revision': case['input_revision']})
    assert same.status_code == 200 and same.json()['input_revision'] == case['input_revision']
    evidence = case['evidence'][0]
    assert client.patch(BASE + case['id'] + '/evidence/' + evidence['id'], json={'text': evidence['confirmed_text'], 'confirmed': True, 'expected_revision': case['input_revision']}).status_code == 200
    assert client.get(report_url(case)).json() == report
    if operation == 'context':
        response = client.patch(BASE + case['id'] + '/context', json={'already_sent_money': 'yes', 'expected_revision': case['input_revision']})
    elif operation == 'edit':
        response = client.patch(BASE + case['id'] + '/evidence/' + evidence['id'], json={'text': 'Corrected synthetic text', 'confirmed': True, 'expected_revision': case['input_revision']})
    elif operation == 'delete':
        response = client.delete(BASE + case['id'] + '/evidence/' + evidence['id'] + f'?expected_revision={case["input_revision"]}')
    else:
        response = client.post(BASE + case['id'] + '/evidence', json={'type': 'call_summary', 'text': 'A synthetic call', 'expected_revision': case['input_revision']})
    assert response.status_code in (200, 201, 204), response.text
    assert client.get(report_url(case)).status_code == 409
    assert client.get(report_url(case) + '?format=txt').status_code == 409
    assert client.get(BASE + case['id']).json()['analysis'] is None
    assert client.post(report_url(case), json={'expected_revision': case['input_revision']}).json()['error']['code'] == 'stale_revision'
    with client.app.state.pool.connection() as conn:
        assert conn.execute('SELECT count(*) AS n FROM incident_reports').fetchone()['n'] == 0
        assert conn.execute('SELECT count(*) AS n FROM risk_assessments').fetchone()['n'] == 0
        assert conn.execute('SELECT count(*) AS n FROM extracted_signals').fetchone()['n'] == 0
    current = client.get(BASE + case['id']).json()
    run_case(client, current)
    fresh = generate_report(client, current)
    assert fresh['id'] != report['id'] and fresh['input_revision'] > report['input_revision']


def test_concurrent_report_generation_and_input_lock(client):
    case = report_case(client)
    with ThreadPoolExecutor(4) as executor:
        responses = list(executor.map(lambda _: client.post(report_url(case), json={'expected_revision': case['input_revision']}), range(4)))
    assert sorted(r.status_code for r in responses) == [200, 200, 200, 201]
    assert len({r.json()['id'] for r in responses}) == 1
    # Hold the input writer lock, launch generation, then invalidate before release.
    started = Event()
    with ThreadPoolExecutor(1) as executor:
        with client.app.state.pool.connection() as conn:
            owner = conn.execute('SELECT owner_id FROM investigations WHERE id=%s', (case['id'],)).fetchone()['owner_id']
            owned_case(conn, owner, case['id'])
            def request():
                started.set()
                return client.post(report_url(case), json={'expected_revision': case['input_revision']})
            future = executor.submit(request)
            assert started.wait(2)
            bump(conn, case['id'])
        assert future.result(timeout=5).status_code == 409
    with client.app.state.pool.connection() as conn:
        assert conn.execute('SELECT count(*) AS n FROM incident_reports').fetchone()['n'] == 0
    # Reverse ordering: report created under lock, then a waiting edit deletes it.
    current = client.get(BASE + case['id']).json()
    run_case(client, current)
    with ThreadPoolExecutor(1) as executor:
        with client.app.state.pool.connection() as conn:
            locked = owned_case(conn, owner, case['id'])
            generate(conn, locked)
            future = executor.submit(lambda: client.patch(BASE + case['id'] + '/context', json={'already_sent_money': 'yes', 'expected_revision': current['input_revision']}))
        assert future.result(timeout=5).status_code == 200
    assert client.get(report_url(case)).status_code == 409


@pytest.mark.parametrize('index', [1, 2])
def test_incomplete_report_wording_and_post_loss(client, index):
    case = new_case(client, 'E', index)
    case = client.patch(BASE + case['id'] + '/context', json={'already_sent_money': 'yes', 'expected_revision': case['input_revision']}).json()
    run_case(client, case)
    report = generate_report(client, case)
    status = case['transaction']['status']
    assert report['assessment']['category'] == 'Unable to assess'
    assert status in report['transaction_explanation']
    assert 'Recovery cannot be promised' in report['assessment']['recommendations'][0]
    assert any(f['kind'] == 'collect_approval' for f in report['assessment']['findings'])
    text = client.get(report_url(case) + '?format=txt').text
    assert status in text
    assert ('Funds are not confirmed as received.' if index == 1 else 'Funds were not received.') in text
    assert 'Do not spend' not in text


def test_audit_actions_privacy_and_payload_allowlist(client, caplog):
    case = new_case(client, 'A')
    value = '<script>window.evidenceExecuted=true</script>\n\nmy OTP: 739182\n\npassword=canary-secret'
    result = client.post(BASE + case['id'] + '/evidence', json={'type': 'call_summary', 'text': value, 'expected_revision': case['input_revision']})
    assert result.status_code == 201
    item = result.json()['evidence']
    current = client.get(BASE + case['id']).json()
    # No-op resubmission does not add an update event.
    client.patch(BASE + case['id'] + '/evidence/' + item['id'], json={'text': item['confirmed_text'], 'confirmed': True, 'expected_revision': current['input_revision']})
    run_case(client, current)
    report = generate_report(client, current)
    text = client.get(report_url(current) + '?format=txt').text
    for canary in ('739182', 'canary-secret'):
        assert canary not in json.dumps(report) + text + caplog.text
    assert '<script>' in text  # inert plain-text export; React must escape this on review.
    audit = events(client, case)
    assert [e['action'] for e in audit] == ['investigation_created', 'context_updated', 'evidence_submitted', 'evidence_submitted', 'action_executed', 'analysis_completed', 'report_generated']
    assert all(e['created_at'].tzinfo and e['actor'] in ('user', 'system', 'agent') for e in audit)
    raw = json.dumps([e['metadata'] for e in audit])
    for forbidden in ('739182', 'canary-secret', '<script>', 'different.demo@upi', 'confirmed_text', 'filename'):
        assert forbidden not in raw
    with client.app.state.pool.connection() as conn:
        for invalid in ({'evidence_id': uuid4(), 'text': value}, {'evidence_id': value}):
            with pytest.raises(ValueError):
                record(conn, case['id'], 'evidence_removed', **invalid)
        stored = str(conn.execute('SELECT snapshot FROM incident_reports').fetchall()) + str(conn.execute('SELECT metadata FROM audit_events').fetchall())
        assert '739182' not in stored and 'canary-secret' not in stored
    response = client.delete(BASE + case['id'] + '/evidence/' + item['id'] + f'?expected_revision={current["input_revision"]}')
    assert response.status_code == 204
    assert events(client, case)[-1]['action'] == 'evidence_removed'
    assert all('<script>' not in str(e) for e in events(client, case))


def test_foreign_and_absent_sessions_no_side_effects(client, prepared):
    case = report_case(client)
    generate_report(client, case)
    before = events(client, case)
    with TestClient(create_app(prepared, worker_enabled=False)) as other:
        for initialized in (False, True):
            if initialized:
                other.get('/api/v1/transactions')
            for method, suffix, payload in (
                ('GET', '/report', None), ('GET', '/report?format=txt', None),
                ('POST', '/report', {'expected_revision': case['input_revision']}),
            ):
                foreign = other.request(method, BASE + case['id'] + suffix, json=payload)
                unknown = other.request(method, BASE + str(uuid4()) + suffix, json=payload)
                assert foreign.status_code == unknown.status_code == 404
                assert foreign.json() == unknown.json()
                assert 'set-cookie' not in foreign.headers
            payload = {'status': 'Reported', 'expected_status_revision': 0}
            foreign = other.patch('/api/v1/incidents/' + case['id'] + '/status', json=payload)
            unknown = other.patch('/api/v1/incidents/' + str(uuid4()) + '/status', json=payload)
            assert foreign.status_code == unknown.status_code == 404 and foreign.json() == unknown.json()
    assert len(events(client, case)) == len(before)


def test_report_gating_validation_and_fallback(client):
    case = new_case(client)
    url = report_url(case)
    assert client.get(url).json()['error']['code'] == 'analysis_required'
    assert client.post(url, json={'expected_revision': 0}).status_code == 409
    for value in (True, -1, '0'):
        assert client.post(url, json={'expected_revision': value}).status_code == 422
    case = client.patch(BASE + case['id'] + '/context', json={'expected_payment': 'no', 'repayment_requested': 'yes', 'expected_revision': 0}).json()
    client.post(BASE + case['id'] + '/evidence', json={'type': 'message', 'text': 'Unknown fixture evidence', 'expected_revision': case['input_revision']})
    case = client.get(BASE + case['id']).json()
    run_case(client, case)
    report = generate_report(client, case)
    assert report['assessment']['extraction_status'] == 'unavailable'
    assert report['notices'] and report['assessment']['limitations']


def test_report_uses_reviewed_ocr_only(prepared):
    from synthetic_images import screenshot
    class SyntheticOCR:
        def extract(self, image):
            return 'Uncorrected OCR text. OTP: 739182', None
    with TestClient(create_app(prepared, ocr_adapter=SyntheticOCR(), extraction_provider=FixtureProvider(), worker_enabled=False)) as client:
        case = new_case(client, 'D')
        uploaded = client.post(BASE + case['id'] + '/evidence', data={'expected_revision': str(case['input_revision'])},
            files={'file': ('private-739182.png', screenshot(), 'image/png')})
        assert uploaded.status_code == 201
        item = uploaded.json()['evidence']
        revision = uploaded.json()['input_revision']
        assert client.post(BASE + case['id'] + '/analyze', json={'expected_revision': revision}).status_code == 409
        corrected = client.patch(BASE + case['id'] + '/evidence/' + item['id'], json={
            'text': 'Reviewed synthetic screenshot statement.', 'confirmed': True, 'expected_revision': revision})
        assert corrected.status_code == 200
        case = client.get(BASE + case['id']).json()
        run_case(client, case)
        report = generate_report(client, case)
        assert report['evidence'] == [{'id': item['id'], 'type': 'screenshot',
            'source': 'User-reviewed local OCR', 'text': 'Reviewed synthetic screenshot statement.'}]
        combined = json.dumps(report) + client.get(report_url(case) + '?format=txt').text
        for forbidden in ('739182', 'private-', 'Uncorrected OCR', 'ocr_text', 'metadata'):
            assert forbidden not in combined
        # Unread evidence and no further questions hand the case to a person.
        assert [e['action'] for e in events(client, case)][-4:] == [
            'evidence_updated', 'escalation_opened', 'analysis_completed', 'report_generated']


def test_phase03_upgrade_backfill_repeatability(prepared):
    # Create populated Phase 03 using current code, then retain only its historical schema.
    with TestClient(create_app(prepared, extraction_provider=FixtureProvider(), worker_enabled=False)) as client:
        case = report_case(client)
        cookie = client.cookies.get('bytebot_session')
    with psycopg.connect(prepared) as conn:
        facts = conn.execute('SELECT created_at FROM investigations WHERE id=%s', (case['id'],)).fetchone()
        conn.execute('DROP TABLE incident_reports,audit_events')
        conn.execute('ALTER TABLE investigations DROP COLUMN case_status,DROP COLUMN status_revision')
        # The ledger columns belong to the dropped audit table, so that migration is re-applied too.
        conn.execute("DELETE FROM schema_migrations WHERE version IN ('004_reports_and_follow_up.sql','012_ledger_hash_chain.sql')")
    migrate(prepared); migrate(prepared); seed(prepared); seed(prepared)
    with TestClient(create_app(prepared, worker_enabled=False)) as client:
        client.cookies.set('bytebot_session', cookie)
        saved = client.get(BASE + case['id']).json()
        assert saved['case_status'] == 'Open' and saved['status_revision'] == 0
        assert saved['evidence'] == case['evidence'] and saved['context'] == case['context']
        assert saved['analysis']['state'] == 'complete'
        audit = events(client, case)
        assert [e['action'] for e in audit] == ['investigation_created', 'evidence_submitted', 'analysis_completed']
        assert all(e['metadata']['backfilled'] is True for e in audit)
        assert audit[0]['created_at'] == facts[0]
        with client.app.state.pool.connection() as conn:
            evidence_at = conn.execute('SELECT created_at FROM evidence WHERE id=%s', (case['evidence'][0]['id'],)).fetchone()['created_at']
            analysis_at = conn.execute('SELECT updated_at FROM analysis_runs WHERE id=%s', (saved['analysis']['run_id'],)).fetchone()['updated_at']
        assert audit[1]['created_at'] == evidence_at and audit[2]['created_at'] == analysis_at
        generate_report(client, saved)
