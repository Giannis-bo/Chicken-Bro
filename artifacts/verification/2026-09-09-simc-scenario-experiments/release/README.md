# SimC 场景实验正式发布 · 2026-09-09

用户明确授权“OK，提交，合入，发布”。功能源码已合入 main 并推送，API、Worker、Web 已发布；运行源码 `7ef8a5dfd9a48de9c9d6c12c660b6564446fd5eb`。随后发布文档提交不改变运行代码。

## 发布与验证

- [清单](manifest.json)：15 个后端文件更新/新增，13 个 Web 文件，全部绑定逐文件 SHA。Web 构建来自 `8a82c3d5f`，与最终运行提交的全部 apps/packages 源文件一致；没有混入旧 dist 目录产物。
- [本地检查](local-checks.json)：465 项后端、260 项前端、63 项控制面通过；H5 构建通过，存在已有资源体积警告。
- [隔离验收](candidate.jsonl)：独立 DB、Cookie、18790 API / 18794 工具端口、任务目录及 Worker。两个案例均由真实模型调用 get/options/preview/submit/get/compare，实际任务成功且生效配置验证通过；幂等、CSRF、QQ 授权 URL 和第二用户隔离通过。进程已停止，临时会话撤销。
- [生产切换](promotion.jsonl)：锁定准入表确认 Chat、SimC、queue 全部空闲，再同时切换 API/Worker/Web。仅新增本批 compiler v5 配置覆盖；没有数据清理、引擎升级或生产 migration。
- [公网业务](production.jsonl)：复用两个既有专用测试账号，新增生产身份为 0。Fusionbolt 仅替换节点 80999 为 entry 101872；Giannis 仅替换 trinket2 为物品 270164、装等 308、bonus 12838。真实模型完成预检、提交、等待与比较；每个结果由 Worker 核对实际天赋/装备 ID/覆盖装等。临时会话已撤销，验证对话与模拟记录保留在专用测试账号。
- [线上身份与文件](live-verification.json)：API/Worker cwd 与 compiler v5 一致，完整后端清单和公网 13 个 Web 文件匹配；旧 backend/Web 未变，结果保护触发器与约束有效。
- [浏览器](browser-verification.json)：原真实 QQ 会话刷新恢复，历史对话、SimC 工作台、引擎版本和旧报告可读。没有发送真实用户消息；本轮未重复真人 QQ OAuth。

第一轮模型验收已完成两种操作，但物品查询三次为空，暴露中文库未收录这两件饰品。修复后加入引擎英文名/ID 与受控候选目录回退，并新增会失败的回归后验证修复；最终隔离和公网两轮均重新通过。一次隔离启动命令误填目录 SHA，在启动服务前报模块不存在；改用实际 manifest 的目录后重跑通过，生产未受影响。

## 回滚与保留

当前 backend：`/opt/chickenbro-releases/simc-experiments-7ef8a5dfd9a48de9c9d6c12c660b6564446fd5eb`；Web 使用相同目录名，位于 `/var/www/chickenbro-web/releases/`。

前版本两端均为 `mini-retirement-7adcdeffa3566add1cc9fe33325df5b7360e29df`，内容哈希已核对保持不变。本批仅为 API 和 Worker 添加 `99-zzzzz-simc-experiments-7ef8a5dfd9a4.conf`，引用 root-owned 0600 `/etc/chickenbro-simc-experiments-7ef8a5dfd9a4.env`；其唯一字段为 compiler v5。

精确恢复入口：以 root 和现有 `/opt/chickenbro-runtime/bin/python` 调用 `/var/tmp/cb-simc-experiments-release-final/deploy.py /var/tmp/cb-simc-experiments-release-final/manifest.json rollback`。脚本重新通过空闲门禁，恢复两个旧指针，仅移除本批两个 drop-in，重新启动匹配服务；不覆盖数据库、不删除别批配置。恢复材料已核对，本轮未实际触发生产回滚，不称为恢复演练。

隔离库 `chickenbro_simc_exp_candidate_20260909`、私有目录 `/var/lib/chickenbro-simc-experiments-candidate` 和前一候选版本保留用于复核。其他任务 WIP、未跟踪文件和 worktree 均保留。

## 已发布范围

支持版本绑定的节点/整套天赋修改、受控场景参数、同进度饰品候选与同条件比较；制造/特殊装备版本并未全面覆盖，缺资料的组合仍拒绝或明确要求可靠资料。不把少量候选的对照当成全局最优，也不把误差内差异说成确定收益。
