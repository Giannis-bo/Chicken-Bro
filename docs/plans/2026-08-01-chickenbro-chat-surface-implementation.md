# 炸鸡队长 Phase 1 极简聊天表面实施计划

> **执行方式：** 在当前 `codex/chickenbro-chat-surface` 分支内联执行。用户已确认 [产品设计](2026-08-01-chickenbro-chat-surface-design.md)，本计划不创建新路由、不自动携带构筑上下文，也不提前启用 WCL、Raider.IO 或 SimC Tool。

## 目标与验收

玩家从“队长”Tab 进入后，看到的是单一对话页：左侧可查看存档，中间是“炸鸡队长”，右侧可新建话题；正文展示该会话完整消息历史，底部只有输入与发送。新话题只是本地清空，会在首次发送时才创建服务端会话。存档是按最近更新排序的真实服务端会话列表，点击后回到根页并恢复该会话。

验收边界：

- 保持 `apps/mini-taro/src/app.config.ts` 的 14 条活动路由不变：`/pages/simulator/simulator` 为队长主对话，既有 `/pages/simulator/chickenbro` 为对话存档。
- 消息请求仅携带输入文本、选定会话 ID 与该会话服务端历史；客户端不读取、不传递职业、专精、场景或模板上下文。
- 会话列表和详情都按当前 owner / guest 隔离；非法 cursor、limit、身份或会话归属必须失败，不能伪装为“没有存档”。
- 仅在服务端已有的受限证据附件随回答内联展示；没有伪造的“资料不足”、建议问题、上下文卡、固定分析状态或 SimC/WCL/Raider.IO 结果。
- 所有 UI 几何来自本计划 Task 1 产生的 target-only 设计合同，不从旧 CSS 或运行截图反推。

## 共同约束

- 先写失败测试，再实现最小代码使其通过；不改 legacy `pages/`，除非 caller-proof 证明活动路径依赖它。
- `packages/domain` 定义共享数据形状，`packages/api-client` 是 Taro 的唯一 HTTP 调用方。
- PostgreSQL 是运行时唯一数据库；SQLite helper 仅保持本地测试兼容。两条数据路径须拥有同一分页、排序和 owner 语义。
- `nextCursor` 是 base64url JSON，字段仅为 `updatedAt`、`sessionId`；服务端严格解析，列表排序为 `updated_at DESC, id DESC`。
- 页面无法加载会话、列表或发送失败时必须显示明确错误和重试，不把 transport fallback 作为真实空状态或真实回答。
- 每个任务完成后运行其列出的测试和 `git diff --check`；只在用户完成手工验收并明确允许收尾时再合并、推送或刷新微信 DevTools。

## Task 1：更新控制面和 target-only 交互合同

**文件：**

- Modify: `docs/plans/README.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/simulator-simc-end-to-end.md`
- Modify: `docs/design/current-ui/core-interaction-contract.json`
- Modify: `docs/design/current-ui/route-geometry-contract.json`
- Modify: `docs/design/current-ui/target-registry.json`
- Modify: `docs/design/current-ui/runtime-review-status.json`
- Modify: `docs/design/current-ui/runtime-asset-slot-mapping-contract.json`
- Add: `docs/design/current-ui/routes/simulator-home/product-design.md`
- Add: `docs/design/current-ui/routes/chickenbro-chat/product-design.md`
- Modify: `docs/design/current-ui/routes/simulator-home/{asset-contract.json,component-contract.json,target-inventory.json,target-geometry.json,truth-adaptation.json}`
- Modify: `docs/design/current-ui/routes/chickenbro-chat/{asset-contract.json,component-contract.json,target-inventory.json,target-geometry.json,truth-adaptation.json}`
- Modify: `scripts/audit-ui-architecture.js`
- Test: `tests/audit-ui-architecture-paths.test.js`

1. 在现有两个 canonical route ID 内保留 14-route registry：`simulator_home` 的显示角色改为“队长主对话”，`chickenbro_chat` 的显示角色改为“对话存档”，不新增 route target。所有可见角色在 truth-adaptation 中明确为 UI 状态，不把旧截图、旧 CSS 或旧组件当 target 几何来源。
2. 在两个 `product-design.md` 中录入用户确认的 390×843 target-only 结构：主页顶部 `[对话存档 | 炸鸡队长 | + 新话题]`、全量消息滚动区、底部输入发送；存档页为返回、标题、更新时间排序会话列表。只定义安全区、间距、字号、浅金强调、空状态与 loading/error 状态，不保留旧仪表盘卡片。
3. 从该设计源派生 inventory、geometry、component tree 与交互合同。核心控件稳定命名为 `chickenbro-open-archive`、`chickenbro-new-topic`、`chickenbro-composer`、`chickenbro-send`、`chickenbro-archive-session`；删除旧的证据架、粘贴、上传、推荐问法和工作台上下文控件要求。
4. 更新 owner map：活动 Taro page、共享 `PageFrame`、`ChickenbroChatComponents`、domain/API client、`news_backend.py` 和 `postgres_personal_store.py` 的 owner 与 consumer 边界可追溯。更新 runbook，使“队长根页 + 存档页”与既有受控 Tool 路线一致。
5. 先扩展 `tests/audit-ui-architecture-paths.test.js`，断言新 contract 的固定控件与 14 路由一致性；改造 `scripts/audit-ui-architecture.js` 至测试通过。运行：

   ```powershell
   $env:Path='C:\Users\blizz\Tools\node\node-v23.9.0-win-x64;'+$env:Path
   node --test tests/audit-ui-architecture-paths.test.js
   npm run audit:ui-architecture
   ```

