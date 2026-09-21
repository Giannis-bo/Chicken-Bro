# SDD ledger — plan: docs/plans/2026-09-20-poe2-character-link-implementation.md

工作区：.worktrees/poe2-20260918；云端：/opt/chickenbro-candidates/poe2-20260918。保留所有未提交旧变更，不提交合入。
Ruling: 使用现有工作区和文档 ledger，不本地执行技能脚本；所有运行/测试云端，用户约束优先。
Ruling: 用户确认国服/国际服独立入口；POST imports 显式 provider，与 URL 来源不符拒绝。来源校验后共享状态机。
Ruling: 按用户选择由子代理实施及独立审查；计划完成状态不包含用户验收。新授权未要求设置新 goal，不创建 goal。
Ruling: 珠宝路径先做针对性公开页面核实；如能取得真实资料则更新缺口结论，不能依旧快照假设永久缺失。

| 任务/接口 | 预检 |
| --- | --- |
| 1 URL/类型 | provider 明确传入，规范化 URL 仅一次；自洽 |
| 2 application/存储 | 依赖 Task 1 SourceRef；租约完成必须与 attempt 一致；自洽 |
| 3 source/采集 | 与 2/4 共享净化 snapshot；网络隔离单独验证；自洽 |
| 4 mapping/bridge | 只对已完整映射资料调用 PoB；与 3 缺口状态一致；自洽 |
| 5 Web/Chat | 消费 Task 1/2 JSON，两个独立入口；不重复 baseline；自洽 |
| 6 部署/验收 | 消费 1–5，国服完整样本是单独门槛；自洽 |

Task 1: review — implementer /root/link_contract 完成 URL/provider 与响应合同；reviewer /root/review_link_contract 审查未提交 diff。Python 7/7、Vitest 5/5、全量 TS 类型检查均云端通过。
Task 2: pending
Task 3: pending
Task 4: pending
Task 5: pending
Task 6: pending

Task 1: fix round 1/5 — reviewer found missing Python full response invariant and TS provider coercion. Implementer /root/link_contract fixing with targeted cloud tests; dependent implementation waits for contract review.

Research: /root/mapping_research 正在检查国服字典与许可。root 珠宝复查已确认公开页空响应，详见 2026-09-20-poe2-jewels-recheck.md；可选补充问题已发用户，不阻塞独立任务。

Task 1: fix round 1/5 (2 addressed, 0 open). Python 10/10，正常 Vitest 两文件 5/5，全量 tsc 通过；独立复审 PASS。
Task 1: complete (uncommitted worktree, review clean)。
Task 2: implementing — /root/import_pipeline，task2 brief，root 协調；存储/状态机/API/worker及真实 ninja 基线。
Research: mapping 与来源隔离探测完成，结论已纳入 Task 3/4 briefs。PoBR MIT 代码可参考，数据词典许可不等同代码；空珠宝没有新增数据源。独立公网 DNS 与内核私网拒绝已云端验证，实际 Chromium 采集仍由 Task 3 验证。

