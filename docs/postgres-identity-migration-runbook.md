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

Migration `0030_websim_exact_authority_bundle.sql` is not production-authorized
by local unit, schema or candidate tests. Two Task 3A candidates failed before the former `0026` authority migration:
`t3a2608050955` at `f90a302040f722fec0807bd600f8e2242169801c` because `0001`
already creates the `(user_id, template_type, config_hash)` unique constraint and
`0003` unconditionally attempted to add the named target constraint, then
`t3a260805111623` because `0003` compared PostgreSQL `name[]` catalog attributes
with a `text[]` literal. A third run, `t3a260805113656`, passed both runtime
paths at commit `0e0743ca188efbd7cb818bfb8a210fd998379f4d` / tree
`3fce81f57dbdc851a9438ae63ea051f666bf1051`, but its active requirement status
was `local_verified`. Harness permits evidence promotion only when the
requirement is `implementation_allowed`; correcting that requirement and its
owner contracts after execution also invalidates this candidate under the
post-candidate mutation boundary. These three runs retain the literal historical
state `candidate_rerun_required / evidence_promotion_blocked` and are never green
Task 3A evidence.

The fourth run `t3a260805120026` genuinely passed both fresh and upgrade paths from clean
commit `9ffd57b05ab97be880daf65425d6de9e26609e32` / tree
`4f4a857ed52d65e04ab6bccfc5b3ac4649c3d94e` while the active requirement was
`implementation_allowed`. Its single-line attestation binds both exact database
identities and migration `0026` SHA-256
`ddbe31fc26c8ad1aafa68bc7608f083e8415e5b4353cd5145450e2791303eb8a` to 14
verified checks. The read-only post-audit independently confirmed 26 ledger rows,
one `0003`, one `0026`, one exact target constraint, expected authority counts and
SELECT-only `wow_app` privileges in both databases. That remains immutable historical evidence.
However, origin/main subsequently occupied migration ids `0026..0029`, so safe integration
must move Task 3A to `0030`, changing its path, ledger identity, SHA and full migration chain.
The fourth run is therefore `runtime_passed_superseded_by_main_integration`, not current
0030 evidence. origin/main integration and the 0030 local verification matrix passed at
merge commit `1619815c`.

The fifth run `t3a260805125812` genuinely passed fresh `0001..0030` and upgrade
`0001..0029` plus frozen-v1 seed/snapshot plus `0030` from exact clean commit
`a4c0fd04b39577838ad4fb7a0e3c54b8e0205c30` / tree
`aa0908eb8214d9572fc604e3399321c5d6eb3754`. Its single-line
`task3a-candidate-attestation-v2` binds both exact database identities and migration
`0030` SHA-256 `41e12fd5b12cac79ed57dde266e4b515b0b731dfcc9c9874d818ddc306f957c3`
to 14 verified checks. The read-only post-audit confirmed 30 ledger rows, one
`0003`, one `0030`, the exact target constraint, expected authority counts and
SELECT-only `wow_app` privileges in both databases. That candidate object and its
single-line attestation-v2 remain immutable historical evidence. GitHub PR #114
full-profile run `30977816268`, job `92215539827`, then failed
`GearRuntimeTest.test_runtime_imports_from_server_directory_for_direct_backend_startup`
and `PgGearAuthorityLoaderTest.test_loader_imports_in_direct_server_runtime_mode`:
its source used only `server.gear_contracts` while direct startup runs from `server/`.
The Node deprecation warning was not the cause. The compatibility correction is
candidate-invalidating, so the fifth run remains
`runtime_passed_invalidated_by_direct_runtime_import_regression`.

The sixth run `t3a260805142130` then genuinely passed fresh `0001..0030` and
upgrade `0001..0029` plus frozen-v1 seed/snapshot plus `0030` from exact frozen
commit `9f67ec2f72f59dc1def7b035fc4d9da27b8802b5` / tree
`c2a686e6ed8f7a9ff15c82f4e45996636c49d9a7`. Its raw single-line
attestation-v2, parsed 14 checks, bundle/log hashes and independent read-only
post-audit are immutable historical PASS evidence. The same frozen HEAD failed
the current-truth owner test because it hard-coded
`evidence.status == implementation_allowed` after the authorized local promotion
had set `local_verified`; the schema current-truth test passed. PostgreSQL was not
the cause. Correcting the lifecycle test, requirement and owner contracts is
candidate-invalidating, so the sixth status is exactly
`runtime_passed_unpromotable_evidence_lifecycle_test_regression`.
The exact full local profile subsequently passed at clean HEAD
`7a4390c9794dd46b5e95aa142409bfcc6952bf74` / tree
`606a17509aa5294cc1de8ceb129f0046bc2cd5a9`, allowing a seventh candidate.

