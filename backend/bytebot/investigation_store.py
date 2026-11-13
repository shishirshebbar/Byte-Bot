from uuid import uuid4
from psycopg.types.json import Jsonb
from .sessions import find_owner, COOKIE, lock_owner
from .ocr import EvidenceError
from .investigation_schemas import Context
from .audit import record


def not_found():
    return EvidenceError(404, 'not_found', 'Resource not found.')


def owner_for(conn, request):
    owner = find_owner(conn, request.cookies.get(COOKIE))
    if owner is None:
        raise not_found()
    return owner


def owned_case(conn, owner, case_id, revision=None):
    row = conn.execute('SELECT * FROM investigations WHERE id=%s AND owner_id=%s FOR UPDATE',
                       (case_id, owner)).fetchone()
    if row is None:
        raise not_found()
    if revision is not None and row['input_revision'] != revision:
        raise EvidenceError(409, 'stale_revision', 'This case changed. Reload it before saving again.')
    return row


def bump(conn, case_id):
    # Deletion and revision fencing are atomic with every actual input change.
    conn.execute('DELETE FROM incident_reports WHERE investigation_id=%s', (case_id,))
    conn.execute("UPDATE analysis_runs SET state='failed',error_code='input_changed',outputs='{}',"
                 "lease_token=NULL,lease_until=NULL,updated_at=now() WHERE investigation_id=%s", (case_id,))
    conn.execute('DELETE FROM extracted_signals WHERE run_id IN (SELECT id FROM analysis_runs WHERE investigation_id=%s)', (case_id,))
    conn.execute('DELETE FROM risk_assessments WHERE run_id IN (SELECT id FROM analysis_runs WHERE investigation_id=%s)', (case_id,))
    return conn.execute("UPDATE investigations SET input_revision=input_revision+1, workflow_state='collecting_context', updated_at=now() "
                        'WHERE id=%s RETURNING input_revision', (case_id,)).fetchone()['input_revision']


def snapshot(conn, case):
    from .analysis_store import status as analysis_status
    transaction = conn.execute('SELECT * FROM transactions WHERE owner_id=%s AND id=%s',
                               (case['owner_id'], case['transaction_id'])).fetchone()
    context = conn.execute('SELECT answers FROM investigation_context WHERE investigation_id=%s',
                           (case['id'],)).fetchone()['answers']
    items = conn.execute('SELECT * FROM evidence WHERE investigation_id=%s ORDER BY created_at,id',
                         (case['id'],)).fetchall()
    return {**case, 'transaction': transaction, 'context': Context.model_validate(context),
            'evidence': items, 'analysis': analysis_status(conn, case)}


def create_case(conn, owner, transaction_id):
    lock_owner(conn, owner)
    if not conn.execute('SELECT id FROM transactions WHERE owner_id=%s AND id=%s',
                        (owner, transaction_id)).fetchone():
        raise not_found()
    row = conn.execute('INSERT INTO investigations (id,owner_id,transaction_id) VALUES (%s,%s,%s) '
                       'ON CONFLICT (owner_id,transaction_id) DO NOTHING RETURNING *',
                       (uuid4(), owner, transaction_id)).fetchone()
    created = row is not None
    if created:
        conn.execute('INSERT INTO investigation_context (investigation_id) VALUES (%s)', (row['id'],))
        record(conn, row['id'], 'investigation_created')
    else:
        row = conn.execute('SELECT * FROM investigations WHERE owner_id=%s AND transaction_id=%s FOR UPDATE',
                           (owner, transaction_id)).fetchone()
    return snapshot(conn, row), created


def save_answers(conn, case, changes):
    previous = conn.execute('SELECT answers FROM investigation_context WHERE investigation_id=%s',
                            (case['id'],)).fetchone()['answers']
    answers = Context.model_validate({**previous, **changes}).model_dump()
    if Context.model_validate(previous).model_dump() != answers:
        conn.execute('UPDATE investigation_context SET answers=%s WHERE investigation_id=%s',
                     (Jsonb(answers), case['id']))
        case['input_revision'] = bump(conn, case['id'])
        record(conn, case['id'], 'context_updated', input_revision=case['input_revision'])
    return case


def confirmed_evidence(conn, owner, case_id):
    """Future analysis input; ownership and explicit review are mandatory."""
    owned_case(conn, owner, case_id)
    return conn.execute("SELECT id,type,confirmed_text,metadata FROM evidence WHERE investigation_id=%s "
                        "AND review_state='confirmed' ORDER BY created_at,id", (case_id,)).fetchall()


def add_evidence(conn, case, kind, text, metadata=None, notice=None):
    count = conn.execute('SELECT count(*) AS n FROM evidence WHERE investigation_id=%s', (case['id'],)).fetchone()['n']
    if count >= 20:
        raise EvidenceError(422, 'evidence_limit', 'A case can contain up to 20 evidence items. Remove an item first.')
    screenshot = kind == 'screenshot'
    row = conn.execute('INSERT INTO evidence (id,investigation_id,type,review_state,ocr_text,confirmed_text,metadata,notice) '
                       'VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *',
                       (uuid4(), case['id'], kind, ('ocr_failed' if notice else 'needs_review') if screenshot else 'confirmed',
                        text if screenshot else None, None if screenshot else text, Jsonb(metadata or {}), notice)).fetchone()
    record(conn, case['id'], 'evidence_submitted', evidence_id=row['id'], evidence_type=kind)
    return {'evidence': row, 'input_revision': bump(conn, case['id'])}
