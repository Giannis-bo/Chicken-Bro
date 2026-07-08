# WOW UI System First Surface Activation Readiness Preflight

Status: `first_surface_activation_readiness_ready`

Date: 2026-07-07

Design read: WOW 小程序 redesign-overhaul for C-end WoW players, with a dense evidence-cockpit language, leaning toward a custom component owner system rather than a landing-page design system.

This preflight checks whether the first implementation surface, `news_list_detail`, is ready to become the first active permit after a user-confirmed target lock. It is not `target_locked`, not an active implementation permit, not page integration and not runtime verification.

## Command

```sh
node scripts/ui-system-first-surface-activation-readiness-preflight.js --require-ready --json
```

Current expected exit code: `0`.

## What It Checks

- target-lock readiness packet exists and still points to `A-Cockpit + B-Ledger + C-Captain`;
- activation packet remains `activation_packet_draft` and covers `news_list_detail`;
- owner registry maps `news_list_detail` to `ArticleListBoard` and `ArticleReader`;
- material asset seed is ready, covers required material classes, includes `news_list_detail`, stays non-production, and keeps semantic safety flags clean;
- real WoW source-map seed is ready and does not use imagegen for real objects;
- `news_list_detail` draft permit and active-permit template exist;
- active-permit template includes required owner components and 12 route smoke scenes;
- active-permit template inherits decision brief and two-part goal boundaries;
- owner skeleton fixture matrix exists;
- component/browser precheck has no failures, warnings or horizontal overflow;
- component crops and contact sheet exist;
- route smoke plan has capture-safe DevTools policy and required news scenes;
- route smoke execution, visual acceptance, DevTools ledger, page adoption and production asset manifest templates exist;
- every checked manifest remains non-promoting.

## Current Result

- status: `first_surface_activation_readiness_ready`
- surface: `news_list_detail`
- readyForTargetLockActivation=true
- targetLocked=false
- activeImplementationPermit=false
- pageIntegration=false
- runtimeVerified=false
- finalAccepted=false

## Non-Promotion Rule

This preflight only proves that the first surface has a coherent source-level activation packet. The next legal transition is still explicit user target-lock confirmation or written modification, then a real `target_locked` decision record, then exactly one active implementation permit.

It cannot prove:

- `target_locked`;
- `active_implementation_permit`;
- page WXML/WXSS adoption;
- real mini-program screenshots;
- visual acceptance;
- route smoke execution;
- `runtime_verified`;
- `final_accepted`.
