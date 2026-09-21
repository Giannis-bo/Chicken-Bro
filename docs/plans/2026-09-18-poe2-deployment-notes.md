# POE2 Candidate 部署设计（只读调查）

> 当前状态（2026-09-21）：已完成。用户已验收并授权发布，运行源码 `77cee1603` 已上线，提交与合入已完成；见[正式发布记录](../../artifacts/releases/2026-09-21-poe2/README.md)。下文 Candidate、禁止提交与待验收等表述记录此前阶段，不代表当前状态。

2026-09-18 实查 `wow-lighthouse`；本轮未创建数据库、修改配置、启动服务或发布页面。以下是待实施配置，不能视为已部署。

## 已确认的云端现状

| 对象 | 实查状态 |
|---|---|
| 生产 | API 8790、durable Chat 工具 28794，API/worker active |
| 既有测试 | `/test/` → `/opt/chickenbro-test/current/web/`，API 8792；test API/worker active |
| 旧 QQ Candidate | `/web-candidate/`、`/api/v2-candidate/` → 8794，须保留 |
| 新端口 | 8796、18794 当前无监听 |
| 新数据库 | `chickenbro_poe2_candidate` 当前不存在 |
| 源码根 | `/opt/chickenbro-candidates/poe2-20260918/source` 已存在 |
| 引擎 | `upstream/pob` HEAD=`7d6f530cbdab20389ff8bc6ba97a37ac27f74e41`，tag=`v0.23.1` |
| Python | `/opt/chickenbro-runtime/bin/python` 已存在 |
| LuaJIT | `runtime/root/usr/bin/luajit`，已解包到独立目录 |
| SimC | `/opt/wow-simc/current/simc` 已存在；使用现有云端版本 |
| Codex profile | `/home/ubuntu/.codex/chickenbro-production.config.toml` 已存在 |

Nginx 实际 Web site 为 `/etc/nginx/sites-enabled/wow-v2-web`，已有 test 与旧 QQ Candidate 两个 include。只新增 `/poe2-candidate/` 专用 include；不运行已退役的 `deploy_chickenbro_candidate_lighthouse.sh`，也不运行绑定 `/test/`、8792、`chickenbro_test` 的 `deploy_test_login.py`。

## 必须先完成的代码前置

1. `AppSettings.__post_init__` 的 test-login 数据库 allowlist 加入准确名称 `/chickenbro_poe2_candidate`。当前只允许 test/candidate/dev 三个旧名称。
2. 新建专用 `server.poe2_candidate_runtime`，最后一步在进程内强制所有隔离变量。现有 `test_login_runtime` 强制 `/chickenbro_test` 与 8792，不能直接调用。
3. 最终复读确认 `chickenbro_native_mcp._source_gateway_target_is_local` 已加入本机端口 8796。durable Chat 使用的 18794 已在白名单；`start_chat_workers` 也已允许 18794。
4. 最终复读确认 Chat game 环境转发、严格 XML 根校验已落地；jobs 请求上限/摘要响应、重试耗尽终态、常驻 worker 每进程 UUID 身份与 0012 的 `wow_app` schema/table GRANT 已落地。迁移后仍须实际角色检查权限。实现代理报告已有实际 wow_app 角色 PostgreSQL 3/3 与真实 PoB worker 1/1 通过；本轮只读复核未重跑。

推荐运行时 `WOW_APP_ENV=test`，产品交付仍称 POE2 Candidate。原因：当前 `candidate` 环境把 heartbeat 强制锁定 `/var/lib/chickenbro/candidate-worker-heartbeat.json`，且 QQ 路径固定 `/web-candidate/`；使用 test 模式配合准确 DB allowlist、独立路径和禁用 QQ，避免与既有 Candidate 控制面共用文件。若必须使用 `candidate` 环境标记，应同步增加准确的专用 heartbeat 路径支持，不能直接共用旧路径。

## 测试账号与凭据

已只输出布尔校验：`/etc/chickenbro-test-login.env` 存在、启用、A/B SHA256 都合法且不同。没有输出哈希或明文。因此现有 A/B 登录口令可以沿用：新服务将该文件作为只读 EnvironmentFile 加载，认证时使用相同哈希；新 DB 首次登录由 `ensure_test_user` 创建保留测试 UUID。无需复制旧库业务记录、会话或 QQ 身份，也无需重新配置用户口令。

数据库凭据沿用当前 runtime 已获权限的 `wow_app` 连接：新 wrapper 在内存中从现有 `WOW_DATABASE_URL`/`PGPASSFILE` 读取凭据，严格校验源 DB 是 `chickenbro_prod`，仅把数据库名改成 `chickenbro_poe2_candidate`，设置进程内 `PGPASSWORD`。方法参考 `test_login_runtime.prepare_environment`；禁止打印完整 URL、PGPASSFILE 内容、环境快照。新 DB 中授权角色仍为 wow_app，生产数据库和 `/test/` 数据不变。

