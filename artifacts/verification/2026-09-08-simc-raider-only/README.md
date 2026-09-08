# SimC Raider.IO-only 发布

用户于 2026-09-08 验收双端预览与 Web 卡片对齐，并授权提交、合入、发布。

- 新 SimC 来源仅接受 HTTPS Raider.IO 角色链接；应用入口统一拒绝 WCL，双端示例、提示、FAQ 同步。
- 保留 Chat WCL 研究和历史快照/任务；无数据库迁移或 SimC 引擎变更。
- 桌面两列等高，左侧来源行自然高度，下方两卡片与摘要底边一致；实际浏览器差值由 16.75px 变为 0px。
- 独立源码审查无发现。CodeRabbit CLI/MCP 不可用，未安装依赖。
- 421 项后端测试、335 项前端测试、typecheck、lint、H5/WeApp 构建通过；修正既有 Mini 键盘发布文档的保留归类，提交快照 62 项控制面检查通过。
- 源码 `4315455479566aab7ead4488c52842f3b83c55b1` 已进入 main 并推送；后端/Web 已发布，27 个公网文件 SHA256 一致。Mini/Web 正式 HTTPS 接口均拒绝 WCL，未写入快照；Raider.IO 导入为 READY_FOR_SIMC，未创建模拟任务。现有网页登录会话确认最新页面且卡片底边一致。Mini 1.0.4 上传成功，工具安全策略阻止版本管理页面访问，审核/公开发布待用户操作。详见 [发布结果](publish.json) 与 [内容清单](manifest.json)。旧后端/Web 目录保留用于回滚，无数据库迁移或 SimC 引擎变更。
