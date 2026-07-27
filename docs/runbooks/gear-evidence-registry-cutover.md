# Gear Evidence Registry Candidate Cutover Runbook

## Purpose and hard boundary

This runbook covers Task 8 of the Evidence Registry plan. It prepares and
verifies a candidate release before a retail cutover. It does not authorize an
operation merely by being followed.

The player journey that this protects is simple: the same item capability must
mean the same thing in browse, Resolve, and the active Taro equipment route.
`250033/void_upgrade-298` must offer one gem socket; a fact verified as false
or zero must display **不可用**; missing or conflicting evidence must display
**待核验** only for that category, without disabling already verified categories.
Players must not see Artifact payloads, Observation content, hashes, queue
state, root codes, worker internals, or database configuration.

This is a Strict `user_visible_runtime` procedure. Local tests can establish
only `local_verified`. Candidate verification does not authorize retail
promotion. The existing immutable Gear Release and Active Season Manifest are
the only release and pointer authority; do not create a second release type,
Manifest, or pointer.

## Preconditions and evidence record

Before any candidate write, assign and record these non-secret identities in
the task release packet. Stop if any is absent, mutable, or points at retail.

| Identity | Required proof | Fail-closed rule |
| --- | --- | --- |
| Pre-candidate checkpoint | final local CR, committed and pushed task branch, clean worktree, re-run scoped suites, exact `HEAD` and `HEAD^{tree}` | Candidate deployment is forbidden until this checkpoint is recorded. Later evidence-only appends may not modify runtime or build inputs; any runtime change requires a new checkpoint and candidate window. |
| Candidate source | checkpoint branch, commit, `HEAD^{tree}`, and source-tree SHA-256 inventory | The candidate root must be an immutable copy/check-out of that committed tree; no uncommitted source or copied retail tree is eligible. |
| Candidate build | build command, build output hash inventory, and build timestamp | Rebuild or reject if output hashes do not match the candidate tree/commit record. |
| Candidate root | unique path such as `/opt/wow-mini-program-candidate/<candidate-id>` | Never use `/opt/wow-mini-program`, a retail worktree, or `server/deploy_lighthouse.sh`. |
| Candidate database | separately provisioned database identity and backup artifact path, with credentials kept in a root-readable environment file or `PGPASSFILE` | The identity must be demonstrably different from retail before migration, import, replay, or a worker run. Do not print a URL, password, token, or environment-file contents. |
| Candidate service and port | unique systemd unit such as `wow-backend-candidate-<candidate-id>.service`, private listener port, and unit/root hash | Do not reuse `wow-backend`, retail listeners, or a port with retail traffic. The repository's `wow-backend-candidate.service` is a read-only preview template; do not use it unchanged for candidate migration/write work because it sets `PGOPTIONS=-c default_transaction_read_only=on`. |
| Retail rollback target | current retail Active Season Manifest revision, pointer generation, active mode, Gear/Community Release IDs, and dependency revisions | Read and record this before candidate work. No retail pointer write is allowed at this point. |

Use a dedicated candidate environment file with restrictive permissions and
keep it outside evidence text, shell history, command output, screenshots, and
support tickets. Run commands with tracing disabled. Record a sanitized
database label/checksum, not its connection string.

The public candidate API unit must use the candidate root, candidate database,
unique candidate port, `WOW_DATABASE_RUNTIME=postgres_only`, and
`WOW_DEPLOY_START_ASYNC_SYNCS=0`. It is read-only, has collectors disabled, and
does not run migrations, Artifact/Observation replay, or workers. Those writes
may run only through separately named one-off writable migration/worker units
against the isolated candidate database; their unit names, roots, locks, and
exit state are recorded separately. The API unit's service definition,
environment-file path (not content), and executable file hashes belong in the
evidence packet.

## 1. Freeze the candidate and backup the isolated database

1. Complete the immutable pre-candidate checkpoint: final local CR, commit and
   push the complete runtime slice, confirm a clean task branch, re-run the
   scoped backend and Taro suites, and record the exact committed `HEAD` and
   `HEAD^{tree}`. Stop if any source/build input differs afterward. Preserve
   unrelated work; do not reset, clean, pull, or modify retail source.
2. Materialize the candidate root from that exact recorded checkpoint tree. Record the
   commit, tree, candidate-root file inventory, executable hashes, and future
   build output hashes. Do not copy selected files into a retail root.
