# 全职业 SimC 支持验证 · 2026-09-09

## 发布结果

2026-09-09 已按用户授权提交、合入 main 并发布后端/Web。线上原始野德任务成功，治疗拒绝、幂等与账号隔离通过；846 个后端文件及 13 个 HTTPS Web 文件核对通过。详见 [发布记录](release/README.md)。下文保留发布前的调查与验证阶段证据，最终生产状态以发布记录为准。

## 发布前实现结果

- 已实现 40 专精识别；配置 `all` 开放 33 个输出/坦克专精，7 个治疗专精统一返回 `HEALER_SPEC_UNSUPPORTED`，Web 展示“SimC 不支持治疗专精进行模拟”。未知专精、未开放配置与引擎不可用使用独立错误码。
- 33 个非治疗专精均有云端正数 DPS 和正式语义解析成功证据：27 个同版本官方样例，6 个实时 Raider.IO 角色。逐项见 [summary.json](summary.json)。这些是有界 100 次 / 60 秒 / 单目标验证，不代表每种配装、天赋与战斗配置均通过。
- 用户原始角色“魔魔糊胡萝卜”在隔离源码中以 `all` 配置读取就绪、无 blocker、完成真实云端模拟；见 [character-candidate-final.jsonl](character-candidate-final.jsonl)。没有写入用户业务历史或冒充线上提交。
- 增辉保持 SimC 自带简化队友模型；解析器严格核验当前引擎已知队友集合，唯一目标角色及技能身份，不合计队友 DPS。提交与报告明确模型局限。坦克只表示 DPS，不承诺生存指标。
- 噬灭中文名称按[国服官方说明](https://wow.blizzard.cn/news/24235744/index.html)补齐。

## 身份与边界

源码基线 `d58bfbee7ca22dff1aa4d22c32c879c325ef1cc4`；工作区改动未提交，各产品文件 SHA 见 summary。云端隔离源码为 `/tmp/chickenbro-all-specs-20260909.TbBdl8`，只使用已有运行依赖。

引擎源码 `f50a2121bf894570146507496f3e113bff68e445`，二进制 SHA `69b3e5fb56f3b7149fa239059cb510f1924ef5cd6690db718812df4d938172da`。没有更新、下载或本地运行 SimC。

云端验证是隔离 Python 进程调用来源适配器、编译器及现有引擎；不是独立 DB/API/Worker 全套 Candidate，不是公网业务写入验收。生产 API/Worker、环境文件、Web 指针均未变更，旧进程名单仍只有元素/增强萨。未 push 或合入。

## 本地验证

- 477 个后端测试通过，含新专精矩阵、治疗不入队、野德幂等、第二账号拒绝、报告身份。见 `backend-tests-final.log`。
- 281 个 Web/前端测试通过，含真实组件渲染、治疗提交禁用、增辉模型说明。见 `frontend-tests-final.log`。
- typecheck、lint、H5 构建通过；H5 仍有两条既有包体积警告。构建目录 `/tmp/chickenbro-all-specs-h5-20260909`，没有覆盖其他任务预览。
- 62 个控制面、80 个部署脚本和 11 个 Candidate 验收逻辑测试通过。新增计划及验证目录已纳入保留规则，现有其他任务的文档改动保留。
- 云端 5 个涉及执行的源码文件 SHA 与本地精确一致，见 `cloud-source-sha256.txt`；Web 13 文件哈希见 `web-manifest.json`。
- 新增测试先观察失败；`red-tests.txt`、`ui-red-tests.txt`、`web-regression-red.log` 保留回归证据。
- 初次系统 Python 全套测试因缺少 FastAPI 未通过，后续复用既有 `/tmp/chickenbro-merge-check-venv-20260907` 运行全部通过，没有安装依赖。
- 未重跑 PostgreSQL 专项或真实 QQ 登录；本次不修改数据、认证或队列持久化合同。未声称真人浏览器验收。

## 引擎样例调查

`engine-probe.jsonl` 首轮 MID1 样例有旧天赋与引擎目录不匹配的问题，保留失败原始证据。优先同版本 MID2 后有 27 个专精通过。剩余浩劫、惩戒、三系战士使用当前 Raider.IO 角色验证；来源偶有专精/天赋不一致，未修改或猜测天赋以强行通过。

`remaining-candidate-probe.jsonl` 验证本轮职业编译名称；`augmentation-inspect.jsonl` 记录原有单角色解析拒绝默认简化队友；`augmentation-candidate.jsonl` 记录修复后的同类真实角色成功。只有 summary 列出的成功证据用于覆盖统计。

## 发布准备

发布需包含 summary 中的后端文件、四个 service 配置及当前构建 Web。新建独立可回滚版本；API 和 Worker 的最后生效环境文件均须设置 `WOW_SIMC_SUPPORTED_SPECS=all`，防止旧 EnvironmentFile 覆盖 unit 默认。保留旧版本和原配置，核对空闲队列/活动请求后切换；失败恢复原指针和配置。

上线后核验两个实际进程的能力配置、精确源码/Web 文件身份、原始野德正式导入/任务结果、治疗提示和第二账号隔离。上述生产步骤本轮尚未执行。
