# POE2 角色入口最终独立审查

日期：2026-09-20。审查对象：`2026-09-20-poe2-link-final-review.diff`，基线 `fe0e398697bf31791d213a5845a0818cf54572df` 至当前未提交工作区。整体包含此前工程；本轮重点为角色入口增量与既有构筑、基线、Chat 的接线。依照 requesting-code-review/code-reviewer 模板独立审查，未派代理、未运行本地程序或重复云测试，仅写本文件。

**当前结论：工程 gate 与 Task6 最小 Candidate 集成验收 PASS / Approved，F1、F2 均关闭，无新增 open Critical/Important。** 以下初审及阶段性判断保留历史；最终证据核对见文末。用户仍禁止提交合入，完整真实国服样本及用户验收仍 pending。

## Spec Compliance

- 两来源入口与 provider 校验、统一 owner-scoped 状态机、ninja 零后台网络辅助导入、WeGame 自然请求独立采集、缺口阻断转换、真实基线 ready 不变量均已实现。API/Chat 使用同一 application/repository，旧 `/builds` 分享码/XML 路由保留。
- **工程质量仍有一项 Important：F1。** 单 Task 审查通过没有覆盖完成后父子组件卸载/重挂载的导航闭环。
- **业务范围未整体完成。** 当前 finite 映射真实国服返回 needs_input；版本、任务依据、珠宝及大量映射缺口仍可见。至少一份资料完整的真实国服样本及其面板/导出往返对账仍未验收。该项是已记录的业务缺口，不将合成 ready 或补充用户 PoB 当作国服来源完整转换。
- Task6 最终 Candidate API、实际浏览器、移动布局、最终 collector 自然采集及部署身份尚待执行方提供证据，本版审查不宣称通过。

## Strengths

- `server/app/poe2/imports/repository.py:122–147`：当前 attempt、lease owner、租约/快照期限和活动状态共同约束完成；真实结果指标及 XML hash 验证后，在同事务内创建确定性 build/job 和 ready 引用，取消后的旧 worker 不能写回。
- `server/app/poe2/imports/worker.py:18–49`：网络采集仅在未提供 XML 的 WeGame 分支，owner 来自 claim 行；mapper 的 blocking issue 阻止 convert，来源面板值未写成引擎结果；补充 PoB 的 provenance 明确 user_supplied。
- `server/poe2_source_browser.cjs:15–35,86–115,118–177` 与专用 service：自然页面请求精确白名单、流式字节上限、先展开珠宝再净化、完成窗口错误收束；独立服务文件视图和内核 IP deny 与无网络引擎分离。`server/poe2_source_supervisor.py:13–28,60–80` 保留每任务收养/回收及 stdout 排空修复。
- `server/app/poe2/imports/mapping.py:122–129,276–335`：版本未证实、珠宝、任务等不足仍为 blocking；词缀/宝石/节点有逐项计账，未知值未通过模型猜译进入计算。原生桥接检查固定引擎提交、gem ID、词缀解析及导入后数量/节点状态。
- `server/app/poe2/tools.py:33–66`：可信 POE2 capability 与 principal 提供 owner，新增动作拒绝多余参数；MCP/adapter 的 game 工具集与 gateway 对齐。`WebPoe2.tsx:169–176` 验证 build/job 关联及成功基线，正常 ready 接线没有再提交计算。
- 前几轮修复有对应定向红绿证据：过期 snapshot 不复活、珠宝敏感值净化、进程回收/大响应、预览与珠宝计账、旧 poll/restore/历史列表竞态。阅读现有报告及测试实现，本轮没有重复执行这些用例。

## Issues

### Critical (Must Fix)

无新增发现。

### Important (Should Fix)

**F1 / P2 — ready 恢复记录未消费，返回导入会自动跳回旧构筑。**

- 位置：`apps/mini-taro/src/web/Poe2CharacterImport.tsx:51–57,75–78,94–98`；接线路径 `apps/mini-taro/src/web/WebPoe2.tsx:166–176,228`。
- 触发：正常角色导入达到 ready，onReady 装入构筑并令父组件进入第二步，角色入口因此卸载；用户随后点击“返回导入”或第①步。新入口实例将 delivered ref 重置为空，从 sessionStorage 读取仍保存的 ready ID，再次自动调用 onReady，父组件跳回第二步。
- 影响：成功过一次的会话无法稳定停留导入页继续输入第二个角色，也会打断手动 PoB 入口。该行为由组件挂载、storage 和 effect 顺序直接成立；现有 Task5 时序用例覆盖首次 ready 与旧列表，但未覆盖完成后返回入口。
- 修复：成功交付基线后消费该 ready 恢复记录，或由父级持有已交付 ID 并避免导航返回时再次自动交付；加载失败仍应保留恢复/重试能力。注意父级 onReady 会卸载子组件，不能让仅挂载期间执行的 finally 条件导致消费动作失效。
- 验证：仅补云端定向用例“ready → 第二步 → 返回第一步 → 稳定停留并可新建”；结合现有 ready 加载失败/恢复行为校验，不必重复来源采集或全量套件。

