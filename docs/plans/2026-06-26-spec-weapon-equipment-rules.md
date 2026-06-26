# 职业专精武器适配实施方案

**Goal:** 修正装备模拟中主手 / 副手候选按职业粗粒度放开的行为，改为按职业专精的可执行武器模式过滤，确保玩家看到的装备候选、前端换装状态和后端 SimC profile 序列化使用同一套规则。

**Architecture:** 后端拥有完整专精武器矩阵，负责 compact payload 前的候选过滤、兼容性标记和 serializer blocker；前端只消费后端字段，并在本地交互时镜像同一规则清理 stale draft。缺少上游证据的武器类型默认不进入玩家可选候选。

**Tech Stack:** Python backend、SQLite gear catalog、Battle.net / Blizzard 官方职业页与补丁说明、SimulationCraft profile smoke、微信小程序前端、`unittest`、Node test harness。

## Evidence Chain

本轮证据按优先级分层使用：

1. **Blizzard 官方职业页**：作为每个职业 class-level available weapons 与 specialization preferred weapons 的主证据。
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
2. **Blizzard 官方补丁说明**：作为双持 / 双手例外和当前版本变化证据。
   - 10.0.5 group loot 说明强调 1H / 2H need eligibility 要按 loot spec 判断是否能双持。
   - Shadowlands notes 说明 Frost DK 支持双手与双持两套路径，并说明 Brewmaster / Windwalker 相关双手支持回归。
   - Midnight pre-expansion notes 说明 Fury `Single-Minded Fury` talent 移除，同时保留 Titan's Grip 方向。
   - 2024-10-16 hotfix notes 说明 Fury Warriors 需要两把双手武器的 PvP token 特例。
3. **结构化游戏数据与 SimC profile**：用于验证当前赛季候选是否有可执行属性、是否能被 SimC profile 接收。SimC / observed profile 不能覆盖官方专精规则，只能作为补充证据。
4. **生产 compact payload 只读审计**：用于发现当前读模型泄漏项。2026-06-26 抽样发现：
   - `monk/brewmaster` off_hand 候选为 0，但该专精应支持双持模式。
   - `shaman/enhancement` off_hand 混入盾牌，且 main_hand 混入法杖 / 双手武器。
   - `warrior/fury` off_hand 混入盾牌，main_hand 混入单手 / 法杖。
   - `deathknight/frost` off_hand 为 0，但 Frost DK 应支持双持单手模式。

## Weapon Mode Matrix

规则表达目标不是“角色理论上是否能装备”，而是“该职业专精在当前装备模拟中是否应展示为可执行候选”。

