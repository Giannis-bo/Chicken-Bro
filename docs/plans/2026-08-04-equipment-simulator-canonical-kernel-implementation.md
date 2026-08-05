# 装备模拟 Canonical Kernel Replacement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

状态：`已停止（pure foundation 的 forward replacement 与 final whole-branch re-review 已完成；replacement Task 3A 当前为 candidate_rerun_required / evidence_promotion_blocked：前三次仍为失败/不可晋升历史，第四次 t3a260805120026 真实通过旧 0026 链但因 main 已占用 0026-0029、当前必须改为 0030 而 superseded；四对八库不可复用，必须第五次新 run-id/双库重跑；本计划原 Task 3 继续停止）`

**Task 5 schema replacement:** [Canonical Ownership Change-Control Plan](2026-08-04-equipment-simulator-canonical-owner-change-control.md)。本计划不得改名进入第六轮；历史提交保留，不 reset/rebase。

**Goal:** 用唯一 Canonical Kernel 和不可变 sealed documents 替换未发布的 Task 2 内部实现，使 Exact、Progression、Effect、Probe、CLI 与 Authority Envelope 对同一输入语言给出一致、fail-closed、内容寻址的结果。

**Architecture:** Task 1 的外部 Exact v2 schema 和全部 v1 identity 保持稳定；新增纯 `gear_canonical_kernel.py` 统一 primitive、canonical bytes、seal 和 reload verification。Exact、Progression、Effect 与 Envelope 各自保留业务 schema owner，但跨模块只传 `SealedCanonicalDocument`，不再传任意 `dict` 或第二份 serializer payload。

**Tech Stack:** Python 3 standard library (`dataclasses`, `json`, `hashlib`, `re`, `unicodedata`, `unittest`)、TypeScript/Vitest、现有 Track Authority pure owner、Harness Strict；不增加依赖。

## Global Constraints

- `selection-intent-v1`、v1 ExactItemInstance、ResolvedLoadout、SimulationSnapshot canonical bytes/key 必须保持不变。
- generation 35、Phase 0-4 归档证据和活动 Manifest/Catalog 指针不得改变。
- Task 1 `exact-loadout-intent-v2` schema revision、字段集合、15 个核心槽和可选 off-hand 顺序保持不变；合法 fixture bytes/key 零漂移。
- 原先可被 parser 接受、但含非 canonical Unicode/control 的输入改为明确 `blocked`；不得自动 normalize。
- Import Adapter 可以解析外部表达；Canonical Kernel 内禁止 trim、大小写转换、类型转换、排序、去重和默认补值。
- Exact identity 和 simulation readiness 不依赖 Catalog membership；Catalog、owner、observation、listed/unlisted 和 provenance 不进入 canonical payload。
- 原始 SimulationCraft 插件文本不得持久化、记录日志、进入 job/result/artifact 或出现在诊断。
- `CANONICAL_GEAR_SLOTS` 继续由 `server/gear_contracts.py` 唯一拥有；Progression 必须调用现有 `resolve_exact_instance_progression`，不得复制 ladder/rank/crafted/Ascendant 规则。
- Task 1 没有 `craftedEffectIds`；出现该字段必须 path-specific blocked。合法 `craftedStats` 确定性生成 `crafted_effect` subjects。
- 不新增依赖、不联网、不下载、不部署、不创建 migration/store/worker/API/UI；原计划 Task 3 在本计划全部 review clean 前不得启动。
- 当前五轮实验实现保留 Git 历史，不做 reset/rebase；允许在后续提交中替换其未发布内部接口。
- 每个任务必须先得到预期 RED，再最小实现 GREEN，提交后接受 fresh spec reviewer 和 fresh code-quality reviewer；任一 Important/Critical 未关闭，不进入下一任务。

---

### Task 1: 建立唯一 Canonical Kernel 与共享 mutation corpus

**Files:**

- Create: `server/gear_canonical_kernel.py`
- Create: `tests/gear_canonical_kernel_test.py`
- Create: `tests/fixtures/gear_canonical_mutations.json`
- Modify: `artifacts/releases/2026-08-04-equipment-simulator-exact-first/requirement.json`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/backend-owner-map.json`

**Interfaces:**

- Produces:

```python
@dataclass(frozen=True)
class CanonicalIssue:
    code: str
    path: str
    recovery_action: str

@dataclass(frozen=True, init=False, slots=True)
class SealedCanonicalDocument:
    document_kind: str
    schema_revision: str
    canonical_bytes: bytes
    content_key: str

@dataclass(frozen=True)
class CanonicalResult:
    status: Literal["verified", "blocked"]
    document: SealedCanonicalDocument | None
    issues: tuple[CanonicalIssue, ...]

