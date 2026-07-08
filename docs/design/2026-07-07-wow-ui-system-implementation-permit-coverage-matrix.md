# WOW UI System Implementation Permit Coverage Matrix

Status: `permit_coverage_matrix_draft`
Created: 2026-07-07

This document records implementation-permit coverage for the WOW mini-program UI system rebuild. It is not `target_locked`, not an active implementation permit, and does not authorize page WXML/WXSS edits.

## Linked Control Plane

- [WOW 小程序 UI 系统重建完整 Goal](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Target Lock Proposal](2026-07-07-wow-ui-system-target-lock-proposal.md)
- [Foundation Component Contracts](2026-07-07-wow-ui-system-foundation-component-contracts.md)
- [Surface Owner Contracts](2026-07-07-wow-ui-system-surface-owner-contracts.md)
- [News List Detail Owner Skeleton Source Precheck](2026-07-07-wow-ui-system-news-list-detail-owner-skeleton-precheck.md)
- [News List Detail Component Precheck](2026-07-07-wow-ui-system-news-list-detail-component-precheck.md)
- [Builds Tab Owner Skeleton Source Precheck](2026-07-07-wow-ui-system-builds-tab-owner-skeleton-precheck.md)
- [Builds Tab Component Precheck](2026-07-07-wow-ui-system-builds-tab-component-precheck.md)
- [Workbench Owner Skeleton Source Precheck](2026-07-07-wow-ui-system-workbench-owner-skeleton-precheck.md)
- [Workbench Component Precheck](2026-07-07-wow-ui-system-workbench-component-precheck.md)
- [TalentTreeCanvas Owner Skeleton Source Precheck](2026-07-07-wow-ui-system-talent-tree-canvas-owner-skeleton-precheck.md)
- [TalentTreeCanvas Component Precheck](2026-07-07-wow-ui-system-talent-tree-canvas-component-precheck.md)
- [Gear Detail Owner Skeleton Source Precheck](2026-07-07-wow-ui-system-gear-detail-owner-skeleton-precheck.md)
- [Gear Detail Component Precheck](2026-07-07-wow-ui-system-gear-detail-component-precheck.md)
- [Tasks Owner Skeleton Source Precheck](2026-07-07-wow-ui-system-tasks-owner-skeleton-precheck.md)
- [Tasks Component Precheck](2026-07-07-wow-ui-system-tasks-component-precheck.md)
- [Profile Templates Owner Skeleton Source Precheck](2026-07-07-wow-ui-system-profile-templates-owner-skeleton-precheck.md)
- [Profile Templates Component Precheck](2026-07-07-wow-ui-system-profile-templates-component-precheck.md)
- [Chickenbro Owner Skeleton Source Precheck](2026-07-07-wow-ui-system-chickenbro-owner-skeleton-precheck.md)
- [Chickenbro Component Precheck](2026-07-07-wow-ui-system-chickenbro-component-precheck.md)
- [Asset Manifest Draft](2026-07-07-wow-ui-system-asset-manifest-draft.md)
- [Route Smoke And Runtime Verification Plan](2026-07-07-wow-ui-system-route-smoke-plan.md)
- [News Home Permit Draft](../plans/2026-07-07-wow-ui-system-news-home-implementation-permit-draft.md)
- [News List Detail Permit Draft](../plans/2026-07-07-wow-ui-system-news-list-detail-implementation-permit-draft.md)
- [Builds Tab Permit Draft](../plans/2026-07-07-wow-ui-system-builds-tab-implementation-permit-draft.md)
- [Workbench Permit Draft](../plans/2026-07-07-wow-ui-system-workbench-implementation-permit-draft.md)
- [Talent Simulator Permit Draft](../plans/2026-07-07-wow-ui-system-talent-simulator-implementation-permit-draft.md)
- [Gear Detail Permit Draft](../plans/2026-07-07-wow-ui-system-gear-detail-implementation-permit-draft.md)
- [SimC Permit Draft](../plans/2026-07-07-wow-ui-system-simc-implementation-permit-draft.md)
- [Chickenbro Permit Draft](../plans/2026-07-07-wow-ui-system-chickenbro-implementation-permit-draft.md)
- [Tasks Permit Draft](../plans/2026-07-07-wow-ui-system-tasks-implementation-permit-draft.md)
- [Profile Templates Permit Draft](../plans/2026-07-07-wow-ui-system-profile-templates-implementation-permit-draft.md)
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-permit-coverage-matrix/manifest.json`

## Coverage Rule

A core surface is not implementation-ready until it has:

- a target direction in the target-lock proposal;
- explicit owner components;
- data boundary and forbidden claims;
- asset boundary and real WoW source-map expectations;
- route smoke scenes;
- stop conditions;
- an explicit draft-to-active permit conversion.

Existing page code, old pass artifacts, component skeletons, browser precheck or a passing page test cannot substitute for an implementation permit.

## Core Surface Matrix

| Surface | Primary Routes | Current Permit Status | Current Evidence | Missing Before Implementation |
| --- | --- | --- | --- | --- |
| `news_home` | `/pages/news/news` | `implementation_permit_draft` | [News Home Permit Draft](../plans/2026-07-07-wow-ui-system-news-home-implementation-permit-draft.md) | target lock, active permit conversion, runtime screenshots and route smoke |
| `news_list_detail` | `/pages/news/list`, `/pages/news/detail` | `surface_component_precheck` | [News List Detail Component Precheck](2026-07-07-wow-ui-system-news-list-detail-component-precheck.md) | target lock, active permit conversion, page integration under permit, runtime screenshots and route smoke |
| `builds_tab` | `/pages/builds/builds` | `surface_component_precheck` | [Builds Tab Component Precheck](2026-07-07-wow-ui-system-builds-tab-component-precheck.md), [Builds Tab Owner Skeleton Source Precheck](2026-07-07-wow-ui-system-builds-tab-owner-skeleton-precheck.md), [Builds Tab Permit Draft](../plans/2026-07-07-wow-ui-system-builds-tab-implementation-permit-draft.md) | target lock, active permit conversion, page integration under permit, runtime screenshots and route smoke |
| `current_spec_workbench` | `/pages/builds/workbench`, `/pages/builds/builds` entry | `surface_component_precheck` | [Workbench Component Precheck](2026-07-07-wow-ui-system-workbench-component-precheck.md), [Workbench Owner Skeleton Source Precheck](2026-07-07-wow-ui-system-workbench-owner-skeleton-precheck.md), [Workbench Permit Draft](../plans/2026-07-07-wow-ui-system-workbench-implementation-permit-draft.md) | target lock, active permit conversion, page integration under permit, runtime screenshots and route smoke |
| `talent_simulator` | `/pages/builds/talent-simulator` | `surface_component_precheck` | [TalentTreeCanvas Component Precheck](2026-07-07-wow-ui-system-talent-tree-canvas-component-precheck.md), [TalentTreeCanvas Owner Skeleton Source Precheck](2026-07-07-wow-ui-system-talent-tree-canvas-owner-skeleton-precheck.md), [Talent Simulator Permit Draft](../plans/2026-07-07-wow-ui-system-talent-simulator-implementation-permit-draft.md) | target lock, active permit conversion, page integration under permit, runtime screenshots and route smoke |
| `gear_detail` | `/pages/builds/detail?query=gear` | `surface_component_precheck` | [Gear Detail Component Precheck](2026-07-07-wow-ui-system-gear-detail-component-precheck.md), [Gear Detail Owner Skeleton Source Precheck](2026-07-07-wow-ui-system-gear-detail-owner-skeleton-precheck.md), [Gear Detail Permit Draft](../plans/2026-07-07-wow-ui-system-gear-detail-implementation-permit-draft.md) | target lock, active permit conversion, page integration under permit, runtime screenshots and route smoke |
| `simc` | `/pages/simulator/simc` | `implementation_permit_draft` | [SimC Permit Draft](../plans/2026-07-07-wow-ui-system-simc-implementation-permit-draft.md) | target lock, active permit conversion, template gate fixture strategy, runtime screenshots and route smoke |
| `chickenbro` | `/pages/simulator/simulator`, `/pages/simulator/chickenbro` | `surface_component_precheck` | [Chickenbro Component Precheck](2026-07-07-wow-ui-system-chickenbro-component-precheck.md), [Chickenbro Owner Skeleton Source Precheck](2026-07-07-wow-ui-system-chickenbro-owner-skeleton-precheck.md), [Chickenbro Permit Draft](../plans/2026-07-07-wow-ui-system-chickenbro-implementation-permit-draft.md) | target lock, active permit conversion, page integration under permit, runtime screenshots and route smoke |
| `tasks` | `/pages/simulator/tasks`, `/pages/simulator/task-detail` | `surface_component_precheck` | [Tasks Component Precheck](2026-07-07-wow-ui-system-tasks-component-precheck.md), [Tasks Owner Skeleton Source Precheck](2026-07-07-wow-ui-system-tasks-owner-skeleton-precheck.md), [Tasks Permit Draft](../plans/2026-07-07-wow-ui-system-tasks-implementation-permit-draft.md) | target lock, active permit conversion, page integration under permit, runtime screenshots and route smoke |
| `profile_templates` | `/pages/profile/profile` | `surface_component_precheck` | [Profile Templates Component Precheck](2026-07-07-wow-ui-system-profile-templates-component-precheck.md), [Profile Templates Owner Skeleton Source Precheck](2026-07-07-wow-ui-system-profile-templates-owner-skeleton-precheck.md), [Profile Templates Permit Draft](../plans/2026-07-07-wow-ui-system-profile-templates-implementation-permit-draft.md) | target lock, active permit conversion, page integration under permit, runtime screenshots and route smoke |
| `pve_dormant` | `pages/pve/*` not registered | `out_of_scope_for_runtime_acceptance` | route smoke plan excludes it because `app.json` does not register it | product decision before adding to this UI system runtime acceptance |

## Draft Permit Inventory

| Draft | Surface | Status | Activation State |
| --- | --- | --- | --- |
| `2026-07-07-wow-ui-system-news-home-implementation-permit-draft.md` | `news_home` | `implementation_permit_draft` | not active |
| `2026-07-07-wow-ui-system-news-list-detail-implementation-permit-draft.md` | `news_list_detail` | `implementation_permit_draft` | not active |
| `2026-07-07-wow-ui-system-builds-tab-implementation-permit-draft.md` | `builds_tab` | `implementation_permit_draft` | not active |
| `2026-07-07-wow-ui-system-workbench-implementation-permit-draft.md` | `current_spec_workbench` | `implementation_permit_draft` | not active |
| `2026-07-07-wow-ui-system-talent-simulator-implementation-permit-draft.md` | `talent_simulator` | `implementation_permit_draft` | not active |
| `2026-07-07-wow-ui-system-gear-detail-implementation-permit-draft.md` | `gear_detail` | `implementation_permit_draft` | not active |
| `2026-07-07-wow-ui-system-simc-implementation-permit-draft.md` | `simc` | `implementation_permit_draft` | not active |
| `2026-07-07-wow-ui-system-chickenbro-implementation-permit-draft.md` | `chickenbro` | `implementation_permit_draft` | not active |
| `2026-07-07-wow-ui-system-tasks-implementation-permit-draft.md` | `tasks` | `implementation_permit_draft` | not active |
| `2026-07-07-wow-ui-system-profile-templates-implementation-permit-draft.md` | `profile_templates` | `implementation_permit_draft` | not active |

## Missing Permit Queue

All core runtime surfaces now have implementation permit drafts. No surface is implementation-ready until its draft is explicitly converted to an active permit.

Recommended next work:

1. Resolve the target lock or revise it with the user.
2. Decide which single surface becomes the first active implementation permit.
3. Run any missing surface-specific fixture strategy before activating that chosen permit.
4. Convert exactly one draft into an active implementation permit before page edits.

## Non-Promotion Rule

This matrix can only prove `permit_coverage_matrix_draft`. It cannot prove:

- `target_locked`;
- `active_implementation_permit`;
- `component_precheck`;
- `runtime_verified`;
- `final_accepted`.

## Current Status

Permit draft coverage is now complete for the current core runtime surface set, and surface owner contracts now exist as drafts. `news_list_detail` has a source-level owner skeleton, fixture matrix and surface component precheck with browser crops. `builds_tab` now has a source-level `BuildsTabSurface` owner skeleton, fixture matrix and surface component precheck with browser crops. `current_spec_workbench` now has a source-level `WorkbenchCockpitSurface` owner skeleton, fixture matrix and surface component precheck with browser crops. `talent_simulator` now has a source-level `TalentTreeCanvas` owner skeleton, fixture matrix and surface component precheck with browser crops. `gear_detail` now has source-level `GearLoadoutBoard` / `GearConfigSheet` owner skeletons, fixture matrix and surface component precheck with browser crops. `tasks` now has source-level `TaskQueueBoard` / `TaskResultReport` owner skeletons, fixture matrix and surface component precheck with browser crops. `profile_templates` now has source-level `ProfileIdentityPanel` / `TemplateLibraryBoard` owner skeletons, fixture matrix and surface component precheck with browser crops. `chickenbro` also has a source-level `ChickenbroCoachSurface` owner skeleton, fixture matrix and surface component precheck with browser crops. This still does not authorize implementation: target lock, active permit conversion, page integration under permit and runtime evidence are still missing.
