# 炸鸡队长来源驱动 Agent 实施计划

> **For agentic workers:** 按任务逐项执行；实现前使用 `superpowers:test-driven-development`，完成前使用 `superpowers:verification-before-completion`。任务的验证、候选部署和回滚证据只进入自己的 release packet，不借用聊天表面阶段的结果。

**目标：** 玩家自然咨询 WoW 正式服或 PTR/Beta 内容时，云端 Codex Agent 自动使用允许的、带新鲜度的来源事实回答，不再因为缺少本地 published profile 而输出泛化话术。

**架构：** `news_backend.py` 保持 HTTP、owner、会话与消息的唯一入口；新 `chickenbro_agent.py` 只负责意图、受限 Tool 调度、来源上下文裁剪与两轮 Agent 协议。`raiderio_payload.py` 继续拥有 Raider.IO 缓存，`simulator_payload.py` 继续拥有 WCL 官方 API；Agent 只接收脱敏、已校验、可引用的 `ToolResult`。缓存、社区同步和持久化的事实摘要构成“来源记忆”，不训练模型权重、不抓取未授权 Archon 页面、也不把私有聊天或日志沉淀为公共知识。

**技术栈：** Python 标准库服务、现有 PostgreSQL personal store、SQLite 测试适配器、现有 LLM/Codex executor adapter、Raider.IO 公共 API 缓存、Warcraft Logs 官方 GraphQL。

## 全局约束

- 玩家表面仍只有聊天、新话题和存档；不增加 Tool 模式、URL 表单或固定回答模板。
- Agent 只能使用后端 allowlist 的 Tool，不能取得 SQL、Shell、密钥、文件路径或任意 URL。
- 普通社区咨询不要求 WCL 链接；个人日志结论只在报告可见且授权范围满足时生成。
- 事实必须带来源、引用、track/赛季或版本、查询时间、新鲜度状态与限制；`partial`、`stale`、`blocked`、失败或缺失来源不得升级为已验证结论。
- Archon.gg 在取得 API 或书面授权前不抓取，只作为不可执行参考链接，不进入实时事实链。
- 不改变既有 SimC 提交、装备模拟、任务详情、会话 owner 隔离或前端 14 路由；`WOW_DEPLOY_START_ASYNC_SYNCS=0` 保持默认。

## 候选运行时记录（2026-08-01）

- Raider.IO 缓存来源摘要、可选 WCL 适配和自然对话回复已进入候选服务；普通构筑咨询不会要求玩家先提交 WCL、SimC 或链接。
- 2026-08-01 已修复云主机到 ChatGPT/Codex 的代理选路并重启 mihomo：未登录的 `chatgpt.com` 请求返回 403、`auth.openai.com` 的 GET 返回 405，均表明 TLS/HTTP 已到达上游而非被握手中断。
- `WOW_CHICKENBRO_CODEX_ENABLED=1` 已随 wow-backend 重启生效；同日端到端候选 smoke 返回 HTTP 200，队长任务成功完成，Codex 子进程 return code 为 0 且写入有效末条消息。运行时仍不得静默回退为固定回复。
- `chickenbro_source_refresh` 及其 4 小时定时器将 Raider.IO 来源刷新从 observed-build/装备编译中隔离；首次候选刷新正在运行，独立结果必须在下一次候选 smoke 前记录，不能借用旧 community-template service 的 failed 状态。

---

## 文件职责

- `server/chickenbro_agent.py`（新建）：`ToolResult`、意图分类、Tool allowlist、来源上下文裁剪、两轮 Agent 调度。
- `server/news_backend.py`：把 owner 和会话传给 Agent；仅在最终结果校验成功后持久化 assistant 消息。
- `server/raiderio_payload.py`：从 `get_raiderio_payload` 产生专精/场景最小来源摘要，不把完整缓存交给模型。
- `server/simulator_payload.py`：复用 `build_wcl_log_evidence`，只在聊天实际携带 WCL URL/code 时返回可见性摘要。
- `server/migrations/postgres/0024_chickenbro_source_memory.sql`（新建）：非个人来源摘要与受 owner 保护的 WCL 摘要的最小持久层。
- `server/postgres_personal_store.py`：来源记忆的 owner-bound 读写。
- `tests/chickenbro_agent_test.py`（新建）：无网络的意图、Tool、来源状态和协议单测。
- `tests/news_backend_test.py`、`tests/postgres_personal_store_test.py`、`tests/database_adapter_test.py`：路由、持久化和数据库适配回归。