Task 2: review — /root/review_import_pipeline 审查 task2-review.diff。综合云端29/29，真实ninja基线 Life2813/ES962；成功snapshot保留调整后12 pass/1 live opt-in skip。0013 已在Candidate直接psql应用但尚未正式migration ledger登记，最终部署需登记。source/map/convert唯一定义见Task2report。
Task 2: fix round 1/5 — I1 已过期snapshot被source延期TTL复活；implementer修复行锁事务并补未先expire的回归。跨任务 collector净化和mapper public值/issue内容交Task3/4验证；真实Cookie/CSRF和服务装配交Task6验证。
Task 2: fix round 1/5 (1 addressed, 0 open). 云端新增红绿回归；13pass/1live opt-in skip，scoped复审spec compliant / quality approved。
Task 2: complete (uncommitted worktree, review clean)。
Task 3: implementing — /root/wegame_collector，专用collector unit可在Candidate部署验证，现有API/worker保持运行。
Ruling: collector增加server-owned owner_id关键字参数，来自已claim记录的user_id，由Task4装配更新worker调用和fake测试 — collector需要独立执行每owner并发1，URL本身不含可信owner — 若漏接会保守共享并发限额而影响吞吐，必须集成验证。
Deployment preparation: root核对Candidate数据库comment后运行正式apply_product_migrations，登记 `0013_poe2_character_imports`；expires_at默认7 days已读回。尚未重启API/worker。
Task 3: review — /root/review_wegame_collector 审查task3-review.diff；8JS+2Python通过，真实分享采集17装备/16技能/105主节点/6珠宝槽但珠宝missing；实际采集早于最后schema_gaps/Worker禁用/子孙回收加固，Task6需对最终整体版本做一次真实业务smoke。新collector unit已部署，API/worker未重启。
Task 3: fix round 1/5 — R1嵌套珠宝JSON敏感值收集顺序、R2父进程先死后detached子孙回收、R3最后等待窗口失败传播；原implementer一波修复并加3项定向测试。最终真实页面证据移交Task6，不在本轮重复请求。
Task 3: fix round 1/5 (3 addressed, 1 new open R4). 11JS+2Python通过；每任务subreaper修复原回收缺陷，新增stdout退出尾部可能截断。
Task 3: fix round 2/5 — R4监督器需读至EOF/排空大响应后完成；增加大快照正常退出定向测试，保持字节/期限上限。
Task 3: fix round 2/5 (R4 addressed, 0 open). 227303字符stdout定向红绿通过，父死/并行隔离/deadline回归通过；scoped复审spec compliant / quality approved。
Task 3: complete (uncommitted worktree, review clean; final real-page E2E explicitly assigned Task6)。
Task 4: implementing — /root/national_mapping；有限确定性词典、PoB原生bridge、owner参数和worker三端装配，真实国服完整样本缺口单列。
Task 4: review — /root/review_national_mapping。mapper+live bridge11/11，PG25pass/1旧ninja opt-in skip，最终单测12/12。两份合成fixture真实原生转换/计算/export往返通过；实际国服净化快照含嵌入物品共41件/181词缀/81宝石/153节点/49属性/15任务已全部计账，仍needs_input，不视为完整国服打通。
Task 4: fix round 1/5 — I1预览保留可用角色名/赛季/读取时间；I2非空珠宝及词缀逐项ledger/coverage。原implementer做两项最小修复，真实完整国服样本单列待验收。
Task 4: fix round 1/5 (2 addressed, 0 open). 新增两项红绿，mapper11/11；scoped复审工程spec compliant / quality approved。
Task 4: complete (uncommitted worktree, engineering review clean; real complete CN acceptance remains pending)。
Task 5: implementing — /root/character_import_ui；Web/API client/Chat及相关测试，root最终集成部署。
Task 5: review — /root/review_character_ui 审查精确Task5baseline增量。Vitest18/18、Python78/78、typecheck/lint通过；H5构建独立产物 task5-web-build，尚未发布或重启服务。
Task 5: fix round 1/5 — R1旧poll/restore响应覆盖显式动作；R2初始化listBuilds覆盖ready恢复；R3迟到create取消失败无反馈/恢复。原implementer一波修复并补deferred交错测试，重新独立构建，不发布。
Task 5: minor (deferred): 2条webpack体积警告保留；Task6真实页面加载检查，无需为既有警告另扩优化范围。
Task 5: fix round 1/5 (3 addressed, 0 open). scoped复审PASS/Approved；7项deferred回归加入，Vitest25/25、typecheck/lint及H5重构建通过。
Task 5: complete (uncommitted worktree, review clean)。
Task 6: implementing — /root/candidate_import_acceptance 负责真实API/云端浏览器验收；root同步server、重启Candidate API/worker及替换Candidate Web，3服务active。全部Web产物与公网身份另行核对。
Task 6: partial verified — 真实Cookie/CSRF、来源错配、owner隔离、幂等/取消；最终collector一次读取实际WeGame进入needs_input，预览及珠宝缺口真实展示，390px无横向溢出。未重复采集，原任务用于刷新/取消验收。
Final review: one fix wave — F1 ready交付后的恢复记录造成返回①再次跳②；Task6发现F2 ninja缺少打开原页链接。/root/character_import_ui 合并两项最小修复；/root/candidate_import_acceptance 暂停待新产物。现有Task6净化报告与截图保留。
Ruling: final review 的生产QQ/全量词典/历史全部回归/来源规范终局判断按既有授权和证据边界保留，不能由Candidate替代；工程完成与完整真实国服验收分别报告。
Final review: fix wave complete — F1/F2 addressed，唯一scoped复审PASS/Approved，无新增阻断。云端定向29项、typecheck/lint/H5通过；最终Web产物已精确替换Candidate目录，替换前版本保留。Task6后半浏览器继续。
Task 6: verified — 实际用户ninja链接+真实XML产生成功baseline，Life2813/ES962/Armour7284/Evasion14138；无重复POST jobs。返回①新建、原页链接刷新、详情导出、手动/示例、WoW、390px及B隔离/retry404通过。单条真实Chat绑定succeeded run，恰好一次poe2_character_get。最终公网15文件hash一致、生产路径及Nginx身份不变。净化证据已归档，待最终证据审阅收束。
Task 6: complete (uncommitted worktree, Candidate engineering review PASS)。最终独立证据审阅通过，3验收脚本与API/浏览器/Chat记录一致。源文件manifest已在最终测试脚本后刷新为 cc6dab6fc95098c6469d0eec8a638bbc119d04b88eacf84dd2a48040a3a85e60。
Delivery: Candidate等待用户体验验收；国服公开预览及缺口处理已验证，完整真实国服自动转换仍未完成。未提交/push/合入/生产切换，保留工作区与恢复材料，不删除计划或证据。
