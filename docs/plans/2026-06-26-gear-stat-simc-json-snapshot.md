# 装备属性百分比 SimC JSON 快照方案

> 状态：已按本轮验证结论实施，并完成生产热部署与线上 smoke。
> 来源：2026-06-26 用户对元素萨装备模板中急速、暴击、精通、全能百分比准确性提出质疑。

## 背景

此前装备属性概览曾尝试用 level 90 rating 常量在前端本地换算副属性百分比。这个方案被本轮验证推翻：装备栏上的 rating 汇总不等于角色面板百分比。真实角色面板还包含基础属性、职业/专精被动、天赋、光环、SimC 对当前客户端数据的 rating curve、精通专精公式，以及装备解析是否完整等因素。

因此装备模拟页不再把本地 `statConversion` 结果当作玩家可见百分比来源。本地装备属性汇总只保留为 raw rating 兜底；只有 SimC JSON 里的角色快照字段验证通过时，才展示百分比。

## Evidence Chain

本轮证据按可信度排序：

1. **SimulationCraft JSON output**：`sim.players[0].collected_data.buffed_stats.attribute` 与 `sim.players[0].collected_data.buffed_stats.stats` 是 SimC 在完整 profile 执行后给出的角色快照。它已经吃到了职业、专精、天赋、装备、宝石、附魔和当前客户端 combat rating 数据。
2. **Raider.IO 线上角色观测**：用于拿真实角色装备与天赋组合做 profile 输入，不把 Raider.IO 自身当属性百分比 authority。
3. **项目后端 serializer**：`gearSelection + enhancementBySlot + talents` 必须先经过 `build_websim_profile()`，由后端生成 SimC profile；前端不拼 profile。
4. **前端本地装备汇总**：只用于装备变更后的即时 raw rating 展示和强化计数，不用于百分比结论。

## Validation Samples

### Elemental Shaman

- 角色：`听凭风引`
- 区域/服务器：`cn / sylvanas`
- 职业专精：`shaman / elemental`
- Raider.IO：`https://raider.io/characters/cn/sylvanas/听凭风引`
- SimC：`1205-01 / WoW 12.0.5.67823`

无 consumable / 非 `optimal_raid` 快照：

| Stat | Rating | SimC character percent |
| --- | ---: | ---: |
| Crit | 757 | 21.4565% |
| Haste | 250 | 8.8523% |
| Mastery | 845 | 55.0679% |
| Versatility | 83 | 1.5370% |

同一 profile 启用默认 raid buff / consumable 后，精通接近 65.54%。这和用户对 291 元素萨 “暴击约 25%、急速约 10%、精通约 70%、全能 1% 不到” 的经验方向一致，证明本地 rating 常量把元素萨精通、暴击算偏了。

注意：该样本有 SimC 物品解析 warning，`268290` 相关 item document 为空，只能作为算法方向验证。生产展示遇到同类 item resolution warning 必须 fail closed，不展示 verified 百分比。

### Frost Mage

- 角色：`Mageroysong`
- 区域/服务器：`cn / zuldrak`
- 职业专精：`mage / frost`
- Raider.IO：`https://raider.io/characters/cn/zuldrak/Mageroysong`
- SimC：`1205-01 / WoW 12.0.5.67823`

无 consumable 快照：

| Stat | Rating | SimC character percent |
| --- | ---: | ---: |
| Crit | 994 | 28.6087% |
| Haste | 554 | 18.2880% |
| Mastery | 545 | 36.5565% |
| Versatility | 0 | not present |

这个样本验证了非萨满职业也不能用本地 rating 直接推面板百分比；SimC JSON 会返回当前职业专精实际面板口径。

### Retribution Paladin Cross Check

- 角色：`哦毕爷`
- 区域/服务器：`cn / shadowmourne`
- 职业专精：`paladin / retribution`

无 consumable 快照：

| Stat | Rating | SimC character percent |
| --- | ---: | ---: |
| Crit | 792 | 26.2174% |
| Haste | 355 | 8.0680% |
| Mastery | 596 | 33.6910% |
| Versatility | 0 | not present |

第二个非萨满样本进一步确认：百分比应由 SimC 角色快照给出，不应由前端按固定 rating 常量动态推导。

## Final Decision

1. `/api/websim/gear/stats` 运行 SimC 时追加临时 `json=<path>`。
2. 后端优先解析 `collected_data.buffed_stats`：
   - 主属性和耐力来自 `attribute`。
   - 暴击、急速、精通、全能的 rating 和百分比来自 `stats`。
   - 返回 `statStatus=verified`、`statSource=simulationcraft_json`。
