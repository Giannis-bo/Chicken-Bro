# 炸鸡队长与 SimC 生产迁移、切流与恢复 Runbook

状态：当前生产操作权威；Phase 2 只允许本地实现、测试、云端只读刷新和 provisioning dry-run，candidate apply 仍 blocked

本 Runbook 规定如何从 legacy `wow_test` 和旧运行单元迁移到干净 `chickenbro_prod`，如何验证双端数据一致，何时可以切流，以及何时仍然禁止删除。执行者必须同时阅读 [当前架构](chickenbro-simc-architecture.md)、[project-state.json](project-state.json) 和对应阶段的 Harness requirement。

## 当前事实

最新脱敏快照：[chickenbro-simc-cloud-inventory.json](refactor/chickenbro-simc-cloud-inventory.json)

| 项目 | 2026-09-02T13:43:05Z 只读结果 |
| --- | ---: |
| 根分区总量 | 73,859,022,848 bytes |
| 根分区已用 | 62,144,901,120 bytes |
| 根分区可用 | 8,583,778,304 bytes |
| PostgreSQL 所有非模板数据库合计 | 39,277,479,625 bytes |
| PostgreSQL 目录 | 39,630,380,619 bytes |
| 数据库数量 | 31 |
| `wow-*` unit 数量 | 32 |
| 容量门禁 | `blocked_until_independent_legacy_cleanup_or_storage_expansion` |

这些数字只说明快照时刻的资源状态。执行任何写入前必须刷新；旧快照、HTTP 200 或单个服务 active 不能解锁后续步骤。

## 绝对安全边界

- 不读取、打印或提交 env 值、DSN、PGPASS、微信凭据、Codex 配置、Cookie、Bearer、OpenID 或第三方 token。
- 不在没有独立恢复副本和恢复验证时删除数据库、正式部署、唯一 SimC runtime 或回滚包。
- “独立恢复副本”必须位于与 PostgreSQL 数据目录不同的设备/故障域；同一根盘的 `/var/backups` 不算磁盘故障恢复点。
- 不把 `wow_test` 当作普通测试库。它当前仍是 legacy/正式 v2 的运行数据面。
- 不直接手写 `DROP DATABASE`、宽泛递归删除或批量停服务。只有仓库内通过测试的精确 manifest/apply 脚本可以执行变更。
- Candidate、生产切流和 destructive cleanup 分别需要独立证据。前一步完成不自动授权后一步。
- 新系统接受第一条正式写入后，legacy 永久保持只读；不得重新开放旧写入口形成双主。

## 角色与证据

| 角色 | 允许做什么 | 不允许做什么 |
| --- | --- | --- |
| runtime role | 目标 API/Worker 的最小业务读写 | schema/role/database 管理 |
| migrator role | 目标 schema、受控全量/delta、核对 | 读取无关 secret、写 legacy、删除库 |
| operator | 运行已审阅脚本、systemd/Nginx 切换和 smoke | 跳过 manifest SHA、备份或恢复证明 |
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

目标是同时容纳：新库、迁移临时空间、旧库回滚窗口、WAL/日志余量和至少一次恢复演练。`rootFreeBytes > currentDatabaseBytes` 也只进入 `capacity_preflight_required`，不是自动通过。

允许两种路径：

1. 扩容/挂载独立数据或备份设备；
2. 对完全无运行引用、无回滚职责的 evidence/test 数据库或构建缓存做“独立备份 -> 恢复验证 -> 精确清理”。

禁止通过删除 `wow_test`、正式部署、唯一 SimC runtime 或唯一回滚包释放空间。

检查设备 ID（把第二个路径替换为已批准的独立备份根）：

```bash
ssh wow-lighthouse \
  'stat -c "%d %n" /var/lib/postgresql /absolute/independent-backup-root'
```

两个设备 ID 相同时，该路径不能作为独立介质证明。不同设备 ID 仍需记录容量、挂载来源、加密/权限和恢复验证结果。

容量前置清理必须有独立 cleanup manifest，逐个记录数据库/目录名称、bytes、最后连接、systemd/env/Nginx 引用、备份 identity、restore identity 和保留理由。默认 `--dry-run`；当前 Phase 2 不存在 cleanup apply 授权。

当前只读清理清单是 [chickenbro-simc-capacity-cleanup-manifest.json](refactor/chickenbro-simc-capacity-cleanup-manifest.json)：四个 `wow_gear_evidence_*` 数据库共 22,533,484,636 bytes，当前连接与已扫描配置引用均为 0，但服务器只有单一 `vda` 根盘，且没有独立 archive/restore identity。因此四项都只是 `candidate_only`，不得据此删除。

## 3. 建立可恢复备份

Phase 2 的受控备份必须覆盖：

- PostgreSQL globals/roles 的可恢复描述和所有迁移源数据库；
- 当前生产业务库与精确 migration/version identity；
- Nginx effective config、TLS 文件 identity、systemd unit 文件和启用状态；
- 服务 env 文件的加密备份，只记录 path/hash/permission/configured 状态，不在证据中记录内容；
- `/opt/wow-mini-program` deployable tracked set、runtime overrides 和 `.deploy-revision` 真实性；
- `/opt/wow-simc/current` 指针、binary hash、`.commit` 和 runtime revision；
- 静态 Web root、候选 root 和恢复所需的精确发布 identity。

备份完成不等于可恢复。必须在隔离位置实际执行 restore/list/校验，记录：备份 SHA、字节数、创建时间、设备 ID、加密状态、恢复目标、恢复命令退出状态、schema/row/hash 抽样和操作者。未完成恢复验证时，所有 destructive gate 保持 false。

## 4. 建立干净 `chickenbro_prod`

