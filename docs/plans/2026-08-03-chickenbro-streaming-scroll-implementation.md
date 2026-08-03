# 炸鸡队长：真实流式回复与会话自动跟随实施计划

> **执行者：** 使用 `superpowers:executing-plans` 逐项实施；每项先写失败测试，再以最小改动实现并运行该项验证。

**目标：** 在不改变 owner、来源、最终校验和持久化权威的前提下，让炸鸡队长通过服务端代理的真实模型 delta 输出回答，并在玩家仍阅读最新内容时自动跟随；上滑阅读时不抢滚动位置。

**架构：** 独立的 Chickenbro 流式 provider 配置仅由后端读取。服务端以 provider-compatible 的 JSON object 模式读取 OpenAI-compatible Chat Completions SSE delta，经过 `answer` 字段、完整 schema 和数字门禁后，转换成小程序可消费的 HTTP chunked NDJSON。`final` 仍走既有完整 `ChickenbroResponse` 校验和持久化；任何中断、取消、解码或最终校验失败都丢弃内存中的 partial 文本并不写 assistant 消息。

**技术栈：** Python 标准库 HTTP/urllib、现有 `news_backend.py` / PostgreSQL personal store、Taro `request.onChunkReceived` / `ScrollView`、TypeScript node:test。

**设计合同：** [真实流式回复与会话自动跟随设计](2026-08-03-chickenbro-streaming-scroll-design.md)。本实施计划具有当前执行权。

## 全局边界与验收

- 保留 `POST /api/chickenbro/messages` 的完整 JSON 合同；新增 `POST /api/chickenbro/messages/stream`，相同 owner、会话、访客和 `clientMessageId` 语义。
- 公开 NDJSON 事件仅为 `started`、`status`、`delta`、`final`、`failed`；每条含 `requestId`，`delta` 含严格递增 `sequence`。
- 不向客户端发送密钥、上游原始 SSE/JSONL、提示词、Tool 信息、内部异常、未验证来源或数字。流量或 `started` 不算流式成功，候选必须观测到真实 `delta`。
- dedicated provider 未配置、连接失败、读取中断、取消、行解码失败、事件顺序错误或最终校验失败均 fail closed：移除临时 turn、不写 assistant 历史、保留用户消息可重试。
- 禁止延时字符切片、前端假打字、直连模型、SSE/WebSocket 对小程序暴露、来源/Tool/worker/timer/迁移扩张。
- 聊天在距底 80px 内才自动跟随；玩家上滑后停止跟随并提供“回到最新”。输入区与全局底部导航的现有 dock 合同不得改变。

## 文件责任图

| 文件 | 责任 |
| --- | --- |
| `server/llm_client.py` | 读取独立流式配置、建立上游 SSE、只产出可解析的 provider delta |
| `server/chickenbro_stream.py` | 将 provider 文本累积为安全的 `answer` 前缀，负责数字门禁和最终 JSON 完整性 |
| `server/news_backend.py` | owner/preflight、agent 编排、chunked NDJSON、最终持久化与取消/失败清理 |
| `server/postgres_personal_store.py` | 允许 agent job 精确记录取消终态，不新增表或迁移 |
| `packages/domain/src/route-contract.ts` | 声明受认证/访客能力约束的流式端点 |
| `packages/api-client/src/transport.ts` | 集中处理 Taro chunk transport、取消及 byte-safe NDJSON 解码 |
| `packages/api-client/src/simulator.ts` | 校验公开流事件、暴露 typed stream 生命周期而不把 partial 当作历史 |
| `apps/mini-taro/src/pages/simulator/*` | 临时 turn、请求代际隔离、跟随/锁定/回到最新交互与卸载取消 |
| `tests/*` 与 `apps/mini-taro/src/pages/simulator/*.test.ts` | 对上述 fail-closed、owner 与阅读主权合同的可复现证据 |

## 任务 1：专用 provider 流与安全 answer 增量解析

**文件：**

- 新增：`server/chickenbro_stream.py`
- 修改：`server/llm_client.py`
- 新增：`tests/chickenbro_stream_test.py`
- 新增：`tests/llm_client_test.py`

