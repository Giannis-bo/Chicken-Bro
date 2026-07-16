# 文档地图

`docs/` 只保留当前契约，以及被当前架构或 runbook 精确引用的领域记录。只有本页和这些文档继续链接的文件可以进入执行上下文。

## 先看这里

| 需求 | 当前文档 | 说明 |
| --- | --- | --- |
| 产品方向、里程碑和状态 | [roadmap.md](roadmap.md) | 长期控制台；功能落地后在这里更新状态和证据。 |
| 还没进入正式里程碑的想法 | [roadmap/ideas.md](roadmap/ideas.md) | 想法池和已采纳索引。 |
| 当前计划白名单 | [plans/README.md](plans/README.md) | 只有白名单中的计划拥有执行权。 |
| 职业专精、天赋、装备、SimC 入口 | [builds-architecture.md](builds-architecture.md) | 职业专精 tab 的产品和前后端架构。 |
| PostgreSQL-only 运行时、schema 域、数据归属 | [database-architecture.md](database-architecture.md) | 当前数据库契约。 |
| 装备库治理 | [gear-database-governance.md](gear-database-governance.md) | 物品、变体、宝石、附魔、美化和 health 的可信规则。 |
| 装备模拟更新和发布流程 | [gear-simulation-full-chain-runbook.md](gear-simulation-full-chain-runbook.md) | `/api/websim/gear`、装备序列化和 readiness 运维。 |
| 天赋模拟更新和发布流程 | [talent-simulation-full-chain-runbook.md](talent-simulation-full-chain-runbook.md) | `/api/websim/talents`、天赋规则、profile 和 simulate 运维。 |
| 社区天赋 / 装备模板导入 | [community-template-import-full-chain-runbook.md](community-template-import-full-chain-runbook.md) | 来源真实性、同步、promotion、展示、导入和回滚。 |
| SimC 提交和任务契约 | [simulator-simc-end-to-end.md](simulator-simc-end-to-end.md) | 当前模板到 SimC 任务链路，以及 legacy raw profile 边界。 |
| 资讯内容服务 | [news-architecture.md](news-architecture.md) | 当前资讯后端、来源保真、翻译和内容路径。 |
| 云端访问和运维 | [remote-debugging.md](remote-debugging.md) | 已知主机、服务路径、日志和 smoke 命令。 |
| 当前 14 路由 Target-First 重建 | [plans/2026-07-14-target-first-14-route-rebuild.md](plans/2026-07-14-target-first-14-route-rebuild.md) | 当前唯一 UI 执行入口；只读原始 target、当前业务源码和 `design/current-ui`。 |
| 当前 UI 控制面 | [design/current-ui/README.md](design/current-ui/README.md) | Target registry、活动证据策略和逐路由合同。 |
| 仓库设计规范 | [../DESIGN.md](../DESIGN.md) | 稳定设计合同；设计方向、数据可信、组件和素材边界。 |

## 维护规则

- 不要再把一次性实施笔记直接放到 `docs/` 顶层。
- 活跃产品方向放进 `roadmap.md` 或 `roadmap/ideas.md`。
- 可复用运维流程放进对应 runbook。
- 稳定系统契约放进对应 architecture / governance 文档。
- 文档只有仍被当前入口引用时才保留；无入口文件直接删除。
- 计划落地或被取代后，从 [plans/README.md](plans/README.md) 当前白名单移除并删除文件，不新增中间态说明文档。
