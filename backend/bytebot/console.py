"""Human teammate console. A separate demo support-agent session reads only escalated cases.

Customer endpoints never accept the console cookie, and console endpoints never
accept the customer cookie. Console reads go through allowlisted fields and mask
the customer's own identifiers.
"""
import hashlib
import secrets
from typing import Literal
from uuid import UUID, uuid4
from fastapi import APIRouter, Request, Response, Body
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .settings import COOKIE_SECURE, GEMINI_API_KEY, GEMINI_MODEL, SARVAM_API_KEY
from .ocr import EvidenceError
from .redaction import redact
from .audit import record, verify_ledger
from .actions import execute, decline, compensate
from .planner import ACTIONS
from .policy import REASONS
from .systems import LABELS

router = APIRouter(prefix='/console')
COOKIE = 'bytebot_console'
PRIORITY_RANK = "CASE e.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 ELSE 2 END"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class SessionRequest(StrictModel):
    name: str = Field(default='Demo support agent', min_length=1, max_length=60)


class Decision(StrictModel):
    decision: Literal['approve', 'reject']


class Note(StrictModel):
    text: str = Field(min_length=1, max_length=2000)

    @field_validator('text')
    @classmethod
    def clean(cls, value):
        value = redact(value)
        if not value:
            raise ValueError('Provide a note')
        return value


class Resolve(StrictModel):
    note: str | None = Field(default=None, max_length=2000)


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def console_agent(conn, request):
    token = request.cookies.get(COOKIE)
    row = conn.execute('SELECT id,name FROM console_agents WHERE token_hash=%s', (digest(token),)).fetchone() \
        if token and len(token) <= 128 else None
    if row is None:
        raise EvidenceError(401, 'console_session_required', 'Open the support console session first.')
    return row


def mask(vpa):
    if not vpa or '@' not in vpa:
        return '•••'
    name, domain = vpa.split('@', 1)
    return f'{name[:2]}•••@{domain}'


def escalated(conn, escalation_id, lock=False):
    """Only cases with an escalation are visible here, whoever owns them."""
    row = conn.execute('SELECT e.*, i.owner_id, a.name AS assignee FROM escalations e '
                       'JOIN investigations i ON i.id=e.investigation_id LEFT JOIN console_agents a ON a.id=e.assignee_id '
                       'WHERE e.id=%s', (escalation_id,)).fetchone()
    if row is None:
        raise EvidenceError(404, 'not_found', 'Resource not found.')
    case = conn.execute(f"SELECT * FROM investigations WHERE id=%s{' FOR UPDATE' if lock else ''}",
                        (row['investigation_id'],)).fetchone()
    return row, case


def escalation_view(row):
    return {'id': row['id'], 'investigation_id': row['investigation_id'], 'source': row['source'],
            'priority': row['priority'], 'state': row['state'], 'assignee': row['assignee'],
            'reasons': [{'code': code, 'label': REASONS[code][1]} for code in row['reasons']],
            'sla_due_at': row['sla_due_at'], 'created_at': row['created_at'], 'resolved_at': row['resolved_at']}


@router.post('/session')
def open_session(request: Request, response: Response, payload: SessionRequest = Body(default=SessionRequest())):
    with request.app.state.pool.connection() as conn:
        try:
            return {'agent': console_agent(conn, request)}
        except EvidenceError:
            pass
        token = secrets.token_urlsafe(32)
        row = conn.execute('INSERT INTO console_agents (id,name,token_hash) VALUES (%s,%s,%s) RETURNING id,name',
                           (uuid4(), payload.name, digest(token))).fetchone()
    response.set_cookie(COOKIE, token, httponly=True, samesite='lax', secure=COOKIE_SECURE, path='/api/v1/console')
    return {'agent': row}


@router.get('/session')
def get_session(request: Request):
    with request.app.state.pool.connection() as conn:
        return {'agent': console_agent(conn, request)}


@router.get('/queue')
def queue(request: Request):
    with request.app.state.pool.connection() as conn:
        console_agent(conn, request)
        rows = conn.execute(
            'SELECT e.*, a.name AS assignee, t.amount_paise, t.sender_vpa, t.status AS transaction_status, '
            "(SELECT ra.data->>'category' FROM analysis_runs r JOIN risk_assessments ra ON ra.run_id=r.id "
            " WHERE r.investigation_id=i.id AND r.input_revision=i.input_revision AND r.state='complete') AS category, "
            "(SELECT (ra.data->>'risk_score')::int FROM analysis_runs r JOIN risk_assessments ra ON ra.run_id=r.id "
            " WHERE r.investigation_id=i.id AND r.input_revision=i.input_revision AND r.state='complete') AS risk_score, "
            "(SELECT count(*) FROM agent_actions x WHERE x.investigation_id=i.id AND x.state='awaiting_human') AS awaiting_human "
            'FROM escalations e JOIN investigations i ON i.id=e.investigation_id '
            'JOIN transactions t ON t.id=i.transaction_id LEFT JOIN console_agents a ON a.id=e.assignee_id '
            f"ORDER BY (e.state='resolved'), {PRIORITY_RANK}, e.sla_due_at LIMIT 200").fetchall()
        return {'cases': [{**escalation_view(row), 'amount_paise': row['amount_paise'], 'sender_vpa': row['sender_vpa'],
                           'transaction_status': row['transaction_status'], 'category': row['category'], 'risk_score': row['risk_score'],
                           'awaiting_human': row['awaiting_human']} for row in rows]}


