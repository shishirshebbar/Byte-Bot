"""Exact simulated intelligence; no reputation or trust inference."""
import re


def normalize(kind, identifier):
    return identifier.strip().casefold() if kind == 'vpa' else re.sub(r'[^\d+]', '', identifier)


def seed_intelligence(conn):
    conn.execute("INSERT INTO intel_entities VALUES ('reported-vpa','vpa','reported.demo@upi',"
                 "'Synthetic reported-entity fixture','2026-11-01T00:00:00Z') ON CONFLICT DO NOTHING")
    conn.execute("INSERT INTO intel_entities VALUES ('reported-phone','phone','+919000000001',"
                 "'Synthetic reported-entity fixture','2026-11-01T00:00:00Z') ON CONFLICT DO NOTHING")
    for kind in ('vpa', 'phone'):
        conn.execute('INSERT INTO intel_relations VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                     (f'relation-{kind}', f'reported-{kind}', 'SYNTHETIC-INCIDENT-001',
                      'reported_in_demo_incident', 'Synthetic incident relationship'))


def lookup(conn, identifiers):
    matches = []
    for kind, identifier in sorted(set(identifiers)):
        identifier = normalize(kind, identifier)
        rows = conn.execute('SELECT e.*,r.incident_reference,r.relation_type,r.source_label AS relationship_source '
                            'FROM intel_entities e JOIN intel_relations r ON r.entity_key=e.fixture_key '
                            'WHERE e.entity_type=%s AND e.identifier=%s', (kind, identifier)).fetchall()
        for row in rows:
            matches.append({**row, 'reported_at': row['reported_at'].isoformat(), 'match_type': 'exact',
                            'limitations': 'Simulated reported intelligence only; a match is not proof of guilt.'})
    return matches


# A small synthetic mule ring. Two repayment UPI IDs from the demo scenarios share a
# phone number and a device with three reported incidents. Every row is synthetic.
GRAPH_NODES = [
    ('vpa-refund-demo', 'vpa', 'refund.demo@upi', 'Repayment UPI ID'),
    ('vpa-refund-desk', 'vpa', 'refund.desk@upi', 'Repayment UPI ID'),
    ('phone-ring', 'phone', '+919000000002', 'Shared contact number'),
    ('device-ring', 'device', 'DEVICE-SYN-7F2A', 'Shared device fingerprint'),
    ('incident-002', 'incident', 'SYNTHETIC-INCIDENT-002', 'Reported repayment scam'),
    ('incident-003', 'incident', 'SYNTHETIC-INCIDENT-003', 'Reported repayment scam'),
    ('incident-004', 'incident', 'SYNTHETIC-INCIDENT-004', 'Reported collect-request scam'),
    # Case 4: a sender whose credits were followed by rapid repayment requests to other accounts.
    ('vpa-rahul', 'vpa', 'rahul.demo@upi', 'Sender UPI ID'),
    ('incident-005', 'incident', 'SYNTHETIC-INCIDENT-005', 'Credit followed by a rapid repayment request'),
    ('incident-006', 'incident', 'SYNTHETIC-INCIDENT-006', 'Credit followed by a rapid repayment request'),
    ('incident-007', 'incident', 'SYNTHETIC-INCIDENT-007', 'Reported mistaken-credit scam'),
    ('vpa-payback', 'vpa', 'payback.demo@upi', 'Repayment recipient'),
    ('vpa-returnhelp', 'vpa', 'return.help@upi', 'Repayment recipient'),
]
GRAPH_EDGES = [
    ('e1', 'vpa-refund-demo', 'phone-ring', 'registered_with'),
    ('e2', 'vpa-refund-desk', 'phone-ring', 'registered_with'),
    ('e3', 'vpa-refund-desk', 'device-ring', 'used_on'),
    ('e4', 'phone-ring', 'incident-002', 'reported_in'),
    ('e5', 'phone-ring', 'incident-003', 'reported_in'),
    ('e6', 'device-ring', 'incident-004', 'reported_in'),
    ('e7', 'vpa-rahul', 'incident-005', 'sent_credit_in'),
    ('e8', 'vpa-rahul', 'incident-006', 'sent_credit_in'),
    ('e9', 'vpa-rahul', 'incident-007', 'sent_credit_in'),
    ('e10', 'incident-005', 'vpa-payback', 'repaid_to'),
    ('e11', 'incident-006', 'vpa-returnhelp', 'repaid_to'),
    ('e12', 'incident-007', 'vpa-payback', 'repaid_to'),
]
GRAPH_SOURCE = 'Synthetic fraud-intelligence graph'
LINK_LIMITATION = 'Simulated graph link only; shared contact details are not proof of guilt.'


