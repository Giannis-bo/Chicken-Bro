# Badcase 工作流与 WCL 排行榜修复

状态（2026-09-10）：V11 完整24次 HTTP 对照通过，但额外4次 Candidate 均未满足全部标准：前十第1次因两处未被实际回执支持的报告代码引用触发校验，唯一一次修稿60秒超时，无终稿；其余3次只返回目录 unavailable、零研究，不能算业务成功。V11 未切换生产、没有新回滚，线上仍为基线 `03275ee5…`。V12 已预注册，配额95%阶段准入与紧凑引用修稿验证待做。G6 仍未完成，V9/V10生产失败与全部历史记录保留。

授权：用户要求落地扫描/诊断/条件发布工作流，并用其修复发布两条当前未解决反馈。本批直接授权立即发布；未来保持6小时扫描及18点条件发布，新组仍需人工批准。

最新证据：[V11 额外 Candidate 失败与诊断边界](candidate-v11-failure.json)、[V11 完整对照](generalization-v11-summary.json)、[V12 预注册](preregistration-v12.json)。[V10 正式失败、诊断边界及独立恢复](production-v10-failure-recovery.json)。[V10 完整对照](generalization-v10-summary.json)、[追加 Candidate](candidate-v10-summary.json)、[实际交付耗时](delivery-timing-v10-summary.json)及[防重复发布门禁](workflow-release-dedup-v10.json)。[V9 正式失败及恢复](production-v9-failure-recovery.json)、[V10 交付机制修复](delivery-design-v10.json)及[预注册](preregistration-v10.json)。[V9 完整 HTTP 对照](generalization-v9-summary.json)通过；[零点自动扫描](automation-scheduled-scan-v9.json)已实际执行，新增 0，不能据此声称既有反馈已解决。V8 的[模型层对照](generalization-v8-summary.json)通过，但[真实 HTTP 验收失败](candidate-v8-failure.json)，因此未发布。一次额外诊断重放未复现修稿错误，不替代失败结果。V9 修复已确认的批量响应超限整包丢失及索引/可见证据不一致，见[机制与测试](transport-design-v9.json)和[预注册](preregistration-v9.json)。两条 G6 继续验收，第三条 G7 待决策。下文为各阶段历史证据，早期通过不替代当前版本门禁。

## 已核验

正式库只读扫描找到2条负反馈，属于同一会话；本地私有工作流创建G6，绑定报告SHA及本次用户批准。再次扫描新增0。原始用户反馈不改写，私有原文0600保存7天；缺失工具/模型输入证据明确标记。

旧版真实模型按原问题上下文回放前十请求66秒完成，仍声称无榜单API，没有实际分析。官方GraphQL实测支持Encounter.characterRankings；当前缺少网关/MCP工具。原答案引用zone54为PTR，正式服zone53、partition12.1；首Boss正式榜可读100条而PTR为0。

新工具通用查询团本目录、版本分区、Boss、难度、职业/专精、地区和DPS/HPS榜，返回报告/fight链接、玩家/服务器身份、准确范围与有界分页。不会把网页403等同API不支持，榜单与分析覆盖分开。

真实模型首轮发现同时传zoneId/encounterId被不必要拒绝，已改为交叉校验；坏记录不丢掉整页，缺身份记录明确partial。测试先失败再修正。另一个Boss火法、国服、第二页真实查询通过；治疗样本有1条不满足身份条件，保留9条并报告partial。

## 发布门禁

本地扫描/批准/冻结/发布状态与SHA证据验证，云端精确manifest/锁/排空/API+Worker切换和回滚执行器分别测试。候选完整业务、公网真实答案、版本/恢复及Web哈希尚待完成，不能仅据测试/工具取数成功标为已处理。

## 固定标准的重复验证

[v1注册](preregistration.json)先固定各Boss取得请求前N排名、每Boss至少一个真实匹配样本及施法观察、诚实说明未分析的名次，480秒总时限与360秒WCL报告研究预算不变。v1前十两次均仅完成7/9 Boss，拒绝发布，完整24次轨迹的哈希/耗时/调用数见[v1清单](v1-trial-inventory.json)，独立审查见[判定](generalization-v1-review.json)。此前Mage/治疗/国服/第二页查询属于探索，不作为独立留出证据。

[v2注册](preregistration-v2.json)保留验收条件，调试前换为新的狂徒双Boss独立留出；通用提示仅调整跨组研究顺序为先覆盖再深入。不能将取得90/900个排名条目称为已分析全部90/900份日志；本批最低要求是全部Boss分别有真实抽样观察，更多样本及因果解释仍须额外证据。

扫描最新新增1条同机制反馈，独立记录G7/pending，不扩大G6批准范围。实际缺少泛化证据的冻结请求已被拒绝，见[工作流演练](workflow-exercise.json)。

