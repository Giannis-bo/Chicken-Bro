# Repo-native Harness

> Harness version：v0.6.4。

Harness 检查显式合同、owner、依赖与 evidence，不产生用户授权，也不替代真实业务验收。任务范围遵循 AGENTS.md 和[计划白名单](plans/README.md)，验证等级见[验证矩阵](verification-matrix.md)。

## 使用

```sh
npm run harness -- --help
npm run test:control
```

`scripts/project-harness.js` 使用[项目状态](project-state.json)、owner 映射及 `docs/refactor/chickenbro-simc-disposition-rules.json` 等机器合同。新增当前文档或工具须登记 owner 与保留规则，避免历史清理器误判。不能为缩短文档删除被工具读取的字段或改写历史 manifest。

按任务影响选择检查；文档核对语法、链接与控制面，代码运行相关测试，受影响客户端构建 H5。远端同步、安装、发布及数据处置遵循本轮授权，Harness 输出不能扩权。

当前客户端只有 Web，生产认证为 QQ/Web Session，不执行 Mini 构建或微信上传。发布与恢复遵循[Runbook](chickenbro-simc-production-runbook.md)；保护 WIP，历史无备份授权不能用于新删除。[历史协议](harness-pre-mini-retirement.md)仅供追溯。
