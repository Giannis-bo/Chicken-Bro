> 2026-09-09 后续已正式发布并完成真实 QQ 登录和业务验证，见 [部署记录](deployment/README.md)。下文保留早前本地阶段证据。

# Web-only 与 QQ 登录重构验证

本任务在 `codex/qq-web-only` 独立工作树实现。旧微信账号及 Chat/SimC 数据保留，QQ 创建独立账号，本次不迁移或绑定历史。原主工作树中的其他任务改动未合入本分支。

## 当前证据

- 后端：451 项回归通过；84 项迁移与真实 PostgreSQL 测试通过，无跳过。隔离 PostgreSQL 16 本地库验证新增迁移、QQ 身份唯一性、并发消费和账号隔离。
- 独立后端审查通过。修复了 callback 尾斜杠等路径变体可能记录授权参数的问题；应用拒绝这些变体并脱敏 access log。待部署 Nginx 片段对 callback 前缀关闭 access/error log。
- 运维脚本：当前运维入口 80 项 Node 和 11 项 Python 回归通过；旧重建流程仅作历史脚本安全回归，不作为 QQ 业务验收。
- Web：258 项测试、类型检查、lint、生产 H5 构建通过；当前控制面 62 项通过。旧 Mini 测试移出当前选择，文件清单与验证见 [frontend-report.md](frontend-report.md)。
- 生产 H5 的桌面及手机宽度预览通过：QQ 按钮/图标正常，503 可重试，取消与异常回调参数可恢复且保留路由；模拟 persisted pageshow 验证请求未返回时也能恢复操作、丢弃旧响应。未验证从真实 QQ 页面后退的 BFCache 行为。
- 最终整体验证详见 [local-verification.json](local-verification.json)，构建文件 SHA 见 [h5-manifest.json](h5-manifest.json)。最终独立审查通过，没有遗留可操作问题；仅批准本地实现。

[桌面登录页](login-desktop.png) · [手机登录页](login-mobile.png) · [未配置时的失败恢复](login-unavailable.png)

## 云端配置与真实验收边界

`/etc/chickenbro-qq.env` 已安全保存，root-owned、0600，只含服务端配置。未加载到现有服务、未重启、未应用迁移、未发布 Web/API。脱敏保存记录见 [cloud-secret.json](cloud-secret.json)，其中不含 AppKey。

正式回调为 `https://www.chickenbro.cloud/api/v2/auth/qq/callback`。QQ 后台登记值必须完全一致；测试和候选环境需分别登记固定回调。

用户提供的截图中网站应用仍为审核中。真实 QQ 授权、云端回调、登录后的真实 Chat/SimC 与第二账号隔离尚未验收。本地 fake-provider、UI 模拟响应、测试通过或配置存在都不证明真实 QQ 登录成功。

本次未推送、合并或切换生产，也未删除旧数据。Nginx 片段尚未针对真实配置运行语法验证；正式发布需在既有 TLS server 中接入并验证。继续发布前遵循当前 Runbook 与用户授权，不能复用历史无备份删除授权。