3. Verify that the candidate service has no retail bind address, root, port,
   database identity, or systemd unit name. Keep `WOW_DEPLOY_START_ASYNC_SYNCS=0`.
4. Before any SQL migration or candidate data write, create a restorable,
   timestamped backup of the **candidate** PostgreSQL target. Record backup
   path, SHA-256, sanitized database label, schema-migration list, current
   candidate Manifest/pointer row, and its generation. Do not substitute a
   retail backup or a logical description for a real backup artifact.
5. With a migration-owner connection to the candidate database only, read
   `ops.schema_migrations` and assert the expected preceding migration state.
   The candidate sequence is strictly ordered: first apply
   `0019_gear_evidence_registry` only if it is absent; re-read and validate its
   Artifact/Observation/Canonical Fact/Gap tables, append-only constraints and
   runtime grants; then apply `0020_gear_evidence_candidate_recompile` only if
   it is absent. Do not skip, reorder, or apply `0020` without a verified 0019.
6. After `0020`, re-read `ops.schema_migrations` and verify its candidate
   request table, status/lease constraints, foreign keys, indexes, and grants.
   Verify both migrations' schema/grant expectations before import or replay.
7. Also assert PostgreSQL-only runtime, expected candidate identity, no
   unexpected active writer, existing Manifest/pointer state captured, and the
   recorded migration sequence. Any mismatch
   stops the run; restore the candidate database before retrying.

The migrations are additive for the immutable registry and candidate recompile
handoff. They are not a
license to update or delete Artifact, Observation, or Canonical Fact rows. If
the migration check fails, stop the candidate service, restore the isolated
candidate backup, and record the failure; do not continue with a partially
migrated database.

## 2. Rebuild evidence and seal an inactive candidate Gear Release

1. Import immutable source inputs as Evidence Artifacts. Record source
   identity/revision, season revision, payload hash, Artifact ID, import count,
   and idempotency result. Reject secret-shaped input and do not put raw payload
   content in the release packet.
2. Replay each Artifact through the versioned observers. Record parser
   revision, Observation IDs, structured non-observation diagnostics, and
   replay count. Replaying the same inputs must reuse identities rather than
   mutate prior rows.
3. Compile Facts only from the recorded Artifact/Observation inputs, parser
   revision, and policy revision. Record candidate fact digest and counts by
   `verified`, `unresolved_missing`, and `unresolved_conflict`. A confirmed
   `false`/`0` remains `verified`; absence must never be coerced to false/zero.
4. Run the old-versus-canonical shadow report before sealing. Every difference
   must be exactly one of `exact_parity`, `intended_correction`,
   `newly_exposed_gap`, or `regression`. Record the complete classification
   counts and the reviewed `250033/void_upgrade-298` correction. Any
   `regression`, unclassified difference, release-integrity failure, or mixed
   release blocks sealing and promotion.
5. Invoke the existing candidate release-preparation path only. It may seal or
   reuse an immutable **inactive** candidate Gear Release; record its release
   ID, content hash, parent release, dependencies, fact/provenance digest, and
   no-op result. Do not call `run_release_refresh`, a Manifest writer, a
   promotion command, or `server/deploy_lighthouse.sh` here.
6. Run every full-catalog candidate materialization as a named, bounded one-off
   unit: record a non-zero CPU quota, a memory maximum that leaves retail headroom,
   positive niceness, and a finite runtime maximum before starting it. A quota,
   memory, or time breach is a failed candidate attempt: stop there, preserve the
   isolated database/backup for diagnosis, and never retry without a fresh root
   cause and a new recorded envelope. Do not use an uncapped foreground process
   on a shared retail host.
7. If a fenced Evidence Gap request is part of the candidate sample, run the
   candidate gap worker and candidate recompiler against the candidate root and
   candidate database only. Record request/gap identity, lock outcome,
   Artifact/Observation reuse, candidate release ID, and bounded job count.
   The worker may collect immutable input and request an inactive candidate
   release; it may not write facts directly, alter policy/code, invoke refresh,
   deploy, or switch a Manifest.

## 3. Isolated candidate runtime verification

Start only the named read-only public candidate service on its unique private
port. Confirm its process root, command, environment guards (without printing
secrets), listener, and file/build hashes match the recorded candidate identity.
The candidate must not receive retail traffic. Its collectors remain disabled;
the one-off writable migration/worker processes must be stopped before public
API smoke begins unless a bounded worker gate expressly requires a separately
recorded run.

