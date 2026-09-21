# Task 5 独立审查

## Round 1 scoped 复审：PASS

- **Spec Compliance：✅ Pass；Task quality：Approved（本 Task 范围）。** R1、R2、R3 均关闭；本轮修复增量未发现新的阻断问题。以下初审记录保留为历史，当前结论以本节为准。
- **R1 已关闭。** `Poe2CharacterImport.tsx:75–92,114`：显式操作递增 generation，恢复 GET 核验生命周期、操作 epoch 和 id；轮询 cleanup 同时置 disposed，响应核对当前 importId。旧 GET 已无法覆盖取消/新建。`poe2-character-import.test.tsx:86–109` 使用 deferred 响应直接覆盖所报交错，并检查 onReady 与 storage。
- **R2 已关闭。** `WebPoe2.tsx:78–83,129,174`：初始化历史结果绑定 selectionEpoch，手动导入及 ready 成功装入后使旧列表失效。`web-poe2.test.tsx:88–103` 明确使历史快照后返回，并断言保留成功基线、第二步及当前构筑，同时没有重算/读取旧构筑任务。
- **R3 已关闭。** `Poe2CharacterImport.tsx:100–110,122,135–137,152`：废弃任务取消经 result 和 id/status 校验，失败保留 id 并提供恢复入口；生命周期隔离阻止旧账号续发取消和回写。`poe2-character-import.test.tsx:110–130` 覆盖 fallback/rejection 两种失败的恢复，以及账号切换后的迟到创建。
- **修复附带回归检查通过。** `Poe2CharacterImport.tsx:60–82` 将指纹计算绑定 auth 生命周期，操作 epoch 改变不打断命名空间准备；hash 迟到会保存当前 importId，避免恢复旧 id。`poe2-character-import.test.tsx:131–139` 检查只持久化当前 id。Web ready 加载期间创建/恢复/重复加载按钮禁用（`Poe2CharacterImport.tsx:148,152,169`）。
- **审查范围及验证证据：** 逐项对照 `.task5-fix1-baseline` 与当前两个组件、两个测试，读取 task5-report 的 round 1 结果；报告记录云端 red 14/20、修复后 25/25、typecheck/lint/H5 通过及两条体积告警。本复审没有重复执行测试、运行本地程序或改产品文件，只更新本报告。
- **Task6 仍需验证：** Candidate 服务/Cookie/真实浏览器及移动端三步流程；真实国服完整导入仍未验收。此 scoped pass 不改变这些证据边界。

## Spec Compliance

- ❌ Issues found：迟到结果守卫未覆盖同账号操作间的轮询/恢复竞态，ready 恢复可被初始化历史列表覆盖，切源后的迟到创建取消失败缺少反馈。见 R1–R3。
- ⚠️ 实际移动布局、Cookie/服务 E2E、完整三步浏览器交互仍交 Task6；本审查没有将组件测试或构建当作这些验收。真实国服完整导入也未获证明。

## Strengths

- `apps/mini-taro/src/web/Poe2CharacterImport.tsx:11–19,118–139`：两个来源独立校验并显式提交 provider；国际服 Copy PoB、用户确认及未核验来源关系均可见。国服缺口按类别计数、详情折叠并通过文本渲染。
- `apps/mini-taro/src/web/Poe2CharacterImport.tsx:47–72`：会话指纹使用 SHA256，sessionStorage 只写 importId；账号切换撤销旧 generation，未存 token、URL 或 PoB 原文。
- `apps/mini-taro/src/web/WebPoe2.tsx:166–187`：ready 校验 build/job 关联、成功状态及空 changes，读取已有结果，保留三步及官方项目/下载链接，没有重新提交基线。
- `server/app/poe2/tools.py:33–37,50–67`、`server/chickenbro_native_mcp.py:397–409,610–641`、`server/app/chickenbro/codex_adapter.py:219–222,530`：可信 game/capability、工具可见性和 principal owner 边界相符；新动作参数集合拒绝额外 owner，委派给共同 ImportApplication。

