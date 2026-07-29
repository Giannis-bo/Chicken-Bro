# 装备模拟 Phase 4：单一 Manifest 切换与旧 Reader 淘汰

状态：`正在推进`

分类：`Strict`

基线提交：`ae537ff5bdfcca1984459747b909dcbcb59b5046`

## 1. 用户结果

玩家继续使用现有入口完成手动配装、社区模板导入、强化、保存和 SimC。切换后，
浏览目录、社区模板、Resolver、Profile、SimulationSnapshot 和任务执行必须从同一
活动 Manifest dependency vector 取得 Catalog、Exact Registry、Rule、Compiler 和
Runtime 身份；任何缺失或混版本都必须 fail closed。

用户可见行为不新增入口、不改变模板 ID、不改历史任务。40 个专精继续支持配装，
26 个输出专精可执行真实 SimC，14 个已确认不支持的专精在任务创建前明确阻断。

## 2. 当前摩擦与已验证事实

- 活动指针仍为 generation 32；Manifest v1 直接绑定 Gear/Community Release，
  但不绑定已封存的 CatalogRevision 和 Exact Registry。
- CatalogRevision
  `gear-catalog:sha256:2addca2ff52fdcc2d23c369572c88fba9919332927f07f10350d700654e5aa34`
  与 Exact Registry
  `gear-exact-registry:sha256:ef910dd82d402f035959e628295e7d2b05dd74aca02463163c452da2d5eeb88a`
  已分别通过 Phase 1/2 的生产候选和不可变校验。
- Phase 3 的 SimC 准备路径仍调用 `get_latest_gear_exact_registry()`；这允许“当前
  Manifest + 最新 exact”组合，不能满足单一活动版本。
- 公共 Gear、社区导入和 Resolver 都先读同一活动 Manifest，但 Catalog 浏览仍从
  旧 Gear Release membership 物化；旧 staging fallback 在正式活动绑定失败时仍存在。
- Phase 0 caller audit 的未分类 caller 已为零；Phase 4 还需要单独证明待淘汰 runtime
  reader 的 caller 为零。
- 全局 `/api/data/health` 当前为 `partial`。本阶段只迁移自己拥有的 Catalog、
  Exact/Simulation 和 Manifest 组件，不能把其他 owner 的 partial 包装成成功。

## 3. 目标合同

### 3.1 Manifest v2

新增 hash-addressed `active-season-manifest-v2`，在现有 Gear/Community/Talent 和
runtime dependencies 之外直接绑定：

```text
gearCatalogRevision
gearExactRegistryRevision
```

这两个身份同时进入 Manifest identity 和 dependencyRevisions，并与 Catalog、
Exact Registry、Gear Rule、源 Gear Release、Community Release 交叉校验。Manifest
v1 只保留为现有 generation 32 和回滚目标，不能进入 v2 consumer 的成功路径。

PostgreSQL 增加 Exact Registry header 和 Manifest 外键列；历史 v1 行保持只读，
新 v2 行必须完整绑定。所有 Catalog、Exact、Manifest、Snapshot 行继续 append-only。

### 3.2 单次绑定读取

活动或候选 reader 在一个 repeatable-read transaction 中绑定：

```text
pointer/generation
-> Manifest v2
-> Gear Release
-> Community Release
-> CatalogRevision
-> Exact Registry
```

返回一个不可变 binding。Catalog 浏览从 CatalogRevision 的 ItemDefinition 和
BrowseVariant membership 生成；强化候选和 Resolver 的底层权威仍可读取 Manifest
绑定的源 Gear Release，但必须对外报告 v2 的 CatalogRevision，禁止把 Gear Release
ID 继续冒充 CatalogRevision。

社区导入、Resolver、Profile、SimulationSnapshot 和 task preparation 必须使用同一
binding 中的 Exact Registry；删除 runtime `latest exact` 读取。历史 task 继续按自己
已封存的 SimulationSnapshot 执行，不重新绑定当前 Manifest。

### 3.3 兼容与淘汰

- 现有前端 Selection Intent 字段保持不变。
- BrowseVariant 对外保留 canonical `browseVariantKey`，后端负责映射到 Manifest
  绑定的源 variant；前端不能补写或推断旧 key。
