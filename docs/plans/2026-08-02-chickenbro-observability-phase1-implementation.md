# Chickenbro Observability Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为现有炸鸡队长来源 Agent 增加 owner-bound 结构化 Trace、确定性 Outcome Signal、不可反查用户的脱敏投影和离线 Eval 回放器，在不改变回答、Tool 选择或前端合同的前提下建立能力演化的可观测基线。

**Architecture:** 新的 `server/chickenbro_observability.py` 只从现有 bounded context、ToolResult、Agent terminal result 和错误中选择允许字段，生成 `chickenbro-agent-trace-v1`，再生成不含 owner、消息、证据引用或自由文本的 `chickenbro-trace-projection-v1`。PostgreSQL 与 SQLite 测试适配器只持久化 owner-bound Trace；跨用户投影首阶段不落库。新的离线 Eval 运行器只回放仓库内脱敏 fixture，不调用网络、模型、生产数据库或 Toolsmith。

**Tech Stack:** Python 3 标准库、`unittest`、现有 `wow-backend`、PostgreSQL personal store、SQLite 测试适配器、JSON fixture、Project Harness。

状态：`已完成`（Phase 1 已由合并提交 `c1d5c52` 集成；最终源码提交 `22db29a` 通过空 SQLite 完整 Harness，已验证 `main`/`origin/main` 对齐并清理任务 worktree 与分支）

当前证据：[Phase 1 release packet](../../artifacts/releases/2026-08-02-chickenbro-observability-phase1/evidence.json)

设计依据：[能力演化控制面设计](2026-08-02-chickenbro-capability-evolution-design.md)

## Global Constraints

- 本计划只实现设计 Phase 1；不得加入动态 Tool Registry、CapabilityGap 持久化/聚类、Toolsmith、shadow、canary 或自动 promotion。
- 在线 Agent 继续使用当前固定 allowlist 与现有回答路径；不得修改 prompt、模型 schema、Tool 选择语义、消息 API 或前端 UI。
- 原始聊天、完整 prompt、完整 bounded context、模型 chain-of-thought、回答正文、角色名、服务器名、WCL report code/URL、SimC stdout、密钥和 token 不得进入 Trace 或脱敏投影。
- owner、session、message 和 job 身份只作为 `app.chickenbro_agent_traces` 的 owner-bound 关系列保存，不进入 `payload_json`，也不得进入脱敏投影。
- `explicit_correction` 只允许来自未来经过 owner 校验的结构化反馈事件；Phase 1 不通过自然语言启发式自动生成该信号。
- Trace 写入失败不得改变已验证回答、不得补写固定回复，也不得覆盖原始 Agent 错误；本次运行因没有 Trace 自动排除在 Eval 输入之外。
- PostgreSQL 是唯一生产持久层；SQLite 变更只用于当前测试与兼容路径，不授予生产运行权。
- 不增加依赖。所有新模块只使用 Python 标准库与现有 store/helper。
- 使用隔离 worktree 和 `codex/chickenbro-observability-phase1` 分支执行，保留当前主工作区五个未提交 UI 文件，不把它们带入本任务提交。
- 候选部署保持 `WOW_DEPLOY_START_ASYNC_SYNCS=0`；数据库迁移先备份、后应用；代码回滚不删除新增 Trace 表。

---

## File Responsibility Map

| 文件 | 单一职责 |
| --- | --- |
| `server/chickenbro_observability.py` | Trace、Outcome Signal、脱敏投影的纯函数合同；不做 I/O |
| `server/migrations/postgres/0024_chickenbro_agent_observability.sql` | 新增 owner-bound Trace 表、索引和 migration identity |
| `server/postgres_personal_store.py` | PostgreSQL Trace 写入与 owner-bound 单条读取 |
| `server/news_backend.py` | 在现有 Agent 成功/失败终点采集并尽力写入 Trace；SQLite 测试兼容表与写入 |
| `server/chickenbro_eval.py` | 验证 Eval Case、生成 Trace/投影并执行确定性断言 |
| `scripts/evaluate_chickenbro_traces.py` | 无网络 CLI，读取 fixture、输出 JSON 汇总并以退出码表示通过/失败 |
| `tests/fixtures/chickenbro_trace_eval_cases.json` | 未包含真实聊天或 owner 身份的固定回放样本 |
| `tests/chickenbro_observability_test.py` | 纯函数、字段 allowlist、Outcome 和脱敏泄漏回归 |
| `tests/chickenbro_eval_test.py` | Eval Case schema、通过/失败汇总和 CLI 回归 |
| `tests/postgres_schema_test.py` | 0024 migration 的表、FK、唯一性、索引和 migration 记录 |
| `tests/postgres_personal_store_test.py` | PostgreSQL Trace 写入/读取的 owner 约束与 JSON 参数 |
| `tests/database_adapter_test.py` | `news_backend` 对 PostgreSQL store 的 Trace 路由合同 |
| `tests/news_backend_test.py` | SQLite 端到端成功、失败、重试与 Trace 写入失败不影响回答 |
| `docs/backend-owner-map.json` | 为后端热点登记 observability owner 与不得改变的边界 |
| `docs/project-owner-map.json` | 把新模块、迁移、fixture 和测试接入 Chickenbro 事实 owner |
| `artifacts/releases/2026-08-02-chickenbro-observability-phase1/*` | 本阶段 requirement、manifest、验证、候选部署和回滚证据 |

## Contract Definitions

`server/chickenbro_observability.py` 对外只暴露以下接口：

```text
TRACE_SCHEMA_REVISION = "chickenbro-agent-trace-v1"
PROJECTION_SCHEMA_REVISION = "chickenbro-trace-projection-v1"
RUNTIME_VERSION = "chickenbro-fixed-allowlist-v1"

build_chickenbro_agent_trace(*, bounded_context: dict, agent_result: dict | None,
                             error: str, latency_ms: int, created_at: str) -> dict
deidentify_chickenbro_agent_trace(trace: dict) -> dict
validate_chickenbro_agent_trace(trace: dict) -> dict
```

Trace payload 固定为：

```json
{
  "schemaRevision": "chickenbro-agent-trace-v1",
  "runtimeVersion": "chickenbro-fixed-allowlist-v1",
  "selectionMode": "fixed_allowlist",
  "requestScope": {
    "topicStatus": "in_scope",
    "productPhase": "retail",
    "region": "cn",
    "classKey": "deathknight",
    "specKey": "frost",
    "scenarioKey": "mythic_plus"
  },
  "discoveredCapabilityIds": ["source:raiderio:v1"],
  "selectedCapabilityIds": ["source:raiderio:v1"],
  "toolStatuses": [
    {
      "capabilityId": "source:raiderio:v1",
      "status": "source_reference",
      "freshnessState": "fresh",
      "evidenceCount": 1
    }
  ],
  "evidenceRefs": ["raiderio:deathknight:frost:mythic_plus"],
  "answerStatus": "succeeded",
  "validationStatus": "passed",
  "outcomeSignals": [{"code": "answer_succeeded", "severity": "info"}],
  "latencyMs": 1200,
  "boundedCost": {"status": "not_available"},
  "createdAt": "2026-08-02T00:00:00+00:00"
}
```

