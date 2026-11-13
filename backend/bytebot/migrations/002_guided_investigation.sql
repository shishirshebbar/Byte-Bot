CREATE TABLE investigations (
    id uuid PRIMARY KEY,
    owner_id uuid NOT NULL REFERENCES demo_users(id),
    transaction_id uuid NOT NULL,
    input_revision integer NOT NULL DEFAULT 0 CHECK (input_revision >= 0),
    workflow_state text NOT NULL DEFAULT 'collecting_context' CHECK (workflow_state = 'collecting_context'),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (owner_id, transaction_id) REFERENCES transactions(owner_id, id),
    UNIQUE (owner_id, transaction_id)
);
CREATE TABLE investigation_context (
    investigation_id uuid PRIMARY KEY REFERENCES investigations(id) ON DELETE CASCADE,
    answers jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(answers) = 'object')
);
CREATE TABLE evidence (
    id uuid PRIMARY KEY,
    investigation_id uuid NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    type text NOT NULL CHECK (type IN ('message', 'call_summary', 'screenshot')),
    review_state text NOT NULL CHECK (review_state IN ('needs_review', 'ocr_failed', 'confirmed')),
    ocr_text text,
    confirmed_text text,
    metadata jsonb NOT NULL DEFAULT '{}',
    notice text CHECK (notice IN ('ocr_unavailable', 'unreadable')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (review_state <> 'confirmed' OR length(trim(confirmed_text)) > 0),
    CHECK (review_state <> 'confirmed' OR confirmed_text IS NOT NULL),
    CHECK (type = 'screenshot' OR review_state = 'confirmed')
);
CREATE INDEX evidence_case_time ON evidence(investigation_id, created_at, id);