模型实验只计来源网关调用与墙钟时间；未获得模型公共Web工具或供应商token/账单，相关成本为未知，不按0计算。原始回放/上下文保存在私有验证目录，不入Git；本目录只保留脱敏摘要、哈希和通用harness。

第二轮的6个输入样本（覆盖5类）（两个原题+变体+新独立留出+正常+权限）各做前后2次，共24次。候选12/12满足固定条件，基线原题/变体/留出8次均未完成取榜分析，正常/权限4次通过。逐次独立评审与SHA、同条件及耗时成本见[完整v2证据](generalization-v2.json)及[汇总](generalization-v2-summary.json)。v1失败未删除或重新命名为成功。此结果只证明本轮定义的机制、覆盖和边界，不证明所有职业/全部前N日志已穷尽分析。

Candidate完整业务验证已通过：两条原上下文HTTP回放分别410.56/261.29秒，逐Boss排名/日志和独立语义通过；图片、QQ授权地址/CSRF、真实SimC正DPS与provenance、owner隔离/幂等均通过，见[Candidate v2](candidate-v2-summary.json)。通用fixture初次端口检查失败发生在业务运行前，确认释放后重跑成功，失败未隐藏。尚未把这些Candidate证据当成正式公网验收。


## 发布执行与终稿缺陷拦截

首次实际冻结发布批次 `398da44b…` 在数据库预检失败，尚未停止服务或切换正式指针。原因是独立发布进程未把服务的 `PGPASSFILE` 显式传给连接器；已修复传递并增加真实 `SELECT 1` 预检。失败批次及其源码禁止盲目重试，原记录保留。期间另一个已授权任务发布了运营后台，后续验证基底改为实际在线的 `03275ee5…`，并保留其 `8fba1535…` Web 制品。

新基底上的第三轮24次模型实验中，Candidate 12/12满足固定标准，见 [v3模型汇总](generalization-release-v3-summary.json)。但是随后独立HTTP验收的前十回答出现一个虚构报告链接和一个空白Boss观察；取得了工具证据不能替代正确终稿，Candidate门禁判定失败，`007074a8…` 未发往生产，见 [v3失败证据](candidate-v3-failure.json)。前百回答独立语义通过，不能抵消前十失败。

正在增加通用终稿引用校验：按本次实际工具回执核对报告、fight和actor，有限证据索引供一次无工具修正，正文通过后才外发；修正与原执行共享截止时间。它不替代独立语义评审，不承诺识别所有自然语言错误。[v4注册](preregistration-v4.json)在新实验前固定新的独立留出，其余480秒/360秒预算、重复次数及全部验收条件保持不变。原始两条反馈的不可变 `resolved=false` 历史不被改写。

首次真实无工具修稿设计探针在55.02秒截止时失败，未泄漏坏稿，见 [修稿失败证据](repair-design-d7a3e1f06-failed.json)。该设计样本不计独立留出成功；后续仅降低修稿阶段的推理开销，主研究模型、原问题和480秒总预算保持不变。

低推理强度的设计探针仍超时。仪表化确认启动不到1秒、6.107秒开始正文，55秒截止时仍在输出（3,027字符），故瓶颈是整稿重发。下一步改为严格有限替换块并在服务端复核完整答案，继续保持一次修稿与原预算；这不是降低语义验收条件。

严格补丁修稿的真实设计探针已在新源码 `3215b3f7…` 上12.18秒通过：单次进程、375字符补丁、无工具调用和业务能力环境，修正后完整引用校验通过，见 [设计探针](repair-design-3215b3f79.json)。此前失败记录全部保留；设计探针不能替代原题/变体/独立留出重复实验或公网验收。

[V4失败](candidate-v4-failure.json)：original10第二次虽然完成90条排名和全部9组研究，却将已读事件的先后写反，analysis失败。新[V5注册](preregistration-v5.json)先固定新的独立留出和原验收阈值，再补充通用时间戳/目标证据规则；V4完整24次前后回执与逐项判词已保留，汇总见[V4完整失败实验](generalization-v4-failed-summary.json)；Candidate 11份通过、1份analysis失败，不满足固定阈值，不能发布。后续HTTP只追加该失败批次的证据。

[V5失败](candidate-v5-failure.json)：首次前十因一份正确范围日志的OAuth provider错误未恢复而只有8/9组实际分析，不能发布。另一前十及两个前百通过不抵消失败；模型回执继续完整保留，后续未启动HTTP/general取消，避免在已失败候选上消耗额外验证。[V6注册](preregistration-v6.json)先于token可靠性和覆盖摘要修复固定，仍要求同预算、全部标准两次均通过。
