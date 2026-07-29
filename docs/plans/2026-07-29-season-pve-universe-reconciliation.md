# Current-Season PVE Universe Reconciliation Plan

> **Harness slice:** Strict, read-only authority and differential audit. This
> plan does not sync an external source, mutate PostgreSQL, build a Catalog, or
> deploy a runtime.

**Goal:** Establish a deterministic `SeasonPveUniverseRevision` that can prove,
item by item and source by source, whether the current-season actually
obtainable PVE equipment universe reached staging and the Catalog, was excluded
by a governed rule, or is explicitly blocked.

## Current finding

The existing source policy is not complete enough to support the product
promise:

- production staging currently contains `dungeon`, `raid`, `crafted`,
  `tier_set`, and `observed_profile` source types;
- its active season row is expired;
- the 40-specialization shadow projects the same staging/Catalog source and
  therefore cannot discover an upstream omission;
- the official Midnight Season 1 material also names Delves, world bosses,
  Prey, Great Vault rewards, Catalyst acquisition, Voidforge/Ascendant paths,
  Revelations world activities, Sporefall, and a time-bounded Turbulent
  Timeways reward path;
- a second official-source opposition pass also found current-season
  equipment from core Midnight world quests/rares/events, Midnight Renown
  vendors, and the Chiming Void Curio tier-set vendor transform. These remain
  separate required owners rather than aliases for raid or Revelations
  world-content rows.

Until every required source has an independently enumerated membership
snapshot, the Universe status is `blocked`; an existing Catalog count cannot
upgrade it.

## Contract

The canonical Universe input contains:

- exact `seasonRevision` and `sourcePolicyRevision`;
- every required acquisition source with its authority references,
  membership mode, and effective window;
- discovery status for each source, instance, encounter/difficulty, item
  relation and canonical `progressionState`, cap, pagination cursor, fetch
  failure, and fallback;
- a timezone-bound audit instant plus source evidence capture/valid-until
  instants; empty or expired source snapshots cannot claim completeness;
- exact coverage of every authority reference declared by the source policy;
  an unrelated mirror or partial authority set cannot claim verified;
- staging and Catalog membership snapshots;
- governed exclusions with stable reason code, fact owner, evidence reference,
  and decision time.

Every known member has exactly one outcome:

- `included`: the relation reaches verified staging and the Catalog;
- `excluded`: a governed exclusion supplies all required decision fields;
- `blocked`: evidence, discovery, staging, or Catalog closure is missing or
  conflicting.

The revision is a SHA-256 hash of canonical business content. A report is
`verified` only when every required source is verified, no cap/fetch/pagination
gap exists, every required source has at least one governed member, every
discovered item/progression relation is partitioned exactly once, and no
staging/Catalog relation exists outside independent discovery.

## Tasks

### Task 1 — Freeze the inclusive source-policy boundary

- [x] Add a versioned Midnight Season 1 source-policy artifact covering direct
  drops, reward-pool projections, crafting, transforms, vendors, open-world
  activities, and time-bounded events.
- [x] Require an authority reference and membership mode for every source.
- [x] Treat a missing/expired/not-yet-enumerated source as `blocked`, never as an
  empty verified source.

### Task 2 — Build the deterministic pure reconciler

- [x] RED: a source omitted from discovery blocks the Universe.
- [x] RED: cap, pagination, fetch, and fallback gaps become machine-readable
  blocked ledger members.
- [x] RED: discovered items missing from staging or Catalog remain blocked.
- [x] RED: downstream-only members absent from independent discovery are
  represented once as `DOWNSTREAM_MEMBER_NOT_DISCOVERED`.
- [x] RED: an empty required source, expired/evidenceless source snapshot, or
  non-array member payload cannot be upgraded to verified.
- [x] RED: discovery authority coverage must exactly match the policy-owned
  authority set.
- [x] RED: progression state is part of item-relation identity, so Hero/Myth,
  crafted, and Ascendant states cannot collapse onto one item ID.
- [x] RED: a governed exclusion is accepted only with reason, owner, evidence,
  and decision time.
- [x] RED: the same canonical inputs produce the same revision regardless of
  input order.
- [x] Implement the smallest pure builder; no DB, HTTP, or runtime side effects.

### Task 3 — Add read-only snapshot adapters

- [x] Read a previously captured official discovery snapshot and current
  staging/Catalog snapshot without triggering sync.
- [x] Reject season/source-policy revision drift.
- [x] Emit a bounded JSON report and summary; do not print full source payloads
  into journald.

### Task 4 — Run the current differential audit

- [x] Run a read-only production staging inventory. It currently exposes 84
  crafted, 203 dungeon, 104 raid, 65 tier-set, and 594 observed-profile source
  rows; the active season row expired on 2026-06-25. This is downstream gap
  evidence, not a source-universe snapshot.
- [ ] Obtain the official discovery snapshot only after the repository network
  approval boundary is satisfied.
- [ ] Produce source → instance → encounter/difficulty → item differences.
- [ ] Keep the slice `blocked` while any source membership is unknown, capped,
  failed, stale, or absent from staging/Catalog.
- [ ] Hand each real gap to its upstream owner; do not repair it in a public
  view or Taro.

Observed local guard: with the inclusive 18-source policy and no independently
captured membership snapshot, the builder emits 18/18 `SOURCE_DISCOVERY_MISSING`
source members and a literal `blocked` report. It does not treat the five
currently present staging source types as universe proof.

## Verification

- targeted unit tests for the pure reconciler and adapters;
- deterministic repeat-build hash test;
- real current snapshot report with bounded diagnostics;
- Harness packet at literal `implementation_allowed`, `local_verified`, or
  `blocked` according to the evidence actually obtained;
- local CR and `git diff --check`.

## Stop lines

- no external data download or sync without the required approval;
- no PostgreSQL write, Catalog build, active-pointer change, candidate deploy,
  or DevTools acceptance in this slice;
- no `verified` result derived only from production staging/Catalog counts;
- no silent cap, pagination, fetch, fallback, expired-source, or unknown-source
  omission.
