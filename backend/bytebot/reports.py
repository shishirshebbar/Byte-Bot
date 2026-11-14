"""Immutable, revision-bound user-owned reports. No provider calls or file storage."""
from datetime import datetime, timezone
from uuid import uuid4
from psycopg.types.json import Jsonb
from .audit import record
from .investigation_store import not_found
from .investigation_schemas import Context
from .ocr import EvidenceError
from .report_schemas import ReportSnapshot

CONTEXT_LABELS = {
    'expected_payment': 'Expected payment', 'knows_sender': 'Knows sender',
    'repayment_requested': 'Repayment requested', 'contact_channels': 'Contact channels',
    'requested_destination_type': 'Requested destination type', 'requested_vpa': 'Requested UPI ID',
    'pressure_tactics': 'Reported pressure', 'already_sent_money': 'Already sent money',
}
EXPLANATIONS = {
    'successful': 'This synthetic payment completed successfully.',
    'pending': 'This payment is pending. Funds are not confirmed as received.',
    'failed': 'This payment failed. Funds were not received.',
}


def current_result(conn, case):
    from .analysis_store import status

    run = status(conn, case)
    if not run or run['state'] != 'complete' or not run['result']:
        raise EvidenceError(409, 'analysis_required', 'Analyze the current saved information before generating or viewing a report.')
    return run


def retrieve(conn, case):
    current_result(conn, case)
    row = conn.execute('SELECT snapshot FROM incident_reports WHERE investigation_id=%s AND input_revision=%s',
                       (case['id'], case['input_revision'])).fetchone()
    if row is None:
        raise not_found()
    return ReportSnapshot.model_validate(row['snapshot'])


def report_actions(conn, run_id):
    from .planner import ACTIONS
    from .systems import LABELS
    rows = conn.execute('SELECT action_type,system,state,actor,system_reference FROM agent_actions WHERE run_id=%s ORDER BY seq',
                        (run_id,)).fetchall()
    return [{**row, 'label': ACTIONS[row['action_type']]['label'], 'system_label': LABELS[row['system']]} for row in rows]


def generate(conn, case, *, actor='user'):
    # Caller holds the case lock through snapshot creation and commit. Input
    # writers use this same lock, so a stale snapshot cannot be republished.
    run = current_result(conn, case)
    existing = conn.execute('SELECT snapshot FROM incident_reports WHERE investigation_id=%s AND input_revision=%s',
                            (case['id'], case['input_revision'])).fetchone()
    if existing:
        return ReportSnapshot.model_validate(existing['snapshot']), False
    transaction = conn.execute('SELECT * FROM transactions WHERE id=%s AND owner_id=%s',
                               (case['transaction_id'], case['owner_id'])).fetchone()
    answers = Context.model_validate(conn.execute('SELECT answers FROM investigation_context WHERE investigation_id=%s',
                                                  (case['id'],)).fetchone()['answers'])
    evidence = conn.execute("SELECT id,type,confirmed_text FROM evidence WHERE investigation_id=%s AND review_state='confirmed' ORDER BY created_at,id",
                            (case['id'],)).fetchall()
    signals = conn.execute('SELECT data FROM extracted_signals WHERE run_id=%s ORDER BY evidence_id,id',
                           (run['run_id'],)).fetchall()
    unknowns = [f'{CONTEXT_LABELS[key]}: not supplied or unknown.' for key, value in answers.model_dump().items()
                if value is None or value == 'unknown']
    snapshot = ReportSnapshot.model_validate({
        'id': uuid4(), 'investigation_id': case['id'], 'input_revision': case['input_revision'],
        'run_id': run['run_id'], 'generated_at': datetime.now(timezone.utc),
        'status_at_generation': case['case_status'], 'transaction': transaction,
        'transaction_explanation': EXPLANATIONS[transaction['status']],
        'user_statements': answers, 'evidence': [
            {'id': e['id'], 'type': e['type'], 'text': e['confirmed_text'],
             'source': {'screenshot': 'User-reviewed local OCR', 'voice_note': 'User-reviewed Sarvam voice transcript'}.get(e['type'], 'User statement')} for e in evidence],
        'extracted_signals': [{**r['data'], 'value':
            f"₹{r['data']['value'] // 100:,}.{r['data']['value'] % 100:02d} INR"
            if r['data']['kind'] == 'amount' and type(r['data']['value']) is int else r['data']['value']
        } for r in signals], 'assessment': run['result'],
        'unknowns': unknowns, 'notices': run['notices'],
        'actions': report_actions(conn, run['run_id']),
    })
    conn.execute('INSERT INTO incident_reports(id,investigation_id,input_revision,run_id,snapshot,generated_at) VALUES (%s,%s,%s,%s,%s,%s)',
                 (snapshot.id, case['id'], case['input_revision'], run['run_id'],
                  Jsonb(snapshot.model_dump(mode='json')), snapshot.generated_at))
    record(conn, case['id'], 'report_generated', actor=actor, report_id=snapshot.id, input_revision=case['input_revision'])
    return snapshot, True