Trace payload 本身不得包含 owner、session、message、job 或 trace 身份；这些身份只存在于 owner-bound 数据库关系列。脱敏投影进一步移除 `evidenceRefs`、`createdAt` 和任何自由文本，只保留 request scope 枚举、能力 ID、Tool 状态、信号代码、answer/validation 状态与 latency bucket。

---

### Task 1: Add the pure Trace, Outcome, and de-identification contract

**Files:**
- Create: `server/chickenbro_observability.py`
- Create: `tests/chickenbro_observability_test.py`

**Interfaces:**
- Consumes: existing `bounded_context["requestContext"]`, `bounded_context["topic"]`, `bounded_context["sourceEvidence"]`, `agent_result["validation"]`, and terminal error text.
- Produces: `build_chickenbro_agent_trace`, `validate_chickenbro_agent_trace`, and `deidentify_chickenbro_agent_trace` exactly as defined above.

- [ ] **Step 1: Write failing tests for the minimal successful trace**

```python
def test_builds_structured_trace_without_copying_chat_or_answer_text(self):
    trace = build_chickenbro_agent_trace(
        bounded_context={
            "message": "SECRET RAW USER MESSAGE",
            "conversationHistory": [{"content": "SECRET HISTORY"}],
            "topic": {"status": "in_scope", "reason": "wow_topic"},
            "requestContext": {
                "productPhase": "retail", "region": "cn",
                "classKey": "deathknight", "specKey": "frost",
                "scenarioKey": "mythic_plus",
            },
            "sourceEvidence": [{
                "sourceKey": "raiderio", "status": "source_reference",
                "evidenceRefs": ["raiderio:deathknight:frost:mythic_plus"],
                "facts": [{"summary": "SECRET SOURCE FACT"}],
            }],
        },
        agent_result={
            "answer": {"answer": "SECRET ASSISTANT ANSWER"},
            "validation": {"status": "passed"},
            "model": {"status": "succeeded"},
        },
        error="",
        latency_ms=1200,
        created_at="2026-08-02T00:00:00+00:00",
    )
    encoded = json.dumps(trace, ensure_ascii=False)
    self.assertEqual("succeeded", trace["answerStatus"])
    self.assertEqual(["source:raiderio:v1"], trace["selectedCapabilityIds"])
    self.assertNotIn("SECRET RAW USER MESSAGE", encoded)
    self.assertNotIn("SECRET HISTORY", encoded)
    self.assertNotIn("SECRET SOURCE FACT", encoded)
    self.assertNotIn("SECRET ASSISTANT ANSWER", encoded)
```

- [ ] **Step 2: Run the focused test and verify the module is missing**

Run:

```powershell
python -m unittest tests.chickenbro_observability_test
```

Expected: `ModuleNotFoundError: No module named 'server.chickenbro_observability'`.

- [ ] **Step 3: Implement allowlisted normalization and stable capability IDs**

```python
import copy
import re
from datetime import datetime

TRACE_SCHEMA_REVISION = "chickenbro-agent-trace-v1"
PROJECTION_SCHEMA_REVISION = "chickenbro-trace-projection-v1"
RUNTIME_VERSION = "chickenbro-fixed-allowlist-v1"

def _text(value, limit=160):
    return str(value or "").strip()[:limit]

def _capability_id(source_key):
    key = _text(source_key, 48).lower()
    return f"source:{key}:v1" if key in {"raiderio", "warcraftlogs"} else ""

SAFE_EVIDENCE_REF_PATTERNS = (
    re.compile(r"^profile\.[a-z0-9_.-]{1,96}$"),
    re.compile(r"^simc\.[a-z0-9_.-]{1,96}$"),
    re.compile(r"^wcl\.[a-z0-9_.-]{1,96}$"),
    re.compile(r"^raiderio:[a-z0-9_-]{1,48}:[a-z0-9_-]{1,48}:[a-z0-9_-]{1,48}$"),
)

def _safe_evidence_ref(value):
    ref = _text(value, 160).lower()
    return ref if any(pattern.fullmatch(ref) for pattern in SAFE_EVIDENCE_REF_PATTERNS) else ""

def _request_scope(bounded_context):
    context = bounded_context if isinstance(bounded_context, dict) else {}
    request = context.get("requestContext") if isinstance(context.get("requestContext"), dict) else {}
    topic = context.get("topic") if isinstance(context.get("topic"), dict) else {}
    return {
        "topicStatus": _text(topic.get("status"), 32),
        "productPhase": _text(request.get("productPhase"), 32),
        "region": _text(request.get("region"), 16),
        "classKey": _text(request.get("classKey"), 48),
        "specKey": _text(request.get("specKey"), 48),
        "scenarioKey": _text(request.get("scenarioKey"), 48),
    }

def build_chickenbro_agent_trace(
    *, bounded_context, agent_result, error, latency_ms, created_at
):
    context = bounded_context if isinstance(bounded_context, dict) else {}
    result = agent_result if isinstance(agent_result, dict) else {}
    validation = result.get("validation") if isinstance(result.get("validation"), dict) else {}
    model = result.get("model") if isinstance(result.get("model"), dict) else {}
    validation_status = _text(validation.get("status"), 32) or "failed"
    model_status = _text(model.get("status"), 32) or "failed"
    answer_status = "succeeded" if validation_status == "passed" else (
        model_status if model_status in {"failed", "timed_out", "skipped"} else "failed"
    )
    source_rows = [
        row for row in context.get("sourceEvidence") or [] if isinstance(row, dict)
    ][:8]
    tool_statuses = []
    evidence_refs = []
    for row in source_rows:
        capability_id = _capability_id(row.get("sourceKey"))
        if not capability_id:
            continue
        status = _text(row.get("status"), 32).lower() or "unknown"
        safe_refs = [
            ref for ref in (_safe_evidence_ref(value) for value in row.get("evidenceRefs") or []) if ref
        ]
        evidence_refs.extend(ref for ref in safe_refs if ref not in evidence_refs)
        freshness = (
            "fresh" if status in {"verified", "source_reference"}
            else "stale" if status == "stale"
            else "unavailable" if status in {"blocked", "failed"}
            else "unknown"
        )
        tool_statuses.append({
            "capabilityId": capability_id,
            "status": status,
            "freshnessState": freshness,
            "evidenceCount": len(safe_refs),
        })
    signal_codes = []
    if answer_status == "succeeded":
        signal_codes.append(("answer_succeeded", "info"))
    else:
        signal_codes.append(("model_failed", "error"))
    if any(row["status"] in {"blocked", "failed"} for row in tool_statuses):
        signal_codes.append(("tool_failed", "error"))
    if any(
        row["status"] in {"stale", "blocked", "failed"} or row["evidenceCount"] == 0
        for row in tool_statuses
    ):
        signal_codes.append(("evidence_missing", "warning"))
    normalized_error = _text(error, 240).lower()
    if any(token in normalized_error for token in ("invalid model json", "schema", "model_output_invalid")):
        signal_codes.append(("schema_invalid", "error"))
    if any(token in normalized_error for token in ("unknown evidence ref", "unapproved number")):
        signal_codes.append(("verification_conflict", "error"))
    seen = set()
    outcome_signals = []
    for code, severity in signal_codes:
        if code not in seen:
            outcome_signals.append({"code": code, "severity": severity})
            seen.add(code)
    capability_ids = sorted({row["capabilityId"] for row in tool_statuses})
    return validate_chickenbro_agent_trace({
        "schemaRevision": TRACE_SCHEMA_REVISION,
        "runtimeVersion": RUNTIME_VERSION,
        "selectionMode": "fixed_allowlist",
        "requestScope": _request_scope(context),
        "discoveredCapabilityIds": capability_ids,
        "selectedCapabilityIds": capability_ids,
        "toolStatuses": tool_statuses,
        "evidenceRefs": evidence_refs,
        "answerStatus": answer_status,
        "validationStatus": validation_status,
        "outcomeSignals": outcome_signals,
        "latencyMs": max(0, int(latency_ms or 0)),
        "boundedCost": {"status": "not_available"},
        "createdAt": _text(created_at, 80),
    })
```