def canonical_identity_token(value: object, *, path: str, allow_empty: bool = False, max_bytes: int = 256) -> str
def canonical_report_token(value: object, *, path: str, allow_empty: bool = False, max_bytes: int = 256) -> str
def canonical_slot(value: object, *, path: str) -> str
def canonical_int(value: object, *, path: str, minimum: int, maximum: int) -> int
def canonical_ordered_list(value: object, *, path: str, item_rule: Callable[[object, str], T], max_items: int) -> tuple[T, ...]
def canonical_set_list(value: object, *, path: str, item_rule: Callable[[object, str], T], max_items: int) -> tuple[T, ...]
def canonical_mapping(value: object, *, path: str, exact_keys: frozenset[str]) -> Mapping[str, object]
def canonical_json_bytes(value: object) -> bytes
def seal_canonical_document(*, document_kind: str, schema_revision: str, payload: Mapping[str, object], key_prefix: str) -> SealedCanonicalDocument
def verify_sealed_document(document: object, *, document_kind: str, schema_revision: str, key_prefix: str, payload_validator: Callable[[object], object]) -> bool
def verified_payload_copy(document: SealedCanonicalDocument, *, document_kind: str, schema_revision: str, payload_validator: Callable[[object], object]) -> dict[str, object]
```

`SealedCanonicalDocument` 的实际构造必须要求 module-private seal token；consumer 不能直接实例化。

- Consumes: `server.gear_contracts.CANONICAL_GEAR_SLOTS` only for `canonical_slot`.

- [ ] **Step 1: 写 mutation fixture**

在 `tests/fixtures/gear_canonical_mutations.json` 固定原最终审查和相邻等价类：

```json
{
  "invalidIdentityStrings": [" head", "head ", "heroic\rforged", "heroic\nforged", "heroic\u0085forged", "heroic\u0090forged", "heroic\u2028forged", "heroic\u2029forged", "heroic\u200dforged"],
  "invalidSlots": ["bogus", "HEAD", "trinket_1", "mainhand"],
  "invalidIntegers": [true, false, 3.0, -1, 0, 10000],
  "invalidSetLists": [["haste", "crit"], ["crit", "crit", "haste"]]
}
```

- [ ] **Step 2: 写 Kernel RED tests**

在 `tests/gear_canonical_kernel_test.py` 写具体行为：

```python
class GearCanonicalKernelTest(unittest.TestCase):
    def test_rejects_ascii_and_unicode_controls_without_normalizing(self):
        for value in MUTATIONS["invalidIdentityStrings"]:
            with self.subTest(value=ascii(value)):
                with self.assertRaises(CanonicalValueError):
                    canonical_identity_token(value, path="exact.context")

    def test_slot_uses_the_single_canonical_slot_set(self):
        self.assertEqual(canonical_slot("head", path="slot"), "head")
        for value in MUTATIONS["invalidSlots"]:
            with self.assertRaises(CanonicalValueError):
                canonical_slot(value, path="slot")

    def test_set_list_requires_already_sorted_unique_input(self):
        self.assertEqual(
            canonical_set_list(["crit", "haste"], path="craftedStats", item_rule=identity_rule, max_items=8),
            ("crit", "haste"),
        )
        for value in MUTATIONS["invalidSetLists"]:
            with self.assertRaises(CanonicalValueError):
                canonical_set_list(value, path="craftedStats", item_rule=identity_rule, max_items=8)

    def test_sealed_document_cannot_be_forged_or_mutated(self):
        document = seal_canonical_document(
            document_kind="fixture", schema_revision="fixture-v1",
            payload={"schemaRevision": "fixture-v1", "value": "ok"}, key_prefix="fixture:sha256:",
        )
        self.assertFalse(hasattr(document, "__dict__"))
        with self.assertRaises(TypeError):
            SealedCanonicalDocument("fixture", "fixture-v1", b"{}", "fixture:sha256:" + "0" * 64)
```

- [ ] **Step 3: 运行 RED**

Run:

```bash
python3 -m unittest tests.gear_canonical_kernel_test
```

Expected: import failure for missing `server.gear_canonical_kernel`, not fixture/environment failure.

- [ ] **Step 4: 实现 primitive 与 issue/result types**

在 `server/gear_canonical_kernel.py` 实现 raw-value validation。Control predicate 必须使用原字符串：

```python
def _has_forbidden_codepoint(value: str) -> bool:
    return any(unicodedata.category(ch) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for ch in value)

def canonical_identity_token(value: object, *, path: str, allow_empty: bool = False, max_bytes: int = 256) -> str:
    if type(value) is not str or value != value.strip():
        raise CanonicalValueError("NON_CANONICAL_TEXT", path)
    if (not allow_empty and not value) or len(value.encode("utf-8")) > max_bytes:
        raise CanonicalValueError("TEXT_BOUNDS", path)
    if _has_forbidden_codepoint(value) or _IDENTITY_PATTERN.fullmatch(value) is None:
        raise CanonicalValueError("INVALID_IDENTITY_TOKEN", path)
    return value
