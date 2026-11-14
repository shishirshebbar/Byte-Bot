"""Sarvam voice: transcribe a customer's voice note, and speak Byte Bot's guidance in their language."""
from uuid import UUID
from fastapi import APIRouter, Request, Query
from starlette.concurrency import run_in_threadpool
from .investigation_schemas import EvidenceResult, SpeakRequest
from .investigation_store import owner_for, owned_case, add_evidence
from .investigations import check_case
from .uploads import screenshot_body
from .redaction import redact
from .safety import request_markers
from .sarvam import SpeechUnavailable, LANGUAGES
from .ocr import EvidenceError

router = APIRouter(prefix='/investigations')
AUDIO_LIMIT = 2 * 1024 * 1024
AUDIO_TYPES = ('audio/webm', 'audio/ogg', 'audio/wav', 'audio/x-wav', 'audio/wave', 'audio/mpeg', 'audio/mp4', 'audio/aac', 'video/webm')
LANGUAGE_CODES = tuple(LANGUAGES) + ('unknown',)


def audio_like(data):
    """Check container magic bytes so that arbitrary files are not forwarded."""
    return (data[:4] in (b'RIFF', b'OggS', b'\x1a\x45\xdf\xa3', b'fLaC') or data[:3] == b'ID3'
            or data[:2] in (b'\xff\xfb', b'\xff\xf3', b'\xff\xf1', b'\xff\xf9') or data[4:8] == b'ftyp')


def transcribe(request, data, media, language):
    speech = request.app.state.speech
    try:
        original, detected = speech.transcribe(data, media, language)
        if not original:
            raise EvidenceError(422, 'speech_unreadable', 'No speech was recognised. Record again or type a call summary.')
        raw_markers = set(request_markers(original))  # Before redaction, as for screenshots.
        original = redact(original)[:4000]
        english = original if detected == 'en-IN' else redact(speech.translate(original, detected, 'en-IN'))[:4000]
    except SpeechUnavailable:
        raise EvidenceError(503, 'speech_unavailable', 'Voice transcription is unavailable. Type a call summary instead.') from None
    text = original if english == original else f'{english}\n\nOriginal ({detected}): {original}'
    # Markers are computed from both versions so local safety checks cover Hinglish too.
    markers = sorted(raw_markers | set(request_markers(english)))
    return text[:10000], {'request_markers': markers, 'language': detected, 'source': 'Sarvam speech-to-text'}


@router.post('/{case_id}/voice', response_model=EvidenceResult, status_code=201)
async def voice_note(case_id: UUID, request: Request, language: str = Query(default='unknown')):
    if language not in LANGUAGE_CODES:
        raise EvidenceError(422, 'invalid_input', 'Choose a supported language.')
    await run_in_threadpool(check_case, request, case_id)
    data, media, revision = await screenshot_body(request, AUDIO_LIMIT, 'voice note')
    media = media.split(';')[0].strip().lower()
    if media not in AUDIO_TYPES or not audio_like(data):
        raise EvidenceError(415, 'unsupported_evidence', 'Record a voice note or upload WebM, OGG, WAV, MP3, or M4A audio.')
    text, metadata = await run_in_threadpool(transcribe, request, data, media, language)
    del data  # Audio is never stored.

    def persist():
        with request.app.state.pool.connection() as conn:
            case = owned_case(conn, owner_for(conn, request), case_id, revision)
            return add_evidence(conn, case, 'voice_note', text, metadata)
    return await run_in_threadpool(persist)


@router.post('/{case_id}/speak')
def speak(case_id: UUID, payload: SpeakRequest, request: Request):
    """Read Byte Bot's own summary aloud. Evidence text is never sent to text-to-speech."""
    from .analysis_store import status
    with request.app.state.pool.connection() as conn:
        case = owned_case(conn, owner_for(conn, request), case_id)
        current = status(conn, case)
    result = current and current['result']
    if not result:
        raise EvidenceError(409, 'result_unavailable', 'Analyze the case before listening to its guidance.')
    english = f"{result['summary']} {result['recommendations'][0] if result['recommendations'] else ''}".strip()
    speech = request.app.state.speech
    try:
        text = speech.translate(english, 'en-IN', payload.language)
        audio = speech.speak(text, payload.language)
    except SpeechUnavailable:
        raise EvidenceError(503, 'speech_unavailable', 'Spoken guidance is unavailable right now.') from None
    return {'language': payload.language, 'text': text, 'audio_base64': audio, 'media_type': 'audio/wav'}
