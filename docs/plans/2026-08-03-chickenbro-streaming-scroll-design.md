# 炸鸡队长：真实流式回复与会话自动跟随设计

状态：`需求合同已确认，待实施计划`

分类：`Strict`

确认日期：2026-08-03

本设计扩展 [炸鸡队长 Phase 1：极简聊天表面与会话存档设计](2026-08-01-chickenbro-chat-surface-design.md)，但不改变其 owner、证据、会话、持久化和 Tool 边界。它只解决玩家发送后等待整段长回答才看到内容、以及阅读位置被新内容打断的体验问题。

当前事实：[project-state.json](../project-state.json)、[roadmap.md](../roadmap.md)、[Harness](../harness.md)、[统一 ChatBot 后端设计](2026-07-24-chickenbro-chatbot-design.md)、[Phase 1 聊天表面设计](2026-08-01-chickenbro-chat-surface-design.md)、[验证矩阵](../verification-matrix.md)。

## 用户目标与完成体验

玩家向炸鸡队长提问后，应能在回答生成期间逐段看见**真实且可公开的**内容，而不是面对长时间空白或由客户端伪造的“正在输入”。当玩家留在会话底部时，最新内容应自然进入视野；当他上滑阅读前文时，页面必须停止抢回到底部，并给出一个明确的“回到最新”操作。

正常路径：

```text
发送问题 -> 显示生成中 -> 真实安全片段逐段出现 -> 最终校验通过 -> 完整回答落库
                    |                                   |
                    +-- 位于底部：随新内容跟随             +-- 保持在最新
                    +-- 手动上滑：停止跟随，显示“回到最新”
```

失败路径：若连接中断、上游事件不可安全公开、最终回答不通过既有来源/数字/owner 校验，客户端立即丢弃本轮临时片段，保留用户消息并在原位置显示“重试发送”。服务端不得写入 assistant 消息，不得把未完成片段作为历史、依据或可引用结论。

## 已确认的范围

### 1. HTTP 分块 NDJSON 传输

- 新增同一后端、同一认证与 owner 规则下的 `POST /api/chickenbro/messages/stream`。请求体、访客/认证 owner 注入、会话选择和幂等语义与现有 `POST /api/chickenbro/messages` 一致。
- 响应为 UTF-8、逐行结束的 `application/x-ndjson; charset=utf-8`。服务端在每一条已完成 JSON 记录后 flush，并为既有部署链路显式关闭可能的代理缓冲。
- 现有 `POST /api/chickenbro/messages` 保持完整 JSON 响应合同与超时语义，作为不支持流式传输、流式连接建立失败或后续兼容调用的降级路径；它不是第二个事实来源。
- 每次发送只允许一个活动请求。新话题、重试、离开页面或取消当前发送都会取消当前传输；旧请求的迟到事件不得写入新会话或覆盖新一轮状态。

对外事件严格限于下列公开协议，所有记录都带 `requestId`，`delta` 另带单调递增的 `sequence`：

| 类型 | 允许内容 | 客户端行为 |
| --- | --- | --- |
| `started` | 已创建/选定的 `sessionId`、`requestId` | 把本轮标记为生成中；不创建 assistant 历史消息 |
| `status` | 有限枚举的公开阶段，如 `preparing`、`generating` | 可展示简短等待状态；不展示内部 Tool、日志或诊断 |
| `delta` | 已通过公开可见性和文本安全检查的 `text` | 追加到仅内存中的临时 assistant turn；按滚动规则处理 |
| `final` | 与现有完整接口相同、已经过最终校验和持久化的 `ChickenbroResponse` | 用最终响应原子替换临时 turn，并刷新会话真值 |
| `failed` | 有界错误 `code`、`retryable` | 丢弃临时 turn，保留用户消息并提供重试 |

协议不得发送模型提示词、思维链、原始 CLI JSONL、Tool 名称/参数、日志、密钥、内部异常、未验证来源、未过滤数字或其他 owner 的数据。未知事件、跨 requestId/sequence、无法解码 JSON、重复/倒退 sequence 或不符合 schema 的记录均 fail closed：取消该轮、丢弃临时文本并进入可重试失败态。

### 2. 真实文本增量的上游证明门槛

当前执行器只保证可在结束后获得完整、经验证的回答；它的 JSONL 事件是否有可安全映射为玩家文本的增量，尚未作为生产事实确认。因此，实施必须先在最终候选执行器版本上完成事件 schema characterization：记录可复现实例的事件类型、顺序、内容边界与取消行为，并证明至少一种事件能稳定提供独立、公开、安全的回答文本片段。

