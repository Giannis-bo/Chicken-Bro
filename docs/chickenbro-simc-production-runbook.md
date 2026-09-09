# 炸鸡队长与 SimC 生产迁移、切流与恢复 Runbook

## Web-only / QQ 登录部署准备（2026-09-09）

用户已授权 Web-only 与 QQ 重构，并授权云端保存 QQ 凭据。`/etc/chickenbro-qq.env` 已创建，root-owned、mode 0600；包含 `WOW_QQ_APPID`、`WOW_QQ_APP_KEY`、`WOW_QQ_REDIRECT_URI`。仅保存文件，没有给现有服务加载或重启，没有切换生产。不得打印该文件内容。

正式 callback 固定为 `https://www.chickenbro.cloud/api/v2/auth/qq/callback`。后续已获发布授权时，先部署隔离 API/Web 版本并应用 additive QQ migration、保留回滚版本；通过 systemd `EnvironmentFile=/etc/chickenbro-qq.env` 给新 API 加载配置。不要复制密钥到 release 目录、Web 构建变量、Git 或日志。同站点的测试 callback 使用 `/test/api/v2/auth/qq/callback`，候选使用 `/api/v2-candidate/auth/qq/callback`，分别返回 `/test/` 和 `/web-candidate/`；需在 QQ 后台单独登记，Cookie 名称与正式环境隔离。不要把正式 callback 指向候选数据库。测试/候选的 callback 路径及尾斜杠、无效后缀同样必须关闭 query access log。

QQ callback 携带授权码和 state，反向代理需为该 callback 路径前缀关闭 access log（包括尾斜杠重定向和无效后缀） 或采用不包含 query 的脱敏格式（部署片段 `server/qq-callback.nginx`），Nginx error log 也可能附带原始请求 URL，因此该窄路由同时屏蔽 error log，错误排查使用应用的固定错误码与脱敏状态；应用不得记录原始 URL/provider 响应。登录成功/失败响应使用 no-store 和 no-referrer，并重定向回固定站点页面。

本地 fake-provider、配置存在和 readiness 都不证明 QQ 应用审核或真实登录。发布验收需要真实 QQ 授权回调、账号 A/B 隔离、Chat 和 SimC 实际业务。保留旧微信数据，不做绑定、迁移或数据库删除；Mini 不再作为新发布验收或上传对象。

实施与状态见 [当前 QQ 计划](plans/2026-09-09-web-only-qq.md)。后文仍为各次历史部署和恢复记录。

## 1.0 运维入口（2026-09-08）

1.0 当前实现已获用户验收，当前仓库状态见 [版本说明](releases/1.0.md)。下文带日期的 code/Web 路径、service readiness、容量与清理记录均是当时的快照；其中“当前/现指向”只相对于该记录日期成立。操作前必须重新读取有效 symlink、systemd WorkingDirectory、构建 manifest 和健康状态，不能直接使用最晚一段文字猜当前部署。

2026-09-08 本轮重新核对：Web `current` 指向 `/var/www/chickenbro-web/releases/credit-189d711648c6846df73f07d9aeb2ae7f9766ff15`；`/opt/chickenbro` 指向 `/opt/chickenbro-releases/raider-4315455479566aab7ead4488c52842f3b83c55b1`。源码与当前 main 对应运行面无差异；逐文件 SHA、两个域名 readiness、小程序 `1.0.5` 构建/上传结果见 [本轮对齐记录](../artifacts/verification/2026-09-08-v1-close/alignment/README.md)。历史 `v1-d2a2b752c...` / Mini `1.0.0` 已被后续发布取代。

最近 Web 发布的回滚点为 `/var/www/chickenbro-web/releases/raider-4315455479566aab7ead4488c52842f3b83c55b1`；后端最近发布的回滚点为 `/opt/chickenbro-releases/feedback-5ace442c38f6ec2657c2804f6bf87b96aa46ade5`。操作前核对当前指针及目录存在性，禁止机械使用下面历史发布的回滚命令。微信上传与审核/公开发布分别记录。

日常增量变更按影响范围构建并核对精确文件身份，保留当前回滚包；不得重放下面已完成的 legacy 迁移、切流或清理脚本。SimC 引擎继续只运行于云端。1.0 文档收尾本身不需要修改数据库、Worker 或 SimC runtime。

静态资源仅通过鉴权控制台或签名请求上传到新版本目录，不得为了上传恢复 COS 公有写。已有整改记录见 [COS 安全处理](../artifacts/security/2026-09-08-cos-write-hardening/report.md)；历史请求审计与恢复能力仍是独立待办。

## SimC Raider.IO-only 增量发布（2026-09-08）

源码 `4315455479566aab7ead4488c52842f3b83c55b1` 已发布。代码指针 `/opt/chickenbro` 指向 `/opt/chickenbro-releases/raider-4315455479566aab7ead4488c52842f3b83c55b1`；Web current 指向 `/var/www/chickenbro-web/releases/raider-4315455479566aab7ead4488c52842f3b83c55b1`。仅 SimC application 拒绝新 WCL 导入，保留 Chat WCL 和历史任务。无迁移、引擎或服务配置变更。

服务器独立候选目录 87 项测试通过，27 个公网文件 SHA 匹配，正式接口 Mini/Web WCL 导入 422 且无快照写入，Raider.IO 导入 READY_FOR_SIMC。Mini 1.0.4 已上传；微信审核和公开发布待用户操作。见 [发布结果](../artifacts/verification/2026-09-08-simc-raider-only/publish.json)。

回滚前核对当前指针仍为本次目录并排空任务，停止 API/Worker，代码原子恢复到 `/opt/chickenbro-releases/feedback-5ace442c38f6ec2657c2804f6bf87b96aa46ade5`，Web 恢复到 `/var/www/chickenbro-web/releases/keyboard-c1dfe7bfd94f42fc07d9fe626edd462cbb470cbe`，启动服务并复核健康；不修改数据库或 SimC runtime。

## 回答反馈增量发布（2026-09-08）

源码 `5ace442c38f6ec2657c2804f6bf87b96aa46ade5` 已发布。`/opt/chickenbro` 指向 `/opt/chickenbro-releases/feedback-5ace442c38f6ec2657c2804f6bf87b96aa46ade5`，Web current 指向 `/var/www/chickenbro-web/releases/feedback-5ace442c38f6ec2657c2804f6bf87b96aa46ade5`；迁移 `0006_chat_resolution_feedback` 已应用，公网 27 文件哈希匹配，反馈接口验证通过。Mini `1.0.1` 已上传，微信公开发布待用户后台操作。见 [发布证据](../artifacts/verification/2026-09-08-chat-feedback/publish.json)。

回滚前核对有效指针并排空任务，停止 API/Worker，代码原子恢复到 `/opt/chickenbro-releases/faq-f2932f8b6eb68ea7627ca428e14f460a57ab4ad4`，Web 恢复到 `/var/www/chickenbro-web/releases/simc-layout-27e3dd08b8a75bab`，启动服务并验证。保留新增列和已收集反馈，不反向删除。没有修改既有 dropin 或 SimC 引擎。

## 历史运行与操作记录

历史状态（仅适用于 2026-09-04 六阶段退役，不构成本次授权）：Phase 5 accepted_write、生产 Chat/SimC 双端业务验收、首条新写入核对和稳定健康窗口均已通过。2026-09-04 用户明确授权不制作独立备份并直接永久清理旧目标；云端与本地旧服务/代码/数据已按精确清单完成清理，最终只剩 main/origin parity 与 WeApp 刷新收尾。

本 Runbook 规定如何从 legacy `wow_test` 和旧运行单元迁移到干净 `chickenbro_prod`，如何验证双端数据一致，何时可以切流，以及何时仍然禁止删除。执行者必须同时阅读 [当前架构](chickenbro-simc-architecture.md)、[project-state.json](project-state.json) 和对应阶段的 Harness requirement。

## 当前事实

最新脱敏快照：[chickenbro-simc-cloud-inventory.json](refactor/chickenbro-simc-cloud-inventory.json)；恢复通道只读清单：[chickenbro-simc-recovery-inventory.json](refactor/chickenbro-simc-recovery-inventory.json)

