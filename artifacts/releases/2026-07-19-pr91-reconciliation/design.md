# PR #91 Mainline Reconciliation Design

状态：`requirement_contract_approved`

确认日期：`2026-07-19`

## 用户目标与承诺

微信用户在四个一级入口之间切换时，TabBar 必须立即显示真实激活项；页面滚动、进入详情和返回时，顶部内容不得穿透安全区、覆盖系统胶囊或丢失返回入口；正式构建不得因输出目录处于半成品状态而让开发者工具白屏。整合后继续使用当前已经发布并通过回读校验的 `https://api.chickenbro.cloud/wow-assets/releases/2026-07-19-taro-full-integration`，不把未发布的资源或诊断状态包装成生产可用。

## 当前事实

- 当前主线为 `65be719204d4e398cede2dd1a947821cbd00c3d4`，即 PR #92 的合并提交。
- PR #91 当前 head 为 `600f09bc91dca8236627e6001bd1160dd75c4821`，相对共同基线有 13 个独立提交和 154 个文件变化。
- PR #92 相对同一基线有 15 个独立提交；两个 PR 有 25 个重叠文件，但没有可直接复用的 patch-equivalent commit。
- 当前 `main` 已拥有 14 路由、typed API/domain、生产 HTTPS 请求域名、immutable 远端素材根、发布包门禁和候选部署证据。
- #91 中的 `static.chickenbro.cloud/wow-media/releases/2026-07-19-wow-icons-v1` 尚未发布，不能替代当前生产素材根。

## 方案选择

### 采用：在 #91 上非改史整合当前主线

把当前 `main` 以普通 merge commit 合入 `codex/cdn-api-publishing`，不 rebase、不 force push。冲突文件以当前主线 owner、合同和用户可见行为为基线，再逐项恢复 #91 仍缺失的行为。最终继续使用原 PR #91 完成 CI、候选验证和合并，使 GitHub 将 #91 记录为 merged。

### 未采用：直接合并现有 #91

当前 GitHub 返回不可直接合并；直接处理冲突会让旧文档、旧 route 行为、fallback 语义和未发布 CDN 状态混入主线，无法证明 #92 的主线合同未被回退。

### 未采用：rebase 或新建替代 PR

rebase 需要改写公开分支历史；新建替代 PR 虽然 diff 更小，但不能满足让 #91 本身以 merged 状态关闭的目标。

## 整合边界

### 必须保留或按当前 owner 重建

1. 四个 Tab 根页在 `useDidShow` 时发布真实 route identity；custom TabBar 订阅同一 store，并在 `switchTab` 失败时恢复实际路由。
2. 当前共享 `AppShell` / `PageFrame` / `ProductTabBar` owner 下的安全区、胶囊避让和滚动遮罩修复；route-private CSS 不获得新的共享 chrome 所有权。
3. 经当前构建合同适配后的隔离构建、输出完整性校验和安全晋级；失败构建不得覆盖活动 `dist/weapp`。
4. 不关闭、不重载、不破坏已有微信开发者工具登录会话的自动化约束。
5. 仍未被当前 typed API 覆盖的装备首屏 `mode=initial` 瘦身；前端仍只消费后端 owner 的真实字段，后续槽位详情保持按需请求。
6. 只有在当前 asset registry、包体预算和运行素材合同全部通过时，才保留 #91 的本地 PNG utility fallback 与 trusted-media 加载状态。
7. 与上述行为直接对应的单元、合同、构建、包体和 Harness 门禁。

### 必须排除

1. 切换或默认启用 `static.chickenbro.cloud/wow-media`。
2. 对未上传的 COS 目录、3413 个 staging 对象或 404 路径作生产成功声明。
3. 回退 #92 的 14 路由 owner、typed API/domain、canonical empty/blocked 语义、新闻和模拟页面动作、生产 request/downloadFile 域名或当前发布素材根。
4. 用 #91 的旧 roadmap、计划、验证状态或历史截图覆盖 `main` 的当前控制面。
5. 直接编辑生成后的 WXML/WXSS、重建前端业务事实、启用 URL 校验绕过或触发异步 sync/backfill。

## 所有权与数据流

