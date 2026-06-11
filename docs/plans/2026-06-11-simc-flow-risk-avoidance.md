# SimC 全链路问题回顾与规避方案

**目标：** 单独梳理 SimC 从入参校验、真实执行、执行结果输出、横向校验，到 LLM 总结输出的完整链路，并把项目会话里反复出现的问题收束成可执行的规避方案。

**当前证据基线：**
- 后端入口：`server/news_backend.py` 的 `POST /api/simulator/analyze`。
- SimC 主流程：`server/simulator_payload.py`。
- 小程序 SimC 工作台：`pages/simulator/simc.js` / `pages/simulator/simc.wxml`。
- 小程序任务详情：`pages/simulator/task-detail.js` / `pages/simulator/task-detail.wxml`。
- 端到端契约文档：`docs/simulator-simc-end-to-end.md`。
- 关键测试：`tests/news_backend_test.py`、`tests/frontend-api-client.test.js`、`tests/simulator-page.test.js`、`server/simulator_e2e_smoke.py`。

## 一、当前真实流程

### 1. 前端入参阶段

当前小程序 SimC 页面采用“两段式”流程：

1. 用户在 `pages/simulator/simc.js` 输入自然语言。
2. 前端先发 `mode=simcraft_agent`、`confirmOnly=true`，让后端判断是否信息足够。
3. 后端如果认为可生成模板，前端才开放“提交任务”。
4. 用户点击提交后，前端发 `runSimulation=true`、`saveTask=true`，请求真实执行并保存任务。

从职业专精页进入 SimC 时，前端还会带入 `buildContext`，包括专精、天赋导入代码、装备候选、属性趋势和来源窗口。这里的边界是：装备候选只能作为比较上下文；没有 item id、bonus id、附魔、宝石和当前角色导出时，不能硬转成 SimC gear 行。

### 2. 后端 API 接入阶段

`server/news_backend.py` 中：

- `POST /api/simulator/analyze` 调 `analyze_and_store_simulator_task()`。
- `analyze_and_store_simulator_task()` 调 `analyze_simulator_request()` 得到分析结果。
- 如果用户已登录或允许游客保存，并且 `saveTask=true`，结果会写入 `simulator_tasks`。

这层只应该做 HTTP、鉴权、任务存储和路由，不应该承载 SimC 语义判断。

### 3. 入参归一化与校验阶段

后端目前有两条入口：

- `mode=simcraft`：偏旧的 prompt/profile 直接分析路径。
- `mode=simcraft_agent`：当前主要玩家路径，按对话确认需求。

`simcraft` 路径会：

- 读取 `prompt` 和显式 `profile`。
- 从 fenced ```simc / ```simulationcraft 代码块提取 profile。
- 如果没有 fenced block，则尝试从 profile-like 行提取。
- `profileSource` 标成 `explicit`、`prompt` 或 `none`。
- 有 profile 时才允许 `runSimulation`，并在 `mode=simcraft` 且 profile 存在时自动开启真实执行。

`simcraft_agent` 路径会：

- 从 message 推断 intent：baseline、stat_weights、gear_compare、talent_compare、out_of_scope。
- 推断 scenario：单体 Patchwerk 或大秘境多目标 HecticAddCleave。
- 推断职业、专精、装等。
- 从 `buildContext` 补齐专精和天赋导入代码。
- 如果缺关键信息，返回 `needs_clarification`，不执行 SimC。
- 如果是违规/跑题输入，返回 `off_topic`，不执行 SimC。
- 如果只有自然语言且信息足够，生成一个 `generated` 模板，但它只能是模板预览，不是正式角色模拟结果。
- 只有 `explicit` 或 `prompt` 来源的完整 profile 才能进入真实 SimC 执行。

### 4. SimC 真实执行阶段

`run_simcraft()` 做的事情：

- 通过 `WOW_SIMC_BIN` 或 PATH 查找 `simc` / `simulationcraft`。
- profile 为空时直接返回 `empty profile`，不执行。
- 用 `[binary, "-"]` 把 profile 从 stdin 传给 SimC。
- 使用 `WOW_SIMC_TIMEOUT_SECONDS`，默认 45 秒。
- 捕获 stdout/stderr。
- 先从完整输出中解析 `DPS=` 或 `DPS Ranking`，再把 summary 截断到 4000 字符。

