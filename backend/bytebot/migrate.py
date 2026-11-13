import hashlib
from pathlib import Path
import psycopg

MIGRATIONS = Path(__file__).parent / "migrations"


def migrate(url, directory=MIGRATIONS):
    with psycopg.connect(url) as conn:
        # One transaction and lock cover tracking-table creation and all pending DDL.
        conn.execute("SELECT pg_advisory_xact_lock(82740101)")
        conn.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
            version text PRIMARY KEY, checksum text NOT NULL,
            applied_at timestamptz NOT NULL DEFAULT now())""")
        applied = dict(conn.execute("SELECT version, checksum FROM schema_migrations").fetchall())
        paths = sorted(directory.glob("[0-9]*_*.sql"))
        if set(applied) - {p.name for p in paths}:
            raise RuntimeError("An applied migration is missing")
        for path in paths:
            sql = path.read_text()
            checksum = hashlib.sha256(sql.encode()).hexdigest()
            if path.name in applied:
                if applied[path.name] != checksum:
                    raise RuntimeError("An applied migration has changed")
                continue
            conn.execute(sql)
            conn.execute("INSERT INTO schema_migrations (version, checksum) VALUES (%s, %s)",
                         (path.name, checksum))
