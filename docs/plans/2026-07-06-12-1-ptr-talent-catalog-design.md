# 12.1 PTR Talent Catalog Isolation Design

## 背景

2026-07-06 讨论确认：天赋数据需要采用与装备类似的赛季切换和 PTR 隔离方案。正式小程序如果仍运行在 Midnight 12.0 Season 1，就只能读取 S1 的天赋树、英雄天赋、规则、社区模板和 SimC 编码能力；12.1 PTR / Season 2 的天赋变化只能进入内部 staging/PTR catalog，用于线下测试、联调和切赛季预热。

外部调研结论：

- Blizzard 12.1 PTR notes 已包含大量职业、专精、英雄天赋和 Apex Talent 变更，例如新天赋、移除天赋、节点位置互换、效果重做和数值改动。
- Battle.net Game Data API 不是稳定 PTR/future patch 数据源；PTR/future namespace 可能不可用，正式数据仍应等 live 后重新验证。
- Raidbots 对历史 pre-patch talent desync 的说明表明，live / beta / PTR 之间的天赋树不同步会导致 talent hash / import code 只能在对应版本正确工作。
- Wowhead PTR / Talent Calculator 可作为候选发现和人工交叉检查，但不能作为正式 `verified` 的唯一来源。

本设计只记录模型和门禁，不实现代码、不下载数据、不写库。

## 核心结论

采用与装备一致的 Hybrid Catalog，但天赋侧的主对象不是装备 item/source/variant，而是 talent tree / rule / encoding / template 四类 catalog。

正式小程序：

- 只读取 active retail talent catalog，例如 `retail-12.0-s1-talents`。
- 不允许用户通过 query 参数读取 PTR，例如 `talentCatalog=ptr-*`、`patch=12.1-ptr`。
- 前端不判断赛季，也不按 talentId、spellId、节点名硬编码修复规则。

内部测试：

- 12.1 PTR 数据进入 `ptr-12.1-s2-talents-*` 或独立测试库。
- 可以标记 `candidate`、`ptr_executable`、`partial`、`blocked`。
- 只能用于 owner/admin、线下测试环境、SimC PTR/nightly 联调和切赛季预热。

正式切换：

- 12.1 live 后，用稳定 SimC trait data、Wago DB2 TraitEdge、Battle.net spell/media 和社区模板重新验证。
- 当 40 spec / 80 hero tree、import/export、profile serializer、SimC smoke 和 health gate 全部通过后，原子切 active talent catalog pointer。
- 回滚时回滚 pointer，不删除新 catalog。

## Talent Catalog Scope

每条天赋 catalog 数据至少要带：

- `expansion`：例如 `midnight`
- `patch`：例如 `12.0` / `12.1`
- `season`：例如 `s1` / `s2`
- `channel`：`retail`、`ptr`、`staging`
- `talentCatalogRevision`：例如 `retail-12.0-s1-talents`、`ptr-12.1-s2-talents-build-xxxxx`
- `schemaRevision`：前后端读模型和保存模板 schema
- `simcBuild` / `traitDataBuild`：SimC generated trait data 来源
- `wagoBuild`：TraitEdge / DB2 补充规则来源
- `blizzardBuild`：spell/media/official metadata 来源
- `active`：只有一个 active retail revision 可被正式小程序读取
- `status`：`candidate`、`ptr_executable`、`verified`、`partial`、`blocked`
- `sourceRefs`：PTR notes、SimC、Wago DB2、Battle.net、Wowhead PTR、manual fixture 等证据引用

`ptr_executable` 不等于 `verified`。它只说明内部 SimC PTR/nightly 能编码或运行，不能直接进入正式小程序。

## 数据源与可信边界

| 来源 | PTR 阶段用途 | 正式 verified 条件 | 不能做的事 |
| --- | --- | --- | --- |
| Blizzard PTR notes | 发现新天赋、重做、移除、位置互换、系统性改动 | 只作为 live 后对账提示 | 不能证明本地节点、entry、edge 已可执行 |
| Wowhead PTR / Talent Calculator | 候选发现、人工 diff、视觉检查 | 只能作为交叉参考 | 不能作为 backend authority |
| SimC generated trait data | 节点、entry、tree type、encoding、profile preset | 稳定 SimC build 可解析并通过 40 spec / 80 hero matrix | 不能替代 Wago/Battle.net 展示素材和边规则对账 |
| Wago DB2 TraitEdge / Spell | 父子依赖、choice、point gate、spell text/icon 补充 | build 与 SimC catalog 对齐，缺口可解释 | 不能绕过 SimC encoding |
| Battle.net spell/media | 法术名、图标、描述、媒体素材 | live metadata 与 talent spell id 对齐 | 没有官方树 API 对账时，不能单独把 tree 标为 verified |
| Raider.IO / WCL community templates | PTR/Season 2 候选构筑和样本 | 当前 catalog 可解析、signature 去重、来源状态可追踪 | 不能把旧赛季模板静默当成新赛季模板 |
| Manual fixture | 测试、兜底 smoke、缺口定位 | 必须带 source/status/checkedAt | 不能被 GET 隐式生成或伪装成真实社区样本 |

## API 与环境边界

正式读接口：

- `GET /api/websim/talents`
- `/api/talents/validate`
- `/api/talents/export`
- `/api/talents/import`
- `POST /api/websim/profile`
- `POST /api/websim/simulate`

