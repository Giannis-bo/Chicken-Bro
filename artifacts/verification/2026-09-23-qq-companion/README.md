# QQ 陪伴角色「炸鸡」

2026-09-23，用户授权当前会话顺序实现、完成后独立审查。开发与独立审查在隔离工作区 `codex/qq-companion` 完成；用户验收后进入[Git 交付与身份核对](closure/README.md)。

## 当前表情方案

用户修订已落实为优先复用当前群友的表情、缺少合适图片时专用网上搜索。固定原创表情库停用；当前 QQ 版本为 20260923-companion-quote-v5。[本次修订、验证、独立审查与发布记录](meme-revision.md)。用户已确认 @ 后文字与表情可见；主动互动与按需引用亦已获用户确认。

## 轻互动修复

用户反馈自带表情被当成附件后，已修复 QQ face 语义丢失并调整自然回应风格。[根因、模型实例和发布证据](natural-reply-fix.md)。36 项相关云端测试与独立复核通过，群内风格体验继续按实际消息验收。

## 首版已验证

- 云端 196 项相关 Python/PG 测试通过；隔离数据库，无跳过。一次 adapter 负例的 return_code=17 是预期测试输出。
- 本地 16 项项目状态/owner/保留清单控制面检查通过；`git diff --check` 通过。无客户端修改，未构建 Web。
- [独立代码审查](review.md)全部重要问题关闭。
- [真实社交模型](candidate-social.json)：同一群友称呼记忆、后续识别、只发表情、未 @ 主动接梗；四次调用没有工具事件。
- [真实专业流程](candidate-professional.json)：本人 Raider.IO 输入经 QQ owner/run scope 进入云端 SimC。开启/关闭嗜血各 100 次、60 秒单目标，DPS 263674.98 / 224469.18，结果绑定引擎版本。专业运行时同一成员的闲聊正常回复。该数据是隔离 Candidate 验证，不是正式群验收。
- 固定 NapCat 4.18.28 源码核实 `set_qq_profile`；资料 fresh `get_stranger_info` 与目标群名片回读均为“炸鸡”。`get_login_info` 的内存缓存仍显示旧名字；没有为刷新缓存重启 NapCat。
- [正式切换记录](release.json)：QQ 独立库完整备份，独立恢复后关键表行数逐表相等，随后应用 0016/0017/0018；只切 `/opt/chickenbro-qq-current` 和 QQ 两个服务。网站 API/Worker PID、源码及 Web 指针前后相同。

## 当前验收边界

正式 companion 模式已开启主动参与，用户确认 @ 后文字与表情可见。用户进一步确认主动文字和群友表情复用可见；记忆与 SimC 的群端体验待核对。[本批修复、80 项云端检查与发布恢复记录](activation/README.md)。

## 回退

可设置服务器可信配置 `proactiveEnabled=false` 并重启 QQ channel，保留观察和必答；严重问题停止 QQ 两服务，恢复 `release.json` 记录的旧代码指针、私有备份中的 `production.env` / `channel.json` / 两个 systemd 单元并启动。保留增量数据库表和数据，不执行降级删除。备份与模型凭据仍在服务器私有目录。

[首版源码 manifest](release-manifest.json)与[表情修订 manifest](meme-release-manifest.json)和[当前源码 manifest](optional-quote/release-manifest.json)分别绑定各次发布的源码；当前提交与线上文件通过清单逐项核对。

## 按需引用

社交消息默认直发，只在需要明确指代时引用。[本次修改、测试与发布](optional-quote/README.md)。
