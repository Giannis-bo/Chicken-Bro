# 炸鸡队长与 SimC 平台骨架实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变当前生产入口的前提下，建立可独立运行和验证的 `/api/v2` 模块化单体、PostgreSQL 领域 schema、异步 Worker、组件健康合同与双端共享 typed client，为后续 Identity、Chickenbro、Raider.IO/WCL 和 SimC 子项目提供稳定边界。

**Architecture:** 新代码进入 `server/app`，Domain 只依赖 Python 标准库，API 使用 FastAPI/Pydantic，Worker 通过 PostgreSQL `FOR UPDATE SKIP LOCKED` 领取基础设施命令。前端本阶段只增加 `/api/v2` 共享类型和 health client，不改 14 条活动路由；旧 `news_backend.py` 与现有 systemd service 继续作为 last-known-good。

**Tech Stack:** Python 3.11+（CI 基线 3.11）、FastAPI 0.141.1、Pydantic 2.13.5、Uvicorn 0.52.4、Psycopg 3.3.4、HTTPX 0.28.1、PostgreSQL、Python `unittest`、TypeScript 5.9、Vitest 4.1、现有 Harness。

**Spec:** `docs/superpowers/specs/2026-09-01-chickenbro-simc-dual-client-architecture-design.md`

## Global Constraints

- 目标产品只有炸鸡队长和 SimC；Identity、历史、health 和 Worker 是共享基础能力，不扩张为第三个业务域。
- 本计划只实现平台骨架，不实现微信 code exchange、网站应用 OAuth/`snsapi_login`、小程序辅助 Web 登录流程、Codex 对话、Raider.IO/WCL 网络解析、SimC profile 编译或 SimC 执行。
- 当前生产 `server/news_backend.py`、`server/wow-backend.service`、14 条 Taro 路由、Active Manifest、Gear Catalog 和 SimC runtime 均保持不变。
- 新后端只能从 `/api/v2` 暴露；不得把新模块导入旧后端，也不得让新模块导入 legacy `news_backend.py`、`simulator_payload.py`、WebSim、Catalog、Resolver 或 Manifest owner。
- PostgreSQL 是唯一新持久层；不得增加 SQLite、Redis、Celery、Kafka、RabbitMQ 或另一个数据库。
- Domain 不导入 FastAPI、Pydantic、Psycopg、Taro、Codex、WCL、Raider.IO 或 SimC 实现。
- 业务表只保存内部 `user_id`；客户端提交的 owner 字段不得进入应用合同。
- `chat`、`simc` 和 `ops` 数据由各自模块写入；跨域读取只通过 port，不能跨 schema 直接查询。
- HTTP 200、进程存活、migration 成功或测试通过都不能提升未配置组件为 ready。
- 本计划不部署、不切流、不删除旧代码、不清空生产数据，也不触发任何 async sync。
- FastAPI、Pydantic、Uvicorn、Psycopg 和 HTTPX 当前未安装。本计划可以先提交锁定清单；创建虚拟环境和执行 `pip install` 前必须取得网络下载/依赖安装的明确批准。
- 每个 Task 先 RED、再最小 GREEN、再定向验证和独立提交；任何测试数据只允许使用临时目录或专用 PostgreSQL candidate database。

## Architecture correction: Web login under a personal WeChat主体

2026-09-01 的当前微信后台证据显示账号主体为个人，无法申请微信认证。因此本计划不再把 Web 登录建模为网站应用 OAuth、`snsapi_login`、独立网站 AppID/AppSecret 或 UnionID 必选链路；这些只保留为未来企业主体的可选升级，不是当前阻塞项。

本计划后续 Identity 子项目的默认合同改为：PC Web 创建短时、一次性、可取消且绑定浏览器 verifier 的 login session，二维码只承载 opaque scene ticket；用户使用现有小程序 `wx.login`/project identity 扫码后，在炸鸡队长小程序内明确确认；服务端将 ticket 绑定到该内部 `user_id`，Web 以同一 verifier 单次交换自己的 HttpOnly Secure SameSite session cookie。scene ticket 不得包含 user_id、OpenID、UnionID、token 或个人信息；移动 Web 明确降级到 PC/另一设备扫码或直接使用小程序。

影响范围：

| 分类 | 结论 |
| --- | --- |
| `must_change` | 父级架构身份/部署/API/安全/验证表述；roadmap 的 Web 登录承诺；本 requirement 的决策记录；Identity 后续的纯 Domain ticket/verifier 合同测试 |
| `must_not_change` | 已完成 Task 0–4、6 的模块边界、PostgreSQL chat/simc/ops schema、Worker lease、旧生产入口、14 条路由、Active Manifest、生产数据库和依赖安装暂停状态 |
| `risk_unknown` | 小程序扫码确认所需的实际小程序码生成能力、当前 project identity API 的具体复用入口、PC 与移动 Web 的最终交互细节；这些留到 Identity 子项目，不在本骨架中猜测实现 |
| `evidence_required` | 纯 Domain 对过期/取消/错 verifier/重复 exchange 的 fail-closed 测试；后续真实小程序确认与 Web Cookie exchange 的 candidate/用户验收；不把设计文档或本地测试宣称为登录完成 |

---

## File and Boundary Map

| Boundary | Responsibility | Planned files |
| --- | --- | --- |
| Dependency lock | 固定新 API 的 Python 运行依赖，不影响旧后端解释器 | Create `server/requirements-v2.txt`, `tests/app_dependency_manifest_test.py` |
| Domain | 身份主体、对话/AgentRun、来源快照和模拟任务状态机 | Create `server/app/{identity,chickenbro,simulation}/domain.py`, matching `ports.py`, package markers |
| Architecture guard | 禁止 Domain/Adapter/API/Worker 逆向依赖和 legacy import | Create `tests/app_architecture_test.py` |
| PostgreSQL schema | `chat`、`simc`、`ops.job_queue` 的正式 owner 与 append-only 结果 | Create `server/migrations/postgres/0038_chickenbro_simc_platform_foundation.sql`, `tests/app_schema_test.py`, `tests/app_postgres_integration_test.py` |
| PostgreSQL platform | 连接 factory、事务边界、readiness probe | Create `server/app/platform/postgres.py`, `server/app/platform/config.py` |
| Job queue | enqueue、claim、lease、heartbeat、terminal transition、cancel | Create `server/app/worker/leases.py`, `tests/app_worker_lease_test.py` |
| API/BFF | request ID、错误 envelope、liveness、component readiness | Create `server/app/main.py`, `server/app/api/errors.py`, `server/app/api/routes/health.py`, `server/app/platform/health.py`, `tests/app_api_test.py` |
| Worker runtime | handler registry 和 `--once`/continuous loop；无业务 handler 时诚实 idle | Create `server/app/worker/handlers.py`, `server/app/worker/main.py`, `tests/app_worker_runtime_test.py` |
| Shared client | 小程序/H5 共用 `/api/v2` health 类型和 typed client | Create `packages/domain/src/platform-v2.ts`, `packages/api-client/src/platform-v2.ts`, matching tests; modify both package indexes |
| Harness/control plane | Strict requirement、验证证据、计划白名单和迁移期边界 | Create task release packet during execution; modify `docs/plans/README.md`, `docs/backend-owner-map.json`, `docs/project-owner-map.json` |

## Task 0: Record the Strict implementation contract before code

**Files:**
- Create: `artifacts/releases/2026-09-01-chickenbro-simc-platform-foundation/requirement.json`

