# 炸鸡队长 Web 原型、Codex 对话与角色 SimC 设计

日期：2026-09-01
状态：用户已批准，进入 goal 实施
范围：H5 Web 原型、prototype bypass、Chickenbro 原生 Codex 对话、Raider.IO/WCL 角色快照与 SimC 任务

## 1. 用户目标与完成体验

用户打开公网 Web 后，不需要先完成正式微信登录，就能进入一个明确标注为“原型 bypass”的炸鸡队长工作台：

1. 页面立即显示当前是 Web prototype，不把 bypass 描述成已登录；
2. 用户可以进入 Chickenbro 对话，看到真实流式进度；
3. 用户可以粘贴 Raider.IO 或 Warcraft Logs 链接；
4. 没有真实角色快照时，SimC 明确停在“待输入 / 未连接 / 不可模拟”；
5. 只有 `READY_FOR_SIMC` 的不可变快照可以提交 Worker；
6. 结果必须来自真实 SimC 执行并包含有效语义指标；
7. prototype 数据永远不会进入正式用户历史；
8. Codex、来源 Adapter、Worker 或 SimC 不可用时，用户看到明确失败原因和恢复动作。

正式的微信小程序 Bearer、Web 二维码确认、HttpOnly Cookie 和 `/api/v2/me` 保留为独立能力；本原型不以它们作为进入条件。

## 2. 当前代码事实

- `apps/mini-taro` 已有 H5 shell，`app.tsx` 在 Web 环境渲染 `WebApp`；微信编译继续保留现有 14 条路由。
- 之前的 v2 foundation 已建立 `chat`、`simc`、`ops` schema、identity session、Worker lease 和 H5 构建/部署骨架。
- 现有 WebApp 是二维码登录页面；它必须保留正式登录动作，但默认入口改为 prototype 工作台。
- `server/codex_worker.py` 是原生 Codex runner；新 API 只能通过它或同等 Codex adapter，不能调用 legacy 普通 LLM fallback。
- `server/community_talent_sources/raiderio.py` 与 `warcraftlogs.py` 主要是社区模板加载器，不可冒充角色快照 Adapter；角色链接 Adapter 要在 v2 simulation owner 内实现。
- `server/simulation_snapshot.py` 的既有 v1/v2/v3 snapshot 绑定旧 resolver/release 合同；新链路必须使用独立 `CharacterSnapshot`，不能绕过 readiness 直接复用旧 WebSim profile。

## 3. 入口与 principal 隔离

### 3.1 Web 入口

继续使用现有 H5 `WebApp` root mount，不增加微信 14 条业务路由。WebApp 默认显示 prototype shell，并提供一个次级动作打开正式二维码登录面板。正式登录实现和确认页不删除、不弱化。

### 3.2 Prototype session

首次打开时，浏览器请求：

```text
POST /api/v2/prototype/sessions
```

服务端生成：

- 仅服务端可见的内部 `identity.users.id`；
- `account_kind = 'prototype'` 的 owner；
- 随机 prototype token 的 SHA-256；
- 过期时间和撤销状态。

浏览器只把原始 token 放在当前 tab 的 `sessionStorage`，不写正式 `auth.token`、Cookie 或 URL。后续请求使用：

```text
X-Prototype-Session: <opaque token>
```

该 token 是短期、限能力的 demo capability，不是正式账号登录。所有 prototype endpoint 都通过 `PrototypePrincipal` 注入内部 owner；客户端不能提交 `user_id` 或伪造 owner。

`identity.users.account_kind` 只允许 `formal|prototype`。正式 identity、`/api/v2/me`、正式历史和账号绑定接口拒绝 prototype principal；prototype 数据只在 prototype repository scope 内可读写。prototype session 可重置、撤销和过期，服务端按 TTL 清理。

### 3.3 API 命名

prototype 使用独立入口，避免把匿名能力误接到正式 user route：

```text
POST /api/v2/prototype/sessions
POST /api/v2/prototype/conversations
GET  /api/v2/prototype/conversations/{id}
POST /api/v2/prototype/conversations/{id}/messages/stream
POST /api/v2/prototype/source-snapshots
GET  /api/v2/prototype/source-snapshots/{id}
POST /api/v2/prototype/simulations
GET  /api/v2/prototype/simulations/{id}
POST /api/v2/prototype/sessions/revoke
```

内部 application/domain service 与正式路径共享 port 和状态机，但 repository 查询必须接收 principal 并带 owner 条件。prototype 不允许转换为 formal owner。

## 4. Chickenbro 合同

`POST /api/v2/prototype/conversations/{id}/messages/stream` 接收 `content` 与 `clientMessageId`，要求 `Idempotency-Key`。响应为 `text/event-stream`，事件为：

```text
started -> delta* -> completed
started -> failed
```

每个事件含严格递增的 `sequence`、conversation id 和 request id。后端在开始前保存 user message 和 streaming agent run；只有 Codex 完成并通过输出边界后才保存 assistant message 并转为 `succeeded`。

以下情况必须产生公开失败事件，且不能调用其他模型：

