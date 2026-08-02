# SQLite 全面退役设计

状态：`待用户审阅`
分类：`Strict（分阶段实施）`
提出日期：2026-08-02

当前事实入口：[project-state.json](../project-state.json)、[roadmap.md](../roadmap.md)、[数据库架构](../database-architecture.md)、[Harness](../harness.md)、[验证矩阵](../verification-matrix.md)

## 用户目标与完成体验

玩家侧不应感知数据库迁移：资讯、构筑、模板、SimC、炸鸡队长、存档和后台同步继续使用同一接口与可信状态。区别只体现在故障语义：PostgreSQL 配置或 store 缺失时，服务和任务必须明确失败并暴露真实 blocker，不能创建本地数据库、读取旧快照或静默降级。

开发与测试侧的完成体验是：启动后端只接受 PostgreSQL 配置；业务单测不需要本机共享数据库；需要验证 SQL、约束和事务时使用 PostgreSQL 专项测试；仓库不再携带 SQLite runtime、测试适配器、迁移读取器或相关环境变量。

## 当前问题

线上服务已经使用 `WOW_DATABASE_RUNTIME=postgres_only`，但“生产 PostgreSQL-only”不等于“SQLite 已退役”。当前可执行源码和测试仍存在以下遗留：

- `server/db.py` 在缺少 `WOW_DATABASE_URL` 时隐式选择 SQLite；
- `server/news_backend.py` 保留 `db_connection()`、`init_db()` 以及多处 PostgreSQL/SQLite 双路径；
- 多个同步、回填和 payload 模块仍能直接打开 SQLite；
- PostgreSQL 迁移目录仍包含读取旧 SQLite 文件的 shadow/copy 工具；
- `tests/` 仍大量创建 SQLite 临时库并直接断言表状态；
- 当前活跃文档仍描述 SQLite 测试适配、离线迁移源和回退门禁。

2026-08-02 盘点基线为：`server/` 中 19 个 Python 文件、187 个匹配行，`tests/` 中 15 个 Python 文件、537 个匹配行；仓库没有跟踪 `.sqlite`、`.sqlite3` 或 `.db` 数据文件。该计数只用于确定范围，不作为最终验收；最终验收检查可执行依赖与当前合同，而不是删除 Git 历史或不可变 release 证据中的旧文字。

## 方案比较

| 方案 | 收益 | 风险 | 结论 |
| --- | --- | --- | --- |
| 一次性把所有测试和代码直接改为共享 PostgreSQL | SQL 语义最接近生产 | 测试慢、并发污染、开发机依赖重；一次改动跨越大量 owner，回归难定位 | 不采用 |
| 保留 SQLite 仅供测试 | 改动较小，现有测试迁移容易 | 继续维护第二套 Schema 和 SQL 行为；无法满足“彻底去除” | 不采用 |
| 分阶段删除 SQLite，业务测试用接口级 fake，PostgreSQL 专项测试验证持久层 | 最终只有一个真实持久层；单测快速且隔离；每阶段可审查、回退和证明调用者归零 | 需要先补齐 store seam，并迁移大量直连数据库测试 | 采用 |

## 目标架构

```text
HTTP / worker / scheduled job
  -> typed domain/store interface
       -> PostgreSQL store
            -> PostgreSQL migrations

business unit tests
  -> bounded in-memory fake of the same interface

store/schema/integration tests
  -> PostgreSQL fake connection for query-shape tests
  -> disposable real PostgreSQL for schema, transaction and candidate smoke
```

内存 fake 不是第二个数据库实现：它不解析 SQL、不复制 Schema、不提供生产运行入口，只保存完成单个业务测试所需的有界对象。所有 SQL 方言、约束、索引、事务和迁移事实只由 PostgreSQL 测试与候选环境证明。

## 全面退役边界

### 运行时与配置

- `database_config_from_env()` 只接受 `WOW_DATABASE_URL` 和 `WOW_DATABASE_RUNTIME=postgres_only`；缺少或模式错误时立即失败。
- 删除 `sqlite3` import、`DEFAULT_SQLITE_PATH`、`sqlite_path`、SQLite connection helper、runtime-disabled/migration-source helper。
- 删除 `WOW_NEWS_DB`、`WOW_SQLITE_RUNTIME_DISABLED`、`WOW_SQLITE_MIGRATION_SOURCE`、`WOW_ALLOW_SQLITE_MIGRATION_SOURCE` 及 SQLite public-cache fallback 配置。
- `news_backend.py` 不再提供 `db_connection()`、`init_db()` 或任何 SQLite 分支；缺失的 domain store 是启动或请求 blocker。

### 同步、回填与工具

- 仍有业务价值的同步和回填能力改为调用现有 PostgreSQL store / `postgres_cache_sync`。
- 与现有 PostgreSQL 作业重复的 SQLite entrypoint 直接删除，不保留同名兼容包装。
- CLI 不再接受 `--db` 或 SQLite 文件路径；需要数据库时只接受 PostgreSQL DSN/现有环境合同。
- 删除 SQLite lock、WAL、PRAGMA、`sqlite_master` 和 SQLite 方言分支。

