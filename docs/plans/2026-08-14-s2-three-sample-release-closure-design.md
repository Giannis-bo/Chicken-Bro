# S2 三件样本最短发布闭环设计

状态：`范围已确认；三样本 golden prefix 已纳入四类范围 Candidate v69；未授权 Active Manifest、生产切换、提交或推送`

确认日期：`2026-08-14`

当前事实入口：[project-state.json](../project-state.json)、[roadmap.md](../roadmap.md)、
[S2 有限可选目录与社区 Exact 设计](2026-08-13-s2-selectable-catalog-community-exact-design.md)。

## 1. 目标

只闭环三条最短、真实可发布的用户路径：

1. 一件 S2 大秘境装备；
2. 一件 S2 团本装备；
3. 一件 S2 制造业装备。

每件都必须在现有装备编辑、保存和 SimC 任务链中对用户可见且可模拟。通过后只能说明这三件样本
可发布，不说明 S2 全量装备库已完成。

## 2. 最小公开集合

三件样本在第一次事实采集后固定 item/source identity，不因后续 SimC 失败静默更换。

| 样本 | 对用户公开的最小状态 | 本次不做 |
| --- | --- | --- |
| 大秘境 | 同一件装备的勇士最高 rank、英雄最高 rank、神话最高 rank | 每条轨道的所有中间 rank |
| 团本 | 同一件装备的勇士最高 rank、英雄最高 rank、神话最高 rank | 其他 Boss、难度或中间 rank |
| 制造业 | 同一产物的低档、中档、神话终点品质 | 完整制造业装备库或全部制造品质 |

这九个状态就是本试验的公开装备集合。这里的“三段轨道”以每条真实轨道的最终公开形态为代表；
`maxRank` 必须来自当次 S2 事实，不能硬编码为 `6/6`。

制造业还必须证明“可选择”，但只取最小可用集合：每个公开品质至少有两组官方合法的副属性选择，
以及“无美化”和一项官方合法美化。它不承诺展示该配方全部可能组合；未验证的选项不出现在 UI。

## 3. 三条路径的唯一事实边界

每条路径只有一份第一方事实记录，不让 API、DB2、SimC 或社区数据相互背书。API 仍负责来源、membership
和其能直接确认的游戏事实；只有 API 明确缺失且命中有限白名单的字段，才允许追加官方客户端 DB2 投影：

| 路径 | 游戏事实 owner | 运行时 owner | 阻断规则 |
| --- | --- | --- | --- |
| 大秘境 | 暴雪 Game Data API：来源、item、勇士/英雄/神话终点变体；仅对 API 缺失的 item variant/cap-track 字段使用有限 DB2 | 固定 SimC | 来源或 membership 不闭合就停止；DB2 不得扩张来源或猜测轨道 |
| 团本 | 暴雪 Game Data API：来源/Boss、item、三条终点变体；仅对 API 缺失的 item static/variant edge 使用有限 DB2 | 固定 SimC | 同上；DB2 不得替代官方来源/Boss/drop 关系 |
| 制造业 | 暴雪 Game Data API：产物公开身份；仅对 API 缺失的配方/品质/副属性/美化关系，使用获明确授权的暴雪客户端 DB2 | 固定 SimC | 关系无法从第一方表面闭合即 `blocked`；不得用 token、社区样本或公开 TACT key 猜测 |

第三方 parser/schema/listfile 只可用于读取官方 DB2 原始字节，不能成为游戏事实来源；Raider.IO 不参与本试验。
套装 membership 仍由官方 API 的 item-set/class 关系负责；只有套装转换保留属性、原始特效或转换边确实缺失时，才可按同一白名单追加 DB2 证据，不能生成通用替代物品。

`237842`「绽铸大斧」仍只是制造业探针候选：已知 SimC 会把最高品质解析为装等 46，而官方 API 基础装等为
197，且美化槽位关系未闭合。因此它不能直接入库，除非本路径重新通过全部门禁。

## 4. 复用现有发布链，不新建大体系

本试验不建设通用 S2 装备仓库、全量 Catalog、社区 Exact 池或新的发布模型。只在现有候选 / Catalog /
Resolver / Profile Compiler / SimulationManifest / SimC Task 链中加入一份隔离的“三件样本”候选。

候选至少保存：

- 三件固定 item/source identity；
- 九个公开状态及其 itemId、bonus、装等、静态属性和 canonical SimC 输入；
- 制造业的两组副属性和一项美化的合法边；
- 事实 revision、Catalog/Resolver/Compiler revision 与固定 SimC runtime identity。

候选验证失败不改现有 Active Manifest。通过候选部署和用户验收后，使用既有不可变 Manifest 与 CAS 回滚机制
发布；不另造一套 Trial Manifest。

## 5. 最小 SimC 矩阵

| 路径 | 必跑数量 | 通过条件 |
| --- | --- | --- |
| 大秘境 | 3 条终点轨道 | SimC 回读 item、bonus、装等和静态属性与第一方事实一致 |
| 团本 | 3 条终点轨道 | 同上 |
| 制造业 | 3 个品质 × 2 组副属性 ×（无美化 / 1 项合法美化）= 12 条 | 无未知 token、无装等漂移，且实际选择被 profile 回读 |

共 18 条固定 profile probe。全部通过后，才允许把九个状态和制造业的最小选项集合对用户公开。当前
SimC build 与事实 build 不一致时，直接标记 `SIMC_RUNTIME_REVISION_STALE`，不以 `returncode=0` 放行。

## 6. 用户可见闭环

不新增路由。在现有装备选择页中，将这九个状态标为“**S2 样本**”：

1. 玩家选择大秘境装备的勇士 / 英雄 / 神话终点之一，保存后提交 SimC 并看到真实任务结果；
2. 玩家选择团本装备的三条终点之一，完成同一流程；
3. 玩家选择制造业的低 / 中 / 神话终点品质，切换两组可选副属性和一项可选美化，保存后提交 SimC 并看到真实结果。

后端只返回已验证状态和选项；客户端提交伪造 item、bonus、品质、副属性或美化时必须拒绝。任一状态
变为 `blocked` 或 `stale` 时，不能降级到相似装备，也不能提交模拟。

## 7. 发布门禁与证据

正式发布只要求这五项：

1. 三件样本和九个公开状态均有已锁定的第一方事实；
2. 九个状态已通过现有 Catalog / Resolver / Profile Compiler；
3. 18 条固定 SimC probe 全部通过；
4. 三条真实微信选择、保存、提交、查看结果路径通过；
5. 候选部署可回滚，并按既有 Harness 与用户明确发布授权完成切换。

证据只沉淀为一份小型 release packet：三件事实收据、18 条 probe 结果、候选部署 smoke、三条微信验收和
回滚记录。没有全量覆盖率、社区模板矩阵、通用样本选择器或额外的发布框架。

## 8. 实施顺序

1. 取得本次三件样本所需的官方 API 采集授权，并使用已批准的有限 DB2 字段合同补齐 API 明确缺失的字段；
2. 选定并冻结三件样本，事实未闭合就停止，不开始 Catalog；
3. 用现有链路 materialize 九个状态和制造业最小选项，跑 18 条 SimC probe；
4. 候选部署，完成三条真实微信路径和回滚；
5. 用户明确允许后发布。

本设计原先的“仅三件样本、未授权执行”限制已被 2026-08-20 的用户授权覆盖；当前执行仍只生成隔离
Candidate，并把三样本 probe 作为 golden prefix 和代表性矩阵的一部分。Candidate 验证通过不等于
Active Manifest 或生产发布，后两者仍需单独的用户发布授权。
