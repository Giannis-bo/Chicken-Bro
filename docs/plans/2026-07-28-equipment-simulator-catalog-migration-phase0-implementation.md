# Equipment Simulator Catalog Migration Phase 0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不修改活动数据库、Manifest、公开 API、前端或 SimC 任务链的前提下，量化首个 `CatalogRevision` 迁移的四类未知风险，并冻结后续 schema/API 切片必须遵守的输入、输出和资源门禁。

**Architecture:** 新增一个纯 `gear_catalog_migration_audit` 领域模块负责分类和聚合，一个只读 `gear_catalog_audit_store` 负责有界 PostgreSQL 投影，一个 CLI 负责环境预检和 JSON 输出。所有业务判断都在纯模块完成；store 不写库，CLI 不修改 runtime。Phase 0 只产生去标识化审计证据，不创建 Catalog 表、不构建 Release、不切指针。

**Tech Stack:** Python 3 标准库、现有 `psycopg` runtime、Node.js 静态调用方审计、`unittest`、`node:test`、Project Harness v0.6.4。

## Global Constraints

- 分类为 `Strict`。用户已批准
  [目标架构](2026-07-28-equipment-simulator-target-architecture.md)，本计划需审阅通过后才能执行。
- 本阶段只解决目标架构 `risk_unknown`：
  1. 活动 Gear Release 到首个 `CatalogRevision` 的无损映射率；
  2. 社区模板和个人装备模板的 Exact Item 身份完整率；
  3. 当前 builder/物化/诊断的可观测资源基线；
  4. 旧 catalog/release/API 调用方清单。
- 不创建或修改 PostgreSQL schema，不写任何业务表，不 seal Release/Manifest，不执行
  pointer CAS，不触发同步、backfill、timer 或 SimC。
- 不运行 `build-legacy-gear`、`build-legacy-all` 或其他全量 builder；无法从现有数据证明的
  峰值 RSS/临时磁盘必须记为 `unknown`，不能靠一次无保护重跑猜测。
- 所有 PostgreSQL 会话必须显式 `BEGIN READ ONLY`，设置有界
  `statement_timeout`/`lock_timeout`，并在退出时 `ROLLBACK`。
- 报告不得包含数据库 URL、用户 ID、角色名、realm、token、原始模板文本、完整 profile、
  原始装备行或其他个人数据。允许输出总数、比例、状态、problem code 和最多 20 个
  `sha256:` 匿名样本身份。
- `blocked` 不计入覆盖通过；`unknown` 不得转换为零或默认预算。
- Phase 0 的通过只授权编写 Phase 1 合同，不授权新 schema、公开 reader、候选构建、
  数据迁移、部署或 Manifest 切换。

## Harness Contract

### 用户场景与可见承诺

本阶段不改变玩家体验。它确保下一阶段不会在不知道“现有数据能否无损映射、模板是否
保存了精确实例、旧调用方是否仍在使用、环境能否承受构建”的情况下开始迁移。

最终玩家承诺仍由目标架构拥有：

- 40/40 专精可配装和保存；
- 手动浏览只显示每件物品每条合法轨道的最高 rank；
- 社区导入保留英雄 3/6 等真实实例；
- 26 个常规输出专精可运行 SimC，14 个已确认不支持的专精在 Runner 前阻断。

### 非目标

- 不实现 `CatalogRevision`、`ItemDefinition`、`BrowseVariant`、`ExactItemInstance` 表。
- 不修改 `gear_release.py`、`gear_resolver.py`、`gear_runtime.py` 的活动语义。
- 不迁移社区模板、个人模板、stat snapshot 或历史 SimC task。
- 不修改 Taro 页面、typed API、视觉目标或微信包。
- 不新增长期 health/admin endpoint；Phase 0 CLI 是显式运维工具，不是 runtime reader。
- 不根据名称、tooltip、默认轨道或 BrowseVariant 补全缺失的精确实例字段。

