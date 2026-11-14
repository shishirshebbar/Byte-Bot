"""Versioned categorical decision table, independent of the provider."""
from datetime import datetime, timezone
from .analysis_schemas import Assessment, RULE_VERSION, SCORE_VERSION
from .intelligence import normalize
from .extraction import VPA

PRESSURE = {'urgency': 'urgency', 'threat': 'threat', 'bank_avoidance': 'isolation', 'secrecy': 'isolation'}
DANGEROUS = {'credential_request', 'collect_approval', 'remote_access', 'screen_sharing', 'qr_payment', 'pin_to_receive'}
# Requests whose mechanism starts a payment *out of* the customer's account.
OUTGOING = {'qr_payment', 'pin_to_receive', 'collect_approval'}
LABELS = {
    'urgency': 'Urgency was reported or observed.', 'threat': 'Threats were reported or observed.',
    'bank_avoidance': 'A request to avoid contacting the bank was reported or observed.',
    'secrecy': 'A request for secrecy was reported or observed.',
    'repayment': 'A repayment request was reported or observed.',
    'credential_request': 'A request to disclose a credential was detected; never share a PIN or OTP.',
    'collect_approval': 'A request to approve a collect/payment request was detected.',
    'remote_access': 'A request to enable remote access was detected.',
    'screen_sharing': 'A request to share the screen was detected.',
    'qr_payment': 'A request to scan a QR code to return money was detected. Scanning a UPI QR sends money; it never receives it.',
    'pin_to_receive': 'A request to enter a UPI PIN to receive or return money was detected. A PIN only ever authorises a payment out.',
}
# Explainable score weights (score-1). The score summarises supported signals for
# display; the categorical decision table below never reads it.
WEIGHTS = {
    'credential_request': 30, 'collect_approval': 30, 'remote_access': 30, 'screen_sharing': 30,
    'qr_payment': 30, 'pin_to_receive': 30, 'intel_match': 25, 'threat': 20, 'intel_link': 15, 'destination_mismatch': 15, 'bank_avoidance': 15,
    'reported_destination_mismatch': 10, 'secrecy': 10, 'urgency': 10, 'repayment': 10, 'unexpected': 10,
    'same_destination': 0, 'reported_same_destination': 0,
}
FACTOR_LABELS = {
    'credential_request': 'Credential request', 'collect_approval': 'Collect-request approval', 'remote_access': 'Remote-access request',
    'screen_sharing': 'Screen-sharing request', 'intel_match': 'Reported in simulated intelligence', 'threat': 'Threats',
    'intel_link': 'Linked to reported incidents', 'destination_mismatch': 'Different repayment UPI ID', 'bank_avoidance': 'Told to avoid the bank',
    'reported_destination_mismatch': 'Different destination reported', 'secrecy': 'Asked for secrecy', 'urgency': 'Urgency',
    'repayment': 'Repayment request', 'unexpected': 'Unexpected payment', 'same_destination': 'Same UPI ID as sender (no reduction)',
    'reported_same_destination': 'Same destination reported (no reduction)',
    'qr_payment': 'QR code that pays out', 'pin_to_receive': 'UPI PIN asked to receive money',
}


def score(findings):
    """One factor per signal kind, whatever the number of sources; capped at 100."""
    factors = {}
    for finding in findings:
        kind = finding['kind']
        if kind not in WEIGHTS:
            continue
        factor = factors.setdefault(kind, {'id': kind, 'label': FACTOR_LABELS[kind], 'weight': WEIGHTS[kind],
                                           'status': 'fail' if WEIGHTS[kind] >= 15 else 'warn', 'sources': [], 'detail': finding['text']})
        if finding['source'] not in factor['sources']:
            factor['sources'].append(finding['source'])
    ordered = sorted(factors.values(), key=lambda f: (-f['weight'], f['id']))
    return min(100, sum(f['weight'] for f in ordered)), ordered


UNCERTAINTY = ('Byte Bot cannot confirm from the information provided whether the sender is a scammer. '
               'This assessment identifies signals that need verification; it is not a definitive finding of fraud.')


