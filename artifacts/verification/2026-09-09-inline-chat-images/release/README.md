# Web 输入框图片发布验证 · 2026-09-09

用户确认预览后明确授权“提交，合入，发布”。功能源码 `4a519c4c1882db9085fe5b4ad345cc1c062e522d` 已合入并推送 main。Web 包以该提交构建；之后的证据提交不改变发布源码。

278 项前端、62 项控制面、TypeScript、lint 通过；H5 构建通过，保留 2 个包体积警告。采用本地源码审查。本次只发布 Web，生产后端仍为 `a89dc8a334d892a826e80fcb2e1decdeadbdee47`，不迁移生产数据库。

隔离数据库 `chickenbro_inline_candidate_20260909` 使用当前生产后端及独立 API/worker，完成实际 API→模型验证。公网发布后使用实际 HTTPS 页面重复验证：原生 Meta+V 粘贴、DataTransfer 拖图、原生选图、框内三图、实际模型抄出随机八位码、刷新历史、图片私有读取和另一用户拒绝访问。使用两组独立的合成 QQ 身份，未重新验收 QQ OAuth 登录。见 candidate.json、production.json 及对应截图。

manifest.json 绑定构建源码、压缩包与 13 个文件 SHA。publish.py 先校验并解包到独立目录，再原子切换 Web 符号链接；切换失败自动退回 previousWeb。promotion.json 与 public-verification.json 证明全部 13 个公网文件匹配、readiness ready、后端指针未变。旧 Web 目录保留作为回滚目标。

验证结束后仅归档本次合成身份的会话、撤销其会话令牌并禁用身份，图片遵循现有归档保留策略；专用候选服务停止，候选数据库保留。cleanup JSON 还验证了实际生成会话的跨账号隔离与无活动运行。首次清理脚本因数据库返回 tuple 而非 dict 失败，发生在任何写入前；修正后完成。测试凭据不进入交付物。

主检出原有 4 个未提交文档和 56 个未跟踪文件已备份并保留，未覆盖其他任务；备份 stash 保留。未执行微信小程序构建或发布。
