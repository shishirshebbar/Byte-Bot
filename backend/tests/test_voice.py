"""Sarvam voice notes, spoken guidance, the Sarvam extraction provider, and Hinglish rules."""
import asyncio
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from bytebot.main import create_app
from bytebot.fixtures import FixtureProvider
from bytebot.extraction import extract, PATTERNS
from bytebot.safety import request_markers
from bytebot.sarvam import SarvamProvider, SpeechUnavailable
from test_analysis import run_case
from test_agent import load, path, API

WAV = b'RIFF\x24\x00\x00\x00WAVEfmt ' + b'\x00' * 64
HINGLISH = 'Galti se paise bhej diye. Turant wapas karo, bank ko mat batana. OTP batao 482913.'


class FakeSpeech:
    configured = True

    def __init__(self, transcript=HINGLISH, language='hi-IN', fail=False):
        self.transcript, self.language, self.fail, self.calls = transcript, language, fail, []

    def transcribe(self, audio, media_type, language='unknown'):
        self.calls.append(('stt', len(audio), media_type, language))
        if self.fail:
            raise SpeechUnavailable('down')
        return self.transcript, self.language

    def translate(self, text, source, target):
        self.calls.append(('translate', text, source, target))
        return 'Money was sent by mistake. Return it immediately, do not tell the bank.' if target == 'en-IN' else f'[{target}] {text}'

    def speak(self, text, language):
        self.calls.append(('tts', text, language))
        return 'UklGRg=='


@pytest.fixture
def speech():
    return FakeSpeech()


@pytest.fixture
def client(prepared, speech):
    with TestClient(create_app(prepared, extraction_provider=FixtureProvider(), worker_enabled=False, speech=speech)) as client:
        client.get(API + '/transactions')
        yield client


def upload(client, case, data=WAV, media='audio/wav', language='unknown'):
    return client.post(path(case) + f'/voice?language={language}', data={'expected_revision': str(case['input_revision'])},
                       files={'file': ('note.wav', data, media)})


def test_voice_note_is_transcribed_translated_redacted_and_reviewed(client, speech):
    case = load(client, 'D')
    response = upload(client, case, language='hi-IN')
    assert response.status_code == 201, response.text
    item = response.json()['evidence']
    assert item['type'] == 'voice_note' and item['review_state'] == 'needs_review'
    assert 'Return it immediately' in item['ocr_text'] and 'Original (hi-IN): Galti se paise' in item['ocr_text']
    assert '482913' not in json.dumps(response.json())  # Credentials are redacted before storage.
    assert item['metadata']['language'] == 'hi-IN' and 'credential_request' in item['metadata']['request_markers']
    assert speech.calls[0][:2] == ('stt', len(WAV)) and speech.calls[0][3] == 'hi-IN'
    assert '482913' not in str(speech.calls[1])  # Translation receives redacted text only.
    # Like OCR, an unreviewed transcript blocks analysis until the customer confirms it.
    revision = response.json()['input_revision']
    assert client.post(path(case) + '/analyze', json={'expected_revision': revision}).status_code == 409
    confirmed = client.patch(path(case) + '/evidence/' + item['id'], json={'text': item['ocr_text'], 'confirmed': True, 'expected_revision': revision})
    assert confirmed.status_code == 200
    with client.app.state.pool.connection() as conn:
        assert 'filename' not in json.dumps(conn.execute('SELECT metadata FROM evidence WHERE id=%s', (item['id'],)).fetchone()['metadata'])


def test_voice_note_validation_and_outage(client, speech):
    case = load(client, 'D')
    assert upload(client, case, data=b'not audio at all', media='audio/wav').status_code == 415
    assert upload(client, case, media='image/png').status_code == 415
    assert upload(client, case, data=b'RIFF' + b'\x00' * (2 * 1024 * 1024)).status_code == 413
    assert upload(client, case, language='xx-YY').status_code == 422
    speech.fail = True
    failed = upload(client, case)
    assert failed.status_code == 503 and failed.json()['error']['code'] == 'speech_unavailable'
    assert client.get(path(case)).json()['evidence'] == []  # Nothing is stored on failure.


def test_spoken_guidance_uses_only_byte_bot_text(client, speech):
    case = load(client, 'B')
    assert client.post(path(case) + '/speak', json={'language': 'hi-IN'}).status_code == 409
    run_case(client, case)
    spoken = client.post(path(case) + '/speak', json={'language': 'ta-IN'})
    assert spoken.status_code == 200
    body = spoken.json()
    assert body['language'] == 'ta-IN' and body['audio_base64'] and body['text'].startswith('[ta-IN] Supported warning signs')
    tts = [call for call in speech.calls if call[0] == 'tts'][0]
    assert 'I will call the police' not in tts[1]  # Evidence never goes to text-to-speech.
    assert client.post(path(case) + '/speak', json={'language': 'fr-FR'}).status_code == 422


def test_hinglish_scenario_and_patterns(client):
    analysis = run_case(client, load(client, 'L'))
    kinds = {f['kind'] for f in analysis['result']['findings']}
    assert analysis['result']['category'] == 'High concern'
    assert {'threat', 'bank_avoidance', 'urgency', 'repayment'} <= kinds
    assert PATTERNS['repayment'].search('paise wapas bhej do')
    assert not PATTERNS['repayment'].search('paise wapas mat karo')
    assert request_markers('AnyDesk install karo aur OTP batao') == ['credential_request', 'remote_access']


class Transport(httpx.AsyncBaseTransport):
    def __init__(self, status, content):
        self.status, self.content, self.requests = status, content, []

    async def handle_async_request(self, request):
        self.requests.append(json.loads(request.content))
        return httpx.Response(self.status, json={'choices': [{'message': {'content': self.content}}]})


@pytest.mark.parametrize('status,expected', [(200, 'complete'), (403, 'unavailable'), (500, 'unavailable')])
def test_sarvam_provider_validates_claims_locally(monkeypatch, status, expected):
    content = json.dumps({'claims': [
        {'evidence_ref': 'E1', 'kind': 'repayment', 'quote': 'turant wapas karo', 'value': None},
        {'evidence_ref': 'E1', 'kind': 'amount', 'quote': 'INR 5000', 'value': 5000},
        {'evidence_ref': 'E1', 'kind': 'vpa', 'quote': '[VPA_1]', 'value': None},
        {'evidence_ref': 'E1', 'kind': 'threat', 'quote': 'warna police bulaunga', 'value': None}]})
    transport = Transport(status, '```json\n' + content + '\n```')
    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: real(transport=transport, **kwargs))
    evidence = [{'id': 'e1', 'type': 'message', 'confirmed_text': 'Galti se INR 5000 bhej diya, turant wapas karo refund.demo@upi pe, warna police bulaunga.'}]
    result = asyncio.run(extract(SarvamProvider('test-key'), evidence, {}))
    assert result['status'] == expected and result['provider_mode'] == 'sarvam'
    if status == 200:
        assert {c['kind'] for c in result['claims']} == {'repayment', 'amount', 'vpa', 'threat'}
        assert next(c for c in result['claims'] if c['kind'] == 'vpa')['value'] == 'refund.demo@upi'
        sent = json.dumps(transport.requests[0])
        assert 'refund.demo@upi' not in sent and '[VPA_1]' in sent  # Identifiers are masked before the provider.
    assert asyncio.run(extract(SarvamProvider(''), evidence, {}))['status'] == 'unavailable'
