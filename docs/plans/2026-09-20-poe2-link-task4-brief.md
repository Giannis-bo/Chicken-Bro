### Task 4: 国服映射与真实 PoB 转换

**Files:** 新增 `imports/mapping.py`、`imports/data/zhCN-0_5.json`、`server/app/poe2/character_bridge.lua`、`tests/app_poe2_mapping_test.py`、`tests/app_poe2_character_bridge_live_test.py`。

**Interfaces:** `map_snapshot(snapshot: dict, dictionary: dict) -> MappingResult`；MappingResult 含 character（标准 PoB 角色 JSON）、issues、mappingVersion、sourceHash、gameDataVersion；`convert_character(character: dict) -> str` 返回 PoB XML。未知关键字段存在时不调用 convert。

- [ ] 建立带来源及许可标记的字典，单独记录 classes、bases、uniques、gems（含阶级）、modifier templates、quest rewards；执行时先核对上游公开资料和固定引擎数据，不用图片名猜身份。
- [ ] 写失败测试：中英标记数值、词缀 flags、同名 II/III 辅助、两套武器、属性选择、珠宝缺口、未知版本。

```python
def test_unmapped_modifier_blocks_conversion(self):
    snapshot = self.valid_snapshot()
    snapshot['equipment'][0]['explicitMods'].append({'description': '未登记测试词缀'})
    mapped = map_snapshot(snapshot, self.dictionary)
    self.assertTrue(any(i.code == 'MOD_UNMAPPED' for i in mapped.issues))
    self.assertIsNone(mapped.character)
```

- [ ] 云端单测确认失败后，按类型逐项实现映射；每一原始节点/词缀/宝石必须进入已映射清单或问题清单，清单数量可核对。quest/skill_overrides 不走模糊文本匹配。
- [ ] 桥接复用上游 `ImportPassiveTreeAndJewels` / `ImportItemsAndSkills`，输入和文件路径均由服务器控制；继承现有进程内存、时间、网络限制。由 PoB 保存 XML，再通过既有引擎计算及 export roundtrip。

```lua
build.importTab:ImportPassiveTreeAndJewels(character)
build.importTab:ImportItemsAndSkills(character)
build.buildFlag = true
runCallback('OnFrame')
local xml = assert(build:SaveDB('code'))
```

- [ ] 给定 WeGame 样本逐项核对天赋/武器专精、技能辅助、装备与任务奖励。珠宝为空保留 needs_input，完整 PoB 上传可补齐；不将其记作完整国服自动转换成功。
- [ ] 在当前公开分享数据中尝试取得完整的珠宝资料；页面未提供则停止该方向，向用户请求同角色完整导出或另一个资料完整的公开国服样本，继续其他独立任务。
- [ ] 至少一份资料完整的真实国服样本，通过源数据清单、PoB 导出重导入、生命/属性/抗性对齐和特定主技能配置核对。未取得完整样本时记录具体阻塞，整体“国服完整打通”不得标完成。

## Binding context

Local workspace /Users/boyuan/Documents/wow_mini_program/.worktrees/poe2-20260918; cloud ssh wow-lighthouse root /opt/chickenbro-candidates/poe2-20260918. ALL executions/tests/downloads cloud only; local file edits/reads/transfers allowed. No commits, no deployment, no subagents. Root dispatches review.

Read docs/plans/2026-09-20-poe2-mapping-research.md and 2026-09-20-poe2-jewels-recheck.md. These are research evidence, not complete mappings. Follow verified identifier+domain/range joins; unknown fields remain explicit. Current user sample is missing jewels and quest choice provenance. User has been asked asynchronously for optional complete PoB or jewel data; independent implementation proceeds meanwhile. Report precise missing items; do not invent stat IDs or credentials or quest completions.

Raw existing cloud capture evidence/link-research/wegame.json; refreshed capture wegame-jewels-recheck.json. Raw captures have extraneous data; consume only domain fields and never commit raw tokens/openid. Fixed PoB upstream/pob at 7d6f530c, LuaJIT environment in server/poe2_candidate_runtime.py. Existing international-character.xml is validation reference, not national data. No ninja scraping.

