# Equipment Simulator Phase 5 Async Stat Snapshot Delivery Plan

**Status:** Slices 5A-5B merged/live-verified; Slice 5C implementation allowed
**Classification:** Strict  
**Goal boundary:** Phase 5 only; Phase 6 Catalyst remains disabled and external-dependency gated  
**Starting point:** main `1e4b549867aac49ccbb73a4281821f0cf114423e`, Phase 4E merged by PR #78 and clean-main live-verified

> 2026-07-11 progress: Slice 5A merged through PR #79 at `8a75fd5`; Slice 5B merged through PR #80 at `9ee557b` after exact-head CI, candidate and clean-main live verification. The canonical async route, stable one-child worker, active-binding/authority cache seam, bounded operations health and best-effort legacy telemetry are live. Slice 5C now owns only the active frontend client/state cutover; backend execution and Catalyst remain unchanged.

## 1. Outcome

Move verified SimC character-stat snapshots out of the HTTP request thread and into a PostgreSQL-backed, single-flight worker path without changing equipment legality, public template policy, standard Profile behavior, or legacy `/api/websim/gear/stats` response shape.

The new contract is:

```text
POST /api/websim/gear/stat-snapshots
  -> re-resolve untrusted Selection Intent against the active Manifest
  -> serialize stat_snapshot_v1 input on the server
  -> derive a revision-complete stat signature
  -> 200 verified cache hit
     202 pending get-or-start
     structured 503 unavailable/saturated/cooldown

wow-gear-stat-snapshot-worker.service
  -> claim one PG job with a fenced lease
  -> re-resolve and re-serialize before execution
  -> reject revision/signature drift
  -> run one SimC child
  -> parse verified JSON buffed_stats
  -> atomically publish one immutable snapshot
```

No response exposes DPS, raw profile text, raw SimC output, SQL, DSN, traceback, lock token, or unbounded evidence.

## 2. Current truth and reusable boundaries

- Formal retail Manifest is active at generation 9 and binds immutable Gear and Community Releases.
- `Selection Intent` remains untrusted. `server/gear_runtime.py` owns canonical Resolve/Profile re-resolution.
- `server/websim_payload.py` already owns `stat_snapshot_v1`, `iterations=1`, `calculate_scale_factors=0`, JSON output parsing and the synchronous legacy adapter.
- `pages/builds/gear-workbench-state.js` already owns intent versioning, stale Resolve suppression, last verified snapshot state and stat status fields.
- `pages/builds/detail.js` and `pages/simulator/simc.js` still call `/api/websim/gear/stats` synchronously.
- There is no snapshot/job table, worker liveness record, worker service, async endpoint or queue health surface.
- PostgreSQL-only runtime must not fall back to SQLite.
- Phase 4 scheduled refresh and Phase 5 worker have separate ownership and locks.

## 3. Non-goals

- No DPS calculation, comparison, optimizer or system BiS.
- No public baseline, recommendation, default or SimC preset template.
- No frontend profile assembly.
- No reuse of `personal.simulator_tasks` or Chickenbro/Codex workers.
- No Redis, Celery, event bus or microservice split.
- No deletion of legacy `/api/websim/gear/stats` in this Goal.
- No automatic background generation for all user combinations.
- No two-child concurrency until the one-child candidate resource gate passes; Phase 5 ships with one child.
- No Phase 6 `preserve_base_secondary_stats` activation or Catalyst UI.

## 4. Architecture decisions

### 4.1 Signature

`stat-signature-v1` hashes a canonical object containing:

- resolved Gear signature;
- server-built `stat_snapshot_v1` profile hash;
- active Manifest, Gear Release, talent catalog and pointer generation;
- season, resolver, rule, serializer, selection-schema, stat-policy, capability and SimC runtime revisions;
- bounded actor context that is already represented in the profile hash.

The client never supplies or overrides the final signature. A runtime or dependency revision change creates a natural cache miss.

### 4.2 Stored inputs and outputs

- Jobs store only normalized `selectionIntent`, allowlisted `profileContext`, exact expected release context and signature metadata.
- Workers never execute a stored profile. They re-resolve and rebuild the profile, then compare the new signature to the queued signature.
- Verified snapshots are immutable and keyed by stat signature.
- Job rows are mutable operational state and append attempts; no job or snapshot DELETE is granted to `wow_app`.
- Deterministic blockers stay tied to the exact signature. Transient failures use a bounded cooldown and become retryable afterward.

### 4.3 Single-flight and fencing

- A partial unique index allows at most one `queued` or `running` job per signature.
- Claim uses `FOR UPDATE SKIP LOCKED`.
- Every claim receives a random lock token plus `lease_until`.
- Heartbeat and completion update only when `(job_id, lock_token, status='running')` still match.
- Expired running jobs are reclaimed with a new lock token. A stale worker cannot publish after losing its lease.

### 4.4 Backpressure

