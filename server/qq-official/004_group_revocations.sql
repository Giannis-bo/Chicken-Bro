-- A provider removal event remains authoritative across members and restarts.
CREATE TABLE IF NOT EXISTS qq_channel.official_group_revocations (
    bot_id text NOT NULL,
    group_id text NOT NULL,
    revoked_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (bot_id, group_id)
);
GRANT SELECT, INSERT, UPDATE ON qq_channel.official_group_revocations TO wow_app;
