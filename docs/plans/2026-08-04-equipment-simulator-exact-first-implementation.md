# 装备模拟 Exact-first 与三来源 Catalog 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

状态：`待决策（Task 1-2 scoped clean；whole-branch review FAIL / 1 Important；重复 effect subject 语义纠偏中；旧 Task 2 已停止，原 Task 3 未启动）`

**Task 2 replacement:** [Canonical Kernel 重设计](2026-08-04-equipment-simulator-canonical-kernel-redesign.md)、[Canonical Ownership Change-Control Plan](2026-08-04-equipment-simulator-canonical-owner-change-control.md) 与 [重复 Effect Subject 语义纠偏](2026-08-04-equipment-simulator-duplicate-effect-subject-correction.md)。原 Task 2 不再执行；Task 1-2 scoped reviews 已 PASS/APPROVED，但 fresh whole-branch review 因一项 effect ordered-multiset 语义缺口而 FAIL。纠偏 scoped review 与新的 whole-branch review 全部 clean 后，才允许进入本计划 Task 3。

**Goal:** 让完整、合法且被当前 SimC runtime 明确支持的精确装备，即使不在 Catalog 中，也能确定性保存、重载、生成不可变快照并模拟；同时把模拟器可换装 Catalog 收敛为大秘境、团本和制造三个来源内、可物化为 SimC-ready Exact 的受治理子集。

**Architecture:** 保留 `selection-intent-v1`、generation 35 和全部 v1 封存行；新增 Catalog-independent 的 `exact-loadout-intent-v2`、内容寻址的 `ExactAuthorityEnvelope`、三态 effect-support 预检和 v2 ResolvedLoadout/SimulationSnapshot。Observation 只异步收集已去身份化的 ready/unlisted Exact，Catalog 只通过候选构建、硬门禁、不可变 revision 和 CAS 发布。前端只消费后端的正交 `simulationStatus`/`catalogStatus`，不推断装备事实或效果支持。

**Tech Stack:** Python 3 `unittest`、PostgreSQL migrations/store、现有 SimC 子进程封装、TypeScript domain/API client、React/Taro/Vitest、Harness Strict release packet 与真实微信验收。

## Global Constraints

- 这是 Strict 任务。开始执行前建立本任务 Harness requirement/release packet；每个 release slice 都必须有独立 RED/GREEN、回归、回滚和停止结论。
- 不修改、重写或重新解释 generation 35、Phase 0-4、26/14 矩阵和既有 v1 快照证据。`selection-intent-v1`、`resolved-loadout-v1`、`simulation-snapshot-v1` 继续可读、可校验、可重放。
- 插件导出是“要模拟什么”的可编辑输入，不证明账号实际拥有装备。原始导出只允许存在于请求内存和前端当前输入框，不写模板、日志、队列、数据库或证据包。
- Exact 主链不得读取 Catalog membership 来决定可模拟性；`originCatalogRevision` 只能作为 canonical payload/hash 之外的 provenance 保存。
- `effectSupport=unknown|unsupported` 必须在创建正式 SimC 任务前阻断。SimC 解析成功、退出码为零或产生 DPS 都不能自动把动态效果提升为 `verified`。
- Observation 写入失败不能阻断 ready Exact 模拟；请求路径只能写幂等 observation event，不能写 staging、candidate、active Catalog 或 Manifest 指针。
- Catalog 首期只接纳 `mythic_plus|raid|crafted`。观察频率只改变调查优先级，不能形成来源、赛季、variant 或效果支持事实。
- 迁移文件固定为 `0026_websim_exact_first_authority.sql` 和 `0027_websim_exact_observation.sql`。执行前若任一路径已被其他主干迁移占用，停止该 slice，先同步主干并在本计划与 `docs/plans/README.md` 中原子改为后续连续编号；不得静默复用编号。
- 不在同一发布窗口触发赛季全量 Universe 回填、异步 Catalog backflow 或其他无关数据同步。候选部署默认保持 `WOW_DEPLOY_START_ASYNC_SYNCS=0`。
- 每次 commit 只包含当前 Task 的文件；提交前运行 `git diff --check` 并确认没有无关用户改动。

## Release Slice 1：Catalog-independent Exact 模拟主链

完成条件：一套 Catalog 外的完整合法装备能得到 owner-scoped 导入结果、v2 ResolvedLoadout、v2 SimulationSnapshot 和真实 SimC 终态；缺字段、非法组合和 effect-support 缺口在任务创建前分别 fail closed；v1 身份与重放完全不漂移。

### Task 1: 冻结 v1 兼容基线并引入 Exact v2 输入合同

**Files:**

- Create: `artifacts/releases/2026-08-04-equipment-simulator-exact-first/requirement.json`
- Create: `server/simc_gear_import.py`
- Create: `tests/simc_gear_import_test.py`
- Modify: `server/news_backend.py`
- Modify: `tests/news_backend_test.py`
- Modify: `server/gear_contracts.py`
- Modify: `tests/gear_contracts_test.py`
- Modify: `packages/domain/src/entities.ts`
- Modify: `packages/domain/src/gear-intent.ts`
- Modify: `packages/domain/src/gear-intent.test.ts`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/backend-owner-map.json`

**Contract:**

```python
EXACT_LOADOUT_INTENT_SCHEMA_REVISION = "exact-loadout-intent-v2"

def parse_simc_exact_import(
    raw_profile: object,
    *,
    class_key: str,
    spec_key: str,
    level: int,
    season_revision: str,
    game_build: str,
) -> dict[str, object]:
    """Return exact-import-parse-v1 with status parsed|blocked and no raw text."""