**Interfaces:**
- Consumes: the approved parent architecture, current roadmap and Harness schema.
- Produces: the exact `implementation_allowed` boundary every later Task and reviewer must enforce.

- [ ] **Step 1: Create the requirement packet**

Write this complete JSON before Task 1 changes runtime or dependency files:

```json
{
  "schemaVersion": 1,
  "slug": "chickenbro-simc-platform-foundation",
  "classification": "Strict",
  "status": "implementation_allowed",
  "goal": "建立不改变旧生产入口的 /api/v2 模块化单体、PostgreSQL owner schema、独立 Worker 和双端 typed platform client。",
  "userValue": "后续微信双端、炸鸡队长和角色链接 SimC 可以在同一内部账号与可审计任务底座上独立交付，不再向单个 legacy 后端大文件继续堆叠。",
  "nonGoals": [
    "不实现微信网站应用 OAuth、snsapi_login、小程序辅助 Web 登录流程、Codex 对话、Raider.IO/WCL 网络解析或 SimC 执行。",
    "不改变生产服务、旧 API、14 条路由、Active Manifest 或任何正式数据。",
    "不部署、切流、删除 legacy、安装未经批准的依赖或触发异步同步。"
  ],
  "currentTruth": {
    "sources": [
      "docs/project-state.json",
      "docs/roadmap.md",
      "docs/plans/README.md",
      "docs/superpowers/specs/2026-09-01-chickenbro-simc-dual-client-architecture-design.md",
      "docs/superpowers/plans/2026-09-01-chickenbro-simc-platform-foundation.md",
      "docs/harness.md",
      "docs/verification-matrix.md"
    ],
    "activeMilestone": "taro_target_first_14_route_rebuild",
    "featureIteration": "platform_foundation"
  },
  "impactMap": {
    "mustChange": [
      "server/app modular foundation and dependency guard",
      "PostgreSQL chat/simc/ops queue schema",
      "v2 health API and Worker runtime",
      "shared TypeScript v2 health client and owner maps"
    ],
    "mustNotChange": [
      "server/news_backend.py and server/wow-backend.service",
      "active Taro route registration and navigation",
      "Active Manifest, Gear Catalog, legacy SimC tasks and production data"
    ],
    "evidenceRequired": [
      "focused Python domain/schema/queue/API/Worker tests",
      "focused TypeScript client tests, typecheck and lint",
      "dependency and AST legacy-import guards",
      "Harness packet and diff proof that no production entry changed"
    ]
  },
  "ownership": {
    "factOwner": "docs/superpowers/specs/2026-09-01-chickenbro-simc-dual-client-architecture-design.md",
    "consumers": [
      "future Identity",
      "future Chickenbro",
      "future CharacterSnapshot and SimC Worker",
      "future dual-client shell"
    ]
  },
  "identityConstraint": {
    "currentWechatSubject": "personal_unverified",
    "websiteOAuth": "forbidden_for_current_subject",
    "webLogin": "mini_program_qr_confirmation_with_browser_verifier",
    "unionidRequired": false,
    "sceneTicket": "opaque_short_lived_single_use_no_personal_fields"
  },
  "engineeringHealth": {
    "status": "isolated_foundation",
    "reason": "The new runtime is parallel, unregistered in production and guarded against legacy imports."
  },
  "acceptanceEvidence": [
    "The v2 API exposes only liveness/readiness and reports unimplemented adapters as unconfigured.",
    "The Worker claims each queued command once under lease and has no business handler in this slice.",
    "The TypeScript client is shared by H5/WeApp without changing a route or navigation entry.",
    "Current production files and business data remain unchanged.",
    "This foundation does not claim Web login; it only preserves the mini-program-confirmed, browser-bound identity contract for the later Identity slice."
  ],
  "manualAcceptanceContract": {
    "required": false,
    "requiredItemIds": []
  },
  "releaseTrigger": "backend_api",
  "rollback": [
    "remove_unreferenced_v2_runtime",
    "revert_migration_before_candidate_only",
    "keep_legacy_backend_active"
  ],
  "decisionLog": [
    {
      "date": "2026-09-01",
      "decision": "The user approved the modular monolith API plus independent Worker topology and delegated technical details to Codex best practices."
    },
    {
      "date": "2026-09-01",
      "decision": "The current WeChat account is a personal主体 that cannot apply for WeChat verification; Web login therefore uses mini-program QR confirmation with a browser-bound verifier, without website OAuth, snsapi_login or a UnionID prerequisite."
    }
  ]
}
```

- [ ] **Step 2: Validate the requirement schema and commit**

Run:

```bash
node scripts/project-harness.js --check-requirement --requirement-file artifacts/releases/2026-09-01-chickenbro-simc-platform-foundation/requirement.json
git diff --check
```

If `project-harness.js` does not expose `--check-requirement`, run the repository's exact schema test instead:

```bash
node --test tests/project-harness.test.js
```

Expected: the requirement JSON satisfies `docs/schemas/harness-requirement.schema.json`. Commit:

```bash
git add artifacts/releases/2026-09-01-chickenbro-simc-platform-foundation/requirement.json
git commit -m "docs: authorize the v2 platform foundation slice"
```

## Task 1: Lock the isolated Python v2 dependency set

**Files:**
- Create: `server/requirements-v2.txt`
- Create: `tests/app_dependency_manifest_test.py`

**Interfaces:**
- Consumes: Python 3.11 from CI and the future candidate virtual environment.
- Produces: one exact five-package direct dependency lock used only by `/api/v2` and its tests.

- [ ] **Step 1: Write the failing manifest test**

```python
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "server" / "requirements-v2.txt"


class AppDependencyManifestTest(unittest.TestCase):
    def test_v2_dependencies_are_exact_and_do_not_add_a_broker(self):
        lines = [
            line.strip()
            for line in LOCK.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(
            lines,
            [
                "fastapi==0.141.1",
                "httpx==0.28.1",
                "psycopg[binary]==3.3.4",
                "pydantic==2.13.5",
                "uvicorn==0.52.4",
            ],
        )
        lowered = "\n".join(lines).lower()
        for forbidden in ("celery", "redis", "kafka", "rabbitmq"):
            self.assertNotIn(forbidden, lowered)
```

- [ ] **Step 2: Run RED**

Run: `python3 -m unittest tests.app_dependency_manifest_test -v`

Expected: FAIL because `server/requirements-v2.txt` does not exist.

- [ ] **Step 3: Add the exact lock**

```text
fastapi==0.141.1
httpx==0.28.1
psycopg[binary]==3.3.4
pydantic==2.13.5
uvicorn==0.52.4
```

Keep direct dependencies alphabetized. Do not modify the system Python, old backend service, root Node lockfile or deployment script.

- [ ] **Step 4: Run GREEN and commit**

Run: `python3 -m unittest tests.app_dependency_manifest_test -v && git diff --check`

Expected: PASS. Commit:

```bash
git add server/requirements-v2.txt tests/app_dependency_manifest_test.py
git commit -m "build: lock the v2 API dependencies"
```

- [ ] **Step 5: Stop at the network approval boundary**

After explicit dependency-install approval, create `.venv-v2` and install only from the committed lock:

```bash
python3 -m venv .venv-v2
.venv-v2/bin/python -m pip install -r server/requirements-v2.txt
.venv-v2/bin/python -c "import fastapi, httpx, psycopg, pydantic, uvicorn"
```

