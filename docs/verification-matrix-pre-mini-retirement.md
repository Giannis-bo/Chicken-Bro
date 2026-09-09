> 历史存档：2026-09-09 小程序源码清理前的文档快照。不是当前执行说明；不授予发布、迁移或删除权限。

# Chickenbro Verification Matrix

状态：当前执行权威

当前验证以 Web-only / QQ 重构为准；后面的双端记录仅解释 1.0 历史。验证等级相互独立：本地通过不代表 candidate，通过 candidate 不代表生产切流，生产可用也不代表真实用户已接受。

## 证据等级

| 等级 | 能证明 | 不能证明 |
| --- | --- | --- |
| `local_verified` | 当前 commit 的合同、代码、测试和构建通过 | 云端数据、真实 QQ 登录、生产流量 |
| `candidate_verified` | 隔离 DB/API/Worker/Web 与回滚通过 | 已切生产、用户已接受 |
| `live_verified` | 指定生产 identity 的业务 smoke 通过 | 用户实际体验已完成 |
| `user_accepted` | 用户明确完成真实 Web 验收 | 自动替代备份、恢复或清理证据 |
| `recovery_verified` | 独立介质可恢复为可核对的隔离副本 | 当前线上业务体验 |

`skipped`、`partial`、`blocked`、dry-run、HTTP 200、systemd active、Candidate 或 SimC return code 0 都不是成功等级。

## Web-only / QQ 当前验收

- 本地：QQ provider 数据校验、浏览器 state 绑定、超时/取消/重放/并发消费拒绝、Cookie/CSRF/Origin、旧微信身份拒绝及第二账号隔离；真实 PostgreSQL 的 QQ identity 和 login attempt 持久化验证。
- Web：明确点击 QQ 登录后授权跳转；取消或失败可重试；回到站点后显示账号并访问自己的 Chat/SimC；刷新、退出、401 恢复正常。构建产物不包含可运行的小程序产品页面，也不出现微信扫码或小程序推广入口。
- 退役：WeApp 构建/预览/上传不再是交付步骤，旧微信和 Mini HTTP 登录入口不可用；保留旧业务数据和历史证据。
- 真实环境：QQ 应用审核、AppID/回调配置、真实 QQ 登录、业务成功及第二用户隔离分别验证。保存密钥、配置存在和本地模拟 provider 测试不冒充真实登录成功。
- 新部署使用可回滚的独立版本；历史无备份授权不适用。本次不删除旧账号数据或云端旧版本。

## 本地验证入口

```bash
npm run test:control
npm run test:backend
npm run test:migration
npm run test:ops
npm run test:taro
npm run typecheck
npm run lint
npm run build:h5
git diff --check
```

本地不能安装或运行 SimulationCraft。SimC 语义结果只在云端受控 runtime 上验证。

回答解决情况反馈的真实数据库与 API 用例为 `tests.app_chat_feedback_postgres_test`，纳入 `test:migration`；须配置独立 UTF8 `WOW_PG_TEST_DSN_V2`。UI 验证 Web 页面提交、重新打开历史恢复；旧客户端不请求 `includeFeedback` 时必须保持原合同。

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

## 历史六阶段 Candidate 与切流（不得作为本次授权）

以下容量、迁移及清理门禁属于已完成的六阶段重构，不要求普通文档或界面变更重跑。新的 Candidate 部署、生产切流按当次范围和生产 Runbook 取得授权、容量、恢复与业务证据；命令默认 dry-run，apply 只使用审核过的 commit、inventory SHA 和对应恢复身份。

历史六阶段曾在用户明确授权下使用 `--no-independent-backup --irreversible-no-backup-confirmation I_UNDERSTAND_NO_BACKUP_IS_IRREVERSIBLE`；它只免除了当次独立备份/恢复副本，没有免除迁移核对、真实双端验收、首条新写入、稳定健康和零引用检查。该记录不是新的无备份删除授权，不得重放到未来任务。

```bash
bash server/deploy_chickenbro_candidate_lighthouse.sh --dry-run
bash server/cutover_chickenbro_lighthouse.sh --dry-run
```

真实验收至少覆盖：Mini 登录；小程序确认 Web 登录；Mini 创建 Chat 后 Web 可见并续聊；Web 创建 Chat 后 Mini 可见并续聊；任一端创建 SimC 后另一端看到同一任务、状态和结果；第二用户隔离；两端独立退出。

## 历史六阶段精确清理（不得重放）

本地清单在 apply 前必须绑定审核 commit 和每个文件的 SHA，且 `review=0`、`blocked=0`；实际 apply 在 Phase 5 acceptance 前必须拒绝。清理提交合并后，原始清单中的目标文件已不存在，最终只读复核会报告 `TARGET_MISSING` 以及清单基线已过期的 `INVENTORY_BASE_COMMIT_DIFFERS_FROM_HEAD`，这证明不会重放删除，不是新的待处理目标。

```bash
node scripts/build-chickenbro-simc-refactor-inventory.js \
  --rules docs/refactor/chickenbro-simc-disposition-rules.json \
  --output docs/refactor/chickenbro-simc-refactor-inventory.json
node scripts/apply-chickenbro-simc-local-cleanup.js \
  --inventory docs/refactor/chickenbro-simc-refactor-inventory.json \
  --dry-run
```

云端退役同样默认 dry-run，并保护 `chickenbro_prod`、`chickenbro-api.service`、`chickenbro-worker.service`、当前 Web/Mini identity、Nginx/TLS 与 `/opt/wow-simc/current`。新的数据库删除要求零连接、零配置引用及独立恢复验证；历史无备份例外仅供追溯。

## 历史六阶段最终完成条件

以下要求描述六阶段整体退役的历史验收合同，不要求每次文档或 UI 收尾重跑迁移/销毁。任何新的生产操作仍应按当次范围取得证据与授权。

最终 evidence 必须同时包含：本地全套验证；candidate identity；白名单全量 + fenced delta 核对；生产切流和首条新写入；云端语义 SimC；本地/云端精确清理结果；隔离恢复演练；清理后真实 Mini/Web 验收；本地 `main`、`origin/main`、部署文件和 migration identity 一致；回滚窗口到期并按 manifest 退役。

任何一项缺失都不能把整体目标标为完成。相关入口：[当前架构](chickenbro-simc-architecture.md) · [生产 Runbook](chickenbro-simc-production-runbook.md) · [计划白名单](plans/README.md)

## 截图输入增量（2026-09-09，后端/Web 已发布）

`tests.app_chat_images_test` 使用 Pillow 完整解码验证；`tests.app_chat_images_postgres_test` 使用独立 UTF8 PostgreSQL，覆盖上传幂等、owner/CSRF、绑定原子性、历史视觉输入、过期及数量限制，纳入 test:migration。服务器实际模型/CLI、真实双端选择上传与阅读、第二用户访问拒绝都必须在 Candidate 上复验。入口默认关闭，代码测试与本地模型识别不等于线上开放。

本次截图任务例外：2026-09-09 用户明确“不需要验证微信小程序端了”，后续 Mini 验证/真机验收记为 `user_waived`，不当作通过；已有测试证据保留，服务端共享身份/隔离和 Web 完整联调仍在范围内。

截图增量正式证据见 [发布记录](../artifacts/verification/2026-09-09-chat-images/deployment/README.md)：源码 `72e6224f2`，fresh PostgreSQL 91 项无 skip，包含图片与断线后台生成组合；Web 真实发送和公网图片识别通过。后续新改动仍须重新验证。
