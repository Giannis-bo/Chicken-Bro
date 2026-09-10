# Chickenbro 当前生产 Runbook

适用产品为 Web / QQ 登录、Chat、云端 SimC。历史迁移、双端切流和小程序发布过程归入[历史存档](chickenbro-simc-production-runbook-pre-mini-retirement.md)，不得重放六阶段脚本作为常规发布。

## 运行身份核对

操作前核对 `wow-lighthouse` 所对应实例、当前代码/Web symlink、systemd API/Worker 的有效工作目录与配置文件路径、数据库名，以及实际源文件和产物 SHA。不要输出环境文件内容、DSN 密码或第三方凭据。正式库为 `chickenbro_prod`，正式网站为 `https://www.chickenbro.cloud/`，readiness 为 `/api/v2/health/readiness`。

QQ 配置位于 root-owned 0600 `/etc/chickenbro-qq.env`，包含服务端 `WOW_QQ_APPID`、`WOW_QQ_APP_KEY`、`WOW_QQ_REDIRECT_URI`。正式 callback 为 `https://www.chickenbro.cloud/api/v2/auth/qq/callback`；隔离环境须使用独立 Cookie、数据库、目录、端口和已登记 callback。不要恢复微信配置或小程序码作为登录方式。

## 发布与回滚

用户明确授权发布后，绑定本次源码、基底、逐文件清单与 Web 产物。先部署隔离 Candidate 并验证 QQ/CSRF、Chat/SSE、第二用户隔离、图片及真实 SimC 指标；未覆盖项单列。新增 migration 保持向前兼容。

切换前排空 Chat execution、SimC 任务及队列，保留旧代码/Web 与精确 drop-in 清单。API 与 Worker 同时加载匹配配置，再切换受控 symlink。readiness 后继续验证真实业务与公网 Web 文件哈希。只重启 API 不等于持久化生成的完整发布。

失败时按本批精确清单恢复文件或指针、移除仅本批 drop-in，再核验 systemd 有效配置和业务。已有新写入时不得把旧 dump 覆盖回生产。Worker 中断会依租约明确失败，不能以此为随意终止正在执行任务的授权。

## 数据清理

本次范围见[小程序清理计划](plans/2026-09-09-mini-retirement.md)。先确认目标 owner 精确列表；排除任何 QQ/其他 provider 混合身份，核对所有外键及 JSON 任务引用。检查目标用户无活动 Chat、execution、SimC、queue lease，且旧入口不可再产生对应业务。

删除前创建独立私有备份，恢复到隔离库并逐表核对；备份不进入仓库或普通日志。最终事务重新核对清单和活动任务，再按 tool_results、executions、agent_runs、SimC results/attempts/jobs、queue、图片/消息/会话、identity 等依赖顺序处置，审计与 usage 也必须纳入清单。QQ 及其他保留用户的记录需在事务前后逐行匹配。未完成范围确认或恢复验证时不得执行删除。

旧 schema migration 保留，不改写已应用历史；清理数据不要求销毁可恢复备份。QQ 上线时的旧备份不能代替本次删除前的新快照。

## 当前运行能力与证据

- [QQ 发布与恢复](../artifacts/verification/2026-09-09-qq-web/deployment/README.md)：真实登录、Chat/SimC、旧记录保留与独立恢复证明。
- [持久化生成](../artifacts/verification/2026-09-09-g2-durable/README.md)：`WOW_CHAT_DURABLE_ENABLED=1` 在 API/Worker 同时启用；执行、租约及中断语义。
- [截图发布](../artifacts/verification/2026-09-09-chat-images/deployment/README.md)：私有图片、保留策略与回滚。

## 当前 Codex 配置与精简（2026-09-09）