- Default global active queue limit: 100.
- Default per-client active ownership limit: 2.
- Client identity is stored only as a server-side SHA-256 hash of the bounded analytics client ID; raw client identifiers are not stored.
- Default worker concurrency: one SimC child.
- API never launches SimC or waits for a job to finish.

### 4.5 Response semantics

- `200 resolved`: verified immutable snapshot for the exact signature.
- `202 pending`: queued/running job with bounded `jobId`, `statSignature`, `status`, `queuedAt` and `retryAfterMs`.
- `503 unavailable`: worker/runtime unavailable, saturated, lease/cooldown state or transient store failure via a structured `gear-result-envelope-v1` problem.
- Resolver/profile blockers keep their existing 200/400/409/503 structured semantics and do not enqueue work.

## 5. Delivery slices

### Slice 5A — Pure contract, PostgreSQL store and migration

**New boundaries:** pure snapshot policy; one SQL repository.

Files:

- Create `server/gear_stat_snapshot.py`.
- Create `server/gear_stat_snapshot_store.py`.
- Create `server/migrations/postgres/0015_websim_gear_stat_snapshots.sql`.
- Create `tests/gear_stat_snapshot_test.py`.
- Create `tests/gear_stat_snapshot_store_test.py`.
- Update `tests/postgres_schema_test.py`.
- Update owner maps, verification matrix and this release packet.

Required behavior:

- deterministic revision-complete signature;
- bounded verified/pending/unavailable data projections;
- immutable snapshot insert/reuse with content hash verification;
- single-flight get-or-start in one transaction;
- global/per-client limits;
- fenced claim, heartbeat, completion, deterministic block, transient cooldown and expired-job reclaim;
- bounded queue/worker/cache/legacy telemetry projection;
- least privileges and no DELETE.

Candidate gate:

- backup `wow_test`;
- atomically apply migration 0015;
- verify constraints, indexes, grants and migration identity;
- direct store smoke proves single-flight, fenced lease, reclaim, immutable reuse and cleanup-free rollback;
- no route, worker or frontend behavior exists yet.

### Slice 5B — Canonical async API, worker and operations

**New boundaries:** worker runner; route/orchestration facade over the 5A repository.

Files:

- Create `server/gear_stat_snapshot_worker.py`.
- Create `server/wow-gear-stat-snapshot-worker.service`.
- Update `server/gear_runtime.py` only if a reusable stat-profile re-resolution facade is required.
- Update `server/websim_payload.py` to serialize a canonical resolved snapshot with explicit execution flavor; preserve standard Profile defaults.
- Update `server/news_backend.py` for `POST /api/websim/gear/stat-snapshots`, bounded health/admin and best-effort legacy telemetry.
- Update `server/postgres_cache_store.py` only for the bounded health projection seam.
- Update `server/deploy_lighthouse.sh` to install and start/restart the worker without starting Phase 4 refresh or async staging syncs.
- Add focused worker/route/deploy/health tests.

Required behavior:

- API re-resolves before enqueue and never calls SimC;
- worker re-resolves again before execution and rejects signature drift;
- heartbeat remains live during the blocking SimC child through a separate PG connection;
- one worker process owns one child at a time;
- worker state records revision, heartbeat, current job and bounded last outcome;
- crash/timeout/restart/expired lease paths are recoverable;
- output parser accepts only verified `buffed_stats`; DPS fields are discarded/not persisted;
- legacy `/gear/stats` remains synchronous and shape-compatible, but increments bounded legacy telemetry best-effort.

Candidate gate:

- runtime file parity at exact implementation head;
- explicit worker start with current SimC revision;
- cache miss returns 202 without request-thread SimC; poll returns 200 verified;
- duplicate concurrent requests share one job;
- forced stale lease is reclaimed; stale lock token cannot complete;
- worker stop returns structured 503 for new misses while verified hits remain readable;
- service resource, heartbeat, queue, health/admin, logs and rollback evidence pass.

### Slice 5C — Frontend cutover and polling state

**New boundaries:** API client method; pure stat-snapshot state transitions reused by active consumers.

Files:

- Update `pages/builds/websim-api.js` with structured `requestWebsimGearStatSnapshot`.
- Extend `pages/builds/gear-workbench-state.js` with begin/apply/poll/stale transitions guarded by intent version and request serial.
- Update `pages/builds/detail.js` to send canonical `selectionIntent + profileContext`, poll boundedly and preserve last verified stale/read-only display.
- Update `pages/simulator/simc.js` to use the new endpoint for summary snapshots.
- Update frontend API, workbench, builds-page and simulator-page tests.

Required behavior:

- no active frontend call site invokes `requestWebsimGearStats`;
- 202 polling is bounded by attempt and wall-clock limits and stops on intent/template/race/scenario change;
- old response serials cannot overwrite a newer intent;
- 409 may use the existing single rebase path, then re-resolve before any new snapshot request;
- 503/offline retains last verified snapshot only as stale/read-only evidence;
- pending/unavailable state never turns raw deterministic attributes into verified SimC percentages;
- no full template array rewrite is introduced.