Construct only this fresh dictionary. Never copy `bounded_context`, `agent_result`, Tool facts, limitations, model content, or error text into the return value.
Only references accepted by `_safe_evidence_ref` may enter the owner-bound `evidenceRefs`; URLs, report codes, task/template IDs and unknown reference shapes are silently omitted from Trace and remain available only in their existing owner-bound evidence owner.

- [ ] **Step 4: Add failing tests for deterministic Outcome Signal mapping**

```python
def test_maps_tool_and_validation_failures_to_bounded_signal_codes(self):
    blocked = build_chickenbro_agent_trace(
        bounded_context={
            "message": "untrusted user text",
            "topic": {"status": "in_scope"},
            "requestContext": {
                "productPhase": "retail", "region": "cn",
                "classKey": "deathknight", "specKey": "frost",
                "scenarioKey": "mythic_plus",
            },
            "sourceEvidence": [
                {"sourceKey": "raiderio", "status": "blocked", "evidenceRefs": []}
            ],
        },
        agent_result={"validation": {"status": "failed"}, "model": {"status": "failed"}},
        error="model_output_invalid: unknown evidence ref",
        latency_ms=250,
        created_at="2026-08-02T00:00:00+00:00",
    )
    codes = {item["code"] for item in blocked["outcomeSignals"]}
    self.assertIn("tool_failed", codes)
    self.assertIn("evidence_missing", codes)
    self.assertIn("schema_invalid", codes)
    self.assertIn("verification_conflict", codes)

def test_does_not_infer_explicit_correction_from_user_text(self):
    trace = build_chickenbro_agent_trace(
        bounded_context={
            "message": "不对，现在明确是 12.0.7",
            "topic": {"status": "in_scope"},
            "requestContext": {
                "productPhase": "retail", "region": "cn",
                "classKey": "", "specKey": "", "scenarioKey": "",
            },
            "sourceEvidence": [],
        },
        agent_result={"validation": {"status": "passed"}, "model": {"status": "succeeded"}},
        error="",
        latency_ms=250,
        created_at="2026-08-02T00:00:00+00:00",
    )
    self.assertNotIn("explicit_correction", {item["code"] for item in trace["outcomeSignals"]})
```

Signal mapping is exact:

```python
answer_succeeded       # validated terminal answer
model_failed           # terminal model skipped/failed/timed_out or raised error
tool_failed            # ToolResult status is failed or blocked
evidence_missing       # selected Tool has stale/blocked/failed status or zero evidence
schema_invalid         # parse/schema/model_output_invalid failure
verification_conflict  # unknown evidence ref or unapproved number rejection
```

- [ ] **Step 5: Implement validation and de-identification**

```python
TRACE_KEYS = {
    "schemaRevision", "runtimeVersion", "selectionMode", "requestScope",
    "discoveredCapabilityIds", "selectedCapabilityIds", "toolStatuses",
    "evidenceRefs", "answerStatus", "validationStatus", "outcomeSignals",
    "latencyMs", "boundedCost", "createdAt",
}
REQUEST_SCOPE_KEYS = {
    "topicStatus", "productPhase", "region", "classKey", "specKey", "scenarioKey",
}
SIGNAL_CODES = {
    "answer_succeeded", "model_failed", "tool_failed", "evidence_missing",
    "schema_invalid", "verification_conflict", "explicit_correction",
}

def validate_chickenbro_agent_trace(trace):
    if not isinstance(trace, dict) or set(trace) != TRACE_KEYS:
        raise ValueError("invalid chickenbro trace keys")
    if trace["schemaRevision"] != TRACE_SCHEMA_REVISION:
        raise ValueError("invalid chickenbro trace schema revision")
    if trace["runtimeVersion"] != RUNTIME_VERSION or trace["selectionMode"] != "fixed_allowlist":
        raise ValueError("invalid chickenbro trace runtime identity")
    if not isinstance(trace["requestScope"], dict) or set(trace["requestScope"]) != REQUEST_SCOPE_KEYS:
        raise ValueError("invalid chickenbro trace request scope")
    if trace["answerStatus"] not in {"succeeded", "failed", "timed_out", "skipped"}:
        raise ValueError("invalid chickenbro trace answer status")
    if trace["validationStatus"] not in {"passed", "failed"}:
        raise ValueError("invalid chickenbro trace validation status")
    if not isinstance(trace["latencyMs"], int) or trace["latencyMs"] < 0:
        raise ValueError("invalid chickenbro trace latency")
    datetime.fromisoformat(str(trace["createdAt"]).replace("Z", "+00:00"))
    for key in ("discoveredCapabilityIds", "selectedCapabilityIds"):
        if not isinstance(trace[key], list) or any(
            not str(value).startswith("source:") for value in trace[key]
        ):
            raise ValueError(f"invalid chickenbro trace {key}")
    if not isinstance(trace["evidenceRefs"], list) or any(
        not _safe_evidence_ref(value) for value in trace["evidenceRefs"]
    ):
        raise ValueError("invalid chickenbro trace evidence refs")
    if not isinstance(trace["toolStatuses"], list):
        raise ValueError("invalid chickenbro trace tool statuses")
    for row in trace["toolStatuses"]:
        if not isinstance(row, dict) or set(row) != {
            "capabilityId", "status", "freshnessState", "evidenceCount",
        }:
            raise ValueError("invalid chickenbro trace tool status")
        if row["capabilityId"] not in trace["selectedCapabilityIds"]:
            raise ValueError("unselected chickenbro trace capability")
        if row["freshnessState"] not in {"fresh", "stale", "unavailable", "unknown"}:
            raise ValueError("invalid chickenbro trace freshness state")
        if not isinstance(row["evidenceCount"], int) or row["evidenceCount"] < 0:
            raise ValueError("invalid chickenbro trace evidence count")
    if not isinstance(trace["outcomeSignals"], list):
        raise ValueError("invalid chickenbro trace outcome signals")
    for signal in trace["outcomeSignals"]:
        if not isinstance(signal, dict) or set(signal) != {"code", "severity"}:
            raise ValueError("invalid chickenbro trace outcome signal")
        if signal["code"] not in SIGNAL_CODES or signal["severity"] not in {"info", "warning", "error"}:
            raise ValueError("unknown chickenbro trace outcome signal")
    if trace["boundedCost"] != {"status": "not_available"}:
        raise ValueError("invalid chickenbro trace cost state")
    return copy.deepcopy(trace)

def deidentify_chickenbro_agent_trace(trace):
    validated = validate_chickenbro_agent_trace(trace)
    latency = int(validated["latencyMs"])
    bucket = "le_1s" if latency <= 1000 else "le_5s" if latency <= 5000 else "le_15s" if latency <= 15000 else "gt_15s"
    return {
        "schemaRevision": PROJECTION_SCHEMA_REVISION,
        "problemSignature": ":".join([
            validated["requestScope"]["topicStatus"],
            validated["requestScope"]["productPhase"],
            validated["requestScope"]["region"],
            validated["requestScope"]["classKey"],
            validated["requestScope"]["specKey"],
            validated["requestScope"]["scenarioKey"],
            ",".join(sorted(item["code"] for item in validated["outcomeSignals"])),
        ]),
        "requestScope": dict(validated["requestScope"]),
        "selectionMode": validated["selectionMode"],
        "selectedCapabilityIds": list(validated["selectedCapabilityIds"]),
        "toolStatuses": [dict(item) for item in validated["toolStatuses"]],
        "answerStatus": validated["answerStatus"],
        "validationStatus": validated["validationStatus"],
        "outcomeSignals": [dict(item) for item in validated["outcomeSignals"]],
        "latencyBucket": bucket,
        "costStatus": validated["boundedCost"]["status"],
    }
```