| 项目 | 已记录的只读事实 |
| --- | ---: |
| 根分区总量 | 73,859,022,848 bytes |
| 根分区已用 | 10,710,212,608 bytes |
| 根分区可用 | 60,018,577,408 bytes |
| PostgreSQL 所有非模板数据库合计 | 18,987,054 bytes |
| PostgreSQL 目录 | 120,303,536 bytes |
| 数据库数量 | 2（`chickenbro_prod`、`postgres`） |
| `wow-*` unit 数量 | 0 |
| 容量门禁 | `post_cleanup_complete` |
| 当前目标 identity | Tencent CVM `ins-93tgv1rb` / `ap-shanghai` / `ap-shanghai-2`，SSH alias `wow-lighthouse`，公网 `124.223.51.33` |
| 失效 provider evidence | `lhins-dr6tkl63` / Guangzhou；不属于本目标，不能参与 gate |

这些数字来自 `2026-09-04T07:46:14Z` 清理后 fresh 只读快照，文件 SHA 为 `95937c5c4f3b2be9553ec673bfde7864ba83f132d0285cf7be0c7ca65cd4cdb2`。`wow_test`、候选库、旧 unit、旧 env、旧部署目录和旧 Web evidence 均已不存在；systemd 运行时旧 mask 另行清除 33 个。当前 Active SimC 二进制仍由 `f50a2121bf894570146507496f3e113bff68e445` 身份管理，生产 API/Worker readiness 为 `ready`。本快照证明清理后的目标运行面，不把 HTTP 200 或单个服务 active 当作业务验收替代品。

## 绝对安全边界

- 不读取、打印或提交 env 值、DSN、PGPASS、微信凭据、Codex 配置、Cookie、Bearer、OpenID 或第三方 token。
- 不在有效业务白名单尚未完成迁移、核对、导出、隔离恢复与第二次核对时执行容量预清理；不在已接受生产数据缺少恢复验证或用户明确无备份授权时执行最终退役。
- 四个明确拒绝的 evidence/test 数据库不建立恢复副本，也不上传 COS；其内容在精确容量预清理后不可恢复。它们的删除前恢复权威是 `chickenbro-whitelist-recovery-v1` 业务白名单清单，而不是 evidence 数据归档。
- `wow_test` 已按 accepted_write 后的无备份永久删除授权清理；不得重新创建或恢复为可写主库。
- 不直接手写 `DROP DATABASE`、宽泛递归删除或批量停服务。只有仓库内通过测试的精确 manifest/apply 脚本可以执行变更。
- Candidate、生产切流和 destructive cleanup 分别需要独立证据。前一步完成不自动授权后一步。
- 新系统接受第一条正式写入后，legacy 永久保持只读；不得重新开放旧写入口形成双主。

## 角色与证据

| 角色 | 允许做什么 | 不允许做什么 |
| --- | --- | --- |
| runtime role | 目标 API/Worker 的最小业务读写 | schema/role/database 管理 |
| migrator role | 目标 schema、受控全量/delta、核对 | 读取无关 secret、写 legacy、删除库 |
| operator | 运行已审阅脚本、systemd/Nginx 切换和 smoke | 跳过 manifest SHA、目标 identity 或适用的恢复证明 |
| user acceptance | 真实 Mini/Web 登录、跨端 Chat/SimC 验收 | 代替技术恢复、owner 隔离或迁移核对 |

每个阶段证据至少绑定：branch/commit、release packet、输入 inventory SHA、数据库 migration identity、部署文件 hash、候选入口、回滚 identity、验证命令和实际输出摘要。

## 1. 刷新只读云端清单

在仓库根运行：

```bash
python3 -m unittest tests.chickenbro_simc_cloud_inventory_test -v
ssh -o BatchMode=yes -o ConnectTimeout=15 wow-lighthouse \
  'python3 - --read-only --output -' \
  < server/chickenbro_simc_cloud_inventory.py
```

只允许返回：数据库名称/大小/连接数，unit 名称/load/active/enabled，监听地址/端口/进程名，目录路径/大小，文件系统容量，以及安全的 SHA/version identity。

验证：

1. `status` 必须为 `reachable`，`probeErrors` 必须为空；否则只记录 `partial`/`unreachable`。
2. `observedAt` 必须是本次真实 UTC 时间。
3. `capacityGate` 不是 `capacity_preflight_required` 时，不得创建新库。
4. 输出不得出现 `Environment=`、URL userinfo、DSN、PGPASS、token、Cookie、OpenID 或 secret-shaped key。
5. 复核数据库连接数、legacy units、监听端口和目录体积是否出现未知资源。

快照写入 `docs/refactor/chickenbro-simc-cloud-inventory.json` 后，记录文件 SHA。后续 apply 脚本必须接收并校验这个 SHA，不能只按文件名信任。

## 2. 关闭容量门禁

目标是先证明有效业务白名单可恢复，再释放被明确拒绝的数据占用；不是为拒绝数据建立通用备份设施。允许路径只有：

1. 扩容；或
2. 先完成第 3 节的业务白名单恢复证明，再按 reviewed manifest 精确清理四个 evidence 库和四个 env 伴随项。

容量预清理的数据库 allowlist 固定为：`wow_gear_evidence_01adf184_r14`、`wow_gear_evidence_0be65754_r24`、`wow_gear_evidence_145dee16_r22`、`wow_gear_evidence_15f514d5_r23`。env 伴随项固定为 `/etc/wow-backend-candidate-gear-evidence-r14.env`、`r24.env`、`r22.env`、`r23.env`。`wow_test`、任何通配符、前缀匹配和其他 `wow_*` 库均拒绝。

容量清理清单 [chickenbro-simc-capacity-cleanup-manifest.json](refactor/chickenbro-simc-capacity-cleanup-manifest.json) 的四个精确 evidence 库和四份 env 已完成两次哈希对账并删除；其余完整退役清单按 `d96caa10b07160469c1e652b70783bfaa63e24a8df42833402707054dd3aa8cc` 执行，结果 SHA 为 `58882aeae8e61ab406350f3e4ae0417b9c1b7bd73f722578087da9a6e839a242`。未来 apply 必须重新确认 Tencent metadata identity、fresh inventory、零引用和零连接，已完成 run root 不得重放。

禁止通过删除或写入 `wow_test`、正式部署、唯一 SimC runtime 或唯一回滚包释放空间。拒绝 evidence/test 内容不建立 archive，也不引入 COS、依赖或下载。

## 3. 建立业务白名单恢复证明

容量清理的唯一恢复权威是 `chickenbro-whitelist-recovery-v1`：

1. 用只读、repeatable-read 的 `wow_test` 作为源，把显式业务白名单迁入干净 `chickenbro_prod`；
2. 对迁移结果按 owner、外键、顺序、终态、计数与 hash 做第一次核对；
3. 只导出已迁移的 `chickenbro_prod`，并执行 `pg_restore --list`；
4. 恢复到名称不同的 `chickenbro_restore_verify_*`；
5. 对恢复库运行同一迁移器/核对逻辑，确认第二次结果为 `matched`；
6. 生成 0600、hash-bound 清单，只记录 exact target identity、archive/evidence path、bytes/SHA、时间与核对结果，不记录行内容或 secret。

候选部署和容量清理都必须验证清单本体 SHA、archive SHA/bytes、两份核对证据 SHA，以及 distinct restore target。清单可与 PostgreSQL 位于同一主机，因为它证明的是迁移白名单可恢复性，不冒充整机灾备。四个被拒绝 evidence 库不属于该 archive。

## 4. 建立干净 `chickenbro_prod`

只有 Phase 2 提供并验证 `server/provision_chickenbro_database_lighthouse.sh` 后才能 apply。脚本契约：

- 默认 `--dry-run`；
- 精确目标固定为 `chickenbro_prod`；
- 要求 inventory SHA、management role、0600 PGPASSFILE 与迁移所需的小程序 app context；
- 重新检查 `df`、数据库大小、连接和目标是否存在；
- 只应用 `server/migrations/product`；
- 发现意外 migration identity 或 forbidden schema 立即停止；
- 永远不包含 `DROP DATABASE wow_test`。

创建后验证：

```text
允许 schema: identity, chat, simc, ops
禁止 schema: app, content, cache, knowledge, analytics
允许业务表: 当前架构“数据模型”列出的精确集合
runtime role: 无 CREATE SCHEMA / CREATE ROLE / DROP DATABASE 权限
```

白名单迁移恢复、生产 accepted_write 与清理后 readiness 均已通过；后续不得重放已完成的 destructive run root。

### Provisioning 脚本与当前 dry-run

仓库唯一建库入口是 `server/provision_chickenbro_database_lighthouse.sh`。它固定 source=`wow_test`、target=`chickenbro_prod`，默认只读取已审阅 inventory/project-state 并输出一行 JSON；不会在 dry-run 中检查本机 PostgreSQL 命令、访问数据库或写备份。

