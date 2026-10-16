-- Dedicated official QQ Candidate/test DB only. Lease-fenced evidence stays
-- beside its original inbox identity; no website identity/session changes.
ALTER TABLE qq_channel.official_queries ADD COLUMN IF NOT EXISTS result_packet jsonb;
