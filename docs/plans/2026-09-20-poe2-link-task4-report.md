# Task 4 — 有限国服映射与原生 PoB 桥接

2026-09-20。实现、云端定向验证完成，交 root 独立审查。未提交、推送、合入；未重启或部署 Candidate API/worker。现有服务进程仍是先前代码，本文测试为云端独立进程。没有重新请求同一分享，没有下载依赖或扩抓字典。本地仅文件读写、传输与 git diff 检查。

**真实国服完整导入仍未验收**。当前真实分享只有有限字段可验证，缺珠宝、base_info、版本/任务选择依据，以及大量未支持装备与词缀。实现返回 needs_input 并保留预览；合成数据已验证原生转换、计算、导出重导入以及持久化 worker ready 流程。

## 文件与唯一接口

新增：

- `server/app/poe2/imports/mapping.py`
- `server/app/poe2/imports/data/zhCN-0_5.json`
- `server/app/poe2/imports/data/README.md`
- `server/app/poe2/imports/data/UPSTREAM-LICENSE.md`
- `server/app/poe2/character_bridge.py`
- `server/app/poe2/character_bridge.lua`
- `tests/app_poe2_mapping_test.py`
- `tests/app_poe2_character_bridge_live_test.py`

修改：`server/app/poe2/imports/worker.py`、`server/app/worker/main.py`、`tests/app_poe2_import_application_test.py`、`tests/app_poe2_import_postgres_test.py`。没有改 collector/Web/Chat。

端口：

```python
collect_wegame(ref, *, owner_id=row.user_id)
map(snapshot) -> MappingResult
convert_character(character: dict) -> str  # native PoB XML
```

`map` 绑定服务器字典，调用 `map_snapshot(snapshot, dictionary)`。结果字段 `character, issues, preview, mapping_version, source_hash, game_data_version` 与 Task2 唯一接口一致，额外 `coverage, ledger` 为无原文的内部逐项审计；每种分类的 `total == mapped + unmapped`。ledger 只含受控类型、数组位置路径和状态。任何 blocking issue 都令 character=None，worker 不调用 convert。

worker collect 的 owner 来自已 claim 数据库行。main.py 已把 collector/mapper/converter 三端注入 ImportWorker；数据库、owner、状态机、租约仍复用 Task2。

## 字典及事实边界

`mappingVersion=zhCN-0_5-finite-1`，`gameDataVersion=0_5`；目标固定 `7d6f530cbdab20389ff8bc6ba97a37ac27f74e41`。

有限覆盖：

| 分类 | 已内置的有限范围 |
| --- | --- |
| 职业 | Huntress/Amazon，4个中英文精确名称入口 |
| 基底 | Akoyan Spear、Amethyst Ring，两项 |
| 暗金 | 0，明确 UNIQUE_UNMAPPED |
| 宝石 | Explosive Spear、Execute II、Execute III，3项；后两者PoB Tier4/5、gem ID分别固定 |
| 词缀 | 生命、火/冰/电/混沌抗性，5个精确数值模板 |
| 属性选择 | 3个稳定来源ID，要求已验证Attribute节点、对应名称、+5数值和stat全部一致 |
| 被动节点 | 当前样本涉及的153个ID，从固定0_5/tree.json逐一验证；未复制整棵树 |
| 任务 | Beira、Candlemass两项精确choice/stat对应；没有汇总反推任务 |
| 珠宝/符文/药剂/咒符 | 未支持，逐项/类别报告缺口 |

来源是固定上游 `TreeData/0_5/tree.json`、`Data/Bases/{spear,ring}.lua`、`Data/Gems.lua`、`Data/QuestRewards.lua`、`Data/StatDescriptions/stat_descriptions.lua` 和 `Classes/ImportTab.lua`。英文目标、节点与属性来自该提交；有限中文对应独立编写并与已有研究证据交叉核对。保留上游完整LICENSE，未复制 PoBR 或无license中文词典。各条目保存固定来源索引；上游7个相关文件SHA256保存在云端 `task4-upstream-sha256.json`。

GGG标记保留显示侧的区分，例如 `[Resistances|火焰抗性]` 不退化为统一Resistances。模板要求精确全文、物品domain、数值边界；flags只有实际原生支持的字段/类型可通过，其余阻断。装备基础属性/需求、插槽、暗金、未知结构均不能静默删除后声称完整。嵌套equipment/socketedItems及其全部词缀进入ledger，即使父物品已经失败也继续计账。

