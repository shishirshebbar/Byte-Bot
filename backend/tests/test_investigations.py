from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from threading import Event
from uuid import UUID, uuid4
import tempfile
import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from bytebot.main import create_app
from bytebot.migrate import migrate, MIGRATIONS
from bytebot.seeds import seed
from bytebot.redaction import redact
from bytebot.ocr import OCRAdapter, decode_image, EvidenceError, FILE_LIMIT, PIXEL_LIMIT
from bytebot.investigation_store import confirmed_evidence
from synthetic_images import screenshot


class FixedOCR:
    def extract(self, image):
        return 'Return INR 5000. OTP: 739182', None


def start(client, index=0):
    transaction = client.get('/api/v1/transactions').json()['transactions'][index]
    response = client.post('/api/v1/investigations', json={'transaction_id': transaction['id']})
    assert response.status_code == 201, response.text
    return response.json()


def path(case):
    return '/api/v1/investigations/' + case['id']


def text(client, case, revision=0, value='Please return INR 5000', kind='message'):
    return client.post(path(case) + '/evidence', json={'type': kind, 'text': value, 'expected_revision': revision})


def upload(client, case, revision=0, image=None, media='image/png'):
    return client.post(path(case) + '/evidence', data={'expected_revision': str(revision)}, files={'file': ('ignored-OTP-739182.png', screenshot() if image is None else image, media)})


def test_context_resume_statuses_and_noop(prepared):
    with TestClient(create_app(prepared)) as client:
        cases = [start(client, i) for i in range(3)]
        for case, status in zip(cases, ['successful', 'pending', 'failed']):
            assert case['transaction']['status'] == status
            assert case['context']['expected_payment'] == 'unknown'
            assert case['context']['contact_channels'] is None
            assert client.post('/api/v1/investigations', json={'transaction_id': case['transaction_id']}).json()['id'] == case['id']
        case = cases[0]
        changes = {'expected_revision': 0, 'expected_payment': 'no', 'contact_channels': [], 'pressure_tactics': None,
                   'requested_vpa': 'OTP: 739182', 'already_sent_money': 'unknown'}
        response = client.patch(path(case) + '/context', json=changes)
        assert response.status_code == 200
        saved = response.json()
        assert saved['input_revision'] == 1 and '739182' not in response.text
        assert saved['context']['contact_channels'] == []
        assert saved['context']['pressure_tactics'] is None
        changes['expected_revision'] = 1
        assert client.patch(path(case) + '/context', json=changes).json()['input_revision'] == 1
        assert client.patch(path(case) + '/context', json={**changes, 'expected_revision': 0}).status_code == 409
        for invalid in [{'expected_payment': 'maybe'}, {'expected_payment': None}, {'contact_channels': ['fax']}, {'extra': 'data'}, {'expected_revision': 1.0}]:
            assert client.patch(path(case) + '/context', json={'expected_revision': 1, **invalid}).status_code == 422
        cookie = client.cookies.get('bytebot_session')
    with TestClient(create_app(prepared)) as restarted:
        restarted.cookies.set('bytebot_session', cookie)
        assert restarted.get(path(case)).json() == saved


def test_evidence_lifecycle_redaction_and_gating(prepared, caplog, monkeypatch):
    # Multipart uploads must not invoke filesystem-backed upload helpers.
    def forbidden(*args, **kwargs):
        raise AssertionError('Upload attempted to create a temporary file')
    monkeypatch.setattr(tempfile, 'TemporaryFile', forbidden)
    monkeypatch.setattr('starlette.formparsers.SpooledTemporaryFile', forbidden)
    with TestClient(create_app(prepared, FixedOCR())) as client:
        case = start(client)
        first = text(client, case, value='Please send OTP: 739182. Return to demo@upi')
        assert first.status_code == 201 and '739182' not in first.text
        call = text(client, case, 1, 'Caller said PIN is 842951', 'call_summary')
        assert call.status_code == 201 and '842951' not in call.text
        # >1 MiB used to spill to disk with the framework's default parser.
        result = upload(client, case, 2, screenshot() + b'\0' * (1024 * 1024)).json()
        item = result['evidence']
        assert result['input_revision'] == 3 and item['review_state'] == 'needs_review'
        assert '739182' not in str(result) and 'ignored' not in str(result)
        with psycopg.connect(prepared, row_factory=psycopg.rows.dict_row) as conn:
            owner = conn.execute('SELECT owner_id FROM investigations WHERE id=%s', (case['id'],)).fetchone()['owner_id']
            assert len(confirmed_evidence(conn, owner, UUID(case['id']))) == 2
        confirm_path = path(case) + '/evidence/' + item['id']
        assert client.patch(confirm_path, json={'text': ' ', 'confirmed': True, 'expected_revision': 3}).status_code == 422
        response = client.patch(confirm_path, json={'text': 'OTP: 673821. Please return funds', 'confirmed': True, 'expected_revision': 3})
        assert response.status_code == 200 and response.json()['input_revision'] == 4
        assert '673821' not in response.text
        same = response.json()['evidence']['confirmed_text']
        assert client.patch(confirm_path, json={'text': same, 'confirmed': True, 'expected_revision': 4}).json()['input_revision'] == 4
        assert client.patch(confirm_path, json={'text': 'changed', 'confirmed': True, 'expected_revision': 3}).status_code == 409
        with psycopg.connect(prepared, row_factory=psycopg.rows.dict_row) as conn:
            assert len(confirmed_evidence(conn, owner, UUID(case['id']))) == 3
            durable = str(conn.execute('SELECT * FROM evidence').fetchall())
            assert not any(secret in durable for secret in ('739182', '842951', '673821', 'ignored-OTP'))
        assert client.delete(confirm_path + '?expected_revision=3').status_code == 409
        assert client.delete(confirm_path + '?expected_revision=4').status_code == 204
        with psycopg.connect(prepared) as conn:
            assert conn.execute('SELECT id FROM evidence WHERE id=%s', (item['id'],)).fetchone() is None
        assert len(client.get(path(case)).json()['evidence']) == 2
    assert not any(secret in caplog.text for secret in ('739182', '842951', '673821'))


