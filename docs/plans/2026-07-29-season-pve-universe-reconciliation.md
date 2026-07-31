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
- the policy now declares an official effective window for all 19 required
  sources. The nineteenth source is the independently governed Revelations
  Val/Naigtal world-content reward pool; it was previously collapsed into the
  world-boss/core-world-content boundary even though Blizzard documents a
  separate rare-enemy reward path;
- the source policy itself remains `required_membership_discovery`, not
  `approved`, and therefore cannot authorize a verified Universe revision;
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
- the approved isolated official snapshot currently contains 24 Blizzard
  authority pages plus 335 checksum-verified Game Data responses. All 19
  policy authority identities are captured, but only 9 sources have partial
  raw membership and 10 have no official membership API. None of the 19
  sources can yet claim complete membership;
- the snapshot preserves 1,871 raw source relations and 21 explicit gaps:
  progression state, transform eligibility, and source APIs that Blizzard
  does not expose. Current-client joins have already removed the earlier
  Journal difficulty and crafted recipe-output gaps;
- a bounded official `required_level=90 && equippable` opposition set contains
  977 items. Only 256 currently connect to the partial Journal/class-set/craft
  evidence, while 721 still require a source relation or governed exclusion.
  This set is intentionally not treated as the Universe because scaled legacy
  dungeon/Timewalking items can fall outside that search scope;
- the initial `itemId=230000..280000` opposition range was rejected before
  execution: the existing official max-level search already reaches item
  `282426`, and reused legacy/Timewalking identities can sit below the lower
  bound. The replacement capture walks the complete positive ID space through
  ordered capped-page cursors, checksums every response, rejects extra raw
  files, and requires a terminal page. Even that closed all-equippable index
  remains `sourceMembershipComplete=false`;
- that replacement capture is now checksum-closed at 109,786 official
  equippable items, 440 pages, and 407,881,902 persisted response bytes. The
  final uncapped cursor chain has page counts `4 → 3 → 2 → 1` and terminates
  with 36 rows at item `282426`. Exact-head verification links only 1,431
  items to the partial source evidence; 108,355 still require a source
  relation or governed exclusion. The SimC client comparison has 522
  official-only and 4,774 client-only IDs and cannot bridge build
  `67808`/`68887`;
- the Game Data responses self-identify static client build `67808`, while the
  captured SimC client data identifies live hotfix build `68887`. That
  mismatch is recorded as an evidence blocker rather than hidden by the common
  capture date;
- official profession discovery yields 172 non-PvP equipment recipe
  candidates. Current-client build 68887 now proves one output item per recipe,
  and the checked-in candidate authority governs all 172: 106 customizable
  two-secondary items, 38 Engineering single-secondary items, and 28
  fixed/recipe-defined-stat items. The allowlist differential is verified at
  zero missing, zero extra, and zero unsupported;
- current-client build 68887 also closes every captured Journal relation by
  `source + instance + encounter + item`, producing 1,412 unique governed
  difficulty relations across all six Journal-backed sources. This removes the
  six Journal-difficulty gaps without treating progression as known.
- a second bounded current-client pass captured seven additional official DB2
  files, bringing the isolated raw DB2 set to 58. It found one expansion-11
  Mythic+ season candidate with a complete `+2..+10` weekly-reward ladder, but
  every end-of-run reward level is `0` and no official season-name join binds
  numeric season `117` to Midnight Season 1. `RenownRewards` identifies four
  level-90 power unlocks—necklace, waist, head, and trinket—and three Delve
  progression unlocks, but every relevant row has `item_id=0`. The
  fail-closed investigation therefore remains `blocked` and closes none of the
  21 remaining gaps; the exact remaining owners are the current-season
  activity/reward join and vendor-stock/item relations.
- after explicit user approval, the isolated evidence set pins the minimum
  schema aid and license from
  `wowdev/WoWDBDefs@b207ddd46e9e5350d262c2bd8e3d6181c5561aba`.
  The definitions establish layouts only: unknown fields remain named
  `unverified_*`, no third-party code executes, and the schema aid may not
  establish official membership;
- three additional official join tables plus the pinned layouts now produce a
  checksum-bound 10/10-table parse of every unencrypted record. The
  `CollectableSourceVendor → CollectableSourceInfo →
  ItemModifiedAppearance` chain reaches 19,309 official equippable candidates
  after the corrected partial re-extraction,
  including 374 required-level-90 items, while `QuestPackageItem` reaches
  11,058 candidates. Those sets contain legacy, PvP, and non-current-season
  equipment and still lack an authoritative current-season PVE vendor identity
  or quest-to-package join, so their promotable member count is exactly zero;
