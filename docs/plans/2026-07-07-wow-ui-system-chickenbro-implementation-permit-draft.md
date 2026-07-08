# WOW UI System Chickenbro Implementation Permit Draft

Status: `implementation_permit_draft`

This is the single-surface permit draft for making Chickenbro a first-class WOW mini-program surface. It is not `target_locked`, not an active implementation permit, and does not authorize page WXML/WXSS edits.

## Linked Control Plane

- [WOW 小程序 UI 系统重建完整 Goal](2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Phase 1/2 Inventory](2026-07-07-wow-mini-program-ui-system-rebuild-phase1-inventory.md)
- [Target Lock Proposal](../design/2026-07-07-wow-ui-system-target-lock-proposal.md)
- [Foundation Component Contracts](../design/2026-07-07-wow-ui-system-foundation-component-contracts.md)
- [Asset Manifest Draft](../design/2026-07-07-wow-ui-system-asset-manifest-draft.md)
- [Route Smoke And Runtime Verification Plan](../design/2026-07-07-wow-ui-system-route-smoke-plan.md)
- [Production Component Precheck](../design/2026-07-07-wow-ui-system-production-component-precheck.md)
- [Browser Component Precheck](../design/2026-07-07-wow-ui-system-browser-component-precheck.md)
- [Chickenbro Owner Skeleton Source Precheck](../design/2026-07-07-wow-ui-system-chickenbro-owner-skeleton-precheck.md)
- [Chickenbro Component Precheck](../design/2026-07-07-wow-ui-system-chickenbro-component-precheck.md)
- Artifact manifest: `artifacts/ui-system-rebuild/20260707-chickenbro-permit-draft/manifest.json`

## Surface

Surface: `chickenbro`

Routes:

- `/pages/simulator/simulator` as the smart-analysis tab entry.
- `/pages/simulator/chickenbro` as the stack route and workbench-context route.

Reason to draft this now:

- The active goal explicitly says Chickenbro must become a first-class surface, not an old chat shell.
- Current source inspection shows raw backend-facing fields still appear in visible WXML.
- Chickenbro exercises the highest-risk interaction layer: long scroll, input safe-area, topic drawer, generating state, fallback failure, evidence language and workbench context.

## Current Source Findings

These findings are diagnostic evidence, not permission to patch:

- `pages/simulator/chickenbro.wxml` displays `assistantPayload.answerSource` and `assistantPayload.confidence` inside the visible `回答依据` row.
- `pages/simulator/chickenbro.wxml` displays `job.status` in the chat status row and topic drawer.
- `pages/simulator/simulator.wxml` has the same visible raw field pattern for the tab entry.
- Both route shells use page-private chat layout classes instead of the target `ChatShell` owner contract.
- Both route shells reference old generated material directly through page WXML.

## Target Dependency

This draft assumes the target proposal direction `A-Cockpit + B-Ledger + C-Captain`, but it cannot activate until the user confirms or edits the target lock.

Required before activation:

- `target_locked` design for Chickenbro direct tab entry and workbench-context entry.
- Accepted or revised asset manifest with production / quarantine / real source-map sections.
- Clean Chickenbro surface component precheck with production WXSS class names.
- Clean browser component precheck rerun before activation.
- Accepted `ChickenbroCoachSurface` owner skeleton and fixture matrix.
- Explicit user or owner approval to convert this draft into an active implementation permit.

## Intended Component Owners

| Owner | Role On Chickenbro |
| --- | --- |
| `ChickenbroCoachSurface` | Route-level coach composition, header/status, workbench context, suggested prompts, evidence summary, topic drawer and retry/error slab. |
| `ChatShell` | Chat page structure, message list, topic drawer, input safe-area, keyboard avoidance, long-message scroll. |
| `PageFrame` | Route-level gutters, top rhythm, stack/tab boundary and safe scroll lane. |
| `EvidenceLedger` | Player-language evidence rows, limitations and source explanation. |
| `StatusVisual` | Generating, failed, fallback, source_reference and blocked state visuals. |
| `ActionButton` | Send, new topic, retry, suggested prompt and bounded-context actions. |
| `MaterialImage` | Low-semantic background material only through component-owned fit and opacity. |

Pages may bind messages, session state, job state and route actions, but may not own chat bubble geometry, evidence-row grammar, input bar layout or topic drawer geometry.

## Proposed Allowed Files After Activation

These files would be allowed only after this draft becomes an active permit:

- `pages/simulator/chickenbro.wxml`
- `pages/simulator/chickenbro.wxss`
- `pages/simulator/chickenbro.js`
- `pages/simulator/chickenbro.json`
- `pages/simulator/simulator.wxml`
- `pages/simulator/simulator.wxss`
- `pages/simulator/simulator.js`
- `pages/simulator/simulator.json`
- `pages/simulator/chickenbro-chat.js`
- `components/chat-shell/*`
- `components/evidence-ledger/*`
- `components/status-visual/*`
- narrowly scoped simulator / Chickenbro tests
- Chickenbro-specific browser/runtime evidence under `artifacts/ui-system-rebuild/`

