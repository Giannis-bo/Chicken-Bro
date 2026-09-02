# WOW Mini Program Roadmap

活动前端由 `apps/mini-taro` 负责，`packages/api-client/src` 负责 typed transport；根目录
`app.json` 与 `pages/` 只保留 14 路由兼容职责。机器可读 owner 矩阵见
[project-owner-map.json](project-owner-map.json)。

状态：`active`
更新时间：`2026-09-02`

## 本文职责

本文只保留产品方向、当前优先级和用户可见完成标准。执行步骤进入
[plans/README.md](plans/README.md)；接口、运行和部署细节进入 architecture 或 runbook；
过程记录由 Git 与 release packet 保存。

## 产品方向

下一代产品只保留炸鸡队长与 SimC 两个业务域，把角色来源、模拟任务、结果解释和跨端历史串成
可复用路径：

`微信登录 -> 提交 Raider.IO/WCL 链接 -> 冻结角色快照 -> 执行 SimC -> 交给炸鸡队长解释`

微信小程序与独立 HTTPS Web 复用一套 Taro 业务代码。小程序使用现有 `wx.login`/project identity；
Web 使用“微信扫码，在炸鸡队长小程序中确认登录”的辅助登录 session，通过不同会话映射到同一个内部
`user_id`，共享对话与 SimC 任务历史。当前 Web 原型先使用显式、可逆的 prototype bypass：不强制
`/api/v2/me` 或 Web Cookie，服务端生成隔离的 demo owner，prototype 数据不进入正式用户历史；正式二维码登录接口
仍保留为后续连接账号的独立路径。共享的是账号数据，不是 Cookie、OpenID、`session_key` 或客户端 token；正式 Web
登录不依赖网站应用 OAuth 或 UnionID。炸鸡队长继续由原生 Codex 负责理解和分析，服务端只保留身份、隐私、只读工具、
预算、超时、流式和持久化边界。SimC 只接受经过独立 Adapter 解析、统一 readiness 校验和单一 compiler 生成的
`CharacterSnapshot`。

资讯、天赋模拟、装备模拟、旧 WebSim 工作台及其一级入口已经退出目标产品。当前生产 14 路由、
Active Manifest、Gear Catalog 和旧 API 只作为迁移期 last-known-good 如实保留；在新路径完成 candidate、
回滚和用户验收前，不把“目标删除”写成“线上已删除”，也不继续扩展旧业务能力。

## 当前能力边界

| 能力 | 当前判断 | 下一步边界 |
| --- | --- | --- |
| 职业构筑与 SimC | Manifest v2、canonical resolver、精确装备/强化、任务保存和 26/14 执行边界已验证 | 仅作为迁移期 last-known-good；新链接输入链路不得依赖旧 Catalog、Resolver 或 Manifest owner |
| 至暗之夜 S2 | Active 与 Candidate 分层推进；生产仍是正式 Active Manifest generation 41，30555 freshness Candidate 已封存但未 promotion | Active 当前绑定 SimC 12.1.0.69299/f50a，`updateAvailable=true`，全局 `/api/data/health=partial`。2026-08-28 刷新后 season 18、WebSim sync 与生产 Gear Catalog 已 `verified`（567 items、20,910/20,910 variants）；Stat Weights 为新鲜 `partial`（23 accepted / 97 blocked），Community Templates 仍因 WCL combatantinfo seed/report 缺口和 Active observed compile 完整性门禁保持 `partial`，gear release catch-up 超时且没有改写 Active。Candidate Manifest `season-manifest:sha256:46c76d...` 未切换 Active；legality、Catalyst、spell/media、Community 与 cutover 继续独立裁决 | [cloud refresh evidence](../artifacts/releases/2026-08-28-cloud-main-data-refresh/evidence.json) · [freshness evidence](../artifacts/releases/2026-08-25-s2-freshness-rebase/evidence.json) · [source policy](../server/data/midnight-season-2/source-policy.json) |
| Exact-first runtime | `0030`--`0035` foundation `runtime_verified`；provider/worker disabled、eligible source 为零 | 仅在完整 owner source 出现后另开 activation 与真实微信验收合同 |
| 炸鸡队长 | 聊天表面、流式与原生 Agent 已有交付证据；Smart Question/Evidence Planner 仍有待验收范围 | 抽取为 Codex-only 主链；不把旧问题分类树、普通 LLM fallback 或逐 claim 门禁带入新架构 |
| 数据与发布 | PostgreSQL-only、Harness、验证矩阵、Taro owner 与 release packet 机制已建立 | 按 caller-proof 与新鲜验证逐项淘汰兼容面 |

