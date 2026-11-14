"""Local simulated systems. Every record is labelled simulated; nothing leaves the server.

Each system receives only the action type and the case; any identifier it needs is
re-derived from the database, never from model output.
"""
import secrets
from uuid import uuid4

LABELS = {
    'paytm_upi_sandbox': 'Paytm UPI sandbox (simulated)',
    'bank_dispute_desk': 'Bank dispute desk (simulated)',
    'cybercrime_1930_draft': '1930 cybercrime complaint draft (simulated, never submitted)',
    'notification_service': 'Notification service (simulated)',
}
PREFIX = {'hold_credit': 'HOLD', 'block_vpa': 'BLOCK', 'decline_collect': 'DECLINE',
          'raise_bank_dispute': 'BANK', 'draft_cybercrime_complaint': '1930', 'notify_customer': 'NOTE'}
DETAIL = {
    'hold_credit': 'Dispute hold placed on the unexpected credit. The funds cannot be spent or forwarded until the hold is released.',
    'block_vpa': 'The requesting UPI ID is blocked for this customer. Payments and collect requests to it are refused.',
    'decline_collect': 'The pending collect request was declined. No money left the account.',
    'raise_bank_dispute': 'Dispute ticket opened with the bank. Expected first response within 48 hours.',
    'draft_cybercrime_complaint': 'A complaint draft was prepared for the customer to review and submit at 1930 or cybercrime.gov.in. Byte Bot does not submit it.',
    'notify_customer': 'In-app safety summary sent to the customer.',
}


class SystemUnavailable(Exception):
    pass


class SimulatedSystems:
    """Writes durable mock records so that results can be read back and reversed."""

    def execute(self, conn, case, action):
        reference = f"SIM-{PREFIX[action['action_type']]}-{secrets.token_hex(4).upper()}"
        conn.execute('INSERT INTO simulated_records (id,investigation_id,action_id,system,action_type,reference,status,detail) '
                     "VALUES (%s,%s,%s,%s,%s,%s,'active',%s)",
                     (uuid4(), case['id'], action['id'], action['system'], action['action_type'], reference,
                      DETAIL[action['action_type']]))
        return reference

    def verify(self, conn, action_id):
        row = conn.execute("SELECT reference FROM simulated_records WHERE action_id=%s AND status='active'", (action_id,)).fetchone()
        return row['reference'] if row else None

    def reverse(self, conn, action_id):
        conn.execute("UPDATE simulated_records SET status='reversed',updated_at=now() WHERE action_id=%s", (action_id,))
