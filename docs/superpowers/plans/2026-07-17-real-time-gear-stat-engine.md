# 实时装备属性引擎 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让装备模拟在玩家确认换装、调整强化或导入模板后，本地立即计算并展示可与游戏非战斗常态面板对照的属性；SimC 不再决定该面板何时可用。

**Architecture:** 后端维护可追溯的 `gear-attribute-rulebook-v1`，并提供 Python 参考解释器；小程序使用同一份规则数据和相同 fixture 的 JavaScript 解释器即时计算。Resolver 继续拥有装备、强化和合法性事实，计算器只消费其静态输入；一个轻量、可取消的服务端属性审计用于交叉验证，绝不替换前端即时面板或调用 SimC。

**Tech Stack:** Python 3、现有 Resolver/Release authority、WeChat Mini Program JavaScript、Node test runner、Python `unittest`、现有 Harness candidate deployment。

## Global Constraints

- 基础面板口径固定为非战斗常态：等级、种族、职业/专精稳定被动、已确认装备/宝石/附魔/美化、稳定套装效果和明确的属性换算规则；不包含药水、饰品触发、战斗 Buff 或其他条件效果。
- `selection-intent-v1`、Resolver legality、observed-only 社区准入、Release/Manifest、强化容量和 PG-only 运行时边界保持不变。种族是独立的 `gear-attribute-character-v1` 输入，不能塞入或扩展 `selection-intent-v1`。
- 前端只能解释服务端返回的 `attributeCalculator` 规则上下文及已有受控装备/强化事实；不得从名称、ID、旧 snapshot 或 UI 文案猜测任何公式、variant 或来源。
- 即时面板不调用、不等待、不回退到 SimC `gear_stat_snapshot`。SimC snapshot、队列、worker、fencing 和健康语义保留给模拟、DPS、复杂条件效果和审计。
- 每个绿字必须同时保留 raw rating 与规则定义的百分比或效果；没有已证实百分比口径的属性必须显示明确效果口径，不能编造百分比。
- 未有已证实规则来源、完整角色上下文或已解析物品/强化事实时，显示“属性资料待补齐”，不得把静态装备和、旧配置结果或默认种族显示为最终角色面板。
- 第一批公开启用仅限有 source ledger、跨端 fixture 和英雄榜黄金样本的上下文；本计划先以法师冰霜/奥术案例建立垂直切片。其他职业/专精在证据齐全前保持 `rule_unavailable`，不做“全职业已准确”的声明。
- 任何从英雄榜、官方 API、SimC 上游或其他网络来源读取后再写入 fixture/规则账本的内容，都必须先取得用户对“将网络来源写入仓库”的明确许可；浏览、方案和本地 synthetic fixture 不需要该许可。
- 不新增依赖、不下载数据、不改数据库 schema；运行时代码完成后必须走最终 CI、一个最终候选部署、真实小程序验证、timer/backflow 检查和 rollback smoke。候选期间保持 `WOW_DEPLOY_START_ASYNC_SYNCS=0`。

---

## File Structure

| 文件 | 职责 |
| --- | --- |
| `server/gear_attribute_rules.py` | Rulebook schema、角色上下文解析、公开规则上下文和 rule availability gate。 |
| `server/gear_attribute_engine.py` | 不访问数据库、不运行 SimC 的 Python 参考属性解释器。 |
| `server/gear_attribute_api.py` | 以 canonical Resolver snapshot + 种族输入构造服务端参考审计结果。 |
| `tests/fixtures/gear-attribute-rulebook-v1.json` | 只用于双端算术/舍入 contract 的 synthetic rulebook；不是线上规则来源。 |
| `tests/fixtures/gear-attribute-calculator-cases-v1.json` | Python 与 JavaScript 共用的固定输入/输出案例。 |
| `tests/fixtures/gear-attribute-armory-v1.json` | 经用户授权后写入的英雄榜黄金样本；`candidate` 不能参与发布断言。 |
| `tests/gear_attribute_rules_test.py`、`tests/gear_attribute_engine_test.py`、`tests/gear_attribute_api_test.py` | 后端规则、算术、Resolver 绑定和 fail-closed coverage。 |
| `pages/builds/gear-attribute-engine.js` | 纯 JavaScript 解释器；不访问 `wx`、不请求网络、不保存状态。 |
| `tests/gear-attribute-engine.test.js` | 消费同一 JSON case fixture 的前端解释器 contract。 |
| `pages/builds/detail.js`、`.wxml`、`.wxss` | 种族选择、即时计算状态、属性差值、服务端审计状态和 SimC 展示解耦。 |
| `pages/builds/builds-api.js` | 轻量属性审计 API client；不得替换 SimC client。 |
| `server/websim_payload.py`、`server/news_backend.py` | 向 gear read payload 发布可解释的 `attributeCalculator`，并注册轻量审计 endpoint。 |
| `docs/gear-attribute-rule-source-ledger.md` | 每个生产 rule 的来源、适用上下文、revision、样本和状态。 |
| `docs/builds-architecture.md`、`docs/gear-simulation-full-chain-runbook.md` | 更新即时属性与 SimC 的最终 owner、状态和运维边界。 |

