"""Synthetic scenario preparation and atomic, owner-scoped reset."""
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Request, Response, Body
from pydantic import BaseModel, ConfigDict
from .fixtures import SCENARIOS, SCENARIO_LABELS, scenario_answers
from .investigation_schemas import Investigation, TextEvidence
from .investigation_store import (owner_for, create_case, owned_case, snapshot,
                                  save_answers, add_evidence, not_found)
from .sessions import lock_owner, copy_transaction
from .seeds import TEMPLATES
from .ocr import EvidenceError

router = APIRouter(prefix='/demo')


class LoadRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    evidence_mode: Literal['text', 'manual'] = 'text'


class ResetRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')


class LoadedScenario(BaseModel):
    scenario_id: str
    transaction_id: UUID
    investigation: Investigation
    created: bool


@router.get('/scenarios')
def scenarios(request: Request):
    return {'extraction_mode': request.app.state.extractor.mode, 'scenarios': [
        {'id': key, 'title': SCENARIO_LABELS[key][0], 'description': SCENARIO_LABELS[key][1],
         'evidence_text': fixture['text']} for key, fixture in SCENARIOS.items()]}


@router.post('/scenarios/{scenario_id}/load', response_model=LoadedScenario)
def load(scenario_id: str, request: Request, response: Response,
         payload: LoadRequest = Body(default=LoadRequest())):
    with request.app.state.pool.connection() as conn:
        owner = owner_for(conn, request)
        if scenario_id not in SCENARIOS:
            raise not_found()
        lock_owner(conn, owner)
        key = f'scenario-{scenario_id.lower()}'
        if not conn.execute('SELECT 1 FROM transaction_templates WHERE template_key=%s', (key,)).fetchone():
            raise EvidenceError(503, 'demo_unavailable', 'Demo templates are unavailable. Run the seed command.')
        copy_transaction(conn, owner, key)
        transaction = conn.execute('SELECT id FROM transactions WHERE owner_id=%s AND template_key=%s',
                                   (owner, key)).fetchone()
        state, created = create_case(conn, owner, transaction['id'])
        if created:
            case = owned_case(conn, owner, state['id'])
            save_answers(conn, case, scenario_answers(scenario_id))
            text = SCENARIOS[scenario_id]['text']
            if text and payload.evidence_mode == 'text':
                evidence = TextEvidence(type='message', text=text, expected_revision=case['input_revision'])
                metadata = {'request_markers': evidence._request_markers}
                if SCENARIOS[scenario_id].get('qr'):
                    # The synthetic refund QR is decoded for real, exactly like an upload.
                    metadata['qr_payments'] = demo_qr(SCENARIOS[scenario_id]['qr'])
                add_evidence(conn, case, evidence.type, evidence.text, metadata)
            state = snapshot(conn, owned_case(conn, owner, case['id']))
    response.status_code = 201 if created else 200
    return {'scenario_id': scenario_id, 'transaction_id': transaction['id'],
            'investigation': state, 'created': created}


def demo_qr(name):
    from pathlib import Path
    from PIL import Image
    from . import qr
    with Image.open(Path(__file__).parent / 'demo_assets' / name) as image:
        return qr.payment_intents(image.convert('RGB'))


def reset_session(conn, owner):
    lock_owner(conn, owner)
    keys = [row[0] for row in TEMPLATES]
    available = conn.execute('SELECT template_key FROM transaction_templates WHERE template_key=ANY(%s)',
                             (keys,)).fetchall()
    if len(available) != len(keys):
        raise EvidenceError(503, 'demo_unavailable', 'Demo templates are unavailable. Run the seed command.')
    # Writers lock case then run. Creation/load lock owner first. Never hold a
    # case lock while waiting for the owner, and never hold locks during OCR/LLM.
    conn.execute('SELECT id FROM investigations WHERE owner_id=%s ORDER BY id FOR UPDATE', (owner,)).fetchall()
    conn.execute('DELETE FROM investigations WHERE owner_id=%s', (owner,))
    conn.execute('DELETE FROM transactions WHERE owner_id=%s', (owner,))
    for key in keys:
        copy_transaction(conn, owner, key)
    return {'status': 'reset', 'transaction_count': len(keys)}


@router.post('/reset')
def reset(request: Request, payload: ResetRequest | None = Body(default=None)):
    with request.app.state.pool.connection() as conn:
        return reset_session(conn, owner_for(conn, request))