```bash
INVENTORY_SHA="$(python3 - <<'PY'
from hashlib import sha256
from pathlib import Path
print(sha256(Path('docs/refactor/chickenbro-simc-cloud-inventory.json').read_bytes()).hexdigest())
PY
)"
bash server/provision_chickenbro_database_lighthouse.sh \
  --dry-run --inventory-sha "${INVENTORY_SHA}"
```

审阅文件已在目标主机完成刷新并绑定清理结果。白名单迁移核对与隔离恢复核对均为 `matched`，root-only 恢复清单 SHA-256 为 `a383d4c32f4edf08360055316c73f451d5b19fe1e81630dbb79b935126f8c818`；四组拒绝 evidence 库及伴随 env 已完成容量预清理，最终 inventory 的容量状态已进入 `post_cleanup_complete`。

只有 `candidateDatabaseProvisioningAuthorized=true`、最新 inventory 为 `reachable` 且无 probe error、target metadata 精确匹配时，才可准备以下命令。当前用户授权已记录为 true，但脚本仍会在任何数据库写入前执行全部 live preflight：

```bash
sudo -E server/provision_chickenbro_database_lighthouse.sh \
  --apply \
  --inventory-sha "${INVENTORY_SHA}"
```

apply 还要求：`WOW_CHICKENBRO_RECOVERY_ROOT` 是 mode=0700 的专用根，`WOW_REBUILD_MANAGEMENT_ROLE` 是已审阅管理角色，`WOW_REBUILD_PGPASSFILE` 是精确 0600 普通文件，既有受管 migration Python（默认 `/opt/wow-mini-program/.venv-v2/bin/python`）可执行，实时根盘满足创建小型目标的最低余量，runtime role 无 database/schema 创建权限，也无 Identity/Chat/SimC/job queue/usage counter 的 DELETE 权限。脚本创建目标并应用 product migrations，运行白名单迁移和第一次核对，然后只对目标库生成 custom archive、执行 `pg_restore --list`、恢复到 distinct verify DB 并第二次核对；最后原子写入 root-only recovery manifest。

如果目标已存在，脚本停止并要求操作者确认一个新的干净目标起点；它不会把旧目标或仅存在的清单冒充本次恢复证明。新目标创建后的迁移失败也不会自动移除数据库，需由操作者只读检查后另行处理。

## 5. 候选全量迁移

迁移器只从明确源表读取，并为每条记录产生：

```text
candidate -> accepted | rejected(reason_code)
```

接受范围：

- 可精确绑定正式 `wechat_mini` identity、非 prototype 的 user；
- owner/外键/角色/顺序/终态合法的 `chat.*`；
- owner、snapshot、scenario、attempt、result 语义合法的 `simc.*`；
- 能确定 owner 和终态的 legacy Chickenbro/SimC 记录，经显式转换后进入目标模型；
- 解释已接受结果所需的最小 provenance/hash。

拒绝范围：

- prototype/demo user、session、票据和候选扫码记录；
- 所有旧 auth session/token/Cookie；
- news/content/cache/WebSim/gear/talent/stat-weight/observed-build/evidence；
- owner、顺序、终态、输入或语义无法确定的记录；
- secret、运行日志、模型思维链或无限期第三方 payload。

迁移保存不可变 source table/source primary key -> target UUID 映射。重复执行必须得到相同 accepted/rejected hash，不得复制记录。

### 白名单迁移器契约

当前唯一转换规则位于 `server/migrations/product/migrate_legacy.py`，核对规则位于 `server/migrations/product/reconcile_legacy.py`。它们是候选迁移的纯规则层，不自行读取 DSN、env 或凭据，也不提供绕过容量/备份门禁的生产 apply 入口。`server/migrations/product/postgres_legacy.py` 是唯一 PostgreSQL adapter：source 使用 `REPEATABLE READ READ ONLY` 快照，target 固定为候选库并在一个事务内完成写入与核对；事务失败时不得留下部分迁移。full/delta 的 through watermark 只能在该只读快照事务内由数据库时间捕获，CLI 不接受外部 `captured-watermark` 覆盖；delta 只接受上一次已封存报告的 `from-watermark`。source/target DSN 均固定为 `wow_app@127.0.0.1:5432/<精确库名>`、URL 内无密码/query/fragment，并只通过 0600 PGPASSFILE 认证；同名远端库、漂移 role/port 或 URL userinfo 一律拒绝。公开报告不包含凭据、provider subject 或原始主键。

每条 source record 的内部输入 envelope 固定为：

```text
table + pk + updated_at + row
```

- `pk` 必须由 source adapter 显式提供且非空，只用于计算 `source_primary_key_hash` 与 UUIDv5，绝不以 row.id 猜测、也绝不进入公开报告；
- `updated_at/pk` 组成全序 watermark。full 使用 `<= through`，delta 使用 `(from, through]`；
- watermark 必须从同一只读快照捕获。写栅栏之后只运行一次最终 delta；
- Identity source 必须已经规范化为 `provider=wechat_mini + app_context + provider_subject`。如果 legacy 只保存了 `wechat_openid`，source adapter 只有在操作者提供且校验了当前正式小程序 app context 后才可做这一步规范化；缺失或不一致时固定拒绝，不能按昵称、UnionID 或“只有一个 AppID”猜合并；
- 同一个 `provider + app_context + provider_subject` 在快照中出现多条 identity 时，相关 identity 全部按 `AMBIGUOUS_IDENTITY_MAPPING` 拒绝；不得挑第一条、按时间覆盖或把两个内部用户合并；
- target UUID 由固定 namespace、source table、canonical pk 和必要的子记录 suffix 生成；
- `app.simulator_tasks` 只有在 owner、`READY_FOR_SIMC` 正式 source、scenario/profile/source hash、compiler/runtime、真实 worker/exit code、终态和正数 DPS/HPS 全部存在时，才展开为 snapshot/job/attempt/result；迁移器不补写 `legacy-worker` 或猜测 exit code；
- `app.chickenbro_sessions/messages` 只有在正式 owner、parent、role、时间和内容均可验证时才转换；assistant 不能早于尚未配对的 user message，AgentRun 的 user/assistant message 必须都属于该 run 的 conversation；
- formal `chat.*`/`simc.*` 仍重新验证 owner、复合父键、终态和 result provenance，不因表名新就直接信任；`succeeded` SimC job 必须在同一稳定快照中存在且仅存在一条 owner、runtime/compiler、scenario、source 与 metric 全部匹配的 semantic result；
- `identity.auth_tokens`、`identity.auth_sessions`、`identity.web_login_sessions`、`identity.prototype_sessions` 只产生稳定拒绝原因，不写目标表。

每条接受记录写入一条 `ops.audit_events`：

```text
event_type = legacy_migration.accepted
subject_key = <source_table>:<source_primary_key_hash>
UNIQUE(event_type, subject_key)
```

payload 只能包含 migration revision、哈希、目标表、目标 UUID 和展开后的目标引用。不得包含 OpenID、UnionID、旧主键、token hash、source URL userinfo 或原始第三方 payload。重复 full/delta 必须保持映射唯一；identity 既有 `provider/app_context/provider_subject` 不得被重绑；任一正式 unique key 冲突或不可变 message/result 内容冲突都必须使目标事务整批停止，不能挑一条、覆盖或留下部分数据。

本地规则验证：

```bash
python3 -m unittest \
  tests.legacy_product_migration_test \
  tests.postgres_legacy_migration_test -v
```

fixture 同时覆盖正式 direct Chat/SimC、owner-bound legacy Chat、可发布 legacy SimC、prototype/auth/无关域拒绝、显式 pk、重复 identity 拒绝、会话顺序/归属、真实 worker/exit code、READY source、semantic result、UUIDv5 幂等、同时间戳 `updated_at/pk` delta 和报告脱敏。fixture 通过不是生产迁移证据；真实候选仍需事务、数据库约束和逐域核对。

## 6. 逐域核对

全量和 delta 都必须分别核对：

| 域 | 必须一致的内容 |
| --- | --- |
| Identity | accepted/rejected user、provider mapping、prototype 排除、无旧 session |
| Chat | owner、conversation、message role/order/content hash、AgentRun 终态 |
| SimC | owner、snapshot/source hash、job/scenario、attempt、result metric/provenance |
| Ops | migration mapping、queue 空闲/终态、audit redaction |