## Task 1: 建立版本化规则合同、来源账本和 fail-closed gate

**Files:**

- Create: `server/gear_attribute_rules.py`
- Create: `tests/gear_attribute_rules_test.py`
- Create: `tests/fixtures/gear-attribute-rulebook-v1.json`
- Create: `tests/fixtures/gear-attribute-calculator-cases-v1.json`
- Create: `docs/gear-attribute-rule-source-ledger.md`
- Modify: `docs/superpowers/specs/2026-07-17-real-time-gear-stat-engine-design.md:62-124`

**Interfaces:**

- Consumes: a JSON rulebook and `{classKey, specKey, level, raceKey}`.
- Produces: `public_attribute_calculator_context(rulebook, class_key, spec_key, level)` and either a sealed applicable rule or `ATTRIBUTE_RULE_UNAVAILABLE`.
- Produces: `parse_attribute_character_context(raw)` for the new `gear-attribute-character-v1` boundary; it accepts only `schemaRevision` and a bounded `raceKey`.

- [x] **Step 1: Write failing schema and availability tests**

Create the rulebook fixture with one synthetic, explicitly non-production mage context and add these tests. The synthetic values test the contract only; the source ledger must label the context `fixture_only`, so it cannot appear in public payloads.

```python
from server import gear_attribute_rules

def test_public_context_excludes_unverified_rulebook_context():
    context = gear_attribute_rules.public_attribute_calculator_context(
        fixture_rulebook(), class_key="mage", spec_key="frost", level=90
    )
    assert context["status"] == "rule_unavailable"
    assert context["problems"][0]["code"] == "ATTRIBUTE_RULE_UNAVAILABLE"

def test_character_context_accepts_only_explicit_race_key():
    parsed, issues = gear_attribute_rules.parse_attribute_character_context(
        {"schemaRevision": "gear-attribute-character-v1", "raceKey": "human"}
    )
    assert issues == []
    assert parsed == {"schemaRevision": "gear-attribute-character-v1", "raceKey": "human"}
```

Add negative cases for unknown fields, empty race, unknown race for an otherwise verified context, missing revision, missing `sourceRefs`, duplicate output keys and a rule marked `verified` without a golden sample ID.

- [x] **Step 2: Run the focused tests and confirm they fail**

Run: `python3 -m unittest tests.gear_attribute_rules_test`

Expected: FAIL because `server.gear_attribute_rules` and its public/fail-closed APIs do not exist.

- [x] **Step 3: Implement the narrow pure rule contract**

In `server/gear_attribute_rules.py`, define the following exact boundary. Keep the rulebook as ordinary data; do not add DB tables or network reads.

```python
ATTRIBUTE_RULEBOOK_SCHEMA_REVISION = "gear-attribute-rulebook-v1"
ATTRIBUTE_CHARACTER_CONTEXT_REVISION = "gear-attribute-character-v1"

def parse_attribute_character_context(raw: object) -> tuple[dict | None, list[dict]]:
    # Reject every key except schemaRevision and raceKey.
    # Return bounded lower-case raceKey only; never accept stats or client final values.

def validate_attribute_rulebook(raw: object) -> tuple[dict | None, list[dict]]:
    # Require sourceRefs and goldenSampleIds for each production context.
    # Allow fixture_only only when public=False.

def public_attribute_calculator_context(rulebook: dict, *, class_key: str, spec_key: str, level: int) -> dict:
    # Return {contractRevision, status, attributeRuleRevision, raceOptions, rules}
    # only if an applicable verified context exists; otherwise return bounded rule_unavailable.
```

Use a context key of `"{classKey}:{specKey}:{level}:{raceKey}"`. The schema must define `primaryKey`, `baseAttributes`, ordered `stableModifiers`, `resources`, and `secondaryRules`; each secondary rule names `inputKey`, `outputKey`, `label`, `basePercent`, `ratingPerPercent`, `precision`, `sourceRefs`, and `displayUnit`. Store source references and golden sample IDs in the rulebook, but strip only non-public implementation notes from the payload; do not strip revisions or sources.

Create `docs/gear-attribute-rule-source-ledger.md` with the columns `ruleContext`, `attributeRuleRevision`, `status`, `sourceRefs`, `goldenSampleIds`, `owner`, `lastVerifiedAt`, `coverage`. Its first rows must be `mage:frost:90:*` and `mage:arcane:90:*` with `status=blocked_pending_source_capture`, not invented production values.

- [x] **Step 4: Run rule tests and inspect the ledger gate**

Run: `python3 -m unittest tests.gear_attribute_rules_test`

Expected: PASS; synthetic contexts are usable only by explicit fixture tests, while public context requests return `rule_unavailable` until source and golden IDs are both verified.

- [x] **Step 5: Commit the rule-contract slice**

