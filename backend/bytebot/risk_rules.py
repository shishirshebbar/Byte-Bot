"""Versioned categorical decision table, independent of the provider."""
from datetime import datetime, timezone
from .analysis_schemas import Assessment, RULE_VERSION, SCORE_VERSION
from .intelligence import normalize
from .extraction import VPA

PRESSURE = {'urgency': 'urgency', 'threat': 'threat', 'bank_avoidance': 'isolation', 'secrecy': 'isolation'}
DANGEROUS = {'credential_request', 'collect_approval', 'remote_access', 'screen_sharing'}
LABELS = {
    'urgency': 'Urgency was reported or observed.', 'threat': 'Threats were reported or observed.',
    'bank_avoidance': 'A request to avoid contacting the bank was reported or observed.',
    'secrecy': 'A request for secrecy was reported or observed.',
    'repayment': 'A repayment request was reported or observed.',
    'credential_request': 'A request to disclose a credential was detected; never share a PIN or OTP.',
    'collect_approval': 'A request to approve a collect/payment request was detected.',
    'remote_access': 'A request to enable remote access was detected.',
    'screen_sharing': 'A request to share the screen was detected.',
}
# Explainable score weights (score-1). The score summarises supported signals for
# display; the categorical decision table below never reads it.
WEIGHTS = {
    'credential_request': 30, 'collect_approval': 30, 'remote_access': 30, 'screen_sharing': 30,
    'intel_match': 25, 'threat': 20, 'intel_link': 15, 'destination_mismatch': 15, 'bank_avoidance': 15,
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
        risk_score=total, score_version=SCORE_VERSION, risk_factors=factors, graph_links=list(links)).model_dump(mode='json')