- Codex binary/provider 未配置：`CODEX_UNAVAILABLE`；
- 超时：`CODEX_TIMEOUT`；
- 非法/空输出：`CODEX_OUTPUT_INVALID`；
- persistence 或 owner 校验失败：对应稳定错误码。

trace 和日志不得包含聊天正文、prompt、凭据、完整答案、第三方 token、WCL 私有内容或 SimC stdout。

## 5. 角色快照与 SimC 合同

### 5.1 来源解析

服务端只接受 HTTPS 且 host/path 匹配 allowlist 的 Raider.IO/WCL 链接，不跟随到非 allowlist host。Router 只选择来源 Adapter，不把来源 payload 直接当 profile。

`RaiderIOCharacterAdapter` 输出角色身份、class/spec/race、装备/天赋可用字段、抓取时间、访问状态和 source provenance。Web 原型的有效角色等级统一按当前满级 90 处理，并在快照中标记 `levelSource=prototype_max_level`；来源若返回其他等级，只保留为 `sourceLevel` 供追溯，不参与原型 SimC profile。
`WclCharacterAdapter` 输出 report、revision、fight、actor/guid、playerDetails 字段和抓取时间；缺少种族、装备或必需字段时输出 `INCOMPLETE_FOR_SIMC`。

两者都只输出不可变 `CharacterSnapshot` candidate，保存 raw hash 和 provenance；不得静默混源。

### 5.2 Readiness 与提交

公开状态固定为：

```text
INVALID_LINK
CHARACTER_NOT_FOUND
ACCESS_RESTRICTED
SNAPSHOT_UNAVAILABLE
INCOMPLETE_FOR_SIMC
READY_FOR_SIMC
```

`READY_FOR_SIMC` 至少要求身份、class/spec/race、原型满级策略、必需装备槽、bonus/gem/enchant 语义、天赋、source provenance、compiler 支持和当前 runtime 支持全部通过。

SimC submit 只接收 snapshot id、scenario 和 idempotency key；服务端重新读取并验证 owner、revision、readiness、compiler revision 和 runtime revision。客户端不能上传 canonical profile 字符串。

Worker 使用同一云端 SimC runtime；结果只有在真实执行、解析出有效 primary metric、保留 runtime/compiler provenance 后才是 `SUCCEEDED`。进程退出码 0、HTTP 200、generated profile 或 preview profile 都不构成成功。

## 6. Web 用户界面

WebApp 必须显示 prototype 状态条、数据隔离说明和“重置演示会话”。主体包含：

- Chickenbro 对话卡：消息气泡、输入框、流式状态、Codex 错误恢复；
- SimC 卡：来源链接输入、来源/快照 provenance、readiness blocker、任务进度和结果；
- 正式登录入口：作为独立次级动作，不阻塞 prototype 使用。

初始 SimC 状态为“待输入角色链接”，提交按钮禁用。`INCOMPLETE_FOR_SIMC`、`ACCESS_RESTRICTED` 和 `SNAPSHOT_UNAVAILABLE` 必须显示原因，不显示默认人物、伪造 DPS 或 legacy WebSim 结果。

## 7. 兼容、部署与回滚

- 不修改旧 `/api/*`、旧 `/websim`、Active Manifest、14-route target registry、正式微信登录 API 或现有 TLS 证书配置。
- 新 schema 使用 additive migration（prototype owner/session 与 v2 业务已有表），不改变旧表语义；正式登录 migration 0039 保持不变。
- Web/API 使用现有独立 v2 API service、独立 SimC Worker service、Nginx 和部署脚本，候选部署前备份 PostgreSQL、旧静态目录、service env、Nginx 配置和当前 release link。
- feature flag 关闭 prototype API/UI 后，正式二维码登录和旧入口仍可运行；失败候选按脚本恢复上一版静态目录、service/Nginx 配置，数据库 backup 保留。
- 上线证据必须区分 `runtime_verified`、`candidate`、`live_verified`；页面可达、HTTP 200、systemd active、SimC exit code 0 和 Candidate 不可单独作为业务成功。

## 8. 验收标准

1. 无正式 Cookie、无 `/api/v2/me` 也能打开 Web prototype，并持续显示 bypass 文案。
2. prototype session 只绑定当前 demo owner；不同 session 和正式用户之间不能互读任何对话、snapshot、job 或 result。
3. 重置/过期后旧 token 失效，正式 auth storage 不被写入。
4. Codex 不可用时显示明确失败，无普通 LLM、模板回答或伪造 assistant。
5. 流式事件 sequence 正确，只有 completed assistant 才进入历史。
6. 没有角色链接、链接非法、来源受限或除等级外的 snapshot 字段不完整时 SimC 不可提交；Web 原型角色等级统一按满级 90 处理。
7. 只有 READY snapshot 可进入 Worker；generated/preview profile 不能变成成功结果。
8. 真正成功的结果包含有效 metric、runtime/compiler provenance 和 owner-bound job。
9. 14 条小程序路由、正式二维码确认路径、旧 API/WebSim、Active Manifest 和 TLS/部署边界保持不变。
10. targeted tests、H5 build、candidate API/Worker smoke 和上线后 HTTPS smoke 均有新鲜证据及回滚目标。
