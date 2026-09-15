# Chickenbro 生产 Runbook

适用于 Web/QQ、Chat 和云端 SimC。按当前任务授权及[验证矩阵](verification-matrix.md)操作；Badcase 持续授权范围见[工作流](plans/2026-09-08-badcase-workflow.md)。发布不自动授权新数据删除、依赖安装或基础设施变更。

## 运行身份与配置

操作前核对 `wow-lighthouse` 对应实例、代码/Web 指针、systemd API/Worker 有效工作目录与配置来源、数据库、实际文件和制品哈希。正式库为 `chickenbro_prod`，网站为 `https://www.chickenbro.cloud/`，readiness 为 `/api/v2/health/readiness`；这些是核对入口，不是本次健康证明。

- QQ 服务端配置为 `WOW_QQ_APPID`、`WOW_QQ_APP_KEY`、`WOW_QQ_REDIRECT_URI`，部署记录使用 root/0600 `/etc/chickenbro-qq.env`；正式 callback 为 `https://www.chickenbro.cloud/api/v2/auth/qq/callback`。不打印秘密值、DSN 或 token。
- 核对当前实际启用的 Codex、Chat 持久化、compiler、引擎与管理员配置；不从旧发布目录名推断当前版本。`WOW_ADMIN_USER_ID` 必须是经核验的内部 QQ owner，不能用昵称、QQ 数字或固定测试账号代替。
- Candidate 使用独立数据库、Cookie、目录和端口；涉及真实 QQ 授权时使用已登记 callback。测试环境见[测试账号说明](test-account-login.md)。

## 发布流程

1. 绑定本次源码、实际生产基底、完整差异、配置和逐文件制品清单，排除其他任务 WIP；运行受影响测试，准备旧代码/Web、精确 drop-in 清单及可核验恢复材料。
2. 在隔离 Candidate 验证受影响合同与真实业务，记录未覆盖项。涉及数据库迁移时先验证前后版本兼容与恢复方案，不能仅依赖应用回退。
3. 使用本批受审查且哈希固定的执行器。在发布锁内重查基底，有界等待 Chat execution、SimC 与队列安全排空；不能为了窗口强杀任务。
4. 按清单切换受控文件或指针，API/Worker 同时加载匹配源码与配置，Web 与接口合同一致。readiness 后继续核对真实业务、公网 Web 文件和系统有效配置。
5. 在事先固定的错误、延迟、队列阈值及观察时长内完成验收。保存本次运行身份、真实回执和独立语义结论；不以重启、HTTP 200 或脚本成功代替业务通过。

## 失败与恢复

先核对本批发布锁与当前身份，再按本批 manifest 恢复旧文件或指针、移除仅本批新增的 drop-in。恢复后重新核对 API/Worker/Web、配置和真实业务。若目标已被其他发布改变或恢复失败，停止继续切换并报告。

保护在途任务和新增写入。应用回退不等于数据库回退；不得用旧 dump 覆盖生产新数据，也不能随意撤销已应用迁移。Worker 中断依租约明确失败，不承诺恢复模型会话。记录失败、恢复结果与未验证范围，失败批次不盲重发。

## 数据与文件处置

每次删除使用本次明确授权的精确清单，不重放历史清理脚本或借用历史无备份授权。