The seventh run `t3a260805160003` genuinely passed fresh `0001..0030` and
upgrade `0001..0029` plus frozen-v1 seed/snapshot plus `0030` from exact frozen
commit `8c9490cdc074001ca58c03a6e67bacf2806b33fa` / tree
`f71aad198ab66e4ff22b6f893b004bccfd3e35b4`. Its raw single-line
attestation-v2, parsed 14 checks, bundle/log hashes and independent read-only
post-audit are immutable historical PASS evidence. The same exact source then
failed its full profile: `docs/plans/README.md` and `docs/roadmap.md` omitted
literal `0030`, and the schema current-truth test hard-coded
`implementation_allowed` although the evidence packet was legitimately
`local_verified`. PostgreSQL was not the cause. Correcting the lifecycle test,
owner contracts and status docs is candidate-invalidating, so the seventh status
is exactly `runtime_passed_unpromotable_current_truth_lifecycle_test_regression`.
The eighth run `t3a260805163536` then passed fresh `0001..0030` and upgrade
`0001..0029` plus frozen-v1 seed/snapshot plus `0030` from exact runtime commit
`9f230f2e0c44a0157fb58870f10197e5525c227a` / tree
`89e7e5e70ca16cfba20f4140df7995a463b7ce31`. Its attestation-v2, controller
read-only post-audit and independent read-only review passed for all sixteen
database identities. The cross-version owner-digest correction verification
commit `1714f376d40e21112b13f537572932a1f5bd38f0` / tree
`7ba9ff1863822a90ffd081d3de70c0f7af3dfbc2` separately passed the unique
173-command full profile (Node 747/747, Python 2718/2718 with two expected
unconfigured candidate skips, Vitest 437/437), Harness and exact two-path
candidate-to-verification diff gate; it does not replace the runtime identity.
Historical PR CI run `30993690037` produced 29 false owner-gate failures because
Python 3.11 included empty optional AST fields that Python 3.13 omitted by
default. The stable serializer at `1714f376` corrects that compatibility defect
without changing or invalidating the runtime candidate. Current evidence is
`runtime_verified / candidate_verified`; runtime and verification identities
are separately bound. Task 3A delivery closure then completed: PR #114 merged
as `97fca062`, the merge result and final archive record passed scoped Harness,
and main/origin parity was confirmed before scoped cleanup. Only the exact eighth
fresh/upgrade databases were discarded; current candidate artifacts were moved to
recoverable quarantine/Trash and all fourteen historical databases were untouched.
The merged Task 3A implementation worktree and its local feature branch were
removed; the remote feature ref was already absent after PR merge.
The formal closure identity remains `pending` because the active Task 3A lifecycle
test permits no `archived` stage and explicitly requires pending; no lifecycle-contract
change was included in this closure. Runtime consumers remain empty, production
migration was not executed, generation 35 is unchanged, and only separate Task 4P
pure-domain work is authorized next.

All seven run-id pairs and all fourteen databases are immutable/non-reusable
evidence: never reset or reuse them. The test suite never creates, drops, resets
or reuses any candidate database.

The fourteen non-reusable database identities are:

- `wow_exact_first_fresh_test_t3a2608050955` and
  `wow_exact_first_upgrade_test_t3a2608050955`;
- `wow_exact_first_fresh_test_t3a260805111623` and
  `wow_exact_first_upgrade_test_t3a260805111623`;
- `wow_exact_first_fresh_test_t3a260805113656` and
  `wow_exact_first_upgrade_test_t3a260805113656`;
- `wow_exact_first_fresh_test_t3a260805120026` and
  `wow_exact_first_upgrade_test_t3a260805120026`;
- `wow_exact_first_fresh_test_t3a260805125812` and
  `wow_exact_first_upgrade_test_t3a260805125812`;
- `wow_exact_first_fresh_test_t3a260805142130` and
  `wow_exact_first_upgrade_test_t3a260805142130`;
- `wow_exact_first_fresh_test_t3a260805160003` and
  `wow_exact_first_upgrade_test_t3a260805160003`.

Because the current-truth lifecycle correction was candidate-invalidating, the eighth run did not
reuse any prior identity. It used new lowercase run id `t3a260805163536`, matching
`[a-z0-9]{8,32}`; the suite rejected all seven historically forbidden ids before importing
`psycopg` or connecting. An operator with explicit authority provisioned two distinct empty
databases and exact database comments:

