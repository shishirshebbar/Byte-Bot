"""Audit metadata is constructed from typed identifiers/enums, never payloads."""
from uuid import UUID
from psycopg.types.json import Jsonb

STATUSES = ('Open', 'Bank Contacted', 'Reported', 'Awaiting Response', 'Resolved', 'Closed')
ALLOWED = {
    'investigation_created': {},
    'context_updated': {'input_revision': int},
    'evidence_submitted': {'evidence_id': UUID, 'evidence_type': ('message', 'call_summary', 'screenshot')},
    'evidence_updated': {'evidence_id': UUID},
    'evidence_removed': {'evidence_id': UUID},
    'analysis_completed': {'run_id': UUID, 'input_revision': int},
    'report_generated': {'report_id': UUID, 'input_revision': int},
    'status_updated': {'from_status': STATUSES, 'to_status': STATUSES, 'status_revision': int},
}


def record(conn, case_id, action, *, actor=None, **metadata):
    schema = ALLOWED[action]
    if set(metadata) != set(schema):
        raise ValueError('Invalid audit metadata')
    safe = {}
    for key, kind in schema.items():
        value = metadata[key]
        if kind is UUID:
            safe[key] = str(UUID(str(value)))
        elif kind is int:
            if type(value) is not int or value < 0:
                raise ValueError('Invalid audit number')
            safe[key] = value
        else:
            if value not in kind:
                raise ValueError('Invalid audit enum')
            safe[key] = value
    conn.execute('INSERT INTO audit_events(investigation_id,actor,action,metadata) VALUES (%s,%s,%s,%s)',
                 (case_id, actor or ('system' if action == 'analysis_completed' else 'user'), action, Jsonb(safe)))
