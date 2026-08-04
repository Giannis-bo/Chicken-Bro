# 装备模拟 Canonical Ownership Change-Control Replacement Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to execute this plan task by task. This is a schema-boundary replacement after the previous Task 5 reached its five-round Stop Gate; it is not a sixth patch round.

状态：`已完成（仅 Task 1-2 scoped 与 pure-foundation final whole-branch PASS/APPROVED；proofClaim=source_change_control_only；后续 readiness audit 已停止原 Task 3）`

**Goal:** 保留已经通过语义测试的 Canonical Kernel、sealed documents、Exact/Progression/Effect/Probe/CLI/Envelope contracts，把失控增长的 Python AST “authority proof” 替换成诚实、可维护的 source change-control：四个 server owner 使用 declaration-only module-load profile，CLI 使用独立的受限 bootstrap profile，所有未知模块加载语法 fail closed。

**Architecture:** Canonical 语义由 Kernel constructor/reload、shared mutation corpus、frozen identity 和端到端 pure-contract tests 证明；ownership gate 只证明五个受保护源文件符合已登记的模块加载语法、import/symbol owner 与精确例外，不证明任意 Python 执行路径、被信任 import 的语义、同进程 monkeypatch 或 `sys.modules`/import hook 安全。不得继续扩展跨模块 call graph、alias dataflow 或 Python expression evaluator。

**User-visible boundary:** 本计划没有 runtime consumer，不增加玩家能力。它只让后续 Exact-first 工作建立在可复核的代码所有权边界上；原 Task 3、持久化、worker、Resolver/API/UI、Catalog 发布、候选部署和微信验收仍未启动。

## 为什么替换原 Task 5 gate

原 Task 5 在五轮 fix/re-review 后仍不能 clean。`tests/gear_canonical_owner_gate_test.py` 从约 577 行增长到 2,600+ 行，并逐步解释 alias、lambda、callback、decorator、class、descriptor 和 namespace mutation，但最终仍允许下面的模块加载副作用零告警通过：

```python
from server.hidden_owner import mutate
mutate()
```

这不是漏掉一个 helper 名字，而是信任模型错误：`from x import y` 会执行 `x` 的整个模块；只递归 `y` 的函数体不能证明 import 安全，递归整个 import closure 又会遇到 cycle、partially initialized modules、conditional imports、stdlib/C extension、module cache 和 monkeypatch。原 Stop Gate 已要求停止该 schema，不得改名进入第六轮。

保留的真实成果：

- strict NFC、Unicode/control、UTF-8 byte bounds；
- 1 MiB / 64 containers / 10,000 JSON nodes、cycle 和 `RecursionError` fail-closed；
- seal → reload/verify invariant；
- Exact/Static Facts/Progression/Effect/Probe/CLI/Envelope sealed schemas；
- v1 与合法 v2 canonical bytes/key freeze；
- raw plugin text privacy、Catalog independence、generation 35 不变。

被替换的只有静态 owner gate 的证明模型；历史提交保留，不 reset/rebase。

## 可信声明与非声明

### 本计划完成后可以声明

- 五个受保护文件的 module-load AST 符合登记 profile；未知节点默认阻断。
- import module、symbol 与 alias 必须精确登记，禁止 star import、未登记 re-export 和动态 import。
- 四个 server owner 顶层只有声明、精确 immutable intrinsics 和受限 frozen dataclass。
- CLI 顶层只有精确 bootstrap、两个精确 class base 和单一 main guard 例外。
- 任何例外都绑定单一 AST node、理由、owner 与 canonical AST SHA-256；修改节点而不更新 registry 会失败。
- Canonical 业务语义仍由运行测试、sealed reload 和 identity freeze 证明。

### 本计划完成后仍不能声明

- 静态 gate 形式化证明了任意 Python 语义或传递 import graph 无副作用。
- 被信任的 project/stdlib/C-extension import 本身安全。
- gate 能抵抗任意同进程代码执行、pre-import monkeypatch、`sys.modules` 注入或 import hook。
- source/AST hash 证明业务语义正确，或可进入 canonical identity。
- Task 3、runtime、persistence、API/UI、Catalog candidate、微信验收或 release 已完成。

若未来要抵抗同进程篡改，需要进程隔离、只读签名构建与 runtime attestation；不属于本计划。

## Registry contract

新增 `tests/fixtures/gear_canonical_owner_registry.json`，至少包含：

