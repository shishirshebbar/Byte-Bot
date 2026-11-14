"""Customer-facing agent operations: answer follow-ups and ask for a person."""
from uuid import UUID
from fastapi import APIRouter, Request, Body
from .investigation_schemas import Investigation, FollowUpAnswers, EscalationRequest, ConsentRequest
from .analysis_schemas import RevisionRequest
from .actions import execute, decline, compensate
from .planner import ACTIONS
from .investigation_store import owner_for, owned_case, snapshot, save_answers, not_found
from .analysis_store import enqueue
from .agent_store import open_escalation
from .policy import REASONS
from .ocr import EvidenceError
from .audit import record

router = APIRouter(prefix='/investigations')


@router.post('/{case_id}/follow-ups', response_model=Investigation)
def answer_follow_ups(case_id: UUID, payload: FollowUpAnswers, request: Request):
    """Save answers to the supervisor's open questions and resume the investigation."""
    with request.app.state.pool.connection() as conn:
        case = owned_case(conn, owner_for(conn, request), case_id, payload.expected_revision)
        answers = payload.answers.model_dump(exclude_unset=True)
        run = conn.execute('SELECT id,prepare_report FROM analysis_runs WHERE investigation_id=%s AND input_revision=%s',
                           (case_id, case['input_revision'])).fetchone()
        rows = conn.execute("SELECT field,blocking FROM follow_up_questions WHERE run_id=%s AND state='open'",
                            (run['id'],)).fetchall() if run else []
        open_fields = {row['field'] for row in rows}
        blocking = any(row['blocking'] for row in rows)
        if not answers or not set(answers) <= open_fields:
            raise EvidenceError(409, 'follow_up_closed', 'These questions are no longer open. Reload the case.')
        conn.execute("UPDATE follow_up_questions SET state='answered' WHERE run_id=%s AND field=ANY(%s) AND state='open'",
                     (run['id'], list(answers)))
        before = case['input_revision']
        save_answers(conn, case, answers)
        record(conn, case_id, 'follow_ups_answered', input_revision=case['input_revision'])
        if case['input_revision'] == before and blocking:
            # "I'm not sure" adds nothing new, so asking again cannot help.
            open_escalation(conn, case, run['id'], 'agent', ['insufficient_information'],
                            REASONS['insufficient_information'][0])
        else:
            enqueue(conn, case['owner_id'], case_id, case['input_revision'], request.app.state.extractor.mode, run['prepare_report'])
        return snapshot(conn, owned_case(conn, case['owner_id'], case_id))


@router.post('/{case_id}/escalate', response_model=Investigation)
def request_person(case_id: UUID, request: Request, payload: EscalationRequest | None = Body(default=None)):
    """The customer can always ask for a person; repeat requests merge."""
    with request.app.state.pool.connection() as conn:
        case = owned_case(conn, owner_for(conn, request), case_id)
        run = conn.execute('SELECT id FROM analysis_runs WHERE investigation_id=%s AND input_revision=%s',
                           (case_id, case['input_revision'])).fetchone()
        open_escalation(conn, case, run['id'] if run else None, 'customer', ['customer_requested'],
                        REASONS['customer_requested'][0])
        return snapshot(conn, owned_case(conn, case['owner_id'], case_id))


def current_action(conn, case, action_id, states):
    row = conn.execute('SELECT a.* FROM agent_actions a JOIN analysis_runs r ON r.id=a.run_id '
                       'WHERE a.id=%s AND a.investigation_id=%s', (action_id, case['id'])).fetchone()
    if row is None:
        raise not_found()
    if row['input_revision'] != case['input_revision'] or row['state'] not in states:
        raise EvidenceError(409, 'action_unavailable', 'This step is no longer waiting for you. Reload the case.')
    return row


@router.post('/{case_id}/actions/{action_id}/consent', response_model=Investigation)
def consent(case_id: UUID, action_id: UUID, payload: ConsentRequest, request: Request):
    """The customer approves or declines one step that needs their consent."""
    with request.app.state.pool.connection() as conn:
        case = owned_case(conn, owner_for(conn, request), case_id, payload.expected_revision)
        action = current_action(conn, case, action_id, ('awaiting_consent',))
        if payload.decision == 'approve':
            execute(conn, request.app.state.systems, case, action, 'customer')
        else:
            decline(conn, case, action)
        return snapshot(conn, owned_case(conn, case['owner_id'], case_id))


@router.post('/{case_id}/actions/{action_id}/undo', response_model=Investigation)
def undo(case_id: UUID, action_id: UUID, payload: RevisionRequest, request: Request):
    """Reverse an executed, reversible step on its simulated system."""
    with request.app.state.pool.connection() as conn:
        case = owned_case(conn, owner_for(conn, request), case_id, payload.expected_revision)
        action = current_action(conn, case, action_id, ('executed',))
        if not ACTIONS[action['action_type']]['reversible']:
            raise EvidenceError(409, 'action_irreversible', 'This step cannot be reversed here. Contact the bank.')
        compensate(conn, request.app.state.systems, case, action, 'customer')
        return snapshot(conn, owned_case(conn, case['owner_id'], case_id))


@router.get('/{case_id}/intel-graph')
def intel_graph(case_id: UUID, request: Request):
    """The simulated fraud graph around this case's own identifiers (owner-scoped)."""
    from .intelligence import subgraph
    with request.app.state.pool.connection() as conn:
        case = owned_case(conn, owner_for(conn, request), case_id)
        transaction = conn.execute('SELECT sender_vpa FROM transactions WHERE id=%s', (case['transaction_id'],)).fetchone()
        context = conn.execute('SELECT answers FROM investigation_context WHERE investigation_id=%s', (case_id,)).fetchone()['answers']
        identifiers = [('vpa', transaction['sender_vpa'])]
        if context.get('requested_vpa'):
            identifiers.append(('vpa', context['requested_vpa']))
        run = conn.execute("SELECT outputs FROM analysis_runs WHERE investigation_id=%s AND input_revision=%s AND state='complete'",
                           (case_id, case['input_revision'])).fetchone()
        for claim in (run['outputs'].get('message_analysis', {}).get('claims', []) if run else []):
            if claim['kind'] in ('vpa', 'phone') and claim.get('intel_relevant'):
                identifiers.append((claim['kind'], claim['value']))
        return {**subgraph(conn, identifiers), 'case_identifiers': sorted({value for _, value in identifiers})}
