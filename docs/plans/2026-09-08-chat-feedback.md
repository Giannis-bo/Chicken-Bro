# 鸡哥回答解决情况反馈

状态：`已完成 / 本地预览已验收，提交合入`（Web/后端已上线，Mini 1.0.1 已上传，微信公开发布待用户操作）

## 已确认范围

2026-09-08 用户要求在回答下方增加是否解决按钮，收集 badcase；随后明确不收集原因；本地 Web 预览后，用户进一步明确最终界面为「是否解决」+ 线条拇指上下图标，不用 emoji 或选项文字；点击后先确认，提示“您的反馈会让鸡哥变得更好。”。沿用现有双端 Chat 流程，不新增运营后台。

- Mini/Web 已完成并持久化的回答下方显示「是否解决」和两个无边框线条拇指小图标（无障碍名称仍为已解决/未解决），点击弹窗，取消不保存、确认后保存并高亮，确认后不可修改。
- 未评价为 `null`，已解决为 `true`，未解决为 `false`。失败和生成中的回答不显示入口。
- 重复提交相同选择不新增记录、不刷新反馈时间；确认后禁止改选，双端竞态只保留先成功保存的一次。反馈失败保留已保存状态，允许重试。
- 服务端保存并在重新打开会话时双端读取；不增加实时推送。
- 每条反馈关联现有 AgentRun，因此保留 owner、会话、原提问、回答及 runtime revision，可沿会话复盘上下文。公开 API 只返回解决状态，不暴露内部运行信息。

## 当前合同与所有权

- `chat.agent_runs` 增加 `resolved` 和 `feedback_updated_at`，迁移 `0006_chat_resolution_feedback`。只允许成功回答存在反馈，不新增业务域。
- `POST /api/v2/chat/conversations/{conversationId}/messages/{messageId}/feedback`，请求与响应均为 `{ "resolved": boolean }`。已经提交相反选择返回 `409 FEEDBACK_ALREADY_SUBMITTED`，同一选择重试仍幂等成功。严格布尔输入、不接受 owner 字段；Mini Bearer/Web Cookie + CSRF 沿用现有认证。
- Chat application 接收 Principal；repository 在事务内锁住 active conversation、更新本账号成功运行记录。别人/不存在/用户消息/未完成/已归档目标统一不可评价。
- 会话读取用 `includeFeedback=true` 显式请求反馈字段；旧客户端保持原有响应合同，支持分别发布后端和客户端。
- typed domain、API client、ChatModel 和共享 `ChatFeedback` 组件承接双端 UI。

## 内部 badcase 查询

以下只读 SQL 供已获授权的数据库维护人员使用。它不会通过面向玩家的 API 公开跨账号数据；不包含 Cookie、OpenID、token 或原始模型推理。被软删除的会话按现有历史保留规则保留在库中，查询同时显示其状态。

```sql
SELECT r.id AS run_id, r.conversation_id, c.status AS conversation_status,
       r.user_message_id, r.assistant_message_id, r.runtime_revision,
       r.feedback_updated_at, q.content AS question, a.content AS answer
FROM chat.agent_runs r
JOIN chat.conversations c ON c.id = r.conversation_id AND c.user_id = r.user_id
JOIN chat.messages q ON q.id = r.user_message_id AND q.user_id = r.user_id
JOIN chat.messages a ON a.id = r.assistant_message_id AND a.user_id = r.user_id
WHERE r.resolved = false
ORDER BY r.feedback_updated_at DESC, r.id DESC
LIMIT 200;
```

## 验证与发布边界

- 验证：反馈真实 PostgreSQL 持久化/不可修改/并发首写/去重、Mini/Web 认证和 CSRF、owner 隔离、旧客户端兼容；共享组件、双端页面和历史恢复；前端测试、类型检查、lint、双端构建及生成产物。
- 证据：[本地验证记录](../../artifacts/verification/2026-09-08-chat-feedback/README.md)。浏览器截图仅为真实共享组件 + 测试容器，不代表真实微信登录或生产数据。
- 下一步：在授权发布范围内先应用迁移并更新后端，再发布 Web/Mini，执行真实双端反馈验收。回滚应用时保留新增反馈列及收集结果。
- 2026-09-08 用户确认 Web 和 Mini 本地示例预览，并明确“OK，没问题，提交合入”，授权提交、合入 main 与远端同步。预览验收不替代生产迁移、部署和真实双端数据验收。