def assess(transaction, context, evidence, extraction, matches, links=()):
    findings, limitations = [], list(extraction['notices'])
    pressures, dangerous = set(), set()
    repayment = context['repayment_requested'] == 'yes'
    unexpected = context['expected_payment'] == 'no'
    suspicious = False
    def add(kind, text, source, reference, rule, quote=None):
        findings.append(dict(kind=kind, text=text, source=source, reference=reference, rule_id=rule, quote=quote))
    if transaction is not None:
        add('transaction_status', f"Transaction status: {transaction['status']}.", 'synthetic transaction record',
            str(transaction['id']), 'transaction-status')
    if unexpected:
        add('unexpected', 'You reported that this payment was unexpected.', 'user statement', 'context.expected_payment', 'unexpected-credit')
    if context['repayment_requested'] == 'yes':
        add('repayment', LABELS['repayment'], 'user statement', 'context.repayment_requested', 'repayment-request')
    for kind in context['pressure_tactics'] or []:
        pressures.add(PRESSURE[kind])
        suspicious = True
        add(kind, LABELS[kind], 'user statement', 'context.pressure_tactics', f'pressure-{PRESSURE[kind]}')
    for item in evidence:
        for kind in item.get('metadata', {}).get('request_markers', []):
            if kind in DANGEROUS:
                dangerous.add(kind)
                suspicious = True
                add(kind, LABELS[kind], 'local safety check on user-reviewed OCR text' if item['type'] == 'screenshot' else 'local safety check on user statement', str(item['id']), f'safety-{kind}')
        for intent in item.get('metadata', {}).get('qr_payments', []):
            dangerous.add('qr_payment')
            suspicious = True
            amount = rupees(intent['amount_paise']) if intent.get('amount_paise') else 'an amount you enter'
            pays_sender = bool(transaction) and normalize('vpa', intent['payee_vpa']) == normalize('vpa', transaction['sender_vpa'])
            add('qr_payment', f"This QR code starts a payment of {amount} from your account to {intent['payee_vpa']}"
                f"{' (the original sender)' if pays_sender else ''}. It needs your UPI PIN and cannot receive money.",
                'local QR decode of the user-submitted image', str(item['id']), 'qr-outgoing-payment')
    identifiers = []
    if context.get('requested_vpa') and VPA.fullmatch(context['requested_vpa'].strip()):
        identifiers.append((context['requested_vpa'], 'user statement', 'context.requested_vpa', None))
    for claim in extraction['claims']:
        kind = claim['kind']
        source = f"validated extraction from {claim['evidence_type']} (user-submitted)"
        ref = claim['evidence_id']
        if kind == 'repayment':
            repayment = True
        if kind in PRESSURE:
            pressures.add(PRESSURE[kind])
            suspicious = True
        if kind in DANGEROUS:
            dangerous.add(kind)
            suspicious = True
        if kind == 'vpa' and claim.get('requested_destination'):
            identifiers.append((claim['value'], source, ref, claim['quote']))
        if kind == 'amount':
            text = f"Amount mentioned in submitted evidence: ₹{claim['value'] // 100:,}.{claim['value'] % 100:02d}."
        elif kind == 'vpa':
            text = f"UPI ID mentioned in submitted evidence: {claim['value']}."
        else:
            text = LABELS.get(kind, f"{kind.upper()} observed: {claim['value']}")
        add(kind, text, source, ref, f'extracted-{kind}', claim['quote'])
    if context['repayment_requested'] == 'no' and repayment:
        limitations.append('Your saved answer and submitted evidence disagree about a repayment request; verify both.')
    if transaction:
        for identifier, source, ref, quote in sorted(set(identifiers), key=str):
            same = normalize('vpa', identifier) == normalize('vpa', transaction['sender_vpa'])
            if same:
                add('same_destination', 'The requested UPI ID matches the sender. This does not verify legitimacy or reduce concern.', source, ref, 'same-id-zero-reduction', quote)
            else:
                suspicious = True
                add('destination_mismatch', 'The requested UPI ID differs from the sender. Verify the destination; this alone does not prove fraud.', source, ref, 'destination-mismatch', quote)
    if context['requested_destination_type'] == 'different_vpa' and not identifiers:
        suspicious = True
        add('reported_destination_mismatch', 'You reported a different destination; the identifier has not been independently compared.', 'user statement', 'context.requested_destination_type', 'reported-destination-mismatch')
    if context['requested_destination_type'] == 'same_sender' and not identifiers:
        add('reported_same_destination', 'You reported the same destination. This does not establish legitimacy; no identifier comparison was possible.', 'user statement', 'context.requested_destination_type', 'same-id-zero-reduction')
    for match in matches:
        suspicious = True
        add('intel_match', f"Exact simulated match for {match['identifier']} linked to {match['incident_reference']}. A match is not proof of guilt.",
            match['source_label'], match['fixture_key'], 'simulated-intel-match')
    for link in links:
        suspicious = True
        hops = 'directly' if link['min_hops'] == 1 else 'through a shared contact or device'
        add('intel_link', f"{link['identifier']} is linked {hops} to {len(link['incidents'])} reported incident"
            f"{'' if len(link['incidents']) == 1 else 's'} ({', '.join(link['incidents'])}). A link is not proof of guilt.",
            link['source_label'], link['identifier'], 'simulated-graph-link')
    if not matches and not links:
        limitations.append('No match found in the available demo data. This is not a trust or safety guarantee.')
    if not transaction or transaction['status'] != 'successful':
        category, decision = 'Unable to assess', 'transaction-not-complete'
    elif dangerous & OUTGOING:
        category, decision = 'High concern', 'outgoing-payment-mechanism'
    elif dangerous or len(pressures) >= 2 or (matches and unexpected and repayment):
        category, decision = 'High concern', 'strong-signal-combination'
    elif (unexpected and repayment) or suspicious:
        category, decision = 'Needs verification', 'verification-needed'
    elif (context['expected_payment'] == 'yes' and context['knows_sender'] == 'yes'
          and context['repayment_requested'] == 'no' and context['pressure_tactics'] == []
          and (not evidence or extraction['status'] == 'complete')):
        category, decision = 'No strong indicators found', 'expected-with-sufficient-context'
    else:
        category, decision = 'Unable to assess', 'insufficient-information'
    add('decision', f'Applied rule: {decision}.', 'Python decision table', decision, decision)
    total, factors = score(findings)
    limitations.append(UNCERTAINTY)
    if category == 'Unable to assess':
        limitations.append('Check the actual transaction status and provide missing or corrected context; completed funds cannot be assumed.')
    if extraction['provider_mode'] == 'fixture':
        limitations.append('Synthetic extraction fixture mode; no live Gemini analysis was performed.')
    summary = {
        'High concern': 'Supported warning signs warrant immediate caution and bank verification.',
        'Needs verification': 'The request needs verification; the available information does not confirm fraud.',
        'No strong indicators found': 'No strong indicators were found in the information supplied. This does not establish that the sender or payment is safe.',
        'Unable to assess': 'A reliable assessment is unavailable from the current transaction status or information.',
    }[category]
    return Assessment(category=category, rule_version=RULE_VERSION,
        triggered_rules=sorted({f['rule_id'] for f in findings}), findings=findings,
        limitations=list(dict.fromkeys(limitations)), recommendations=[],
        summary=summary, generated_at=datetime.now(timezone.utc), intelligence_matches=matches,
        extraction_status=extraction['status'], provider_mode=extraction['provider_mode'],
        risk_score=total, score_version=SCORE_VERSION, risk_factors=factors, graph_links=list(links),
        headline=headline(transaction, category, decision, findings),
        story=story(transaction, findings, pressures, dangerous, category, decision)).model_dump(mode='json')


