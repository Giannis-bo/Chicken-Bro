ALTER TABLE cache.websim_active_manifest_pointer
    ADD COLUMN IF NOT EXISTS pointer_mode text NOT NULL DEFAULT 'active';

ALTER TABLE cache.websim_active_manifest_pointer
    ALTER COLUMN manifest_revision DROP NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'websim_active_manifest_pointer_mode_check'
          AND conrelid = 'cache.websim_active_manifest_pointer'::regclass
    ) THEN
        ALTER TABLE cache.websim_active_manifest_pointer
            ADD CONSTRAINT websim_active_manifest_pointer_mode_check
            CHECK (pointer_mode IN ('active', 'transitional'));
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'websim_active_manifest_pointer_state_check'
          AND conrelid = 'cache.websim_active_manifest_pointer'::regclass
    ) THEN
        ALTER TABLE cache.websim_active_manifest_pointer
            ADD CONSTRAINT websim_active_manifest_pointer_state_check
            CHECK (
                (pointer_mode = 'active' AND manifest_revision IS NOT NULL)
                OR (pointer_mode = 'transitional' AND manifest_revision IS NULL)
            );
    END IF;
END
$$;

REVOKE DELETE ON cache.websim_active_manifest_pointer FROM wow_app;
GRANT SELECT, INSERT, UPDATE ON cache.websim_active_manifest_pointer TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0014_websim_active_manifest_pointer_state',
    'Add explicit active and transitional modes while preserving one monotonic retail Manifest pointer row'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();