只比较数据库总行数不合格。核对报告必须包含 candidate/accepted/rejected 数量和稳定拒绝原因，且不能包含 provider subject 或 credential 明文。

`reconcile(...)` 的 `matched` 只在以下计数全部为零时成立：source drift、accepted target count/hash mismatch、mapping missing、owner/FK violation、message order/content hash mismatch、SimC snapshot/job/attempt/result semantic mismatch。任一项非零都输出 `diverged` 和稳定 `violationHash`；不得把部分相符、总行数相同或重复运行无异常写成核对通过。

## 7. Candidate 部署与双端验证

Candidate 必须隔离数据库、API port、systemd unit、Nginx path 和 Web root，不读取或写入生产库。记录：

- commit 和远端逐文件 hash；
- candidate DB/migration identity 与 forbidden schema 结果；
- API/Worker/SimC runtime identity；
- `/health` 与逐组件 readiness；
- Mini Bearer 与 Web Cookie 对同一测试 identity 解析为同一内部 owner 的脱敏证明；
- 第二用户 owner 隔离；
- Chat create/list/get/stream、SSE sequence、幂等和 Codex 失败语义；
- SimC snapshot/readiness/submit/list/detail、Worker lease、有效结果和失败语义；
- H5/WeApp 构建 identity、候选入口和回滚路径。

静态页面、QR 图片、Cookie 存在或候选 API 200 不能代替真实扫码。真实用户必须在小程序确认 Web 登录，并在两端交叉创建/查看/继续 Chat 与 SimC。

### 候选部署入口

仓库唯一候选入口是 `server/deploy_chickenbro_candidate_lighthouse.sh`。默认 `--dry-run` 只读取本地 commit 与当前 inventory，不访问云端、不构建、不写入：

```bash
bash server/deploy_chickenbro_candidate_lighthouse.sh --dry-run
```

只有最新 inventory 为 `reachable`、无 probe error、`capacityGate=capacity_preflight_required`，且操作者已审阅 `chickenbro-whitelist-recovery-v1` 清单后，才可准备 apply：

```bash
bash server/deploy_chickenbro_candidate_lighthouse.sh \
  --apply \
  --expected-commit "${CANDIDATE_COMMIT}" \
  --inventory-sha "${INVENTORY_SHA}" \
  --recovery-manifest-sha "${WHITELIST_RECOVERY_MANIFEST_SHA}"
```

脚本拒绝 dirty worktree、宽松 commit、不匹配的 inventory/recovery manifest SHA、错误 Tencent metadata identity、legacy async sync、容量不足和非精确 Nginx owner。它只创建/替换以下隔离面：

- `/opt/chickenbro-candidate`、`chickenbro_candidate`、loopback `8791`、`chickenbro-api-candidate.service`；
- `chickenbro-worker-candidate.service` 与 `/etc/chickenbro-worker-candidate.env`，不停止、不改写正式 `chickenbro-worker.service` 或 `/etc/chickenbro-worker.env`；
- `/var/www/chickenbro-candidate/releases/<manifest-sha>` 和 `/web-candidate/`；
- 两个现有 server block 内带 marker 的 `/api/v2-candidate/` 路由。

H5 和 WeApp 必须从同一 clean commit 重新构建，使用统一候选前缀 `/api/v2-candidate`、公共 API origin `https://api.chickenbro.cloud` 和候选专用 CSRF Cookie 名。两个完整目录 identity、WeApp `wow-build.json`、source archive、逐文件 manifest、部署后 manifest、systemd/Nginx/Codex/SimC identity 都写入 root-only 候选证据；只对 `index.html` 哈希不合格。

部署中的自动化验收由 `server/accept_chickenbro_candidate.py` 执行，输出 `automated-acceptance.json`。它在候选库中签发短期测试 Bearer 与已确认的单次 Web ticket，通过真实公网候选路径验证：

- 同一正式迁移 owner 的 Mini Bearer 与 Web Cookie/CSRF；
- Mini 创建、Web 查看/续聊，以及 Web 创建、Mini 查看/续聊；
- 两个方向的 SimC 创建、历史可见、Worker 终态和正数 DPS/HPS 语义结果；每个 job/result 必须逐字段绑定提交的 snapshot/scenario hash、正式 compiler revision、runtime revision、profile SHA 和 source provenance，最终 attempt 必须为 `exitCode=0`/`SUCCEEDED`；
- Chat 幂等重放、ticket replay 拒绝、Web logout 不撤销 Mini session；
- 第二个隔离 owner 的列表和直接对象读取都不可越权。

自动化验收只证明正式 API、两种 credential transport 和 owner-scoped 数据链路，明确保留 `realWechatQrAcceptance=pending` 与 `realDeviceAcceptance=pending`。它不调用 `wx.login`，也没有在真实小程序中扫描或确认 QR，因此不得写成真实扫码成功。经本轮用户明确授权，双端验收可使用 `server/accept_chickenbro_dual_client.py` 记录 `loginMode=user_authorized_skipped`：它继续真实执行 Web Cookie 与 Mini Bearer 的跨端 Chat/SimC、owner 隔离、退出和重启恢复，并在报告中把 `realWechatQrLogin.status` 固定为 `skipped`，绝不伪造 QR 通过。

Chat SSE 的每个事件都必须有从 1 开始连续递增的整数 `sequence`，首尾必须是 `started`/`completed` 且不得夹带 `failed`；缺 sequence 的“成功文本”不能形成验收证据。SimC 仅凭 job id、`succeeded`、正指标和 return code 0 同样不合格，缺失上述 provenance 绑定时自动化验收必须失败关闭。

部署脚本必须解析 loopback、`www` 和 `api` 三份 readiness JSON，要求语义一致、`database` 与 `wechat_mini` 为 `ready`，且任何组件都不能是 `blocked`。如果总状态仍是 `partial`，证据必须记为 `partial_not_promotable`：可以保留候选环境供诊断，但不得称为 ready、验收成功或允许切流。顶层候选状态始终是 `candidate_deployed_user_acceptance_pending`，直到真实双端用户验收和后续切流门禁全部单独通过。

完整 `ready` 还要求候选 Worker 已成功访问候选队列并持续刷新 `candidate-worker-heartbeat.json`，Codex revision 与本机 binary SHA-256 一致，WCL v2 OAuth client credentials 完整，Raider.IO dependency 可加载，以及 `/opt/wow-simc/current` 的 content-addressed release metadata 与实际 binary hash、compiler/spec 配置一致。Worker unit 启动前会移除旧环境心跳；心跳缺失、跨环境、格式非法、未来时间或超过 45 秒均失败关闭。以上是无外部请求的配置与本地 liveness 证据，不替代随后真实 Codex、WCL/Raider.IO、SimC 和微信链路 smoke。

### 体验版扫码验证（2026-09-07）

用户明确授权正式 Web 使用小程序体验版验证真实微信登录。正式 API 原配置为 `WOW_WECHAT_ENV_VERSION=release`、`WOW_WECHAT_CHECK_PATH=1`；微信取 token 成功，但二维码请求返回 `41030 invalid page`。现在通过独立配置 `/etc/chickenbro-wechat-trial-20260907.env` 设置 `WOW_WECHAT_ENV_VERSION=trial`、`WOW_WECHAT_CHECK_PATH=0`，由 `/etc/systemd/system/chickenbro-api.service.d/95-wechat-trial-20260907.conf` 最后加载。未修改原 release 配置、身份映射、会话安全或测试账号开关；部署源码仍为 `1862e167fafa0469888c3b2b489a8799ae19a799`。

已重启正式 API 并检查实际进程配置；`api` 与 `www` 两域名的七项 readiness 全部 ready，正式 Web 真实创建登录请求成功并显示等待扫码，返回完整 430 × 430 JPEG 小程序码。页面显示存在裁切，已单独提供原图用于本次扫码，布局问题待修复。扫码者需有体验权限，体验版需包含 `pages/auth/web-login-confirm` 并连接正式 API；平台体验版设置、手机扫码确认及跨端用户验收仍待完成，不将二维码生成成功记为登录成功。

恢复正式版二维码时，只移除上述两个本次新增配置文件，执行 `systemctl daemon-reload` 并重启 `chickenbro-api.service`，验证实际配置恢复为 `release` / `1`、两域名 readiness 和新二维码。恢复前应先确认微信正式版已包含登录确认页，否则将再次出现原错误。

### 真实用户验收

