"""Versioned action policy and escalation rules. Python decides; models never do."""
import re

POLICY_VERSION = 'agent-policy-1'
HIGH_VALUE_PAISE = 5_000_000  # ₹50,000
ACCOUNT_ACTIONS = {'hold_credit', 'block_vpa', 'decline_collect', 'raise_bank_dispute', 'draft_cybercrime_complaint'}
STATES = {'auto': 'approved', 'needs_customer_consent': 'awaiting_consent',
          'needs_human_approval': 'awaiting_human', 'deny': 'denied'}
PRIORITY_ORDER = ('normal', 'high', 'urgent')
SLA_MINUTES = {'urgent': 15, 'high': 60, 'normal': 240}
REASONS = {
    'customer_reported_loss': ('urgent', 'The customer reported already sending money.'),
    'possible_prompt_injection': ('high', 'Submitted evidence contains instructions aimed at the assistant.'),
    'high_value': ('high', 'The credit is ₹50,000 or more.'),
    'customer_requested': ('high', 'The customer asked to speak with a person.'),
    'conflicting_evidence': ('normal', 'The saved answers and the submitted evidence disagree.'),
    'extraction_unavailable': ('normal', 'The submitted evidence could not be read automatically.'),
    'insufficient_information': ('normal', 'No reliable assessment is possible and no further questions would help.'),
    'repeated_unable_to_assess': ('normal', 'Follow-up questions were asked twice without a reliable assessment.'),
}
# Instruction-like text inside evidence is data. Its presence is a reason for a
# person to review the case; it never changes the rule category.
INJECTION = re.compile(
    r'\b(?:ignore|disregard|forget|override)\b[^.!?\n]{0,40}\b(?:previous|prior|above|earlier|all|your|system)\b[^.!?\n]{0,20}\b(?:instructions?|rules?|prompts?|guidelines?)\b'
    r'|(?:^|[\s.!?])(?:system|assistant|developer)\s*:'
    r'|\bmark (?:this|the) (?:case|payment|message|transaction) (?:as )?(?:safe|legitimate|genuine|resolved)\b'
    r'|\byou are now\b|\bnew instructions?\s*:|\bpretend (?:you are|to be)\b|\bdisregard (?:the|everything) above\b'
    r'|\b(?:pichle|purane|saare|upar ke) (?:instructions?|nirdesh|rules?) (?:ignore|bhool) (?:karo|kar do|jao)\b'
    r'|\b(?:is|yeh|ye) (?:case|payment|message) ko (?:safe|theek|resolved|genuine) (?:mark|bata) (?:karo|kar do|do)\b', re.I)


def escalation_reasons(transaction, context, evidence, assessment, extraction, *, blocking, questions, follow_up_rounds):
    reasons = []
    if context['already_sent_money'] == 'yes':
        reasons.append('customer_reported_loss')
    if any(INJECTION.search(item.get('confirmed_text') or '') for item in evidence):
        reasons.append('possible_prompt_injection')
    if (transaction and transaction['amount_paise'] >= HIGH_VALUE_PAISE
            and assessment['category'] in ('High concern', 'Needs verification')):
        reasons.append('high_value')
    if context['repayment_requested'] == 'no' and any(c['kind'] == 'repayment' for c in extraction['claims']):
        reasons.append('conflicting_evidence')
    # Unread evidence matters only when the rules could not already act on a
    # warning: it could hide risk behind an apparently calm result.
    if (evidence and extraction['status'] == 'unavailable'
            and assessment['category'] in ('Unable to assess', 'No strong indicators found')):
        reasons.append('extraction_unavailable')
    if blocking:
        if follow_up_rounds >= 2:
            reasons.append('repeated_unable_to_assess')
        elif not questions:
            reasons.append('insufficient_information')
    return reasons


def priority(reasons):
    return max((REASONS[code][0] for code in reasons), key=PRIORITY_ORDER.index, default='normal')


def verdict(action_type, transaction, *, escalating):
    """Return (verdict, reason) for one playbook step."""
    if action_type in ('hold_credit',) and (not transaction or transaction['status'] != 'successful'):
        return 'deny', 'Funds that have not been received cannot be held.'
    if action_type == 'notify_customer':
        return 'auto', 'Informational message sent only to the customer.'
    if escalating and action_type in ACCOUNT_ACTIONS:
        return 'needs_human_approval', 'The case is escalated, so a person approves account actions.'
    if action_type == 'hold_credit' and transaction['amount_paise'] >= HIGH_VALUE_PAISE:
        return 'needs_human_approval', 'Holds on credits of ₹50,000 or more need a person.'
    return 'needs_customer_consent', "Byte Bot acts on the customer's account only with their consent."


def outcome(*, escalated, blocking, actions):
    states = {action['state'] for action in actions}
    if escalated:
        return 'escalated'
    if blocking:
        return 'needs_customer_info'
    if 'awaiting_consent' in states:
        return 'awaiting_consent'
    if 'approved' in states:
        return 'actions_ready'
    if 'executed' in states:
        return 'actions_completed'
    return 'resolved'
