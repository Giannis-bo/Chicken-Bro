# 社区模板导入全链路 Runbook

## 适用范围

本手册覆盖社区天赋与装备模板的采集、归属、验证、去重、PostgreSQL 入库、read model、Taro 导入、个人模板保存、health、发布和回滚。

天赋规则由 [天赋模拟 Runbook](talent-simulation-full-chain-runbook.md) 管理，装备规则由 [装备模拟 Runbook](gear-simulation-full-chain-runbook.md) 管理。本手册只管理“外部样本如何成为可展示、可应用的模板”。

## 不变规则

- 社区模板是样本和建议输入，不是职业、天赋树或装备规则的真值。
- Raider.IO / WCL 等真实玩家来源必须保留 URL、region、窗口、样本、更新时间和提取方式。
- Manual fixture 与系统 baseline 只允许显式本地或诊断使用，不能伪装成线上玩家样本。
- 前端只应用后端返回的结构化模板，不跨专精补模板，不猜槽位，不拼 SimC profile。
- Read API、health 和页面加载不得触发外部同步或写库。
- 无法映射当前天赋 authority 或 canonical gear snapshot 的模板 fail-closed。
- 生产写库前备份 PostgreSQL target；同步结果必须可按 run 和 source 审计。

## 数据链路

```text
Raider.IO established collector
  -> 80 class/spec/hero/scenario candidate slots
  -> immutable ObservedBuildSnapshot
  -> current Talent Catalog + Gear Release projection
  -> complete TemplateSet with same-slot LKG
  -> candidate or retail PostgreSQL pointer
  -> /api/websim/talents and /api/websim/gear
  -> Taro import
  -> personal template
  -> /api/websim/profile final readiness
```

## Observed Build Registry

对外真实玩家模板以同一份 80 槽 `TemplateSet` 为唯一 owner：40 个专精各有两个 Hero 槽。每个槽的天赋与装备必须共享 `projectionId`、`snapshotId` 和 Raider.IO `sourceIdentity`；同一专精的两个 Hero 槽必须是不同角色。

每日同步只对新建或变化的快照执行精确装备回填与本地 projection 编译。快照和 dependency vector 均未变化时复用现有 projection，不重跑完整发布链，也不运行战斗 SimC。新角色完整通过时可自动切换；采集或映射失败时，已激活槽共同保留上一次天赋与装备并标记 `stale_lkg`，其他槽继续更新。首次激活必须 80/80 verified，任何 `pending_collection` 都阻断指针。

`candidate` 与 `retail` 指针隔离。候选部署必须先完成 80 个天赋读取/导入、40 个装备双模板读取、80 个装备精确导入、80 个同玩家身份匹配和一次指针回滚恢复；用户在微信开发者工具确认前不得激活 `retail`。

## 来源边界

| 来源 | 可提供 | 必须降级或阻断的情况 |
| --- | --- | --- |
| Raider.IO run/profile | 真实角色、run、天赋/装备样本和 M+ 上下文 | 当前 profile 专精与目标 run 不一致；缺 run-detail；无法归属 hero；结构不可解析 |
| Warcraft Logs | 战斗记录、角色支持证据、可验证时的模板签名 | 缺凭据、缺 combatantinfo、只能证明同角色而不能证明同模板 |
| Manual fixture | 本地测试夹具 | 未显式启用时不得进入同步或线上 read model |
| System baseline | 诊断 authority 与 UI 起点 | 不得称为社区样本、玩家模板、排名或 BiS |
| Default gear template | Verified catalog 上的可导入起点 | 不得称为真实玩家装备或毕业推荐；缺可执行 16 槽时阻断 |

WCL evidence 只用于说明和排序，不能绕过天赋或装备 authority。裸 DPS/HPS、热度或单一高层 run 不能直接成为强度结论。

## 天赋模板合同

### 入库

天赋候选必须依次完成：

1. 目标 `classKey + specKey + heroKey + scenarioKey` 归属。
2. Structured loadout 解析，或明确保留为 external/SimC-only raw code。
3. 当前 WebSim 节点映射与点数、choice、edge 校验。
4. `encode_websim_talents` 可重复编码。
5. Talent signature 去重和 source refs 合并。
6. 状态写入 `verified`、`pending_collection` 或带阶段 blocker 的 `blocked`。

Profile-current 专精与目标 run 不一致时，该样本应计为 source warning/skipped，不得写成目标专精模板。

每个来源摘要至少包含 candidate、verified、blocked、skipped、warning、error 和 gap 数量；blocker 要指向采集、抽取、归属、authority 或 encoding 阶段。

生产社区天赋矩阵以 `expected_hero_tree_triplets()` 的 80 个 `class/spec/hero` 槽位为准；每个槽位只保留一个 active、可导入的 winner。补洞采集必须先按目标职业和专精独立读取 Raider.IO 高分候选，再从 run-detail 识别英雄天赋并以 M+ 总分选出目标槽位 winner；不得用全局榜单、其他专精或系统 baseline 填洞。候选预算要先在目标专精间公平分配，剩余少量槽位时可以扩大该专精的深页窗口，但不降低 authority、归属或编码门槛。

