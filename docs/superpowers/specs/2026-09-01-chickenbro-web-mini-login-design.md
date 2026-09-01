# 炸鸡队长公网 Web 原型与小程序确认登录设计

日期：2026-09-01
状态：已确认，待实施
公网入口：`https://www.chickenbro.cloud`

## 1. 目标与边界

本子项目交付一个真实可访问的桌面优先 Web/H5 原型，并完成“Web 浏览器生成二维码、微信小程序扫码确认、Web 建立自己的登录会话”的最短闭环。用户在 Web 上看到的是下一代产品的精简入口：登录后展示炸鸡队长和 SimC 两个业务入口；本子项目不提前实现 Codex 对话、Raider.IO/WCL 解析或 SimC 执行。

现有 14 条 Taro 业务路由、根目录兼容路由、`server/news_backend.py`、旧 API、Active Manifest 和既有生产服务继续作为 last-known-good 保留。新增的小程序确认页是无 TabBar 的辅助路由，不计入 14 条业务路由的视觉目标或导航合同，也不改变现有四个 tab 的顺序。

权威输入：

- [双端精简架构](2026-09-01-chickenbro-simc-dual-client-architecture-design.md)；
- [当前项目真相](../../project-state.json) 与 [路线图](../../roadmap.md)；
- [v2 平台骨架实施计划](../plans/2026-09-01-chickenbro-simc-platform-foundation.md)；
- [公网部署 Runbook](../../remote-debugging.md)；
- [现有 Taro H5 配置](../../../apps/mini-taro/config/index.ts) 与 [0038 平台 schema](../../../server/migrations/postgres/0038_chickenbro_simc_platform_foundation.sql)。

## 2. 用户完成体验

### 2.1 Web 主路径

1. 用户打开 `https://www.chickenbro.cloud`，看到品牌、产品说明和“使用微信小程序登录”卡片。
2. 浏览器用 `crypto.getRandomValues` 生成高熵 `browserVerifier`，只把它保存在当前浏览器的 `sessionStorage`；服务端只保存其 SHA-256。
3. Web 创建 login session，服务端生成不超过微信场景限制的随机 `sceneTicket`，调用微信小程序码接口，并将二维码 PNG 作为短期响应返回；二维码不携带 `user_id`、OpenID、UnionID、token 或个人字段。
4. 用户使用炸鸡队长小程序扫码。小程序打开隐藏的 `pages/auth/web-login-confirm`，先用 `wx.login` 换取本小程序专用 Bearer token，再展示待确认的 Web 登录说明。
5. 用户在小程序内明确点击“确认登录”后，服务端按 scene ticket 找到未过期的 login session，并绑定该小程序认证得到的内部 `user_id`。
6. Web 以同一个 verifier 轮询状态；状态变为 `confirmed` 后调用一次 exchange。服务端消费 login session，签发独立的 `HttpOnly; Secure; SameSite=Lax` Web Cookie。
7. Web 调用 `/api/v2/me`，展示“已连接微信账号”和两个业务入口卡片。刷新页面仍通过 Cookie 识别同一内部用户；退出登录撤销 Web session 并清除 Cookie。

移动 Web 不在同一设备上伪造扫码能力：页面明确提示使用电脑/另一台设备展示二维码，或直接使用小程序。等待、过期、取消、二维码生成失败、verifier 不匹配和重复 exchange 都有可见的恢复动作。

### 2.2 用户可见状态

| 状态 | Web 表达 | 可用动作 |
| --- | --- | --- |
| `idle` | 等待生成登录二维码 | 生成二维码 |
| `pending` | “请用小程序扫码并确认”及剩余时间 | 取消、刷新二维码 |
| `confirmed` | “已在小程序确认，正在建立 Web 会话” | 等待一次 exchange |
| `authenticated` | 已连接账号、队长和 SimC 入口 | 进入原型入口、退出 |
| `expired` | 二维码已过期 | 重新生成 |
| `cancelled` | 登录已取消 | 重新生成 |
| `blocked` | 配置/网络/服务不可用，显示公开错误码 | 重试或转小程序 |

