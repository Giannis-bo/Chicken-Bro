# 回答解决情况反馈：本地验证

日期：2026-09-08。范围：[已确认任务](../../../docs/plans/2026-09-08-chat-feedback.md)。

本地工作分支 `codex/chat-resolution-feedback`；基线 `f8a8e3c48`，改动尚未提交。最终改动源码与双端构建哈希见 [文件身份](file-identities.json)。未 fetch/pull、未安装依赖、未连接生产数据库、未部署/上传微信。

## 实现与审查

- 最新采用「是否解决」加两个无边框线条拇指图标，不显示已解决/未解决选项文字或原因收集框；点击弹窗确认后才保存；重复点击受控，失败时保留原选择并允许重试。
- 原 AgentRun 增加可空解决状态及反馈时间，复用问题/回答/会话/运行版本关联，首次确认后不可改评，重复同一选择不刷新时间；不新增跨账号公开查询。
- API 使用严格布尔输入与 Principal；Web 写入继续校验 Origin/CSRF。事务以 active conversation 的共享锁与软删除串行化，只接受本账号成功回答。
- 新字段由 `includeFeedback=true` 显式开启，避免旧客户端严格字段校验失败。UI 在服务端历史加载后展示，不伪造流式阶段的 message ID。
- 一次本地源码审查覆盖路由、application、repository、迁移、typed client、共享状态和双端组件。已修正旧客户端兼容问题；控制面新增文件已纳入 keep 清单，不改历史删除 inventory。
- 控制面测试还发现基线已存在的问题：roadmap 引用的 `2026-09-08-web-simc-layout` 发布记录未被列为 keep（以 HEAD 规则复现为 delete）。补齐该既有证据目录的保留前缀，未改发布记录或执行任何清理。

## 验证

- TDD：先运行新增用例，确认缺少反馈接口/组件/字段而失败；实现后通过。旧客户端响应合同另有失败再修复证据。
- 后端全套：420 项通过。
- 迁移与 PostgreSQL：使用本机已有 PostgreSQL 16、独立 UTF8 临时数据库、预建 `wow_app NOLOGIN`；反馈用例覆盖持久化、改选、去重时间、其他 owner、错误会话、用户消息、未完成/失败/已归档回答、严格布尔及 CSRF。
- 前端：共享组件、typed contract、ChatModel、Mini/Web 真实页面组件；已覆盖按钮提交、选中状态、历史恢复、失败重试。
- 类型检查、lint、控制面、双端构建及最终计数见本文件下方最终检查记录。
- Web/Mini 构建成功；Webpack 有既有体积警告。Mini 安全构建完成 staged atomic promotion，生成 43 文件。
- 390×844 / 桌面浏览器检查真实 `ChatFeedback.tsx` + SCSS，点击「未解决」后选中反馈正确，无原因输入。截图为本地测试容器，并非正式页面或真实微信 DevTools 验收：[桌面](component-desktop.png)、[手机宽度](component-mobile.png)。完整页面的双端行为由组件集成测试验证。

最终检查（2026-09-08 18:31，Asia/Shanghai）：

| 检查 | 结果 |
| --- | --- |
| `npm run test:taro` | 46 文件、328 项通过 |
| `npm run test:backend`（已有测试 venv） | 420 项通过 |
| `npm run test:migration`（全新独立 UTF8 DB） | 81 项通过，零跳过 |
| `npm run test:control` | 62 项通过 |
| `npm run typecheck` / `npm run lint` | 通过 |
| `npm run build:h5` / `npm run build:weapp` | 通过；27 / 43 个产物文件 |
| Mini 生成产物 | 已核对两项选择、提示文案、`includeFeedback=true` 和 `/feedback` 请求路径；压缩 JS 使用 Unicode 转义 |
| `git diff --check` | 通过 |

## 交付边界

当前为本地实现与验证。Candidate、生产部署、真实 Mini/Web 用户验收均未进行。发布须先迁移/更新后端，再发布客户端；回滚旧应用时保留反馈数据列。

## 19:14 图标精简

