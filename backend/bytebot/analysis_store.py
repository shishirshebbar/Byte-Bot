"""Durable queue, lease fencing, and revision-bound result access."""
from uuid import uuid4
from psycopg.types.json import Jsonb
from .analysis_schemas import RULE_VERSION
from .investigation_store import owned_case
from .ocr import EvidenceError
from .audit import record
from . import reports


class LostLease(Exception):
    pass


def status(conn, case):
    row = conn.execute('SELECT * FROM analysis_runs WHERE investigation_id=%s AND input_revision=%s',
                       (case['id'], case['input_revision'])).fetchone()
    if not row:
        return None
    result = conn.execute('SELECT data FROM risk_assessments WHERE run_id=%s', (row['id'],)).fetchone()
    report = conn.execute('SELECT id FROM incident_reports WHERE run_id=%s AND investigation_id=%s AND input_revision=%s',
                          (row['id'], case['id'], case['input_revision'])).fetchone() if row['state'] == 'complete' else None
    extraction = row['outputs'].get('message_analysis', {})
    return {'run_id': row['id'], 'input_revision': row['input_revision'], 'state': row['state'],
            'stage': row['stage'], 'error_code': row['error_code'], 'notices': extraction.get('notices', []),
            'result': result['data'] if result and row['state'] == 'complete' else None,
            'prepare_report': row['prepare_report'], 'report_id': report['id'] if report else None}


def prepare_approved_report(conn, case):
    # A savepoint isolates a report failure from the completed assessment and
    # its audit. The client can use the regular report endpoint to retry.
    try:
        with conn.transaction():
            reports.generate(conn, case, actor='system')
    except Exception:
        # Do not log exceptions that may contain evidence. A completed,
        # approved run with no report ID is the retry signal.
        pass


def enqueue(conn, owner, case_id, revision, mode, prepare_report):
    case = owned_case(conn, owner, case_id, revision)
    if conn.execute("SELECT 1 FROM evidence WHERE investigation_id=%s AND review_state<>'confirmed' LIMIT 1", (case_id,)).fetchone():
        raise EvidenceError(409, 'evidence_review_required', 'Confirm or remove every screenshot before analyzing.')
    row = conn.execute('SELECT * FROM analysis_runs WHERE investigation_id=%s AND input_revision=%s',
                       (case_id, revision)).fetchone()
    if row is None:
        conn.execute("INSERT INTO analysis_runs (id,investigation_id,input_revision,state,provider_mode,rule_version,prepare_report) "
                     "VALUES (%s,%s,%s,'queued',%s,%s,%s)", (uuid4(), case_id, revision, mode, RULE_VERSION, prepare_report))
    elif row['state'] == 'failed':
        conn.execute("UPDATE analysis_runs SET state='queued',stage='queued',attempts=0,lease_token=NULL,"
                     "lease_until=NULL,outputs='{}',stage_durations='{}',stage_started_at=NULL,error_code=NULL,provider_mode=%s,updated_at=now() WHERE id=%s",
                     (mode, row['id']))
        conn.execute('DELETE FROM extracted_signals WHERE run_id=%s', (row['id'],))
        conn.execute('DELETE FROM risk_assessments WHERE run_id=%s', (row['id'],))
    if row and prepare_report and not row['prepare_report']:
        conn.execute('UPDATE analysis_runs SET prepare_report=true WHERE id=%s', (row['id'],))
    current = status(conn, case)
    if prepare_report and current['state'] == 'complete' and not current['report_id']:
        prepare_approved_report(conn, case)
        current = status(conn, case)
    if current['state'] == 'queued':
        conn.execute("UPDATE investigations SET workflow_state='analysis_queued' WHERE id=%s", (case_id,))
    return current