必须使用 apply 证据中相同的 commit、H5 identity 和 WeApp identity，并确认测试版确实包含 `pages/auth/web-login-confirm`。本轮已由用户授权跳过测试版二维码登录；因此使用 `loginMode=user_authorized_skipped` 的双端 transport 验收，不把它描述成扫码成功。若未来恢复真实扫码，流程固定为：

1. 小程序通过 `wx.login` 获得正式 Mini session；
2. Web 创建 QR，用户在小程序确认，Web 成功建立独立 HttpOnly Cookie；
3. Mini 创建会话并发送消息，Web 重载后可见且可继续；Web 新建另一会话后 Mini 重载可见且可继续；
4. Mini 与 Web 分别提交一个 SimC，另一端可见相同任务、状态、attempt 与 semantic result；
5. Web 退出后 Mini 仍登录；不同微信 owner 不能看到上述对象；
6. 记录用户明确确认、UTC 时间、route 名、commit、双端 build identity 和对象脱敏 hash，不记录 OpenID、内部 user id、Cookie、Bearer、ticket 或 verifier。

扫码模式必须有真实扫码和双设备交叉验证；本轮授权跳过模式由机器跨 transport evidence 替代这两个不可执行步骤，但仍必须有用户明确确认。任一模式缺少对应证据时，状态只能是 `user_acceptance_pending`。授权跳过只改变登录证据字段，不降低 Chat/SimC 跨端、owner、退出、重启和首写门禁。

### SimC runtime 更新

生产切流会停止、禁用并运行时屏蔽旧 updater/version-check unit，再安装 `chickenbro-simc-runtime-update.service`；SimC 二进制和当前指针保持可用。新 unit 不会被 enable、start，也不会创建定时器。没有 `/run/lock/chickenbro-simc-runtime-update.env` 时该静态 unit 失败关闭；旧 unit 文件只有在新 unit 已安装、当前 runtime identity 已备份且 Phase 6 全部门禁满足后才能退役。切流在不可逆边界前失败时，会恢复旧 unit 文件与原有 active/enabled 状态。

默认预检只读取当前 commit，不访问网络：

```bash
/opt/chickenbro/server/chickenbro_simc_runtime_update.sh \
  --dry-run \
  --target-commit "${REVIEWED_TARGET_COMMIT}"
```

真正更新必须先从外部权威确认目标 commit，并记录当前 `/opt/wow-simc/current/.commit` 或兼容 `.commit`。只有目标 commit、预期当前 commit、至少 12 GiB 空闲空间和下载/构建授权都已审阅时，才创建一次性、非 secret 的 trigger：

```bash
sudo -u ubuntu sh -c '
  umask 077
  printf "SIMC_TARGET_COMMIT=%s\nSIMC_EXPECTED_CURRENT_COMMIT=%s\n" "$1" "$2" \
    > /run/lock/chickenbro-simc-runtime-update.env
' _ "${REVIEWED_TARGET_COMMIT}" "${REVIEWED_CURRENT_COMMIT}"
sudo systemctl start chickenbro-simc-runtime-update.service
```

unit 只接受固定 `simulationcraft/simc` 的精确 commit，不查询或跟随 branch。成功后会删除 trigger，保留旧 release，不重启 API/Worker，并输出 previous/target commit、source archive SHA 或旧 release 的 `legacy-unavailable` 状态、binary SHA 和 `servicesRestarted=false`。必须另行核对 `readlink -f /opt/wow-simc/current`、release metadata、binary hash、API readiness，并提交真实 SimC smoke；systemd 成功不代表模拟业务成功。

如果新 runtime 的语义 smoke 失败，使用同一入口把 target 指回已验证的旧 release，并把 expected-current 固定为失败的新 commit。已有 release 的回切不下载、不重建，也不受构建空间门禁影响；禁止删除失败 release 或唯一可恢复 release来“修复”问题。

## 8. 写栅栏、delta 与切流

切流窗口固定顺序：

1. 确认候选、容量、全量迁移和真实用户验收均已通过；恢复门禁使用已接受生产恢复证据，或使用本轮用户明确授权的无备份模式。
2. 把 legacy 产品写入口置为只读，保留健康/读取和明确维护文案。
3. 记录 write watermark、活动连接、队列和运行中 job。
4. 等待/收口允许完成的 job，执行唯一一次只读 delta。
5. 重新运行逐域核对，要求无未解释差异。
6. 原子切换 API/Worker DSN、systemd 和 Nginx 到新部署 identity。
7. 验证只有新路径可写，legacy 仍只读。
8. 在公开新写入口前落盘 `WRITE_AUTHORITY_BOUNDARY`；从此即使尚未观测到第一条写入，恢复策略也保守地禁止重新开放 legacy 写入。
9. 使用真实 Mini/Web 完成生产双端 Chat/SimC、owner 隔离、退出和重启恢复验收；验收文件必须绑定 `switched` 证据 SHA、同一 commit 和双端 build identity，并记录真实 `firstAcceptedWriteAt`。
10. 仅在上述生产验收及用户明确确认都通过后，以 `--seal-accepted-write` 把状态从 `switched` 单向推进到 `accepted_write`。开放写入口的边界时间不能冒充实际首条写入时间。

任何步骤失败都停止推进，不跳到删除。

## 9. 回滚规则

### 第一条新生产写入之前

可以原子恢复上一部署包、旧 DSN 和旧写入口，但必须先确认 delta 尚未产生新主数据。回滚后记录 Nginx/systemd/DSN identity、旧库可写状态和新库保持隔离。

### 第一条新生产写入之后

禁止把 legacy 恢复为可写，也不做反向同步或双向合并。故障处理优先：

1. 回滚/修复新代码但继续使用 `chickenbro_prod`；
2. 保护新库 WAL/audit/write log；
3. 必要时提供 legacy 只读降级页；
4. 从新主数据面的恢复点恢复。

这条边界避免双主、覆盖和跨端历史分叉。

实际操作分成两个不可混淆的状态：`--apply` 最多产出 `switched` 和 `production_acceptance_pending`；随后使用精确的 `production-cutover.json`、`production-user-acceptance.json` 及二者 SHA 执行 `--seal-accepted-write`。seal 会再次确认 legacy 只读、新库可写、正式 API/Worker active、readiness、真实微信扫码或本轮授权跳过、跨端 Chat/SimC、owner 隔离、独立退出、服务重启恢复和用户明确确认。任一证据字段、时间顺序、route、build identity 或 secret-redaction 不满足时失败关闭。

## 10. Legacy 退役

容量预清理是唯一可在 Phase 5 前执行的例外；它只包含四个精确 evidence 库及四个精确 env 伴随项，并要求白名单恢复清单、fresh target identity、fresh size/connection/reference/open-handle 证据和 reviewed SHA 全部成立。除此以外，只有以下条件全部满足才可进入完整 Phase 6 apply：

- 正式切流稳定窗口结束；
- 真实 Mini/Web Chat 与 SimC 验收有明确用户确认；
- 新库备份和恢复演练通过，或 cleanup manifest 记录本轮无备份永久清理授权；
- legacy 无连接、无 open handle、无 systemd/Nginx/env/caller 引用；
- 文档链接图和代码 caller graph 对每个删除目标为零；
- cleanup manifest 列出精确路径/库/unit/env、hash/bytes/reason/restore identity；
- manifest SHA 与 apply 参数一致；
- 回滚包保留窗口有书面状态。

当前云端精确控制文件是 [chickenbro-simc-cloud-cleanup-manifest.json](refactor/chickenbro-simc-cloud-cleanup-manifest.json)。最终清单绑定清理前 reviewed SHA `d96caa10b07160469c1e652b70783bfaa63e24a8df42833402707054dd3aa8cc`、执行结果 SHA `58882aeae8e61ab406350f3e4ae0417b9c1b7bd73f722578087da9a6e839a242` 和清理后 reachable inventory；113 个目标中 1 个在最终运行实际删除、112 个此前已不存在，旧 runtime mask 另行清除 33 个。清理结果不制作独立备份，生产 `chickenbro_prod`、API/Worker、当前 Web、TLS 和 SimC runtime 未触碰。

本地评审入口默认只解析清单，不连接云端、不停服务、不删数据：

```bash
npm run test:ops
bash server/retire_chickenbro_legacy_lighthouse.sh \
  --manifest docs/refactor/chickenbro-simc-cloud-cleanup-manifest.json \
  --dry-run
```