### Impact Map

| 分类 | 内容 |
| --- | --- |
| `must_change` | 纯审计合同、只读 PG 投影、静态调用方审计、去标识化 Phase 0 报告、owner/control-plane 登记、Harness packet |
| `must_not_change` | 活动 Gear/Community Release、Manifest pointer、公开 API payload、个人模板授权、SimC task/result、timer/backfill、Taro |
| `risk_unknown` | 活动 release 的 canonical 映射率、社区/个人模板 exactness、真实 peak RSS/temp bytes、旧 caller 数量 |
| `evidence_required` | fixed-query read-only proof、相同输入相同报告 hash、40 专精真实覆盖状态、template exactness totals、relation/materialization bytes、static/runtime caller inventory、零写入与零 pointer 变化 |

### Owner 与工程健康

- `server/gear_catalog_migration_audit.py`：唯一拥有 Phase 0 分类、状态、聚合和报告 hash。
- `server/gear_catalog_audit_store.py`：只读 PostgreSQL projection owner；不得决定
  `verified/partial/blocked`。
- `scripts/gear-catalog-migration-audit.py`：CLI/environment orchestrator；只接受 PG-only
  runtime 和显式输出路径。
- `scripts/audit-gear-catalog-callers.js`：仓库静态调用方 inventory owner；不判断运行流量。
- `server/gear_release_store.py`、`server/postgres_personal_store.py` 继续拥有活动数据写入；
  Phase 0 不向两个热点文件增加方法。
- 工程健康为 `health_watch`：原因是跨 release、community、personal 和
  `pg_catalog` 的只读审计；通过 fixed-query、read-only transaction、输出上限和
  去标识化约束风险。

### 发布与回滚

- 本地单元测试和 fixture 不连接网络或生产。
- 生产审计只读；执行前记录 active pointer identity，执行后重新读取并证明 generation、
  manifest revision 和 release IDs 未变化。
- 本阶段不部署 active service、不重启进程、不应用 migration。
- 代码回滚使用 `code_rollback`。审计输出是不可变证据；若含敏感或超界内容，整份报告
  作废并重新生成，不能局部编辑伪装为原始输出。
- 无业务数据写入，因此 `data_restore` 不适用。

---

## Task 1: Freeze the Phase 0 Harness requirement

**Files:**

- Create: `artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/requirement.json`
- Modify: `tests/project-state.test.js`

**Interfaces:**

- Consumes: approved target architecture and this implementation plan.
- Produces: one task-scoped Strict requirement with no manual acceptance and no runtime activation.

- [ ] **Step 1: Add the failing requirement assertion**

Extend the existing Phase 0 control-plane assertion so it also loads the task requirement and checks
its slug, `Strict` classification, empty manual-acceptance set and `code_rollback` boundary.

Run:

```bash
node --test tests/project-state.test.js
```

Expected: FAIL because the task requirement does not exist yet.

- [ ] **Step 2: Create the task-scoped requirement**

The requirement must freeze:

```json
{
  "schemaVersion": 1,
  "slug": "equipment-simulator-catalog-migration-phase0",
  "classification": "Strict",
  "status": "implementation_allowed",
  "manualAcceptanceContract": {
    "required": false,
    "requiredItemIds": []
  },
  "releaseTrigger": "pg_read_model",
  "rollback": [
    "code_rollback"
  ]
}
```

`goal`, `userValue`, `nonGoals`, `currentTruth`, `impactMap`, `ownership`,
`engineeringHealth`, `acceptanceEvidence` and `decisionLog` must fully encode the
constraints above. `currentTruth.candidateDeploymentRequiredBeforeMerge` is `false`
because no runtime code or schema is activated; the production evidence requirement is an
explicit read-only audit.

- [ ] **Step 3: Validate the requirement before production code**

Run:

```bash
node scripts/project-harness.js --json \
  --check-requirement \
  --requirement-file artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/requirement.json
```

