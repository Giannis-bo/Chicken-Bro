# Web 会话返回状态修复

用户于 2026-09-11 要求删除研究额度文案，并修复 A 会话回复时切走再返回后状态消失、无法继续对话的问题。

## 实现与根因

- 基于 `40b5e22be64121bf976c90089bd702ff48e35052` 的本地未提交修改；源码及构建文件 SHA-256 见 `identity.json`。
- 原实现把流事件绑定到页面导航代次；切换后只保留连接和终态历史刷新，丢弃期间进度。返回只读消息历史，未恢复活动回复。
- 按会话保存运行中的回复、序列与身份、文字及进度；返回时重新关联原连接。后台内容不投影到另一会话。完成和失败仍以服务端历史收敛，释放发送状态。
- 对尚未进入服务端历史的文字/图片保留发送中展示；已入库消息不重复展示。
- 删除聊天区与输入框下的研究额度说明。服务端研究预算、账号单回复限制及身份合同不变。

## 本地验证

- 新增 A→B→A 成功/失败回归先失败：预期 sending 与已累积进度，实际 ready 与空进度；修复后通过。
- 相关模型与真实 React 页面交互测试 61 项通过，包含重复切换、等待提示、后台进度隔离、完成后按钮恢复、图片发送、B 被拒后返回 A 及恢复连接中断。
- 全量前端/共享包测试：32 文件、279 项通过。
- TypeScript、全量 lint、最终修改文件 lint、`git diff --check` 通过。
- `npm run build:h5` 成功；Webpack 报资源体积建议警告（app.js、吉祥物图片及入口体积）。
- 补充控制面检查：14/15 通过。文档链接检查失败于 runbook 引用缺失的 `artifacts/verification/2026-09-09-cloud-codex-cleanup/report.json`。HEAD 已含该链接且 Git tree 无目标；本轮未修改 runbook 或该测试，保留此原有失败。

## 验证边界

首轮验证为本地受控流事件和页面交互。用户随后明确授权“直接发布”。发布前使用本机 Edge 对实际 Web 构建产物验证六项行为，通过结果见 `candidate-browser.json`；API 与流事件完全隔离，未调用真实模型或写入生产数据。未改变完整页面刷新后的服务端执行恢复合同。线上发布结果将在本目录单独记录，不将自动化验证视为用户手工验收。

## 已发布

源码 `0f8b3ce9da11012e1afdcaaa5675d243ae0f8d67` 已合入并推送 main。Web current 已原子切至 `/var/www/chickenbro-web/releases/chat-return-0f8b3ce9da11012e1afdcaaa5675d243ae0f8d67`。后端保持 `badcase-b406fc9155a03edba9e95912713606736fb2a1bd`，API/Worker 未重启，数据库、环境及 SimC runtime 未改动。

发布前新目录 13 文件通过 SHA 和服务器隔离 loopback HTTP 读取；正式切换后 13 个公网文件全部与 `release-manifest.json` 匹配（`public-verification.json`）。Edge 加载实际公网产物，使用隔离 API/SSE fixture 验证额度提示移除、等待恢复、后台内容隔离、进度恢复、完成解锁和再次发送，六项通过（`live-browser.json`、`live-progress.png`）。真实 readiness 全部 ready，API/Worker active。未宣称真实 QQ 登录、真实模型/图片/SimC 新任务或第二账号业务验收；本批仅前端，未重放后端整套 Candidate。

恢复包 `/var/lib/chickenbro-chat-return-20260911/` 为 root/0700，包含 root/0600 `deploy-web.py`、静态归档、manifest 和 baseline 清单。旧目录 `research-22c681f99f457329f1b25570343b7f9be401201b` 完整保留、SHA 核验通过。仅当当前指针仍为本批且两版清单匹配时，可由 root 执行 `python3 /var/lib/chickenbro-chat-return-20260911/deploy-web.py rollback /var/lib/chickenbro-chat-return-20260911/release-manifest.json` 原子恢复旧 Web；不影响后端任务或新写入。未执行实际回切演练。
