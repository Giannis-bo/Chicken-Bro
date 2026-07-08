# Chickenbro Owner Skeleton Source Precheck

Status: `owner_skeleton_source_precheck`
Created: 2026-07-07

This document records the first source-level owner skeleton for the `chickenbro` surface. It is not `target_locked`, not `component_precheck`, not `browser_precheck`, not an active implementation permit, not page integration, and not runtime verified.

## Linked Control Plane

- [WOW 小程序 UI 系统重建完整 Goal](../plans/2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Surface Owner Contracts](2026-07-07-wow-ui-system-surface-owner-contracts.md)
- [Chickenbro Permit Draft](../plans/2026-07-07-wow-ui-system-chickenbro-implementation-permit-draft.md)
- [Chickenbro Component Precheck](2026-07-07-wow-ui-system-chickenbro-component-precheck.md)
- [Implementation Permit Coverage Matrix](2026-07-07-wow-ui-system-implementation-permit-coverage-matrix.md)
- [Route Smoke And Runtime Verification Plan](2026-07-07-wow-ui-system-route-smoke-plan.md)
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-chickenbro-owner-skeleton/manifest.json`
- Fixture matrix: `artifacts/ui-system-rebuild/20260707-chickenbro-owner-skeleton/fixtures.json`

## What Changed

- Added `components/chickenbro-coach-surface/*`.
- Tightened `components/chat-shell/*` defaults so shell actions are Chinese, configurable and owner-controlled.
- Added a `chickenbro` fixture matrix for tab entry, workbench context, generating, completed reply, failure, topic drawer, input focus and long-message states.
- No `pages/simulator/chickenbro.*` or `pages/simulator/simulator.*` page integration was performed.
- No route registration, tabBar, appid, DevTools or backend contract changes were performed.

## Design Read

Reading this as: native WeChat mini-program product UI for WoW players, with a dense evidence cockpit language and a first-class coach conversation surface.

Dial settings:

- `DESIGN_VARIANCE: 6`
- `MOTION_INTENSITY: 3`
- `VISUAL_DENSITY: 9`

## Owner Responsibilities Now In Source

### ChickenbroCoachSurface

- Owns Chickenbro route-level composition above `ChatShell`.
- Owns title/status header, context summary, suggested prompts, evidence summary, request-error slab, topic drawer and retry action.
- Translates backend-facing evidence fields into player-facing labels before they reach visible UI.
- Emits route events only: `send`, `inputchange`, `inputfocus`, `inputblur`, `newtopic`, `opendrawer`, `closedrawer`, `suggestedprompt`, `retry` and `evidencetoggle`.
- Uses `ChatShell` for message list, input safe-area, empty state and chat actions.
- Uses `EvidenceLedger` for answer evidence, limitations and next-action rows.
- Uses `StatusVisual` for generating, failed, fallback and source-reference state.
- Uses `ActionButton` for topic, suggested prompt, retry and close actions.
- Uses `MaterialImage` only for low-semantic material under manifest control.

### ChatShell

- Owns message bubble geometry, message list scroll lane, input bar, safe-area spacing, context strip and next-question chips.
- Now has configurable player-facing labels for context, new topic, send and submitting.
- Does not expose raw backend field names in WXML.

## Current Source Findings Still Unfixed

These findings remain in the current routes until a future active implementation permit:

- `pages/simulator/chickenbro.wxml` still displays `assistantPayload.answerSource` and `assistantPayload.confidence`.
- `pages/simulator/chickenbro.wxml` still displays `job.status`.
- `pages/simulator/simulator.wxml` still has the same visible raw field pattern.
- Both route shells still use page-private chat layout classes instead of the target `ChickenbroCoachSurface` and `ChatShell` owners.
- Both route shells still reference old generated material directly through page WXML.

This skeleton does not patch those routes. It gives the future active permit a component owner that can replace them without page-private geometry.

## Fixture Coverage

- `chickenbro_tab_empty`
- `chickenbro_workbench_context`
- `chickenbro_generating`
- `chickenbro_done_with_evidence`
- `chickenbro_failed`
- `chickenbro_topic_drawer`
- `chickenbro_input_focus`
- `chickenbro_long_message_scroll`

## Protected Boundaries

- No visible `answerSource`, `confidence` or `job.status` text.
- No raw SimC profile, raw WCL log payload, token, openid, user id, database id or secret-like value.
- No unsupported DPS, ranking, percentile, S/A grade, comprehensive score or upgrade-priority claim.
- No generated portrait, source logo, class/spec/talent/item icon or whole-page target image.
- No fake phone chrome, time, battery, Wi-Fi or WeChat capsule.
- No page-private chat bubble, evidence row, status badge, input bar, drawer or material geometry.

## Mapping Rules

Backend-facing values are allowed in JS data only as inputs. The owner maps them before visible UI:

- `answerSource` -> `通用回答` / `本地证据` / `降级回复` / `来源参考` / `证据不足`
- `confidence` -> `可解释` / `部分可用` / `证据不足` / `阻断`
- `job.status` -> `等待整理` / `整理中` / `已完成` / `暂时失败`

## Next Required Evidence

- Production/browser component precheck for `ChickenbroCoachSurface` and `ChatShell` now exists; rerun it before activation.
- User confirmation or revision of target lock.
- Explicit conversion of the `chickenbro` permit draft into an active implementation permit before page integration.
- Page integration that replaces current route shells with owner components only.
- Real mini-program screenshots after `captureSafe=true`.
- Route smoke manifest and DevTools action ledger.

## Non-Promotion Rule

This document can only prove `owner_skeleton_source_precheck`. It cannot prove:

- `target_locked`;
- `active_implementation_permit`;
- `component_precheck`;
- `browser_precheck`;
- `page_integration`;
- `runtime_verified`;
- `final_accepted`.
