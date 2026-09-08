# Chickenbro-SimC Rebuild Phase 3 Formal Chat Implementation Plan

> 当前结论（2026-09-08）：本计划已交付的 1.0 实现范围获用户整体验收，状态为 `已完成`。下面保留各阶段当时的状态与证据；旧“待验收/未合入/阻塞”描述不代表当前结论，也不授权重放迁移、发布或清理。未实现设想及微信公开发布不自动完成。详见 [1.0 说明](../../releases/1.0.md)。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace prototype-only Chickenbro routes with one owner-scoped formal Chat API shared by Mini and Web sessions.

**Architecture:** The existing Chat domain, repository, native Codex adapter, and SSE serializer remain the core. The application becomes Principal-based, adds stable owner-scoped pagination and idempotent message replay, and is exposed through formal `/api/v2/chat/**` routes that accept either authenticated transport while applying CSRF to Cookie writes.

**Tech Stack:** Python 3, FastAPI, PostgreSQL, native Codex adapter, SSE, TypeScript domain guards and API client.

**Spec:** `docs/superpowers/specs/2026-09-02-chickenbro-simc-total-rebuild-design.md`

## Global Constraints

- Every conversation, message, and agent run query includes the authenticated `user_id`; cross-owner access returns the same not-found response as an absent object.
- User messages are append-only; assistant success is published only after assistant-message persistence succeeds.
- `Idempotency-Key` and `clientMessageId` make retried sends return the original run/message instead of invoking Codex twice.
- SSE sequence numbers are strictly increasing; reconnect uses the persisted run/messages rather than model replay.
- Native Codex failure, timeout, invalid output, or persistence failure produces an explicit failed AgentRun and public error; no ordinary LLM or template fallback is allowed.
- Raw Codex events, reasoning, credentials, internal user IDs, source credentials, and server paths are not returned to clients.
- Prototype routes remain physically present until Phase 6 but have no formal-client caller after this phase.

---

## File Structure

- Modify `server/app/chickenbro/{ports,application,repository,stream,codex_adapter}.py`: formal Principal application, pagination, idempotency, and replay.
- Create `server/app/api/routes/chat.py`: formal Chat transport.
- Modify `server/app/api/routes/__init__.py`, `server/app/api/dependencies.py`, `server/app/main.py`: register formal Chat application/router.
- Create `tests/app_chat_api_test.py`, `tests/app_chat_cross_client_test.py`: formal route and dual-session evidence.
- Modify `tests/app_chickenbro_{application,owner_isolation,stream,codex_adapter}_test.py`: rename/generalize prototype fixtures.
- Create `packages/domain/src/chat.ts`, `packages/domain/src/chat.test.ts`: public Chat contracts and guards.
- Create `packages/api-client/src/auth-context.ts`, `packages/api-client/src/auth-context.test.ts`: shared Mini/Web request-auth union.
- Create `packages/api-client/src/chat.ts`, `packages/api-client/src/chat.test.ts`: transport shared by Web and Mini.
- Modify `packages/domain/src/index.ts`, `packages/api-client/src/index.ts`, `packages/api-client/src/clients.ts`: export `ChatClient`.
- Create `artifacts/releases/2026-09-02-chickenbro-simc-chat/{requirement,evidence,manifest}.json`.

### Task 1: Principal-based Chat application and stable pagination

**Files:**
- Modify: `server/app/chickenbro/ports.py`
- Modify: `server/app/chickenbro/application.py`
- Modify: `server/app/chickenbro/repository.py`
- Modify: `tests/app_chickenbro_application_test.py`
- Modify: `tests/app_chickenbro_owner_isolation_test.py`

**Interfaces:**
- Produces: `ChatApplication.create_conversation(principal, title)`, `list_conversations(principal, cursor, limit) -> ConversationPage`, `load_conversation(principal, id) -> ConversationView`, and `stream_message(...) -> Iterable[ChatEvent]`.
- Cursor payload: base64url JSON `{"updatedAt":"<UTC ISO>","id":"<UUID>"}`; maximum limit 50, default 20.

- [ ] **Step 1: Write failing owner-scoped pagination tests**