当前清单记录 `deletionAuthorized=true`、`status=cleanup_complete`、`unresolvedRequiredTargets=[]`，清理后 fresh inventory 为 `reachable`，旧数据库与旧 unit 均为 0。容量 scope 已关闭，dry-run 返回 0 个 pending 目标；未来不得对已完成 run root 重放 destructive apply。

apply 只接受精确名称。已完成的容量 scope 先将 env 逐个移到同主机 `/var/lib/chickenbro-retirement-quarantine/<manifest-sha>` 并确认原路径不存在，再逐库检查 `pg_stat_activity`、实时大小和当前配置/进程引用，以引用安全的精确 identifier 执行删除；四组均已写入 `completedPairs`，不会进入新的执行计划。完整 Phase 6 默认会把 unit、旧文件和目录移动到精确 quarantine；本轮用户已选择无备份永久删除时，必须同时传入 `--no-independent-backup` 与确认词 `I_UNDERSTAND_NO_BACKUP_IS_IRREVERSIBLE`，脚本会在同样的依赖、引用、SHA/realpath 和生产健康检查之后删除精确目标，不保留旧目标副本。无论哪种模式，都不会删除 Chickenbro 新生产、SimC runtime、PostgreSQL 数据根、TLS 或当前 Nginx owner。

退役顺序：停止并禁用 legacy unit/timer；移除 candidate/prototype；精确删除无引用数据库；删除旧部署/静态/数据目录；执行绑定 SHA 的本地旧代码/文档/测试清理；刷新本地/云端清单和 parity。不得对 `/opt`、`/var/lib`、数据库前缀或仓库根做宽泛递归删除。

## 11. 最终验证与完成

最终证据必须同时包含：

- 本地 `main` 与 `origin/main` SHA 相同；
- 云端 deployable tracked set 和 runtime overrides 与发布 identity 相同；
- `chickenbro_prod` migration identity、允许/禁止 schema 和 runtime role 权限；
- systemd/Nginx/listener/DB 连接只指向目标运行面；
- API/Worker/SimC 语义 smoke；
- 两个用户的 owner 隔离；
- 同一用户 Mini/Web 的 Chat 与 SimC 双向同步；
- 备份恢复或明确无备份授权，以及清理后的最新 inventory；
- 旧 route、unit、timer、数据库、目录和文档/代码 manifest 目标全部不存在；
- 用户明确确认真实双端结果。

未满足任一项时，状态只能是 `blocked`、`candidate_pending`、`user_acceptance_pending` 或 `cleanup_pending`，不能写“整体完成”。

## 故障定位

| 现象 | 先检查 | 结论边界 |
| --- | --- | --- |
| Web 扫码后不登录 | 小程序页是否已发布、ticket 状态、verifier、Origin、Cookie 属性 | prototype bypass 或 QR 可见不是登录完成 |
| 两端历史不同 | 两端 Principal 的内部 owner、游标、水位、迁移 mapping | 不按昵称/OpenID 猜合并 |
| SimC return code 0 但无结果 | metric parser、profile/runtime identity、fatal diagnostic | return code 0 不是业务成功 |
| Worker active 但任务不动 | queue status、lease owner/expiry、handler、attempt/max attempts | systemd active 只证明进程活着 |
| 空间仍不足 | 刷新 df/DB/目录清单、白名单恢复证明、精确容量 scope、回滚保留量 | 不删正式库/唯一恢复点绕过 |
| 切流后需要回退 | `firstNewProductionWriteAt` 是否存在 | 有新写入后 legacy 永不恢复为写主 |

## 相关文档

- [当前架构](chickenbro-simc-architecture.md)
- [验证矩阵](verification-matrix.md)
- [项目状态](project-state.json)
- [本地处置清单](refactor/chickenbro-simc-refactor-inventory.json)
- [云端只读清单](refactor/chickenbro-simc-cloud-inventory.json)
- [云端退役清单](refactor/chickenbro-simc-cloud-cleanup-manifest.json)
- [当前六阶段计划](plans/README.md)

## 原生 Codex 模型配置（2026-09-05）

同日长回复改进：Chat adapter 改为每请求 `codex app-server --listen stdio://`，通过现有 Chat SSE 传递真实正文增量；不新增常驻服务。0.153.4 的 app-server 不接受 CLI profile，因此服务端使用标准库读取当前 `CODEX_HOME/<profile>.config.toml`，在内存中传入 `thread/start.config`，保留模型与 MCP 配置，显式保持 read-only 和 never；行为规则通过 `developerInstructions` 注入。仅最终答复阶段的正文进入客户端，重试通知继续沿用同一截止时间，完整正文一致且 turn 成功后才完成。具体部署身份与回滚另记本次任务证据；以下 exec 描述为该日较早的历史验证。

用户要求云端切换 Astra／高。已通过现有 `codex update` 将官方独立安装从 `0.146.0` 升级到 `0.153.4`，未安装业务依赖；旧版本保留在 `/home/ubuntu/.codex/packages/standalone/releases/0.146.0-x86_64-unknown-linux-musl/bin/codex`。旧 CLI 对 Astra 返回明确的需要升级错误，已用升级后真实调用验证。

当前 `/home/ubuntu/.codex/config.toml` 及 `chickenbro-native.config.toml`、`chickenbro-candidate.config.toml`、`chickenbro-production.config.toml` 均设置：

```toml
model = "gpt-6-astra"
model_reasoning_effort = "high"
```

正式和测试 API 当前都选择 `WOW_CODEX_PROFILE=chickenbro-production`，每次消息创建新 `codex exec`，没有覆盖模型的 CLI 参数。配置逐文件原内容备份后缀为 `.before-astra-high-20260905T030752Z`。其余配置键和现有认证保持不变。

已将 `/etc/chickenbro-api.env` 的 `WOW_CODEX_RUNTIME_REVISION` 同步为 `codex:sha256:56ef98ab4032d317ab26e9b5e5a175650717351edb16ed9cde0cb6d1734d62da`，确认无运行中的 Codex 调用后重启正式/测试 API。两端 readiness 为 ready；不传模型覆盖参数的 CLI 输出确认 `gpt-6-astra` / `high`，现有 `NativeCodexChatAdapter` 的实际 JSONL 调用返回正常 completed 文本。该检查不等同于完整 Chat/SimC 用户验收。

手工云端诊断必须使用服务已有的代理环境（只在进程内传递，禁止打印代理或认证值）。普通 SSH shell 未继承这些配置，可能出现网络超时，不应误判模型不可用。

