CREATE TABLE IF NOT EXISTS ops.chickenbro_tool_manifests (
    tool_id text NOT NULL,
    version text NOT NULL,
    content_hash text NOT NULL,
    manifest_json jsonb NOT NULL,
    created_at timestamptz NOT NULL,
    PRIMARY KEY (tool_id, version),
    UNIQUE (tool_id, version, content_hash),
    CHECK (content_hash ~ '^sha256:[0-9a-f]{64}$'),
    CHECK (manifest_json ->> 'toolId' = tool_id),
    CHECK (manifest_json ->> 'version' = version),
    CHECK (manifest_json ->> 'contentHash' = content_hash)
);

CREATE TABLE IF NOT EXISTS ops.chickenbro_tool_registry_releases (
    registry_version text PRIMARY KEY,
    manifest_refs_json jsonb NOT NULL,
    release_hash text NOT NULL UNIQUE,
    provenance_json jsonb NOT NULL,
    created_at timestamptz NOT NULL,
    CHECK (release_hash ~ '^sha256:[0-9a-f]{64}$'),
    CHECK (jsonb_typeof(manifest_refs_json) = 'array'),
    CHECK (jsonb_typeof(provenance_json) = 'object')
);

CREATE TABLE IF NOT EXISTS ops.chickenbro_tool_registry_release_manifests (
    registry_version text NOT NULL REFERENCES ops.chickenbro_tool_registry_releases (registry_version),
    ordinal integer NOT NULL CHECK (ordinal >= 0),
    tool_id text NOT NULL,
    version text NOT NULL,
    content_hash text NOT NULL,
    PRIMARY KEY (registry_version, ordinal),
    UNIQUE (registry_version, tool_id),
    FOREIGN KEY (tool_id, version) REFERENCES ops.chickenbro_tool_manifests (tool_id, version),
    FOREIGN KEY (tool_id, version, content_hash)
        REFERENCES ops.chickenbro_tool_manifests (tool_id, version, content_hash)
);

CREATE TABLE IF NOT EXISTS ops.chickenbro_tool_registry_active (
    singleton_id smallint PRIMARY KEY DEFAULT 1 CHECK (singleton_id = 1),
    registry_version text NOT NULL REFERENCES ops.chickenbro_tool_registry_releases (registry_version),
    provenance_json jsonb NOT NULL,
    activated_at timestamptz NOT NULL,
    CHECK (jsonb_typeof(provenance_json) = 'object')
);

CREATE OR REPLACE FUNCTION ops.reject_chickenbro_tool_registry_immutable_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '% is immutable', TG_TABLE_NAME;
END;
$$;

DROP TRIGGER IF EXISTS chickenbro_tool_manifests_immutable
ON ops.chickenbro_tool_manifests;
CREATE TRIGGER chickenbro_tool_manifests_immutable
BEFORE UPDATE OR DELETE ON ops.chickenbro_tool_manifests
FOR EACH ROW EXECUTE FUNCTION ops.reject_chickenbro_tool_registry_immutable_mutation();

DROP TRIGGER IF EXISTS chickenbro_tool_registry_releases_immutable
ON ops.chickenbro_tool_registry_releases;
CREATE TRIGGER chickenbro_tool_registry_releases_immutable
BEFORE UPDATE OR DELETE ON ops.chickenbro_tool_registry_releases
FOR EACH ROW EXECUTE FUNCTION ops.reject_chickenbro_tool_registry_immutable_mutation();

DROP TRIGGER IF EXISTS chickenbro_tool_registry_release_manifests_immutable
ON ops.chickenbro_tool_registry_release_manifests;
CREATE TRIGGER chickenbro_tool_registry_release_manifests_immutable
BEFORE UPDATE OR DELETE ON ops.chickenbro_tool_registry_release_manifests
FOR EACH ROW EXECUTE FUNCTION ops.reject_chickenbro_tool_registry_immutable_mutation();

