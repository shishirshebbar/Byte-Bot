import pytest
import psycopg
from psycopg.conninfo import conninfo_to_dict
from bytebot.settings import DATABASE_URL, TEST_DATABASE_URL
from bytebot.migrate import migrate
from bytebot.seeds import seed


@pytest.fixture(scope='session')
def db_url():
    target = conninfo_to_dict(TEST_DATABASE_URL)
    demo = conninfo_to_dict(DATABASE_URL)
    identity = lambda c: tuple(c.get(k) for k in ('host', 'port', 'dbname'))
    if identity(target) == identity(demo) or target.get('dbname') != 'bytebot_test':
        pytest.fail('Tests require the separate bytebot_test database')
    return TEST_DATABASE_URL


@pytest.fixture
def prepared(db_url):
    with psycopg.connect(db_url) as conn:
        conn.execute('DROP SCHEMA public CASCADE')
        conn.execute('CREATE SCHEMA public')
    migrate(db_url)
    seed(db_url)
    return db_url