## 当前实际状态分层

| 层 | 状态 | 当前事实 |
| --- | --- | --- |
| UI 源码与路由 | `active_unverified` | 活动 owner 是 `apps/mini-taro`，14 条 Taro/兼容路径完全同序；架构审计为 14 routes、14 contracts、284 checks、0 findings。视觉账本仍是 14 条 `UNVERIFIED`，历史 6 条接受和 8 条 waiver 不能改写为当前 14/14 通过。 |
| S2 生产 | `partial` | 正式 Active Manifest generation 41 保持不变并继续绑定 f50a SimC；season 18、WebSim sync、Gear Catalog 已新鲜 `verified`，Stat Weights 新鲜 `partial`，Community Templates、gear release refresh 与 cutover readiness 仍未闭合。 |
| S2 freshness | `Candidate` | 30555 replay、dormant release pair、Talent Catalog 与 Candidate Manifest 已验证；没有 Active pointer mutation。 |
| 云端代码身份 | `已完成` | 仓库最新树已用 no-bootstrap、no-async hot deploy 发布；deployable tracked set 逐文件 hash 与云端一致，`data_health_followup.py` 和 `postgres_cache_store.py` 均回到仓库 owner。部署脚本新增真实 tar 归档回归测试，忽略的微信产物与私有配置不再进入 backend archive。代码一致不提升业务数据状态；全局 health 仍为 `partial`。 |
| Web Codex 来源查询 | `Candidate 已验证` | 当消息包含 WCL 或 Raider.IO 链接时，原生 Codex 通过短期 capability 调用云端 API 进程内的只读来源网关；WCL live smoke 返回 `verified` 的 report/fight/events 证据，Raider.IO live smoke 返回 Giannis 的 `source_reference`。凭据保留在 `/etc/wow-v2-source.env`（`0600 root:root`），不进入 Codex 子进程；正式用户验收仍未闭合。 |
| 云端卫生 | `已完成（限定范围）` | 2026-08-28 已清除无引用候选、旧 SimC 可重建版本、Git 已删除的部署残留、178 份被当前 S2 恢复点替代的旧代码/数据备份，以及本次 tar overlay 重新带入的 `apps/mini-taro/dist`、`.swc` macOS 编译缓存与两份 `project.private.config.json`；部署排除已补测试防复发。正式 evidence、PG 数据与经 `pg_restore --list` 验证的最新 1.16 GB 恢复点、Exact-first foundation、Active/Candidate/单一 rollback 均保留。备份与数据刷新后磁盘为 77% 使用、16G 可用；清理不等于 Active promotion。 |

## 当前优先级

| 优先级 | 里程碑 | 完成标准 | 权威入口 |
| --- | --- | --- | --- |
| 正在推进 | 双端精简架构骨架 | 建立模块化单体 `/api/v2`、独立 Worker、`identity/chat/simc/ops` 数据 owner 和依赖守卫；不改变当前生产入口 | [父级架构](superpowers/specs/2026-09-01-chickenbro-simc-dual-client-architecture-design.md) |
| 正在推进 | 微信双端 Identity 与公网 Web 原型 | 小程序 exchange 与 Web 一次性扫码确认 session 使用独立会话并映射到同一内部 `user_id`；scene ticket/verifier 防重放，UnionID 仅可选，冲突 fail-closed；公网 Web 原型必须经真实二维码、确认页、Cookie 会话和候选回滚门禁 | [设计](superpowers/specs/2026-09-01-chickenbro-web-mini-login-design.md) · [实施计划](superpowers/plans/2026-09-01-chickenbro-web-mini-login.md) |
| 正在推进 | Codex-only 炸鸡队长与来源 API | 抽取当前原生 Codex runner、owner-bound 会话和 SSE；收到 WCL/Raider.IO 链接时必须调用云端已配置的来源 API 工具，禁止打开来源公网页面；Codex 或来源 API 不可用时明确失败，不静默切换普通 LLM 或模板回答 | [父级架构](superpowers/specs/2026-09-01-chickenbro-simc-dual-client-architecture-design.md) · [Web prototype evidence](../artifacts/releases/2026-09-01-chickenbro-web-prototype/evidence.json) |
| 下一步 | Raider.IO/WCL 到 SimC | 两个 Adapter 只输出统一 Snapshot candidate；readiness、compiler、Worker 和云端 SimC 形成单一可审计主链 | [父级架构](superpowers/specs/2026-09-01-chickenbro-simc-dual-client-architecture-design.md) |
| 正在推进 | Web prototype bypass 纵向交付 | Web 可直接进入隔离 demo owner；Chickenbro、真实角色快照和 SimC 只在各自 readiness/semantic gate 通过后可用；角色等级按原型默认满级 90 处理，其他来源字段仍需真实校验；候选和公网 smoke 保留回滚证据 | [设计](superpowers/specs/2026-09-01-chickenbro-web-prototype-design.md) · [实施计划](superpowers/plans/2026-09-01-chickenbro-web-prototype.md) |
| 后续 | 双端切流与 legacy 删除 | 独立 Web 域名、Web login session/小程序确认、跨端历史、候选、回滚与用户验收闭合后，删除资讯、天赋模拟、装备模拟及其 route/job/data owner | [父级架构](superpowers/specs/2026-09-01-chickenbro-simc-dual-client-architecture-design.md) |
| 暂缓 | 旧 14 路由 UI 与 S2 Catalog 扩展 | 当前线上事实、证据和回滚继续保留，但不再新增产品能力；由新双端路径验收后统一退役 | [project-state.json](project-state.json) |

