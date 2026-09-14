# Badcase 执行说明

通用流程、授权范围、工具抽象与有界验证遵循[工作流](plans/2026-09-08-badcase-workflow.md)。本文件只说明命令、状态与恢复入口；[证据合同](badcase-evidence-contract.md)定义冻结和执行器字段，CLI 不代替诊断、真实回放与独立业务审查。

## 状态与入口

定时任务使用 `/Users/boyuan/.codex/badcase/chickenbro`，CLI 默认目录为 `~/.local/share/chickenbro-badcase`；实际执行必须显式选择同一状态根，避免产生两份账本。执行器仅用 Python 标准库。

```sh
python3 scripts/badcase_workflow.py --root /Users/boyuan/.codex/badcase/chickenbro scan
python3 scripts/badcase_workflow.py --root /Users/boyuan/.codex/badcase/chickenbro status
```

先读当前状态与简洁交接，具体授权引用、预算、保留清单和独立交付记录按需读 `operational-state.json` 及其引用。持续授权内无需逐组/逐版确认，仍须将每组实际报告 SHA 绑定可核验的授权凭据；范围外另获授权。历史凭据可从[归档](badcase-workflow-operations-history-20260911.md#当前持续授权2026-09-10)追溯，不能把其中旧预算、组名或单次例外扩为通用授权。

## 扫描与隐私

```sh
python3 scripts/badcase_workflow.py --root /绝对私有路径 scan
python3 scripts/badcase_workflow.py --root /绝对私有路径 status
python3 scripts/badcase_workflow.py --root /绝对私有路径 prune
```

在仓库目录运行；可在子命令之前用 `--root /绝对私有路径` 指定状态目录。SSH 固定使用 `wow-lighthouse`，远端命令固定为 `sudo -u postgres psql -X -qAt -v ON_ERROR_STOP=1 chickenbro_prod`，SQL 使用 `BEGIN READ ONLY` 和30秒 statement timeout；连接10秒、整个读取45秒超时。不会写原反馈或业务数据。

每轮最多100条（`scan --limit 20` 可降低预算）。按 `feedback_updated_at, run_id` 排序和推进复合游标，同时间戳分页不丢失；已扫描 run ID 永久去重。每8个成功扫描轮次启动一次从头核对，用独立复合游标逐页越过已读数据，补获时间戳较早但事务较晚提交的反馈；每页仍最多100条。核对启动时冻结当前高水位，达到该位置即结束，避免新反馈持续到来使核对永不结束。核对完成后恢复增量扫描，遗漏发生在本轮核对游标之后才提交的旧记录由下一轮核对补获。响应需严格排序。SQL 使用原始问题/回答 ID 且匹配同一 owner；上下文只取原问题之前最近40条，每条最多16000字符，裁剪会明确标记。原问题与原答案保存完整数据库文本（各最多100000字符），保留运行时 revision；不读取模型内部推理、认证配置或工具凭据。实际模型输入、历史工具调用、模型配置和 SimC 快照没有从当前表获取，问题包明确记为缺失，不能用今天的查询补作历史事实。

先写不可变问题包、再写脱敏扫描报告、最后原子落游标；中途失败保留旧游标，再执行同一命令可恢复。SQL错误、超时、超预算、坏游标或错误数据不会推进游标。目录0700、文件0600，写入使用临时文件、fsync 和原子替换，拒绝路径穿越及符号链接。报告不自动复制提问、回答、角色或用户标识，只有计数、游标和证据状态。`raw/` 保存原文，因此只在本地受限环境展开。

原文按首次保存时间保留7天；每次扫描前及显式 `prune` 清理到期问题包。离线期间无法按时删除，下一次运行首先清理；去重标识、哈希和脱敏报告保留。操作者提供的组说明及证据必须提前脱敏；不要把凭据或原始聊天全文放进长期保存的 `reports/`、`evidence/`。`status` 的 `batches` 列出冻结批次及 `eligible/ineligible/publishing/failed/released`；eligible仅表示本地门禁符合，真实基底仍须执行器preflight核实。无eligible批次时跳过发布，不创建空批次。`page_full=true` 表示本轮达到上限，需要下一窗口继续，不能声称已覆盖全部反馈。扫描器不是数据库变更日志：晚提交或回写较早时间戳的反馈通过周期核对最终补获，不能声称在下一次增量扫描中立即可见；源数据在被读取前删除则无法恢复。

## 按组绑定授权与决定

在私有目录创建组输入 JSON，例如：

```json
{"id":"G1","runs":["00000000-0000-0000-0000-000000000001"],"mechanism":"已观察到的查询入口缺失；根因待对照验证","scope":"限定后端查询能力；原题、变体、留出样本和owner回归"}
```

```sh
python3 scripts/badcase_workflow.py --root /绝对私有路径 group --file /绝对私有路径/group.json
python3 scripts/badcase_workflow.py --root /绝对私有路径 decide --group G1 --report-sha REPORT_SHA256 --decision approved --approval-ref '用户原始任务或消息引用'
```

`group` 输出 `report_sha256`；决策精确绑定组成员、问题包哈希、机制和范围，任一变更使决策回到 pending。范围内按当前持续授权调用 `decide` 并引用可核验的授权记录，无需逐组或逐版确认；范围外须另获明确授权。不得把定时唤醒或模型结论写作用户批准。其他决定为 `investigate`、`deferred`、`no_verified_defect`。可继续调查但不进入发布。

向用户交付的人工报告仍须包含代表问题的脱敏表述、云端表现、验收条件、本地证据、根因假设与置信依据、影响范围、成本和所需决定。CLI的计数报告不替代这些诊断内容。

## 验证、冻结与发布

按[泛化验收](plans/2026-09-08-badcase-workflow.md#通用修复与泛化验收必须满足)及[停止条件](plans/2026-09-08-badcase-workflow.md#验证范围与停止条件)完成组级证据。`freeze` 前核对真实源码/基底/构建/配置/完整差异、同条件五类对照、审查、Candidate 及恢复准备，具体字段见[证据合同](badcase-evidence-contract.md)。

```sh
python3 scripts/badcase_workflow.py --root /绝对私有路径 freeze --file /绝对私有路径/manifest.json
python3 scripts/badcase_workflow.py --root /绝对私有路径 release --batch BATCH_SHA256 --executor /本批已审查执行器绝对路径 --executor-sha256 EXECUTOR_FILE_SHA256
```

冻结只表示本地门禁符合，真实基底仍需执行器在发布锁内预检。异步编排发布，在执行器规定的时间与恢复预算内及时审查本批线上回答、工具回执和身份；只提交真实判词，不预填通过，不等进程结束后才开始语义审查。

已 released 的报告版本不重复发布；publishing/failed 先对账，不能删除历史或伪造新报告绕过失败锁。独立交付只在报告 SHA、证据 SHA 和适用范围全部匹配时用于避免重复工作，不冒充 CLI release 事件。

## 保留与独立处置对账

原始问题包按扫描器既有规则处理。额外私有副本清单由调度 Agent 按已登记流程消费；`_prune` 只处理状态根的 `raw/*.json`，不能据其成功推断其他目录已清理。

- 读取已登记的精确清单、原到期时间和逐文件哈希基线，不扩大父目录范围或重新计时。
- 到期前保留；到期后校验清单自身及目标哈希、大小、文件类型、无活动进程/发布引用与 runbook 恢复门禁。拒绝符号链接、非普通文件和意外新增文件，不递归删除父目录。
- 只处置完全匹配的到期文件，空目录可 rmdir。缺失仅记 already_absent；失败保留目标并报告，执行中断按逐文件结果续办。
- 生产记录、源码、rollback metadata、恢复快照、发布 manifest 与原清单独立保留；结果脱敏读回，全部完成后幂等无操作。

现存登记及恢复入口按需查[保留记录](badcase-workflow-operations-history-20260911.md#2026-09-11-联合发布私有副本保留登记)、[处置凭据](badcase-workflow-operations-history-20260911.md#联合私有副本到期处置)和[独立交付映射](badcase-workflow-operations-history-20260911.md#独立交付与旧cli状态对账)。这些记录保留精确路径和哈希，不是本次已删除的证明。

## 调度与检查

具体时间和通知策略由现有定时任务管理；每个窗口按当前授权扫描、诊断并发布达标批次。离线/失败时记录实际状态，不无条件补发，不把唤醒当作扫描或发布成功。

```sh
python3 -m unittest discover -s tests -p badcase_workflow_test.py
```

离线检查覆盖游标、锁、隐私、保留、授权绑定、证据完整性及失败防重试。生产扫描、模型回放、Candidate、线上及恢复验证分别记录。单次续验或排除历史见[归档](badcase-workflow-operations-history-20260911.md)，没有新的精确授权不得使用例外。