Implement finite, evidence-backed dictionary and conversion layer, tests proving unknown mapping blocks; do not pass a few known fields as complete. Confirm expected upstream JSON class and item/skill schemas before invoking native ImportTab functions. Build representative complete synthetic fixture separately, clearly marked synthetic. Real complete national sample remains independent acceptance.

Report docs/plans/2026-09-20-poe2-link-task4-report.md with mappings coverage, unknowns, files, interfaces, exact cloud tests and artifacts.

补充研究已完成：同一 mapping-research 报告新增 PoBR `ackness/pobr` 固定 commit `6ab51142e6b56f139a690ddec99d22a7cc0b850d` 的 MIT 转换代码文件/函数索引，可参考其 item/gem/quest/weapon/jewel 转换逻辑并保留出处。其 data 不是 MIT，中文词典来源无 LICENSE，不直接打包。poe2db 只作公开既有案例人工对照，不提交用户角色分享给第三方。PoBR 对空 jewel_data 会整单失败；我们必须保留预览，返回 missing_jewels/needs_input。页面珠宝方向针对性复查已穷尽，不重复猜接口；现阶段通过完整 PoB 补充继续计算。

Task 2 已确定唯一 Python mapper 端口（替代上文示意camelCase属性）：`map(snapshot)` 返回对象字段 `character`, `issues: tuple[Issue,...]`, `preview: dict`（只允许公开camelCase字段）、`mapping_version`, `source_hash`, `game_data_version`。worker使用snake_case读取，写snapshot={data,provenance}并保存preview/source_relation。按实际 Task2 report 和 Task3 snapshot schema接线，不重复造兼容形状。

root 已只读确认固定上游 `src/Classes/ImportTab.lua:650-805`：ImportQuestRewardConfig 需要 `quest_stats` 英文行，ImportPassiveTreeAndJewels 会读 passives.hashes/specialisations/skill_overrides/jewel_data，class/name/league/level 必备。其后会 EstimatePlayerProgress 并自动设置 resistancePenalty（约805-827），不能将该推断冒充来源任务进度；实际配置应明确记录/校核，来源未知时继续阻断关键任务映射。ImportItemsAndSkills:918 起，skills 数据由typeLine/support和properties来识别，未知gemId会静默不导入，因此mapper必须先完整校验并做输入/导出数量对账。云端没有rg，用grep/sed读取。

Task2审查的跨任务净化检查归本任务：preview只返回简单公共值，issues message/path使用受控说明和安全字段路径，不复制源rawresponse/URL/token/openid或任意嵌套对象。加入定向恶意额外字段不会进入public结果的测试。

Task3接口协调：collector需要自己执行owner并发1，因此最终调用为 `self.collect(ref, owner_id=row.user_id)`（只信已claim记录user_id），提供者 `collect_wegame(ref, *, owner_id=...)`。本任务负责更新imports/worker.py该调用及受影响fake测试、worker/main.py注入三端；Task2原collect(ref)示意据此收敛。不要将owner参数暴露给用户/模型输入，collector IPC只接哈希owner key。

root定向原始schema检查：GetEquipments的equipments已经是数组，implicitMods/explicitMods各元素目前只有description，properties/requirements有name/type/displayMode/values，没有可直接当英文stat ID的字段。公开样本观察到中文数值模板与GGG标记混用（如`+101 生命上限`、`[Resistances|火焰抗性] +39%`），不要只取标记左侧导致冷火电抗混淆。映射覆盖可有限，但每条未知必须可对账；逐条英文语义应通过固定PoB原数据/解析结果验证。

固定上游 ImportItem:1152 起：PassiveJewels 通过 `latestTree.jewelSlots[itemData.x+1]` 选槽，Flask x>1映射Charm(x-1)，否则Flask(x+1)，Weapon2/Offhand2为换装武器。未知inventoryId静默return，未知base打印警告；mapper先校验槽位/珠宝索引/基底并保证条目数量不被静默丢弃。

Task3真实隔离采集已取得 `evidence/link-research/task3-snapshot.json`（云端净化快照，17装备/16技能/105主节点/珠宝missing）。实现直接复用此fixture，不再请求同分享。collector新增 `source.schema_gaps` 安全枚举，如 unknown_item_fields/unknown_jewel_structure；任一未知结构需在mapper报明确issues并阻止完整转换。以Task3最终报告schema为准。
