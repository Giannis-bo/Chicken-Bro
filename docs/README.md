# 文档地图

`docs/` 只保留当前契约，以及被当前架构或 runbook 精确引用的领域记录。只有本页和这些文档继续链接的文件可以进入执行上下文；Git 历史承担过程归档。

## 先看这里

| 需求 | 当前文档 | 说明 |
| --- | --- | --- |
| 机器可读状态与当前发布包 | [project-state.json](project-state.json) | Standard / Strict 工作第一入口。 |
| 产品方向、里程碑和状态 | [roadmap.md](roadmap.md) | 长期控制台。 |
| 还没进入正式里程碑的想法 | [roadmap/ideas.md](roadmap/ideas.md) | 想法池。 |
| 当前计划白名单 | [plans/README.md](plans/README.md) | 只有白名单中的计划拥有执行权。 |
| 需求分级与交付门禁 | [harness.md](harness.md) | Harness 的分类、证据和关闭规则。 |
| 关键领域 owner | [project-owner-map.json](project-owner-map.json) | 事实 owner、consumer、验证和发布触发器。 |
| 后端热点 owner | [backend-owner-map.json](backend-owner-map.json) | 后端拆分边界与 characterization anchors。 |
| 统一验证入口 | [verification-matrix.md](verification-matrix.md) | `harness` / `backend` / `frontend` / `full` profiles。 |
| 职业专精、天赋、装备、SimC | [builds-architecture.md](builds-architecture.md) | 构筑产品与前后端架构。 |
| PostgreSQL-only 运行时 | [database-architecture.md](database-architecture.md) | schema、数据归属和运行时契约。 |
| 装备库治理 | [gear-database-governance.md](gear-database-governance.md) | 物品、变体、强化和 health 的可信规则。 |
| 装备属性规则证据 | [gear-attribute-rule-source-ledger.md](gear-attribute-rule-source-ledger.md) | 已验证属性上下文与公开计算启用闸门。 |
| 装备模拟全链路 | [gear-simulation-full-chain-runbook.md](gear-simulation-full-chain-runbook.md) | resolver、release、属性快照、导入与回滚。 |
| 天赋模拟全链路 | [talent-simulation-full-chain-runbook.md](talent-simulation-full-chain-runbook.md) | 天赋规则、profile 和 simulate 运维。 |
| 社区模板导入 | [community-template-import-full-chain-runbook.md](community-template-import-full-chain-runbook.md) | 来源、同步、promotion、展示和回滚。 |
| SimC 任务链路 | [simulator-simc-end-to-end.md](simulator-simc-end-to-end.md) | 模板到任务与报告。 |
| 资讯内容服务 | [news-architecture.md](news-architecture.md) | 来源、翻译和内容路径。 |
| 云端运维 | [remote-debugging.md](remote-debugging.md) | 主机、服务、日志和 smoke。 |
| 14 路由 Target-First 重建 | [plans/ui-reconstruction.md](plans/ui-reconstruction.md) | 当前唯一 UI 执行计划。 |
| 当前 UI 控制面 | [design/current-ui/README.md](design/current-ui/README.md) | Target registry、证据策略和逐路由合同。 |
| CDN 与运行时素材发布 | [cdn-asset-publishing.md](cdn-asset-publishing.md) | 当前生产资源根、不可变发布与回滚。 |
| 稳定设计合同 | [../DESIGN.md](../DESIGN.md) | 设计语言、组件和素材边界。 |

## 维护规则

- 一次性实施、思考、审计和交接记录不进入长期文档。
- 活跃方向进 roadmap；稳定事实进 architecture / governance / runbook；多步骤执行只进计划白名单。
- 计划落地或被替代后删除文件并移出白名单，Git 历史即归档。
- 证据保存在 release packet 或当前 UI 控制面明确登记的位置，不复制成叙事流水。