## Task 1：创建受限 Agent 协议

**Files:**
- Create: `tests/chickenbro_agent_test.py`
- Create: `server/chickenbro_agent.py`
- Modify: `server/news_backend.py` (`run_chickenbro_agent`, `send_chickenbro_message`, `send_chickenbro_message_postgres`)
- Modify: `tests/news_backend_test.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class AgentIntent:
    kind: str              # community_build | personal_wcl | general
    product_phase: str     # retail | ptr | beta
    class_key: str
    spec_key: str
    scenario_key: str
    wcl_report: str

def classify_chickenbro_request(message: str, history: list[dict]) -> AgentIntent: ...

def run_chickenbro_source_agent(
    request: dict, tool_runner: Callable[[AgentIntent], list[dict]], executor: Callable
) -> dict: ...
```

- [ ] **Step 1: 写失败测试。**

  ```python
  def test_protection_warrior_build_intent_requests_community_tool(self):
      intent = classify_chickenbro_request('防战现在天赋怎么点，属性怎么搭配？', [])
      self.assertEqual('community_build', intent.kind)
      self.assertEqual('warrior', intent.class_key)
      self.assertEqual('protection', intent.spec_key)

  def test_reportless_wcl_question_does_not_require_a_report(self):
      intent = classify_chickenbro_request('防战 WCL 要看什么？', [])
      self.assertEqual('', intent.wcl_report)
      self.assertNotEqual('personal_wcl', intent.kind)
  ```

- [ ] **Step 2: 运行以确认失败。**

  ```powershell
  python -m unittest tests.chickenbro_agent_test
  ```

  预期：模块或接口不存在。

- [ ] **Step 3: 最小实现。** 创建只识别 WoW、职业/专精别名、测试服词与 WCL URL/code 的分类器。两轮 executor 协议只能产生 `query_raiderio`、`inspect_wcl_report` 或 `none`；后端验证 Tool 意图后执行，再把 `ToolResult` 给第二轮自然回答。拒绝任何 userId、URL、SQL、Shell 或非 allowlist 命令。`news_backend.py` 保留既有失败语义：executor、schema 或 Tool 失败只更新 job 为 failed 并返回可重试错误，绝不写 assistant message。

- [ ] **Step 4: 运行通过测试。**

  ```powershell
  python -m unittest tests.chickenbro_agent_test tests.news_backend_test.NewsBackendTest
  ```

  预期：不发出真实网络请求；已有 fixed-reply 和重试回归仍通过。

## Task 2：让普通职业咨询自动使用 Raider.IO 来源摘要

**Files:**
- Modify: `server/raiderio_payload.py` (`get_raiderio_payload` 旁新增 `build_raiderio_chickenbro_tool_result`)
- Modify: `server/chickenbro_agent.py`
- Modify: `server/news_backend.py`
- Modify: `tests/chickenbro_agent_test.py`
- Modify: `tests/news_backend_test.py`

**Interfaces:**

```python
def build_raiderio_chickenbro_tool_result(payload: dict, intent: AgentIntent) -> dict:
    # {'status', 'facts', 'evidence', 'limitations', 'nextActions'}
    ...
```

- [ ] **Step 1: 写失败测试。**

  ```python
  def test_raiderio_context_is_narrow_and_fresh(self):
      result = build_raiderio_chickenbro_tool_result(FRESH_PROTECTION_PAYLOAD, PROT_INTENT)
      self.assertEqual('verified', result['status'])
      self.assertEqual(['raiderio:warrior:protection'], result['evidenceRefs'])
      self.assertNotIn('unrelated-player@example', json.dumps(result))

  def test_stale_raiderio_never_becomes_current_rank_claim(self):
      result = build_raiderio_chickenbro_tool_result(STALE_PROTECTION_PAYLOAD, PROT_INTENT)
      self.assertEqual('stale', result['status'])
      self.assertEqual([], result['facts'])
  ```

