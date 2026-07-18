# CDN 美术资源发布 Runbook

状态：`active`

## 固定链路

小程序美术资源使用不可变版本目录发布：

`packages/design-system/assets -> COS zhajiduizhang-1257807175 (ap-shanghai) -> static.chickenbro.cloud -> WOW_ASSET_RUNTIME_ROOT`

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

4. 对已经上传的版本独立重跑 135 个资源及发布清单的字节数和 SHA-256 校验：

   ```bash
   npm run verify:ui-cdn -- 2026-07-18-ui-v2
   ```

5. 用该不可变根目录执行发布门禁：

   ```bash
   WOW_ASSET_RUNTIME_ROOT=https://static.chickenbro.cloud/wow-assets/releases/2026-07-18-ui-v2 \
   WOW_BACKEND_API_BASE_URL=https://api.chickenbro.cloud \
   WOW_WECHAT_REQUEST_DOMAIN_APPROVED=yes \
   npm run verify:ui-package:release
   ```

## 失败与回滚

- `publish` 在上传后强制从 CDN 回读所有文件；任一 HTTP、字节数或 SHA-256 不一致即失败。
- 不修补已经发布的版本目录。修正源文件、换新 `release-id` 重新发布。
- 回滚小程序时，把 `WOW_ASSET_RUNTIME_ROOT` 恢复到上一版不可变目录；COS 和 CDN 中的旧版本保留。
- 腾讯云访问密钥、临时令牌和 `coscli` 配置不得写入仓库或构建产物。