Record all responses as sanitized structured evidence, including request shape,
HTTP status, fact state/value, release/Manifest revision, and problem code. Do
not record credentials or raw registry evidence.

Required candidate gates are:

1. `/health` and `/api/data/health` return their expected service and business
   states. A 200 does not erase a `partial` or `blocked` component; record the
   component key/value separately.
2. Affected compact browse and exact Resolve use the same candidate-released
   fact identity for `250033/void_upgrade-298`, and report one socket. Resolve
   must retain dynamic legality and fail closed for malformed, stale,
   wrong-slot, and unavailable-authority input.
3. A verified zero/false capability returns unavailable; an unresolved
   socket/enchant/embellishment category returns pending only for that category.
   Confirm another verified category remains usable in the same response.
4. Artifact/Observation/Fact details, hashes, queue data, root codes, and
   worker diagnostics are absent from the public browse/Resolve/Taro contract.
5. The bounded gap worker and candidate recompiler are either deliberately
   exercised with the recorded request or proven idle/no-op. Record service
   exit, request state, retry/lease behavior when exercised, and candidate
   release identity. A successful systemd exit alone is insufficient.
6. Record timer and backflow state before and after candidate activation. With
   `WOW_DEPLOY_START_ASYNC_SYNCS=0`, no deploy-triggered refresh, sync,
   backfill, or retail write may occur. Any unexpected task is a candidate
   failure, even if health remains 200.
7. Review candidate logs from activation through smoke for traceback, error,
   failed, or unexpected write evidence. Correlate any failure with health and
   payload state rather than declaring success from service liveness.

Candidate sealed releases do not exist in retail merely because their IDs exist
in the candidate database. The candidate preview must bind the inactive
candidate Gear/Community Release IDs through the dedicated candidate-release
environment configuration and must report that binding in health/API evidence;
it must not change a candidate or retail Active Season Manifest pointer. If the
runtime has no verified inactive-release configuration path, candidate preview
is blocked rather than using a candidate CAS as a substitute.

## 4. Real Taro acceptance gate

Build the active Taro package from the exact candidate root and record its
immutable build hash/file inventory. Use the real WeChat DevTools project and
the isolated candidate endpoint; browser emulation, unit tests, screenshots,
or a stale package do not satisfy this gate.

The user must explicitly accept all of these frozen items on the same candidate
identity:

| Manual item ID | User-visible action and expected result |
| --- | --- |
| `gear_evidence_250033_one_socket` | Open the relevant equipment detail and verify `250033/void_upgrade-298` shows exactly one selectable gem socket. |
| `gear_evidence_confirmed_unavailable` | Verify a released capability with `verified` false/zero displays **不可用** and has no selectable control. |
| `gear_evidence_pending_category_only` | Verify an unresolved capability displays **待核验** only for that category; a verified category in the same item remains usable. |

Until every item is accepted by the user, the packet remains
`candidate_verified` at most, retail remains on its existing Active Season
Manifest, and no retail CAS, merge, or live-verified claim is allowed.

## 5. Accepted candidate to main and retail replay parity

This section may run only after all candidate gates pass and the user gives
explicit cutover authorization following the real Taro acceptance. The sealed
candidate releases live only in the isolated candidate database; retail must
materialize its own deterministic copies before any pointer write.

1. Append the candidate and manual-acceptance evidence, perform final local CR,
   and commit/push the task branch. Evidence-only additions after this point
   must not modify runtime source, build inputs, or the accepted candidate
   identity.
2. Sync and merge `main` without history rewrite, re-run the scoped suites on
   the merge result, push `main`, and prove local/`origin/main` SHA parity. Any
   conflict, failed re-test, or changed runtime tree stops the cutover and
   requires a new candidate checkpoint.
3. Back up the retail database before any schema or replay write. Read
   `ops.schema_migrations`, then apply and verify `0019_gear_evidence_registry`
   followed by `0020_gear_evidence_candidate_recompile` only as required by its
   existing state, with the same schema/grant checks used on candidate. Deploy
   the compatible committed `main` code without invoking refresh/sync/backfill.
4. Deterministically replay the **same** immutable Artifact IDs/payload hashes,
   Observation IDs/parser revisions, and compiler policy revision into retail.
   Materialize retail Gear/Community Releases from those identities. Compare the
   retail and accepted candidate Gear/Community Release IDs, content hashes,
   fact/provenance digests, dependencies, and no-op result. Any mismatch blocks
   retail CAS; do not point retail at a candidate-database release ID.
