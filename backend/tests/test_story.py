"""The four-case "verify the story" checks: claimed credits, outgoing mechanisms, and suspicious networks."""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from bytebot.main import create_app
from bytebot.fixtures import SCENARIOS, FixtureProvider
from bytebot import qr
from bytebot.safety import request_markers
from test_analysis import run_case
from test_agent import load, path, API

QR_PNG = Path(__file__).resolve().parents[1] / 'bytebot' / 'demo_assets' / 'refund-qr.png'
RAHUL = 'Hi, I sent you ₹5,000 by mistake. Please return it immediately.'


@pytest.fixture
def client(prepared):
    with TestClient(create_app(prepared, extraction_provider=FixtureProvider(), worker_enabled=False)) as client:
        client.get(API + '/transactions')
        yield client


def check(client, **body):
    response = client.post(API + '/claim-check', json=body)
    assert response.status_code == 200, response.text
    return response.json()


def steps(result):
    return {s['id']: s for s in result['story']}


# Case 1: a claimed payment that never arrived.
def test_claimed_payment_not_in_history_is_a_scam_warning(client):
    result = check(client, text=RAHUL, sender='Rahul')
    assert result['status'] == 'not_found' and result['claimed_amount_paise'] == 500000
    assert result['headline']['label'] == 'Scam warning' and 'Do not send money back' in result['headline']['message']
    assert steps(result)['arrived']['status'] == 'fail' and steps(result)['sends_out']['status'] == 'fail'
    assert result['claims_payment'] and result['stored'] is False


def test_claim_is_verified_once_the_credit_really_arrives(client):
    load(client, 'M')  # Copies Rahul Mehta's genuine ₹5,000 credit.
    result = check(client, text=RAHUL, sender='Rahul')
    assert result['status'] == 'verified' and result['matches'][0]['sender_vpa'] == 'rahul.mehta.demo@upi'
    assert steps(result)['arrived']['status'] == 'pass'


def test_claim_without_sender_lists_candidates_and_pending_is_not_owed(client):
    assert check(client, text='I sent you Rs 5000')['status'] == 'ambiguous'
    pending = check(client, amount_paise=125000, sender='Meera')
    assert pending['status'] == 'not_completed' and pending['headline']['label'] == 'Payment not complete'
    assert check(client, text='please send it back')['status'] == 'need_amount'


def test_claim_check_needs_a_session_and_redacts_nothing_into_storage(client, prepared):
    fresh = TestClient(create_app(prepared, extraction_provider=FixtureProvider(), worker_enabled=False))
    with fresh:
        assert fresh.post(API + '/claim-check', json={'text': RAHUL}).status_code == 404
    result = check(client, text='I sent INR 5000. Share your OTP 482913 to get it back.', sender='Rahul')
    assert '482913' not in str(result)
    assert steps(result)['asked']['status'] == 'warn'


# Case 3: the "refund" mechanism is really an outgoing payment.
def test_upi_qr_is_decoded_and_parsed_as_an_outgoing_payment():
    with Image.open(QR_PNG) as image:
        intents = qr.payment_intents(image.convert('RGB'))
    assert intents == [{'payee_vpa': 'rahul.mehta.demo@upi', 'payee_name': 'Rahul Mehta', 'amount_paise': 500000,
                        'mandate': False, 'initiates_payment': True}]
    assert qr.parse_upi('https://example.com/?pa=a@upi') is None
    assert qr.parse_upi('upi://pay?pa=not-a-vpa&am=10') is None


@pytest.mark.parametrize('text, kind', [
    ('Please scan this QR code to return the money.', 'qr_payment'),
    ('Ye QR scan karke paise wapas karo', 'qr_payment'),
    ('To receive the refund, enter your UPI PIN.', 'pin_to_receive'),
])
def test_outgoing_mechanism_markers(text, kind):
    assert kind in request_markers(text)


def test_outgoing_markers_respect_negation():
    assert request_markers('Never scan a QR to receive money.') == []


def test_qr_refund_scenario_is_a_dangerous_payment_action(client):
    result = run_case(client, load(client, 'N'))['result']
    assert result['category'] == 'High concern'
    assert 'outgoing-payment-mechanism' in result['triggered_rules'] and result['extraction_status'] == 'complete'
    qr_finding = next(f for f in result['findings'] if f['kind'] == 'qr_payment' and f['rule_id'] == 'qr-outgoing-payment')
    assert 'payment of ₹5,000 from your account to rahul.mehta.demo@upi (the original sender)' in qr_finding['text']
    assert result['headline']['label'] == 'Dangerous payment action'
    assert steps(result)['sends_out']['status'] == 'fail'
    assert result['recommendations'][0].startswith('Do not scan the QR code')


def test_collect_request_is_also_an_outgoing_mechanism(client):
    result = run_case(client, load(client, 'E'))['result']
    assert result['headline']['label'] == 'Dangerous payment action'


# Case 2 and Case 4: a genuine credit.
def test_genuine_credit_with_unverified_request_is_caution(client):
    result = run_case(client, load(client, 'M'))['result']
    assert result['category'] == 'Needs verification' and result['headline']['label'] == 'Caution'
    assert "repayment request can't be verified" in result['headline']['title']
    assert steps(result)['arrived']['status'] == 'pass' and 'Rahul Mehta' in steps(result)['arrived']['answer']


def test_same_id_sender_in_a_suspicious_network(client):
    case = load(client, 'O')
    result = run_case(client, case)['result']
    factors = {f['id']: f for f in result['risk_factors']}
    assert factors['same_destination']['weight'] == 0  # A same-ID request never reduces concern.
    assert result['graph_links'][0]['identifier'] == 'rahul.demo@upi' and len(result['graph_links'][0]['incidents']) == 3
    assert result['headline']['label'] == 'Suspicious network' and 'even though the repayment UPI ID matches' in result['headline']['message']
    assert result['category'] == SCENARIOS['O']['category']
    graph = client.get(path(case) + '/intel-graph').json()
    assert {'payback.demo@upi', 'return.help@upi'} <= {n['identifier'] for n in graph['nodes']}
    assert 'let your bank handle the reversal' in result['recommendations'][0].lower()


def test_every_assessment_answers_the_six_questions(client):
    for key in ('A', 'D', 'J', 'M', 'N', 'O'):
        result = run_case(client, load(client, key))['result']
        assert [s['id'] for s in result['story']] == ['arrived', 'asked', 'sends_out', 'pressure', 'intel', 'safest']
        assert result['headline']['label']
