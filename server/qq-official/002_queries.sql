-- Official QQ Candidate/test only. No website migration or production data.
CREATE TABLE IF NOT EXISTS qq_channel.official_queries (
 inbox_id uuid PRIMARY KEY REFERENCES qq_channel.inbox(id),
 request jsonb NOT NULL,
 result_text text NOT NULL DEFAULT '',
 attempts integer NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 2),
 lease_token uuid,
 lease_expires_at timestamptz,
 completed_at timestamptz
);
GRANT SELECT,INSERT,UPDATE ON qq_channel.official_queries TO wow_app;