## Issues

### Critical

- 无。

### Important

- **R1 / P1 — 操作未使旧读取失效。** `apps/mini-taro/src/web/Poe2CharacterImport.tsx:65–68,74–80,88–103`。`run` 只读取 generation，轮询清理也只清 timer；已发出的 GET 仍可 accept。触发：轮询读到旧 queued 响应但网络延迟，取消先成功显示 cancelled，随后旧 GET 恢复 queued；若用户已创建同来源新任务，还会把 packet 和 sessionStorage 改回旧 importId。刷新恢复 GET 与用户新建同样可竞争，旧 ready 还可能调用 onReady 把用户带到旧构筑。为每次显式操作/恢复/轮询设置可失效请求序列或 action epoch，清理时撤销在途读取，并验证当前 importId。补一个受控 deferred GET 测试覆盖取消→新建→旧响应，以及恢复→新建→旧 ready。
- **R2 / P2 — 历史列表迟到覆盖 ready 恢复的选中构筑。** `apps/mini-taro/src/web/WebPoe2.tsx:80–82,166–172`。初始化 listBuilds 和角色恢复并行，二者共享同一账号 generation。触发：onReady 已装入真实 build/job 并进入第二步后，较早的 listBuilds 返回旧快照，直接替换 builds 和 selected；可能切到其他构筑，或 selected 变空使第二步没有内容，随后 listJobs 也切换/清除已恢复基线。初始化结果应保留期间显式选中的构筑并合并列表，或在 onReady 成功后使该初始化读取失效。增加 listBuilds deferred、ready 先完成的定向测试。
- **R3 / P2 — 切源时迟到创建的取消失败被吞掉且 importId 丢失。** `apps/mini-taro/src/web/Poe2CharacterImport.tsx:94–99`。创建请求仍在途时切换来源，旧创建随后返回 pending，会发 cancelImport，但没有经 result 校验，并且异常完全忽略；旧 id 也未进入可恢复状态。触发网络取消失败或 structured-problem fallback 时，旧后台任务继续，用户看不到失败，也拿不到旧任务 id 去恢复/取消，与明确取消反馈要求不符。保留废弃任务 id 的可恢复状态，检查取消结果并在仍为该账号时展示可操作反馈；账号变化仍不得续发旧账号操作。新增迟到 create + cancel fallback/rejection 的测试。

### Minor

- `docs/plans/2026-09-20-poe2-link-task5-report.md` 的构建结果记录 2 条 webpack 体积告警。当前报告明确记录，尚不能从本 Task 增量判断是否新增；由 Task6 结合实际 Candidate 加载检查，无须为此重复构建。

## Checks and scope

- 审查输入为 Task5 brief/report 与精确 baseline 增量 diff；没有运行测试、构建或本地程序，没有改产品文件、索引或分支，仅写本报告。
- 为具体跨层风险做了定向补读：预览键是否与 mapper/worker 一致（`server/app/poe2/imports/mapping.py:89–94`、`worker.py:34–35`）；MCP dispatch 与 adapter game 是否共同阻止 WoW 调用（`server/chickenbro_native_mcp.py:610–641`、`codex_adapter.py:530`）；gateway capability 的签发/撤销是否继续约束新动作（`tools.py:33–50`）。未发现这些边界新增问题。
- 为 R2 补读 diff 截断的 WebPoe2 初始化及 selected/listJobs effect（`WebPoe2.tsx:74–93`）。上述竞态可由代码时序确定，已有测试均即时返回这些请求，未覆盖所列交错；没有重复现有测试。

## Assessment

**Task quality: Needs fixes.**

来源语义、隐私存储与 Chat 权限接线符合本 Task 方向；R1–R3 影响刷新恢复、取消和已完成基线的可信展示，应修复后再交 Task6 集成验收。