关键边界：

- `confirmOnly=true` 不执行真实 SimC。
- `profileSource=generated` 不执行正式 DPS 模拟。
- `generated` 的 `simulation.quality=preview`，`metrics` 清空，前端不能显示成正式 DPS。

### 5. SimC 输出结果阶段

后端响应包含：

- `request`：归一化后的 mode、prompt、profile、profileSource、runSimulation、buildContext。
- `agent`：状态、缺失槽位、draftProfile、校验结果、summaryCards。
- `stages`：profile_check、simc_execution、mythic_plus_reference、ai_interpretation。
- `simulation`：ran、available、summary、metrics、error、quality、metricLabel、metricUnit。
- `mythicPlusReference`：大秘境横向参考。
- `recommendations`：最多三条确定性建议。
- `llm`：prompt、called、model、content、error。
- `codex`：可选 Codex worker 状态。

当前任务详情页刻意不展示完整 generated SimC 模板、原始 SimC summary 或完整 LLM content，而是展示：

- 顶部简化结论；
- `AI 结论` 的 recommendations；
- `SimC 结果`；
- `真实大秘境对标`；
- `执行阶段`。

### 6. 横向校验阶段

当前横向校验依赖 `server/simulator_payload.py` 内置的 WoW.gg Mythic+ snapshot：

- 覆盖 13 职业、39 专精。
- DPS/Tank 用 Avg DPS、Max DPS、Max Key。
- Healer 同时带 Avg DPS、Avg HPS、Max HPS，避免只用 DPS 评价治疗。
- 多目标场景才挂 `mythicPlusReference`。
- LLM prompt 会收到该参考，并被要求先对齐真实大秘境量级。

这个阶段的本质不是“证明 SimC 结果一定正确”，而是防止报告输出与真实日志量级冲突，尤其防止 80 万、100 万、数百万这种无来源的大数。

### 7. LLM 总结阶段

`build_llm_prompt()` 会把以下内容组装给 LLM：

- 模式、角色、玩家问题；
- profile 或构筑输入；
- 经过过滤的 SimC 摘要；
- SimC 错误；
- 真实大秘境对标；
- 构筑上下文；
- 数值规则。

`sanitize_simcraft_summary_for_llm()` 会过滤 `Generating Baseline` 进度行，避免 LLM 把进度数字当 DPS。

`build_guarded_llm_content()` 会在两类情况下覆盖 LLM 输出：

- SimC 没有可用 DPS，但 LLM 试图给模拟 DPS 结论；
- LLM 输出百万级或明显超过参考量级的 DPS。

LLM 在这里只能做解释和表达，不能成为数字事实来源。数字事实必须来自后端解析的 SimC output 或可信参考源。

## 二、已经遇到和反复出现的问题

### 1. 架构边界一开始容易混在一起

问题表现：

- 把普通 LLM、Codex CLI、SimC runner、业务 API 混成一个“AI 后端”。
- 容易问成“Codex 能不能做整套 LLM 方案”，而不是拆清楚每个 executor 的职责。

规避原则：

- 普通模型执行器负责高频文本任务：中文总结、格式化、报告草稿、轻量解释。
- SimC runner 负责 deterministic 执行和数字解析。
- Codex worker 只做低频复杂 agent 任务：profile 修复、WCL 导出分析、跨文件证据复核。
- 前端永远不直连 OpenAI/Codex/SimC。

### 2. 路由实现和真实 API 可达性曾经不一致

问题表现：

- `/api/simulator/analyze` 看起来实现了，但曾经因为挂错 handler 分支导致 404。

规避原则：

- 每个新 API 必须有 route-level test。
- smoke 不能只测函数，要测 HTTP route。
- POST/GET 路由表要作为验收项单独列出。

### 3. 空 profile 或自然语言输入被误尝试执行

问题表现：

