# 鸡哥直接结论表达

用户于 2026-09-13 授权测试、验收通过后提交、合入并发布。当前状态：最终 Candidate 和独立修正路径验收通过，准备发布。

## 改动

核心规则禁止在句尾、段尾、总结中追加无关免责及预防性反驳，包括同义改写；证据检查用于形成结论，不逐条输出否定归因。WCL 流程补充责任归因、药水建议和伤害对比的具体表达规则。影响建议的条件和用户直接追问的未知仍如实回答。

运行变更为两份 Markdown 与适配器中的答案修正提示词，无工具、身份、预算、模型配置、数据库、引擎和 Web 改动。发布包保持核心规则、四份流程、读取器、MCP 及适配器同版。

## 测试与语义证据

- [Linux 后端](backend.log)：802 项，801 通过、1 项 Windows 专用跳过。Windows 的两项管道错误在 Linux 均通过。
- [控制面](control.log)：真实 Git 工作区 63 项通过。初次在无 `.git` 的云端归档执行有三项环境失败；改在本地执行后发现计划缺少保留规则，补齐后通过。
- [固定用例](cases.json)：死亡复盘、药水时机、伤害对比、直接追问未知、影响建议的模拟条件、完整复盘；另读取真实已完成 SimC 结果。不查询外部 WCL、不提交新模拟。
- [旧规则对照](direct-conclusions-baseline.json)：相同药水问题，答案追加“不能保证提前喝药一定存活，也不能认定7层是走位失误”。
- [诊断轮](direct-conclusions-diagnostic.json)：新规则直接给药水前移结论，无上述尾句；真实 SimC DPS 为159166.78869662393，答案159166.79。
- [失败一](direct-conclusions-candidate-attempt1.json)、[失败二](direct-conclusions-candidate-attempt2.json)：药水用例出现 `CODEX_OUTPUT_INVALID`；Worker 定位到原生协议重复 final 开始事件检查。临时诊断轮和旧规则对照均成功，触发原因尚未确定，不宣称修复协议问题。临时诊断仅用于 Candidate，已恢复原文件，不进入发布。
- [修正器调整前完整用例](direct-conclusions-candidate-final.json)：7条请求业务成功，但模拟条件用例经独立修正提示词后追加了无关独立验证声明，语义验收未通过。由此同步收紧 `_repair_answer` 提示词，保留证据验证器和最小替换协议；新一轮完整验收单列。
- [修正器调整后的第一轮](direct-conclusions-candidate-accepted.json)对比题仍出现“不能仅凭321对323确定升级收益”，用户并未询问升级收益，判定该轮语义未通过（文件名为当时运行标签，不代表验收结论）。核心规则进一步明确：建议写完即止；条件差异写成比较行动，不延伸到未问的收益后再否定。
- [最终 Candidate](direct-conclusions-candidate-v3.json)：7条全部成功。六个表达用例逐句审阅通过；未知归因与三目标适用条件直接回应问题，其他建议无旁支免责。真实 SimC 结果159166.78869662393与回答159166.79匹配。QQ授权URL、CSRF、私有图片、第二账号Chat/SimC隔离、SSE与幂等重放通过。
- [独立真实修正路径](direct-conclusions-repair.json)：以真实 `SIMULATION_BENEFIT_UNSUPPORTED` 拒绝的草稿调用修正器，移除无依据提升结论，直接指出三目标对照这个必要条件；再次通过原验证器。该路径禁用外部工具。初次测试构造未包含 simulation 证据键，入口断言拒绝，修正测试输入后执行真实模型。

自动化与代理输出审阅作为本轮验收依据；未冒称用户交互QQ登录、手工Web验收或完整外部WCL研究。

真实模型结果按 run ID 绑定流程哈希，原始私有记录保留在 root/0700 `/var/lib/chickenbro-direct-conclusions-20260913/`。公开证据只导出回答、运行状态、用量、流程摘要和业务检查，不导出会话令牌、用户或原始工具数据。

## 发布与恢复

待最终验收通过后，以新提交绑定精确 overlay；空闲门禁切换 API/Worker，保留旧后端与 Web。使用本批私有 `deploy.py manifest.json rollback` 恢复旧指针后重新核验业务，不覆盖数据库。线上业务、运行清单和公网 Web 哈希另行记录。
