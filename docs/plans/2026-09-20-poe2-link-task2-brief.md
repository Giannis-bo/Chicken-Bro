### Task 2: 持久化导入任务与 ninja 辅助导入

**Files:** 新增 `server/migrations/product/0013_poe2_character_imports.sql`、`imports/{repository,application,worker}.py`、`imports/sources/{__init__,ninja}.py`、`tests/app_poe2_import_application_test.py`、`tests/app_poe2_import_postgres_test.py`；修改 API routes/poe2.py、dependencies.py、worker/main.py。

**Interfaces:** `ImportApplication.create(principal,provider,url,key)`、`read(principal,id)`、`supply_source(principal,id,source,key)`、`retry(principal,id,key)`、`cancel(principal,id)`；`ImportWorker.run_once() -> bool`。repository claim/complete 接受 lease_owner、attempt，complete 通过 CAS 校验；ninja 的 nextAction 为 supply_pob，携带已验证站点链接。

- [ ] 写失败测试：ninja 创建直接 needs_input 且网络 spy 零调用；给定 XML 完成真实基线；owner B 的五项操作均 404；相同 key 不重复；相同 key 不同内容 409；取消后旧 worker 不可完成。

```python
def test_cancel_fences_old_worker(self):
    row = self.app.create(self.a, 'wegame', self.wegame_url, 'first')
    claim = self.repo.claim('worker-a')
    self.app.cancel(self.a, row.id)
    self.assertFalse(self.repo.complete(claim.id, 'worker-a', claim.attempt, {'status': 'ready'}))
    self.assertEqual(self.app.read(self.a, row.id).status, 'cancelled')
```

- [ ] 云端运行这两个新 unittest 模块，确认失败；迁移添加 imports 表、owner FK、唯一幂等索引、attempt/lease、最小快照字段、expires_at、stage、result IDs，并授予实际 wow_app 所需权限。
- [ ] 实现 CAS 状态机及每 owner 活跃任务约束；最多 2 次可重试基础设施失败，登录/限流/映射错误不自动重试；worker 重启可恢复。
- [ ] supply_source 创建新 attempt 并验证 XML，调用既有 PoB/构筑和基线任务合同。持久化 source relation=user_supplied；构筑记录与完成引用用事务/确定性唯一键避免崩溃后重复。ready 必须同时有成功 job 和 build ID。

```python
if job.status == 'succeeded' and build is not None:
    repo.complete(import_id, lease_owner, attempt,
                  {'status': 'ready', 'buildId': str(build.id), 'baselineJobId': str(job.id)})
```

- [ ] API 实现设计中五路由，source/retry 添加幂等 key；使用既有 Principal、CSRF、ApiProblem。只返回净化 preview/issues，不返回快照原文和分享凭据。
- [ ] 云端普通单测、SET ROLE wow_app PG 用例、真实 ninja XML 基线执行；保存 owner、重试/取消及基础指标证据。未成功快照只读取未过期记录；TTL 清理接入受限 worker 的任务级行为，保留成功构筑资料，不扩大到旧数据。

## Binding constraints and interfaces

用户明确国服 WeGame、国际服 ninja 两个独立入口。create(principal,provider,url,key) 必须核对来源；网络读取和计算汇入统一管线。所有测试、程序运行、依赖在云端，禁止本地执行；本地仅编辑/读取/传输。禁止提交、推送、合入、生产切换。保留既有 WIP，不触碰其他任务文件。

Python 合同：SourceProvider(WEGAME,NINJA)，SourceRef(provider,canonical_url,account,league,character,share_id)，ImportStatus(queued,fetching,mapping,validating,ready,needs_input,blocked,failed,cancelled)，ImportIssue(code,path,severity,message)，parse_character_url(value,expected_provider)。issues severity info/warning/error/blocking。

完整响应使用已验证 frozen ImportPacket(id: UUID,status: ImportStatus,provider: SourceProvider,preview: Mapping|None,issues: tuple[Issue,...],next_action: str|None,build_id: UUID|None,baseline_job_id: UUID|None,attempt: int,updated_at: aware datetime)。ready 强制两个 ID。注意 camelCase API 输出与 snake_case Python 字段转换。

现有构筑 import_build 会同步调用引擎；不能直接在 HTTP supply_source 请求中阻塞执行。提交补充后入队，由任务执行并原子关联 build/baselineJob。可通过 import-owned deterministic IDs 和单事务写 build/job/import 链接实现恢复安全；不要重复导入后产生孤儿。不同 owner 的读取与所有动作均 404。

Task 3/4 的 collector/mapper 尚未完成，用依赖注入而非伪实现提供端口：worker 可接收 collect(ref)、map(snapshot)、convert(character)；默认未配 WeGame collector 时明确 blocked SOURCE_UNAVAILABLE，不假 ready。完成 Task 2 应真实打通 ninja 用户提交 XML 路径。

本任务负责 application/repository/worker/API/main/dependencies 接线及迁移测试。不要修改浏览器源适配器、mapping、Web 或 TS 合同，发现合同问题先发消息。Chat 接线由后续任务负责。

云端 ssh wow-lighthouse；source=/opt/chickenbro-candidates/poe2-20260918/source；python=/opt/chickenbro-runtime/bin/python。PG 测试仅 chickenbro_poe2_candidate；以 postgres 的 peer socket 建连接后 SET ROLE wow_app。只上传拥有的文件。不重启服务、不自行部署，由 root 集成。

实际引擎样本：本地 artifacts/research/2026-09-20-poe2-character-links/international-character.xml；云端 evidence/link-research/ninja-build.xml。运行环境参考 server/poe2_candidate_runtime.py 中 POE2_* / LUA_* 值，禁止打印凭据。

报告路径：docs/plans/2026-09-20-poe2-link-task2-report.md，记录文件清单、确切测试命令、结果、首次失败和复验、外部集成缺口。不派子代理；review 由 root 调度。