def rupees(paise):
    return f"₹{paise // 100:,}" if paise % 100 == 0 else f"₹{paise / 100:,.2f}"


def _network(findings):
    return any(f['kind'] in ('intel_match', 'intel_link') for f in findings)


def headline(transaction, category, decision, findings):
    """Presentation-only verdict banner; the category remains authoritative."""
    kinds = {f['kind'] for f in findings}
    genuine = bool(transaction) and transaction['status'] == 'successful'
    if decision == 'outgoing-payment-mechanism':
        return {'tone': 'danger', 'label': 'Dangerous payment action',
                'title': "This 'refund' would send money from your account",
                'message': 'Scanning a UPI QR, approving a collect request, or entering your UPI PIN starts a payment out of your account. '
                           'None of these is ever needed to receive money. Do not proceed.'}
    if genuine and _network(findings) and category in ('High concern', 'Needs verification'):
        same = ', even though the repayment UPI ID matches the sender' if kinds & {'same_destination', 'reported_same_destination'} else ''
        return {'tone': 'caution', 'label': 'Suspicious network',
                'title': 'The payment is genuine, but the network behind it is not',
                'message': f'The sender or repayment details are linked to reported fraud in the simulated intelligence graph{same}. '
                           'Do not return the funds yourself; let your bank handle the reversal. A link is not proof of guilt.'}
    if genuine and category == 'High concern':
        return {'tone': 'danger', 'label': 'High concern',
                'title': 'The payment is genuine, but the request shows strong warning signs',
                'message': 'Do not send money back yourself. Ask your bank or Paytm to reverse the original credit through official channels.'}
    if genuine and category == 'Needs verification':
        return {'tone': 'caution', 'label': 'Caution',
                'title': "The payment is genuine, but the repayment request can't be verified",
                'message': 'Do not make a separate payment until your bank or payment provider confirms the correct way to return the funds.'}
    if category == 'No strong indicators found':
        return {'tone': 'safe', 'label': 'No strong warning signs',
                'title': 'Nothing here suggests a repayment scam',
                'message': 'This is not a safety guarantee. If someone later asks for the money back, check with Byte Bot again.'}
    if decision == 'transaction-not-complete':
        return {'tone': 'info', 'label': 'Payment not complete',
                'title': 'This money has not arrived',
                'message': 'The payment is pending or failed. Do not send anything back for a payment that has not completed.'}
    return {'tone': 'info', 'label': 'Need more detail', 'title': 'Byte Bot needs a little more information',
            'message': 'Answer the follow-up questions so Byte Bot can decide the safest next step.'}


