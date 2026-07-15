# Community Template Import Performance Design

**Date:** 2026-07-15

**Status:** implementation complete; exact runtime candidate `99acc45` local-full verified after repairing a predecessor live scoped-read alias mismatch; replacement candidate deployment and real WeChat acceptance pending

**Harness:** [community-template-import-performance requirement](../../../artifacts/releases/2026-07-15-community-template-import-performance/requirement.json)

**Historical boundary:** [Community Enhancement Editability v2](2026-07-14-community-enhancement-editability-v2-design.md) remains accepted evidence for editable canonical gems, enchants and embellishments. This design replaces only its import-time all-affected-slot hydration behavior; it does not reopen socket authority, observed-only eligibility, Release cutover, or editable-selection semantics.

## 1. User problem and measurable current facts

A player opens a real community template and expects one clear outcome: the build appears promptly, its existing gems, enchants and embellishments are visible as normal selections, and a later tap on a slot allows a normal edit. Instead, the current import can appear frozen and reach the client timeout before anything is applied.

The current path is verified as follows:

1. `applyGearCommunityTemplate` calls `loadCommunityTemplateEnhancementDetails` before applying the template.
2. That helper finds every affected enhancement slot and calls `Promise.all(loadGearSlotDetailForPage(...))`.
3. The investigated Elemental Shaman incident produced one initial request followed by twelve `mode=slot` requests.
4. Each slot is a distinct cache key. The server accepts at most four concurrent gear builds, while the client timeout is 30 seconds.
5. Against the effective production environment, one compact cold `finger1` slot build took 3.731 seconds. The corresponding warm response took 0.097 seconds; it was 625,921 bytes uncompressed and 40,282 bytes compressed.

The small DevTools transfer number therefore does not establish a cheap request. It is the compressed result of a much more expensive release-backed build. The active release currently has 27,949 variants and 19,201 sources, and a slot request constructs a catalog fragment from those immutable facts.

The exact historical cache hit/miss and phase split are not yet observable. The runtime currently exposes neither import-cache metrics nor queue/read/assembly timing. This design adds that evidence rather than guessing which sub-stage dominates every future incident.

## 2. Product contract

### 2.1 Main path

When a player taps an applicable observed community template:

1. The button becomes non-reentrant and shows `正在导入并校验强化…`.
2. The mini-program sends exactly one import request that names the selected class, spec and public template ID. It never sends raw item, enhancement or option values as authority.
3. The backend reads one Active Manifest binding, validates the template is the current winner for that class/spec, reconciles it against the matching immutable Gear Release and invokes existing Resolver ownership.
4. The client atomically applies only the matching verified response: selected gear display records, canonical selected enhancements, resolved signature and ordinary slot rows.
5. When the player later opens an enhancement slot, the already-established lazy `mode=slot` route may load that one slot's option list. Import itself must not prefetch every enhancement slot.

The result is immediately actionable: selected enhancements are shown as canonical selections, not inherited facts. A selected-slot option list may load on demand, exactly as it already does in the normal editor.

### 2.2 Failure and recovery

If the template is no longer active, cannot bind to the current Manifest, has a blocked required item, or includes unrecognized enhancement coverage:

- the backend returns a structured problem or a bounded unresolved-type summary;
- the client retains its previous verified configuration;
- the user sees a plain, retryable explanation rather than a stalled sheet or an apparently successful partial import;
- raw unrecognized values never enter Intent, WXML, Profile, SimC or telemetry payloads.

Rapid import taps continue to use the existing serial/generation fence: only the response belonging to the latest class/spec/template import can commit.

### 2.3 Trust and compatibility boundaries

- Public entry remains `raiderio_observed_profile` winners only.
- All request-time reads remain within the immutable active Gear/Community Release and PostgreSQL; no external fetch occurs.
- The backend owns template applicability, option reconciliation, constraints, legality, resolved signature and Profile-compatible canonical state.
- `mode=initial` and `mode=slot` retain their existing browse/edit contract. This new route is not a general replacement catalog endpoint.
- Release pointer, candidate generation, sync, backfill, cleanup, schema and production writes are out of scope.

## 3. Counterargument and alternatives

### A. Dedicated atomic import snapshot — recommended

