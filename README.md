# Chickenbro

炸鸡队长是一个微信小程序 + Web 双端 WoW 助手。当前重构后的产品范围只有两项：

1. 炸鸡队长会话；
2. SimC 模拟任务。

两端不共享 Cookie 或 Bearer。小程序通过 `wx.login` 建立 Mini Session；Web 由已登录小程序扫码并明确确认后建立独立 HttpOnly Session。两种会话都解析为同一个内部 `user_id`，因此从服务端读取同一份会话、消息、SimC 快照、任务、尝试和结果。

## 当前状态

六阶段彻底重构的 Phase 1 控制面已在 clean HEAD 封存；当前执行 Phase 2 干净数据面与 Identity 的本地实现、测试和 provisioning dry-run。生产 DSN、流量、服务和数据尚未切换，云端建库仍未授权。

最新只读快照显示根分区约余 8.58 GB，而 PostgreSQL 目录约 39.63 GB。创建干净 `chickenbro_prod` 前必须先完成独立恢复副本与恢复验证并精确清理无引用旧数据，或扩容。不能提前删除 `wow_test`、正式部署或唯一恢复点绕过容量门禁。

机器状态以 [docs/project-state.json](docs/project-state.json) 为准。

## 目标体验

小程序最终只有两个 Tab：

```text
队长 | SimC
```

目标路由只有：

```text
pages/chickenbro/index
pages/simc/index
pages/simc/tasks
pages/simc/task-detail
pages/auth/web-login-confirm
```

Web 使用相同 typed API/domain/feature model，只保留登录、队长、SimC、账号状态和退出。资讯、构筑、装备、天赋、WebSim、prototype bypass 和旧 14 路由都属于待退役 legacy。

## 架构

```text
Mini Bearer -----\
                  > API -> Principal(user_id) -> Identity
Web Cookie ------/                           -> Chat -> Codex
                                             -> SimC -> PostgreSQL Queue -> Worker -> cloud SimC
```

代码依赖固定为：

```text
UI -> typed API client -> API route -> application -> domain -> port <- adapter
```

详见 [当前架构](docs/chickenbro-simc-architecture.md)。

## 目录

```text
.
├── apps/mini-taro/            # Taro Mini/H5 客户端；dist/weapp 为本地构建产物
├── packages/api-client/       # Mini/Web 分离 transport 与 typed API
├── packages/domain/           # 跨端领域 guard/model
├── server/app/                # 模块化 Identity/Chat/SimC/Worker/API 核心
├── server/migrations/         # 当前旧迁移输入；干净 product chain 在 Phase 2 建立
├── docs/                      # 当前架构、runbook、状态、计划和验证
└── artifacts/releases/        # Harness requirement/evidence/manifest
```

根目录旧 `app.json`、`pages/`、`components/`、`custom-tab-bar/` 和 `websim/` 只承担迁移期 last-known-good/回滚职责，不接收新实现。

## 本地开发与验证

依赖使用仓库现有 lockfile；安装或下载缺失依赖前先取得明确授权。已有依赖时，持续构建微信小程序：

```bash
npm run dev:weapp
```

一次构建：

```bash
npm run build:weapp
```

微信开发者工具导入 `apps/mini-taro`，不要导入仓库根或 `apps/mini-taro/dist/weapp`。后者是构建输出，由 `apps/mini-taro/project.config.json` 指向。

Phase 1 控制面基线验证：

```bash
node --test tests/chickenbro-simc-refactor-inventory.test.js
python3 -m unittest tests.chickenbro_simc_cloud_inventory_test -v
node --test tests/project-state.test.js
```

后续 Identity、Chat、SimC、双端、迁移、切流和清理命令见 [验证矩阵](docs/verification-matrix.md)。缺失的阶段测试/脚本表示该阶段尚未落地，不能标为 skipped pass。

## 生产操作

生产迁移只允许按 [生产 Runbook](docs/chickenbro-simc-production-runbook.md) 执行：

- Candidate、切流和删除是独立门禁；
- 独立备份必须与 PostgreSQL 数据目录处于不同设备/故障域；
- 迁移是一遍全量 + 写栅栏后的一遍 delta，不长期双写；
- 第一条新生产写入后，legacy 永久只读；
- 删除只能使用带 SHA 的精确 manifest，禁止宽泛递归删除。

## 文档入口

- [文档地图](docs/README.md)
- [项目状态](docs/project-state.json)
- [产品 Roadmap](docs/roadmap.md)
- [当前架构](docs/chickenbro-simc-architecture.md)
- [生产 Runbook](docs/chickenbro-simc-production-runbook.md)
- [验证矩阵](docs/verification-matrix.md)
- [六阶段计划白名单](docs/plans/README.md)

旧文档和 release packet 只在当前迁移/回滚仍有精确引用时暂留；Phase 6 通过链接图、调用图和恢复门禁后从工作树删除，Git 历史承担归档。
