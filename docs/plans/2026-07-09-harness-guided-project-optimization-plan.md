# 2026-07-09 Harness-Guided Project Optimization Plan

## Status

`Phase 0 + Phase 1 已完成 / 当前 UI 基线已验收`

本文件承接 `docs/harness.md` v0.5、`docs/plans/2026-07-09-docs-implementation-current-truth-review.md` 和当前用户确认的 A 路线：先收口 Harness 与证据系统，再做结构拆分。

2026-07-09 14:29 CST 更新：Phase 0 工作树主题收口与 Phase 1 UI proof matrix 已完成。当前 UI rescue 基线为 `runtime_recapture_complete_auto_14_screenshots_14_pass_final_accepted`，14/14 当前自动截图证据已归档，`runtimeVerified=true`、`finalAccepted=true`、`riskCount=0`。后续 UI 设计调整不纳入本轮 rescue，按新需求重新走 Harness。

2026-07-09 后续更新：用户确认本项目与已配置远端仓库之间的常规同步不再需要额外授权。Phase 2 开始把 `scripts/project-harness.js` 从只读风险表推进为 evidence packet 起点：脚本仍不执行测试、不部署、不联网、不下载，但可读取仓库内本地 `--evidence-file` JSON，并在 manifest 中标出证据包完整性与 repository remote sync 边界。

2026-07-09 继续更新：用户确认没有明确阻塞或待决策点时，agent 应自动向下一步推进，不再每个步骤单独请求同意。Harness v0.4 增加 Autonomous Progression Gate：已批准计划或授权继续后，默认执行范围内后续实现、验证、同步、PR、合入和归档；只有 clear blocker、验证失败需权衡、产品/技术待决策、范围变化、工作树/远端冲突或越界高风险操作才停下来确认。

2026-07-09 Phase 3/4 继续更新：第一条后端热点拆分纵切已按 Harness 规则推进。Phase 3 补齐 `gear_serializer_golden_payload` 与 `gear_template_selectors` golden characterization；Phase 4 新增 `server/gear_public_contract.py` 作为公开装备模板合同的 adapter/selector 模块，`server/websim_payload.py` 保留旧导出并委托新模块，PG store 现有导入面不变。

2026-07-09 Phase 4 第二刀更新：PG gear selector 调用面已开始从 `websim_payload.py` 兼容导出收敛到 `server/gear_public_contract.py`。`server/postgres_cache_store.py` 现在通过模块限定调用公开 source policy、observed-only visibility、baseline fallback gating 和 real-player public import 配置；`websim_payload.py` 兼容导出继续保留，sync 写入路径暂不移动。

2026-07-09 Phase 4 第二刀部署补录：用户指出 backend/API/read model 变更应先部署验证再合入；由于本刀已经合入，已补做 post-merge 热部署与线上 smoke，并将 release evidence 晋级到 `live_verified`。后续同类 backend/API/PG read model 变更默认在 PR 候选阶段先部署或预览验证，通过后再合入。

2026-07-09 Phase 4 第三刀候选推进：Harness 升级到 v0.5，并将 backend/API、PG read model、公开 payload、health/admin、定时任务、部署脚本和用户可见 runtime 的候选部署 / 预览 smoke 前置为正式 gate。本刀继续拆 PG gear selector 只读面，新增 `server/pg_gear_template_selectors.py` 集中 `communityTemplates` / `baselineTemplates` public selection，`server/postgres_cache_store.py` initial 与 full/slot 分支改为委托 helper；sync 写入路径、SQL row 读取和公开 observed-only 语义不变。PR #12 branch 已按 Candidate Deployment Gate 完成候选热部署和线上 smoke，并已 rebase merge 到 `main@704714f`。

2026-07-09 Phase 4 第四刀候选推进：继续沿 PG selector helper 做只读 read-model adapter 拆分，新增 `build_public_gear_template_read_model()`，把 selected public templates 的 payload compact 输出与 `communityTemplateSync` 组装从 `server/postgres_cache_store.py` 收敛到 `server/pg_gear_template_selectors.py`。本刀不移动 PG SQL 读取、不碰 sync/write/backfill，不改变 observed-only 公开入口；当前分支已完成红测、目标测试、完整本地验证和 Candidate Deployment Gate。PR #13 branch 已候选热部署，公网 API、40-spec observed-only sweep、systemd/log/hash parity smoke 通过，已 rebase merge 到 `main@a7fc163` 并同步到本地。

