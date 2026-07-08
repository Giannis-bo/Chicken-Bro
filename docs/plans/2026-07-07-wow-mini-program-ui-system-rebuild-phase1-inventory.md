# WOW 小程序 UI 系统重建 Phase 1/2 Inventory

Status: `source evidence`
Created: 2026-07-07

Source goal: [WOW 小程序 UI 系统重建完整 Goal](2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)

## Active Goal Alignment

- 2026-07-07 用户已将 active Codex goal 重置为 `WOW 小程序 UI 系统重建`。
- 本文是 Phase 1 `Inventory And Freeze` 和 Phase 2 `Current Problem Register` 的项目侧证据。
- 本文覆盖旧 `pass36 局部修复 / 像素调参 / 单页 scorecard` 执行线。旧 pass36/pass37 只保留为失败证据、诊断证据和历史上下文。

## Phase 1 Inventory

### Registered App Pages

`app.json` 当前注册 14 个页面：

| Surface | Page |
| --- | --- |
| 资讯首页 | `pages/news/news` |
| 资讯列表 | `pages/news/list` |
| 资讯详情 | `pages/news/detail` |
| 职业专精 tab | `pages/builds/builds` |
| 当前专精工作台 | `pages/builds/workbench` |
| 职业情报 | `pages/builds/intel` |
| 天赋模拟器 | `pages/builds/talent-simulator` |
| 装备详情/装备模拟 | `pages/builds/detail` |
| 智能分析 tab | `pages/simulator/simulator` |
| SimC | `pages/simulator/simc` |
| 炸鸡队长 | `pages/simulator/chickenbro` |
| 任务列表 | `pages/simulator/tasks` |
| 任务详情 | `pages/simulator/task-detail` |
| 我的模板/个人页 | `pages/profile/profile` |

Dormant page files still exist under `pages/pve/*` and `pages/simulator/wcl.*`; they are not current app entry points, but their page-level UI patterns can still pollute shared styles and audits.

### Component Owner Inventory

| Component | Current Adoption | Phase 1 Judgment |
| --- | --- | --- |
| `navigation-bar` | Used globally by registered and dormant pages. | Existing owner, but still needs AppShell/PageFrame boundary audit to avoid fake chrome and safe-area confusion. |
| `channel-dock` | Used by `pages/news/news` only. | Partial owner. Needs general ChannelDock contract before reuse across app tabs. |
| `ranked-feed` | Used by `pages/news/news` only. | Partial owner. Needs feed row, thumbnail, rank and save affordance contract. |
| `status-badge` | Used by `pages/builds/workbench` only. | Partial owner. Not enough to solve full `StatusVisual` state contract. |
| `action-button` | 0 page usage. | Present but not adopted. Cannot claim button system is componentized. |
| `evidence-ledger` | 0 page usage. | Present but not adopted. Evidence UI is still page-level in key surfaces. |
| `game-object-icon` | 0 page usage. | Present but not adopted. Real WoW icon/fallback boundary is not centralized. |
| `module-card` | 0 page usage. | Present but not adopted. Module/status cards remain page-private. |
| `page-frame` | 0 page usage. | Present but not adopted. App shell and page gutters are not centralized. |
| `wow-panel` | 0 page usage. | Present but not adopted. Panel geometry still risks page-level patching. |
| `ChatShell` | missing | Required for Chickenbro, but no component owner exists yet. |

### Material And Asset Inventory

- `pages/news/news.*` already references v2.1 material slices and pass36 fallback thumbnails, but the page owns too much layout geometry.
- `pages/builds/builds.wxml` and `pages/builds/workbench.wxml/wxss` reference `assets/generated/ui-v2-1-slices/20260703/*`, including workbench panels, sockets and status assets.
- `pages/simulator/simulator.wxml`, `pages/simulator/simc.wxml`, `pages/simulator/chickenbro.wxml`, `pages/simulator/tasks.wxml` and `pages/profile/profile.wxml` still reference old `assets/generated/ui-redesign/20260701/*` material.
- Existing imagegen output is not yet a clean production workflow because production pages still mix page-level geometry, pass-named assets and old whole-surface materials.
- True WoW objects must remain outside imagegen: class/spec/talent/equipment/source icons need a source map from verified repo assets, Battle.net/WebSim mappings, interface payloads, or user-provided material.

### Screenshot And Scorecard Evidence

| Evidence | Current Fact | Phase 1 Judgment |
| --- | --- | --- |
| `20260703-ui-v2-1-pass36/manifest-pass36l.json` | `status=complete`, `strictGateEligible=true`, `sceneCount=33`, `failedScenes=0`. | Screenshot manifest exists, but cannot stand alone as final acceptance. |
| `20260703-ui-v2-1-pass36/visual-scorecard-pass36l.json` | `pass=pass36l`, `strictGateEligible=false`. | Not a strict visual pass. |
| `20260705-pass37-current/manifest-pass37current.json` | `status=complete`, `strictGateEligible=false`, `sceneCount=11`, `failedScenes=0`. | Current-device evidence only. |
| `20260705-pass37-current/visual-scorecard-pass37current.json` | `pass=pass37current`, `strictGateEligible=false`. | Not final acceptance. |
| `20260705-pass52-current-os-fallback-full/.../visual-scorecard-pass52-current-os-fallback-full-redlines.json` | `status=not_accepted`, `score=71`, `accepted90=false`, `strictGateEligible=false`. | Explicit failure evidence. |

