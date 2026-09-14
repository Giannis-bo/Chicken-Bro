# 文档整理前快照（仅供追溯）

本文件保留整理前原文，不代表当前状态或新增授权。当前入口见[verification-matrix.md](verification-matrix.md)。历史链接保持原相对位置，按具体证据需要读取，不作为日常执行必读。

---

# Chickenbro Verification Matrix

状态：当前执行权威

当前验证以 Web-only / QQ 重构为准；历史验证另见[存档](verification-matrix-pre-mini-retirement.md)。验证等级相互独立：本地通过不代表 candidate，通过 candidate 不代表生产切流，生产可用也不代表真实用户已接受。

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
- 退役：WeApp 构建/预览/上传不再是交付步骤，旧微信和 Mini HTTP 登录入口不可用；残余 Mini 源码、微信 provider 与原生传输分支移除；历史证据保留。
- 真实环境：QQ 应用审核、AppID/回调配置、真实 QQ 登录、业务成功及第二用户隔离分别验证。保存密钥、配置存在和本地模拟 provider 测试不冒充真实登录成功。
- 新部署使用可回滚的独立版本；历史无备份授权不适用。旧测试数据清理必须绑定本轮精确清单、零活动引用和独立恢复验证；QQ 账号不受影响。

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


## 小程序清理验收

- Web 登录、退出、CSRF、旧 Bearer 拒绝、两个独立浏览器的同账号历史与第二账号隔离均回归。
- 流式回复验证 UTF-8 分块、错误、取消、结束与超时；不再通过 Mini mock 验证已删除的实现。
- 删除文件须原先受 Git 跟踪且无 WIP，保留清单；不删除未跟踪预览图或其他任务证据。
- 数据先按 provider/owner 生成清单，检查 Chat execution、SimC 和队列活动；备份独立恢复并比对后方可事务清理，保留用户及业务逐行核验。
- 未执行生产清理、真实 QQ 或发布时明确记录未执行，不替换为本地通过。

## 运营后台

- 唯一真实 QQ owner 允许读取；空配置、普通用户、固定测试账号、已撤销会话和 Bearer 拒绝。不能通过 query/body/header 覆盖服务端 owner；跨账号返回不泄露管理员标识。
- 北京时间起止、366 天限制、区间活跃用户去重、每日补零、反馈分母、无样本 null、有效 SimC 结果和已知模拟身份排除需 PostgreSQL 验证。
- 本地 `tests.app_admin_test`、`tests.app_admin_postgres_test`（独立 `WOW_ADMIN_TEST_DSN`）、`web-admin.test.tsx`，以及 typecheck/lint/H5 build；生产验证本人浏览器、第二账号 403、无会话 401、聚合 SQL 对账和公网产物。
