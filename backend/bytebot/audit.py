"""Audit metadata is constructed from typed identifiers/enums, never payloads.

Entries form a per-case hash chain, so any later edit or deletion is detectable.
"""
import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID
from psycopg.types.json import Jsonb

STATUSES = ('Open', 'Bank Contacted', 'Reported', 'Awaiting Response', 'Resolved', 'Closed')
ACTION_TYPES = ('hold_credit', 'block_vpa', 'decline_collect', 'raise_bank_dispute', 'draft_cybercrime_complaint', 'notify_customer')
ALLOWED = {
    'investigation_created': {},
    'context_updated': {'input_revision': int},
    'evidence_submitted': {'evidence_id': UUID, 'evidence_type': ('message', 'call_summary', 'screenshot', 'voice_note')},
    'evidence_updated': {'evidence_id': UUID},
    'evidence_removed': {'evidence_id': UUID},
    'analysis_completed': {'run_id': UUID, 'input_revision': int},
    'report_generated': {'report_id': UUID, 'input_revision': int},
    'escalation_opened': {'escalation_id': UUID, 'priority': ('urgent', 'high', 'normal')},
    'follow_ups_answered': {'input_revision': int},
    'action_executed': {'action_id': UUID, 'action_type': ACTION_TYPES},
    'action_failed': {'action_id': UUID, 'action_type': ACTION_TYPES},
    'action_declined': {'action_id': UUID, 'action_type': ACTION_TYPES},
    'action_compensated': {'action_id': UUID, 'action_type': ACTION_TYPES},
    'escalation_assigned': {'escalation_id': UUID},
    'escalation_resolved': {'escalation_id': UUID},
    'note_added': {'escalation_id': UUID},
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
    actor = actor or ('system' if action == 'analysis_completed' else 'user')
    # Serialise chain writes for this case; always the last lock taken, so it cannot deadlock.
    conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 82740102))', (str(case_id),))
    last = conn.execute('SELECT entry_hash FROM audit_events WHERE investigation_id=%s AND entry_hash IS NOT NULL '
                        'ORDER BY id DESC LIMIT 1', (case_id,)).fetchone()
    previous = last['entry_hash'] if last else None
    created = datetime.now(timezone.utc)
    conn.execute('INSERT INTO audit_events(investigation_id,actor,action,metadata,created_at,prev_hash,entry_hash) '
                 'VALUES (%s,%s,%s,%s,%s,%s,%s)',
                 (case_id, actor, action, Jsonb(safe), created, previous, entry_hash(case_id, actor, action, safe, created, previous)))


def entry_hash(case_id, actor, action, metadata, created, previous):
    canonical = json.dumps([str(case_id), actor, action, metadata, created.astimezone(timezone.utc).isoformat(), previous],
                           sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()


def verify_ledger(conn, case_id):
    """Recompute the chain. Entries written before the ledger existed are reported, not verified."""
    rows = conn.execute('SELECT * FROM audit_events WHERE investigation_id=%s ORDER BY id', (case_id,)).fetchall()
    previous, verified, legacy = None, True, 0
    for row in rows:
        if row['entry_hash'] is None:
            legacy += 1
            continue
        expected = entry_hash(case_id, row['actor'], row['action'], row['metadata'], row['created_at'], previous)
        if row['prev_hash'] != previous or row['entry_hash'] != expected:
            verified = False
            break
        previous = row['entry_hash']
    return {'verified': verified, 'entries': len(rows) - legacy, 'legacy_entries': legacy, 'head': previous}