@router.get('/cases/{escalation_id}')
def case_detail(escalation_id: UUID, request: Request):
    from .analysis_store import status
    with request.app.state.pool.connection() as conn:
        console_agent(conn, request)
        row, case = escalated(conn, escalation_id)
        t = conn.execute('SELECT * FROM transactions WHERE id=%s', (case['transaction_id'],)).fetchone()
        context = conn.execute('SELECT answers FROM investigation_context WHERE investigation_id=%s', (case['id'],)).fetchone()['answers']
        evidence = conn.execute("SELECT id,type,confirmed_text FROM evidence WHERE investigation_id=%s AND review_state='confirmed' "
                                'ORDER BY created_at,id', (case['id'],)).fetchall()
        notes = conn.execute('SELECT n.id,n.text,n.created_at,a.name AS author FROM escalation_notes n '
                             'LEFT JOIN console_agents a ON a.id=n.agent_id WHERE n.escalation_id=%s ORDER BY n.created_at', (row['id'],)).fetchall()
        activity = conn.execute('SELECT action,actor,metadata,created_at FROM audit_events WHERE investigation_id=%s ORDER BY id DESC LIMIT 50',
                                (case['id'],)).fetchall()
        return {'escalation': escalation_view(row),
                'case': {'id': case['id'], 'input_revision': case['input_revision'], 'case_status': case['case_status']},
                'transaction': {'amount_paise': t['amount_paise'], 'sender_name': t['sender_name'], 'sender_vpa': t['sender_vpa'],
                                'customer_vpa': mask(t['receiver_vpa']), 'status': t['status'], 'reference': t['reference'],
                                'occurred_at': t['occurred_at']},
                'context': context,
                'evidence': [{'id': e['id'], 'type': e['type'], 'text': e['confirmed_text']} for e in evidence],
                'analysis': status(conn, case), 'notes': notes, 'activity': activity, 'ledger': verify_ledger(conn, case['id'])}


@router.post('/cases/{escalation_id}/actions/{action_id}')
def decide(escalation_id: UUID, action_id: UUID, payload: Decision, request: Request):
    """A person approves or rejects a step the policy reserved for human approval."""
    with request.app.state.pool.connection() as conn:
        agent = console_agent(conn, request)
        row, case = escalated(conn, escalation_id, lock=True)
        action = conn.execute('SELECT * FROM agent_actions WHERE id=%s AND investigation_id=%s', (action_id, case['id'])).fetchone()
        if action is None:
            raise EvidenceError(404, 'not_found', 'Resource not found.')
        if action['state'] != 'awaiting_human' or action['input_revision'] != case['input_revision']:
            raise EvidenceError(409, 'action_unavailable', 'This step is no longer waiting for approval. Reload the case.')
        if row['state'] == 'open':
            claim_case(conn, row, case, agent)
        if payload.decision == 'approve':
            execute(conn, request.app.state.systems, case, action, 'human')
        else:
            decline(conn, case, action, 'human')
    return case_detail(escalation_id, request)


@router.post('/cases/{escalation_id}/actions/{action_id}/undo')
def undo(escalation_id: UUID, action_id: UUID, request: Request):
    with request.app.state.pool.connection() as conn:
        console_agent(conn, request)
        _, case = escalated(conn, escalation_id, lock=True)
        action = conn.execute("SELECT * FROM agent_actions WHERE id=%s AND investigation_id=%s", (action_id, case['id'])).fetchone()
        if action is None:
            raise EvidenceError(404, 'not_found', 'Resource not found.')
        if action['state'] != 'executed' or not ACTIONS[action['action_type']]['reversible']:
            raise EvidenceError(409, 'action_unavailable', 'Only executed, reversible steps can be undone.')
        compensate(conn, request.app.state.systems, case, action, 'human')
    return case_detail(escalation_id, request)


def claim_case(conn, row, case, agent):
    conn.execute("UPDATE escalations SET state='assigned',assignee_id=%s,updated_at=now() WHERE id=%s", (agent['id'], row['id']))
    record(conn, case['id'], 'escalation_assigned', actor='human', escalation_id=row['id'])


