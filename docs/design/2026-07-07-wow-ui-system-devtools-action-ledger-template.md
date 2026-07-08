# WOW UI System DevTools Action Ledger Template

Status: `devtools_action_ledger_template_only`

Date: 2026-07-07

This template defines the runtime capture ledger that must exist before any real mini-program screenshot can be used as UI system evidence. It does not touch WeChat DevTools, does not prove `captureSafe=true`, and does not approve runtime verification.

## Command

```sh
node scripts/ui-system-devtools-action-ledger-preflight.js --require-ledger --json
```

Current expected exit code without a real runtime ledger: `9`.

## Default Runtime Ledger Path

```text
artifacts/ui-system-rebuild/runtime/devtools-action-ledger.json
```

The default file is intentionally absent in the current source-evidence phase.

## Required JSON Shape

```json
{
  "status": "devtools_action_ledger_capture_safe",
  "captureSafe": true,
  "checkedAt": "2026-07-07T00:00:00.000Z",
  "captureRunner": "scripts/or/artifacts/runner-name.js",
  "devtools": {
    "appPath": "/Applications/wechatwebdevtools.app",
    "port": 12345,
    "appidState": "existing_authorized_project"
  },
  "forbiddenActionCheck": {
    "status": "pass",
    "prohibitedActionsUsed": []
  },
  "sceneList": [
    "news_home_top"
  ],
  "failedScenes": [],
  "screenshotPathList": [
    "screenshots/news_home_top.png"
  ],
  "routeActionList": [
    {
      "scene": "news_home_top",
      "action": "switchTab",
      "route": "/pages/news/news"
    }
  ],
  "loginStateIncidentNote": "none"
}
```

## Forbidden Actions

- `cli open`
- `cli close`
- forced restart
- clear cache
- switch project
- switch appid
- delete or replace user data directory
- login/logout operations
- screenshot before `captureSafe=true`
- navigation before `captureSafe=true`

## Preflight Meaning

The preflight can prove only that a ledger file is structurally ready for use as runtime capture evidence. It cannot prove visual quality, target matching, route success, overlay, red-zone, scorecard, `runtime_verified`, or `final_accepted`.

## Current State

- real runtime ledger exists: false
- captureSafe proven: false
- DevTools touched by this template: false
- runtime screenshots accepted: false

## Non-Promotion Rule

This template can only prove `devtools_action_ledger_template_only`. It cannot prove `runtime_verified`, `final_accepted`, visual acceptance, target lock, active permit, or page integration.