- 用户只输入“我是元素萨，帮我模拟”，早期路径可能进入 SimC 执行，导致 `empty profile`。
- 旧后端 payload 还会让前端以为进入了可提交/可执行状态。

规避原则：

- 没有 `explicit` 或 `prompt` profile 时，不允许 `runSimulation=true`。
- `generated` profile 只允许模板预览。
- 前端对旧后端响应要兜底成 clarification，而不是把 `empty profile` 当执行失败报告。

### 4. generated 模板容易被误当真实角色结论

问题表现：

- 自然语言足够时，系统能生成可执行模板；但这不是用户真实角色导出。
- 如果把模板跑出的 DPS 显示成“当前角色 DPS”，会产生严重误导。

规避原则：

- `profileSource=generated` 时不执行正式 DPS。
- 即使未来允许模板试跑，也必须标为 `quality=preview`、`metricLabel=模板试跑`，不能和正式 `/simc` 结果混用。
- 任务详情必须隐藏 generated 模板里的伪 DPS。

### 5. SimC 示例 profile 不可执行

问题表现：

- 早期 smoke 用 `gear_ilvl`、短 talents 字符串等不完整示例，导致真实 SimC `simulation.ran=false`。

规避原则：

- smoke profile 必须是 SimC 可执行最小 actor profile。
- 示例输入不能只满足“看起来像 profile”，要真的被 SimC 二进制跑通。

### 6. 真实链路时间预算不足

问题表现：

- 本地/前端默认 15 秒对真实 SimC + LLM 不够。
- 远程 smoke 曾经超时。

规避原则：

- SimC-only smoke 和 SimC+LLM full smoke 分开。
- 前端 full analysis timeout 使用 90 秒量级。
- 后端阶段要返回 stage timing，避免用户只看到“卡住”。

### 7. DPS 解析曾经过窄

问题表现：

- 真实 SimC 返回 `DPS=119.35741006451615` 这类 decimal。
- 初始 parser 只适配整数或 ranking 文本，导致 `simulation.metrics.dps` 缺失。

规避原则：

- 解析必须支持 decimal `DPS=` 和 `DPS Ranking`。
- 解析必须发生在 summary 截断前。
- 不能把 report id、iteration count、进度耗时等大数当 DPS。

### 8. SimC 版本/可用性探测不能依赖 `--version`

问题表现：

- 该 SimC binary 的 `--version` 不可靠，曾经误判版本状态。

规避原则：

- 用 `iterations=1 max_time=1` 的真实最小 probe。
- 从输出里的 `SimulationCraft ...` 行识别版本。
- 版本状态写入 `/var/lib/wow-backend/simc-version.json`，前端只读状态，不直接推断。

### 9. LLM 会编数字或误读进度行

问题表现：

- LLM 可能把 `Generating Baseline` 行里的进度/耗时当 DPS。
- LLM 可能输出 80-100 万、数百万 DPS，和真实 Mythic+ 参考量级冲突。

规避原则：

- LLM prompt 必须只喂过滤后的 SimC 摘要。
- LLM 输出必须被后端 guard。
- 任何报告数字都要带 `source=either simulation.metrics.dps or reference row`。

### 10. 前端曾经展示本地占位建议而不是真实结果

问题表现：

- 后端已经跑完 SimC+LLM，但页面仍显示“已生成本地建议”或只显示 summary/recommendations。
- 用户明确要求返回“真实的建议”。

规避原则：

- 当目标是 live analysis，前端 fallback 只能标成 fallback，不能伪装成真实建议。
- SimC 页面和任务详情需要明确展示：正在确认、正在执行、执行失败、已跑通、需要完整 `/simc`。
- 如果要隐藏原始 LLM content，也必须把 LLM 结论经过后端结构化后落到 `recommendations/reportCards`，不能丢失。

### 11. 横向参考目前有 stale 风险

问题表现：

- 当前 WoW.gg snapshot 是内置静态数据，适合防止离谱数字，但会随赛季、周数、热修变化漂移。

规避原则：