- 核对目标 owner/provider、外键、JSON 任务引用、队列与图片；确认无活动 Chat、execution、SimC 或 lease，且不会继续产生目标业务。
- 删除前建立私有恢复材料，独立恢复到隔离环境并核对。最终事务重查清单与活动状态，按实际依赖顺序处置，保留审计、usage 和应保留记录的前后核验。
- 恢复数据时先在隔离库核对备份、清单与当前键冲突，再按明确方案恢复目标记录，不覆盖其他用户新写入。
- 到期私有副本遵循[保留与对账流程](badcase-workflow-operations.md#保留与独立处置对账)；生产数据、源码、发布 manifest 与恢复材料不因同目录存放而连带删除。

## 证据查询

[项目状态](project-state.json)登记历次交付身份与证据；执行前仍须核对当前实际运行。具体发布、配置和清理恢复材料按批次读取[历史操作记录](chickenbro-simc-production-runbook-history-20260911.md)，旧双端迁移见[早期归档](chickenbro-simc-production-runbook-pre-mini-retirement.md)。归档中的“当前”只指记录当时，不能直接作为今日命令或授权。

## 2026-09-13 鸡哥直接结论表达

API/Worker运行源码 `730882f2aef78f4460295800065c5d82b7fb7d72`，核心、WCL与答案修正提示词禁止无关防御性尾句。8文件同版overlay，未改数据库、引擎、环境和Web；144份后端实际清单、13份公网Web文件及线上4条业务验收通过。

root/0700 `/var/lib/chickenbro-direct-conclusions-20260913/` 保留manifest、overlay、deploy.py和root/0600恢复快照。以root执行本批 `deploy.py manifest.json rollback`，在相同全任务空闲门禁下恢复旧2294cb95版本后核验业务；不覆盖数据库。旧版本保留，恢复材料已核验，未实际回切。[本批证据](../artifacts/verification/2026-09-13-direct-conclusions/README.md)。

## 2026-09-11 Web 会话返回状态修复

本批仅切换静态 Web 到 `chat-return-0f8b3ce9da11012e1afdcaaa5675d243ae0f8d67`，API/Worker 继续运行 `badcase-b406fc9155a03edba9e95912713606736fb2a1bd`。13 份公网文件、真实浏览器加载公网构建后的隔离会话交互与 readiness 通过。未重启服务、迁移或写生产业务数据。

root/0700 发布包 `/var/lib/chickenbro-chat-return-20260911/` 保存完整静态包、manifest、旧目录清单及发布执行器。回退执行 `python3 /var/lib/chickenbro-chat-return-20260911/deploy-web.py rollback /var/lib/chickenbro-chat-return-20260911/release-manifest.json`（root），只在当前指针和两版 SHA 均匹配时原子恢复旧 `research-22c681f99...`。旧版保留且逐文件核验；未实际回切。见[本批记录](../artifacts/verification/2026-09-11-chat-return-state/README.md)。

## 按需流程发布（2026-09-12）

API/Worker运行源码2294cb95095a3822e1f4e2c43e225bf0bfdb2f63，8文件增量；144份后端及13份公网Web文件核验，Web保持chat-return-0f8b3ce9。核心规则与四份流程、读取器及MCP必须同release，禁止仅复制核心文件。run-identity.json只含run UUID，用于精确审计流程调用。

私有root/0700包 `/var/lib/chickenbro-skills-release-20260912/` 保存manifest、overlay、deploy.py与root/0600恢复快照。恢复以root运行本批 `deploy.py manifest.json rollback`，使用相同空闲门禁恢复旧b406fc915并验证业务；不回滚数据库。旧版保留，恢复材料已核验，未实际回切演练。[发布与已知效率边界](../artifacts/verification/2026-09-12-agent-skills/README.md)。

## 2026-09-14 取消 Chat SimC 次数上限

运行源码 `22037c2a27c8db331e31d7a481425c97455f7c99`，四文件 overlay，API/Worker 同版；单轮与跨研究均不限新模拟次数，历史计数和幂等保留。Candidate 与线上第五次提交均得到真实正 DPS，并完成第二账号隔离与消息重放验证。Web、数据库结构和引擎未改变。[证据](../artifacts/verification/2026-09-14-simc-quota/README.md)。

恢复包为 root/0700 `/var/lib/chickenbro-simc-quota-20260914/`，含固定 manifest、deploy.py、overlay 和 root/0600 恢复快照。以 root 运行本批 `deploy.py manifest.json rollback`，在共享发布锁及全任务空闲门禁下恢复旧 `cdc7d262`，随后核对业务。旧文件独立复制哈希核验通过；未进行生产回切演练。

## 2026-09-15 SimC 引擎与绑定目录更新

运行源码 `057378afc7b30e904b6bdd333283c93867dfb4b0`，引擎 `ac0f3a3c7ff9e521137c0ca1760d548330c697f3` / `12.1.0.69814`。9文件overlay包含英雄树免费点兼容修复、更新器私有权限修正及匹配目录；API/Worker同版，Web保持原制品。新任务使用新引擎，历史结果保留原始runtime身份；跨引擎比较继续拒绝。

恢复包 root/0700 `/var/lib/chickenbro-simc-update-20260915/` 保存manifest、engine-manifest、deploy.py、overlay和root/0600环境快照。以root运行 `/opt/chickenbro-runtime/bin/python /var/lib/chickenbro-simc-update-20260915/deploy.py /var/lib/chickenbro-simc-update-20260915/manifest.json rollback`，在共享发布锁、引擎锁和全任务空闲门禁下同时恢复旧后端22037c2a与旧引擎f50a2121。旧引擎独立副本已核对哈希并实际模拟成功；生产回切演练未执行。原始源码、构建与报告保留，不设置自动清理。[本批证据](../artifacts/verification/2026-09-15-simc-update/README.md)。
