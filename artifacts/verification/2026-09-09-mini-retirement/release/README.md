# 小程序退役正式发布 · 2026-09-09

用户明确授权“OK，合入，提交，发布”。源码 `7adcdeffa3566add1cc9fe33325df5b7360e29df` 已在 main 提交并推送；后端和 Web 已发布。发布后追加的文档/验证提交不改变运行代码身份。

## 发布与验证

- [精确 manifest](manifest.json)：10 个后端文件更新、2 个已退役后端文件移除，14 个 H5 文件。所有保留 backend 文件逐字节/符号链接一致；新副本移除继承的 Python 缓存，旧版本不变。内部 apps/mini-taro 名称保留，不提供小程序运行或构建。
- [隔离 Candidate](candidate.jsonl)：独立数据库、Cookie、18790 API / 18794 工具端口、任务目录及 heartbeat。真实图片识别、断线继续、账号单活动回复、历史回放、CSRF、旧 Bearer/入口拒绝、第二用户隔离、SimC 入队/幂等/真实 DPS 和来源指纹全部通过。验证后 API/Worker 停止、临时会话撤销。
- [生产切换](promotion.jsonl)：锁定准入表核对 Chat/SimC/queue 全部空闲，再停 API/Worker、切换两个 symlink，Worker 持有 28794 监听后开放 API。没有修改有效业务环境配置、数据库迁移或再次删除数据。
- [公网业务](production.jsonl)：同样覆盖真实图片生成、SSE 回放、CSRF、所有权、SimC 结果与来源。真实 SimC DPS 为 157969.1518，报告持久化。复用先前 simc-all-smoke 专用合成 QQ 身份；新增生产账号为 0，临时凭据已撤销。其新增验证会话、图片和模拟记录明确归属既有测试账号，未混入真实用户。
- [线上身份和文件](live-verification.json)：API/Worker cwd 同指本次提交，完整后端清单匹配；公网 14 个 Web 文件匹配；QQ identity 仍为 18，微信为 0，约束有效，旧 backend/Web 与清理备份不变。
- [浏览器](browser-verification.json)：发布后原真实 QQ 会话继续有效，既有历史与图片、SimC 工作台和引擎版本正常。未发送真实用户消息，未冒称本轮重新完成真人 QQ OAuth。

本地完整检查见[上级记录](../README.md)。本次 commit 绑定 H5 构建再次通过，仍有两项既有包体积警告。首次隔离脚本漏传 QQ 登录的空 JSON body，返回 422；修正 smoke 请求后全部通过，业务源码未因此改变。

## 恢复与保留

当前 backend 为 `/opt/chickenbro-releases/mini-retirement-7adcdeffa3566add1cc9fe33325df5b7360e29df`，Web 为 `/var/www/chickenbro-web/releases/mini-retirement-7adcdeffa3566add1cc9fe33325df5b7360e29df`。

前版本两端均为 `simc-all-0649a2e858f51d633380873912ef75a8c91687ea`，目录与逐文件指纹完整保留。精确脚本在 `/var/tmp/cb-mini-retirement-release/deploy.py`，manifest 同目录。需要恢复时以 root 和已安装 `/opt/chickenbro-runtime/bin/python` 调用 `deploy.py manifest.json rollback`，仍须通过空闲门禁；脚本只恢复这两个指针并启动匹配服务，不恢复旧数据库，不删除任何别批 drop-in。本次未实际触发线上回滚，因此只记录恢复材料核对，不称为新一轮线上恢复演练。

186 个已确认微信测试账号的数据备份、独立恢复库和删除证据见[数据记录](../data-cleanup/README.md)。本轮再次核对备份 SHA，一致；恢复需先在新隔离库还原并按精确清单处理键冲突，禁止 dump 覆盖 QQ 新写入。

隔离库 `chickenbro_mini_retire_candidate_20260909` 与私有目录 `/var/lib/chickenbro-mini-retirement-candidate` 保留用于复核，服务进程已停止。其他任务未跟踪文件未加入本次提交，也未删除。

收尾核对：仓库 115 个已跟踪 server 文件全部匹配部署清单；新增发布文档后的控制面 63 项通过。构建日志仅清理行尾空白。原始 baseline.patch 保留补丁格式中的上下文空行，不改写该 WIP 快照；最终 diff 空白检查排除此唯一原始补丁附件。