5. Re-read the retail pointer immediately before writing and record the existing
   retail Active Season Manifest as `PRIOR_MANIFEST`, its exact fresh pointer
   generation as `PRIOR_GENERATION`, mode, retail Gear/Community Release IDs,
   dependency revisions, and the new backup artifact. This is the rollback
   target.
6. Confirm the retail materialized releases are immutable, complete, and
   compatible with explicit season, SimC, talent, and optional Community Release
   revisions. Re-run the final retail shadow check; any regression blocks CAS.
7. Use the existing release tool's `promote` command with every identity and
   `--expected-generation` explicitly supplied. It seals/reuses the existing
   Manifest model and atomically compare-and-swaps the existing retail pointer;
   never update tables or the pointer by ad-hoc SQL.

```bash
python3 -m server.gear_release_tool promote \
  --season-revision "$SEASON_REVISION" \
  --simc-runtime-revision "$SIMC_RUNTIME_REVISION" \
  --gear-release-id "$CANDIDATE_GEAR_RELEASE_ID" \
  --community-release-id "$COMMUNITY_RELEASE_ID" \
  --talent-catalog-revision "$TALENT_CATALOG_REVISION" \
  --expected-generation "$PRIOR_GENERATION" \
  --rollback-manifest-revision "$PRIOR_MANIFEST" \
  --updated-by "$CUTOVER_ACTOR"
```

The values are identity labels, never credentials. A CAS conflict, missing
release, dependency mismatch, integrity failure, or unexpected pointer state is
a hard stop: re-read retail state and do not retry with a guessed generation.

8. Record returned Manifest revision and generation, then immediately repeat
   health, affected API, exact Resolve, candidate-equivalent Taro smoke, worker,
   timer/no-op/backflow, log, and release/Manifest parity checks against the
   new retail identity. `200` alone is not evidence of a correct cutover.
9. After the user-accepted cutover is healthy, perform caller-proof cleanup in
   a separately reviewed source change: no independent `hasSocket`, enchant, or
   embellishment truth writer/reader may remain outside Canonical Fact
   projection. Do not fold unreviewed cleanup into the CAS window.

## 6. Rollback drill and recovery

Rollback is a pointer operation, not a mutation or deletion of immutable
registry/release records. Artifact, Observation, Canonical Fact, invalidation,
and candidate-request rows are append-only and survive Manifest rollback.

If the post-CAS smoke finds a regression or the user rejects the live behavior:

1. Stop further rollout activity and record the current retail pointer
   generation. Do not run refresh, source sync, backfill, or ad-hoc repair.
2. Re-read `PRIOR_MANIFEST` and ensure it is still an existing compatible
   Manifest. Call the existing `rollback` command with the **current** pointer
   generation and that prior Manifest revision. It must remain a CAS.

```bash
python3 -m server.gear_release_tool rollback \
  --manifest-revision "$PRIOR_MANIFEST" \
  --expected-generation "$CURRENT_GENERATION" \
  --updated-by "$CUTOVER_ACTOR"
```

3. A rollback CAS conflict is a hard stop. Re-read the pointer, preserve
   evidence, and escalate; never force a generation, delete a pointer, reset
   it to generation zero, or use direct SQL.
4. Prove rollback with fresh health, data-health component, browse, Resolve,
   active Taro, worker/timer/no-op, and log smoke bound to the restored Manifest
   revision. Record the new rollback generation and confirm that append-only
   registry rows still exist unchanged.
5. Restore the candidate database from its pre-`0019` backup only when the
   isolated candidate migration/data state itself must be discarded. This is
   not the normal retail release rollback and must never target retail.

## Evidence completion and prohibited shortcuts

The final packet must separately bind runtime (candidate or retail immutable
identity), verification (clean exact `HEAD`), and closure (merge identity).
It must distinguish `local_verified`, `candidate_verified`, `live_verified`,
and manual acceptance truthfully.

Do not:

- use `server/deploy_lighthouse.sh`, `wow-backend`, a retail database, or a
  retail listener for candidate verification;
- confuse the task-scoped Harness `manifest.json` with an Active Season
  Manifest, or create a new Active Season Manifest before candidate identity
  and candidate evidence exist;
- promote because tests, health, or a worker unit exit successfully;
- silently downgrade an unresolved category to unavailable or infer a false/0
  value from a missing field;
- erase append-only registry rows to make rollback look clean; or
- print or store database URLs, passwords, tokens, or environment-file content
  in commands, logs, screenshots, documentation, or the release packet.