## Task 2：以 owner 安全的会话列表补齐后端合同

**文件：**

- Modify: `server/news_backend.py`
- Modify: `server/postgres_personal_store.py`
- Modify: `tests/news_backend_test.py`
- Modify: `tests/postgres_personal_store_test.py`
- Modify when schema test needs public-contract coverage: `tests/postgres_schema_test.py`

1. 在 `tests/news_backend_test.py` 先添加 API 失败测试：匿名/guest 不可跨 owner 读取、无 `id` 的 `GET /api/chickenbro/sessions` 返回自己的分页列表、非法 `limit` 或 cursor 为 400、他人 detail 仍为 404。
2. 在 `tests/postgres_personal_store_test.py` 先添加排序与 pagination 测试：结果以 `(updated_at DESC, id DESC)` 稳定排序，第二页无重复/无遗漏，查询仅按 `user_id` 过滤，查询投影不返回 `metadata/context_json`。
3. 在 `server/postgres_personal_store.py` 实现 `list_chickenbro_sessions(user_id, limit, cursor)`：查询 `limit + 1`，根据最后一项生成下一 cursor；仅投影 `id,title,created_at,updated_at`。在 `server/news_backend.py` 增加严格 limit/cursor 编解码，SQLite 兼容实现同一排序/过滤语义。
4. 扩展既有 GET 分发：带 `id` / `sessionId` 时继续走详情；无 ID 时解析身份且只返回 `{ sessions, nextCursor }`。未知或缺失 owner 不创建 guest；detail 的既有 404 owner-mismatch 语义不变。
5. 运行：

   ```powershell
   $env:PYTHONIOENCODING='utf-8'
   python -m unittest tests.news_backend_test tests.postgres_personal_store_test tests.postgres_schema_test
   ```

## Task 3：定义类型并提供显式的 session/list client 调用

**文件：**

- Modify: `packages/domain/src/entities.ts`
- Modify: `packages/domain/src/index.ts`（仅当新类型未被 re-export）
- Modify: `packages/api-client/src/simulator.ts`
- Modify: `packages/api-client/src/simulator.test.ts`

1. 先在 API client 测试写入真实 payload 的严格验证：会话摘要要求 `sessionId/title/productPhase/createdAt/updatedAt`，消息沿用现有 role/content 合同；列表可以为空但 malformed 条目不可静默跳过；detail 不可缺 session。
2. 在 domain 增加 `ChickenbroSessionSummary`、`ChickenbroSessionListPayload` 与 `ChickenbroSessionDetailPayload`。列表摘要不含 `metadata`，以免 UI 把服务端内部上下文暴露为用户事实。
3. 在 `SimulatorClient` 增加 `chickenbroSessions({ limit, cursor })` 与 `chickenbroSession(sessionId)`，每次都显式带现有 guest identity 参数。成功响应经严格 validator 后返回；fallback 标识保持 `fromFallback`，调用页面不得将它作为真实 archive 结果使用。
4. 保持 `chickenbroMessage` 的唯一发送路径；不添加 `context` 参数，现有根页和存档选择后都只传 `{ sessionId, content }`。
5. 运行：

   ```powershell
   $env:Path='C:\Users\blizz\Tools\node\node-v23.9.0-win-x64;'+$env:Path
   node --test packages/api-client/src/simulator.test.ts
   ```

## Task 4：将活动根页改为 ChatGPT 式对话并将原 chat route 改为存档

**文件：**

