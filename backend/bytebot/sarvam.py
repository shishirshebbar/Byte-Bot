"""Sarvam AI adapters: Indic speech-to-text, translation, text-to-speech, and extraction.

Privacy boundary: speech-to-text receives the customer's in-memory audio, which is
never stored. Translation and extraction receive only redacted, identifier-masked
text. Text-to-speech receives only Byte Bot's own guidance, never evidence. Error
bodies from the provider are never logged or returned.
"""
import json
import re
import httpx
from .extraction import ProviderUnavailable
from .prompts import EXTRACTION_PROMPT

BASE = 'https://api.sarvam.ai'
STT_MODEL, TRANSLATE_MODEL, TTS_MODEL, TTS_SPEAKER = 'saaras:v4', 'mayura:v1', 'bulbul:v3', 'priya'
LANGUAGES = {'en-IN': 'English', 'hi-IN': 'हिन्दी', 'bn-IN': 'বাংলা', 'ta-IN': 'தமிழ்', 'te-IN': 'తెలుగు',
             'kn-IN': 'ಕನ್ನಡ', 'ml-IN': 'മലയാളം', 'mr-IN': 'मराठी', 'gu-IN': 'ગુજરાતી', 'pa-IN': 'ਪੰਜਾਬੀ', 'od-IN': 'ଓଡ଼ିଆ'}
SCHEMA_HINT = ('Respond with one JSON object only: {"claims": [{"evidence_ref": "E1", "kind": "<kind>", '
               '"quote": "<exact contiguous substring of that evidence text>", "value": <string or null>}]}. '
               'Evidence may be English, Hindi, or Hinglish; quote it exactly as written.')


class SpeechUnavailable(Exception):
    pass


class SarvamClient:
    def __init__(self, key, timeout=20):
        self.key, self.timeout = key, timeout

    @property
    def configured(self):
        return bool(self.key)

    def _post(self, path, **kwargs):
        if not self.key:
            raise SpeechUnavailable('missing_configuration')
        try:
            response = httpx.post(BASE + path, headers={'api-subscription-key': self.key}, timeout=self.timeout, **kwargs)
        except httpx.HTTPError:
            raise SpeechUnavailable('provider_unreachable') from None
        if response.status_code != 200:
            raise SpeechUnavailable(f'provider_status_{response.status_code}')
        return response.json()

    def transcribe(self, audio, media_type, language='unknown'):
        data = self._post('/speech-to-text', files={'file': ('voice-note', audio, media_type)},
                          data={'model': STT_MODEL, 'language_code': language})
        return (data.get('transcript') or '').strip(), data.get('language_code') or language

    def translate(self, text, source, target):
        if not text or source == target:
            return text
        data = self._post('/translate', json={'input': text[:1000], 'source_language_code': source,
                                              'target_language_code': target, 'model': TRANSLATE_MODEL})
        return (data.get('translated_text') or '').strip()

    def speak(self, text, language):
        data = self._post('/text-to-speech', json={'text': text[:1500], 'language_code': language,
                                                   'model': TTS_MODEL, 'speaker': TTS_SPEAKER})
        audios = data.get('audios') or []
        if not audios:
            raise SpeechUnavailable('empty_audio')
        return audios[0]


class SarvamProvider:
    """Schema-validated extraction with Sarvam's conversational model. Citations are re-checked locally."""
    mode = 'sarvam'

    def __init__(self, key='', model='sarvam-105b-conversations'):
        self.key, self.model = key, model

    async def extract(self, texts):
        if not self.key:
            raise ProviderUnavailable('missing_configuration')
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.post(BASE + '/v1/chat/completions', headers={'api-subscription-key': self.key}, json={
                'model': self.model, 'temperature': 0, 'reasoning_effort': 'low', 'max_tokens': 1500,
                'response_format': {'type': 'json_object'},
                'messages': [{'role': 'system', 'content': EXTRACTION_PROMPT + '\n' + SCHEMA_HINT},
                             {'role': 'user', 'content': json.dumps(texts, ensure_ascii=False)}]})
        if response.status_code in (401, 403):
            raise ProviderUnavailable('authentication')
        if response.status_code != 200:
            raise ValueError('Invalid provider response')
        content = (response.json().get('choices') or [{}])[0].get('message', {}).get('content') or ''
        content = re.sub(r'^```(?:json)?|```$', '', content.strip()).strip()
        raw = json.loads(content)
        # The model may return numbers; the schema stores every value as text.
        for claim in raw.get('claims', []) if isinstance(raw, dict) else []:
            if isinstance(claim, dict) and claim.get('value') is not None and not isinstance(claim['value'], str):
                claim['value'] = str(claim['value'])
            # A bare placeholder quote names its own identifier; local validation still checks it.
            if isinstance(claim, dict) and claim.get('kind') in ('vpa', 'phone') and not claim.get('value') \
                    and re.fullmatch(r'\[(?:VPA|PHONE)_\d+\]', str(claim.get('quote', ''))):
                claim['value'] = claim['quote']
        return raw
