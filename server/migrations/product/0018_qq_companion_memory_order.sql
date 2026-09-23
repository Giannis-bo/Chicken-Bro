-- Stable source ordering survives observation retention and prevents stale writes.
ALTER TABLE qq_channel.member_facts ADD COLUMN source_seq bigint NOT NULL DEFAULT 0;
