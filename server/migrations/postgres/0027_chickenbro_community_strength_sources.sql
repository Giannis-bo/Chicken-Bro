-- Immutable Registry v3: append bounded public community-strength sources.
-- Apply this file with psql --single-transaction. The active pointer moves
-- only from the known v2 release on the first recorded application.

INSERT INTO ops.chickenbro_tool_manifests (
    tool_id, version, content_hash, manifest_json, created_at
) VALUES
(
    'source:raiderio-strength:v1',
    '1.0.0',
    'sha256:13165bc8f607d654cbedeeaf64db71582d5e672294052f0ee7267e1924eb63b9',
    $manifest${"contentHash":"sha256:13165bc8f607d654cbedeeaf64db71582d5e672294052f0ee7267e1924eb63b9","costBudget":{"status":"bounded_existing_runtime"},"createdAt":"2026-08-03T00:00:00+00:00","discoveryPolicy":{"evidenceNeeds":["comparative_strength_signal"],"priority":90,"productPhases":["retail"],"regions":["cn","global","us","eu","kr","tw"],"requestKinds":["current_research"],"requiredContextFields":["classKey","specKey","questionType","scenarioKey"],"scenarioKeys":["mythic_plus"]},"evalRefs":["chickenbro-eval:community_strength"],"freshnessPolicy":{"maxAgeSeconds":21600,"requireCheckedAt":true,"staleBehavior":"limitation_only"},"implementationRef":"chickenbro.source.raiderio_strength.v1","inputSchema":{"required":["classKey","specKey","questionType","scenarioKey"]},"kind":"tool","namespace":"source","outputSchema":{"schemaRevision":"chickenbro-tool-result-v1"},"ownerPolicy":"public_source","provenance":{"kind":"repository_migration","revision":"0027"},"purpose":"Load bounded fresh Raider.IO Mythic+ same-role high-key strength evidence.","riskClass":"read_only","sideEffects":[],"sourcePolicy":{"requiredStatuses":["source_reference","partial","failed"],"sourceKey":"raiderio_strength"},"status":"active","timeoutBudgetMs":3000,"toolId":"source:raiderio-strength:v1","version":"1.0.0"}$manifest$::jsonb,
    '2026-08-03T00:00:00+00:00'::timestamptz
),
(
    'source:warcraftlogs-public-rankings:v1',
    '1.0.0',
    'sha256:5759584f99241c7fcc42a7b18aeeaa28446ff24247ddafffc1ec43d4ca9d9bc6',
    $manifest${"contentHash":"sha256:5759584f99241c7fcc42a7b18aeeaa28446ff24247ddafffc1ec43d4ca9d9bc6","costBudget":{"maxPages":1,"maxRequestsPerWindow":12,"status":"bounded_live_public_read","windowSeconds":60},"createdAt":"2026-08-03T00:00:00+00:00","discoveryPolicy":{"evidenceNeeds":["comparative_strength_signal"],"priority":80,"productPhases":["retail"],"regions":["cn","global","us","eu","kr","tw"],"requestKinds":["current_research"],"requiredContextFields":["classKey","specKey","questionType","scenarioKey"],"scenarioKeys":["mythic_plus"]},"evalRefs":["chickenbro-eval:community_strength"],"freshnessPolicy":{"maxAgeSeconds":60,"requireCheckedAt":true,"staleBehavior":"limitation_only"},"implementationRef":"chickenbro.source.warcraftlogs_public_rankings.v1","inputSchema":{"required":["classKey","specKey","questionType","scenarioKey"]},"kind":"tool","namespace":"source","outputSchema":{"schemaRevision":"chickenbro-tool-result-v1"},"ownerPolicy":"public_source","provenance":{"kind":"repository_migration","revision":"0027"},"purpose":"Load one configured current public Warcraft Logs Mythic+ rankings page as supplementary coverage evidence.","riskClass":"read_only","sideEffects":[],"sourcePolicy":{"requiredStatuses":["source_reference","partial","failed"],"sourceKey":"warcraftlogs_public_rankings"},"status":"active","timeoutBudgetMs":10000,"toolId":"source:warcraftlogs-public-rankings:v1","version":"1.0.0"}$manifest$::jsonb,
    '2026-08-03T00:00:00+00:00'::timestamptz
)
ON CONFLICT (tool_id, version) DO NOTHING;

