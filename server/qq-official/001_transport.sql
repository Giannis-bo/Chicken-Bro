-- Apply only to the dedicated official QQ Candidate/test databases.
CREATE TABLE IF NOT EXISTS qq_channel.official_messages (
 inbox_id uuid PRIMARY KEY REFERENCES qq_channel.inbox(id),
 occurred_at timestamptz NOT NULL,
 next_sequence integer NOT NULL DEFAULT 1 CHECK(next_sequence BETWEEN 1 AND 6)
);
GRANT SELECT,INSERT,UPDATE ON qq_channel.official_messages TO wow_app;