Any change outside this list requires a revised permit.

## Forbidden Files And Actions

- No `app.json` route or tabBar changes.
- No `project.config.json` / appid / DevTools shadow changes.
- No backend API contract changes.
- No direct database / token / raw log / raw SimC exposure.
- No unrelated workbench, builds, news, profile or task page edits.
- No page-private chat bubble, evidence row, status badge, input bar, drawer or material geometry.
- No direct page reference to quarantine assets, whole-page target images or pass-named generated glyphs.
- No WeChat DevTools open/close/restart/cache-clear/login/logout actions.

## Data Boundary

Allowed data sources:

- Existing `/api/chickenbro/messages`, session and job client calls.
- Existing bounded context from workbench route query.
- Existing local fallback response, but only with clear fallback language.
- Existing message/session/job state in `pages/simulator/chickenbro-chat.js`.

Required UI mapping:

- Backend `answerSource` must be translated into user-language source labels such as `通用回答`, `本地证据`, `降级回复`, `来源参考`, or `证据不足`.
- Backend `confidence` must be translated into evidence strength language such as `可解释`, `部分可用`, `证据不足`, or `阻断`.
- Backend `job.status` must be translated into player-facing task states such as `整理中`, `已完成`, `暂时失败`, or `等待重试`.
- Evidence references may show compact user labels, but raw internal ids must not become primary UI text.

Forbidden visible text:

- `answerSource`
- `confidence`
- `job.status`
- raw SimC profile
- raw WCL log payload
- raw API tokens, openid, user id, database ids or secret-like values
- unsupported DPS, ranking, percentile, S/A grade or upgrade-priority claims

## Asset Boundary

Allowed:

- Low-semantic panel, border, texture or socket material after manifest approval.
- Real class/spec/talent/item/source icons only through verified source map and `GameObjectIcon` if shown.
- Text fallback for missing context/source icons.

Forbidden:

- Imagegen portraits pretending to be Chickenbro evidence.
- Generated source logos.
- Generated class/spec/talent/item icons.
- Whole-page target images or contact sheets in production WXML/WXSS.
- Fake time, battery, Wi-Fi, phone frame or WeChat capsule.

## Route Smoke Scope

Required scenes after implementation:

- `smart_analysis_tab`: tab entry is Chickenbro-first and not a dead card grid.
- `chickenbro_empty`: empty state, input safe-area and new topic action.
- `chickenbro_workbench_context`: bounded context summary, suggested prompts and evidence chips without raw backend fields.
- `chickenbro_generating`: generating row, disabled/loading input and stable scroll.
- `chickenbro_done`: completed reply, evidence rows and next questions.
- `chickenbro_failed`: recoverable failure, fallback clarity and retry path.
- `topic_drawer`: topic drawer open/close with long title handling.
- `input_focus`: keyboard/input-safe layout without bottom tab or button overlap.
- `long_message_scroll`: long assistant answer remains scrollable and does not overflow horizontally.

Required assertions:

- No visible raw backend field names or raw values.
- No horizontal overflow on compact / standard / large.
- No fake host chrome.
- Input bar and topic drawer are owned by `ChatShell`.
- Evidence rows are in user language and do not replace SimC/WCL/real evidence with unsupported claims.
- Direct tab entry and stack route stay visually consistent.
- Workbench context does not pass raw profile data.
- No quarantine asset reference.

## Evidence Required Before Runtime Acceptance

- Browser scene precheck for all Chickenbro states listed above.
- Real WeChat mini-program screenshots after `captureSafe=true`.
- Component crops for `ChatShell`, `EvidenceLedger`, `StatusVisual` and input bar.
- Current / target / implementation comparison.
- Overlay and red-zone output for header, message list, evidence area, topic drawer and input bar.
- Scorecard that explicitly rejects raw backend field exposure, hidden evidence source, bottom overlap and unsupported scoring.
- Route smoke report and DevTools action ledger.

## Rollback And Stop Conditions

Stop implementation and return to permit revision if any of these occur:

- The target is still not locked.
- The page requires direct WXML/WXSS geometry for chat bubbles, evidence rows, drawer or input bar instead of `ChatShell`.
- Visible UI needs raw backend fields to explain evidence.
- Workbench context requires raw SimC profile or raw logs.
- A generated image implies a real source, real character, real class/spec, real item or real proof.
- Browser precheck passes but real mini-program screenshot shows keyboard/tab/safe-area overlap.
- DevTools capture is not safe or would require high-disturbance actions.

## Current Status

This draft is ready for target-lock review. `ChickenbroCoachSurface` and `ChatShell` now have a surface component precheck with 3 viewport screenshots, 8 component crops, failures=0, warnings=0 and horizontalOverflow=0. This still does not activate implementation.
