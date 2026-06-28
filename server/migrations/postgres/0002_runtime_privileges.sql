GRANT USAGE ON SCHEMA identity, app, content, cache, knowledge, analytics, ops TO wow_app;

GRANT SELECT, INSERT, UPDATE, DELETE
ON ALL TABLES IN SCHEMA identity, app, content, cache, knowledge, analytics, ops
TO wow_app;

GRANT USAGE, SELECT, UPDATE
ON ALL SEQUENCES IN SCHEMA identity, app, content, cache, knowledge, analytics, ops
TO wow_app;

ALTER DEFAULT PRIVILEGES FOR ROLE wow_migrator IN SCHEMA identity
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO wow_app;

ALTER DEFAULT PRIVILEGES FOR ROLE wow_migrator IN SCHEMA app
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO wow_app;

ALTER DEFAULT PRIVILEGES FOR ROLE wow_migrator IN SCHEMA content
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO wow_app;

ALTER DEFAULT PRIVILEGES FOR ROLE wow_migrator IN SCHEMA cache
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO wow_app;

ALTER DEFAULT PRIVILEGES FOR ROLE wow_migrator IN SCHEMA knowledge
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO wow_app;

ALTER DEFAULT PRIVILEGES FOR ROLE wow_migrator IN SCHEMA analytics
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO wow_app;

ALTER DEFAULT PRIVILEGES FOR ROLE wow_migrator IN SCHEMA ops
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES ('0002_runtime_privileges', 'Grant PostgreSQL runtime privileges to wow_app')
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();