清空 `WOW_QQ_APPID`、`WOW_QQ_APP_KEY`、`WOW_QQ_REDIRECT_URI`，本 Candidate 使用现有测试账号入口；避免错误回调到 `/test/` 或旧 Candidate。wrapper 必须在加载环境文件之后执行覆盖，systemd 的普通 Environment= 无法胜过 EnvironmentFile 中同名项。

## 固定隔离值与引擎环境

```text
WOW_APP_ENV=test
WOW_API_V2_HOST=127.0.0.1
WOW_API_V2_PORT=8796
WOW_WEB_ORIGIN=https://www.chickenbro.cloud
WOW_WEB_COOKIE_NAME=__Host-chickenbro-poe2-candidate-session
WOW_WEB_CSRF_COOKIE_NAME=__Host-chickenbro-poe2-candidate-csrf
WOW_WEB_SESSION_TTL_SECONDS=86400
WOW_TEST_LOGIN_ENABLED=1
WOW_CHAT_DURABLE_ENABLED=1
WOW_CHAT_WORKER_TOOL_PORT=18794
WOW_WORKER_V2_HEARTBEAT_PATH=/var/lib/chickenbro/poe2-candidate-worker-heartbeat.json
WOW_CODEX_JOBS_DIR=/var/lib/chickenbro/poe2-candidate-codex-jobs
WOW_CHICKENBRO_CODEX_ENABLED=1
WOW_CODEX_BIN=/usr/local/bin/codex
WOW_CODEX_HOME=/home/ubuntu/.codex
CODEX_HOME=/home/ubuntu/.codex
WOW_CODEX_PROFILE=chickenbro-production
HOME=/home/ubuntu
WOW_SIMC_BIN=/opt/wow-simc/current/simc
WOW_SIMC_SUPPORTED_SPECS=all
WOW_SIMC_COMPILER_REVISION=chickenbro-simc-compiler-v6
POE2_POB_ROOT=/opt/chickenbro-candidates/poe2-20260918/upstream/pob
POE2_LUAJIT=/opt/chickenbro-candidates/poe2-20260918/runtime/root/usr/bin/luajit
POE2_ENGINE_VERSION=v0.23.1@7d6f530cbdab20389ff8bc6ba97a37ac27f74e41
LD_LIBRARY_PATH=/opt/chickenbro-candidates/poe2-20260918/runtime/root/usr/lib/x86_64-linux-gnu
LUA_CPATH=/opt/chickenbro-candidates/poe2-20260918/runtime/root/usr/lib/x86_64-linux-gnu/lua/5.1/?.so;;
LUA_PATH=/opt/chickenbro-candidates/poe2-20260918/upstream/pob/runtime/lua/?.lua;/opt/chickenbro-candidates/poe2-20260918/upstream/pob/runtime/lua/?/init.lua;;
```

Lua 扩展目录实查已有 `lua-utf8.so`、`zlib.so`、`cjson.so`；后二者链接到独立 runtime 的实际库文件。以上路径要同时进入 API（同步 import 会调用引擎）和 worker（任务计算、Chat import）。引擎无网络隔离方案随 Task 1 最终实现补齐，不得把进程限时/内存限制当成断网证明。

Cookie 的 `__Host-` 名称必须配 `Secure; Path=/`，不能设置 `Path=/poe2-candidate/`。这里通过**不同 Cookie 名称、不同数据库、不同 CSRF 名称**隔离会话；URL 路径独立。浏览器仍可能在同域请求上携带多套 Cookie，服务端只读取对应名称。不要添加 `proxy_cookie_path` 改写。验证新登录不覆盖 `/test/` cookie，原 test cookie 不能登录新 API。

## 数据库与服务设计

新 DB 只创建一次并记录专用 comment；若名称已经存在，先核验 comment、owner、schema 版本，不覆盖、不 drop。用既有 `apply_product_migrations` 应用当前 `server/migrations/product`；不要手工字符串排序迁移。数据库连接收窄：REVOKE CONNECT FROM PUBLIC，GRANT CONNECT TO wow_app；确认 migration 0012 对 wow_app 有 `USAGE poe2`、`SELECT/INSERT builds`、`SELECT/INSERT/UPDATE jobs`。

服务名：`chickenbro-poe2-candidate-api.service`、`chickenbro-poe2-candidate-worker.service`。两者同一源码路径：