Expected: all imports succeed. Without that approval, continue only with Tasks whose tests use the standard library and do not invoke these imports.

## Task 2: Establish domain contracts and dependency guards

**Files:**
- Create: `server/app/__init__.py`
- Create: `server/app/api/__init__.py`
- Create: `server/app/identity/__init__.py`
- Create: `server/app/identity/domain.py`
- Create: `server/app/identity/ports.py`
- Create: `server/app/chickenbro/__init__.py`
- Create: `server/app/chickenbro/domain.py`
- Create: `server/app/chickenbro/ports.py`
- Create: `server/app/simulation/__init__.py`
- Create: `server/app/simulation/domain.py`
- Create: `server/app/simulation/ports.py`
- Create: `server/app/integrations/__init__.py`
- Create: `server/app/platform/__init__.py`
- Create: `server/app/worker/__init__.py`
- Create: `tests/app_domain_test.py`
- Create: `tests/app_architecture_test.py`

**Interfaces:**
- Consumes: Python standard library only.
- Produces: `Principal`, `Conversation`, `AgentRun`, `SourceSnapshot`, `SimulationJob`, their literal enums, legal transition functions and Protocol ports used by every following Task.

**Architecture correction addition:** `server/app/identity/domain.py` also owns the pure `WebLoginSession` contract: only lowercase scene-ticket/verifier SHA-256 digests are stored; mini-program confirmation must match the scene-ticket digest before binding `user_id`; exchange requires the matching verifier, expiry check and a single `confirmed -> exchanged` transition. This is a contract only; it does not implement the Web login route, QR generation or Cookie issuance.

- [ ] **Step 1: Write failing domain transition tests**

```python
import unittest
from uuid import UUID

from server.app.chickenbro.domain import AgentRunStatus, transition_agent_run
from server.app.identity.domain import Principal
from server.app.simulation.domain import (
    SimulationJobStatus,
    SourceReadiness,
    transition_simulation_job,
)


class AppDomainTest(unittest.TestCase):
    def test_principal_is_internal_user_only(self):
        principal = Principal(user_id=UUID("00000000-0000-0000-0000-000000000001"), session_kind="mini_bearer")
        self.assertEqual(principal.session_kind, "mini_bearer")
        self.assertFalse(hasattr(principal, "openid"))
        self.assertFalse(hasattr(principal, "unionid"))

    def test_agent_run_requires_persisted_message_before_success(self):
        with self.assertRaisesRegex(ValueError, "assistant message"):
            transition_agent_run(AgentRunStatus.STREAMING, AgentRunStatus.SUCCEEDED, assistant_message_id=None)

    def test_simulation_job_rejects_queued_to_succeeded(self):
        with self.assertRaisesRegex(ValueError, "illegal simulation job transition"):
            transition_simulation_job(SimulationJobStatus.QUEUED, SimulationJobStatus.SUCCEEDED)

    def test_readiness_literals_match_the_parent_spec(self):
        self.assertEqual(
            {value.value for value in SourceReadiness},
            {
                "INVALID_LINK",
                "CHARACTER_NOT_FOUND",
                "ACCESS_RESTRICTED",
                "SNAPSHOT_UNAVAILABLE",
                "INCOMPLETE_FOR_SIMC",
                "READY_FOR_SIMC",
            },
        )
```

- [ ] **Step 2: Write the failing AST dependency test**

```python
import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "server" / "app"
DOMAIN_FORBIDDEN = ("fastapi", "pydantic", "psycopg", "server.news_backend", "server.simulator_payload")
LEGACY_FORBIDDEN = ("server.news_backend", "server.simulator_payload", "server.websim_payload")


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


class AppArchitectureTest(unittest.TestCase):
    def test_domain_is_framework_and_adapter_free(self):
        for path in APP.glob("*/domain.py"):
            imports = imported_modules(path)
            for forbidden in DOMAIN_FORBIDDEN:
                self.assertFalse(any(name == forbidden or name.startswith(f"{forbidden}.") for name in imports), path)

    def test_new_app_never_imports_legacy_owners(self):
        for path in APP.rglob("*.py"):
            imports = imported_modules(path)
            for forbidden in LEGACY_FORBIDDEN:
                self.assertFalse(any(name == forbidden or name.startswith(f"{forbidden}.") for name in imports), path)
```

- [ ] **Step 3: Run RED**

Run: `python3 -m unittest tests.app_domain_test tests.app_architecture_test -v`

Expected: import failure because `server.app` does not exist.

- [ ] **Step 4: Implement the pure domain types**

Use frozen dataclasses and string enums. Required signatures:

```python
@dataclass(frozen=True)
class Principal:
    user_id: UUID
    session_kind: Literal["mini_bearer", "web_cookie"]

class AgentRunStatus(str, Enum):
    STREAMING = "streaming"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

def transition_agent_run(
    current: AgentRunStatus,
    target: AgentRunStatus,
    *,
    assistant_message_id: UUID | None,
) -> AgentRunStatus:
    if current is not AgentRunStatus.STREAMING or target not in {
        AgentRunStatus.SUCCEEDED,
        AgentRunStatus.FAILED,
    }:
        raise ValueError("illegal agent run transition")
    if target is AgentRunStatus.SUCCEEDED and assistant_message_id is None:
        raise ValueError("assistant message is required before success")
    return target

class SourceReadiness(str, Enum):
    INVALID_LINK = "INVALID_LINK"
    CHARACTER_NOT_FOUND = "CHARACTER_NOT_FOUND"
    ACCESS_RESTRICTED = "ACCESS_RESTRICTED"
    SNAPSHOT_UNAVAILABLE = "SNAPSHOT_UNAVAILABLE"
    INCOMPLETE_FOR_SIMC = "INCOMPLETE_FOR_SIMC"
    READY_FOR_SIMC = "READY_FOR_SIMC"

class SimulationJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

def transition_simulation_job(
    current: SimulationJobStatus,
    target: SimulationJobStatus,
) -> SimulationJobStatus:
    legal = {
        SimulationJobStatus.QUEUED: {
            SimulationJobStatus.RUNNING,
            SimulationJobStatus.CANCELLED,
        },
        SimulationJobStatus.RUNNING: {
            SimulationJobStatus.SUCCEEDED,
            SimulationJobStatus.FAILED,
            SimulationJobStatus.CANCELLED,
        },
    }
    if target not in legal.get(current, set()):
        raise ValueError("illegal simulation job transition")
    return target
```

Legal Simulation transitions are exactly `queued -> running|cancelled` and `running -> succeeded|failed|cancelled`. Legal AgentRun transitions are exactly `streaming -> succeeded|failed`; success requires a non-null assistant message ID.

Define Protocols without concrete imports:

```python
class ConversationRepository(Protocol):
    def list_for_user(self, user_id: UUID, *, limit: int, before: datetime | None) -> Sequence[Conversation]:
        raise NotImplementedError

class SimulationReadPort(Protocol):
    def result_for_user(self, user_id: UUID, result_id: UUID) -> SimulationResult | None:
        raise NotImplementedError

class CharacterSourcePort(Protocol):
    def resolve(self, source_url: str) -> SourceSnapshot:
        raise NotImplementedError
```

- [ ] **Step 5: Run GREEN and commit**

Run:

```bash
python3 -m unittest tests.app_domain_test tests.app_architecture_test -v
python3 -m compileall -q server/app
git diff --check
```

Expected: all tests pass and no framework or legacy import appears in Domain. Commit:

```bash
git add server/app tests/app_domain_test.py tests/app_architecture_test.py
git commit -m "feat: establish the next-generation domain boundaries"
```

## Task 3: Add the PostgreSQL owner schemas and queue tables

**Files:**
- Create: `server/migrations/postgres/0038_chickenbro_simc_platform_foundation.sql`
- Create: `tests/app_schema_test.py`
- Create: `tests/app_postgres_integration_test.py`

**Interfaces:**
- Consumes: existing `identity.users`, `ops.schema_migrations`, roles `wow_migrator` and `wow_app` from migrations `0001`/`0002`.
- Produces: `chat.conversations`, `chat.messages`, `chat.agent_runs`, `simc.source_snapshots`, `simc.simulation_jobs`, `simc.simulation_attempts`, `simc.simulation_results`, `ops.job_queue` and their indexes/constraints.

- [ ] **Step 1: Write the failing static schema contract**

```python
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "server/migrations/postgres/0038_chickenbro_simc_platform_foundation.sql"


class AppSchemaTest(unittest.TestCase):
    def test_platform_schema_has_exact_domain_owners(self):
        sql = " ".join(MIGRATION.read_text(encoding="utf-8").split())
        for clause in (
            "CREATE SCHEMA IF NOT EXISTS chat",
            "CREATE SCHEMA IF NOT EXISTS simc",
            "CREATE TABLE IF NOT EXISTS chat.conversations",
            "CREATE TABLE IF NOT EXISTS chat.messages",
            "CREATE TABLE IF NOT EXISTS chat.agent_runs",
            "CREATE TABLE IF NOT EXISTS simc.source_snapshots",
            "CREATE TABLE IF NOT EXISTS simc.simulation_jobs",
            "CREATE TABLE IF NOT EXISTS simc.simulation_attempts",
            "CREATE TABLE IF NOT EXISTS simc.simulation_results",
            "CREATE TABLE IF NOT EXISTS ops.job_queue",
        ):
            self.assertIn(clause, sql)
        self.assertNotIn("CREATE SCHEMA IF NOT EXISTS news", sql)
        self.assertNotIn("CREATE SCHEMA IF NOT EXISTS websim", sql)

    def test_every_business_table_is_owner_scoped(self):
        sql = MIGRATION.read_text(encoding="utf-8")
        self.assertGreaterEqual(sql.count("user_id uuid NOT NULL REFERENCES identity.users(id)"), 5)
        self.assertIn("'0038_chickenbro_simc_platform_foundation'", sql)
```

- [ ] **Step 2: Run RED**

Run: `python3 -m unittest tests.app_schema_test -v`

Expected: FAIL because migration `0038` does not exist.

- [ ] **Step 3: Implement migration 0038**

Use UUID primary keys supplied by the application; do not require an extension. Required state checks and owner indexes:

```sql
CREATE SCHEMA IF NOT EXISTS chat;
CREATE SCHEMA IF NOT EXISTS simc;

CREATE TABLE IF NOT EXISTS chat.conversations (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    title text NOT NULL DEFAULT '',
    status text NOT NULL CHECK (status IN ('active', 'archived')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat.messages (
    id uuid PRIMARY KEY,
    conversation_id uuid NOT NULL REFERENCES chat.conversations(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    role text NOT NULL CHECK (role IN ('user', 'assistant')),
    content text NOT NULL CHECK (length(content) > 0),
    client_message_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, client_message_id)
);

CREATE TABLE IF NOT EXISTS chat.agent_runs (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    conversation_id uuid NOT NULL REFERENCES chat.conversations(id) ON DELETE CASCADE,
    user_message_id uuid NOT NULL REFERENCES chat.messages(id) ON DELETE RESTRICT,
    assistant_message_id uuid REFERENCES chat.messages(id) ON DELETE RESTRICT,
    status text NOT NULL CHECK (status IN ('streaming', 'succeeded', 'failed')),
    runtime_revision text NOT NULL DEFAULT '',
    public_error_code text NOT NULL DEFAULT '',
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    CHECK (status <> 'succeeded' OR assistant_message_id IS NOT NULL)
);
```

`simc.source_snapshots` stores provider, normalized source URL, revision, readiness code, immutable snapshot JSON, provenance JSON, raw SHA-256 and timestamps. Enforce provider `raiderio|warcraftlogs`, positive revision, the six uppercase readiness literals and unique `(user_id, provider, source_key, revision)`.

`simc.simulation_jobs` stores owner, snapshot ID, scenario hash, compiler/runtime revisions, status, idempotency key and terminal public error. Enforce the five job states and unique `(user_id, idempotency_key)`.

`simc.simulation_attempts` stores one row per attempt with worker ID, start/finish, exit code and bounded diagnostic; unique `(job_id, attempt_number)`.

`simc.simulation_results` stores one immutable row per job with profile hash, result JSON, primary metric name/value and provenance. Add a trigger function that rejects UPDATE/DELETE/TRUNCATE on this table.

`ops.job_queue` is infrastructure-owned and has this claimable contract:

```sql
CREATE TABLE IF NOT EXISTS ops.job_queue (
    id uuid PRIMARY KEY,
    domain text NOT NULL CHECK (domain IN ('identity', 'chat', 'simc')),
    command_type text NOT NULL,
    aggregate_id uuid,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    attempt integer NOT NULL DEFAULT 0 CHECK (attempt >= 0),
    max_attempts integer NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 10),
    available_at timestamptz NOT NULL DEFAULT now(),
    lease_owner text NOT NULL DEFAULT '',
    lease_expires_at timestamptz,
    heartbeat_at timestamptz,
    cancel_requested boolean NOT NULL DEFAULT false,
    public_error_code text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ops_job_queue_claim
ON ops.job_queue (available_at, created_at)
WHERE status = 'queued';
```

Grant `USAGE` on `chat`/`simc` and table DML to `wow_app`; set matching default privileges for `wow_migrator`. Record `0038` in `ops.schema_migrations`. The claim query belongs only to `server/app/worker/leases.py`, where the lease tests inspect it directly.

- [ ] **Step 4: Add disposable PostgreSQL integration coverage**

`tests/app_postgres_integration_test.py` must skip unless `WOW_PG_TEST_DSN_V2` is present. With a dedicated empty database, apply migrations `0001..0038`, insert two users, prove owner indexes and FKs, claim two queued jobs from separate transactions without duplication, recover an expired lease, and prove `simc.simulation_results` rejects update/delete. The test must never create or drop a database.

- [ ] **Step 5: Run schema verification and commit**

Run without a DSN:

```bash
python3 -m unittest tests.app_schema_test tests.app_postgres_integration_test -v
python3 -m unittest tests.postgres_schema_test -v
git diff --check
```

Expected: static tests pass and the integration case reports skipped. When a dedicated DSN is supplied, all integration assertions pass. Commit:

```bash
git add server/migrations/postgres/0038_chickenbro_simc_platform_foundation.sql tests/app_schema_test.py tests/app_postgres_integration_test.py
git commit -m "feat: add the Chickenbro and SimC platform schemas"
```

## Task 4: Implement PostgreSQL configuration, transactions and leases

**Files:**
- Create: `server/app/platform/config.py`
- Create: `server/app/platform/postgres.py`
- Create: `server/app/worker/leases.py`
- Create: `tests/app_config_test.py`
- Create: `tests/app_worker_lease_test.py`

