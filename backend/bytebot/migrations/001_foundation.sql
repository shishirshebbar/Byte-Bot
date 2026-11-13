CREATE TABLE demo_users (
    id uuid PRIMARY KEY,
    display_name text NOT NULL DEFAULT 'Demo user',
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE demo_sessions (
    token_hash text PRIMARY KEY,
    owner_id uuid NOT NULL REFERENCES demo_users(id),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE transaction_templates (
    template_key text PRIMARY KEY,
    direction text NOT NULL CHECK (direction = 'incoming'),
    amount_paise bigint NOT NULL CHECK (amount_paise > 0),
    currency text NOT NULL CHECK (currency = 'INR'),
    sender_name text NOT NULL,
    sender_vpa text NOT NULL,
    receiver_vpa text NOT NULL,
    occurred_at timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('successful', 'pending', 'failed')),
    reference text NOT NULL,
    source text NOT NULL CHECK (source = 'mock')
);
CREATE TABLE transactions (
    id uuid PRIMARY KEY,
    owner_id uuid NOT NULL REFERENCES demo_users(id),
    template_key text NOT NULL REFERENCES transaction_templates(template_key),
    direction text NOT NULL CHECK (direction = 'incoming'),
    amount_paise bigint NOT NULL CHECK (amount_paise > 0),
    currency text NOT NULL CHECK (currency = 'INR'),
    sender_name text NOT NULL,
    sender_vpa text NOT NULL,
    receiver_vpa text NOT NULL,
    occurred_at timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('successful', 'pending', 'failed')),
    reference text NOT NULL,
    source text NOT NULL CHECK (source = 'mock'),
    UNIQUE (owner_id, template_key),
    UNIQUE (owner_id, id)
);
CREATE INDEX transactions_owner_time ON transactions(owner_id, occurred_at DESC, id);