Expected: exit `0`; classification is `Strict`, manual acceptance is not required, and no
complete packet claim is made yet.

- [ ] **Step 4: Commit the frozen contract**

```bash
git add artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/requirement.json tests/project-state.test.js
git commit -m "test(gear): freeze catalog migration phase0 contract"
```

The active contract already points to the reviewed plan. Task 7 updates its status from
`pending_user_review` to the measured Phase 0 result; it does not create a second contract.

## Task 2: Add pure migration-audit classifications

**Files:**

- Create: `server/gear_catalog_migration_audit.py`
- Create: `tests/gear_catalog_migration_audit_test.py`

**Interfaces:**

- Produces:
  `audit_catalog_mapping(binding, rows) -> dict`
- Produces:
  `audit_template_exactness(community_rows, personal_rows) -> dict`
- Produces:
  `audit_spec_coverage(spec_rows) -> dict`
- Produces:
  `audit_resource_baseline(resource_rows) -> dict`
- Produces:
  `build_phase0_report(*, catalog, templates, coverage, resources, callers) -> dict`
- Produces:
  `validate_phase0_report(report) -> list[dict]`

- [ ] **Step 1: Write failing deterministic and fail-closed tests**

At minimum cover:

```python
def test_same_inputs_have_same_report_id_despite_observation_time():
    first = build_phase0_report(**complete_inputs(), observed_at="2026-07-28T10:00:00+08:00")
    second = build_phase0_report(**complete_inputs(), observed_at="2026-07-28T11:00:00+08:00")
    self.assertEqual(first["reportId"], second["reportId"])
    self.assertNotEqual(first["observedAt"], second["observedAt"])

def test_blocked_spec_is_not_counted_as_covered():
    result = audit_spec_coverage([
        {"classKey": "mage", "specKey": "frost", "status": "verified", "candidateCount": 12},
        {"classKey": "warrior", "specKey": "arms", "status": "blocked", "candidateCount": 0},
    ])
    self.assertEqual(result["verifiedSpecCount"], 1)
    self.assertEqual(result["blockedSpecCount"], 1)
    self.assertFalse(result["complete"])

def test_missing_peak_rss_stays_unknown():
    result = audit_resource_baseline({"peakRssObservedBytes": None})
    self.assertEqual(result["peakRss"]["status"], "unknown")
    self.assertIsNone(result["peakRss"]["bytes"])
```

Also test:

- a BrowseVariant candidate lacking track/rank/ilevel/static stats is not losslessly mappable;
- one item/track with multiple highest-rank rows is `blocked`, not silently deduplicated;
- an exact instance requires item ID, canonical bonus IDs, ilevel and enough track/rank context to
  distinguish an intermediate variant;
- missing gems/enchant are valid empty selections, while an explicitly present but malformed value is
  `blocked`;
- personal and community totals remain separate;
- samples are hashed, deduplicated, sorted and capped at 20;
- timestamps, DB row IDs and display labels do not enter `reportId`.

- [ ] **Step 2: Verify RED**

Run:

```bash
python3 -m unittest tests.gear_catalog_migration_audit_test -v
```

Expected: FAIL because `server.gear_catalog_migration_audit` does not exist.

- [ ] **Step 3: Implement the minimal pure contract**

The top-level report shape is:

```python
{
    "schemaRevision": "equipment-simulator-catalog-migration-audit-v1",
    "reportId": "catalog-migration-audit:sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "observedAt": "2026-07-28T10:00:00+08:00",
    "status": "blocked",
    "catalogMapping": {
        "status": "blocked",
        "itemTotal": 0,
        "mappedItemCount": 0,
        "variantTotal": 0,
        "mappedVariantCount": 0,
        "optionTotal": 0,
        "mappedOptionCount": 0
    },
    "templateExactness": {
        "community": {"status": "blocked", "total": 0, "exact": 0, "partial": 0, "blocked": 0},
        "personal": {"status": "blocked", "total": 0, "exact": 0, "partial": 0, "blocked": 0},
    },
    "specCoverage": {"status": "blocked", "total": 0, "verified": 0, "partial": 0, "blocked": 0},
    "resources": {"status": "blocked", "measured": {}, "unknown": []},
    "callers": {"status": "blocked", "runtimeCallerCount": 0, "unresolvedCount": 0},
    "problems": [],
}
```

