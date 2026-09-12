# Chickenbro 路线图

## 已完成

- 鸡哥按需流程已发布（`2294cb95`）：核心规则缩小74%，四类流程受控按需读取，统一跨轮预算并绑定调用证据。最终后端801通过/1平台跳过，5条Candidate与3条线上通过；复杂问题存在额外读取往返，不宣称普遍提速。[发布记录](../artifacts/verification/2026-09-12-agent-skills/README.md)。

- Web 会话切换修复已发布（`0f8b3ce9`）：删除两处研究额度说明，返回进行中的会话恢复等待、进度和流式回复，结束后可继续提问。279 项本地测试、实际构建与公网页面隔离交互验证通过，13 个公网文件匹配。[发布记录](../artifacts/verification/2026-09-11-chat-return-state/README.md)。

- 通用研究证据与语义优化已发布（`b406fc915`）：独立窗口、伤害/施法/资源摘要复用，长对话目标与修正保留，统一研究额度及有限模拟声明校验；8条Candidate与2条线上验证通过，固定20题集合已建立但未全跑。[发布证据](../artifacts/verification/2026-09-11-research-generalization/README.md)。

- 有限研究完整解答已发布（`e61595bf2`）：正常追问可继续、历史属性与治疗复用、治疗聚合及正确计费上线；Candidate属性与线上三人日志原题通过，实际token已可审计。保留范围上限、失败与未覆盖项。[发布证据](../artifacts/verification/2026-09-11-research-completion/README.md)。

- 光塔持续时间有限实验完成：0.1/0.5/1及无额外精通共4组；站圈收益影响约0.5%，去掉收益仍未反转限定组合排名。乘数不是整场站圈率，真实站位仍未知，保留现有默认值，不改生产。[证据](../artifacts/verification/2026-09-11-lightspire-sensitivity/README.md)。

- 饰品机制第一批：固定元素萨298羽毛＋黄眼睛，取消羽毛属性惩罚后DPS点估计+0.13%，未推翻历史组合排名；仅此条件实验完成，真实概率及当前游戏版本差异仍未验证。[证据](../artifacts/verification/2026-09-11-trinket-mechanism/README.md)。

