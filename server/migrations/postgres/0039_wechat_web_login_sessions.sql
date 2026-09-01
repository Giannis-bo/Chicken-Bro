BEGIN;

-- 0039 is an additive v2 identity boundary. The legacy identity tables remain
-- owned by the existing compatibility runtime and are not altered here.

CREATE TABLE IF NOT EXISTS identity.auth_sessions (
    token_hash text PRIMARY KEY CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    kind text NOT NULL CHECK (kind IN ('mini_bearer', 'web_cookie')),
    issued_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_identity_auth_sessions_user_kind
ON identity.auth_sessions (user_id, kind, expires_at DESC)
WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS identity.web_login_sessions (
    id uuid PRIMARY KEY,
    scene_ticket_sha256 text NOT NULL UNIQUE CHECK (scene_ticket_sha256 ~ '^[0-9a-f]{64}$'),
    browser_verifier_sha256 text NOT NULL CHECK (browser_verifier_sha256 ~ '^[0-9a-f]{64}$'),
    idempotency_key_sha256 text CHECK (
        idempotency_key_sha256 IS NULL OR idempotency_key_sha256 ~ '^[0-9a-f]{64}$'
    ),
    user_id uuid REFERENCES identity.users(id) ON DELETE CASCADE,
    status text NOT NULL CHECK (status IN ('pending', 'confirmed', 'exchanged', 'cancelled', 'expired')),
    expires_at timestamptz NOT NULL,
    exchanged_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_identity_web_login_idempotency
ON identity.web_login_sessions (browser_verifier_sha256, idempotency_key_sha256)
WHERE idempotency_key_sha256 IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_identity_web_login_expiry
ON identity.web_login_sessions (expires_at, status);

GRANT USAGE ON SCHEMA identity TO wow_app;
GRANT SELECT, INSERT, UPDATE, DELETE
ON identity.auth_sessions, identity.web_login_sessions
TO wow_app;

ALTER DEFAULT PRIVILEGES FOR ROLE wow_migrator IN SCHEMA identity
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0039_wechat_web_login_sessions',
    'Create isolated v2 mini bearer and Web cookie login session owners'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();

COMMIT;