```

`canonical_int` 必须用 `type(value) is int`；`canonical_set_list` 必须比较原 tuple 与 `tuple(sorted(set(result)))`，不返回修正后的输入。

- [ ] **Step 5: 实现 canonical bytes、private seal 和 reload verification**

```python
def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")

def _content_key(prefix: str, encoded: bytes) -> str:
    return prefix + hashlib.sha256(encoded).hexdigest()
```

`verify_sealed_document` 必须 parse `canonical_bytes`、运行 `payload_validator`、重新 serialize 并要求 bytes/key 完全相同；禁止 `default=str`。

- [ ] **Step 6: 运行 Kernel GREEN**

Run:

```bash
python3 -m unittest tests.gear_canonical_kernel_test
```

Expected: all Kernel tests pass.

- [ ] **Step 7: 更新 Strict requirement 与 owner maps**

把 requirement 的 `currentTruth.sources` 加入本设计和本计划；设置：

```json
"featureIteration": "equipment_simulator_exact_first_task2r_kernel"
```

`impactMap.mustChange` 明确 Kernel、sealed documents、Exact/Progression/Effect/Envelope consumers；`mustNotChange` 保留 v1、generation 35、Catalog pointers、Task 3+。Harness status 仍是 `implementation_allowed`，不是 evidence promotion。

Owner maps 把 `server/gear_canonical_kernel.py` 登记为 Task 2 primitive/bytes/seal fact owner；`gear_contracts.py` 继续是 slot-set owner。

- [ ] **Step 8: 运行控制面验证并提交**

Run:

```bash
python3 -m unittest tests.gear_canonical_kernel_test
node --test tests/project-harness.test.js tests/project-owner-map.test.js tests/backend-owner-map.test.js
node scripts/project-harness.js --json --check-requirement --requirement-file artifacts/releases/2026-08-04-equipment-simulator-exact-first/requirement.json
jq empty docs/project-owner-map.json docs/backend-owner-map.json artifacts/releases/2026-08-04-equipment-simulator-exact-first/requirement.json
git diff --check
```

Expected: Kernel、40 个控制面测试、Harness requirement、JSON 和 diff 全部通过。

Commit:

```bash
git add server/gear_canonical_kernel.py tests/gear_canonical_kernel_test.py tests/fixtures/gear_canonical_mutations.json artifacts/releases/2026-08-04-equipment-simulator-exact-first/requirement.json docs/project-owner-map.json docs/backend-owner-map.json
git commit -m "feat(websim): add exact canonical kernel"
```

---

### Task 2: 将 Exact v2 与 Progression 切到 sealed documents

**Files:**

- Modify: `server/gear_contracts.py`
- Modify: `tests/gear_contracts_test.py`
- Modify: `packages/domain/src/gear-intent.ts`
- Modify: `packages/domain/src/gear-intent.test.ts`
- Modify: `server/gear_exact_item_instance.py`
- Modify: `tests/gear_exact_item_instance_test.py`
- Modify: `server/gear_exact_authority.py`
- Modify: `tests/gear_exact_authority_test.py`
- Test: `tests/fixtures/gear_canonical_mutations.json`

**Interfaces:**

- Consumes from Task 1: Kernel primitives, `SealedCanonicalDocument`, `CanonicalResult`, `verified_payload_copy`.
- Produces:

```python
def seal_exact_item(exact_slot_payload: object) -> CanonicalResult
def derive_simc_serializer_input(exact: SealedCanonicalDocument) -> dict[str, str]
def seal_exact_progression(
    exact: SealedCanonicalDocument,
    *, season_revision: str, gear_rule_revision: str,
    slot: str, has_crafted_source: bool,
) -> CanonicalResult
```

Document kinds/prefixes:

```text
exact_item / gear-exact-item-instance-v2 / exact-item-instance:sha256:
exact_progression / exact-progression-binding-v1 / exact-progression:sha256:
```

- [ ] **Step 1: 写 Task 1 Python/TypeScript parity RED**

Python 和 Vitest 都读取 `tests/fixtures/gear_canonical_mutations.json`。对 applicable string mutations，`parse_exact_loadout_intent` 和 `canonicalExactLoadoutIntent` 都必须拒绝；合法 frozen fixture bytes 不变。

Vitest fixture loader 使用：

```ts
const mutationPath = fileURLToPath(new URL('../../../tests/fixtures/gear_canonical_mutations.json', import.meta.url))
const mutations = JSON.parse(readFileSync(mutationPath, 'utf8'))
```

必须覆盖 `U+0085/U+0090/U+2028/U+2029/U+200D`，不能只覆盖 CR/LF。

- [ ] **Step 2: 写 Exact sealed RED**

```python
def test_seal_exact_item_rejects_noncanonical_set_and_contract_extra_fields(self):
    for field, value in (
        ("craftedStats", ["haste", "crit"]),
        ("craftedStats", ["crit", "crit", "haste"]),
        ("embellishmentIds", ["b", "a"]),
    ):
        row = {**VALID_EXACT_SLOT, field: value}
        self.assertEqual(seal_exact_item(row).status, "blocked")
    self.assertEqual(
        seal_exact_item({**VALID_EXACT_SLOT, "craftedEffectIds": ["craft-a"]}).issues[0].path,
        "exactSlot.craftedEffectIds",
    )

