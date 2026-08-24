-- 0036: allow the governed S2 tier-set static Browse track.
--
-- The application Track Authority already treats season_special as a
-- first-class progression kind.  Older databases still carry the 0019
-- three-kind constraint, so replace only that check before sealing the S2
-- Catalog.  Existing sealed rows remain append-only and are unaffected.
DO $progression_kind_constraint$
DECLARE
    v_constraint_name name;
BEGIN
    SELECT constraint_row.conname
    INTO v_constraint_name
    FROM pg_catalog.pg_constraint AS constraint_row
    WHERE constraint_row.conrelid = 'cache.websim_gear_browse_variants'::pg_catalog.regclass
      AND constraint_row.contype = 'c'
      AND pg_catalog.pg_get_constraintdef(constraint_row.oid) LIKE '%progression_kind%';

    IF v_constraint_name IS NOT NULL THEN
        EXECUTE pg_catalog.format(
            'ALTER TABLE cache.websim_gear_browse_variants DROP CONSTRAINT %I',
            v_constraint_name
        );
    END IF;
END;
$progression_kind_constraint$;

ALTER TABLE cache.websim_gear_browse_variants
ADD CONSTRAINT websim_gear_browse_variants_progression_kind_check
CHECK (progression_kind IN ('upgrade_track', 'crafted_quality', 'ascendant', 'season_special'));

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0036_websim_gear_catalog_season_special',
    'Allow the governed season_special tier-set static Browse progression kind'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description;
