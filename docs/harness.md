# Repo-native Harness

> Harness version：v0.6.4。

文档于 2026-09-09 按当前 Web/QQ 实现整理；脚本兼容版本保持原值。

## 当前规则

`AGENTS.md`、[项目状态](project-state.json)、[路线图](roadmap.md)、[计划白名单](plans/README.md)和[验证矩阵](verification-matrix.md)是当前工作入口。Harness 是代码和文档的检查工具，不创建额外用户授权，不替代真实产品验证。输出中的远端同步不再标记为默认预授权，须遵循本轮用户授权。

常用入口为 `npm run harness -- --help`、`npm run test:control`。`scripts/project-harness.js` 检查显式合同、owner、依赖和 evidence；`docs/refactor/chickenbro-simc-disposition-rules.json` 列出保留范围。新增当前文档或工具须同步 owner 与保留规则，避免历史清理器误判。

## 证据与完成

本地测试与 H5 构建、隔离 Candidate、线上业务、用户验收、独立恢复分别记载。不得以 HTTP 200、进程退出 0、dry-run 或调度成功代替业务完成。受影响代码运行相关测试；文档仅做必要语法、链接和控制面核对。

QQ 是当前网站登录方式，Web HttpOnly Session 是唯一生产认证。没有 Mini 构建、DevTools、预览刷新或微信上传步骤。浏览器验证针对实际 Web 页面；当前实例、发布身份与清理范围必须重新核对。

## 清理与恢复

保护未提交、未跟踪及其他任务的工作。已应用 migration、历史 manifest、发布与恢复证据只供追溯。新数据删除须精确清单、零活动引用及独立恢复核验；历史无备份授权不能复用。常规发布使用[当前 Runbook](chickenbro-simc-production-runbook.md)，旧双端发布入口已停止执行。

历史协议和 v0.6.4 形成过程见[原 Harness 存档](harness-pre-mini-retirement.md)。
