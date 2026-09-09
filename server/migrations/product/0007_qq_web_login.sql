-- Add QQ without changing, merging or deleting retained WeChat owners.
ALTER TABLE identity.user_identities
    DROP CONSTRAINT user_identities_provider_check,
    ADD CONSTRAINT user_identities_provider_check CHECK (provider IN ('wechat_mini', 'qq'));

CREATE TABLE identity.qq_login_attempts (
    state_sha256 text PRIMARY KEY CHECK (state_sha256 ~ '^[0-9a-f]{64}$'),
    browser_sha256 text NOT NULL CHECK (browser_sha256 ~ '^[0-9a-f]{64}$'),
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (expires_at > created_at)
);
CREATE INDEX qq_login_attempts_expiry ON identity.qq_login_attempts (expires_at);
GRANT SELECT, INSERT, UPDATE ON identity.qq_login_attempts TO wow_app;
