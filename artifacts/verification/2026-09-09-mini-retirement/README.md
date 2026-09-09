# 小程序源码与历史测试数据清理 · 2026-09-09

## 当前结果

本地代码及当前文档清理已验证；未提交、推送或部署。用户随后确认的 186 个仅微信账号及业务数据已从正式库清理，新备份独立恢复、删除演练及保留记录核对通过。本轮用户已说明 QQ 登录顺利，但不把这句话当成本轮源码部署或数据清理验收。

删除 80 个已跟踪的小程序专用文件，见 [精确清单](local-files.json)。包括页面、Mini 组件和样式、平台 shim、微信 provider、旧头像上传处理、构建及预览工具、项目配置与专用测试。进一步移除共享模块中的 Mini auth、原生网络/UTF-8 分支、扫码状态机和微信配置。Taro H5、QQ/Web Cookie、CSRF、公开 transport、Chat/SimC 与浏览器 SSE 保留。

两份历史双端 Candidate/cutover 脚本改为立即拒绝执行的退役入口，不能触发构建、网络或数据库变更；当前运维说明不再要求调用它们。已应用 migration、历史接受记录与恢复材料保留，不改写历史 schema。

README、架构、路线图、文档地图、开发指南、用户指南、测试登录说明、Harness、验证矩阵和生产 Runbook 按当前实现整理；旧混合说明存为同目录 `*-pre-mini-retirement.md`。原有四份文档 WIP 已保存于 baseline.patch，并保留在相关历史快照或叠加后的规则中；未跟踪预览、其他任务产物和忽略的本地产物未删除。

## 本地检查

| 检查 | 结果 |
| --- | --- |
| 后端 | 447 通过 |
| Web | 259 通过，30 个测试文件 |
| PostgreSQL / migration | 新建独立 UTF8 空库，102 通过，无跳过；后续受影响 fixture 再验 9 通过 |
| 控制面 | 63 通过 |
| 运维 | 56 Node + 11 Python 通过 |
| TypeScript / lint | 通过 |
| H5 生产构建 | 通过，2 项既有包体积警告 |
| git diff --check | 通过 |

日志与本报告同目录。未新增/安装依赖，未运行本地 SimulationCraft，未进行本轮 Candidate、生产发布或真实 QQ 交互回归。本地 PostgreSQL 为本轮新建 `/tmp/cb-mini-retirement-pg`，验证后已停止。

## 已确认并清理的数据

只读盘点目标为正式 `chickenbro_prod` 中“有微信身份、无其他 provider 身份”的候选 owner；用户已明确批准上述 186 个 owner 范围，后续执行另行刷新并绑定精确记录清单。共 186 个账号、222 段会话、651 条消息、258 个 Chat run、7 个 SimC 任务、17 个来源快照、7 条队列项；相关 identity、审计等数量见 [逐表清单与指纹](data-inventory.jsonl)，查询见 [只读 SQL](data-inventory.sql)。未发现混合 QQ 身份、活动目标任务或有效 execution lease。

另有 14 个无 provider 关联账号，其中 4 个名称含测试字样；名称和 provider 都不足以独立证明“测试数据”。它们未纳入上述 186 个候选账号，不做推断删除。QQ 账号与业务数据须保留；操作前需刷新清单，不能用本次指纹覆盖之后的新写入。

正式事务已完成：`dataApplied=true`、`backupCreated=true`、`restoreVerified=true`。最终清单额外识别了无 user_id、但明确引用目标记录的迁移审计，因此本轮共删除 3465 条相关审计记录。18 个 QQ、14 个无关联账号及其记录前后完全一致；未归属这些目标的匿名旧票据/审计不在本轮已确认范围内。详细[数据执行记录](data-cleanup/README.md)。源码仍未提交或部署。