当前 collector schema 不提供 `source.game_data_version` 或 `passives.quest_provenance`（完整choice列表及resistance_penalty）。这两个来源事实缺失时明确阻断；合成fixture提供它们用于验证。没有新增外部用户请求字段，没有让collector伪造版本或任务事实。空base_info和source.schema_gaps同样阻断。

`source_hash` 是 mapper收到的完整净化dict按排序紧凑UTF-8 JSON计算的SHA256；它与collector排除时钟后的snapshot_hash是不同定义，二者都留在内部snapshot中。

## 原生桥接

Python边界检查实际上游Git HEAD与固定提交一致，采用已有 `engine_slot`、服务器自选临时输入输出文件、环境白名单、2MB输入/4MB输出、1GiB address space、40秒CPU、45秒外部超时、128文件描述符及 `engine_runner.py` seccomp无网络限制。临时目录随调用回收，错误只公开固定错误码。

Lua调用 `newBuild()` → `ImportPassiveTreeAndJewels` → `ImportItemsAndSkills` → `OnFrame` → `SaveDB('code')`。原生导入前校验gemForBaseName必须对应字典的精确gem ID、base存在、每行英文词缀被modLib完整解析。导入后校核装备/宝石/技能组数量、所有来源节点仍allocated、两套武器allocMode、属性节点dn。PoB按等级估算的resistancePenalty被有来源依据的输入覆盖；不把估算当任务进度。

测试曾捕获两种真实静默损失：稀有物品空title导致原生丢弃，已生成服务器控制的通用title；断连合成节点被原生清理，计数校核拦住，验证fixture改为固定树上的连接子树。另修正PoB内部属性名字段为dn，并给跨运行用户的只读Git HEAD检查传单次safe.directory，不修改全局Git设置。

## 云端验证

所有运行均在 `/opt/chickenbro-candidates/poe2-20260918/source`，Python `/opt/chickenbro-runtime/bin/python`，引擎 `v0.23.1@7d6f530cbdab20389ff8bc6ba97a37ac27f74e41`。

首次测试先上传测试文件，得到 `ModuleNotFoundError: server.app.poe2.imports.mapping`。实现后：

1. `bash .../evidence/link-research/poe2-task4-tests.sh`：9项mapper单测 + 2项原生bridge/live测试，全通过。最终输出 `task4-tests.log`；脚本保留完整固定POB/Lua/LD_LIBRARY_PATH/LUA_PATH/LUA_CPATH设置。
2. `bash .../evidence/link-research/poe2-task4-pg-tests.sh`：26项，25通过，1项旧real-ninja opt-in未重跑。包括新合成WeGame worker真实原生转换+引擎+Candidate Postgres ready，以及Task2状态机、URL/packet回归、owner接线和未知mapper禁止convert。输出 `task4-pg-tests.log`，耗时8.279秒。连接显式SET ROLE wow_app；只创建/清理本次随机测试owner。
3. 最后小范围复验 `python -m unittest tests.app_poe2_mapping_test tests.app_poe2_import_application_test -v`：12项通过，0.008秒，输出 `task4-final-unit-tests.log`。本地 `git diff --check`通过。

两个完整合成fixture的证据：

- 最小合成：1装备、1词缀、2宝石；Life1091、Mana364、TotalDPS35.96581296。原生导入保留fractured；导出重导入生命/魔力/三抗/混抗/DPS一致。XML及结果为 `task4-synthetic.xml`、`task4-synthetic-result.json`。
- 扩展合成：3装备（含换装战矛和戒指）、11词缀（全部5模板）、2宝石、6连接节点、4敏捷选择、1明确任务奖励；Life1091、Mana364、TotalDPS39.41785344，火19/冰18/电-3/混沌26。两套节点模式及属性名原生校核通过；显式-20抗性进度、Beira冷抗奖励和上述指标在export重导入后一致。详细计数和指标在 `task4-tests.log`。
- PG worker的collector是合成fixture返回器；mapper/converter/engine/repository均为真实实现。它验证接线及持久化ready，不等于真实网络采集角色完整转换。