```python
def test_conversation_page_is_stable_and_owner_scoped(self):
    first = app.list_conversations(owner_a, cursor=None, limit=2)
    second = app.list_conversations(owner_a, cursor=first.next_cursor, limit=2)
    self.assertEqual([row.id for row in first.items + second.items], expected_owner_a_ids)
    self.assertFalse(any(row.user_id == owner_b.user_id for row in first.items + second.items))

def test_invalid_cursor_fails_without_querying_repository(self):
    with self.assertRaisesRegex(ChatApplicationError, "INVALID_CURSOR"):
        app.list_conversations(owner_a, cursor="not-a-cursor", limit=20)
```

- [ ] **Step 2: Run and verify failure**

Run: `python3 -m unittest tests.app_chickenbro_application_test tests.app_chickenbro_owner_isolation_test -v`

Expected: FAIL because `ChatApplication` and list pagination do not exist.

- [ ] **Step 3: Generalize the application from PrototypePrincipal to Principal**

```python
@dataclass(frozen=True)
class ConversationPage:
    items: tuple[Conversation, ...]
    next_cursor: str | None

class ChatApplication:
    def list_conversations(self, principal: Principal, cursor: str | None, limit: int = 20) -> ConversationPage:
        bounded = min(max(int(limit), 1), 50)
        boundary = decode_conversation_cursor(cursor) if cursor else None
        rows = self._repository.list_conversations(principal.user_id, boundary, bounded + 1)
        items = tuple(rows[:bounded])
        return ConversationPage(items, encode_conversation_cursor(items[-1]) if len(rows) > bounded else None)
```

Retain `PrototypeChatApplication = ChatApplication` only as a temporary Phase-6 deletion alias if prototype tests still require it; no formal code may import the alias.

- [ ] **Step 4: Add repository keyset query**

Use `(updated_at, id) < (%s, %s)` with `ORDER BY updated_at DESC, id DESC LIMIT %s`, always preceded by `WHERE user_id = %s`. Add `list_messages(user_id, conversation_id)` ordered by `created_at, id`.

- [ ] **Step 5: Run focused tests and commit**

```bash
python3 -m unittest tests.app_chickenbro_application_test tests.app_chickenbro_owner_isolation_test -v
git add server/app/chickenbro tests/app_chickenbro_application_test.py tests/app_chickenbro_owner_isolation_test.py
git commit -m "feat: formalize owner-scoped Chickenbro application"
```

### Task 2: Idempotent Codex run and persistent SSE replay

**Files:**
- Modify: `server/app/chickenbro/application.py`
- Modify: `server/app/chickenbro/repository.py`
- Modify: `server/app/chickenbro/stream.py`
- Modify: `server/app/chickenbro/codex_adapter.py`
- Modify: `tests/app_chickenbro_application_test.py`
- Modify: `tests/app_chickenbro_stream_test.py`
- Modify: `tests/app_chickenbro_codex_adapter_test.py`

**Interfaces:**
- Produces: `repository.get_message_by_client_id(user_id, client_message_id)`, `get_run_for_user_message(user_id, message_id)`, and `replay_run(principal, run_id) -> Iterable[ChatEvent]`.

- [ ] **Step 1: Write failing retry and failure-terminal tests**

```python
def test_same_client_message_and_idempotency_key_invokes_codex_once(self):
    first = list(app.stream_message(owner, conversation_id, "hello", client_message_id="m1", idempotency_key="r1"))
    second = list(app.stream_message(owner, conversation_id, "hello", client_message_id="m1", idempotency_key="r1"))
    self.assertEqual(codex.calls, 1)
    self.assertEqual(second[-1].run_id, first[-1].run_id)

def test_assistant_persistence_failure_never_marks_run_succeeded(self):
    repository.fail_assistant_insert = True
    events = list(app.stream_message(owner, conversation_id, "hello", client_message_id="m2", idempotency_key="r2"))
    self.assertEqual(events[-1].event, "failed")
    self.assertEqual(repository.runs[-1].status.value, "failed")
```

- [ ] **Step 2: Run and verify failure**

Run: `python3 -m unittest tests.app_chickenbro_application_test tests.app_chickenbro_stream_test tests.app_chickenbro_codex_adapter_test -v`

- [ ] **Step 3: Implement persistence-first terminal events**

Insert the user message and streaming AgentRun in one transaction. Buffer bounded public deltas in memory, persist the assistant message, update the run to `succeeded`, then emit `completed`. On any error, update the run to `failed` with one of `CODEX_UNAVAILABLE`, `CODEX_TIMEOUT`, `CODEX_INVALID_OUTPUT`, or `CHAT_PERSISTENCE_FAILED`, and emit one public `failed` frame.