def test_sealed_exact_identity_ignores_catalog_provenance_but_changes_for_each_exact_field(self):
    base = seal_exact_item(VALID_EXACT_SLOT).document
    unlisted_import = adapter_exact_slot_fields({**VALID_EXACT_SLOT, "listed": False})
    self.assertEqual(base, seal_exact_item(unlisted_import).document)
    self.assertEqual(seal_exact_item({**VALID_EXACT_SLOT, "listed": False}).status, "blocked")
```

`adapter_exact_slot_fields` 在测试中按 Task 1 exact slot key set 投影，不调用 Kernel。该测试同时证明 adapter 外的 provenance 不改变 identity，以及 Kernel 自身遇到未知 key 必须 blocked。

- [ ] **Step 3: 写 Progression RED**

```python
def test_progression_requires_canonical_slot_and_production_track_authority(self):
    exact = seal_exact_item(HERO_RANK_3_EXACT).document
    ready = seal_exact_progression(
        exact, season_revision=SEASON, gear_rule_revision=RULE,
        slot="head", has_crafted_source=False,
    )
    self.assertEqual(ready.status, "verified")
    for slot in ("bogus", "HEAD", "trinket_1", "mainhand"):
        self.assertEqual(
            seal_exact_progression(exact, season_revision=SEASON, gear_rule_revision=RULE, slot=slot, has_crafted_source=False).status,
            "blocked",
        )
```

增加 forged hero rank 6、myth rank 3、crafted quality、Ascendant、arbitrary rule/record key reload tests；`verify_sealed_document` 必须拒绝。

- [ ] **Step 4: 运行 RED**

Run:

```bash
python3 -m unittest tests.gear_contracts_test tests.gear_exact_item_instance_test tests.gear_exact_authority_test
npm exec vitest run packages/domain/src/gear-intent.test.ts
```

Expected: missing `seal_exact_item`/`seal_exact_progression` and Unicode parity behavior failures; v1 tests remain green where reached.

- [ ] **Step 5: 收紧 Task 1 accepted language without changing schema/valid bytes**

Python `_exact_identifier` 与 TypeScript `boundedExactIntentString` 使用与 Kernel 对齐的 raw/control predicate。TypeScript 不 trim 后接受；先要求 `value === value.trim()`，再拒绝 C0/C1、`Cf/Cs/Zl/Zp`。合法 fixture canonical bytes 不改变。

- [ ] **Step 6: 实现 `seal_exact_item` 并保持 v1 wrapper不变**

删除 v2 对 `variantKey`、rowFamily、Catalog、status 和 `simcOptions` 的依赖。用 Kernel exact-key mapping、strict int、ordered/set list 建 payload，再 seal。

`derive_simc_serializer_input` 只接受 verified `exact_item` document，通过 `verified_payload_copy`读取；不接受 dict。

- [ ] **Step 7: 实现 `seal_exact_progression`**

先用 `canonical_slot`，再调用：

```python
resolve_exact_instance_progression(
    {"seasonRevision": season_revision, "gearRuleRevision": gear_rule_revision},
    {
        "rowFamily": "exact_instance",
        "status": "verified",
        "itemId": exact_payload["itemId"],
        "variantKey": exact.content_key,
        "itemLevel": exact_payload["itemLevel"],
        "bonusIds": exact_payload["bonusIds"],
        "slot": slot,
        "hasCraftedSource": has_crafted_source,
    },
)
```

只 seal production owner 返回的 verified state、ruleRevision、recordKey 和完整 canonical input；不接受调用者提交 progression payload。

- [ ] **Step 8: 运行 GREEN 与冻结回归**

Run:

```bash
python3 -m unittest tests.gear_contracts_test tests.gear_exact_item_instance_test tests.gear_exact_authority_test tests.gear_track_authority_test tests.gear_exact_item_registry_test tests.gear_resolved_loadout_test tests.simulation_snapshot_test
npm exec vitest run packages/domain/src/gear-intent.test.ts
git diff --check
```

Expected: Python/Vitest parity、Exact/Progression、v1 Exact/ResolvedLoadout/Snapshot 全通过，frozen bytes/key 零漂移。

- [ ] **Step 9: 提交**

```bash
git add server/gear_contracts.py tests/gear_contracts_test.py packages/domain/src/gear-intent.ts packages/domain/src/gear-intent.test.ts server/gear_exact_item_instance.py tests/gear_exact_item_instance_test.py server/gear_exact_authority.py tests/gear_exact_authority_test.py
git commit -m "refactor(websim): seal exact identity and progression"
```

---

### Task 3: 将 Effect、Probe 与 CLI 切到同一 seal path

**Files:**

- Modify: `server/simc_item_effect_support.py`
- Modify: `tests/simc_item_effect_support_test.py`
- Modify: `server/simc_item_effect_probe.py`
- Modify: `tests/simc_item_effect_probe_test.py`
- Modify: `scripts/simc-item-effect-probe.py`
- Modify: `tests/simc_item_effect_probe_cli_test.py`
- Modify: `tests/gear_exact_authority_test.py`（仅将 pre-Task-4 raw Effect fixture callsites 切到显式 legacy helper；不得修改 Envelope assertions 或生产实现）

**Interfaces:**

- Consumes: sealed `exact_item`; Kernel primitives/seal/reload.
- Produces:

```python
@dataclass(frozen=True)
class EffectSubject:
    kind: Literal["item", "gem", "enchant", "embellishment", "crafted_effect", "set_bonus"]
    key: str
    variant_signature: str

