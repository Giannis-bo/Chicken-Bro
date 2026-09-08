# 开发指南

先读仓库 [AGENTS.md](../AGENTS.md)、[项目状态](project-state.json)、[路线图](roadmap.md)与[计划白名单](plans/README.md)。产品介绍见根目录 [README](../README.md)。

## 代码入口

| 目录 | 职责 |
| --- | --- |
| `apps/mini-taro/src` | Taro 小程序与 Web，平台入口分离 |
| `packages/api-client/src` | typed API、Mini Bearer 与 Web Cookie 传输 |
| `packages/domain/src` | Chat、SimC 与登录合同 |
| `server/app` | 身份、聊天、模拟、Worker 与 HTTP 适配 |
| `server/migrations/product` | PostgreSQL schema 与迁移 |
| `scripts` | 构建、验证、Harness 和受控运维 |

## 本地验证

使用 Node.js 20+、仓库 lockfile 与已有 Python 后端环境。下载或安装依赖须取得明确授权。系统 Python 缺少 FastAPI 时应选用已有虚拟环境，不把导入失败记为实现测试通过。

```bash
npm run test:taro
npm run test:control
npm run test:backend
npm run test:migration
npm run test:ops
npm run typecheck
npm run lint
npm run build:weapp
npm run build:h5
git diff --check
```

PostgreSQL 集成测试需要 `WOW_PG_TEST_DSN_V2` 指向独立的本地测试库，使用 UTF8 并预先创建迁移要求的 `wow_app` 角色。不得指向生产或共享业务数据库。未配置时相关测试会跳过，必须单独记录，不能称为完整迁移验证。

SimC 引擎只在云端运行，不在本机安装或执行。部署与语义模拟验证按 [验证矩阵](verification-matrix.md)和[生产 Runbook](chickenbro-simc-production-runbook.md)执行。

## 小程序预览

```bash
npm run refresh:weapp
```

脚本分阶段构建，核对 `wow-build.json` 的 commit/sourceHash，再打开微信开发者工具的 `apps/mini-taro/dist/weapp` 运行目录。源码工程配置在 `apps/mini-taro`。CLI 不可用时按脚本给出的目录手动导入。

构建、工具打开、代码上传、体验版设置与微信公开发布是不同步骤。Web 代码或样式不能泄漏到 WeApp；检查最终 JS/WXSS，而非仅检查源码。