以上接口在正式小程序中只读取 active retail talent catalog。即使后端已经有 PTR catalog，正式用户也不能通过 query、body 或模板加载绕过 active pointer。

内部测试接口可以读取 PTR catalog，但必须满足：

- 只在测试环境或 owner/admin 配置启用。
- response 明确输出 `channel=ptr|staging`、`talentCatalogRevision`、`status`。
- 不能写入正式用户模板或正式社区模板池。
- 不能改变 active retail pointer。

## 保存模板影响

天赋模板必须绑定保存时的 catalog：

- `rawString` / `websimExportCode` 必须保存 `talentCatalogRevision`。
- 保存时记录 `classKey`、`specKey`、`heroKey`、`schemaRevision`、`simcBuild`、`encodingStatus`。
- 社区模板也必须记录来源赛季和可解析 catalog revision。

12.1 切换后：

- S1 保存的 `websim:` 导出码不能静默按 S2 树重新解释。
- S1 官方 import code / talent hash 如果只能在 S1 解析，应展示为历史模板或 `needs_migration`。
- 如果 SimC live 仍能接受外部 `talents=<code>`，可以走 SimC-only external path，但不能把它包装成当前 WebSim 可视化树。
- 用户要在 S2 下继续使用时，需要重新导入、迁移或重建，并通过当前 catalog validator。

## 社区模板影响

社区天赋模板需要按 catalog revision 分层：

- `community_template.status=verified` 必须限定在它验证通过的 talent catalog revision。
- 新赛季不能直接继承旧赛季 winner。
- PTR 阶段可生成 `candidate` / `ptr_executable` 社区模板，但正式小程序不可见。
- 12.1 live 后重新跑 community template sync，旧模板只能作为 history / diff / migration hint。

低风险展示可以保留：

- 历史模板卡片。
- “当前赛季不可直接应用”的标签。
- 迁移建议或重新导入入口。

不允许：

- 把旧赛季模板继续标为当前赛季推荐。
- 让旧 import code 失败后 fallback 成近似节点。
- 用 LLM 猜测新赛季对应节点。

## 切赛季流程

1. PTR candidate：基于 PTR notes、Wowhead PTR、SimC PTR/Wago PTR 生成 candidate catalog 和 diff 报告。
2. PTR executable：SimC PTR/nightly 支持后，跑 40 spec / 80 hero tree import/export/profile smoke，晋升可执行项为 `ptr_executable`。
3. 预热 inactive retail：准备 `retail-12.1-s2-talents` inactive revision，正式 API 仍读 S1。
4. Live 复核：12.1 live 后重新同步稳定 SimC、Wago DB2、Battle.net spell/media 和社区模板。
5. Cutover gate：`talent_catalog` data readiness、rule readiness、encoding readiness、SimC readiness、community template readiness、40 spec / 80 hero tree matrix 全部通过。
6. Active pointer 切换：把 active talent catalog 从 S1 切到 S2。
7. 回滚：如 S2 发现阻断问题，active pointer 回到 S1，保留 S2 catalog 供排查。

装备和天赋的 active pointer 最终需要协调：SimC 页面固定读取“当前 active talent catalog + 当前 active gear catalog”，不能出现 S2 天赋搭配 S1 装备被误标为正式 ready 的状态，除非明确是内部测试环境。

## Health 与后台展示

`/api/data/health` 或后台 health 需要能区分：

- active retail talent catalog 状态。
- staging/PTR talent catalog 状态。
- 40 spec / 80 hero tree 覆盖。
- `treeReady`、`ruleReady`、`spellReady`、`encodingReady`、`simcReady`。
- import/export roundtrip 状态。
- community template 当前赛季覆盖率和 stale count。
- SimC build / Wago build / Blizzard spell/media build。
- top blockers：缺 spec、缺 hero tree、entry 变更、edge mismatch、choice/gate 缺口、import code hash mismatch、SimC 不支持、spell/media 缺口、community template stale。

正式小程序只根据 active retail health 决定是否允许保存或提交 SimC。PTR health 只给 owner/admin 和测试环境看。

## 验收标准

实现时至少覆盖：

- 正式小程序在 S1 active 时，`/api/websim/talents` 不返回 12.1 PTR 节点、规则或社区模板。
- PTR 测试环境可以读取 12.1 talent catalog，并输出 candidate / ptr_executable / partial / blocked 统计。
- 保存天赋模板时写入 `talentCatalogRevision`，回放时校验 revision。
- 旧赛季模板在新赛季不能静默重新解释为当前可执行模板。
- `/api/talents/validate|export|import` 按指定 catalog authority 校验，不接受前端裁剪状态。
- `/api/websim/profile` 同时校验 active talent catalog 和 active gear catalog。
- 40 spec / 80 hero tree matrix、import/export roundtrip、profile/simulate smoke 均通过后才允许切 active pointer。

## 后续实施提示

后续实现应 TDD 先行，至少添加以下 fixture：

1. S1 active + S2 staging 并存，正式 GET 只返回 S1。
2. S2 PTR 新增/移除/换位节点，旧 `websim:` 导出码回放为 `needs_migration`。
3. official import code 在 catalog mismatch 时进入 SimC-only external 或 blocked，而不是硬映射。
4. 社区模板 winner 带旧 revision 时，在 S2 active 下标记 stale。
5. `/api/websim/profile` 拒绝 talent revision 与 gear revision 不匹配的正式 SimC-ready 输出。
