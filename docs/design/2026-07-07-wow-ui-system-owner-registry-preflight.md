# WOW UI System Owner Registry Preflight

Status: `owner_registry_source_ready`

Date: 2026-07-07

This document records the machine-readable owner registry gate for the UI system rebuild. It checks that the core App-level component system has explicit owners before page integration begins.

This is source evidence only. It does not create a target lock, does not activate an implementation permit, does not adopt pages, and does not claim runtime verification.

## Command

```bash
node scripts/ui-system-owner-registry-preflight.js --require-ready --json
```

Expected current exit code: `0`.

## Current Result

- Status: `owner_registry_source_ready`
- ownerRegistryReady: `true`
- ownerCount: `26`
- foundationOwnerCount: `12`
- surfaceOwnerCount: `14`
- pageIntegration: `false`
- runtimeVerified: `false`
- finalAccepted: `false`

## Foundation Owners

- `AppShell`
- `PageFrame`
- `WowPanel`
- `MaterialImage`
- `GameObjectIcon`
- `StatusVisual`
- `ActionButton`
- `ModuleCard`
- `ChannelDock`
- `RankedFeed`
- `EvidenceLedger`
- `ChatShell`

## Surface Owners

- `NewsHomeSurface`
- `ArticleListBoard`
- `ArticleReader`
- `BuildsTabSurface`
- `WorkbenchCockpitSurface`
- `TalentTreeCanvas`
- `GearLoadoutBoard`
- `GearConfigSheet`
- `SimcSubmitSurface`
- `ChickenbroCoachSurface`
- `TaskQueueBoard`
- `TaskResultReport`
- `ProfileIdentityPanel`
- `TemplateLibraryBoard`

## Core Surface Coverage

| Surface | Owner(s) |
| --- | --- |
| `news_home` | `NewsHomeSurface` |
| `news_list_detail` | `ArticleListBoard`, `ArticleReader` |
| `builds_tab` | `BuildsTabSurface` |
| `current_spec_workbench` | `WorkbenchCockpitSurface` |
| `talent_simulator` | `TalentTreeCanvas` |
| `gear_detail` | `GearLoadoutBoard`, `GearConfigSheet` |
| `simc` | `SimcSubmitSurface` |
| `chickenbro` | `ChickenbroCoachSurface` |
| `tasks` | `TaskQueueBoard`, `TaskResultReport` |
| `profile_templates` | `ProfileIdentityPanel`, `TemplateLibraryBoard` |

## Boundary Owners

- Real WoW object icons: `GameObjectIcon`
- Low-semantic imagegen material: `MaterialImage`
- State visuals: `StatusVisual`
- Action geometry: `ActionButton`
- Evidence rows and blockers: `EvidenceLedger`
- Coach chat layout and input safety: `ChatShell`

## Guard Rules

- Every owner must have `.js`, `.json`, `.wxml` and `.wxss`.
- Every owner JSON must be a mini-program component.
- Every core surface must map to at least one registered owner.
- `StatusBadge` / `status-badge` cannot be part of the vNext owner registry.
- The registry must keep `pageIntegration=false`, `runtimeVerified=false` and `finalAccepted=false`.

## Non-Promotion Boundary

This preflight is not:

- `target_locked`
- `active_implementation_permit`
- page integration evidence
- real mini-program screenshots
- `runtime_verified`
- `final_accepted`
