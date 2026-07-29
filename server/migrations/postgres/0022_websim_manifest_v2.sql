CREATE TABLE IF NOT EXISTS cache.websim_gear_exact_registries (
    registry_revision text PRIMARY KEY
        CHECK (
            registry_revision
            ~ '^gear-exact-registry:sha256:[0-9a-f]{64}$'
        ),
    catalog_revision text NOT NULL
        REFERENCES cache.websim_gear_catalog_revisions(catalog_revision)
        ON DELETE RESTRICT,
    season_revision text NOT NULL,
    gear_rule_revision text NOT NULL,
    registry_status text NOT NULL
        CHECK (registry_status IN ('verified', 'partial')),
    registry_summary_json jsonb NOT NULL
        CHECK (
            jsonb_typeof(registry_summary_json) = 'object'
            AND octet_length(registry_summary_json::text) <= 131072
        ),
    registry_problem_codes_json jsonb NOT NULL
        CHECK (
            jsonb_typeof(registry_problem_codes_json) = 'array'
            AND octet_length(registry_problem_codes_json::text) <= 131072
        ),
    sealed_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO cache.websim_gear_exact_registries (
    registry_revision,
    catalog_revision,
    season_revision,
    gear_rule_revision,
    registry_status,
    registry_summary_json,
    registry_problem_codes_json,
    sealed_at
)
SELECT DISTINCT ON (registry_revision)
    registry_revision,
    catalog_revision,
    season_revision,
    gear_rule_revision,
    registry_status,
    registry_summary_json,
    registry_problem_codes_json,
    sealed_at
FROM cache.websim_gear_exact_instance_template_refs
WHERE registry_status IN ('verified', 'partial')
ORDER BY registry_revision, sealed_at DESC
ON CONFLICT (registry_revision) DO NOTHING;

ALTER TABLE cache.websim_season_manifests
    ADD COLUMN IF NOT EXISTS gear_catalog_revision text;

ALTER TABLE cache.websim_season_manifests
    ADD COLUMN IF NOT EXISTS gear_exact_registry_revision text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'websim_season_manifest_catalog_revision_fk'
          AND conrelid = 'cache.websim_season_manifests'::regclass
    ) THEN
        ALTER TABLE cache.websim_season_manifests
            ADD CONSTRAINT websim_season_manifest_catalog_revision_fk
            FOREIGN KEY (gear_catalog_revision)
            REFERENCES cache.websim_gear_catalog_revisions(catalog_revision)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'websim_season_manifest_exact_registry_revision_fk'
          AND conrelid = 'cache.websim_season_manifests'::regclass
    ) THEN
        ALTER TABLE cache.websim_season_manifests
            ADD CONSTRAINT websim_season_manifest_exact_registry_revision_fk
            FOREIGN KEY (gear_exact_registry_revision)
            REFERENCES cache.websim_gear_exact_registries(registry_revision)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'websim_season_manifest_v2_binding_check'
          AND conrelid = 'cache.websim_season_manifests'::regclass
    ) THEN
        ALTER TABLE cache.websim_season_manifests
            ADD CONSTRAINT websim_season_manifest_v2_binding_check
            CHECK (
                (
                    schema_revision = 'active-season-manifest-v2'
                    AND gear_catalog_revision IS NOT NULL
                    AND gear_exact_registry_revision IS NOT NULL
                )
                OR (
                    schema_revision <> 'active-season-manifest-v2'
                    AND gear_catalog_revision IS NULL
                    AND gear_exact_registry_revision IS NULL
                )
            );
    END IF;
END
$$;

CREATE OR REPLACE FUNCTION cache.reject_websim_gear_exact_registry_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'sealed WebSim exact registry headers are append-only';
END;
$$;

DROP TRIGGER IF EXISTS trg_websim_gear_exact_registries_immutable
ON cache.websim_gear_exact_registries;
CREATE TRIGGER trg_websim_gear_exact_registries_immutable
BEFORE UPDATE OR DELETE ON cache.websim_gear_exact_registries
FOR EACH ROW EXECUTE FUNCTION cache.reject_websim_gear_exact_registry_mutation();

REVOKE UPDATE, DELETE, TRUNCATE ON
    cache.websim_gear_exact_registries
FROM wow_app;

GRANT SELECT, INSERT ON
    cache.websim_gear_exact_registries
TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0022_websim_manifest_v2',
    'Bind immutable Gear Catalog and Exact Registry revisions in active Season Manifest v2'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();