Add `POST /api/websim/gear/community-import`. It receives only `{ classKey, specKey, templateId, expectedManifestRevision? }`, performs a scoped immutable release read and canonical Resolve on the server, and returns a compact import snapshot.

This is the only option that removes the client reconstruction loop while preserving the existing backend trust boundary. It also gives the service a narrow, cacheable target: one winner template under one Manifest generation, rather than one generic catalog payload per slot.

### B. Make the existing `mode=slot` route cheaper

This can reduce cost for normal editing and should remain a later engineering-health follow-up. It still leaves the template importer issuing twelve requests, repeatedly acquiring the global gear-build capacity and waiting on the client timeout boundary. It is therefore insufficient as the user-facing fix.

### C. Increase workers, cache entries, or serialize the fan-out

This only moves the queue: more workers raise CPU/memory contention, a larger generic LRU makes eviction less frequent but does not make a cold import cheap, and serial requests make the wait longer. It also offers no atomic import result or visible recovery. Do not choose it as the primary remedy.

## 4. Backend design

### 4.1 Route and response

`POST /api/websim/gear/community-import` uses a structured result envelope with this public shape:

```json
{
  "contractRevision": "websim-community-template-import-v1",
  "status": "verified | partial | blocked",
  "template": {
    "id": "observed_profile_mage_frost",
    "sourceKey": "raiderio_observed_profile",
    "profileHash": "…",
    "gearHash": "…"
  },
  "manifest": {
    "manifestRevision": "…",
    "pointerGeneration": 16,
    "gearCatalogReleaseId": "…",
    "communityTemplateReleaseId": "…"
  },
  "selectedGearBySlot": { "head": { "…": "…" } },
  "resolvedSnapshot": { "…": "existing canonical Resolver result" },
  "unresolvedBySlot": { "…": { "gemCount": 0, "enchantCount": 0, "embellishmentCount": 0 } },
  "warnings": []
}
```

The exact selected-gear display shape follows the current frontend selection contract. The response contains canonical option identity and authoritative display labels through the resolved snapshot, never raw enhancement tokens.

Failures use the existing structured-problem style with stable codes such as `template_not_active`, `template_inapplicable`, `manifest_mismatch`, `template_import_blocked` and `template_import_unresolved`. A failed response never triggers the legacy all-slot fallback.

### 4.2 Scoped immutable read model

Add a dedicated release-store read whose input is `(active binding, classKey, specKey, templateId)`. It must:

1. bind one Active Manifest using the existing integrity checks;
2. locate exactly one active public winner for the requested class/spec/template ID;
3. read only the winner selection, its selected item/variant/source records and applicable option authority from the matching Gear Release;
4. verify row hashes and release compatibility under the same read-only snapshot;
5. return a minimal internal import source model, not `replacementCandidates`, `slotGroups` or a broad catalog.

The current generic `get_websim_gear(..., mode="slot")` path is deliberately not reused for the import. Reusing it would preserve the expensive repeated catalog construction that caused the incident.

### 4.3 Pure reconciliation and Resolver handoff

Introduce one pure backend owner, for example `server/community_template_import.py`:

- normalize the sealed template's known enhancement values;
- match only verified, visible, slot-applicable canonical option records;
- preserve ordered duplicate gem occurrences;
- report unknown values only as bounded type/count evidence;
- construct the canonical selection intent and invoke the existing Resolver path;
- reject any response lacking the expected binding, constraints or canonical selected options.

The module has no database, HTTP, release-pointer or frontend side effect. The scoped store provides immutable rows; `gear_runtime` / `gear_resolver` remain final owners of legality and resolved state.

### 4.4 Cache and instrumentation

Use a separate bounded immutable import-snapshot cache. Its key includes at least Manifest revision, pointer generation, class, spec, template ID and compact contract revision. It never caches malformed, blocked or transiently incomplete results, and must not consume the generic 80-entry slot-payload LRU budget.

The route records bounded performance evidence:

- `queueMs` before and after the gear-build limiter;
- `releaseReadMs` for scoped immutable reads;
- `reconcileMs` and `resolveMs`;
- `serializeMs` and `cache=hit|miss`.

Safe aggregate values may be emitted as `Server-Timing`; structured logs may contain the same numeric fields plus manifest/template identity hashes. They must not include raw values, client content or SQL text.

## 5. Mini-program design

