# 装备强化资格与已确认标记对齐实施计划

> **For agentic workers:** Apply the Harness Strict contract first. Use `superpowers:systematic-debugging` for the established regression and `superpowers:test-driven-development` for each behavioral change. Do not promote a release without fresh Harness evidence.

**Goal:** 让装备模拟只展示真实已确认的宝石、附魔和美化标记；由后端单一规则发布可编辑资格：宝石仅限固有槽位或当季打孔器支持的槽位，附魔按物品/副手类型过滤，美化仅限已验证制造装备且全身最多两件。

**User journey:** 玩家在装备详情浏览 16 个部位时，只会看到该件已确认的强化；打开编辑器时，只有真实可用的选项，第三件美化不会被接受或伪装为可用。导入的历史已封存强化仍可如实显示并计入限制，但不会反向扩大可编辑资格。

**Architecture:** `server/gear_socket_authority.py` 保持 socket 容量的唯一事实；`server/websim_payload.py` 与 `server/pg_gear_authority_loader.py` 以该季节支持范围提供候选 option group，并仅从经过验证的制造来源发布 `canEmbellish`。Resolver 的现有 `embellishmentMax` 继续是跨装备上限的唯一写入裁决。Taro 消费 `modCapabilities`、`allowed*OptionIds` 与 resolved selections，详情卡不再渲染未确认的占位标记。

**Tech stack:** Python `unittest`、React/Taro、TypeScript、Vitest、现有 `gearResolve` 和 Harness release packet。

## Scope and constraints

- 只改活动 backend capability/read-model 投影、活动 Taro `gear_detail` 消费者、design-system 的 confirmed-marker 表面、当前 UI 合同和本任务 packet；不改 legacy `pages/builds/detail.js`。
- 不新增前端资格规则：前端只能按后端的 item capability 和 canonical option key 过滤展示；不得根据图标、槽位名称或本地猜测制造来源开放选项。
- `neck`、`finger1`、`finger2` 是固有 socket 候选部位；`head`、`wrist`、`waist` 仅在后端为当前 item 发布 socket capacity 时可编辑。PvP 和 socket capacity 为零的装备必须没有可选宝石。
- 附魔 eligibility 保留 backend item-type 过滤：背部、胸部、腕部、腿部、脚部、两枚戒指、主手，以及非盾牌/非副手物品的副手；具体 option 仍以 `allowedEnchantOptionIds` 为准。
- 美化的 editable capability 只接受 item 或已选 variant 的 canonical `sourceType=crafted`；`embellishment`、`craftedStats` 等孤立展示字段不能自行授予 capability。已封存 source-only 选择不变，仍由 Resolver 计入 `embellishmentMax=2`。
- 目标几何、外层滚动、16 槽布局和任何 Catalog/Manifest 指针不在本任务中改变；不执行数据同步、迁移、部署或真实微信验收，除非后续另获授权。

## Task 1: Freeze the Strict contract and executable regressions

**Files:** `artifacts/releases/2026-07-29-gear-enhancement-rule-alignment/requirement.json`, this plan, `docs/plans/README.md`, server and Taro tests.

- [x] Record current truth, source owners, non-goals, acceptance evidence, manual acceptance items and rollback in the Strict requirement.
- [x] Add or retain RED regressions for: H/W/W socket option availability with zero-capacity items still blocked; non-crafted items cannot gain editable embellishment from descriptive fields; the existing Resolver 3/2 embellishment blocker; confirmed markers omit absent enhancement kinds.
- [x] Run the new RED tests and preserve the failures as the behavioral baseline before implementation.

## Task 2: Align backend capability publication

**Files:** `server/websim_payload.py`, `server/pg_gear_authority_loader.py`, related Python tests; only update `server/gear_socket_authority.py` if a test proves capacity authority itself is wrong.

- [x] Replace the legacy neck/ring-only socket option seed with the explicit current-season candidate scope (neck/rings plus Jewelbinder head/wrist/waist); retain per-item capacity as the gate.
- [x] Restrict editable `canEmbellish` to verified crafted source provenance for the current item/variant. Keep exact-template source-only recovery and the Resolver's global cap semantics intact.
- [x] Apply the same crafted-provenance clamp in the formal PG authority projection, so raw payload fields cannot reopen editability after the public payload is normalized.
- [x] Make the public and formal projections fail closed alike: only `verified` crafted source/variant records open editable embellishment; legacy `hasSocket` cannot attach gem options without a positive exact socket count.
- [x] Prove socket counts, item-type enchant filtering, crafted-only embellish capability, and `embellishmentMax=2` with targeted and existing Resolver unit tests.

## Task 3: Render only confirmed state in the active Taro detail surface

**Files:** `apps/mini-taro/src/pages/builds/gear-detail-model.ts`, `apps/mini-taro/src/pages/builds/gear-detail-model.test.ts`, `packages/design-system/src/components/GearDetailComponents.tsx`, its tests, and active gear-detail UI contracts.

- [x] Change the slot marker projection to emit a kind only when that exact slot has a selected gem, enchant, or embellishment.
- [x] Suppress the marker container when the projection is empty; markers must remain descriptive, not eligibility controls.
- [x] Present the resolver-owned embellishment cap in the summary where the current snapshot exposes it; do not hard-code or locally enforce a second cap.
- [x] Update the current interaction/truth/component contracts to state the confirmed-only and backend-owned boundaries.

## Task 4: Verify, review and prepare the handoff

- [x] Run targeted Python socket/payload/resolver tests and targeted Vitest model/component tests.
- [x] Run `npm run typecheck`, `npm run audit:ui-architecture`, `npm run build:weapp`, `git diff --check`, and a local CR against this requirement and plan.
- [x] Deploy and smoke the repaired exact candidate head with runtime parity, read-only PostgreSQL, bootstrap/compact-gear and no-backflow checks.
- [x] Re-exercise the two manual acceptance items against the repaired candidate; the user explicitly accepted the repaired candidate for Harness closure.

## Acceptance and rollback

1. No slot renders a gem/enchant/embellishment medallion unless that exact resolved enhancement is selected.
2. A socket option can reach head/wrist/waist only when current backend capacity is positive; neck/ring innate sockets remain available, while unsupported and PvP items remain unavailable.
3. Enchant options remain item-type and canonical-option filtered by backend publication.
4. Non-crafted equipment never exposes editable embellishment merely because a descriptive metadata field exists; crafted equipment does, and any third embellishment is blocked by the Resolver's backend-published maximum.
5. No active Manifest/catalog pointer, persisted user data, legacy page, target geometry or deployment state changes.

Rollback is a code rollback of this task branch. Because the task has no migration, sync or data write, there is no data rollback or pointer repair path.
