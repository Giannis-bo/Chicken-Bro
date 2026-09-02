BEGIN;

-- 0040 is an additive, short-lived owner boundary for the Web prototype.
-- Formal WeChat and Web login sessions remain owned by migration 0039.

ALTER TABLE identity.users
    ADD COLUMN IF NOT EXISTS account_kind text NOT NULL DEFAULT 'formal';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'users_account_kind_check'
          AND conrelid = 'identity.users'::regclass
    ) THEN
        ALTER TABLE identity.users
            ADD CONSTRAINT users_account_kind_check
            CHECK (account_kind IN ('formal', 'prototype'));
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_identity_users_account_kind
ON identity.users (account_kind, status, id);

CREATE TABLE IF NOT EXISTS identity.prototype_sessions (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    token_sha256 text NOT NULL UNIQUE CHECK (token_sha256 ~ '^[0-9a-f]{64}$'),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_identity_prototype_sessions_owner
ON identity.prototype_sessions (user_id, expires_at DESC)
WHERE revoked_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_identity_prototype_sessions_expiry
ON identity.prototype_sessions (expires_at)
WHERE revoked_at IS NULL;

GRANT USAGE ON SCHEMA identity TO wow_app;
GRANT SELECT, INSERT, UPDATE, DELETE
ON identity.prototype_sessions
TO wow_app;

ALTER DEFAULT PRIVILEGES FOR ROLE wow_migrator IN SCHEMA identity
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0040_web_prototype_sessions',
    'Create isolated short-lived Web prototype owners and capabilities'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();

COMMIT;
