"""Case 1: verify a claimed payment against the customer's own Paytm history.

"I sent you ₹5,000" is checked before anything else: did that money actually arrive?
Nothing is stored. The message is redacted and analysed locally (no provider call).
"""
import re
from uuid import UUID
from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field
from .investigation_store import owner_for
from .redaction import redact
from .safety import request_markers
from .extraction import PATTERNS, VPA
from .intelligence import lookup, graph_links, normalize
from .risk_rules import OUTGOING, rupees

router = APIRouter()
AMOUNT = re.compile(r'(?:₹|\bINR|\bRs\.?)\s?(\d{1,3}(?:,\d{2,3})+|\d+)(?:\.(\d{1,2}))?', re.I)
CLAIM = re.compile(r'\b(?:I|we)\s+(?:have\s+)?(?:sent|transferred|paid|credited)\b|\bbhej(?:a|e|i)?\b|\bgalti se\b', re.I)
PRESSURE = ('urgency', 'threat', 'bank_avoidance', 'secrecy')


class ClaimCheck(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str | None = Field(default=None, max_length=2000)
    sender: str | None = Field(default=None, max_length=80)
    amount_paise: int | None = Field(default=None, gt=0, lt=10_000_000_00)


def parse_amount(text):
    found = AMOUNT.search(text or '')
    if not found:
        return None
    return int(found.group(1).replace(',', '')) * 100 + int((found.group(2) or '0').ljust(2, '0'))


def sender_matches(row, hint, vpas):
    if any(normalize('vpa', v) == normalize('vpa', row['sender_vpa']) for v in vpas):
        return True
    if not hint:
        return False
    hint = hint.strip().casefold()
    if VPA.fullmatch(hint):
        return hint == normalize('vpa', row['sender_vpa'])
    tokens = [t for t in re.split(r'\s+', hint) if len(t) >= 2]
    return bool(tokens) and all(t in row['sender_name'].casefold() for t in tokens)


def verdict(status, amount, hint, matches):
    who = f' from {hint.strip()}' if hint else ''
    money = rupees(amount) if amount else 'the claimed'
    if status == 'not_found':
        return {'tone': 'danger', 'label': 'Scam warning', 'title': "The claimed payment can't be verified",
                'message': f'No {money} credit{who} is in your Paytm history. Do not send money back. '
                           'Fake "payment received" messages and screenshots are a common scam. '
                           'If a payment is genuinely delayed, it will appear here as pending.'}
    if status == 'not_completed':
        return {'tone': 'info', 'label': 'Payment not complete', 'title': 'This payment has not completed',
                'message': f"The matching payment is {matches[0]['status']}. Money that has not arrived can't be owed back. Don't send anything."}
    if status == 'verified':
        return {'tone': 'caution', 'label': 'Payment found', 'title': 'The money really arrived',
                'message': 'The payment is genuine. That alone does not make a repayment request safe. Ask Byte Bot to check the request before doing anything.'}
    if status == 'ambiguous':
        return {'tone': 'caution', 'label': 'Which payment?', 'title': f'Found {len(matches)} credit{"s" if len(matches) != 1 else ""} of {money}',
                'message': 'Tell Byte Bot who says they sent it, or open the matching payment to check the request.'}
    return {'tone': 'info', 'label': 'Need the amount', 'title': 'How much do they say they sent?',
            'message': 'Add the amount (for example ₹5,000) so Byte Bot can search your history.'}


def story(status, matches, kinds, intel):
    arrived = {
        'not_found': ('fail', 'No. There is no matching credit in your Paytm history.'),
        'not_completed': ('warn', 'Not yet. The matching payment has not completed.'),
        'verified': ('pass', f"Yes. {rupees(matches[0]['amount_paise'])} from {matches[0]['sender_name']} is in your history." if matches else 'Yes.'),
        'ambiguous': ('warn', 'Possibly. More than one credit matches; confirm the sender.'),
        'need_amount': ('warn', 'Unknown until the claimed amount is given.'),
    }[status]
    steps = [{'id': 'arrived', 'question': 'Did the money actually arrive?', 'status': arrived[0], 'answer': arrived[1]}]
    asks = (['scan a QR code'] if 'qr_payment' in kinds else []) + (['approve a collect request'] if 'collect_approval' in kinds else []) \
        + (['enter or share your UPI PIN or OTP'] if kinds & {'pin_to_receive', 'credential_request'} else []) \
        + (['give someone control of your screen'] if kinds & {'remote_access', 'screen_sharing'} else [])
    if not asks and 'repayment' in kinds:
        asks = ['send the money back']
    steps.append({'id': 'asked', 'question': 'What exactly are you being asked to do?',
                  'status': 'warn' if asks else 'pass', 'answer': ('To ' + ', '.join(asks) + '.') if asks else 'No request was found in the message.'})
    out = kinds & OUTGOING
    steps.append({'id': 'sends_out', 'question': 'Would that send money from your account?',
                  'status': 'fail' if out or (asks and status == 'not_found') else 'warn' if asks else 'pass',
                  'answer': 'Yes. It starts a payment out of your account.' if out else
                            ('Yes, and for money that never arrived.' if asks and status == 'not_found' else
                             'Yes. A repayment is a new outgoing payment.' if asks else 'No outgoing payment was requested.')})
    tactics = [k.replace('_', ' ') for k in PRESSURE if k in kinds]
    steps.append({'id': 'pressure', 'question': 'Is there evidence of social engineering?', 'status': 'warn' if tactics else 'pass',
                  'answer': ('Yes: ' + ', '.join(tactics) + '.') if tactics else 'No pressure tactics were found in the message.'})
    steps.append({'id': 'intel', 'question': 'Is there relevant fraud intelligence?', 'status': 'fail' if intel else 'pass',
                  'answer': intel[0] if intel else 'No match in the available demo intelligence. This is not a safety guarantee.'})
    safest = {'not_found': "Don't send any money. Block the contact and report the message from the chat.",
              'not_completed': "Don't send anything until the payment completes.",
              'verified': 'Open the payment and let Byte Bot check the repayment request.',
              'ambiguous': 'Pick the payment they mean, or add who sent it.',
              'need_amount': 'Add the claimed amount.'}[status]
    steps.append({'id': 'safest', 'question': "What's the safest next action?", 'status': 'pass', 'answer': safest})
    return steps


@router.post('/claim-check')
def claim_check(payload: ClaimCheck, request: Request):
    raw = payload.text or ''
    kinds = set(request_markers(raw))  # Markers come from the raw text, before redaction.
    text = redact(raw) if raw else ''
    kinds |= {kind for kind, pattern in PATTERNS.items() if pattern.search(text)}
    amount = payload.amount_paise or parse_amount(text)
    vpas = sorted({m.group().casefold() for m in VPA.finditer(text)})
    with request.app.state.pool.connection() as conn:
        owner = owner_for(conn, request)
        rows = conn.execute("SELECT id, amount_paise, sender_name, sender_vpa, occurred_at, status FROM transactions "
                            "WHERE owner_id=%s AND direction='incoming' AND amount_paise=%s ORDER BY occurred_at DESC",
                            (owner, amount)).fetchall() if amount else []
        identifiers = [('vpa', v) for v in vpas]
        if payload.sender and VPA.fullmatch(payload.sender.strip()):
            identifiers.append(('vpa', payload.sender.strip()))
        intel = [f"{m['identifier']} matches simulated incident {m['incident_reference']}. A match is not proof of guilt." for m in lookup(conn, identifiers)]
        intel += [f"{l['identifier']} is linked to {len(l['incidents'])} reported incident{'s' if len(l['incidents']) != 1 else ''} in the simulated graph. "
                  'A link is not proof of guilt.' for l in graph_links(conn, identifiers)]
    hinted = bool(payload.sender and payload.sender.strip()) or bool(vpas)
    matches = [r for r in rows if sender_matches(r, payload.sender, vpas)] if hinted else rows
    if not amount:
        status = 'need_amount'
    elif not matches:
        status = 'not_found'
    elif not hinted and len(matches) > 1:
        status = 'ambiguous'
    elif any(m['status'] == 'successful' for m in matches):
        status = 'verified'
        matches = [m for m in matches if m['status'] == 'successful']
    else:
        status = 'not_completed'
    return {'status': status, 'claimed_amount_paise': amount, 'claims_payment': bool(CLAIM.search(text)),
            'matches': [{'transaction_id': str(m['id']), 'amount_paise': m['amount_paise'], 'sender_name': m['sender_name'],
                         'sender_vpa': m['sender_vpa'], 'status': m['status'], 'occurred_at': m['occurred_at'].isoformat()} for m in matches[:5]],
            'headline': verdict(status, amount, payload.sender, matches), 'story': story(status, matches, kinds, intel),
            'stored': False}