```

成功 payload 必须严格为：

```json
{
  "schemaRevision": "exact-import-parse-v1",
  "status": "parsed",
  "intent": {
    "schemaRevision": "exact-loadout-intent-v2",
    "authoredAgainst": {"seasonRevision": "season-revision-fixture-v1", "gameBuild": "game-build-fixture-v1"},
    "eligibilityContext": {"classKey": "warrior", "specKey": "fury", "level": 80},
    "slots": {
      "head": {
        "itemId": "225574",
        "declaredItemLevel": null,
        "bonusIds": [],
        "context": "",
        "gemIds": [],
        "gemBonusIds": [],
        "gemItemLevels": [],
        "enchantId": "",
        "craftedStats": [],
        "embellishmentIds": [],
        "redirectedBaseStats": []
      }
    }
  },
  "problems": []
}
```

- [ ] 写入 Harness requirement：四个 release slice、用户可见验收、数据/隐私边界、候选部署、回滚和“真实微信未验收不得完成”的关闭条件。
- [ ] 在 `tests/simc_gear_import_test.py` 写 RED：从完整 SimulationCraft 插件导出中只提取 15 个核心槽与可选 off-hand，安全忽略已知 character/talent/scenario 行；多 character section、raw class/spec 冲突、重复/未知 slot、未知 gear option、错位 gem 辅助数组、超过 65,536 UTF-8 bytes、换行注入、缺 `id` 均返回具体 `path`。插件未声明 `ilevel` 时保留 `declaredItemLevel=null`，不在 parser 中补值；bonus/context 可显式为空，是否足以建立 Exact 由 authority worker 裁决。
- [ ] 在 `tests/gear_contracts_test.py` 写 RED：v2 不含 `gearCatalogRevision`/`variantKey`；出现这两个字段必须报 `UNKNOWN_FIELD`；v1 原样继续通过。
- [ ] 在 `packages/domain/src/gear-intent.test.ts` 写 RED：`canonicalExactLoadoutIntent` 只接受完全相同的 key set、15 个核心槽与可选 off-hand、canonical slot 顺序、有限整数/标识符和 class/spec identity；off-hand 最终合法性仍由整套 Resolver 裁决。
- [ ] 运行 `python3 -m unittest tests.simc_gear_import_test tests.gear_contracts_test`，确认因模块/常量缺失失败；运行 `npm exec vitest run packages/domain/src/gear-intent.test.ts`，确认因 `canonicalExactLoadoutIntent` 缺失失败。
- [ ] 从 `server/news_backend.py` 的 `parse_simcraft_template_gear_line`/`parse_simcraft_template_gear_raw` 提取纯解析逻辑到 `server/simc_gear_import.py`；原函数改为薄兼容 wrapper，避免第二套 SimC 行解析器。
- [ ] 在 Python/TypeScript 合同中实现严格 v2 canonicalization；不补最高 variant、默认装等、相似 bonus 或 Catalog metadata。
- [ ] 添加冻结断言：已知 v1 intent、ResolvedLoadout 和 SimulationSnapshot 的 canonical bytes/key 与当前 main fixture 完全相同。
- [ ] 运行上述 Python/Vitest 命令，预期全部通过；再运行 `python3 -m unittest tests.news_backend_test.NewsBackendTest.test_simcraft_template_canonical_context_uses_server_owned_snapshot_for_confirm_and_final_without_legacy_fallback`，预期现有 v1 canonical path 通过。
- [ ] 运行 `git diff --check`，提交 `feat(websim): add catalog-independent exact intent contract`。

### Task 2: 拆分 Catalog-independent Exact identity 与三态效果支持

**Files:**

- Modify: `server/gear_exact_item_instance.py`
- Modify: `tests/gear_exact_item_instance_test.py`
- Create: `server/simc_item_effect_support.py`
- Create: `tests/simc_item_effect_support_test.py`
- Create: `server/simc_item_effect_probe.py`
- Create: `tests/simc_item_effect_probe_test.py`
- Create: `scripts/simc-item-effect-probe.py`
- Create: `tests/simc_item_effect_probe_cli_test.py`
- Create: `server/gear_exact_authority.py`
- Create: `tests/gear_exact_authority_test.py`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/backend-owner-map.json`

**Interfaces:**

```python
def build_exact_item_identity(
    binding: object,
    exact_row: object,
    *,
    enhancement_selection: object = None,
) -> dict[str, object]:
    """Build gear-exact-item-instance-v2 without catalog membership."""

def resolve_exact_item_effect_support(
    exact_item: object,
    *,
    runtime_revision: str,
    support_records: object,
) -> dict[str, object]:
    """Aggregate item/gem/enchant/embellishment/crafted-effect subjects."""

def build_exact_authority_envelope(
    *,
    exact_item: object,
    static_facts: object,
    serializer_input: object,
    progression_binding: object,
    effect_support: object,
    resolver_revision: str,
) -> dict[str, object]:
    """Return one immutable exact-authority-envelope-v1."""
```

效果支持的 subject 固定为 `item|gem|enchant|embellishment|crafted_effect|set_bonus`。ExactItemEnvelope 聚合前五类；整套 Resolver 另外聚合 `set_bonus` 和其他跨槽效果。动态效果 probe manifest 必须显式提供 subject kind/key、subject variant signature、固定 runtime、`on_use|proc|buff` 类型、预期 report action/buff tokens 和一个 control snapshot key。Probe 只有在实验组出现全部预期 token、control 不出现这些 token、两者均无 item-resolution warning 时才能生成 `verified` record；只有普通 DPS 输出或成功退出仍返回 `unknown`。

- [ ] 在 `tests/gear_exact_item_instance_test.py` 写 RED：同一 Exact 字段在 listed/unlisted 情况得到同一 v2 identity；不同 itemLevel、bonusIds、context、gems、enchant、craftedStats、embellishments、redirectedBaseStats 任一变化都改变 identity。
- [ ] 写 RED：`build_exact_item_instance(binding, row, catalog_revision=catalog_revision)` 的 v1 bytes/key 不变，确保旧 registry builder 不被隐式切换。
- [ ] 在 `tests/simc_item_effect_support_test.py` 写 RED：base item、每颗 gem、enchant、embellishment 和 crafted effect 分别枚举 subject；每个 subject 只有明确“无动态效果”的 authority 才是静态 `verified`，动态效果只有 runtime-bound governed record/probe 为 `verified`；任一缺记录聚合为 `unknown`，任一明确未实现聚合为 `unsupported`，runtime revision 不匹配降为 `unknown`。
- [ ] 在 probe tests 写 RED：manifest key 白名单、固定 runtime、实验/对照 snapshot identity、预期 action/buff tokens、item-resolution warning、timeout 和 token 缺失；只有完整差分证据生成可 seal record，单纯 DPS 差异或退出码零不能通过。
- [ ] 在 `tests/gear_exact_authority_test.py` 写 RED：envelope 内容寻址、字段严格、绑定 exact item/static facts/serializer/rule/runtime/effect record；`unknown|unsupported` 不能返回 ready envelope。
- [ ] 运行 `python3 -m unittest tests.gear_exact_item_instance_test tests.simc_item_effect_support_test tests.simc_item_effect_probe_test tests.simc_item_effect_probe_cli_test tests.gear_exact_authority_test`，确认新接口缺失导致 RED。
- [ ] 把当前 `build_exact_item_instance` 内不依赖 Catalog 的 canonical identity 抽成 `build_exact_item_identity`；保留 v1 wrapper 的 `CATALOG_REVISION_PATTERN` 与输出不变。
- [ ] 实现 effect support：静态判定必须消费显式 `hasDynamicEffect=false` authority；动态 record 必须绑定 subject kind/key、subject variant signature、`simcRuntimeRevision`、probe/record identity 和 `verifiedAt`，不接受进程退出码字段作为证据。
- [ ] 实现 pure probe evaluator 和薄 CLI；CLI 只接受本地 manifest/snapshot 文件与当前 SimC runtime，不联网、不写 Catalog，只向 stdout 输出通过 evaluator 的 canonical support record JSON，后续由 Task 3 store ingestion 校验并封存。
- [ ] 实现 ExactAuthorityEnvelope；key 格式固定 `exact-authority:sha256:<64 hex>`，canonical payload 不包含 owner、Catalog 或观察计数。
- [ ] 运行 Task 2 Python 测试，预期全部通过；再运行 `python3 -m unittest tests.gear_track_authority_test tests.gear_exact_item_registry_test`，预期 v1 回归通过。
- [ ] 运行 `git diff --check`，提交 `feat(websim): add exact authority and effect support`。

### Task 3: 添加 append-only authority/store 与 v1/v2 条件持久化