```ini
[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/chickenbro-candidates/poe2-20260918/source
Environment=PYTHONPATH=/opt/chickenbro-candidates/poe2-20260918/source
EnvironmentFile=/etc/chickenbro-source.env
EnvironmentFile=/etc/chickenbro-api.env
EnvironmentFile=/etc/chickenbro-test-login.env
Environment=PATH=/home/ubuntu/.local/bin:/usr/local/bin:/usr/bin:/bin
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/var/lib/chickenbro /home/ubuntu/.codex
ReadOnlyPaths=/opt/chickenbro-candidates/poe2-20260918 /opt/chickenbro-runtime /opt/wow-simc
Restart=always
RestartSec=5
TimeoutStopSec=540
```

API ExecStart：`/opt/chickenbro-runtime/bin/python -m server.poe2_candidate_runtime api`，wrapper 最终 exec `-m uvicorn server.app.main:app --host 127.0.0.1 --port 8796`。

Worker ExecStart：`/opt/chickenbro-runtime/bin/python -m server.poe2_candidate_runtime worker`，wrapper 最终 exec `-m server.app.worker.main --worker-id chickenbro-poe2-candidate-worker`。使用常驻入口，它启动 Chat 18794、POE2 lane 与原 SimC lane；`--once` 当前仅执行 SimC queue，不适合验证 POE2 启动合同。不要复制生产 worker 的 `ProtectHome=true`，它阻止 Chat 读取 Codex 配置。

保留现有代理地址 `HTTP_PROXY/HTTPS_PROXY/ALL_PROXY=http://127.0.0.1:7890` 及 NO_PROXY 中 localhost；wrapper 显式设置或复制安全值，不能遗漏导致 loopback tool 被代理。profile 可复用已有生产模型配置，adapter 会把 toolbox args 指向当前 Candidate 源码。部署前核验该 profile 的 server args 重写和 CHICKENBRO_GAME 转发确实生效。

## Web 构建与 Nginx

只在云端用已存在 Node/runtime/dependencies 构建；建议输出独立 `web/`，不可覆盖当前 `/var/www/chickenbro-web/current` 或 `/opt/chickenbro-test/current`。

```text
WOW_APP_ENV=test
WOW_TEST_LOGIN_UI=1
WOW_H5_PUBLIC_PATH=/poe2-candidate/
WOW_API_V2_PREFIX=/poe2-candidate/api/v2
WOW_WEB_AUTH_API_PREFIX=/poe2-candidate/api/v2
WOW_WEB_CSRF_COOKIE_NAME=__Host-chickenbro-poe2-candidate-csrf
WOW_BACKEND_API_BASE_URL=https://www.chickenbro.cloud
WOW_TARO_ISOLATED_BUILD=1
```

在 `wow-v2-web` HTTPS server 新增单独 include，内容如下。发布前保存原 site/snippet 文件身份，`nginx -t` 成功才 reload；既有 production/test/旧 Candidate location 均保留。

```nginx
location = /poe2-candidate { return 302 /poe2-candidate/; }
location ^~ /poe2-candidate/api/v2/internal/ { return 404; }
location ^~ /poe2-candidate/api/v2/ {
    proxy_pass http://127.0.0.1:8796/api/v2/;
    client_max_body_size 7m;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;
    proxy_read_timeout 540s;
}
location ^~ /poe2-candidate/ {
    alias /opt/chickenbro-candidates/poe2-20260918/web/;
    index index.html;
    rewrite ^/poe2-candidate/(simc|poe2|admin)/?$ /poe2-candidate/index.html last;
    add_header Cache-Control "no-store" always;
}
```

构建路由还需确认 `h5.router.customRoutes` 包含 `/poe2`；当前 Web 路由已经生成该路径，Nginx SPA rewrite 不能替代 Taro 客户端路由注册。7m API 限额同时覆盖既有图片与 PoE2 XML JSON；不要沿用 Nginx 默认 1m。

## 部署顺序与接受证据

1. 固化待部署源码 diff hash、引擎 commit、Web artifact manifest；确认源码修复已包含在上传版本。
2. 新 DB/migrations/实际 wow_app 权限验证；只用新 DB 做两账号会话与任务验证。
3. 建独立可写 jobs/heartbeat 路径且 ubuntu 可遍历、写入；启动两个新服务，检查 8796/18794 监听与专属 heartbeat。
4. 本机只读 readiness、登录、真实 import→queue→worker→succeeded→compare/export；readiness 正常不替代真实 PoB task 成功。
5. 新 Web 与新 Nginx include；核验 public shell/bundle hashes，真实浏览器进入 `/poe2-candidate/`、`/poe2-candidate/poe2`、`/poe2-candidate/simc`。
6. 用 A/B 做历史、构筑、job、导出 owner 隔离；分别确认 `/test/` 仍可用、原会话未被覆盖；真实 Chat tools/list 与来源应为当前 game。

撤回仅停新服务、移除新增 include 并 reload；保留新 DB/源码/证据供恢复。不删除已有生产/test/Candidate 数据。用户验收前不切换生产、提交、推送或合入。