恶意额外字段测试将嵌套token、URL、任意skill_override键、原始response等放入来源；公共preview/issues不含其原文。preview最初只输出通用角色标签、经验证level、字典class和完整性；独立审查后已补回经安全校验的角色、赛季和时间字段，见文末修复记录。issues始终只用受控码、说明及索引路径。

## 真实净化样本逐项清单

直接使用既有 `task3-snapshot.json`，没有网络重采。结果完整保存 `task4-real-mapping.json`（包含全部安全ledger及issues），characterProduced=false；sourceHash=`d1588143122ec5343c737db7785a6d31ff25b114f425fed2aa4b87b875364052`。

| 分类 | 总数 | mapped | unmapped |
| --- | ---: | ---: | ---: |
| 物品，含17装备与24嵌入物品 | 41 | 0 | 41 |
| 所有物品词缀，含嵌入物品 | 181 | 2 | 179 |
| 主技能与辅助 | 81 | 0 | 81 |
| 主树与两套武器节点 | 153 | 153 | 0 |
| 属性选择 | 49 | 49 | 0 |
| 任务汇总行 | 15 | 0 | 15 |

这里mapped表示该项满足固定映射合同；装备存在已知base或宝石名称命中也不能盖过其余未支持字段。节点/属性验证也不代表已通过整角色版本与计算验收。

真实缺项包括：游戏版本未被来源证明、GetJewels无珠宝物品、6个珠宝插槽不能反推珠宝、base_info空、15任务汇总无choice/完整性/抗性进度、暗金/咒符/符文/装备属性及大量词缀/宝石仍无有限映射。公开完整角色与面板对齐仍需用户完整PoB或资料完整且有合法可验证映射的国服样本；此项维持未完成，不阻碍上述实现与合成工程验证交审。

## 独立审查修复 R1 / 两项 P2

本轮仅修改 `server/app/poe2/imports/mapping.py`、`tests/app_poe2_mapping_test.py` 和本报告。未改字典、collector、桥接或worker；未重新采集或重复真实引擎/PG验证；未提交、部署或重启。

1. 公共preview现在保留collector已净化的可用 `role.name → character`、`role.league_id → league`、`source.fetched_at → fetchedAt`。名称/赛季要求字符串、1–100字符、允许字符格式、无敏感标记/长hex串，并排除快照内敏感字段值的复现；嵌套对象、URL或私有值不复制。赛季ID原样显示，不猜译名称。时间要求完整带时区ISO格式和真实有效日期，规范为UTC；未知 `sourceUpdatedAt` 明确null，非法读取时间不输出。没有把读取时钟当作来源更新时间。无法公开角色名时才用通用标签。
2. `jewels.items` 每个条目都产生unmapped物品ledger，仍返回明确阻断；检查真实collector结构中的 `item.jewel`。同时遍历wrapper/jewel的标准mods及 `mod_descriptions`；每条源mod描述计一次unmapped modifier，其 `values_formats[].des` 是该源mod的显示格式，缺失/异常结构另报 `JEWEL_STRUCTURE_UNSUPPORTED`。路径只用固定键和数组索引，不复制珠宝名、描述或未知字段值。装备式socketedItems继续使用既有递归计账。此修复只补审计覆盖，不宣称支持珠宝计算。

新增两个针对用例：安全角色/赛季/读取时间保留，同时敏感值复现、URL、嵌套对象和非法日期剔除；两颗珠宝采用 `jewel.mod_descriptions[].values_formats[].des`，另混合1条explicitMods和1个未知wrapper。加上原有合成武器，断言物品total4（1 mapped/3 unmapped）、词缀total5（1 mapped/4 unmapped），ledger分类总数与coverage一致，character=None。

云端先只运行新增2项：两项均FAIL，分别确认通用角色标签覆盖了真实角色名、珠宝未增加计数。上传修复后：

```sh
cd /opt/chickenbro-candidates/poe2-20260918/source
/opt/chickenbro-runtime/bin/python -m unittest tests.app_poe2_mapping_test -v
```

11项全部通过，0.009秒；包括原有恶意字段净化、未知词缀/节点、版本/珠宝/base_info缺口、双武器/属性、flags和coverage测试。日志 `/opt/chickenbro-candidates/poe2-20260918/evidence/link-research/task4-fix1-mapping-tests.log`。本地 `git diff --check`通过。真实fixture珠宝仍missing，因此原真实计数和业务验收缺口不变。
