# WOW UI System Gear Detail Implementation Permit Draft

Status: `implementation_permit_draft`

This is the single-surface permit draft for rebuilding the gear detail / gear simulator page inside the WOW mini-program UI system. It is not `target_locked`, not an active implementation permit, and does not authorize page WXML/WXSS edits.

## Linked Control Plane

- [WOW 小程序 UI 系统重建完整 Goal](2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Phase 1/2 Inventory](2026-07-07-wow-mini-program-ui-system-rebuild-phase1-inventory.md)
- [Target Lock Proposal](../design/2026-07-07-wow-ui-system-target-lock-proposal.md)
- [Foundation Component Contracts](../design/2026-07-07-wow-ui-system-foundation-component-contracts.md)
- [Asset Manifest Draft](../design/2026-07-07-wow-ui-system-asset-manifest-draft.md)
- [Implementation Permit Coverage Matrix](../design/2026-07-07-wow-ui-system-implementation-permit-coverage-matrix.md)
- [Route Smoke And Runtime Verification Plan](../design/2026-07-07-wow-ui-system-route-smoke-plan.md)
- [Production Component Precheck](../design/2026-07-07-wow-ui-system-production-component-precheck.md)
- [Browser Component Precheck](../design/2026-07-07-wow-ui-system-browser-component-precheck.md)
- [Gear Detail Owner Skeleton Source Precheck](../design/2026-07-07-wow-ui-system-gear-detail-owner-skeleton-precheck.md)
- [Gear Detail Component Precheck](../design/2026-07-07-wow-ui-system-gear-detail-component-precheck.md)
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-gear-detail-permit-draft/manifest.json`

## Surface

Surface: `gear_detail`

Route:

- `/pages/builds/detail?query=gear`

Reason to draft this now:

- It is the next missing permit in the current implementation permit coverage matrix after the talent simulator draft.
- It owns the most sensitive real-item UI: 16-slot readiness, real replacement candidates, item-level variants, crafted stat choices, sockets, enchants, embellishments, community imports, personal templates, stat snapshots and SimC handoff.
- It is the gear upstream for workbench readiness and SimC template submission, so fake icons, fake BiS language, weakened save gates or broken item-picker geometry can corrupt the whole product path.

## Current Source Findings

These findings are diagnostic evidence, not permission to patch:

- `pages/builds/detail.wxml` directly composes `gear-panel`, `gear-request-alert`, `gear-attribute-panel`, `gear-attribute-grid`, `gear-slot-grid`, `gear-slot-card`, `gear-icon-frame`, `gear-template-actions`, `gear-save-template-sheet`, `gear-slot-sheet`, `gear-candidate-list`, `gear-candidate-row`, `gear-variant-track-grid`, `gear-crafted-stat-chip`, `gear-enhancement-sheet` and `gear-community-template-sheet`.
- `pages/builds/detail.wxss` owns gear attribute panel, slot card, icon socket, enhancement badge, candidate row, variant card, crafted stat chip, community import sheet, save sheet, fixed action and bottom sheet geometry with page-private classes.
- `pages/builds/detail.js` uses `requestWebsimGear()` and `requestWebsimGearStats()` to build the gear read model and verified stat snapshot path.
- `pages/builds/detail.js` keeps `gearPayloadCache`, `gearSlotCandidateCache`, `gearInitialLoading`, `gearDataFallback`, `gearStatSnapshot`, request signatures and request serials so heavy candidate payloads do not enter `setData`.
- `pages/builds/detail.js` builds derived state through helpers such as `buildGearSlotRows()`, `buildGearAttributePanel()`, `buildGearSlotSheet()`, `buildGearEnhancementSheet()`, `gearCommunityTemplatesForPayload()`, `gearTemplateSnapshot()`, `prunedGearSelectionByWeaponRule()`, `prunedEnhancementBySlot()` and `gearStatsRequestForPage()`.
- The current tests cover source-reference gear, missing/untrusted slots, heavy candidate cache behavior, catalog fallback, stat snapshot request gates, crafted stat selection, variant selection, DK runeforge warnings, embellishment cap, primary stat gem uniqueness, community template overlay, personal template import and save serialization.
- The page blocks saving or applying when required gear slots are missing, candidates are untrusted, variants or crafted stats are not selected, enhancement state exceeds caps, backend fallback is active, or the selected gear cannot form a SimC-ready structured snapshot.
- Saved gear templates store a structured `gearBySlot` and `enhancementBySlot` snapshot, with verified stat snapshot metadata kept separately; the raw snapshot does not become a fake DPS or ranking result.
- Real item icons are attached through `attachGameAsset()` as gear/item assets; missing icons must fall back to text.

## Target Dependency

This draft assumes the target proposal direction `A-Cockpit + B-Ledger + C-Captain`, but it cannot activate until the user confirms or edits the target lock.

Required before activation:

- `target_locked` design for the gear loadout board, attribute summary, 16-slot grid, slot states, item picker, candidate detail, variant selector, crafted stat selector, enhancement sheet, community import sheet, personal template import and save sheet.
- Accepted or revised asset manifest with production / quarantine / real source-map sections.
- `GearLoadoutBoard` owner skeleton and fixture matrix remain valid after target lock.
- `GearConfigSheet` owner skeleton and fixture matrix remain valid after target lock.
- Clean gear-detail surface component precheck rerun before activation.
- Explicit user or owner approval to convert this draft into an active implementation permit.

## Current Owner Evidence

`GearLoadoutBoard` and `GearConfigSheet` now have source-level owner skeletons, fixture matrix and browser/component precheck evidence:

- [Gear Detail Owner Skeleton Source Precheck](../design/2026-07-07-wow-ui-system-gear-detail-owner-skeleton-precheck.md)
- [Gear Detail Component Precheck](../design/2026-07-07-wow-ui-system-gear-detail-component-precheck.md)
- `artifacts/ui-system-rebuild/20260707-gear-detail-owner-skeleton/manifest.json`
- `artifacts/ui-system-rebuild/20260707-gear-detail-component-precheck/manifest.json`

The component precheck currently records `failures=0`, `warnings=0`, 3 viewport screenshots, 10 component crops, `pageIntegration=false`, `runtimeVerified=false` and `devtoolsTouched=false`. This upgrades the surface evidence to `surface_component_precheck`, but it still does not activate page implementation.

## Intended Component Owners

| Owner | Role On Gear Detail |
| --- | --- |
| `PageFrame` | Route gutters, scroll bounds, safe-area, bottom sheet clearance and tabBar-aware spacing. |
| `WowPanel` | Attribute summary shell, evidence sections, sheet shells and panel structure. |
| `GearLoadoutBoard` | Surface-specific owner for 16-slot grid, slot dimensions, slot status, icon sockets, equipment/enhancement badges and touch targets. |
| `GearConfigSheet` | Surface-specific owner for candidate list, item detail, filters, variant tracks, crafted stat chips, enhancement groups, community import and fixed sheet actions. |
| `GameObjectIcon` | Real item icon sockets and text fallback only from payload/mapping/repository/user-provided source. |
| `StatusVisual` | Loading, blocked, partial, source_reference, fallback, verified and save-readiness status labels. |
| `ActionButton` | Save, import, reset, apply candidate, confirm enhancement and sheet primary/secondary actions. |
| `EvidenceLedger` | Slot readiness, catalog status, stat snapshot, blockers, source-reference rows and checkedAt/source rows. |
| `ModuleCard` | Compact gear-summary modules where the target design needs scannable cards. |
| `MaterialImage` | Low-semantic panel/background/socket material through component-owned fit and opacity. |

Pages may bind selected class/spec/hero, active query, gear payload, selected gear, enhancement records, sheet visibility, candidate selection, template actions and route events, but may not own gear grid geometry, icon sockets, slot cards, badge geometry, candidate list tracks, sheet layout, fixed actions, evidence-row tracks or material fit.

## Proposed Allowed Files After Activation

These files would be allowed only after this draft becomes an active permit:

- `pages/builds/detail.wxml`
- `pages/builds/detail.wxss`
- `pages/builds/detail.js`
- `pages/builds/detail.json`
- `pages/builds/websim-api.js` only if existing client shape needs UI-facing normalization and no backend contract changes are introduced
- `pages/common/game-asset.js` only for source-map/fallback wiring, not generated fake item icons
- `components/page-frame/*`
- `components/wow-panel/*`
- `components/gear-loadout-board/*`
- `components/gear-config-sheet/*`
- `components/game-object-icon/*`
- `components/status-visual/*`
- `components/action-button/*`
- `components/evidence-ledger/*`
- `components/module-card/*`
- `components/material-image/*`
- narrowly scoped `tests/builds-page.test.js`, `tests/frontend-api-client.test.js` and UI-system tests
- Gear-detail-specific browser/runtime evidence under `artifacts/ui-system-rebuild/`

Any change outside this list requires a revised permit.

## Forbidden Files And Actions

- No `app.json` route or tabBar changes.
- No `project.config.json` / appid / DevTools shadow changes.
- No backend API contract changes.
- No unrelated workbench, builds tab, talent simulator, SimC, Chickenbro, task detail, profile or news page edits.
- No page-private 16-slot grid, slot card, icon socket, candidate row, variant chip, crafted stat chip, enhancement group, status, action button, evidence row, bottom sheet, fixed action or material geometry.
- No direct page reference to quarantine assets, whole-page target images or pass-named generated glyphs.
- No generated item, source, dungeon, raid, class, spec or hero icon pretending to be real WoW evidence.
- No fake DPS, damage preview, BiS label, comprehensive score, S/A grade, percentile, ranking, popularity, official badge or upgrade-priority claim.
- No weakening SimC-ready slot validation, apply-candidate trust gates, crafted stat gates, variant gates, enhancement caps, source-reference blockers, save-readiness rules, stat snapshot request gates or community import safety.
- No raw backend payload, raw internal blocker key, token, openid, user id or database id in visible UI.
- No WeChat DevTools open/close/restart/cache-clear/login/logout actions.

## Data Boundary

Allowed data sources:

- Existing `fallbackBuildsDetail()` / current detail fallback and current route query state.
- Existing `requestWebsimGear()` payload for slots, slot groups, equipped set, replacement candidates, community templates, community sync state, readiness, catalog status, checkedAt, blockers, item database revision and variant revision.
- Existing `requestWebsimGearStats()` payload for verified SimC stat snapshot only; it must not become DPS, ranking, percentile or upgrade priority.
- Existing local and remote gear template storage through `listBuildTemplates('gear')` and `syncBuildTemplate()`.
- Existing `attachGameAsset()` / `GameObjectIcon` path for item icon source and fallback.
- Existing gear helper paths for slot rows, attribute panel, candidate sheet, enhancement sheet, community template import, snapshot serialization and SimC handoff.

Required UI mapping:

- `from_workbench`: show bounded class/spec/hero/scenario context and return language, not raw profile data.
- `gear_initial_loading`: show stable loading shell for current class/spec without fake slot items.
- `gear_payload_fallback`: show backend/WebSim fallback reason and keep save/import/apply disabled where the current code blocks it.
- `catalog_blocked_or_partial`: show catalog status, blockers and source rows without presenting missing data as zero quality.
- `slot_grid_ready`: show 16-slot board or the canonical slot set returned by the payload with stable card dimensions.
- `slot_missing`: show missing slot and affected save/SimC readiness in user language.
- `slot_source_reference`: show source-reference item as usable reference, not verified BiS.
- `candidate_list_empty`: show empty source/candidate state without fake item suggestions.
- `candidate_selected`: show selected item details, real icon/text fallback, item level, source status and verified detail rows.
- `candidate_untrusted`: keep apply disabled and explain source or SimC-readiness blocker.
- `variant_required`: keep apply disabled until a verified variant track is selected.
- `crafted_stat_required`: keep apply disabled until a verified crafted stat option is selected.
- `candidate_apply_blocked`: show blocker and keep sheet action disabled.
- `candidate_apply_ready`: allow apply only after trust, variant and crafted-stat gates pass.
- `enhancement_sheet_ready`: show socket, enchant and embellishment groups from backend readable display evidence.
- `enhancement_over_cap`: keep confirm blocked and explain the cap.
- `enhancement_stale_pruned`: show that incompatible off-hand, enchant or enhancement state was pruned after weapon changes.
- `community_missing_credentials`: show source dependency, not zero sample popularity.
- `community_source_reference_blocked`: keep import blocked when template is source_reference only or missing required evidence.
- `personal_template_import`: overlay saved gear onto the current baseline without corrupting untouched slots.
- `community_template_import`: overlay community gear onto the current baseline only when canApplyGear is true.
- `stat_snapshot_loading`: show stat snapshot request in progress without DPS preview.
- `stat_snapshot_verified`: show verified attribute metadata and checkedAt/source without presenting it as performance score.
- `stat_snapshot_blocked`: show localized stat snapshot blockers and keep SimC readiness honest.
- `save_blocked_missing_slots`: list missing slots in user language and keep save disabled.
- `save_blocked_untrusted_slots`: list untrusted/source-reference slots and keep save disabled.
- `save_ready`: open save sheet only after structured snapshot is SimC-ready under current rules.
- `template_saved`: close save sheet and surface saved status without mutating selected gear.
- `simc_handoff`: navigate to existing SimC route with bounded context only after the current saved/selected template gate allows it.

Forbidden product claims:

- No DPS, damage, ranking, percentile, tier, S/A grade, comprehensive score, BiS, popularity or upgrade priority.
- No fake official, verified, community, dungeon, raid or source logo.
- No real WoW icon unless it comes from payload, Battle.net/WebSim mapping, repository verified asset or user-provided source.
- No community popularity claim unless payload provides sample count, source, checkedAt/source window and status.
- No raw internal blocker keys or raw backend payload fields in user text.

## Asset Boundary

Allowed:

- Low-semantic panel, border, texture, socket, divider and decorative material after manifest approval.
- Real item/source icons through verified source map and `GameObjectIcon`.
- Text fallback for missing item/source icons.
- Slot/socket material only through `GearLoadoutBoard` and `GameObjectIcon`.
- Status material only through `StatusVisual`.

Forbidden:

- Imagegen item/source/dungeon/raid/class/spec/hero icons.
- Imagegen item names, item levels, source names, DPS, scores, labels or business conclusions.
- Whole-page target images or contact sheets in production WXML/WXSS.
- Fake time, battery, Wi-Fi, phone frame or WeChat capsule.
- Direct `ui-redesign` or `ui-v2-1-slices` page references outside active permit production manifest entries.

## Route Smoke Scope

Required scenes after implementation:

- `gear_detail_from_builds`: `/pages/builds/detail?query=gear&spec=<spec>` loads selected class/spec context.
- `gear_detail_from_workbench`: `/pages/builds/detail?query=gear&from=workbench&spec=<spec>` keeps bounded return context.
- `gear_initial_loading`: first loading shell is stable.
- `gear_payload_fallback`: fallback payload explains blocker and does not enable unsafe actions.
- `gear_catalog_blocked_or_partial`: catalog blockers are visible without fake quality scores.
- `gear_slot_grid_ready`: real slot board renders without overflow.
- `gear_slot_missing`: missing slot state is visible and blocks save readiness.
- `gear_slot_source_reference`: source-reference slot state is visible and not promoted to verified.
- `gear_slot_sheet_empty`: empty candidate sheet has stable layout.
- `gear_candidate_detail`: candidate detail rows, icon fallback and source state render.
- `gear_variant_required`: variant selector blocks apply until selected.
- `gear_crafted_stat_required`: crafted stat selector blocks apply until selected.
- `gear_candidate_apply_blocked`: candidate apply gate stays disabled with explanation.
- `gear_candidate_apply_ready`: candidate apply updates selection and closes sheet.
- `gear_enhancement_sheet`: socket, enchant and embellishment groups render from readable backend evidence.
- `gear_enhancement_over_cap`: embellishment cap blocks confirm.
- `gear_enhancement_stale_pruned`: incompatible off-hand/enhancement state is pruned and explained.
- `gear_community_missing_credentials`: missing source credentials show partial/blocked copy.
- `gear_community_source_reference_blocked`: source-reference community template stays blocked.
- `gear_personal_template_import`: personal template overlays selected slots safely.
- `gear_community_template_import`: community template overlays selected slots safely.
- `gear_stat_snapshot_loading`: stat snapshot loading does not show DPS preview.
- `gear_stat_snapshot_verified`: verified stat snapshot metadata renders as evidence, not score.
- `gear_stat_snapshot_blocked`: stat snapshot blocker renders in user language.
- `gear_save_blocked`: missing/untrusted slots block save.
- `gear_save_ready`: complete structured gear opens save sheet.
- `gear_template_saved`: saved template feedback is visible.
- `gear_simc_handoff`: SimC route handoff preserves bounded context.

Required assertions:

- No horizontal overflow on compact / standard / large.
- No fake host chrome.
- Bottom sheets and fixed actions do not cover tabBar, safe-area or keyboard area.
- `GearLoadoutBoard` keeps slot card, icon socket, equipment badges and enhancement badges inside measured bounds.
- `GearConfigSheet` keeps filters, candidate rows, variant tracks, crafted stat chips and action buttons inside measured bounds.
- Long item names, long source names, missing icons and source-reference labels do not resize the grid.
- Apply/save/import/reset buttons keep stable size in disabled/loading states.
- No DPS preview, score, tier, ranking, BiS or upgrade-priority claim.
- No raw backend blockers or secret-like values are visible.
- No quarantine asset reference.

## Evidence Required Before Runtime Acceptance

- Browser scene precheck for all gear scenes listed above.
- Real WeChat mini-program screenshots after `captureSafe=true`.
- Component crops for `PageFrame`, `WowPanel`, `GearLoadoutBoard`, `GearConfigSheet`, `GameObjectIcon`, `StatusVisual`, `ActionButton`, `EvidenceLedger`, sheet components and fixed action area.
- Current / target / implementation comparison.
- Overlay and red-zone output for attribute panel, 16-slot board, item socket, slot card, candidate row, variant selector, crafted stat selector, enhancement sheet, community sheet, save sheet, fixed action and bottom safe-area.
- Scorecard that explicitly rejects fake icons, fake BiS/DPS/score, grid overflow, sheet overflow, weakened trust gates, lost stat snapshot gate, lost template import behavior, raw blockers, fixed-button overlap and page-private material geometry.
- Route smoke report and DevTools action ledger.

## Rollback And Stop Conditions

Stop implementation and return to permit revision if any of these occur:

- The target is still not locked.
- `GearLoadoutBoard` / `GearConfigSheet` owner skeleton or clean component precheck is missing, stale or contradicted before page integration.
- A required owner needs page-private WXML/WXSS geometry to look acceptable.
- The page needs new backend fields or fake front-end fields to express readiness.
- The UI needs fake official item icons, fake source logos, fake BiS, fake ranking, fake popularity or fake DPS to look complete.
- Gear data tests fail or visual changes require weakening SimC-ready slot validation, apply-candidate trust gates, crafted stat gates, variant gates, enhancement caps, stat snapshot gates or save-readiness gates.
- Browser precheck passes but real mini-program screenshot shows grid, sheets, fixed action, tab/safe-area or keyboard overlap.
- DevTools capture is not safe or would require high-disturbance actions.

## Current Status

This draft is ready for target-lock review and now has `GearLoadoutBoard` / `GearConfigSheet` owner skeleton plus component precheck evidence. It does not activate implementation.
