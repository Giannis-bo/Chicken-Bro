# Task 4 独立审查

Spec compliance：✅ 本次工程范围合规。R1 两项 P2 已修复，scoped 复审未发现修复引入的新阻断项；真实完整国服样本验收仍未完成。

Code quality：Approved。R1 scoped 复审只覆盖两个发现及修复新增逻辑，完整真实国服样本属于单独的业务验收缺口。

## R1 scoped 复审结果

- ✅ 原 P2-1 已关闭：`server/app/poe2/imports/mapping.py:52-94,136` 新增 `_preview_values`，保留经校验的角色、原始赛季 ID、UTC 读取时间；来源更新时间未知返回 null。值级敏感信息复现检查、标签格式/长度限制和时间格式/有效性检查覆盖了此次新增公开面。`tests/app_poe2_mapping_test.py:108-127` 同时断言正常字段保留与敏感值、URL、嵌套对象、非法日期剔除。
- ✅ 原 P2-2 已关闭：`server/app/poe2/imports/mapping.py:296-316` 遍历每个珠宝 wrapper，记录 unmapped item，覆盖 wrapper/jewel 标准词缀、socketedItems 以及 WeGame `mod_descriptions`。每个源 mod 对象计一次，`values_formats` 作为该 mod 的显示格式检查；未知结构有固定路径 issue。`tests/app_poe2_mapping_test.py:129-144` 验证非空珠宝、多词缀、未知 wrapper 的总数和 ledger 一致，所有珠宝记录 unmapped 且 character=None。
- ✅ 已读 `2026-09-20-poe2-link-task4-fix-review.diff` 和 report 的 R1 红绿证据：新增两项修复前 FAIL，修复后 mapper 11/11 通过。未重复运行已有测试、未扩大旧代码范围、未改产品或部署。旧审查正文下方的行号与问题描述保留为初审快照；两项状态以本节为准。

## Strengths

- `server/app/poe2/imports/mapping.py:73-82,250-278`：字典/游戏版本、schema gaps、任务 choice 与抗性进度均有阻断门槛；不会从任务汇总或等级推断完整来源事实。
- `server/app/poe2/imports/mapping.py:54-63,89-92`：issues 使用固定说明、数组索引路径；preview 只组装受控值。`tests/app_poe2_mapping_test.py:98-106` 覆盖恶意嵌套字段不进入公开结果。
- `server/app/poe2/character_bridge.lua:12-70`：原生导入前校验 gem ID 和词缀可解析性，导入后核对物品/技能组/宝石数量、节点与武器分组及属性选择。`server/app/poe2/character_bridge.py:20-40` 使用实际 Git HEAD 检查、服务器临时路径、白名单环境、资源限制和既有无网络 launcher。
- `server/app/poe2/imports/worker.py:28`：collector 的 owner 参数取自 claim 数据库行。`tests/app_poe2_import_application_test.py:22-34` 同时覆盖该接线和未知映射不调用 converter。
- `tests/app_poe2_character_bridge_live_test.py:1,13-72` 与 Task4 report 明确标记 synthetic；没有用合成 roundtrip 或持久化 ready 代替完整国服真实角色验收。

## Issues

### Important / P2（初审记录；R1 均已关闭）

1. **预览丢掉已有角色身份、赛季和读取时间。** `server/app/poe2/imports/mapping.py:89-92` 固定输出 `Imported character`，没有 `league` 或 `fetchedAt`；`server/app/poe2/imports/worker.py:34-36` 只透传 mapper 返回值，因此后续界面无法恢复这些字段。设计 `docs/plans/2026-09-20-poe2-character-link-design.md:12` 要求角色卡呈现赛季和更新时间/读取时间；Task3 schema 已提供 `role.name`、`role.league_id` 和 `source.fetched_at`（Task3 report:34,46）。触发：任意真实 WeGame snapshot，包括当前 needs_input 样本。影响：用户无法辨认读取的是哪个角色、哪个赛季或何时读取，尤其同一链接内容会更新。修复：对已有净化字段做类型、长度、允许格式与私有内容检查后输出公共 camelCase 值；来源时间不存在时明确只保留读取时间。未知赛季 ID 不凭空翻译。补安全字段保留与恶意值剔除两个定向断言，保持无需重新采集。

2. **非空珠宝及其词缀不进入逐项审计清单。** `server/app/poe2/imports/mapping.py:246-249` 对整段 `jewels.items` 仅产生一个 `JEWELS_UNMAPPED`，没有遍历任何珠宝或调用 `record` / `mods`。Task3 的实际 schema 为 `items: [{jewel: {...}, ...}]`（Task3 report:44），因此不能用装备的 socketedItems 遍历覆盖此路径。触发：来源自然返回任意非空珠宝结构。影响：虽然转换被阻断，但 coverage/ledger 的 items 和 modifiers 总数漏掉整类原始数据，无法满足 brief 的“每一原始节点/词缀/宝石必须进入已映射清单或问题清单、数量可核对”；report 的全类别对账声明不成立。修复：不需要增加珠宝转换支持，只需按 collector 的安全结构为每个珠宝及可识别的词缀建立受控路径的 unmapped 记录；未知结构单列缺口。补一个至少两颗珠宝、多条词缀的非空 fixture，核对原始总数与 ledger/coverage 一致，且 character 仍为 None。

### Critical

无。

### Minor

无额外阻断建议。

## 定向核查及证据边界

- 按 review package 读取新增文件及 Task4 接线；worker/数据库测试中的 Task2 底座未重新作为 Task4 改动评审。未运行任何本地程序、测试或现有云端测试套件，未改产品代码、未部署。
- 具体跨文件风险“资源限制是否真的阻断网络”：只读检查既有 `server/app/poe2/engine_runner.py:9-41`，确认 Lua exec 前加载 seccomp 网络调用拒绝规则。
- 具体跨文件风险“mapper 输出的 flags/词缀类别是否被 ImportTab 静默丢弃”：云端只读检查固定上游 `src/Classes/ImportTab.lua:1210-1415`，确认 properties/requirements、物品 flags、implicit/explicit/enchant/rune/crafted/fractured/desecrated/mutated 路径；未发现本次有限模板/flags 在该路径被静默丢弃。另读取 `918-1060` 核对宝石按 typeLine/support 查 ID 及等级/品质导入逻辑。
- 具体跨任务风险“预览与珠宝真实形状”：只读检查 Task3 report:30-58 的已定 schema，以及 design:12；没有扩展到 Web 实现。
- 没有重跑 implementer 已报告测试。现有测试缺少上述两个断言；建议修复时云端定向运行 mapper 用例，不需要重采分享或重复全套 PostgreSQL/引擎测试。

## Task 6 待验证

- ⚠️ 至少一份资料完整、来源版本/任务选择可证明的真实国服样本；当前分享缺珠宝、base_info、版本及 quest provenance，必须保持 needs_input。有限映射工程完成与“国服完整打通”分别计状态，后者仍未完成。
- ⚠️ 对该真实样本做源清单→原生 XML→导出重导入对账，核对生命、属性、抗性和指定主技能配置。当前合成 fixture 的 roundtrip 不能证明这些真实业务结果。
- ⚠️ 最终 Candidate 真实进程装配下，验证采集→缺口预览→补充 PoB→ready 的 Web/Chat 流程、第二 owner 隔离与公开输出净化；当前 report 说明服务未部署本次代码，因此不能从 main.py 静态注入推导已上线可用。

**Assessment：Approved（Task4 工程范围）。** 两项 P2 已修复并有针对性测试；真实完整样本验收继续作为 Task6 的明确未完成项。
