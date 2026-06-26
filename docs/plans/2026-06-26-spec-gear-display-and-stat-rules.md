# 职业专精装备展示与主属性过滤方案

**Goal:** 在装备模拟中把“可装备候选”和“装备明细展示”统一到职业专精规则：武器明细显示单手 / 双手 / 远程 / 副手标签，唯一装备显示装备标签，候选装备和制造业属性组合只展示当前专精可用的主属性。

**Architecture:** 后端读模型负责证据审计、候选过滤、属性归一化和 compact payload 字段；前端只消费 `equipmentBadges`、`primaryStatKey`、`handednessLabel`、`statSummary` 等 display-ready 字段，并保留同规则的本地交互兜底。SimC serializer 继续 fail closed：即使前端提交 stale 或不兼容装备，也不能写入可执行 profile。

## Evidence Chain

本轮证据按优先级分层：

1. **Blizzard 官方职业页**：作为全职业武器可用性与专精偏好武器主证据。官方页包含 `Available Weapons` 和各专精 `Preferred Weapon(s)`，覆盖本轮武器栏过滤矩阵。
   - Death Knight: https://worldofwarcraft.blizzard.com/en-us/game/classes/death-knight
   - Demon Hunter: https://worldofwarcraft.blizzard.com/en-us/game/classes/demon-hunter
   - Druid: https://worldofwarcraft.blizzard.com/en-us/game/classes/druid
   - Evoker: https://worldofwarcraft.blizzard.com/en-us/game/classes/evoker
   - Hunter: https://worldofwarcraft.blizzard.com/en-us/game/classes/hunter
   - Mage: https://worldofwarcraft.blizzard.com/en-us/game/classes/mage
   - Monk: https://worldofwarcraft.blizzard.com/en-us/game/classes/monk
   - Paladin: https://worldofwarcraft.blizzard.com/en-us/game/classes/paladin
   - Priest: https://worldofwarcraft.blizzard.com/en-us/game/classes/priest
   - Rogue: https://worldofwarcraft.blizzard.com/en-us/game/classes/rogue
   - Shaman: https://worldofwarcraft.blizzard.com/en-us/game/classes/shaman
   - Warlock: https://worldofwarcraft.blizzard.com/en-us/game/classes/warlock
   - Warrior: https://worldofwarcraft.blizzard.com/en-us/game/classes/warrior
2. **Battle.net item metadata / SimC observed variant stats**：作为物品 `inventory_type`、`item_class`、`item_subclass`、`preview_item.stats`、`unique_equipped`、`limit_category` 的结构化来源。UI 不按中文名判断。
3. **美化 / 唯一装备 tooltip 证据**：Wowhead 对 The War Within crafted embellishment 的说明显示美化会以 `Unique-Equipped: Embellished (2)` 形式进入 tooltip；本项目只把这类 limit metadata 作为标签和上限判断输入，不把 tooltip 文案本身当业务规则。
4. **当前 compact payload 审计**：上一轮已经修正专精武器候选泄漏；本轮继续把同一专精矩阵扩展到装备明细标签、制造业属性组合和主属性展示。

## Primary Stat Matrix

| Primary | Class / Spec |
| --- | --- |
| Strength | Death Knight 全专精；Warrior 全专精；Paladin Protection / Retribution |
| Agility | Demon Hunter 全专精；Hunter 全专精；Rogue 全专精；Druid Feral / Guardian；Monk Brewmaster / Windwalker；Shaman Enhancement |
| Intellect | Evoker 全专精；Mage 全专精；Priest 全专精；Warlock 全专精；Druid Balance / Restoration；Monk Mistweaver；Paladin Holy；Shaman Elemental / Restoration |

规则：如果物品或制造业属性明确只有非当前主属性，则不进入该专精候选；如果属性为混合主属性（如 `力量/敏捷/智力`、`敏捷 or 智力`），保留候选但展示时只显示当前专精主属性。

## Backend Implementation

### 1. Spec-Aware Primary Stat Rule

**Files:** `server/websim_payload.py`, `tests/websim_payload_test.py`

- 新增 `primary_stat_key_for_spec(class_key, spec_key)`，与前端现有汇总面板规则对齐。
- 新增 `item_primary_stat_keys(stat)` 和 `filter_item_stats_for_spec(stats, primary_key)`。
- 候选过滤：
  - 有明确主属性且不包含当前专精主属性：`compatibility=incompatible`，不进入 `replacementCandidates`。
  - 无主属性、纯耐力 / 二级属性 / 特效饰品：保留。
  - 混合主属性：保留，compact payload 的 `itemStats/statSummary` 改写为当前专精主属性。

