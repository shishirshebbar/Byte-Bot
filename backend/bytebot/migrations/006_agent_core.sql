-- Supervisor decisions, follow-up questions, policy-gated actions, and human escalation.
CREATE TABLE agent_trace (
    run_id uuid NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    seq integer NOT NULL CHECK (seq >= 0),
    node text NOT NULL,
    reason text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, seq)
);
CREATE TABLE follow_up_questions (
    id uuid PRIMARY KEY,
    investigation_id uuid NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    run_id uuid NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    input_revision integer NOT NULL CHECK (input_revision >= 0),
    field text NOT NULL,
    blocking boolean NOT NULL,
    state text NOT NULL DEFAULT 'open' CHECK (state IN ('open','answered','revoked')),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, field)
);
CREATE INDEX follow_up_case ON follow_up_questions(investigation_id, input_revision);
CREATE TABLE agent_actions (
    id uuid PRIMARY KEY,
    investigation_id uuid NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    run_id uuid NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    input_revision integer NOT NULL CHECK (input_revision >= 0),
    seq integer NOT NULL CHECK (seq >= 0),
    action_type text NOT NULL,
    system text NOT NULL,
    verdict text NOT NULL CHECK (verdict IN ('auto','needs_customer_consent','needs_human_approval','deny')),
    state text NOT NULL CHECK (state IN ('approved','awaiting_consent','awaiting_human','denied',
                                         'executed','failed','compensated','revoked')),
    actor text NOT NULL DEFAULT 'agent' CHECK (actor IN ('agent','customer','human')),
    reason text NOT NULL,
    policy_version text NOT NULL,
    idempotency_key text NOT NULL UNIQUE,
    system_reference text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, action_type)
);
CREATE INDEX agent_actions_case ON agent_actions(investigation_id, state);
CREATE TABLE escalations (
    id uuid PRIMARY KEY,
    investigation_id uuid NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    run_id uuid REFERENCES analysis_runs(id) ON DELETE SET NULL,
    input_revision integer NOT NULL CHECK (input_revision >= 0),
    source text NOT NULL CHECK (source IN ('agent','customer')),
    reasons jsonb NOT NULL,
    priority text NOT NULL CHECK (priority IN ('urgent','high','normal')),
    state text NOT NULL DEFAULT 'open' CHECK (state IN ('open','assigned','resolved')),
    sla_due_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX one_active_escalation ON escalations(investigation_id) WHERE state <> 'resolved';
ALTER TABLE audit_events DROP CONSTRAINT audit_events_actor_check;
ALTER TABLE audit_events ADD CHECK (actor IN ('user','system','agent'));
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CHECK (action IN ('investigation_created','context_updated',
    'evidence_submitted','evidence_updated','evidence_removed','analysis_completed',
    'report_generated','status_updated','escalation_opened','follow_ups_answered'));