INSERT INTO ops.chickenbro_tool_registry_releases (
    registry_version, manifest_refs_json, release_hash, provenance_json, created_at
) VALUES (
    'chickenbro-tools-3',
    $refs$[{"contentHash":"sha256:9e14fb40e1ee51ba8820cc498fd90d2aa745d3cf9cf1125d878a003996caea25","toolId":"source:raiderio:v1","version":"1.0.0"},{"contentHash":"sha256:c532f1760e75612cdf8396af9eaf0484b0f8da04398fb06499c9689efd3a934c","toolId":"source:warcraftlogs:v1","version":"1.0.0"},{"contentHash":"sha256:10fb83be9bd9a985d5c600028d49049f93d2b035aadef3b89df35d377646f9de","toolId":"source:current-wow-sources:v1","version":"1.0.0"},{"contentHash":"sha256:13165bc8f607d654cbedeeaf64db71582d5e672294052f0ee7267e1924eb63b9","toolId":"source:raiderio-strength:v1","version":"1.0.0"},{"contentHash":"sha256:5759584f99241c7fcc42a7b18aeeaa28446ff24247ddafffc1ec43d4ca9d9bc6","toolId":"source:warcraftlogs-public-rankings:v1","version":"1.0.0"}]$refs$::jsonb,
    'sha256:0270673753652ae031ddf12129eee6179a40b12b8254beef3951b382ceaf43b5',
    '{"kind":"repository_migration","revision":"0027"}'::jsonb,
    '2026-08-03T00:00:00+00:00'::timestamptz
)
ON CONFLICT (registry_version) DO NOTHING;

INSERT INTO ops.chickenbro_tool_registry_release_manifests (
    registry_version, ordinal, tool_id, version, content_hash
) VALUES
('chickenbro-tools-3', 0, 'source:raiderio:v1', '1.0.0', 'sha256:9e14fb40e1ee51ba8820cc498fd90d2aa745d3cf9cf1125d878a003996caea25'),
('chickenbro-tools-3', 1, 'source:warcraftlogs:v1', '1.0.0', 'sha256:c532f1760e75612cdf8396af9eaf0484b0f8da04398fb06499c9689efd3a934c'),
('chickenbro-tools-3', 2, 'source:current-wow-sources:v1', '1.0.0', 'sha256:10fb83be9bd9a985d5c600028d49049f93d2b035aadef3b89df35d377646f9de'),
('chickenbro-tools-3', 3, 'source:raiderio-strength:v1', '1.0.0', 'sha256:13165bc8f607d654cbedeeaf64db71582d5e672294052f0ee7267e1924eb63b9'),
('chickenbro-tools-3', 4, 'source:warcraftlogs-public-rankings:v1', '1.0.0', 'sha256:5759584f99241c7fcc42a7b18aeeaa28446ff24247ddafffc1ec43d4ca9d9bc6')
ON CONFLICT (registry_version, ordinal) DO NOTHING;

WITH first_application AS (
    SELECT NOT EXISTS (
        SELECT 1
        FROM ops.schema_migrations
        WHERE id = '0027_chickenbro_community_strength_sources'
    ) AS pending
)
UPDATE ops.chickenbro_tool_registry_active AS active
SET registry_version = 'chickenbro-tools-3',
    provenance_json = '{"kind":"repository_migration","revision":"0027"}'::jsonb,
    activated_at = '2026-08-03T00:00:00+00:00'::timestamptz
FROM first_application
WHERE active.singleton_id = 1
  AND active.registry_version = 'chickenbro-tools-2'
  AND first_application.pending;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0027_chickenbro_community_strength_sources',
    'Append Chickenbro community Mythic+ strength Registry release'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();
