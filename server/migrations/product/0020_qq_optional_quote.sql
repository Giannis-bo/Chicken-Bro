-- Historical and professional replies keep their reference; new social drafts opt in.
ALTER TABLE qq_channel.outbox ADD COLUMN quote_reply boolean NOT NULL DEFAULT true;
