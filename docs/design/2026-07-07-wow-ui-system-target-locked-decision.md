# WOW UI System Target-Locked Decision

Status: `target_locked`

Date: 2026-07-07

## User Decision Source

The user explicitly confirmed in the current Codex thread:

- `target lock 采用当前推荐：A-Cockpit + B-Ledger + C-Captain`
- `本轮 single surface 选 news_list_detail`
- `允许我改 app.json，并新增 assets/tabbar/ 原生 tabBar 图标资源。`

This is the confirmation required by the activation guard. It is not a continuation turn and is not inferred from passing tests.

## Confirmed Target

Confirmed target: `A-Cockpit + B-Ledger + C-Captain`.

The target keeps the current product direction:

- `A-Cockpit`: top-level task and readiness clarity.
- `B-Ledger`: evidence, blockers, coverage and source state stay visible.
- `C-Captain`: assistant surfaces explain evidence without inventing conclusions.

The confirmed first delivery surface is `news_list_detail`.

## Decision Brief Boundary

The decision is based on `artifacts/ui-system-rebuild/20260707-target-lock-decision-brief/manifest.json`.

Expected brief status: `target_lock_decision_brief`.

Expected preflight ready status: `target_lock_decision_brief_ready`.

The brief remains a non-runtime artifact. It does not by itself prove page integration, runtime verification or final acceptance.

Runtime gates preserved from the brief:

- `production_asset_manifest_preflight`
- `real_wow_source_map_preflight`
- `page_adoption_preflight`
- `visual_acceptance_preflight`
- `route_smoke_execution_preflight`
- `devtools_action_ledger_preflight`

Runtime evidence still requires real WeChat mini-program screenshots, component crops, overlay/red-zone, scorecard, route smoke and DevTools action ledger.

## First-Class Surfaces

The long-term UI system still recognizes all core surfaces:

- `news_home`
- `news_list_detail`
- `builds_tab`
- `current_spec_workbench`
- `talent_simulator`
- `gear_detail`
- `simc`
- `chickenbro`
- `tasks`
- `profile_templates`

This target lock does not authorize all of them for implementation in this delivery pass. Only exactly one active permit may be active after this decision.

## Foundation Owner Rules

- Pages compose `AppShell`, `PageFrame` and surface owner components.
- Page files bind data, pass props and handle routes.
- Page files do not recreate panel geometry, status visuals, action buttons, evidence rows, chat bubbles, material slots or list row internals.
- Existing navigation chrome can be used as a component, but pages cannot fake system chrome, bottom tabs, status bar, battery, Wi-Fi, or WeChat capsule.

## Surface Owner Rules

- `news_list_detail` is owned by `ArticleListBoard` and `ArticleReader`.
- List rows, article visual fallback, source state, empty/loading/fallback UI and row status belong to `ArticleListBoard`.
- Detail headline, chips, body block rendering, evidence rows, missing id, not-found, fallback and copy source action belong to `ArticleReader`.
- Other surfaces remain backlog, next permit candidates or risk items until separately permitted.

## Asset Production And Quarantine Rules

- Native bottom tab icons are allowed in this delivery because the user explicitly permitted `app.json` tabBar icon changes and `assets/tabbar/` runtime resources.
- Imagegen may provide low-semantic material only after manifest, slicing, compression and owner fit rules.
- Reference-only, quarantine, pass36/pass37 and generated whole-page UI images cannot be referenced directly by production page WXML/WXSS.
- `assets/tabbar/` icons are runtime UI chrome assets, not real WoW class/spec/talent/item/source icons.

## Material Asset Seed Boundary

The material seed remains `artifacts/ui-system-rebuild/20260707-material-asset-seed/manifest.json`.

Expected status: `material_asset_seed_ready`.

The seed is not a production manifest: `productionManifest=false`.

The seed is not page-direct or production-direct material: `pageDirectUseAllowed=false` and `productionUseAllowed=false`.

Production use still requires a separate production manifest and owner fit strategy.

## Real WoW Object Source Rules

Real WoW class, spec, hero talent, talent, spell, item, source, dungeon, raid and affix objects cannot come from imagegen.

Allowed real object sources are API, Battle.net, WebSim, repository verified mapping or user-provided verified material. Imagegen can only provide low-semantic material and must never generate a fake WoW object or fake source logo.

## Route Smoke Rules

The first active permit must keep route smoke scenes bounded to `news_list_detail`.

Required route smoke coverage includes list channel/filter states, loading, empty, fallback, opening detail, first detail, missing id, not found, fallback detail, copy source and return to list.

Route smoke output must not promote non-selected pages.

## Implementation Permit Rule

Exactly one active implementation permit is allowed for this delivery pass.

The selected permit is `news_list_detail` and its real active permit file is:

- `docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit.md`

`app.json` changes are allowed only for native tabBar `iconPath` / `selectedIconPath` wiring under the delivery convergence permission. Broader route registration, page expansion, project config or unrelated surface edits remain outside this target lock.

## Non-Promotion Boundary

This record proves `target_locked` only.

It does not prove:

- `runtime_verified`
- `final_accepted`
- all-surface implementation
- all-surface visual acceptance
- DevTools route smoke completion

The first active surface still needs implementation evidence, static gates, route smoke evidence and screenshots before any runtime claim.

## Next Allowed Action

Create and validate exactly one active implementation permit for `news_list_detail`, add native tabBar icons under `assets/tabbar/`, wire `app.json` tabBar icon paths, then implement `pages/news/list` and `pages/news/detail` through `AppShell`, `PageFrame`, `ArticleListBoard` and `ArticleReader`.