2026-07-09 Phase 4 第五刀候选推进：继续拆 PG full/slot gear read model 的只读 catalog fragment，新增 `server/pg_gear_read_model_selectors.py::build_catalog_gear_read_model_fragment()`，把 catalog item legality filtering、replacement candidate slot grouping、compact/full candidate fragments、catalogItems compaction、readiness / slotReadiness 和 candidateLegalityAudit 组装从 `server/postgres_cache_store.py` 收敛到 helper。`server/postgres_cache_store.py` 保留 PG SQL 读取、payload cache fingerprint、template read model、catalog health 外层字段和 response envelope；sync/write/backfill 路径不动，公开 observed-only template 入口不变。红测已证明缺 helper，最小实现后目标 helper/store tests 通过；完整 Python/Node/compile/check/JSON/diff 验证和本地 CR 已通过。PR #14 branch 已按 Candidate Deployment Gate 完成候选热部署，公网 API、40-spec observed-only sweep、systemd/log/hash parity smoke 通过，已 rebase merge 到 `main@6c7bf71` 并同步到本地。

2026-07-09 Phase 4 第六刀进行中：继续拆 PG gear read model 的只读 catalog state envelope，新增 `build_catalog_state_read_model_fragment()`，把 initial 与 full/slot payload 共同使用的 catalog revision/status/health/coverage/blocker 字段从 `server/postgres_cache_store.py` 收敛到 `server/pg_gear_read_model_selectors.py`。本刀只移动只读 payload fragment 组装，不移动 PG SQL 读取、cache fingerprint、cache put、sync/write/backfill、template public selector 或 candidate grouping 逻辑；公开 observed-only 入口不变。红测已证明缺 helper，最小实现后目标 tests、完整 Python/Node/compile/check/JSON/diff 验证和本地 CR 已通过。PR #15 branch 已按 Candidate Deployment Gate 完成候选热部署，公网 API、40-spec observed-only sweep、systemd/log/hash parity smoke 通过，已 rebase merge 到 `main@608b77f` 并同步到本地。

2026-07-09 Phase 4 第七刀候选推进：继续拆 PG initial gear read model 的只读 baseline/equipped fragment，新增 `build_initial_gear_read_model_fragment()`，把 baseline template 到 `equippedSet`、initial 16 槽 `replacementCandidates` summary、`slotReadiness`、`baselineSet`、`readiness` 和初始 `catalogItems` 的组装从 `server/postgres_cache_store.py` 收敛到 `server/pg_gear_read_model_selectors.py`。本刀只移动只读 payload fragment 组装，不移动 PG SQL 读取、cache fingerprint、cache put、sync/write/backfill、template public selector、catalog state 或 full/slot candidate grouping 逻辑；公开 observed-only 入口不变。红测已证明缺 helper，最小实现后目标 tests 通过，完整本地验证、本地 CR 已通过。PR #16 branch 已按 Candidate Deployment Gate 完成候选热部署，公网 API、40-spec observed-only sweep、systemd/log/hash parity smoke 通过，已 rebase merge 到 `main@fed3f3e` 并同步到本地。

本计划只定义整体优化顺序和验收门禁，不授权直接修改业务实现、不替代 roadmap、runbook 或当前 UI source-of-truth。

## Requirement Contract

用户场景：

- 用户希望不再由 agent 凭单点判断推进重构，而是基于项目真实状态和 Harness 规范，形成可执行、可验收、可回滚的整体优化方案。

用户侧承诺：

- 后续 Standard / Strict 需求先走 Harness 分级、当前事实、影响图、owner、工程健康、证据晋级和发布回滚门禁。
- UI 交付不再用旧截图、静态测试或 browser-only 结果声明完成。
- 装备 / 推荐 / SimC / PG / health / admin 等核心链路不再按单点代码改动推进，必须先说明传播半径和事实 owner。
- 后端热点文件的结构优化必须先有 characterization / contract / golden payload 安全网。

