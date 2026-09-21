# 国服简体术语展示实施报告

2026-09-20。保留既有 WIP，修改前副本在 `docs/plans/.cn-terms-baseline/`；未提交、推送、重启或部署。程序执行仅使用云端既有依赖，本地仅文件读写、git 检查与定向 rsync。

## 变更

- `packages/domain/src/poe2-terms.zh-CN.json`：研究代理逐项核实的小词表，69 条（38 个去重技能/辅助、8 职业、23 升华），实际用户 48 颗宝石所涉名称优先。来源 PoE2DB `/cn/`，逐条 URL、读取日期 2026-09-20、词表版本 2026-09-20.1。来源未声明精确游戏补丁，不声称全库覆盖。参考研究 `2026-09-20-poe2-cn-terms-research.md/.json`；unknown 保留未覆盖范围。
- `packages/domain/src/poe2-terms.ts` + `index.ts`：按 kind/英文精确匹配展示名称；中文输入只精确反查唯一已核实项，保留辅助罗马阶级，未知中文拒绝提交并提示核实；原英文仍可作为引擎输入。槽位/配置和固定引擎提示中文化；无法解释的提示原文留在折叠原始数据。
- `server/app/poe2/presentation.py` + `tools.py`：共享读取同一 JSON，为 POE2 工具 import/list/get/calculate/job_get/compare/export 添加 presentation 来源、版本、当前相关术语与 unknown。get/export 从已按账号读取的构筑原 XML 提取当前 activeSkillSet 下实际技能组，保留组和宝石 attrs（enabled、level、quality、nameSpec、原 ID），空名不造词。英文/ID/XML/分享码/计算入参保持原义。
- `WebPoe2.tsx`：解析卡和摘要用国服职业/升华，详情技能名称保留等级，装备选项中文、值仍为原字段，修改摘要中文，技能编辑接受已核实中文且未知中文不发 API；有效配置展示已知中文字段，其余配置与节点/原始技能/原提示折叠核对。固定提示覆盖本次用户精魂负值、11/9 技能组、天赋点、空技能、护符和药剂引擎缺口。
- `server/app/chickenbro/agent/POE2.md` / `skills/poe2-build-analysis.md`：默认所有术语国服简体；国际服 PoB 不改变语言；依已核实对照，缺失先查国服来源，仍缺明确待核实；不猜译、不借 POE1 或繁体。同步 Web 当前字符串单入口说明。WoW `agent/AGENTS.md` 仅在默认语言一行补通用国服简体原则。
- 新增 `poe2-terms.test.ts`、`app_poe2_presentation_test.py`，更新 Web 测试与 Vitest include。

配置显示的暴击球/狂怒球/耐力球由研究代理同日核实于 `https://poe2db.tw/cn/Power_charge`、`https://poe2db.tw/cn/Frenzy_charge`、`https://poe2db.tw/cn/Endurance_charge`；其他槽位及引擎提示是产品字段/语句标签，不扩充为全库游戏名称映射。

## 云端验证

源码 `/opt/chickenbro-candidates/poe2-20260918/source`；日志同 root 下 `evidence/link-research/`。

- `npm run typecheck` 通过；相关 Web/helper/tests 定向 ESLint 通过。
- Python：`tests.app_poe2_presentation_test tests.app_poe2_chat_isolation_test tests.app_poe2_character_tools_test tests.app_chickenbro_codex_adapter_test`，76 项通过（0.459 秒）。验证 activeSkillSet/启用状态/等级品质、unknown、原分享码保持、owner-scoped 读取、提示规则；既有 Chat 隔离与适配器检查通过。日志 `cn-terms-tests.log`。
- Web 15 项 + API 1 项已通过（1.91 秒），包括国服职业升华展示、中文盾墙转回 Shield Wall、未知中文阻止提交。
- 最终 Vitest 3 文件 18 项通过（2.11 秒），包括 domain 2 项：来源词条、精确名称/unknown/输入反查、配置与真实固定提示。日志 `cn-terms-vitest.log`。初次命令因 Vitest include 未包含新文件只执行 16 项，已补 include 并明确重跑新文件。
- H5 独立输出 `/opt/chickenbro-candidates/poe2-20260918/cn-terms-web-build`，使用已有 Candidate 环境（`WOW_H5_PUBLIC_PATH=/poe2-candidate/`、API/auth 前缀同 Candidate、test 登录 UI）。webpack 5.91.0 构建通过，28979 ms，2 条体积告警。日志 `cn-terms-build.log`。未覆盖运行中 Web。
- 本地 `git diff --check` 通过。

root 负责切换 Candidate 与真实 Chat/UI 业务验证，本报告的静态和测试证据不替代该验收。