- 横向参考应有 `sampleWindow`、`sourceUrl`、`fetchedAt`、`expiresAt`。
- 过期后只能显示“参考过期，需要刷新”，不能继续当作最新事实。
- 最终方案应接入定时刷新或人工刷新后的 reference table。

### 12. 远程环境问题会反复干扰验证

问题表现：

- SSH root 不通，ubuntu alias 可用。
- 服务器直连 OpenAI/GitHub 不稳定，需要代理和预置 geodata。
- 远程 smoke 和本地 smoke 的时延差异很大。

规避原则：

- 远程验证固定使用项目 deploy/smoke 脚本。
- 网络、代理、SimC 二进制、LLM 配置必须拆成独立 health check。
- 下载、安装、拉取远程内容前必须先获用户批准。

## 三、反复问题的根因模式

1. **把“能生成模板”误当“真实模拟完成”。**
   生成模板只是输入补全；真实结论必须有可执行 profile、SimC 成功、DPS 被解析。

2. **把“LLM 说了”误当“后端证明了”。**
   LLM 是报告层，不是事实层。数字事实必须由 runner/parser/reference provider 产出。

3. **把“本地兜底可用”误当“真实后端可用”。**
   小程序 fallback 适合保持页面不崩，但不能替代 live result。

4. **把“单次跑通”误当“链路可维护”。**
   SimC、LLM、远程代理、参考数据都是漂移面，必须有 health check、smoke 和数据时效。

5. **把“实现细节”散落在页面、API、LLM prompt 中。**
   状态机和证据边界应该在后端统一定义，前端只渲染状态。

## 四、完整规避方案

### 方案总原则

SimC 链路应该改成一个明确的证据状态机：

```text
input_received
  -> input_classified
  -> needs_clarification | off_topic | template_ready
  -> simc_executable
  -> simc_running
  -> simc_completed | simc_failed | simc_timeout
  -> reference_checked
  -> llm_summarized
  -> report_ready
```

每个状态都有严格的进入条件、输出字段和前端展示口径。

### 1. 入参契约

建议统一成后端 DTO：

```json
{
  "mode": "simcraft_agent",
  "message": "玩家原始输入",
  "profile": "可选显式 /simc profile",
  "buildContext": {},
  "confirmOnly": false,
  "saveTask": true,
  "clientRequestId": "optional-id"
}
```

后端归一化后必须给出：

```json
{
  "profileSource": "none | generated | prompt | explicit",
  "runPolicy": "never | confirm_only | preview_only | full_simc",
  "missingSlots": [],
  "inputEvidence": {
    "class": "",
    "spec": "",
    "itemLevel": "",
    "scenario": "",
    "profileHash": ""
  }
}
```

硬规则：

- `profileSource=none`：只能 clarification。
- `profileSource=generated`：只能 preview，不可输出正式 DPS。
- `profileSource=prompt/explicit` 且 validation passed：才允许 full_simc。
- `confirmOnly=true`：永远不执行 SimC、不调用 LLM、不保存最终报告。
- `buildContext.gear`：永远只作为 context，不转成 gear lines。

### 2. Profile 校验层

把当前 `validate_agent_simc_profile()` 扩展成独立的 `SimcProfileValidator`：

- 长度限制；
- 禁止 `html/json/xml/output/save` 等输出类 key；
- 必须有 actor line；
- 如果需要正式结果，必须有 `talents=` 或明确提示可信度不足；
- generated profile 必须标注来源和 preview 质量；
- explicit/prompt profile 要生成 profile hash，便于复跑比对。

输出：

```json
{
  "passed": true,
  "severity": "ok | warning | blocking",
  "errors": [],
  "warnings": [],
  "profileHash": "sha256..."
}
```

### 3. SimC Runner 层

把 `run_simcraft()` 收束成 runner 边界：

- 输入只接受 validated profile。
- 用 stdin 传 profile。
- 限制 timeout、最大输出、并发数。
- 解析 metrics 必须在截断前完成。
- 保存原始 stdout/stderr 到内部 task artifact，前端默认只看摘要。
- 错误类型结构化：`binary_missing`、`empty_profile`、`timeout`、`nonzero_exit`、`metric_missing`。

返回：

