# Task 5 — 两个来源入口、统一结果及 Chat

工作区 `/Users/boyuan/Documents/wow_mini_program/.worktrees/poe2-20260918`。用户已批准直接实施和子代理审查。阅读 design 中用户路径以及 Task 1/2/3/4 报告和实际合同；本任务负责 Web/API client/Chat，不更改已审查的后端状态机，发现问题发给 root。

## 产品与交付

- 保留导入 → 调整与对比 → 查看详情三步。第一步清晰展示国服 WeGame、国际服 poe.ninja 两个独立来源入口；分别输入/校验链接，发 createImport 显式 provider，不静默切换。
- 给每个入口简洁操作说明和格式示例，示例不要默认填充真实用户角色。WeGame 说明复制公开分享；ninja 说明还需打开角色页复制 PoB 码。已提供 PoB/XML/教学示例折叠为次级入口，保留 PoB 2 官方项目和下载链接。
- 持久化 importId，刷新可恢复；存储与登录身份绑定，不把原始分享链接、码、角色快照放持久客户端缓存。轮询/异步操作加 generation/abort 守卫，旧来源/旧账号迟到结果不更新当前UI。
- 角色预览：来源、赛季、等级、职业、读取时间/来源更新时间、完整性。缺口逐项显示为可读文字，尤其珠宝缺失必须明确保留；不把 raw JSON 渲染用户。
- needs_input 显示补充 PoB 码/XML 的操作和用户确认：代码由用户提供，系统未验证其与链接同角色。国际服不声称已自动读取角色。
- ready 仅接收合法 buildId + baselineJobId，加载其真实成功结果并进入第二步，不重复提交 baseline。取消/失败/重试有明确反馈；按钮禁用时说明原因；状态区域可读屏，检查手机布局。

## 文件与接口

新增 `apps/mini-taro/src/web/Poe2CharacterImport.tsx` 和对应测试；修改 WebPoe2.tsx/module.scss、packages/api-client/src/poe2.ts、新增 API client 导入合同测试并加入正常 vitest.config.ts include。

组件接口 `Poe2CharacterImport({auth,onReady})`，onReady(buildId,baselineJobId)。API createImport/getImport/supplyImportSource/retryImport/cancelImport 严格响应校验，沿用现有 transport/web CSRF。

身份恢复约束：现有 ClientAuthContext 只有kind/web和csrfToken，MeResponse不提供userId。不要为UI恢复新增可伪造owner参数。可用同会话CSRF的WebCrypto SHA256指纹作为sessionStorage命名空间，仅读写importId，不持久化原始token/URL/角色资料；auth改变时取消旧异步、切换命名空间。WebCrypto或storage不可用时降级不自动恢复并说明可重试，不回退共用账号缓存。服务器GET仍是最终owner检查。该方式恢复同登录会话刷新，新登录不跨会话自动恢复；报告明确范围。

检查本流程相关WebPoe2在auth改变时的来源文本/文件读取迟到回调与onReady；应清空旧账号输入，不能让旧file.text()或fetch结果落到新账号表单。这属于上述A/B迟到结果要求，不需要扩大到其他Web域。

国服真实样本可能有大量issues。按受控code归纳“珠宝缺失/技能资料不足/装备词缀尚未支持/版本或任务信息待确认”，展示数量和可展开的位置详情，避免几百行相同提示淹没补充入口。不要假称只有珠宝缺项；Task4report明确有限覆盖和完整国服未验收。不要对原始path中的任意字符串做HTML；所有渲染走文本。

Chat 路径为 `server/app/poe2/tools.py`、`server/chickenbro_native_mcp.py`、`server/app/chickenbro/agent/POE2.md`、`agent/skills/poe2-build-analysis.md`，以及 `server/app/chickenbro/worker.py` 工具网关装配。新增本人角色导入创建/读取/补充/重试/取消工具可按实际用户流程最小实现；后端动作通过 ImportApplication，不能绕过 owner 或信任模型传 owner。加载固定 game=poe2，魔兽上下文不可见/调用。

Task 2 会接 main.py/dependencies.py 导入应用；Chat 使用同一 repo/app，避免另建状态机。既有 `poe2_import` 的分享码/XML 行为兼容；新角色链接使用明确的新工具，更新 codex_adapter.py 相关工具允许策略和测试。长 PoB 超过 Chat 4000 字引导到构筑页，不要求用户拆分消息。

## 验证

所有执行/测试/构建/浏览器/依赖只在云端 `ssh wow-lighthouse`，source=`/opt/chickenbro-candidates/poe2-20260918/source`，node=`.../runtime/node-v22.19.0-linux-x64/bin/node`，python=`/opt/chickenbro-runtime/bin/python`。本地仅读写文件、git检查、传输。仅上传所拥有文件，不覆盖别的任务。禁止提交推送合入、生产切换。不要派子代理；不要重启/部署服务，交 root。

组件测试沿用项目 ReactDOM act 模式与现有测试依赖，无须新增测试库。覆盖两入口来源误配、ninja指导、WeGame阶段缺口、ready不重算、取消/刷新恢复、A迟到不污染B。API合同和Chat owner/game合同定向测试；正常 Vitest 收录。云端类型检查、相关 lint、受影响 H5 build。报告记录首次失败和修复证据、确切命令结果及所有文件。

报告 `docs/plans/2026-09-20-poe2-link-task5-report.md`。独立 task review 由 root 调度，之后 Candidate 集成和真实浏览器验收为 Task 6。