- [ ] **Step 4: Implement replay without re-running Codex**

For an existing succeeded run, emit `started` then one persisted assistant `completed`; for a failed run, emit `started` then `failed`; for a still-streaming run, return `CHAT_RUN_IN_PROGRESS`. Sequence starts at 1 and increases by exactly 1.

- [ ] **Step 5: Run and commit**

```bash
python3 -m unittest tests.app_chickenbro_application_test tests.app_chickenbro_stream_test tests.app_chickenbro_codex_adapter_test -v
git add server/app/chickenbro tests/app_chickenbro_application_test.py \
  tests/app_chickenbro_stream_test.py tests/app_chickenbro_codex_adapter_test.py
git commit -m "feat: make Chickenbro sends idempotent and replayable"
```

### Task 3: Formal Chat HTTP/SSE routes

**Files:**
- Create: `server/app/api/routes/chat.py`
- Modify: `server/app/api/routes/__init__.py`
- Modify: `server/app/api/dependencies.py`
- Modify: `server/app/main.py`
- Create: `tests/app_chat_api_test.py`
- Create: `tests/app_chat_cross_client_test.py`

**Interfaces:**
- Routes:
  - `GET /api/v2/chat/conversations?cursor=&limit=`
  - `POST /api/v2/chat/conversations`
  - `GET /api/v2/chat/conversations/{conversation_id}`
  - `POST /api/v2/chat/conversations/{conversation_id}/messages/stream`
- All response objects omit `user_id`; writes depend on `require_mutating_principal`.

- [ ] **Step 1: Write failing route matrix tests**

```python
def test_conversation_created_by_mini_is_visible_to_web_same_user(self):
    created = client.post("/api/v2/chat/conversations", headers=mini_headers, json={"title": "跨端"})
    listed = client.get("/api/v2/chat/conversations", headers=web_headers, cookies=web_cookies)
    self.assertEqual(created.status_code, 201)
    self.assertIn(created.json()["id"], [row["id"] for row in listed.json()["items"]])

def test_other_user_gets_not_found(self):
    response = client.get(f"/api/v2/chat/conversations/{owner_a_id}", headers=owner_b_headers)
    self.assertEqual(response.status_code, 404)
```

- [ ] **Step 2: Run and verify 404/missing-router failures**

Run: `python3 -m unittest tests.app_chat_api_test tests.app_chat_cross_client_test -v`

- [ ] **Step 3: Implement bounded public payloads**

```python
@router.get("/api/v2/chat/conversations")
def list_conversations(
    principal: Annotated[Principal, Depends(require_principal)],
    application: Annotated[ChatApplication, Depends(chat_application)],
    cursor: str | None = None,
    limit: int = 20,
) -> dict[str, object]:
    page = application.list_conversations(principal, cursor, limit)
    return {"items": [conversation_payload(row) for row in page.items], "nextCursor": page.next_cursor}
```

Use `StreamingResponse(..., media_type="text/event-stream")`, `Cache-Control: no-store`, `X-Accel-Buffering: no`, and serialized `started/delta/completed/failed` events only.

- [ ] **Step 4: Verify both transports and CSRF**

Tests must cover Mini Bearer success without Cookie, Web Cookie read success, Web Cookie write rejection without Origin/CSRF, same-user cross-client history, and cross-user isolation.

- [ ] **Step 5: Run and commit**

```bash
python3 -m unittest tests.app_chat_api_test tests.app_chat_cross_client_test \
  tests.app_chickenbro_application_test tests.app_chickenbro_owner_isolation_test \
  tests.app_chickenbro_stream_test tests.app_chickenbro_codex_adapter_test -v
git add server/app/api server/app/main.py tests/app_chat_api_test.py tests/app_chat_cross_client_test.py
git commit -m "feat: expose formal cross-client Chickenbro API"
```

### Task 4: Typed shared Chat client

**Files:**
- Create: `packages/domain/src/chat.ts`
- Create: `packages/domain/src/chat.test.ts`
- Create: `packages/api-client/src/auth-context.ts`
- Create: `packages/api-client/src/auth-context.test.ts`
- Create: `packages/api-client/src/chat.ts`
- Create: `packages/api-client/src/chat.test.ts`
- Modify: `packages/domain/src/index.ts`
- Modify: `packages/api-client/src/index.ts`
- Modify: `packages/api-client/src/clients.ts`