The canonical hash excludes `observedAt` and includes every result section and problem. Status
precedence is `blocked > partial > verified`. Any missing required section is `blocked`.

Exactness classification must use structural fields only. It must never infer rank or stats from
item name, item level alone, BrowseVariant maximum, source display text or frontend labels.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
python3 -m unittest tests.gear_catalog_migration_audit_test -v
```

Expected: PASS.

- [ ] **Step 5: Commit the pure audit owner**

```bash
git add server/gear_catalog_migration_audit.py tests/gear_catalog_migration_audit_test.py
git commit -m "feat(gear): add pure catalog migration audit"
```

## Task 3: Add the fixed-query read-only PostgreSQL projection

**Files:**

- Create: `server/gear_catalog_audit_store.py`
- Create: `tests/gear_catalog_audit_store_test.py`

**Interfaces:**

- Produces: `GearCatalogAuditStore(connection_factory)`
- Produces:
  `snapshot(*, statement_timeout_ms=15000, lock_timeout_ms=1000, batch_size=500) -> dict`
- Consumes only the current active Manifest, immutable release rows, community template projection,
  account-owned gear template metadata, relation sizes and release events.

- [ ] **Step 1: Write failing store-boundary tests**

The fake connection must prove:

```python
self.assertIn("BEGIN READ ONLY", statements)
self.assertIn("SET LOCAL statement_timeout", statements)
self.assertIn("SET LOCAL lock_timeout", statements)
self.assertEqual(write_statements(statements), [])
self.assertLessEqual(store.query_count, 12)
self.assertTrue(connection.rolled_back)
self.assertFalse(connection.committed)
```

Also verify:

- pointer identity is read both before and after the snapshot;
- a changed pointer yields `AUDIT_POINTER_CHANGED` and discards the mixed snapshot;
- result rows are bounded and paged by stable primary keys;
- raw personal identifiers and `raw_string` are never returned;
- template rows expose only template type, hashed template identity and structural gear fields;
- relation sizes use `pg_total_relation_size` for an allowlisted table set, never a caller-provided
  identifier;
- every exception triggers rollback and connection close.

- [ ] **Step 2: Verify RED**

Run:

```bash
python3 -m unittest tests.gear_catalog_audit_store_test -v
```

Expected: FAIL because the store module does not exist.

- [ ] **Step 3: Implement the bounded read-only store**

Required sections:

```python
{
    "pointerBefore": {
        "generation": 0,
        "manifestRevision": "",
        "pointerMode": "active"
    },
    "activeBinding": {
        "manifest": {},
        "gearRelease": {},
        "communityRelease": {}
    },
    "catalogRows": {
        "items": [],
        "variants": [],
        "options": [],
    },
    "communityTemplates": [],
    "personalGearTemplates": [],
    "relationSizes": [],
    "releaseEvents": [],
    "pointerAfter": {
        "generation": 0,
        "manifestRevision": "",
        "pointerMode": "active"
    },
    "queryMetrics": {
        "total": 0,
        "reads": 0,
        "writes": 0,
    },
}
```

`catalogRows` may include only the active Gear Release. `communityTemplates` may include only the
Community Release cross-bound by the same Manifest. Personal gear templates are inventory inputs,
not active catalog membership, and remain a separate section.

The store must not import `news_backend.py`, must not call a public HTTP route, and must not reuse
`snapshot_staging_gear()` because staging can differ from the active Manifest.

- [ ] **Step 4: Verify GREEN and existing release-store regression**

Run:

```bash
python3 -m unittest \
  tests.gear_catalog_audit_store_test \
  tests.gear_release_store_test \
  tests.postgres_personal_store_test -v
