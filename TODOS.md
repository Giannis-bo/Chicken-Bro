# TODOS

## Equipment Simulator

### Activate the 12.1 Catalyst retained-secondary-stat overlay

**What:** Implement and enable the `preserve_base_secondary_stats` tier overlay for 12.1 Catalyst conversions.

**Why:** Support converting a non-tier item into its tier identity while retaining the base item's secondary stats, without weakening legality, attribute, evidence, or SimC trust boundaries.

**Context:** Equipment Simulator Phase 0-5 is complete and archived; this Phase 6 item is not an active milestone. The current-season workbench continues to expose fixed tier items directly and does not need a conversion control. The 12.1 conversion UI must remain disabled until the active catalog provides a sourced overlay policy, the canonical Resolver produces the expected attributes and Evidence Claims, the backend Serializer emits the supported SimC representation, the active SimC runtime passes real fixture smoke, and the active Season Manifest binds the verified capability revision. An allowlist entry or patch-version check is not activation evidence; current health must remain `capabilityEnabled=false`, `frontendMaySynthesize=false` and `failClosed=true`.

**Effort:** L
**Priority:** P1
**Depends on:** Canonical Gear Instance Resolver, versioned legality rule matrix, backend SimC Serializer, Catalyst Capability Proof Matrix, and active Season Manifest.
**Blocked by:** Confirmed 12.1 conversion semantics, verifiable catalog fields, and stable SimC runtime support.

### Retire the legacy synchronous gear-stats endpoint

**What:** Retire the legacy synchronous `/api/websim/gear/stats` endpoint after the asynchronous stat-snapshot API and migrated mini-program clients are proven stable.

**Why:** Remove the remaining path that runs SimC in an HTTP request lifecycle and avoid permanently maintaining two execution contracts, two response shapes, and two serializer call paths.

**Context:** The compatibility endpoint retains its response shape, lightweight `stat_snapshot_v1` execution mode and global concurrency limit. The active frontend now uses `/api/websim/gear/stat-snapshots` backed by the PostgreSQL snapshot store and systemd worker; Phase 5D observed zero new-frontend legacy traffic while the bounded legacy telemetry count stayed at one. Observe client-version and endpoint-call telemetry for at least two client release cycles, define an explicit retirement threshold and rollback plan, then deprecate and eventually return `410 Gone` for the legacy route. New frontend code must not call the legacy endpoint.

**Effort:** M
**Priority:** P2
**Depends on:** PostgreSQL stat-snapshot store, `wow-gear-stat-snapshot-worker.service`, asynchronous snapshot API, structured-problem client mode, new gear workbench rollout, and client-version/request telemetry.
**Blocked by:** Remaining traffic from mini-program versions that still depend on the synchronous response contract.

## Completed
