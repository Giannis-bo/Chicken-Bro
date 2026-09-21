# POE2 国际服 PoB 字符串入口实施报告

2026-09-20。本轮范围见 `2026-09-20-poe2-pob-only.md`。仅修改以下文件，保留全部已有 WIP；修改前副本位于 `docs/plans/.pob-only-baseline/`：

- `apps/mini-taro/src/web/WebPoe2.tsx`
- `apps/mini-taro/src/web/WebPoe2.module.scss`
- `apps/mini-taro/src/web/web-poe2.test.tsx`

## 行为

Web 第一步只有国际服 PoB 2 字符串导入，指向 `https://poe.ninja/poe2/builds` 并说明角色页的 `IMPORT CODE FOR PATH OF BUILDING` 区复制操作。保留 PoB 官方项目和下载链接。移除角色链接组件挂载、来源选择、XML 原文/文件上传、示例导入和赛季手填。旧服务端合同、独立角色链接组件及历史记录未删除。

复用 `importBuild`，提交前拒绝空输入、URL、XML、明显非 base64 字符；标准和 URL-safe 字母表及末尾 padding 可通过前端初筛，真实格式继续由服务端判定。错误显示只接受 PoB 2 字符串，前端拒绝时不发 API 请求。产品入口说明支持国际服；字符串不宣称已验证账号、来源区服或角色名称。

成功停在第一步，显示独立 `section aria-label="已解析角色"`，标题“角色解析成功”。卡片只显示 summary 中实际返回的 level / className / ascendancy，构筑名称明确标注为管理记录。没有伪造角色名、账号或赛季。点击“继续调整与对比”后进入第二步，既有基线、比较、详情和历史访问保留。

“＋ 导入新构筑”清除成功卡和输入、撤销当前选择但保留侧栏历史。初始历史迟到时合并记录，不覆盖已解析构筑、选择或步骤。auth 生命周期守卫拒绝旧账号导入结果。已弃用的旧 import sessionStorage 不再被入口恢复和自动推进。

## 云端验证

所有程序执行均在 `ssh wow-lighthouse`；本地只有文件读写、git 检查和定向 rsync。云源码目录 `/opt/chickenbro-candidates/poe2-20260918/source`。仅以上三个文件同步到源码目录，未覆盖运行中 Web 或重启服务。

使用现有 Node `/opt/chickenbro-candidates/poe2-20260918/runtime/node-v22.19.0-linux-x64/bin` 及已安装依赖：

- `npm run typecheck` 通过。
- `node node_modules/eslint/bin/eslint.js apps/mini-taro/src/web/WebPoe2.tsx apps/mini-taro/src/web/web-poe2.test.tsx --max-warnings=0` 通过。
- `npm run test:taro -- apps/mini-taro/src/web/web-poe2.test.tsx packages/api-client/src/poe2.test.ts`：2 文件 15 项通过，1.94 秒。覆盖手动继续、真实字段展示、6 类拒绝输入、API 格式拒绝、新导入清卡/保留历史、迟到历史合并、旧账号迟到、既有比较详情和计算失败显示。
- 本地 `git diff --check` 通过。

日志：云端 `evidence/link-research/pob-only-tests.log`。

H5 使用 Task 5 已有 Candidate 环境变量，独立输出 `/opt/chickenbro-candidates/poe2-20260918/pob-only-web-build`；日志 `evidence/link-research/pob-only-build.log`。构建成功，webpack 5.91.0 耗时 26524 ms，2 条体积告警。完整输出 SHA256 清单为 `evidence/link-research/pob-only-web-sha256.txt`。实际浏览器和真实用户字符串业务验收由 root 执行，本文测试不代替用户验收。

未提交、推送、合入、部署服务或切换生产。