### 2. Crafted Stat Options Filtering

**Files:** `server/websim_payload.py`, `tests/websim_payload_test.py`

- `compact_crafted_stat_option()` 接收当前候选 `primaryStatKey`。
- 制造业属性选项如果只提供非当前主属性，直接从 `craftedStatOptions` 排除。
- 如果制造业候选没有任何可用 stat option，候选不应以“可配置制造业”形式展示给当前专精。

### 3. Equipment Badges

**Files:** `server/websim_payload.py`, `tests/websim_payload_test.py`

新增 display-ready 字段：

- `primaryStatKey`
- `handedness`: `one_hand` / `two_hand` / `ranged` / `off_hand`
- `handednessLabel`: `单手` / `双手` / `远程` / `副手`
- `uniqueEquipped`
- `uniqueEquippedLabel`
- `uniqueLimit`
- `equipmentBadges`: stable badge list, e.g. `[{ key: "weapon_handedness", label: "双手" }, { key: "unique_equipped", label: "唯一" }]`

来源：

- 单手 / 双手：Battle.net `inventory_type` 与 `item_subclass` 归一化后的 `weaponType`。
- 唯一装备：`unique_equipped`、`uniqueEquipped`、`unique_equipped_category`、`limit_category`、`Unique-Equipped` tooltip marker。
- 美化：沿用现有 `builtInEmbellishment` 与 `embellishmentOptions`，但同样进入 `equipmentBadges`，供 UI 统一展示。

### 4. Compact Payload Contract

`/api/websim/gear?...compact=1` 输出 display-ready 候选：

- `replacementCandidates[].items[].statSummary` 已按当前专精主属性过滤。
- `replacementCandidates[].items[].craftedStatOptions` 已按当前专精过滤。
- `equippedSet` 与 `baselineSet` 同样使用 spec-aware 展示字段。
- `gearBySlot` / `enhancementBySlot` 快照结构不变。

### 5. Health / Audit

`/api/data/health` 复用现有 gear catalog health，可追加：

- `primaryStatRuleCoverage.totalSpecs`
- `primaryStatRuleCoverage.missingSpecs`
- `primaryStatRuleCoverage.excludedCandidateCount`
- `primaryStatRuleCoverage.examples`

本轮若时间不足，至少保证单测覆盖主属性候选过滤；health 统计可作为后续审计增强，不阻塞线上修复。

## Frontend Implementation

**Files:** `pages/builds/detail.js`, `tests/builds-page.test.js`

- 装备卡片和候选行展示 `equipmentBadges`，样式复用美化 / 附魔已有 badge 方案。
- 装备详情 `装备属性` 使用后端过滤后的 `statSummary`；若缓存里仍是旧 payload，按 `primaryStatKey || primaryStatKeyForSpec(selectedSpec)` 做本地兜底过滤。
- 不新增按物品名、ID、中文 tooltip 文案的前端特判。
- 换装后继续使用既有 `weaponRule` 清理 stale off-hand 和 stale enhancement draft。

## Test Plan

### Backend

```bash
python3 -m unittest tests.websim_payload_test
```

Required cases:

- Warrior/Fury 看不到智力制造业候选，混合 `力量 or 敏捷` 只展示 `力量`。
- Mage/Frost 对同一混合候选只展示 `智力`。
- Crafted stat options 对 Warrior/Fury 只保留力量组合，对 Mage/Frost 只保留智力组合。
- 武器 compact item 含 `handednessLabel` 和 `equipmentBadges`。
- 唯一装备 compact item 含 `uniqueEquippedLabel` 和 `equipmentBadges`。

### Frontend

```bash
node --test tests/builds-page.test.js
```

Required cases:

- 装备明细显示单手 / 双手标签。
- 唯一装备显示 `唯一` 标签。
- 装备详情属性对 Warrior/Fury 从混合主属性中只显示力量。
- 候选卡片和详情行不显示不适配主属性文案。

### Verification / Deploy

```bash
git diff --check
python3 -m unittest tests.websim_payload_test
node --test tests/builds-page.test.js
WOW_DEPLOY_SKIP_BOOTSTRAP=1 WOW_DEPLOY_START_ASYNC_SYNCS=0 ./server/deploy_lighthouse.sh
```

Post-deploy smoke:

- `/health`
- `/api/data/health`
- `/api/websim/gear?class=warrior&spec=fury&compact=1`
- `/api/websim/gear?class=mage&spec=frost&compact=1`
- `/api/websim/gear?class=shaman&spec=enhancement&compact=1`
- `/api/websim/gear?class=monk&spec=brewmaster&compact=1`
