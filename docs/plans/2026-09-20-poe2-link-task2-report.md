# Task 2 — 持久化角色导入管线

2026-09-20，工作区 `.worktrees/poe2-20260918`。实现完成，等待 root 独立审查及后续 Task 3/4/5 接线。没有提交、推送、合入、生产切换或服务重启。全部程序运行在 `ssh wow-lighthouse`；本地仅读取、编辑、传输和 git diff 检查。

## 文件

新增：
- `server/migrations/product/0013_poe2_character_imports.sql`
- `server/app/poe2/imports/application.py`
- `server/app/poe2/imports/repository.py`
- `server/app/poe2/imports/worker.py`
- `server/app/poe2/imports/sources/__init__.py`
- `server/app/poe2/imports/sources/ninja.py`
- `tests/app_poe2_import_application_test.py`
- `tests/app_poe2_import_postgres_test.py`

修改：`server/app/api/routes/poe2.py`、`server/app/api/dependencies.py`、`server/app/worker/main.py`。仅传输上述文件到 Candidate 对应路径；未触碰 Web/mapper/browser/domain/urls。

## 实现与接口

- `ImportApplication(repository)`：`create(principal,provider,url,key)`、`read(principal,id)`、`supply_source(principal,id,source,key)`、`retry(principal,id,key)`、`cancel(principal,id)`。返回 Task 1 的 frozen `ImportPacket`。`packet_json(packet)` 唯一 camelCase serializer。
- 共用装配：`ImportApplication(PostgresImportRepository(connection_factory))`；API dependency `poe2_import_application` 使用当前 `request.app.state.poe2_application.repository._connect`。后续 Chat gateway 使用相同装配即共用完整状态机。
- 路由前缀 `/api/v2/poe2`：POST `/imports`，GET `/imports/{id}`，POST `/imports/{id}/source`、`/retry`、`/cancel`。create/source/retry body 必须含 `idempotencyKey`。写接口使用既有 `require_mutating_principal`，读接口使用 `require_principal`，错误走 `ApiProblem`。
- 所有四个已有任务 ID 操作的跨 owner 请求返回 404。create 无已有 ID 参数，另一个 owner 的同 key 创建独立任务；不存在可给 owner B 调用的第五种已有 ID 操作。
- owner/action_key 唯一幂等日志保存请求 hash；同 key 同内容重放原任务，异内容409。owner advisory lock + partial unique index 限制每 owner 同时一个 queued/fetching/mapping/validating 任务。
- claim/stage/complete 校验 attempt + lease_owner + lease expiry + snapshot expiry；取消递增 attempt，清租约，迟到 worker 不能写回。默认600秒租约；引擎既有45秒子进程限时。最多首次执行加2次基础设施重试；租约失效也计入重试预算。登录/限流/映射错误不自动重试。
- supply_source 在 HTTP 路径只 decode/验证 XML、持久入队；计算在 ImportWorker 完成。ready 同事务插入 deterministic build/job ID 和成功引用；调用 validate_result，并比对 XML sha256。事务中途失败不留下孤儿构筑；重复完成 CAS 返回 False。
- `source_relation=user_supplied` 持久保存并公开于 preview.sourceRelation；成功基线 result 和 build.summary 中追加 sourceProvenance。
- 未成功 source_xml/snapshot TTL 7天。worker.claim 前执行受限 expire，仅作用 character_imports 非 ready 行；过期原文内部读取也屏蔽。成功任务保留最小净化 snapshot，XML 保存在 build.source_xml，expire 不触碰 ready 任务或既有 build/job 数据。

### Task 3/4 端口唯一约定

`ImportWorker(repository,engine,*,worker_id=None,collect=None,map=None,convert=None)`；`run_once()->bool`。