非目标：

- 本计划不直接拆 `server/websim_payload.py`、`server/news_backend.py` 或 `server/postgres_cache_store.py`。
- 本计划不重新开放 `recommended_bis`、`season_recommendation` 或 legacy baseline 的公开入口。
- 本计划不部署、不 SSH、不触发生产任务、不下载依赖或外部数据。
- 本计划不包含后续 UI 视觉/布局重设计；当前 14 页 accepted baseline 只代表本轮 rescue 证据收口。

关键假设：

- `docs/roadmap.md` 顶部、`docs/README.md`、`docs/harness.md`、相关 runbook 和 current source-of-truth 继续作为当前事实入口。
- 当前 Harness v0.5 是规则基线，但 `scripts/project-harness.js` 仍只是只读聚合器，不能替代人工需求合同、测试输出、候选部署 smoke 或运行时证据。
- 当前工作树已经存在多项未提交文档、证据和测试改动；交付前必须继续按主题解释并保持可审阅 diff。

验收证据：

- 每个执行阶段都必须能说明最高证据等级：`requirement_challenged`、`local_verified`、`runtime_verified`、`deployable`、`live_verified` 或 `archived`。
- 每次 Standard / Strict 变更必须产出当前事实入口、影响图、owner 合同、工程健康结论和验证路径。
- UI runtime 只能由真实微信小程序截图、route/action 记录和 DevTools ledger 晋级。
- 后端重构只能由 characterization tests、contract tests、golden payload、真实 API / PG read model 或线上 smoke 晋级。

## Opposition Challenge

反方质疑：

- 如果先做后端拆分，会不会更快降低结构债？
- 如果先补 14 页 UI 截图，会不会更快交付用户可见结果？
- Harness 会不会变成流程负担，拖慢小修？
- 只读 manifest 会不会给人一种“项目已被治理”的错觉？
- 热点文件过大已经明显，为什么不立刻拆？

结论：

- 立即大拆热点文件风险高，因为当前公开装备合同、health/admin、PG read model、同步任务和前端展示高度耦合，必须先有 owner 合同和 golden payload。
- 立即只补 UI 截图可以降低交付风险，但不能解决后续 agent 继续误用证据、旧计划和单点改动的问题。
- Harness 的价值不是增加表格，而是阻止低等级证据越权和影响面漏评。Light 需求仍允许 agent 简短自审后执行。

## Approach Comparison

| 方案 | 内容 | 优点 | 风险 | 结论 |
| --- | --- | --- | --- | --- |
| A. Harness + evidence first | 先收口 Harness、当前事实、UI proof matrix、证据晋级和发布回滚，再做后端结构拆分 | 最符合当前事故形态；先修判断系统，再修代码结构；能减少返工 | 用户可见功能推进较慢 | 推荐 |
| B. Backend refactor first | 直接拆 `websim_payload`、`news_backend`、`postgres_cache_store` | 长期结构收益最高 | 缺 characterization 时容易改坏公开入口、health 或定时任务 | 暂缓 |
| C. UI rescue first only | 只补 UI runtime proof 和少量 UI 修复 | 短期交付最快 | Harness 和后端结构债继续存在，后续仍会重复误判 | 已作为 A 的 Phase 1 完成 |

## Recommended Route

采用 A；UI proof matrix 已作为第一条执行纵切完成，后续从 Harness evidence packet 标准化和后端 owner map 继续。

顺序：

1. 收口当前工作树和文档控制面。
2. 完成 UI 14 页 proof matrix 的低扰动 runtime evidence。`已完成`
3. 把 Harness manifest 从只读风险表升级为每个需求的 evidence packet 入口。
4. 给三大热点后端文件建立 owner map 和 characterization tests。
5. 按 owner 切出小型 adapter / selector / serializer 模块，不先做大搬家。
6. 每个阶段只在证据等级允许时升级 roadmap、runbook 和 release 状态。

