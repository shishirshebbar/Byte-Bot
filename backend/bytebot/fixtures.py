"""Synthetic exact-input fixtures; never a general-purpose extraction fallback."""
from .extraction import ProviderUnavailable

SCENARIOS = {
    'A': {'text': 'Please return INR 5000 immediately to another.demo@upi.',
          'context': {'expected_payment': 'no', 'knows_sender': 'no', 'repayment_requested': 'yes', 'pressure_tactics': ['urgency'], 'requested_vpa': 'another.demo@upi'},
          'kinds': ['repayment', 'urgency', 'vpa', 'amount'], 'category': 'Needs verification'},
    'B': {'text': 'Please return INR 5000 to aarav.demo@upi. I will call the police. Do not contact your bank.',
          'context': {'expected_payment': 'no', 'knows_sender': 'no', 'repayment_requested': 'yes', 'pressure_tactics': ['threat', 'bank_avoidance'], 'requested_vpa': 'aarav.demo@upi'},
          'kinds': ['repayment', 'vpa', 'amount', 'threat', 'bank_avoidance'], 'category': 'High concern'},
    'C': {'text': 'Please return INR 5000 to aarav.demo@upi when convenient.',
          'context': {'expected_payment': 'no', 'knows_sender': 'no', 'repayment_requested': 'yes', 'pressure_tactics': [], 'requested_vpa': 'aarav.demo@upi'},
          'kinds': ['repayment', 'vpa', 'amount'], 'category': 'Needs verification'},
    'D': {'text': None,
          'context': {'expected_payment': 'yes', 'knows_sender': 'yes', 'repayment_requested': 'no', 'pressure_tactics': []},
          'kinds': [], 'category': 'No strong indicators found'},
    'E': {'text': 'Approve the collect request to receive the money.',
          'context': {'expected_payment': 'no', 'repayment_requested': 'unknown', 'pressure_tactics': []},
          'kinds': ['collect_approval'], 'category': 'High concern'},
}

SCENARIO_LABELS = {
    'A': ('Different-ID repayment pressure', 'An unexpected credit followed by an urgent request to repay another UPI ID.'),
    'B': ('Same-ID repayment pressure', 'A same-ID request includes a police threat and a request to avoid the bank.'),
    'C': ('Polite repayment request', 'A polite same-ID request with no pressure or matching demo intelligence.'),
    'D': ('Expected payment', 'An expected credit from a known contact without a repayment request.'),
    'E': ('Unexpected collect approval', 'A request to approve a collect request in order to receive money.'),
}


def scenario_answers(scenario):
    """Complete demo answers; original minimal rule fixtures remain unchanged."""
    from .investigation_schemas import Context
    fixture = SCENARIOS[scenario]
    destination = {'A': 'different_vpa', 'B': 'same_sender', 'C': 'same_sender',
                   'D': 'not_specified', 'E': 'payment_request'}[scenario]
    channels = {'A': ['whatsapp'], 'B': ['call', 'whatsapp'], 'C': ['sms'],
                'D': [], 'E': ['paytm_request']}[scenario]
    return Context.model_validate({'knows_sender': 'no', 'already_sent_money': 'no',
        'contact_channels': channels, 'requested_destination_type': destination,
        **fixture['context']}).model_dump()


class FixtureProvider:
    mode = 'fixture'

    async def extract(self, texts):
        import re
        from .extraction import PATTERNS
        from .safety import PATTERNS as SAFETY
        claims = []
        for item in texts:
            text = item['text']
            # Match only predefined synthetic inputs, with identifier placeholders.
            selected = None
            for fixture in SCENARIOS.values():
                original = fixture['text']
                if original and re.sub(r'[\w.+-]+@\w+', '[VPA]', original) == re.sub(r'\[VPA_\d+\]', '[VPA]', text):
                    selected = fixture
                    break
            if selected is None:
                raise ProviderUnavailable('unknown_fixture')
            for kind in selected['kinds']:
                if kind == 'vpa':
                    quote = re.search(r'\[VPA_\d+\]', text).group()
                    value = quote
                elif kind == 'amount':
                    quote, value = 'INR 5000', '5000'
                else:
                    pattern = (SAFETY if kind in SAFETY else PATTERNS)[kind]
                    quote, value = pattern.search(text).group(), None
                claims.append({'evidence_ref': item['evidence_ref'], 'kind': kind, 'quote': quote, 'value': value})
        return {'claims': claims}
