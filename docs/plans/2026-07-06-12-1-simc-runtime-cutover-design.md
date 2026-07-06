# 12.1 SimC Runtime Revision and Cutover Design

## 背景

2026-07-06 讨论确认：游戏大版本更新时，SimC 也必须作为独立运行时依赖纳入版本切换机制。装备 catalog 和天赋 catalog 决定小程序能生成什么 profile；SimC runtime 决定这个 profile 是否能被解析、执行，以及职业机制、APL、物品效果、天赋编码是否可信。

外部证据：

- [SimulationCraft 官方下载页](https://www.simulationcraft.org/download.html)说明 nightly builds 持续产出，并且每个 nightly 带源代码 git commit hash；官方也说明手工 release 容易过期。
- [SimulationCraft GitHub 仓库](https://github.com/simulationcraft/simc)是持续开发的模拟器，而不是静态数据包。
- [Raidbots 对 pre-patch talent desync 的说明](https://support.raidbots.com/article/68-major-talent-issues-with-the-war-within-pre-patch)表明，live / beta / PTR 之间的天赋树不同步会让 talent hash 只能适用于对应游戏版本。
- [Raidbots 支持文档](https://support.raidbots.com/article/69-why-isnt-my-spec-supported)说明其底层依赖 SimulationCraft，且新版本或 prepatch 阶段部分专精可能暂不可用。

本设计只记录模型、门禁和切换策略，不执行下载、构建、部署或生产写库。

## 核心结论

12.1 切换必须同时管理三条版本轴：

- `gearCatalogRevision`：装备、宝石、附魔、制造业、美化、套装转化实例字段。
- `talentCatalogRevision`：天赋树、英雄天赋、规则、import/export、SimC talent encoding。
- `simcRuntimeRevision`：SimC binary、source commit、game build support、generated data、smoke 结果。

正式小程序只使用 active retail SimC runtime。PTR/nightly runtime 可以提前安装到 staging 或 inactive runtime slot，用于 12.1 PTR 装备、天赋、套装转化和 serializer 联调，但不能自动成为正式 runtime。

## 受控操作边界

SimC 官方 runtime 更新链路不再要求逐次显式批准。以下动作在后台受控流程内可以直接执行：

- 获取官方 SimulationCraft nightly / source / artifact。
- 构建或安装新的 SimC binary。
- 替换 inactive runtime slot。
- 更新 `simc-version.json` 或等价 runtime manifest。
- 运行 SimC smoke、compatibility matrix 和回归检查。
- 切换 active SimC runtime pointer。
- 发现问题时回滚到上一版 runtime。

该例外只覆盖 SimC 官方 runtime 更新链路。Wago / Battle.net / Raider.IO / WCL 等外部数据采集、生产数据写库、gear/talent catalog active pointer 切换、依赖安装和非 SimC runtime 下载，不自动继承这个例外。

即使不逐次审批，SimC runtime 更新仍必须留审计记录：

- 来源 URL、source commit、artifact hash。
- binary 路径、构建时间、安装时间。
- 旧 active runtime、候选 runtime、切换时间。
- 执行命令摘要、smoke 结果、blockers。
- 回滚路径和上一版 runtime 保留位置。

## Runtime Revision Scope

每个 SimC runtime revision 至少记录：

- `simcRuntimeRevision`：例如 `simc-12.0-s1-20260706-commitabcdef`。
- `channel`：`retail`、`ptr`、`staging`。
- `status`：`candidate`、`ptr_executable`、`verified`、`partial`、`blocked`。
- `binaryPath`：实际执行的 `simc` 路径。
- `sourceUrl` / `sourceCommit` / `artifactHash`。
- `localTag` / `latestTag` / `gameBuild`。
- `builtAt`、`installedAt`、`checkedAt`、`activatedAt`。
- `compatibleGearCatalogRevisions`。
- `compatibleTalentCatalogRevisions`。
- `smokeMatrix`：单体、大秘境、装备、天赋、套装转化和 profile serializer 检查结果。
- `blockers`：无法解析 profile、新字段不支持、专精 APL 缺失、物品效果缺失、talent hash mismatch 等。

现有 `WOW_SIMC_BIN` 和 `WOW_SIMC_VERSION_FILE` 可以作为第一阶段 runtime pointer / manifest 入口；后续可以再抽象为数据库中的 active pointer。

## 与 Gear / Talent Catalog 的关系

SimC runtime 不应被 gear / talent catalog 隐式替代。

允许：

- S1 active gear + S1 active talent + S1 verified SimC runtime 正式对外。
- S2 PTR gear + S2 PTR talent + PTR/nightly SimC runtime 仅内部测试。
- S2 inactive retail catalog 预热时绑定候选 SimC runtime 做 smoke。

不允许：

- S2 gear catalog 已 verified，但 active SimC runtime 不支持新 item / bonus / embellishment 时进入正式 sim-ready path。
- S2 talent catalog 已 verified，但 active SimC runtime 不支持新 trait data / import hash 时允许正式提交。
- Catalyst `redirected_base_stats` 还不能被当前 SimC 解析时，把转化套装包装成 verified。
- 让正式小程序通过 query/body 选择 PTR SimC runtime。

切换 active gear / talent catalog 前，必须确认目标 catalog 与目标 SimC runtime 组合通过 compatibility gate。

## Smoke Matrix

SimC runtime 候选至少需要通过以下检查，才能晋升为正式 `verified`：

- `simc --version` 或等价版本探测能返回可解析版本和 commit。
- `server/simulator_e2e_smoke.py` 本地 fake-SimC 与真实 SimC 模式均可跑通对应阶段检查。
- 代表专精在正式场景中能返回 `simulation.ran=true` 和可解析 DPS：
  - `single`：`Patchwerk` / `300s` / `1 target`
  - `mythic_plus`：`DungeonSlice` / `360s` / `5 targets`
- 40 spec / 80 hero tree 的 talent profile serializer smoke 不出现系统性解析失败。
- 装备 serializer 覆盖普通装备、宝石、附魔、美化、crafted_stats、双武器 / 双戒指 / 饰品等核心槽位。
- 12.1 专项 fixture 覆盖 Catalyst `redirected_base_stats`。
- 新赛季装备、附魔、宝石、制造业 optional reagent 和美化 key 至少有代表样本。
- 旧 S1 模板在 S2 runtime 下不会被静默重解释为当前 verified；需要迁移或 blocked。

如果 smoke 失败，候选 runtime 保持 `partial` 或 `blocked`，不得切 active pointer。

## Health 与后台展示

`/api/data/health` 和后台门禁需要表达 SimC runtime 状态：

- active runtime revision、binary path、source commit、checkedAt。
- local/latest 差异和 `updateAvailable`。
- runtime 与 active gear / talent catalog 的 compatibility status。
- 最近一次 smoke matrix 结果。
- top blockers：binary missing、version stale、profile parse failure、talent hash mismatch、item option unsupported、APL/spec unsupported、Catalyst field unsupported。
- staging/PTR runtime 与 active retail runtime 分开展示。

正式小程序只根据 active retail runtime health 决定能否提交真实 SimC。PTR runtime health 只给后台 owner/admin 和测试环境看。

## SimC 任务与历史结果

每个 SimC 任务和可复用 snapshot 都必须记录运行时版本：

- `gearCatalogRevision`
- `talentCatalogRevision`
- `simcRuntimeRevision`
- `scenario`
- `profileSignature`
- `statSnapshotSignature`

历史任务展示仍显示原始结果和原 runtime；用户重新运行时应使用当前 active runtime，并产生新的任务记录。不能把旧任务结果静默标记为新 runtime 下的结论。

## Cutover 流程

1. 发现候选：根据官方 SimC nightly/source 获取候选 revision，记录 source commit 和 artifact hash。
2. 安装 inactive：安装到新 runtime slot，不影响当前 `WOW_SIMC_BIN` 或 active pointer。
3. 基础探测：执行版本、路径、权限和最小 profile 解析检查。
4. Catalog compatibility：绑定目标 gear / talent catalog 运行 serializer 和 smoke matrix。
5. 12.1 专项检查：覆盖新装备、新天赋、Catalyst `redirected_base_stats`、新附魔/美化/制造业字段。
6. 晋升候选：全部通过后标记 `verified`，写入 runtime manifest。
7. 切换 active：更新 active pointer / symlink / env，并重启相关服务。
8. 切后 smoke：验证 `/health`、`/api/data/health`、`/api/websim/profile`、`/api/websim/simulate` 和 SimC 任务提交。
9. 回滚：如切后失败，active pointer 回到上一版 runtime，并保留失败 revision 供排查。

## 验收标准

- 正式小程序无法读取或选择 PTR SimC runtime。
- active gear / talent catalog 与 active SimC runtime 不兼容时，真实 SimC 提交 fail-closed。
- 后台能看到 active 和 staging runtime 的版本、commit、smoke、blockers。
- SimC runtime 更新、切换和回滚有审计记录。
- SimC 任务保存 `simcRuntimeRevision`，历史结果不会被新 runtime 静默重解释。
- 12.1 S2 cutover 前，gear catalog、talent catalog 和 SimC runtime 三者 compatibility gate 全部通过。

## 后续实施提示

后续实现应 TDD 先行，至少添加以下 fixture：

1. `WOW_SIMC_VERSION_FILE` 中 active runtime 与 staging runtime 并存，正式接口只读取 active。
2. SimC binary 支持 S1 但不支持 S2 `redirected_base_stats` 时，S2 gear catalog 不能进入 sim-ready。
3. Talent catalog revision 与 SimC trait data revision 不匹配时，profile serializer blocked。
4. SimC 任务写入并回放 `simcRuntimeRevision`。
5. active pointer 切换失败时回滚上一版 runtime，并在 health 暴露 blocker。
