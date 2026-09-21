# POE2 构筑分析流程

1. 确认输入是 PoB 2 分享码/XML 正文或本账号已有 buildId，并记录版本、赛季、输入来源和引擎身份。
2. 先用 `poe2_get` 读取构筑；有 `baselineJobId` 时直接用 `poe2_job_get` 读取已有基线，缺失基线才调用空 changes 的 `poe2_calculate`。导入 ready 返回的 baselineJobId 同样直接复用。读取成功计算的攻防摘要、有效配置和 unsupported；缺失关键配置时先补齐，不从名称推断数值。
3. 解释核心机制、资源闭环、输出条件与防御层，指出能由当前结果直接支持的短板。
   所有游戏术语默认使用已核实的国服简体名称，不能因输入来自国际服 PoB 就全用英文。技能问题先用 `poe2_get` / `poe2_export` 的 presentation.skills 或成功 `poe2_job_get` 的 skills 核对实际组、启用状态、等级和辅助阶级，再用 presentation.terms 对照展示。未收录先查 POE2 国服来源，仍缺标记“国服名称待核实”并附原文，不猜译，不借用 POE1 或繁体译名。计算参数保留 PoB 原始英文名和 ID，不能把中文展示名直接写进引擎参数。
4. 所有候选复用同一个 buildId，并对齐版本、赛季和控制配置。已有基线和相同方案优先复用，只为尚缺的候选调用 `poe2_calculate`；相同请求重试沿用幂等键。例如：

   `{"buildId":"<同一个 buildId>","changes":{"mainSocketGroup":2},"idempotencyKey":"variant-main-group-2"}`

   这些 changes 是完整的候选修改，不要填写 schema 之外的字段。装备替换使用 `items:[{"slot":"Helmet","text":"<完整装备文本>"}]`；技能组使用 `skillGroups:[{"index":1,"gems":[{"name":"<技能英文名>","level":20,"quality":20}]}]`。
5. `poe2_calculate` 的 reused=true 表示复用了已有任务，直接使用返回的 id。queued/running 时尚无结果，用 `poe2_job_get` 读取终态；failed 报告错误及修正步骤，不送入比较。不要为相同方案不断换幂等键。同一已失败任务的明确重试才使用新键。
6. 两个任务都 succeeded 后，使用 `poe2_compare`，参数为 `{"jobIds":["<基线 jobId>","<候选 jobId>"]}`。仅对工具确认可比的真实结果报告绝对值与差异，同时写清实际 changes 和 unsupported；结果足够回答后停止。
7. Chat 单条消息最多 4000 字。分享码超过 4000 字时，让用户在 POE2 构筑工作台粘贴完整国际服 PoB 2 字符串；XML 先在 PoB 转成分享码。当前 Web 只有字符串单入口，不提供文件上传。随后调用 `poe2_list` 找到该构筑，再用 `poe2_get` 读取 buildId 和来源，不要求用户拆分长文本到聊天中。

8. 计算额度以工具 researchBudget 为准：每轮最多新增 12 次方案计算，同一研究最多 60 个不同方案、120 次执行尝试；达到 30 个方案时优先收敛但仍允许继续。读取、轮询、对比及复用不扣额度。失败的新执行保留消耗；同源构筑、引擎和相同修改按同一方案计数。POE2_RESEARCH_TURN_LIMIT 只停止本轮新增计算，正常追问可继续；POE2_RESEARCH_SCOPE_LIMIT 停止本研究新增计算，仍可分析已有结果。不要建议拆轮、换构筑、重新导入或 /新研究 绕过同一研究上限。Web 手动操作不受此 Chat 方案预算限制。

### 角色链接与持久任务

- WeGame / poe.ninja 分别用 `poe2_character_create` 的 provider=wegame/ninja；链接必须与来源一致。
- `poe2_character_get` 给出阶段及缺口。国际服需用户从角色页 Copy PoB；国服有限映射可能缺珠宝、技能、装备词缀、版本或任务信息。
- 用户确认使用完整 PoB 后调用 `poe2_character_source`；明确代码与链接关系为 user_supplied，尚未核验同一角色。超过 Chat 4000 字时引导 Web 构筑页面，不拆分消息。
- ready 用已有 buildId 与 baselineJobId 调用 poe2_get/poe2_job_get，核对成功结果，不再 poe2_calculate 空 changes。后续方案仍从同一基线创建。
- 失败提供 `poe2_character_retry`；取消用 `poe2_character_cancel`。needs_input 只展示可读取预览及具体缺口，不声称完整国服计算已通过。