1. 先在 `tests/chickenbro_stream_test.py` 写入失败测试：JSON `{"answer":"..."}` 被任意 Unicode 边界分段时，只释放完整、安全的 answer 新增前缀；未知顶层字段、未经允许的数字、超限缓冲和不完整终态均不释放。
2. 在 `tests/llm_client_test.py` 写入失败测试：仅当 `WOW_CHICKENBRO_STREAM_ENABLED=1` 和专用 URL/key/model 都存在才启用；请求带 `stream: true`、provider-compatible 的 `json_object` 与 `Accept: text/event-stream`；SSE 的 `[DONE]`、空 delta 与 malformed 行有明确结果，测试日志不含 key。完整 schema 仍由后端流解析器与最终校验器执行。
3. 新建 `ChickenbroAnswerStream`，以 answer JSON 字符串的完整前缀作为唯一 public text 来源；在流内保持 64 字符数字尾部，调用既有 allowed-number/文本门禁后才按 sequence 释放。
4. 在 `llm_client.py` 新增无副作用的专用配置读取及 `stream_chat_completion(...)` 生成器。保持现有 `call_chat_completion` 行为不变；不复用全局 LLM 配置以免意外改变其他调用。
5. 运行 `python3 -m unittest tests.chickenbro_stream_test tests.llm_client_test`；确认先红、实现后绿，再局部审查无凭据输出。

## 任务 2：服务端 NDJSON 生命周期、最终校验和零 partial 落库

**文件：**

- 修改：`server/news_backend.py`
- 修改：`server/postgres_personal_store.py`
- 修改：`tests/news_backend_test.py`
- 修改：`tests/postgres_personal_store_test.py`

1. 先写失败测试，覆盖：guest/auth owner 仍被服务端注入；成功顺序为 `started`、有限 `status`、单调 `delta`、`final`；最终 assistant 恰写一次；上游/校验/写入失败仅留 user；取消记录 `cancelled` 且不留 assistant；旧完整端点行为不回归。
2. 抽取已有回答 JSON schema，让完整路径和流式路径共享 `validate_chickenbro_model_output`、数字/来源/owner 校验。实现 `run_chickenbro_agent_stream`：只有专用 provider 的真实 delta 通过 `ChickenbroAnswerStream` 才 emit；最终完整 answer 必须通过同一校验器。
3. 为 HTTP/1.1 handler 新增安全的 chunk writer：响应头使用 `application/x-ndjson; charset=utf-8`、`Transfer-Encoding: chunked`、`Cache-Control: no-cache, no-transform`、`X-Accel-Buffering: no`；每条 JSON 行后 flush，绝不写内部异常文本。连接断开转换为取消清理。
4. 实现 `/api/chickenbro/messages/stream` 的 preflight、幂等会话和 job lifecycle。`failed` 只发送有限 `code`/`retryable`，之后结束 chunk；任何 `final` 前失败不得写 assistant。将两个 store 的允许 job status 同步为 `cancelled`，不做 schema migration。
5. 运行 `python3 -m unittest tests.news_backend_test tests.postgres_personal_store_test tests.database_adapter_test`，并用一个本地 stub upstream 验证 UTF-8 NDJSON 的 chunk framing 和顺序。

## 任务 3：typed client 的 chunk decoder、代际取消和兼容降级

**文件：**

- 修改：`packages/domain/src/route-contract.ts`
- 修改：`packages/api-client/src/transport.ts`
- 修改：`packages/api-client/src/simulator.ts`
- 修改：`packages/api-client/src/index.ts`
- 修改：`packages/api-client/src/transport.test.ts`
- 修改：`packages/api-client/src/simulator.test.ts`

