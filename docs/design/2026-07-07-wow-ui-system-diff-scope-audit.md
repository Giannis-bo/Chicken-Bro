# WOW UI System Diff Scope Audit

Status: `diff_scope_blocked_page_integration_present`

Date: 2026-07-07

This audit classifies the current dirty worktree against the activation guard. It does not approve page implementation, does not activate a permit, and does not make runtime claims. Its purpose is to prevent current page-level changes from being mistaken for authorized UI system rebuild implementation.

## Command

```sh
node scripts/ui-system-diff-scope-audit.js --summary-json
node scripts/ui-system-diff-scope-audit.js --require-no-page-integration --summary-json
```

The first command reports the current scope. The second command is the implementation-entry guard and exits non-zero while page integration is blocked.

## Result

- status: `diff_scope_blocked_page_integration_present`
- activationAllowed=false
- pageIntegrationAllowed=false
- changedFileCount=2858
- blockedPageIntegrationFileCount=44
- pageScopeBlocked=true
- devtoolsScopeRisk=true
- requiredAction=`quarantine page/app/navigation changes until target lock and active implementation permit exist`

## Category Counts

| Category | Count |
| --- | ---: |
| appShellIntegration | 2 |
| evidenceOrTooling | 2579 |
| assetWork | 124 |
| componentOwnerWork | 108 |
| existingChromeIntegration | 3 |
| pageIntegration | 39 |
| devtoolsProjectConfig | 1 |
| backendOrDataWork | 2 |

## Quarantined Page/App/Navigation Files

- `app.json`
- `app.wxss`
- `components/navigation-bar/navigation-bar.js`
- `components/navigation-bar/navigation-bar.wxml`
- `components/navigation-bar/navigation-bar.wxss`
- `pages/builds/builds-api.js`
- `pages/builds/builds.js`
- `pages/builds/builds.wxml`
- `pages/builds/builds.wxss`
- `pages/builds/detail.wxml`
- `pages/builds/intel.wxml`
- `pages/builds/talent-simulator-core.js`
- `pages/builds/talent-simulator.wxml`
- `pages/builds/workbench-state.js`
- `pages/builds/workbench.js`
- `pages/builds/workbench.json`
- `pages/builds/workbench.wxml`
- `pages/builds/workbench.wxss`
- `pages/common/wow-spec-assets.js`
- `pages/news/detail.wxml`
- `pages/news/list.wxml`
- `pages/news/news-api.js`
- `pages/news/news.js`
- `pages/news/news.json`
- `pages/news/news.wxml`
- `pages/news/news.wxss`
- `pages/profile/profile.js`
- `pages/profile/profile.wxml`
- `pages/profile/profile.wxss`
- `pages/pve/detail.wxml`
- `pages/pve/pve.wxml`
- `pages/simulator/chickenbro-chat.js`
- `pages/simulator/chickenbro.wxml`
- `pages/simulator/chickenbro.wxss`
- `pages/simulator/simc.js`
- `pages/simulator/simc.wxml`
- `pages/simulator/simc.wxss`
- `pages/simulator/simulator.wxml`
- `pages/simulator/simulator.wxss`
- `pages/simulator/task-detail.wxml`
- `pages/simulator/tasks.js`
- `pages/simulator/tasks.wxml`
- `pages/simulator/tasks.wxss`
- `pages/simulator/wcl.wxml`

## DevTools Risk

- `project.config.json`

This is a DevTools-sensitive file. It must remain treated as a risk item until the implementation permit explicitly allows it and the DevTools action ledger explains why it is safe.

## Interpretation

The worktree contains useful evidence/tooling and component-owner work, but it also contains page/app/navigation changes that cannot be treated as authorized implementation while activation is blocked. The correct next step remains target-lock confirmation or modification, followed by exactly one active implementation permit.

## Evidence Links

- [Activation Guard](2026-07-07-wow-ui-system-activation-guard.md)
- [Two-Part Goal Sync](../plans/2026-07-07-wow-ui-system-two-part-goal-sync.md)
- [Target Lock Decision Request](2026-07-07-wow-ui-system-target-lock-decision-request.md)
- [Diff Scope Audit Manifest](../../artifacts/ui-system-rebuild/20260707-diff-scope-audit/manifest.json)