只有 Phase 2 提供并验证 `server/provision_chickenbro_database_lighthouse.sh` 后才能 apply。脚本契约：

- 默认 `--dry-run`；
- 精确目标固定为 `chickenbro_prod`；
- 要求 inventory SHA、独立 backup device 和 management role；
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

容量门禁或独立备份仍 blocked 时，只封存 `blocked` evidence，不尝试 `--apply`。

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

当前审阅文件 SHA-256 是 `1466a227e882125ddd342c9518025b583b7bbead80dabb193f29997ff41e80c6`；实际 dry-run 返回 `mutationAuthorized=false` 和 `blocked_until_independent_legacy_cleanup_or_storage_expansion`。文件刷新后必须重新计算并评审 SHA，不能继续使用这里的历史值。

只有 `candidateDatabaseProvisioningAuthorized=true`、最新 inventory 为 `reachable` 且无 probe error、capacity gate 已进入 `capacity_preflight_required`、独立备份与恢复证据已通过时，才可准备以下命令；当前禁止执行：

```bash
sudo -E server/provision_chickenbro_database_lighthouse.sh \
  --apply \
  --inventory-sha "${INVENTORY_SHA}" \
  --backup-device /absolute/approved-independent-device
```

apply 还要求：`WOW_REBUILD_BACKUP_ROOT` 位于上述独立设备且 mode=0700，`WOW_REBUILD_MANAGEMENT_ROLE` 是已审阅管理角色，PostgreSQL 数据与备份根的 device ID 不同，实时数据库总量与 inventory 漂移不超过 5%，PostgreSQL 与备份设备分别满足余量，runtime role 无 database/schema 创建权限，也无 Identity/Chat/SimC/job queue/usage counter 的 DELETE 权限。脚本先对 `wow_test` 生成 custom archive 并通过 `pg_restore --list`，再创建目标并逐个事务应用 product migrations。restore-list 不是恢复演练；候选授权仍必须引用独立的真实恢复证据。

如果目标已存在，脚本只接受精确 schema/table/migration/owner/权限 identity 且零连接，否则停止。新目标创建后的迁移失败不会自动移除数据库，而会在独立备份 run 中留下 `failed_requires_operator_review`，由操作者只读检查后另行处理。

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

## 6. 逐域核对

全量和 delta 都必须分别核对：

| 域 | 必须一致的内容 |
| --- | --- |
| Identity | accepted/rejected user、provider mapping、prototype 排除、无旧 session |
| Chat | owner、conversation、message role/order/content hash、AgentRun 终态 |
| SimC | owner、snapshot/source hash、job/scenario、attempt、result metric/provenance |
| Ops | migration mapping、queue 空闲/终态、audit redaction |

只比较数据库总行数不合格。核对报告必须包含 candidate/accepted/rejected 数量和稳定拒绝原因，且不能包含 provider subject 或 credential 明文。

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

## 8. 写栅栏、delta 与切流

切流窗口固定顺序：

1. 确认候选、备份、恢复、容量、全量迁移和真实用户验收均已通过。
2. 把 legacy 产品写入口置为只读，保留健康/读取和明确维护文案。
3. 记录 write watermark、活动连接、队列和运行中 job。
4. 等待/收口允许完成的 job，执行唯一一次只读 delta。
5. 重新运行逐域核对，要求无未解释差异。
6. 原子切换 API/Worker DSN、systemd 和 Nginx 到新部署 identity。
7. 验证只有新路径可写，legacy 仍只读。
8. 写入一条受控正式记录，记录 `firstNewProductionWriteAt`。
9. 执行生产双端 Chat/SimC、owner 隔离、退出和恢复 smoke。

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

## 10. Legacy 退役

只有以下条件全部满足才可进入 Phase 6 apply：

- 正式切流稳定窗口结束；
- 真实 Mini/Web Chat 与 SimC 验收有明确用户确认；
- 新库备份和恢复演练通过；
- legacy 无连接、无 open handle、无 systemd/Nginx/env/caller 引用；
- 文档链接图和代码 caller graph 对每个删除目标为零；
- cleanup manifest 列出精确路径/库/unit/env、hash/bytes/reason/restore identity；
- manifest SHA 与 apply 参数一致；
- 回滚包保留窗口有书面状态。

退役顺序：停止并禁用 legacy unit/timer；移除 candidate/prototype；精确删除无引用数据库；删除旧部署/静态/数据目录；删除本地旧代码/文档/测试；刷新本地/云端清单和 parity。不得对 `/opt`、`/var/lib`、数据库前缀或仓库根做宽泛递归删除。

## 11. 最终验证与完成

最终证据必须同时包含：

- 本地 `main` 与 `origin/main` SHA 相同；
- 云端 deployable tracked set 和 runtime overrides 与发布 identity 相同；
- `chickenbro_prod` migration identity、允许/禁止 schema 和 runtime role 权限；
- systemd/Nginx/listener/DB 连接只指向目标运行面；
- API/Worker/SimC 语义 smoke；
- 两个用户的 owner 隔离；
- 同一用户 Mini/Web 的 Chat 与 SimC 双向同步；
- 备份恢复与清理后的最新 inventory；
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
| 空间仍不足 | 刷新 df/DB/目录清单、独立设备容量、回滚保留量 | 不删正式库/唯一恢复点绕过 |
| 切流后需要回退 | `firstNewProductionWriteAt` 是否存在 | 有新写入后 legacy 永不恢复为写主 |

## 相关文档

- [当前架构](chickenbro-simc-architecture.md)
- [验证矩阵](verification-matrix.md)
- [项目状态](project-state.json)
- [本地处置清单](refactor/chickenbro-simc-refactor-inventory.json)
- [云端只读清单](refactor/chickenbro-simc-cloud-inventory.json)
- [当前六阶段计划](plans/README.md)
