CREATE TABLE IF NOT EXISTS poe2.character_imports (
 id uuid PRIMARY KEY,
 user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
 provider text NOT NULL CHECK (provider IN ('ninja','wegame')),
 canonical_url text NOT NULL,
 status text NOT NULL CHECK (status IN ('queued','fetching','mapping','validating','ready','needs_input','blocked','failed','cancelled')),
 stage text NOT NULL DEFAULT 'created',
 preview jsonb,
 issues jsonb NOT NULL DEFAULT '[]',
 next_action text,
 source_xml text,
 source_relation text CHECK (source_relation IN ('user_supplied','collected')),
 snapshot jsonb,
 expires_at timestamptz NOT NULL DEFAULT now()+interval '7 days',
 attempt integer NOT NULL DEFAULT 0 CHECK (attempt >= 0),
 infrastructure_failures integer NOT NULL DEFAULT 0 CHECK (infrastructure_failures BETWEEN 0 AND 3),
 lease_owner text,
 lease_expires_at timestamptz,
 build_id uuid REFERENCES poe2.builds(id),
 baseline_job_id uuid REFERENCES poe2.jobs(id),
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 CHECK (status <> 'ready' OR (build_id IS NOT NULL AND baseline_job_id IS NOT NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS poe2_import_owner_active ON poe2.character_imports(user_id)
 WHERE status IN ('queued','fetching','mapping','validating');
CREATE INDEX IF NOT EXISTS poe2_import_claim ON poe2.character_imports(status,lease_expires_at);
CREATE TABLE IF NOT EXISTS poe2.character_import_actions (
 user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
 action_key text NOT NULL CHECK (length(action_key) BETWEEN 1 AND 128),
 request_hash text NOT NULL,
 import_id uuid NOT NULL REFERENCES poe2.character_imports(id) ON DELETE CASCADE,
 PRIMARY KEY(user_id,action_key)
);
GRANT SELECT,INSERT,UPDATE ON poe2.character_imports TO wow_app;
GRANT SELECT,INSERT ON poe2.character_import_actions TO wow_app;