def seed_graph(conn):
    for key, kind, identifier, label in GRAPH_NODES:
        conn.execute('INSERT INTO intel_nodes VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                     (key, kind, identifier, label, GRAPH_SOURCE, '2026-11-05T00:00:00Z'))
    for key, source, target, relation in GRAPH_EDGES:
        conn.execute('INSERT INTO intel_edges VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                     (key, source, target, relation, GRAPH_SOURCE))


WALK = '''
WITH RECURSIVE walk(node_key, hops, path) AS (
    SELECT node_key, 0, ARRAY[node_key] FROM intel_nodes WHERE kind=%s AND identifier=%s
  UNION ALL
    SELECT CASE WHEN e.source_key = w.node_key THEN e.target_key ELSE e.source_key END, w.hops + 1,
           w.path || CASE WHEN e.source_key = w.node_key THEN e.target_key ELSE e.source_key END
    FROM walk w JOIN intel_edges e ON w.node_key IN (e.source_key, e.target_key)
    WHERE w.hops < 2 AND NOT (CASE WHEN e.source_key = w.node_key THEN e.target_key ELSE e.source_key END) = ANY(w.path)
)
SELECT w.hops, w.path, n.identifier AS incident FROM walk w JOIN intel_nodes n ON n.node_key = w.node_key
WHERE n.kind = 'incident' ORDER BY w.hops, n.identifier
'''


def graph_links(conn, identifiers):
    """Incidents within two hops of each identifier, with the connecting path."""
    links = []
    for kind, identifier in sorted(set(identifiers)):
        rows = conn.execute(WALK, (kind, normalize(kind, identifier))).fetchall()
        if not rows:
            continue
        via = sorted({row['path'][1] for row in rows if row['hops'] == 2})
        links.append({'identifier': normalize(kind, identifier), 'kind': kind,
                      'incidents': sorted({row['incident'] for row in rows}),
                      'min_hops': min(row['hops'] for row in rows), 'via': via,
                      'source_label': GRAPH_SOURCE, 'limitations': LINK_LIMITATION})
    return links


def subgraph(conn, identifiers):
    """Nodes and edges within two hops of the case's identifiers, for display."""
    keys = set()
    for kind, identifier in set(identifiers):
        for row in conn.execute(WALK.replace("WHERE n.kind = 'incident'", 'WHERE true'), (kind, normalize(kind, identifier))).fetchall():
            keys.update(row['path'])
    if not keys:
        return {'nodes': [], 'edges': []}
    nodes = conn.execute('SELECT node_key AS id, kind, identifier, label FROM intel_nodes WHERE node_key = ANY(%s) ORDER BY node_key', (list(keys),)).fetchall()
    edges = conn.execute('SELECT source_key AS source, target_key AS target, relation FROM intel_edges '
                         'WHERE source_key = ANY(%s) AND target_key = ANY(%s) ORDER BY edge_key', (list(keys), list(keys))).fetchall()
    return {'nodes': nodes, 'edges': edges, 'source_label': GRAPH_SOURCE, 'limitations': LINK_LIMITATION}