def answer_text(value):
    if value is None or value == 'unknown':
        return 'Not supplied or unknown'
    if isinstance(value, list):
        return ', '.join(value) or 'None reported'
    return str(value)


def format_text(report):
    """UTF-8 text is generated from the persisted snapshot only."""
    r = report.model_dump(mode='json')
    t, a = r['transaction'], r['assessment']
    lines = ['BYTE BOT — INCIDENT REPORT', 'Synthetic demo; user-owned report',
             f"Report ID: {r['id']}", f"Case ID: {r['investigation_id']}",
             f"Input revision: {r['input_revision']}", f"Analysis run: {r['run_id']}",
             f"Generated: {r['generated_at']} (UTC)", f"Status at generation: {r['status_at_generation']}",
             '', 'TRANSACTION FACTS — SYNTHETIC RECORD',
             f"Amount: ₹{t['amount_paise'] // 100:,}.{t['amount_paise'] % 100:02d} INR",
             f"Status: {t['status']}", r['transaction_explanation'],
             *[f'{key}: {value}' for key, value in t.items() if key not in ('amount_paise', 'status')],
             '', 'USER STATEMENTS — NOT INDEPENDENTLY VERIFIED',
             *[f'{CONTEXT_LABELS[key]}: {answer_text(value)}' for key, value in r['user_statements'].items()],
             '', 'CONFIRMED REDACTED EVIDENCE']
    for e in r['evidence']:
        lines.extend([f"Evidence {e['id']} · {e['type']} · {e['source']}", e['text'], ''])
    if not r['evidence']:
        lines.append('No evidence submitted.')
    lines.extend(['', 'VALIDATED EXTRACTED SIGNALS'])
    for s in r['extracted_signals']:
        lines.extend([f"{s['kind']} · evidence {s['evidence_id']} · value: {s['value'] if s['value'] is not None else 'Not supplied'}", f"Quote: {s['quote']}"])
    if not r['extracted_signals']:
        lines.append('No validated extracted signals available.')
    lines.extend(['', 'ASSESSMENT', a['category'], a['summary'],
                  f"Assessment generated: {a['generated_at']}", f"Rule version: {a['rule_version']}",
                  f"Triggered rules: {', '.join(a['triggered_rules'])}",
                  f"Extraction: {a['extraction_status']} · provider mode: {a['provider_mode']}"])
    if a['provider_mode'] == 'fixture':
        lines.append('SYNTHETIC EXTRACTION FIXTURE')
    lines.extend(['', 'FINDINGS AND PROVENANCE'])
    for f in a['findings']:
        lines.extend([f['text'], f"Source: {f['source']} · reference: {f['reference']} · rule: {f['rule_id']}"])
        if f['quote']:
            lines.append(f"Quote: {f['quote']}")
    lines.extend(['', 'SIMULATED INTELLIGENCE MATCHES'])
    if not a['intelligence_matches']:
        lines.append('No match found in the available demo data. This does not imply trust.')
    for match in a['intelligence_matches']:
        # The validated assessment owns the explicit presentation fields.
        lines.append(' · '.join(f'{key}: {match.get(key, "")}' for key in
                     ('identifier', 'source_label', 'reported_at', 'match_type', 'incident_reference', 'limitations')))
    lines.extend(['', 'BYTE BOT ACTIONS AT REPORT TIME (SIMULATED SYSTEMS)'])
    if not r.get('actions'):
        lines.append('No account actions were planned.')
    for action in r.get('actions', []):
        lines.append(f"{action['label']} · {action['state'].replace('_', ' ')} · {action['system_label']}"
                     + (f" · reference {action['system_reference']}" if action['system_reference'] else ''))
    lines.extend(['', 'UNKNOWNS AND LIMITATIONS', *r['unknowns'], *a['limitations'], *r['notices'],
                  '', 'RECOMMENDED NEXT STEPS', *[f'{i}. {text}' for i, text in enumerate(a['recommendations'], 1)],
                  '', 'Byte Bot cannot confirm fraud or move real money. Listed actions ran on simulated systems; it does not contact your real bank or submit this report.',
                  'Case status records actions reported by you outside the app. Recovery cannot be promised.',
                  'Changed case inputs invalidate the server copy. Previously downloaded files remain with you.'])
    return '\n'.join(lines) + '\n'