只有同时满足以下条件，后端才可发出 `delta`：

1. 上游事件类型已被明确白名单化，并能与本轮 `requestId` 唯一关联；
2. 每一个片段在发送前经过与完整回答一致的公开可见性、数字、证据/owner 防泄漏规则，且不依赖未到达的后文才可判定安全；
3. 片段顺序完整可判定，取消或失败不会让片段进入 PostgreSQL assistant history；
4. 最终 `ChickenbroResponse` 仍由既有完整校验器校验并作为唯一可持久化、可引用的回答。

如果候选环境只提供最终完整回答，或任何文本事件不能满足上述安全证明，禁止用延时切片、前端打字动画、替代模型/供应商或暴露原始事件来伪装流式。此时只可发送安全的状态和最终事件，保留完整 JSON 降级，并将“真实文本流式受上游事件能力阻断”如实记录为候选阻断；接入其他 provider 或直连模型 API 是范围扩展，须另行获得用户确认。

### 3. 微信客户端的增量解析与状态

- typed API client 负责创建 `Taro.request` 任务、订阅 `onChunkReceived`、取消请求，并将 byte chunk 交给增量 UTF-8/NDJSON decoder；页面和设计系统组件不得自行拼接网络字节。
- decoder 必须容忍 JSON 行、换行符和 UTF-8 中文字符被任意切分；只有完整且 schema 合法的一行才交给会话状态机。
- 页面保持 `empty`、`loading`、`ready`、`sending`、`error` 既有含义。`sending` 中的临时 assistant turn 只存在于内存，不能被会话归档、路由恢复、缓存或重新加载当作历史。
- `final` 到达后，以完整响应原子替换临时 turn；`failed`、网络断开、取消、解析失败或最终校验失败时移除临时 turn。若用户主动取消，则不制造“队长回答失败”的结论；他仍可继续输入或重试原用户消息。
- 完整接口的 fallback 与流式接口使用同一用户消息、同一 `clientMessageId`、同一会话归属与幂等约束，避免一次手动发送形成两条用户消息或两次 Agent 执行。

### 4. 自动跟随与阅读主权

聊天正文改由受控的 `ScrollView` 承载，输入框和全局四项导航仍保持既有固定区域合同。滚动状态是本轮页面交互状态，不写入后端：

- 首次发送、打开会话后首次定位到底部、点击“回到最新”后，`followLatest=true`。
- 通过 `scrollTop`、`scrollHeight`、`clientHeight` 计算距底部距离；在小阈值（实现时固定为有测试覆盖的值，建议 80px）内视为仍在底部。
- 当玩家主动上滑且已离开该阈值，设置 `followLatest=false`。后续 `delta`、`status`、`final` 和键盘布局变化都不得强制改变其阅读位置。
- `followLatest=true` 时，新片段在下一次 layout 后定位到末尾；长回答最终到达也保持末尾可见。滚动请求必须按帧合并，避免每个小片段触发一次布局抖动。
- `followLatest=false` 且有未见的新内容时，在不遮挡输入框的固定聊天区域内显示轻量“回到最新”按钮。点击后滚至末尾、清空未见标记并重新启用跟随。
- 新话题、会话切换、发送失败和取消必须清除本轮未见标记，不能把上一会话的滚动位置/新内容提示带到下一会话。

这不是把 WebView 位置当作消息真值：后端仍拥有消息排序、最终内容与 owner 隔离；前端只控制本地视口。

## Owner、数据与工程边界

| 范围 | 责任与约束 |
| --- | --- |
| `server/news_backend.py` / 消息编排 owner | 建立流式 HTTP 生命周期，注入认证/访客 owner，映射有限公开事件，并只在最终校验成功后写 assistant 消息 |
| `server/codex_worker.py` / 执行器 adapter | 表征并白名单映射上游事件；不能把原始 JSONL、stdout、提示词或 Tool 事件抬升为公开 payload |
| PostgreSQL 会话/消息 owner | 继续作为唯一运行时持久层；只保存既有最终 `ChickenbroResponse` 对应的 assistant 消息，失败/取消/partial text 零写入 |
| `packages/api-client` | 严格校验完整 JSON 与 NDJSON 事件、维护同一发送幂等身份；不从未知字段推断安全状态 |
| `apps/mini-taro` 与共享聊天组件 | 呈现临时 turn、重试和阅读位置；不自行校验来源/数字/owner，不合成队长内容 |
| health、timer、同步、Tool Registry | 本次 `must_not_change`；流式连接和页面状态不得触发来源刷新、异步 backfill、SimC/WCL 执行或工具能力扩张 |

