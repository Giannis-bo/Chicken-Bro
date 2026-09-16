# 开发指南

先读仓库 [AGENTS.md](../AGENTS.md)、[项目状态](project-state.json)、[路线图](roadmap.md)与[计划白名单](plans/README.md)。产品介绍见根目录 [README](../README.md)。

## 代码入口

| 目录 | 职责 |
| --- | --- |
| `apps/mini-taro/src` | Taro H5 / React Web |
| `packages/api-client/src` | typed API、Web Cookie 与 public 传输 |
| `packages/domain/src` | Chat、SimC 与登录合同 |
| `server/app` | 身份、聊天、模拟、Worker 与 HTTP 适配 |
| `server/migrations/product` | PostgreSQL schema 与迁移 |
| `scripts` | 构建、验证、Harness 和受控运维 |

## 本地验证

使用 Node.js 20+、仓库 lockfile 与已有 Python 后端环境。下载或安装依赖须取得明确授权。系统 Python 缺少 FastAPI 时应选用已有虚拟环境，不把导入失败记为实现测试通过。

按[验证矩阵](verification-matrix.md)选择受影响入口，不把下表当作每次必跑全量清单。

| 影响 | 命令 |
| --- | --- |
| 文档/控制面 | `git diff --check`、`npm run test:control` |
| 后端 | 相关 `python3 -m unittest` 模块；完整集合为 `npm run test:backend` |
| 数据库 | `npm run test:migration`；管理员聚合另用 `npm run test:admin:postgres` |
| 运维脚本 | `npm run test:ops` |
| Web/共享合同 | `npm run test:taro`、`npm run typecheck`、`npm run lint`、`npm run build:h5` |

PostgreSQL 集成测试需要 `WOW_PG_TEST_DSN_V2` 指向独立的本地测试库，使用 UTF8 并预先创建迁移要求的 `wow_app` 角色。不得指向生产或共享业务数据库。未配置时相关测试会跳过，必须单独记录，不能称为完整迁移验证。

SimC 引擎只在云端运行，不在本机安装或执行。部署与语义模拟验证按 [验证矩阵](verification-matrix.md)和[生产 Runbook](chickenbro-simc-production-runbook.md)执行。

## Web 预览与 QQ 配置

```bash
npm run dev:h5
```

QQ 应用使用 `WOW_QQ_APPID`、`WOW_QQ_APP_KEY`、`WOW_QQ_REDIRECT_URI` 三个服务端配置。正式 callback 固定为 `https://www.chickenbro.cloud/api/v2/auth/qq/callback`。AppKey 不得编译进 Web、写入源码或打印到日志。只有已登记的 HTTPS callback 才能参与真实 QQ 授权；localhost 测试使用受控 fake provider，不伪称真实登录。

构建前后检查实际 H5 产物，Web 预览、部署和真实 QQ 验收分别记录。