**Interfaces:**
- Consumes: `WOW_DATABASE_URL`, `WOW_APP_ENV`, `WOW_API_V2_HOST`, `WOW_API_V2_PORT`; DB-API-compatible connection/cursor objects.
- Produces: `AppSettings.from_env`, `PostgresConnectionFactory.connection`, `PostgresJobQueue.enqueue/claim/heartbeat/succeed/fail/request_cancel`.

- [ ] **Step 1: Write failing configuration tests**

```python
import unittest

from server.app.platform.config import AppSettings


class AppConfigTest(unittest.TestCase):
    def test_postgres_url_is_required_and_secrets_are_not_repr_visible(self):
        with self.assertRaisesRegex(ValueError, "WOW_DATABASE_URL"):
            AppSettings.from_env({"WOW_APP_ENV": "candidate"})
        settings = AppSettings.from_env({
            "WOW_APP_ENV": "candidate",
            "WOW_DATABASE_URL": "postgresql://user:secret@db.example/wow",
            "WOW_API_V2_HOST": "127.0.0.1",
            "WOW_API_V2_PORT": "8790",
        })
        self.assertEqual(settings.port, 8790)
        self.assertNotIn("secret", repr(settings))
```

- [ ] **Step 2: Write failing lease tests with a fake DB connection**

```python
import unittest
from uuid import UUID

from server.app.worker.leases import LostLeaseError, PostgresJobQueue


JOB_ID = UUID("00000000-0000-4000-8000-000000000010")


class RecordingCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rowcount = connection.rowcount

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=()):
        self.connection.statements.append((" ".join(sql.split()), params))
        return self

    def fetchone(self):
        return self.connection.rows.pop(0) if self.connection.rows else None


class RecordingConnection:
    def __init__(self, *, rows=None, rowcount=1):
        self.rows = list(rows or [])
        self.rowcount = rowcount
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self, **_):
        return RecordingCursor(self)

    @property
    def normalized_sql(self):
        return "\n".join(sql for sql, _ in self.statements)


class AppWorkerLeaseTest(unittest.TestCase):
    def test_claim_uses_skip_locked_and_returns_typed_envelope(self):
        connection = RecordingConnection(rows=[{
            "id": UUID("00000000-0000-0000-0000-000000000010"),
            "domain": "simc",
            "command_type": "snapshot.resolve",
            "aggregate_id": None,
            "payload_json": {"snapshotId": "s1"},
            "attempt": 1,
            "max_attempts": 3,
        }])
        queue = PostgresJobQueue(lambda: connection)
        lease = queue.claim(worker_id="worker-a", lease_seconds=30)
        self.assertEqual(lease.command_type, "snapshot.resolve")
        self.assertIn("FOR UPDATE SKIP LOCKED", connection.normalized_sql)

    def test_terminal_update_requires_the_current_lease_owner(self):
        connection = RecordingConnection(rowcount=0)
        queue = PostgresJobQueue(lambda: connection)
        with self.assertRaisesRegex(LostLeaseError, "lease"):
            queue.succeed(JOB_ID, worker_id="wrong-worker")
```

- [ ] **Step 3: Run RED**

Run: `python3 -m unittest tests.app_config_test tests.app_worker_lease_test -v`

Expected: import failure for missing platform and lease modules.

- [ ] **Step 4: Implement fail-closed settings and connection factory**

```python
@dataclass(frozen=True)
class AppSettings:
    environment: Literal["local", "test", "candidate", "production"]
    database_url: str = field(repr=False)
    host: str = "127.0.0.1"
    port: int = 8790
    worker_poll_seconds: float = 1.0

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "AppSettings":
        environment = env.get("WOW_APP_ENV", "").strip()
        if environment not in {"local", "test", "candidate", "production"}:
            raise ValueError("WOW_APP_ENV must name a supported environment")
        database_url = env.get("WOW_DATABASE_URL", "").strip()
        if not database_url.startswith(("postgresql://", "postgres://")):
            raise ValueError("WOW_DATABASE_URL must be a PostgreSQL URL")
        host = env.get("WOW_API_V2_HOST", "127.0.0.1").strip()
        port = int(env.get("WOW_API_V2_PORT", "8790"))
        poll_seconds = float(env.get("WOW_WORKER_V2_POLL_SECONDS", "1.0"))
        if environment in {"candidate", "production"} and host not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError("candidate and production API must bind to loopback")
        if not 1 <= port <= 65535:
            raise ValueError("WOW_API_V2_PORT is outside 1..65535")
        if not 0.1 <= poll_seconds <= 30:
            raise ValueError("WOW_WORKER_V2_POLL_SECONDS is outside 0.1..30")
        return cls(environment, database_url, host, port, poll_seconds)
```

Reject missing database URL, unsupported environment, non-loopback production/candidate host, ports outside `1..65535`, and poll intervals outside `0.1..30`. Never log or expose the DSN.

`PostgresConnectionFactory` must lazy-import `psycopg`, open `autocommit=False`, commit on success, rollback on exception and always close. It must not import `server.db`, whose SQLite-compatible fallback is outside the new runtime.

- [ ] **Step 5: Implement lease-safe queue operations**

Required public types and methods:

```python
@dataclass(frozen=True)
class JobLease:
    id: UUID
    domain: str
    command_type: str
    aggregate_id: UUID | None
    payload: Mapping[str, object]
    attempt: int
    max_attempts: int

```

`PostgresJobQueue` exposes these exact operations:

- `enqueue(*, job_id: UUID, domain: str, command_type: str, aggregate_id: UUID | None, payload: Mapping[str, object], max_attempts: int = 3) -> None`
- `claim(*, worker_id: str, lease_seconds: int) -> JobLease | None`
- `heartbeat(job_id: UUID, *, worker_id: str, lease_seconds: int) -> None`
- `succeed(job_id: UUID, *, worker_id: str) -> None`
- `fail(job_id: UUID, *, worker_id: str, error_code: str, retryable: bool) -> None`
- `request_cancel(job_id: UUID) -> bool`

`claim` must atomically select the oldest available queued job or expired running lease, increment attempt, set lease owner/expiry and return one row. `fail(retryable=True)` requeues only while `attempt < max_attempts`; all other failures become terminal. Every lease-owned mutation includes `WHERE id=%s AND status='running' AND lease_owner=%s`; zero rows raises `LostLeaseError`.

Use this single-statement claim, with `worker_id` and `lease_seconds` bound as parameters:

```sql
WITH candidate AS (
    SELECT id
    FROM ops.job_queue
    WHERE (
        status = 'queued' AND available_at <= now()
    ) OR (
        status = 'running' AND lease_expires_at < now()
    )
    ORDER BY available_at, created_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
UPDATE ops.job_queue AS jobs
SET status = 'running',
    attempt = jobs.attempt + 1,
    lease_owner = %s,
    lease_expires_at = now() + make_interval(secs => %s),
    heartbeat_at = now(),
    updated_at = now()
FROM candidate
WHERE jobs.id = candidate.id
RETURNING jobs.id, jobs.domain, jobs.command_type, jobs.aggregate_id,
          jobs.payload_json, jobs.attempt, jobs.max_attempts;
```

- [ ] **Step 6: Run GREEN and commit**

Run:

```bash
python3 -m unittest tests.app_config_test tests.app_worker_lease_test -v
python3 -m compileall -q server/app
git diff --check
```

Expected: all tests pass without a PostgreSQL server. Commit:

```bash
git add server/app/platform/config.py server/app/platform/postgres.py server/app/worker/leases.py tests/app_config_test.py tests/app_worker_lease_test.py
git commit -m "feat: add the PostgreSQL v2 runtime foundation"
```