```

Expected: PASS; query metrics report zero writes.

- [ ] **Step 5: Commit the read-only projection**

```bash
git add server/gear_catalog_audit_store.py tests/gear_catalog_audit_store_test.py
git commit -m "feat(gear): add read-only catalog audit store"
```

## Task 4: Inventory static catalog and SimC callers

**Files:**

- Create: `scripts/audit-gear-catalog-callers.js`
- Create: `tests/gear-catalog-callers-audit.test.js`

**Interfaces:**

- Produces:
  `collectGearCatalogCallers({ root, allowlist }) -> CallerAudit`
- CLI prints stable JSON to stdout or atomically writes a repository-relative path supplied through
  `--output`.

- [ ] **Step 1: Write failing fixture tests**

Create temporary fixture files in the test and assert the auditor separates:

- active backend readers;
- Taro typed clients;
- legacy compatibility readers;
- tests/fixtures/docs;
- dynamic or unresolved references.

The test must prove comments and archived artifacts do not count as runtime callers, and that
`server/gear_release_store.py` definitions are owners rather than callers.

Run:

```bash
node --test tests/gear-catalog-callers-audit.test.js
```

Expected: FAIL because the audit script does not exist.

- [ ] **Step 2: Implement a deterministic repository scan**

Scan only tracked files returned by:

```bash
git ls-files -z
```

Match the frozen API/owner symbols:

```text
/api/websim/gear
/api/websim/gear/resolve
/api/websim/profile
/api/simulator/simc
load_active_public_gear
load_active_authority_context
load_active_manifest_binding
gearCatalogReleaseId
gearCatalogRevision
```

Output repository-relative paths, line numbers and one category. Do not emit the matched source
line. Results must be sorted and content-addressed. Unknown dynamic references are `partial`, not
ignored.

- [ ] **Step 3: Verify against the real repository**

Run:

```bash
node --test tests/gear-catalog-callers-audit.test.js
node scripts/audit-gear-catalog-callers.js | \
  node -e "let s=''; process.stdin.on('data',d=>s+=d).on('end',()=>{const x=JSON.parse(s); if(!x.reportId||!x.categories.activeBackend.length||!x.categories.taro.length) process.exit(1)})"
```

Expected: exit `0`; output contains no source text, secrets or absolute paths.

- [ ] **Step 4: Commit the caller inventory**

```bash
git add scripts/audit-gear-catalog-callers.js tests/gear-catalog-callers-audit.test.js
git commit -m "feat(gear): inventory catalog callers"
```

## Task 5: Add the explicit Phase 0 CLI and resource baseline

**Files:**

- Create: `scripts/gear-catalog-migration-audit.py`
- Create: `tests/gear_catalog_migration_audit_cli_test.py`

**Interfaces:**

- CLI:

```text
python3 scripts/gear-catalog-migration-audit.py \
  --callers-json artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/caller-inventory.json \
  --output artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/runtime-readonly-audit.json \
  --statement-timeout-ms 15000 \
  --lock-timeout-ms 1000 \
  --batch-size 500
