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
