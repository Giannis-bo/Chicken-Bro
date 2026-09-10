# 自定义施法与玩家术语检索

2026-09-10。用户授权实现两项修复；源码未提交，未推送或发布。生产仍使用 compiler v5。本目录 source-manifest.json 绑定本轮文件，不能将其 baseCommit 当作包含改动的提交。

## 实现

- compiler v6 支持 `actionLists` 完整列表，含 default、precombat、子列表、条件与序列。保留原角色/装备/天赋与其他场景设置；整组替换、稳定哈希、幂等和 owner 边界沿用 application。
- 预检、Chat 提交/读取、任务对照与 Web scenarioVersion=4 合同贯通；旧客户端隐藏新字段。预检不是引擎语义验收；未知技能或无效表达式由云端运行拒绝。
- v6 Worker 继续核对有效装备/天赋，并要求实际动作样本。记录采样迭代最多 512 条的相对时间、动作名、spellId 和 profile hash。样本不能代表全部迭代，也不能由相同时间戳推断先后。
- 俗称/简称/套装先按职业、版本、赛季检索；命中无关资料时换正式名、英文名或相关原始资料。只有检索后仍缺关键信息才追问。没有给“神器”硬编码固定映射，也没有写死四件套效果。

## 实际验证

- 最终源码：112 项 Python 定向测试通过，覆盖 compiler/readiness/Worker/application、预检/幂等/第二账号、API 旧版本兼容和 native MCP。运行在云端已有 Python 环境的隔离代码目录；本机 Python 缺 FastAPI，未安装依赖。首轮少带脚本导致的失败已补齐重跑；早期 128 项中包含重复导入的 16 项 fixture，最终移除重复收集后为 112 项。
- 本机：12 项 TS domain/API 测试、typecheck、lint、H5 build、diff --check 通过。H5 保留资源体积两项警告。
- 云端现有引擎，两组完整 APL、相同存档公开角色、单体 60 秒/100 迭代：风暴守护者 0 秒→升腾 1.207 秒；升腾 0 秒→风暴守护者 1.206 秒。有效装备/天赋均核对通过，见 cloud-summary.json 与可复现脚本 cloud-apl-check.py。
- 两组 DPS 为 205930.81 ±2500.56 与 209433.26 ±2773.32，差异落在两组报告误差之和内。这仅验证顺序控制链路；不是当前玩家四件套收益结论，也不是“神器”解释的事实依据。
- 最终源码再次运行同一输入哈希，两种顺序仍核对成功（0→1.205 秒、0→1.206 秒），两组收益仍在报告误差内；未固定随机种子，不将重跑波动当作性能变化。复测数值见 cloud-summary.json 的 finalSourceRerun。
- strict_sequence 初测的 JSON 只显示包装动作，没有子技能时间；该次没有被认定为顺序验收。最终用 buff/cooldown 条件使实际动作可核对，并在 Chat 规则中保留此限制。
- 初轮真实 Chat 三题：原题检索 2 次；冰法俗称 holdout 检索 5 次；纯方案题未提交模拟。后两项取得的资料不足以确认当前技能联动时，如实保留缺口。第一轮原题 148.92 秒包含隔离 Worker 端口配置修复等待，不作性能比较。
- 最终原题复测：46.82 秒、3 次检索，先查资料、提出风暴守护者候选，再追问版本和角色/已有任务，未宣称不支持自定义施法、未捏造模拟结果。外部来源本次没有提供有效套装/技能正文，不能宣称已成功解析当前四件套效果。最终结果保存在云端隔离目录 `/tmp/chickenbro-custom-apl-20260910/candidate.json`；初轮为 candidate-first.json。
- 隔离 Chat 还核对了历史、幂等、断开后继续、账号并发限制与第二账号访问拒绝。测试会话归档，临时 sessions 撤销；临时服务在无活动任务时停止。QQ 只验证授权 URL，不宣称新一次真实扫码登录。

## 发布前仍需

用户明确授权发布；API/Worker 同时加载本轮源码并设置 `WOW_SIMC_COMPILER_REVISION=chickenbro-simc-compiler-v6`；绑定 Web 新产物、保留精确回退配置，空闲门禁切换后做公网 Chat/SimC 验证。没有升级 SimC 引擎、安装依赖、改生产数据库或重放旧迁移。

APL 语义参照 [SimulationCraft ActionLists](https://github.com/simulationcraft/simc/wiki/ActionLists)，并核对云端当前 source archive；优先级不等于施放时间。