`validate_chickenbro_agent_trace` must reject unknown top-level fields, invalid schema revision, invalid answer status, negative latency, unknown capability prefixes, free-text signal fields, and non-list Tool/evidence/signal collections. It returns a normalized copy; it never mutates the input.

- [ ] **Step 6: Run the pure contract tests**

Run:

```powershell
python -m unittest tests.chickenbro_observability_test
```

Expected: all tests pass; the Trace payload contains no owner/session/message/job/trace identity, and the serialized projection contains none of `evidenceRefs`, `createdAt`, raw message, answer, report code, character name, realm, URL, token or Tool facts.

- [ ] **Step 7: Commit the pure contract**

```powershell
git add server/chickenbro_observability.py tests/chickenbro_observability_test.py
git commit -m "feat(chickenbro): define bounded agent trace contract"
```

---

### Task 2: Persist owner-bound Trace records in PostgreSQL and the SQLite test adapter

**Files:**
- Create: `server/migrations/postgres/0024_chickenbro_agent_observability.sql`
- Modify: `server/postgres_personal_store.py:734-944`
- Modify: `server/news_backend.py:938-1005`
- Modify: `tests/postgres_schema_test.py:1-210`
- Modify: `tests/postgres_personal_store_test.py:287-396`

**Interfaces:**
- Consumes: a validated `chickenbro-agent-trace-v1` dictionary from Task 1.
- Produces: `PostgresPersonalStore.insert_chickenbro_agent_trace`, `PostgresPersonalStore.get_chickenbro_agent_trace`, and equivalent SQLite helpers.

- [ ] **Step 1: Write failing PostgreSQL migration assertions**

Add `CHICKENBRO_AGENT_OBSERVABILITY` to `tests/postgres_schema_test.py` and assert:

```python
def test_chickenbro_agent_observability_migration_is_owner_bound_and_idempotent(self):
    normalized = " ".join(self.chickenbro_agent_observability_sql.split())
    self.assertIn("CREATE TABLE IF NOT EXISTS app.chickenbro_agent_traces", normalized)
    self.assertIn("user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE", normalized)
    self.assertIn("session_id uuid NOT NULL REFERENCES app.chickenbro_sessions(id) ON DELETE CASCADE", normalized)
    self.assertIn("user_message_id uuid NOT NULL REFERENCES app.chickenbro_messages(id) ON DELETE CASCADE", normalized)
    self.assertIn("agent_job_id uuid NOT NULL REFERENCES app.agent_jobs(id) ON DELETE CASCADE", normalized)
    self.assertIn("UNIQUE (agent_job_id)", normalized)
    self.assertIn("payload_json jsonb NOT NULL", normalized)
    self.assertIn("0024_chickenbro_agent_observability", normalized)
```

- [ ] **Step 2: Run the schema test and verify the migration is missing**

Run:

```powershell
python -m unittest tests.postgres_schema_test.PostgresSchemaTest.test_chickenbro_agent_observability_migration_is_owner_bound_and_idempotent
```

Expected: failure because `0024_chickenbro_agent_observability.sql` does not exist.

- [ ] **Step 3: Create the additive migration**

```sql
CREATE TABLE IF NOT EXISTS app.chickenbro_agent_traces (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    session_id uuid NOT NULL REFERENCES app.chickenbro_sessions(id) ON DELETE CASCADE,
    user_message_id uuid NOT NULL REFERENCES app.chickenbro_messages(id) ON DELETE CASCADE,
    agent_job_id uuid NOT NULL REFERENCES app.agent_jobs(id) ON DELETE CASCADE,
    schema_revision text NOT NULL,
    runtime_version text NOT NULL,
    answer_status text NOT NULL,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (agent_job_id)
);

CREATE INDEX IF NOT EXISTS idx_chickenbro_agent_traces_owner_created
ON app.chickenbro_agent_traces (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chickenbro_agent_traces_session_created
ON app.chickenbro_agent_traces (session_id, created_at);

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0024_chickenbro_agent_observability',
    'Add owner-bound Chickenbro agent traces for bounded observability'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();
```

Do not add a cross-user projection, CapabilityGap, Registry, Eval result or Tool candidate table.

- [ ] **Step 4: Write failing personal-store tests**

```python
trace_payload = {
    "schemaRevision": "chickenbro-agent-trace-v1",
    "runtimeVersion": "chickenbro-fixed-allowlist-v1",
    "selectionMode": "fixed_allowlist",
    "requestScope": {
        "topicStatus": "in_scope", "productPhase": "retail", "region": "cn",
        "classKey": "mage", "specKey": "arcane", "scenarioKey": "mythic_plus",
    },
    "discoveredCapabilityIds": [], "selectedCapabilityIds": [],
    "toolStatuses": [], "evidenceRefs": [],
    "answerStatus": "succeeded", "validationStatus": "passed",
    "outcomeSignals": [{"code": "answer_succeeded", "severity": "info"}],
    "latencyMs": 500, "boundedCost": {"status": "not_available"},
    "createdAt": "2026-08-02T00:00:02+00:00",
}
trace_id = store.insert_chickenbro_agent_trace(
    "user-pg-1",
    session_id,
    message_id,
    job_id,
    trace_payload,
    "2026-08-02T00:00:02+00:00",
)
trace = store.get_chickenbro_agent_trace("user-pg-1", job_id)

self.assertTrue(trace_id)
self.assertEqual("chickenbro-agent-trace-v1", trace["payload"]["schemaRevision"])
self.assertNotIn("user-pg-1", json.dumps(trace["payload"]))
self.assertNotIn("Answer text", json.dumps(trace["payload"]))
self.assertNotIn("How should Arcane play?", json.dumps(trace["payload"]))
self.assertIn("WHERE user_id = %s AND agent_job_id = %s", sql)
self.assertNotIn("SELECT content", sql)
```