def claim(pool):
    with pool.connection() as conn:
        # Case then run is the lock order used by all writers. SKIP LOCKED also
        # allows independent processes to share the queue without duplicate work.
        candidate = conn.execute("SELECT r.id,i.id AS case_id FROM investigations i JOIN analysis_runs r "
            "ON r.investigation_id=i.id AND r.input_revision=i.input_revision "
            "WHERE r.state='queued' OR (r.state='running' AND r.lease_until<now()) "
            "ORDER BY r.created_at FOR UPDATE OF i SKIP LOCKED LIMIT 1").fetchone()
        if not candidate:
            return None
        row = conn.execute('SELECT r.*,i.owner_id FROM analysis_runs r JOIN investigations i ON i.id=r.investigation_id '
                           'WHERE r.id=%s FOR UPDATE OF r', (candidate['id'],)).fetchone()
        if row['attempts'] >= 3:
            conn.execute("UPDATE analysis_runs SET state='failed',error_code='attempts_exhausted',lease_token=NULL,lease_until=NULL,updated_at=now() WHERE id=%s", (row['id'],))
            conn.execute("UPDATE investigations SET workflow_state='analysis_failed' WHERE id=%s", (candidate['case_id'],))
            return None
        token = uuid4()
        conn.execute("UPDATE analysis_runs SET state='running',attempts=attempts+1,lease_token=%s,"
                     "lease_until=now()+interval '60 seconds',error_code=NULL,updated_at=now() WHERE id=%s", (token, row['id']))
        conn.execute("UPDATE investigations SET workflow_state='analyzing' WHERE id=%s", (candidate['case_id'],))
        return {**row, 'lease_token': token, 'state': 'running'}


def fenced(conn, run):
    try:
        case = owned_case(conn, run['owner_id'], run['investigation_id'])
    except EvidenceError as exc:
        if exc.status == 404:
            raise LostLease() from None
        raise
    row = conn.execute('SELECT * FROM analysis_runs WHERE id=%s FOR UPDATE', (run['id'],)).fetchone()
    valid = (case['input_revision'] == run['input_revision'] and row and row['state'] == 'running'
             and row['lease_token'] == run['lease_token'])
    if valid:
        valid = conn.execute('SELECT lease_until > now() AS valid FROM analysis_runs WHERE id=%s', (run['id'],)).fetchone()['valid']
    if not valid:
        raise LostLease()
    return case


def heartbeat(pool, run):
    with pool.connection() as conn:
        fenced(conn, run)
        conn.execute("UPDATE analysis_runs SET lease_until=now()+interval '60 seconds' WHERE id=%s", (run['id'],))


def save_stage(pool, run, stage, output=None):
    with pool.connection() as conn:
        fenced(conn, run)
        if output is None:
            conn.execute('UPDATE analysis_runs SET stage=%s,stage_started_at=now(),updated_at=now() WHERE id=%s', (stage, run['id']))
        else:
            conn.execute('UPDATE analysis_runs SET outputs=outputs || %s,updated_at=now() WHERE id=%s',
                         (Jsonb({stage: output}), run['id']))
            conn.execute("UPDATE analysis_runs SET stage_durations=stage_durations || "
                         "jsonb_build_object(%s::text,extract(epoch from (now()-stage_started_at))) WHERE id=%s",
                         (stage, run['id']))
            if stage == 'message_analysis':
                conn.execute('DELETE FROM extracted_signals WHERE run_id=%s', (run['id'],))
                for item in output['claims']:
                    conn.execute('INSERT INTO extracted_signals VALUES (%s,%s,%s,%s)',
                                 (uuid4(), run['id'], item['evidence_id'], Jsonb(item)))


def publish(pool, run, result):
    with pool.connection() as conn:
        case = fenced(conn, run)
        conn.execute('INSERT INTO risk_assessments (run_id,data) VALUES (%s,%s) ON CONFLICT (run_id) DO UPDATE SET data=excluded.data',
                     (run['id'], Jsonb(result)))
        completed = conn.execute("UPDATE analysis_runs SET state='complete',stage='complete',lease_token=NULL,"
                                 "lease_until=NULL,updated_at=now() WHERE id=%s RETURNING prepare_report", (run['id'],)).fetchone()
        conn.execute("UPDATE investigations SET workflow_state='results_ready' WHERE id=%s", (run['investigation_id'],))
        record(conn, run['investigation_id'], 'analysis_completed', run_id=run['id'], input_revision=run['input_revision'])
        if completed['prepare_report']:
            prepare_approved_report(conn, case)


def fail(pool, run):
    with pool.connection() as conn:
        fenced(conn, run)
        conn.execute("UPDATE analysis_runs SET state='failed',error_code='analysis_failed',lease_token=NULL,lease_until=NULL,updated_at=now() WHERE id=%s", (run['id'],))
        conn.execute("UPDATE investigations SET workflow_state='analysis_failed' WHERE id=%s", (run['investigation_id'],))
