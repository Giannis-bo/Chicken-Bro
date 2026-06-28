CREATE SCHEMA IF NOT EXISTS identity;
CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS content;
CREATE SCHEMA IF NOT EXISTS cache;
CREATE SCHEMA IF NOT EXISTS knowledge;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE IF NOT EXISTS identity.users (
    id uuid PRIMARY KEY,
    display_name text NOT NULL DEFAULT '',
    status text NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS identity.user_identities (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    provider text NOT NULL,
    provider_subject text NOT NULL,
    profile_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider, provider_subject)
);

CREATE TABLE IF NOT EXISTS identity.auth_tokens (
    token_hash text PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    issued_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS app.build_templates (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    template_type text NOT NULL,
    name text NOT NULL,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    config_hash text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, template_type, config_hash)
);

CREATE TABLE IF NOT EXISTS app.build_archives (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    source_template_id uuid REFERENCES app.build_templates(id) ON DELETE SET NULL,
    source_event text NOT NULL,
    name text NOT NULL,
    config_hash text NOT NULL,
    snapshot_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, name, config_hash)
);

CREATE TABLE IF NOT EXISTS app.simulator_tasks (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    mode text NOT NULL,
    status text NOT NULL,
    request_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    analysis_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    summary_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    queued_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    attempt integer NOT NULL DEFAULT 0,
    locked_by text NOT NULL DEFAULT '',
    heartbeat_at timestamptz,
    cancel_requested boolean NOT NULL DEFAULT false,
    last_error text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.chickenbro_sessions (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    title text NOT NULL DEFAULT '',
    status text NOT NULL DEFAULT 'active',
    context_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.chickenbro_messages (
    id uuid PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES app.chickenbro_sessions(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    role text NOT NULL,
    content text NOT NULL,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    evidence_refs_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    agent_job_id uuid,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.chickenbro_actions (
    id uuid PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES app.chickenbro_sessions(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'open',
    title text NOT NULL DEFAULT '',
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    evidence_refs_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.agent_jobs (
    id uuid PRIMARY KEY,
    user_id uuid REFERENCES identity.users(id) ON DELETE SET NULL,
    session_id uuid REFERENCES app.chickenbro_sessions(id) ON DELETE CASCADE,
    task_id uuid REFERENCES app.simulator_tasks(id) ON DELETE CASCADE,
    job_type text NOT NULL,
    status text NOT NULL DEFAULT 'queued',
    request_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    bounded_context_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    result_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    queued_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    attempt integer NOT NULL DEFAULT 0,
    locked_by text NOT NULL DEFAULT '',
    heartbeat_at timestamptz,
    cancel_requested boolean NOT NULL DEFAULT false,
    last_error text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS content.sources (
    id uuid PRIMARY KEY,
    source_key text NOT NULL UNIQUE,
    name text NOT NULL,
    url text NOT NULL DEFAULT '',
    source_type text NOT NULL DEFAULT '',
    status text NOT NULL DEFAULT 'active',
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS content.raw_articles (
    id text PRIMARY KEY,
    source_id uuid REFERENCES content.sources(id) ON DELETE SET NULL,
    source_url text NOT NULL DEFAULT '',
    title text NOT NULL DEFAULT '',
    summary text NOT NULL DEFAULT '',
    body text NOT NULL DEFAULT '',
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    discovered_at timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS content.article_evidence (
    id uuid PRIMARY KEY,
    article_id text NOT NULL REFERENCES content.raw_articles(id) ON DELETE CASCADE,
    evidence_type text NOT NULL,
    status text NOT NULL DEFAULT 'pending',
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS content.articles (
    id text PRIMARY KEY,
    raw_article_id text REFERENCES content.raw_articles(id) ON DELETE SET NULL,
    title text NOT NULL,
    summary text NOT NULL,
    body_zh text NOT NULL DEFAULT '',
    channel text NOT NULL DEFAULT '',
    category text NOT NULL DEFAULT '',
    tags_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    importance integer NOT NULL DEFAULT 0,
    source_name text NOT NULL DEFAULT '',
    source_url text NOT NULL DEFAULT '',
    source_note text NOT NULL DEFAULT '',
    published_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cache.websim_sync_state (
    id text PRIMARY KEY,
    state_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cache.websim_items (
    id text PRIMARY KEY,
    name text NOT NULL DEFAULT '',
    slot text NOT NULL DEFAULT '',
    item_level integer,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_status text NOT NULL DEFAULT 'unknown',
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cache.websim_gear_sources (
    id uuid PRIMARY KEY,
    item_id text NOT NULL REFERENCES cache.websim_items(id) ON DELETE CASCADE,
    source_type text NOT NULL,
    source_key text NOT NULL DEFAULT '',
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cache.websim_gear_variants (
    id uuid PRIMARY KEY,
    item_id text NOT NULL REFERENCES cache.websim_items(id) ON DELETE CASCADE,
    variant_key text NOT NULL,
    readiness text NOT NULL DEFAULT 'partial',
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (item_id, variant_key)
);

CREATE TABLE IF NOT EXISTS cache.websim_gear_mod_options (
    id uuid PRIMARY KEY,
    variant_id uuid NOT NULL REFERENCES cache.websim_gear_variants(id) ON DELETE CASCADE,
    option_key text NOT NULL,
    is_visible boolean NOT NULL DEFAULT false,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (variant_id, option_key)
);

CREATE TABLE IF NOT EXISTS cache.websim_talents (
    id text PRIMARY KEY,
    class_key text NOT NULL,
    spec_key text NOT NULL,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cache.websim_community_talent_templates (
    id uuid PRIMARY KEY,
    class_key text NOT NULL,
    spec_key text NOT NULL,
    source_key text NOT NULL,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cache.raiderio_cache (
    cache_key text PRIMARY KEY,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    fetched_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz
);

CREATE TABLE IF NOT EXISTS cache.stat_weight_cache (
    cache_key text PRIMARY KEY,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    computed_at timestamptz NOT NULL DEFAULT now(),
    source_status text NOT NULL DEFAULT 'unknown'
);

CREATE TABLE IF NOT EXISTS knowledge.public_documents (
    id uuid PRIMARY KEY,
    source_type text NOT NULL,
    title text NOT NULL,
    body text NOT NULL DEFAULT '',
    tags_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    search_vector tsvector,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS knowledge.public_document_chunks (
    id uuid PRIMARY KEY,
    document_id uuid NOT NULL REFERENCES knowledge.public_documents(id) ON DELETE CASCADE,
    chunk_index integer NOT NULL,
    body text NOT NULL,
    tags_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    search_vector tsvector,
    embedding_status text NOT NULL DEFAULT 'disabled',
    embedding_vector double precision[],
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS knowledge.user_context_summaries (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    context_type text NOT NULL,
    summary_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_refs_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, context_type)
);

CREATE TABLE IF NOT EXISTS analytics.events (
    id uuid PRIMARY KEY,
    user_id uuid REFERENCES identity.users(id) ON DELETE SET NULL,
    anonymous_id text NOT NULL DEFAULT '',
    event_name text NOT NULL,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS analytics.user_links (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    anonymous_id text NOT NULL,
    linked_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, anonymous_id)
);

CREATE TABLE IF NOT EXISTS analytics.daily_metrics (
    metric_date date NOT NULL,
    metric_key text NOT NULL,
    dimensions_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    value numeric NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (metric_date, metric_key, dimensions_json)
);

CREATE TABLE IF NOT EXISTS ops.schema_migrations (
    id text PRIMARY KEY,
    description text NOT NULL DEFAULT '',
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ops.sync_runs (
    id uuid PRIMARY KEY,
    sync_type text NOT NULL,
    status text NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    counts_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    error text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS ops.audit_logs (
    id uuid PRIMARY KEY,
    actor_user_id uuid REFERENCES identity.users(id) ON DELETE SET NULL,
    action text NOT NULL,
    target_type text NOT NULL DEFAULT '',
    target_id text NOT NULL DEFAULT '',
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ops.health_snapshots (
    id uuid PRIMARY KEY,
    snapshot_type text NOT NULL,
    status text NOT NULL,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0001_identity_app_content_cache_knowledge_analytics_ops',
    'Create PostgreSQL identity, app, content, cache, knowledge, analytics, and ops schemas'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();
