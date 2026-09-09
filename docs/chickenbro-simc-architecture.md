# Chickenbro 当前架构

依据 2026-09-09 仓库实现整理。当前只提供 Web Chat 与 SimC，QQ 网站登录已上线；本轮移除残余小程序源码的部署状态另见[清理计划](plans/2026-09-09-mini-retirement.md)。

## 客户端与传输

`apps/mini-taro/src/app.tsx` 挂载 React WebApp，Taro H5 使用单一 `pages/web/index` 入口。`/` 是对话，`/simc` 是模拟，`/?view=faq` 是 FAQ；旧短路径仅作为 Web URL 兼容入口，不挂载小程序页面。

依赖方向为 UI → typed API client → HTTP route → application → domain / port → repository / adapter。Domain 不依赖 FastAPI、Taro 或具体外部 provider。客户端使用显式 `web` 或受限 `public` auth context，普通请求使用 Taro H5 request，SSE 使用浏览器 fetch；不再提供 Mini Bearer、微信运行环境或原生分块请求分支。

## 身份

QQ 登录由 `identity.qq_application` 与 `integrations.qq_connect` 实现：同源 POST 创建随机 state 和 HttpOnly 浏览器绑定，浏览器跳转 QQ 官方授权，固定 callback 校验 state、绑定、时效和 AppID，再由数据库原子消费尝试。provider/appid/openid 映射到 `identity.users.id`，签发 Web Session 和 CSRF Cookie。

授权码、AppKey 和 QQ token 只在服务器 provider 边界短暂使用，不写日志、业务表或公开响应。QQ 昵称与头像经过有界清理；头像只允许受信 HTTPS QQ 域名。默认 Cookie 使用 Secure、HttpOnly（Session）、SameSite=Lax 和 Path=/；写请求检查精确 Origin/Host 与 CSRF。Bearer 请求拒绝，QQ 登录不会自动关联旧微信账号。

## Chat

`server/app/chickenbro` 拥有会话、消息、运行、图片和工具结果。路由从 Principal 注入 owner；账号级单回复与请求幂等在服务端执行。Web 可读取历史、流式进展、耗时、回答反馈以及归档会话。

生成使用 `chat.executions` 持久化调度和独立 Worker；API 断开不主动取消生成。Worker 通过租约、阶段和工具结果记录处理故障，不盲目重放副作用。图片存储与读取 owner-scoped，归档和保留策略由服务端执行。

## SimC 与 Worker

`server/app/simulation` 拥有 Raider.IO 来源快照、校验、compiler、任务、attempt 和结果。`server/app/worker` 负责 PostgreSQL 队列 claim、lease、心跳和 handler dispatch。SimulationCraft 仅在云端运行；结果必须有正业务指标与来源信息，不能用进程退出码代替成功。

WCL 适配器用于战斗研究及历史天赋恢复，不恢复 WCL 新角色导入。输出和坦克专精受运行配置与 readiness 控制，治疗明确拒绝。新任务和装备对照保留原快照与结果。

## 数据与所有权

PostgreSQL 当前 schema 为 `identity`、`chat`、`simc`、`ops`。所有用户业务查询从内部 `user_id` 限定所有权；请求体不能选择 owner。`ops.job_queue` 包含任务引用，`ops.audit_events` 保留操作审计；清理不能只删除用户而遗漏队列、运行及图片。

历史 migration 不改写，旧微信 schema 只作为已应用迁移与恢复兼容结构保留；本轮数据清理以精确清单及新恢复证据执行，不与 QQ 数据合并。

当前职责与检查入口见[项目 owners](project-owner-map.json)、[后端 owners](backend-owner-map.json)和[验证矩阵](verification-matrix.md)。[旧双端架构](chickenbro-simc-architecture-pre-mini-retirement.md)仅供追溯。