```bash
git add server/gear_attribute_rules.py tests/gear_attribute_rules_test.py tests/fixtures/gear-attribute-rulebook-v1.json tests/fixtures/gear-attribute-calculator-cases-v1.json docs/gear-attribute-rule-source-ledger.md docs/superpowers/specs/2026-07-17-real-time-gear-stat-engine-design.md
git commit -m "feat: add versioned gear attribute rule contract"
```

## Task 2: 实现服务端纯参考属性计算器

**Files:**

- Create: `server/gear_attribute_engine.py`
- Create: `tests/gear_attribute_engine_test.py`
- Modify: `tests/fixtures/gear-attribute-calculator-cases-v1.json`

**Interfaces:**

- Consumes: a validated applicable rule, `character_context`, resolver-owned `static_attributes`, and `stable_effects` that have explicit rule IDs.
- Produces: `gear-attribute-calculation-v1` with `status`, `attributeRuleRevision`, `primary`, `stamina`, `resources`, `secondary`, `conditionals`, `problems`, and `inputSignature`.
- Produces: no database access, no Resolver call, no SimC call and no use of preformatted `value` strings.

- [x] **Step 1: Write failing calculation/rounding tests from the shared fixture**

Use one fixture case with static input `{intellect: 500, stamina: 600, crit_rating: 35, haste_rating: 100, mastery_rating: 75, versatility_rating: 25, avoidance_rating: 20, leech_rating: 10, speed_rating: 5}` and a synthetic rule whose expected output is already stored in the JSON fixture. Assert all fields, including the original rating and one-decimal percentage string.

```python
from server.gear_attribute_engine import calculate_noncombat_attributes

result = calculate_noncombat_attributes(rule, {"raceKey": "human"}, fixture["staticAttributes"], [])
assert result["status"] == "calculated"
assert result["primary"] == {"key": "intellect", "rawValue": 1500, "value": "1,500"}
assert result["secondary"][0] == {
    "key": "crit", "label": "暴击", "rawValue": 35,
    "value": "35", "convertedValue": "6.0%", "displayUnit": "percent"
}
```

Also assert: modifier order is deterministic; zero rating still returns a row; `ratingPerPercent <= 0` blocks; an unsupported condition becomes a `conditional` row rather than changing totals; missing rule/race returns no numeric final panel; `inputSignature` changes for race, static value, stable modifier or rule revision.

- [x] **Step 2: Run the focused engine tests and confirm they fail**

Run: `python3 -m unittest tests.gear_attribute_engine_test`

Expected: FAIL because `calculate_noncombat_attributes` is unavailable.

- [x] **Step 3: Implement the reference evaluator with one ordered arithmetic path**

Implement these functions in `server/gear_attribute_engine.py`:

```python
ATTRIBUTE_CALCULATION_CONTRACT_REVISION = "gear-attribute-calculation-v1"

def format_attribute_value(value: float | int) -> str:
    return f"{round(value):,}" if float(value).is_integer() else f"{value:,.1f}".rstrip("0").rstrip(".")

def calculate_noncombat_attributes(rule: dict, character_context: dict, static_attributes: dict, stable_effects: list[dict]) -> dict:
    # 1. start from rule.baseAttributes; 2. add normalized static attributes;
    # 3. apply rule.stableModifiers in declared order; 4. derive resources;
    # 5. preserve each secondary raw rating and calculate its rule-defined effect.
    # On any validation issue return status="rule_unavailable" with no final numeric rows.
```

Normalize `crit`/`critical_strike` to `crit`, `haste`/`haste_rating` to `haste_rating`, and similarly for mastery, versatility, avoidance, leech and speed before arithmetic. Only modifiers present in the rule's allow-list may apply; every other effect goes to `conditionals` with `included=false`. The reference result must never read `gear_stat_snapshot`, SimC JSON or a client supplied final stat.

- [x] **Step 4: Run reference tests and the existing Resolver static-attribute test**

Run: `python3 -m unittest tests.gear_attribute_engine_test tests.gear_resolver_test`

Expected: PASS; the resolver remains a static-input provider and the new evaluator produces deterministic complete rows from the fixture.

- [x] **Step 5: Commit the server-calculator slice**

```bash
git add server/gear_attribute_engine.py tests/gear_attribute_engine_test.py tests/fixtures/gear-attribute-calculator-cases-v1.json
git commit -m "feat: add deterministic gear attribute reference engine"
```

## Task 3: 实现小程序纯解释器并锁定跨端 fixture parity

**Files:**

- Create: `pages/builds/gear-attribute-engine.js`
- Create: `tests/gear-attribute-engine.test.js`
- Modify: `tests/fixtures/gear-attribute-calculator-cases-v1.json`
- Modify: `tests/builds-page.test.js:29-121`

**Interfaces:**

- Consumes: the same public rule shape, character context, static attributes and stable effects as `calculate_noncombat_attributes`.
- Produces: the same `gear-attribute-calculation-v1` fields and formatting, with no `wx`, HTTP or `setData` dependency.
- Produces: an exported `calculateNonCombatAttributes(rule, characterContext, staticAttributes, stableEffects)` function.

- [x] **Step 1: Write a Node test that reads every shared fixture case**

