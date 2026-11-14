"""Demo-wide outcome metrics. Counts and durations only; no evidence, identifiers, or per-case data."""
import json
import statistics
from uuid import UUID
from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field
from .settings import ROOT
from .investigation_store import owner_for, owned_case
from .ocr import EvidenceError

router = APIRouter()
EVAL_DIR = ROOT / '.cache' / 'eval'
MANUAL_REVIEW_MINUTES = 8  # Pilot assumption for a support agent's manual review; shown as an estimate.


class Feedback(BaseModel):
    model_config = ConfigDict(extra='forbid')
    helpful: bool = Field(strict=True)


@router.post('/investigations/{case_id}/feedback', status_code=204)
def feedback(case_id: UUID, payload: Feedback, request: Request):
    with request.app.state.pool.connection() as conn:
        case = owned_case(conn, owner_for(conn, request), case_id)
        run = conn.execute("SELECT id FROM analysis_runs WHERE investigation_id=%s AND input_revision=%s AND state='complete'",
                           (case_id, case['input_revision'])).fetchone()
        if run is None:
            raise EvidenceError(409, 'result_unavailable', 'Feedback applies to a completed assessment.')
        conn.execute('INSERT INTO agent_feedback (investigation_id,run_id,helpful) VALUES (%s,%s,%s) '
                     'ON CONFLICT (investigation_id,run_id) DO UPDATE SET helpful=excluded.helpful, created_at=now()',
                     (case_id, run['id'], payload.helpful))


@router.get('/metrics')
def metrics(request: Request):
    with request.app.state.pool.connection() as conn:
        runs = conn.execute("SELECT r.investigation_id, r.stage_durations FROM analysis_runs r JOIN investigations i "
                            "ON i.id=r.investigation_id AND i.input_revision=r.input_revision WHERE r.state='complete'").fetchall()
        analyzed = {row['investigation_id'] for row in runs}
        escalated = {row['investigation_id'] for row in conn.execute('SELECT DISTINCT investigation_id FROM escalations').fetchall()}
        actions = conn.execute("SELECT actor, state, verdict, count(*) AS n FROM agent_actions WHERE state IN "
                               "('executed','failed','compensated','declined') GROUP BY actor, state, verdict").fetchall()
        violations = conn.execute("SELECT count(*) AS n FROM agent_actions WHERE actor='agent' AND state IN ('executed','compensated') "
                                  "AND verdict <> 'auto'").fetchone()['n']
        protected = conn.execute("SELECT coalesce(sum(t.amount_paise),0) AS paise FROM agent_actions a JOIN investigations i ON i.id=a.investigation_id "
                                 "JOIN transactions t ON t.id=i.transaction_id WHERE a.action_type='hold_credit' AND a.state='executed'").fetchone()['paise']
        votes = conn.execute('SELECT helpful, count(*) AS n FROM agent_feedback GROUP BY helpful').fetchall()
    durations = [sum(float(v) for v in row['stage_durations'].values() if v is not None) for row in runs]
    by_actor = {}
    for row in actions:
        if row['state'] in ('executed', 'compensated'):
            by_actor[row['actor']] = by_actor.get(row['actor'], 0) + row['n']
    helpful = {row['helpful']: row['n'] for row in votes}
    autonomous = len(analyzed - escalated)
    evaluation = {mode: json.loads((EVAL_DIR / name).read_text(encoding='utf-8'))
                  for mode, name in (('fixture', 'results.json'), ('sarvam', 'results-sarvam.json')) if (EVAL_DIR / name).exists()}
    return {
        'scope': 'All local demo sessions. Counts only.',
        'cases_analyzed': len(analyzed),
        'handled_without_person': autonomous,
        'escalated': len(analyzed & escalated),
        'autonomy_rate': round(autonomous / len(analyzed), 3) if analyzed else None,
        'median_analysis_seconds': round(statistics.median(durations), 2) if durations else None,
        'actions_completed': by_actor,
        'actions_failed': sum(row['n'] for row in actions if row['state'] == 'failed'),
        'policy_violations': violations,
        'simulated_amount_held_paise': protected,
        'feedback': {'helpful': helpful.get(True, 0), 'not_helpful': helpful.get(False, 0)},
        'estimated_review_minutes_saved': autonomous * MANUAL_REVIEW_MINUTES,
        'estimate_basis': f'{MANUAL_REVIEW_MINUTES} minutes per manual review, a pilot assumption rather than a measurement.',
        'evaluation': evaluation,
    }