- `wow_exact_first_fresh_test_t3a260805163536` with comment
  `wow_exact_first_disposable:t3a260805163536:fresh`;
- `wow_exact_first_upgrade_test_t3a260805163536` with comment
  `wow_exact_first_disposable:t3a260805163536:upgrade`.

The cluster must already contain the repository's `wow_migrator` and `wow_app`
roles. Historical migration `0009_runtime_reconcile_privileges.sql` executes
`ALTER DEFAULT PRIVILEGES FOR ROLE postgres`; therefore each explicit candidate
DSN must use an existing operator/migrator identity that already has the
authority required by migrations `0001..0029` (commonly `postgres`, or an
existing operator that can `SET ROLE postgres`). The suite does not create,
alter or grant roles, and it does not change any historical migration. Do not
add a non-superuser role gate that would contradict the frozen migration chain.

The safety boundary is instead exact and machine-checked: the two explicit DSNs
must resolve to the exact run-id-bound names/comments above; both databases must
have no project schema, table or ledger before the first write; the suite never
creates, drops, resets or reuses a database; and migrations `0001..0030` contain
no `CREATE DATABASE`, `DROP DATABASE` or `ALTER DATABASE`. Every migration DDL
statement is therefore scoped to the current DSN database. No additional DSN or
implicit admin connection is accepted.

After origin/main is integrated and the Task 3A code, tests and `0030` are committed
on a clean final runtime-affecting tree, run:

```bash
WOW_PG_TEST_RUN_ID_0030='<run-id>' \
WOW_PG_TEST_DSN_FRESH_0030='<fresh-disposable-dsn>' \
WOW_PG_TEST_DSN_UPGRADE_0030='<upgrade-disposable-dsn>' \
python3 -m unittest \
  tests.postgres_integration_test.PostgresExactAuthorityCandidateTest
```

The fresh path applies `0001..0030`; it must end with exactly 30 migration ledger
rows, exactly one `0030_websim_exact_authority_bundle` ledger row and exactly one
`app.build_templates` target constraint named
`build_templates_user_id_template_type_config_hash_key`, type `u`, with ordered
columns `user_id, template_type, config_hash`, no legacy
`build_templates_user_id_template_type_name_key` constraint, and exactly one
`0003_build_template_config_hash_unique` ledger row. The upgrade path independently applies
`0001..0029`, inserts a frozen v1 row, snapshots its complete row including
`sealed_at` plus all existing project schemas, tables, columns, constraints,
indexes, triggers, default ACLs and effective `wow_app` grants, applies `0030`,
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
`0030` SHA-256 and both database names/comments, then emits exactly one compact
`task3a-candidate-attestation-v2` JSON record as its final stdout line. Archive that
single line verbatim for the later Task 3A `evidence.json`/`manifest.json` promotion review; it contains
the run id, both database identities, commit/tree/migration hashes,
`passed=true`, and the exact verified-check list, but no DSN or credential.
Local/skipped runs emit no successful attestation and must not create or update
either evidence file.

Leave the seventh pair intact as immutable historical evidence; it was not used for
current promotion. The eighth pair used a new run id and two new
operator-provisioned databases. Runtime/product code, migration, PostgreSQL candidate
integration test, requirement or owner-contract changes after candidate execution
invalidate the candidate. The accepted lifecycle and cross-version digest correction is
separately bound to verification commit `1714f376`; executable Git diff gates prove
candidate-to-verification contains only the owner test and active plan, and
verification-to-promotion contains
only the six declared evidence/status files. Only an operator may discard the two exact
eighth-candidate database identities after delivery closure, archival and identity
verification; the suite never does.
Missing `psql`, either DSN, or the run id is a skipped candidate and remains
`candidate_pending`, never green evidence. The fourth pair remains superseded
attestation-v1 history, the fifth remains
`runtime_passed_invalidated_by_direct_runtime_import_regression`, and the sixth remains
`runtime_passed_unpromotable_evidence_lifecycle_test_regression`; the seventh remains
`runtime_passed_unpromotable_current_truth_lifecycle_test_regression`; none can be reused.
The historical `candidate_rerun_required / evidence_promotion_blocked` status was cleared
only by the independent eighth pair plus the separately bound verification HEAD. Runtime
and verification identities are bound; delivery closure is recorded, while formal closure
remains pending under the current lifecycle contract.
The technically successful
`t3a260805113656` attestation also remains unpromotable.
No production migration is authorized.

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