```javascript
const cases = require('./fixtures/gear-attribute-calculator-cases-v1.json')
const { calculateNonCombatAttributes } = require('../pages/builds/gear-attribute-engine')

for (const fixture of cases.cases) {
  test(`attribute fixture ${fixture.id}`, () => {
    assert.deepEqual(
      calculateNonCombatAttributes(fixture.rule, fixture.characterContext, fixture.staticAttributes, fixture.stableEffects),
      fixture.expected
    )
  })
}
```

Add explicit tests that a missing race, `fixture_only` rule, unsupported secondary rule and unrecognized stable effect produce the same bounded `rule_unavailable`/`conditional` output as Python. Extend `loadBuildsDetailPageConfig` in `tests/builds-page.test.js` so `detail.js` can require the new module in its existing VM loader.

- [x] **Step 2: Run the new Node tests and confirm they fail**

Run: `node --test tests/gear-attribute-engine.test.js`

Expected: FAIL because `pages/builds/gear-attribute-engine.js` does not exist.

- [x] **Step 3: Implement the JavaScript interpreter without UI coupling**

```javascript
function calculateNonCombatAttributes(rule, characterContext, staticAttributes, stableEffects) {
  // Use the same normalized key map, modifier order, precision and row schema as Python.
  // Return { contractRevision, status, attributeRuleRevision, primary, stamina,
  // resources, secondary, conditionals, problems, inputSignature }.
}

module.exports = { calculateNonCombatAttributes, formatAttributeValue }
```

Use plain objects and `Number.isFinite`; do not import `detail.js`, do not duplicate item parsing, do not read `gearStatSnapshot`, and do not make a default race selection. The test fixture is the exact parity surface: any added output field must first be added to the shared fixture and Python test.

- [x] **Step 4: Run both language suites against the same cases**

Run: `python3 -m unittest tests.gear_attribute_engine_test && node --test tests/gear-attribute-engine.test.js`

Expected: PASS; every JSON fixture has identical Python and JavaScript output.

- [x] **Step 5: Commit the client-calculator slice**

```bash
git add pages/builds/gear-attribute-engine.js tests/gear-attribute-engine.test.js tests/builds-page.test.js tests/fixtures/gear-attribute-calculator-cases-v1.json
git commit -m "feat: add client gear attribute interpreter"
```

## Task 4: 发布受控计算上下文并提供非阻塞服务端审计

**Files:**

- Create: `server/gear_attribute_api.py`
- Create: `tests/gear_attribute_api_test.py`
- Modify: `server/websim_payload.py:20383-20640`
- Modify: `server/news_backend.py:12800-12837`
- Modify: `pages/builds/websim-api.js`
- Modify: `tests/websim_payload_test.py`
- Modify: `tests/news_backend_test.py`

**Interfaces:**

- `GET /api/websim/gear` adds `attributeCalculator` with `{contractRevision, status, attributeRuleRevision, raceOptions, rules, problems}`. It is additive and never exposes fixture-only contexts.
- `POST /api/websim/gear/attributes` accepts `{selectionIntent, characterContext}` and returns the existing result envelope with `{resolvedGearSignature, attributeCalculation}`.
- `requestWebsimGearAttributeAudit(selectionIntent, characterContext)` is a best-effort client API. It never calls the SimC endpoint and callers must not use it as the panel's source of truth.

- [x] **Step 1: Write failing payload and endpoint tests**

```python
payload = websim_payload.get_websim_gear(conn, "mage", "frost", compact=True)
assert payload["attributeCalculator"]["status"] == "rule_unavailable"
assert "staticAttributes" not in payload["attributeCalculator"]

status, envelope = gear_attribute_api.calculate_attributes_for_selection(
    {"selectionIntent": valid_intent, "characterContext": {"schemaRevision": "gear-attribute-character-v1", "raceKey": "human"}},
    store=store, simc_runtime_revision="ignored-by-attribute-engine", request_id="attribute-test"
)
assert status == 200
assert envelope["data"]["attributeCalculation"]["status"] == "calculated"
```

Add negative HTTP cases for client-authored static values, missing character context, invalid race, Resolver rejection and unverified rules. Assert that no test double for `run_websim_stat_simcraft` or the snapshot store is touched.

- [x] **Step 2: Run payload/API tests and confirm they fail**

Run: `python3 -m unittest tests.gear_attribute_api_test tests.websim_payload_test tests.news_backend_test`

Expected: FAIL because the calculator payload and `/api/websim/gear/attributes` route do not exist.

- [x] **Step 3: Implement the additive context serializer and audit endpoint**

In `server/websim_payload.py`, append `attributeCalculator` to the final `get_websim_gear` payload using `public_attribute_calculator_context`; do not use `blocked_stat_snapshot` to represent rule availability.

In `server/gear_attribute_api.py`, implement:

```python
def calculate_attributes_for_selection(raw_request, *, store, simc_runtime_revision, request_id):
    request = raw_request if isinstance(raw_request, dict) else {}
    character, issues = parse_attribute_character_context(request.get("characterContext"))
    if issues:
        return bounded_attribute_problem_envelope(issues, request_id)
    status, resolved = resolve_selection_intent(request.get("selectionIntent"), store=store,
        simc_runtime_revision=simc_runtime_revision, request_id=request_id)
    if status != 200 or resolved.get("status") != "resolved":
        return status, resolved
    # Build input only from resolved["data"]["staticAttributes"] and sealed stable effects.
```

Register the route before `/api/websim/gear/stats` in `server/news_backend.py`. In `pages/builds/builds-api.js`, add the client wrapper with the normal API error envelope but do not import it into the old SimC snapshot client.

- [x] **Step 4: Run focused server/API tests and prove SimC isolation**

Run: `python3 -m unittest tests.gear_attribute_api_test tests.websim_payload_test tests.news_backend_test`

Expected: PASS; attribute audit returns a deterministic result or bounded rule problem, and the SimC mock invocation count is zero.

- [x] **Step 5: Commit the context and audit slice**

```bash
git add server/gear_attribute_api.py server/websim_payload.py server/news_backend.py pages/builds/builds-api.js tests/gear_attribute_api_test.py tests/websim_payload_test.py tests/news_backend_test.py
git commit -m "feat: expose deterministic gear attribute context"
```

## Task 5: 在装备页引入显式种族上下文与即时计算状态

**Files:**

- Modify: `pages/builds/detail.js:1275-1520`, `pages/builds/detail.js:5890-5910`, `pages/builds/detail.js:6800-7420`
- Modify: `pages/builds/detail.wxml:65-105`
- Modify: `pages/builds/detail.wxss`
- Modify: `tests/builds-page.test.js:29-121`, `tests/builds-page.test.js:1120-1195`

**Interfaces:**

- Page data gains `selectedRaceKey`, `selectedRaceName`, `gearAttributeState` and `gearAttributeAudit`.
- `refreshGearAttributePanel(page, {previousCalculation})` consumes the current selection's locally derived static totals plus `gearPayload.attributeCalculator`; it synchronously updates `gearAttributePanel` and returns no Promise.
- `selectGearAttributeRace(event)` accepts a race from server-provided `raceOptions`; it never changes `selection-intent-v1` and never starts SimC.

- [ ] **Step 1: Write failing page-state tests for explicit race and immediate recompute**

```javascript
const pageConfig = loadBuildsDetailPageConfig({ exposeDetailHelpers: true })
const page = buildResolvedGearPage({
  attributeCalculator: verifiedMageRuleContext,
  selectedRaceKey: ''
})

pageConfig.refreshGearAttributePanel.call(page)
assert.equal(page.data.gearAttributePanel.status, 'character_context_required')
assert.match(page.data.gearAttributePanel.summary, /请选择种族/)

pageConfig.selectGearAttributeRace.call(page, { currentTarget: { dataset: { key: 'human' } } })
assert.equal(page.data.gearAttributePanel.status, 'calculated')
assert.equal(page.data.gearAttributePanel.statRows.find((row) => row.key === 'haste').convertedValue, '2.0%')
```

Add a same-event-loop test: set a new selected head item, call the existing confirm handler, and assert the panel's `haste.rawValue`, `convertedValue` and `deltaValue` update before the deferred `requestWebsimGearResolve` promise resolves. Add a missing-rule test that asserts no static integer is labeled as a final stat.

- [ ] **Step 2: Run page tests and confirm they fail**

Run: `node --test tests/builds-page.test.js`

Expected: FAIL because race state, immediate attribute state and `refreshGearAttributePanel` do not exist.

- [ ] **Step 3: Add explicit race selection and local panel state**

In `pages/builds/detail.js`, import `calculateNonCombatAttributes` and add:

```javascript
function gearAttributeCharacterContext(data) {
  return data && data.selectedRaceKey
    ? { schemaRevision: 'gear-attribute-character-v1', raceKey: data.selectedRaceKey }
    : null
}

function refreshGearAttributePanel(page, options = {}) {
  const input = localAttributeInputFromCurrentGear(page)
  const result = calculateNonCombatAttributes(input.rule, input.characterContext, input.staticAttributes, input.stableEffects)
  page.setData({ gearAttributeState: result, gearAttributePanel: renderGearAttributePanel(result, options.previousCalculation) })
  return result
}
```

`localAttributeInputFromCurrentGear` must reuse the existing controlled item/option parsing (`gearStatEntriesForItem` and `gearStatEntriesForEnhancementOption`) but output only normalized numeric totals; it must not read `gearStatSnapshot`. Add a compact custom race sheet using only `gearPayload.attributeCalculator.raceOptions`. Default race is empty; show a clear required state instead of choosing the simulator page's current default.

In WXML, place a small identity row above the attribute grid. It must display `种族 / 请选择种族` when missing, use the existing dark-sheet interaction style, and display a separate calculation status. In WXSS, reuse the panel's existing borders and typography; do not introduce a native picker/button that can reintroduce WebView composition issues.

- [ ] **Step 4: Run the page tests and inspect the no-race state**

Run: `node --test tests/builds-page.test.js`

