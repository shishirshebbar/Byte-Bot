"""Deterministic follow-up questions and action playbook.

The supervisor chooses steps only from ACTIONS. A language model may later phrase
or explain a step, but it can never add a tool or change a step's arguments.
"""

YES_NO = [('yes', 'Yes'), ('no', 'No'), ('unknown', "I'm not sure")]
QUESTIONS = {
    'expected_payment': {'prompt': 'Were you expecting this payment?', 'options': YES_NO, 'multi': False},
    'already_sent_money': {'prompt': 'Have you already sent any money back or to someone else?', 'options': YES_NO, 'multi': False},
    'repayment_requested': {'prompt': 'Has anyone asked you to send this money back?', 'options': YES_NO, 'multi': False},
    'pressure_tactics': {'prompt': 'Did the person do any of these? Choose all that apply, or none.', 'multi': True,
                         'options': [('urgency', 'Rushed me'), ('threat', 'Threatened me'),
                                     ('bank_avoidance', 'Told me not to contact my bank'), ('secrecy', 'Asked me to keep it secret')]},
    'requested_destination_type': {'prompt': 'Where were you asked to send the money?', 'multi': False,
                                   'options': [('same_sender', 'Back to the same UPI ID'), ('different_vpa', 'To a different UPI ID'),
                                               ('bank_account', 'To a bank account'), ('payment_request', 'Approve a payment or collect request'),
                                               ('not_specified', 'They did not say')]},
    'knows_sender': {'prompt': 'Do you know the sender personally?', 'options': YES_NO, 'multi': False},
}
MAX_QUESTIONS = 3

ACTIONS = {
    'hold_credit': {'system': 'paytm_upi_sandbox', 'label': 'Place a dispute hold on the unexpected credit', 'reversible': True},
    'block_vpa': {'system': 'paytm_upi_sandbox', 'label': 'Block the requesting UPI ID for this customer', 'reversible': True},
    'decline_collect': {'system': 'paytm_upi_sandbox', 'label': 'Decline the pending collect request', 'reversible': True},
    'raise_bank_dispute': {'system': 'bank_dispute_desk', 'label': 'Open a dispute ticket with the bank', 'reversible': False},
    'draft_cybercrime_complaint': {'system': 'cybercrime_1930_draft', 'label': 'Prepare a 1930 cybercrime complaint draft for the customer to submit', 'reversible': True},
    'notify_customer': {'system': 'notification_service', 'label': 'Send the customer a safety summary', 'reversible': False},
}


def decision(assessment):
    return next((f['reference'] for f in assessment['findings'] if f['kind'] == 'decision'), None)


def follow_ups(context, assessment, extraction):
    """Ask only for missing answers that can change the decision or escalation."""
    claimed = {claim['kind'] for claim in extraction['claims']}
    destination = any(f['kind'] in ('same_destination', 'destination_mismatch') for f in assessment['findings'])
    repayment = context['repayment_requested'] == 'yes' or 'repayment' in claimed
    missing = []
    if context['expected_payment'] == 'unknown':
        missing.append('expected_payment')
    if context['already_sent_money'] == 'unknown':
        missing.append('already_sent_money')
    if context['repayment_requested'] == 'unknown' and 'repayment' not in claimed:
        missing.append('repayment_requested')
    if context['pressure_tactics'] is None:
        missing.append('pressure_tactics')
    if repayment and context['requested_destination_type'] == 'unknown' and not destination:
        missing.append('requested_destination_type')
    if context['expected_payment'] != 'no' and context['knows_sender'] == 'unknown':
        missing.append('knows_sender')
    blocking = decision(assessment) == 'insufficient-information'
    return missing[:MAX_QUESTIONS], blocking


def plan(transaction, context, assessment):
    """Choose protective steps for the rule category; never more than the playbook."""
    category = assessment['category']
    kinds = {f['kind'] for f in assessment['findings']}
    received = bool(transaction) and transaction['status'] == 'successful'
    steps = []
    def add(action, reason):
        if action not in (step['action_type'] for step in steps):
            steps.append({'action_type': action, 'reason': reason})
    if category in ('High concern', 'Needs verification'):
        if received and context['expected_payment'] == 'no':
            add('hold_credit', 'Keep the unexpected funds untouched while the original credit is verified.')
        if kinds & {'same_destination', 'destination_mismatch'}:
            add('block_vpa', 'Prevent an accidental transfer to the UPI ID that requested repayment.')
    if 'collect_approval' in kinds:
        add('decline_collect', 'A collect request is never needed to receive money.')
    if kinds & {'qr_payment', 'pin_to_receive'}:
        add('block_vpa', 'Block the UPI ID that the QR code or PIN prompt would pay.')
    if received and kinds & {'intel_match', 'intel_link'} and category in ('High concern', 'Needs verification'):
        add('raise_bank_dispute', 'The sender is linked to reported fraud; let the bank handle the reversal instead of repaying.')
    if category == 'High concern':
        add('raise_bank_dispute', 'Strong warning signs need the bank to verify how the original credit should be handled.')
    if context['already_sent_money'] == 'yes':
        add('raise_bank_dispute', 'The customer reported sending money; the bank must be informed quickly.')
        add('draft_cybercrime_complaint', 'A reported loss should be filed with the 1930 cybercrime helpline by the customer.')
    if steps:
        add('notify_customer', 'Confirm in writing what was done and what the customer should do next.')
    return steps