3. 如果 SimC JSON 缺失、字段不完整，才回退解析旧 `STAT SNAPSHOT` 文本；旧文本兜底不产生百分比。
4. 如果 SimC 输出包含 item resolution warning，例如无法下载物品、item document 为空、未知 item id，API 返回 blocked，不展示 verified 百分比。
5. 前端装备页只在完整装备 + 有天赋导入码时请求 `/api/websim/gear/stats`。
6. 前端按请求签名去重：同一 `class/spec/talents/scenario/gearSelection/enhancementBySlot` 不重复请求；切装备、改宝石/附魔/美化或切场景后清掉旧百分比，等待新 SimC 快照。
7. 没有 verified snapshot 时，属性概览只显示本地 raw rating，不显示任何百分比。

## Implementation Notes

**Backend**

- `server/websim_payload.py`
  - 新增 `parse_simcraft_json_stat_snapshot(payload)`。
  - `run_websim_stat_simcraft(profile)` 写入 JSON 临时文件并返回 `jsonPayload`。
  - `build_websim_gear_stats_response()` 优先使用 JSON snapshot，遇到 item resolution warning fail closed。

**Frontend**

- `pages/builds/detail.js`
  - 导入 `requestWebsimGearStats`。
  - `gearAttributePanel` 支持 `gearStatSnapshot` 覆盖主属性、耐力、副属性和百分比。
  - 本地 `statConversion` 不再参与玩家可见百分比。
  - 新增 `refreshGearStats()`、`clearGearStatsSnapshot()` 和请求签名去重；同一签名 pending、verified 或 blocked 快照不重复触发 SimC，请求异常才允许同签名重试。

**Tests**

- `tests/websim_payload_test.py`
  - 覆盖 SimC JSON buffed stats 解析。
  - 覆盖 `/api/websim/gear/stats` 优先使用 JSON，不误读 DPS 文本。
- `tests/builds-page.test.js`
  - 覆盖无 verified snapshot 时不显示本地百分比。
  - 覆盖 verified snapshot 时展示 SimC 百分比。
  - 覆盖装备完整且有天赋导入码时触发 stats 请求。
  - 覆盖同签名 blocked 快照不会重复请求 SimC。

## Verification

本轮本地已通过：

```bash
python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_parse_simcraft_json_stat_snapshot_extracts_character_percentages tests.websim_payload_test.WebSimPayloadTest.test_http_websim_gear_stats_prefers_simc_json_character_snapshot tests.websim_payload_test.WebSimPayloadTest.test_http_websim_gear_stats_fake_snapshot_smoke_for_core_specs
node --test tests/builds-page.test.js --test-name-pattern "gear detail requests SimC stat snapshot|gear detail does not request stat snapshot|gear attribute panel"
```

完整发布执行：

```bash
git diff --check
python3 -m unittest tests.websim_payload_test.py
node --test tests/builds-page.test.js
WOW_DEPLOY_SKIP_BOOTSTRAP=1 WOW_DEPLOY_START_ASYNC_SYNCS=0 ./server/deploy_lighthouse.sh
```

生产 smoke 需要至少覆盖：

- `/health`
- `/api/data/health`
- `/api/websim/gear?class=shaman&spec=elemental&compact=1`
- `/api/websim/gear/stats` blocked/verified 两类响应，其中 item resolution warning 必须 blocked。

本轮生产部署后已验证：

- 热部署命令：`WOW_DEPLOY_SKIP_BOOTSTRAP=1 WOW_DEPLOY_START_ASYNC_SYNCS=0 ./server/deploy_lighthouse.sh`
- `/health` 返回 `ok=true`。
- `/api/data/health` 返回 `overallStatus=partial`，保持既有数据健康状态。
- `/api/websim/gear?class=mage&spec=frost&compact=1` 返回 16 槽，并且不再下发 `statConversion`。
- `/api/websim/gear/stats` 在缺天赋或缺 SimC-ready 装备时返回 `blocked`。
- `mage/frost/spellslinger` 使用生产 Raider.IO 社区天赋模板和当前装备模板请求 `/api/websim/gear/stats`，返回 `statStatus=verified`、`statSource=simulationcraft_json`、`simcVersion=1205-01`；最终 smoke 副属性样例为暴击 `1,055 / 29.9%`、急速 `748 / 22.9%`、精通 `961 / 54.2%`、全能 `0 / 3%`。
- `shaman/elemental/stormbringer` 当前生产 baseline 有 2 个槽位缺 SimC 字段，`/api/websim/gear/stats` 返回 blocked：`Missing core SimC gear slots: waist, feet.` 这符合 fail-closed 规则。

## Remaining Boundaries

- 这不是“每次渲染动态计算百分比”，而是“装备/天赋签名变化后请求一次 SimC 快照”。真正百分比由 SimC 计算。
- 如果玩家没有天赋导入码，前端不请求 SimC 百分比，避免用不完整 profile 给出错误结论。
- 如果 SimC 当前 build 暂时无法解析某些 Midnight item，宁可 blocked，也不展示残缺 gear 的百分比。