## Task 5: Compose the FastAPI app and honest health surface

**Files:**
- Create: `server/app/api/errors.py`
- Create: `server/app/api/routes/__init__.py`
- Create: `server/app/api/routes/health.py`
- Create: `server/app/platform/health.py`
- Create: `server/app/main.py`
- Create: `tests/app_api_test.py`

**Interfaces:**
- Consumes: `AppSettings`, injected named readiness probes and FastAPI request scope.
- Produces: `create_app(settings, readiness_registry) -> FastAPI`, `GET /health`, `GET /api/v2/health/readiness`, stable problem envelope and `X-Request-Id`.

- [ ] **Step 1: Write failing API tests**

```python
from fastapi.testclient import TestClient
import unittest

from server.app.main import create_app
from server.app.platform.config import AppSettings
from server.app.platform.health import ComponentState, ReadinessRegistry


class AppApiTest(unittest.TestCase):
    def setUp(self):
        settings = AppSettings(
            environment="test",
            database_url="postgresql://redacted",
            host="127.0.0.1",
            port=8790,
        )
        registry = ReadinessRegistry({
            "database": lambda: ComponentState("ready", ""),
            "worker": lambda: ComponentState("unconfigured", "WORKER_NOT_CONFIGURED"),
        })
        self.client = TestClient(create_app(settings=settings, readiness_registry=registry))

    def test_liveness_is_separate_from_business_readiness(self):
        live = self.client.get("/health")
        ready = self.client.get("/api/v2/health/readiness")
        self.assertEqual(live.json()["status"], "ok")
        self.assertEqual(ready.json()["status"], "partial")
        self.assertEqual(ready.json()["components"]["worker"]["status"], "unconfigured")

    def test_request_id_is_returned_and_invalid_ids_are_replaced(self):
        response = self.client.get("/health", headers={"X-Request-Id": "../../secret"})
        request_id = response.headers["X-Request-Id"]
        self.assertRegex(request_id, r"^[0-9a-f-]{36}$")
        self.assertEqual(response.json()["requestId"], request_id)
```

- [ ] **Step 2: Run RED in the approved v2 virtual environment**

Run: `.venv-v2/bin/python -m unittest tests.app_api_test -v`

Expected: import failure because API composition modules do not exist. If `.venv-v2` is absent, stop at the explicit dependency-install boundary from Task 1.

- [ ] **Step 3: Implement health and request/error middleware**

```python
@dataclass(frozen=True)
class ComponentState:
    status: Literal["ready", "partial", "blocked", "unconfigured"]
    code: str

class ReadinessRegistry:
    def __init__(self, probes: Mapping[str, Callable[[], ComponentState]]):
        self._probes = dict(probes)

    def check_all(self) -> Mapping[str, ComponentState]:
        result: dict[str, ComponentState] = {}
        for name, probe in self._probes.items():
            try:
                result[name] = probe()
            except Exception:
                result[name] = ComponentState("blocked", "PROBE_FAILED")
        return result
```

Probe exceptions map to `blocked` with `PROBE_FAILED`; public output never contains exception text. Overall readiness is `ready` only when every component is `ready`, `blocked` when any required component is blocked, otherwise `partial`.

The API error envelope is exact:

```json
{
  "error": {
    "code": "STABLE_PUBLIC_CODE",
    "message": "safe public message",
    "requestId": "uuid"
  }
}
```

Middleware accepts an incoming request ID only when it is a canonical UUID; otherwise generates UUIDv4. Do not log headers, cookies, bodies or database URLs.

- [ ] **Step 4: Compose the app without business routes**

`create_app` must set `docs_url=None`, `redoc_url=None` and `openapi_url="/api/v2/openapi.json"` outside production; production disables all three until the public API contract is reviewed. Register only health routes. The default registry must publish these names with honest states: `database`, `worker`, `codex`, `raiderio`, `warcraftlogs`, `simc`. Unimplemented adapters are `unconfigured`, never ready.

The default database probe opens a read-only transaction, runs `SELECT 1` and maps any connection/query exception to public `ComponentState("blocked", "DATABASE_UNAVAILABLE")` without exposing the exception. Worker and all unimplemented external adapters remain `unconfigured` until a later deployment or adapter slice injects a real probe.

Module entrypoint:

```python
settings = AppSettings.from_env(os.environ)
app = create_app(settings=settings)
```

- [ ] **Step 5: Run GREEN and commit**

Run:

```bash
.venv-v2/bin/python -m unittest tests.app_api_test -v
.venv-v2/bin/python -m compileall -q server/app
git diff --check
```

Expected: health tests pass, liveness remains `ok`, readiness remains `partial` with unconfigured adapters. Commit:

```bash
git add server/app/api server/app/platform/health.py server/app/main.py tests/app_api_test.py
git commit -m "feat: expose the v2 API health foundation"
```

## Task 6: Add the independent Worker runtime

**Files:**
- Create: `server/app/worker/handlers.py`
- Create: `server/app/worker/main.py`
- Create: `tests/app_worker_runtime_test.py`

**Interfaces:**
- Consumes: `PostgresJobQueue`, exact `(domain, command_type)` handler registry and a monotonic clock/sleeper.
- Produces: `HandlerRegistry.register/resolve`, `Worker.run_once() -> bool`, CLI `python -m server.app.worker.main --once`.

- [ ] **Step 1: Write failing Worker tests**

```python
import unittest
from uuid import UUID

from server.app.worker.handlers import HandlerRegistry, UnknownJobHandler
from server.app.worker.leases import JobLease
from server.app.worker.main import Worker


LEASE = JobLease(
    id=UUID("00000000-0000-4000-8000-000000000020"),
    domain="simc",
    command_type="snapshot.resolve",
    aggregate_id=None,
    payload={"snapshotId": "s1"},
    attempt=1,
    max_attempts=3,
)


class FakeQueue:
    def __init__(self, *, claimed):
        self.claimed = claimed
        self.succeeded = []
        self.failed = []

    def claim(self, *, worker_id, lease_seconds):
        return self.claimed

    def succeed(self, job_id, *, worker_id):
        self.succeeded.append((job_id, worker_id))

    def fail(self, job_id, *, worker_id, error_code, retryable):
        self.failed.append((job_id, worker_id, error_code, retryable))


class AppWorkerRuntimeTest(unittest.TestCase):
    def test_idle_once_returns_false_without_sleeping(self):
        worker = Worker(queue=FakeQueue(claimed=None), handlers=HandlerRegistry(), worker_id="worker-a")
        self.assertFalse(worker.run_once())

    def test_registered_handler_marks_the_lease_succeeded(self):
        calls = []
        registry = HandlerRegistry()
        registry.register("simc", "snapshot.resolve", lambda lease: calls.append(lease.id))
        queue = FakeQueue(claimed=LEASE)
        self.assertTrue(Worker(queue=queue, handlers=registry, worker_id="worker-a").run_once())
        self.assertEqual(calls, [LEASE.id])
        self.assertEqual(queue.succeeded, [(LEASE.id, "worker-a")])

    def test_unknown_handler_is_terminal_and_not_retried(self):
        queue = FakeQueue(claimed=LEASE)
        Worker(queue=queue, handlers=HandlerRegistry(), worker_id="worker-a").run_once()
        self.assertEqual(queue.failed, [(LEASE.id, "worker-a", "UNKNOWN_JOB_HANDLER", False)])
```