### 测试

- 路由和业务行为测试通过明确注入的 store fake 验证 owner、状态和响应，不直接创建表或读取数据库文件。
- PostgreSQL store 单测继续使用现有 query-shape fake；Schema、FK、唯一性、JSONB 与事务由真实 PostgreSQL 集成测试和候选 smoke 覆盖。
- 删除验证 SQLite fallback、SQLite 锁、SQLite schema 初始化和 SQLite/PG 双写一致性的测试。
- 增加仓库门禁，禁止活动 Python/JS、部署文件和当前文档重新引入 `sqlite3`、SQLite 数据路径或已退役环境变量；门禁自身和不可变历史证据使用显式小范围豁免。

### 迁移与历史数据

- 删除 `identity_shadow_plan.py`、`data_copy_plan.py`、`shadow_migrate.py` 及其测试和当前 runbook 入口。
- 删除前先以只读 PostgreSQL 查询证明各 domain 的生产表、migration ledger、关键 owner 数据和当前 release identity 已完整存在；发现缺口时先完成一次最终受控迁移，再继续退役，绝不恢复在线 fallback。
- 部署目录中的旧 SQLite 文件在候选通过后移出运行目录并取消任何服务引用。冷备份可以按现有保留策略留在受限备份区，但系统不再包含读取、恢复或迁移它的代码。
- 不删除 Git 历史和不可变 release packet；它们只记录过去发生过什么，不构成当前执行能力。

## 分阶段实施

### Phase 0：合同冻结与测试支架

冻结 PostgreSQL-only requirement，建立 domain store fake 与退役扫描门禁，先把新增测试写成失败状态。此阶段不改变生产请求路径。

### Phase 1：后端运行时单路径

让 `db.py` 和 `news_backend.py` 只允许 PostgreSQL，迁移身份、个人数据、Chickenbro、news、analytics、cache 和 ops 调用者，删除核心 SQLite schema 与 helper。候选部署必须证明 API、owner 隔离、Trace 和 health 无回退。

### Phase 2：同步与回填单路径

把社区模板、WebSim、stat weight、observed/crafted gear 等剩余作业切到 PostgreSQL-native owner，删除重复 SQLite entrypoint 和 CLI 参数。逐个验证 timer、锁、重试、partial/blocked 状态和回滚。

### Phase 3：测试与迁移工具退役

迁移剩余 SQLite 测试，完成真实 PostgreSQL 集成矩阵，删除 shadow/copy 工具、旧测试、环境变量、当前 runbook 和部署残留引用。

### Phase 4：最终零调用方证明与发布

对活动源码、测试、部署配置和当前文档运行零入口审计；在一个不可变候选上执行 full Harness、真实 PostgreSQL API/worker/timer smoke 和代码回滚证明。只有 Phase 0-4 全部归档后，路线图才能写“SQLite 已全面退役”。

## 验收标准

1. 活动 runtime、worker、sync、CLI 和测试没有 `sqlite3` import、SQLite connection、SQLite 文件参数或 SQLite SQL 方言。
2. 后端缺少 PostgreSQL DSN 或 `postgres_only` 模式时 fail closed，不创建本地文件。
3. 所有生产 domain 只有 PostgreSQL store owner；owner map 不再列 SQLite compatibility consumer。
4. 当前测试不创建、读取或清理 `.sqlite`、`.sqlite3`、`.db` 文件。
5. 旧 migration reader、相关测试和当前 runbook 已删除；生产完整性由 PostgreSQL 只读审计证明。
6. full Harness、PostgreSQL 集成测试、候选 API/worker/timer smoke、回滚和 local/origin/cloud identity 全部有新证据。
7. 不以删除历史证据、屏蔽扫描路径或保留隐藏兼容开关伪造完成。

## 失败与回滚

- 任一 domain 缺少 PostgreSQL store 方法：停止该 phase，补齐接口与测试，不恢复 SQLite。
- PostgreSQL 数据完整性审计发现缺口：保持当前 PG-only 线上版本，执行一次有证据的最终迁移；迁移工具删除推迟，其他 phase 不冒充完成。
- 候选部署回归：回滚到上一已验证代码身份，线上环境仍保持 `postgres_only`；不回滚 PostgreSQL 数据到 SQLite。
- 删除的工具只通过 Git 恢复用于离线事故分析，不能重新安装成 runtime 或长期兼容面。

## 非目标

- 不在本任务重构业务 API、前端交互或炸鸡队长回答策略；
- 不更换 PostgreSQL、引入新的持久化产品或建设通用 ORM；
- 不为追求文本级 `rg sqlite` 为零而篡改历史 release evidence；
- 不在没有精确目标和保留证据时删除远端冷备份。