每个对外 winner 必须带真实玩家名、服务器、实际区域、Raider.IO M+ 总分、更新时间、来源和可导入编码；任一字段缺失时不得替换完整元数据的 active winner。过期模板仍可导入，但必须显式标记“已过期”；采集失败保持最近一次已校验 winner，不能清空为伪成功或冒充最新数据。

### 读取

`GET /api/websim/talents` 必须：

- 只读 PostgreSQL；
- 按当前 class/spec 收敛模板；
- 只把通过 authority 的结构化模板标记为可视化/可编辑；
- 按 signature 与可见身份去重；
- 缺真实样本时返回明确的 `pending_collection` 槽，而不是借用其他 spec/hero 或系统模板；
- 返回 source、更新时间、evidence tier、可应用性和 SimC readiness。

前端切换 class/spec/hero 后才能应用目标不同的模板；raw external code 不得伪造成可编辑节点。

## 装备模板合同

社区装备候选必须：

- 映射到当前 class/spec 的 canonical slots；
- 保留 `gearBySlot`、`enhancementBySlot`、source 和 revision；
- 由当前 catalog 补齐并验证 variant，而不是信任 profile 展示属性；
- 经过 weapon/armor/slot/unique/embellishment compatibility；
- 经过 `merge_websim_gear_enhancements` 和 serializer readiness。

Observed-only、source-reference、partial 或错季候选必须阻断或诚实降级。

默认装备模板只能在 16 个 canonical slots 均来自当前 verified catalog、兼容规则通过且 serializer 可执行时生成。副属性权重是选择依据之一，不是 BiS 证明；饰品效果、坦克/治疗目标函数等未验证部分必须写入 warnings。

`GET /api/websim/gear` 必须区分真实社区模板与 default/diagnostic 模板，不能用后者填平真实玩家样本覆盖率。

## 前端与个人模板

前端可以：

- 展示 source、状态、更新时间和 blocker；
- 应用可视化天赋模板或结构化装备模板；
- 将应用结果保存为当前用户的个人模板；
- 在提交前调用 `/api/websim/profile` 重新验证。

前端不能：

- 跨 class/spec/hero 借用模板；
- 把 unavailable 槽隐藏成“已覆盖”；
- 修改来源身份或提升 evidence tier；
- 从显示文本反推装备或 SimC 字段。

## Health 合同

`/api/data/health` 只读展示：

- 每个来源的可用性、凭据与提取能力；
- 40 专精与英雄槽位 coverage；
- verified、pending、blocked、stale 和 skipped 数量；
- 首个 blocking stage、代表性原因和 next action；
- 当前 sync run、revision 和 checkedAt。

Health 不得触发采集、修复或 DB 写入，也不得把独立 source dependency 复制成大量虚假 spec blocker。

## 同步顺序

1. 明确目标赛季、场景、class/spec/hero 矩阵和来源预算。
2. 运行本地测试与只读 health 审计。
3. 备份实际写入的 PostgreSQL target。
4. 显式运行来源采集；记录 endpoint、region、窗口、预算和错误。
5. 执行归属、authority/gear validation、signature dedupe 和 promotion。
6. 写入 PostgreSQL，并生成 source summary、coverage matrix 和 blockers。
7. 只读调用 talents/gear API，抽样可应用性和个人模板保存。
8. 部署后复核 health、关键 API 与定时任务状态。

外部下载、依赖安装或新的来源访问遵循 `AGENTS.md` 的网络规则；已获授权的已知云服务器例行同步和部署按仓库云端规则执行。

## 验证

```bash
python3 -m unittest tests.raiderio_payload_test
python3 -m unittest tests.websim_payload_test
python3 -m unittest tests.postgres_cache_store_test
node --test tests/builds-page.test.js tests/build-template-storage.test.js
npm run typecheck
npm run test:taro
git diff --check
```

远端至少复核：

- `/health`
- `/api/data/health`
- 一个有 verified 样本的天赋专精
- 一个 pending/blocked 天赋槽
- 一个真实社区装备模板
- 一个 default/diagnostic 装备模板边界
- 保存后再次加载的个人模板

HTTP 200、模板条数或 coverage 数字不能替代 source、authority、blocker 和可执行性检查。

## 回滚

### 代码问题

回退代码并重新部署，保持可信 PostgreSQL 数据不变；复核 read model 和 health。

### 同步污染

1. 停止相关同步 timer/service。
2. 备份当前异常 PostgreSQL 状态。
3. 恢复本轮同步前的 PostgreSQL 备份，或按可审计 run/revision 回退本轮写入。
4. 重启服务并复核 coverage、API 和个人模板边界。

SQLite 备份不能恢复为线上 runtime fallback。来源规则错误必须补代码和测试，不能只删生产行。

## 发布清单

- [ ] 目标矩阵、来源预算和赛季窗口明确。
- [ ] Source URL、region、checkedAt 和 revision 可追踪。
- [ ] Class/spec/hero/scenario 归属通过。
- [ ] 天赋 authority 或装备 catalog/serializer 验证通过。
- [ ] Dedupe、promotion 和 blocker 可解释。
- [ ] 真实社区模板与 default/diagnostic 模板明确分层。
- [ ] PostgreSQL 备份和写入范围已记录在本次任务输出。
- [ ] 本地测试、health、关键 API 和个人模板 smoke 通过。