## Impact Map

| 分类 | 联动面 | 处理方式 |
| --- | --- | --- |
| `must_change` | `docs/roadmap.md`、`docs/plans/`、Harness evidence packet 格式 | 每个新阶段必须有当前入口和状态，不新增孤立计划 |
| `must_change` | UI proof matrix artifacts | 已同步为 14/14 current automated screenshot accepted baseline；后续 UI 变更另开 proof matrix |
| `must_change` | Harness use in future Standard / Strict work | 每次需求先输出合同、影响图、owner、证据、回滚 |
| `must_not_change` | 公开装备模板入口 | 保持 observed-only，不让 recommended / season / legacy 回流 |
| `must_not_change` | DevTools 安全规则 | 不关闭、不重启、不清缓存、不切 appid、不跑长批量 |
| `must_not_change` | 线上生产数据 | 本计划阶段不写生产、不部署、不触发 sync |
| `risk_unknown` | 后端热点文件拆分边界 | 先做 owner map 和 characterization，再决定切分点 |
| `risk_unknown` | 后续 UI 设计预期 | 当前 rescue 基线已验收；未来视觉调整必须重新定义目标与截图验收 |
| `evidence_required` | UI | screenshot path、route result、current page、DevTools ledger |
| `evidence_required` | Backend | golden payload、contract test、真实 API / PG read model |
| `evidence_required` | Release | pre/post smoke、timer backflow check、rollback strategy |

## Ownership Contract

默认 owner：

- `docs/harness.md` owns delivery gates and evidence promotion rules.
- `docs/roadmap.md` owns active project status and current top-level truth.
- Domain runbooks own current operational contracts.
- Backend read model / serializer owns public structured facts.
- Frontend consumes read model and renders labels/actions; it does not infer source quality or public readiness.
- Health/admin displays authoritative states and blockers; it does not turn partial/internal evidence into verified facts.
- Scheduled jobs write only their owned sync/cache/evidence state.
- Deployment scripts execute delivery and smoke; they do not create product judgment.

热点文件拆分前必须建立 owner map：

| 热点文件 | 当前风险 | 推荐 owner 拆分方向 |
| --- | --- | --- |
| `server/websim_payload.py` | 装备、天赋、物品、serializer、health 边界混杂，约 25.7k 行 | 先抽 gear public contract、legality/source-map、serializer/golden payload；每次只抽一条 owner |
| `server/news_backend.py` | API route、news、admin、Chickenbro、WebSim wiring、runtime store 混杂，约 12.6k 行 | 先把 route wiring / response helpers / admin summaries 从业务构建逻辑中分层 |
| `server/postgres_cache_store.py` | PG cache read/write、community templates、recommended evidence、cleanup 混杂，约 7.2k 行 | 先抽 repository-level selectors 和 write intents，保持 SQL 行为有 golden tests |

## Engineering Health Gate

当前结论：`health_watch`。

原因：

- 本地 Node 和 Python 测试通过，但 Python 测试仍有 ResourceWarning / fixture warning。
- Harness 能暴露热点文件和缺证据项，但不执行验证命令，也不自动附测试输出。
- UI runtime proof 已补齐并验收；后端热点文件结构债、live 状态和后续变更证据仍需保持 `health_watch`。
- 三个后端热点文件继续承载多领域职责，后续任何新增逻辑都可能扩大结构债。

进入实现前必须补齐：

- 对应 owner 的 characterization / contract test。
- 现有行为 golden payload 或 response snapshot。
- 性能 / payload / PG query / task runtime 的可观察基线，至少对高频路径记录 before-state。
- fail-closed / partial / blocked / fallback 的错误语义。
- rollback 或 feature_hide / config_disable / resync_repair 路径。

## Release / Rollback Gate

本计划自身不发布。

后续任何触达公开入口、PG read model、cache、health/admin、定时任务、部署脚本或用户主流程的阶段，必须在实施计划中声明：