- WDC5 section accounting also exposes 178 encrypted records across the
  membership-chain tables. The corrected extractor and parser recover 114;
  64 remain unavailable and cannot be treated as irrelevant. The fail-closed relation
  audit therefore records four blockers:
  `CURRENT_CLIENT_ENCRYPTED_SOURCE_RECORDS_UNAVAILABLE`,
  `CURRENT_QUEST_PACKAGE_RELATION_UNAVAILABLE`,
  `CURRENT_SEASON_PVE_VENDOR_IDENTITY_UNAVAILABLE`, and
  `THIRD_PARTY_SCHEMA_FIELDS_UNVERIFIED`. The exact-head official evidence
  rebuild binds this audit at 21 gaps before, zero resolved, and 21 after;
  no relation candidate mutates the Catalog or a release pointer.
- the official current-client `TactKey` and `TactKeyLookup` tables were then
  captured and parsed inside the same isolated boundary. Their 24 static key
  rows and 204 lookup rows form 24 joins, but they contain zero of the 12 key
  identities required by the 178 encrypted membership-chain records. The
  checksum-bound coverage audit therefore reports `0/12` required keys and
  `0/178` covered records, emits no key material, and remains blocked by
  `CURRENT_CLIENT_STATIC_TACT_KEYS_INCOMPLETE`. This rules out a missed static
  client-table join as the cause without pretending that the encrypted rows
  are irrelevant; server-delivered hotfix cache or another authoritative key
  source remains an upstream requirement.
- under the user's separate approval, fixed
  `wowdev/TACTKeys@c034041cc4570016d845e2cb711d684b5e0a74bf` was first
  used in a transient isolated extractor. That v4 run exposed a deeper
  representation bug: WDC5 stores the key identity as a little-endian uint64
  while BLTE exposes the original eight bytes. Direct string comparison falsely
  reported zero overlap, but byte reversal maps all 12 WDC5 identities to all
  12 BLTE identities exactly. The old namespace-mismatch conclusion is
  withdrawn.
- after the user authorized all necessary in-Goal operations without repeated
  approval prompts, the exact repository head
  `wowdev/TACTKeys@a3449fd5cfc3a0053cbff2c65f7d16166774cbf9` was captured
  transiently and then deleted. Its 981,450-byte, 19,629-line body has SHA-256
  `e4fe2fd39ccc43b5ee14b1ced69dce9f21d4d90267a8a3e2bbb2b953597f55f9`
  and proves 9-of-12 WDC5 record keys covering 114-of-178 records, not merely
  the earlier diff inference. After byte-order mapping, the isolated SimC
  keyfile resolves 9-of-12 BLTE identities; the v5 extractor decrypts 17-of-20
  chunks and the parser recovers exactly 114 records across the four tables.
  Three keys, three chunks, and 64 records remain unavailable. The 114 recovered
  rows add 6 source-info, 17 vendor, 17 vendor-sparse, and 74 appearance rows;
  39 appearance items match the official all-equippable index, but all are
  level 1 and source-unlinked cosmetics/transmog, while the source chain links
  only two participation tabards and no level-90 PVE equipment. Zero rows are
  promoted and the 21-gap Universe remains blocked. Raw/key material and the
  cloud transient workset were deleted after the audit.
- the exact current TACTKeys head was then compared with every build-68887
  cache exposed by the current Raidbots lists: 9 verified retail/enUS caches
  and all 98 opt-in retail caches. The serial in-memory target-table scan had
  zero fetch failures, read 298,323,339 bytes in total, and persisted no raw
  cache or complete key output. Both cache corpora cover only 6-of-12 target
  keys and 82-of-178 records, entirely inside the public head's 9-of-12 and
  114-of-178 coverage. They add zero keys, so the combined upstream-source
  boundary still lacks the same three identities and 64 records. This proves
  that the current public head and published exact-build cache corpus do not
  close the gap; it does not prove that region-, account-, entitlement-, or
  content-gated server delivery can never supply them.
- all 24 captured Blizzard authority pages were also scanned for embedded
  item links. Only nine distinct item IDs occur: eight are mount, PvP,
  visual-effect, or cosmetic rewards; `249367` is the Chiming Void Curio token
  relation already present in the current-client Journal evidence. The page
  corpus enumerates no new PVE combat-equipment member and closes zero of the
  21 gaps.
