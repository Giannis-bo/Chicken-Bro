# WOW 小程序 UI 系统重建 Two-Part Goal Sync

Status: `two_part_goal_sync`

Date: 2026-07-07

This document records the two-part goal the user asked for: first a Codex execution goal, then a project documentation goal. The Codex goal is the work-control contract for this thread; the project documentation goal is the repo-control contract for roadmap, plans, design docs, artifacts, and tests. It does not promote any design to `target_locked`, does not activate an implementation permit, does not authorize page WXML/WXSS edits, and does not claim runtime verification.

## Latest Request Handling

The user asked to split the update into two visible steps: first provide the Codex goal, then update the project documentation. The Codex tool goal is already active and already points to `WOW 小程序 UI 系统重建`; the tool does not support rewriting an unfinished active objective. Therefore this document records the exact two-part wording for execution, while the active tool goal remains open. This is not a completion claim and must not be used to bypass target lock, active permit, runtime screenshots, route smoke, or DevTools ledger evidence.

## Step 1: Codex Goal To Use Now

Codex 当前执行 goal：

把 WOW 小程序 UI 优化从 `pass36/pass37` 局部修补、像素调参和单页 scorecard 路线，重置为 `WOW 小程序 UI 系统重建`。先建立可复用、可验证、可解释的 App 级 UI 生产系统，再按单 surface active implementation permit 接入真实页面。执行必须依次经过：问题登记、组件 owner、imagegen 低语义素材 manifest、真实 WoW source map、target lock、单 surface permit、component/browser precheck、真实微信小程序截图、组件 crop、overlay/red-zone/scorecard、route smoke、DevTools action ledger。

当前线程可以推进文档、组件合同、素材边界、source map、测试、harness、manifest、precheck 和证据审计；没有 active implementation permit 不改核心页面 WXML/WXSS；没有真实微信小程序截图、组件 crop、overlay/red-zone、scorecard、route smoke 和 DevTools action ledger，不得声明 `runtime_verified`、`final_accepted` 或目标完成。

## Step 2: Project Documentation Update Contract

项目文档 goal：

把上述 UI 系统重建作为长期产品与工程控制面同步到 `docs/roadmap.md`、`docs/roadmap/ideas.md`、`docs/plans/`、`docs/design/`、`artifacts/ui-system-rebuild/` 和测试。文档只记录方向、边界、证据、状态和下一步，不能把 Codex 自信、旧 pass 产物、imagegen 整页图、浏览器预检、单页截图或主观评分写成真实小程序验收。

项目文档的状态晋级必须分层：`draft / design_candidate / target_lock_proposal / component_contract_draft / asset_manifest_draft / component_precheck / browser_component_precheck / source evidence / runtime_verified / final_accepted`。当前只能记录 `source evidence` 与 blocked gates；`targetLocked=false`、`activeImplementationPermit=false`、`pageIntegrationAllowed=false`、`runtimeVerified=false` 保持不变。

## Codex Execution Rules

- Codex 负责推进当前工作方法：组件 owner、素材边界、target lock、单 surface permit、precheck、runtime evidence 和 route smoke。
- Codex 可以更新 roadmap、ideas、plans、design docs、tests、harness、manifest、source-level owner skeleton 和 component/browser precheck。
- Codex 不能把 pass36/pass37 旧 scorecard、主观评分、单张截图、浏览器预检或 imagegen 整页图当成最终验收。
- Codex 不能在没有 active implementation permit 时修改核心页面 WXML/WXSS。
- Codex 不能在没有真实微信小程序截图、组件 crop、overlay、red-zone、scorecard、route smoke 和 DevTools action ledger 时声明 `runtime_verified` 或 `final_accepted`。

## Documentation Control Rules

- `docs/roadmap.md` 记录正式路线、当前状态、证据链接和后续门禁。
- `docs/roadmap/ideas.md` 记录被采纳的讨论结论、风险、收益和待完成证据。
- `docs/plans/` 记录 goal、阶段盘点、permit、失败证据和执行边界。
- `docs/design/` 记录设计候选、target lock proposal、组件合同、素材 manifest、precheck 和 route smoke plan。
- Tests 必须守住状态晋级：`draft / design_candidate / target_lock_proposal / component_contract_draft / asset_manifest_draft / component_precheck / browser_component_precheck / runtime_verified / final_accepted`。

## Current Gate

- Codex tool active goal: `active`, already points to `WOW 小程序 UI 系统重建`, but its objective is not the exact two-part wording in this document.
- Codex tool objective rewrite: not supported while the active goal is unfinished; do not mark the existing active goal complete or blocked just to rewrite it.
- Current execution source of truth: this two-part document plus the roadmap entry.
- Target lock: `false`.
- Active implementation permit: `false`.
- Page integration allowed: `false`.
- Runtime verified: `false`.
- DevTools touched by this document: `false`.

## Required Transition

The next valid transition is explicit user confirmation or written modification of the target lock. After that, the project may write a `target_locked` decision record and convert exactly one draft permit into an active implementation permit. Until then, page implementation stays blocked.

## Evidence Links

- [WOW 小程序 UI 系统重建完整 Goal](2026-07-07-wow-mini-program-ui-system-rebuild-goal.md)
- [Phase 1/2 Closure Audit](2026-07-07-wow-mini-program-ui-system-rebuild-phase1-2-closure-audit.md)
- [Target Lock Decision Request](../design/2026-07-07-wow-ui-system-target-lock-decision-request.md)
- [Target Lock Readiness Review](../design/2026-07-07-wow-ui-system-target-lock-readiness-review.md)
- [Target Lock Decision And News List Detail Activation Packet](2026-07-07-wow-ui-system-target-lock-decision-and-news-list-detail-activation-packet.md)
- [Permit Coverage Matrix](../design/2026-07-07-wow-ui-system-implementation-permit-coverage-matrix.md)
