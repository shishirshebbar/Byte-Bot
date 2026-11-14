"""Privacy boundary, structured provider adapter, and citation validation."""
import asyncio
import json
import re
from decimal import Decimal, InvalidOperation
from .analysis_schemas import Extraction
from .prompts import EXTRACTION_PROMPT
from .redaction import redact
from .safety import request_markers, NEGATION

VPA = re.compile(r'(?<![\w.])[\w.+-]{2,}@[a-zA-Z][a-zA-Z0-9_-]{1,}(?!\w)')
PHONE = re.compile(r'(?<!\w)\+?\d[\d -]{8,}\d(?!\w)')
EMAIL = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')
PATTERNS = {
    'repayment': re.compile(r'\b(?:return|repay|(?:send|bring|give|pay) (?:it|the money|the amount|that) back|refund|wapas (?:karo|kar do|bhejo|bhej do|kijiye)|lauta (?:do|dijiye)|lautao)\b', re.I),
    'urgency': re.compile(r'\b(?:immediately|urgent|right now|within \d+ minutes|hurry|turant|abhi ke abhi|jaldi karo|fauran)\b', re.I),
    'threat': re.compile(r'\b(?:I will (?:(?:call|contact) (?:the )?police|file a police complaint|block your account|expose you|take legal action)|threaten(?:ed|ing)?|you will be arrested|(?:warna )?police (?:ko )?bula(?:unga|ungi|enge)|police complaint kar(?:unga|ungi|enge)|case kar d(?:unga|ungi|enge)|jail bhej d(?:unga|ungi|enge))\b', re.I),
    'bank_avoidance': re.compile(r"\b(?:(?:do not|don't|never)\s+(?:contact|call|tell)\s+(?:your |the )?bank|bank (?:ko|se) (?:mat|na) (?:batana|batao|bolna|bolo|call karna|contact karna))\b", re.I),
    'secrecy': re.compile(r"\b(?:keep (?:it|this) secret|do not tell|don't tell|kisi ko mat (?:batana|batao))\b", re.I),
}


def prepare(evidence, transaction):
    mapping, texts, sources = {}, [], {}
    def placeholder(kind, raw):
        normalized = raw.casefold().strip() if kind == 'vpa' else re.sub(r'[^\d+]', '', raw)
        for token, item in mapping.items():
            if item == (kind, normalized):
                return token
        token = f'[{kind.upper()}_{len(mapping)+1}]'
        mapping[token] = (kind, normalized)
        return token
    for i, item in enumerate(evidence, 1):
        text = redact(item['confirmed_text'])
        # These facts are not needed by the extractor and never leave the server.
        for field in ('reference', 'sender_name'):
            value = str(transaction.get(field) or '')
            if value:
                text = re.sub(re.escape(value), '[PERSONAL_DATA]', text, flags=re.I)
        text = EMAIL.sub('[EMAIL]', text)
        text = VPA.sub(lambda m: placeholder('vpa', m.group()), text)
        text = PHONE.sub(lambda m: placeholder('phone', m.group()), text)
        ref = f'E{i}'
        texts.append({'evidence_ref': ref, 'text': text})
        sources[ref] = item
    return texts, sources, mapping