- [ ] **Step 2: Run RED**

Run: `python3 -m unittest tests.app_worker_runtime_test -v`

Expected: import failure for missing handler registry and Worker.

- [ ] **Step 3: Implement an explicit registry and one-job loop**

```python
JobHandler = Callable[[JobLease], None]


class UnknownJobHandler(LookupError):
    def __init__(self, domain: str, command_type: str):
        super().__init__(f"unknown job handler: {domain}/{command_type}")


class RetryableJobError(RuntimeError):
    def __init__(self, code: str):
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", code):
            raise ValueError("retryable error code must be a stable public literal")
        self.code = code
        super().__init__(code)

class HandlerRegistry:
    def __init__(self):
        self._handlers: dict[tuple[str, str], JobHandler] = {}

    def register(self, domain: str, command_type: str, handler: JobHandler) -> None:
        key = (domain, command_type)
        if key in self._handlers:
            raise ValueError(f"duplicate job handler: {domain}/{command_type}")
        self._handlers[key] = handler

    def resolve(self, domain: str, command_type: str) -> JobHandler:
        try:
            return self._handlers[(domain, command_type)]
        except KeyError as error:
            raise UnknownJobHandler(domain, command_type) from error

class Worker:
    def __init__(
        self,
        *,
        queue: PostgresJobQueue,
        handlers: HandlerRegistry,
        worker_id: str,
        lease_seconds: int = 30,
        poll_seconds: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.queue = queue
        self.handlers = handlers
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.poll_seconds = poll_seconds
        self.sleep = sleep

    def run_once(self) -> bool:
        lease = self.queue.claim(worker_id=self.worker_id, lease_seconds=self.lease_seconds)
        if lease is None:
            return False
        try:
            handler = self.handlers.resolve(lease.domain, lease.command_type)
            handler(lease)
        except UnknownJobHandler:
            self.queue.fail(lease.id, worker_id=self.worker_id, error_code="UNKNOWN_JOB_HANDLER", retryable=False)
        except RetryableJobError as error:
            self.queue.fail(lease.id, worker_id=self.worker_id, error_code=error.code, retryable=True)
        except Exception:
            self.queue.fail(lease.id, worker_id=self.worker_id, error_code="JOB_HANDLER_FAILED", retryable=False)
        else:
            self.queue.succeed(lease.id, worker_id=self.worker_id)
        return True

    def run_forever(self, stop_requested: Callable[[], bool]) -> None:
        while not stop_requested():
            if not self.run_once():
                self.sleep(self.poll_seconds)
```

Duplicate registration raises `ValueError`. Unknown handler is terminal `UNKNOWN_JOB_HANDLER`. `RetryableJobError(code)` maps to `retryable=True`; all other exceptions map to `JOB_HANDLER_FAILED`, exclude exception text from the queue row and are logged only as structured class names with request/job IDs. `KeyboardInterrupt` and `SystemExit` are not swallowed.

The CLI accepts only `--once`, `--worker-id` and `--lease-seconds`; worker ID must match `^[a-zA-Z0-9._:-]{1,64}$`. No domain handlers are registered in this Task, so an empty queue is healthy idle and a queued unknown command fails honestly.

- [ ] **Step 4: Run GREEN and commit**

Run:

```bash
python3 -m unittest tests.app_worker_runtime_test tests.app_worker_lease_test -v
python3 -m compileall -q server/app
git diff --check
```

Expected: Worker tests pass with no external service. Commit:

```bash
git add server/app/worker/handlers.py server/app/worker/main.py tests/app_worker_runtime_test.py
git commit -m "feat: add the PostgreSQL-backed v2 worker runtime"
```

## Task 7: Add the shared TypeScript v2 health contract and client

**Files:**
- Create: `packages/domain/src/platform-v2.ts`
- Create: `packages/domain/src/platform-v2.test.ts`
- Modify: `packages/domain/src/index.ts`
- Create: `packages/api-client/src/platform-v2.ts`
- Create: `packages/api-client/src/platform-v2.test.ts`
- Modify: `packages/api-client/src/index.ts`

**Interfaces:**
- Consumes: existing `ApiTransport.request`, `/api/v2/health/readiness` JSON.
- Produces: `ComponentReadiness`, `PlatformReadinessEnvelope`, `isPlatformReadinessEnvelope`, `PlatformV2Client.readiness()` for both WeApp and H5.

- [ ] **Step 1: Write failing domain validation tests**

```typescript
import { describe, expect, it } from 'vitest'
import { isPlatformReadinessEnvelope } from './platform-v2'

describe('platform v2 readiness contract', () => {
  it('accepts an honest partial component map', () => {
    expect(isPlatformReadinessEnvelope({
      status: 'partial',
      requestId: '00000000-0000-4000-8000-000000000001',
      components: {
        database: { status: 'ready', code: '' },
        simc: { status: 'unconfigured', code: 'SIMC_NOT_CONFIGURED' },
      },
    })).toBe(true)
  })

  it('rejects unknown states and missing request identity', () => {
    expect(isPlatformReadinessEnvelope({ status: 'green', components: {} })).toBe(false)
  })
})
```

- [ ] **Step 2: Write the failing client test**

```typescript
import type { ApiTransport } from './transport'
import { PlatformV2Client } from './platform-v2'


function recordingTransport(payload: unknown): ApiTransport & { paths: string[] } {
  const paths: string[] = []
  return {
    paths,
    async request<T>(path: string) {
      paths.push(path)
      return { payload: payload as T, fromFallback: false, error: '' }
    },
    async requestEndpoint<T>() {
      throw new Error('endpoint registry is not used by the v2 health client')
    },
  }
}


it('reads only the v2 readiness endpoint and never promotes fallback', async () => {
  const transport = recordingTransport({
    status: 'partial',
    requestId: '00000000-0000-4000-8000-000000000001',
    components: { worker: { status: 'unconfigured', code: 'WORKER_NOT_CONFIGURED' } },
  })
  const result = await new PlatformV2Client(transport).readiness()
  expect(transport.paths).toEqual(['/api/v2/health/readiness'])
  expect(result.fromFallback).toBe(false)
  expect(result.payload.status).toBe('partial')
})
```

- [ ] **Step 3: Run RED**

Run: `npm run test:taro -- packages/domain/src/platform-v2.test.ts packages/api-client/src/platform-v2.test.ts`

Expected: import failure because v2 contract/client files do not exist.

- [ ] **Step 4: Implement types, validator and client**

```typescript
export type ComponentReadinessStatus = 'ready' | 'partial' | 'blocked' | 'unconfigured'

export interface ComponentReadiness {
  status: ComponentReadinessStatus
  code: string
}

export interface PlatformReadinessEnvelope {
  status: 'ready' | 'partial' | 'blocked'
  requestId: string
  components: Readonly<Record<string, ComponentReadiness>>
}

export function isPlatformReadinessEnvelope(value: unknown): value is PlatformReadinessEnvelope {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return false
  const root = value as Record<string, unknown>
  if (!['ready', 'partial', 'blocked'].includes(String(root['status']))) return false
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(root['requestId']))) return false
  const components = root['components']
  if (typeof components !== 'object' || components === null || Array.isArray(components)) return false
  return Object.entries(components as Record<string, unknown>).every(([name, component]) => {
    if (!name || typeof component !== 'object' || component === null || Array.isArray(component)) return false
    const row = component as Record<string, unknown>
    return ['ready', 'partial', 'blocked', 'unconfigured'].includes(String(row['status']))
      && typeof row['code'] === 'string'
  })
}
```

