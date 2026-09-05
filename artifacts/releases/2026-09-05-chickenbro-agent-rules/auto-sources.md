# 自动来源调用验证

日期：2026-09-05。实现 commit：`491d5379c5e7766f8e9260e3c6c9e7d8036c73f5`。

## 根因与修复

此前测试调用记录为 `partial`，原因为工具拒绝本机 8792 端口；两端 WCL v2 OAuth 凭据均已配置。额外国服域名解析缺失使 cn 链接无法取报告。现允许固定网关路径及 managed 8790/8791/8792 端口，继续拒绝其他端口、路径和外部主机；cn 链接归一化后保留 fight/source。

工具增加有界 actors、fights、casts、damage 与样本覆盖信息。Codex 可自行选择 source= 继续查询，AGENTS 仅加入通用的主动用工具、自动用服务端凭据、必要时引导补充等规则。没有加入用户否定的玩家分析固定流程；凭据不进入 Codex 环境或提示词。

## 验证

- 回归先失败后通过；30 项来源专项、247 项云端既有依赖后端测试、62 项控制面通过。无新依赖，无本地 SimC。
- 独立审查指出未筛选时报告汇总误归因首场，已改为报告范围和空 fight，新增回归并复核通过。
- 真实来源 API：用户报告第 4 场可用，Giannis 为 source=4，取得 23 条施法技能及 17 条伤害技能统计。事件样本不代表完整时间线，工具显式携带范围信息。
- 隔离源码 `/tmp/chickenbro-auto-sources.fa5pe49o`、回环 8791 API、同一网关路由与 capability、真实原生 Codex/MCP 验证：只输入原问题，Codex 自主调用报告和角色两个查询，均 verified，输出基于技能统计的分析。`auto-sources-candidate.json` 留存回答及脱敏工具记录；没有要求用户提供 Key 或提醒用 API。
- 部署后在用户已登录的 Edge 测试页新建一条测试对话，发送原报告分析问题，不附加任何 API 提示。页面收到真实技能统计分析；服务端记录确认两个 WCL 调用均 verified。结果仍如实区分技能汇总与不完整事件时间线。`auto-sources-live.json` 记录该回答、工具观察及两端最新文件 SHA/ready 状态；此前失败会话保留。

## 部署与回滚

- 包 SHA：`edf37aa14705eec43feee69bf307fe6a89325e4e162adc68e2671b8caa73df27`。
- 正式仅按 `auto-sources-manifest.json` 覆盖五文件；原文件在 `/var/lib/chickenbro/auto-source-backups/491d5379c5e7766f8e9260e3c6c9e7d8036c73f5`。
- 测试 current 为同名 commit release，继承 `f144923c0a1ffb4c21aad4567f3e9e443b3b036d` 的 Web 和其余后端；旧 release 保留。两端 API 已重启、readiness ready，文件 SHA 一致。凭据、数据库、模型和前端没有修改。
- 当前五文件身份以 `SOURCE_API_PATCH.json` 为准；此前 `AGENT_RULES_PATCH.json` 是上一阶段记录，不覆盖本次更新。回滚前核对五文件 SHA，恢复正式精确备份并将测试 current 切回 f144923c，再重启两个 API；回滚会恢复旧工具端口/解析限制，需同时恢复，不能只回退一端 MCP。
- main 尚未合入。自动 smoke 不替代用户体验接受，不宣称任意新 API 都已接入。