- 跨轮预算、原生策略拒绝终态、G10原题俗称自动检索及引擎诊断投影已联合发布（运行源码 `22c681f99`）；0009迁移、API/Worker与Web、四项真实语义、13份公网文件及运行观察通过。旧失败与消费保留，未做回滚演练、未声明手工验收。[最终分级记录](plans/2026-09-11-remaining-issues-status.md#最终联合发布证据2026-09-11)。

- G8 顺序原题、G9 两条预算解释已在已上线源码回放通过；仅完成该有限原题范围，不冒称新五类模型矩阵或新生产发布。[回放记录](../artifacts/verification/2026-09-11-g12-final-window/remaining-tests/README.md)。
- G11 有限附魔清单名称、覆盖与版本整理已通过前后对照及线上验收（`6c2b36b2e`）；全制造品质仍未全面覆盖。[证据](../artifacts/verification/2026-09-10-native-search/quality-README.md)。

- 当前装备完整名称查询修复已正式发布（运行树同`af244e22b`，发布标识`60028b833`）；修正验收脚本后，线上武器/饰品两题、通用业务、账号隔离、Web13文件及运行观察通过，G13已released。[记录](../artifacts/verification/2026-09-11-g12-final-window/remaining-tests/release-rerun/README.md)。

- 戒指附魔对照与任务完成读取竞争修复已发布（`95569fc01`）；按用户授权暂缓一条无工具调用、无回答的模型失败，保留实际9/10结果。隔离及线上两条真实对照、通用业务与Web核验通过。[发布记录](../artifacts/verification/2026-09-11-g12-final-window/release/README.md)。

- Chat 原生实时搜索已恢复上线（`1c7caa159`）：隔离和线上均验证真实搜索、页面读取与资料取得，图片/SimC/权限及 Web 核验通过。[记录](../artifacts/verification/2026-09-10-native-search/README.md#本轮线上结果)。

- 自定义施法 APL 与玩家术语先检索：`c408a30e6` 已合入推送并发布；隔离与公网真实相反顺序、Chat 先检索、第二账号隔离及 Web 13 文件核对通过。见[发布记录](../artifacts/verification/2026-09-10-custom-apl/release/README.md)。

- [Chat 有界研究](plans/2026-09-10-bounded-research.md)：Top10、查询/实验预算及网页统一计量已提交推送并发布（`3f0c15d98`）；隔离图片/SimC/WCL、公网拒答/榜单/网页及Web14文件核验通过。[发布记录](../artifacts/verification/2026-09-10-bounded-research/release/README.md)。

- G7 日志施法归因修复已上线（`f1f0f0a0d`）：不把日志频次或同步事件直接当作按键习惯；两次完整Candidate及公网高分对照验收通过，保留失败与适用边界。[记录](../artifacts/verification/2026-09-10-badcase-g7/release/README.md)。

- [WCL 工具效率优化](plans/2026-09-10-wcl-tool-efficiency.md)：按需视图、单轮去重和有界窗口统计已合入推送并发布（`f95f6bbe2`）；隔离图片/Chat/SimC、隔离及公网 WCL 与账号隔离通过，Web 14 文件一致。复用 667 项后端与 63 项控制面测试，按用户要求停止扩样本。[发布证据](../artifacts/verification/2026-09-10-wcl-tool-efficiency/release/README.md)。

- [Badcase 复盘](plans/2026-09-08-badcase-workflow.md)：扫描、诊断、批准与条件发布闭环已落地，两条G6排行榜修复已正式发布；线上两题、Chat/SimC/owner及Web14文件验收通过。自动化00点执行成功、06点因额度失败；该记录中的G7待办后来已发布，其他反馈按当前分级状态追踪。[发布证据](../artifacts/verification/2026-09-09-badcase-workflow/production-final-release.json)。

- [运营后台](plans/2026-09-09-admin-ops.md)：QQ唯一管理员、只读用户/Chat/SimC数据、北京时间趋势；已发布并完成真实本人权限、非管理员拒绝、业务和SQL对账。[证据](../artifacts/verification/2026-09-09-admin-ops/README.md)。

- [SimC 场景实验](plans/2026-09-09-simc-scenario-experiments.md)：已合入推送并发布（`7ef8a5dfd`）；天赋节点/整套替换、同进度饰品候选、预检重跑和对照已通过隔离及公网真实模型验收。[发布证据](../artifacts/verification/2026-09-09-simc-scenario-experiments/release/README.md)。制造/特殊装备版本仍未全面覆盖。

- Web 是唯一产品客户端；QQ 网站授权登录已上线，用户本轮确认已顺利使用 QQ 登录。服务端内部账号拥有 Chat/SimC 历史，跨用户隔离，不自动绑定旧微信账号。
- Chat 支持流式回复、历史继续、归档、账号级单回复、不可修改的回答解决情况反馈、截图提问，以及持久化生成与独立 Worker。
- SimC 支持 Raider.IO 导入、参数设置、队列进度、报告、任务 ID 复制及对话中的换装重跑。WCL 用于战斗研究和历史资料；新角色导入不接受 WCL。
- Web 提供七种插画主题、独立 FAQ 和更新日志。当前源码和各次运行版本的证据见[项目状态](project-state.json)，不把一次发布的 SHA 当成所有运行面的统一身份。

- 输出与坦克全专精支持已发布，治疗明确拒绝；原始功能发布源码 `0649a2e858f5`；本轮清理发布延续该能力。全专精及公网验收见[发布记录](../artifacts/verification/2026-09-09-simc-all-specs/release/README.md)。

- [小程序清理](plans/2026-09-09-mini-retirement.md)：源码和 Web 已合入、推送及发布（`7adcdeffa`）；隔离及公网真实图片/SimC、CSRF、账号隔离和幂等验证通过；用户确认的 186 个仅微信账号及业务数据已从正式库删除，私有备份独立恢复、演练及保留记录核对通过。18 个 QQ 与 14 个无关联账号保留。公网 14 个 Web 文件与发布清单一致，旧代码/Web 版本保留用于回滚。

- 食物与精确属性短时实验已发布（`342039cab`）：复用引擎选项完成 50 智力/72 暴击的条件爆发对照，支持最短 20 秒及真实属性读回；后端、Web 和线上业务验收通过，不冒称完整首领阶段还原。[发布记录](../artifacts/verification/2026-09-11-g12-final-window/remaining-tests/food-release/README.md)。

- G10 饰品组合已完成三组有限模拟：本季321光柱＋毒液对上季289或虚铸298黄眼睛＋羽毛均领先；复用已上线工具，无新增产品代码或部署。保留装等及引擎机制假设，不称全装等结论。[对照记录](../artifacts/verification/2026-09-11-g12-final-window/remaining-tests/g10-comparison/README.md)。

## 正在推进

本轮 Web 会话切换修复已完成发布；用户手工验收未声明。

## 下一步

联合私有副本已接入现有 Badcase 调度，到期后按精确文件及哈希处置；最早北京时间 9 月 17 日 10:21，未提前删除。资料与外部输入按[收尾记录](../artifacts/verification/2026-09-11-project-closure/README.md)的恢复条件推进。

## 暂缓与待决策

- 制造/特殊装备真实版本fixture、附魔各品质效果、完整首领阶段及饰品机制实测仍需资料；当前诊断投影不补齐这些事实。历史原生失败2ed6根因仍未知，本轮新策略拒绝不能反推同因。跨轮预算不承诺原生网页的网关5页硬计量或跨独立研究的账号总额度。

- 暂缓新增新闻、装备库、天赋库、旧模拟器及插件 `/simc` 文本导入。
- COS 历史调查及相关审计/恢复跟进已于2026-09-11按用户决定关闭，不再作为待办推进。既有完整性及本地重建证据保留，历史匿名写入结论仍未知。[历史记录](../artifacts/security/2026-09-11-cos-audit-recovery/README.md)。

[架构](chickenbro-simc-architecture.md) · [验证矩阵](verification-matrix.md) · [生产 Runbook](chickenbro-simc-production-runbook.md) · [计划白名单](plans/README.md)

1.0 双端交付、小程序上传和早期迁移均属于[历史记录](roadmap-pre-mini-retirement.md)，不再存在当前微信审核或上传待办。
