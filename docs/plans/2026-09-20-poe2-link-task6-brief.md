# Task 6 — Candidate 集成验证与交付

工作区 `.worktrees/poe2-20260918`，只云端运行，不提交推送合入或切换生产。Task 1–5 独立审查后执行。读取各 task report、progress ledger 和实际代码；本文件为交付验收核对，不是重复实施授权。

## 身份与恢复材料

- Candidate root `/opt/chickenbro-candidates/poe2-20260918`，API 8796、工具18794；DB 只允许 `chickenbro_poe2_candidate`；API/worker unit 前缀 `chickenbro-poe2-candidate-`。
- 2026-09-20 更新前备份 `evidence/pre-character-links-20260920/{web,runtime.py,api.service,worker.service}`。Web index SHA256 `4d75949e72bfad7040013d1f643e78d7b73ad309ccb94e4508c3d4c5560c4fe3`；旧 runtime hash `690cb9db1a4ff40d6ed63dbf17a00e7d8d51a75c45b58017996df58e3e99dd73`。
- Nginx Candidate snippet hash `00084da4d8b6dc6ad076db18cc278c9de42ff3fdc67559c4e9e59163f8ff47b5`，本次入口不需改 Nginx。生产 root 只读身份 `/var/www/chickenbro-web/releases/phase-state-32add63464e28ea53a9df23690cc1800dbe74953`，交付复核。
- Task 2 已在独立 Candidate 应用新增表迁移 0013；验证其增量与实际权限，撤回代码时保留新增表和导入资料，不删除旧记录或回滚他人并发修改。未执行数据库恢复演练。

## 最小完整验收

1. Task 2 migration/真实 wow_app 权限和 owner隔离、action幂等、cancel fencing、lease恢复已有证据；检查适配器实际装配不是默认关闭占位。
2. Task 3 collector 独立服务上执行实际 Chromium 公网分享；内核私网拒绝、无 DB/QQ 环境，Unix socket边界、并发/60秒回收已有证据可复用。开启仅 Candidate。
3. ninja 创建无远端读取，needs_input；本人上传现有真实 XML → 成功 build+baseline。回归 Life2813、ES962、Armour7284、Evasion14138。DPS按主技能配置另行展示，不宣称与来源面板严格相同。
4. WeGame 实际用户分享 → 净化预览+明确 missing_jewels 等缺项；不能 ready。存在未知装备/技能/任务奖励也列出。完整国服真实样本未取得必须单独保留待验收，不能把合成样本替代。
5. 真实云端浏览器：来源入口误配、两来源说明、国服读取及缺口、国际服打开原页/补充导入、进入步骤2不重复baseline、详情/导出；取消、刷新恢复、B不能访问A。390px宽无横向溢出，状态反馈和聚焦可用。
6. 既有手工 PoB/XML、示例构筑和魔兽导航保持可用。相关回归足够即停止，不拓展历史迁移。
7. 公网全部 Web 产物 hash 与本次 manifest逐一一致，Candidate runtime/source/engine/mapping身份明确；服务 active 与业务成功分别记录。

输出 `artifacts/verification/2026-09-20-poe2-character-import/README.md`、净化 business evidence、必要截图/manifest；不拷贝 sessioncookies、凭据、原始 WeGame sharetoken/openid。更新 docs 状态/验证矩阵/owner maps，独立整体审查后等待用户体验验收。

截图同样不能包含真实WeGame分享凭据或完整PoB正文；在截图前以测试专用CSS遮蔽链接/源码输入内容，或截取不含输入值的状态区域，报告注明遮蔽。不要为截图重发/修改导入任务。保存浏览器console/error时净化URL query/fragment与用户正文。

## 现成环境

Node `runtime/node-v22.19.0-linux-x64/bin/node`；Python `/opt/chickenbro-runtime/bin/python`；浏览器 `runtime/browser/node_modules/playwright` 与 `runtime/browser/chrome-headless-shell-linux64/chrome-headless-shell`；浏览器 LD_LIBRARY_PATH=`runtime/browser/root/usr/lib/x86_64-linux-gnu`、FONTCONFIG_FILE=`runtime/browser/fonts.conf`。

云端 H5 build 用现有部署文档的 Candidate环境和 `WOW_TARO_ISOLATED_BUILD=1`，构建输出核实后复制到root/web。不要重新运行旧 provision 覆盖已变更 unit；部署 collector 使用 Task3专用文件。旧 test sessions()可生成私有测试cookie，但 logout会失效，不能复用过期 fixture。