- 是否需要代码、PG、cache 或配置备份。
- 是否需要 migration、cache rebuild、sync trigger 或 cleanup。
- 发布前本地 / staging smoke。
- 发布后线上 HTTP/API/PG/timer/health/admin smoke。
- 哪些 timer、sync、cleanup 可能回写旧状态。
- 回滚策略：`code_rollback`、`data_restore`、`feature_hide`、`config_disable` 或 `resync_repair`。

## Phase Plan

### Phase 0：当前工作树收口（已完成）

目标：把治理、UI runtime evidence、gear docs/current truth 和测试更新分成可审阅主题。

验收：

- `git status --short --branch` 中的改动能按主题解释。
- 每个主题都有对应文档或 artifact 入口。
- `git diff --check` 通过。

当前结果：

- 工作树改动已按 Harness governance、current truth / optimization plan、gear public entry current truth、UI runtime evidence recovery 分组记录。
- `artifacts/releases/2026-07-09-phase0-worktree-scope/manifest.json` 作为 Phase 0 evidence packet。
- `git diff --check` 在最终验证中通过。

### Phase 1：UI proof matrix 收口（已完成）

目标：把当前 UI rescue proof matrix 推进到 14 页均有 pass/risk/fail 当前证据。

执行边界：

- 使用 `--auto-port 9854` 和 `auto-route-screenshot.js`。
- 一次只验证一个 route。
- 首选 P0：`pages/builds/workbench`、`pages/builds/builds`、`pages/builds/talent-simulator`、`pages/builds/detail`、`pages/simulator/simulator`、`pages/simulator/simc`、`pages/profile/profile`。
- DevTools 一旦 timeout、unresponsive 或 endpoint 掉线，立即停止并标 risk。

验收：

- 每页都有 screenshot path 或明确 risk。
- `final-delivery-audit.json`、`devtools-action-ledger.json`、`page-captures/manifest.json` 同步更新。
- 不使用旧截图、browser preview 或静态测试晋级 runtime。

当前结果：

- 14/14 `app.json` 页面均有 current automated route+screenshot proof。
- `final-delivery-audit.json`、`devtools-action-ledger.json`、`page-captures/manifest.json`、`manifest.json` 已同步为 accepted baseline。
- `finalAccepted=true`、`runtimeVerified=true`、`currentRuntimeScreenshotCount=14`、`riskCount=0`、`failCount=0`。
- 用户确认当前 UI 基线先收口，后续调整另开需求。

### Phase 2：Harness evidence packet 标准化

目标：让 `scripts/project-harness.js` 的输出成为每个 Standard / Strict 需求的 release artifact 起点，而不是孤立 smoke。

执行边界：

- 保持脚本默认只读。
- 可选 `--write` 只写 `artifacts/releases/<date>-<slug>/manifest.json`。
- 不让脚本自动 SSH、部署、下载、安装或写生产。

验收：

- 每个 artifact 显示 harness version、current truth sources、impact map placeholder、owner principles、engineering health、release/rollback、evidence status、dirty diff 和 hotspot files。
- 后续需求文档引用该 artifact，并补齐人工验证命令输出。

当前进展：

- `AGENTS.md` 与 `docs/harness.md` 已新增 repository remote sync 例外：常规 `fetch / pull --ff-only / push / PR` 同步不再二次授权，但 force push、改 remote、clone、submodule、依赖安装、第三方下载和生产操作仍需明确确认。
- `AGENTS.md` 与 `docs/harness.md` 已新增 autonomous progression 规则：用户确认计划、授权继续或直接推进后，agent 默认继续执行范围内下一步，只在 blocker、验证失败需权衡、待决策、范围变化、冲突或越界操作时停下来确认。
- `AGENTS.md` 与 `docs/harness.md` 已新增 candidate deployment 规则：backend/API、PG read model、公开 payload、health/admin、定时任务、部署脚本和用户可见 runtime 变更默认在 PR 候选阶段先部署或预览 smoke，通过后再合入。
- `scripts/project-harness.js` 已新增 `--evidence-file`，只读取仓库内本地 JSON evidence packet，不执行其中命令。
- Manifest 现在输出 `repositoryRemoteSync` gate、`autonomousProgression` gate、`candidateDeployment` gate、`safety.repositoryRemoteSyncPreapproved`、`safety.autonomousProgressionEnabled` 和 `evidencePacket` 完整性检查。