1. 先写失败测试：端点合同要求认证且支持 guest；中文 UTF-8 和 JSON 行在任意 ArrayBuffer 边界仍精确还原；不合法 JSON、未知 event、requestId 不一致、重复或倒退 sequence fail closed 并 abort。
2. 将 Taro `request` 的 `enableChunked`、`responseType: 'arraybuffer'` 与 `onChunkReceived` 封装在 transport；保留 auth、guest、URL 和 telemetry 中央路径。公开 task 仅能 `abort()`，不得暴露原始响应字节给页面。
3. 在 simulator client 声明封闭 `ChickenbroStreamEvent` 联合与 `streamMessage`。只有服务端在开始前明确返回 `HTTP 503` 时，才允许以同一个 `clientMessageId` 调用完整接口；未知网络失败、取消或收到 `started` 后的任何失败都只报失败，不自动再跑一次 agent。
4. 完成后运行 `npm test -- --runInBand packages/api-client/src/transport.test.ts packages/api-client/src/simulator.test.ts`；若仓库 test runner 不接受该参数，使用 `node --test` 的现有等价 scoped command 并记录实际命令。

## 任务 4：会话临时 turn 与阅读主权 UI

**文件：**

- 修改：`apps/mini-taro/src/pages/simulator/chickenbro-model.ts`
- 修改：`apps/mini-taro/src/pages/simulator/chickenbro-model.test.ts`
- 修改：`apps/mini-taro/src/pages/simulator/simulator.tsx`
- 修改：`apps/mini-taro/src/pages/simulator/ChickenbroChatComponents.tsx`
- 修改：`apps/mini-taro/src/pages/simulator/ChickenbroChatComponents.module.scss`
- 修改：`apps/mini-taro/src/pages/simulator/simulator-home-dock-contract.test.ts`

1. 先写纯模型失败测试：临时 assistant 只存内存；`delta` 按 sequence 追加；`final` 原子替换；失败/取消移除；旧 request 的迟到事件不能改新 request；80px 阈值内跟随、上滑锁定、回到最新解锁并清除未见标记。
2. 以 reducer/纯函数承载 request generation、临时文本、followLatest、unseen 状态，避免在 JSX 内做字节或协议判断。
3. 将 transcript 改为受控 `ScrollView`。用 layout 后、按帧合并的 `scrollTop` 更新实现跟随；`onScroll` 检测用户离底；锁定时渲染不遮挡 composer 的“回到最新”。不要用每个 delta 的同步强制滚动。
4. 页面使用 typed `streamMessage`；发送、新话题、重试、session change、unmount 统一 abort 当前 task，并用 generation 忽略迟到回调。partial 不进入 `loadTranscript`、本地归档或恢复状态。保留 composer/loading/error 和底部导航合同。
5. 运行 `npx vitest run apps/mini-taro/src/pages/simulator/chickenbro-model.test.ts apps/mini-taro/src/pages/simulator/simulator-home-dock-contract.test.ts`、`node --test tests/audit-ui-architecture-paths.test.js`，并用 Taro build/type check 的现有 scoped 脚本验证无 JSX/样式回归。

## 任务 5：集成验证、候选烟测和人工验收包

**文件：**

- 新增或更新：`artifacts/releases/2026-08-03-chickenbro-streaming-scroll/evidence.json`
- 修改：与现有 release packet 相连的最小 runbook/roadmap 状态文件（仅在证据形成后）

1. 本地 CR：检查 diff 只涉及文件责任图；核对所有 terminal 成功都对应真实 `delta` 计数或明确 `final-only/blocked`，绝不把 HTTP 200 当流式成功。
2. 运行受影响 Python、TypeScript、UI contract 测试及 `node scripts/verify-project.js --profile harness`。记录命令、commit、结果、失败语义、专用配置是否存在（仅布尔值）。
3. 在候选部署上，使用已有受管配置提供专用流式 provider。记录 branch/commit、runtime parity、guest/auth owner、可观测到的 `delta` 顺序、UTF-8、最终落库、取消零 partial、上滑锁定和回到最新；不得把 provider key 写入证据。
4. 回滚验证：关闭 `WOW_CHICKENBRO_STREAM_ENABLED` 或撤回候选后，完整 JSON 端点仍可用，流端点返回有界可重试失败，且无 assistant partial 修复任务。
5. 请用户在微信开发者工具手动验收长回答的首段到达、上滑不抢位、回到最新、取消/重试。获得“我已测试通过”或“可以收尾”前，不合并、推送或把任务标记完成。