```json
{
  "ran": true,
  "status": "completed",
  "metrics": {
    "dps": {
      "value": "185432",
      "unit": "damage_per_second",
      "source": "simc_stdout",
      "evidenceLine": "DPS=185432 ..."
    }
  },
  "summary": "...",
  "error": "",
  "durationMs": 42311
}
```

不要只返回裸字符串 `metrics.dps`；最终应逐步迁移到带 unit/source/evidence 的结构。

### 4. SimC 结果输出层

后端应该同时输出机器可读和玩家可读两套结构：

```json
{
  "simulation": {},
  "referenceComparison": {},
  "report": {
    "status": "ready",
    "title": "SimC 已跑通",
    "topFindings": [],
    "nextActions": [],
    "limitations": []
  }
}
```

前端只根据 `report` 和 `stages` 渲染，避免自己拼关键结论。

展示规则：

- 已跑通：显示 DPS、单位、场景、profile 来源、执行耗时。
- 未跑通：显示错误分类和下一步，不显示 DPS。
- generated preview：显示“已生成模板，需完整 /simc 导出”，不显示 DPS。
- LLM 失败：保留 deterministic recommendations。

### 5. 横向校验层

横向校验应从内置 snapshot 升级为 `ReferenceProvider`：

```json
{
  "provider": "wowgg | archon | warcraftlogs",
  "specKey": "paladin-retribution",
  "role": "dps",
  "sampleWindow": "Week 12",
  "fetchedAt": "2026-06-10T10:46:00+00:00",
  "expiresAt": "2026-06-11T10:46:00+00:00",
  "metrics": {
    "avgDps": "186K",
    "maxDps": "260K",
    "maxKey": "+23"
  },
  "sources": []
}
```

硬规则：

- 参考数据过期时，报告必须显示 stale 状态。
- healer 必须显示 HPS 维度。
- generated preview 不能和真实日志横向比较成“合格/不合格”。
- SimC raw DPS 和 Mythic+ logs 是不同证据类型，只能并排解释，不能强行等价。

### 6. LLM 总结层

LLM 输入应该从自由文本 prompt 逐步改成 evidence JSON + report instruction：

```json
{
  "playerQuestion": "",
  "normalizedInput": {},
  "simulationEvidence": {},
  "referenceEvidence": {},
  "allowedNumbers": [],
  "forbiddenClaims": [
    "不得从进度行推断 DPS",
    "不得输出 allowedNumbers 之外的数值结论",
    "不得把 generated preview 当正式模拟"
  ]
}
```

LLM 输出建议强制 JSON schema：

```json
{
  "topFindings": [
    { "text": "", "evidenceRefs": ["simc.dps", "reference.avgDps"] }
  ],
  "nextActions": [],
  "limitations": []
}
```

后端再做二次校验：

- 每个数字必须出现在 allowedNumbers。
- 每条 finding 必须有 evidenceRefs。
- 不合格则丢弃 LLM 输出，使用 deterministic fallback。

### 7. Codex Worker 边界

Codex worker 不进入同步主链路。

适合 Codex 的场景：

- 修复用户粘贴的无效 profile；
- 分析完整 WCL 导出；
- 多轮装备、天赋、日志证据复核；
- 生成可审计的诊断报告草稿。

不适合 Codex 的场景：

- 每次普通 SimC 请求都调用；
- 高频中文总结；
- 直接替代 SimC runner；
- 作为唯一 LLM 入口。

调用条件：

- profile 已验证或 SimC 已返回结构化错误；
- task 已异步保存；
- 有独立 job directory、resource limit、timeout、output schema；
- 结果进入 review/secondary advice，不覆盖 deterministic facts。

### 8. 前端展示契约

SimC 页面要明确拆成四种状态：

- `clarifying`：继续问最小缺失槽位。
- `ready_to_submit`：模板/输入确认完成，可提交。
- `running`：真实 SimC/LLM 执行中，展示阶段进度。
- `report_ready`：展示结构化报告入口。

任务详情页展示：