def test_foreign_and_unknown_resources(prepared):
    with TestClient(create_app(prepared, FixedOCR())) as a, TestClient(create_app(prepared, FixedOCR())) as b, TestClient(create_app(prepared)) as anonymous:
        ca, cb = start(a), start(b)
        ea = text(a, ca).json()['evidence']['id']
        eb = text(b, cb).json()['evidence']['id']
        for client in (b, anonymous):
            assert client.post('/api/v1/investigations', json={'transaction_id': ca['transaction_id']}).status_code == 404
            foreign = client.get(path(ca))
            unknown = client.get('/api/v1/investigations/' + str(uuid4()))
            assert foreign.status_code == unknown.status_code == 404 and foreign.json() == unknown.json()
            assert client.patch(path(ca) + '/context', json={'expected_revision': 0}).status_code == 404
            assert text(client, ca).status_code == 404
            assert upload(client, ca).status_code == 404
            assert client.patch(path(ca) + '/evidence/' + ea, json={'text': 'test', 'confirmed': True, 'expected_revision': 0}).status_code == 404
            assert client.delete(path(ca) + '/evidence/' + ea + '?expected_revision=0').status_code == 404
        assert not anonymous.cookies
        for eid in (eb, str(uuid4())):
            assert a.patch(path(ca) + '/evidence/' + eid, json={'text': 'test', 'confirmed': True, 'expected_revision': 0}).status_code == 404
            assert a.delete(path(ca) + '/evidence/' + eid + '?expected_revision=0').status_code == 404
        assert a.get(path(ca)).json()['input_revision'] == 1
        assert len(a.get(path(ca)).json()['evidence']) == 1
        assert a.get('/api/v1/investigations/invalid').status_code == 422


def test_upload_validation_and_chunked_limits(prepared):
    with TestClient(create_app(prepared, FixedOCR())) as client:
        case = start(client)
        for image, media, status in [(b'bad', 'image/png', 422), (screenshot(), 'image/jpeg', 415),
                                      (b'<svg/>', 'image/svg+xml', 415), (b'x' * (FILE_LIMIT + 1), 'image/png', 413),
                                      (screenshot(False, size=(4001, 4000)), 'image/png', 413)]:
            response = upload(client, case, image=image, media=media)
            assert response.status_code == status, response.text
        animated = BytesIO()
        Image.new('RGB', (10, 10), 'white').save(animated, format='PNG', save_all=True, append_images=[Image.new('RGB', (10, 10), 'black')], duration=10)
        assert upload(client, case, image=animated.getvalue()).status_code == 415
        exact = screenshot(False, size=(4000, 4000))
        rgb, meta = decode_image(exact, 'image/png')
        assert meta['width'] * meta['height'] == PIXEL_LIMIT
        rgb.close()
        for content, media, expected in [(b'not-json', 'application/json', 422), (b'text', 'text/plain', 415),
                                         (b'bad', 'multipart/form-data; boundary=abc', 422)]:
            assert client.post(path(case) + '/evidence', content=content, headers={'content-type': media}).status_code == expected
        request = httpx.Request('POST', 'http://test/upload', files={'file': ('test.png', screenshot(), 'image/png')}, data={'expected_revision': '0'})
        payload = request.read()
        response = client.post(path(case) + '/evidence', content=(payload[i:i+333] for i in range(0, len(payload), 333)), headers={'content-type': request.headers['content-type']})
        assert response.status_code == 201, response.text
        oversized = client.post(path(case) + '/evidence', content=(b'x' * 1024 * 1024 for _ in range(7)), headers={'content-type': 'multipart/form-data; boundary=test'})
        assert oversized.status_code == 413