**Interfaces:**
- Produces: `ConversationSummary`, `ConversationDetail`, `ChatMessage`, `ChatEventEnvelope`, `ClientAuthContext = {kind:'mini', accessToken:string}|{kind:'web', csrfToken:string}`, and `ChatClient` with `list`, `create`, `get`, and `streamMessage`.

- [ ] **Step 1: Write failing guards and transport tests**

```ts
expect(isConversationPage({ items: [{ id, title: '跨端', status: 'active', updatedAt }], nextCursor: null })).toBe(true)
expect(isConversationPage({ items: [{ id, userId: id }], nextCursor: null })).toBe(false)

await client.create({ title: '跨端' }, { auth: { kind: 'mini', accessToken: 'mini' } })
expect(transport.last.path).toBe('/api/v2/chat/conversations')
```

- [ ] **Step 2: Run and verify missing-module failure**

Run: `npm run test:taro -- packages/domain/src/chat.test.ts packages/api-client/src/auth-context.test.ts packages/api-client/src/chat.test.ts`

- [ ] **Step 3: Implement exact validators and auth-neutral client**

The caller passes `ClientAuthContext`: Mini injects Bearer with credentials omitted; Web includes Cookie and CSRF header. The Chat client never reads or converts one transport into the other. Phase 4 reuses this exact type and Phase 5 supplies it from concrete session stores.

- [ ] **Step 4: Run type and unit tests**

```bash
npm run test:taro -- packages/domain/src/chat.test.ts packages/api-client/src/auth-context.test.ts packages/api-client/src/chat.test.ts
npm run typecheck
```

- [ ] **Step 5: Commit**

```bash
git add packages/domain/src/chat.ts packages/domain/src/chat.test.ts packages/domain/src/index.ts \
  packages/api-client/src/auth-context.ts packages/api-client/src/auth-context.test.ts \
  packages/api-client/src/chat.ts packages/api-client/src/chat.test.ts \
  packages/api-client/src/index.ts packages/api-client/src/clients.ts
git commit -m "feat: add typed Chickenbro client"
```

### Task 5: Candidate smoke and Strict Chat evidence

**Files:**
- Create: `artifacts/releases/2026-09-02-chickenbro-simc-chat/requirement.json`
- Create: `artifacts/releases/2026-09-02-chickenbro-simc-chat/evidence.json`
- Create: `artifacts/releases/2026-09-02-chickenbro-simc-chat/manifest.json`
- Modify: `docs/project-state.json`

- [ ] **Step 1: Create a Strict requirement with no production-cutover authority**

Require owner-scoped DB integration, two-auth-session same-user history, second-user isolation, idempotency, SSE order/replay, Codex failure truth, CSRF, typed client, candidate identity, rollback, and public-payload redaction.

- [ ] **Step 2: Run the complete local Chat matrix**

```bash
python3 -m unittest tests.app_chat_api_test tests.app_chat_cross_client_test \
  tests.app_chickenbro_application_test tests.app_chickenbro_owner_isolation_test \
  tests.app_chickenbro_stream_test tests.app_chickenbro_codex_adapter_test -v
npm run test:taro -- packages/domain/src/chat.test.ts packages/api-client/src/auth-context.test.ts packages/api-client/src/chat.test.ts
npm run typecheck
```

- [ ] **Step 3: Deploy and smoke only the isolated candidate**

Record branch/commit, deployed-file hashes, clean candidate DB identity, API/Worker identities, Mini and Web test-session owner equivalence, conversation create/list/get/stream, Codex configured/unavailable behavior, and rollback. Do not route public production traffic to the candidate.

- [ ] **Step 4: Review and seal evidence**

Local CR must reject any prototype caller from the formal client, unscoped query, model fallback, raw internal field, or successful run without persisted assistant message. Write/check the Harness packet and commit.

```bash
git add artifacts/releases/2026-09-02-chickenbro-simc-chat docs/project-state.json
git commit -m "test: seal formal Chickenbro evidence"
```

Phase 3 is complete when the formal API is candidate-verified through both session kinds and production remains unchanged.
