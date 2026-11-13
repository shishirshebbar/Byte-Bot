"""Opt-in live Gemini check using synthetic evidence only. No evidence is saved."""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from uuid import uuid4
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bytebot.settings import GEMINI_API_KEY, GEMINI_MODEL
from bytebot.extraction import GeminiProvider, extract
from bytebot.fixtures import SCENARIOS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', required=True)
    parser.parse_args()
    if not GEMINI_API_KEY or not GEMINI_MODEL:
        print('PENDING: configure a local GEMINI_API_KEY and GEMINI_MODEL for this optional check.')
        return 2
    evidence = [{'id': uuid4(), 'type': 'message', 'confirmed_text': SCENARIOS['A']['text']}]
    start = time.monotonic()
    output = asyncio.run(extract(GeminiProvider(GEMINI_API_KEY, GEMINI_MODEL), evidence, {}))
    kinds = sorted({item['kind'] for item in output['claims']})
    print(json.dumps({'model': GEMINI_MODEL, 'status': output['status'], 'kinds': kinds,
                      'duration_seconds': round(time.monotonic()-start, 2)}))
    return 0 if output['status'] == 'complete' and {'repayment','vpa','urgency'}.issubset(kinds) else 1


if __name__ == '__main__':
    sys.exit(main())