| Class / Spec | Main Hand | Off Hand | Mode |
| --- | --- | --- | --- |
| Death Knight / Blood | Two-Handed Axe, Two-Handed Mace, Two-Handed Sword, Polearm | none | two_hand |
| Death Knight / Frost | Two-Handed Axe, Two-Handed Mace, Two-Handed Sword, Polearm or One-Handed Axe, One-Handed Mace, One-Handed Sword | none for two_hand; matching one-hand weapon for dual_wield_1h | selectable |
| Death Knight / Unholy | Two-Handed Axe, Two-Handed Mace, Two-Handed Sword, Polearm | none | two_hand |
| Demon Hunter / Devourer, Havoc, Vengeance | Warglaive, Fist Weapon, One-Handed Axe, One-Handed Sword | Warglaive, Fist Weapon, One-Handed Axe, One-Handed Sword | dual_wield_1h |
| Druid / Balance, Restoration | Staff or Dagger / One-Handed Mace | Held In Off-hand only when using one-hand mode | caster_1h_or_staff |
| Druid / Feral, Guardian | Staff, Polearm | none | two_hand_agi |
| Evoker / Augmentation, Devastation, Preservation | Staff or Dagger / One-Handed Sword / One-Handed Mace | Held In Off-hand only when using one-hand mode | caster_1h_or_staff |
| Hunter / Beast Mastery, Marksmanship | Bow, Crossbow, Gun | none | ranged |
| Hunter / Survival | Polearm, Staff, or other current-season agility two-hand evidence | none unless current upstream evidence proves dual wield | melee_two_hand |
| Mage / Arcane, Fire, Frost | Staff or Dagger / One-Handed Sword / Wand | Held In Off-hand only when using one-hand mode | caster_1h_or_staff |
| Monk / Brewmaster | Staff, Polearm or Fist Weapon / One-Handed Axe / One-Handed Mace / One-Handed Sword | none for two_hand; matching one-hand weapon for dual_wield_1h | selectable |
| Monk / Mistweaver | Staff or One-Handed Mace / One-Handed Sword | Held In Off-hand only when using one-hand mode | healer_1h_or_staff |
| Monk / Windwalker | Staff, Polearm or Fist Weapon / One-Handed Axe / One-Handed Mace / One-Handed Sword | none for two_hand; matching one-hand weapon for dual_wield_1h | selectable |
| Paladin / Holy | One-Handed Mace, One-Handed Sword | Shield | shield_caster |
| Paladin / Protection | One-Handed Axe, One-Handed Mace, One-Handed Sword | Shield | shield_tank |
| Paladin / Retribution | Two-Handed Axe, Two-Handed Mace, Two-Handed Sword, Polearm | none | two_hand |
| Priest / Discipline, Holy, Shadow | Staff or Dagger / One-Handed Mace / Wand | Held In Off-hand only when using one-hand mode | caster_1h_or_staff |
| Rogue / Assassination | Dagger | Dagger | dual_wield_dagger |
| Rogue / Outlaw | Fist Weapon, One-Handed Axe, One-Handed Mace, One-Handed Sword | Fist Weapon, One-Handed Axe, One-Handed Mace, One-Handed Sword, Dagger if current upstream profile evidence uses it | dual_wield_1h |
| Rogue / Subtlety | Dagger | Dagger | dual_wield_dagger |
| Shaman / Elemental, Restoration | Staff or Dagger / One-Handed Mace | Shield or Held In Off-hand when using one-hand mode | caster_shield_or_holdable |
| Shaman / Enhancement | Fist Weapon, One-Handed Axe, One-Handed Mace | Fist Weapon, One-Handed Axe, One-Handed Mace | dual_wield_1h |
| Warlock / Affliction, Demonology, Destruction | Staff or Dagger / One-Handed Sword / Wand | Held In Off-hand only when using one-hand mode | caster_1h_or_staff |
| Warrior / Arms | Two-Handed Axe, Two-Handed Mace, Two-Handed Sword, Polearm | none | two_hand |
| Warrior / Fury | Two-Handed Axe, Two-Handed Mace, Two-Handed Sword | Two-Handed Axe, Two-Handed Mace, Two-Handed Sword | dual_wield_2h |
| Warrior / Protection | One-Handed Axe, One-Handed Mace, One-Handed Sword | Shield | shield_tank |

## Backend Tasks

### Task 1: Add Structured Spec Rules

**Files:**
- Modify: `server/websim_payload.py`
- Test: `tests/websim_payload_test.py`

Add:

- `SPEC_WEAPON_EQUIPMENT_RULES`
- `weapon_rule_for_spec(class_key, spec_key)`
- `weapon_type_allowed_for_slot(class_key, spec_key, slot, weapon_type, payload)`
- `gear_candidate_slots(item)` with class/spec-aware slot routing

The rule must distinguish:

- class-level proficiency
- specialization equipment mode
- slot target (`main_hand` vs `off_hand`)
- shield vs Held In Off-hand vs real off-hand weapon
- two-hand mode removing off-hand
- selectable mode such as Frost DK / Brewmaster / Windwalker

### Task 2: Filter Before Compact Payload

**Files:**
- Modify: `server/websim_payload.py`
- Test: `tests/websim_payload_test.py`

Rules:

- `gear_compatibility_from_payload()` must return incompatible when a weapon is class-usable but spec-mode-invalid.
- The grouping loop in `get_websim_gear()` must not append invalid `main_hand` / `off_hand` candidates.
- For dual-wield specs, one-hand candidates must be routable to both `main_hand` and `off_hand` when evidence says the item is a one-hand weapon.
- For Fury, two-handed axe / mace / sword candidates must route to both `main_hand` and `off_hand`.
- For caster 1H + Held In Off-hand specs, Held In Off-hand candidates stay in `off_hand`; weapon candidates do not route to `off_hand`.

### Task 3: Serializer Blocker