- the refreshed official-page set now includes the Revelations-live overview
  and the July 28 hotfix published on July 29. The hotfix confirms that the
  current Val/Naigtal world-boss reward is matched to the player's chosen
  specialization. The detailed Blizzard pages still describe Ritual Sites,
  Lost Armaments, Val/Naigtal world bosses, Voidforge, and Prey as dynamic
  loot-specialization or warband reward pools without enumerating their combat
  item members. This improves the eligibility and freshness evidence but does
  not turn any source-membership gap into a complete list.

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
- [x] Treat a missing or malformed source `effectiveWindow` as `blocked`, and
  exclude a well-formed source that is outside its declared window from the
  current-obtainability universe.

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
- [x] Obtain the official discovery snapshot after explicit repository network
  approval. It remains isolated evidence only and has not been synchronized to
  production or promoted to an active pointer.
- [x] Capture and checksum-close the official all-equippable Item Search index
  under the Goal audit directory after the cloud `MemAvailable >= 2 GiB` gate
  and the currently running scheduled SimC job finish.
- [ ] Produce source → instance → encounter/difficulty → item differences.
- [x] Keep the slice `blocked` while any source membership is unknown, capped,
  failed, stale, or absent from staging/Catalog.
- [ ] Hand each real gap to its upstream owner; do not repair it in a public
  view or Taro.

Observed current guard: all 19 source windows are explicit, but the policy is
still unapproved and the isolated official projection is literally `blocked`:
`completeSourceCount=0`, `partialSourceCount=9`,
`blockedSourceCount=10`, and `gapCount=21`. The exact-head Universe adapter
therefore emits 19 blocked source rows, all 21 named upstream gap rows, and one
policy-approval row rather than flattening the snapshot into missing discovery.
The official item opposition is also blocked at 108,355 unresolved candidates
inside the checksum-closed 109,786-item all-equippable index; the older
level-90-only opposition remains 721 unresolved out of 977. The crafted
allowlist diff is verified at 172/172, while the overall Universe remains
blocked by progression, transform eligibility, source membership, and client
build parity. The current-client progression investigation is preserved at
`official-client-db2-v1/current-client-progression-investigation.json`; it
records a 9-row weekly Mythic+ ladder, 4 unresolved Renown power unlocks, and
literal upstream blockers instead of treating the newly captured tables as
membership closure. These results do not treat
the five currently present production staging source types, either official
item opposition scope, or the 40-specialization Catalog projection as universe
proof. Catalog 回填也不得把槽位类别当成 transform eligibility：当前
membership seed 不再自动生成 `crafted_void_upgrade`，且 SimC 静态属性
成功不能覆盖 `OFFICIAL_PROGRESSION_STATE_UNAVAILABLE`；只有独立上游
eligibility/progression 关系闭合后才能解除对应 blocked 状态。
The pinned source-relation evidence is preserved at
`official-client-db2-v1/current-client-source-relations-audit.json`, while
`current-client-source-relations-verification.json` binds its SHA-256 to the
rebuilt membership snapshot and item opposition. It verifies 10 tables, 114
recovered plus 64 unavailable encrypted relationship records, 19,309 vendor-chain candidates,
11,058 quest-package candidates, zero promotable members, and no change to the
21-gap ledger. The same verification now binds
`official-client-db2-v1/current-client-tact-key-coverage.json`: 24 static key
rows, 204 lookup rows, 12 required key identities, zero present keys, zero
covered records, while the static source alone still cannot decrypt any record. It also
binds
`official-client-db2-v1/current-client-public-tact-key-reextract-audit.json`:
9 of 12 public record keys, 114 of 178 record identities covered, all 12
record identities byte-order-mapped to the 12 observed BLTE identities, 20
encrypted chunks, 17 key hits/decryptions, 3 zero fallbacks, 114 recovered
records, 64 unavailable records, and no production or release-pointer mutation.

## Verification

- targeted unit tests for the pure reconciler and adapters;
- deterministic repeat-build hash test;
- real current snapshot report with bounded diagnostics;
- Harness packet at literal `implementation_allowed`, `local_verified`, or
  `blocked` according to the evidence actually obtained;
- local CR and `git diff --check`.

## Stop lines

- necessary in-Goal downloads and fixed-source audits are authorized without
  repeated prompts, but raw key material must remain transient and all
  persisted evidence must stay isolated, checksum-bound, and key-free;
- no PostgreSQL write, Catalog build, active-pointer change, candidate deploy,
  or DevTools acceptance in this slice;
- no `verified` result derived only from production staging/Catalog counts;
- no silent cap, pagination, fetch, fallback, expired-source, or unknown-source
  omission.