@dataclass(frozen=True)
class EffectSupportOutcome:
    status: Literal["verified", "unknown", "unsupported"]
    document: SealedCanonicalDocument | None
    issues: tuple[CanonicalIssue, ...]

def derive_exact_effect_subjects(exact: SealedCanonicalDocument) -> tuple[EffectSubject, ...]
def seal_effect_record(record_payload: object, *, runtime_revision: str) -> CanonicalResult
def verify_effect_record(document: object, *, runtime_revision: str) -> bool
def resolve_exact_effect_support(exact: SealedCanonicalDocument, *, runtime_revision: str, records: Sequence[SealedCanonicalDocument]) -> EffectSupportOutcome
def evaluate_effect_probe(manifest: object, experiment: object, control: object, *, runtime_revision: str) -> CanonicalResult
```

Document kinds/prefixes:

```text
effect_record / simc-item-effect-record-v1 / simc-item-effect-record:sha256:
effect_aggregate / simc-item-effect-support-v1 / simc-item-effect-support:sha256:
```

- [ ] **Step 1: 写 subject derivation RED**

```python
def test_subjects_are_derived_only_from_sealed_exact(self):
    exact = seal_exact_item(EXACT_WITH_GEMS_ENCHANT_EMBELLISHMENT_AND_CRAFTED_STATS).document
    subjects = derive_exact_effect_subjects(exact)
    self.assertEqual(
        [subject.kind for subject in subjects],
        ["item", "gem", "enchant", "embellishment", "crafted_effect"],
    )
    self.assertTrue(all("\n" not in subject.key for subject in subjects))

def test_each_crafted_stat_requires_its_own_crafted_effect_record(self):
    exact = seal_exact_item({**VALID_EXACT_SLOT, "craftedStats": ["crit", "haste"]}).document
    outcome = resolve_exact_effect_support(exact, runtime_revision=RUNTIME, records=[record_for("crafted_effect", "crit")])
    self.assertEqual(outcome.status, "unknown")
```

- [ ] **Step 2: 写 record/aggregate Unicode 与内容地址 RED**

逐一 mutation `subjectKey`、`subjectVariantSignature`、runtime、record key、experiment/control snapshot key：padding、CR/LF、C1、`U+2028/U+2029`、format control、oversize 必须 blocked/False/unknown。修改 payload 不改 key、相同 key 不同内容也必须拒绝。

Unsupported record 必须出现在 aggregate payload/key；不同 reason/verifiedAt/record key 改变 aggregate key。

- [ ] **Step 3: 写 Probe/CLI RED**

```python
def test_probe_uses_shared_record_factory_and_rejects_malformed_reports(self):
    for patch in (
        {"timedOut": 0}, {"warnings": ""}, {"exitCode": False},
        {"actions": ["action\u2028token"]},
    ):
        result = evaluate_effect_probe(MANIFEST, {**EXPERIMENT, **patch}, CONTROL, runtime_revision=RUNTIME)
        self.assertEqual(result.status, "blocked")