@pytest.mark.parametrize('notice', ['unreadable', 'ocr_unavailable'])
def test_ocr_fallback_is_editable(prepared, notice):
    class Fallback:
        def extract(self, image):
            return '', notice
    with TestClient(create_app(prepared, Fallback())) as client:
        case = start(client)
        result = upload(client, case).json()
        item = result['evidence']
        assert item['review_state'] == 'ocr_failed' and item['notice'] == notice
        assert client.get(path(case)).json()['evidence'][0]['id'] == item['id']
        response = client.patch(path(case) + '/evidence/' + item['id'], json={'text': 'Manually transcribed message', 'confirmed': True, 'expected_revision': 1})
        assert response.json()['evidence']['review_state'] == 'confirmed'


def test_concurrent_creation_edits_and_ocr_revision(prepared):
    entered, release = Event(), Event()
    class SlowOCR:
        def extract(self, image):
            entered.set()
            assert release.wait(5)
            return 'Synthetic text', None
    with TestClient(create_app(prepared, SlowOCR())) as client:
        transaction = client.get('/api/v1/transactions').json()['transactions'][0]
        with ThreadPoolExecutor(2) as executor:
            results = list(executor.map(lambda _: client.post('/api/v1/investigations', json={'transaction_id': transaction['id']}), range(2)))
            assert sorted(r.status_code for r in results) == [200, 201]
            assert len({r.json()['id'] for r in results}) == 1
            case = results[0].json()
            edits = list(executor.map(lambda answer: client.patch(path(case) + '/context', json={'expected_revision': 0, 'expected_payment': answer}), ['yes', 'no']))
            assert sorted(r.status_code for r in edits) == [200, 409]
            future = executor.submit(upload, client, case, 1)
            assert entered.wait(5)
            assert client.patch(path(case) + '/context', json={'expected_revision': 1, 'knows_sender': 'yes'}).status_code == 200
            release.set()
            assert future.result().status_code == 409
            assert client.get(path(case)).json()['evidence'] == []


def test_limits_and_database_owner_constraint(prepared):
    with TestClient(create_app(prepared)) as a, TestClient(create_app(prepared)) as b:
        case = start(a)
        other = start(b)
        for i in range(20):
            assert text(a, case, i).status_code == 201
        assert text(a, case, 20).status_code == 422
        assert text(a, case, 20, value='x'*10001).status_code == 422
        assert text(a, case, 20, kind='invalid').status_code == 422
        with psycopg.connect(prepared) as conn:
            owner = conn.execute('SELECT owner_id FROM investigations WHERE id=%s', (case['id'],)).fetchone()[0]
            with pytest.raises(psycopg.errors.ForeignKeyViolation):
                conn.execute('INSERT INTO investigations(id,owner_id,transaction_id) VALUES(%s,%s,%s)', (uuid4(), owner, other['transaction_id']))


def test_phase01_upgrade_preserves_sessions(prepared, tmp_path):
    with psycopg.connect(prepared) as conn:
        conn.execute('DROP SCHEMA public CASCADE')
        conn.execute('CREATE SCHEMA public')
    original = MIGRATIONS / '001_foundation.sql'
    (tmp_path / original.name).write_text(original.read_text())
    migrate(prepared, tmp_path)
    seed(prepared, include_intelligence=False)
    with TestClient(create_app(prepared)) as client:
        before = client.get('/api/v1/transactions').json()
        migrate(prepared)
        migrate(prepared)
        seed(prepared)
        seed(prepared)
        assert client.get('/api/v1/transactions').json() == before
        assert client.post('/api/v1/investigations', json={'transaction_id': before['transactions'][0]['id']}).status_code == 201


@pytest.mark.parametrize('value', ['OTP: 739182', 'my UPI PIN is 739182', 'password=canary-secret', 'CVV 739182', '739182 is my OTP', '739182 OTP', 'OTP:\n739182', 'password:\ncanary-secret', 'OＴＰ: 739182', 'OT\u200bP: 739182', 'remote-access code 739182'])
def test_redaction_variants(value):
    result = redact(value)
    assert '739182' not in result and 'canary-secret' not in result
    assert redact(result) == result


def test_ocr_reader_failure_and_busy_fallback():
    image = Image.new('RGB', (20, 20), 'white')
    adapter = OCRAdapter()
    class BrokenReader:
        def readtext(self, *args, **kwargs):
            raise RuntimeError('private image data')
    adapter.reader = BrokenReader()
    assert adapter.extract(image) == ('', 'ocr_unavailable')
    adapter.lock.acquire()
    try:
        assert adapter.extract(image) == ('', 'ocr_unavailable')
    finally:
        adapter.lock.release()
        image.close()