**Files:**
- Modify: `server/websim_payload.py`
- Test: `tests/websim_payload_test.py`

When saved `gearBySlot` contains invalid combinations:

- Enhancement Shaman off-hand shield -> blocker, no SimC off_hand line.
- Fury Warrior off-hand shield / one-hand weapon -> blocker.
- Frost DK two-hand main hand plus off-hand weapon -> blocker unless user has selected a dual-wield mode with one-hand main hand.
- Caster Held In Off-hand with a two-hand main hand -> blocker.

### Task 4: Health / Audit Output

**Files:**
- Modify: `server/websim_payload.py`
- Test: `tests/websim_payload_test.py`

`/api/data/health` should expose weapon rule coverage or reuse gear catalog detail output:

- total class/spec rule count
- missing rule count
- excluded candidate count
- examples with `classKey/specKey/slot/itemId/weaponType/reason`

## Frontend Tasks

### Task 5: Consume Backend Rule Fields

**Files:**
- Modify: `pages/builds/detail.js`
- Test: `tests/builds-page.test.js`

Frontend should not hardcode item names or item IDs. It may mirror backend rule fields for immediate interaction:

- `weaponRule.mode`
- `weaponRule.mainHandTypes`
- `weaponRule.offHandTypes`
- `weaponRule.offHandPolicy`

### Task 6: Clean Stale Draft on Gear Changes

**Files:**
- Modify: `pages/builds/detail.js`
- Test: `tests/builds-page.test.js`

When selected gear changes:

- selecting a two-hand main hand clears incompatible `off_hand` gear and `enhancementBySlot.off_hand`
- selecting one-hand mode for Frost DK / Brewmaster / Windwalker allows off-hand weapon candidates
- switching to shield / held-offhand mode removes off-hand weapon enchants if invalid
- confirm action cannot save stale draft that is no longer compatible

## Test Plan

### Backend

```bash
python3 -m unittest tests.websim_payload_test
```

Required focused cases:

- `shaman/enhancement`: main/off hand only Fist Weapon, One-Handed Axe, One-Handed Mace; no shield, no held offhand, no staff, no two-hand.
- `monk/brewmaster`: off-hand one-hand weapon candidates are visible in dual-wield mode; two-hand mode still valid with empty off-hand.
- `warrior/fury`: main/off hand show two-handed axe/mace/sword; no shield, no one-hand, no staff/polearm unless explicit upstream evidence changes.
- `deathknight/frost`: supports both two-hand and dual-wield one-hand; invalid mixed mode blocked.
- caster specs: off-hand weapon candidates never appear; Held In Off-hand appears only for eligible specs.
- serializer rejects invalid saved `gearBySlot` even if frontend submits it.

### Frontend

```bash
node --test tests/builds-page.test.js
```

Required focused cases:

- Enhancement Shaman off-hand sheet does not show shields.
- Brewmaster off-hand sheet shows one-hand weapon candidates when main hand is one-hand.
- Fury Warrior off-hand sheet shows two-handed weapon candidates.
- Switching main hand from one-hand to two-hand clears stale off-hand selection.
- Confirming replacement cannot persist stale incompatible `enhancementBySlot`.

### Release

```bash
git diff --check
python3 -m unittest tests.websim_payload_test
node --test tests/builds-page.test.js
WOW_DEPLOY_SKIP_BOOTSTRAP=1 WOW_DEPLOY_START_ASYNC_SYNCS=0 ./server/deploy_lighthouse.sh
```

Post-deploy smoke:

- `/health`
- `/api/data/health`
- `/api/websim/gear?class=shaman&spec=enhancement&compact=1`
- `/api/websim/gear?class=monk&spec=brewmaster&compact=1`
- `/api/websim/gear?class=warrior&spec=fury&compact=1`
- `/api/websim/gear?class=deathknight&spec=frost&compact=1`
- Full `WOW_CLASSES` traversal with weapon type assertions.

## Rollback

This change is read-model / serializer logic only. If production smoke finds wrong candidate filtering:

1. Keep production DB unchanged.
2. Revert deployed code to the previous backend/frontend version.
3. Restart backend.
4. Re-run `/health`, `/api/data/health`, and the four focused compact payloads.

If a future iteration also writes DB audit metadata, back up SQLite before write and document the backup path in this plan before deployment.
