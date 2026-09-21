# 管理后台双游戏统计 · 2026-09-21

已于 2026-09-21 按用户授权发布正式环境；管理员真实会话、独立聚合 SQL 和公网制品均已验证。

## 范围

- `/admin` 新增魔兽世界／POE2 独立切换，`/api/v2/admin/overview?game=wow|poe2` 默认 wow，其他值返回 400。
- 对话、反馈、活跃用户和趋势按游戏过滤。QQ 累计／新增账号维持全站口径并明确标注。
- 魔兽保留 SimC 和职业专精分布；POE2 展示 PoB 计算状态、成功率、异常结果、耗时及构筑导入数。导入计入活跃，软删除保留历史统计，复用不产生新任务计数。
- 沿用 QQ 管理员权限、只读快照事务、账号排除规则和不缓存响应；无迁移或新依赖。

## 验证

基线见 `source-sha256.json`。云端目录 `/opt/chickenbro-candidates/admin-games-20260921`，使用既有 Python、Node 22 和前端依赖；没有运行本地测试、构建或游戏引擎。

| 检查 | 结果 |
| --- | --- |
| 后端权限、日期、游戏参数和通用错误 | 7 项通过 |
| 独立 admin PostgreSQL fixture | 1 项通过；混合 WoW/POE2、非 QQ／错误应用／测试身份排除、异常来源、构筑单独活跃、软删除历史、空样本 |
| WebAdmin 合同和交互 | 6 项通过，含游戏切换后迟到响应隔离 |
| TypeScript / ESLint | 通过 |
| H5 构建 | 通过，现有体积警告 2 项 |
| 云端 Chromium | 1440 / 390 / 320px，切换与重复点击、游戏专属内容、无横向溢出、无页面异常 |
| 项目状态与 owners | 9 项通过 |
| 本地 diff | 无空白错误 |

隔离浏览器验证使用此次 H5 制品和拦截式 API fixture。发布后的管理员现有真实 QQ 会话和独立 SQL 对账见下方；未重新走 QQ OAuth 授权或声称用户手工验收。浏览器脚本为 [browser.cjs](browser.cjs)，结果为 [browser.json](browser.json)，[手机截图](poe2-390.png)。

浏览器运行需 `FONTCONFIG_FILE=/opt/chickenbro-candidates/poe2-20260918/runtime/browser/fonts.conf` 和 `LD_LIBRARY_PATH=/opt/chickenbro-candidates/poe2-20260918/runtime/browser/root/usr/lib/x86_64-linux-gnu`。初次启动缺该环境变量，补齐后通过。首次 SQL 验证发现动态 JSON key 缺少 text 类型，修复后真实数据库测试通过。首次构建缺 app 层既有依赖链接、初次 lint 受 macOS 打包元数据影响，隔离移出元数据并链接既有依赖后通过。


## 正式发布与复核

- 最终 backend `/opt/chickenbro-releases/admin-games-20260921-final`，Web `/var/www/chickenbro-web/releases/admin-games-20260921-final`。首次切换只修改 3 个后台文件；实际对账发现先前 POE2 发布合成身份仍被计入，补入 `poe2-release-smoke-%` 排除规则、通过 PostgreSQL 回归后追加一次精确 repository 文件发布。
- 保留 main 上 `77fbcf864` 的已提交更新日志并在云端重建。运行时 `server/app` 全部 146 个跟踪文件与最终本地源码 SHA-256 一致，3 个后台文件和 15 个 Web 制品见 [release.json](release.json)。
- 最终管理员现有 QQ 会话实页可切换两游戏；近 7 天全站账号 73、新增 14；魔兽 131 次提问、29 个模拟，POE2 2 次提问、1 个构筑、1 次计算，与 [独立 SQL 对账](live.json) 一致（瞬时快照，随业务变化）。
- 两游戏均验证匿名 401、非管理员 403 和 no-store；使用原有合成验证 owner 的短时非管理员会话，已撤销，未创建或冒用管理员会话。
- 15 个公网 Web 文件逐个 SHA-256 匹配，连续 3 次 readiness 正常，API/Worker 同版且原有环境配置完整保留。无数据库迁移、数据同步或数据删除。

## 恢复材料

私有精确清单和旧指针保存在 `/var/lib/chickenbro/releases/admin-games-20260921-final`，最初批次保存在 `/var/lib/chickenbro/releases/admin-games-20260921`。每次切换前校验原后端/Web 的全量文件哈希，持发布锁且确认 Chat、SimC、POE2 任务排空；保留旧目录。恢复执行器 `deploy.py rollback` 先核验当前版本并走同样排空门禁，再恢复上一个版本的 backend/Web。最终批次回退到首个后台分游戏版本；若需完全恢复发布前版本，再使用首批私有目录内保留的 `deploy.py rollback`。不覆盖数据库或其他批次配置；未执行生产回退演练。
