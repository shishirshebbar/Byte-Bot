-- Records held by the local simulated systems that Byte Bot acts on.
CREATE TABLE simulated_records (
    id uuid PRIMARY KEY,
    investigation_id uuid NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    action_id uuid NOT NULL UNIQUE REFERENCES agent_actions(id) ON DELETE CASCADE,
    system text NOT NULL,
    action_type text NOT NULL,
    reference text NOT NULL UNIQUE,
    status text NOT NULL CHECK (status IN ('active','reversed')),
    detail text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE agent_actions DROP CONSTRAINT agent_actions_state_check;
ALTER TABLE agent_actions ADD CHECK (state IN ('approved','awaiting_consent','awaiting_human','denied','declined',
                                               'executed','failed','compensated','revoked'));
ALTER TABLE agent_actions ADD COLUMN attempts integer NOT NULL DEFAULT 0;
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CHECK (action IN ('investigation_created','context_updated',
    'evidence_submitted','evidence_updated','evidence_removed','analysis_completed',
    'report_generated','status_updated','escalation_opened','follow_ups_answered',
    'action_executed','action_failed','action_declined','action_compensated'));
