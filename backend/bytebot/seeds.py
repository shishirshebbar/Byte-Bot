import psycopg
from .intelligence import seed_intelligence

FIELDS = "direction, amount_paise, currency, sender_name, sender_vpa, receiver_vpa, occurred_at, status, reference, source"
TEMPLATES = [
    ("credit-success", "incoming", 500000, "INR", "Aarav Sharma", "aarav.demo@upi", "recipient.demo@upi", "2026-11-13T09:30:00+05:30", "successful", "DEMO261113001", "mock"),
    ("credit-pending", "incoming", 125000, "INR", "Meera Rao", "meera.demo@upi", "recipient.demo@upi", "2026-11-12T16:15:00+05:30", "pending", "DEMO261112002", "mock"),
    ("credit-failed", "incoming", 75000, "INR", "Kabir Shah", "kabir.demo@upi", "recipient.demo@upi", "2026-11-11T11:45:00+05:30", "failed", "DEMO261111003", "mock"),
]
# Separate transactions let all five scenarios coexist. Keep the original three
# first in history, and preserve every pre-existing session during ordinary seeds.
TEMPLATES += [
    (f'scenario-{key.lower()}', 'incoming', 500000, 'INR', f'Scenario {key} sender',
     'aarav.demo@upi', 'recipient.demo@upi', f'2026-11-10T09:0{index}:00+05:30',
     'successful', f'DEMOSCENARIO{key}', 'mock')
    for index, key in enumerate('ABCDE')
]


def seed(url, *, include_intelligence=True):
    with psycopg.connect(url) as conn:
        for row in TEMPLATES:
            conn.execute(f"INSERT INTO transaction_templates (template_key, {FIELDS}) VALUES ({', '.join(['%s'] * 11)}) ON CONFLICT (template_key) DO NOTHING", row)

        if include_intelligence:
            seed_intelligence(conn)