- `collect(ref: SourceRef) -> dict`：净化最小快照。来源错误抛 `ValueError` 或 `RuntimeError`，字符串为 SOURCE_UNAVAILABLE / AUTH_REQUIRED / RATE_LIMITED / INCOMPLETE；直接公共 code 采用白名单，其他错误净化为通用错误。TimeoutError/ConnectionError 是可重试基础设施错误。
- `map(snapshot: dict) -> MappingResult`：属性使用 snake_case：`character: dict|None`、`issues: tuple[Issue,...]`、`preview: dict`、`mapping_version: str`、`source_hash: str`、`game_data_version: str`。
- `preview` 公共键只允许 character、league、level、class、ascendancy、fetchedAt、sourceUpdatedAt、completeness；worker 加 provider/sourceRelation/mappingVersion/sourceHash/gameDataVersion。分享凭据和完整 URL 不从 WeGame preview 返回。
- `convert(character: dict) -> str` 返回 XML。存在 error/blocking issue 或 character=None，worker 持久化 preview/issues/snapshot，返回 needs_input + supply_pob，不调用 convert。
- 任务 snapshot 保存 `{data: <collector dict>, provenance: <版本/hash/provider/relation>}`。成功任务保留该字段；API 从不返回 snapshot 原文。地图/字典版本元数据也保存在成功 build.summary/sourceProvenance 和 job.result/sourceProvenance。
- map callable 需要自己绑定 dictionary，例如 `lambda snapshot: map_snapshot(snapshot, dictionary)`。
- 默认未注入任意 WeGame 端口时 blocked SOURCE_UNAVAILABLE；ninja create 为 needs_input/supply_pob，纯本地解析零网络读取。

## 云端迁移状态

已用 postgres peer socket 对 **chickenbro_poe2_candidate** 直接 `psql -f 0013` 执行表、索引和 wow_app grants。没有运行项目正式 migration apply，也没有写 migration ledger/checksum；root 后续正式登记。

首次默认24小时已按设计修正文件为7天，Candidate 做了定向：

```sql
ALTER TABLE poe2.character_imports ALTER COLUMN expires_at SET DEFAULT now()+interval '7 days';
```

测试只有随机生成的测试 owner，tearDown 清理本次 owner 数据；没有删除历史业务数据。

## 验证

首次云端运行两个新 unittest 模块分别失败：`ModuleNotFoundError: server.app.poe2.imports.application`。上传实现后进入通过阶段。

所有命令 cwd：`/opt/chickenbro-candidates/poe2-20260918/source`。Python `/opt/chickenbro-runtime/bin/python`。Postgres test 每个应用连接显式 `SET ROLE wow_app`；admin peer 只用于构造/清理自己测试 owner 以及测试租约时间。

最终综合运行29 tests，全部通过，耗时6.517秒，含真实 ninja XML、API、事务回滚、Task1 URL与Packet回归、既有 POE2 application/jobs PG回归。云端完整输出：`/opt/chickenbro-candidates/poe2-20260918/evidence/link-research/task2-final-tests.log`。

```sh
sudo -u postgres env \
 POE2_TEST_DATABASE_URL=dbname=chickenbro_poe2_candidate POE2_TEST_ROLE=wow_app \
 POE2_IMPORT_LIVE_XML=/opt/chickenbro-candidates/poe2-20260918/evidence/link-research/ninja-build.xml \
 POE2_POB_ROOT=/opt/chickenbro-candidates/poe2-20260918/upstream/pob \
 POE2_LUAJIT=/opt/chickenbro-candidates/poe2-20260918/runtime/root/usr/bin/luajit \
 POE2_ENGINE_VERSION=v0.23.1@7d6f530cbdab20389ff8bc6ba97a37ac27f74e41 \
 POE2_ENGINE_LOCK=/tmp/poe2-import-task2-engine.lock \
 LD_LIBRARY_PATH=/opt/chickenbro-candidates/poe2-20260918/runtime/root/usr/lib/x86_64-linux-gnu \
 LUA_CPATH='/opt/chickenbro-candidates/poe2-20260918/runtime/root/usr/lib/x86_64-linux-gnu/lua/5.1/?.so;;' \
 LUA_PATH='/opt/chickenbro-candidates/poe2-20260918/upstream/pob/runtime/lua/?.lua;/opt/chickenbro-candidates/poe2-20260918/upstream/pob/runtime/lua/?/init.lua;;' \
 /opt/chickenbro-runtime/bin/python -m unittest \
 tests.app_poe2_import_application_test tests.app_poe2_import_postgres_test \
 tests.app_poe2_import_urls_test tests.app_poe2_application_test tests.app_poe2_jobs_postgres_test -v
```

