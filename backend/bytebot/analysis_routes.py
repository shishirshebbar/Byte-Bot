from uuid import UUID
from fastapi import APIRouter, Request
from .analysis_schemas import AnalyzeRequest, AnalysisStatus
from .analysis_store import enqueue
from .investigation_store import owner_for

router = APIRouter(prefix='/investigations')


@router.post('/{case_id}/analyze', response_model=AnalysisStatus, status_code=202)
def analyze(case_id: UUID, payload: AnalyzeRequest, request: Request):
    with request.app.state.pool.connection() as conn:
        return enqueue(conn, owner_for(conn, request), case_id, payload.expected_revision,
                       request.app.state.extractor.mode)
