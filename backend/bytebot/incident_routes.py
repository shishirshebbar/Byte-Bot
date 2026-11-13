from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Request, Response
from .analysis_schemas import AnalyzeRequest
from .audit import record
from .investigation_store import owner_for, owned_case
from .ocr import EvidenceError
from .report_schemas import Incident, IncidentList, ReportSnapshot, StatusPatch
from .reports import generate, retrieve, format_text

router = APIRouter()


def incident(conn, case):
    transaction = conn.execute('SELECT * FROM transactions WHERE id=%s AND owner_id=%s',
                               (case['transaction_id'], case['owner_id'])).fetchone()
    assessment = conn.execute("SELECT a.data->>'category' AS category FROM analysis_runs r "
        "JOIN risk_assessments a ON a.run_id=r.id WHERE r.investigation_id=%s "
        "AND r.input_revision=%s AND r.state='complete'", (case['id'], case['input_revision'])).fetchone()
    return {**case, 'transaction': transaction, 'category': assessment['category'] if assessment else None}


@router.get('/incidents', response_model=IncidentList)
def list_incidents(request: Request):
    with request.app.state.pool.connection() as conn:
        owner = owner_for(conn, request)
        # One SQL snapshot prevents a category from becoming stale mid-list.
        rows = conn.execute("SELECT i.id,i.created_at,i.case_status,i.status_revision,"
            "to_jsonb(t) AS transaction,a.data->>'category' AS category FROM investigations i "
            "JOIN transactions t ON t.id=i.transaction_id AND t.owner_id=i.owner_id "
            "LEFT JOIN analysis_runs r ON r.investigation_id=i.id AND r.input_revision=i.input_revision AND r.state='complete' "
            "LEFT JOIN risk_assessments a ON a.run_id=r.id WHERE i.owner_id=%s ORDER BY i.created_at DESC,i.id DESC", (owner,)).fetchall()
        return {'incidents': rows}


@router.patch('/incidents/{case_id}/status', response_model=Incident)
def update_status(case_id: UUID, payload: StatusPatch, request: Request):
    with request.app.state.pool.connection() as conn:
        case = owned_case(conn, owner_for(conn, request), case_id)
        if case['status_revision'] != payload.expected_status_revision:
            raise EvidenceError(409, 'stale_status', 'This case status changed. Reload the saved status before updating it.')
        if case['case_status'] != payload.status:
            previous = case['case_status']
            case = conn.execute('UPDATE investigations SET case_status=%s,status_revision=status_revision+1,updated_at=now() WHERE id=%s RETURNING *',
                                (payload.status, case_id)).fetchone()
            record(conn, case_id, 'status_updated', from_status=previous, to_status=payload.status, status_revision=case['status_revision'])
        return incident(conn, case)


@router.post('/investigations/{case_id}/report', response_model=ReportSnapshot)
def create_report(case_id: UUID, payload: AnalyzeRequest, request: Request, response: Response):
    with request.app.state.pool.connection() as conn:
        case = owned_case(conn, owner_for(conn, request), case_id, payload.expected_revision)
        report, created = generate(conn, case)
    response.status_code = 201 if created else 200
    return report


@router.get('/investigations/{case_id}/report', response_model=ReportSnapshot)
def get_report(case_id: UUID, request: Request, format: Literal['json', 'txt'] = 'json'):
    with request.app.state.pool.connection() as conn:
        report = retrieve(conn, owned_case(conn, owner_for(conn, request), case_id))
    if format == 'txt':
        return Response(format_text(report), media_type='text/plain; charset=utf-8',
                        headers={'Content-Disposition': f'attachment; filename="bytebot-report-{report.id}.txt"',
                                 'X-Content-Type-Options': 'nosniff'})
    return report
