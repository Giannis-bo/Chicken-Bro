# 天赋模板闭环恢复与社区 winner 新鲜度

状态：正在推进
分类：Strict
需求合同：[release packet](../../artifacts/releases/2026-07-20-talent-template-recovery/requirement.json)
当前事实：[project-state.json](../project-state.json)、[roadmap.md](../roadmap.md)、[Harness](../harness.md)、[社区模板全链路 runbook](../community-template-import-full-chain-runbook.md)、[天赋全链路 runbook](../talent-simulation-full-chain-runbook.md)

## 用户结果与边界

玩家在天赋构筑页完成配置后，可以：命名保存至“我的”；从自己的保存或当前职业/专精/英雄天赋/场景唯一的社区 winner 导入；一键重置自己分配的点数。社区卡只展示后端已验证的真实玩家、服务器、实际区域、Raider.IO 大秘境总分、更新时间、来源和“已过期”状态；过期 winner 仍可导入。

M+ winner 必须先通过精确职业/专精/英雄天赋/场景归属和可视导入校验，再按 Raider.IO 大秘境总分降序选择。WCL 只作可信背书与同分决胜，绝不与 M+ 总分混算。一个 `(classKey, specKey, heroKey, scenarioKey)` 最多公开一个 winner。地区是采集到的实际地区，不能把 CN/EU 或默认区域伪装为角色事实。

同步每天执行；最近成功同步的 winner 在失败期间保留。连续 7 个日同步周期失败，或距最后成功同步超过 7 天，才标记为“已过期”。过期不是不可导入，也不是“最新推荐”。每个来源区域独立进行 3 次请求尝试、记录成功/失败结果并进入健康/告警门禁；单一区域失败只影响该区域的 freshness，不能中断其他区域、清空其他区域或覆盖上一次 winner；全部区域失败时保留旧缓存并返回 stale。

非目标：不改变天赋规则、客户端自行编解码天赋、让前端推断区域/新鲜度、清空最后成功 winner、把 WCL 表现分当作 M+ 总分、引入运行时同步、触发 backfill，或在用户真实微信验收前合入。

装备模拟复用此处每个 `(classKey, specKey, heroKey, scenarioKey)` 的候选序列与来源角色。正常情况下，两个 hero winner 的已采集装备快照直接成为该职业‑专精的两个社区装备模板；装备快照不完整或不合法时，装备侧只在同一 hero 的候选序列内递补，不回写、替换或重新排序天赋 winner。完整实施与验收见 [装备模板投影计划](2026-07-22-gear-template-projection.md)。

## 方案取舍

1. 只恢复 Taro 按钮：会继续消费不完整公共字段，无法兑现区域、分数、新鲜度和 winner 一致性，拒绝。
2. 前端按列表本地排序/判过期：会让不可信的客户端成为事实 owner，且不同页面可得到不同 winner，拒绝。
3. 后端归一 winner/read model + Taro 消费：唯一可同时保证排名、来源、新鲜度、失败保留和一键导入的方案，采用。

## 实施序列（每项先红后绿）

1. **后端事实与新鲜度。**
   - 在 `server/raiderio_payload.py` 将实际 `characterName`、服务器、地区、`run_ranking_evidence().score/rank` 绑定到每个天赋 loadout；生成的展示名不再硬编码 `CN`。
   - 在 `server/postgres_cache_store.py` 将 community talent slot 扩展为四元组，增加 M+ score-first comparator，且在 SQL 去重中以相同四元组/排序消重。保留 WCL 证据给同分决胜和展示背书。
   - 在 `server/postgres_cache_sync.py` / `server/community_template_sync.py` 保存每个区域的成功/失败结果及 winner 的 `lastSuccessfulSyncAt`、连续失败数。成功区域只重置自身 winner 的 failure count，失败区域只递增自身 winner；失败时保留前一条。`server/wow-community-template-sync.service` 显式配置 3 次 Raider.IO 请求尝试。严格阈值为 `failureCount >= 7 || age > 7 days`。
   - 在 `server/websim_payload.py` 和 `server/pg_gear_read_model_selectors.py` 输出单一可导入 winner 的结构化 `playerName`、`serverName`、`region`、`mplusScore`、`updatedAt`、`sourceName`、`freshnessStatus`、`isStale` 与受后端验证的 `talentState`。读取 API 不得触发同步。
   - 红测：Raider.IO metadata；四元组隔离；更高 M+ score 覆盖更强 WCL 的候选；同分 WCL 决胜；第 6 次失败仍 fresh、第 7 次失败 stale、7 天外 stale、失败保留 winner；read model 不丢弃 stale winner。

2. **typed contract 与 Taro 行为。**
   - 在 `packages/domain/src/entities.ts` 和 `packages/api-client/src/websim.ts` 加入上述社区 winner 字段及严格归一化；在 `apps/mini-taro/src/pages/builds/talent-simulator-model.ts` 新增可测试的默认标题与 winner 展示模型。
   - `TalentSimulatorPage` 保存前使用可编辑标题对话框，默认格式为 `职业-天赋-英雄天赋-时间`，再用现有后端导出+个人模板 repository 持久化。
   - 导入打开一个路由内 overlay（不新增常驻 target region），有“我的保存”和“社区模板”两个页签。我的保存通过 `/api/talents/import` 得到后端验证状态；社区 winner 直接提交其后端校验过的结构化 state。仅以 `canApplyVisual/status` 禁用，绝不因 `已过期` 禁用。
   - 重置继续只恢复 `initialTalentRanks` 的 granted 点，之后通过后端 validate 提交。
   - 红测：旧页面契约不再允许“导入=复制导出码”；标题可改且默认格式稳定；两种导入都调用对应后端 authority；唯一社区 card 展示实际 metadata；stale 可以导入；重置保留 grants、清掉玩家点。

3. **当前 UI 合同、回归和运行时。**
   - 保持八个稳定 target region 和底部三按钮几何；更新事实适配合同、页面契约和核心微信交互，让验收动作覆盖保存、我的导入、社区导入/过期、重置。
   - 开发中只跑受影响 Python/Vitest；收尾跑一次完整 Strict profile、架构审计、候选部署、API/健康/timer/log/区域状态 smoke 及真实微信验收。

## 影响与回滚

必须改：`raiderio_payload.py`、`postgres_cache_store.py`、`postgres_cache_sync.py`、`community_template_sync.py`、`websim_payload.py`、`pg_gear_read_model_selectors.py`、domain/API/Taro 页面与相关测试/当前 UI 合同。不得改：天赋 authority、客户端本地编码、个人模板账号隔离、GET 读接口无同步、现有目标图的稳定区域与几何。

候选失败或新鲜度异常时：回滚代码到候选前 commit；保留已有 winner；以最近成功 PG 快照恢复；可用 feature hide 暂时隐藏社区页签，但不得删除“我的保存”和重置。

## 验收

自动证据需覆盖排序、分槽、元数据、新鲜度、失败保留、typed normalization、保存/导入/重置及构建。候选环境需记录 final commit/runtime hash、`/health`、`/api/data/health`、受影响 talents payload、区域同步/失败计数、timer/backflow 和 rollback。最终用户在微信开发者工具中验收四项：命名保存、我的保存导入、社区 winner（含过期状态仍可导入）、重置。
