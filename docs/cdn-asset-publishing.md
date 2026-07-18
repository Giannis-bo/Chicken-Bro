# CDN 美术资源发布 Runbook

状态：`active`

## 固定链路

小程序美术资源使用不可变版本目录发布：

`packages/design-system/assets/raster -> COS zhajiduizhang-1257807175 (ap-shanghai) -> static.chickenbro.cloud -> WOW_ASSET_RUNTIME_ROOT`

职业、专精、天赋和装备等事实型图标使用独立不可变目录：

`受信任上游图标 -> 临时 staging -> COS wow-media/releases/<release-id> -> static.chickenbro.cloud -> WOW_RUNTIME_MEDIA_ROOT`

微信小程序发布包保留由 66 个注册 SVG 确定性生成的 `packages/design-system/assets/vector-runtime` PNG 派生物。真实微信端对 SVG 与 CSS mask 的渲染不稳定，组件必须通过原生 `<image>` 使用这些本地 PNG；大体积栅格美术仍由不可变 CDN 根提供。源 SVG 和许可证继续纳入仓库与 CDN 发布审计，但微信运行路径不得依赖 SVG 或 mask。

生产根目录必须是 `https://static.chickenbro.cloud/wow-assets/releases/<release-id>`。已发布目录只读不覆盖；资源变化必须使用新的 `release-id`，以便小程序版本回滚时仍能访问原资源。

## 发布

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

5. 用该不可变根目录执行发布门禁：

   ```bash
   WOW_ASSET_RUNTIME_ROOT=https://static.chickenbro.cloud/wow-assets/releases/2026-07-18-ui-v2 \
   WOW_RUNTIME_MEDIA_ROOT=https://static.chickenbro.cloud/wow-media/releases/2026-07-19-wow-icons-v1 \
   WOW_BACKEND_API_BASE_URL=https://api.chickenbro.cloud \
   WOW_WECHAT_REQUEST_DOMAIN_APPROVED=yes \
   npm run verify:ui-package:release
   ```

6. 生成供微信开发者工具真机调试/上传的 CDN 版本构建：

   ```bash
   npm run build:weapp:release
   ```

   `build:weapp` 默认保留本地素材，便于离线开发，因此会超过微信 2 MiB 主包限制；真机调试和发布必须使用 `build:weapp:release`。发布命令会禁用 Taro 构建缓存，避免上一次本地构建的素材根常量污染 CDN 包。切换 CDN `release-id` 时，同步更新该命令中的不可变根目录。

## 运行时图标发布

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
