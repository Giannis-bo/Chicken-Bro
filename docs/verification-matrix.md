# 验证矩阵

按变更影响选择验证，遵循当前 AGENTS.md。命令见[开发指南](development.md)，生产步骤见[Runbook](chickenbro-simc-production-runbook.md)，Badcase 另须满足[泛化门禁](plans/2026-09-08-badcase-workflow.md#通用修复与泛化验收必须满足)。

## 证据等级

| 等级 | 证明范围 |
| --- | --- |
| local_verified | 指定源码的本地合同、测试及受影响构建 |
| candidate_verified | 指定隔离环境的受影响业务与恢复准备 |
| live_verified | 指定生产身份的真实业务与制品核验 |
| user_accepted | 用户明确完成约定范围的实际验收 |
| recovery_verified | 恢复材料在隔离环境恢复并核对，或明确记录的业务回退验证 |

各等级独立记录，不能互相替代。记录实际 commit/build/runtime、条件、结果与未覆盖范围；skipped、partial、blocked、HTTP 200、服务运行及 SimC 退出码 0 均不能代替业务通过。备份可恢复与应用回退后业务恢复也分别说明。

## 按影响选择检查

| 影响 | 本地与隔离验证 | 真实环境验收 |
| --- | --- | --- |
| 文档/配置控制面 | 语法、链接、owner/保留规则与相关控制面检查；运行配置另验实际加载 | 仅影响运行配置时核对对应 runtime 与业务 |
| QQ/会话 | provider 校验、浏览器 state、时效/取消/重放/并发、Cookie/CSRF/Origin、Bearer 拒绝、真实 PostgreSQL 持久化 | 已登记 callback 的真实授权、取消重试、刷新/退出/401 恢复、第二账号隔离 |
| Chat/图片/反馈 | 幂等、账号单回复、SSE UTF-8/错误/结束/取消/超时、断连与 Worker 故障语义、图片 owner、反馈写入及历史读回 | 真实回答终态、历史、受影响工具、图片与账号隔离；不以工具调用完成代替答案正确 |
| 研究/工具 | 参数、预算、来源完整性、窗口/过滤、跨轮复用及注入边界；真实前后语义按任务预注册 | 当前条件下真实回答、工具回执与限制说明；不把有限样本扩称全场景 |
| SimC | 快照、预检、有效配置、幂等/队列/租约、结果读取与 owner；云端引擎语义 | 正指标、来源与引擎/输入身份、场景差异、对照条件；治疗拒绝及故障如实呈现 |
| POE2 Candidate | 严格 PoB 2 输入、展开限额、工具游戏隔离、owner/CSRF、幂等与租约终态、typed API 真实包 | 云端固定上游对照、正指标、装备/技能变化、导出再导入、两账号拒绝、真实 Chat 检索与工具、浏览器工作台；合成构筑不代替玩家验收 |
| POE2 天赋树 Candidate | owner 在引擎前校验、job/build 绑定、引擎版本拒绝、typed 几何合同、迟到响应、武器组筛选 | 实际构筑与 PoB/独立导出 XML 节点一致、方案退点与原始树区分、图集版本绑定、两账号/匿名拒绝、缩放拖拽搜索、升华节点详情及 390px 可读性；[证据](../artifacts/verification/2026-09-20-poe2-passive-tree/README.md) |
| POE2 角色链接 Candidate | 两入口 provider 与 URL 一致性、状态/attempt/租约 CAS、来源及补充幂等、owner隔离、净化/TTL、采集器内核私网拒绝、未知映射阻断 | [2026-09-20云端证据](../artifacts/verification/2026-09-20-poe2-character-import/README.md)：ninja 补充 PoB 的真实基线、WeGame 预览及缺珠宝提示、刷新/取消/两账号、三步和390px通过。完整国服样本及用户体验验收待完成；ready 必须绑定构筑和成功基线 |
| Web | 相关组件/API 合同、typecheck、lint、H5 build，实际导航和可交互状态 | 公网制品哈希、Web 路由与 QQ 登录入口 |
| 运营后台 | 唯一管理员、空配置/测试身份/普通用户拒绝；北京时间、366 天限制、去重、补零、分母、null 与异常结果的 PostgreSQL 验证 | 本人可读、第二账号 403、匿名 401、聚合 SQL 对账及公网制品 |
| 迁移/删除/恢复 | 独立测试库、版本兼容、精确依赖及活动引用、独立恢复核验 | 明确授权的清单、保留数据前后核对、失败恢复；不得覆盖生产新写入 |

## 数据库与执行边界

数据库测试使用独立 UTF8 测试库，按入口配置 `WOW_PG_TEST_DSN_V2` 或 `WOW_ADMIN_TEST_DSN`；不得指向生产或共享业务库。未配置造成跳过时单列，不能称数据库验证完成。反馈数据库用例为 `tests.app_chat_feedback_postgres_test`，旧请求未带 `includeFeedback` 时保持合同。

SimC 只在云端受控环境运行，不本地安装。数据处置使用本次授权和恢复材料。
