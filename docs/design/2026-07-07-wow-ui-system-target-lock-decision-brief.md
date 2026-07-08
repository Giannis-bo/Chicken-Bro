# WOW UI System Target Lock Decision Brief

Status: `target_lock_decision_brief`
Created: 2026-07-07

Artifact manifest: `artifacts/ui-system-rebuild/20260707-target-lock-decision-brief/manifest.json`

This brief is the compact decision packet to show before target lock. It does not create `target_locked`, does not activate an implementation permit, does not authorize page integration, and does not prove runtime verification.

## Codex Goal Context

The active Codex goal is `WOW 小程序 UI 系统重建`: stop pass36/pass37 page-level repair and rebuild the app through component owners, imagegen low-semantic material, real WoW source maps, target lock, one active permit, component/browser precheck, real mini-program screenshots, overlay/red-zone/scorecard, route smoke and DevTools action ledger.

Current flags remain:

- `targetLocked=false`
- `activeImplementationPermit=false`
- `pageIntegrationAllowed=false`
- `runtimeVerified=false`
- `finalAccepted=false`

## Recommended Target

Recommended target: `A-Cockpit + B-Ledger + C-Captain`.

Meaning:

- `A-Cockpit`: App shell, high-density first-screen scanning and strong surface hierarchy.
- `B-Ledger`: source state, blockers, coverage, checkedAt and veteran-player evidence rows.
- `C-Captain`: Chickenbro, task queue, novice next action and contextual follow-up language as first-class surfaces.

This is the direction already described in [Target Lock Proposal](2026-07-07-wow-ui-system-target-lock-proposal.md) and verified as ready-for-decision by [Target-Lock Readiness Preflight](2026-07-07-wow-ui-system-target-lock-readiness-preflight.md).

## Decision Options

| Option | User Meaning | Next Allowed Action |
| --- | --- | --- |
| Confirm recommended target | Lock `A-Cockpit + B-Ledger + C-Captain` as the product/UI direction. | Write a `target_locked` decision record, then convert exactly one draft permit to active. |
| Confirm with modifications | Lock the direction with explicit written changes. | Write a modified `target_locked` decision record and update the activation packet before page edits. |
| Reject or revise target | Keep target unlocked. | Return to design candidates or target proposal revision; no page integration. |

Sufficient confirmation text examples:

- `确认 A-Cockpit + B-Ledger + C-Captain 为 target lock`
- `按 readiness review 的推荐方向锁定`
- `锁定，但做这些修改：...`

Insufficient signals:

- `继续`
- ambiguous approval
- passing tests
- browser/component precheck
- Codex confidence
- continuation turn

## First Surface

Recommended first active surface after target lock: `news_list_detail`.

Reason:

- `ArticleListBoard` and `ArticleReader` owner skeletons exist.
- Fixture matrix and component precheck exist.
- Route smoke scene ids are stable.
- The surface is bounded and protects source translation, fallback, source proof and copy-source behavior.

Planned active permit after target lock:

- `docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit.md`
- `artifacts/ui-system-rebuild/20260707-news-list-detail-active-permit/manifest.json`

## Material Asset Boundary

Imagegen remains in the workflow, but only as low-semantic material seed and later production material. The current seed is:

- `artifacts/ui-system-rebuild/20260707-material-asset-seed/manifest.json`
- expected status: `material_asset_seed_ready`
- expected flags: `productionManifest=false`, `pageDirectUseAllowed=false`, `productionUseAllowed=false`

Allowed material classes:

- `panel`
- `border`
- `texture`
- `socket`
- `state-base`
- `state-atomic`
- `decorative`

Generated material must not contain real WoW objects, source logos, visible text, fake chrome, business conclusions or generated fact icons.

## Production Asset Manifest Gate

Before any page integration, the active surface must produce and pass a real production asset manifest:

- template: `docs/design/2026-07-07-wow-ui-system-production-asset-manifest-template.md`
- preflight: `node scripts/ui-system-production-asset-manifest-preflight.js --require-production-manifest --json`
- runtime path: `artifacts/ui-system-rebuild/runtime/production-asset-manifest.json`

The production manifest must derive from material seed recuts and record exact file paths, dimensions, owners, fit strategy, allowed surfaces, package budget and semantic safety flags. Whole-page target images, pass36/pass37 assets and reference-only generated images cannot enter pages.

## Real WoW Source Map Gate

Real WoW objects cannot come from imagegen, target screenshots or page-private fallback art.

Before any page integration, the active surface must produce and pass a runtime source map:

- seed: `artifacts/ui-system-rebuild/20260707-real-wow-source-map-seed/manifest.json`
- template: `docs/design/2026-07-07-wow-ui-system-real-wow-source-map-template.md`
- preflight: `node scripts/ui-system-real-wow-source-map-preflight.js --require-source-map --json`
- runtime path: `artifacts/ui-system-rebuild/runtime/real-wow-source-map.json`

The runtime source map must cover class, spec, hero, talent, spell, item, source, dungeon, raid and affix objects when they appear in integrated pages. Allowed source classes are `api`, `battlenet`, `websim`, `repo_verified` and `user_provided`.

## Page Integration Gate

Page integration remains forbidden until all of these exist:

- explicit user target-lock confirmation or written modification;
- valid `docs/design/2026-07-07-wow-ui-system-target-locked-decision.md`;
- exactly one active implementation permit;
- passing active permit preflight;
- passing production asset manifest preflight;
- passing real WoW source map preflight;
- passing page adoption preflight for the permitted surface.

Pages may compose owner components, bind real data and handle routes. Pages may not patch component internals, split state visuals, create page-private article rows, use direct generated material, or restyle owner geometry to fix layout.

## Runtime Evidence Gate

After permitted page integration, runtime acceptance still requires:

- real WeChat mini-program screenshots after `captureSafe=true`;
- compact / standard / large viewport evidence;
- component crops;
- target/current/implementation comparison;
- overlay and red-zone reports;
- visual scorecard;
- route smoke execution manifest;
- DevTools action ledger.

Browser screenshots, component precheck, static tests, old pass screenshots and subjective scores are not runtime verification.

## Non-Promotion Boundary

This brief proves only `target_lock_decision_brief`.

It cannot prove:

- `target_locked`
- `active_implementation_permit`
- `page_integration`
- `runtime_verified`
- `final_accepted`

## Next Required Evidence

The next valid external evidence is explicit user target-lock confirmation or written modification. If that happens, write the target-locked decision record using [Target-Locked Decision Template](2026-07-07-wow-ui-system-target-locked-decision-template.md), then validate it with:

```bash
node scripts/ui-system-target-lock-decision-preflight.js --require-decision --json
```
