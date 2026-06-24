# 装备强化配置方案

> 状态：已确认方向，待后续拆实施计划。
> 来源：2026-06-24 本地讨论，围绕装备模拟如何处理宝石、附魔、美化、饰品特效和套装效果。

## 背景

装备模拟需要从“展示候选装备”继续推进到“可被 SimC 消费的完整配置”。普通静态属性可以由装备变体读取模型提供，但饰品特效、美化、附魔 proc、套装效果不是简单属性相加。它们必须进入 SimC profile，或由 SimC 根据装备实例自动推导，否则模拟结果会和玩家预期不一致。

当前决策是把装备选择和强化配置分层：装备模拟主流程负责 16 个装备槽位，强化配置负责玩家主动加工行为，套装和饰品特效尽量自动推导。

## 产品方案

1. 装备模拟默认展示 16 个 canonical 槽位，由玩家自行选择装备、来源和装等变体。
2. 套装数量由已选装备自动计算，不增加普通玩家手动开关。页面展示当前 2 件 / 4 件触发状态、缺口和数据可信状态。
3. 饰品特效由 SimC 基于饰品装备实例自动处理。玩家只选择 `trinket1` / `trinket2` 的装备本体；首版不单独暴露饰品特效或使用策略配置。
4. 宝石、附魔、美化进入独立的“强化配置”入口。该入口只展示当前已选装备中支持配置的部位。
5. 强化配置按槽位回写，最终保存为可由后端序列化成 SimC profile 的装备配置快照。

## UI 边界

装备模拟主界面保持以 16 槽装备为中心，避免把宝石、附魔、美化、套装细节塞进每个装备候选 sheet。新增“强化配置”入口后，用户进入一个按能力分组的配置界面：

- 宝石：仅展示有真实插槽或已验证可加插槽的部位。
- 附魔：仅展示当前版本明确可附魔的部位。
- 美化：仅展示可制造或已带制造字段的装备部位。
- 套装：只读展示自动推导状态，不作为普通配置项。

换装备后，原强化配置必须重新校验：如果新装备不支持原宝石、附魔或美化，配置应被清除或标为 blocker，不能静默保留到 SimC profile。

## 数据模型

保存时不要让前端直接拼 SimC 字符串。建议保存结构化快照：

```json
{
  "gearBySlot": {},
  "enhancementBySlot": {
    "main_hand": { "enchant_id": "8039" },
    "finger1": { "enchant_id": "example" },
    "back": { "embellishment": "blue_silken_lining", "crafted_stats": "haste/vers" }
  },
  "derivedSetBonuses": [
    { "setId": "example", "pieces": 4, "tokens": ["example_2pc", "example_4pc"] }
  ],
  "readiness": {
    "simcReady": true,
    "blockers": []
  }
}
```

字段含义：

- `gearBySlot`：16 槽装备选择，保留 slot、item id、ilevel、bonus/gem/enchant/crafted fields、来源和可信状态。
- `enhancementBySlot`：玩家主动配置的宝石、附魔、美化，必须绑定到具体 slot。
- `derivedSetBonuses`：由已选装备自动推导的套装状态，普通用户不可随意伪造。
- `readiness`：后端校验结果，任何缺字段、槽位不兼容、重复美化、套装 token 缺失或 SimC 不支持都进入 blockers。

## SimC 序列化规则

后端是唯一 profile serializer。最终 profile 生成规则：

- 装备行写入 `slot=name,id=...,ilevel=...,bonus_id=...` 等实例字段。
- 宝石 / 附魔 / 美化回写到对应装备行，例如 `gem_id`、`gem_bonus_id`、`enchant_id`、`crafted_stats`、`embellishment`。
- 套装由 `derivedSetBonuses` 写入显式 `set_bonus=...` 行；如果缺少当前版本 token 映射，则 profile 阻断，不能伪造套装效果。
- 饰品只写装备实例字段，特效交给 SimC 自身处理；首版不增加手动 `use` / `equip` proc 编辑。
- 生成 profile 必须继续区分小程序配置快照和玩家官方 `/simc` 导出。小程序配置可以是可执行输入，但不能包装成真实角色最高保真快照。

## 信任边界

- 展示型装备、partial 变体或缺实例字段的装备不得进入可执行 profile。
- `itemId + ilevel` 只能作为属性候选或入库探针，不等于完整特效已验证。
- 宝石、附魔、美化选项必须来自真实插槽、可附魔部位、制造字段或明确服务端数据支持。
- 套装触发必须由已选装备和已验证 set membership 推导。
- SimC 报错、warning、缺支持或 profile 生成失败时，前端只能展示 blocked / partial，不能输出 DPS 或强结论。

## 实施切片建议

1. **契约层**：定义装备配置快照 schema、`enhancementBySlot` 和后端 serializer 输入输出。
2. **字段补齐**：让 WebSim gear line 支持 `embellishment`，并统一宝石 / 附魔 / 美化字段的 normalize / sanitize。
3. **强化配置 UI**：新增入口，按当前已选装备筛出可配置部位，替代把复杂配置继续塞进单个装备 sheet。
4. **套装推导**：从已选装备的 item set metadata 计算 2/4 件状态，补 SimC `set_bonus` token 映射和 blocker。
5. **保存与提交**：装备模板保存结构化快照，SimC 页面由后端确定性转换成 profile，confirmOnly 与 final submit 复用同一 payload。
6. **验收**：覆盖换装备后强化配置清理、重复美化阻断、套装 token 缺失阻断、饰品无需额外配置、完整快照可生成 profile。

## 待确认问题

- 当前版本套装 `set_bonus` token 的权威来源与映射维护方式。
- 美化选项来源：只从 observed profile 反哺，还是建立当前赛季制造美化 catalog。
- 是否需要首版支持“高级模式”手动 override 套装或饰品使用策略。默认建议暂缓。