**Files:**

- Create: `server/migrations/postgres/0026_websim_exact_first_authority.sql`
- Modify: `tests/postgres_shadow_migration_test.py`
- Create: `server/gear_exact_authority_store.py`
- Create: `tests/gear_exact_authority_store_test.py`
- Modify: `server/simulation_snapshot_store.py`
- Modify: `tests/simulation_snapshot_store_test.py`
- Modify: `server/postgres_cache_store.py`
- Modify: `tests/postgres_cache_store_test.py`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/backend-owner-map.json`

**Schema:**

```sql
CREATE TABLE cache.websim_gear_exact_authority_envelopes (
    exact_authority_envelope_key text PRIMARY KEY,
    schema_revision text NOT NULL CHECK (schema_revision = 'exact-authority-envelope-v1'),
    exact_item_instance_key text NOT NULL,
    gear_rule_revision text NOT NULL,
    simc_runtime_revision text NOT NULL,
    effect_support_status text NOT NULL CHECK (effect_support_status = 'verified'),
    envelope_json jsonb NOT NULL CHECK (octet_length(envelope_json::text) <= 1048576),
    row_hash text NOT NULL CHECK (row_hash ~ '^sha256:[0-9a-f]{64}$'),
    sealed_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE cache.websim_simc_item_effect_support_records (
    effect_support_record_key text PRIMARY KEY CHECK (effect_support_record_key ~ '^effect-support:sha256:[0-9a-f]{64}$'),
    schema_revision text NOT NULL CHECK (schema_revision = 'simc-item-effect-support-record-v1'),
    subject_kind text NOT NULL CHECK (subject_kind IN ('item','gem','enchant','embellishment','crafted_effect','set_bonus')),
    subject_key text NOT NULL,
    subject_variant_signature text NOT NULL,
    simc_runtime_revision text NOT NULL,
    support_status text NOT NULL CHECK (support_status IN ('verified','unsupported')),
    evidence_json jsonb NOT NULL CHECK (octet_length(evidence_json::text) <= 262144),
    row_hash text NOT NULL CHECK (row_hash ~ '^sha256:[0-9a-f]{64}$'),
    sealed_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ops.websim_exact_import_jobs (
    exact_import_job_key text PRIMARY KEY CHECK (exact_import_job_key ~ '^exact-import-job:[0-9a-f]{32}$'),
    owner_key_hash text NOT NULL CHECK (owner_key_hash ~ '^sha256:[0-9a-f]{64}$'),
    request_hash text NOT NULL CHECK (request_hash ~ '^sha256:[0-9a-f]{64}$'),
    status text NOT NULL CHECK (status IN ('pending','running','resolved','blocked','unsupported','failed')),
    sanitized_intent_json jsonb NOT NULL CHECK (octet_length(sanitized_intent_json::text) <= 1048576),
    result_json jsonb CHECK (result_json IS NULL OR octet_length(result_json::text) <= 1048576),
    attempt integer NOT NULL DEFAULT 0 CHECK (attempt BETWEEN 0 AND 3),
    locked_by text NOT NULL DEFAULT '',
    lock_token text NOT NULL DEFAULT '',
    lease_until timestamptz,
    heartbeat_at timestamptz,
    problem_json jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (octet_length(problem_json::text) <= 16384),
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (
        (status = 'running' AND locked_by <> '' AND lock_token <> '' AND lease_until IS NOT NULL)
        OR (status <> 'running' AND lease_until IS NULL)
    )
);

CREATE UNIQUE INDEX idx_ops_websim_exact_import_idempotent
ON ops.websim_exact_import_jobs (owner_key_hash, request_hash)
WHERE status IN ('pending','running','resolved','blocked','unsupported');
```

同一 migration 还必须：

- 创建 `ops.websim_exact_authority_worker_state`，字段与现有 gear stat worker state 对齐，独立记录 worker/runtime/current job/heartbeat/last outcome。
- 创建按 UTC 日和 terminal classification 聚合的 `ops.websim_exact_import_metrics_daily`；只保存日期、`resolved|incomplete|illegal|runtime_gap|internal_error`、catalog status 和计数，不保存 owner/item/loadout。
- 创建每次最多删除 100 条的 `ops.prune_websim_exact_import_jobs(batch_limit integer)` 与 `ops.prune_websim_exact_import_metrics(batch_limit integer)` fenced functions；只向 worker 角色授予 `EXECUTE`，不向应用角色授予底表 `DELETE`。terminal job 保留期固定 7 天，daily metrics 保留 90 天。
- 给 `cache.websim_gear_resolved_loadouts` 增加 `exact_authority_envelope_keys_json` 和非 canonical `origin_catalog_revision`，将 `catalog_revision`/`exact_registry_revision` 改为可空，并增加 schema-conditioned check：v1 两列必填且 envelope keys 为空；v2 Catalog/registry 为空且 envelope keys 为非空 JSON array。
- 给 `cache.websim_simulation_snapshots` 增加 `exact_authority_envelope_keys_json` 和非 canonical `origin_catalog_revision`，将 `catalog_revision` 改为可空，并增加同类 v1/v2 check。
- 保留原外键；PostgreSQL nullable FK 只在非空时约束，因此 v1 仍受原 Catalog FK 保护。
- 不 UPDATE 任何历史行，不重算 row hash，不修改 append-only trigger。

- [ ] 运行 `test ! -e server/migrations/postgres/0026_websim_exact_first_authority.sql`；若失败，按 Global Constraints 停止并处理编号冲突。
- [ ] 在 migration tests 写 RED：全新 schema 和从 0025 升级均成功；v1 行仍要求 Catalog/registry；v2 行必须有 envelope keys 且 Catalog 为空；历史 v1 row hash 不改变；直接 UPDATE/DELETE 仍失败。
- [ ] 在 authority store tests 写 RED：内容相同幂等插入、内容冲突拒绝、只返回 `verified` envelope、按 exact key 批量读取不混 runtime/rule revision；effect-support record append-only、runtime-bound，缺记录时明确返回 `unknown`。
- [ ] 在 snapshot store tests 写 RED：v1 round-trip 不变；v2 能以 envelope keys round-trip；`originCatalogRevision` 不进入 row hash/snapshot key；v1/v2 混合字段 fail closed。
- [ ] 写 RED：terminal job 七天后才可由 fenced function 以每批最多 100 条清理；pending/running 永不被清理；daily metrics 不含 owner/item 字段且只保留 90 天。
- [ ] 运行 `python3 -m unittest tests.postgres_shadow_migration_test tests.gear_exact_authority_store_test tests.simulation_snapshot_store_test`，确认 RED。
- [ ] 编写 0026 migration，末尾写入唯一 `ops.schema_migrations` identity；按 `docs/postgres-identity-migration-runbook.md` 的 lexicographic SQL 路径验证从 0001 到 0026 顺序应用。
- [ ] 实现 `GearExactAuthorityStore` 和 owner-filtered exact import job CRUD；所有 job 读取/更新都要求 `owner_key_hash`，不提供只凭 job key 的公开读取方法；request hash 绑定 sanitized intent、season/game build、Rule/Resolver/worker/SimC runtime revisions；claim 使用三次尝试上限、30 秒 lease、heartbeat 和 lock token fencing。pending/确定性终态幂等复用，failed 在 cooldown 后允许新 job 重试。
- [ ] 扩展 snapshot store 的 schema 分支；canonical hash 只消费 v2 payload 中的 envelope identities，排除 provenance。
- [ ] 运行 Task 3 测试，预期全部通过；再运行 `python3 -m unittest tests.gear_exact_item_registry_store_test tests.simulation_snapshot_compat_test`，预期 v1 兼容通过。
- [ ] 运行 `git diff --check`，提交 `feat(websim): persist exact authority and v2 snapshots`。

### Task 4: 建立 owner-scoped 异步 Exact Authority 解析任务

**Files:**

- Create: `server/gear_exact_authority_worker.py`
- Create: `tests/gear_exact_authority_worker_test.py`
- Create: `server/wow-gear-exact-authority-worker.service`
- Modify: `server/websim_payload.py`
- Modify: `tests/websim_payload_test.py`
- Modify: `server/simc_preparation.py` only to expose an existing bounded server-owned preparation preset; do not add client-authored preparation lines.
- Modify: `server/deploy_lighthouse.sh`
- Modify: `tests/deploy_lighthouse_test.py`
- Modify: `docs/project-owner-map.json`
- Modify: `server/news_backend.py` and `tests/news_backend_test.py` only for the worker health component; the public endpoint remains Task 6.
- Modify: `docs/backend-owner-map.json`

**Worker result:**

```json
{
  "schemaRevision": "exact-import-envelope-v1",
  "status": "resolved",
  "simulationStatus": "ready",
  "catalogStatus": "unlisted",
  "exactLoadoutIntentKey": "exact-loadout-intent:sha256:0000000000000000000000000000000000000000000000000000000000000000",
  "exactAuthorityEnvelopeKeys": ["exact-authority:sha256:0000000000000000000000000000000000000000000000000000000000000000"],
  "resolvedLoadoutKey": "resolved-loadout:sha256:0000000000000000000000000000000000000000000000000000000000000000",
  "problems": []
}
```

- [ ] 写 RED：worker 只接收 sanitized v2 intent；从 verified class/spec/scenario preset 重建有界 profile；不把 raw profile 传入 store、logger 或 result。
- [ ] 写 RED：同 owner+requestHash+dependency revisions 幂等；不同 owner 不可读取；pending/确定性终态重试不重复创建；failed 在 cooldown 后生成新 job；runtime/rule revision 改变生成新 request identity；同一 ExactAuthorityEnvelope 可跨 owner 内容复用但 job/result 仍隔离。
- [ ] 写 RED：SimC 返回的逐槽 `id/bonus_id/context/gem/enchant/crafted/embellishment` 必须与输入已声明 canonical values 精确一致；`ilevel` 在输入已声明时也必须一致，未声明时只能由绑定 runtime/progression authority 解析并写入 envelope。缺槽、冲突或无法解析正 itemLevel 返回具体 blocked problem，不能用输出覆盖用户已声明选择。
- [ ] 写 RED：authority run 可以从完整 SimC `bonus_id/context` 语义解析正 itemLevel 和静态 facts；只验证输入中明确声明的 `declaredItemLevel`，不以 SimC 输出覆盖相冲突的声明或选择项。authority 仍无法得到正 itemLevel/完整语义时 blocked。
- [ ] 写 RED：static facts authority 不完整为 blocked；effect support unknown 为 unsupported；SimC timeout/crash 在三次 fenced 尝试后为 failed；这些状态都没有 ready envelope keys。
- [ ] 写 RED：worker state heartbeat、runtime revision 和 current job 可由 `/api/data/health` 的独立 component 读取；worker 过期必须 literal blocked，不能由 backend liveness 代替。
- [ ] 运行 `python3 -m unittest tests.gear_exact_authority_worker_test tests.websim_payload_test`，确认 RED。
- [ ] 复用 `run_websim_simcraft_process`、`simc_json_gear_stats_by_slot` 和 `simc_observed_variant_stat_payload` 的受控执行/结果提取边界；不得复制 subprocess 调用或使用 `gear_item_level_stat_probe.py` 的 11x4 特化报告路径。
- [ ] 实现 worker 的 `claim -> reconstruct -> run -> compare -> effect preflight -> seal -> terminalize`；terminal write 使用 compare-and-set，重复 worker 不覆盖已完成终态；每分钟最多调用一次两个 bounded prune functions。
- [ ] 将日志限制为 job key、owner hash、状态、problem codes、duration 和 SimC runtime identity；测试断言原始 item lines/角色名/服务器名不出现。
- [ ] 添加单 child systemd service，沿用 stat snapshot worker 的 `NoNewPrivileges`/`PrivateTmp`/`ProtectSystem`/资源上限模式；部署脚本安装、enable、restart 并回读 active/heartbeat；`tests/deploy_lighthouse_test.py` 验证 unit 与 deploy wiring，owner map 登记新 worker/store/migration/API owner。
- [ ] 运行 Task 4 测试，预期全部通过；再运行 `python3 -m unittest tests.simc_fixedint_test tests.simc_execution_matrix_test`，预期现有 SimC 边界回归通过。
- [ ] 运行 `git diff --check`，提交 `feat(websim): resolve exact authority asynchronously`。

### Task 5: 引入 v2 Resolver、ResolvedLoadout 和 SimulationSnapshot

**Files:**

- Modify: `server/gear_resolver.py`
- Modify: `tests/gear_resolver_test.py`
- Modify: `server/gear_rule_matrix.py`
- Modify: `tests/gear_rule_matrix_test.py`
- Modify: `server/gear_resolved_loadout.py`
- Modify: `tests/gear_resolved_loadout_test.py`
- Modify: `server/simulation_snapshot.py`
- Modify: `tests/simulation_snapshot_test.py`
- Modify: `server/simulation_snapshot_compat.py`
- Modify: `tests/simulation_snapshot_compat_test.py`

**v2 identity dependency vector:**

```json
{
  "seasonRevision": "season-revision-fixture-v1",
  "gameBuild": "game-build-fixture-v1",
  "gearRuleRevision": "gear-rule-revision-fixture-v1",
  "exactAuthorityEnvelopeKeys": ["exact-authority:sha256:0000000000000000000000000000000000000000000000000000000000000000"],
  "loadoutEffectSupportRecordKeys": ["effect-support:sha256:0000000000000000000000000000000000000000000000000000000000000000"],
  "resolverRevision": "gear-resolver-v2",
  "compilerRevision": "simulation-compiler-v2",
  "simcRuntimeRevision": "simc-runtime-fixture-v1"
}
```

- [ ] 在 Resolver tests 写 RED：v2 intent 不要求 Catalog authority；仍完整裁决 class/spec/slot/weapon hand/unique/gems/enchants/embellishment/crafting/catalyst/tier/cross-slot aggregate；非法组合返回规则问题而非 Catalog 缺失。
- [ ] 写 RED：每个 v2 slot 必须精确匹配一个 verified ExactAuthorityEnvelope；缺失、重复、rule/runtime revision 不一致均 blocked；不允许用同 itemId 的其他 envelope 替代。
- [ ] 写 RED：Resolver 根据已裁决的 tier/set/cross-slot aggregate 枚举 `set_bonus` 等 loadout-level effect subjects；全部 runtime-bound records verified 才能 ready，任一 unknown/unsupported 在 snapshot/task 前阻断。
- [ ] 在 ResolvedLoadout tests 写 RED：`resolved-loadout-v2` key 由完整 canonical loadout + envelope keys + Rule/Resolver revisions 形成，不含 Catalog；修改 `originCatalogRevision` 不改变 key。
- [ ] 在 SimulationSnapshot tests 写 RED：`simulation-snapshot-v2` 绑定 v2 loadout、talent、compiler、runtime；effect support 非 verified 无法编译；相同输入字节一致；Catalog 晋升后 key 不变。
- [ ] 写兼容 RED：v1 verifier/reader 仍只接受 v1 结构；v2 verifier 不放宽 v1；历史 v1 fixtures 的 key/hash 原样通过。
- [ ] 运行 `python3 -m unittest tests.gear_resolver_test tests.gear_rule_matrix_test tests.gear_resolved_loadout_test tests.simulation_snapshot_test tests.simulation_snapshot_compat_test`，确认 RED。
- [ ] 在 `gear_resolver.py` 按 schema revision 路由 v1/v2 authority adapter，但让两者调用同一个 `gear_rule_matrix.py` 整套规则引擎；禁止复制规则矩阵。
- [ ] 在 `gear_resolved_loadout.py` 新增 `build_resolved_loadout_v2`/`verify_resolved_loadout_v2`，serializer input 必须来自 envelope，不读取 Catalog 或前端拼装字段。
- [ ] 在 `simulation_snapshot.py` 新增 v2 builder/verifier；compiler 继续复用固定 `SIMC_OPTION_ORDER`，并在编译前验证全部 envelope 和 loadout-level effect support 为 `verified`。
- [ ] 运行 Task 5 测试，预期全部通过；再运行 `python3 -m unittest tests.gear_resolved_snapshot_shadow_test tests.gear_exact_template_options_test`，预期 v1 路径不变。
- [ ] 运行 `git diff --check`，提交 `feat(websim): resolve exact-first loadouts and snapshots`。

### Task 6: 暴露 Exact import API 并接入正式 SimC 提交

**Files:**

- Modify: `server/news_backend.py`
- Modify: `tests/news_backend_test.py`
- Modify: `server/postgres_cache_store.py`
- Modify: `tests/postgres_cache_store_test.py`
- Create: `server/gear_exact_metrics.py`
- Create: `tests/gear_exact_metrics_test.py`
- Modify: `server/simc_support_policy.py` only to add the v2 pre-task decision; retain existing scenario/spec support rules.
- Modify: `tests/simulation_snapshot_store_test.py`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/backend-owner-map.json`

**HTTP contract:**

```text
POST /api/websim/gear/exact-import
Content-Type: application/json

{
  "rawProfile": "warrior=fixture\nspec=fury\nhead=,id=225574,bonus_id=10356/10390",
  "classKey": "warrior",
  "specKey": "fury",
  "level": 80,
  "guestId": "guest-fixture-01"
}
```

返回 `exact-import-envelope-v1`，HTTP 语义为：

- `202 pending`：含稳定 `jobKey` 与 `retryAfterMs=1000`。
- `200 resolved|blocked|unsupported`：终态可重放。
- `400 blocked`：请求/解析结构错误，含 field path。
- `401/403`：owner 不成立或跨 owner job 读取。
- `503 failed`：受控内部/runtime 故障；不得包装为 partial success。

- [ ] 写 RED：认证用户和 guest simulator user 都形成稳定 owner；相同 owner 重复 POST 轮询同 job；跨 owner 不可见；response 不回显 rawProfile。
- [ ] 写 RED：pending 不创建 simulation task；blocked/unsupported 不调用 runner；resolved v2 snapshot 才能进入现有 `/api/websim/simulate`，且 runner 只消费封存 snapshot key。
- [ ] 写 RED：Catalog 外完整装备返回 `ready+unlisted`；来源外完整装备返回 `ready+out_of_scope`；Catalog 查询/queue 故障不改变 simulationStatus。
- [ ] 写 RED：请求处理期间 Catalog revision/staging/candidate/Manifest store 的写方法调用次数为零；仅 exact job、authority envelope、sealed loadout/snapshot 和 observation hook 可写。
- [ ] 写 RED：复用现有 Web gear request limiter；同 owner 同时最多一个 active import，global queued/running 上限 1,000，超过上限返回 literal 429/503 capacity problem，不启动后台线程绕过 worker。
- [ ] 在 `tests/gear_exact_metrics_test.py` 写 RED：按 UTC 窗口输出 `exact_sim_success_rate`，denominator 只含语法有效终态，并分别计数 incomplete、illegal、runtime_gap、internal_error；输出 `unlisted_but_simulatable_rate`，零 denominator 返回 `blocked` 而非 `0%`。
- [ ] 写 RED：`/api/data/health` 的 Exact component 只发布聚合窗口、literal rate/status 和 worker freshness，不发布 owner、item 或 loadout；worker fresh 不能覆盖业务指标 `partial|blocked`。
- [ ] 写 RED：`/api/me/build-templates` 只保存 `rawString=exact-loadout-intent:sha256:<hash>`、canonical `metadata.exactLoadoutIntent`、v2 snapshot key 和两类状态；拒绝把 original `rawProfile`/item lines 写入模板。重载必须 owner-isolated，并验证 intent hash、sealed snapshot 与当前记录一致。
- [ ] 运行精确的 `tests.news_backend_test` 新测试与 `tests.postgres_cache_store_test` 新测试，确认 RED；不要在本步骤运行整个大型文件来掩盖目标失败。
- [ ] 实现 endpoint，先做 65,536-byte、JSON key 白名单和容量校验，再调用纯 parser；rawProfile 在 request handler 返回前释放，不能进入 job payload。`seasonRevision`/`gameBuild` 只能由 active server authority 注入 parser，不能接受客户端字段。
- [ ] 将 resolved job 接入 v2 resolver/loadout/snapshot sealer；正式 SimC task gate 同时要求 snapshot v2 verified、runtime identity 一致和全部 effect support verified。
- [ ] 扩展 build-template normalizer/readiness：exact v2 只从 canonical metadata 和 sealed snapshot 恢复，`rawString` 仅保存 intent identity；legacy gear raw path 不读取或降级解析 v2 模板。
- [ ] 加入 bounded `retryAfterMs=1000`，不暴露 worker stack、SimC stdout 或数据库错误；所有 problem 都含稳定 `code/path/recoveryAction`。
- [ ] 运行新增 API tests，预期全部通过；运行 `python3 -m unittest tests.gear_contracts_test tests.gear_resolver_test tests.gear_resolved_loadout_test tests.simulation_snapshot_test tests.simulation_snapshot_store_test tests.news_backend_test`，预期全量相关 Python 回归通过。
- [ ] 运行 `git diff --check`，提交 `feat(websim): expose exact-first import and simulation`。

### Slice 1 停止门禁

- [ ] 保存三组字节级证据：v1 历史 fixture 无漂移、同一 v2 canonical input/key/profile 可复现、改变任一 Exact 字段必改变 identity。
- [ ] 用受控 Catalog 外 fixture 跑通 API `pending -> ready+unlisted -> v2 snapshot -> completed result`；结果必须来自实际 SimC runner，不接受 mock 作为 slice 关闭证据。
- [ ] 证明 incomplete、illegal、unknown effect、unsupported effect 在 SimC task 创建前分别阻断，且问题对象/字段/恢复动作可见。
- [ ] 记录 `historical_snapshot_identity_drift=0`、`silent_default_fill_count=0`、`mixed_revision_read_count=0`。
- [ ] 本门禁任一项不通过，停止；不得开始 Observation/Catalog/UI，也不得修改活动 Manifest。

## Release Slice 2：隔离 Observation Queue

### Task 7: 记录去身份化、幂等、有界的 Exact 观察

**Files:**

- Create: `server/migrations/postgres/0027_websim_exact_observation.sql`
- Create: `server/gear_exact_observation.py`
- Create: `tests/gear_exact_observation_test.py`
- Create: `server/gear_exact_observation_store.py`
- Create: `tests/gear_exact_observation_store_test.py`
- Modify: `server/news_backend.py`
- Modify: `tests/news_backend_test.py`
- Modify: `tests/postgres_shadow_migration_test.py`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/backend-owner-map.json`

**Canonical observation identity:**

```python
observation_key = sha256({
    "seasonRevision": season_revision,
    "gameBuild": game_build,
    "itemId": item_id,
    "catalogDiscoverySignature": catalog_discovery_signature,
})
```

`catalogDiscoverySignature` 只绑定 itemLevel、bonusIds、context 和 progression state；明确排除宝石、附魔、制造副属性和装饰选择，避免用玩家强化组合制造无界 Catalog candidate identity。

允许状态固定为 `observed_unlisted|out_of_scope|evidence_pending|runtime_gap|conflict`；仅 `ready+unlisted` 和 `ready+out_of_scope` 从成功主链产生普通 observation，runtime gap 使用独立诊断路由，illegal/incomplete 不成为 Catalog candidate。

- [ ] 运行 `test ! -e server/migrations/postgres/0027_websim_exact_observation.sql`；若失败，按 Global Constraints 停止并处理编号冲突。
- [ ] 写 RED：同 canonical identity 幂等 upsert，只增加 capped `observationCount` 和 `lastObservedAt`；计数上限固定 `2147483647`。
- [ ] 写 RED：当前 season+game build 最多 50,000 个 discovery identities、全表最多 250,000 行；达到上限只丢弃新 identity 并记录 bounded capacity warning，已有 identity 仍可计数，Exact simulation 不受影响。
- [ ] 写 RED：表和 payload 不包含 `ownerKey`、角色名、服务器名、rawProfile、完整 loadout、DPS 或用户 template key；单事件 JSON 上限 16,384 bytes。
- [ ] 写 RED：queue exception/timeout 被请求路径记录为 bounded warning，但 API 仍返回原 `ready` simulation result；同一次请求 Catalog/staging/candidate/Manifest 写调用为零。
- [ ] 写 RED：相同 itemId 出现互斥 authority evidence 时变为 `conflict`，不能按次数多数票覆盖；`runtime_gap` 不进入 admission query。
- [ ] 运行 `python3 -m unittest tests.gear_exact_observation_test tests.gear_exact_observation_store_test` 和新增 backend 精确测试，确认 RED。
- [ ] 编写 0027 migration：唯一 canonical key、first/last/count、classification、sanitized payload、冲突状态；只授予 app 最小 SELECT/INSERT/受控 upsert 权限。
- [ ] 实现 recorder/store，并在 Exact API 终态形成后 best-effort 调用；不要在 parser、worker 中同步等待 Catalog 逻辑。
- [ ] 实现 admission read selector，只返回三来源调查所需的结构化字段和排序优先级，不返回任何用户信息。
- [ ] 运行 Task 7 测试和 migration tests，预期全部通过；执行一次 fault-injection smoke，确认 queue down 时 Exact SimC 仍完成。
- [ ] 运行 `git diff --check`，提交 `feat(websim): record isolated exact observations`。

### Slice 2 停止门禁

- [ ] 证明 `request_time_catalog_write_count=0`，并分别列出请求允许写入的四类 owner/global 表。
- [ ] 证明重复观察资源有界、冲突不自动决议、runtime gap/illegal/incomplete 不进入 Catalog admission。
- [ ] 证明 queue 不可用时 ready Exact 保存、快照、SimC 结果均不受影响。
- [ ] 任一项不通过，保持 Slice 1 可用并停止；不得创建 Catalog candidate。

## Release Slice 3：三来源 Catalog Admission 与发布硬门禁

### Task 8: 建立纯 Admission 决策与 candidate gate

**Files:**

- Create: `server/gear_catalog_admission.py`
- Create: `tests/gear_catalog_admission_test.py`
- Modify: `server/gear_release_tool.py`
- Modify: `tests/gear_release_tool_test.py`
- Modify: `server/gear_catalog_revision.py`
- Modify: `tests/gear_catalog_revision_test.py`
- Modify: `server/gear_release.py`
- Modify: `tests/gear_release_test.py`
- Modify: `server/gear_release_refresh.py`
- Modify: `tests/gear_release_refresh_test.py`
- Modify: `docs/verification-matrix.md`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/backend-owner-map.json`

**Admission decision:**

```python
def evaluate_catalog_admission(
    observation: object,
    *,
    source_evidence: object,
    progression_evidence: object,
    rule_revision: str,
    exact_samples: object,
) -> dict[str, object]:
    """Return catalog-admission-v1: admitted|partial|blocked|out_of_scope."""
```

`admitted` 必须同时满足 current season、`mythic_plus|raid|crafted` 来源证据、完整 ItemDefinition、所有拟发布 progression states、合法选择规则、至少一个无默认 Exact 样本、effect support verified、Rule/SimC/runtime revisions 一致。

- [ ] 写 RED：玩家观察次数再高也不能替代 source evidence；三来源外固定 `out_of_scope`；来源 denominator 不可枚举时 coverage 为 `blocked` 而非估算百分比。
- [ ] 写 RED：制造只发布稳定产品/品质/progression state，不枚举 crafted stats/embellishment 笛卡尔积；必选 option 未选择时不可 materialize，不能补默认。
- [ ] 写 RED：每个 BrowseVariant 至少一条 verified Exact materialization；每条后端接受的完整选择均生成 SimC-ready Exact；dynamic effect unknown/unsupported 不可 admitted。
- [ ] 写 RED：candidate gate 输出并强制 `catalog_non_simulatable_count=0`、`silent_default_fill_count=0`；任一非零，release builder 失败且活动指针/LKG 不变。
- [ ] 写 RED：candidate 构建/资源探测/CAS 任一失败，现有 `gear_catalog_revision` 和 Manifest 原样；成功只生成新不可变 revision，不回写历史 snapshot。
- [ ] 运行 `python3 -m unittest tests.gear_catalog_admission_test tests.gear_release_tool_test tests.gear_catalog_revision_test tests.gear_release_test tests.gear_release_refresh_test`，确认 RED。
- [ ] 实现纯 admission；来源 adapter 只消费已有受治理 source evidence，不从观察、item 名称、装等或历史赛季推断 membership。
- [ ] 在 release builder 中把 admitted rows 转为现有 ItemDefinition/BrowseVariant 输入，并对每个 variant 调用 Exact materializer/effect preflight；不要创建第二套 Catalog schema。
- [ ] 将两个新硬计数写入 release evidence 和 failure envelope；CAS 前重放现有 Exact templates、负向规则、资源预算和 mixed-revision probes。
- [ ] 更新 `docs/verification-matrix.md`，明确三个来源分别报告 denominator/verified/partial/blocked，且 `unlisted_but_simulatable_rate` 不是 Catalog coverage。
- [ ] 运行 Task 8 测试，预期全部通过；再运行 `python3 -m unittest tests.gear_release_shadow_test tests.gear_release_resource_probe_test tests.gear_catalog_http_completeness_matrix_test`，预期现有发布门禁回归通过。
- [ ] 运行 `git diff --check`，提交 `feat(websim): admit simulatable three-source catalog candidates`。

### Slice 3 停止门禁

- [ ] 用 raid、mythic_plus、crafted 各至少一个 positive fixture 和一个 source/progression/effect negative fixture 生成 admission report。
- [ ] 证明 `catalog_non_simulatable_count=0`、`silent_default_fill_count=0`，且候选失败不会改变 LKG/Manifest。
- [ ] 证明候选晋升前后的既有 v1/v2 SimulationSnapshot keys 和结果行完全一致。
- [ ] 三来源任一 denominator 无权威输入时按该来源报告 `blocked`；不得以观察样本或其他来源通过替代。
- [ ] 任一项不通过，保留上一 CatalogRevision，Exact 主链继续运行，停止 UI/候选发布。

## Release Slice 4：微信体验、候选环境与用户验收

### Task 9: 发布 typed Exact import API client

**Files:**

- Modify: `packages/domain/src/entities.ts`
- Modify: `packages/api-client/src/websim.ts`
- Modify: `packages/api-client/src/websim.test.ts`
- Modify: `packages/api-client/src/templates.ts`
- Modify: `packages/api-client/src/templates.test.ts`
- Modify: `tests/frontend-api-client.test.js`
- Modify: `docs/project-owner-map.json`

**Type surface:**

```ts
export type ExactSimulationStatus = 'ready' | 'pending' | 'blocked' | 'unsupported'
export type ExactCatalogStatus = 'listed' | 'unlisted' | 'candidate' | 'out_of_scope'

interface ExactImportEnvelopeBase {
  readonly schemaRevision: 'exact-import-envelope-v1'
  readonly catalogStatus: ExactCatalogStatus
  readonly problems: readonly ExactImportProblem[]
}

export type ExactImportEnvelope =
  | (ExactImportEnvelopeBase & { readonly status: 'pending'; readonly simulationStatus: 'pending'; readonly jobKey: string; readonly retryAfterMs: 1000 })
  | (ExactImportEnvelopeBase & { readonly status: 'resolved'; readonly simulationStatus: 'ready'; readonly jobKey: string; readonly exactLoadoutIntent: ExactLoadoutIntent; readonly resolvedSnapshot: GearResolvedSnapshotV2 })
  | (ExactImportEnvelopeBase & { readonly status: 'blocked'; readonly simulationStatus: 'blocked'; readonly jobKey?: string })
  | (ExactImportEnvelopeBase & { readonly status: 'unsupported'; readonly simulationStatus: 'unsupported'; readonly jobKey: string })
  | (ExactImportEnvelopeBase & { readonly status: 'failed'; readonly simulationStatus: 'blocked'; readonly jobKey: string })
```

- [ ] 写 RED：request serializer 只发送 `rawProfile,classKey,specKey,level,guestId`；拒绝未知 key 和超过 65,536 bytes；response validator 拒绝未知 status、缺 path/recoveryAction 和 raw profile 回显。
- [ ] 写 RED：202 pending 保留 `retryAfterMs=1000`；200 blocked/unsupported 不抛 transport success；401/403/503 保留 literal terminal state，不包装成 ready。
- [ ] 写 RED：v1 `requestWebsimGearResolve` 和现有 SimC client bytes/request paths 不变。
- [ ] 在 `packages/api-client/src/templates.test.ts` 写 RED：exact 模板只能持久化 intent identity、canonical intent、snapshot key 和两类状态；local/remote template payload 中出现 original profile lines 时拒绝，legacy talent/gear template 行为不变。
- [ ] 运行 `npm exec vitest run packages/api-client/src/websim.test.ts packages/api-client/src/templates.test.ts` 和 `node --test tests/frontend-api-client.test.js`，确认 RED。
- [ ] 实现 `requestWebsimExactImport` 与严格 validator；调用者不能自行构造 `ready` 或把 `catalogStatus` 当 simulation gate。
- [ ] 运行 Task 9 tests，预期全部通过；运行 `npm run typecheck`，预期无类型错误。
- [ ] 运行 `git diff --check`，提交 `feat(api-client): add exact import contract`。

### Task 10: 在活动 Taro 装备体验接入导入、状态和恢复动作

**Files:**

- Create: `apps/mini-taro/src/pages/builds/gear-exact-import-model.ts`
- Create: `apps/mini-taro/src/pages/builds/gear-exact-import-model.test.ts`
- Modify: `apps/mini-taro/src/pages/builds/detail.tsx`
- Modify: `apps/mini-taro/src/pages/builds/gear-detail-model.ts`
- Modify: `apps/mini-taro/src/pages/builds/gear-detail-model.test.ts`
- Modify: `apps/mini-taro/src/pages/simulator/simc-submit-model.ts`
- Modify: `apps/mini-taro/src/pages/simulator/simc-submit-model.test.ts`
- Modify: `packages/design-system/src/components/GearDetailComponents.tsx` for the existing-contract state surface; do not change target geometry without isolated target measurement.
- Modify: `docs/design/current-ui/routes/gear-detail/truth-adaptation.json`
- Modify: `docs/design/current-ui/routes/gear-detail/component-contract.json`
- Modify: `docs/design/current-ui/routes/simc-submit/truth-adaptation.json`
- Modify: `docs/design/current-ui/routes/simc-submit/component-contract.json`
- Modify: `docs/design/current-ui/core-interaction-contract.json`
- Modify: `docs/project-owner-map.json`

**Player states:**

- `ready+listed`：可以模拟、可以换装。
- `ready+unlisted`：可以模拟，暂未进入换装目录。
- `ready+out_of_scope`：可以模拟，不属于当前目录范围。
- `pending`：正在验证具体装备；保留输入页但不创建任务。
- `blocked`：展示 slot/item/field 与修改或重新导出动作。
- `unsupported`：展示具体 item/effect/runtime 缺口，禁止提交。
- `failed`：展示系统验证失败与重试动作，保留当前输入，禁止提交；不得显示为装备不支持。

- [ ] 写 model RED：raw profile 只在当前 component/model memory；route unload、保存成功或明确清空时移除；不能写 build template、local storage、analytics 或 error log。
- [ ] 写 model RED：pending 按服务端 `retryAfterMs=1000` 有界轮询，离开页面取消；重复点击复用同 job；blocked/unsupported/failed 停止轮询。
- [ ] 写 UI RED：`ready+unlisted`/`out_of_scope` 的保存和提交按钮可用；pending/blocked/unsupported/failed 不可提交；所有 problem 显示对象、字段、恢复动作。
- [ ] 写回归 RED：raw-only gear template 仍不是 SimC-ready；只有后端 resolved v2 snapshot 可进入 `simc-submit-model`；v1 已封存模板继续可提交。
- [ ] 运行 `npm exec vitest run apps/mini-taro/src/pages/builds/gear-exact-import-model.test.ts apps/mini-taro/src/pages/builds/gear-detail-model.test.ts apps/mini-taro/src/pages/simulator/simc-submit-model.test.ts`，确认 RED。
- [ ] 实现导入入口和状态展示；前端不得根据 itemId、source label、Catalog presence 或 SimC stdout 推断 ready。
- [ ] 保存结构化 v2 confirmed intent、snapshot reference 和两类状态；不保存原始插件文本。重载后由后端重新读取封存 snapshot，不重新猜 Catalog membership。
- [ ] 更新当前 UI 合同，仅描述用户可见状态和后端 truth owner；不从 runtime CSS/旧截图调整 target bounds。
- [ ] 运行 Task 10 Vitest，预期全部通过；运行 `npm run typecheck && npm run audit:ui-architecture && npm run build:weapp`，预期全部通过。
- [ ] 运行 `git diff --check`，提交 `feat(weapp): add exact-first gear import journey`。

### Task 11: 完整回归、候选部署和 Harness 用户验收关闭

**Files:**

- Create: `artifacts/releases/2026-08-04-equipment-simulator-exact-first/evidence.json`
- Create: `artifacts/releases/2026-08-04-equipment-simulator-exact-first/handoff.json`
- Modify: `docs/roadmap.md`
- Modify: `docs/project-state.json`
- Modify: `docs/plans/README.md`
- Modify: this plan checkbox/status only after corresponding fresh evidence exists.

- [ ] 运行当前 `docs/verification-matrix.md` 指定的 Python Exact/Resolver/Snapshot/Release suites、domain/API Vitest、Taro tests、`npm run typecheck`、`npm run audit:ui-architecture`、`npm run build:weapp` 和 `git diff --check`。
- [ ] 运行本任务 26/14 矩阵：26 条支持路径必须产生真实 SimC 终态；14 条阻断路径必须在 task 创建前终止。保留 PTR/正式服、团本/大秘境证据隔离，不借用其他场景通过。
- [ ] 重放 40 专精、现有 v1 templates、generation 35 历史 snapshot/result identities；记录 `historical_snapshot_identity_drift=0` 和 `mixed_revision_read_count=0`。
- [ ] 生成三来源 Catalog admission report 和 request-write audit；记录五个硬门禁全部为零。
- [ ] 做本地 CR：对照 design、Harness requirement、四个 slice、迁移 rollback、隐私、owner isolation、API literal states 和活动 UI authority；修复有效发现后重跑受影响测试。
- [ ] 在候选分支部署并记录 branch/commit、数据库备份、migration identity、runtime file SHA、SimC runtime identity、service/API smoke、timer/backflow 状态和回滚命令；保持活动 Catalog/Manifest 指针不变，除非本任务 candidate gate 明确包含一次受控 CAS candidate。
- [ ] 候选故障注入：queue down、worker timeout、effect unknown、Catalog candidate fail、CAS conflict；证明 Exact LKG 与 Catalog LKG 分别保持。
- [ ] 真实微信逐项验收：插件导入、pending、保存、重载、unlisted 模拟、listed 换装、Resolve、提交、结果；再验证字段缺失、非法组合、runtime unsupported、Catalog candidate fail 的文字和恢复动作。
- [ ] 在用户明确说“我已测试通过”“可以收尾”或“合入吧”之前，状态保持 `正在推进/待微信验收`，不提交关闭证据、不合并 main。
- [ ] 用户明确验收后，按 Harness 自动完成最终 local CR、任务分支 commit、同步/合并 main、merge result scoped verification、push、local/origin SHA parity、`npm run refresh:weapp` 和任务分支/worktree 清理。
- [ ] 只有生产/微信证据与 parity 全部成立后，将 roadmap 状态改为 `已完成`，登记 evidence/handoff；否则保留 literal `partial|blocked` 和具体恢复入口。

## Final Acceptance Matrix

| Gate | Required evidence | Failure meaning |
| --- | --- | --- |
| Catalog 外 Exact | 真实插件输入完成保存、重载、v2 snapshot、真实 SimC result | Exact-first 主目标未实现 |
| 字段/规则 | 缺字段和非法组合分别定位 object/path/recovery | 仍在用 Catalog/泛化错误掩盖真实原因 |
| 效果支持 | unknown/unsupported 在任务创建前阻断 | 存在伪准确 DPS 风险 |
| 身份稳定 | v1 历史和既有 v2 快照零漂移 | 破坏可复现/历史证据 |
| Queue 隔离 | Queue 故障不阻断；请求不写 Catalog | 动态发现污染主链 |
| Catalog 子集 | 三来源 denominator 分开；所有 BrowseVariant 可物化 | 展示池大于可准确模拟池 |
| 发布安全 | candidate/CAS 失败保持 LKG | Catalog 更新可能破坏现网 |
| 微信闭环 | 玩家看见并完成主路径与异常恢复 | API/测试通过尚未形成产品完成 |

硬计数必须全部为零：

```text
catalog_non_simulatable_count = 0
silent_default_fill_count = 0
request_time_catalog_write_count = 0
historical_snapshot_identity_drift = 0
mixed_revision_read_count = 0
```

## Rollback

- Slice 1 代码回滚到最后一个 v1-compatible commit；0026 只新增表/可空列/条件约束且不重写历史行，回滚应用读写路径即可，保留未被活动 reader 引用的 append-only v2 rows 供取证。不得 DROP 表或删除封存行作为常规回滚。
- Slice 2 停止 observation hook/worker 即可；队列行不影响 simulation identity。不得用清空队列替代修复冲突或隐私问题。
- Slice 3 不切或 CAS 切回上一 Manifest/Catalog LKG；不逐表回写，不重算 Exact/SimulationSnapshot。
- Slice 4 回滚 Taro/API client 到上一兼容 build；后端 v1 与 v2 reader 在迁移窗口内并存。若微信验收失败，保持 candidate 分支和证据，不合并 main。
- 任何 mixed revision、历史 identity drift、原始插件文本落盘、跨 owner job 泄露或 active Catalog 请求时写入，均视为 P0 停止条件，立即停止候选流量并保留现场证据。