性能与可用性要求：流式端点必须保留单请求超时、取消、并发和输出大小上限；服务端检测到下游断开后停止继续向该客户端写入并走既有取消/清理语义。客户端只保留当前流的受限文本缓冲，增量合帧渲染；不因历史会话加载而重放流事件。应记录不含内容的请求结果、事件计数、首个安全文本/最终完成/失败/取消耗时，以区分“连接成功”与“真正出现安全文本”；不得把 HTTP 200、`started` 或状态事件当作流式成功。

## 明确不做

- 不采用 SSE、WebSocket 或浏览器/客户端直连任意模型、供应商、数据库、密钥或 Tool。
- 不增加 Tool、外部来源、个人上下文、会话查询权限、SimC/WCL 重分析、异步 Worker、定时刷新或数据迁移。
- 不把最终回答按字符/延迟切片伪装成真实流式，不在客户端生成或改写队长内容。
- 不更改其他 13 个路由、全局导航、聊天存档数据模型或已归档 Tool Registry Phase 2 的能力范围。

## 验收与证据

### 自动化合同

- 后端：同一认证/访客 owner、会话归属、错误分类、取消、断开、最终成功写入、失败零 assistant 写入；完整 JSON 接口不回归。
- 执行器 adapter：候选版本实际事件 schema characterization；未知/Tool/原始事件拒绝；只有被证明安全的文本事件可形成 `delta`。
- typed client：NDJSON schema、UTF-8 中文跨 chunk、JSON 行跨 chunk、乱序/重复 sequence、`requestId` 不匹配、未知事件、取消与 fallback 幂等性。
- Taro：临时 turn 仅内存、失败丢弃+重试、最终原子替换；`followLatest` 阈值状态机、手动上滑锁定、未见提示、回到最新与会话切换清理。
- 回归：聊天表面、会话归档、owner 隔离、UI 架构审计和 API client 合同保持有效。自动测试只能证明协议和行为合同，不证明真实上游文本流或微信视觉体验。

### 候选与人工验收

最终 runtime head 必须在候选部署/预览中记录：commit 与运行文件 identity、stream 端点响应头、真实 NDJSON 记录顺序、上游文本 delta 的安全映射证明、取消后的零 assistant 持久化、完整 JSON fallback、用户/访客 owner 隔离、定时任务/同步未回流，以及可执行的 code rollback 路径。若实际执行器没有可安全文本 delta，候选证据必须明确为阻断，不能以 status/final 或接口 200 晋级。

真实微信验收至少覆盖：

1. 正常提问能逐段看到实际队长内容，最终回答与归档中的已保存版本一致；
2. 回答增长时停留底部会自然跟随；用户上滑后不会被拉回，点击“回到最新”才恢复跟随；
3. 人为中断、校验失败或网络失败后，临时队长文本消失、用户消息保留并可重试，归档没有不完整 assistant 消息；
4. 访客与认证用户不能读取或写入对方会话；完整接口降级仍能在不支持流式的环境完成同一聊天动作。

## 回滚与实施拆分

流式端点、事件 adapter 和客户端开关应可整体关闭，回退到已存在的完整 JSON 聊天路径；不依赖数据迁移，因此回滚不删除或修复临时 assistant 数据（合同要求它从不落库）。候选部署失败、上游事件证明失败、owner/校验问题或微信滚动行为不符合验收时，保持该功能不晋级，恢复完整响应体验并记录阻断。

实施计划必须按以下顺序拆分：

1. 为候选执行器建立事件 schema characterization 和公开文本安全映射测试；未证明真实文本 delta 前不实现可见伪流式。
2. 冻结 NDJSON endpoint、typed client decoder、取消和幂等合同；先补充失败路径测试。
3. 在共享聊天 owner 实现临时 turn 与 `ScrollView` 跟随状态机，保持 Phase 1 的固定输入区和会话边界。
4. 完成后端/前端定向验证、UI 架构审计、最终候选部署、真实微信验收和 Strict task-scoped release packet；通过后才进入合并与 post-merge DevTools 刷新。