Build `sql` from the fake connections with `sql = "\n".join(statement for conn in used for statement in conn.cursor_instance.statements)`. Then call `get_chickenbro_agent_trace("owner-b", job_id)` with a separate fake empty connection and assert `KeyError("chickenbro agent trace not found")`.

- [ ] **Step 5: Implement PostgreSQL insert and owner-bound read**

```python
def insert_chickenbro_agent_trace(
    self, user_id, session_id, user_message_id, agent_job_id, trace, now
):
    payload = validate_chickenbro_agent_trace(trace)
    trace_id = str(uuid.uuid4())
    with self.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO app.chickenbro_agent_traces (
                    id, user_id, session_id, user_message_id, agent_job_id,
                    schema_revision, runtime_version, answer_status, payload_json, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb,
                    COALESCE(%s::timestamptz, now())
                )
                ON CONFLICT (agent_job_id) DO NOTHING
                RETURNING id
                """,
                (
                    trace_id, user_id, session_id, user_message_id, agent_job_id,
                    payload["schemaRevision"], payload["runtimeVersion"], payload["answerStatus"],
                    json_param(payload), now or None,
                ),
            )
            row = cur.fetchone()
            if row:
                return str(row[0])
            cur.execute(
                "SELECT id FROM app.chickenbro_agent_traces WHERE user_id = %s AND agent_job_id = %s",
                (user_id, agent_job_id),
            )
            row = cur.fetchone()
            if not row:
                raise PermissionError("chickenbro trace job owner mismatch")
            return str(row[0])

def get_chickenbro_agent_trace(self, user_id, agent_job_id):
    with self.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, session_id, user_message_id, agent_job_id, payload_json, created_at
                FROM app.chickenbro_agent_traces
                WHERE user_id = %s AND agent_job_id = %s
                """,
                (user_id, agent_job_id),
            )
            row = cur.fetchone()
    if not row:
        raise KeyError("chickenbro agent trace not found")
    return {
        "traceId": str(row[0]), "sessionId": str(row[1]),
        "userMessageId": str(row[2]), "agentJobId": str(row[3]),
        "payload": row[4] if isinstance(row[4], dict) else {},
        "createdAt": str(row[5]),
    }
```

Import `validate_chickenbro_agent_trace` from `server.chickenbro_observability`. Do not expose a list-all or cross-user read method in Phase 1.

- [ ] **Step 6: Add the SQLite compatibility table and helpers**

Extend `ensure_chickenbro_tables(conn)` with `chickenbro_agent_traces` using TEXT identities, `payload_json TEXT NOT NULL`, `UNIQUE(agent_job_id)`, owner/session foreign keys and the same owner-created/session-created indexes.

Add:

```python
def insert_chickenbro_agent_trace(
    conn, user_id, session_id, user_message_id, agent_job_id, trace, now
):
    payload = validate_chickenbro_agent_trace(trace)
    trace_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT OR IGNORE INTO chickenbro_agent_traces (
            id, user_id, session_id, user_message_id, agent_job_id,
            schema_revision, runtime_version, answer_status, payload_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trace_id, user_id, session_id, user_message_id, agent_job_id,
            payload["schemaRevision"], payload["runtimeVersion"], payload["answerStatus"],
            json.dumps(payload, ensure_ascii=False), now or utc_now(),
        ),
    )
    row = conn.execute(
        "SELECT id FROM chickenbro_agent_traces WHERE user_id = ? AND agent_job_id = ?",
        (user_id, agent_job_id),
    ).fetchone()
    if not row:
        raise PermissionError("chickenbro trace job owner mismatch")
    return row[0]

def get_chickenbro_agent_trace(conn, user_id, agent_job_id):
    row = conn.execute(
        """
        SELECT id, session_id, user_message_id, agent_job_id, payload_json, created_at
        FROM chickenbro_agent_traces
        WHERE user_id = ? AND agent_job_id = ?
        """,
        (user_id, agent_job_id),
    ).fetchone()
    if not row:
        raise KeyError("chickenbro agent trace not found")
    return {
        "traceId": row[0], "sessionId": row[1], "userMessageId": row[2],
        "agentJobId": row[3], "payload": json.loads(row[4]), "createdAt": row[5],
    }
```

Both helpers must use `validate_chickenbro_agent_trace(trace)` before serialization; the read helper must filter by `user_id` and `agent_job_id`.

- [ ] **Step 7: Run schema and store tests**

Run:

```powershell
python -m unittest tests.postgres_schema_test tests.postgres_personal_store_test tests.chickenbro_observability_test
```

Expected: all pass; the generated SQL has no cross-owner query and migration 0024 is additive/idempotent.

- [ ] **Step 8: Commit persistence**

```powershell
git add server/migrations/postgres/0024_chickenbro_agent_observability.sql server/postgres_personal_store.py server/news_backend.py tests/postgres_schema_test.py tests/postgres_personal_store_test.py
git commit -m "feat(chickenbro): persist owner-bound agent traces"
```

---

### Task 3: Instrument successful and failed Agent terminal paths without changing answers

**Files:**
- Modify: `server/news_backend.py:269-279, 8217-8450`
- Modify: `tests/news_backend_test.py:7800-8335`
- Modify: `tests/database_adapter_test.py:827-960`

**Interfaces:**
- Consumes: Task 1 `build_chickenbro_agent_trace` and Task 2 store/SQLite insertion methods.
- Produces: one best-effort Trace per terminal Chickenbro job, keyed by `agent_job_id`.

- [ ] **Step 1: Write failing SQLite success and failure-path tests**

```python
def successful_trace_runner(prompt, **kwargs):
    bounded = json.loads(prompt)["boundedContext"]
    return {
        "status": "succeeded",
        "content": json.dumps({
            "answer": "先确认场景，再逐项检查天赋与装备。",
            "confidence": "low",
            "answerLayer": bounded["answerLayer"],
            "basisLabel": bounded["basisLabel"],
            "priorityActions": [],
            "evidenceRefs": [],
            "limitations": [],
            "missingInputs": [],
            "nextQuestion": "",
        }, ensure_ascii=False),
    }

def test_chickenbro_success_persists_one_bounded_trace(self):
    result = self.backend.send_chickenbro_message(
        {"message": "frost death knight build", "guestId": "trace-success-owner"},
        codex_runner=successful_trace_runner,
    )
    with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
        rows = conn.execute(
            "SELECT user_id, agent_job_id, answer_status, payload_json FROM chickenbro_agent_traces"
        ).fetchall()
    self.assertEqual(1, len(rows))
    self.assertEqual(result["job"]["jobId"], rows[0][1])
    self.assertEqual("succeeded", rows[0][2])
    self.assertNotIn("frost death knight build", rows[0][3])

def test_chickenbro_model_failure_persists_failure_trace_and_no_assistant_message(self):
    with self.assertRaises(self.backend.ChickenbroGenerationUnavailable):
        self.backend.send_chickenbro_message(
            {"message": "PTR DPS?", "guestId": "trace-failure-owner"},
            codex_runner=lambda *_args, **_kwargs: {"status": "failed", "error": "offline"},
        )
    with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
        trace = json.loads(conn.execute("SELECT payload_json FROM chickenbro_agent_traces").fetchone()[0])
        roles = [row[0] for row in conn.execute("SELECT role FROM chickenbro_messages")]
    self.assertEqual("failed", trace["answerStatus"])
    self.assertIn("model_failed", {item["code"] for item in trace["outcomeSignals"]})
    self.assertEqual(["user"], roles)
```