```

- Requires: `WOW_DATABASE_RUNTIME=postgres_only` and `WOW_DATABASE_URL`.
- Produces one bounded atomic JSON file and the same `reportId` on stdout.

- [ ] **Step 1: Write failing CLI tests**

Cover:

- missing PG-only runtime exits non-zero before connecting;
- output outside the current repository is rejected;
- caller JSON larger than 2 MiB is rejected before parsing;
- result larger than 8 MiB is rejected before replace;
- temporary output is removed on error or signal;
- the output path cannot overwrite requirement/evidence/manifest;
- fixed limits cannot exceed `statement_timeout=30000`, `batch_size=1000` or
  `sample_limit=20`;
- database URL is never present in stdout, stderr or report;
- a fake unchanged pointer yields a stable report ID;
- a fake changed pointer exits non-zero and does not leave an output file.

- [ ] **Step 2: Verify RED**

Run:

```bash
python3 -m unittest tests.gear_catalog_migration_audit_cli_test -v
```

Expected: FAIL because the CLI does not exist.

- [ ] **Step 3: Implement orchestration without runtime mutation**

The CLI must:

1. validate the environment and output path;
2. load the bounded caller report;
3. obtain a read-only store snapshot;
4. enumerate the exact 40 class/spec pairs from the existing backend-owned `WOW_CLASSES` matrix and
   call the current
   `PostgresCacheStore.get_websim_gear(class_key=class_key, spec_key=spec_key, compact=True, mode="initial")`
   reader
   through a query-counting, session-read-only connection wrapper;
5. immediately reduce each payload to class/spec, backend status, candidate count and blocker codes;
   never persist the full public payload in the report;
6. collect local filesystem facts with `os.statvfs()` only for explicitly named roots;
7. classify any unavailable historical peak RSS or temp-byte evidence as `unknown`;
8. call the pure audit module;
9. validate the report;
10. atomically write with `O_EXCL` temporary creation, `fsync`, size check and `os.replace`;
11. print only `{status, reportId, output}` with a repository-relative output path.

The 40-spec reader wrapper must record read/write statement counts independently from the audit
store, reject any write statement, and cap the aggregate read-query count at a value frozen by the
fixture baseline. It reuses the activity reader instead of reimplementing specialization relevance
rules in the audit.

Filesystem baseline must report:

```python
{
    "databaseRelationsBytes": 0,
    "activeMaterializationBytes": 0,
    "rollbackMaterializationBytes": 0,
    "diagnosticBytesObserved": 0,
    "filesystemTotalBytes": 0,
    "filesystemUsedBytes": 0,
    "filesystemFreeBytes": 0,
    "filesystemUsedPercent": 0.0,
    "peakRssObservedBytes": None,
    "temporaryBytesObserved": None,
}
```

Zeros are allowed only for measured empty sets. Missing measurements are `None` and generate
`RESOURCE_BASELINE_UNKNOWN` problems.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
python3 -m unittest \
  tests.gear_catalog_migration_audit_cli_test \
  tests.gear_catalog_migration_audit_test \
  tests.gear_catalog_audit_store_test -v
```

Expected: PASS.

- [ ] **Step 5: Commit the bounded CLI**

```bash
git add scripts/gear-catalog-migration-audit.py tests/gear_catalog_migration_audit_cli_test.py
git commit -m "feat(gear): add bounded catalog migration audit cli"
```

## Task 6: Run local and production read-only evidence

**Files:**

- Create:
  `artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/caller-inventory.json`
- Create:
  `artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/runtime-readonly-audit.json`
- Create:
  `artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/phase1-decision.json`

**Interfaces:**

- Consumes exact committed Phase 0 tool sources.
- Produces aggregate-only evidence; no raw personal data.

- [ ] **Step 1: Generate and validate the static caller inventory**

Run the caller tool through its explicit output option added during implementation; do not use shell
redirection for tracked artifacts.

Expected:

- active backend, Taro and compatibility caller categories are non-empty;
- test/docs categories do not affect runtime caller counts;
- every entry is repository-relative and content-addressed.

- [ ] **Step 2: Capture the active pointer before the audit**

Use the known cloud runtime in read-only mode. Record only:

```text
pointer generation
manifest revision
gear release ID
community release ID
dependency vector hash
runtime deployment identity
```

Do not print or persist the database URL. If the exact Phase 0 CLI cannot run against the current
production database without copying unreviewed code into the active service tree, stop and mark the
runtime audit `blocked`; do not substitute ad-hoc SQL.

- [ ] **Step 3: Run the bounded read-only audit**

The execution must use:

```text
WOW_DATABASE_RUNTIME=postgres_only
statement_timeout_ms=15000
lock_timeout_ms=1000
batch_size=500
```

Expected:

- query metrics show zero writes;
- pointer before/after identities are identical;
- report contains all five sections;
- template samples are anonymous hashes;
- unknown resource measurements remain explicit.

- [ ] **Step 4: Re-read runtime identity**

Re-read the active pointer and affected health components. Expected:

- pointer generation unchanged;
- Manifest and release IDs unchanged;
- no release event, template row, stat job or SimC task created by Phase 0;
- timers/backflow unchanged;
- `/api/data/health` is reported literally, including any pre-existing `partial` or `blocked`.

- [ ] **Step 5: Build the Phase 1 decision gate**

`phase1-decision.json` must contain:

```json
{
  "schemaRevision": "equipment-simulator-phase1-decision-v1",
  "status": "blocked",
  "inputs": {
    "auditReportId": "catalog-migration-audit:sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "callerReportId": "gear-catalog-callers:sha256:0000000000000000000000000000000000000000000000000000000000000000"
  },
  "gates": {
    "activeReleaseMapping": "blocked",
    "templateMigration": "blocked",
    "specCoverageBaseline": "blocked",
    "resourceBudgetInputs": "blocked",
    "callerRetirementInventory": "blocked"
  },
  "allowedNextPlan": "none",
  "problems": []
}
```

Allowed values are `ready`, `partial`, or `blocked` for the top-level status;
`pass`, `partial`, or `blocked` for gates that admit partial evidence; and
`contracts_only`, `schema_shadow`, or `none` for `allowedNextPlan`.

Rules:

- `activeReleaseMapping=pass` requires every active item/variant/option row to have a deterministic
  mapping or an explicit exclusion approved by the target scope;
- `templateMigration=pass` requires every template to be exact or explicitly classified
  draft-only/blocked without data substitution;
- `specCoverageBaseline=pass` requires 40/40 real spec rows with non-blocked candidate facts;
- `resourceBudgetInputs=pass` requires measured relation/materialization/disk values; peak RSS/temp
  may remain `partial`, but then `allowedNextPlan` cannot exceed `contracts_only`;
- unresolved runtime callers prevent `schema_shadow`.

- [ ] **Step 6: Commit only aggregate evidence**

Before adding files, scan for URLs with credentials, database URLs, user IDs, character names,
realms, raw profiles and tokens. If any are present, discard the report and fix the tool.

```bash
git add \
  artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/caller-inventory.json \
  artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/runtime-readonly-audit.json \
  artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/phase1-decision.json
git commit -m "evidence(gear): record catalog migration phase0 audit"
```

## Task 7: Record the Phase 0 control-plane result

**Files:**

- Modify: `docs/project-state.json`
- Modify: `docs/roadmap.md`
- Modify: `docs/plans/README.md`
- Modify: `docs/plans/2026-07-28-equipment-simulator-target-architecture.md`
- Modify: `docs/backend-owner-map.json`
- Modify: `tests/project-state.test.js`

**Interfaces:**

- Consumes the exact `phase1-decision.json`.
- Produces one current, non-historical Phase 0 contract and an explicit next-plan boundary.

- [ ] **Step 1: Update the owner map**

Register:

- pure classification owner;
- read-only projection owner;
- CLI orchestrator;
- caller inventory;
- characterization tests;
- zero runtime consumers.

Do not make Phase 0 the owner of release writes, template authorization, Resolver facts or SimC
profile generation.

- [ ] **Step 2: Update project state and plan whitelist**

`equipment_simulator_catalog_migration_phase0` becomes active with one of:

- `audit_verified_phase1_contracts_allowed`;
- `audit_partial_contracts_only`;
- `audit_blocked`.

The target architecture contract stays active. Do not mark the architecture or feature complete.
The roadmap link must point to the target architecture, this plan and the aggregate audit.

