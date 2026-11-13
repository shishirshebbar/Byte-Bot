from uuid import UUID
from fastapi import APIRouter, Request, Response, Query
from pydantic import ValidationError
from psycopg.types.json import Jsonb
from starlette.concurrency import run_in_threadpool
from .investigation_schemas import (CreateInvestigation, ContextPatch, Investigation,
                                    TextEvidence, ConfirmEvidence, EvidenceResult)
from .investigation_store import (owner_for, owned_case, snapshot, create_case, bump,
                                  add_evidence, not_found, save_answers)
from .uploads import json_body, screenshot_body
from .ocr import decode_image, EvidenceError
from .redaction import redact
from .audit import record

router = APIRouter(prefix='/investigations')


@router.post('', response_model=Investigation)
def create(payload: CreateInvestigation, request: Request, response: Response):
    with request.app.state.pool.connection() as conn:
        state, created = create_case(conn, owner_for(conn, request), payload.transaction_id)
    response.status_code = 201 if created else 200
    return state


@router.get('/{case_id}', response_model=Investigation)
def get_case(case_id: UUID, request: Request):
    with request.app.state.pool.connection() as conn:
        return snapshot(conn, owned_case(conn, owner_for(conn, request), case_id))


@router.patch('/{case_id}/context', response_model=Investigation)
def save_context(case_id: UUID, payload: ContextPatch, request: Request):
    with request.app.state.pool.connection() as conn:
        case = owned_case(conn, owner_for(conn, request), case_id, payload.expected_revision)
        changes = payload.model_dump(exclude_unset=True, exclude={'expected_revision'})
        save_answers(conn, case, changes)
        return snapshot(conn, owned_case(conn, case['owner_id'], case_id))


def check_case(request, case_id):
    with request.app.state.pool.connection() as conn:
        owned_case(conn, owner_for(conn, request), case_id)


def persist_evidence(request, case_id, revision, kind, text, metadata=None, notice=None):
    with request.app.state.pool.connection() as conn:
        case = owned_case(conn, owner_for(conn, request), case_id, revision)
        return add_evidence(conn, case, kind, text, metadata, notice)


def process_image(request, data, media):
    image, metadata = decode_image(data, media)
    try:
        text, notice = request.app.state.ocr.extract(image)
        from .safety import request_markers
        metadata['request_markers'] = request_markers(text)
        text = redact(text)[:10000]
        return text, metadata, notice if notice else (None if text else 'unreadable')
    finally:
        image.close()


@router.post('/{case_id}/evidence', response_model=EvidenceResult, status_code=201)
async def submit_evidence(case_id: UUID, request: Request):
    await run_in_threadpool(check_case, request, case_id)
    media = request.headers.get('content-type', '').split(';')[0].lower()
    if media == 'application/json':
        try:
            payload = TextEvidence.model_validate(await json_body(request))
        except ValidationError:
            raise EvidenceError(422, 'invalid_input', 'Check the supplied field values.') from None
        return await run_in_threadpool(persist_evidence, request, case_id, payload.expected_revision, payload.type, payload.text, {'request_markers': payload._request_markers})
    if media != 'multipart/form-data':
        raise EvidenceError(415, 'unsupported_evidence', 'Submit JSON text or a multipart PNG/JPEG screenshot.')
    data, image_media, revision = await screenshot_body(request)
    text, metadata, notice = await run_in_threadpool(process_image, request, data, image_media)
    del data
    return await run_in_threadpool(persist_evidence, request, case_id, revision, 'screenshot', text, metadata, notice)


@router.patch('/{case_id}/evidence/{evidence_id}', response_model=EvidenceResult)
def confirm(case_id: UUID, evidence_id: UUID, payload: ConfirmEvidence, request: Request):
    with request.app.state.pool.connection() as conn:
        case = owned_case(conn, owner_for(conn, request), case_id)
        item = conn.execute('SELECT * FROM evidence WHERE id=%s AND investigation_id=%s', (evidence_id, case_id)).fetchone()
        if item is None:
            raise not_found()
        owned_case(conn, case['owner_id'], case_id, payload.expected_revision)
        revision = case['input_revision']
        if item['review_state'] != 'confirmed' or item['confirmed_text'] != payload.text:
            item = conn.execute("UPDATE evidence SET confirmed_text=%s, review_state='confirmed', notice=NULL, metadata=%s, updated_at=now() "
                                'WHERE id=%s RETURNING *', (payload.text, Jsonb({**item['metadata'], 'request_markers': item['metadata'].get('request_markers', []) if payload.text == item['ocr_text'] else payload._request_markers}), evidence_id)).fetchone()
            revision = bump(conn, case_id)
            record(conn, case_id, 'evidence_updated', evidence_id=evidence_id)
        return {'evidence': item, 'input_revision': revision}


@router.delete('/{case_id}/evidence/{evidence_id}', status_code=204)
def remove(case_id: UUID, evidence_id: UUID, request: Request, expected_revision: int = Query(ge=0)):
    with request.app.state.pool.connection() as conn:
        case = owned_case(conn, owner_for(conn, request), case_id)
        if not conn.execute('SELECT id FROM evidence WHERE id=%s AND investigation_id=%s', (evidence_id, case_id)).fetchone():
            raise not_found()
        owned_case(conn, case['owner_id'], case_id, expected_revision)
        conn.execute('DELETE FROM evidence WHERE id=%s AND investigation_id=%s', (evidence_id, case_id))
        bump(conn, case_id)
        record(conn, case_id, 'evidence_removed', evidence_id=evidence_id)
    return Response(status_code=204)
