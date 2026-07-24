# CDN 美术资源发布 Runbook

状态：`active`

## 当前生产取值与备用发布链路

当前已验证并正在使用的生产美术资源根是：

`https://api.chickenbro.cloud/wow-assets/releases/2026-07-19-taro-full-integration`

当前可用于真机候选、用于职业、专精、天赋和装备事实图标的运行时媒体根是：

`https://api.chickenbro.cloud/wow-media/releases/2026-07-20-wow-icons-v1`

该版本包含 40 个专精所需的 3413 个文件，共 7,326,459 字节；候选包门禁必须回读同目录的 `release-manifest.json`，并确认根、发布号和文件清单完全一致。`static.chickenbro.cloud` 的运行时媒体目录仍未发布，不能配置到候选或生产包。

小程序候选构建和回滚必须以上述两个已验证根为默认基线。除非一个新目录已经完成上传、逐文件回读校验和候选包验收，否则不得替换对应根。

仓库同时保留以下备用 CDN 发布链路，但它们只是显式手工发布工具，不是当前生产配置：

`packages/design-system/assets/raster -> COS zhajiduizhang-1257807175 (ap-shanghai) -> static.chickenbro.cloud -> WOW_ASSET_RUNTIME_ROOT`

职业、专精、天赋和装备等事实型图标使用独立不可变目录：

`受信任上游图标 -> 临时 staging -> COS wow-media/releases/<release-id> -> static.chickenbro.cloud -> WOW_RUNTIME_MEDIA_ROOT`

微信小程序发布包保留由 66 个注册 SVG 确定性生成的 `packages/design-system/assets/vector-runtime` PNG 派生物。真实微信端对 SVG 与 CSS mask 的渲染不稳定，组件必须通过原生 `<image>` 使用这些本地 PNG；大体积栅格美术仍由不可变 CDN 根提供。源 SVG 和许可证继续纳入仓库与 CDN 发布审计，但微信运行路径不得依赖 SVG 或 mask。

`static.chickenbro.cloud/wow-assets` 和 `static.chickenbro.cloud/wow-media` 只有在对应不可变目录真实发布并通过本 Runbook 的完整回读校验后，才可进入候选验证；目录只读不覆盖，资源变化必须使用新的 `release-id`。当前不得把历史示例目录或尚未发布的 `wow-media` 根写入构建脚本、测试脚本或部署默认值。

## 手工发布备用 CDN 目录

以下命令仅供负责人显式执行。它们不挂接 `build`、`test`、`deploy` 或 CI 默认流程，也不改变当前生产配置。

1. 先校验仓库中的源文件和清单：

   ```bash
   npm run verify:ui-asset-integrity
   ```

2. 预演待发布文件，生成临时 staging 目录及 `release-manifest.json`：

   ```bash
   npm run prepare:ui-cdn -- 2026-07-18-ui-v2
   ```

3. 在本机配置腾讯云 `coscli`（凭据只放用户配置，不进入仓库），然后上传并逐文件从 CDN 回读校验：

   ```bash
   npm run publish:ui-cdn -- 2026-07-18-ui-v2
   ```

   默认桶为 `zhajiduizhang-1257807175`、地域为 `ap-shanghai`。如迁移环境，可通过 `WOW_CDN_COS_BUCKET`、`WOW_CDN_COS_REGION` 和 `WOW_CDN_PUBLIC_ORIGIN` 显式覆盖。

   若不创建本地长期密钥，可使用腾讯云 CloudShell 的临时登录会话：打开 `https://iaas.cloud.tencent.com/cloudshell`，完成 MFA 后使用预装的 TCCLI/SDK。CloudShell 仅用于临时发布，不作为生产运行环境；上传前仍需确认当前子账号只拥有目标 release 前缀的最小写权限。不得用轻量云 COS 快捷挂载代替发布身份，因为实例目录用户会继承挂载目录读写能力。

4. 对已经上传的版本独立重跑 135 个资源及发布清单的字节数和 SHA-256 校验：

   ```bash
   npm run verify:ui-cdn -- 2026-07-18-ui-v2
   ```

