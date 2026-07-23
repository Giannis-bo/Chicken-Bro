-- One Community Release now contains one legal observed-gear winner for each
-- of the two Hero Talent slots in a specialization.  The legacy partial index
-- only permitted one winner per spec and therefore prevented v2 releases from
-- being sealed.
-- 0017_websim_hero_community_release

DROP INDEX IF EXISTS cache.idx_cache_websim_community_release_one_winner;

CREATE UNIQUE INDEX IF NOT EXISTS idx_cache_websim_community_release_winner_rank
ON cache.websim_community_release_templates (release_id, class_key, spec_key, election_rank)
WHERE role = 'winner';

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0017_websim_hero_community_release',
    'Allow two ranked Hero Talent Community winners per specialization in a sealed release'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();
