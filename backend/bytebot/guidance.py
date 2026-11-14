"""Incident Resolution builds guidance from validated local facts, without an LLM."""
from datetime import datetime, timezone
from .analysis_schemas import Assessment


def resolve(assessment, transaction, context):
    recommendations = [
        'Do not make a separate repayment solely because someone is pressuring you.',
        'Contact your bank using its official contact details and ask how the original credit should be verified and handled.',
        'Never share your UPI PIN or OTP, enable remote access, or approve an unexpected collect request.',
    ]
    if transaction and transaction['status'] == 'successful' and context['expected_payment'] == 'no':
        recommendations.insert(1, 'Do not spend the unexpected funds while the situation is being checked.')
    kinds = {f['kind'] for f in assessment['findings']}
    if kinds & {'qr_payment', 'pin_to_receive', 'collect_approval'}:
        recommendations.insert(0, 'Do not scan the QR code, approve the request, or enter your UPI PIN. Each of these sends money out of your account; none is needed to receive money.')
    elif (transaction and transaction['status'] == 'successful' and kinds & {'intel_link', 'intel_match'}
          and assessment['category'] != 'No strong indicators found'):
        recommendations.insert(0, 'Do not return the funds yourself, even to the same UPI ID. Let your bank handle the reversal of the original credit.')
    if context['already_sent_money'] == 'yes':
        recommendations.insert(0, 'You reported sending money: preserve evidence, contact your bank immediately, and follow official cybercrime reporting channels. Recovery cannot be promised.')
    return Assessment.model_validate({**assessment, 'recommendations': recommendations,
        'generated_at': datetime.now(timezone.utc)}).model_dump(mode='json')
