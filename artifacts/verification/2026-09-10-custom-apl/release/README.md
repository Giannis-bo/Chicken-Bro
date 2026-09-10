# 自定义施法与术语检索发布

2026-09-10，用户明确授权“提交，合入，发布”。应用源码 `c408a30e676c9884d27b7c4ea8cad39f8ac45a01` 已在 main 提交、推送并上线。后续文档/证据提交不改变应用运行源码。

## 发布内容

- 9 个后端 overlay 文件，860 个后端文件总清单；API/Worker 同时启用 compiler v6。
- 13 个 Web 构建文件，API client 使用 scenarioVersion=4 读取自定义 APL；旧客户端响应仍兼容。
- 玩家术语先检索，结合职业/版本换词与来源；相关资料取不到时说明具体缺口，不编造当前技能或套装效果。
- 没有升级 SimulationCraft 引擎、新增依赖或数据库迁移，没有删除业务数据。

## 验证

[隔离业务](candidate-business.json)：实际 API→队列→Worker→结果链路两组成功，风暴守护者 0 秒→升腾 1.239 秒，以及升腾 0 秒→风暴守护者 1.238 秒。有效装备/天赋、任务幂等、第二账号访问拒绝、QQ 授权 URL、CSRF 与旧凭证拒绝通过；真实 Chat 进行了 4 次网页工具调用。

[公网业务](production-business.json)：复用已有的两个专用模拟账号，未新建生产用户。任务 `9d123a0f-3eba-4644-9f30-9ffecd52f7d0` 和 `c54e5b5b-ab75-44bf-bda6-a0f3134e33cd` 分别记录风暴守护者→升腾（0/1.241 秒）及升腾→风暴守护者（0/1.239 秒）。真实有效配置和报告 hash 绑定通过；Chat host gateway 读取实际动作样本、比较相同控制条件的任务成功，比较字段仅 actionLists 变化。差异在报告误差范围内，不作为某种顺序更优的结论。

公网真实 Chat `4a12b886-c8cd-429c-bf52-59be9ee665d5` 完成 4 次网页工具调用后给出资料缺口；本次公开来源未提供足以确认当前四件套的原文，因此这里只证明“先检索再回答”，没有宣称模型已掌握该套装效果。SSE 终态、历史、第二账号隔离及临时 session 撤销通过。测试会话已归档。

[Web](public-web.json)：13 个公网 HTTPS 文件 SHA256 与冻结清单完全一致。本机 Python 3.13 首次检查因证书链缺少 Authority Key Identifier 被拒绝；改用云端已有 Python 的默认 TLS 校验成功，没有关闭证书验证。H5 构建成功，保留两项资源体积警告。

应用验证复用同文件哈希的 112 项后端、12 项前端合同、typecheck/lint 结果；本轮提交前额外 29 项定向回归与提交后 H5 构建通过。文档收尾的控制面检查 63 项通过；首次发现新证据目录未进入保留规则，补上本批精确保留路径后重跑通过，没有执行清理。

本轮未重新执行人工 QQ 登录，不宣称用户亲自验收或生产回切演练已完成。

## 运行身份与回退

[精确清单](manifest.json)、[切换前](observation-before.json)、[切换后](observation-after.json)及[运行验证](runtime-verified.json)确认：后端位于 `/opt/chickenbro-releases/custom-apl-c408a30e676c9884d27b7c4ea8cad39f8ac45a01`；Web 位于 `/var/www/chickenbro-web/releases/custom-apl-c408a30e676c9884d27b7c4ea8cad39f8ac45a01`。原有 unit/drop-in 文件哈希不变，只新增本批两个 compiler override drop-in；有效环境除 compiler 版本外一致。

发布持有锁，排空 Chat runs/executions、SimC 与队列，并以数据库准入锁保护停止与切换。先启动 Worker 的实际工具监听，再开放 API；旧版本目录完整保留。

[私有恢复核验](recovery.json)绑定发布 manifest、原有效环境和恢复快照 hash。恢复快照 root/0600、父目录 root/0700；凭据未进入仓库。旧后端为 `badcase-3f0c15d988fd33fd08dae8514f70ee483862c3c8`，旧 Web 为 `admin-ops-web-8fba1535f226c5dd6eebbcd3980fc2ca52c4075f`。按空闲门禁回退：

```bash
sudo -n /opt/chickenbro-runtime/bin/python /var/tmp/chickenbro-custom-apl-release-c408a30e676c/deploy.py /var/tmp/chickenbro-custom-apl-release-c408a30e676c/manifest.json rollback
```

该入口同时恢复 backend/Web 指针，仅移除本批两个已核对内容的 drop-in；保留新版本和本批环境文件供追溯，不覆盖数据库。生产回切演练未运行。