- Tab identity：root route `useDidShow` -> active-route store -> custom TabBar subscriber -> `switchTab`；失败时重新读取真实 route，而不是保留乐观状态。
- 顶部和底部安全区：`AppShell` 发布运行变量，`PageFrame` 独占 header/capsule 排除区，`ProductTabBar` 独占四等分导航与底部安全区；页面只消费这些 owner。
- 装备首屏：Taro typed client -> `mode=initial` API -> backend home-payload owner -> 精简首屏；槽位详情继续按用户动作加载，fallback 不升级为 verified。
- 构建：源码 -> 仓库监听树外的隔离输出 -> manifest/page entry/asset/package 验证 -> 活动输出晋级。任一验证失败保留旧活动包。
- 素材：当前 asset manifest -> `api.chickenbro.cloud` immutable release；未发布的 alternative CDN 仅可保留为 dormant tooling，不参与 production define constants。

## 影响图

| 分类 | 范围 |
| --- | --- |
| `must_change` | #91 分支与 `main` 的非改史合并；Tab state/root identity；必要的共享 chrome/build/API/asset 适配；对应测试与当前合同回写 |
| `must_not_change` | 14 路由 owner；canonical backend truth；当前生产 API/asset root；URL 校验；PG-only/read-model/SimC 语义；9 条未人工验收路由的证据等级 |
| `risk_unknown` | #91 原子构建脚本是否与 #92 production-cache 修复重复；PNG fallback 是否超过当前包体或语义槽；`mode=initial` 是否已由当前后端等价覆盖 |
| `evidence_required` | 逐提交保留/排除矩阵；定向测试；typecheck/lint/UI architecture/package release；最终 full/CI；必要候选 API smoke；两条真实微信关键路径；whole-branch CR |

## 异常与降级

- merge conflict：当前主线 owner 和合同优先；无法确定业务语义时停止，不用编译通过代替决定。
- Tab 切换失败：恢复实际 route identity，不显示伪激活成功。
- isolated build 失败：不触碰活动输出，输出明确失败原因。
- initial payload 不可用或畸形：typed client fail closed；不得静默使用不受 owner 约束的本地事实。
- utility asset 缺失或不可信：使用登记 fallback 或明确 blocked/placeholder；不得把未校验远端 URL 标为 verified。
- 新 CDN 不可用：继续使用当前 `api.chickenbro.cloud` release，不切换生产配置。

## 验收与发布

1. 形成 13 个 #91 提交的保留、等价覆盖、排除矩阵，并能从最终 diff 追溯每项结论。
2. 开发阶段运行每个保留行为的最小相关测试；UI owner 变化后运行 `npm run audit:ui-architecture`、`npm run typecheck`、`npm run lint`、`npm run test:taro`。
3. 使用当前正式 API/asset root 和显式微信域名批准标志运行 release package、domain audit 与 production weapp build；alternative CDN 不得出现在生产常量中。
4. 若最终 diff 保留 backend/API/deploy script 变化，先在最终 PR head 完成一次候选部署与只读 health/API smoke，保持 `WOW_DEPLOY_START_ASYNC_SYNCS=0`，记录 commit、文件 parity、服务状态和回滚副本。
5. 微信人工验收每批最多两条路由：先验证四个 Tab 切换，再验证一个详情页顶部栏、胶囊避让与返回入口。自动测试、API 200 和旧截图不替代这一步。
6. 最终 whole-branch 本地 CR 不得遗留 Critical 或 Important finding；最终 head 运行一次 Harness `full`/GitHub CI，不重复串行跑多个 full profile。
7. 用户在新候选上明确验收后，按 Harness 顺序合并 #91、复测合并结果、推送 `main`、核对 `HEAD == origin/main == GitHub main`，再清理本任务 worktree/local branch 和已合并远端分支。

## 回滚

- 代码回滚：revert 最终 PR #91 merge commit。
- 配置回滚：生产始终保留当前 `api.chickenbro.cloud` API/asset root，因此不需要 CDN 指针迁移或数据恢复。
- 候选回滚：若部署 backend/API 文件，使用部署前备份恢复并重启既有服务；不触发数据同步。
- UI 降级：若真实微信关键路径失败，保持 #91 未合并并继续使用当前 `main` 构建。