- AI 结论：来自后端 `report.topFindings` 或经过 guard 的 recommendations。
- SimC 结果：只展示正式 metrics。
- 横向对标：展示来源、窗口、更新时间、stale 状态。
- 执行阶段：展示每一 stage 的 status/error/duration。
- 原始 profile/raw summary 默认隐藏，可作为调试后台或开发模式信息。

如果未来要恢复即时 `AI 建议` 卡片，也应该展示经过后端 guard 的 `report`，不是原始 `llm.content`。

### 9. 测试与验收门槛

每次改 SimC 链路必须跑：

```bash
python3 -m unittest discover -s tests -p '*_test.py'
node --test tests/*.test.js
python3 server/simulator_e2e_smoke.py
```

部署后必须跑：

```bash
python3 server/simulator_e2e_smoke.py --base-url http://124.223.51.33 --timeout 90
```

新增建议测试：

- 状态机测试：每个状态只能由合法前序状态进入。
- LLM schema 测试：数字不在 allowedNumbers 就拒绝。
- stale reference 测试：过期参考不能输出“最新/合格”。
- frontend report 测试：generated preview 不显示正式 DPS。
- route test：`POST /api/simulator/analyze` 每次必须覆盖真实 HTTP 分支。
- runner test：timeout、nonzero exit、metric_missing 都要结构化。

### 10. 运维与远程验证

远程侧分成独立 health checks：

1. `/health`：backend alive。
2. `/api/simulator/home`：simcraft/llm capability。
3. SimC probe：最小 actor profile。
4. LLM probe：短文本 summarization。
5. Reference freshness：参考源更新时间。
6. Full smoke：SimC + reference + LLM。

远程注意事项：

- 使用 `server/deploy_lighthouse.sh` 作为权威部署路径。
- 使用 `ubuntu` / SSH alias 的稳定路径。
- 服务器 GitHub/OpenAI 访问依赖代理时，要先验证 proxy env。
- 下载、安装、git pull/fetch、依赖安装前必须获得用户明确批准。

## 五、建议实施顺序

### Phase 0：冻结契约

- 把本文方案转成 `docs/simulator-simc-end-to-end.md` 的新版 contract。
- 明确 `profileSource`、`runPolicy`、`simulation.quality`、`report` 字段。
- 给当前状态机补测试。

### Phase 1：后端结构化

- 拆出 input normalizer、profile validator、simc runner、reference provider、report builder。
- 保持现有 API response 兼容。
- 先让测试证明行为不变，再收窄边界。

### Phase 2：LLM 输出 schema 化

- LLM 从自由文本输出改为 schema 输出。
- 后端校验 evidenceRefs 和 allowedNumbers。
- 不合格时自动 fallback。

### Phase 3：横向参考刷新

- 将 WoW.gg snapshot 从硬编码迁移到可刷新 reference store。
- 加 `fetchedAt/expiresAt/stale`。
- 过期参考只做提示，不做强结论。

### Phase 4：前端结果页收口

- SimC 页面展示 running/report state。
- 任务详情只渲染后端 report，不再自行推断关键结论。
- 明确 fallback 与 live result 的视觉差异。

### Phase 5：上线验收

- 本地 unittest/node/smoke 全过。
- Lighthouse full smoke 通过。
- 抽样三类输入：
  - 完整 `/simc` 导出；
  - 纯自然语言 generated preview；
  - SimC 失败 profile。
- 确认三类输入都不会输出越权 DPS 或无来源数字。

## 六、最终判断

当前项目已经有可用的 SimC 主链路，但它还处在“能跑通并有不少 guard”的阶段。下一步真正要规避反复问题，重点不是继续堆 prompt，而是把证据边界产品化：

- 输入是不是足够？
- profile 是真实导出还是 generated template？
- SimC 是否真的跑过？
- DPS 是从哪一行解析出来的？
- 横向参考是否新鲜？
- LLM 的每个数字有没有证据？
- 前端展示的是 live result 还是 fallback？

只要这些问题在 schema、状态机、测试和 UI 文案里都有硬约束，后续再扩展 WCL、装备对比、Codex worker，就不会反复掉回“看起来跑了，其实证据链没闭合”的坑里。