INSERT INTO ops.chickenbro_tool_manifests (
    tool_id, version, content_hash, manifest_json, created_at
) VALUES
(
    'source:raiderio:v1',
    '1.0.0',
    'sha256:9e14fb40e1ee51ba8820cc498fd90d2aa745d3cf9cf1125d878a003996caea25',
    $manifest${"contentHash":"sha256:9e14fb40e1ee51ba8820cc498fd90d2aa745d3cf9cf1125d878a003996caea25","costBudget":{"status":"bounded_existing_runtime"},"createdAt":"2026-08-02T00:00:00+00:00","discoveryPolicy":{"priority":100,"productPhases":["retail","ptr"],"regions":["cn","global","us","eu","kr","tw"],"requestKinds":["community_build"],"requiredContextFields":["classKey","specKey"]},"evalRefs":["chickenbro-eval:verified_source_success"],"freshnessPolicy":{"maxAgeSeconds":86400,"staleBehavior":"limitation_only"},"implementationRef":"chickenbro.source.raiderio.v1","inputSchema":{"required":["classKey","specKey"]},"kind":"tool","namespace":"source","outputSchema":{"schemaRevision":"chickenbro-tool-result-v1"},"ownerPolicy":"public_source","provenance":{"kind":"repository_migration","revision":"0025"},"purpose":"Load bounded Raider.IO specialization evidence.","riskClass":"read_only","sideEffects":[],"sourcePolicy":{"requiredStatuses":["synced","partial"],"sourceKey":"raiderio"},"status":"active","timeoutBudgetMs":3000,"toolId":"source:raiderio:v1","version":"1.0.0"}$manifest$::jsonb,
    '2026-08-02T00:00:00+00:00'::timestamptz
),
(
    'source:warcraftlogs:v1',
    '1.0.0',
    'sha256:c532f1760e75612cdf8396af9eaf0484b0f8da04398fb06499c9689efd3a934c',
    $manifest${"contentHash":"sha256:c532f1760e75612cdf8396af9eaf0484b0f8da04398fb06499c9689efd3a934c","costBudget":{"status":"bounded_existing_runtime"},"createdAt":"2026-08-02T00:00:00+00:00","discoveryPolicy":{"priority":100,"productPhases":["retail","ptr"],"regions":["cn","global","us","eu","kr","tw"],"requestKinds":["personal_wcl"],"requiredContextFields":["wclReport"]},"evalRefs":["chickenbro-eval:wcl_verified_report"],"freshnessPolicy":{"maxAgeSeconds":3600,"staleBehavior":"limitation_only"},"implementationRef":"chickenbro.source.warcraftlogs.v1","inputSchema":{"required":["wclReport"]},"kind":"tool","namespace":"source","outputSchema":{"schemaRevision":"chickenbro-tool-result-v1"},"ownerPolicy":"owner_bound_report","provenance":{"kind":"repository_migration","revision":"0025"},"purpose":"Load bounded owner-scoped Warcraft Logs report evidence.","riskClass":"read_only","sideEffects":[],"sourcePolicy":{"requiredStatuses":["verified"],"sourceKey":"warcraftlogs"},"status":"active","timeoutBudgetMs":3000,"toolId":"source:warcraftlogs:v1","version":"1.0.0"}$manifest$::jsonb,
    '2026-08-02T00:00:00+00:00'::timestamptz
)
ON CONFLICT (tool_id, version) DO NOTHING;

INSERT INTO ops.chickenbro_tool_registry_releases (
    registry_version, manifest_refs_json, release_hash, provenance_json, created_at
) VALUES (
    'chickenbro-tools-1',
    $refs$[{"contentHash":"sha256:9e14fb40e1ee51ba8820cc498fd90d2aa745d3cf9cf1125d878a003996caea25","toolId":"source:raiderio:v1","version":"1.0.0"},{"contentHash":"sha256:c532f1760e75612cdf8396af9eaf0484b0f8da04398fb06499c9689efd3a934c","toolId":"source:warcraftlogs:v1","version":"1.0.0"}]$refs$::jsonb,
    'sha256:c9d49f00695540052d69d8aea15653ffb227dbed4ecdb6db1ebd01f734e4734a',
    '{"kind":"repository_migration","revision":"0025"}'::jsonb,
    '2026-08-02T00:00:00+00:00'::timestamptz
)
ON CONFLICT (registry_version) DO NOTHING;

INSERT INTO ops.chickenbro_tool_registry_release_manifests (
    registry_version, ordinal, tool_id, version, content_hash
) VALUES
(
    'chickenbro-tools-1', 0, 'source:raiderio:v1', '1.0.0',
    'sha256:9e14fb40e1ee51ba8820cc498fd90d2aa745d3cf9cf1125d878a003996caea25'
),
(
    'chickenbro-tools-1', 1, 'source:warcraftlogs:v1', '1.0.0',
    'sha256:c532f1760e75612cdf8396af9eaf0484b0f8da04398fb06499c9689efd3a934c'
)
ON CONFLICT (registry_version, ordinal) DO NOTHING;

INSERT INTO ops.chickenbro_tool_registry_active (
    singleton_id, registry_version, provenance_json, activated_at
) VALUES (
    1,
    'chickenbro-tools-1',
    '{"kind":"repository_migration","revision":"0025"}'::jsonb,
    '2026-08-02T00:00:00+00:00'::timestamptz
)
ON CONFLICT (singleton_id) DO UPDATE
SET registry_version = EXCLUDED.registry_version,
    provenance_json = EXCLUDED.provenance_json,
    activated_at = EXCLUDED.activated_at;

REVOKE INSERT, UPDATE, DELETE ON ops.chickenbro_tool_manifests FROM wow_app;
GRANT SELECT ON ops.chickenbro_tool_manifests TO wow_app;
REVOKE INSERT, UPDATE, DELETE ON ops.chickenbro_tool_registry_releases FROM wow_app;
GRANT SELECT ON ops.chickenbro_tool_registry_releases TO wow_app;
REVOKE INSERT, UPDATE, DELETE ON ops.chickenbro_tool_registry_release_manifests FROM wow_app;
GRANT SELECT ON ops.chickenbro_tool_registry_release_manifests TO wow_app;
REVOKE INSERT, UPDATE, DELETE ON ops.chickenbro_tool_registry_active FROM wow_app;
GRANT SELECT ON ops.chickenbro_tool_registry_active TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0025_chickenbro_tool_registry',
    'Add immutable Chickenbro Tool Registry releases with a read-only active pointer'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();
