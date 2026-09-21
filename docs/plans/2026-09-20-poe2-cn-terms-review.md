# POE2 国服简体默认术语独立审查

2026-09-20。结论：**PASS（本轮 spec、代码质量与静态集成审查）**。未发现需要阻断 Candidate 真实 Chat/UI 验证的问题。

审查对象为 `2026-09-20-poe2-cn-terms-review.diff` 所界定的增量及当前对应源文件，并对照本轮计划、实施报告、研究 Markdown/JSON。vitest 配置仅将新增 `poe2-terms.test.ts` 纳入本轮审查，不将既有 POE2 include 计成本轮变更。仅写入本审查文件；未运行本地产品程序、未重跑已有测试、未修改产品代码。

## 审查结果

- **默认语言与未知名称规则符合要求。** `server/app/chickenbro/agent/POE2.md:9` 覆盖职业、升华、技能、辅助、装备、天赋与机制，要求优先使用已核实对照，未知先查来源、仍缺则保留原文并标注待核实，明确有限覆盖。`server/app/chickenbro/agent/skills/poe2-build-analysis.md:6` 要求先读取实际技能组与参数，再作中文展示；计算参数保留英文/ID。WoW `server/app/chickenbro/agent/AGENTS.md:10` 只增加默认术语原则，未改变流程。
- **来源与共享数据一致。** 研究 JSON 与 `packages/domain/src/poe2-terms.zh-CN.json` 文件比较无差异，69 条有限事实映射由 TS 和 Python 共享。词表头部记录访问日期、社区资料来源与精确补丁未确定；没有把本次 PoE2DB `/cn/` 名称核查声明为全库或国服客户端逐条验证。
- **原技能状态保留。** `server/app/poe2/presentation.py:13` 从原 XML 的当前 activeSkillSet 提取组，保留组和 gem 全部属性，再附加 index/name，因此 level、quality、enabled、nameSpec 及已有 ID 没有被翻译替换。`presentation.py:27` 只附加展示上下文与 unknown，不改写 packet 的源字段或计算值。
- **账号边界及原输出保持。** `server/app/poe2/tools.py:82` 在原操作之后附加 presentation；get/export 的 XML 读取继续使用 capability 中的 principal 和原 buildId。构筑源、分享码、changes、计算 stats 及原操作权限分支未改变。
- **输入与展示分离。** `packages/domain/src/poe2-terms.ts:5` 按 kind 与英文精确匹配；`:10` 对中文仅接受唯一精确反查，未收录中文抛错，原英文保持可用。罗马阶级作为完整名称组成部分保留。`apps/mini-taro/src/web/WebPoe2.tsx:151` 将反查英文送入原 changes，点击处理捕获未知中文并显示错误，避免提交错误译名。
- **Web 默认中文与原始核对入口齐备。** `WebPoe2.tsx:178` 的职业/升华、`:208` 的槽位选项和 `:237` 的技能/辅助及常用配置走中文展示；槽位 option 的 value 仍为原英文。原技能、有效配置、节点及引擎提示保存在默认折叠的原始技术数据中。未识别术语保留原文定位；未解释的引擎提示显示待核对并指向原数据。

## 验证界限与后续

实施报告记录云端 typecheck、定向 lint、18 项 TS、76 项 Python 与 H5 构建通过；本审查核对了相应测试覆盖和实现，不重复执行或将报告转述为新的独立测试运行。

root 继续本轮已计划的真实 Chat/UI 验证：用户构筑的技能/辅助中文与阶级、当前启用状态回答、Web 默认中文和原始字段折叠、中文参数回传。业务验证结果需另行绑定实际 Candidate 运行身份。本审查不扩大为全游戏术语覆盖或生产发布验收。