- [ ] **Step 3: Make control-plane tests GREEN**

Run:

```bash
node --test tests/project-state.test.js tests/project-harness.test.js
```

Expected: PASS; every active path exists, IDs are unique, and no historical execution plan is
reactivated.

- [ ] **Step 4: Commit the current-truth transition**

```bash
git add \
  docs/project-state.json \
  docs/roadmap.md \
  docs/plans/README.md \
  docs/plans/2026-07-28-equipment-simulator-target-architecture.md \
  docs/backend-owner-map.json \
  tests/project-state.test.js
git commit -m "docs(gear): record catalog migration phase0 result"
```

## Task 8: Complete verification and the Harness packet

**Files:**

- Create:
  `artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/evidence.json`
- Create:
  `artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/manifest.json`

**Interfaces:**

- Consumes exact final Phase 0 branch HEAD.
- Produces a complete task-scoped packet with no manual/runtime activation claim.

- [ ] **Step 1: Run focused verification**

```bash
python3 -m unittest \
  tests.gear_catalog_migration_audit_test \
  tests.gear_catalog_audit_store_test \
  tests.gear_catalog_migration_audit_cli_test \
  tests.gear_release_store_test \
  tests.postgres_personal_store_test -v
node --test \
  tests/gear-catalog-callers-audit.test.js \
  tests/project-state.test.js \
  tests/project-harness.test.js
```

Expected: PASS.

- [ ] **Step 2: Run the Harness profile**

```bash
node scripts/verify-project.js \
  --profile harness \
  --release artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0
```

Expected: PASS. Do not run frontend/full solely for this read-only tooling slice unless the final diff
expands into runtime or UI paths.

- [ ] **Step 3: Perform local CR**

Review the complete diff against:

- approved architecture;
- requirement;
- zero-write boundary;
- output bounds and redaction;
- report hash determinism;
- owner map;
- exact Phase 1 decision rules.

Any technically valid finding must be fixed and focused verification rerun.

- [ ] **Step 4: Build evidence and manifest**

`evidence.json` must record:

- exact verification HEAD;
- focused/Harness commands and results;
- caller/audit/decision report IDs;
- read-only query count and zero write count;
- pointer before/after identity equality;
- literal health/timer state;
- `runtimeIdentity.status=not_applicable_no_runtime_activation`;
- `manualAcceptance.required=false`, empty items and zero rollup;
- any remaining `partial`/`blocked` gate without promotion to success.

`manifest.json` must cross-bind the requirement/evidence paths and Harness v0.6.4.

- [ ] **Step 5: Validate the complete packet**

```bash
node scripts/project-harness.js --json \
  --check \
  --manifest artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/manifest.json \
  --evidence-file artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/evidence.json
```

Expected: exit `0`.

- [ ] **Step 6: Commit the final packet**

```bash
git add \
  artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/evidence.json \
  artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/manifest.json
git commit -m "chore(gear): close catalog migration phase0 packet"
```

## Exit Criteria and Next Plan Boundary

Phase 0 is complete only when:

1. active pointer before/after is identical and audit query metrics contain zero writes;
2. all four target-architecture unknowns have measured evidence or explicit `partial/blocked`;
3. report/caller identities are deterministic and aggregate-only;
4. current project state points to the exact Phase 0 result;
5. the complete task-scoped Harness packet passes.

The next plan is selected mechanically:

- `allowedNextPlan=contracts_only`: write a separate plan for pure
  `CatalogRevision`/`ItemDefinition`/`BrowseVariant`/Exact identity contracts; no schema.
- `allowedNextPlan=schema_shadow`: write separate plans for pure contracts and additive dormant
  schema/shadow readers; runtime cutover remains later.
- `allowedNextPlan=none`: stop and resolve the listed blocker. Do not hide it by designing a schema
  around missing evidence.

Phase 0 never directly authorizes a builder run, database migration, public API cutover, deployment or
Manifest pointer change.