def validated_claims(raw, texts, sources, mapping):
    parsed = Extraction.model_validate(raw)
    by_ref = {item['evidence_ref']: item['text'] for item in texts}
    accepted, dropped = [], 0
    for claim in parsed.claims:
        quote = claim.quote
        if claim.evidence_ref not in by_ref or quote not in by_ref[claim.evidence_ref]:
            dropped += 1
            continue
        value = None
        valid = False
        if claim.kind in ('vpa', 'phone'):
            if claim.value in mapping and claim.value in quote and mapping[claim.value][0] == claim.kind:
                value = mapping[claim.value][1]
                valid = True
        elif claim.kind == 'amount':
            try:
                number = Decimal(claim.value or '')
                valid = number.is_finite() and 0 <= number <= 1000000000000 and number * 100 == (number * 100).to_integral_value()
                numbers = re.findall(r'(?<![\w\d])\d[\d,]*(?:\.\d{1,2})?(?![\w\d])', quote)
                valid = valid and any(Decimal(n.replace(',', '')) == number for n in numbers)
                if valid:
                    value = int(number * 100)
            except (InvalidOperation, ValueError, OverflowError):
                pass
        elif claim.kind in ('credential_request', 'collect_approval', 'remote_access', 'screen_sharing'):
            valid = claim.kind in request_markers(quote)
        else:
            valid = bool(PATTERNS[claim.kind].search(quote))
        if claim.kind in ('repayment', 'urgency', 'threat', 'credential_request', 'collect_approval', 'remote_access', 'screen_sharing'):
            source = by_ref[claim.evidence_ref]
            # A model cannot turn 'do not return' into a positive request by
            # quoting only the word 'return'. Inspect its source context.
            contexts = []
            for hit in re.finditer(re.escape(quote), source):
                prefix = re.split(r'[.!?\n]', source[max(0, hit.start()-120):hit.start()])[-1]
                contexts.append(prefix + quote)
            valid = valid and any(not NEGATION.search(context) for context in contexts)
        if not valid:
            dropped += 1
            continue
        local_quote = quote
        for token, (_, identifier) in mapping.items():
            local_quote = local_quote.replace(token, identifier)
        supplied = by_ref[claim.evidence_ref]
        # Entity extraction alone does not make an identifier a repayment destination.
        # Determine that relationship from the supplied text, never a model assertion.
        destination = bool(claim.kind == 'vpa' and re.search(
            r'\b(?:return|repay|refund|send (?:it|the money|the amount) back)\b[^.!?\n]{0,100}\bto\s+(?:(?:UPI ID|VPA)\s+)?'
            + re.escape(claim.value or ''), supplied, re.I))
        contact = bool(claim.kind == 'phone' and re.search(
            r'\b(?:caller|phone|contact number|called from|call)\b[^.!?\n]{0,30}' + re.escape(claim.value or ''), supplied, re.I))
        accepted.append({'kind': claim.kind, 'value': value, 'quote': local_quote,
                         'requested_destination': destination, 'intel_relevant': destination or contact,
                         'evidence_id': str(sources[claim.evidence_ref]['id']),
                         'evidence_type': sources[claim.evidence_ref]['type']})
    return accepted, dropped


class ProviderUnavailable(Exception):
    pass


class GeminiProvider:
    mode = 'gemini'

    def __init__(self, key='', model=''):
        self.key, self.model = key, model

    async def extract(self, texts):
        if not self.key or not self.model:
            raise ProviderUnavailable('missing_configuration')
        from google import genai
        from google.genai import types
        # SDK retries are disabled; the wrapper owns the single retry budget.
        async with genai.Client(api_key=self.key, http_options=types.HttpOptions(
                timeout=8000, retry_options=types.HttpRetryOptions(attempts=1))).aio as client:
            result = await client.models.generate_content(
                model=self.model, contents=json.dumps(texts),
                config=types.GenerateContentConfig(system_instruction=EXTRACTION_PROMPT,
                    response_mime_type='application/json', response_schema=Extraction,
                    temperature=0, max_output_tokens=8192))
            if not isinstance(result.text, str):
                raise ValueError('Invalid provider output')
            return json.loads(result.text)


async def extract(provider, evidence, transaction):
    if provider.mode == 'fixture':
        from .fixtures import SCENARIOS
        allowed = {item['text'] for item in SCENARIOS.values() if item['text']}
        if any(item['confirmed_text'] not in allowed for item in evidence):
            return {'claims': [], 'status': 'unavailable', 'provider_mode': 'fixture',
                    'notices': ['Evidence extraction is unavailable. Only supported local facts and saved answers were used.']}
    if not evidence:
        return {'claims': [], 'status': 'not_needed', 'notices': [], 'provider_mode': provider.mode}
    texts, sources, mapping = prepare(evidence, transaction)
    for attempt in range(2):
        try:
            raw = await asyncio.wait_for(provider.extract(texts), timeout=8)
            claims, dropped = validated_claims(raw, texts, sources, mapping)
            return {'claims': claims, 'status': 'partial' if dropped else 'complete',
                    'notices': ['Unsupported extraction claims were discarded.'] if dropped else [],
                    'provider_mode': provider.mode}
        except ProviderUnavailable:
            break
        except (TimeoutError, ValueError):
            if attempt == 0:
                continue
        except Exception as exc:
            # Retry transport timeouts, never authentication/configuration or
            # arbitrary provider errors. Error content never crosses the boundary.
            import httpx
            if isinstance(exc, httpx.TimeoutException) and attempt == 0:
                continue
            break
    return {'claims': [], 'status': 'unavailable', 'provider_mode': provider.mode,
            'notices': ['Evidence extraction is unavailable. Only supported local facts and saved answers were used.']}
