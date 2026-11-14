-- "Was this helpful?" answers, one per case and analysis run.
CREATE TABLE agent_feedback (
    investigation_id uuid NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    run_id uuid NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    helpful boolean NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (investigation_id, run_id)
);
