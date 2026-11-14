-- Simulated fraud-intelligence graph: identifiers, devices, and incidents joined by typed, sourced edges.
CREATE TABLE intel_nodes (
    node_key text PRIMARY KEY,
    kind text NOT NULL CHECK (kind IN ('vpa','phone','device','incident','account')),
    identifier text NOT NULL,
    label text NOT NULL,
    source_label text NOT NULL,
    reported_at timestamptz NOT NULL,
    UNIQUE (kind, identifier)
);
CREATE TABLE intel_edges (
    edge_key text PRIMARY KEY,
    source_key text NOT NULL REFERENCES intel_nodes(node_key),
    target_key text NOT NULL REFERENCES intel_nodes(node_key),
    relation text NOT NULL,
    source_label text NOT NULL,
    CHECK (source_key <> target_key)
);
CREATE INDEX intel_edges_source ON intel_edges(source_key);
CREATE INDEX intel_edges_target ON intel_edges(target_key);