模型切换时尚无独立业务 AGENTS.md；同日后续任务已将 `_prompt` 固定规则迁入 [炸鸡队长行为规则](../server/app/chickenbro/agent/AGENTS.md)。Chat adapter 每次启动前读取固定文件（UTF-8，最多 32 KiB），通过 CLI `-c developer_instructions=...` 注入。文件缺失、空白、不可读或超限则返回 `CODEX_UNAVAILABLE`，不启动无规则会话。接入使用官方 [developer_instructions 配置](https://learn.chatgpt.com/docs/config-file/config-reference)；它是会话级开发者指令。用户历史以独立 JSON 输入，保留最近 20 条、每条 4000 字符边界。

规则只讨论魔兽世界、精炼作答，并保留专用来源 API、检索上限和如实说明未知的要求。它不替代服务端 owner、工具 capability 或 sandbox 权限，也不作为服务器全局工程指南。修改仓库规则并部署后，新请求读取新内容；已经运行中的请求保留启动时的版本。采用临时文件加原子替换更新，避免读取半写文件。

初始规则接入 commit 为 `1209850cdb6b601669706602603156a00c15d493`。当时测试 current 指向同名 release，继承 `83b9684b605fa2496db14b81eceb18dc40424c9b` 的 Web 构建，仅覆盖三个 Python 接入文件和规则文件；正式 `/opt/chickenbro` 同样只应用四文件 overlay，不表示整个测试登录分支已部署或 main 已合入。两处 `AGENT_RULES_PATCH.json` 记录该阶段 commit、文件 SHA 与来源。

正式回滚副本及清单：`/var/lib/chickenbro/agent-rules-backups/1209850cdb6b601669706602603156a00c15d493/manifest.json`。回滚前核对当前四文件 SHA 与清单，确认无运行中 Chat；按清单恢复三个原 Python 文件，并移除本次新增的单个规则文件，再重启 `chickenbro-api.service`。测试回滚则将 current 原子切回上述旧 release 并重启 `chickenbro-test-api.service`。检查实际地址 `/api/v2/health/readiness`；初次测试部署因检查地址写错曾自动回滚，修正后重新切换成功。数据库、模型配置和客户端内容不参与本次回滚。

回退时将上述四份配置恢复到对应备份内容；若同时回退二进制，应恢复既有安装链接到保留的旧版本，并同步 runtime revision 后重启两个 API、再次检查 readiness。旧 CLI 不支持 Astra，因此不得只降级二进制而保留 Astra 模型配置。

## 自动来源 API 修复（2026-09-05）

首轮来源 overlay 为 `491d5379c5e7766f8e9260e3c6c9e7d8036c73f5`，五文件 manifest 位于正式/测试根 `SOURCE_API_PATCH.json`，覆盖早期 AGENT_RULES_PATCH 对应文件记录。当时测试 current 为同名 release，Web 继承 `f144923c0a1ffb4c21aad4567f3e9e443b3b036d` 顶栏构建；正式仅更新五文件，没有带入测试登录代码。

MCP 支持固定本机网关 8790/8791/8792；测试仍选用已有 production profile 的 MCP 脚本，但每次调用的 capability 和 8792 目标由测试 API 注入。WCL OAuth 凭据继续仅存在 API 进程。能力通过已接入工具提供，AGENTS 不负责读取密钥。来源 API 与角色技能统计、真实 Codex 主动两次查询均已验证，详情及回滚见 [自动来源验证](../artifacts/releases/2026-09-05-chickenbro-agent-rules/auto-sources.md)。

### 消息渲染与数据补查

消息与 WCL 数据层 release 为 `ce7b924ff7344a1ed9d4b6bad500513ce8b96e39`。当前测试 release/Web 为 `c4b6d4b0f24c40ba4e67ffe3ffbf778a48f9ade5`，追加配套超时修正；正式 Web 保持原构建。正式/测试五文件数据层增量见 `CHAT_RENDER_PATCH.json`，后续两个后端文件以 `CHAT_DEADLINE_PATCH.json` 为准，对应文件身份优先于历史 overlay。

WCL 工具支持 `options.dataType/startTime/endTime/limit`；时间为报告相对毫秒，每页最多 1000。按 `nextPageTimestamp` 继续时保留事件类型和终点；省略终点时服务端自动查询战斗边界，避免 WCL 返回误导性的空页。表格与角色资料按整场 fight/source 查询，事件过滤时间独立。指定 source 才返回该角色的装备、天赋、属性详情；不指定 source 返回角色摘要供自主选择。gameVersion/logVersion 不能代替补丁号。

回滚副本：`/var/lib/chickenbro/chat-render-backups/ce7b924ff7344a1ed9d4b6bad500513ce8b96e39/manifest.json`。先核对当前五文件 SHA 并确认没有运行中 Chat，再按清单恢复正式文件；测试 current 原子切回 `491d5379c5e7766f8e9260e3c6c9e7d8036c73f5`，重启两个 API 并验证 readiness。保留数据库、会话、模型与凭据。详见 [验证记录](../artifacts/releases/2026-09-05-chickenbro-agent-rules/chat-render.md)。

多轮分析采用后端 480 秒、客户端 510 秒、Nginx 540 秒、capability 600 秒的配套预算；运行结束立即撤销 capability。超时层回滚清单为 `/var/lib/chickenbro/chat-deadline-backups/c4b6d4b0f24c40ba4e67ffe3ffbf778a48f9ade5/manifest.json`，含两个后端文件和四个 Nginx 文件原值/SHA。若撤回整轮，先恢复超时层（测试切回 ce7b924f，恢复 Nginx 并 nginx -t/reload、重启 API），再恢复上一层。旧客户端仍保留原等待上限，后续正式 Web/Mini 发布时须使用配套版本。

### 精简防御性表达

规则增量 `91fb8ed167c2065c048ff9fb1f59d3e9821686ae` 已原子同步至正式/测试 AGENTS.md；规则身份以两处 `RESPONSE_STYLE_PATCH.json` 优先。无需重启，新 Chat 请求读取新规则。仅在影响当前建议时解释不确定性，去掉例行版本/免责声明、工具过程汇报、自我表态和装饰性引用。

两组真实 Astra/high 样例验证：直接操作建议无无关尾注，无法量化收益时仍说明必要缺失；[样例](../artifacts/releases/2026-09-05-chickenbro-agent-rules/concise-samples.json) 是给定事实的规则测试，不是新的完整 WCL 复盘。正式/测试文件 SHA 一致、健康 ready。回滚按 [清单](../artifacts/releases/2026-09-05-chickenbro-agent-rules/concise-deployment.json) 核对当前规则 SHA 后，分别原子恢复 `/var/lib/chickenbro/response-style-backups/91fb8ed167c2065c048ff9fb1f59d3e9821686ae/` 内 production/test-AGENTS.md；历史对话不改写。


### 账号头像预览（2026-09-07）

隔离 `chickenbro_test` 已通过实际 PostgreSQL / wow_app 保存、同 owner Mini/Web 读取、第二用户隔离及事务回滚验证。正式库新增 `0003_account_avatar` 可空字段，旧 API 仍兼容。生产 API 通过 `/etc/systemd/system/chickenbro-api.service.d/99-avatar-preview-20260907.conf` 指定 WorkingDirectory `/opt/chickenbro-releases/avatar-preview-5b925e99c4eb1547`；它以 `1862e167f` 运行目录为基础，只叠加六个头像相关服务端/迁移文件，具体 SHA 见 [证据](../artifacts/releases/2026-09-07-shared-account-avatar/verification.json)。此为源码哈希绑定的未提交预览，不冒充新的 Git 发布提交。Worker 与原 `/opt/chickenbro` 指针保留，扫码仍使用先前授权的 trial 配置。

Web 仅更新 `/previews/login-home-20260907/`，当前目标 `/var/www/chickenbro-web/previews/login-home-20260907-avatar-a613d6385820`。小程序仅生成开发预览，既有上传体验版未替换；真实手机头像选择待用户完成。

回滚：仅移除 `99-avatar-preview-20260907.conf`，执行 daemon-reload 并重启 `chickenbro-api.service`，再核对 readiness。保留头像列和用户保存的数据，不做反向破坏性迁移。Web 链接可原子指回 `/var/www/chickenbro-web/previews/login-home-20260907-v2`。不要移除同目录中 `90-release-20260907.conf` 或 `95-wechat-trial-20260907.conf`。


### 正式 Web 默认标题栏修复（2026-09-07）

用户要求移除遮挡导航的黑色 Taro 标题栏。`/var/www/chickenbro-web/current` 当前指向 `/var/www/chickenbro-web/releases/formal-nav-fix-20260907`，以原 `1862e167f` Web 为基础，仅在 `css/app.css` 加入已有 Web 专属标题栏隐藏/占位修复，并在 index 样式链接加 `?nav=20260907`。原 Web 目录和预览 symlink 保留，API/Mini 不变。回滚只需原子指回原 Web 目录。详见 [哈希及页面验证](../artifacts/releases/2026-09-07-web-login-home/formal-nav-fix.json)。


### 完整新版首页发布正式根路径（2026-09-07）

用户反馈退出后显示旧首页，已纠正此前只上线预览/标题栏样式的发布遗漏。`/var/www/chickenbro-web/current` 现指向 `/var/www/chickenbro-web/releases/formal-home-20260907-a53072694a0a`，包含完整新版首页及头像客户端。API/Mini 本步骤不变，原独立预览 symlink 保留；入口资源加 `v=home20260907`，index/JS/CSS 均 no-cache。25 个文件 SHA 与正式浏览器二维码/文案检查见 [发布记录](../artifacts/releases/2026-09-07-web-login-home/formal-home-release.json)。回滚可原子指回 `/var/www/chickenbro-web/releases/formal-nav-fix-20260907`，但该旧包未包含新版未登录首页，回滚时必须明确告知这一用户可见差异。

### 2026-09-07 正式首页固定一屏布局

`/var/www/chickenbro-web/current` 现指向 `/var/www/chickenbro-web/releases/fixed-home-20260907-649f647d696a`，入口版本 `v=fixedhome20260907`。登录首页固定视口，清理下方说明并缩小卡片；登录后解除滚动锁。25个文件哈希匹配，正式真实二维码及4组视口布局验证通过。API/Mini与独立预览未变。回滚原子指回 `/var/www/chickenbro-web/releases/formal-home-20260907-a53072694a0a`，旧目录保留。见 [发布记录](../artifacts/releases/2026-09-07-web-login-home/fixed-layout-release.json)。

2026-09-07 首页署名补充：当前 Web root 为 `/var/www/chickenbro-web/releases/home-credit-20260907-ce49e8b603d1`，入口 `v=credit20260907`，回滚点为上节 fixed-home 目录。移除右上文案并增加底部署名，25文件哈希匹配，API/Mini未变。见 [发布记录](../artifacts/releases/2026-09-07-web-login-home/credit-release.json)。

2026-09-07 小程序头像入口补充：开发者工具已上传 `2026.09.07-avatar2`，465491 bytes，正式 API、关闭测试账号入口。头像选择提前到确认前且可跳过。微信后台版本管理被浏览器安全策略阻止，**未验证设为体验版**；需用户选择此版本后才能用正式 Web 的 trial 二维码验证。未提交微信审核/发布，本步骤 API/Web 不变。见 [上传证据](../artifacts/releases/2026-09-07-shared-account-avatar/mini-upload-avatar2.json)。

2026-09-07 确认页视觉更新：已上传 `2026.09.07-avatar3`（1006698 bytes），Web鸡哥Logo与暖白风格，头像选择保留用户点击、已保存头像自动恢复。实际开发者工具渲染和保存头像恢复通过；真实手机新样式与设为体验版待用户完成。原头像API及正式Web不变。见 [构建与上传记录](../artifacts/releases/2026-09-07-shared-account-avatar/mini-upload-avatar3.json)。

2026-09-07 扫码确认后自动进入：已上传 `2026.09.07-login4`（1007387 bytes），MiniSessionStore保存本次Mini会话后，显式Web确认成功自动进入对话Tab；跳转失败可单独重试导航。正式API/Web未改，未同步Cookie/凭据，未提交微信审核/发布。待用户后台设为体验版和真机验证。见 [构建与验证](../artifacts/releases/2026-09-07-shared-account-avatar/mini-upload-login4.json)。

## 品牌与双端统一发布（2026-09-07）

当前 API/Worker 由 `99-brand-release-20260907.conf` 将 WorkingDirectory 与 PYTHONPATH 绑定 `/opt/chickenbro`，该链接指向 `/opt/chickenbro-releases/95fedba9c5fbc8088a652a887b70dad144164313`。Web current 指向 `/var/www/chickenbro-web/releases/brand-centered-8a047efdaecb14b56590c4f8f72902192b173f48`；Web 相比前者仅补充弹窗居中样式。两个公网域名 readiness 正常，29 个 Web 文件哈希验证通过，真实用户既有会话与推广弹窗读取/交互通过。

小程序上传版本 `2026.09.07-brand` 为源码 `95fedba9c`，尚未代操作微信后台审核/正式发布，继续保留此前体验版 QR 配置。三条 migration 已提前应用，本轮无数据库变更。

回滚时先核对 [精确发布清单](../artifacts/releases/2026-09-07-web-mini-promo/release.json)：单独撤销居中补丁可将 Web current 原子恢复到 `/opt/chickenbro-releases/95fedba9c5fbc8088a652a887b70dad144164313/web`。整批恢复须停止入口并排空工作，将 code/web 链接恢复为清单中原始 `rollbackCode`/`rollbackWeb`，仅移除本次新增的两个 `99-brand-release-20260907.conf`，保留旧 `99-avatar-preview-20260907.conf`，daemon-reload 后分别启动 API/Worker，再核对有效目录与业务页面。旧目录和配置全部保留；未经核验不要重放发布脚本或清理旧数据。


## 双端聊天摘要与回复时间验证部署（2026-09-07）

源码 `c8faf06322a98dc6f754ae8dbf96cfc8ba72c665` 已部署，`/opt/chickenbro` 指向对应 `/opt/chickenbro-releases/<commit>`，Web current 指向该目录的 `web`。API/Worker 新增 `99-chat-progress-release-20260907.conf` 保持 WorkingDirectory/PYTHONPATH 绑定 `/opt/chickenbro`；旧 dropin 全部保留。测试/正式库均已应用 additive `0004_chat_public_progress`；旧客户端不启用 includeProgress 时继续接收旧协议。

29 个线上 Web 文件哈希通过，两个公网域名 ready。小程序 `2026.09.07-chat`（1,036,862 bytes）上传成功，正式 API，开发预览二维码已提供；尚未设为固定体验版或提交微信审核/发布。隔离库真实 Codex 回复与耗时保存通过，摘要存储另经自动化测试验证；该短问题未返回公开摘要，真实手机体验仍待用户验收。见 [发布记录](../artifacts/releases/2026-09-07-chat-progress-timing/release.json)。

回滚前排空当前聊天/模拟任务，停止 API/Worker，把 code 指回 `/opt/chickenbro-releases/95fedba9c5fbc8088a652a887b70dad144164313`，Web 指回 `/var/www/chickenbro-web/releases/brand-centered-8a047efdaecb14b56590c4f8f72902192b173f48`；仅移除本次两个 `99-chat-progress-release-20260907.conf`，daemon-reload 后启动服务并核对 readiness。保留新增列、已存摘要以及旧品牌/头像配置；不执行破坏性反向迁移。源码分支保留，尚未合并 main 或推送。

## WCL 历史天赋修复发布（2026-09-08）

用户已批准发布。`/opt/chickenbro` 指向 `/opt/chickenbro-releases/wcl-8a1a893b1b4b75de7515c85d4cd4a411c49dae30`，是在旧生产 `29c5b2a258bb76c54726fad7285eca25643fbc13` 上精确覆盖五个后端源码/目录文件的组合版本；完整覆盖清单见 [manifest](../artifacts/releases/2026-09-08-wcl-fight-talents/publish-manifest.json)。根目录原始 BRANCH_COMMIT 仍表示基线，补丁身份以 manifest/release 为准。Web 保留并发任务新发布的 `welcome-529a7f1305c28ed96dfff37e8a7d9d7d64bf6bdc`，不修改服务 dropin、登录配置或数据库。

正式原始 WCL 链接读取就绪并完成模拟任务 `2110bcab-27da-4614-a6cf-da07590f5c3b`；新天赋还原路径绑定 SimC 源 f50a2121 的节点目录，未知或不同 runtime 拒绝使用旧目录。

回滚须先确认当前 code 指针仍为上述 wcl 目录、入口无流式 Chat 且模拟/队列已排空；停止 API、再次排空再停 Worker，将 `/opt/chickenbro` 原子切回 `/opt/chickenbro-releases/29c5b2a258bb76c54726fad7285eca25643fbc13`，启动 API/Worker 并核对 readiness 与任务功能。Web 指针和所有现有配置不动。旧代码及新还原快照保留，不反向迁移或清理用户任务。

## 截图输入部署前提（2026-09-09，尚未部署）

见 [截图任务](plans/2026-09-09-chat-images.md)。新增迁移 `0007_chat_images` 为私有图片 bytea 与消息 image_ids；禁止把私有图片迁入公共 COS/CDN。依赖 Pillow 12.3.0 已于本轮获准新增与安装，部署环境须先验证其存在和解码测试。默认 `CHICKENBRO_CHAT_IMAGES_ENABLED` 不设置，入口关闭；只有隔离 Candidate 的真实视觉、Web 上传/历史、服务端身份隔离与异常测试通过后方可设置为 `1`（2026-09-09 用户明确免验小程序端）。本机 PATH CLI 0.144.1 不能使用 Astra，本机已有 0.153.4 通过随机图片识别；不可推断服务器版本。

API 网关需对 `/api/v2/chat/images` 上传允许 7 MiB JSON body（base64 膨胀后），应用持续计数拒绝过量 body，原图及规范化图各限 5 MiB。不扩大其他上传入口。图片读响应 `private,no-store`，不可缓存。图片总量限每用户 100 MiB/1000 个有效 payload。

上线时经部署授权配置每日执行 `python -m server.purge_chat_images --apply`；不带 `--apply` 只统计到期 payload 数/字节。仅清空 expires_at 已到期图像字节，保留消息、图片 metadata 和幂等墓碑；未发送 24 小时过期，归档后 7 天到期，归档立即禁止读取。清理未执行不能宣称保留策略已在生产生效。数据库备份会含图片，沿用正式数据库备份与访问控制。

回滚先关闭图片入口，保留迁移和现存图片数据。旧客户端不请求 includeImages，旧服务不查询 image_ids，但纯图消息 content 为空；回退到完全不理解图片的旧服务会丢失纯图问题的模型上下文，应排空活动运行并以保留新读取能力、仅关闭上传/新发送作为首选回滚。不做反向 schema 删除。
