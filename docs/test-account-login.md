# 测试账号快捷登录

测试 Web 地址：`https://www.chickenbro.cloud/test/`。小程序测试包使用同一测试 API，进入时选择 A/B 并输入对应凭证，两端保留独立会话，同一账号共享测试库中的真实 Chat/SimC 历史。

## 首次设置

在自己的终端进入仓库，执行 `python -X utf8 scripts/configure-test-login.py`。按提示为 A、B 各设置一个不同的 32–256 字符凭证，建议由密码管理器生成并保管。输入不回显，不放进聊天、源码或小程序包；本地只在内存计算摘要，SSH 仅传送摘要。此操作只重启测试服务，并撤销旧测试会话。

之后在 Web/小程序输入一次。会话最多保留 24 小时；退出、到期或测试模式关闭后重新进入。小程序的“退出 / 切换账号”和 Web 的“退出”可切换 A/B。测试凭证不保存在客户端，Mini 只存测试会话；Web 使用独立的 HttpOnly Secure Cookie。

本地启动脚本依赖机器既有的 `wow-lighthouse` SSH 配置。没有此权限的测试者只需要由项目所有者告知自己的测试账号凭证，不需要服务器权限。

本次已生成的测试小程序目录为 `apps/mini-taro/dist/weapp`。如果微信开发者工具提示“需要重新登录”，先登录开发者工具本身，再打开此目录；业务页面随后使用 A/B 测试凭证。首次配置完成前，验收脚本生成的临时凭证不可用于个人登录。

## 构建

测试构建设置：`WOW_APP_ENV=test`、`WOW_TEST_LOGIN_UI=1`、`WOW_API_V2_PREFIX=/test/api/v2`、`WOW_WEB_AUTH_API_PREFIX=/test/api/v2`、`WOW_WEB_CSRF_COOKIE_NAME=__Host-chickenbro-test-csrf`、`WOW_BACKEND_API_BASE_URL=https://api.chickenbro.cloud`。H5 额外设置 `WOW_H5_PUBLIC_PATH=/test/`。

使用已有 `npm run build:h5`、`npm run build:weapp` 或 `npm run refresh:weapp`。测试 UI 在未明确选择 local/test/candidate 时拒绝构建。正式构建不设置上述测试变量，原微信登录保持有效。

## 运行边界

- 测试数据库固定为 `chickenbro_test`，只从空库应用现有有序迁移，正式 `chickenbro_prod` 不写入测试数据。固定 A/B 测试用户没有微信身份映射，客户端不能指定真实用户。
- 测试源码位于 `/opt/chickenbro-test/releases/<commit>`，`current` 指向本次代码；服务为 `chickenbro-test-api.service`、`chickenbro-test-worker.service`，API 绑定 `127.0.0.1:8792`。
- 启动器复用服务器已有 Python、数据库凭据、Codex 和云端 SimC；凭据只在进程内用于连接测试库，不复制明文到新的文件。强制独立 Cookie、心跳与 Chat 工作目录，避免继承生产配置。
- 服务端 `WOW_TEST_LOGIN_ENABLED` 默认关闭，启用时必须在 local/test/candidate 且使用专用测试数据库；A/B 的 SHA256 摘要必须有效且不同。生产环境禁止启用。Web 登录和写操作仍检查 Origin/CSRF。
- 关闭后的身份解析拒绝所有 A/B 会话，包括通过其他正式入口交换出的会话。服务端会话始终受正常过期和撤销检查。
- 本功能不放宽 SimC 来源和 readiness 条件；无法生成完整输入时继续显示真实原因。UI fixture、内存测试与真实云端结果分别记证据。

## 关闭与回滚

执行 `python -X utf8 scripts/configure-test-login.py --disable` 关闭测试入口、撤销 A/B 的现有会话，并重启两个测试服务。正式服务不受影响。需要重新启用时再次运行首次设置命令。

移除客户端测试开关后重新构建。代码回滚仅将 `/opt/chickenbro-test/current` 指回已验证的测试 release 并重启测试服务；不删除数据库。若需完全下线测试网址，移除两个 Nginx site 中精确的 `chickenbro-test-*.conf` include，通过 `nginx -t` 后 reload；停止两个测试 unit。该步骤不删除服务、代码或数据库。

## 验收

登录 Mini A 和 Web A；双向创建/续聊；提交同一 SimC 并对比状态/结果；换 B 确認历史隔离；单端退出另一端保持登录；关闭测试模式确认新登录及旧会话均失败。真实用户验收单独记录，自动测试和测试环境 smoke 不代替手工验收。