- [ ] **Step 2: Run the focused backend tests and verify no Trace is written**

Run:

```powershell
python -m unittest tests.news_backend_test.NewsBackendTest.test_chickenbro_success_persists_one_bounded_trace tests.news_backend_test.NewsBackendTest.test_chickenbro_model_failure_persists_failure_trace_and_no_assistant_message
```

Expected: failure because the send path does not call the Trace builder/store.

- [ ] **Step 3: Add one terminal Trace helper**

Import Task 1 functions into `news_backend.py` and add:

```python
def record_chickenbro_terminal_trace(
    *, store, conn, user_id, session_id, user_message_id, job_id,
    bounded_context, agent_result=None, error="", latency_ms=0, created_at="",
):
    trace = build_chickenbro_agent_trace(
        bounded_context=bounded_context,
        agent_result=agent_result,
        error=error,
        latency_ms=latency_ms,
        created_at=created_at or utc_now(),
    )
    try:
        if store:
            trace_id = store.insert_chickenbro_agent_trace(
                user_id, session_id, user_message_id, job_id, trace, created_at or utc_now()
            )
        else:
            trace_id = insert_chickenbro_agent_trace(
                conn, user_id, session_id, user_message_id, job_id, trace, created_at or utc_now()
            )
    except Exception as trace_error:
        print(f"warning: chickenbro trace write failed: {trace_error}", file=sys.stderr)
        return {"status": "failed", "traceId": ""}
    return {"status": "recorded", "traceId": trace_id}
```

Use `time.perf_counter()` immediately before `run_chickenbro_agent`, and compute a non-negative integer latency at each terminal path. The helper must be called after terminal job/message persistence so Trace failure cannot prevent the response or replace the original model failure.

- [ ] **Step 4: Instrument PostgreSQL and SQLite success paths**

For both paths:

```python
started_clock = time.perf_counter()
agent_result = run_chickenbro_agent(bounded_context, codex_runner=codex_runner)
latency_ms = max(0, int((time.perf_counter() - started_clock) * 1000))
```

After the job is `succeeded`, assistant message is stored and session is touched, write one Trace using `agent_result`. Do not add Trace data to `assistantMessage`, model prompt, public job payload or frontend response.

- [ ] **Step 5: Instrument PostgreSQL and SQLite failure paths**

After the job is `failed` and session timestamp is touched, call the same helper with `agent_result=chickenbro_failed_agent_result(bounded_context, error)` and the original error string. Then re-raise the original `ChickenbroGenerationUnavailable`. Trace write exceptions must be swallowed only after emitting the bounded warning; they must not replace the original exception.

- [ ] **Step 6: Add Trace write-failure and retry idempotency tests**

```python
def test_trace_store_failure_does_not_change_successful_answer(self):
    with patch.object(self.backend, "insert_chickenbro_agent_trace", side_effect=RuntimeError("trace offline")):
        result = self.backend.send_chickenbro_message(
            {"message": "hello", "guestId": "trace-write-failure"},
            codex_runner=successful_trace_runner,
        )
    self.assertEqual("succeeded", result["job"]["status"])
    self.assertTrue(result["assistantMessage"]["content"])

def test_retry_creates_one_trace_per_job_but_reuses_user_message(self):
    request = {
        "message": "frost death knight build",
        "guestId": "trace-retry-owner",
        "clientMessageId": "trace-retry-turn-1",
    }
    with self.assertRaises(self.backend.ChickenbroGenerationUnavailable):
        self.backend.send_chickenbro_message(
            request,
            codex_runner=lambda *_args, **_kwargs: {"status": "failed", "error": "offline"},
        )
    self.backend.send_chickenbro_message(request, codex_runner=successful_trace_runner)
    with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
        trace_count = conn.execute("SELECT COUNT(*) FROM chickenbro_agent_traces").fetchone()[0]
        distinct_job_count = conn.execute(
            "SELECT COUNT(DISTINCT agent_job_id) FROM chickenbro_agent_traces"
        ).fetchone()[0]
        user_message_count = conn.execute(
            "SELECT COUNT(*) FROM chickenbro_messages WHERE role = 'user'"
        ).fetchone()[0]
    self.assertEqual(2, trace_count)
    self.assertEqual(2, distinct_job_count)
    self.assertEqual(1, user_message_count)
```

- [ ] **Step 7: Update the PostgreSQL adapter test**

Add `insert_chickenbro_agent_trace` to the fake store in `test_news_backend_routes_chickenbro_message_runtime_to_postgres_personal_store`, capture its arguments, and change the expected call order to include `insert_trace` after `touch_session` and before `get_job`. Assert the captured Trace does not contain message or answer text.

- [ ] **Step 8: Run the affected backend matrix**

Run:

```powershell
python -m unittest tests.chickenbro_observability_test tests.news_backend_test tests.chickenbro_agent_test tests.database_adapter_test tests.postgres_personal_store_test tests.postgres_schema_test
```

Expected: all pass; existing model failure still returns the same retryable 503 at HTTP level, no fixed assistant message appears, and successful answer content is byte-for-byte unchanged by tracing.

- [ ] **Step 9: Commit runtime instrumentation**

```powershell
git add server/news_backend.py tests/news_backend_test.py tests/database_adapter_test.py
git commit -m "feat(chickenbro): record terminal agent traces"
```

---

### Task 4: Add the offline deterministic Eval corpus and runner

**Files:**
- Create: `server/chickenbro_eval.py`
- Create: `scripts/evaluate_chickenbro_traces.py`
- Create: `tests/fixtures/chickenbro_trace_eval_cases.json`
- Create: `tests/chickenbro_eval_test.py`

**Interfaces:**
- Consumes: Task 1 Trace builder and de-identification function.
- Produces: `load_chickenbro_eval_cases(path)`, `evaluate_chickenbro_trace_case(case)`, `evaluate_chickenbro_trace_cases(cases)`, and a JSON CLI result.

- [ ] **Step 1: Write failing Eval schema and summary tests**