真实基线输出：ready；build `0794b32c-3057-5a34-aa02-3c9bdab60bf3`；baseline job `b108cc39-f800-5b34-8f53-46fbbaf84a0d`；Life2813，EnergyShield962，TotalDPS36852.357708804，engine v0.23.1@7d6f530cbdab20389ff8bc6ba97a37ac27f74e41。上述临时测试记录已随 teardown 清理，输出保留在日志。

随后 root 指定成功任务保留净化 snapshot，修改保留逻辑并新增过期后仍保留 ready snapshot 的断言；最终新增模块复验13 tests，12通过、1真实引擎 opt-in 跳过（真实引擎已有上述独立证据），耗时1.705秒：

```sh
sudo -u postgres env POE2_TEST_DATABASE_URL=dbname=chickenbro_poe2_candidate \
 /opt/chickenbro-runtime/bin/python -m unittest \
 tests.app_poe2_import_application_test tests.app_poe2_import_postgres_test -v
```

最终保留逻辑输出：`/opt/chickenbro-candidates/poe2-20260918/evidence/link-research/task2-retention-tests.log`。

覆盖：ninja零网络、同key重放/冲突、owner隔离、API JSON/错误状态及mutating依赖、取消fencing、同worker旧attempt fencing、基础设施重试上限、恢复claim、TTL、active约束、ready缺结果拒绝、build写入后模拟失败的事务回滚、成功结果单例、mapper缺口停止convert并保留preview/snapshot、ready快照保留。API测试覆盖FastAPI路由与PG业务状态，auth dependency由测试注入；没有重新验证真实浏览器Cookie/CSRF握手。

## 仍待集成

Task3 collector 和 Task4 mapper/bridge 尚未注入 worker；Task5 Chat、Task6 Web 未改。没有重启Candidate运行服务，因此服务进程仍是此前装载代码，以上是云端直接 unittest/真实引擎验证。正式迁移登记、集成装配、Candidate服务更新和Web验收由root后续推进。

## 独立审查 I1/P2 修复与定向复验

修复文件仅 `server/app/poe2/imports/repository.py`、`tests/app_poe2_import_postgres_test.py`；另外更新本报告。`action(source)` 在已持有 FOR UPDATE 行锁的同一 UPDATE 中，使用更新前 `expires_at<=now()` 判断并清空过期 snapshot，然后更新新 XML 与7天期限。未过期 snapshot 不变，不增加字段或迁移。

新增 `test_source_cannot_revive_expired_snapshot_before_cleanup`：构造含净化 snapshot 的 needs_input 行 → 定向设置过期 → 不运行 expire → read 遮蔽 → supply_source → 确認数据库读回 snapshot=None 且新 XML 可读 → 完成基线 → ready 仍无旧 snapshot。原有 `test_mapper_input_gaps_persist_preview_and_snapshot` 保留未过期 snapshot 补 XML 后成功保留，以及 ready 过期后也不清快照的断言。

云端先运行新用例：FAIL，断言显示 supply_source 后旧 snapshot 复活（1 test，0.207秒）。上传最小修复后运行：

```sh
cd /opt/chickenbro-candidates/poe2-20260918/source
sudo -u postgres env POE2_TEST_DATABASE_URL=dbname=chickenbro_poe2_candidate \
 /opt/chickenbro-runtime/bin/python -m unittest \
 tests.app_poe2_import_application_test tests.app_poe2_import_postgres_test -v
```

结果：14 tests，13通过，1 real-engine opt-in 跳过，耗时1.810秒；新过期修复与原有正常保留用例均通过。输出 `/opt/chickenbro-candidates/poe2-20260918/evidence/link-research/task2-i1-tests.log`。本轮仅修 TTL 事务条件，没有重新运行真实引擎；原有真实 ninja 证据见上文。

仅定向上传 repository/test 两个文件；没有提交、重启、部署或额外迁移。交 root scoped 复审。