### Phase 3：后端 owner map 与 characterization

目标：在拆文件前先锁定旧行为。

执行边界：

- 优先 `server/websim_payload.py` 的 gear public contract、legality/source map、serializer。
- 再处理 `server/news_backend.py` 的 route wiring / response helpers / admin summary。
- 最后处理 `server/postgres_cache_store.py` 的 selectors / write intents / cleanup。

验收：

- 每个 owner 都有测试覆盖旧行为。
- 公开 observed-only 合同、PG-only runtime guardrail、health partial/blocker 语义不变。
- 没有性能、payload、PG query 或 timer runtime 的明显退化；无法证明时保持 `health_watch`。

当前进展：

- 已新增 `docs/backend-owner-map.json`，作为三大热点文件拆分前的机器可读 owner map。
- `docs/README.md` 已把 backend owner map 纳入当前文档入口，`scripts/project-harness.js` 已把它加入 current truth sources。
- `server/websim_payload.py` 已明确 `gear_public_contract`、`gear_legality_source_map`、`gear_serializer_golden_payload`、`talent_public_contract` owner；其中公开装备入口继续以 active `raiderio_observed_profile` 为唯一公开 community source，`recommended_bis`、`season_recommendation`、`default_template`、`simc_preset`、`baseline_blocked` 仍为 public blocked source。
- `server/news_backend.py` 已明确 `runtime_api_wiring`、`health_admin_summary`、`news_content_api`、`chickenbro_session_api` owner。
- `server/postgres_cache_store.py` 已明确 `gear_template_selectors`、`sync_state_repository`、`recommended_bis_evidence`、`cleanup_residue_control` owner。
- `gear_public_contract` 已新增 golden payload characterization：`tests/fixtures/gear-public-contract-observed-only.json` 与 `test_gear_public_contract_matches_observed_only_golden_payload` 固定当前 observed-only 输出，不允许 `recommended_bis`、`season_recommendation`、`simc_preset` 回流公开输出。
- `gear_legality_source_map` 已新增 golden payload characterization：`tests/fixtures/gear-legality-source-map-partial-authority.json` 与 `test_gear_legality_source_map_matches_partial_authority_golden_payload` 固定当前 authority health/source-map 输出，确保 official / SimC 仍为 missing、observed 只作为 supporting evidence、manual override 仍为 partial 且不升级 verified。
- `gear_serializer_golden_payload` 已新增 compact serializer golden：`tests/fixtures/gear-serializer-compact-payload.json` 与 `test_gear_serializer_matches_compact_golden_payload` 固定 `compact_community_gear_template`、`compact_gear_candidates`、`gear_readiness`、`blocked_stat_snapshot` 的结构化输出。
- `gear_template_selectors` 已新增 PG selector golden：`tests/fixtures/pg-gear-template-selectors-observed-only.json` 与 `test_pg_gear_template_selectors_match_observed_only_golden_payload` 固定 `get_websim_gear(... compact=True, mode="initial")` 的 public observed-only selector 输出、baseline 空输出与 template chain 状态。
- Phase 3 当前已覆盖 owner map 与 characterization anchors；公开 payload 语义不变。

### Phase 4：小步结构拆分

目标：按 owner 抽小模块，不做大规模搬家。

原则：

- 先 adapter / selector / serializer，后大模块迁移。
- 每次只抽一个 owner。
- 保持 import surface 小而稳定。
- 抽出后旧文件只委托，不新增业务分支。

验收：

- 目标 tests 先失败再通过，或者至少有 characterization 防回归。
- `python3 -m unittest discover -s tests -p '*_test.py'` 和 `node --test tests/*.test.js` 在相关阶段通过。
- 若触达线上链路，必须进入 Phase 5。

当前进展：

