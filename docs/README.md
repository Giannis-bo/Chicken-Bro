# 文档地图

`docs/` 的当前执行上下文只围绕炸鸡队长 + SimC 双端重构、Harness 和生产恢复。旧资讯、14 路由、构筑、装备、天赋、WebSim、S2 Catalog 与 prototype 文档只在迁移/回滚仍有精确引用时暂留，没有新实现权；Phase 6 从工作树删除，Git 历史承担归档。

## 必读顺序

| 顺序 | 文档 | 用途 |
| --- | --- | --- |
| 1 | [project-state.json](project-state.json) | 机器可读状态、当前 phase、授权/ready gate 和执行权威。 |
| 2 | [roadmap.md](roadmap.md) | 用户价值、六阶段里程碑和完成标准。 |
| 3 | [当前架构](chickenbro-simc-architecture.md) | Principal、Chat、SimC、Worker、API、数据和双端边界。 |
| 4 | [生产 Runbook](chickenbro-simc-production-runbook.md) | 容量、独立备份、迁移、candidate、切流、回滚和清理。 |
| 5 | [验证矩阵](verification-matrix.md) | 每阶段自动、candidate、live、用户验收和恢复证据。 |
| 6 | [计划白名单](plans/README.md) | 六阶段唯一顺序执行入口。 |

## 控制面

| 文档 | 说明 |
| --- | --- |
| [harness.md](harness.md) | 任务分级、requirement/evidence/manifest、候选和 closure 规则。 |
| [project-owner-map.json](project-owner-map.json) | 8 个目标产品 owner 与 legacy factual baseline。 |
| [backend-owner-map.json](backend-owner-map.json) | 后端目标 owner；旧热点只保留 characterization/rollback 事实。 |
| [批准规格](superpowers/specs/2026-09-02-chickenbro-simc-total-rebuild-design.md) | 用户确认的最终范围与完成定义。 |
| [六阶段计划](plans/README.md) | Phase 1--6 的依赖、状态和门禁。 |

## 清单与容量

| 文档 | 当前结论 |
| --- | --- |
| [本地处置规则](refactor/chickenbro-simc-disposition-rules.json) | 有序 keep/migrate/delete；未知顶层 fail-closed 为 review。 |
| [本地逐文件清单](refactor/chickenbro-simc-refactor-inventory.json) | 绑定完整 commit 和逐文件 SHA；删除仍需 caller/link graph。 |
| [云端只读清单](refactor/chickenbro-simc-cloud-inventory.json) | 2026-09-02T13:43:05Z reachable；容量 blocked。 |
| [容量清理候选清单](refactor/chickenbro-simc-capacity-cleanup-manifest.json) | 四个精确数据库共 22.53GB；零当前连接/配置引用，但独立恢复缺失，全部仅为 candidate。 |
| [恢复通道只读清单](refactor/chickenbro-simc-recovery-inventory.json) | 控制台唯一系统盘快照早于当前数据且未做 restore；广州地域待挂载云硬盘为 0，且无独立挂载或已配置对象存储客户端，恢复 gate 仍 blocked。 |

本地 inventory 的 `delete` 和容量清单的 `candidate_only` 都不是删除授权。只读云端 inventory 与陈旧 provider snapshot 也不是 apply 授权；任何写入前都必须刷新并重新验证容量、连接、服务、引用、独立 archive 和 restore identity。

## 当前产品边界

小程序最终只有 `队长 | SimC` 两个 Tab，目标路由是：

```text
pages/chickenbro/index
pages/simc/index
pages/simc/tasks
pages/simc/task-detail
pages/auth/web-login-confirm
```

Web 与 Mini 使用不同 credential transport，但同一内部 `user_id` 和同一服务端 Chat/SimC 历史。正式客户端不得调用 `/api/v2/prototype/**` 或 legacy news/builds/gear/talent/WebSim API。

## 微信开发者工具预览

活动项目导入 `apps/mini-taro`，不要直接导入构建目录。前端变更通过用户验收并合入后，在最新 `main` 运行：

```bash
npm run refresh:weapp
```

这个命令会重建并验证 `apps/mini-taro/dist/weapp`，再尝试通过官方 DevTools CLI 打开项目。CLI 不可用时必须按输出手工导入，并明确说明仅构建通过；它不能替代真实小程序登录、扫码、跨端 Chat/SimC 或新的用户验收。

## 文档维护

- 活跃方向进 roadmap；稳定事实进 architecture/runbook/reference；多步骤执行只进计划白名单。
- 新架构和 Runbook 是唯一产品/生产操作权威；旧文档不能反向改变其范围。
- 计划完成、停止或被替代后，从工作树删除；需要长期保留的事实收敛到当前文档。
- release packet 保存阶段证据，不把一次性时间线复制进长期文档。
- Phase 6 删除文档前必须生成链接图，证明保留文档、代码注释、Harness 和当前 packet 无活动引用。