Expected: PASS; a user cannot see a fake final panel without a selected race, and an item change recalculates locally without waiting for Resolver or SimC.

- [ ] **Step 5: Commit the identity and immediate-state slice**

```bash
git add pages/builds/detail.js pages/builds/detail.wxml pages/builds/detail.wxss tests/builds-page.test.js
git commit -m "feat: calculate gear attributes locally with race context"
```

## Task 6: 将最终属性面板与 SimC snapshot 展示路径彻底解耦

**Files:**

- Modify: `pages/builds/detail.js:370-430`, `pages/builds/detail.js:1422-1510`, `pages/builds/detail.js:2258-2328`, `pages/builds/detail.js:6260-6390`, `pages/builds/detail.js:6688-6755`
- Modify: `pages/builds/detail.wxml:65-105`
- Modify: `tests/builds-page.test.js:2898-2968`, `tests/builds-page.test.js:8658-8923`, `tests/builds-page.test.js:9077-9127`
- Modify: `pages/simulator/simc.js`
- Modify: `tests/simulator-page.test.js`

**Interfaces:**

- `gearAttributePanel` reads only `gearAttributeState`; its rows include `rawValue`, `convertedValue`/`effectValue`, `deltaValue`, `calculationStatus` and `attributeRuleRevision`.
- `gearStatSnapshot` remains a SimC-only object for simulator/template metadata. It may be stale/read-only but must never add values or converted percentages to the gear attribute panel.
- `maybeRefreshGearStatsForPage` remains callable only by explicit SimC/saved-template flows; gear load, item confirmation, enhancement confirmation, reset, saved apply, community import and scenario switch no longer invoke it automatically.

- [ ] **Step 1: Rewrite failing regression tests around the new boundary**

Replace the load-time expectation `gear detail requests SimC stat snapshot when gear and talents are complete` with an assertion that `requestWebsimGearStatSnapshot` is never called while an immediate local panel is calculated. Keep a direct `refreshGearStats` compatibility test to prove the existing polling/fencing behavior still works when a simulator flow explicitly invokes it.

```javascript
assert.equal(simcSnapshotCalls, 0)
assert.equal(page.data.gearAttributePanel.statRows.find((row) => row.key === 'crit').convertedValue, '6.0%')
assert.equal(page.data.gearAttributePanel.attributeRuleRevision, 'mage-fixture-r1')
await pageConfig.refreshGearStats.call(simulatorPage, requestPayload, 'explicit-simc-request')
assert.equal(simulatorPage.data.gearStatSnapshot.statStatus, 'verified')
```

Add a stale-SimC test whose snapshot reports `intellect=999999` and `crit=99.9%`; assert the displayed local panel keeps the rule-engine numbers. Add import/manual parity: applying an imported sealed selection and choosing the same slots/options manually produces deep-equal `gearAttributeState` including `inputSignature`.

- [ ] **Step 2: Run frontend and simulator tests and confirm they fail**

Run: `node --test tests/builds-page.test.js tests/simulator-page.test.js`

Expected: FAIL because `canonicalGearAttributePanel` still reads `verifiedGearStatSnapshot` and the gear page still schedules SimC refreshes.

- [ ] **Step 3: Remove snapshot reads from the panel and automatic triggers from gear interaction**

Replace the current panel composition with a renderer whose only numeric source is `gearAttributeState`:

```javascript
function renderGearAttributePanel(calculation, previous) {
  if (calculation.status !== 'calculated') return unavailableGearAttributePanel(calculation.problems)
  return {
    visible: true,
    status: 'calculated',
    summary: `规则 ${calculation.attributeRuleRevision}`,
    attributeRuleRevision: calculation.attributeRuleRevision,
    statRows: metricRowsWithDelta(calculation, previous),
    enhancementRows: currentEnhancementUsageRows()
  }
}
```

Delete the `verifiedGearStatSnapshot` conversion fallback from `buildGearAttributePanel` and `canonicalGearAttributePanel`. Change `resolveOrRefreshGearForPage` to update the local panel before and after Resolver reconciliation, but not chain `maybeRefreshGearStatsForPage`. Remove the existing automatic calls at gear-load and scenario-switch sites. Keep `refreshGearStats`, `compactVerifiedGearStatSnapshot` and saved-template SimC metadata unchanged except that they no longer mutate `gearAttributePanel`.

In `pages/simulator/simc.js`, continue consuming a verified SimC snapshot only for the simulator's own summary; do not read or overwrite `gearAttributeState` from the builds page.

- [ ] **Step 4: Run focused regression tests and diff the two state lanes**

Run: `node --test tests/builds-page.test.js tests/simulator-page.test.js`

Expected: PASS; changing gear refreshes local values immediately, an explicit SimC request still follows its old pending/verified fencing, and neither lane overwrites the other.

- [ ] **Step 5: Commit the decoupling slice**

```bash
git add pages/builds/detail.js pages/builds/detail.wxml pages/simulator/simc.js tests/builds-page.test.js tests/simulator-page.test.js
git commit -m "refactor: decouple gear attributes from simc snapshots"
```