```

CLI 对所有 blocked/unknown/unsupported path 断言：return code 非零、stdout 恰为空；stderr 只含 reason code，不含 manifest/profile 内容。

- [ ] **Step 4: 运行 RED**

Run:

```bash
python3 -m unittest tests.simc_item_effect_support_test tests.simc_item_effect_probe_test tests.simc_item_effect_probe_cli_test
```

Expected: raw-dict APIs/current local validators cannot satisfy sealed interfaces and Unicode corpus.

- [ ] **Step 5: 实现 sealed subject/record/aggregate**

删除 effect 模块的 `_canonical_text`、runtime/token/hash duplicates，全部调用 Kernel。Subject 只由 `verified_payload_copy(exact)` 派生；gem signature 使用 canonical JSON hash of `{id, bonusIds, itemLevel}`，不用字符串分隔拼接。

Static/dynamic/unsupported record 都由 `seal_effect_record` 建立；records 是 sealed sequence，caller 不能提交 raw record dict 给 aggregate。

`seal_effect_record` 的 `runtime_revision` 必须是强制 keyword-only 参数，并且只能返回 `CanonicalResult`。为保持 Task 4 尚未迁移时的 frozen Envelope 回归，可保留单独命名的 legacy raw helper，并只把 `tests/gear_exact_authority_test.py` 的旧 fixture callsites 切到该 helper；禁止用 optional argument 或联合返回类型混合两条路径。

- [ ] **Step 6: 实现 Probe 与 CLI 单一路径**

Probe 验证 manifest/report 后构造 record payload，再调用 `seal_effect_record`；不得自己生成 key。CLI 接受本地 JSON 文件和独立 runtime argument，只有 `CanonicalResult(status="verified")` 才打印 `document.canonical_bytes`。

- [ ] **Step 7: 运行 GREEN**

Run:

```bash
python3 -m unittest tests.gear_canonical_kernel_test tests.simc_item_effect_support_test tests.simc_item_effect_probe_test tests.simc_item_effect_probe_cli_test
git diff --check
```

Expected: Kernel mutation、subject、三态 aggregate、Probe 和 CLI tests 全通过。

- [ ] **Step 8: 提交**

```bash
git add server/simc_item_effect_support.py tests/simc_item_effect_support_test.py server/simc_item_effect_probe.py tests/simc_item_effect_probe_test.py scripts/simc-item-effect-probe.py tests/simc_item_effect_probe_cli_test.py
git commit -m "refactor(websim): seal simc effect authority"
```

---

### Task 4: 封存 Static Facts 并让 Envelope 只组合 sealed documents

**Files:**

- Modify: `server/gear_exact_authority.py`
- Modify: `tests/gear_exact_authority_test.py`
- Modify: `server/gear_exact_item_instance.py`
- Modify: `tests/gear_exact_item_instance_test.py`

**Interfaces:**

- Consumes: sealed Exact、Progression、Effect Aggregate、Kernel.
- Produces:

```python
def seal_exact_static_facts(exact: SealedCanonicalDocument, facts: object) -> CanonicalResult
def seal_exact_authority_envelope(
    *, exact: SealedCanonicalDocument,
    static_facts: SealedCanonicalDocument,
    progression: SealedCanonicalDocument,
    effect_support: SealedCanonicalDocument,
    resolver_revision: str,
) -> CanonicalResult
```

Document kinds/prefixes:

```text
exact_static_facts / exact-static-facts-v1 / exact-static-facts:sha256:
exact_authority / exact-authority-envelope-v1 / exact-authority:sha256:
```

- [ ] **Step 1: 写 Static Facts RED**

```python
def test_static_facts_require_canonical_keys_and_finite_numbers(self):
    exact = seal_exact_item(VALID_EXACT_SLOT).document
    for facts in ({1: 241}, {" stat": 241}, {"stat\u2028x": 241}, {"stat": True}, {"stat": float("nan")}):
        self.assertEqual(seal_exact_static_facts(exact, facts).status, "blocked")
```

相同合法 facts 产生相同 bytes/key；改变 key/value 改变 key。

- [ ] **Step 2: 写 Envelope type/cross-binding RED**

```python
def test_envelope_rejects_raw_dicts_and_cross_bound_documents(self):
    exact_a = seal_exact_item(EXACT_A).document
    exact_b = seal_exact_item(EXACT_B).document
    progression_a = ready_progression(exact_a)
    static_b = ready_static(exact_b)
    effect_a = ready_effect(exact_a)

    self.assertEqual(
        seal_exact_authority_envelope(
            exact=exact_a, static_facts=static_b,
            progression=progression_a, effect_support=effect_a,
            resolver_revision=RESOLVER,
        ).status,
        "blocked",
    )
    with self.assertRaises(TypeError):
        seal_exact_authority_envelope(
            exact=json.loads(exact_a.canonical_bytes),
            static_facts=static_b, progression=progression_a,
            effect_support=effect_a, resolver_revision=RESOLVER,
        )