```json
{
  "schemaVersion": 1,
  "proofClaim": "source_change_control_only",
  "targets": [
    {
      "path": "server/gear_exact_item_instance.py",
      "profile": "server_owner_declaration_v1",
      "sealedEntrypoints": ["..."],
      "publicCallables": ["..."],
      "exports": ["..."],
      "reexports": [],
      "imports": [{"module": "...", "symbol": null, "alias": "..."}],
      "importFallbackPairs": [],
      "exemptions": [
        {
          "id": "...",
          "role": "module_assignment",
          "binding": "...",
          "nodeKind": "Assign",
          "astSha256": "...",
          "reason": "...",
          "owner": "..."
        }
      ]
    }
  ],
  "digestSerialization": "python_ast_dump_v1"
}
```

Registry 必须满足：

- target 集合恰好是：
  - `server/gear_exact_item_instance.py`
  - `server/gear_exact_authority.py`
  - `server/simc_item_effect_support.py`
  - `server/simc_item_effect_probe.py`
  - `scripts/simc-item-effect-probe.py`
- 测试代码硬编码上述五文件集合并与 registry 做双向相等校验；registry 不能自己定义 coverage universe。
- physical import 按 module + symbol + alias 精确登记；module-only import 使用 `symbol: null`。不得用 module wildcard、name pattern 或“任意 callable”。
- relative/absolute import fallback 必须登记精确成对的 module/symbol/alias；检查只解析 target AST binding，绝不 import origin module 来判断 symbol 是否存在。
- `publicCallables` 覆盖所有非下划线本地 callable；`sealedEntrypoints` 必须是其受约束子集。`exports` 必须与 `__all__` 精确一致；imported public symbol 只能通过 `reexports` 记录其 export name 与 physical import binding。当前 `gear_exact_authority.py` 对 `seal_exact_static_facts` 的 re-export 必须显式登记。
- exemption 只能对应一个具体 AST node，含稳定 ID、reason、owner、role、binding（无 binding 的唯一 role 使用 `null`）、node kind 与 location-independent canonical AST SHA-256。匹配键固定为 `target path + role + binding + node kind + digest`，在该 target 内必须恰好命中一个 node；零命中或多命中都失败。
- canonical digest 固定 `python_ast_dump_v1`：对单个 node 使用 `ast.dump(node, annotate_fields=True, include_attributes=False)` 的 UTF-8 bytes 做 SHA-256；不得包含行号，不得执行 node。
- exemption 授权集合不由 registry 扩张。测试代码必须硬编码下面恰好九个 `(target, id, role, binding, node kind)`，并与 registry 双向完全相等；digest 只锁定已批准 node 的内容，不能授予第十种 exception：
  - `server/gear_exact_item_instance.py / EXACT_STATIC_FACTS_MAX_ABSOLUTE_NUMBER_ASSIGN / module_assignment / EXACT_STATIC_FACTS_MAX_ABSOLUTE_NUMBER / Assign`
  - `server/gear_exact_item_instance.py / EXACT_STATIC_FACTS_MAX_CANONICAL_BYTES_ASSIGN / module_assignment / EXACT_STATIC_FACTS_MAX_CANONICAL_BYTES / Assign`
  - `server/simc_item_effect_support.py / EFFECT_DYNAMIC_RECORD_KEYS_ASSIGN / module_assignment / _DYNAMIC_RECORD_KEYS / Assign`
  - `server/simc_item_effect_support.py / EFFECT_UNSUPPORTED_RECORD_KEYS_ASSIGN / module_assignment / _UNSUPPORTED_RECORD_KEYS / Assign`
  - `scripts/simc-item-effect-probe.py / CLI_ROOT_ASSIGNMENT / cli_bootstrap / ROOT / Assign`
  - `scripts/simc-item-effect-probe.py / CLI_PATH_GUARD / cli_bootstrap / null / If`
  - `scripts/simc-item-effect-probe.py / CLI_VALUE_ERROR_BASE / cli_class / _StrictJsonError / ClassDef`
  - `scripts/simc-item-effect-probe.py / CLI_ARGUMENT_PARSER_BASE / cli_class / _ReasonCodeArgumentParser / ClassDef`
  - `scripts/simc-item-effect-probe.py / CLI_MAIN_GUARD / cli_main_guard / null / If`
- 新增 exemption ID、遗漏已批准 ID、target/role/binding/node kind 变化，即使有唯一 digest 和理由也必须失败。需要改变这九项 universe 时必须先修改本计划并重新独立 review，不能在实现 PR 中顺带批准。
- `proofClaim` 固定为 `source_change_control_only`；任何 `authority_proof`、`python_semantics_proof` 等扩张声明必须失败。
- orphan、duplicate、unused、digest mismatch 和指向不存在 target/symbol 的记录全部 fail closed。

## Module-load profiles

### `server_owner_declaration_v1`