- Catalog v2 的 BrowseVariant 身份由
  `itemId + progressionState + variantShape(itemLevel, bonusIds, staticFacts)`
  决定。同一轨道进度下，bonus 或静态属性不同的真实精确实例不得互相覆盖；事实
  完全相同的 observed aliases 可折叠到同一 shape。社区导入只能使用该 shape 已封存
  的 source alias，普通手动选择使用 Catalog 的 canonical source 并由服务端重新投影
  Catalog 静态事实，禁止把 observed profile 的宝石/附魔泄漏为默认值。
- v1 reader 仅用于 generation 32 回滚 smoke；v2 激活后线上成功响应不得回退到
  staging/latest/未绑定 reader。
- 独立 legacy-reader inventory 必须证明活动 backend、Taro 和 runtime tooling 的
  待淘汰 caller 为零，才能删除兼容入口。

## 4. 实施切片

### Slice A：Manifest v2 与不可变绑定

1. RED/GREEN 覆盖 v2 identity、必需依赖、Catalog/Exact/Gear/Community 交叉绑定。
2. 增加 PostgreSQL migration、Exact Registry header、v2 Manifest seal/load、
   candidate preview 和 CAS/rollback。
3. v1 保持可读和可回滚；不允许 v1 假装具备 Catalog/Exact 绑定。

### Slice B：消费者切换

1. 公共 Gear initial/slot 浏览改读 Manifest-bound CatalogRevision。
2. 社区导入和 Resolver 对外使用 v2 CatalogRevision，并验证 Exact Registry。
3. Profile、SimulationSnapshot、task preparation 改用同一 binding，删除
   `get_latest_gear_exact_registry()` runtime caller。
4. owned health 输出 Manifest、Catalog、Exact、Snapshot identity 与明确 blocker。

### Slice C：Shadow、caller 清零与候选

1. 先封存新的 Catalog v2 shape revision、对应 Exact Registry 与 Manifest v2；
   PostgreSQL 只移除旧的“同物品同进度唯一”约束，历史 Catalog/Manifest 行不改写。
2. 40/40 专精浏览、80/80 社区模板、8 ready/72 literal blocked loadout 分类。
3. 26/26 支持专精真实 SimC、14/14 unsupported 前置阻断、重复任务结果复用。
4. Catalog progression、属性、强化、虚空晋升和制造选择与 generation 32 基线逐项
   对比；任何 silent drop 或 fallback 都阻断。
5. legacy-reader inventory、无写 shadow、RSS/磁盘/耗时、服务、timer/backflow 和
   rollback 证据齐全。

### Slice D：CAS 发布与收口

1. 在 immutable candidate 上先验证，再以 generation 32 为 expected generation
   原子提升 v2 Manifest。
2. 真实 API 与官方微信完成手动配装、社区导入、强化、保存和 SimC 自测。
3. CAS 回滚到 v1、完成 API/SimC smoke，再恢复 v2；generation 必须单调增加且无 ABA。
4. PR CI、合入、生产部署、local/origin/cloud/Manifest/runtime identity parity、
   候选和旧 reader 清理、架构最终归档。

## 5. 验收与信任边界

- 一个成功响应内的 Manifest、Catalog、Exact、Rule、Compiler、Runtime revision
  全部一致；缺任何一个都返回明确 partial/blocked。
- 80 个社区模板引用的所有精确 source alias 都必须唯一落到一个 Catalog v2 shape；
  同一物品/装等存在多个真实 shape 时禁止 item-level 猜测，shape 外 alias 必须阻断。
- 40/40 浏览、80/80 导入、26/14 SimC 策略、快照字节确定性和结果复用全部通过。
- 55 条 Phase 2 多附魔 evidence gap 继续 literal partial，不得补值或升级为 ready。
- 正式切换、回滚和恢复均通过 CAS，候选失败不改变活动指针。
- legacy runtime reader caller 为零；无 staging/latest fallback 命中。
- owned health 可验证，全球健康仍按实际结果报告，不能以 `/health=200` 替代业务真值。
- 真实微信自测使用最新 `main` 产物；用户已授权 Codex 自动执行，不等待人工确认。

## 6. 回滚

- 代码和服务回滚保留 Manifest v1/v2 读取兼容。
- 指针只通过 expected-generation CAS 切换到上一稳定 Manifest。
- Catalog、Exact、ResolvedLoadout、SimulationSnapshot 和 result 行不删除、不改写。
- 任一 candidate、shadow、资源、微信或 caller gate 失败时停止 promotion；活动
  generation 保持不变。
