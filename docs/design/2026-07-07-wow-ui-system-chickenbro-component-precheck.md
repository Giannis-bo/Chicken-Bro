# Chickenbro Component Precheck

Status: `surface_component_precheck`
Created: 2026-07-07

This document records the production/browser component precheck for the `chickenbro` surface owners. It is not `target_locked`, not an active implementation permit, not page integration, and not real WeChat mini-program runtime verification.

## Linked Control Plane

- [WOW 小程序 UI 系统重建完整 Goal](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Chickenbro Owner Skeleton Source Precheck](2026-07-07-wow-ui-system-chickenbro-owner-skeleton-precheck.md)
- [Surface Owner Contracts](2026-07-07-wow-ui-system-surface-owner-contracts.md)
- [Chickenbro Permit Draft](../plans/2026-07-07-wow-ui-system-chickenbro-implementation-permit-draft.md)
- [Implementation Permit Coverage Matrix](2026-07-07-wow-ui-system-implementation-permit-coverage-matrix.md)
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-chickenbro-component-precheck/manifest.json`
- Fixture HTML: `artifacts/ui-system-rebuild/20260707-chickenbro-component-precheck/component-fixture.html`
- Contact sheet: `artifacts/ui-system-rebuild/20260707-chickenbro-component-precheck/component-crop-contact-sheet.png`

## What Changed

- Added a local headless Chrome precheck runner for `ChickenbroCoachSurface` and `ChatShell`.
- The runner uses production WXSS class names from the two surface owners and their foundation dependencies.
- The fixture renders the Chickenbro owner fixture matrix: tab empty, workbench context, generating, completed evidence, failure, topic drawer, input focus and long-message states.
- The run captures compact / standard / large browser viewport screenshots.
- The run captures eight standard-viewport component crops:
  - Chickenbro surface empty state
  - workbench-context suggestions
  - generating chat shell
  - answer evidence ledger
  - failure error slab
  - topic drawer
  - input-focus ChatShell with input bar
  - long-message assistant bubble
- Fixed `ChatShell` owner CSS so the scroll lane no longer pushes the input bar outside the component boundary.
- Tightened Chickenbro drawer copy so source-level visible text does not rely on broad forbidden-claim terms.
- No `pages/simulator/chickenbro.*` or `pages/simulator/simulator.*` page integration was performed.
- No WeChat DevTools action was performed.

## Current Result

- Status: `surface_component_precheck`
- Failures: `0`
- Warnings: `0`
- Viewports measured: `compact`, `standard`, `large`
- Horizontal overflow: `0` in every measured viewport
- Standard crops written: `8`
- Owner source precheck: `ChickenbroCoachSurface=pass`, `ChatShell=pass`
- Forbidden visible text: `0` matches for raw `answerSource`, `confidence`, `job.status`, raw SimC/WCL text or unsupported score claims

## Evidence Boundaries

This precheck proves:

- the two owner components parse and keep their declared owner boundaries;
- the owner fixture matrix can be rendered through production class names;
- empty, workbench context, generating, completed evidence, failure, topic drawer, input focus and long-message states have measurable geometry;
- browser-level component crops exist for the key coach, chat, evidence, drawer, error and input slots;
- the input bar remains inside `ChatShell` in the browser fixture;
- no page-level integration or DevTools action happened.

This precheck does not prove:

- real WeChat mini-program runtime rendering;
- route smoke;
- overlay, red-zone or scorecard acceptance;
- `target_locked`;
- active implementation permission for `pages/simulator/chickenbro` or `pages/simulator/simulator`;
- final UI acceptance.

## Next Required Evidence

- User confirmation or revision of the target lock.
- Explicit conversion of the `chickenbro` draft permit into an active implementation permit.
- Page integration only under that active permit.
- Real mini-program screenshots after `captureSafe=true`.
- Route smoke and DevTools action ledger after integration.

## Non-Promotion Rule

This document can only prove `surface_component_precheck`. It cannot prove:

- `target_locked`;
- `active_implementation_permit`;
- `runtime_verified`;
- `final_accepted`.
