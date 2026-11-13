ALTER TABLE investigations
    ADD COLUMN case_status text NOT NULL DEFAULT 'Open'
        CHECK (case_status IN ('Open','Bank Contacted','Reported','Awaiting Response','Resolved','Closed')),
    ADD COLUMN status_revision integer NOT NULL DEFAULT 0 CHECK (status_revision >= 0);

CREATE TABLE incident_reports (
    id uuid PRIMARY KEY,
    investigation_id uuid NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    input_revision integer NOT NULL CHECK (input_revision >= 0),
    run_id uuid NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    snapshot jsonb NOT NULL CHECK (jsonb_typeof(snapshot) = 'object'),
    generated_at timestamptz NOT NULL,
    UNIQUE (investigation_id,input_revision)
);

CREATE TABLE audit_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    investigation_id uuid NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    actor text NOT NULL CHECK (actor IN ('user','system')),
    action text NOT NULL CHECK (action IN ('investigation_created','context_updated',
        'evidence_submitted','evidence_updated','evidence_removed','analysis_completed',
        'report_generated','status_updated')),
    metadata jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(metadata) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_case_time ON audit_events(investigation_id,created_at,id);

-- These are the only historical actions whose original timestamps survive.
INSERT INTO audit_events(investigation_id,actor,action,metadata,created_at)
SELECT id,'user','investigation_created','{"backfilled":true}',created_at FROM investigations;
INSERT INTO audit_events(investigation_id,actor,action,metadata,created_at)
SELECT investigation_id,'user','evidence_submitted',
       jsonb_build_object('backfilled',true,'evidence_id',id,'evidence_type',type),created_at
FROM evidence;
INSERT INTO audit_events(investigation_id,actor,action,metadata,created_at)
SELECT investigation_id,'system','analysis_completed',
       jsonb_build_object('backfilled',true,'run_id',id,'input_revision',input_revision),updated_at
FROM analysis_runs WHERE state='complete';
