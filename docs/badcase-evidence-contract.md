# Badcase 证据与执行器合同

本文是 CLI 字段、身份绑定和拒绝条件参考；准备 group/freeze/release 时按需读取。通用方法见[工作流](plans/2026-09-08-badcase-workflow.md)，命令与续办见[执行说明](badcase-workflow-operations.md)。示例占位符不构成真实证据；具体批次与一次性例外不写入本文。

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
python3 scripts/badcase_workflow.py --root /绝对私有路径 freeze --file /绝对私有路径/manifest.json
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
  "criteria":{"scope":"对象、来源与请求范围正确","result":"实际结果与工具证据一致","coverage":"完整性与遗漏如实说明"},
  "assignments":{
    "original1":{"category":"original","input_sha256":"输入与截止原提问上下文的SHA256","used_for_design":true,"criterion_ids":["scope","result","coverage"],"transformation":""},
    "variant1":{"category":"variant","input_sha256":"不同输入SHA256","used_for_design":true,"criterion_ids":["scope","result","coverage"],"transformation":"改变与机制无关的名称、措辞或标识"},
    "holdout1":{"category":"independent_holdout","input_sha256":"独立输入SHA256","used_for_design":false,"criterion_ids":["scope","result","coverage"],"transformation":""},
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
  "criteria":{"scope":"passed","result":"passed","coverage":"passed"},
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
python3 scripts/badcase_workflow.py --root /绝对私有路径 release --batch BATCH_SHA256 --executor /绝对路径/本批已审查执行器 --executor-sha256 EXECUTOR_FILE_SHA256
```

执行器必须为操作者明确指定的本地绝对可执行普通文件，调用前重新核验文件SHA。不从反馈/批次读取命令，不用 shell 拼接内容。执行器接收一个参数 `preflight` 或 `release`，从 stdin 读取 `{"batch_sha256":"...","batch":{...}}`，只在 stdout 返回 JSON；私有操作日志保存到受限路径。执行总预算1800秒。执行器必须自己约束更短的排空/观察/回滚子预算。

`preflight` 为只读预检，返回同批 `batch_sha256`、实际 `baseline_sha`、`diff_sha256`、`clean:true`。必须查真实生产运行目录、目标与全量差异、待发布内容是否干净，不能回显输入假装验证。漂移时延期，不进入 publishing。`release` 必须再次在云端发布锁内核对基底，避免预检与切换之间的竞态；核验恢复包，有界等待 Chat/SimC 排空，不强杀任务，切换 API/Worker 并验证公网业务。

成功结果必须包含 `batch_sha256`、匹配目标的 `source_sha/build_sha256/config_sha256`、`status:"passed"`、本次发布开始之后的 `observed_at` 和 `checks`：`real_chat_terminal, history_readback, affected_tools, owner_isolation, web_artifact_verified, drained_without_kill, api_worker_identity, observation_passed` 全为true。HTTP200或进程成功不足以填写这些项。观察时长、错误/延迟/队列阈值须在本批受审查执行器中固定并记录；达不到门禁则不返回通过。

失败时执行器负责在同一云端锁内核对当前身份，按本批恢复包安全回滚并验证业务，私有记录确切的失败/恢复身份与结果。若回滚失败或目标已被别人切换，停止切换并通知用户。CLI 在切换调用前持久化 `publishing`；无有效live证据记 `failed`，不声称回滚成功。进程崩溃留下 publishing，不能再次盲目执行。同一失败目标SHA即使重新冻结也被拒绝；需要新修复与新证据。已released的同批调用是无操作并返回原live证明。

成功发布还会消费该批次的每个 `(group_id, report_sha256)` 版本。CLI 从 `state.releases` 中的 `released` 记录及 SHA 校验通过的不可变批次派生 `released_groups`，不改写原批准决定，也无需迁移状态。同组同报告不能靠更新 `created_at` 或其他批次身份重复冻结；此前已冻结的重复批次也会变为 `ineligible`，在执行器 preflight 前被拒绝。混合批次只要包含一个已发布报告版本，整个批次即被拒绝，不会静默删组后继续发布。

`status.groups.<id>.decision` 仍保留当前报告的批准决定，新增 `effective_status` 表示其实际状态；当前报告已经发布时为 `released`。`status.released_groups` 按组 ID、报告 SHA 列出成功批次 SHA，保留历史版本。报告发生实质变更时，`group` 会按原规则重置为待批准；新报告重新绑定适用授权并满足全部证据门禁后才可发布；超出持续授权范围时须另获明确批准。失败或 `publishing` 批次不消费报告，但原有失败来源禁止盲重试规则继续有效。

成功发布记录所指的批次缺失、损坏或 SHA 不符时，`status`、`freeze` 和 `release` 均报完整性错误并停止，包括同 SHA 的无操作调用。不得通过删除成功记录、伪造新报告或忽略错误绕过已发布版本限制；先恢复并核验真实不可变批次历史。


扫描与发布各有独立 flock，同类重入立即拒绝；状态锁最多等待10秒。扫描只在读取游标快照及原子合并时持有状态锁，网络读取和原文文件写入期间释放该锁；合并重新读取最新状态，保留并发产生的组批准和发布终态。外部发布期间扫描可继续，发布终态落库会等待短时状态写者完成。云端发布锁仍是固定执行器的责任，本地锁不能阻止其他发布来源。
