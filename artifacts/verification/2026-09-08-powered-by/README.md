# Web 右下角署名

用户已验收本地预览并授权提交、合入、发布。最终范围为桌面 Web 登录页与业务页右下角显示 `Powered By Lighthouse&Codex`；不占独立行，980px 及以下隐藏。小程序取消本轮署名，与 1.0.4 源码一致，无需重新上传。

## 验证与边界

- 独立源码复核：无发现。CodeRabbit CLI 和连接工具均不可用，未安装新依赖。
- 前端 335 项、typecheck、lint 通过；H5/weapp 构建通过，保留既有包体积告警。
- Chrome 本地预览确认右下角文字与正文融为一体，无独立底栏。生成的 Mini JavaScript 已确认不含署名。
- 本任务只更新 Web 静态文件，不改 API、数据库和 SimC runtime。
- 提交后以 `manifest.json` 绑定源码提交与构建文件；发布结果和回滚目录记录于 `publish.json`。
- 本目录旧 `preview.png` 是被用户否决的初版，`preview-revised.png` 是移除 Mini 署名后的预览；均不作为正式微信发布证据。