```

- [ ] **Step 3: 写 serializer single-owner RED**

证明 `seal_exact_authority_envelope` 签名不接受 `serializer_input`，且 `derive_simc_serializer_input(exact)` 对相同 sealed Exact byte-identical；无法以不同 id/ilevel/options 创建第二份 authority。

- [ ] **Step 4: 运行 RED**

Run:

```bash
python3 -m unittest tests.gear_exact_authority_test tests.gear_exact_item_instance_test
```

Expected: missing sealed static/envelope APIs and current raw-dict envelope acceptance fail.

- [ ] **Step 5: 实现 static seal 与 envelope composition**

Static facts 通过 Kernel exact mapping、identity token 和 finite number 校验后 seal。Envelope 对四个 document 先按 expected kind/schema/prefix 调用 `verify_sealed_document`，再读取 payload，只比较：

```python
exact_key == static_payload["exactItemInstanceKey"]
exact_key == progression_payload["exactItemInstanceKey"]
exact_key == effect_payload["exactItemInstanceKey"]
effect_payload["status"] == "verified"
```

Envelope 自身不再解析 slot/item/context/Unicode/arrays，不再接受 serializer input。

- [ ] **Step 6: 运行 GREEN 与 cross-owner regression**

Run:

```bash
python3 -m unittest tests.gear_canonical_kernel_test tests.gear_exact_item_instance_test tests.gear_exact_authority_test tests.simc_item_effect_support_test tests.gear_track_authority_test tests.gear_exact_item_registry_test
git diff --check
```

Expected: static/envelope/cross-binding、Exact/effect/Track Authority/v1 回归全通过。

- [ ] **Step 7: 提交**

```bash
git add server/gear_exact_authority.py tests/gear_exact_authority_test.py server/gear_exact_item_instance.py tests/gear_exact_item_instance_test.py
git commit -m "refactor(websim): compose sealed exact authority"
```

---

### Task 5: 删除重复 validator，建立 consolidation stop gate

**Files:**

- Modify: `server/gear_canonical_kernel.py`
- Modify: `server/gear_contracts.py`
- Modify: `server/gear_exact_item_instance.py`
- Modify: `server/gear_exact_authority.py`
- Modify: `server/simc_item_effect_support.py`
- Modify: `server/simc_item_effect_probe.py`
- Modify: `scripts/simc-item-effect-probe.py`
- Modify: `packages/domain/src/gear-intent.ts`
- Modify: `packages/domain/src/gear-intent.test.ts`
- Modify: `tests/fixtures/gear_canonical_mutations.json`
- Create: `tests/gear_canonical_owner_gate_test.py`
- Modify: `tests/gear_canonical_kernel_test.py`
- Modify: `tests/gear_contracts_test.py`
- Modify: `tests/gear_exact_item_instance_test.py`
- Modify: `tests/gear_exact_authority_test.py`
- Modify: `tests/simc_item_effect_support_test.py`
- Modify: `tests/simc_item_effect_probe_test.py`
- Modify: `tests/simc_item_effect_probe_cli_test.py`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/backend-owner-map.json`
- Modify: `artifacts/releases/2026-08-04-equipment-simulator-exact-first/requirement.json`
- Modify: `docs/plans/2026-08-04-equipment-simulator-canonical-kernel-redesign.md`
- Modify: `docs/plans/2026-08-04-equipment-simulator-canonical-kernel-implementation.md`
- Modify: `docs/plans/README.md`
- Modify: `docs/roadmap.md`

**Interfaces:**

- Consumes: all Task 1-4 sealed APIs.
- Produces: no new runtime API; produces the static ownership gate and Task 2 completion evidence required before original Task 3.

- [ ] **Step 1: 写 AST owner-gate RED**

`tests/gear_canonical_owner_gate_test.py` 只扫描本计划新增/修改的 Task 2 consumer files，不误伤 frozen v1 owners：

```python
TASK2_CONSUMERS = (
    "server/gear_exact_item_instance.py",
    "server/gear_exact_authority.py",
    "server/simc_item_effect_support.py",
    "server/simc_item_effect_probe.py",
    "scripts/simc-item-effect-probe.py",
)

def test_task2_consumers_do_not_redefine_primitive_canonicalization(self):
    forbidden_defs = {"_canonical_text", "_valid_token", "_canonical", "_hash", "valid_runtime_revision"}
    for path in TASK2_CONSUMERS:
        tree = ast.parse(Path(path).read_text())
        names = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.assertFalse(names & forbidden_defs, (path, names & forbidden_defs))
```

增加 AST assertions：consumer 不得对 identity fields 调用 `.strip()`、`str()`、`sorted(set(...))`，不得使用 `json.dumps(..., default=str)`；Envelope/Probe public functions 的 raw parameters 不得重新声明 `Mapping` payload API。

- [ ] **Step 2: 运行 owner-gate RED**

Run:

```bash
python3 -m unittest tests.gear_canonical_owner_gate_test
```

Expected: current experimental duplicate validators/API remain, test fails with exact file/function names.

- [ ] **Step 3: 删除 Task 2 duplicate validators 与旧 raw-dict APIs**

删除仅属于未发布 Task 2 的：

```text
build_exact_item_identity
build_exact_progression_binding
build_exact_authority_envelope
resolve_exact_item_effect_support(raw dict form)
validate_effect_record(raw dict form)
module-local canonical text/json/hash helpers
```

保留 v1 `build_exact_item_instance(..., catalog_revision=...)` 完整行为。不要添加兼容 wrapper；这些 Task 2 接口从未发布。

- [ ] **Step 4: 运行共享 mutation matrix 和全部 Task 2/v1 回归**

Run:

```bash
python3 -m unittest \
  tests.gear_canonical_kernel_test \
  tests.gear_canonical_owner_gate_test \
  tests.gear_contracts_test \
  tests.gear_exact_item_instance_test \
  tests.gear_exact_authority_test \
  tests.simc_item_effect_support_test \
  tests.simc_item_effect_probe_test \
  tests.simc_item_effect_probe_cli_test \
  tests.gear_track_authority_test \
  tests.gear_exact_item_registry_test \
  tests.gear_resolved_loadout_test \
  tests.simulation_snapshot_test \
  tests.news_backend_test.NewsBackendTest.test_simcraft_template_canonical_context_uses_server_owned_snapshot_for_confirm_and_final_without_legacy_fallback \
  tests.news_backend_test.NewsBackendTest.test_simcraft_template_gear_line_keeps_legacy_canonical_output
npm exec vitest run packages/domain/src/gear-intent.test.ts
node --test tests/project-harness.test.js tests/project-owner-map.test.js tests/backend-owner-map.test.js
node scripts/project-harness.js --json --check-requirement --requirement-file artifacts/releases/2026-08-04-equipment-simulator-exact-first/requirement.json
jq empty docs/project-owner-map.json docs/backend-owner-map.json artifacts/releases/2026-08-04-equipment-simulator-exact-first/requirement.json
git diff --check
```

Expected: all suites pass；原 89 条实验行为被新版 sealed tests 覆盖或显式替换，不能以删除测试减少覆盖。

- [ ] **Step 5: 生成 adversarial closure report**

在 Task 2 report 中记录至少以下逐项结果，不记录 raw payload：

```json
{
  "invalid_slot_alias_ready_count": 0,
  "unicode_control_accept_count": 0,
  "noncanonical_normalization_count": 0,
  "raw_dict_cross_boundary_count": 0,
  "duplicate_canonical_owner_count": 0,
  "v1_identity_drift_count": 0,
  "valid_v2_identity_drift_count": 0,
  "catalog_dependency_count": 0
}
```

把 report 放在 `.superpowers/sdd/<plan>/task-5-report.md`，不提交为 release evidence；正式 evidence 仍属于后续 release slice/Harness closure。

- [ ] **Step 6: Task 5 独立 review clean 后由 controller 更新当前控制面，但保持原 Task 3 未启动**

只有 Task 1-5 独立 review 全部 clean 后，controller 才在独立状态提交中：

- 重设计文档标记 `已完成（Task 2 canonical foundation）`；
- 本计划标记 `已完成`；
- 当时的关闭动作曾把原实施计划改为 `正在推进（Task 3 可开始，尚未启动）`；该动作现已被后续 readiness audit 和持久化重排计划 supersede，不再授予执行权；
- roadmap 从 `待决策` 改为 `正在推进`，明确 Task 2 sealed foundation 已通过、Task 3 尚未开始；
- owner maps 指向最终 Kernel/consumer/tests。

- [ ] **Step 7: 运行最终本地 CR**

Local CR 必须对照设计检查：合法 v2/v1 bytes、slot owner、Unicode/control、sealed type boundary、Track Authority reuse、effect subject derivation、raw text privacy、Catalog independence、Task 3 absence。修复任何有效发现后重跑 Step 4。

- [ ] **Step 8: 提交 consolidation implementation**

```bash
git add server/gear_exact_item_instance.py server/gear_exact_authority.py server/simc_item_effect_support.py server/simc_item_effect_probe.py scripts/simc-item-effect-probe.py tests/gear_canonical_owner_gate_test.py tests/gear_canonical_kernel_test.py tests/gear_contracts_test.py tests/gear_exact_item_instance_test.py tests/gear_exact_authority_test.py tests/simc_item_effect_support_test.py tests/simc_item_effect_probe_test.py tests/simc_item_effect_probe_cli_test.py docs/project-owner-map.json docs/backend-owner-map.json
git commit -m "test(websim): gate exact canonical ownership"
```

- [ ] **Step 9: 由 controller 运行 fresh broad review**

consolidation implementation 提交后先做 Task 5 独立 spec/code-quality review。该 review clean 后，controller 执行 Step 6 的控制面状态提交，再生成从本 replacement plan Task 1 base 到最终状态 head 的完整 review package，交给未参与实现的 fresh final reviewer。Reviewer 必须分别给出 Spec verdict 与 Code Quality verdict；只有 `PASS` 且 `APPROVED` 才能完成本计划。若发现 Critical/Important，回到 Task 5 fix loop 并在修复提交后重新生成 review package。

## Stop Gate

- 任一 Task reviewer 返回 Critical/Important：留在当前 Task，按 Subagent-Driven fix loop 处理，不启动下一 Task。
- 同一 Task 达到五轮 fix/re-review 仍不 clean：停止本计划并重新审视该 Task 的 schema boundary，不改名开启第六轮。
- Task 5 最终 review 未同时 `PASS/APPROVED`：roadmap 保持 `待决策`，原 Task 3 不启动。
- 本计划通过只证明 Task 2 pure canonical foundation；不证明真实 SimC runtime、持久化、API、候选部署、微信体验或 release 完成。
