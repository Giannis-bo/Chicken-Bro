# PostgreSQL Runtime and Migration Runbook

## Current Contract

Production and test runtime use `WOW_DATABASE_RUNTIME=postgres_only`. Identity, personal assets, SimC tasks, Chickenbro, analytics, news, WebSim/cache, health and admin gates must resolve through PostgreSQL stores.

SQLite is permitted only as an explicit offline migration source, audit input or backup artifact. Missing PostgreSQL data or store wiring is a blocker; it never authorizes runtime fallback.

The schema contract lives under `server/migrations/postgres/`. Runtime boundaries are documented in [database-architecture.md](database-architecture.md).

## Safety Rules

- Follow the cloud and network approval rules in `AGENTS.md`.
- Identify the exact source and target database before every migration.
- Back up the PostgreSQL target before schema or data writes.
- Copy a SQLite migration source before reading it; never operate on the only copy.
- Keep secrets in server environment or `PGPASSFILE`, not commands, logs, docs or screenshots.
- Run schema/data work in a transaction where supported.
- Stop on count, checksum, owner or foreign-key mismatch.
- Never migrate guest assets into an authenticated owner by inference.
- Do not migrate auth tokens; require re-login when identity data moves.
- A failed cutover rolls back to the previous PostgreSQL state, not to SQLite runtime.

## Schema Setup

For a disposable local or explicitly selected target:

```bash
createdb wow_pg_local
for file in server/migrations/postgres/*.sql; do
  psql wow_pg_local -v ON_ERROR_STOP=1 -f "$file"
done
```

Verify applied migrations, schemas, extensions, privileges and runtime role access before data copy.

Optional integration tests require an explicit DSN:

```bash
WOW_PG_TEST_DSN='postgresql://wow_migrator@localhost/wow_pg_local' \
  python3 -m unittest tests.postgres_integration_test
```

Without a test DSN the integration suite may skip; a skip is not production evidence.

## Exact-first Production Foundation

The deployed Exact-first foundation is recorded in [the 2026-08-10 release evidence](../artifacts/releases/2026-08-10-equipment-simulator-exact-first-production-foundation-deployment/evidence.json): a validated backup preceded one `0030`--`0035` PostgreSQL transaction, and the expected runtime files were verified. This is `runtime_verified` infrastructure evidence, not a player-visible Exact completion claim.

- `0030_websim_exact_authority_bundle.sql` through `0035_websim_exact_runtime_authority_release.sql` are append-only schema contracts. Their identities, authority bundle bytes and release references must not be rewritten to repair a later source gap.
- The deployed provider and exact worker remain disabled, and aggregate eligible sources are zero. The ready path is literally `blocked`; no job, Active Manifest pointer, Catalog membership or user-facing readiness may be inferred from the foundation.
- A future source admission or activation requires a new task-scoped contract with an immutable source/member/variant/track/set identity, candidate evidence, a reviewed rollback point, and real WeChat acceptance. It is not authorized by this runbook.
- Historical candidate attempts belong in their release packets and Git history. Do not restore an old candidate diary as a current deployment procedure.

## Exact Worker Role and Dormant Candidate Boundary

`0032_websim_exact_import_jobs.sql` defines a future worker-owned queue boundary. It does not authorize a production migration, service activation, API/UI producer, SimC consumer, or data release. The service stays dormant until an explicitly authorized runtime task proves its complete source and ownership chain.

An authorized PostgreSQL operator, outside application migrations, establishes the group and a dedicated login member. The group remains `NOLOGIN`; the member is `LOGIN INHERIT` and has no role-management or superuser powers:

```sql
CREATE ROLE wow_exact_worker NOLOGIN NOCREATEROLE NOSUPERUSER NOREPLICATION;
CREATE ROLE wow_exact_worker_login LOGIN INHERIT NOCREATEROLE NOSUPERUSER NOREPLICATION;
GRANT wow_exact_worker TO wow_exact_worker_login;
```

This is an operator procedure, not migration content. Do not put credentials in the repository, command history, report or attestation. The worker file is root-readable `/etc/wow-exact-worker.env` with mode `0600` and only worker-owned values:

```ini
WOW_EXACT_WORKER_DATABASE_URL=postgresql://<login>:<redacted>@<host>/<database>
WOW_EXACT_WORKER_SIMC_RUNTIME_REVISION=<approved-runtime-revision>
WOW_EXACT_WORKER_ID=<bounded-worker-id>
```

It must not contain `WOW_DATABASE_URL`, and `server/wow-gear-exact-authority-worker.service` must not read the public app environment. Every worker connection executes `SET ROLE wow_exact_worker`, then checks that the session login is a member and `current_user` is exactly `wow_exact_worker`.

The deploy script may only perform its dormant install/preflight when an operator explicitly supplies `WOW_DEPLOY_EXACT_WORKER_PREFLIGHT=1`. It must validate the role boundary, file mode and distinct app/worker DSNs using redacted fingerprints; it must not enable, start or restart the worker.

For a separately approved, cloud-only disposable candidate, keep all DSNs in the operator environment and provide new, empty, run-id-bound databases. The migrator, app and worker identities must be distinct. The intended test shape is:

