### Spec Compliance

- ✅ Spec compliant（Task2 scoped gate，fix round1）：I1 已 addressed；无 open findings。跨任务集成待核实项保持如下。
- ✅ brief 列出的迁移、application/repository/worker、ninja adapter、两份测试及 API/dependencies/main 接线均在审查 diff 中。create/source/retry 的幂等键、owner 隔离、CAS 与真实基线的事务关联具备实现。
- ⚠️ 跨任务净化：`server/app/poe2/imports/worker.py:31-38` 依赖 Task3 的 collector 已净化 snapshot，以及 Task4 的 mapper 只产生公共 preview 值与 issues。Task2 筛选 preview 顶层键，packet serializer 不包含 snapshot/source_xml/canonical_url；递归值及 issues 内容的安全性需 root 在 Task3/4 装配时核实。没有将未实现端口的潜在行为判为既有泄漏。
- ⚠️ 运行态：报告明确 Candidate 服务未重启、迁移未登记 ledger，当前证据是直接云端测试。真实 Cookie/CSRF 握手、完整 collector→mapper→convert 和服务装配留待 root 集成验收。

### Strengths

- `server/app/poe2/imports/repository.py:121-145`：锁定当前 lease/attempt，校验有效期限和真实结果的指标/输入 hash，在同一事务插入确定性 build、成功 baseline job 并设置 ready；事务失败和重复完成有针对性测试。
- `server/app/poe2/imports/repository.py:27-48,70-81,92-98`：owner 范围查询与 advisory lock 配合幂等请求 hash；取消清租约并递增 attempt，旧 worker 不能落库。
- `server/app/poe2/imports/repository.py:108-118,139-141`：过期租约恢复、SKIP LOCKED claim 与基础设施失败上限明确；`server/app/poe2/imports/worker.py:24-27` 未配置 WeGame 端口时明确 blocked。
- `server/app/api/routes/poe2.py:86-105`：全部新写路由使用 require_mutating_principal，读取使用 require_principal；`server/app/poe2/imports/application.py:48-51` 仅在请求中解析 XML，计算由 worker 执行。

### Issues

#### Critical (Must Fix)

- 无。

#### Important (Should Fix)

- **I1 / P2 — Addressed in fix round1：补 XML 会复活已经过期的失败快照。** 以下为初审触发及修复要求，行号引用初审版本。`server/app/poe2/imports/repository.py:82-88` 为 source 操作更新 `expires_at=now()+7 days`，却保留旧 snapshot。触发：WeGame mapping 留下 snapshot 并进入 needs_input；期限已过、worker 清理尚未运行时，用户 supply_source。application.read 只在返回对象上遮蔽快照（`:63-68`），不清库；action 延期后 repository.read 又能读出旧 snapshot。之后 claim 的 expire 因新期限跳过它，若 XML 基线成功，ready 将永久保留该过期快照（`:100-106,142-145`）。清理晚到与正常补充输入的组合即可触发，恢复中的 worker 也适用。
  - 最小修复：在 source 的同一行锁事务中，依据更新前期限清掉已过期 snapshot，再为新 XML 设置新 TTL；未过期 snapshot 的成功保留行为继续保持。若要独立保存多个来源期限，可另设 snapshot expiry，但本缺陷无需扩大模型。
  - 定向回归：创建含 snapshot 的 needs_input 行；将期限设置过去；**不要调用 expire**；确认 read 遮蔽快照；supply_source 合法 XML；确认 snapshot 已清空且新 XML 可读；完成基线后仍无旧 snapshot。并保留已有未过期 snapshot→补 XML→ready 的保留断言。该组合不在已有 TTL/保留测试中。

#### Minor (Nice to Have)

- 无。

### Assessment

**Task quality:** Approved（Task2 scoped gate，fix round1）。

**Reasoning:** ready 原子性、所有权和 worker fencing 主路径成立；I1 已通过同事务清理旧过期 snapshot 修复，补充测试覆盖清理尚未运行时的实际触发路径。其余 Task3/4 的公共字段与真实服务接线由后续集成验收收口。

### Fix round1 scoped re-review

- **Addressed: I1/P2；Open: 无。** `server/app/poe2/imports/repository.py:84` 新增 CASE，仅当 source 操作且更新前 expires_at 已过期时清空 snapshot；与新 XML、新 TTL 在原行锁事务的同一 UPDATE 中执行。SQL 的赋值表达式使用更新前行值，未过期 snapshot 仍保留；新增占位符与参数数量、位置匹配。
- `tests/app_poe2_import_postgres_test.py:135-151` 新用例先构造真实持久化 snapshot、过期并确认 read 遮蔽，再在未调用 expire 时 supply_source；断言延期后旧 snapshot 不可读、新 XML 可读，完成 ready 后旧 snapshot 仍不存在。既有未过期 snapshot 保留测试未改。
- 修复报告记录云端新增用例先 FAIL，修复后两模块共 14 tests：13 pass、1 live-engine opt-in skip（1.810 秒）。此次修改未改变引擎调用，原真实基线证据适用；复审未重复执行测试。
- 仅审阅 `2026-09-20-poe2-link-task2-fix-review.diff` 的 repository/test 两文件精确差异与修复报告；未发现修复引入新问题，未扩大初审范围。上文 Strengths/初审 checks 的行号保留初审版本含义。

### Review checks

- 按 task-reviewer-prompt 读取 brief/report/full diff。工具首次输出截断的 worker/test 段从同一 diff 定向补读；行号从 diff 新文件行号推导。没有重复读取 changed source，也未运行 git 命令。
- 具名集成风险「引擎结果与异常合同」：只读 `server/app/poe2/application.py:22-32` 的 validate_result 和 `server/app/poe2/engine.py:149-176` 的计算/异常合同；确认指标、版本和 XML hash 校验与现有引擎相容。
- 具名集成风险「认证与来源净化」：只读 `server/app/api/dependencies.py:105-160` 的认证依赖、Task1 `imports/domain.py` / `imports/urls.py`；确认变更依赖通向 mutating 验证、URL 按 provider 校验。尝试定向查找 mapper/WeGame adapter 时对应文件尚不存在，未继续扩展搜索。
- 未重跑报告已有测试；I1 由 SQL 更新与读取/清理条件直接确定，未新增运行。仅写本审查报告；未改产品、状态、迁移或服务，未提交、推送、部署、重启。
