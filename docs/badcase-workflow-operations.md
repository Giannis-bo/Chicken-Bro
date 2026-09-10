# Badcase 本地执行说明

执行入口为 `scripts/badcase_workflow.py`，仅使用 Python 标准库。默认私有目录为 `~/.local/share/chickenbro-badcase`；不将原始问题包提交 Git。该工具负责扫描、持久化、人工决策版本和发布门禁；诊断、对照回放和受审查的生产发布由 Codex/操作者执行并提供真实证据。程序不把扫描、退出码或布尔检查的存在当作独立业务验收。

## 扫描与隐私

```sh
python3 scripts/badcase_workflow.py scan
python3 scripts/badcase_workflow.py status
python3 scripts/badcase_workflow.py prune
```

在仓库目录运行；可在子命令之前用 `--root /绝对私有路径` 指定状态目录。SSH 固定使用 `wow-lighthouse`，远端命令固定为 `sudo -u postgres psql -X -qAt -v ON_ERROR_STOP=1 chickenbro_prod`，SQL 使用 `BEGIN READ ONLY` 和30秒 statement timeout；连接10秒、整个读取45秒超时。不会写原反馈或业务数据。

每轮最多100条（`scan --limit 20` 可降低预算）。按 `feedback_updated_at, run_id` 排序和推进复合游标，同时间戳分页不丢失；已扫描 run ID 永久去重。每8个成功扫描轮次启动一次从头核对，用独立复合游标逐页越过已读数据，补获时间戳较早但事务较晚提交的反馈；每页仍最多100条。核对启动时冻结当前高水位，达到该位置即结束，避免新反馈持续到来使核对永不结束。核对完成后恢复增量扫描，遗漏发生在本轮核对游标之后才提交的旧记录由下一轮核对补获。响应需严格排序。SQL 使用原始问题/回答 ID 且匹配同一 owner；上下文只取原问题之前最近40条，每条最多16000字符，裁剪会明确标记。原问题与原答案保存完整数据库文本（各最多100000字符），保留运行时 revision；不读取模型内部推理、认证配置或工具凭据。实际模型输入、历史工具调用、模型配置和 SimC 快照没有从当前表获取，问题包明确记为缺失，不能用今天的查询补作历史事实。

先写不可变问题包、再写脱敏扫描报告、最后原子落游标；中途失败保留旧游标，再执行同一命令可恢复。SQL错误、超时、超预算、坏游标或错误数据不会推进游标。目录0700、文件0600，写入使用临时文件、fsync 和原子替换，拒绝路径穿越及符号链接。报告不自动复制提问、回答、角色或用户标识，只有计数、游标和证据状态。`raw/` 保存原文，因此只在本地受限环境展开。

原文按首次保存时间保留7天；每次扫描前及显式 `prune` 清理到期问题包。离线期间无法按时删除，下一次运行首先清理；去重标识、哈希和脱敏报告保留。操作者提供的组说明及证据必须提前脱敏；不要把凭据或原始聊天全文放进长期保存的 `reports/`、`evidence/`。`status` 的 `batches` 列出冻结批次及 `eligible/ineligible/publishing/failed/released`；eligible仅表示本地门禁符合，真实基底仍须执行器preflight核实。无eligible批次时跳过发布，不创建空批次。`page_full=true` 表示本轮达到上限，需要下一窗口继续，不能声称已覆盖全部反馈。扫描器不是数据库变更日志：晚提交或回写较早时间戳的反馈通过周期核对最终补获，不能声称在下一次增量扫描中立即可见；源数据在被读取前删除则无法恢复。

## 按组人工决定

在私有目录创建组输入 JSON，例如：

```json
{"id":"G1","runs":["00000000-0000-0000-0000-000000000001"],"mechanism":"已观察到的查询入口缺失；根因待对照验证","scope":"限定后端查询能力；原题、变体、留出样本和owner回归"}
```

```sh
python3 scripts/badcase_workflow.py group --file /绝对私有路径/group.json
python3 scripts/badcase_workflow.py decide --group G1 --report-sha REPORT_SHA256 --decision approved --approval-ref '用户原始任务或消息引用'
```

`group` 输出 `report_sha256`；决策精确绑定组成员、问题包哈希、机制和范围，任一变更使决策回到 pending。仅在用户明确批准该组后调用 `decide`，不得把定时唤醒或模型结论写作用户批准。其他决定为 `investigate`、`deferred`、`no_verified_defect`。可继续调查但不进入发布。

