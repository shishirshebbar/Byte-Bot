import psycopg
from .intelligence import seed_intelligence, seed_graph

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
# Agent scenarios are copied only when a presenter loads them, so the default
# history keeps its eight transactions.
SCENARIO_SENDERS = {'M': ('Rahul Mehta', 'rahul.mehta.demo@upi'), 'N': ('Rahul Mehta', 'rahul.mehta.demo@upi'),
                    'O': ('Rahul Kumar', 'rahul.demo@upi')}
ON_DEMAND_TEMPLATES = [
    (f'scenario-{key.lower()}', 'incoming', amount, 'INR', *SCENARIO_SENDERS.get(key, (f'Scenario {key} sender', 'aarav.demo@upi')),
     'recipient.demo@upi', f'2026-11-09T09:0{index}:00+05:30',
     'successful', f'DEMOSCENARIO{key}', 'mock')
    for index, (key, amount) in enumerate([('F', 500000), ('G', 500000), ('H', 500000), ('I', 500000), ('J', 500000),
                                           ('K', 7500000), ('L', 500000), ('M', 500000), ('N', 500000), ('O', 500000)])
]
DEFAULT_KEYS = [row[0] for row in TEMPLATES]


def seed(url, *, include_intelligence=True):
    with psycopg.connect(url) as conn:
        for row in TEMPLATES + ON_DEMAND_TEMPLATES:
            conn.execute(f"INSERT INTO transaction_templates (template_key, {FIELDS}) VALUES ({', '.join(['%s'] * 11)}) ON CONFLICT (template_key) DO NOTHING", row)

        if include_intelligence:
            seed_intelligence(conn)
            seed_graph(conn)
