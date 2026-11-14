"""Explainable risk score and the simulated fraud-intelligence graph."""
import pytest
from fastapi.testclient import TestClient
from bytebot.main import create_app
from bytebot.fixtures import SCENARIOS, FixtureProvider
from bytebot import risk_rules
from bytebot.risk_rules import score, WEIGHTS
from test_analysis import run_case
from test_agent import load, path, API


@pytest.fixture
def client(prepared):
    with TestClient(create_app(prepared, extraction_provider=FixtureProvider(), worker_enabled=False)) as client:
        client.get(API + '/transactions')
        yield client


def test_two_hop_graph_links_raise_findings_and_score(client):
    result = run_case(client, load(client, 'K'))['result']
    link = next(f for f in result['findings'] if f['kind'] == 'intel_link')
    assert 'refund.desk@upi is linked through a shared contact or device to 3 reported incidents' in link['text']
    assert link['source'] == 'Synthetic fraud-intelligence graph' and 'not proof' in link['text']
    assert result['graph_links'][0]['incidents'] == ['SYNTHETIC-INCIDENT-002', 'SYNTHETIC-INCIDENT-003', 'SYNTHETIC-INCIDENT-004']
    assert result['graph_links'][0]['min_hops'] == 2
    factors = {f['id']: f for f in result['risk_factors']}
    assert factors['intel_link']['weight'] == 15 and factors['destination_mismatch']['status'] == 'fail'
    assert result['risk_score'] == sum(f['weight'] for f in result['risk_factors'])
    assert result['score_version'] == 'score-1'
    assert not any('No match found' in line for line in result['limitations'])


def test_same_id_is_a_zero_weight_factor_and_no_link(client):
    result = run_case(client, load(client, 'B'))['result']
    factors = {f['id']: f for f in result['risk_factors']}
    assert factors['same_destination']['weight'] == 0 and factors['same_destination']['status'] == 'warn'
    assert result['graph_links'] == []
    # One factor per signal even when the customer and the evidence both report it.
    assert len(factors['threat']['sources']) == 2
    assert result['risk_score'] == 20 + 15 + 10 + 10  # threat, bank avoidance, repayment, unexpected


@pytest.mark.parametrize('weight', [0, 100])
def test_score_never_changes_the_category(client, monkeypatch, weight):
    for kind in WEIGHTS:
        monkeypatch.setitem(risk_rules.WEIGHTS, kind, weight)
    for key in ('A', 'B', 'D', 'J', 'K'):
        assert run_case(client, load(client, key))['result']['category'] == SCENARIOS[key]['category']


def test_score_is_capped_and_ignores_unknown_kinds():
    findings = [{'kind': kind, 'text': kind, 'source': 'test'} for kind in WEIGHTS] + [{'kind': 'amount', 'text': 'x', 'source': 'test'}]
    total, factors = score(findings)
    assert total == 100 and 'amount' not in {f['id'] for f in factors}
    assert factors[0]['weight'] == max(WEIGHTS.values())


def test_intel_graph_endpoint_is_owner_scoped(client, prepared):
    case = load(client, 'F')
    before = client.get(path(case) + '/intel-graph').json()
    assert {n['id'] for n in before['nodes']} >= {'vpa-refund-demo', 'phone-ring', 'incident-002', 'incident-003'}
    assert {(e['source'], e['target']) for e in before['edges']} >= {('vpa-refund-demo', 'phone-ring'), ('phone-ring', 'incident-002')}
    assert 'recipient.demo@upi' not in str(before)  # The customer's own ID is never part of the graph.
    quiet = client.get(path(load(client, 'C')) + '/intel-graph').json()
    assert quiet['nodes'] == []
    with TestClient(create_app(prepared, extraction_provider=FixtureProvider(), worker_enabled=False)) as other:
        other.get(API + '/transactions')
        assert other.get(path(case) + '/intel-graph').status_code == 404