- [ ] **Step 2: 运行以确认失败。**

  ```powershell
  python -m unittest tests.chickenbro_agent_test tests.news_backend_test.NewsBackendTest.test_chickenbro_raiderio_source_context
  ```

  预期：来源摘要函数不存在或未被 Agent 调用。

- [ ] **Step 3: 最小实现。** 在每个 owner-bound 消息处理里复用 `get_raiderio_payload(conn, allow_sync=True)`；只按既有同步预算刷新。匹配的 `specAggregates` / `communityTemplates` 被裁剪为专精、场景、track、赛季/版本、检查/失效时间、稳定来源引用与状态。新鲜事实进入第二轮 Agent；`stale`、`blocked`、无凭据或空结果只成为限制，不能产生“当前最强”、DPS 或天赋硬结论。

- [ ] **Step 4: 运行通过测试。**

  ```powershell
  python -m unittest tests.chickenbro_agent_test tests.news_backend_test.NewsBackendTest
  ```

  预期：防战等问题自动获得匹配的社区事实；没有来源时回答仍自然，但不声称查询成功。

## Task 3：把 WCL 变成可选个人分析入口

**Files:**
- Modify: `server/simulator_payload.py` (`build_wcl_log_evidence` 的受限适配)
- Modify: `server/chickenbro_agent.py`
- Modify: `server/news_backend.py`
- Modify: `tests/chickenbro_agent_test.py`
- Modify: `tests/news_backend_test.py`

**Interfaces:**

```python
def build_wcl_chickenbro_tool_result(request: dict, owner: dict) -> dict:
    # only a public report or owner-authorized access can return verified facts
    ...
```

- [ ] **Step 1: 写失败测试。**

  ```python
  def test_public_wcl_code_can_create_a_tool_result(self):
      result = build_wcl_chickenbro_tool_result({'message': WCL_URL}, OWNER_A)
      self.assertEqual('warcraftlogs', result['sourceKey'])

  def test_missing_wcl_report_keeps_general_chat_available(self):
      result = build_wcl_chickenbro_tool_result({'message': '帮我看看手法'}, OWNER_A)
      self.assertEqual('not_requested', result['status'])
  ```

- [ ] **Step 2: 运行以确认失败。**

  ```powershell
  python -m unittest tests.chickenbro_agent_test tests.news_backend_test.NewsBackendTest.test_chickenbro_optional_wcl
  ```

  预期：可选 WCL adapter 尚不存在。

- [ ] **Step 3: 最小实现。** 只在消息中提取到 WCL URL/code 时调用现有官方 API 适配。把 `missing_report`、无凭据、不可见性和权限失败转为限制/下一步，不伪造个人技能、伤害或死因结论。耗时深度分析继续创建/复用既有 PostgreSQL job，保留 owner、report、fight、actor 与 track 的确认边界。

- [ ] **Step 4: 运行通过测试。**

  ```powershell
  python -m unittest tests.chickenbro_agent_test tests.news_backend_test.NewsBackendTest
  ```

  预期：WCL 是增强入口而非所有聊天的前置条件。

## Task 4：沉淀可追溯来源记忆

**Files:**
- Create: `server/migrations/postgres/0024_chickenbro_source_memory.sql`
- Modify: `server/postgres_personal_store.py`
- Modify: `server/chickenbro_agent.py`
- Modify: `server/news_backend.py`
- Modify: `tests/postgres_schema_test.py`
- Modify: `tests/postgres_personal_store_test.py`
- Modify: `tests/database_adapter_test.py`

**Interfaces:**

```python
def upsert_chickenbro_source_memory(
    source_key: str, fact_key: str, snapshot: dict, expires_at: str, owner_id: str | None = None
) -> None: ...

def load_chickenbro_source_memory(intent: AgentIntent, owner_id: str | None = None) -> list[dict]: ...
```

