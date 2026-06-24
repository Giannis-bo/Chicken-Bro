# 职业专精 Tab 前后端方案

## 产品目标

`职业专精` tab 是构筑学习与模拟入口，不再只是“BD 文案列表”。当前实现围绕四个入口：

- 天赋构筑：进入原生 WebSim 天赋模拟器。
- 装备模拟：在职业 / 专精上下文内替换 16 个 canonical 槽位、检查 SimC 可执行状态并保存装备模板。
- 属性权重：展示样本、SimC scale factor、来源窗口和解释，不把通用趋势包装成个人结论。
- 输出循环：按职业 / 专精展示可练习的起手、爆发、平稳期和场景处理。

首页保留 `职业情报` 入口，用于聚合赛季状态、来源、样本和近期趋势；它不替代详情页与模拟器。

## 前端结构

当前页面由这些小程序页面共同承载：

- `pages/builds/builds`：tab 首页，请求 `/api/builds/home`，展示四个主入口和职业情报入口。
- `pages/builds/intel`：职业情报页，请求 `/api/builds/intel`。
- `pages/builds/talent-simulator`：原生 WebSim 天赋模拟器，请求 `/api/websim/bootstrap`、`/api/websim/talents`，并通过 `/api/talents/*` 完成校验、导入和导出。
- `pages/builds/detail`：承载装备模拟、属性权重和输出循环。`query=talents` 会重定向到 `talent-simulator`。
- `pages/builds/websim-api.js`：WebSim/装备相关前端 API client 和 fallback。

`/api/builds/home` 仍返回当前 `WOW_CLASSES` 全职业 / 专精矩阵的 `classOptions`，前端同时保留本地 fallback，防止 API 不可用时空屏。远端 payload 可更新 `quickActions`、`trustedSources`、`analysisWindow`、当前赛季字段和来源状态，但不能让无来源结论进入页面。

## 数据契约

`server/builds/home-payload.js` 定义职业专精基础契约：

- `buildSpecializationHomePayload()`：tab 首页、当前 `WOW_CLASSES` 全职业 / 专精矩阵、四个入口、可信来源、当前赛季和 Raider.IO 状态。
- `buildSpecializationIntelPayload()`：职业情报聚合。
- `getSpecializationDetail(id)`：某职业 / 专精的天赋、装备、属性权重和循环基础详情。

装备模拟的真实数据不再由静态 `details.gear` 承担，而是走 `server/websim_payload.py`：

- `GET /api/websim/gear?class=...&spec=...&compact=1` 返回 16 槽、`slotReadiness`、候选装备、来源、变体、宝石/附魔选项、`communityTemplates`、catalog 状态和 blocker。
- `POST /api/websim/profile` 生成可提交 SimC 的 WebSim profile 前置 payload。
- `POST /api/websim/simulate` 只有在天赋编码成功且核心装备槽位 SimC-ready 时才提交到模拟链路。
- `POST /api/websim/gear/stats` 保留给 WebSim/模拟器链路，不作为职业专精页的普通属性快照来源。

每条前端可见构筑、装备、属性和循环数据都必须携带来源、时间窗口、状态或 blocker。缺来源字段的数据不得进入首页或详情页。

## 可信来源和状态

职业专精和装备模拟只能消费可追溯来源：

- Battle.net Game Data：赛季、地下城/团本、物品中文名、图标、护甲/武器类型、职业限制、journal loot 和官方 metadata。
- SimulationCraft：可执行 profile、装备实例属性、scale factors、SimC JSON gear output 和 deterministic report。
- Raider.IO：国服 M+ runs、observed profile 配置、社区模板输入、分数/队伍/样本窗口。Raider.IO/WCL profile API 只能作为观测配置和校验引用，不能反填生产属性。
- Warcraft Logs / Archon / Subcreation / Wowhead / Icy Veins：作为授权或 reference-only 来源时必须记录 source URL、发布时间、分析窗口和来源说明。未确认授权前不得公开第三方全文或把参考来源标为 verified。

状态语义：

- `verified`：可作为强结论、可执行输入或已验证来源。
- `partial`：部分可信或缺字段，只能参考或继续补齐。
- `source_reference`：来源参考，不等于 verified。
- `blocked`：确定性阻断，必须给出原因和下一步。
- `stale`：过期或赛季漂移风险，不能输出强结论。

装备页尤其要保持边界：observed-only、SimC preset-only 或 source-reference 候选不得伪装成当前赛季可信掉落；展示型装备缺少 `bonus_id/gem_id/enchant_id/crafted_stats` 等字段时不能被写成可执行 SimC gear。

前端读取装备明细时以 DB 中的装备变体为准，不在页面现场计算或推断属性。若 API 返回 `partial` / `blocked` 或 blocker，页面不能把它静默折叠成普通候选或强结论；必须展示为来源、属性或可执行字段缺口，并确保 `/api/data/health`、同步日志和交付说明能追溯到具体 item、slot、variant、source 和原因。线上可放心使用的目标是玩家可见装备明细全部收敛为 `verified`。

`/api/websim/gear` 这类读模型只能输出 DB 已入库的变体和属性。缺失的勇士 / 英雄 / 神话 / 虚空晋升轨道、缺失属性或缺失 SimC 字段不得由前端或请求时 payload builder 临时推断；应保留为 `partial` / `blocked`，通过 health 和页面提示暴露给项目 owner 分析并回填。

## 当前实现状态

线上当前赛季来源覆盖已经能通过 `/api/game/season` 和 `/api/data/health` 验证：

- M+ 当前池：执政团之座、艾杰斯亚学院、节点希纳斯、萨隆矿坑、迈萨拉洞窟、通天峰、风行者之塔、魔导师平台。
- 团本当前池：The Voidspire、The Dreamrift、March on Quel'Danas、Sporefall。
- `gear_catalog` 暴露 M+ `8/8`、团本 `4/4` 和 per-instance coverage。
- `/api/websim/gear` 对职业 / 专精返回 16 槽 readiness 和 compact payload；保存装备模板必须补齐 canonical 16 槽，off-hand 只在双手/无副手合理场景可空。

整体 catalog 仍可能是 `partial`。当前主要缺口是 deterministic SimC variant preset、少量天赋 spell detail、社区模板/WCL 凭据或 stat weight 数据，不影响已验证来源覆盖的表达，但会阻断强模拟结论。

## API

- `GET /api/builds/home`
- `GET /api/builds/intel`
- `GET /api/builds/detail?id=<specializationId>`
- `GET /api/builds/stat-weights/refresh-runs/latest`
- `GET /api/game/season`
- `GET /api/data/health`
- `GET /api/websim/bootstrap`
- `GET /api/websim/talents?class=<classKey>&spec=<specKey>&hero=<heroKey>`
- `GET /api/websim/gear?class=<classKey>&spec=<specKey>&compact=1`
- `GET /api/websim/loot?instanceId=<instanceId>`
- `POST /api/websim/profile`
- `POST /api/websim/simulate`
- `POST /api/talents/validate`
- `POST /api/talents/export`
- `POST /api/talents/import`

## 准确性边界

职业专精数据会随版本、热修、团本开放进度、大秘境词缀和外部数据源变化而漂移。页面只展示带来源、时间窗口、样本说明、状态和 blocker 的数据。

没有完成采集和校验前，不得把人工编写内容、LLM 推理、observed-only 配置或第三方参考链接包装成“最优天赋”“毕业装备”或真实个人 Sim 结论。低样本专精展示样本不足；外部凭据缺失、赛季漂移、SimC 不可执行或来源不一致时输出 `partial` / `blocked`，而不是空态或强结论。