`pages/builds/websim-api.js` receives one `requestWebsimCommunityTemplateImport` wrapper with 30-second transport protection and structured-problem handling. `pages/builds/detail.js` changes community import to:

1. capture the existing import serial/generation fence;
2. set a local importing state and retain the visible template sheet;
3. call the single import route;
4. atomically commit only the matching verified snapshot, then close the sheet;
5. on partial/blocked/error, clear importing state, retain the prior verified build and show a retryable plain message.

`loadCommunityTemplateEnhancementDetails` is removed from the community-template apply path. `loadCommunityTemplateWeaponRepairDetails` is also not a precondition for the new atomic route: backend selection validation owns the complete weapon rule. Both helpers may remain for unrelated normal edit paths only if their callers still require them.

`pages/builds/detail.wxml` binds the affected template button to importing/disabled state and exposes progress or recovery text. It must not expose backend terms such as Manifest, Release, cache or canonical reconciliation.

## 6. Impact map

| Classification | Surfaces | Required proof |
| --- | --- | --- |
| `must_change` | `server/news_backend.py`, scoped `gear_release_store` read, `postgres_cache_store`, pure import projector, `websim-api.js`, `detail.js`, `detail.wxml`, focused tests | New import contract returns one verified snapshot; no all-slot fan-out. |
| `must_not_change` | Active Manifest/pointer, releases, schema, sync/backfill/cleanup, public observed-only policy, initial/slot routes, Profile, Catalyst | API compatibility, 40-spec public shadow, timer/backflow and no-write proof. |
| `risk_unknown` | Minimal resolver/input projection, cold p95 after scoped read, exact needed client display fields | Candidate phase timings, fixture parity and real mini-program smoke. |
| `evidence_required` | client behavior, pure mapping, route envelope, cache, release scope, deployment parity | Targeted tests, one final full CI, candidate cold/warm timings and WeChat proof. |

## 7. Verification and release

### 7.1 Development tests

- Backend: scope/read/hash integrity; exact template ownership; canonical mapping; unknown-value omission; duplicate gems; Resolver parity; cache key/invalidation; timing-header shape; malformed/stale/blocked route cases.
- Frontend: one request per import; no call to all affected slot details; visible importing state; failure preserves previous verified build; latest import wins; later enhancement editing loads only the selected slot.
- Regression: existing Frost Mage `8/8`, `6/8`, `2/2`, replacement, duplicate occurrence and unknown-value tests remain green.

### 7.2 Candidate evidence

One final PR-head candidate is required before merge. It records:

1. branch, commit and runtime file parity;
2. PostgreSQL-only runtime and exact Active Manifest identity;
3. cold and warm community-import timings with phase breakdown;
4. one request per import, no client cancellation and unchanged initial/slot smoke;
5. 40-spec public observed-only shadow and Resolve/Profile compatibility;
6. timer/backflow state, logs and rollback command;
7. real WeChat import plus a selected-slot edit for the frozen Frost Mage reference.

The performance gate is not a fabricated universal number: the candidate must establish and record cold/warm p50/p95 from the new endpoint, demonstrate no 30-second cancellation, and show that import does not emit slot fan-out. The final numeric SLO is set only after the scoped-read baseline exists.

### 7.3 Rollback

The route and client use an additive feature boundary. On a production fault, `feature_hide` returns the community-template action to a plain temporary-unavailable state rather than silently restoring the known twelve-request path. `code_rollback` restores the prior release binary; no data restore or resync is expected because this change has no write scope.

## 8. Explicit non-goals and follow-up

This design does not optimize the generic `mode=slot` route for every normal browsing/editing case. After the atomic import path is live, a separate performance review may reduce generic slot catalog construction and revisit the generic cache budget, using the new phase metrics rather than guesswork.

The user reviewed this written specification and approved the executable [Community Template Atomic Import Implementation Plan](../../plans/2026-07-15-community-template-import-performance-implementation.md) on 2026-07-15. Independent CR found and test-drove a close-while-pending UI recovery fix; the exact runtime candidate `e08cbb8eab4a6d444612995e1681e990690c6d65` then passed its final full Harness (Node `527/527`, Python `1576` with one expected skip, `130/130` commands). Candidate deployment and explicit real-WeChat acceptance remain before merge.
