-- Demo support-agent sessions, escalation ownership, and human notes.
CREATE TABLE console_agents (
    id uuid PRIMARY KEY,
    name text NOT NULL,
    token_hash text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE escalations ADD COLUMN assignee_id uuid REFERENCES console_agents(id) ON DELETE SET NULL;
ALTER TABLE escalations ADD COLUMN resolved_at timestamptz;
CREATE TABLE escalation_notes (
    id uuid PRIMARY KEY,
    escalation_id uuid NOT NULL REFERENCES escalations(id) ON DELETE CASCADE,
    agent_id uuid REFERENCES console_agents(id) ON DELETE SET NULL,
    text text NOT NULL CHECK (length(text) BETWEEN 1 AND 2000),
    created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE audit_events DROP CONSTRAINT audit_events_actor_check;
ALTER TABLE audit_events ADD CHECK (actor IN ('user','system','agent','human'));
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CHECK (action IN ('investigation_created','context_updated',
    'evidence_submitted','evidence_updated','evidence_removed','analysis_completed',
    'report_generated','status_updated','escalation_opened','follow_ups_answered',
    'action_executed','action_failed','action_declined','action_compensated',
    'escalation_assigned','escalation_resolved','note_added'));
