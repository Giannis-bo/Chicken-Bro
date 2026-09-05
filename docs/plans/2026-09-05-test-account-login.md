# 测试账号快捷登录

状态：正在推进。2026-09-05 用户确认方案并授权实施。

## 需求合同

测试者无需微信扫码或确认，即可用 A/B 测试账号在 Mini/Web 操作真实 Chat/SimC。服务端仍拥有身份和数据归属，两个独立会话对应同一测试用户。凭证只输入一次，过期或退出后重新输入；失败如实显示，不退回假数据。

反方检查：全局跳过鉴权会失去 owner 合同；前端 fixture 无法验证真实业务。因此复用正式 Session 和业务链路，仅替换测试环境的登录入口。非目标：删除微信登录、生产匿名访问、迁移真实用户、改变 SimC 输入/执行规则。

## 实施与影响

1. Identity/config：默认关闭；生产禁止启用；只允许专用测试数据库。A/B 使用独立高熵凭证的 SHA256 配置，服务端固定用户映射，无客户端 user_id；会话有期限，关闭入口后测试会话立即拒绝。不新增依赖或 schema。
2. API/client：独立 Mini/Web 测试登录请求，Web 保留 Origin/CSRF/HttpOnly Cookie，Mini 保留 Bearer。错误不回显凭证。
3. Mini/Web：显式测试构建开关、密码输入、A/B 选择、已连接提示、退出和重新进入；业务模型继续调用正式 API。
4. 运维：记录测试环境配置和关闭步骤，使用独立数据库/API/Worker；云端 SimC 保持原有 runtime。不得在生产服务上启用。

依赖方向：测试登录 UI -> typed API client -> Identity application -> Identity repository -> 正常 Principal -> Chat/SimC。Chat、SimC、Worker 的 owner 和业务语义不变。身份创建为有界事务，不修改热点业务 application。

## 验收与回滚

先测试默认关闭/生产拒绝/数据库保护、错误凭证、固定用户、正常双端会话、过期退出与关闭失效；再验证 Mini/Web 客户端 transport 和编译构建。隔离 Candidate 验证真实持久化、Chat/SimC、A/B 隔离及独立退出。手工必验：mini_login、web_login、shared_chat、shared_simc、owner_isolation、independent_logout、disabled_mode。自动 API/内存测试不能冒充真实设备或云端 SimC 验收。

回滚：关闭服务端入口并重启，所有测试会话拒绝；关闭客户端测试构建并重建。必要时回退代码；测试数据保留于独立库，不删除生产资源。测试运行态未部署前最高证据只能为本地验证。

使用与运维入口见 [测试账号说明](../test-account-login.md)。

## 当前交付证据（2026-09-05）

代码及测试环境已就绪。运行版本 `d28c68bf10ccb79aae968a5697dc924429649393`，独立测试库/API/Worker 已部署。真实 Chat 回复、两端共享历史、B 隔离、单端退出、重启持久化、关闭入口与旧会话撤销通过；最终 CSS 修正已在浏览器截图复核。Mini 测试包已原子更新；开发者工具自身要求用户重新登录，未冒充真机验收。

定向验证：后端 240、前端 124、控制面 62 项通过；类型检查、lint、双端测试构建通过。迁移 64 项中 1 项既有可选 PostgreSQL 集成跳过；完整 ops 在 Windows/临时 Linux 源码环境仍有 Bash、Git/Taro 和历史清单限制，未宣称全套通过。SimC 仅验证正常鉴权列表，未运行新的模拟。完整记录见 `artifacts/releases/2026-09-05-test-account-login/evidence.json`。

下一步：用户运行配置脚本设置自行持有的 A/B 凭证，在真实 Mini/Web 完成业务验收。当前保留任务分支，main 未修改；不作合并、正式切流或清理收尾。

## 登录失败修正（2026-09-05）

用户已成功配置凭证，但网页仍失败。根因：API client 的 public 请求白名单仍硬编码旧前缀，且缺少测试登录路由，因此登录和 `/test/api/v2/me` 在发送前被拒绝；先前后端 HTTP smoke 和使用 RecordingTransport 的客户端测试未覆盖此交界。

修正版本 `1cb69626758a161170fbcab7ed9aa146ac171d34` 已部署，白名单使用统一配置前缀，仅测试构建允许两个精确登录端点，业务接口仍需登录。新增 9 项跨 API client/真实 transport 回归（修正前 4 项失败），当前前端 133 项、类型检查、lint 和双端测试构建通过。浏览器用明确无效的测试字符串复现旧版泛化错误，更新后收到服务端明确凭证错误，证明请求已通；未索取或重设用户凭证。真实正确凭证登录仍由用户验收。

## Web 输入框优化（2026-09-05 用户授权）

用户确认 Web 登录成功后，要求去掉输入框右侧“对话”、Enter 发送、修复回复过程中箭头和加载动画重叠。范围限定现有 Web 输入框：Shift+Enter 换行，中文输入法选词不发送，回复中保留下一条草稿并禁止重复发送，单一居中加载图标完成后恢复箭头。Chat API、模型及权限不变。通过真实 React DOM 事件回归与测试环境浏览器检查验收，Mini 功能范围不变。
