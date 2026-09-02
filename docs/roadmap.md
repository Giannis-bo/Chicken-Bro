# WOW Mini Program Roadmap

状态：`active`
更新时间：`2026-09-02`

## 本文职责

本文只保留当前产品方向、用户可见完成标准和优先级。机器可读当前事实以
[project-state.json](project-state.json) 为准，实施授权以 [plans/README.md](plans/README.md) 为准，
架构与清理边界以
[双端彻底重构设计](superpowers/specs/2026-09-02-chickenbro-simc-total-rebuild-design.md) 为准。

## 唯一产品方向

项目只保留两个业务域：

1. 炸鸡队长会话；
2. SimC 模拟任务。

微信小程序与独立 HTTPS Web 使用同一套业务能力和服务端数据。小程序通过 `wx.login` 建立 Mini
Session；Web 生成一次性小程序码，由用户在炸鸡队长小程序中明确确认后建立独立 HttpOnly Web
Session。两端会话都解析为同一个内部 `user_id`，共享全部有效会话、消息、SimC 快照、任务和结果。
共享的是账号和业务数据，不是 Cookie、Bearer token、OpenID、`session_key` 或微信 access token；
正式方案不依赖网站应用 OAuth、`snsapi_login` 或 UnionID。

资讯、职业构筑、天赋模拟、装备模拟、旧 WebSim、旧 14 路由、prototype bypass、旧数据刷新链和相关
一级入口全部退出目标产品。它们只在新路径完成 candidate、回滚和用户验收前作为 legacy
last-known-good 存在，不再获得新功能或数据扩展。

## 用户可见完成标准

- 小程序与 Web 登录同一微信用户后，看到相同的会话列表、完整消息和 SimC 任务历史；
- 小程序创建的会话可在 Web 续聊，Web 创建的会话可在小程序续聊；
- 任一端创建 SimC 任务，另一端看到同一任务状态、输入来源和最终结果；
- Web Cookie 与 Mini Bearer 可以独立过期和退出，不影响账号数据归属；
- 不同微信用户之间的 Chat/SimC 数据严格隔离；
- Codex、来源或 SimC 失败时显示真实错误和恢复动作，不使用模板或旧缓存伪造成功；
- 正式客户端只显示“队长”和“SimC”两个 Tab，认证与账号能力只作为辅助界面；
- legacy 文档、代码、路由、服务、timer、数据库和云端目录按精确清单删除，并保留恢复验证。

## 当前事实

| 层 | 状态 | 当前事实 |
| --- | --- | --- |
| legacy 生产 | `Active / last-known-good` | `wow-backend`、旧 14 路由、WebSim/Gear/Talent 数据链仍在运行；它们不是目标产品，但尚未退役 |
| v2 平台核心 | `Candidate 已实现` | `server/app`、`identity/chat/simc/ops` schema、v2 API、Worker、Codex/来源和 SimC 原型路径已有代码与候选证据；不能等同于正式双端切流 |
| Web 小程序确认登录 | `partial` | 正式 ticket/verifier/Cookie 代码与候选已存在；真实已发布小程序确认页、扫码、Cookie、`/api/v2/me` 和跨端历史尚无完整用户验收 |
| Web prototype bypass | `待退役` | prototype 可访问只证明隔离 demo 可用；prototype owner 和数据不迁移到正式历史 |
| 数据面 | `本地已验证 / Candidate 阻塞` | product-only schema、同 owner 双会话、Origin/CSRF 与 provisioning dry-run 已通过本地验证；legacy 正式运行库 `wow_test` 约 16.38GB，独立 `chickenbro_prod` 尚未创建，不能宣称 Phase 2 完成 |
| 云端空间 | `容量阻塞 apply` | 2026-09-02T13:43:05Z 只读盘点为根盘约 84% 已用、仅约 8.58GB 可用，PostgreSQL 目录约 39.63GB；四个无连接 gear evidence DB 合计约 22.53GB，但只能在独立恢复与零引用证明后精确退役，否则必须先扩容 |
| Active Manifest/S2 | `legacy 冻结` | 当前 generation 41 与旧 Catalog 只承担迁移期回滚，不再 promotion 或扩展；新 SimC 主链不依赖这些 owner |

## 当前优先级

| 优先级 | 子项目 | 完成标准 |
| --- | --- | --- |
| 已完成 | 控制面与清理清单 | 新规格、current truth、逐文件 keep/migrate/delete、脱敏云端清单、当前架构、Runbook 与 Strict packet 已封存；删除仍未授权 |
| 正在推进 | 干净数据面与 Identity | 本地 product-only schema、正式同 owner 双会话、Origin/CSRF 与 provisioning dry-run 已验证；云端建库和真实 PG/API 验证继续受容量、独立恢复与运行依赖 gate 阻塞 |
| 下一步 | Chat 正式路径 | 正式 owner API、完整历史、SSE、幂等与 Codex-only 跨端验收完成 |
| 下一步 | SimC 正式路径 | Snapshot/readiness/compiler/Worker/result 单一主链和跨端任务验收完成 |
| 下一步 | 双端精简客户端与迁移切流 | 两个 Tab、五条目标路由、历史白名单迁移、candidate、回滚和真实用户验收完成 |
| 后续 | Legacy 彻底退役 | 旧文档、代码、route、service、timer、database、env、目录和短期回滚包按 manifest 删除并验证 |

## 执行规则

- 本次重构按六个 Strict 子项目推进，不做一次性大爆炸提交；
- 新路径通过前不删除当前正式入口；通过后不保留长期双写、prototype bypass 或无限兼容层；
- 所有历史迁移按 owner/完整性白名单执行，旧 auth session/token 一律不迁移；
- 数据库、服务和目录删除必须使用精确名称，并先完成可恢复备份、引用证明和用户验收；
- Candidate、HTTP 200、测试通过、systemd active、SimC return code 0 或磁盘回收都不是产品完成；
- roadmap 不记录执行流水；完成/停止/替代的计划从工作树删除，Git 历史承担归档。
