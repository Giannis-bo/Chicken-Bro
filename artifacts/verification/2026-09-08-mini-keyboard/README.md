# Mini 输入区与流式兼容修复

用户于 2026-09-08 在修复预览上确认“这次好了，提交、合入、部署”。

- 开启键盘原生避让，发送按钮等宽居中。
- 请求启动后清空草稿，重置原生编辑器并收起键盘，忽略旧输入事件。
- 无浏览器 TextDecoder 时使用支持跨块中文和表情的 UTF-8 解码；启动异常恢复为可重试状态。
- 先前仅修输入框未解决问题；不能将早期预览等同最终验收。
- 本地源码审查完成；CodeRabbit CLI/MCP 不可用，未安装依赖。
- 335 项前端测试已通过；类型、lint、双端构建通过（构建保留原有体积/样式顺序警告）。最终发布检查与身份记录于 publish.json。
- Web 同步共享客户端代码，后端、数据库和 SimC 无变更。微信上传不等于公开发布。

## 发布结果

源码 `c1dfe7bfd` 已合入 main 并推送。Web 27 个公网文件哈希一致，readiness ready；Mini `1.0.2` 上传成功（1,066,901 bytes），微信审核/公开发布待用户平台操作。335 项前端测试和 62 项控制面测试通过。发布元数据提交与运行源码提交分别记录。

Web 回滚：确认 current 仍指向 publish.json 中的 root 后，原子切回 rollback；保留旧目录，无数据库反向迁移。此前各轮二维码仅为本地调试历史，不作为正式发布身份。

## 1.0.3 体验版配置纠正

1.0.2 上传未传 WOW_BACKEND_API_BASE_URL，开发环境默认地址掩盖了体验版缺少正式地址的问题。另需将后台体验路径从已删除的 pages/index/index 改为 pages/chickenbro/index。1.0.2 不能作为体验版通过证据。

已使用以下显式参数构建并上传 1.0.3（1,066,968 bytes），不改 Web/后端：

```sh
WOW_BACKEND_API_BASE_URL=https://api.chickenbro.cloud WOW_TEST_LOGIN_UI=0 WOW_API_V2_PREFIX=/api/v2 WOW_WEB_AUTH_API_PREFIX=/api/v2 npm run build:weapp
```

35 项网络层测试通过；从实际 common.js 提取并执行地址解析函数，在 trial/release 两种环境均返回正式 HTTPS 地址，忽略本地覆盖。见 trial-config-1.0.3.json 和 mini-upload-1.0.3.json。用户重新扫码后于 2026-09-08 明确确认“这次OK了。”，1.0.3 体验版真机验收通过；微信审核与公开发布仍待用户平台操作。源码哈希不能单独证明构建环境配置，后续上传须同时核对编译后的正式地址、测试入口关闭和体验路径。
