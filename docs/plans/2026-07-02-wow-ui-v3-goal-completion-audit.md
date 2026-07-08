# WoW 小程序 UI v3 Goal 完成度审计

> 审计时间：2026-07-02。
> 依据：`/Users/heyesheng/.codex/attachments/557c1a7f-0d12-4157-8226-927ae314a150/goal-objective.md`、`docs/plans/2026-07-01-wow-ui-v3-phase5-implementation-map.md`、当前 worktree。

## 结论

该 goal 尚未完成。

Phase 1 到 Phase 4 已有文件和产物证据，Phase 5/6 未完成。2026-07-02 用户否定原 v3 目标图，指出布局乱、内部元素溢出、背景杂乱，且整体不如早前重 UI 资产方向；随后已补 v3.1 重 UI 资产修正版目标图。当前仍需用户确认 v3.1 后才能改真实小程序页面、进入微信开发者工具最终验收，也不能把 goal 标记为完成。

## 已完成证据

| 要求 | 当前证据 | 判断 |
| --- | --- | --- |
| 信息资产盘点 | `docs/design/2026-07-01-wow-ui-v3-information-inventory.md` | 已完成 |
| v3 设计语言文档 | `docs/design/2026-07-01-wow-ui-v3-design-language.md` | 已完成 |
| imagegen 素材 manifest 完整记录用途和边界 | `assets/generated/ui-v3/20260701/manifest.json`，包含 6 个抽象布局素材、用途、禁用边界和真实资产规则 | 已完成 |
| 所有效果图为现状 vs 目标对比 | `artifacts/ui-v3-comparison/20260701-phase3/manifest.json`，`required=6`、`done=6`、`complete=true` | 已完成 |
| 工作台目标稿保留现状快速浏览信息 | manifest 中 `workbench_first_screen.preservedInformation` 覆盖职业、专精、英雄天赋、场景、readiness、checkedAt、blocker、action、四模块状态、模板数和证据摘要 | 已完成 |
| 真实图标规则明确且可落地 | v3 设计语言与 imagegen manifest 均要求职业、专精、天赋、装备来自 `gameAsset.iconUrl`、接口 `iconUrl` 或受控真实资产索引 | 已完成 |
| TasteSkill / subagent 评测已回收修正 | `docs/reviews/2026-07-01-wow-ui-v3-phase4-review.md` 与 v3 对比 manifest `phase4Review.status=reviewed_and_revised` | 已完成 |
| roadmap/ideas 更新证据链接 | `docs/roadmap/ideas.md` 已包含 v3 信息资产、设计语言、imagegen manifest、对比 manifest、Phase 4 评测和 Phase 5 实施映射 | 已完成 |
| v3.1 重 UI 资产修正稿 | `docs/design/2026-07-02-wow-ui-v3-1-heavy-ui-reset.md`、`assets/generated/ui-v3-1/20260702/manifest.json`、`artifacts/ui-v3-1-comparison/20260702-heavy-ui-reset/manifest.json` | 已完成 |

## 未完成证据

| 要求 | 缺失证据 | 判断 |
| --- | --- | --- |
| 用户确认 v3.1 目标稿后完成实施 | 当前没有用户确认 v3.1 修正版目标稿的记录；真实页面仍未迁移到 v3.1 语义和素材 | 未完成 |
| 当前专精工作台实施 | `pages/builds/workbench-state.js` 仍有 `iconFallback: 'S'` 和 `formatCount(..., ' 槽')`；页面仍引用旧 `ui-redesign` 素材 | 未完成 |
| 职业专精 tab 实施 | 工作台入口仍需 readiness、模板数、状态驱动 CTA 与 v3 surface 接入 | 未完成 |
| 资讯首页和滚动重点列表实施 | 资讯页仍需迁移到 v3 source ledger；旧素材仍在使用 | 未完成 |
| SimC / Chickenbro 承接态实施 | SimC 仍需 context bridge 收敛；Chickenbro 仍直接展示 `answerSource`、`confidence`、`job.status` 这类工程字段 | 未完成 |
| 任务和我的模板一致性修补 | 仍需和 v3 素材、模板状态、工作台路径对齐 | 未完成 |
| 官方小程序截图完整通过 | 还没有 Phase 6 微信开发者工具 14 场景截图 manifest | 未完成 |
| 测试通过作为最终验收 | 2026-07-02 开工前基线通过，但不是 Phase 5 实施后的最终验收 | 未完成 |

## 当前基线验证

2026-07-02 已运行：

```bash
node --test tests/builds-workbench-state.test.js tests/builds-page.test.js tests/frontend-api-client.test.js
node --test tests/simulator-page.test.js tests/news-page-style.test.js tests/ui-style-guide-implementation.test.js tests/profile-auth.test.js
git diff --check
```

结果：

- 第一组 `135` 个 Node 用例通过。
- 第二组 `68` 个 Node 用例通过。
- `git diff --check` 通过。

这些结果只证明当前基线稳定，不能证明 v3 实施完成。

## 下一步门槛

需要用户明确确认 v3.1 修正版目标稿。确认后进入 Phase 5，按以下顺序实施：

1. 当前专精工作台。
2. 职业专精 tab。
3. 资讯首页和滚动重点列表。
4. SimC / Chickenbro 承接态。
5. 任务和我的模板一致性修补。

完成实施后必须进入 Phase 6，用已登录的微信开发者工具会话截取 14 个真实小程序场景，并生成 `status: complete` 的截图 manifest。
