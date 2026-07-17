# Winner 驱动的属性规则后台审计设计

**日期：** 2026-07-17
**状态：** 用户已确认方向；设计待审阅，尚未进入实现
**适用 Harness：** [Repo-native Harness](../../harness.md)（Strict）
**关联主合同：** [实时属性引擎](2026-07-17-real-time-gear-stat-engine-design.md)

## 1. 用户目标与边界

社区装备 winner 在日常选举中更新，意味着项目掌握了一份新的真实玩家装备快照。系统应以这份快照为候选对照，后台确认当前属性规则是否仍能复现对应的官方非战斗面板；但玩家导入模板、切换装备和查看属性必须继续即时，不得等待这次校验。

本设计确认：

- winner 变化是发现新对照样本的事件，不是属性公式本身的权威来源。
- 审计只读访问官方角色资料；不改写 winner、Release、Manifest、Resolver 选择或社区模板可用性。
- 审计不调用 SimC；SimC 仍只服务 DPS、场景模拟和独立复杂效果审计。
- 官方资料缺失、角色已换装或输入无法对齐时，结果只能是 `blocked` / `inconclusive`，不能宣称规则错误。

## 2. 推荐方案：winner 变更驱动、异步且去重的审计

不采用“每日全量抓取全部角色”，也不只依赖代码/fixture 变更时的 CI。推荐在既有 community Release 候选完成 winner 选举后，比较新旧 winner 的 canonical provenance；仅对真实变化且满足输入条件的 context 写入审计 intent。

```text
sealed candidate winner changed
        │
        ├─ unchanged / unsupported / missing source identity
        │        └─ record no-action or blocked; do not call external APIs
        │
        └─ eligible audit intent (deduplicated)
                 │
                 └─ independent background audit worker
                          │
                          ├─ official profile input differs → inconclusive
                          ├─ source unavailable              → blocked
                          ├─ fields all match                → pass
                          └─ same full input but fields differ → confirmed_mismatch
```

候选 Release 的正常 promotion 不等待 worker。审计 intent 带候选 Release identity；若该候选没有成为 active Manifest，则审计结果只保留为内部证据，不改变公开属性规则。

## 3. 触发资格与幂等键

`gear_release.elect_community_winners()` 的输出和 release refresh 已经包含 winner、`profileHash` / `gearHash`、class/spec、Selection Intent 与候选 community Release 身份。本机制只消费这些已封存事实。

一次外部审计必须同时满足：

1. 新行是有效 observed source 的 `winner`，且相对于 active winner 的 canonical `profileHash` 或 `gearHash` 已变化。
2. winner 可还原区域、服务器、角色名，以及完整的 Resolver canonical input；不能从昵称、物品名称或 UI 文案猜测。
3. 对应 `class/spec/race/level` 存在已发布或待验证的 `attributeRuleRevision`。不支持的 context 只记录 `not_applicable`。
4. 官方 Profile 在同一审计窗口返回的装备实例、item level、bonus、宝石和附魔可与 winner 的 canonical input 完整对齐。

建议的 `auditKey` 是下列字段的规范化哈希：

```text
candidateCommunityReleaseId + candidateGearReleaseId
+ templateId + profileHash/gearHash + canonicalInputSignature
+ manifestRevision + attributeRuleRevision
```

同一 key 只能有一个活跃审计。成功、blocked 和 inconclusive 都记录为终态；除非 winner/input/rule/manifest 变化，不重试外部请求。每个 release-refresh 周期应有明确预算（初版每个 `ruleContext` 至多一个 intent），避免大量 winner 变化放大为外部 API 风暴。

## 4. 审计状态和判定

| 状态 | 含义 | 对正常流程的影响 |
| --- | --- | --- |
| `not_applicable` | 当前规则 context 未发布或不在覆盖范围 | 无 |
| `blocked_source_unavailable` | 官方 API 不可用、权限不足或角色不存在 | 无；记录下一次输入变化后再尝试 |
| `inconclusive_input_mismatch` | 官方角色当前已换装，或任一实例/强化无法对齐 | 无；不得报规则错误 |
| `blocked_missing_evidence` | winner 缺少身份、variant 或稳定效果证据 | 无 |
| `pass` | 同一完整输入下，所有基础面板字段、raw rating 和百分比/效果均在该 revision 的精度内一致 | 仅增加审计证据 |
| `confirmed_mismatch` | 同一完整输入已证实，但逐字段存在超出规则精度的差异 | 创建 finding，阻止该 revision 的后续 promotion |

