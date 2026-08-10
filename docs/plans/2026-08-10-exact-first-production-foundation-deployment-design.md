# Exact-first Production Foundation Deployment Design

状态：`implementation_allowed`。这是一个严格受限的生产基础部署任务：把已经候选验证且已合入的 `0030`--`0035` 与对应后端运行时落入正式 PostgreSQL；Exact provider 与 dedicated worker 继续禁用。它不承诺任何模板已经 ready，也不把 Task 5E 的后续档案覆盖变成前置条件。

## 用户结果

用户继续使用现有小程序的页面、入口、文案与交互。此次部署不会把任何缺少 authority 的模板伪装成可模拟，也不会把当前可用的旧用户流程替换成一个全量 blocked 的 Exact 入口。

它为下一条“首个已闭合模板”的体验路径准备真实运行底座：正式库可以安全保存 Authority Bundle、owner-scoped binding、V3 snapshot/job 与 Runtime Authority Release；只有将来某个已保存的远端 gear/talent source 完整通过 admission 后，现有页面才可能得到 Exact ready。

## 已核验事实（2026-08-10，只读）

- `origin/main` 为 `f4dbb13c2536eab3ae11367410fe79f1e1a2d2f1`；其 `server/`、`apps/mini-taro/`、`packages/` 与 Task 5C 最终候选运行时 `70e37b6f` 没有内容差异。候选 tree `516441faca2ac30b51190c29a416c391ce70d31d` 已验证 `0035` fresh/upgrade、ACL、V3 job/worker、provider-disable 与无 async backflow。
- 正式后端 active、`WOW_DATABASE_RUNTIME=postgres_only`、Exact worker inactive；根盘约 4.9 GiB 空闲、可用内存约 2.4 GiB、load average 低。
- 正式 migration ledger 为 `0029` / 29 行；`0030`--`0035` 及 Runtime Authority Release 三表均不存在。
- 正式库已有 797 个 ExactItemInstance、4,590 个 verified validation，且有 126 组 16-slot community template reference 同时处于 registry `verified` 与 `partial` 投影。它们只说明已有装备基线；不等同于 Authority Bundle、owner binding、effect record、profile authority 或 ready release。
- `app.build_templates` 目前没有可用的个人模板汇总行；因此本任务绝不启用 provider/worker，也不会把 community template 或 slot 相似性推断成某个用户的 saved source。

## 需求挑战与决定

反方风险是把“迁移已完成”说成玩家可用，或为了一个示例模板以 Catalog/latest/client input/手写 effect record 补齐缺失事实。两者都会破坏 Exact-first。

比较后采用两段式而非全量启用：

1. 只迁移而不部署运行时：不会影响用户，但不能验证正式后端能加载新的 schema。
2. 直接部署并启用 provider/worker：速度最快，但没有 owner-scoped source-to-bundle closure 时会制造不可信 ready 或使页面整体降级。
3. **推荐：生产 foundation deployment。** 部署与 `0030`--`0035` 同步，但以 feature-disable 保持 Exact API `EXACT_AUTHORITY_UNAVAILABLE`、worker inactive、timer 不动；随后单独进行一次只读 admission preflight。只有存在完整的 authenticated saved source、bundle/effect/profile/release closure 时，才新建首模板 activation 任务。

第 3 条是用户已确认的“先把能完成的完成”路径。它不下载数据、不创建 manual authority、也不重跑候选。

## 运行与回滚边界

- 运行时文件只可来自 `f4dbb13c`，并逐个 SHA-256 对齐；部署目录没有 `.git`，因此不可把目录假称 Git SHA。
- 不调用会 enable/start 多个 timer 的通用 `server/deploy_lighthouse.sh`。运行手册只允许一次备份、受限文件传输、`0030`--`0035` 单事务 apply、仅 `wow-backend` restart、health/schema/provider-disable smoke。
- `wow-gear-exact-authority-worker` 不安装、enable、start 或 restart；所有现有 timer 启用状态与 next/last 记录必须前后相等，且不启动 sync/backfill/health-followup。
- 成功 migration 是 append-only；不通过删除 `0030`--`0035` 回滚。若 transaction 未提交则自动回滚；若部署后 backend 不健康，恢复备份的运行时文件、重启 backend，并保留数据库/immutable rows 供审计。只有明确数据库异常才按已存 production backup 恢复。
- 不改 Catalog/Manifest pointer、generation 35、前端路由/JSX/文案/样式/导航、公开 payload 或 `/api/simulator/analyze`。

## 明确停止规则与后继

部署后唯一允许的首模板检查是只读 aggregate preflight：owner-scoped remote gear/talent row、0033 binding、每 slot Authority Bundle、effect records/occurrence index、八项 vector、release membership、server profile materialization 必须逐项完整且唯一。零行、多行、漂移、未知或 unsupported 任一项都记为该 source 的 literal blocked，创建零 job，保持 provider/worker disabled。

Task 5E 的外部/档案 authority 只在它能扩大覆盖范围时再处理；它不阻止此 foundation deployment。若 preflight 没有任何闭合 source，本任务完成于“安全 deployed foundation + 明确零 ready source”，而不是无限追问数据发布源。只有 preflight 命中至少一个完整 source，才授权一个新的、单模板、可回滚的 provider/worker activation task 和现有页面的真实微信验收。