### Minor (Nice to Have)

- `docs/plans/2026-09-20-poe2-link-task5-report.md:143`：最终 H5 构建有 2 条 webpack 体积告警。当前没有实际加载退化证据；保留给 Task6 页面加载检查，不为已有告警扩展优化或重复构建任务。

### Task6 补充 finding（修复前记录）

**F2 / P2 — ninja 辅助导入缺少打开原角色页入口。** 来源：`docs/plans/2026-09-20-poe2-link-task6-report.md` 的真实浏览器验收；修复前 `Poe2CharacterImport.tsx:154–161` 只显示 Copy PoB 说明，没有锚点。backend handoff 已将校验后的 `sourceUrl` 放入任务 preview，但 Web 未消费；刷新恢复时链接输入框也为空，用户不能从恢复的任务直接打开原页复制。应只用再次通过 ninja URL 校验的已存 preview.sourceUrl 渲染链接，配合 `target=_blank` 与 `rel=noopener noreferrer`，并验证刷新恢复及恶意 URL 不生成链接。

## Recommendations

先修 F1 并提供最小云端回归，再将 Task6 最终身份与业务证据追加到本审查。真实国服完整样本门槛继续单列；当前可交付能力的表述应为 ninja 用户辅助导入、WeGame 公开读取和缺口提示/补充 PoB。

Task6 尚待证据：真实 Cookie/CSRF 与第二 owner 五条任务路由；最终 collector 的 owner 注入、自然采集/净化/needs_input 和退出回收；ninja 真实基线、刷新与三步页面/移动端；旧 PoB/XML 路径；实际 Chat 调用；最终源码、服务和公网 Web 产物身份及保留的恢复入口。该清单沿用已有计划，不要求重新跑已通过的单元套件。

## Declined to judge

- 生产发布、QQ 真人登录及生产回切：本轮仅获 Candidate 授权，用户禁止提交/合入；不从 Candidate 结果推断生产就绪。
- 新赛季、完整词典及所有珠宝语义：超出已确认 finite 工程范围；实际完整国服样本门槛仍保留为未完成业务验收，未被取消。
- 历史 POE2 工程的全部旧回归穷举：本轮只核对与新入口关联的旧 builds/jobs/compare/export、权限及 UI 接线；沿用已提供旧工程证据，不重新宣布整体历史功能经过本轮运行验收。
- WeGame 来源公开使用规范的最终许可结论：代码与现有采集结果不足以作此判断，沿用 Candidate 边界。

## Assessment

**Ready to merge? No. Task quality: Needs fixes (F1).**

核心状态机、来源分离和缺口真实性符合工程设计，但完成后的导航闭环有可复现缺陷，需修复。用户当前禁止合入；Task6 运行证据与完整真实国服样本门槛仍未完成，本结论不构成发布或业务验收。

## 唯一 Scoped Re-review — F1 / F2

**Spec Compliance：PASS（本次工程范围）。Task quality：Approved。**

- **F1 addressed。** `Poe2CharacterImport.tsx:94–104` 在调用 onReady 前捕获 storage key；成功回调后只删除仍指向该 ready ID 的记录，消费不依赖卸载后的 generation，因此父级切换第二步不会阻止清理。异常留存恢复记录；`WebPoe2.tsx:172,177` 在过期账号交付时返回 false、成功加载时返回 true，false 不消费。较新 ID 不被旧完成回调删除。
- **F1 验证匹配。** `web-poe2.test.tsx:103–123` 覆盖 ready→第二步→返回第一步→创建新导入，断言只恢复一次、保存新 ID 且不重算；`poe2-character-import.test.tsx:139–145,161–177` 覆盖加载失败后重挂载恢复、卸载后消费、较新 ID 保留及父级 false 保留。父级真实 generation 分支由静态 diff 核对，组件用例用 false 回调控制该分支结果。
- **F2 addressed。** `Poe2CharacterImport.tsx:149–150,166` 仅使用 ninja 任务的字符串 sourceUrl，经过既有精确 host/path/protocol 校验后显示链接；编辑框不控制 href，目标和 rel 符合要求。`poe2-character-import.test.tsx:147–159` 验证从已存任务恢复、编辑框变更不改来源链接，以及 javascript、伪造主机、userinfo、编码分隔符均不出现锚点。
- **证据范围。** 读取 `2026-09-20-poe2-link-final-fix-review.diff` 的精确四文件增量、当前对应行及 final-fix-report。报告记录旧实现 24/27（3项红）、最终 29/29、typecheck/lint/H5 构建通过；本复审未重复测试、修改产品代码或派发代理。最新构建清单 SHA256 为 `51e606352ba7afeeb831156d3bec02a5d9b5309d6a740233da1e818d9aa48600`，按报告审阅，尚不视为已部署或已做修复后真实页面验收。
- **当前 Issues。** Critical：无；Important：无 open；Minor：两条 webpack 体积告警保留，未扩大优化范围。没有新增 declined-to-judge 项，沿用上文列项。