```python
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "chickenbro_trace_eval_cases.json"

def test_eval_runner_accepts_only_revisioned_deidentified_cases(self):
    cases = load_chickenbro_eval_cases(FIXTURE)
    self.assertGreaterEqual(len(cases), 4)
    self.assertTrue(all(case["schemaRevision"] == "chickenbro-trace-eval-case-v1" for case in cases))

def test_eval_summary_fails_when_required_signal_is_missing(self):
    result = evaluate_chickenbro_trace_cases([
        {
            "schemaRevision": "chickenbro-trace-eval-case-v1",
            "caseId": "required_signal_missing",
            "input": {
                "boundedContext": {
                    "topic": {"status": "in_scope"},
                    "requestContext": {
                        "productPhase": "retail", "region": "cn",
                        "classKey": "mage", "specKey": "arcane",
                        "scenarioKey": "mythic_plus",
                    },
                    "sourceEvidence": [],
                },
                "agentResult": {
                    "validation": {"status": "passed"},
                    "model": {"status": "succeeded"},
                },
                "errorCode": "",
                "latencyMs": 200,
            },
            "expect": {
                "answerStatus": "succeeded",
                "requiredSignals": ["evidence_missing"],
                "forbiddenSignals": [],
                "selectedCapabilityIds": [],
            },
        }
    ])
    self.assertEqual("failed", result["status"])
    self.assertEqual(1, result["failedCount"])
```

- [ ] **Step 2: Run the focused tests and verify the Eval module is missing**

Run:

```powershell
python -m unittest tests.chickenbro_eval_test
```

Expected: `ModuleNotFoundError: No module named 'server.chickenbro_eval'`.

- [ ] **Step 3: Create four synthetic, text-free Eval cases**

`tests/fixtures/chickenbro_trace_eval_cases.json` must include exactly these initial behaviors:

```text
verified_source_success
blocked_source_emits_evidence_missing
invalid_model_schema_emits_schema_invalid
unknown_evidence_emits_verification_conflict
```

Each case contains a bounded synthetic input and expectations:

```json
{
  "schemaRevision": "chickenbro-trace-eval-case-v1",
  "caseId": "blocked_source_emits_evidence_missing",
  "input": {
    "boundedContext": {
      "topic": {"status": "in_scope"},
      "requestContext": {
        "productPhase": "ptr",
        "region": "cn",
        "classKey": "deathknight",
        "specKey": "frost",
        "scenarioKey": "mythic_plus"
      },
      "sourceEvidence": [
        {"sourceKey": "raiderio", "status": "blocked", "evidenceRefs": []}
      ]
    },
    "agentResult": {"validation": {"status": "failed"}, "model": {"status": "failed"}},
    "errorCode": "source_blocked",
    "latencyMs": 500
  },
  "expect": {
    "answerStatus": "failed",
    "requiredSignals": ["tool_failed", "evidence_missing"],
    "forbiddenSignals": ["explicit_correction"],
    "selectedCapabilityIds": ["source:raiderio:v1"]
  }
}
```

Fixtures must not contain real user text, report IDs, URLs, character/realm names, access tokens or production Trace IDs.

- [ ] **Step 4: Implement Eval validation and deterministic comparison**

```python
def evaluate_chickenbro_trace_case(case):
    validated_case = validate_eval_case(case)
    trace = build_chickenbro_agent_trace(
        bounded_context=validated_case["input"]["boundedContext"],
        agent_result=validated_case["input"].get("agentResult"),
        error=validated_case["input"].get("errorCode", ""),
        latency_ms=validated_case["input"].get("latencyMs", 0),
        created_at="2026-08-02T00:00:00+00:00",
    )
    projection = deidentify_chickenbro_agent_trace(trace)
    expected = validated_case["expect"]
    failures = []
    signal_codes = {item["code"] for item in projection["outcomeSignals"]}
    if projection["answerStatus"] != expected["answerStatus"]:
        failures.append("answer_status")
    if not set(expected["requiredSignals"]).issubset(signal_codes):
        failures.append("required_signals")
    if set(expected["forbiddenSignals"]) & signal_codes:
        failures.append("forbidden_signals")
    if sorted(projection["selectedCapabilityIds"]) != sorted(expected["selectedCapabilityIds"]):
        failures.append("selected_capability_ids")
    return {"caseId": validated_case["caseId"], "status": "passed" if not failures else "failed", "failures": failures}
```

Reject unknown case keys and missing required expectations. The result must include only case IDs, assertion labels and counts—not Trace payloads or inputs.

- [ ] **Step 5: Implement the no-network CLI**

```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cases",
        default="tests/fixtures/chickenbro_trace_eval_cases.json",
    )
    args = parser.parse_args()
    summary = evaluate_chickenbro_trace_cases(load_chickenbro_eval_cases(args.cases))
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["status"] == "passed" else 1
```

The script must not import `news_backend`, open PostgreSQL/SQLite, call a model, issue HTTP requests or execute a Tool.

- [ ] **Step 6: Run unit and CLI verification**

Run:

```powershell
python -m unittest tests.chickenbro_eval_test tests.chickenbro_observability_test
python scripts/evaluate_chickenbro_traces.py
```

Expected: tests pass; CLI returns exit code 0 with `status=passed`, `caseCount=4`, `passedCount=4`, `failedCount=0`.

- [ ] **Step 7: Commit the Eval foundation**

```powershell
git add server/chickenbro_eval.py scripts/evaluate_chickenbro_traces.py tests/fixtures/chickenbro_trace_eval_cases.json tests/chickenbro_eval_test.py
git commit -m "test(chickenbro): add deterministic trace eval corpus"
```

---

### Task 5: Bind ownership, release evidence, and exact verification

**Files:**
- Modify: `docs/backend-owner-map.json:437-455`
- Modify: `docs/project-owner-map.json:1061-1150`
- Modify: `docs/plans/README.md:23`
- Modify: `docs/plans/2026-08-02-chickenbro-capability-evolution-design.md:270-310`
- Create: `artifacts/releases/2026-08-02-chickenbro-observability-phase1/requirement.json`
- Create: `artifacts/releases/2026-08-02-chickenbro-observability-phase1/manifest.json`
- Create: `artifacts/releases/2026-08-02-chickenbro-observability-phase1/evidence.json`

**Interfaces:**
- Consumes: Tasks 1-4 and current Project Harness schema.
- Produces: one task-scoped release packet and current-control-plane links; no production completion claim.

- [ ] **Step 1: Update owner maps without changing public API ownership**

Add `server/chickenbro_observability.py` as the Trace fact owner under `chickenbro_session_api`, and add `server/chickenbro_eval.py` plus its fixture/runner as non-runtime evaluation consumers. Extend `mustNotChange` with:

```text
Agent traces must never contain raw chat, prompts, answer text, credentials, WCL report identity, SimC stdout, or cross-owner references.
Trace persistence failure must not change a validated answer or replace the original model error.
```

Do not add the Trace to `publicContracts`, frontend API files or user-visible route owners.

- [ ] **Step 2: Register the approved Phase 1 plan**

Only after the user has approved this implementation plan, add its link to the existing Chickenbro row in `docs/plans/README.md` and add an `实施入口` link in the design. Keep the design status `已确认设计`; set the implementation plan status to `正在推进` at execution start.

- [ ] **Step 3: Create a task-scoped release packet**

Use slug `chickenbro-observability-phase1` and path `artifacts/releases/2026-08-02-chickenbro-observability-phase1`. The requirement must state:

```json
{
  "scope": [
    "owner-bound structured Chickenbro agent traces",
    "deterministic terminal outcome signals",
    "text-free deidentified trace projection",
    "offline no-network trace eval corpus"
  ],
  "outOfScope": [
    "dynamic Tool Registry",
    "CapabilityGap persistence or clustering",
    "Cloud Codex Toolsmith",
    "shadow, canary, promotion or model training",
    "frontend or answer-policy changes"
  ]
}
```

