import hashlib
import secrets
from uuid import uuid4
from fastapi import HTTPException
from .seeds import FIELDS

COOKIE = "bytebot_session"


def lock_owner(conn, owner):
    """Serialize creation/reset before acquiring any case or run locks."""
    conn.execute('SELECT id FROM demo_users WHERE id=%s FOR UPDATE', (owner,)).fetchone()


def copy_transaction(conn, owner, template_key):
    return conn.execute(
        f'INSERT INTO transactions (id,owner_id,template_key,{FIELDS}) '
        f'SELECT %s,%s,template_key,{FIELDS} FROM transaction_templates WHERE template_key=%s '
        'ON CONFLICT (owner_id,template_key) DO NOTHING RETURNING id',
        (uuid4(), owner, template_key)).fetchone()


def find_owner(conn, token):
    if token and len(token) <= 128:
        found = conn.execute("SELECT owner_id FROM demo_sessions WHERE token_hash = %s",
                             (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if found:
            return found["owner_id"]
    return None


def get_owner(conn, token):
    owner = find_owner(conn, token)
    if owner is not None:
        return owner, None
    templates = conn.execute("SELECT template_key FROM transaction_templates ORDER BY template_key").fetchall()
    if not templates:
        raise HTTPException(503)
    owner = uuid4()
    token = secrets.token_urlsafe(32)
    conn.execute("INSERT INTO demo_users (id) VALUES (%s)", (owner,))
    conn.execute("INSERT INTO demo_sessions (token_hash, owner_id) VALUES (%s, %s)",
                 (hashlib.sha256(token.encode()).hexdigest(), owner))
    for template in templates:
        copy_transaction(conn, owner, template['template_key'])
    return owner, token
