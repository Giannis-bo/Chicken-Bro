# 本地、远端与双端版本复核

状态：`已完成 / 小程序已上传，待用户审核`；2026-09-08。

## 仓库与文档

同步起点 `1db94ba9598bfa2c8b67d7e305bcc67f3c6a64b1`；fetch 后本地 main 与 origin/main 为 `0/0`。没有未提交的业务代码；本次仅同步文档及发布证据。既有预览图片/构建记录和 feedback 临时 worktree 保留，不做清理。

当前已交付回答反馈、Mini 键盘/流式恢复、Raider.IO-only 导入、Web SimC 布局及右下角署名。项目状态、路线图、计划索引、架构、Runbook、1.0 说明、验证矩阵和用户指南统一当前范围，1.0.0—1.0.4 保留为历史发布证据。

Badcase 既有文档合并当前决定并登记保留：本地 heartbeat 为 ACTIVE，首次扫描为北京时间 2026-09-09 06:00，每6小时一次，18:00检查条件发布；扫描器、隔离验证与发布执行链路仍未实现/验收，不计为上线能力。

## 线上与小程序

- Web：`credit-189d711648c6846df73f07d9aeb2ae7f9766ff15`，27 个公网文件 SHA256 与发布 manifest 一致；从该源码至当前 main 的 Web/共享代码/构建脚本无差异。
- API/Worker：`raider-4315455479566aab7ead4488c52842f3b83c55b1`，81 个业务源码、配置、产品迁移及已追踪依赖文件与当前 main 一致；两个域名7项 readiness 均 ready。源码无待部署差异，本轮未重启或迁移，SimC runtime 未改。
- 正式 Web 复用既有会话：服务正常、署名可见、导入仅显示 Raider.IO 示例、已有模拟任务和结果读取正常。没有新建 Chat/SimC 任务，没有重新扫码。
- Mini **1.0.5**：从上述仓库基线重新构建，正式 API，关闭测试登录；5条页面含 Web 登录确认，首页为 pages/chickenbro/index。微信开发者工具 CLI 上传成功，**1,066,066 bytes**。构建身份见 [mini-build.json](mini-build.json)，回执见 [mini-upload-1.0.5.json](mini-upload-1.0.5.json)。
- 用户下一步：微信公众平台 → 版本管理 → 开发版本 → **1.0.5** → 提交审核。审核、公开发布和本次真机验收尚未代办或冒称通过。

各运行面的目录提交不同，但对应部署内容与当前源码相同；文档证据提交不会产生新运行差异。Web/后端旧回滚目录已确认存在，具体身份见 [release.json](release.json)；回滚前仍须重新核对指针与排空条件。

## 本轮验证

前端335项、后端421项、控制面62项通过，typecheck、lint、小程序生产构建、git diff --check 通过。后端首次系统 Python 缺 FastAPI，改用已有 `/tmp/chickenbro-merge-check-venv-20260907` 后通过；没有安装依赖。公网 SHA 初次 Python TLS 检查遇到证书兼容错误，使用保持证书验证的系统 curl 完成全部27文件校验。

CodeRabbit CLI/MCP 均不可用，未安装；本地逐项审查文档差异、源码范围、发布回执与哈希证据，未发现阻塞项。无运行/迁移代码变化，本轮不重跑 PostgreSQL 迁移或 H5 构建，使用无源码差异和既有部署 manifest 加公网完整哈希验证 Web 身份。测试通过与文件一致均不替代新一轮双端真人验收。

详见 [文件哈希](file-parity.json) 和 [发布结果](release.json)。