允许：

- 单一 docstring 与 `from __future__ import annotations`；
- registry 中精确登记的 imports；现有 relative import / `except ImportError` absolute fallback 只允许镜像 module/symbol/alias、无 `else/finally` 和额外语句；
- 无 decorator 的 `FunctionDef`/`AsyncFunctionDef`；default 仅 scalar/immutable literal，annotation 不得含 call、lambda、comprehension、named expression；
- 无 base/metaclass 的 class；class body仅 docstring、无 RHS field annotation 和同约束 method；
- 精确解析到 `dataclasses.dataclass(frozen=True)` 的 class decorator；alias、rebind、额外参数或其它 decorator 必须失败；
- 单一 `Name` 赋值，且名称只定义一次；值只允许 scalar/bytes/None、递归 immutable tuple、数字 literal 或 `UnaryOp(UAdd|USub, numeric literal)`、`__all__` string tuple；其它 `BinOp`/算术表达式必须是单 node exact exemption，不实现通用算术 evaluator；
- 两个声明式 intrinsic：`builtins.frozenset` 只消费 literal set/tuple，`re.compile` 只消费 literal pattern 与明确登记 flag；
- `simc_item_effect_support.py` 的 `_DYNAMIC_RECORD_KEYS` 与 `_UNSUPPORTED_RECORD_KEYS` 两个 `frozenset({*existing_set, ...})` assignment 不是通用 intrinsic，必须分别成为 single-node、digest-bound server exemption。

禁止：

- 任何其它 module-level `Call`，包括 imported/local helper、IIFE、lambda、factory 和 callable alias；
- list/dict/set 持久可变模块状态与 mutable factory；
- comprehension/generator、named expression、dynamic import、`exec/eval/compile`；
- call-valued default/annotation、任意未批准 decorator、class base/metaclass/descriptor/property；
- attribute/subscript assignment、`AugAssign`、`Delete`、global/nonlocal/module rebinding；
- `getattr/setattr/delattr/globals/locals/vars` 等动态 namespace 路径；
- module `__getattr__`、`__getattribute__`、`__dir__`；
- 除精确 import fallback 外的 module-level `if/for/while/with/match/try/assert/raise`。

### `simc_probe_cli_bootstrap_v1`

默认继承上述限制，只增加下面五个独立、digest-bound node exemption：

1. `CLI_ROOT_ASSIGNMENT`：当前 `ROOT = Path(__file__).resolve().parents[1]` assignment；
2. `CLI_PATH_GUARD`：当前单一 guarded `sys.path.insert`；
3. `CLI_VALUE_ERROR_BASE`：`_StrictJsonError(ValueError)`；
4. `CLI_ARGUMENT_PARSER_BASE`：`_ReasonCodeArgumentParser(argparse.ArgumentParser)`；
5. `CLI_MAIN_GUARD`：`if __name__ == "__main__": raise SystemExit(main())`。

任何额外 path mutation、class base、main guard statement、top-level call 或 bootstrap alias 都失败。CLI decoder/function body继续由其行为测试验证；本计划不改变 CLI 启动方式。

## Runtime function ownership boundary

Replacement gate 不再声称解释任意函数运行语义，也不递归 imported body。它必须机械保留以下 change-control：

- repository-wide deleted raw API absence；新增任意未登记的非下划线 local callable 必须失败；`publicCallables`、`exports`、`reexports`、`__all__` 与 `sealedEntrypoints` 必须精确一致；
- sealed entrypoint 必须只有一个定义，函数签名、sealed parameter/return boundary 与现有 contract tests 一致；
- protected files 的 exact import registry 不得引入第二套 canonical JSON/hash/Catalog owner；`CANONICAL_GEAR_SLOTS` 仍由 `gear_contracts.py` 唯一拥有，Progression 仍直接消费 production Track Authority owner；
- 明确、直接出现的 trim/coercion/sort/dedupe/JSON/hash/Catalog primitive 保留为非完备 lint；frozen v1 中现有 `json`/`hashlib`/legacy canonical helpers 只能用当前 exact function/node exceptions，不得扩大。该 lint 不得被控制面描述为 helper/alias/callback 完备证明；
- 必须保留并重跑 `tests/gear_canonical_kernel_test.py`、`tests/gear_contracts_test.py`、`packages/domain/src/gear-intent.test.ts`、Exact/Progression/Track Authority/Effect/Probe/CLI/Envelope suites、shared hostile mutation、seal/reload 和 frozen v1/v2 identity tests；
- 不保留或重建跨模块 body traversal、callable-argument binding、alias dataflow、factory-return inference、class execution model或动态 expression evaluator。

## Global constraints