## Task 7: 建档法师黄金样本并开启首个 production rule context

**Files:**

- Modify: `docs/gear-attribute-rule-source-ledger.md`
- Modify: `tests/fixtures/gear-attribute-rulebook-v1.json`
- Create: `tests/fixtures/gear-attribute-armory-v1.json`
- Modify: `tests/gear_attribute_engine_test.py`
- Modify: `tests/gear_attribute_api_test.py`
- Modify: `tests/gear-attribute-engine.test.js`
- Modify: `docs/superpowers/specs/2026-07-17-real-time-gear-stat-engine-design.md:136-166`

**Interfaces:**

- Consumes: explicitly authorized captures for each candidate character: official character URL, captured timestamp, region/realm/name, class/spec/race/level, 16 selected instances, enhancements and visible non-combat expected fields.
- Produces: a `verified` rulebook context only when every referenced source and at least one golden sample ID exists; otherwise it remains `blocked_pending_source_capture`.
- Produces: field-by-field test failures that say whether the mismatch is input, rule, raw rating, percentage/effect or a conditional exclusion.

- [ ] **Step 1: Obtain the required network-write approval before capturing any external source into the repository**

Ask exactly: `我需要读取英雄榜/官方角色资料并将角色装备、属性和抓取时间写入 tests fixture 作为黄金样本。是否允许把这些网络来源内容写入仓库？`

Do not browse-and-save, paste character data into fixtures, or mark a rule verified until the user explicitly grants this approval. Existing screenshots remain discussion evidence and may only be stored as `candidate` metadata if the user supplies their exact immutable input manually.

- [ ] **Step 2: Write failing golden tests after approval**

Create two entries, `mage-frost-armory-<capturedAt>` and `mage-arcane-armory-<capturedAt>`, with explicit `candidate` status first. After identity and full input agree, promote each entry to `verified` and add tests:

```python
for sample in verified_armory_samples():
    actual = calculate_noncombat_attributes(sample["rule"], sample["characterContext"], sample["staticAttributes"], sample["stableEffects"])
    self.assertEqual(actual["primary"], sample["expected"]["primary"], sample["id"])
    self.assertEqual(actual["stamina"], sample["expected"]["stamina"], sample["id"])
    self.assertEqual(actual["secondary"], sample["expected"]["secondary"], sample["id"])
```

Mirror the same fixture loop in `tests/gear-attribute-engine.test.js`. Assert a `candidate` sample is ignored by production enablement and cannot satisfy `goldenSampleIds` validation.

- [ ] **Step 3: Promote only fully evidenced mage contexts**

For each promoted sample, populate actual source references in `docs/gear-attribute-rule-source-ledger.md`, bind the exact sample IDs in the rulebook, and change only the matching `mage:frost:90:<race>` or `mage:arcane:90:<race>` context to `verified`. Leave Fire and every other unsupported race/spec context blocked. Do not infer missing race, talent, variant, item-level, enhancement or temporary-effect data from a screenshot.

Use the existing references as the comparison fields, not as formula inputs: Frost currently targets `智力 2,485 / 耐力 23,001 / 暴击 26% / 急速 21% / 精通 54%`; Arcane currently targets `智力 2,462 / 耐力 22,938 / 暴击 19% / 急速 23% / 精通 37% / 全能 7%`. Replace those candidate values only with values from the confirmed capture record.

- [ ] **Step 4: Run cross-runtime golden tests and inspect release gating**

Run: `python3 -m unittest tests.gear_attribute_rules_test tests.gear_attribute_engine_test tests.gear_attribute_api_test && node --test tests/gear-attribute-engine.test.js tests/builds-page.test.js`

Expected: PASS; only the two evidenced mage contexts return `attributeCalculator.status == "available"`, candidate samples do not enable a rule, and every golden field is compared individually.

- [ ] **Step 5: Commit the authorized mage-evidence slice**

```bash
git add docs/gear-attribute-rule-source-ledger.md tests/fixtures/gear-attribute-rulebook-v1.json tests/fixtures/gear-attribute-armory-v1.json tests/gear_attribute_engine_test.py tests/gear_attribute_api_test.py tests/gear-attribute-engine.test.js docs/superpowers/specs/2026-07-17-real-time-gear-stat-engine-design.md
git commit -m "test: verify mage gear attribute golden samples"
```

## Task 8: 候选发布、真实小程序验证与 Harness 收口

**Files:**

- Modify: `docs/builds-architecture.md`
- Modify: `docs/gear-simulation-full-chain-runbook.md`
- Modify: `docs/roadmap.md:3`
- Modify: `artifacts/releases/2026-07-17-real-time-gear-stat-engine/requirement.json`
- Create: `artifacts/releases/2026-07-17-real-time-gear-stat-engine/evidence.json`
- Create: `artifacts/releases/2026-07-17-real-time-gear-stat-engine/manifest.json`

**Interfaces:**

