# 云端 SimulationCraft 更新（2026-09-15）

用户授权更新云端并验证。固定官方 midnight 提交 `ac0f3a3c7ff9e521137c0ca1760d548330c697f3`（游戏数据 `12.1.0.69814`），旧引擎 `f50a2121` 保留。

升级包含引擎、4 份引擎绑定目录、新版 zhCN 目录，以及两处必要兼容修复：英雄树初始免费点的校验/导出和私有 0700 构建产物的发现。节点顺序、结构、等级上限与专精映射经逐项比较保持一致，旧 Raider.IO 路径图据此复用；43 个 starterSpecs 更新从官方源码生成。历史引擎导出和旧中文目录保留。

## 已有验证

- 本地 49 项天赋/来源测试、8 项更新器测试通过。系统 Python 缺少 FastAPI，使用现有云端 Python 运行全部相关 231 项测试，通过；未安装新依赖。
- 新引擎4次有界运行：增强萨动态增援、防骑、痛苦术，以及独立天赋条目输入。均为100 iterations /60秒场景，正 DPS，报告可被产品解析；独立天赋导出与项目重建结果逐字一致。
- Candidate 共3个真实队列任务：单体、多目标及一个选择节点的天赋替换。正 DPS、有效配置/天赋、来源、runtime/compiler、幂等重放及第二账号隔离通过。
- 新中文目录按精确Build的5张Wago来源表重新生成并保留哈希。返回匹配的 catalogRevision；部分名称仍 unresolved，报告为 partial，不宣称全量中文覆盖。
- [失败记录](known-failures.json)保留构建发现、目录兼容及验收请求缺少locale参数的问题。缺少locale的任务已成功，只读回同一任务并验证幂等，没有重跑。

## 发布与恢复

当前为 Candidate 验证完成，尚待生产切换。使用本目录的固定manifest执行器，在共享发布锁和SimC锁下获取全任务空闲门禁；同时切换后端与引擎并重启API/Worker。切换前对旧引擎进行独立复制、哈希和模拟核验；旧后端和Web保留。线上计划3个同范围任务，45秒观察、10次readiness、错误日志及公网Web哈希核对。生产回切演练和人工QQ登录不在本次验证范围。

证据：[引擎](engine-smoke.json)、[Candidate](candidate.json)、[天赋与中文读回](candidate-talents.json)、[测试](test-results.json)、[目录构建](catalog-build.json)。原始报告与源码/构建保存在云端私有目录 `/var/lib/chickenbro-simc-update-20260915/` 及对应 `/opt/wow-simc/work/update-ac0...`，无到期自动删除。