Generate `manifest.json` through the repository Harness flow; do not hand-invent immutable identities. Keep `manualAcceptance.required=false` because there is no frontend or answer behavior change; candidate API smoke remains required.

- [ ] **Step 4: Run the targeted Python verification**

Run sequentially on the exact candidate HEAD:

```powershell
python -m unittest tests.chickenbro_observability_test tests.chickenbro_eval_test
python -m unittest tests.news_backend_test tests.chickenbro_agent_test
python -m unittest tests.postgres_schema_test tests.postgres_personal_store_test tests.database_adapter_test
python scripts/evaluate_chickenbro_traces.py
git diff --check
```

Expected: every command exits 0; Eval summary reports four passing cases; no SQLite lock failure is hidden by parallel execution.

- [ ] **Step 5: Run local CR against the approved scope**

Review the source diff and assert all of the following in `evidence.json`:

```text
No prompt, answer, message content, Tool fact, character/realm, report identity, URL, token or stdout enters Trace/projection.
No cross-owner list/read method exists.
No Tool selection, prompt, model schema, answer validation, public API or frontend file changed.
No Trace error can mask a validated answer or original generation failure.
No Phase 2-5 table, runtime, flag or status exists.
```

- [ ] **Step 6: Run the exact full Harness candidate**

Use the bundled modern Node if PATH resolves to WeChat DevTools Node:

```powershell
$node = 'C:\Users\blizz\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
& $node scripts/verify-project.js --profile full --release artifacts/releases/2026-08-02-chickenbro-observability-phase1
```

Expected: full profile passes against a clean exact HEAD and binds only this release packet. Do not reuse the 2026-08-01 source-agent packet.

- [ ] **Step 7: Commit control-plane and release files**

```powershell
git add docs/backend-owner-map.json docs/project-owner-map.json docs/plans/README.md docs/plans/2026-08-02-chickenbro-capability-evolution-design.md artifacts/releases/2026-08-02-chickenbro-observability-phase1
git commit -m "docs(chickenbro): bind observability phase one evidence"
```

---

### Task 6: Candidate deployment, live Trace smoke, and rollback proof

**Files:**
- Modify after evidence collection: `artifacts/releases/2026-08-02-chickenbro-observability-phase1/evidence.json`
- No other source change is allowed in this task.

**Interfaces:**
- Consumes: exact clean candidate HEAD and migration 0024.
- Produces: candidate runtime identity, migration backup/apply evidence, live API/Trace smoke, rollback proof and honest release status.

- [ ] **Step 1: Record immutable candidate identity and remote pre-state**

```powershell
git status --short --branch
git rev-parse HEAD
git diff --check HEAD^ HEAD
ssh wow-lighthouse "cd /opt/wow-mini-program && sha256sum server/news_backend.py server/postgres_personal_store.py && systemctl is-active wow-backend && curl -fsS http://127.0.0.1:3000/health"
```

Expected: local candidate worktree is clean; remote backend is active; health is HTTP 200. Record local SHA, remote pre-deploy hashes, service state and rollback target in `evidence.json`.

- [ ] **Step 2: Back up PostgreSQL schema state and affected remote files**

Use the repository’s known cloud deployment procedure from `docs/remote-debugging.md` and `server/deploy_lighthouse.sh`. Back up the current remote `news_backend.py`, `postgres_personal_store.py` and migration ledger/query result before applying migration 0024. Keep `WOW_DEPLOY_START_ASYNC_SYNCS=0`.

Expected: backup paths, byte sizes and hashes are recorded before writes; no sync/backfill/timer is started.

- [ ] **Step 3: Deploy the exact candidate and apply migration 0024**

Deploy only the clean candidate tree, apply `server/migrations/postgres/0024_chickenbro_agent_observability.sql` through the existing repository-owned migration path, restart `wow-backend`, and verify:

```text
local candidate SHA matches deployed source/build identity
ops.schema_migrations contains 0024_chickenbro_agent_observability
app.chickenbro_agent_traces exists with both owner/session indexes
wow-backend is active and localhost /health returns 200
```

- [ ] **Step 4: Run one real candidate Chickenbro API smoke**

Create an isolated guest session, send one normal WoW question through `POST /api/chickenbro/messages`, and assert:

```text
HTTP 200
job.status == succeeded
assistant message exists and retains the existing response schema
exactly one Trace row exists for that job
Trace user_id/session_id/user_message_id/agent_job_id match the smoke owner and job
payload schemaRevision == chickenbro-agent-trace-v1
payload contains no request message or assistant answer substring
no row is visible when the same owner-bound store read is attempted with another owner
```

Do not use the smoke answer as factual evidence for WoW version correctness; this task validates observability and non-regression only.

- [ ] **Step 5: Prove rollback without deleting Trace data**

Disable the candidate code by restoring the recorded prior backend/store files or prior build identity, restart `wow-backend`, and verify health plus one normal Chickenbro request. Leave the additive 0024 table intact. Then restore the candidate and repeat health/one-message smoke if the candidate is still intended for review.

Expected: both code versions tolerate the additive table; rollback does not delete messages, jobs or traces and does not require a destructive migration.

- [ ] **Step 6: Finalize evidence without claiming merge or production completion**

Update `evidence.json` with candidate SHA, deployed hashes, migration identity, service/API smoke, Trace redaction assertions, owner isolation, timer/backflow state and rollback target. Set status no higher than `candidate_verified`; closure, merge, `main` parity, production release and cleanup remain pending until the user explicitly authorizes closure.

- [ ] **Step 7: Commit the candidate evidence update**

```powershell
git add artifacts/releases/2026-08-02-chickenbro-observability-phase1/evidence.json
git commit -m "test(chickenbro): record observability candidate smoke"
```

## Final Acceptance Matrix

| Boundary | Required proof |
| --- | --- |
| User journey | Normal chat succeeds or fails exactly as before; no new controls or fixed response |
| Trace shape | Structured allowlist only; no raw message, answer, prompt, Tool facts or secrets |
| Privacy | Owner-bound DB identity; projection removes all direct references and free text |
| Outcome | Only deterministic execution signals; no NLP-generated `explicit_correction` |
| Failure | Trace storage failure never masks answer or original generation error |
| Eval | Four synthetic cases pass offline without model, network, DB or Tool calls |
| Scope | No Registry, Gap store, Toolsmith, shadow/canary or promotion |
| Runtime | Candidate SHA/file parity, migration 0024, service health and API/Trace smoke |
| Rollback | Prior code works with additive table retained; no destructive down migration |

## Execution Notes

- Execute inline with `superpowers:executing-plans`; the current session policy does not authorize subagent dispatch.
- Create the isolated worktree at execution start through `superpowers:using-git-worktrees`; do not move or commit the main checkout’s unrelated UI changes.
- Stop for a scope expansion, failed owner/redaction gate, non-additive migration need, local/remote conflict, destructive rollback, or Candidate behavior change. Do not weaken the contract to obtain a green test.