### Task6 当前证据与剩余边界

已读取 Task6 首轮 report：执行方报告真实已签发 Candidate Cookie A/B、错误 CSRF 403、来源错配422、创建幂等、跨 owner 读取/取消/补充404；最终 collector 一次自然采集得到 needs_input、角色预览与珠宝等缺口、空 build/job ID；真实云浏览器验证恢复、取消后刷新、390px 无横向溢出及输入聚焦。本复审按报告采纳范围，没有独立重跑或将测试 Cookie 当 QQ 登录。

仍待修复后部署与 Task6 后半证据：ninja 原页入口和真实 XML ready 指标、无额外基线提交、ready 返回第一步、详情/导出、手动/示例兼容、WoW 导航、完成结果的第二 owner 隔离，以及最终产物/运行身份。真实完整国服样本仍缺，不能声称 fullready；首轮 WeGame needs_input 证据无需为本次纯 UI 修复重复采集。

**Ready to merge? No（用户禁止提交合入，Task6 仍在进行）。Engineering gate: Approved，可继续既有授权的 Candidate 部署与后半验收。**

## Task6 最终证据与验收脚本范围核对

本节仅读取 Task6 report 末节、`artifacts/verification/2026-09-20-poe2-character-import/` 下 `api.json`、`browser.json`、`chat.json`、`delivery-identity.json`、`runtime-identity.json`，及三个新增 `tests/poe2_character_candidate_{smoke.py,browser.cjs,chat.py}`。没有第二次产品代码复审、运行测试、访问来源或扩展验收范围。

**Task6 engineering / 最小真实 Candidate 集成验收：PASS。** 报告、净化结果和脚本断言的主要业务结论相互匹配：

- API：错误 CSRF、两来源误配、创建幂等、第二 owner 读取/取消/补充拒绝和取消均有对应断言。WeGame 任务 `d18e6514-1480-42b3-a7b4-24c1343deb29` 的实际读取结果为 needs_input，572项缺口、MISSING_JEWELS、空 build/baseline；Chat 后续读取同一任务为 cancelled，与浏览器取消后的时序一致。
- 浏览器：实际用户 ninja 链接来自已存任务的原页 href，刷新仍匹配；确认后补充真实 XML 得到 ready。结果 `Life=2813 / EnergyShield=962 / Armour=7284 / Evasion=14138` 与报告、脚本 exact assertions 一致，引擎为 `v0.23.1@7d6f530cbdab20389ff8bc6ba97a37ac27f74e41`。脚本断言 `/poe2/jobs` POST 数为0；净化 POST 清单也没有该路径。ready→返回①→不同新任务、详情导出、手动/示例导入、WoW/SimC 导航、B读取结果及retry404均有实际操作和断言。390px无横向溢出、截图遮蔽输入及空 pageerror 符合报告；本节不重做截图视觉审查。
- Chat：`chat.json` 和报告一致绑定 conversation `73fe3d4c-c37f-57ae-824d-828f8d16d792`、run `9839ab7b-1a93-4cb6-9d90-802fdfe1b906`，run succeeded，恰一条 `poe2_character_get`，无errorCode，返回 cancelled。三个脚本中 Chat 脚本只负责发起这一受限读取、私存原始SSE/消息和初始报告；最终 run/tool/answer 字段来自执行方后续持久 trace 核对，并非该脚本自动断言。当前证据足以记作一次真实 Chat get 成功，不扩大为五种 Chat 操作的全部端到端验收。
- 身份：delivery 记录15个公网文件逐项匹配、未提交及固定引擎；runtime 的 Candidate runtime、collector、supervisor、service、mapping hash 与 delivery 对应 sourceFiles 一致。服务 active 仅作身份背景，业务结论来自上述实际API/浏览器/Chat证据。最终 source manifest 仍由root按验收脚本更新刷新；本节不把当前包含旧测试清单的 manifest hash 固定为最终全部文件身份。
- 范围：API脚本仅对授权WeGame链接作本轮采集；最终浏览器从已取消任务继续，不重复采集，ninja没有上游自动抓取。脚本读取已有云端私有会话/样本，截图mask输入，未见新增产品实现、提交/合入、生产切换或恢复演练动作。旧 `browser-failure.json` 仅为F2修复前失败历史，最终结论采用 `browser.json`。

**最终 Assessment：Approved（工程及最小 Candidate 集成范围）；Ready to merge? No（用户禁止提交合入）。** 两条构建体积告警保持非阻断，实际页面流程已完成。完整真实国服来源映射/面板对账、用户体验验收仍 pending；QQ真人登录、生产发布及数据库恢复演练没有新增证明。所有已关闭 finding 保持关闭，无新增产品缺陷。