## 3. 方案比较与选择

| 方案 | 说明 | 判断 |
| --- | --- | --- |
| A：把 Web 登录接入 `news_backend.py` | 复用旧 Bearer 和 SQLite/PG 兼容路径，最短但会把新身份、Cookie、二维码和旧业务继续耦合到超大文件 | 不采用；破坏新 owner 边界，回滚和审计困难 |
| B：v2 API + 独立 Web H5 壳 + 小程序辅助页 | 复用现有 Taro/React、domain、typed client 和 PostgreSQL；用独立 `wow-v2-api` 与 Nginx `www` server block 承载新链路 | **采用**；隔离旧入口，能做真实 Cookie/Origin/登录 smoke，后续可增量接入 Chickenbro/SimC |
| C：静态二维码/模拟登录原型 | 只展示假二维码或前端 mock 状态 | 不采用；不满足真实小程序登录要求，也不能验证账号归属 |

## 4. 系统拓扑

```text
Browser Web/H5 (www.chickenbro.cloud)
  -> same-origin /api/v2
  -> Nginx
  -> wow-v2-api (127.0.0.1:8790)
  -> PostgreSQL identity schema
  -> WeChat APIs (server-side app credentials only)

WeChat mini program
  -> wx.login
  -> POST /api/v2/auth/wechat/mini/exchange
  -> explicit confirmation page
  -> POST /api/v2/auth/wechat/mini/web-login-confirm
  -> same PostgreSQL identity.web_login_sessions
```

Web 继续使用 `apps/mini-taro` 的 Taro/React 编译链和 shared packages，但 H5 入口渲染新的 `WebApp`，不显示旧四 tab 业务导航。微信编译仍保留现有 14 条业务路由，并追加一个标记为 `auxiliary_auth` 的确认页；该页不出现在 TabBar、不进入当前 14-route target registry。

### 4.1 身份与会话所有权

- `identity.users.id` 是唯一业务 owner；`identity.user_identities` 按现有身份 schema 保存 `provider`、应用上下文和 provider subject 等服务端身份字段，provider subject 只用于精确身份解析，不进入客户端响应或日志；不能用昵称、头像或 UnionID 猜测归并。
- `identity.auth_sessions` 保存 v2 mini Bearer 和 Web Cookie 的 token hash、种类、过期时间、撤销时间与 `user_id`；原始 token 不落库、不进日志。
- `identity.web_login_sessions` 保存 login session id、scene ticket hash、browser verifier hash、绑定的 `user_id`、状态、过期与 exchange 时间。scene ticket 和 verifier 明文只存在请求/响应边界，不进入持久层。
- Web Cookie 和小程序 Bearer 独立撤销；共享的是内部 `user_id`，不是 Cookie、`session_key` 或微信 access token。

### 4.2 微信二维码

服务端通过 `WOW_WECHAT_APPID`/`WOW_WECHAT_SECRET` 调用微信服务端接口获取 app access token，再调用小程序码接口生成 `pages/auth/web-login-confirm` 的二维码。二维码生成失败返回稳定的公开错误码，不降级为假的成功二维码。微信 app access token 仅保存在服务端短时内存缓存，不写日志或业务表。

如果云端缺少微信凭据、确认页未发布到该 AppID，Web 仍可交付结构和 blocked 状态，但不得标记为“登录已完成”；正式登录 smoke 必须使用真实小程序扫码和用户确认。

## 5. API 合同

所有新路由都在 `/api/v2` 下，使用 request id、稳定错误码和公开安全消息。写请求带 `Origin` 校验和 `Idempotency-Key`（适用时）；浏览器不持久化 Bearer。