- Modify: `apps/mini-taro/src/pages/simulator/simulator.tsx`
- Modify: `apps/mini-taro/src/pages/simulator/simulator.scss`
- Modify: `apps/mini-taro/src/pages/simulator/chickenbro.tsx`
- Modify: `apps/mini-taro/src/pages/simulator/chickenbro.scss`
- Modify: `apps/mini-taro/src/pages/simulator/chickenbro-model.ts`
- Modify: `apps/mini-taro/src/pages/simulator/chickenbro-model.test.ts`
- Modify: `apps/mini-taro/src/pages/builds/workbench.tsx`
- Modify: `packages/design-system/src/components/ChickenbroChatComponents.tsx`
- Modify: `packages/design-system/src/components/ChickenbroChatComponents.module.scss`
- Modify: `packages/design-system/src/components/PageFrame.tsx`
- Modify: `packages/design-system/src/components/PageFrame.chrome.ts`
- Modify: `packages/design-system/src/components/owners.module.scss`
- Modify: `packages/design-system/src/index.ts`
- Delete after caller proof: `packages/design-system/src/components/SimulatorHomeComponents.tsx`
- Delete after caller proof: `packages/design-system/src/components/SimulatorHomeComponents.module.scss`
- Modify: `apps/mini-taro/src/pages/simulator/simulator-page-contract.test.ts`
- Modify: `apps/mini-taro/src/pages/simulator/simulator-home-model.test.ts`

1. 先改 model/component tests，使其要求完整历史（非最后两条）、空新话题、纯文本 send payload、受限附件内联显示、archive click 选会话，并明确拒绝旧 context/suggestion/evidence-shelf 结构。
2. 在 `PageFrame` 增加共享的队长根页 chrome variant：左 action、视觉居中的标题、右 action。保持其他四个 root variant 原样；通过 `data-control` 暴露新 contract 的控件名。
3. 重写 `ChickenbroChatComponents` 为少量可组合单元：完整 transcript、单条附件、composer、message loading/error、archive row。删除或停止 export 所有 context panel、推荐问法、固定状态与证据边界面板。删除 `SimulatorHomeComponents` 前使用 `rg` 证明没有活动调用方，并同步 package index。
4. 将 `/pages/simulator/simulator` 实现为队长 Tab 根页：`useDidShow` 加载/恢复当前会话；“新话题”只清空本地 state；首次发送不带 session ID，让现有 message endpoint 创建 session；之后按返回 session 更新。本地用已有 namespaced storage 暂存 archive 选择，archive 页 `switchTab` 回根页后由根页消费 ID 并加载详情。`apps/mini-taro/src/pages/builds/workbench.tsx` 的 assistant 导航改到根页，去掉 URL context 传递。
5. 将 `/pages/simulator/chickenbro` 实现为 pushed 存档列表：首次加载真实列表，支持“继续加载”但不加搜索、重命名或删除。点击写入待恢复 ID 后回队长根页。对于失败、fallback 或无 owner，显示错误重试而非空存档；正常空列表显示“还没有对话”。
6. 用设计 token 和共享壳实现页面；不引入独立 dashboard panel、固定底栏卡片或 route-private header。运行：

   ```powershell
   $env:Path='C:\Users\blizz\Tools\node\node-v23.9.0-win-x64;'+$env:Path
   node --test apps/mini-taro/src/pages/simulator/chickenbro-model.test.ts apps/mini-taro/src/pages/simulator/simulator-page-contract.test.ts apps/mini-taro/src/pages/simulator/simulator-home-model.test.ts
   npm run typecheck
   npm run build:weapp
   ```

## Task 5：进行本地 CR、任务级验证并准备人工验收

**文件：**

- Modify: `docs/verification-matrix.md`（仅在现有矩阵缺少此任务所需的 API/UI 断言时）
- Add: `artifacts/releases/2026-08-01-chickenbro-chat-surface/requirements.json`
- Add: `artifacts/releases/2026-08-01-chickenbro-chat-surface/verification.json`
- Add: `artifacts/releases/2026-08-01-chickenbro-chat-surface/evidence.json`

1. 对完整 diff 做本地 CR：核对用户可见范围、owner filter、cursor 边界、fallback 表现、无自动上下文、无凭空外部工具结果、无 15th route、无 legacy owner 回流，并逐项修复有效发现。
2. 重跑 Task 1–4 的所有单测、`npm run audit:ui-architecture`、`npm run typecheck`、`npm run build:weapp`，及 Harness 对 `2026-08-01-chickenbro-chat-surface` 的 scoped verification。每条命令记录实际 command、SHA、时间和结果；不得复用历史 release packet。
3. 在候选运行环境可用时，以本分支 SHA 做 API smoke：owner A/B 列表隔离、cursor 分页、detail 恢复、首条发送创建会话、已有会话续聊；异步 sync 保持关闭。若候选不可用，记录明确的 exception 和原因，不能把本地测试包装为运行态结果。
4. 运行态通过后，给用户一批不超过两条的微信验收路径：新话题首发与回到存档恢复。用户明确表示已验收/可以收尾前，不合并、不推送、不删除分支。

## 回滚

本切片没有 schema migration 或异步任务。若候选/API/UI 验证失败，回退该分支提交即可恢复原 14-route 入口；服务端列表端点是加法，不会改变既有 `GET /api/chickenbro/sessions?id=...` 或 `POST /api/chickenbro/messages` 的 detail/send 合同。
