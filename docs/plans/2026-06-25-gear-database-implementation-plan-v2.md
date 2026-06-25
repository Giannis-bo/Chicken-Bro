# 装备自建数据库实施方案 v2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把装备自建数据库从“按问题补数据”升级为可周期执行、可审计、可回滚的 DB-first 装备数据生产线。

**Architecture:** 后端负责所有装备来源筛选、metadata 校验、SimC 变体生成、mod option 标准化和 health/blocker 输出；前端只消费 compact gear payload 与结构化 `gearBySlot/enhancementBySlot`。生产写库必须先 dry-run、备份、写入、读模型验收，再记录 roadmap/plan 证据。

**Tech Stack:** Python backend、SQLite、Battle.net Game Data API metadata、SimulationCraft JSON output、Raider.IO/WCL observed evidence、微信小程序前端、Node test harness、`unittest`。

## Current Baseline

截至 2026-06-25，生产装备库当前基线：

- Journal / item set / observed profile / crafted source 都进入 `websim_gear_sources`，但只有 active accepted source 能进入玩家可见候选。
- 玩家可见装备变体都进入 `websim_gear_variants`；`verified` 必须带 `itemStats` 或 `statSummary`，缺属性只能是 `partial` / `blocked`。
- 制造业已拆成普通可选属性制造装备与自带美化固定属性制造装备：
  - 普通 PVE 制造装备：54 件，`438` 条 verified variants。
  - 自带美化固定属性制造装备：30 件，`32` 条 verified variants。
  - 合计 `source_type='crafted'` 来源 `84` 条、crafted variants `470/470 verified`、`0 partial`。
- 前端装备替换、来源筛选、候选徽标、属性概览、强化配置都来自 compact payload，不按装备名或 itemId 特判。

## Task 1: Maintain Source Registries

**Files:**
- Modify: `server/websim_payload.py`
- Modify: `server/crafted_gear_backfill.py`
- Modify: `docs/gear-database-governance.md`
- Modify: `docs/roadmap.md`
- Create/Update: `docs/plans/YYYY-MM-DD-<source-update>.md`

**Step 1: Classify the update**

把每次装备更新归到明确类别：

- M+ / 团本 Journal loot
- 职业套装 item set
- 普通可选属性制造装备
- 自带美化固定属性制造装备
- 宝石 / 附魔 / Optional Reagent
- observed profile 反哺

**Step 2: Update allowlist / exclusion list**

普通制造业必须更新 `CURRENT_PVE_CRAFTED_METADATA_ITEMS`，错误或不支持条目更新 `EXCLUDED_CRAFTED_METADATA_ITEMS` / `UNSUPPORTED_CRAFTED_METADATA_ITEMS`。

当前 Midnight 重点规则：

- `251105 / 破法者之盾` 只能作为 dungeon 掉落来源，不允许 crafted。
- `237831 / 破法者的责难` 才是真实制造盾牌。
- `260370-260375`、`260377` 不能作为 crafted。
- `244774 / 以太流明践踏靴` 在单副属性模型实现前保持 unsupported。

**Step 3: Add tests before changing production data**

至少覆盖：

- allowlist item 能生成 governed crafted source。
- excluded item 即使带 `crafted_stats` 或 crafting-like metadata，也不能生成 crafted source。
- unsupported item 不生成双属性 `crafted_stats` option。

**Step 4: Run targeted tests**

Run:

```bash
python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_crafted_preview_catalog_items_from_profile_presets_builds_governed_seed tests.websim_payload_test.WebSimPayloadTest.test_crafted_catalog_items_from_metadata_builds_full_slot_seed
```

Expected: `OK`。

## Task 2: Execute Read-Only Audit Before Writes

**Files:**
- Modify: `server/crafted_gear_backfill.py`
- Modify: `docs/plans/YYYY-MM-DD-<source-update>.md`

**Step 1: Query current production shape**

只读检查：

- `websim_items` metadata 是否 verified。
- `websim_gear_sources` 是否存在错误 `source_type`。
- `websim_gear_variants` 是否有 stale `needs-variant`、异常装等、verified 缺属性。
- `websim_gear_mod_options` 是否有可读 `displayLabel` 和后端证据。

**Step 2: Dry-run**

制造业更新先跑：

```bash
python3 server/crafted_gear_backfill.py --db <db-path> --from-metadata --dry-run
```

Expected:

- 输出 item / track / variant 计数。
- 输出 skipped / unsupported / excluded 清单。
- 不写库。

**Step 3: Record blockers**

无法解释的新增、删除、partial 或 unsupported，必须先写入本次 plan 的 blocker 表，不进入正式写库。

## Task 3: Write Verified Variants

**Files:**
- Modify: `server/websim_payload.py`
- Modify: `server/crafted_gear_backfill.py`
- Test: `tests/websim_payload_test.py`

**Step 1: Back up production DB**

写库前必须有生产 SQLite 备份路径。没有备份不写库。

**Step 2: Write source rows**

`websim_gear_sources` 只写 accepted current source：