- [ ] **Step 1: 写失败测试。**

  ```python
  def test_source_memory_replaces_same_fact_but_preserves_provenance(self):
      store.upsert_chickenbro_source_memory('raiderio', 'retail:warrior:protection', FRESH, EXPIRES)
      self.assertEqual(FRESH['checkedAt'], store.load_chickenbro_source_memory(PROT_INTENT)[0]['checkedAt'])

  def test_owner_wcl_memory_is_not_visible_to_another_owner(self):
      store.upsert_chickenbro_source_memory('warcraftlogs', 'report:abc', WCL, EXPIRES, owner_id='owner-a')
      self.assertEqual([], store.load_chickenbro_source_memory(WCL_INTENT, owner_id='owner-b'))
  ```

- [ ] **Step 2: 运行以确认失败。**

  ```powershell
  python -m unittest tests.postgres_schema_test tests.postgres_personal_store_test tests.database_adapter_test
  ```

  预期：migration 与 store 接口不存在。

- [ ] **Step 3: 最小实现。** 新表仅保存来源 key、事实 key、scope、JSON 摘要、checked/expires/status 与 timestamps；公共 Raider.IO 摘要没有 user data，WCL 摘要强制 owner。只从成功且可引用的 ToolResult 写入，拒绝 executor 自然语言、原始 WCL events、完整 prompt 与 token。过期摘要保留供限制说明，但不进入 verified facts。

- [ ] **Step 4: 运行通过测试。**

  ```powershell
  python -m unittest tests.postgres_schema_test tests.postgres_personal_store_test tests.database_adapter_test tests.chickenbro_agent_test
  ```

  预期：来源记忆可更新、可过期、可追溯且不跨 owner；它不是模型训练。

## Task 5：候选验证、人工验收与回滚

**Files:**
- Add: `artifacts/releases/2026-08-01-chickenbro-source-agent/requirements.json`
- Add: `artifacts/releases/2026-08-01-chickenbro-source-agent/verification.json`
- Add: `artifacts/releases/2026-08-01-chickenbro-source-agent/evidence.json`
- Modify: `docs/verification-matrix.md`（只在现有矩阵缺少该任务断言时）

- [ ] **Step 1: 本地 CR。** 核对 diff 没有固定回复、任意抓取、跨 owner 读取、密钥进入模型、全量缓存进入 prompt、Archon 未授权抓取、同步自动全量启动或未经证实数值。

- [ ] **Step 2: 运行目标验证。**

  ```powershell
  python -m unittest tests.chickenbro_agent_test tests.news_backend_test tests.postgres_schema_test tests.postgres_personal_store_test tests.database_adapter_test
  npm run typecheck
  git diff --check
  ```

  预期：全部通过；若本机 Node 不能启动前端 Vitest，记录环境阻断，不把未运行写成通过。

- [ ] **Step 3: 候选部署与 smoke。** 备份 `/opt/wow-mini-program/server/news_backend.py` 与新增 agent 文件，以本分支 SHA 部署，保持 `WOW_DEPLOY_START_ASYNC_SYNCS=0`，重启 `wow-backend`。确认 service active、部署 hash 匹配；以 guest 会话发送“防战现在天赋怎么点、属性怎么搭配、装备哪里获取？”，断言回答来自 Agent、包含实际来源/时间或明确来源限制、没有固定模板。再发送不带 WCL 的普通问题，确认不会被要求提交链接。记录回滚路径与 hash。

- [ ] **Step 4: 人工验收。** 给用户至多两条微信路径：普通职业咨询；可选公开 WCL 链接咨询。用户明确“我已测试通过”“可以收尾”或“合入吧”前，不合并、不推送、不删除分支。

## 回滚

候选 smoke 失败时恢复候选备份的后端/agent 文件并重启既有 `wow-backend`；来源记忆迁移只新增表，不改变会话/消息既有合同。关闭来源 Agent feature flag 后，队长回到现有自然聊天 executor；不启动异步同步，也不清除 Raider.IO 或已有个人数据。
