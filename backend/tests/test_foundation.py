from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
import hashlib
import psycopg
import pytest
from fastapi.testclient import TestClient
from bytebot.main import create_app
from bytebot.migrate import migrate
from bytebot.seeds import seed, TEMPLATES


def snapshot(url, table):
    with psycopg.connect(url) as conn:
        return conn.execute(f'SELECT * FROM {table} ORDER BY 1').fetchall()


def test_repeatability_and_concurrent_migration(prepared):
    before = snapshot(prepared, 'transaction_templates')
    versions = snapshot(prepared, 'schema_migrations')
    with ThreadPoolExecutor(2) as executor:
        list(executor.map(migrate, [prepared, prepared]))
    seed(prepared)
    seed(prepared)
    assert snapshot(prepared, 'transaction_templates') == before
    assert snapshot(prepared, 'schema_migrations') == versions
    assert len(before) == len(TEMPLATES) == 8


def test_migration_failure_and_checksum(prepared, tmp_path):
    sources = sorted(Path('backend/bytebot/migrations').glob('[0-9]*_*.sql'))
    source = sources[0]
    for item in sources:
        (tmp_path / item.name).write_text(item.read_text())
    pending = tmp_path / '999_bad.sql'
    pending.write_text('CREATE TABLE should_rollback(id int); SELECT missing_column;')
    with pytest.raises(psycopg.Error):
        migrate(prepared, tmp_path)
    with psycopg.connect(prepared) as conn:
        assert conn.execute("SELECT to_regclass('should_rollback')").fetchone()[0] is None
    assert len(snapshot(prepared, 'schema_migrations')) == len(sources)
    pending.unlink()
    (tmp_path / source.name).write_text('-- changed')
    with pytest.raises(RuntimeError, match='changed'):
        migrate(prepared, tmp_path)


def test_transactions_and_ownership(prepared):
    app = create_app(prepared)
    with TestClient(app) as a, TestClient(create_app(prepared)) as b:
        assert a.get('/api/v1/health').json() == {'status': 'ready', 'database': 'available'}
        assert not a.cookies
        result = a.get('/api/v1/transactions')
        assert result.status_code == 200
        assert 'HttpOnly' in result.headers['set-cookie']
        assert 'SameSite=lax' in result.headers['set-cookie']
        assert 'no-store' in result.headers['cache-control']
        rows = result.json()['transactions']
        assert [r['status'] for r in rows[:3]] == ['successful', 'pending', 'failed']
        assert len(rows) == 8 and all(r['status'] == 'successful' for r in rows[3:])
        assert rows[0]['amount_paise'] == 500000
        assert all(r['occurred_at'].endswith(('Z', '+00:00')) for r in rows)
        assert a.get('/api/v1/transactions').json()['transactions'] == rows
        for row in rows:
            assert a.get('/api/v1/transactions/' + row['id']).json() == row
        others = b.get('/api/v1/transactions').json()['transactions']
        assert {r['id'] for r in rows}.isdisjoint({r['id'] for r in others})
        foreign = b.get('/api/v1/transactions/' + rows[0]['id'])
        unknown = b.get('/api/v1/transactions/' + str(uuid4()))
        assert foreign.status_code == unknown.status_code == 404
        assert foreign.json() == unknown.json() == {'error': {'code': 'not_found', 'message': 'Transaction not found.'}}
        invalid = a.get('/api/v1/transactions/not-a-uuid')
        assert invalid.status_code == 422 and invalid.json()['error']['code'] == 'invalid_input'
        cookie = a.cookies.get('bytebot_session')
        with psycopg.connect(prepared) as conn:
            hashes = conn.execute('SELECT token_hash FROM demo_sessions').fetchall()
            assert (hashlib.sha256(cookie.encode()).hexdigest(),) in hashes
            assert (cookie,) not in hashes
        seed(prepared)
        assert a.get('/api/v1/transactions').json()['transactions'] == rows
    with TestClient(create_app(prepared)) as restarted:
        restarted.cookies.set('bytebot_session', cookie)
        assert restarted.get('/api/v1/transactions').json()['transactions'] == rows


def test_invalid_cookie_and_first_detail(prepared):
    with TestClient(create_app(prepared)) as a:
        a.cookies.set('bytebot_session', 'invalid', domain='testserver.local', path='/')
        result = a.get('/api/v1/transactions/' + str(uuid4()))
        assert result.status_code == 404
        assert 'set-cookie' in result.headers
        assert len(a.get('/api/v1/transactions').json()['transactions']) == len(TEMPLATES)
        assert len(snapshot(prepared, 'demo_users')) == 1


def test_missing_templates_atomicity(prepared):
    with psycopg.connect(prepared) as conn:
        conn.execute('DELETE FROM transaction_templates')
    with TestClient(create_app(prepared)) as client:
        assert client.get('/api/v1/transactions').status_code == 503
        assert not client.cookies
    assert not snapshot(prepared, 'demo_users')


def test_constraints(prepared):
    with TestClient(create_app(prepared)) as client:
        client.get('/api/v1/transactions')
    with psycopg.connect(prepared) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            with conn.transaction():
                conn.execute("UPDATE transactions SET status='invented'")
        with pytest.raises(psycopg.errors.UniqueViolation):
            with conn.transaction():
                conn.execute('INSERT INTO transactions SELECT %s, owner_id, template_key, direction, amount_paise, currency, sender_name, sender_vpa, receiver_vpa, occurred_at, status, reference, source FROM transactions LIMIT 1', (uuid4(),))


def test_database_failure(prepared):
    class BrokenPool:
        def connection(self):
            raise psycopg.OperationalError('private database details')
    with TestClient(create_app(prepared), raise_server_exceptions=False) as client:
        original = client.app.state.pool
        client.app.state.pool = BrokenPool()
        for path in ('health', 'transactions'):
            response = client.get('/api/v1/' + path)
            assert response.status_code == 503
            assert 'private' not in response.text
        client.app.state.pool = original