### DevTools Action State

- This Phase 1/2 update performs no WeChat DevTools actions.
- Runtime screenshot work remains frozen until a low-disturbance DevTools action ledger and `captureSafe=true` path are available for the target run.
- Default forbidden actions remain: close, restart, clear cache, switch appid, switch project, delete user directory, broad `cli open/close/auto`, login probes, and any action that can disturb the user's logged-in developer session.

## Phase 2 Current Problem Register

| Problem | Current Evidence | Required Prevention |
| --- | --- | --- |
| Goal/control-plane mismatch | Older pass36/pass37 docs and tests can still pull execution back to local repair framing. | active goal, goal doc, inventory doc and roadmap idea must all point to UI system rebuild. |
| Component owner gap | Many foundation directories exist, but most have 0 page usage. | Pages may only compose owner components after contracts and fixture matrices pass. |
| Page-level shape patching | `builds`, `workbench` and Chickenbro-related pages still carry private layout/status/button geometry. | Freeze page WXML/WXSS patches until a surface implementation permit names allowed files and owners. |
| State visual split | The workbench shield/exclamation issue showed base and glyph could drift apart. | `StatusVisual` must own base, glyph, center point, transparent boundary, size and modes. |
| Chickenbro under-designed | `pages/simulator/chickenbro` exists, but no `ChatShell` owner or full chat state matrix exists. | Chickenbro is a first-class surface with empty/generating/done/failed/evidence/drawer/input/long-scroll states. |
| Bottom tab and app shell boundary unclear | Prior screenshots and user feedback exposed fake chrome, repeated status bar cues and safe-area confusion. | Keep real WeChat chrome/tabBar. Do not render fake time, battery, Wi-Fi or capsule. |
| imagegen production flow incomplete | Production still references pass-named and old redesign assets. | Use only manifest-approved low-semantic slices in production; keep whole-page targets and fact-bearing images in reference/quarantine. |
| Route smoke gap | Previous work emphasized static scorecards more than navigation and interaction. | Route smoke must cover tab switching, page entries, back, workbench jumps, Chickenbro flows, task/detail and template operations. |
| Evidence promotion risk | pass36l manifest exists but scorecard is not strict eligible; pass52 score is 71 and not accepted. | No `runtime_verified` or `final_accepted` without target, implementation, crop, overlay, red-zone, scorecard and route smoke. |
| DevTools disturbance risk | Earlier workflow sometimes affected login/appid/runtime state. | Low-disturbance ledger first; no high-impact DevTools action without explicit fresh permit. |

## Freeze Rules

`scopedSourceEditsAllowed=false` for core page WXML/WXSS until an implementation permit exists.

Allowed during freeze:

- Documentation, inventory and roadmap updates.
- Static tests that guard goal alignment, asset boundaries, component ownership and evidence promotion.
- Component contract drafts, fixture matrices and browser harnesses that do not mutate core page layout.
- Asset/source-map audits and manifest validation.

Forbidden during freeze:

- Page-level WXML/WXSS layout fixes for `pages/news`, `pages/builds`, `pages/simulator` or `pages/profile`.
- Private class patches for status glyphs, panels, buttons, cards, gutters, input bars or chat bubbles.
- Production references to whole-page target images, reference-only images, quarantine images, fake chrome or fact-bearing imagegen output.
- Runtime verification claims based only on browser/source preview or OS fallback screenshots.
- High-disturbance DevTools actions.

## Route Smoke Gap Matrix

| Surface | Required Smoke Coverage |
| --- | --- |
| 资讯首页 | Enter tab, channel switch, scroll today list, open detail, back to list/home. |
| 职业专精 tab | Enter tab, class/spec/hero switch, workbench entry, old talent/gear/SimC/task entries remain reachable and visually de-prioritized. |
| 当前专精工作台 | `ready_to_simulate`, `blocked`, `partial`, `stale`, `source_reference`; evidence expand/collapse; jump to gear, talent, SimC and Chickenbro. |
| 天赋 | Load fallback and API payload, apply/import, save template, empty/blocked/source-reference states. |
| 装备 | Load gear payload, missing slot, select item/variant/socket/enchant, save template, blocked/source-reference states. |
| SimC | From workbench, missing inputs, confirm, submit, task created, task list/detail jump. |
| 炸鸡队长 | Direct tab entry, workbench context entry, empty session, generating, completed reply, failed reply, evidence explanation, topic drawer, new topic, input focus, keyboard avoidance, long-message scroll. |
| 任务 | List, empty, detail, back, status refresh. |
| 我的模板 | Empty, local templates, remote sync boundary, delete, template entry jumps. |

## Phase 3 Entry Condition

Design candidates may start only after this inventory remains true and the next work explicitly opens a design candidate permit. Implementation must not start from pass36 page patches; it must start from target-locked surfaces, component contracts, material manifest and route smoke plan.