5. 在备用目录尚未完成发布验收时，继续用当前生产根执行发布门禁：

   ```bash
   WOW_ASSET_RUNTIME_ROOT=https://api.chickenbro.cloud/wow-assets/releases/2026-07-19-taro-full-integration \
   WOW_RUNTIME_MEDIA_ROOT=https://api.chickenbro.cloud/wow-media/releases/2026-07-20-wow-icons-v1 \
   WOW_BACKEND_API_BASE_URL=https://api.chickenbro.cloud \
   WOW_WECHAT_REQUEST_DOMAIN_APPROVED=yes \
   npm run verify:ui-package:release
   ```

6. 生成供微信开发者工具真机调试/上传的隔离候选构建：

   ```bash
   NODE_ENV=production \
   WOW_TARO_ISOLATED_BUILD=1 \
   WOW_ASSET_RUNTIME_ROOT=https://api.chickenbro.cloud/wow-assets/releases/2026-07-19-taro-full-integration \
   WOW_RUNTIME_MEDIA_ROOT=https://api.chickenbro.cloud/wow-media/releases/2026-07-20-wow-icons-v1 \
   WOW_BACKEND_API_BASE_URL=https://api.chickenbro.cloud \
   npm run build:weapp
   ```

   仓库不提供固化 URL 的 `build:weapp:release` 脚本，避免历史或未发布目录被静默带入候选包。发布负责人必须在当前会话显式传入已验证的不可变根；`WOW_TARO_ISOLATED_BUILD=1` 会禁用 Taro 构建缓存并使用隔离 staging，避免上一次本地构建的常量或文件污染候选包。

## 运行时图标发布

这组工具只在显式发布时运行。候选验证仅允许使用已经完成清单与逐文件回读的不可变根；未设置时，应用继续使用现有本地 PNG/受信任资源回退，不构成发布阻断。

历史示例 `https://static.chickenbro.cloud/wow-media/releases/2026-07-19-wow-icons-v1` 当前未发布，禁止配置到生产或候选构建中。

1. 从当前 API 发现职业、专精、天赋和装备图标，下载到临时 staging，并生成带字节数与 SHA-256 的清单：

   ```bash
   npm run prepare:runtime-media -- 2026-07-19-wow-icons-v1
   ```

2. 使用已配置的最小权限 `coscli` 上传到 `wow-media/releases/<release-id>`，随后逐文件从 CDN 回读校验：

   ```bash
   npm run publish:runtime-media -- 2026-07-19-wow-icons-v1
   ```

3. 对已发布版本独立重跑清单、文件字节数与 SHA-256 校验：

   ```bash
   npm run verify:runtime-media -- 2026-07-19-wow-icons-v1
   ```

运行时不得把任意第三方 URL 当作代理目标。发布器只接受审计过的 `wow.zamimg.com` 与 `render.worldofwarcraft.com` 图片路径，并把来源映射到确定性对象键；新闻封面属于采集数据合同，不与职业/装备图标混用。

## 失败与回滚

- `publish` 在上传后以 8 路受控并发从 CDN 回读所有文件；任一 HTTP、字节数或 SHA-256 不一致即失败。
- 若已发布版本只缺 `release-manifest.json`，必须先用同一 `release-id` 重新 `prepare`，再逐个确认全部远端资源与本地清单的字节数和 SHA-256 一致；只有 100% 一致时才允许恢复内容完全相同的清单。任一资源缺失或不一致都必须换新 `release-id`。
- 除上述“全部资源一致、只恢复相同清单”的窄例外外，不修补已经发布的版本目录。修正源文件、换新 `release-id` 重新发布。
- 回滚小程序时，把 `WOW_ASSET_RUNTIME_ROOT` 恢复到上一版不可变目录；COS 和 CDN 中的旧版本保留。
- 存储桶只需公有读、私有写；匿名写入不是 CDN 回源要求。生产发布应使用受控的腾讯云身份，不能长期保留“公有读写”。
- 腾讯云访问密钥、临时令牌和 `coscli` 配置不得写入仓库或构建产物。
