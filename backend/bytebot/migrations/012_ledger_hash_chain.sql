-- Tamper-evident audit ledger: every new entry hashes its content and the previous entry for the case.
ALTER TABLE audit_events ADD COLUMN prev_hash text;
ALTER TABLE audit_events ADD COLUMN entry_hash text;
CREATE INDEX audit_events_chain ON audit_events(investigation_id, id);
