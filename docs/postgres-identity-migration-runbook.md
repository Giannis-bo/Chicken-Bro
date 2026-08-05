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

## Exact Authority Bundle Task 3A Candidates

Migration `0026_websim_exact_authority_bundle.sql` is not production-authorized
by local unit or schema tests. Two Task 3A candidates failed before `0026`:
`t3a2608050955` at `f90a302040f722fec0807bd600f8e2242169801c` because `0001`
already creates the `(user_id, template_type, config_hash)` unique constraint and
`0003` unconditionally attempted to add the named target constraint, then
`t3a260805111623` because `0003` compared PostgreSQL `name[]` catalog attributes
with a `text[]` literal. Task 3A is literal `candidate_failed /
migration_chain_blocked` until the authorized fail-closed `0003`
semantic-idempotence/type correction is committed and one final, clean
runtime-affecting head passes two newly provisioned independently empty operator
databases. Failed runs `t3a2608050955` and `t3a260805111623` and their four
failed databases are evidence only: never reset or reuse them. The test suite never creates, drops,
resets or reuses any candidate database.

Choose one lowercase run id matching `[a-z0-9]{8,32}`. An operator with explicit
authority provisions two distinct empty databases and exact database comments:

- `wow_exact_first_fresh_test_<run-id>` with comment
  `wow_exact_first_disposable:<run-id>:fresh`;
- `wow_exact_first_upgrade_test_<run-id>` with comment
  `wow_exact_first_disposable:<run-id>:upgrade`.

The cluster must already contain the repository's `wow_migrator` and `wow_app`
roles. Historical migration `0009_runtime_reconcile_privileges.sql` executes
`ALTER DEFAULT PRIVILEGES FOR ROLE postgres`; therefore each explicit candidate
DSN must use an existing operator/migrator identity that already has the
authority required by migrations `0001..0025` (commonly `postgres`, or an
existing operator that can `SET ROLE postgres`). The suite does not create,
alter or grant roles, and it does not change any historical migration. Do not
add a non-superuser role gate that would contradict the frozen migration chain.

The safety boundary is instead exact and machine-checked: the two explicit DSNs
must resolve to the exact run-id-bound names/comments above; both databases must
have no project schema, table or ledger before the first write; the suite never
creates, drops, resets or reuses a database; and migrations `0001..0026` contain
no `CREATE DATABASE`, `DROP DATABASE` or `ALTER DATABASE`. Every migration DDL
statement is therefore scoped to the current DSN database. No additional DSN or
implicit admin connection is accepted.

After the Task 3A code, tests and `0026` are committed and the tree is clean, run:

```bash
WOW_PG_TEST_RUN_ID_0026='<run-id>' \
WOW_PG_TEST_DSN_FRESH_0026='<fresh-disposable-dsn>' \
WOW_PG_TEST_DSN_UPGRADE_0026='<upgrade-disposable-dsn>' \
python3 -m unittest \
  tests.postgres_integration_test.PostgresExactAuthorityCandidateTest
```

The fresh path applies `0001..0026`; it must end with exactly one
`app.build_templates` target constraint named
`build_templates_user_id_template_type_config_hash_key`, type `u`, with ordered
columns `user_id, template_type, config_hash`, no legacy
`build_templates_user_id_template_type_name_key` constraint, and exactly one
`0003_build_template_config_hash_unique` ledger row. The upgrade path independently applies
`0001..0025`, inserts a frozen v1 row, snapshots its complete row including
`sealed_at` plus all existing project schemas, tables, columns, constraints,
indexes, triggers, default ACLs and effective `wow_app` grants, applies `0026`,
and requires every pre-existing value to remain equal. Both paths verify the
exact six-kind/schema/prefix closed matrix, database-computed SHA-256/JSON
projection, all seven foreign keys, complete binding predicates, all three
tables' UPDATE/DELETE/TRUNCATE immutability, explicit and effective `wow_app`
SELECT-only ACLs, whole-bundle typed reload and duplicate record order. The
concurrency smoke starts from absent authority rows and concurrently writes two
legal bundles that share two effect records in reverse order; both must finish
without deadlock and independently read back.

After each normal migration path has installed the correct target, the candidate
suite executes real `0003` in a rollback-only transaction and proves that the
target constraint OID is unchanged. In separate rollback-only transactions it
replaces that target with a same-name wrong-type constraint and a same-name
wrong-ordered unique constraint; real `0003` must fail through `psycopg`, then
the rollback must restore the original correct state. These are candidate
semantics, not parser or mock checks.

After every assertion passes, the test rechecks the clean commit, Git tree,
`0026` SHA-256 and both database names/comments, then emits exactly one compact
JSON attestation as its final stdout line. Archive that single line verbatim for
the later Task 3A `evidence.json`/`manifest.json` promotion review; it contains
the run id, both database identities, commit/tree/migration hashes,
`passed=true`, and the exact verified-check list, but no DSN or credential.
Local/skipped runs emit no successful attestation and must not create or update
either evidence file.

Leave both exact databases intact through evidence/manifest archival and scoped
review. After candidate execution, any change to code, tests, migration,
requirement or owner contracts invalidates both candidates. Only an operator may
discard the two exact database identities after archival; the suite never does.
Missing `psql`, either DSN, or the run id is a skipped candidate and remains
`candidate_pending`, never green evidence. Before the authorized correction
passes a new pair, the current status remains `candidate_failed /
migration_chain_blocked`, never `candidate_pending` or green evidence.

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