```text
POST /api/v2/auth/wechat/mini/exchange
POST /api/v2/auth/wechat/web/login-sessions
GET  /api/v2/auth/wechat/web/login-sessions/{id}
POST /api/v2/auth/wechat/web/login-sessions/{id}/exchange
POST /api/v2/auth/wechat/web/login-sessions/{id}/cancel
POST /api/v2/auth/wechat/mini/web-login-confirm
POST /api/v2/auth/logout
GET  /api/v2/me
```

### 5.1 Web login session

- `POST create` 接收规范化的高熵 verifier；返回 `sessionId`、`expiresAt` 和二维码图片数据。scene ticket 只作为二维码内部的 opaque 输入，不单独返回给浏览器；返回值不包含 user identity。
- `GET status` 必须带 `X-Web-Login-Verifier`；只返回 `pending|confirmed|expired|cancelled|exchanged`、过期时间和 request id，不返回绑定用户资料。
- `POST exchange` 必须再次证明 verifier 和 `confirmed` 状态，使用事务锁定并消费一次；响应设置 Web Cookie，重复调用返回稳定 `WEB_LOGIN_ALREADY_EXCHANGED`。
- `POST cancel` 必须证明 verifier；只能取消 `pending|confirmed` session。
- `POST mini/web-login-confirm` 必须带 v2 mini Bearer 和 scene ticket；确认只允许一次，session 过期或已消费时 fail-closed。

### 5.2 Cookie 与浏览器安全

- Cookie 名称使用非业务语义的服务端配置值，`HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age` 明确设置。
- 浏览器 Web API 只允许 `https://www.chickenbro.cloud` 的 Origin；不启用 `Access-Control-Allow-Origin: *`，不接受任意 Origin 的 credential request。小程序 Bearer 请求属于独立的非浏览器调用，不依赖 Web Origin。
- 改变状态的浏览器请求校验精确 Origin；状态查询使用 verifier header，不把 verifier 放 URL、日志或 HTML。Cookie 写请求同时使用 `SameSite=Lax`，不接受第三方跨站调用。
- 公开错误不包含微信原始响应、OpenID、UnionID、access token、数据库 DSN 或 Python traceback。

## 6. 前端组件边界

预计新增/修改：

- `apps/mini-taro/src/web/WebApp.tsx`：H5-only Web shell、登录状态机与登录后入口；不拥有身份事实。
- `apps/mini-taro/src/web/WebApp.module.scss`：桌面/移动响应式原型样式，复用 design-system token，不修改旧 14 路由 CSS。
- `apps/mini-taro/src/pages/auth/web-login-confirm.tsx` 与同目录 contract/config/style：小程序扫码确认页，只负责展示和调用 typed client，不读取数据库或微信 secret。
- `packages/domain/src/web-auth.ts`：login session、Cookie user、稳定状态/错误码的纯类型和 validator。
- `packages/api-client/src/web-auth.ts`：Web credential transport、mini exchange、status、confirm、exchange、logout 与 `/me`；Web 使用 `credentials: include`，小程序使用内存 Bearer。
- `packages/api-client/src/index.ts`、`packages/domain/src/index.ts`：导出 shared contracts。

H5 Web shell 不显示旧资讯、天赋、装备、WCL 或旧 WebSim 一级入口；Chickenbro/SimC 卡片在未实现业务 API 前使用清晰的“下一阶段”状态，不伪造任务或结果。

## 7. 后端组件与迁移边界

预计新增/修改：

- `server/app/api/routes/auth.py`：HTTP 输入、认证依赖、错误和 Cookie 响应；不写领域规则。
- `server/app/identity/application.py`：创建/查询/确认/exchange/cancel/logout use case。
- `server/app/identity/repository.py`：PostgreSQL identity owner 读写与事务锁。
- `server/app/integrations/wechat_mini.py`：`jscode2session`、access token 和小程序码 HTTP adapter；只输出规范化 DTO/bytes。
- `server/app/platform/cookies.py`、`server/app/platform/origin.py`：Cookie、CSRF/Origin 和 request security。
- `server/migrations/postgres/0039_wechat_web_login_sessions.sql`：仅新增 v2 identity session 表/索引/权限，不修改旧 `wechat_users`、`auth_tokens` 或旧 schema。
- `server/wow-v2-api.service` 与 `server/wow-v2-web.nginx`（或部署脚本内等价的受控模板）：独立 API 8790、静态 Web root 和 `/api/v2` 反代。