- Dungeon / raid / tier_set 使用 Battle.net Journal / item set evidence。
- Crafted 使用 governed source，例如 `crafted-governed-<itemId>`。
- Observed profile 可以保留证据，但不能替代官方 source 门禁。

**Step 3: Write variant rows**

`websim_gear_variants` 的 `verified` 条件：

- 普通官方装等：`derivedVariantSource=simulationcraft_item_level_probe`。
- 普通制造业：`derivedVariantSource=simulationcraft_crafted_item_probe`，并保留 `crafted_stats`。
- 自带美化制造业：`derivedVariantSource=simulationcraft_preembellished_item_probe`，允许 `craftedStatOptions=[]`，但必须带目标装备属性。

**Step 4: Reject fake readiness**

不允许：

- 用 Battle.net preview stats 伪装当前实例属性。
- 用 `ilevel` alone 把缺属性变体写成 `verified`。
- 用前端硬编码弥补分类或可用性。
- 把 Optional Reagent 美化当成装备自带美化。

## Task 4: Preserve Backend Read Contract

**Files:**
- Modify: `server/websim_payload.py`
- Test: `tests/websim_payload_test.py`

**Step 1: Keep compact payload complete**

compact candidate 必须保留：

- `sourceType` / `sourceTypes`
- source filter 计数所需字段
- verified `variants[]`
- `simcReady`
- `itemStats` / `statSummary`
- `craftedStatOptions`
- `hasBuiltInEmbellishment`
- `builtInEmbellishmentLabel`
- `embellishmentSource`
- mod option `displayLabel` / `displayStatus` / `evidenceSource`

**Step 2: Add regression tests**

Run targeted examples:

```bash
python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_crafted_fixed_stat_variant_without_crafted_stats_is_usable tests.websim_payload_test.WebSimPayloadTest.test_compact_gear_candidate_preserves_built_in_embellishment_marker tests.websim_payload_test.WebSimPayloadTest.test_metadata_built_in_embellishment_survives_simc_preset_merge
```

Expected: `OK`。

## Task 5: Keep Frontend as Consumer Only

**Files:**
- Modify: `pages/builds/detail.js`
- Modify: `pages/builds/detail.wxml`
- Modify: `pages/builds/detail.wxss`
- Test: `tests/builds-page.test.js`

**Step 1: Render only backend fields**

前端装备 sheet 只能展示后端结构化字段：

- “制造业”筛选来自 `sourceTypes`。
- “美化”徽标来自 `hasBuiltInEmbellishment` / `builtInEmbellishmentLabel`。
- `美化 x/2` 计数来自已选装备和 `enhancementBySlot` 的统一计算。
- 强化配置是否显示独立美化选项由装备 mod capability 和 built-in embellishment 决定。

**Step 2: Preserve incompatible cleanup**

切换装备后必须裁剪不兼容的 `enhancementBySlot`。自带美化装备同槽位不能再保存独立美化。

**Step 3: Run frontend tests**

Run:

```bash
node --test tests/builds-page.test.js
```

Expected: all tests pass。

## Task 6: Release Gate and Rollback

**Files:**
- Modify: `docs/roadmap.md`
- Modify: `docs/gear-database-governance.md`
- Create/Update: `docs/plans/YYYY-MM-DD-<source-update>.md`

**Step 1: Local verification**

Run:

```bash
git diff --check
python3 -m unittest tests.websim_payload_test
node --test tests/builds-page.test.js
```

Expected:

- no whitespace errors
- backend tests pass
- frontend tests pass

**Step 2: Code review**

Run local review or CodeRabbit if available:

```bash
coderabbit review --agent -t uncommitted -c AGENTS.md
```

If CodeRabbit is unavailable, run an explicit local review of the diff and record that CodeRabbit was unavailable.

**Step 3: Deploy only with owner authorization**

Default deploy command:

```bash
WOW_DEPLOY_SKIP_BOOTSTRAP=1 WOW_DEPLOY_START_ASYNC_SYNCS=0 ./server/deploy_lighthouse.sh
```

Do not run `git pull`, dependency installs, downloads, or production DB writes without explicit owner approval.

**Step 4: Production smoke**

Verify:

- `/health`
- `/api/data/health`
- representative `/api/websim/gear?compact=1`
- bad ID set does not return with `sourceTypes` containing the forbidden source type.

**Step 5: Record evidence**

Update `docs/roadmap.md` and the relevant plan with:

- backup path
- commands run
- write counts
- verified / partial / blocked counts
- compact smoke profile list
- known blockers and next action

## Next Known Extension

Engineering single-stat crafted gear, currently represented by `244774 / 以太流明践踏靴`, needs a separate implementation before it can be enabled:

- Add a one-stat crafted option model distinct from the six `crafted_stats` pairs.
- Generate SimC probe lines with the correct single-stat option.
- Add compact payload fields that do not pretend it has six pair options.
- Add frontend UI copy and validation for one-stat crafted options.
- Remove the item from `UNSUPPORTED_CRAFTED_METADATA_ITEMS` only after tests and production smoke pass.
