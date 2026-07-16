# 装备模拟全链路 Runbook

## 适用范围

覆盖装备 catalog、canonical resolver、release train、社区模板导入、异步属性快照、SimC serializer、PostgreSQL 同步、health、发布和回滚。

稳定数据规则见 [装备数据库治理](gear-database-governance.md)，产品与路由关系见 [职业专精架构](builds-architecture.md)。

## 不变规则

- Runtime 是 PostgreSQL-only；SQLite 只允许作为显式离线迁移源或备份输入。
- 装备事实先在后端归一，前端只消费 typed payload，不实现第二套职业、槽位、强化或来源规则。
- `verified` 必须有可追溯 source、当前赛季归属、结构化变体和可执行字段。
- 缺 metadata、变体、属性、来源或兼容证据时返回 `partial` / `blocked` 与明确 problem。
- Read API、health 和页面加载不得触发同步、写库或外部下载。
- Resolver、serializer、import 和 snapshot worker 都 fail closed；展示可用不等于 SimC-ready。
- 生产写库前备份实际 PostgreSQL target；代码与 DB 回滚分别处理。

## 权威链路

```text
Battle.net + SimulationCraft + governed rules + observed evidence
  -> PostgreSQL catalog / release manifest
  -> GET /api/websim/gear
  -> POST /api/websim/gear/resolve
  -> canonical selection + profile readiness
  -> POST /api/websim/gear/stat-snapshots
  -> immutable verified snapshot or explicit fail-closed outcome
  -> /api/websim/profile -> SimC task
```

社区模板通过 `POST /api/websim/gear/community-import` 原子转换为同一种 selection intent，再交给 resolver；不得在前端逐槽猜测或拼接。

## 可信来源

| 来源 | 可以决定 | 不能决定 |
| --- | --- | --- |
| Battle.net Game Data | 物品身份、来源、inventory type、Journal 与套装关系 | 当前实例完整属性、SimC 可执行性 |
| SimulationCraft | 变体属性探测、profile 语法和可执行性 | 官方掉落来源、玩家热度 |
| Raider.IO / WCL observed evidence | 玩家样本和候选发现 | 规则合法性、BiS、物品属性真值 |
| 仓库 governed mapping | 可审计的职业、槽位、制造业和例外规则 | 未登记的外部事实 |

社区截图、攻略和 UI target 只用于发现问题或表达界面，不得写成装备事实。

## 核心 owner

- `server/gear_contracts.py`、`gear_rule_matrix.py`：请求、结果和规则合同。
- `server/gear_resolver.py`、`pg_gear_authority_loader.py`：纯 resolver 与 PostgreSQL authority facade。
- `server/gear_result_envelope.py`、`gear_runtime.py`：revision-aware transport 与 runtime 组合。
- `server/gear_release*.py`、`gear_release_store.py`：manifest、shadow、refresh 与原子切换。
- `server/community_template_import.py`：社区模板原子导入与 fidelity 门禁。
- `server/gear_stat_snapshot*.py`：异步快照 API、store 和 worker。
- `server/websim_payload.py`：兼容 read model 与最终 serializer。
- `packages/domain`、`packages/api-client`：Taro typed contract。
- `apps/mini-taro`：活动消费者 UI；`pages/` 是迁移期兼容消费者。

## Catalog 与 release 合同

- Source 包含类型、赛季、状态、provenance 和更新时间；inactive、错季或诊断-only source 不进入选择。
- Verified variant 包含 item level/track、结构化属性、生成来源、SimC 实例字段和一致 revision。
- Socket、enchant、embellishment、crafted stats 是独立结构化 option；blocked option 不进入默认选择。
- 后端统一裁决护甲、武器、槽位、主属性、unique、套装、美化和专精规则。
- 活动 release manifest 是一次原子可读版本；读者不能混用不同 revision 的 catalog、rules 和 templates。
- Refresh 先构建候选 release、运行门禁与 shadow 对比，再切换活动指针；失败保持 last-known-good。

## Resolver 合同

`POST /api/websim/gear/resolve` 接收 `selectionIntent + profileContext`，返回 canonical result envelope：

- 每个槽位的 canonical selection、可应用 enhancement 和结构化 blocker；
- `revision` / signature，供客户端丢弃过期响应；
- profile readiness 与 serializer 所需结构化 payload；
- 不可执行状态不补默认值、不复用 stale option、不返回伪 verified。

