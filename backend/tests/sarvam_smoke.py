"""Optional live Sarvam check with synthetic content only.

Usage: python backend/tests/sarvam_smoke.py --live
Prints timings and extracted kinds. Saves no evidence, audio, or provider response.
Exit code 2 (PENDING) when SARVAM_API_KEY is not configured.
"""
import asyncio
import base64
import sys
import time
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bytebot.settings import SARVAM_API_KEY, SARVAM_CHAT_MODEL  # noqa: E402
from bytebot.sarvam import SarvamClient, SarvamProvider  # noqa: E402
from bytebot.extraction import extract  # noqa: E402
from bytebot.fixtures import SCENARIOS  # noqa: E402

SYNTHETIC_HINDI = 'मैंने गलती से पाँच हज़ार रुपये भेज दिए। तुरंत वापस करो, बैंक को मत बताना।'


def timed(label, function, *args):
    start = time.perf_counter()
    value = function(*args)
    print(f'{label}: {time.perf_counter() - start:.2f}s')
    return value


def main():
    if '--live' not in sys.argv:
        print('Pass --live to call Sarvam with synthetic content.')
        return 1
    if not SARVAM_API_KEY:
        print('PENDING: SARVAM_API_KEY is not configured; no provider request was made.')
        return 2
    client = SarvamClient(SARVAM_API_KEY, timeout=30)
    audio = base64.b64decode(timed('text-to-speech (synthetic Hindi voice note)', client.speak, SYNTHETIC_HINDI, 'hi-IN'))
    transcript, language = timed('speech-to-text', client.transcribe, audio, 'audio/wav', 'unknown')
    print(f'  detected {language}; transcript {len(transcript)} characters')
    english = timed('translate to English', client.translate, transcript, language, 'en-IN')
    print(f'  English: {english}')
    provider = SarvamProvider(SARVAM_API_KEY, SARVAM_CHAT_MODEL)
    for key in ('B', 'L', 'H', 'G'):
        evidence = [{'id': uuid4(), 'type': 'message', 'confirmed_text': SCENARIOS[key]['text']}]
        start = time.perf_counter()
        result = asyncio.run(extract(provider, evidence, {}))
        kinds = sorted({claim['kind'] for claim in result['claims']})
        print(f'extraction {key} ({SARVAM_CHAT_MODEL}): {time.perf_counter() - start:.2f}s · {result["status"]} · {kinds}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