## 装备模拟状态分层

| 层级 | 状态 | 当前含义 | 权威入口 |
| --- | --- | --- | --- |
| 长期目标合同 | 已完成 | v1 的用户主链、40/26/14 能力边界和 fail-closed 合同持续有效；不授予新执行权 | [目标架构](plans/2026-07-28-equipment-simulator-target-architecture.md) |
| v1 已完成基线 | 已完成 | generation 35 的 Manifest v2 已归档；全局数据健康仍为 `partial` | [project-state.json](project-state.json) |
| 至暗之夜 S2 End Game 数据候选 | 正在推进；Candidate 已封存，Active 门禁仍阻断 | PG 中存在新 Talent Catalog 与 dormant Gear/Catalog/Community/Exact pair；Candidate Manifest 完成绑定，但没有 pointer mutation。生产 season 18、WebSim 与 Gear Catalog 已在 2026-08-28 刷新 verified；Community aggregate/observed compile、Stat Weights、gear release timeout、spell/media、legality、Catalyst 与 cutover 仍是独立门禁 | [cloud refresh evidence](../artifacts/releases/2026-08-28-cloud-main-data-refresh/evidence.json) · [freshness evidence](../artifacts/releases/2026-08-25-s2-freshness-rebase/evidence.json) |
| S2 四类范围装备库完整闭环 | 正在推进生产门禁；30555 Candidate 已通过，Active generation 41 保留 | Candidate 数量与 replay 均 verified，但 30555 是证据绑定的 Candidate runtime，不是当前 Active runtime。生产继续以 generation 41/f50a 提供服务；最新 health 仍为 `partial`，新 SimC tag 只报告 `active_manifest_cutover_required`。必须先闭合 Community、Stat Weights、gear release、legality、Catalyst、spell/media 与 cutover gates，当前不切换 Active | [cloud refresh evidence](../artifacts/releases/2026-08-28-cloud-main-data-refresh/evidence.json) · [project-state](project-state.json) |
| 端到端完整性 Goal | 暂缓 / `blocked` | 缺获批 authority 时，不以现有测试替代 Universe 闭包或完整微信矩阵 | [Goal](plans/2026-07-29-equipment-simulator-e2e-completeness-goal.md) |
| `gear_detail` UI 验收 | 用户已确认收尾（保留手工 waiver） | typed API、替换/导入/保存代码路径与本地构建已验证；用户确认最新微信预览可收尾；社区导入与 authenticated save 未另行录制逐路径证据 | [状态账本](design/current-ui/runtime-review-status.json) · [closure evidence](https://api.chickenbro.cloud/wow-evidence/releases/2026-08-24-s2-equipment-library-evidence-v2/artifacts/releases/2026-08-24-s2-equipment-library-ui-closure/evidence.json) |

## 维护规则

- roadmap 保持方向与边界，不追加执行流水。
- 当前计划必须进入白名单；完成、停止或替代后删除其实施文档，Git 即过程归档。
- 稳定事实进入 architecture、governance、runbook 或 `project-state.json`；证据只链接存在且有 owner 的文件。
- 新想法先进入 [ideas.md](roadmap/ideas.md)，确认优先级后才进入本表。
