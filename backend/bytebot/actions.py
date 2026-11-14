"""Idempotent, verified execution of policy-approved steps on simulated systems."""
import time
from .audit import record
from .planner import ACTIONS
from .systems import SystemUnavailable

ATTEMPTS = 2
AUDIT_ACTOR = {'agent': 'agent', 'customer': 'user', 'human': 'human'}
ACTION_TYPES = tuple(ACTIONS)


def execute(conn, systems, case, action, actor):
    """Run one approved step. The caller holds the case lock."""
    current = conn.execute('SELECT * FROM agent_actions WHERE id=%s FOR UPDATE', (action['id'],)).fetchone()
    if current['state'] == 'executed':
        return current  # Idempotent: a repeat request never creates a second record.
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with conn.transaction():  # A failed attempt rolls back only itself.
                systems.execute(conn, case, current)
                reference = systems.verify(conn, current['id'])
                if not reference:
                    raise SystemUnavailable('verification_failed')
            row = conn.execute("UPDATE agent_actions SET state='executed',actor=%s,system_reference=%s,attempts=%s,updated_at=now() "
                               'WHERE id=%s RETURNING *', (actor, reference, attempt, current['id'])).fetchone()
            record(conn, case['id'], 'action_executed', actor=AUDIT_ACTOR[actor],
                   action_id=row['id'], action_type=row['action_type'])
            return row
        except SystemUnavailable:
            if attempt < ATTEMPTS:
                time.sleep(0.05 * attempt)
    row = conn.execute("UPDATE agent_actions SET state='failed',attempts=%s,updated_at=now() WHERE id=%s RETURNING *",
                       (ATTEMPTS, current['id'])).fetchone()
    record(conn, case['id'], 'action_failed', actor='agent', action_id=row['id'], action_type=row['action_type'])
    return row


def execute_approved(conn, systems, case, run_id):
    for action in conn.execute("SELECT * FROM agent_actions WHERE run_id=%s AND state='approved' ORDER BY seq", (run_id,)).fetchall():
        execute(conn, systems, case, action, 'agent')


def decline(conn, case, action, actor='customer'):
    row = conn.execute("UPDATE agent_actions SET state='declined',actor=%s,updated_at=now() WHERE id=%s RETURNING *",
                       (actor, action['id'])).fetchone()
    record(conn, case['id'], 'action_declined', actor=AUDIT_ACTOR[actor], action_id=row['id'], action_type=row['action_type'])
    return row


def compensate(conn, systems, case, action, actor):
    systems.reverse(conn, action['id'])
    row = conn.execute("UPDATE agent_actions SET state='compensated',actor=%s,updated_at=now() WHERE id=%s RETURNING *",
                       (actor, action['id'])).fetchone()
    record(conn, case['id'], 'action_compensated', actor=AUDIT_ACTOR[actor],
           action_id=row['id'], action_type=row['action_type'])
    return row