@router.post('/cases/{escalation_id}/assign')
def assign(escalation_id: UUID, request: Request):
    with request.app.state.pool.connection() as conn:
        agent = console_agent(conn, request)
        row, case = escalated(conn, escalation_id, lock=True)
        if row['state'] == 'resolved':
            raise EvidenceError(409, 'escalation_resolved', 'This case is already resolved.')
        if row['assignee_id'] != agent['id']:
            claim_case(conn, row, case, agent)
    return case_detail(escalation_id, request)


@router.post('/cases/{escalation_id}/notes')
def add_note(escalation_id: UUID, payload: Note, request: Request):
    with request.app.state.pool.connection() as conn:
        agent = console_agent(conn, request)
        row, case = escalated(conn, escalation_id, lock=True)
        conn.execute('INSERT INTO escalation_notes (id,escalation_id,agent_id,text) VALUES (%s,%s,%s,%s)',
                     (uuid4(), row['id'], agent['id'], payload.text))
        record(conn, case['id'], 'note_added', actor='human', escalation_id=row['id'])
    return case_detail(escalation_id, request)


@router.post('/cases/{escalation_id}/resolve')
def resolve(escalation_id: UUID, request: Request, payload: Resolve = Body(default=Resolve())):
    with request.app.state.pool.connection() as conn:
        agent = console_agent(conn, request)
        row, case = escalated(conn, escalation_id, lock=True)
        if row['state'] == 'resolved':
            raise EvidenceError(409, 'escalation_resolved', 'This case is already resolved.')
        if payload.note and redact(payload.note):
            conn.execute('INSERT INTO escalation_notes (id,escalation_id,agent_id,text) VALUES (%s,%s,%s,%s)',
                         (uuid4(), row['id'], agent['id'], redact(payload.note)))
        conn.execute("UPDATE escalations SET state='resolved',resolved_at=now(),assignee_id=COALESCE(assignee_id,%s),updated_at=now() "
                     'WHERE id=%s', (agent['id'], row['id']))
        record(conn, case['id'], 'escalation_resolved', actor='human', escalation_id=row['id'])
    return case_detail(escalation_id, request)


@router.get('/notifications')
def notifications(request: Request):
    with request.app.state.pool.connection() as conn:
        console_agent(conn, request)
        rows = conn.execute(
            "SELECT ev.action, ev.actor, ev.metadata, ev.created_at, e.id AS escalation_id, e.priority "
            'FROM audit_events ev JOIN escalations e ON e.investigation_id=ev.investigation_id '
            "WHERE ev.action IN ('escalation_opened','action_executed','action_failed','action_declined',"
            "'action_compensated','escalation_assigned','escalation_resolved','note_added') "
            'AND ev.created_at >= e.created_at - interval \'5 minutes\' ORDER BY ev.id DESC LIMIT 30').fetchall()
        return {'notifications': rows}


@router.get('/integrations')
def integrations(request: Request):
    with request.app.state.pool.connection() as conn:
        console_agent(conn, request)
        records = conn.execute('SELECT system, count(*) AS n FROM simulated_records GROUP BY system').fetchall()
        intel = conn.execute('SELECT count(*) AS n FROM intel_entities').fetchone()['n']
    counts = {row['system']: row['n'] for row in records}
    mode = request.app.state.extractor.mode
    items = [{'key': key, 'name': label, 'type': 'Simulated system', 'status': 'healthy',
              'detail': f"{counts.get(key, 0)} records"} for key, label in LABELS.items()]
    items += [
        {'key': 'gemini', 'name': 'Gemini extraction', 'type': 'LLM', 'status': 'healthy' if mode == 'gemini' and GEMINI_API_KEY and GEMINI_MODEL else 'standby',
         'detail': 'Live provider' if mode == 'gemini' else 'Not in use (extraction mode: ' + mode + ')'},
        {'key': 'sarvam', 'name': 'Sarvam AI', 'type': 'Indic speech, translation, LLM', 'status': 'healthy' if request.app.state.speech.configured else 'standby',
         'detail': ('Live extraction · ' if mode == 'sarvam' else '') + ('Voice notes and spoken guidance enabled' if request.app.state.speech.configured else 'Add SARVAM_API_KEY to enable')},
        {'key': 'easyocr', 'name': 'EasyOCR', 'type': 'OCR', 'status': 'healthy', 'detail': 'Local CPU, screenshots stay in memory'},
        {'key': 'intel', 'name': 'Fraud intelligence', 'type': 'Intel', 'status': 'healthy', 'detail': f'{intel} simulated entities'},
        {'key': 'policy', 'name': 'Action policy', 'type': 'Rules', 'status': 'healthy', 'detail': 'agent-policy-1'},
    ]
    return {'integrations': items}
