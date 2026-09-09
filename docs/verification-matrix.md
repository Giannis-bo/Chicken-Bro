# Chickenbro Verification Matrix

状态：当前执行权威

本文件只定义双端 Chat/SimC 重构的验证入口。验证等级相互独立：本地通过不代表 candidate，通过 candidate 不代表生产切流，生产可用也不代表真实用户已接受。

## 证据等级

| 等级 | 能证明 | 不能证明 |
| --- | --- | --- |
| `local_verified` | 当前 commit 的合同、代码、测试和构建通过 | 云端数据、真实微信、生产流量 |
| `candidate_verified` | 隔离 DB/API/Worker/Web 与回滚通过 | 已切生产、用户已接受 |
| `live_verified` | 指定生产 identity 的业务 smoke 通过 | 用户双端体验已完成 |
| `user_accepted` | 用户明确完成真实 Mini/Web 验收 | 自动替代备份、恢复或清理证据 |
| `recovery_verified` | 独立介质可恢复为可核对的隔离副本 | 当前线上业务体验 |

`skipped`、`partial`、`blocked`、dry-run、HTTP 200、systemd active、Candidate 或 SimC return code 0 都不是成功等级。

## 本地验证入口

```bash
npm run test:control
npm run test:backend
npm run test:migration
npm run test:ops
npm run test:taro
npm run typecheck
npm run lint
npm run build:weapp
npm run build:h5
git diff --check
```

本地不能安装或运行 SimulationCraft。SimC 语义结果只在云端受控 runtime 上验证。

回答解决情况反馈的真实数据库与 API 用例为 `tests.app_chat_feedback_postgres_test`，纳入 `test:migration`；须配置独立 UTF8 `WOW_PG_TEST_DSN_V2`。UI 同时验证共享组件及 Mini/Web 页面提交、重新打开历史恢复；旧客户端不请求 `includeFeedback` 时必须保持原合同。

## 1.0 验证与历史阶段

2026-09-08 最新仓库/线上对齐与 Mini 1.0.5 上传见 [本轮复核](../artifacts/verification/2026-09-08-v1-close/alignment/README.md)。本轮仅文档与证据变化，fresh 前端335、后端421、控制面62项及类型/lint/小程序构建通过；H5/后端以无源码差异和部署文件哈希核验，不重跑迁移或宣称新的真人验收。

用户于 2026-09-08 接受当前 1.0 实现。新一轮源码验证、环境限制与构建身份见 [收尾验证](../artifacts/verification/2026-09-08-v1-close/README.md)，产品交付状态见 [版本说明](releases/1.0.md)。

| 范围 | 已有结论 | 证据边界 |
| --- | --- | --- |
| 六阶段重构 | 迁移、accepted_write、旧系统退役已完成 | 2026-09-04 历史 evidence，不重复执行清理 |
| 1.0 现有能力 | 用户整体接受当前实现 | 不等于所有历史设想均已实现 |
| 当前差异 | Web 更新日志、Mini 账号面板移除、FAQ 文案与文档同步 | 本轮 fresh tests/build/review 记录 |
| PostgreSQL | 账户互斥、软删除、持久化公开摘要及迁移测试 | 必须配置独立 UTF8 测试库；有 skip 不能称为全套通过 |
| 线上/微信平台 | 逐次发布记录与回滚目录保留 | 本地 build/DevTools 不代表代码已上传或公开发布 |

## Candidate 与切流

Candidate 部署前必须刷新云端只读清单并通过容量及白名单恢复门禁。部署与切流命令默认 dry-run；apply 只能使用审核过的 commit、inventory SHA 和对应恢复身份。生产切流和 legacy 退役本轮可在用户明确授权后使用 `--no-independent-backup --irreversible-no-backup-confirmation I_UNDERSTAND_NO_BACKUP_IS_IRREVERSIBLE`，该模式只免除独立备份/恢复副本，不免除迁移核对、真实双端业务验收、首条新写入、稳定健康和零引用检查。

```bash
bash server/deploy_chickenbro_candidate_lighthouse.sh --dry-run
bash server/cutover_chickenbro_lighthouse.sh --dry-run
```

真实验收至少覆盖：Mini 登录；小程序确认 Web 登录；Mini 创建 Chat 后 Web 可见并续聊；Web 创建 Chat 后 Mini 可见并续聊；任一端创建 SimC 后另一端看到同一任务、状态和结果；第二用户隔离；两端独立退出。

## 精确清理

本地清单在 apply 前必须绑定审核 commit 和每个文件的 SHA，且 `review=0`、`blocked=0`；实际 apply 在 Phase 5 acceptance 前必须拒绝。清理提交合并后，原始清单中的目标文件已不存在，最终只读复核会报告 `TARGET_MISSING` 以及清单基线已过期的 `INVENTORY_BASE_COMMIT_DIFFERS_FROM_HEAD`，这证明不会重放删除，不是新的待处理目标。

```bash
node scripts/build-chickenbro-simc-refactor-inventory.js \
  --rules docs/refactor/chickenbro-simc-disposition-rules.json \
  --output docs/refactor/chickenbro-simc-refactor-inventory.json
node scripts/apply-chickenbro-simc-local-cleanup.js \
  --inventory docs/refactor/chickenbro-simc-refactor-inventory.json \
  --dry-run
```

云端退休同样默认 dry-run，并保护 `chickenbro_prod`、`chickenbro-api.service`、`chickenbro-worker.service`、当前 Web/Mini identity、Nginx/TLS 与 `/opt/wow-simc/current`。数据库删除还要求零连接、零配置引用；独立恢复验证由默认恢复模式或本轮显式无备份授权二选一。

## 历史六阶段最终完成条件

以下要求描述六阶段整体退役的历史验收合同，不要求每次文档或 UI 收尾重跑迁移/销毁。任何新的生产操作仍应按当次范围取得证据与授权。

最终 evidence 必须同时包含：本地全套验证；candidate identity；白名单全量 + fenced delta 核对；生产切流和首条新写入；云端语义 SimC；本地/云端精确清理结果；隔离恢复演练；清理后真实 Mini/Web 验收；本地 `main`、`origin/main`、部署文件和 migration identity 一致；回滚窗口到期并按 manifest 退役。

任何一项缺失都不能把整体目标标为完成。相关入口：[当前架构](chickenbro-simc-architecture.md) · [生产 Runbook](chickenbro-simc-production-runbook.md) · [计划白名单](plans/README.md)

## 截图输入增量（2026-09-09，后端/Web 已发布）

`tests.app_chat_images_test` 使用 Pillow 完整解码验证；`tests.app_chat_images_postgres_test` 使用独立 UTF8 PostgreSQL，覆盖上传幂等、owner/CSRF、绑定原子性、历史视觉输入、过期及数量限制，纳入 test:migration。服务器实际模型/CLI、真实双端选择上传与阅读、第二用户访问拒绝都必须在 Candidate 上复验。入口默认关闭，代码测试与本地模型识别不等于线上开放。

本次截图任务例外：2026-09-09 用户明确“不需要验证微信小程序端了”，后续 Mini 验证/真机验收记为 `user_waived`，不当作通过；已有测试证据保留，服务端共享身份/隔离和 Web 完整联调仍在范围内。

截图增量正式证据见 [发布记录](../artifacts/verification/2026-09-09-chat-images/deployment/README.md)：源码 `72e6224f2`，fresh PostgreSQL 91 项无 skip，包含图片与断线后台生成组合；Web 真实发送和公网图片识别通过。后续新改动仍须重新验证。
