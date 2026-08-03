-- Immutable Registry v2: add the bounded official-current-source capability.
-- Apply this file with psql --single-transaction.  The active pointer moves
-- only on the first recorded application from the known v1 release.

INSERT INTO ops.chickenbro_tool_manifests (
    tool_id, version, content_hash, manifest_json, created_at
) VALUES (
    'source:current-wow-sources:v1',
    '1.0.0',
    'sha256:10fb83be9bd9a985d5c600028d49049f93d2b035aadef3b89df35d377646f9de',
    $manifest${"contentHash":"sha256:10fb83be9bd9a985d5c600028d49049f93d2b035aadef3b89df35d377646f9de","costBudget":{"maxArticlesPerSource":1,"status":"bounded_live_official_read"},"createdAt":"2026-08-03T00:00:00+00:00","discoveryPolicy":{"evidenceNeeds":["official_current_changes"],"priority":100,"productPhases":["retail","ptr"],"regions":["cn","global","us","eu","kr","tw"],"requestKinds":["current_research"],"requiredContextFields":["classKey","specKey","questionType","patchVersion"]},"evalRefs":["chickenbro-eval:current_official_source"],"freshnessPolicy":{"maxAgeSeconds":900,"staleBehavior":"failed"},"implementationRef":"chickenbro.source.current_wow_sources.v1","inputSchema":{"required":["classKey","specKey","questionType","patchVersion"]},"kind":"tool","namespace":"source","outputSchema":{"schemaRevision":"chickenbro-tool-result-v1"},"ownerPolicy":"public_source","provenance":{"kind":"repository_migration","revision":"0026"},"purpose":"Load bounded official current Warcraft facts for a resolved question frame.","riskClass":"read_only","sideEffects":[],"sourcePolicy":{"approvedSourceIds":["blizzard","blizzard-forums"],"requiredStatuses":["source_reference","partial","failed"],"sourceKey":"current_wow_sources"},"status":"active","timeoutBudgetMs":10000,"toolId":"source:current-wow-sources:v1","version":"1.0.0"}$manifest$::jsonb,
    '2026-08-03T00:00:00+00:00'::timestamptz
)
ON CONFLICT (tool_id, version) DO NOTHING;

INSERT INTO ops.chickenbro_tool_registry_releases (
    registry_version, manifest_refs_json, release_hash, provenance_json, created_at
) VALUES (
    'chickenbro-tools-2',
    $refs$[{"contentHash":"sha256:9e14fb40e1ee51ba8820cc498fd90d2aa745d3cf9cf1125d878a003996caea25","toolId":"source:raiderio:v1","version":"1.0.0"},{"contentHash":"sha256:c532f1760e75612cdf8396af9eaf0484b0f8da04398fb06499c9689efd3a934c","toolId":"source:warcraftlogs:v1","version":"1.0.0"},{"contentHash":"sha256:10fb83be9bd9a985d5c600028d49049f93d2b035aadef3b89df35d377646f9de","toolId":"source:current-wow-sources:v1","version":"1.0.0"}]$refs$::jsonb,
    'sha256:a25340f6fe51dfa01d956b7d944891de39771694e4fd3b33fb41b4fba2d9a102',
    '{"kind":"repository_migration","revision":"0026"}'::jsonb,
    '2026-08-03T00:00:00+00:00'::timestamptz
)
ON CONFLICT (registry_version) DO NOTHING;

INSERT INTO ops.chickenbro_tool_registry_release_manifests (
    registry_version, ordinal, tool_id, version, content_hash
) VALUES
(
    'chickenbro-tools-2', 0, 'source:raiderio:v1', '1.0.0',
    'sha256:9e14fb40e1ee51ba8820cc498fd90d2aa745d3cf9cf1125d878a003996caea25'
),
(
    'chickenbro-tools-2', 1, 'source:warcraftlogs:v1', '1.0.0',
    'sha256:c532f1760e75612cdf8396af9eaf0484b0f8da04398fb06499c9689efd3a934c'
),
(
    'chickenbro-tools-2', 2, 'source:current-wow-sources:v1', '1.0.0',
    'sha256:10fb83be9bd9a985d5c600028d49049f93d2b035aadef3b89df35d377646f9de'
)
ON CONFLICT (registry_version, ordinal) DO NOTHING;

INSERT INTO ops.chickenbro_tool_registry_active (
    singleton_id, registry_version, provenance_json, activated_at
) VALUES (
    1,
    'chickenbro-tools-2',
    '{"kind":"repository_migration","revision":"0026"}'::jsonb,
    '2026-08-03T00:00:00+00:00'::timestamptz
)
ON CONFLICT (singleton_id) DO NOTHING;

WITH first_application AS (
    SELECT NOT EXISTS (
        SELECT 1
        FROM ops.schema_migrations
        WHERE id = '0026_chickenbro_smart_question_chain'
    ) AS pending
)
UPDATE ops.chickenbro_tool_registry_active AS active
SET registry_version = 'chickenbro-tools-2',
    provenance_json = '{"kind":"repository_migration","revision":"0026"}'::jsonb,
    activated_at = '2026-08-03T00:00:00+00:00'::timestamptz
FROM first_application
WHERE active.singleton_id = 1
  AND active.registry_version = 'chickenbro-tools-1'
  AND first_application.pending;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0026_chickenbro_smart_question_chain',
    'Append Chickenbro Smart Question Chain official current-source Registry release'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();