TACTICS = {'urgency': 'urgency', 'threat': 'threats', 'bank_avoidance': 'told to avoid the bank', 'secrecy': 'asked for secrecy'}


def story(transaction, findings, pressures, dangerous, category, decision):
    """The six questions behind a suspicious payment, answered from the findings."""
    kinds = {f['kind'] for f in findings}
    steps = []

    def step(key, question, status, answer):
        steps.append({'id': key, 'question': question, 'status': status, 'answer': answer})
    if not transaction:
        step('arrived', 'Did the money actually arrive?', 'fail', 'No matching payment was found in your Paytm history.')
    elif transaction['status'] == 'successful':
        amount = f"{rupees(transaction['amount_paise'])} " if transaction.get('amount_paise') else 'The payment '
        sender = transaction.get('sender_name') or 'the sender'
        step('arrived', 'Did the money actually arrive?', 'pass',
             f"Yes. {amount}from {sender} ({transaction.get('sender_vpa', 'unknown UPI ID')}) is in your Paytm history.")
    else:
        step('arrived', 'Did the money actually arrive?', 'warn' if transaction['status'] == 'pending' else 'fail',
             f"Not yet. This payment is {transaction['status']}, so the money may never arrive.")
    asks = []
    if 'qr_payment' in kinds:
        asks.append('scan a QR code')
    if 'collect_approval' in kinds:
        asks.append('approve a collect request')
    if kinds & {'pin_to_receive', 'credential_request'}:
        asks.append('enter or share your UPI PIN or OTP')
    if kinds & {'remote_access', 'screen_sharing'}:
        asks.append('give someone control of your screen')
    if 'repayment' in kinds and not asks:
        where = (' to a different UPI ID' if kinds & {'destination_mismatch', 'reported_destination_mismatch'}
                 else ' to the same UPI ID' if kinds & {'same_destination', 'reported_same_destination'} else '')
        asks.append(f'send the money back{where}')
    if asks:
        step('asked', 'What exactly are you being asked to do?', 'fail' if dangerous else 'warn', 'To ' + ', '.join(asks) + '.')
    else:
        step('asked', 'What exactly are you being asked to do?', 'pass', 'Nothing has been asked of you.')
    if dangerous & OUTGOING:
        step('sends_out', 'Would that send money from your account?', 'fail',
             'Yes. It starts a payment out of your account. Receiving money never needs a QR scan, a collect approval, or your PIN.')
    elif 'repayment' in kinds:
        step('sends_out', 'Would that send money from your account?', 'warn',
             'Yes. A repayment is a new, separate payment that may not be reversible.')
    else:
        step('sends_out', 'Would that send money from your account?', 'pass', 'No outgoing payment has been requested.')
    tactics = [TACTICS[k] for k in TACTICS if k in kinds]
    if kinds & {'remote_access', 'screen_sharing'}:
        tactics.append('remote access or screen sharing')
    if tactics:
        step('pressure', 'Is there evidence of social engineering?', 'fail' if len(pressures) >= 2 or 'threat' in kinds else 'warn',
             'Yes: ' + ', '.join(tactics) + '.')
    else:
        step('pressure', 'Is there evidence of social engineering?', 'pass', 'No pressure tactics were found in what you shared.')
    intel = [f for f in findings if f['kind'] in ('intel_match', 'intel_link')]
    if intel:
        step('intel', 'Is there relevant fraud intelligence?', 'fail', intel[0]['text'])
    else:
        step('intel', 'Is there relevant fraud intelligence?', 'pass', 'No match in the available demo intelligence. This is not a safety guarantee.')
    genuine = bool(transaction) and transaction['status'] == 'successful'
    if decision == 'outgoing-payment-mechanism':
        safest = "Don't scan, approve, or enter your PIN. Block the UPI ID and let your bank handle the original credit."
    elif genuine and intel and category != 'No strong indicators found':
        safest = "Don't return the money yourself. Let your bank reverse the original credit."
    elif category in ('High concern', 'Needs verification'):
        safest = "Don't make a separate payment. Ask your bank or Paytm to reverse the original credit."
    elif category == 'No strong indicators found':
        safest = 'No action is needed. Check again if anyone asks for the money back.'
    elif decision == 'transaction-not-complete':
        safest = "Wait for the payment to complete, and don't send anything in the meantime."
    else:
        safest = 'Answer a few questions so Byte Bot can decide.'
    step('safest', "What's the safest next action?", 'pass', safest)
    return steps
