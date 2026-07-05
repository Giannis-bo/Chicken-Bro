# 文档地图

`docs/` 里现在保留两类文档：

- 当前契约：roadmap、架构文档和 runbook。凡是要改产品行为、数据契约、部署、模拟链路或 WebSim / SimC 逻辑，先看这里。
- 历史证据：带日期的实施计划、审计、交接和 Agent 产物。它们解释过去为什么这么做，但除非被当前契约明确引用，否则不作为最新决策入口。

## 先看这里

| 需求 | 当前文档 | 说明 |
| --- | --- | --- |
| 产品方向、里程碑和状态 | [roadmap.md](roadmap.md) | 长期控制台；功能落地后在这里更新状态和证据。 |
| 还没进入正式里程碑的想法 | [roadmap/ideas.md](roadmap/ideas.md) | 想法池和已采纳索引。 |
| 文档结构、历史计划落点 | [plans/README.md](plans/README.md) | 记录 `docs/plans/` 每份历史计划现在对应的真实入口。 |
| 职业专精、天赋、装备、SimC 入口 | [builds-architecture.md](builds-architecture.md) | 职业专精 tab 的产品和前后端架构。 |
| PostgreSQL-only 运行时、schema 域、数据归属 | [database-architecture.md](database-architecture.md) | 当前数据库契约。 |
| 装备库治理 | [gear-database-governance.md](gear-database-governance.md) | 物品、变体、宝石、附魔、美化和 health 的可信规则。 |
| 装备模拟更新和发布流程 | [gear-simulation-full-chain-runbook.md](gear-simulation-full-chain-runbook.md) | `/api/websim/gear`、装备序列化和 readiness 运维。 |
| 天赋模拟更新和发布流程 | [talent-simulation-full-chain-runbook.md](talent-simulation-full-chain-runbook.md) | `/api/websim/talents`、天赋规则、profile 和 simulate 运维。 |
| 社区天赋 / 装备模板导入 | [community-template-import-full-chain-runbook.md](community-template-import-full-chain-runbook.md) | 来源真实性、同步、promotion、展示、导入和回滚。 |
| SimC 提交和任务契约 | [simulator-simc-end-to-end.md](simulator-simc-end-to-end.md) | 当前模板到 SimC 任务链路，以及 legacy raw profile 边界。 |
| 资讯内容服务 | [news-architecture.md](news-architecture.md) | 当前资讯后端、来源保真、翻译和内容路径。 |
| 云端访问和运维 | [remote-debugging.md](remote-debugging.md) | 已知主机、服务路径、日志和 smoke 命令。 |
| 视觉 / UI 规则 | [ui-style-guide.md](ui-style-guide.md) | 小程序共享 UI 约定。 |

## 历史区域

| 区域 | 保留为 | 当前入口 |
| --- | --- | --- |
| `docs/plans/` 下的日期计划 | 历史实施证据 | 先看 [plans/README.md](plans/README.md)，再看上方对应的当前契约。 |
| `docs/superpowers/` 下的 Agent 规格和计划 | 历史执行产物 | [superpowers/README.md](superpowers/README.md)，以及其中链接到的 roadmap / runbook。 |
| PostgreSQL identity migration runbook | 带当前状态说明的历史迁移 runbook | 活跃运行时以 [database-architecture.md](database-architecture.md) 为准。 |
| `docs/evidence/` 下的截图或浏览器证据 | 支撑审计材料 | 以链接到该证据的 runbook 或 roadmap 条目为准。 |

## 维护规则

- 不要再把一次性实施笔记直接放到 `docs/` 顶层。
- 活跃产品方向放进 `roadmap.md` 或 `roadmap/ideas.md`。
- 可复用运维流程放进对应 runbook。
- 稳定系统契约放进对应 architecture / governance 文档。
- `docs/plans/` 下的日期计划作为历史实施证据保留，不为了匹配当前行为而改写旧文档。
- 计划落地或被取代后，更新 [plans/README.md](plans/README.md) 的状态和当前入口，不再新增中间态说明文档。
