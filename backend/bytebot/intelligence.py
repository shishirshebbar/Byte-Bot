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
