"""Feedback storage and demo-wide outcome metrics (counts only)."""
import json
import pytest
from fastapi.testclient import TestClient
from bytebot.main import create_app
from bytebot.fixtures import FixtureProvider
from test_analysis import run_case
from test_agent import load, path, API


@pytest.fixture
def client(prepared):
    with TestClient(create_app(prepared, extraction_provider=FixtureProvider(), worker_enabled=False)) as client:
        client.get(API + '/transactions')
        yield client


def test_feedback_is_owner_scoped_and_one_per_run(client, prepared):
    case = load(client, 'B')
    assert client.post(path(case) + '/feedback', json={'helpful': True}).status_code == 409
    run_case(client, case)
    assert client.post(path(case) + '/feedback', json={'helpful': True}).status_code == 204
    assert client.post(path(case) + '/feedback', json={'helpful': False}).status_code == 204
    assert client.post(path(case) + '/feedback', json={'helpful': 'yes'}).status_code == 422
    with TestClient(create_app(prepared, extraction_provider=FixtureProvider(), worker_enabled=False)) as other:
        other.get(API + '/transactions')
        assert other.post(path(case) + '/feedback', json={'helpful': True}).status_code == 404
    assert client.get(API + '/metrics').json()['feedback'] == {'helpful': 0, 'not_helpful': 1}


def test_metrics_count_outcomes_without_personal_data(client):
    calm = load(client, 'D')
    run_case(client, calm)
    risky = load(client, 'B')
    agent = run_case(client, risky)['agent']
    hold = next(a for a in agent['actions'] if a['action_type'] == 'hold_credit')
    client.post(path(risky) + f"/actions/{hold['id']}/consent", json={'decision': 'approve', 'expected_revision': risky['input_revision']})
    run_case(client, load(client, 'F'))
    metrics = client.get(API + '/metrics').json()
    assert metrics['cases_analyzed'] == 3 and metrics['escalated'] == 1 and metrics['handled_without_person'] == 2
    assert metrics['autonomy_rate'] == round(2 / 3, 3)
    assert metrics['actions_completed'] == {'agent': 2, 'customer': 1}  # Two automatic notifications, one consented hold.
    assert metrics['policy_violations'] == 0 and metrics['simulated_amount_held_paise'] == 500000
    assert metrics['estimated_review_minutes_saved'] == 16 and 'assumption' in metrics['estimate_basis']
    text = json.dumps(metrics)
    for private in ('aarav.demo@upi', 'refund.demo@upi', 'recipient.demo@upi', risky['id'], 'Please return'):
        assert private not in text
