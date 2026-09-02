# Chickenbro

Chickenbro 是一个微信小程序 + Web 双端 WoW 助手。产品只保留两项核心能力：炸鸡队长会话和 SimC 模拟任务。

小程序通过 `wx.login` 建立 Mini Bearer Session；Web 生成一次性确认票据，用户必须在已登录小程序中明确确认，随后浏览器获得独立的 HttpOnly Cookie Session。两个 Session 都由服务端解析为同一个内部 `user_id`，所以两端读取同一份 Chat 与 SimC 历史；Cookie、Bearer、OpenID、`session_key` 和微信 access token 不在端间共享。

## 当前状态

Phase 1--4 以及 Phase 5 的本地代码、构建、迁移和切流控制已经验证。真实 candidate 数据库、真实微信扫码、生产切流、第一条新写入和云端清理尚未完成。当前云主机容量与独立恢复链不满足 apply 条件，因此生产旧服务和数据仍保持不变。

机器可读事实以 [项目状态](docs/project-state.json) 为准。任何 candidate、HTTP 200、测试通过、systemd active 或 SimC return code 0 都不能替代真实双端验收。

## 产品路由

小程序只发布五个页面，其中两个是 Tab：

```text
pages/chickenbro/index
pages/simc/index
pages/simc/tasks
pages/simc/task-detail
pages/auth/web-login-confirm
```

Web 只保留登录、Chat、SimC、账号状态和退出。所有正式客户端都通过 typed API client 访问服务端 owner-scoped 数据。

## 代码结构

```text
apps/mini-taro/          Taro 小程序与 H5/Web
packages/api-client/     Mini/Web 分离认证传输和 typed API
packages/domain/         Chat、SimC、Web 登录领域合同
server/app/              Identity、Chat、SimC、Worker 与 API
server/migrations/product/ 干净 schema 和白名单迁移
scripts/                 Harness、构建和精确清理工具
docs/                    当前架构、状态、Runbook 与计划
```

## 本地命令

依赖使用仓库现有 lockfile；在本机下载或安装缺失依赖前需要明确授权。

```bash
npm run test:taro
npm run typecheck
npm run lint
npm run build:weapp
npm run build:h5
npm run test:control
npm run test:backend
```

微信开发者工具导入 `apps/mini-taro`。合入并需要刷新预览时运行：

```bash
npm run refresh:weapp
```

## 安全边界

- 新路径通过 candidate、恢复验证和真实双端验收前，不删除现有生产入口。
- 历史迁移只复制白名单内有效 Chat/SimC 业务数据，不复制旧 Session、token、trace 或 prototype 数据。
- 第一条新生产写入后，旧库永久只读，不建立长期双写或反向同步。
- 文件、服务、数据库与目录只按绑定 SHA 的精确清单清理；禁止通配符和宽泛递归目标。
- 云端 apply 还要求独立、恢复验证过的备份以及零连接、零引用证明。

## 文档

- [文档地图](docs/README.md)
- [Roadmap](docs/roadmap.md)
- [当前架构](docs/chickenbro-simc-architecture.md)
- [生产 Runbook](docs/chickenbro-simc-production-runbook.md)
- [验证矩阵](docs/verification-matrix.md)
- [六阶段计划](docs/plans/README.md)