`confirmed_mismatch` 必须保存每个字段的 input、expected、actual、raw rating、百分比/效果、precision 和 source capture identity。它不应因一次普通 Profile 抓取失败或输入不一致而产生。

## 5. 公开规则与发布边界

审计是属性规则健康信号，不是 community winner election 的新准入条件。

- `pass` 不能自动把 candidate 样本或 `fixture_only` 规则提升为 `verified`；仍需来源账本、完整黄金样本和跨端 fixture 门禁。
- `blocked_*` / `inconclusive_*` 不阻止 community Release/Manifest 的正常更新，也不让小程序等待。
- `confirmed_mismatch` 阻止**下一次**包含该 `attributeRuleRevision` 的规则 promotion，并在 health/admin 形成可追溯 finding。
- 既有已发布规则不会因为单条审计记录自动下线。经人工确认规则确实失真时，才通过新的 rule revision 或 `feature_hide` 让受影响 context fail-closed；装备编辑、模板导入和 SimC 流程继续可用。

这一区分防止外部角色状态变化误伤用户，同时不把可证实的错误继续伪装为可信属性。

## 6. Owner、存储与运行模型

| 面 | Owner | 责任 |
| --- | --- | --- |
| winner election | 既有 `gear_release` / `gear_release_refresh` | 选举、封存候选 Release、仅发出 audit intent；不执行外部抓取 |
| audit queue/state | 新的 `attribute_rule_audit` 边界，复用 PG sync-state/受控持久化模式 | 幂等键、预算、状态、输入/输出摘要和错误分类 |
| official source adapter | 后端 Battle.net Profile client | 只读抓取、凭据不出现在 payload/log/fixture；不写装备目录 |
| comparison | 服务端确定性属性参考解释器 | 用 sealed canonical input 和固定 revision 逐字段比较 |
| public visibility | `attributeCalculator` rule publisher | 只消费已发布规则和人工确认的 finding 结论；前端不推断健康状态 |

实现时新增独立 audit worker/service，由 winner election 的已封存 intent 触发；它不得嵌入 `/api/websim/gear`、Resolver、页面事件或 community refresh 的同步关键路径。第一版只读外部源和审计状态；不运行 SimC、不写 catalog、不改变 active Manifest。

## 7. 验证与验收

本机制进入实现前必须具备：

1. 纯函数测试：winner diff、eligibility、auditKey 去重、预算、每种终态及确认差异分类。
2. 角色对齐测试：同一 canonical input 才允许调用参考解释器；任一 slot、bonus、gem、enchant 或 race/level 不一致必须是 `inconclusive_input_mismatch`。
3. 字段级 golden 测试：主属性、耐力、资源、所有绿字 raw rating 与百分比/效果逐项比较，精度来自 rule revision。
4. 无副作用测试：winner/Release/Manifest 内容不因 audit 成功、blocked 或 mismatch 改变；SimC worker 不被调用。
5. 候选部署 smoke：winner 变化能创建至多一个 intent；外部 API 超时不延迟 Release refresh，也不影响小程序导入、换装或属性本地计算。
6. 回滚演练：禁用 audit worker 后，winner election 与现有公开模板仍正常；保留既有审计记录和 rule revision，不需要数据回滚。

## 8. 范围外与分期

第一期不做全量历史 winner 回放、不做跨角色统计模型、不根据单次 mismatch 自动删除规则，也不新增玩家可见轮询状态。

实现分期为：

1. 纯审计合同、fixture、状态机与 input-matching 测试。
2. PG 持久化、独立 worker、官方 Profile adapter 和只读 audit intent。
3. health/admin finding、候选部署、真实小程序“审计不可用但切装仍即时”的验证。

只有本设计经用户审阅确认后，才编写实施计划并进入 runtime 实现。