- Consumes: final runtime commit identity, focused test output, final CI, candidate identity/file parity, current health/API/UI evidence, timer/backflow result and rollback proof.
- Produces: a truthful Harness evidence packet whose highest level advances only as far as actual candidate/live evidence permits.

- [ ] **Step 1: Update documentation tests and release requirement before candidate deployment**

Document these exact post-cutover statements:

```text
装备模拟基础属性 = versioned deterministic local calculation.
SimC stat snapshot = simulation/audit-only; its pending, blocked or worker-down state cannot block the base panel.
attributeRuleRevision + inputSignature identify every displayed calculated result.
```

In `requirement.json`, retain `releaseTrigger="user_visible_runtime"`, update `status` only to the highest earned state, and list `feature_hide` plus `code_rollback`. Do not mark `live_verified` before the candidate and current runtime evidence exists.

- [ ] **Step 2: Run targeted development suites, then one final local CR**

Run:

```bash
python3 -m unittest tests.gear_attribute_rules_test tests.gear_attribute_engine_test tests.gear_attribute_api_test tests.gear_resolver_test tests.websim_payload_test tests.news_backend_test
node --test tests/gear-attribute-engine.test.js tests/builds-page.test.js tests/simulator-page.test.js
git diff --check
```

Expected: PASS. Perform one local whole-branch CR focused on race absence, stale resolver responses, forged client facts, unverified rule publication, percentage rounding, SimC re-coupling and saved-template compatibility.

- [ ] **Step 3: Deploy only the final candidate head and run bounded smoke**

After final CI passes and before merge, deploy the final candidate once. Record branch/commit/build identity and runtime file parity. Smoke these cases:

```text
1. Frost and Arcane evidenced contexts: community import and identical manual selection produce identical rule revision/input signature/rows.
2. Confirmed item replacement updates panel within p95 <= 100ms on real mini-program/DevTools evidence.
3. No race and unavailable-rule contexts show bounded missing-data state, never static final totals.
4. Stop or force-fail the SimC stat worker: base panel still changes immediately; explicit SimC flow reports its own truthful state.
5. POST /api/websim/gear/attributes rejects forged fields and does not enqueue/run SimC.
6. Health, timers, sync/backfill and `WOW_DEPLOY_START_ASYNC_SYNCS=0` show no rule/snapshot backflow.
```

- [ ] **Step 4: Verify rollback and publish the evidence packet**

Exercise `feature_hide` against the real-time panel flag or equivalent UI gate, then restore the candidate without altering Resolver/Release data. Record that `code_rollback` returns to the prior presentation without a DB restore. Create `evidence.json` with actual commands, timestamps, outputs, candidate identity, smoke, timer/backflow and rollback results. Generate the manifest, then run:

```bash
node scripts/project-harness.js --check --requirement-file artifacts/releases/2026-07-17-real-time-gear-stat-engine/requirement.json --evidence-file artifacts/releases/2026-07-17-real-time-gear-stat-engine/evidence.json --base origin/main
node scripts/verify-project.js --profile full --release artifacts/releases/2026-07-17-real-time-gear-stat-engine --base origin/main
```

Expected: PASS; evidence status matches the strongest evidence actually collected.

- [ ] **Step 5: Commit the documentation/evidence slice after the candidate passes**

```bash
git add docs/builds-architecture.md docs/gear-simulation-full-chain-runbook.md docs/roadmap.md artifacts/releases/2026-07-17-real-time-gear-stat-engine
git commit -m "docs: record real-time gear attribute release evidence"
```

## Self-Review

### Spec coverage

- Non-combat scope, stable versus conditional separation, raw plus percent/effect output, race requirement and no fake static final panel are implemented by Tasks 1, 2, 5 and 6.
- Backend-owned facts, versioned rule revision, client/server rule semantics and source provenance are implemented by Tasks 1–4.
- Community import/manual parity, stale response safety and local interaction latency are covered by Tasks 5–6 and candidate smoke in Task 8.
- SimC decoupling while preserving simulator/snapshot behavior is covered by Task 6 and the worker-down smoke in Task 8.
- The Frost/Arcane comparisons are explicitly gated on identity-complete golden samples in Task 7; no screenshot-only fixture is promoted.
- Candidate deployment, rollback, current evidence and roadmap/runbook updates are covered only in Task 8.

### Placeholder scan

The plan contains no implementation placeholder markers. The only future permission gate is Task 7's explicit network-write approval, required by repository policy before external character data can enter a fixture.

### Type consistency

- Rulebook revision: `gear-attribute-rulebook-v1`.
- Character input revision: `gear-attribute-character-v1`.
- Calculation result revision: `gear-attribute-calculation-v1`.
- Python entry point: `calculate_noncombat_attributes`; JavaScript entry point: `calculateNonCombatAttributes`.
- Public gear payload key: `attributeCalculator`; audited result key: `attributeCalculation`; page state key: `gearAttributeState`.

## Execution Notes

Execute tasks in order. The first runtime-visible vertical may not be exposed until Task 7 has both user-authorized source capture and verified golden samples. Unsupported contexts must remain truthful `rule_unavailable`; they are not acceptable candidates for a global rollout claim.
