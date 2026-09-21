# POE2 正式发布 · 2026-09-21

用户验收 Candidate 并明确授权发布后，已合并最新 main 的魔兽阶段模拟改动，推送 main，切换正式 API、Worker 和 Web。运行代码源为 `77cee1603`；后续收尾提交仅更新文档、验证脚本与测试清理，不改变运行代码。

正式入口：https://www.chickenbro.cloud/poe2 。数据库 `chickenbro_prod`；Candidate 的账号、构筑与对话未迁入生产。

## 发布内容

- WoW/POE2 独立游戏会话及工具；POE2 简体术语、构筑分析与制作顾问。
- 构筑页导入／对比两步，导入即展示角色、属性、技能与辅助卡片、中文天赋树和升华；构筑 ID 复制、列表信息与删除。
- 基线和相同候选优先复用；Chat 每轮 12 次新计算、每研究 60 个不同候选／120 次执行，30 候选软提醒。读取、对比与复用不扣额度，Web 手动计算不使用 Chat 研究额度。
- 按用户决定，不增加 Agent 删除／重命名工具。

## 身份与恢复

- Backend：`/opt/chickenbro-releases/poe2-77cee1603`。
- Web：`/var/www/chickenbro-web/releases/poe2-77cee1603`。
- PoB：`v0.23.1@7d6f530cbdab20389ff8bc6ba97a37ac27f74e41`，独立 `/opt/chickenbro-poe2-runtime/7d6f530c`。
- 正式 API/Worker 原环境逐项保留；仅新增 POE2 专用 drop-in，Lua 库变量仅传入 PoB 子进程。
- 私有恢复包：`/var/lib/chickenbro/releases/poe2-20260921`。数据库备份已独立恢复并应用新增迁移验证；保留旧 backend/Web 指针与精确文件清单。未执行正式回退演练。
- 迁移 0011–0014 均为增量。回退应用不删除 POE2 数据，也不以旧备份覆盖发布后数据。

## 云端验证

| 检查 | 结果 |
| --- | --- |
| TypeScript／正式 H5 构建 | 通过；构建有现有体积提示 |
| 前端测试 | 43 文件、342 项通过 |
| 后端 app 测试发现 | 911 项，85 项按专项环境条件跳过，其余通过 |
| 真实 PoB 引擎（正式独立运行目录） | 5 项通过 |
| 独立 PostgreSQL 构筑／导入／研究回归 | 37 项，2 项跳过，其余通过 |
| 正式 PoB 导入、Worker 计算、比较、树和导出 | 通过 |
| 正式真实 Chat | get → job_get → calculate → job_get → compare 均完成；回答生命变化 |
| 方案复用 | Chat 后仍只有基线与候选两个任务，无重复计算 |
| 账号隔离 | 第二账号读取／删除他人构筑、读取他人任务被拒绝；匿名访问拒绝 |
| 正式浏览器 | 真实导入、ID 剪贴板、树图集、删除后刷新、390px 无横向溢出，零页面异常 |
| 公开产物 | 18 个文件逐一 SHA-256 匹配 |
| 魔兽回归 | 正式 Raider.IO 导入和实际队列模拟成功，返回正数指标 |
| 发布后复查 | API、Worker、数据库及服务 readiness 正常 |

正式业务验证使用两个明确标记的专用合成验证账号，不冒用真实用户；验证会话已撤销。此轮没有重新进行真人 QQ OAuth 授权跳转验收。

测试记录位于云端 `/opt/chickenbro-candidates/poe2-20260918/release-*.log`。第一次 PostgreSQL 测试被 Candidate 数据库命名保护拒绝；之后发现测试残留排队任务，已在测试自身增加仅限该测试 owner/build 的收尾，并在新隔离库复验通过。首次正式鉴权验证因合成账号缺少身份关联而被拒绝，补齐专用验证身份后通过；生产鉴权规则没有改动。

安全回执和页面截图见 [evidence](evidence)。Cookie、环境密钥、数据库备份、原始构筑与完整对话只保留在云端私有目录，不提交仓库。