客户端必须用递增请求序号和返回 signature 防止旧请求覆盖新选择。保存模板只保存 canonical snapshot、revision 和仍匹配的 verified stat snapshot。

## 社区模板导入

`POST /api/websim/gear/community-import` 必须原子处理整份模板：

- 保留可信 item/variant/enhancement 证据，输出逐项 adoption/problem；
- 任何被采用内容都再次经过当前 release/rule authority；
- fidelity 不足时返回可解释 blocker，不静默删槽、猜 option 或部分成功伪装完整成功；
- 导入结果进入 resolver，不形成独立模板事实源。

## 异步属性快照

`POST /api/websim/gear/stat-snapshots` 以 canonical selection signature 幂等创建或查询任务：

- `pending` 允许有界轮询；只有 signature 匹配的 verified snapshot 可写入模板 metadata。
- 换职业、专精、种族、场景、天赋或装备后，旧快照只读 stale；旧请求不得覆盖新状态。
- Worker 终态只能是 immutable verified snapshot，或带 problem/blocker 且无 snapshot 的 fail-closed outcome。
- 旧 `/api/websim/gear/stats` 只保留兼容职责，不是活动 Taro 路径。

## Taro 前端合同

- 通过 `packages/api-client` 调用 gear read、resolve、community import 和 stat snapshots。
- 页面不自行构造 canonical enhancement、合法性或属性快照。
- 换装备后用 resolver 返回值裁剪 stale draft；两个等价槽位仍保持独立 key。
- 请求竞态由 revision/signature 处理；loading、problem、partial 和 stale 都是显式 UI 状态。
- 提交前重新经过 resolver/profile readiness；前端不拼 SimC profile 字符串。

## 只读审计与更新顺序

更新前检查 data health、release manifest、source/item/variant/mod-option 分布、40 专精规则覆盖和重点武器样本。然后：

1. 明确版本、赛季、实例、套装、制造业和规则范围。
2. 运行本地测试与只读审计，列出 blockers。
3. 备份实际 PostgreSQL target。
4. 对写入脚本先 dry-run。
5. 按 source -> metadata -> variant -> mod option -> rules -> candidate release 顺序写入。
6. 运行 release gate、shadow 对比并原子切换。
7. 抽样 gear read、resolve、community import、stat snapshot 和 serializer。
8. 运行 40 专精 traversal、Taro 核心交互和远端 smoke。

## 验证

```bash
python3 -m unittest \
  tests.gear_contracts_test \
  tests.gear_rule_matrix_test \
  tests.gear_resolver_test \
  tests.gear_result_envelope_test \
  tests.gear_release_test \
  tests.gear_stat_snapshot_api_test \
  tests.community_template_import_test
node --test tests/gear-workbench-state.test.js tests/builds-page.test.js
npm run audit:ui-architecture
npm run typecheck
npm run test:taro
git diff --check
```

远端 smoke 至少检查 `/health`、`/api/data/health`、关键专精的 compact gear、resolve、community import dry sample 和 snapshot 状态流。HTTP 200 或单元测试只证明工程基础，仍需核对 revision、状态、blocker、来源和内容。

## 回滚

- 代码问题：回退代码并重新部署，不修改可信 DB；复核 health、manifest、resolve 和 serializer。
- 数据污染：停止写入任务，备份异常状态，恢复写入前 PostgreSQL 备份，重启后复核 release 与 40 专精 coverage。
- Release 问题：原子切回 last-known-good manifest，不拼接旧新 revision。
- 少量规则错误：先备份，再做最小修正；规则错误同时补代码和测试。

## 发布清单

- [ ] 活动 release manifest、revision 和 rollback target 已记录。
- [ ] Verified variant 缺属性和 provenance 为 0。
- [ ] Source、variant、option、compatibility blockers 可解释。
- [ ] 40 专精 traversal 与重点武器/护甲/美化样本通过。
- [ ] Resolver 对 stale/incompatible 输入 fail closed，竞态测试通过。
- [ ] 社区模板导入 fidelity 与原子性通过。
- [ ] 属性快照 verified/fail-closed 状态流与 signature 隔离通过。
- [ ] Taro 使用 typed canonical API，未保留第二套本地装备事实。
- [ ] PostgreSQL 备份路径、写入范围、health 与远端 smoke 已记录。
