ALTER TABLE investigations DROP CONSTRAINT investigations_workflow_state_check;
ALTER TABLE investigations ADD CHECK (workflow_state IN
    ('collecting_context','analysis_queued','analyzing','results_ready','analysis_failed'));
CREATE TABLE analysis_runs (
    id uuid PRIMARY KEY,
    investigation_id uuid NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    input_revision integer NOT NULL CHECK (input_revision >= 0),
    state text NOT NULL CHECK (state IN ('queued','running','complete','failed')),
    stage text NOT NULL DEFAULT 'queued' CHECK (stage IN
        ('queued','transaction_context','message_analysis','risk_investigation','incident_resolution','complete')),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    lease_token uuid,
    lease_until timestamptz,
    stage_started_at timestamptz,
    stage_durations jsonb NOT NULL DEFAULT '{}',
    outputs jsonb NOT NULL DEFAULT '{}',
    error_code text,
    provider_mode text NOT NULL,
    rule_version text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (investigation_id,input_revision)
);
CREATE INDEX analysis_claim ON analysis_runs(state,lease_until,created_at);
CREATE TABLE extracted_signals (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    evidence_id uuid NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,
    data jsonb NOT NULL
);
CREATE TABLE risk_assessments (
    run_id uuid PRIMARY KEY REFERENCES analysis_runs(id) ON DELETE CASCADE,
    data jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE intel_entities (
    fixture_key text PRIMARY KEY,
    entity_type text NOT NULL CHECK (entity_type IN ('vpa','phone')),
    identifier text NOT NULL,
    source_label text NOT NULL,
    reported_at timestamptz NOT NULL,
    UNIQUE (entity_type,identifier)
);
CREATE TABLE intel_relations (
    fixture_key text PRIMARY KEY,
    entity_key text NOT NULL REFERENCES intel_entities(fixture_key),
    incident_reference text NOT NULL,
    relation_type text NOT NULL,
    source_label text NOT NULL
);