本轮开始前已确认的云端配置改动保留：Codex 使用 Astra/low，移除 29 条旧信任记录；禁用通用技能、账号插件和 Apps/远程插件加载。配置变更后实际业务会话保留 9 个业务 MCP 工具并完成回复。[原始验证](../artifacts/verification/2026-09-09-cloud-codex-cleanup/report.json)与[完整配置回滚记录](chickenbro-simc-production-runbook-pre-mini-retirement.md#当前-codex-配置与精简2026-09-09)供复核。后续操作仍须核对当前配置元信息，不以历史记录代替 live 检查。

## 2026-09-09 已确认旧微信测试数据清理

正式库已删除用户明确确认的 186 个仅微信账号及其关联业务记录；18 个 QQ 账号和 14 个无 provider 关联账号保留。事务对全部保留表逐行计算指纹，前后完全一致；结果保护触发器已恢复，所有外键约束保持有效。

本次私有备份为 `/var/backups/chickenbro-mini-retirement/20260909_retire186_02/before.dump`，独立恢复库为 `cb_mini_restore_20260909_retire186_02`；所有非超级用户登录角色均无 CONNECT 权限。完整副本在演练回滚后保留。前一次演练被结果不可变触发器拒绝并回滚，未影响正式库；其备份和隔离副本同样私有保留。

恢复数据时先用新建隔离库还原 dump，依据私有 `manifest.json` 提取本轮目标记录并检查当前键冲突，按外键依赖恢复；不得覆盖清理后的 QQ 新写入。不能直接重放删除脚本或旧迁移。详见[执行证据](../artifacts/verification/2026-09-09-mini-retirement/data-cleanup/README.md)。数据操作与后续源码发布分别记录。

## 小程序清理发布（2026-09-09）

当前后端/Web 源码 `7adcdeffa3566add1cc9fe33325df5b7360e29df`，目录前缀 `mini-retirement-`。精确清单、空闲门禁切换脚本、公网业务检查与恢复指针见[发布记录](../artifacts/verification/2026-09-09-mini-retirement/release/README.md)。没有变更生产环境配置或重放数据删除；旧 backend/Web 逐文件不变，备份 hash 再次匹配。

## SimC 场景实验发布（2026-09-09）

当前后端/Web 运行源码 `7ef8a5dfd9a48de9c9d6c12c660b6564446fd5eb`，API/Worker 同时启用 compiler v5。新增能力、完整 manifest、真实模型验收、空闲门禁及仅本批配置恢复入口见[发布记录](../artifacts/verification/2026-09-09-simc-scenario-experiments/release/README.md)。上一版 Mini 清理代码与 Web 保留不变；本轮没有再次进行数据清理或升级引擎。

## 运营后台发布（2026-09-09）

`/admin` 已发布并绑定经用户确认的真实 QQ 内部账号。权限配置 `/etc/chickenbro-admin-ops-03275ee5ce67.env` 由本批 API/Worker drop-in 同时加载，只有一个 `WOW_ADMIN_USER_ID`，不可用QQ数字、昵称或固定测试账号代替；空配置拒绝所有访问。后续部署须保留该配置及管理员路由，并检查本人200、普通账号403与匿名401。后端运行源码03275ee5c、最终Web源码8fba1535f；清单、业务证据、并行任务边界和精确恢复入口见[发布记录](../artifacts/verification/2026-09-09-admin-ops/README.md)。

## WCL 工具效率发布（2026-09-10）

当前后端增量源码 `f95f6bbe234a2da8a67ca86466e96c6c29c6b794`，API/Worker 位于 `/opt/chickenbro-releases/badcase-f95f6bbe234a2da8a67ca86466e96c6c29c6b794`。本次仅替换五个 WCL/MCP/证据文件，无新 migration、依赖、运行配置或 Web 变动；Web 继续使用 `admin-ops-web-8fba1535f226c5dd6eebbcd3980fc2ca52c4075f`。隔离与公网业务检查、精确清单及空闲门禁恢复入口见[发布记录](../artifacts/verification/2026-09-10-wcl-tool-efficiency/release/README.md)。旧后端完整保留，私有恢复快照已校验；没有执行生产回切演练。

## Chat 有界研究（2026-09-10）

API/Worker当前运行源码 `3f0c15d988fd33fd08dae8514f70ee483862c3c8`，7文件增量启用Top10及来源预算、关闭绕过预算的原生网页搜索。无环境配置、迁移、依赖或Web变更；Web仍为admin-ops-web-8fba1535f。隔离及公网业务和Web哈希已核对，恢复快照保留但未回切演练。[本批发布与回退步骤](../artifacts/verification/2026-09-10-bounded-research/release/README.md)。

## 自定义施法与术语检索发布（2026-09-10）

应用源码 `c408a30e676c9884d27b7c4ea8cad39f8ac45a01` 已上线到 API/Worker 与 Web，目录前缀 `custom-apl-`。本批两个 `99-zzzzzz-custom-apl-c408a30e676c.conf` drop-in 加载 root/0600 `/etc/chickenbro-custom-apl-c408a30e676c.env`，仅覆盖 compiler 为 v6；原有环境和管理员/QQ 配置保留。自定义 APL、动作样本、Chat 先检索以及 scenarioVersion=4 的隔离和公网验证通过；外部来源没有提供当前套装原文时仍保留缺口。精确清单、私有恢复核验和同时回退 backend/Web/compiler 的空闲门禁入口见[发布记录](../artifacts/verification/2026-09-10-custom-apl/release/README.md)。未升级引擎、迁移数据库或执行生产回切演练。


## 原生搜索恢复尝试与回滚（2026-09-10）

原生搜索恢复源码 `031c1b2f4c5e1097b2be99997369fec1faef965b` 线上第二条语义验收失败，已回滚并验证恢复。当前后端重新使用 `custom-apl-c408a30e676c9884d27b7c4ea8cad39f8ac45a01`；Web 保持 `changelog-b5567b1065573cc048eea285bc748c09341a3c31`。未改环境、引擎或数据库合同。失败源码不得原样重发；[失败与恢复记录](../artifacts/verification/2026-09-10-native-search/README.md)说明源码与生产状态的差异。


原生搜索后续按用户新授权拆分工具和回答质量验收，见[当前验收范围](plans/2026-09-10-bounded-research.md#2026-09-10-工具能力独立验收当前授权)。新发布须包含按运行 ID 的无内容原生事件摘要及独立资料取得评审；旧失败记录不改写，使用新 manifest，不重放旧发布包。