In `packages/api-client/src/platform-v2.ts`, consume the domain contract instead of redefining it:

```typescript
import {
  isPlatformReadinessEnvelope,
  type PlatformReadinessEnvelope,
} from '@wow-mini/domain'

import type { ApiResult, ApiTransport } from './transport'

export class PlatformV2Client {
  constructor(private readonly transport: ApiTransport) {}

  readiness(): Promise<ApiResult<PlatformReadinessEnvelope>> {
    return this.transport.request('/api/v2/health/readiness', {
      method: 'GET',
      timeoutMs: 5000,
      auth: false,
      fallback: () => ({ status: 'blocked', requestId: '', components: {} }),
      validate: isPlatformReadinessEnvelope,
    })
  }
}
```

The validator accepts only non-empty component keys, known status literals, string codes and a UUID-shaped request ID. `PlatformV2Client.readiness()` calls `transport.request` with method GET, timeout 5 seconds, `auth=false`, validator above and fallback `{status:'blocked', requestId:'', components:{}}`. It returns the existing `ApiResult` unchanged so fallback cannot become ready.

Export all new names from package indexes. Do not add a route, page, tab, storage key or navigation entry.

- [ ] **Step 5: Run GREEN, typecheck and commit**

Run:

```bash
npm run test:taro -- packages/domain/src/platform-v2.test.ts packages/api-client/src/platform-v2.test.ts
npm run typecheck
npm run lint
git diff --check
```

Expected: focused tests, strict TypeScript and lint pass. Commit:

```bash
git add packages/domain/src/platform-v2.ts packages/domain/src/platform-v2.test.ts packages/domain/src/index.ts packages/api-client/src/platform-v2.ts packages/api-client/src/platform-v2.test.ts packages/api-client/src/index.ts
git commit -m "feat: add the shared v2 platform client"
```

## Task 8: Bind the foundation to Harness and candidate handoff

**Files:**
- Modify: `artifacts/releases/2026-09-01-chickenbro-simc-platform-foundation/requirement.json`
- Create: `artifacts/releases/2026-09-01-chickenbro-simc-platform-foundation/evidence.json`
- Create: `artifacts/releases/2026-09-01-chickenbro-simc-platform-foundation/manifest.json`
- Modify: `docs/plans/README.md`
- Modify: `docs/backend-owner-map.json`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/verification-matrix.md`
- Test: `tests/project-state.test.js`
- Test: `tests/backend-owner-map.test.js`
- Test: `tests/project-owner-map.test.js`

**Interfaces:**
- Consumes: final implementation commit, focused test results, migration hash, dependency lock hash and current `project-state.json`.
- Produces: one complete Strict Harness packet with `local_verified` ceiling; no candidate, deployable or live claim.

- [ ] **Step 1: Revalidate and advance the existing requirement packet**

Run:

```bash
node scripts/project-harness.js --check-requirement --requirement-file artifacts/releases/2026-09-01-chickenbro-simc-platform-foundation/requirement.json
```

Expected: the Task 0 requirement still passes after the final diff. Change its status from `implementation_allowed` to `local_verified` only after Step 3 passes; do not change any non-goal, protected surface, acceptance item or rollback entry.

- [ ] **Step 2: Update owner maps and plan whitelist**

Add one active plan row linking this file. Owner maps must identify:

- `server/app/main.py` as `/api/v2` composition owner, not business-fact owner;
- `server/app/identity`, `server/app/chickenbro`, `server/app/simulation` as domain owners;
- `server/app/worker` as infrastructure execution owner;
- `packages/api-client/src/platform-v2.ts` as typed transport owner;
- legacy routes/services as `mustNotChange` during this slice.

Do not replace `project-state.json` Active runtime until candidate and cutover exist.

- [ ] **Step 3: Run the full local verification appropriate to a migration slice**

Run:

```bash
.venv-v2/bin/python -m unittest \
  tests.app_dependency_manifest_test \
  tests.app_domain_test \
  tests.app_architecture_test \
  tests.app_schema_test \
  tests.app_config_test \
  tests.app_worker_lease_test \
  tests.app_api_test \
  tests.app_worker_runtime_test -v
npm run test:taro -- packages/domain/src/platform-v2.test.ts packages/api-client/src/platform-v2.test.ts
npm run typecheck
npm run lint
node --test tests/project-state.test.js tests/backend-owner-map.test.js tests/project-owner-map.test.js
node scripts/verify-project.js --profile full --release artifacts/releases/2026-09-01-chickenbro-simc-platform-foundation --base origin/main
git diff --check
```

Expected: every command passes. PostgreSQL integration remains separately identified as `UNVERIFIED` unless the dedicated candidate DSN test was actually run.

- [ ] **Step 4: Build evidence and manifest with an honest ceiling**

Record exact Git commit/tree, command exit codes, migration SHA-256, dependency lock SHA-256 and changed paths. Set evidence status to `local_verified` only when every local command passed. Set these literal non-claims:

```json
{
  "candidateDeployment": "NOT_RUN",
  "productionDeployment": "NOT_RUN",
  "postgresMigrationRuntime": "UNVERIFIED",
  "wechatLogin": "NOT_IMPLEMENTED",
  "codexConversation": "NOT_IMPLEMENTED",
  "characterSourceAdapters": "NOT_IMPLEMENTED",
  "simcExecution": "NOT_IMPLEMENTED"
}
```

- [ ] **Step 5: Local CR and final plan-slice commit**

Review the complete diff against the parent spec and confirm:

- no new import from `server.news_backend`, `server.simulator_payload` or `server.websim_payload`;
- no route/navigation/service/deploy change;
- no dependency secret, DSN, OpenID, UnionID, chat content or profile payload in evidence;
- no website OAuth/`snsapi_login`/UnionID prerequisite is introduced; Web login remains a later mini-program-confirmed, browser-verifier-bound Identity slice;
- no health component claims ready without a real probe;
- no migration or queue write has run against production.

Commit:

```bash
git add artifacts/releases/2026-09-01-chickenbro-simc-platform-foundation docs/plans/README.md docs/backend-owner-map.json docs/project-owner-map.json docs/verification-matrix.md tests/project-state.test.js tests/backend-owner-map.test.js tests/project-owner-map.test.js
git commit -m "docs: bind the v2 platform foundation evidence"
```

## Plan Self-Review Checklist

- [ ] Every parent-spec component needed by the platform slice has a file owner and test; business adapters remain explicitly outside this slice.
- [ ] All Python signatures use the same status literals, `user_id` type and queue lease fields across Tasks 2--6.
- [ ] TypeScript readiness literals exactly match API output and cannot promote fallback to ready.
- [ ] Migration `0038` is additive; no legacy schema, row, service or pointer is deleted or mutated by this slice.
- [ ] Dependency install is the only network/download action and remains blocked until explicit approval.
- [ ] Candidate, Web QR confirmation, website OAuth, real Codex, Raider.IO/WCL and SimC semantic smokes are not represented as completed by local foundation tests.

## Completion Boundary

This plan is complete at `local_verified` when the parallel `/api/v2` app, honest readiness, additive PostgreSQL schema, lease-safe Worker, dependency guard and shared typed client all pass fresh verification while the production entry remains unchanged. It does not authorize deployment, migration application on the known cloud database, Web domain configuration, WeChat login, Codex traffic, source parsing, SimC execution, legacy deletion or product acceptance.
