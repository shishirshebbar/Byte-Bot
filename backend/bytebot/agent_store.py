"""Persistence for supervisor decisions, follow-ups, planned actions, and escalation."""
from uuid import uuid4
from psycopg.types.json import Jsonb
from .planner import QUESTIONS, ACTIONS
from .policy import POLICY_VERSION, REASONS, SLA_MINUTES, outcome
from .audit import record
from .systems import LABELS

PENDING = ('approved', 'awaiting_consent', 'awaiting_human')


def open_escalation(conn, case, run_id, source, reasons, priority):
    """Create the case's active escalation, or merge reasons into it."""
    row = conn.execute(
        "INSERT INTO escalations (id,investigation_id,run_id,input_revision,source,reasons,priority,sla_due_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,now() + make_interval(mins => %s)) "
        "ON CONFLICT (investigation_id) WHERE state <> 'resolved' DO UPDATE SET "
        "reasons=(SELECT jsonb_agg(DISTINCT x ORDER BY x) FROM jsonb_array_elements(escalations.reasons || excluded.reasons) x), "
        "priority=CASE WHEN array_position(ARRAY['normal','high','urgent'], excluded.priority) > "
        "array_position(ARRAY['normal','high','urgent'], escalations.priority) THEN excluded.priority ELSE escalations.priority END, "
        "sla_due_at=LEAST(escalations.sla_due_at, excluded.sla_due_at), "
        "run_id=COALESCE(excluded.run_id, escalations.run_id), input_revision=excluded.input_revision, updated_at=now() "
        "RETURNING id,priority,(xmax = 0) AS created",
        (uuid4(), case['id'], run_id, case['input_revision'], source, Jsonb(sorted(reasons)), priority,
         SLA_MINUTES[priority])).fetchone()
    if row['created']:
        record(conn, case['id'], 'escalation_opened', actor='agent' if source == 'agent' else 'user',
               escalation_id=row['id'], priority=row['priority'])
    return row


def persist(conn, case, run, agent):
    """Write one run's decisions atomically with its published assessment."""
    conn.execute('DELETE FROM follow_up_questions WHERE run_id=%s', (run['id'],))
    conn.execute('DELETE FROM agent_actions WHERE run_id=%s', (run['id'],))
    for field in agent['follow_ups']:
        conn.execute('INSERT INTO follow_up_questions (id,investigation_id,run_id,input_revision,field,blocking) '
                     'VALUES (%s,%s,%s,%s,%s,%s)', (uuid4(), case['id'], run['id'], run['input_revision'], field, agent['blocking']))
    for seq, action in enumerate(agent['actions']):
        conn.execute('INSERT INTO agent_actions (id,investigation_id,run_id,input_revision,seq,action_type,system,verdict,state,'
                     'reason,policy_version,idempotency_key) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                     (uuid4(), case['id'], run['id'], run['input_revision'], seq, action['action_type'],
                      ACTIONS[action['action_type']]['system'], action['verdict'], action['state'], action['reason'],
                      POLICY_VERSION, f"{run['id']}:{action['action_type']}"))
    if agent['escalation_reasons']:
        open_escalation(conn, case, run['id'], 'agent', agent['escalation_reasons'], agent['priority'])


def revoke_pending(conn, case_id):
    """An input change makes every unexecuted decision stale."""
    conn.execute("UPDATE follow_up_questions SET state='revoked' WHERE investigation_id=%s AND state='open'", (case_id,))
    conn.execute("UPDATE agent_actions SET state='revoked',updated_at=now() WHERE investigation_id=%s AND state=ANY(%s)",
                 (case_id, list(PENDING)))


def clear_run(conn, run_id):
    for table in ('agent_trace', 'follow_up_questions', 'agent_actions'):
        conn.execute(f'DELETE FROM {table} WHERE run_id=%s', (run_id,))


def escalation(conn, case_id):
    row = conn.execute('SELECT * FROM escalations WHERE investigation_id=%s ORDER BY (state <> %s) DESC, created_at DESC LIMIT 1',
                       (case_id, 'resolved')).fetchone()
    if row is None:
        return None
    return {'id': row['id'], 'source': row['source'], 'priority': row['priority'], 'state': row['state'],
            'reasons': [{'code': code, 'label': REASONS[code][1]} for code in row['reasons']],
            'sla_due_at': row['sla_due_at'], 'created_at': row['created_at'], 'updated_at': row['updated_at'],
            'assignee': conn.execute('SELECT name FROM console_agents WHERE id=%s', (row['assignee_id'],)).fetchone()['name']
            if row['assignee_id'] else None}


def agent_status(conn, run, complete):
    trace = conn.execute('SELECT seq,node,reason,created_at FROM agent_trace WHERE run_id=%s ORDER BY seq',
                         (run['id'],)).fetchall()
    if not complete:
        return {'policy_version': POLICY_VERSION, 'outcome': None, 'trace': trace, 'follow_ups': [], 'actions': []}
    questions = sorted(conn.execute('SELECT id,field,blocking,state FROM follow_up_questions WHERE run_id=%s',
                                    (run['id'],)).fetchall(), key=lambda q: list(QUESTIONS).index(q['field']))
    actions = conn.execute('SELECT a.*,s.detail FROM agent_actions a LEFT JOIN simulated_records s ON s.action_id=a.id '
                           'WHERE a.run_id=%s ORDER BY a.seq', (run['id'],)).fetchall()
    active = conn.execute("SELECT 1 FROM escalations WHERE investigation_id=%s AND state <> 'resolved'",
                          (run['investigation_id'],)).fetchone()
    blocking = any(q['blocking'] and q['state'] == 'open' for q in questions)
    follow_ups = [{'id': q['id'], 'field': q['field'], 'blocking': q['blocking'], 'state': q['state'],
                   'prompt': QUESTIONS[q['field']]['prompt'], 'multi': QUESTIONS[q['field']]['multi'],
                   'options': [{'value': v, 'label': label} for v, label in QUESTIONS[q['field']]['options']]}
                  for q in questions]
    items = [{'id': a['id'], 'action_type': a['action_type'], 'label': ACTIONS[a['action_type']]['label'],
              'system': a['system'], 'reversible': ACTIONS[a['action_type']]['reversible'], 'verdict': a['verdict'],
              'state': a['state'], 'actor': a['actor'], 'reason': a['reason'], 'system_reference': a['system_reference'],
              'system_label': LABELS[a['system']], 'detail': a['detail']}
             for a in actions]
    return {'policy_version': POLICY_VERSION, 'trace': trace, 'follow_ups': follow_ups, 'actions': items,
            'outcome': outcome(escalated=bool(active), blocking=blocking, actions=items)}
