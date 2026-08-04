-- Immutable Registry v4: append one provider-neutral public-web research Tool.
-- This migration intentionally does not move the shared active pointer. A
-- candidate may pin v4 by WOW_CHICKENBRO_TOOL_REGISTRY_VERSION while production
-- keeps the known v3 release until explicit promotion.

INSERT INTO ops.chickenbro_tool_manifests (
    tool_id, version, content_hash, manifest_json, created_at
) VALUES (
    'source:public-web-research:v1',
    '1.0.0',
    'sha256:6038088ff5b1e948c379c7e33025fe1b39b2de6a142a4f524d4b550a74057c2c',
    $manifest${"contentHash":"sha256:6038088ff5b1e948c379c7e33025fe1b39b2de6a142a4f524d4b550a74057c2c","costBudget":{"maxPages":2,"maxRequestsPerWindow":8,"status":"bounded_live_public_web_read","windowSeconds":60},"createdAt":"2026-08-04T00:00:00+00:00","discoveryPolicy":{"priority":70,"productPhases":["retail","ptr"],"regions":["cn","global","us","eu","kr","tw"],"requestKinds":["current_research"],"requiredContextFields":["questionType"]},"evalRefs":["chickenbro-eval:generic_public_web_research"],"freshnessPolicy":{"maxAgeSeconds":120,"requireCheckedAt":true,"staleBehavior":"limitation_only"},"implementationRef":"chickenbro.source.public_web_research.v1","inputSchema":{"required":["target"]},"kind":"tool","namespace":"source","outputSchema":{"schemaRevision":"chickenbro-tool-result-v1"},"ownerPolicy":"public_source","provenance":{"kind":"repository_migration","revision":"0028"},"purpose":"Search a bounded public-web research query or read one Codex-selected safe HTTPS public page.","riskClass":"read_only","sideEffects":[],"sourcePolicy":{"requiredStatuses":["source_reference","partial","failed"],"sourceKey":"public_web_research"},"status":"active","timeoutBudgetMs":15000,"toolId":"source:public-web-research:v1","version":"1.0.0"}$manifest$::jsonb,
    '2026-08-04T00:00:00+00:00'::timestamptz
)
ON CONFLICT (tool_id, version) DO NOTHING;

INSERT INTO ops.chickenbro_tool_registry_releases (
    registry_version, manifest_refs_json, release_hash, provenance_json, created_at
) VALUES (
    'chickenbro-tools-4',
    $refs$[{"contentHash":"sha256:9e14fb40e1ee51ba8820cc498fd90d2aa745d3cf9cf1125d878a003996caea25","toolId":"source:raiderio:v1","version":"1.0.0"},{"contentHash":"sha256:c532f1760e75612cdf8396af9eaf0484b0f8da04398fb06499c9689efd3a934c","toolId":"source:warcraftlogs:v1","version":"1.0.0"},{"contentHash":"sha256:10fb83be9bd9a985d5c600028d49049f93d2b035aadef3b89df35d377646f9de","toolId":"source:current-wow-sources:v1","version":"1.0.0"},{"contentHash":"sha256:13165bc8f607d654cbedeeaf64db71582d5e672294052f0ee7267e1924eb63b9","toolId":"source:raiderio-strength:v1","version":"1.0.0"},{"contentHash":"sha256:5759584f99241c7fcc42a7b18aeeaa28446ff24247ddafffc1ec43d4ca9d9bc6","toolId":"source:warcraftlogs-public-rankings:v1","version":"1.0.0"},{"contentHash":"sha256:6038088ff5b1e948c379c7e33025fe1b39b2de6a142a4f524d4b550a74057c2c","toolId":"source:public-web-research:v1","version":"1.0.0"}]$refs$::jsonb,
    'sha256:0f0922c323a4e6c5ae74e5199f1cd0e77baf8218469062e5c865eeae4e72c742',
    '{"kind":"repository_migration","revision":"0028"}'::jsonb,
    '2026-08-04T00:00:00+00:00'::timestamptz
)
ON CONFLICT (registry_version) DO NOTHING;

INSERT INTO ops.chickenbro_tool_registry_release_manifests (
    registry_version, ordinal, tool_id, version, content_hash
) VALUES
('chickenbro-tools-4', 0, 'source:raiderio:v1', '1.0.0', 'sha256:9e14fb40e1ee51ba8820cc498fd90d2aa745d3cf9cf1125d878a003996caea25'),
('chickenbro-tools-4', 1, 'source:warcraftlogs:v1', '1.0.0', 'sha256:c532f1760e75612cdf8396af9eaf0484b0f8da04398fb06499c9689efd3a934c'),
('chickenbro-tools-4', 2, 'source:current-wow-sources:v1', '1.0.0', 'sha256:10fb83be9bd9a985d5c600028d49049f93d2b035aadef3b89df35d377646f9de'),
('chickenbro-tools-4', 3, 'source:raiderio-strength:v1', '1.0.0', 'sha256:13165bc8f607d654cbedeeaf64db71582d5e672294052f0ee7267e1924eb63b9'),
('chickenbro-tools-4', 4, 'source:warcraftlogs-public-rankings:v1', '1.0.0', 'sha256:5759584f99241c7fcc42a7b18aeeaa28446ff24247ddafffc1ec43d4ca9d9bc6'),
('chickenbro-tools-4', 5, 'source:public-web-research:v1', '1.0.0', 'sha256:6038088ff5b1e948c379c7e33025fe1b39b2de6a142a4f524d4b550a74057c2c')
ON CONFLICT (registry_version, ordinal) DO NOTHING;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0028_chickenbro_generic_public_web_research',
    'Append Chickenbro generic public-web research Registry release without active promotion'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();