- 不 reset/rebase 历史；`f4178c69` 通过 forward replacement 收敛。
- 不新增依赖、不联网、不下载、不部署。
- 不改变 Kernel/Exact v2 schema、合法 bytes/key、v1 identity、generation 35 或 Manifest/Catalog pointer。
- 唯一预期生产变化是将 `_NON_IDENTITY_CONTEXT_KEYS` 的持久 mutable set 改为 `frozenset`；它仅用于 membership，但仍必须用 v1 golden/legacy regression 证明零漂移。
- 其余四个 server owner 与 CLI 不因 gate 改变 runtime/启动语义。
- 原 Task 3 在本计划 Task 1-2 scoped review 与 fresh whole-branch review 同时 clean 前不得启动。

---

## Task 1: TDD forward-replace AST proof engine

**Files:**

- Create: `tests/fixtures/gear_canonical_owner_registry.json`
- Modify: `tests/gear_canonical_owner_gate_test.py`
- Modify: `server/gear_exact_item_instance.py`
- Test: `tests/project-owner-map.test.js`
- Test: `tests/backend-owner-map.test.js`
- Test: existing Kernel/Exact/Progression/Effect/Probe/CLI/Envelope and frozen-v1 suites

- [x] 先把旧 control-plane test 改为断言当前 Stop Gate 与 `none_pending_source_change_control_replacement`，使 committed baseline 不因过期文案失败；不得用无关失败充当 RED。
- [x] 写 registry schema/target completeness/`proofClaim`/public API/export/re-export RED。
- [x] 参数化五个 target，分别注入 `from server.hidden_owner import mutate; mutate()`；断言精确 `path + code + detail`。在 report 中记录预期失败测试名、数量和 reason code；NameError、checker 未定义或旧 control-plane assertion 不算 RED。
- [x] 写 module-load mutation RED：未登记 import/symbol/alias、star import、re-export、已批准 module 的未批准 symbol、`__import__`/`importlib`、IIFE/lambda、comprehension/generator、call-valued default/annotation、移除 future annotations、function/class decorator、base/metaclass/class-body call、mutable module state、namespace mutation、module hooks。
- [x] 写 registry RED：orphan、duplicate、wildcard exemption、digest mismatch、相同 AST 多命中、修改 exemption AST 未更新 digest、扩大 proof claim、未登记 public callable/`__all__`/re-export。
- [x] 写 positive controls：当前四个 server profile、两个 numeric Assign + 两个 starred-frozenset Assign 组成的四个 server exemptions、两个 frozen dataclass、五个 CLI node exemptions 与 `seal_exact_static_facts` re-export 必须被明确识别，不能依赖无关 finding“碰巧变绿”。
- [x] 删除/替换原跨模块 resolver、call graph、callback/alias/dataflow interpreter 和大规模 per-function callable allowlists；不得在新名字下保留相同模型。
- [x] 实现独立、小型 `_module_load_violations(path, tree, profile, registry)`；所有未知 AST 节点 fail closed。
- [x] 实现精确 import/symbol/alias/fallback/public/export/re-export registry、server/CLI profiles、`python_ast_dump_v1` digest 和 exception hygiene；绝不 import origin module。
- [x] physical import registry 使用独立的 file-wide、非 interprocedural syntactic scan，只收集 `Import`/`ImportFrom` nodes（包括函数体内的 physical import），不解析或遍历其周围函数调用语义；module-load checker 仍不进入普通 `FunctionDef.body`。
- [x] 将 `_NON_IDENTITY_CONTEXT_KEYS` 改为 `frozenset`；不做其它生产重构。
- [x] 让本 Task 全部 RED 转 GREEN；五个真实 target baseline 必须零 module-load violation。RED 与 GREEN 在同一 TDD task/report 内完成，只提交 GREEN，不提交有意失败的 Task。
- [x] 保留并改写 raw API/public callable/`__all__`/sealed signature/slot owner/production Track Authority/direct duplicate-owner lint；删除只服务于旧 interprocedural engine 的 alias/callback/factory/class-execution self-tests，并把 decorator/default/class/module-load 风险迁到 grammar tests。
- [x] 增加机器检查，禁止残留 `_ResolvedSymbol`、`_UnknownBinding`、`_CallableTarget`、`_ClassTarget`、`_ScopeBindingCollector`、`_resolve_expression`、`_called_targets`、`_bind_callable_target`、`_sealed_call_graph` 与旧 callable allowlist 常量；普通 `FunctionDef.body` 不得被 module-load checker 遍历，file-wide direct lint 必须独立且非递归。
- [x] 记录旧 gate 的净删除规模。Task 1 changed-file allowlist 仅允许 registry、owner-gate test 与 `gear_exact_item_instance.py` 的 set→frozenset；其余四个 production target 必须零 diff。
- [x] 重跑完整 semantic/frozen-identity/CLI 行为矩阵。
- [x] 运行 hostile snippets，确认原 module-load helper、alias/re-export、dynamic import、decorator/default/class/annotation 等均产生目标 finding。
- [x] 独立 spec 与 code-quality review 必须明确写出：gate 是 `source_change_control_only`，不是 Python semantics proof。