Candidate gate:

- frontend/full profiles pass;
- real WeChat DevTools flow shows 202 to 200 with no legacy `/gear/stats` request;
- race/intent change during polling ignores the stale completion;
- offline/unavailable view remains truthful and recoverable;
- existing Profile/save/submit behavior remains compatible.

### Slice 5D — Real 40-spec matrix, legacy telemetry and closure

No new product semantics. This is the final runtime/evidence gate.

- Run all 40 active observed Community Intents through current Resolver and stat get-or-start.
- Every combination that claims `profileReadiness=ready` must execute through the worker and produce parseable verified JSON `buffed_stats`.
- Non-ready specs must return the existing allowed explicit blocker; no false `ready` and no fabricated snapshot.
- Record queue latency, execution duration, cache-hit latency, single-flight rate, p50/p95/p99, memory, CPU, query counts, worker heartbeat and service restart behavior.
- Prove legacy `/gear/stats` shape compatibility and bounded usage telemetry while new frontend traffic is zero on the legacy route.
- Prove public 40-spec observed-only/baseline-empty policy, active Manifest integrity, Resolver/Profile compatibility, Catalyst fail-closed behavior and PG-only runtime.
- Candidate deploy, exact-head CI, PR, merge, clean-main deploy, post-merge worker run, live smoke, parity and documentation closure are mandatory.

## 6. TDD order

For every slice:

1. Add one failing characterization or contract test.
2. Run the narrow test and capture the expected failure.
3. Implement the smallest boundary.
4. Re-run narrow and related suites.
5. Run backend/frontend/full profile as appropriate.
6. Run local CR against the active requirement and inspect SQL, locks, fallback paths, profile flavor, response envelopes, frontend stale-response guards and Catalyst exclusion.
7. Promote evidence only after current command output exists.

## 7. Mandatory failure cases

- forged client signature or final stat facts are ignored;
- invalid/revision-stale Intent returns existing structured problems and creates no job;
- profile/talent blocker creates no job;
- current runtime revision differs from queued signature;
- worker heartbeat expires mid-run;
- stale worker completes after reclaim;
- two API processes enqueue the same signature concurrently;
- per-client/global limits are exceeded;
- worker is missing, stopped or on the wrong revision;
- SimC timeout, crash, invalid JSON or missing `buffed_stats`;
- snapshot content hash conflict;
- verified old snapshot exists for an incompatible revision;
- frontend receives out-of-order 202/200, 409, 503 or offline results;
- legacy `/gear/stats` remains 200-shape compatible;
- unknown Catalyst option remains structured 503 and never reaches the worker.

## 8. Performance and resource gates

- API cache hit p95 <= 200ms and get-or-start miss p95 <= 500ms on the candidate host.
- API query count is bounded and does not scale with queue depth.
- One SimC child only; record worker MemoryPeak/CPU and backend impact.
- Queue claim is indexed and uses `SKIP LOCKED`.
- Heartbeat interval is less than one third of the lease duration.
- Polling defaults to 1 second initially with bounded backoff, maximum 15 attempts and maximum 45 seconds unless candidate evidence requires a smaller safe bound.
- Snapshot payload and problem arrays have explicit size/count caps.
- Health calculates bounded aggregates, not unbounded event scans.

## 9. Deployment and rollback

Each runtime slice follows:

```text
local TDD + CR
  -> candidate DB backup when schema/data is touched
  -> candidate deploy from exact PR head with WOW_DEPLOY_START_ASYNC_SYNCS=0
  -> explicit worker/service/API smoke
  -> exact-head GitHub CI
  -> merge
  -> clean-main fast-forward and deploy
  -> post-merge worker/API/public/health/log/parity smoke
```

Rollback order:

1. frontend config/code rollback to legacy client;
2. stop/disable worker and remove new route by code rollback;
3. preserve additive 0015 tables and verified snapshots for audit;
4. restore database backup only for corruption, never for normal code rollback;
5. active Manifest and Phase 4 refresh remain independent and unchanged.

## 10. Plan self-review

- **Authority:** both API and worker re-resolve; stored profile text is never execution authority.
- **Atomicity:** snapshot publication and job completion are fenced; cache visibility follows verified insert.
- **Concurrency:** partial unique single-flight plus lock-token fencing covers multi-process races and stale workers.
- **Availability:** verified cache hits remain readable when the worker is down; misses fail truthfully.
- **Compatibility:** standard Profile and legacy stats keep existing flavors/shapes; new frontend uses only the async endpoint.
- **Security/privacy:** no raw identifiers, profile, SimC output, SQL, DSN or traceback is exposed or stored unnecessarily.
- **Scope:** Catalyst, DPS, optimizer, public template policy and staging sync are unchanged.
- **Reviewability:** 5A–5C each introduces at most two new internal boundaries; 5D is evidence/closure only.

No unresolved product decision remains. Candidate measurements may tune numeric timeouts/limits downward, but may not broaden user-visible semantics or increase worker concurrency above one without a new approved decision.