- `server/gear_public_contract.py` 已作为第一条小步抽取落地，集中公开装备模板 source policy、observed-only visibility、baseline fallback gating 与 real-player public import 配置。
- `server/websim_payload.py` 保持原函数名和导出面，旧调用方继续使用 `public_gear_templates_for_spec`、`public_baseline_fallback_templates_for_spec`、`community_gear_template_can_apply` 等兼容包装；PG store 暂不改导入路径。
- `tests/gear_public_contract_test.py` 先因缺少新模块失败，再在抽取后通过；随后新增 `templateEvidence` hash 来源 parity 测试并 red/green 关闭，证明新模块与旧导出 observed-only 行为及证据读取路径一致。
- `server/postgres_cache_store.py` 的 PG gear selector 调用面已改为模块限定调用 `gear_public_contract`，并通过 `test_pg_initial_gear_selector_calls_gear_public_contract_module` red/green 锁定；`test_pg_gear_template_selectors_match_observed_only_golden_payload` 继续固定 PG read model 输出不变。
- `server/pg_gear_template_selectors.py` 已作为 PG selector 只读 helper 抽出，initial 与 full/slot 两个 `get_websim_gear` 读模型分支统一委托 `select_public_gear_templates_for_spec()`；新增 `tests/pg_gear_template_selectors_test.py` red/green 固定 active observed-only、source-less observed blocked、`recommended_bis` / `season_recommendation` 不进入 public baseline 的选择合同。
- `server/pg_gear_template_selectors.py` 进一步承接 PG public template read-model adapter，`build_public_gear_template_read_model()` 负责 raw selected templates、payload-ready compact templates 和 `communityTemplateSync` 组装；`server/postgres_cache_store.py` 保留 SQL 读取、catalog candidate grouping、readiness 和 catalog health 组装，不再直接 compact/sync public template payload。
- `server/pg_gear_read_model_selectors.py` 已开始承接 PG catalog read-model selector，`build_catalog_gear_read_model_fragment()` 负责 full/slot gear payload 的 catalog candidate legality filtering、slot grouping、compact/full candidate fragments、catalogItems compaction、readiness / slotReadiness 和 full payload candidateLegalityAudit；`server/postgres_cache_store.py` 保留 SQL 读取、cache fingerprint、template read model、catalog health 外层字段和 response envelope。
- 本阶段不重新开放 `recommended_bis`、`season_recommendation`、`default_template`、`simc_preset` 或 `baseline_blocked`；上一刀合入后已补做 `WOW_DEPLOY_SKIP_BOOTSTRAP=1 WOW_DEPLOY_START_ASYNC_SYNCS=0` 热部署和线上 smoke，本刀按 Candidate Deployment Gate 在合入前执行候选部署 / 预览 smoke。

### Phase 5：发布、线上 smoke 与归档

目标：把本地 verified 变成 live verified，再归档。

验收：

- 发布前 CR 和回滚计划完成。
- 线上 `/health`、`/api/data/health`、关键 API、PG read model、systemd timer 或 UI evidence 按变更范围 smoke。
- roadmap、runbook、evidence manifest 和 cleanup 状态已回写。
- 没有证据的部分保留 risk，不写 done。

## First Execution Recommendation

第一轮 Phase 0 + Phase 1 已执行完成：

1. 已收口当前 Harness / current-truth / UI evidence 文档和 artifact。
2. 已用 `auto-route-screenshot.js` 完成 14 页当前运行截图证据。
3. 仍不在后端 owner map / characterization 准备好前启动热点文件拆分。

下一轮建议从 Phase 2 开始，把 Harness manifest 升级为每个 Standard / Strict 需求的 evidence packet 起点；再进入 Phase 3 后端 owner map 与 characterization。

## Success Criteria

- 小修仍保持轻量；大需求不会绕过需求合同和用户确认。
- 当前事实入口明确，旧计划、旧截图、旧 scorecard 不再越权。
- UI 交付状态由真实微信证据驱动。
- 推荐、装备、SimC、PG、health/admin、定时任务和部署 smoke 不再被单点改动误伤。
- 热点文件后续新增职责被 Harness 拦住，拆分有测试和 owner 支撑。
- 每次交付声明都能说清证据等级和不能证明什么。