## Task 2: 收敛控制面与证据语言

**Files:**

- Modify: `docs/plans/2026-08-04-equipment-simulator-canonical-owner-change-control.md`
- Modify: `artifacts/releases/2026-08-04-equipment-simulator-exact-first/requirement.json`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/backend-owner-map.json`
- Modify: `docs/plans/README.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/plans/2026-08-04-equipment-simulator-canonical-kernel-redesign.md`
- Modify: `docs/plans/2026-08-04-equipment-simulator-canonical-kernel-implementation.md`
- Modify: `docs/plans/2026-08-04-equipment-simulator-exact-first-implementation.md`
- Modify: `tests/gear_canonical_owner_gate_test.py`（只允许更新 `test_control_plane_records_stop_gate_before_task2` 的 control-plane assertions；Task 1 gate/analyzer/mutations 不得改变）

- [x] 将 `owner authority proof`、`exact imported-callable owner gate` 等过度声明统一改为 `canonical ownership source change-control`。
- [x] 明确三层 owner：Kernel semantic owner、domain schema/business owner、source change-control registry。
- [x] owner maps/requirement 固定 `proofClaim=source_change_control_only`、`runtimeConsumers=[]`、`originalTask3Activated=false`。
- [x] owner maps 明确 registry 是 test-only source change-control，不是 runtime authority；每次 registry 更新必须出现在 review diff。
- [x] 记录五轮 Stop Gate 与 forward replacement，不把 163/9/40 绿测包装成原 gate clean。
- [x] Harness requirement、owner-map tests、`jq empty` 和 `git diff --check` 全绿后接受独立 review。

## Task 3: Fresh whole-branch closure review

- [x] 在 committed clean HEAD 重跑完整 Python/Vitest/Node/Harness/JSON/py_compile/diff matrix；全仓 TypeScript 仍单独记录已有 11 条 pre-existing TS4111，不得写成新绿。
- [x] 分别冻结并报告 shared valid Exact v2 key `exact-item-instance:sha256:e10e93ee691bc1073af958427aa06d451ba1132c5eb8ef0fa8654c70fb4670f6` 与 frozen v1 wrapper key `exact-item-instance:sha256:38b1a60808918f4bab94bd5bc0fd9240418ce72d631369beb054ec485ab636aa`。
- [x] 从 `7cf5c37bb1612ca703cbfbdef21ef31024d7e1e0` 生成 fresh whole-branch review package，由未参与实现的 reviewer 给出 Spec `PASS/FAIL` 与 Code Quality `APPROVED/CHANGES_REQUIRED`。
- [x] Reviewer 必须在最终 tree 重放 module-load helper 反例，验证 registry/exemption hygiene，并确认旧 interprocedural proof engine 已删除而非隐藏。
- [x] 本计划 Task 1-2 scoped reviews 与 whole-branch `PASS/APPROVED` 只完成 canonical foundation；当时写入的“Task 3 可开始”状态已被后续 readiness audit supersede，不再授予持久化执行权。

## Stop Gate

出现任一情况立即停止，不追加语法补丁：

- 新实现重新引入跨模块 call graph、alias/callback dataflow、runtime expression evaluator 或 import-body recursion；
- 上述旧 interpreter symbols 任一仍存在，或旧 engine 仅改名/留作 dead code；
- exemption 扩大为名字模式、模块/文件通配符、任意 callable 或无 AST digest 的特例；
- Task 1 超出 changed-file allowlist，或除 `_NON_IDENTITY_CONTEXT_KEYS` set→frozenset 外修改任何 production 行为；
- 为通过 gate 需要改变 Kernel、v1/v2 identity、CLI 启动语义、runtime、store/API/UI 或 generation 35；
- 五个 target 任一 module-load helper mutation 仍可零 finding；
- fresh reviewer 无法明确分开“语义测试证明什么”与“change-control gate 证明什么”；
- 完整 semantic/frozen-identity/CLI matrix 回归。

本计划通过仍只证明 Task 1-5 pure canonical foundation；不证明真实 SimC runtime、持久化、API、候选部署、微信体验或 release 完成。
