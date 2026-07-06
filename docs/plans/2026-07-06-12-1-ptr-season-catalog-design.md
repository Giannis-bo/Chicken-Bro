# 12.1 PTR Season Catalog Isolation Design

## 背景

2026-07-06 讨论确认：小程序正式上线后，如果 live 仍是 Midnight 12.0 Season 1，正式小程序只能读取 S1 装备、附魔、制造业和美化数据。即使 12.1 PTR 已经放出 Season 2 装备，S2 PTR 数据也只能服务内部采集、线下测试和切赛季预热，不能被正式用户读到。

12.1 的装备变更还引入新的套装转化语义：Catalyst 可以把任意可转化装备保留原属性地转成套装件。后续 SimC profile 需要支持实例级装备字段，例如 `redirected_base_stats`，不能再把套装件理解成固定属性模板。

## 已确认方向

采用 Hybrid Catalog：

- PTR 阶段使用独立测试库或独立 staging catalog 采集 `retail-12.1-s2-ptr`，供线下测试联调用。
- 正式生产 API 只读取 active retail catalog，例如 `retail-12.0-s1`。
- 12.1 正式发布前，可以在生产库中预热 inactive `retail-12.1-s2` catalog revision，但不能被正式小程序读取。
- 12.1 正式发布后，用 Battle.net live metadata、稳定 SimC、Wago/curated evidence 重新验证，再把 active catalog pointer 从 S1 原子切到 S2。
- 回滚时只回滚 active pointer，不删除 S2 数据。

## Catalog Scope

每条公共装备数据都必须带 catalog scope，至少包含：

- `expansion`：例如 `midnight`
- `patch`：例如 `12.0` / `12.1`
- `season`：例如 `s1` / `s2`
- `catalogRevision`：例如 `retail-12.0-s1`、`ptr-12.1-s2-build-xxxxx`
- `channel`：`retail`、`ptr`、`staging`
- `active`：只有一个正式 active retail revision 可被正式小程序读取
- `status`：`candidate`、`ptr_executable`、`verified`、`partial`、`blocked`
- `evidenceSource` / `sourceRefs`：Battle.net、SimC、Wago DB2、Wowhead PTR、official PTR notes、curated allowlist 等

`ptr_executable` 不等于 `verified`。PTR 数据即使能被 SimC PTR/nightly 跑通，也必须在 live 上线后重新通过正式门禁，才能晋升为正式小程序可用的 `verified`。

## 数据源与状态

候选发现：

- Wowhead PTR、官方 PTR notes、PTR client / Wago DB2 / SimC PTR 数据只负责发现候选。
- 候选可以入 staging catalog，但默认 `status=candidate` 或 `partial`。

可执行 PTR：

- 如果 SimC PTR/nightly 能返回目标装备的 JSON stats，可以标记为 `ptr_executable`。
- `ptr_executable` 只允许内部测试环境使用，用于 serializer、read model、40 专精 smoke、制造业/美化联调。

正式 verified：

- 必须经过 Battle.net live metadata / journal / item-set、稳定 SimC JSON probe、Wago DB2 或 curated allowlist 证据门禁。
- Raider.IO / WCL observed profile 只能提供真实装备实例和 bonus/gem/enchant 样本，不能单独把装备提升为正式 verified。

## API 与环境边界

正式小程序：

- `/api/websim/gear`、`/api/websim/profile`、`/api/websim/gear/stats` 只读取 active retail catalog。
- 不允许正式用户通过 query 参数读取 PTR，例如 `season=ptr`、`catalogRevision=ptr-*`。
- 前端不实现赛季判断，不按 itemId / 名称硬编码过滤错季装备。

测试与后台：

- PTR catalog 只允许线下测试环境、后台 owner 工具或明确内部配置读取。
- 后台可以展示 PTR coverage、blocker、candidate diff 和 promotion readiness，但不能改变正式 active pointer。
- Wago / Battle.net / Raider.IO / WCL 等外部数据采集、生产写库和 gear/talent catalog active pointer 切换仍需按对应 runbook 做 owner 决策。SimC 官方 runtime 获取、构建、替换 binary 和 active runtime pointer 切换是单独的受控后台运维动作，不逐次审批，但必须保留审计记录并通过 SimC runtime smoke / rollback gate。

## 切赛季流程

1. PTR 开放：采集 `ptr-12.1-s2-*` candidate catalog，生成覆盖率和 blocker 报告。
2. SimC PTR 支持：把可执行项晋升为 `ptr_executable`，跑 serializer 和全职业 smoke。
3. 上线前预热：准备 inactive `retail-12.1-s2` revision，生产 API 仍读取 S1。
4. 12.1 live：重新同步 Battle.net live metadata / journal / item-set，跑稳定 SimC probe，Wago/curated 证据对账。
5. 切换：当 S2 data readiness、simulation readiness、mod option readiness、40 专精 compact traversal、SimC version gate 都通过后，原子切 active pointer。
6. 回滚：如 S2 出现阻断问题，active pointer 回到 `retail-12.0-s1`，保留 S2 catalog 供排查。

## 装备模板影响

保存的装备模板必须绑定保存时的 catalog：

- S1 模板保存 `catalogRevision=retail-12.0-s1` 和结构化 `gearBySlot` / `enhancementBySlot`。
- 12.1 切换后，S1 模板不能被静默按 S2 规则重解释。
- 历史模板可以展示为“历史赛季模板”，但重新模拟前需要走迁移或重建。
- 若模板含 S1 已失效装备、附魔、制造业或美化，后端 serializer 必须 fail-closed，返回明确 blocker。

## SimC 门禁

12.1 Season 2 切换不能只看装备数据齐不齐，还要看 SimC 是否支持：

- 12.1 item data / bonus / crafted stats / embellishment token
- Catalyst 转化后的 `redirected_base_stats`
- 新附魔、宝石、美化和制造业 optional reagent
- 40 职业专精装备 profile 的真实执行

SimC 版本未满足时，S2 catalog 可以保持 staging 或 partial，但不能进入正式小程序的 sim-ready path。

## 验收标准

- 正式小程序在 S1 active 时，任何装备读接口都不会返回 S2/PTR 装备。
- 内部测试环境能读取 12.1 PTR S2 catalog，并输出 coverage、candidate、partial、blocked、ptr_executable 统计。
- PTR catalog 与 live catalog 使用同一套结构化模型和验证门禁，但状态语义清晰隔离。
- 切赛季是 active pointer 切换，有明确 preflight、smoke 和 rollback。
- 装备模板保存和回放都携带 catalog revision，历史模板不会被错季静默重解释。
- `/api/data/health` 或后台 health 能表达 active retail catalog 与 staging PTR catalog 的独立状态。
