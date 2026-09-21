# 魔兽 Chat 秒失败修复 · 2026-09-21

已发布并验证。修复源码 `9ef8a187d`，正式 backend `/opt/chickenbro-releases/wow-chat-context-20260921`；只替换 `server/app/chickenbro/codex_adapter.py`，无数据库迁移。Web 内容与上一版一致，15 个公开文件哈希逐一匹配。

## 原因与修复

20:17 的四次魔兽 Chat 请求在模型启动前失败。双游戏适配器创建 `ChatToolContext`，但魔兽网关严格要求 `SimulationToolContext`；类型检查抛出的异常被转换为 `CODEX_UNAVAILABLE`，页面只显示“本次回答未完成”。现在在魔兽网关边界将服务端 principal、conversation_id、run_id 转为原合同，保留身份校验和游戏分支。

原测试使用不检查类型的网关替身，未覆盖此集成错误。新增回归用真实 SimulationToolGateway 检查模型启动、账号/会话/run 绑定和结束后撤销 capability；修复前云端复现相同失败，修复后通过。

## 新鲜验证

- 云端正式 Python 环境：adapter、simulation tools、POE2 chat isolation、research grounding 四模块，共 102 项通过。初次系统 Python 运行因缺少 FastAPI 有一个模块加载错误；改用 `/opt/chickenbro-runtime/bin/python` 后全部通过。
- 隔离云端目录：真实模型经过 RegisteredGateway 与 SimulationToolGateway 完成回答并撤销 capability。此项不提交模拟。
- 正式公网、专用合成验证账号：导入 Giannis 快照，真实 Chat 完成 `simc.preview → simc.submit → simc.get`，35.4 秒完成并持久化回答。
- 任务 `4ff32b85-14d6-4cb9-a5d3-4168834f6c7b` 成功，工具结果 DPS `183638.27595692052`，回答 `183,638.28`，任务 ID 一致。
- 第二验证账号读取对话与任务均为 404。验证会话已撤销。
- 未重放用户失败请求；用户可在原会话继续。此轮不声称真人 QQ 登录或用户手工验收。

安全回执见 [live.json](live.json)、[candidate.json](candidate.json)、[release.json](release.json)。真实对话与会话凭据仅在云端私有目录。

## 恢复

旧 backend 与 Web 保留并固定逐文件清单，私有恢复包 `/var/lib/chickenbro/releases/wow-chat-context-20260921`。发布执行器在锁内检查身份、环境摘要、文件清单和在途任务；排空后切换 API/Worker，环境摘要保持一致。准备了精确回退，未执行正式回退演练。