```bash
WOW_PG_TEST_RUN_ID_0032='<new-run-id>' \
WOW_PG_TEST_DSN_FRESH_0032='<fresh-operator-dsn>' \
WOW_PG_TEST_DSN_UPGRADE_0032='<upgrade-operator-dsn>' \
WOW_PG_TEST_DSN_MIGRATOR_0032='<fresh-wow_migrator-login-dsn>' \
WOW_PG_TEST_DSN_APP_0032='<fresh-wow_app-login-dsn>' \
WOW_PG_TEST_DSN_WORKER_0032='<fresh-dedicated-worker-login-dsn>' \
python3 -m unittest \
  tests.postgres_integration_test.PostgresExactImportJobsCandidateTest
```

Missing `psql`, a DSN or a complete source bundle is `candidate_pending`/`blocked`, never green evidence. If a future authorized candidate or activation fails, roll back its transaction or discard only the named disposable candidate databases; preserve logs and restore the reviewed service/environment and PostgreSQL backup. Never fall back to the public app DSN or SQLite runtime.

## SQLite Source Inventory

Use only for an approved one-shot migration or audit:

```bash
python3 server/migrations/postgres/identity_shadow_plan.py /path/to/copied-source.sqlite3
python3 server/migrations/postgres/data_copy_plan.py /path/to/copied-source.sqlite3
```

Review at minimum:

- formal users and stable identity mapping;
- guest users and guest-owned assets excluded from authenticated migration;
- owner references for templates, tasks and Chickenbro data;
- public content/cache row counts and natural keys;
- skipped auth tokens;
- source and target table counts.

The plan output is review evidence, not permission to write production data.

## Guarded Data Copy

Before execution:

1. Record target DSN identity without exposing credentials.
2. Record PostgreSQL backup path and source-copy path.
3. Apply all required migrations.
4. Run the dry-run plan and review counts, conflicts and excluded rows.
5. Confirm target is not serving live traffic, or use the repository's approved guarded procedure.

Execute the repository migration tool only against the reviewed target. Production-like targets must require an explicit production flag and must still preserve transaction, idempotency and count verification.

After execution verify:

- target counts match the approved plan;
- all owner foreign keys resolve;
- natural-key conflicts follow the documented policy;
- sequences and generated IDs are correct;
- no guest ownership or token data leaked;
- migration audit state records source fingerprint, target, run and result.

## Runtime Cutover

1. Back up the current service environment and PostgreSQL target.
2. Confirm `WOW_DATABASE_RUNTIME=postgres_only` and the intended `WOW_DATABASE_URL`/`PGPASSFILE`.
3. Ensure SQLite runtime variables and fallback flags are absent from the service environment.
4. Restart the existing service.
5. Inspect startup logs for store initialization, migration and permission errors.
6. Run the verification ladder below.
7. Keep the previous PostgreSQL backup and environment file until the observation window closes.

Changing to another PostgreSQL database is a database cutover even when the code is unchanged.

## Verification Ladder

```bash
python3 -m unittest tests.database_adapter_test
python3 -m unittest tests.postgres_schema_test
python3 -m unittest tests.postgres_personal_store_test
python3 -m unittest tests.postgres_analytics_store_test
python3 -m unittest tests.postgres_content_store_test
python3 -m unittest tests.postgres_cache_store_test
python3 -m unittest tests.postgres_identity_shadow_plan_test
python3 -m unittest tests.postgres_shadow_migration_test
python3 -m unittest tests.news_backend_test
python3 -m unittest tests.websim_payload_test
git diff --check
```

Remote smoke:

```bash
curl -fsS "$BASE_URL/health"
curl -fsS "$BASE_URL/api/data/health"
curl -fsS "$BASE_URL/api/news/home"
curl -fsS "$BASE_URL/api/websim/bootstrap"
curl -fsS "$BASE_URL/api/websim/gear?class=mage&spec=frost&compact=1"
curl -fsS "$BASE_URL/api/websim/talents?class=mage&spec=frost"
```

Also verify one authenticated owner flow for personal templates, one SimC task flow and one Chickenbro persistence flow. HTTP 200 alone does not prove owner isolation or PostgreSQL-only behavior.

## Rollback

### Schema or data migration failure before cutover

Rollback the transaction or discard the target database, fix the migration, and rerun from a fresh source copy. Do not partially promote the target.

### Runtime failure after cutover

1. Stop writes and the affected service.
2. Preserve logs and back up the failed PostgreSQL state.
3. Restore the previous PostgreSQL backup and service environment.
4. Restart and rerun owner, health, news, WebSim and task smoke.

Do not unset PostgreSQL runtime to reopen SQLite fallback.

### Count or owner mismatch discovered later

Quarantine affected rows, identify the migration run and restore or repair from the recorded PostgreSQL backup. Add a regression test before retrying.

## Completion Checklist

- [ ] Exact source and target identified.
- [ ] PostgreSQL target and migration source copied/backed up.
- [ ] Schema and privileges verified.
- [ ] Dry-run counts and exclusions reviewed.
- [ ] Transactional copy completed with count and owner verification.
- [ ] Runtime environment contains no SQLite fallback.
- [ ] Unit/integration tests and remote smoke passed.
- [ ] Authenticated owner, task and Chickenbro flows passed.
- [ ] Rollback material retained for the observation window.