向用户交付的人工报告仍须包含代表问题的脱敏表述、云端表现、验收条件、本地证据、根因假设与置信依据、影响范围、成本和所需决定。CLI的计数报告不替代这些诊断内容。

## 有界验证与收敛

执行泛化通用工具修复时，遵循[工作流的验证范围与停止条件](plans/2026-09-08-badcase-workflow.md#验证范围与停止条件2026-09-10-补充)：不无限扩展验证场景，不陷入无尽穷举，适可而止。

开始前在本轮私有验证记录中固定代表样本、重复次数、总调用/耗时预算及停止条件；满足现有五类证据与最低重复要求即可，不为穷举输入组合扩样本。预定验收达标且无阻断回归即停止验证，进入已授权的后续流程。只有新失败证据、实际改动或明确合同风险才补测受影响项；复用身份、条件及有效期仍满足门禁的已通过证据，不无故整套重跑。

留出更换与复测共用原总预算。预算耗尽或连续验证不再提供新信息时，保留失败记录、已通过证据及未覆盖范围，标记未验证/暂缓并报告缺口；下次窗口不自动重置预算盲重试。无关新场景另列后续事项。以上为操作者与自动化提示词的执行约束，不代表 CLI 已新增预算强制校验，也不降低现有发布门禁。

## 冻结不可变发布批次

操作者先完成完整基线差异审查、组合回归、Candidate 业务验证和恢复准备，再创建 manifest JSON：

```json
{
  "source_sha":"目标完整40位Git SHA",
  "baseline_sha":"实际生产基底完整40位Git SHA",
  "build_sha256":"实际目标后端产物64位SHA256",
  "config_sha256":"不含秘密值的受控配置身份64位SHA256",
  "diff_sha256":"生产基底到目标完整差异64位SHA256",
  "groups":{"G1":"已批准报告64位SHA256"},
  "backend_only":true,
  "excluded_impacts":[],
  "created_at":"2026-09-09T09:00:00.000000Z",
  "evidence":{
    "scope":{"path":"/私有目录/scope.json","sha256":"该文件字节SHA256"},
    "tests":{"path":"/私有目录/tests.json","sha256":"该文件字节SHA256"},
    "review":{"path":"/私有目录/review.json","sha256":"该文件字节SHA256"},
    "candidate":{"path":"/私有目录/candidate.json","sha256":"该文件字节SHA256"},
    "rollback":{"path":"/私有目录/rollback.json","sha256":"该文件字节SHA256"},
    "generalization":{"path":"/私有目录/generalization.json","sha256":"该文件字节SHA256"}
  }
}
```

示例占位值不能通过验证。每份证据 JSON 重复上述五个身份字段，另含 `kind`（对应证据名称）、`status:"passed"`、`observed_at`、非空 `details` 和 `checks` 对象。`details` 引用真正的测试结果/脱敏验收文件与哈希、运行条件和未覆盖范围，不能只写“通过”。以下检查键都必须严格为 JSON `true`：

| kind | checks |
| --- | --- |
| scope | full_baseline_diff_reviewed, backend_compatible, no_unapproved_commits, budget_unchanged |
| tests | targeted, combined_regression, held_out, normal_queries, owner_isolation, transport_contract |
| review | local_diff_review, no_blocking_findings |
| candidate | real_chat_terminal, history_readback, affected_tools, same_permissions, original_question_context |
| rollback | baseline_package_verified, safe_code_rollback, recovery_procedure_verified |
| generalization | `checks:{}`；按下面的逐组结构检查，不接受一个passed布尔值代替泛化证据 |

`rollback` 还必须包含 `rollback_identity:{"source_sha":"与baseline_sha相同","artifact_sha256":"恢复包SHA256","config_sha256":"恢复配置身份SHA256"}`。所有批次和证据必须在24小时内。证据是受审查的操作者记录；CLI 校验绑定及完整性，不能代替检查记录内容的真实性。

```sh
python3 scripts/badcase_workflow.py freeze --file /绝对私有路径/manifest.json
```

冻结后路径被替换为私有副本的规范 JSON SHA256，批次本身也以规范 JSON SHA256 命名。批次仅保留明确字段，不能携带 shell 命令或选择执行器。证据/批准不全、超时、错SHA、非纯后端或空批次直接拒绝。涉及客户端、破坏接口、迁移、身份权限、队列语义、基础设施、依赖、引擎升级或预算扩大，不能通过填写 `backend_only` 绕过人工发布；scope审查必须覆盖真实行为及完整差异。

## 泛化证据的结构化门禁

`generalization` 和其他证据一样绑定五个批次身份、`kind/status/observed_at/details`；额外 `groups` 必须精确覆盖本批已批准组。缺证据即“泛化未验证”，不能进入自动发布。每组对象包含：

- `mechanism`、`root_cause_evidence`、`applicable_scope`、`excluded_boundaries`：有依据的机制、根因证据、适用及不适用范围。
- `anti_case_specialization`：`status:"passed"`、`reviewed_diff_sha256`匹配本批、`findings:[]`、具体`review_notes`及`reviewed_surfaces:["code","prompts","config","data_mappings"]`。审查覆盖按问题文本、用户/角色/会话/run/报告ID、原题答案匹配的特判、硬编码和白名单。必要领域规则应有独立合同/可信来源并验证同类输入与边界。
- `baseline_config_sha256`、`before_prompt_sha256`、`after_prompt_sha256`、`conditions_sha256`、`model_config_sha256`：均为64位SHA256。conditions身份覆盖模型/profile配置、超时、工具预算、来源访问权限、固定数据条件和回放harness版本。前后源码/提示词/应用配置允许按各自精确身份不同，其余受控条件必须一致。
- `preregistration`：下述事先固定的验收条件及样本划分；`preregistration_sha256`为此对象的规范JSON SHA256（脚本`digest`，UTF-8、键排序、无多余空格）。先保存带可信时间和内容哈希的注册记录，再开始调试/对照验证；不能试完后重新生成一个早于试验的时间戳。程序核验时间先后和哈希绑定，操作者审查真实注册文件的来源。已有探索样本须明确标作探索/调试，不能重新命名为独立留出样本。
- `pairs`：键精确等于已注册sample_id，不能只提交成功样本。每项含`before`和`after`，各含全部`runs`及可重算的`summary`。

注册对象示例（同一类别可有多个sample_id；必须包含五类）：

```json
{
  "fixed_at":"2026-09-09T10:42:27.000000Z",
  "criteria":{"scope":"实际来源、难度和请求排名范围正确","casts":"实际读取排名报告的施法证据","coverage":"说明覆盖数量，不将子样本冒充完整前N"},
  "assignments":{
    "original10":{"category":"original","input_sha256":"输入与截止原提问上下文的SHA256","used_for_design":true,"criterion_ids":["scope","casts","coverage"],"transformation":""},
    "variant1":{"category":"variant","input_sha256":"不同输入SHA256","used_for_design":true,"criterion_ids":["scope","casts","coverage"],"transformation":"改变与机制无关的名称、措辞或标识"},
    "holdout1":{"category":"independent_holdout","input_sha256":"独立输入SHA256","used_for_design":false,"criterion_ids":["scope","casts","coverage"],"transformation":""},
    "normal1":{"category":"normal","input_sha256":"正常路径输入SHA256","used_for_design":true,"criterion_ids":["scope"],"transformation":""},
    "permission1":{"category":"permission","input_sha256":"权限边界输入SHA256","used_for_design":true,"criterion_ids":["scope"],"transformation":""}
  },
  "minimum_repetitions":2,
  "minimum_after_pass_rate":1.0,
  "model_stochastic":true
}
```

示例criteria仅表示结构；权限样本应预注册能直接验证预期拒绝/owner隔离的条件，不应机械复用不适用条件。每个variant须有变换说明且输入哈希不同于原问题；独立holdout不得用于调试/方案选择，且输入哈希不得与任何其他样本相同。若用于调整修复，必须撤销其holdout资格并补充新的独立样本，重新固定注册记录。涉及模型随机性时至少2次，实际前后次数相同且不得少于注册数量（每相位最多20次）；更多重复应完整披露。

每个run的字段：

```json
{
  "trial_id":"version-sample-repeat-unique-execution-id",
  "observed_at":"试验实际完成时间，不能早于fixed_at或晚于证据observed_at",
  "source_sha":"before等于baseline_sha，after等于source_sha",
  "config_sha256":"before等于baseline_config_sha256，after等于批次config_sha256",
  "prompt_sha256":"与该相位prompt身份相同",
  "runtime_id":"实际隔离运行身份",
  "conditions_sha256":"受控条件SHA256",
  "model_config_sha256":"模型配置SHA256",
  "input_sha256":"与sample注册输入哈希相同",
  "evidence_sha256":"实际试验/答案/工具轨迹脱敏记录的SHA256",
  "outcome":"passed",
  "criteria":{"scope":"passed","casts":"passed","coverage":"passed"},
  "duration_seconds":92.5,
  "cost":{"counter_scope":"source_gateway_only","tool_calls":8,"provider_tokens":null,"provider_cost":null,"provider_cost_unit":null}
}
```

`trial_id`必须在整个批次所有组、样本、before/after及重复中唯一，长度1至256，只能使用英文字母、数字、点、下划线、冒号或连字符且首字符为字母或数字。每次真实执行的`evidence_sha256`也必须全批唯一；不得复制一次成功结果并修改汇总次数冒充重复实验。`runtime_id`标识运行环境/版本，可以相同，不能替代独立执行ID。

`criteria`必须精确覆盖该样本注册条件，结果为`passed/failed/unavailable`；所有条件通过才允许`outcome:passed`，否则只能`failed/partial`。原题/变体/留出样本的before可以失败或partial（不得假装基线通过）；after必须达到注册通过率。正常及权限边界的before和after必须全部通过，不得用平均通过率掩盖退化。

每相位`summary`包含：`passed`（通过次数）、`total`、`pass_rate`、`duration_seconds`（总耗时）和`cost`（同run结构，按次数求和）。门禁从全部runs重新计算，任何不一致拒绝。`counter_scope`只能为`source_gateway_only`或`all_tools`，同一样本前后必须一致。供应商不暴露用量/账单时，`provider_tokens/provider_cost/provider_cost_unit`明确为null；工具调用数与耗时仍必须实测。null不当作0，相位汇总中任何一次未知则对应供应商总量仍为null；混合币种拒绝。仅测来源网关调用时，不声称统计了模型公共Web工具或全部费用。

上述JSON中的说明占位符不是可用SHA/时间。证据缺少任何类别、样本、重复、成本可用性说明、身份、反特判审查，或未达到注册验收、正常/权限退化时，必须继续调查/人工决定；不得把布尔checks补齐后绕过门禁。

## 固定执行器合同

```sh
python3 scripts/badcase_workflow.py release --batch BATCH_SHA256 --executor /绝对路径/本批已审查执行器 --executor-sha256 EXECUTOR_FILE_SHA256
```

执行器必须为操作者明确指定的本地绝对可执行普通文件，调用前重新核验文件SHA。不从反馈/批次读取命令，不用 shell 拼接内容。执行器接收一个参数 `preflight` 或 `release`，从 stdin 读取 `{"batch_sha256":"...","batch":{...}}`，只在 stdout 返回 JSON；私有操作日志保存到受限路径。执行总预算1800秒。执行器必须自己约束更短的排空/观察/回滚子预算。

`preflight` 为只读预检，返回同批 `batch_sha256`、实际 `baseline_sha`、`diff_sha256`、`clean:true`。必须查真实生产运行目录、目标与全量差异、待发布内容是否干净，不能回显输入假装验证。漂移时延期，不进入 publishing。`release` 必须再次在云端发布锁内核对基底，避免预检与切换之间的竞态；核验恢复包，有界等待 Chat/SimC 排空，不强杀任务，切换 API/Worker 并验证公网业务。

成功结果必须包含 `batch_sha256`、匹配目标的 `source_sha/build_sha256/config_sha256`、`status:"passed"`、本次发布开始之后的 `observed_at` 和 `checks`：`real_chat_terminal, history_readback, affected_tools, owner_isolation, web_artifact_verified, drained_without_kill, api_worker_identity, observation_passed` 全为true。HTTP200或进程成功不足以填写这些项。观察时长、错误/延迟/队列阈值须在本批受审查执行器中固定并记录；达不到门禁则不返回通过。

失败时执行器负责在同一云端锁内核对当前身份，按本批恢复包安全回滚并验证业务，私有记录确切的失败/恢复身份与结果。若回滚失败或目标已被别人切换，停止切换并通知用户。CLI 在切换调用前持久化 `publishing`；无有效live证据记 `failed`，不声称回滚成功。进程崩溃留下 publishing，不能再次盲目执行。同一失败目标SHA即使重新冻结也被拒绝；需要新修复与新证据。已released的同批调用是无操作并返回原live证明。

成功发布还会消费该批次的每个 `(group_id, report_sha256)` 版本。CLI 从 `state.releases` 中的 `released` 记录及 SHA 校验通过的不可变批次派生 `released_groups`，不改写原批准决定，也无需迁移状态。同组同报告不能靠更新 `created_at` 或其他批次身份重复冻结；此前已冻结的重复批次也会变为 `ineligible`，在执行器 preflight 前被拒绝。混合批次只要包含一个已发布报告版本，整个批次即被拒绝，不会静默删组后继续发布。

`status.groups.<id>.decision` 仍保留当前报告的批准决定，新增 `effective_status` 表示其实际状态；当前报告已经发布时为 `released`。`status.released_groups` 按组 ID、报告 SHA 列出成功批次 SHA，保留历史版本。报告发生实质变更时，`group` 会按原规则重置为待批准；新报告重新获得用户批准并满足全部证据门禁后才可发布。失败或 `publishing` 批次不消费报告，但原有失败来源禁止盲重试规则继续有效。

成功发布记录所指的批次缺失、损坏或 SHA 不符时，`status`、`freeze` 和 `release` 均报完整性错误并停止，包括同 SHA 的无操作调用。不得通过删除成功记录、伪造新报告或忽略错误绕过已发布版本限制；先恢复并核验真实不可变批次历史。


扫描与发布各有独立 flock，同类重入立即拒绝；状态锁最多等待10秒。扫描只在读取游标快照及原子合并时持有状态锁，网络读取和原文文件写入期间释放该锁；合并重新读取最新状态，保留并发产生的组批准和发布终态。外部发布期间扫描可继续，发布终态落库会等待短时状态写者完成。云端发布锁仍是固定执行器的责任，本地锁不能阻止其他发布来源。

## 调度边界与验证

Asia/Shanghai 每日00/06/12/18扫描；18点先冻结此前人工批准且验证完成的非空批次，再处理当轮反馈。机器离线错过窗口就记录错过，不在唤醒后无条件补发。heartbeat 应调用上述实际命令，并按当前授权完成诊断、报告和批准后的开发；CLI 不创建定时任务，也不会自行把 pending 组批准。当前两条反馈立即修复发布的直接授权只适用于本次批次。

```sh
python3 -m unittest discover -s tests -p badcase_workflow_test.py
```

离线测试覆盖分页同时间戳、原文/摘要边界、游标失败恢复、锁和路径权限、保留期限、版本批准、缺失/过期/篡改证据、漂移延期、失败防重试、真实业务证明缺失/错身份以及执行器内容不进shell。生产扫描、真实模型回放、Candidate、正式发布与恢复验证另行记录，不能把离线测试作为线上完成证明。


### 本批公网语义收尾门禁

受审查的 `execute-remote.py` 在公网回放、通用业务和Web制品检查后，等待独立语义审查，最多240秒且共用1350秒正常发布预算；原1650秒总预算中的300秒恢复额度不变。编排者应异步启动发布，读取私有 `live-rankings.jsonl` 及实际工具回执，独立评审两条完整回答，不能等待发布进程结束后才开始评审。

仅在实际评审后，将完整记录以原子写入方式保存到本批远端私有目录的 `live-semantic-review.json`（root所有、0600、普通文件、单链接）。记录绑定五项运行身份、`batch_sha256`、`observed_at`、`reviewer`，以及两条 `cases` 的 `case`、`runId`、`answerSha256`、`criteria`（acquisition/analysis/completion）和有证据的 `notes`。判定为failed时如实记录；缺失、过期、不匹配或负评都会触发原有回滚与基底业务恢复验证。通过记录的SHA进入最终live证据。程序验证身份和必备审查结果，不将这些字段的存在本身当作独立语义判断。


## 已授权的最终有限续验

`generalization.mode: "final_continuation"` 仅用于用户明确授权的有限续验。必须绑定预注册及输入/源码/配置/harness身份，完整保留原24条结果，核对同源码6条既有成功及6条失败，并提交6失败重验和2个精确发布入口的8条唯一回执与独立判词。该分支不把历史失败改判，也不宣称原整组12/12或重复稳定性通过；缺记录、错SHA、超时、工具/历史/权限不一致仍拒绝。实际生产两题、通用业务、独立语义及恢复门禁不变。

暂停后用户明确恢复发布可以新建带授权引用的准入记录；必须保留旧失败记录，重用未过期、同源码的有效验收，不重置失败批次。证据`details`必须是非空文本，补充既有来源说明时另存副本并重新绑定哈希；不得补造测试或把配置存在当作运行成功。