用户在本地 Web 预览后要求改为拇指上下小图标。共享组件已改为 👍🏻 / 👎🏻，保留无障碍名称、选中背景、重复点击保护及失败重试。后端与反馈语义未变。12 项共享组件/双端页面测试、类型检查和 lint 通过，双端构建刷新；文件身份随之更新。原 component 截图仅为此前文字版历史证据，最新 Web 示例预览见 [拇指按钮](web-thumbs.png)。本地预览使用真实 WebShell/WebChatView 和示例数据，点击仅保存预览本地状态，未部署。

## 19:24 最终线条图标与确认弹窗

用户最新要求替代此前 emoji 方案：只显示「是否解决」和简笔线条拇指上下图标，选项名称仅供无障碍使用。点击弹窗提示“您的反馈会让鸡哥变得更好。”；取消不提交，确认后保存。Web 使用带键盘焦点管理的 dialog，Mini 使用平台原生 showModal；图标是 SVG 线条背景，不是 emoji。15 项共享组件、双端页面和 Mini 原生确认测试、typecheck、lint、双端构建通过。浏览器实际核对图标与弹窗并确认保存，见 [线条按钮](web-line-icons.png)、[确认弹窗](web-feedback-confirm.png)。此前图片为历史版本。此轮未改后端，未部署。

## 19:30 确认后锁定

用户要求确认评价后不可修改。最新实现只允许首次 `resolved IS NULL` 的原子更新；相同选择重试幂等成功，改成相反选择返回 409 `FEEDBACK_ALREADY_SUBMITTED`，并发首写只有一个胜出。双端按钮保存后禁用；另一端旧页面遇到冲突会读取已保存状态并锁定。取消或保存失败不锁定。预览 mock 同步采用首次写入规则，截图见 [已锁定](web-feedback-locked.png)。

本次新鲜验证：前端 332 项通过；后端全套 420 项通过；反馈/删除/账号互斥 PostgreSQL 定向测试通过；typecheck、lint、双端构建通过。SQL 迁移文件未变，未再次执行生产迁移或部署。此前关于可修改的描述/记录仅为历史版本，本节与最新任务要求优先。

## Mini 本地预览补充

2026-09-08：Web 本地视觉获用户确认。Mini 独立预览目录 `/tmp/cb-feedback/mini-workspace/apps/mini-taro/dist/weapp`，使用当前组件源码及隔离的示例 API、存储，不写线上数据。构建成功，在微信开发者工具 RC 2.02.2607271 / 已缓存基础库 3.17.0 打开并检查。实际模拟器发现原生按钮默认宽度导致换行，已在共享样式限制宽度与外边距，修复后一行显示文字和两个线条图标。原生确认弹窗提示正确，截图 `mini-devtools-confirm.png`。此项为本地示例预览，未做真机或线上双端验收。原 file-identities.json 为本次样式修复前快照。

## 提交合入检查

用户已确认双端本地预览并授权提交合入。最终本地源码审查无阻断问题；CodeRabbit 不在当前环境，沿用用户不安装的要求。fresh 验证：前端 332、后端 420、独立 PostgreSQL 迁移 82（零跳过）、控制面 62 项通过；typecheck、lint、H5/Weapp 构建通过。另一个正在编辑的 Mini 输入框键盘位置调整不纳入反馈提交，保留在工作区；测试运行时包含此局部工作区改动。生产未部署。

精确暂存版本另行导出到隔离目录，再运行前端 332 项及 typecheck，均通过；这次验证排除了工作区输入框改动。文件身份中的 sourceFiles 已更新为精确暂存版本，builds 保留原历史构建并加注明。

## 生产发布（用户随后授权）

源码 `5ace442c3` 已发布后端和 Web，第 6 号迁移已应用。云端独立 `chickenbro_feedback_verify_20260908` 库 17 项测试通过；公网 27 个 Web 文件 SHA 全部匹配。正式 HTTPS API 使用专用短期验证会话测试 Mini 保存 / Web 读取、同值幂等、相反值 409、其他账号 404、CSRF 403 和旧客户端合同，全部通过。专用验证会话已撤销、验证对话已软删除；使用合成回答，未重新扫码或调用模型。旧代码/Web目录保留，回滚不删除新增反馈列。

Mini 正式 API 构建 `1.0.1` 上传成功，1,066,177 bytes；后台被浏览器站点安全策略阻止，未提交微信审核或公开发布，需用户完成。发布证据见 `publish.json` 和 `publish-manifest.json`。
