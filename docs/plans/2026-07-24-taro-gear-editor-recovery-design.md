# Taro 装备编辑器恢复设计

状态：`本地验证完成，等待精确候选 HEAD 的微信人工验收`

## 用户目标

玩家在装备页更换武器或其他部位时，先看到该部位的真实候选和物品明细；若候选还有等级轨道、制造属性等合法配置，必须先选定配置，再显式应用。宝石、附魔、美化同样先编辑草稿，确认后才由后端校验写入。

```text
部位 -> 候选装备 -> 合法等级轨道 / 制造属性 -> 显式应用 -> canonical Resolve -> 当前装备更新
宝石 / 附魔 / 美化 -> 兼容部位 -> 本地草稿 -> 显式确认 -> canonical Resolve -> 当前强化更新
```

## 已确认决定

- 点击候选只选中和查看明细，不能直接换装。
- “勇士 / 英雄 / 神话”等轨道只展示后端为精确候选返回的合法选项；前端不写死、不推断。
- 没有额外变体的装备也保留“应用”按钮，避免误触并保持所有部位一致。
- 玩家文案使用“美化”；内部字段、API 和 `embellishment` 名称不变。
- Resolve、网络或版本校验失败时，已确认装备和强化保持不变；不得展示未验证的成功状态。

## 范围与非目标

必须恢复当前 `gear_detail` 内部的候选详情面板和强化编辑面板：按槽位懒加载、候选详情、等级轨道选择、显式应用；逐 socket 宝石编辑、附魔/美化选择、限制提示、取消与原子确认。页面外层仍锁定滚动，编辑内容只在既有装备工作台区域滚动。

当前接口的制造属性行仅返回展示用 `key/simcOptions`，没有可提交给 Resolver 的 canonical option ID；本任务不得猜测、改写或直传这些字段。因此制造属性仅可作为候选详情中的只读信息，不开放成可应用选择。若需要开放，必须先用后端契约将其绑定到可校验的 `variantKey` 或 `craftedOptionId`，并按 Strict 重新立项。

不修改 `server/`、PG、公开装备来源政策、Release/Manifest、SimC 或社区模板选举；不让前端判断合法性、插槽数、唯一宝石、美化上限、来源质量或最终属性；不迁移或扩张 `pages/builds/detail.js`；不新增候选筛选、推荐排序、物品目录或新的视觉 target。

## 结构与 Owner

| 单元 | 责任 | 不拥有 |
| --- | --- | --- |
| `apps/mini-taro/src/pages/builds/detail.tsx` | 协调路由、草稿、`websim.gear(mode=slot)`、`gearResolve` 和成功后的提交 | 装备合法性与来源判断 |
| `apps/mini-taro/src/pages/builds/gear-detail-editor-model.ts` | 候选/变体选择、逐 socket 宝石替换或移除、附魔/美化切换、草稿差异的纯函数 | 请求和 React state |
| `packages/design-system/src/components/GearEditorSheets.tsx` | 候选详情与强化编辑的 Taro 控件、选择态、加载态、阻断提示、应用/确认/取消 | API 与装备事实 |
| `apps/mini-taro/src/pages/builds/gear-detail-model.ts` | 后端候选和增强选项的显示投影；完整保留多个 `gemOptionIds` | 缺失信息补全 |
| `apps/mini-taro/src/pages/builds/gear-request-fence.ts` | 防止旧槽位详情、Resolve、导入响应覆盖当前编辑上下文 | 业务事实 |

现有 `GearDetailComponents.tsx` 继续拥有摘要、强化摘要条、槽位网格和底部动作；新编辑面板独立，避免继续放大共享组件文件。

## 行为和异常

1. 初始页只从 `equippedSet` 读取当前可编辑装备；compact catalog 绝不升级为已装备或就绪事实。
2. 打开槽位创建候选草稿并按需请求 `mode=slot`。加载中显示骨架；关闭、切专精、导入或重置后，旧响应不能回写。
3. 选择候选或后端返回的等级轨道只更新草稿。没有可校验 ID 的制造属性只展示，不能变成草稿或启用“应用”；“应用”始终需玩家显式点击。
4. 点击应用时，页面构造 identifier intent 并调用 `gearResolve`。只有 verified 且仍是当前请求时，才替换该部位；只清除变化部位的旧强化，其他部位保持。
5. 打开强化时，先按需补齐已装备物品详情，再从已确认强化复制草稿。宝石按 socket 分别选择或移除，附魔和美化各保留一个选择；取消丢弃草稿。
6. 点击确认时一次 Resolve。成功后整体提交强化；失败保留已确认强化与编辑面板，并显示后端 blocker。
7. 409 revision conflict 重新加载并丢弃草稿；网络或 503 保留已确认状态与草稿，不写入未验证值。

## 合同、测试与验收

- 更新 `truth-adaptation.json`、`component-contract.json`、`core-interaction-contract.json` 和 `selected-control-contract.json`：候选应用与强化确认替代目前只验证职业切换的装备页核心交互；每个 socket 是独立选择边界，允许多个 socket 同时各有一个已选宝石。
- 单元/组件测试覆盖：候选不能直接应用、轨道选择后才可应用、同槽强化清除、跨槽强化保留、多 socket 编辑、取消丢弃草稿、限制阻断、Resolve 失败保留旧状态、409 重载和旧响应 fencing。
- 真实微信候选验证一件多轨道武器、一件无变体装备、一个多 socket 部位、一个附魔和一个美化；分别覆盖取消、失败提示和成功提交。

## Harness 边界

本任务为 `Standard / user_visible_runtime`。变更范围是活动 Taro、当前 UI 合同和真实微信预览；后端、数据库、公开 payload、定时任务与部署不变。

- 任务 release packet 冻结 requirement、evidence 和 manifest。
- 开发期只跑模型、组件和页面的定向测试；UI owner 变更额外运行架构审计。
- 最终由 CI 跑一次 `full`，对精确 PR head 做一次真实微信候选 smoke，并等待用户手工验收。
- 不需要候选后端部署；若 API 或 Resolver 必须改变，停止并升级为 Strict。
- 回滚为前端代码回滚；没有数据迁移、release pointer 或同步回流风险。

本地验证证据已记录在
`artifacts/releases/2026-07-24-taro-gear-editor-recovery/evidence.json`；其中
`gear_candidate_variant_apply` 与 `gear_enhancement_confirm` 均保持
`pending`，不得据此宣称真实微信验收、合入或发布完成。