0039 必须在候选数据库备份后由明确的 PostgreSQL migrator 执行；本地测试可以使用临时 schema/fixture，但 SQLite 不得成为 Web 登录运行时 fallback。部署 Web 静态文件和 API 服务属于同一个候选窗口，必须保留上一版静态目录、service env 与 schema rollback 路径。

## 8. 失败、回滚和隐私

用户可见失败只分为：二维码不可生成、会话不存在/过期/取消、需要小程序确认、verifier 不匹配、已消费、服务不可用和身份服务未配置。所有状态保留重试或转小程序的动作，不自动把失败变成匿名成功。

代码回滚可以恢复上一版 Web/API；Cookie session 可通过撤销表或配置禁用；0039 迁移只在候选前按备份和反向清理预案回滚，候选/生产已有用户数据不做未经审计的 destructive rollback。Web 页面和 evidence 不记录 OpenID、UnionID、昵称、完整 profile、聊天正文、微信 token 或 DSN。

## 9. 验证与交付门槛

### 9.1 本地

- Domain/API contract tests：状态机、verifier hash、一次性 exchange、过期/重放/错误 Origin、Cookie 属性与 mini Bearer/ Web Cookie 分离；
- PostgreSQL repository/migration tests：owner isolation、唯一性、行锁、状态转换和 additive schema；
- Taro H5/WeApp tests：Web shell 状态、二维码/blocked/pending/authenticated 展示、小程序确认页和不进入 TabBar；
- `npm run typecheck`、`npm run lint`、目标 Vitest、Python focused suite、H5 production build；
- Harness evidence 记录缺失 PG DSN/微信配置时的真实 `UNVERIFIED` 或 `blocked`，不把构建成功当成登录成功。

### 9.2 候选/公网

候选部署前检查 `www.chickenbro.cloud` DNS、证书、Nginx 配置、API 8790 loopback、PostgreSQL 0039、微信 app 配置和静态包 identity。部署后执行：

1. HTTPS Web 首屏和静态资源 smoke；
2. create session 返回真实二维码，不能是 placeholder；
3. 真实小程序扫码进入确认页并由用户点击确认；
4. Web 状态完成 `pending -> confirmed -> authenticated`，Cookie 属性正确；
5. `/api/v2/me`、刷新、logout、过期和重放 smoke；
6. 未登录用户无法读取 `/api/v2/me`，不会看到其他用户资料；
7. 旧 `https://api.chickenbro.cloud` 健康与旧核心 API 保持原结论；
8. systemd/Nginx 日志无 secret、OpenID、UnionID、Cookie 值或完整 QR payload。

公网正式交付的证据上限只有在第 1--6 项真实通过后才可升到 `live_verified`；仅页面可访问或 API 返回 200 只能标记为可达，不能标记为登录完成。若微信凭据、AppID 环境或证书缺失，交付结果必须写成“公网 Web 原型已部署，真实小程序登录 blocked”，并保留修复入口。

## 10. 明确不做

- 不实现微信网站应用 OAuth、`snsapi_login`、网站 AppID/AppSecret 或 UnionID 前置条件；
- 不把小程序 `session_key`、Cookie、OpenID 或 access token 交给 Web；
- 不把二维码 scene ticket 当作 user identity；
- 不把现有旧 `/api/auth/wechat-login` 直接暴露给 Web；
- 不在本项目中接入 Codex、Raider.IO、WCL、SimC 执行、付费或旧路由删除；
- 不在验证不足时把 `www` DNS、Nginx active、HTTP 200 或静态构建称为产品完成。
