# 最终 fixwave — F1 / F2

2026-09-20。本轮只修最终review的F1，以及Task6确认的F2。没有后端/API/Chat改动、服务重启、部署、提交、推送或子代理；所有程序运行在 `ssh wow-lighthouse`。本地只读写、git检查、rsync。

## 文件与改动

相对 `docs/plans/.final-fix-baseline/`，只修改：
- `apps/mini-taro/src/web/Poe2CharacterImport.tsx`
- `apps/mini-taro/src/web/WebPoe2.tsx`
- `apps/mini-taro/src/web/poe2-character-import.test.tsx`
- `apps/mini-taro/src/web/web-poe2.test.tsx`

另新增本报告。仅这4个实现/测试文件上传Candidate source。

F1：onReady成功交付后，用调用前捕获的sessionStorage key和ready importId做匹配删除；清理不依赖挂载generation，因此父组件进入第二步并卸载入口之后仍消费恢复记录。若同一key已指向新importId，保留新记录。父组件加载失败仍抛错；auth失效的过期交付返回false，入口保留记录。onReady的两个参数不变，返回类型增加可选boolean作为交付确认；void仍视为成功。返回①或“返回导入”后不再自动重放已消费的ready，可继续新建。

F2：仅用任务packet.provider=ninja且preview.sourceUrl为字符串，并再次通过validCharacterUrl(source,'ninja')，才显示“打开 poe.ninja 角色页”。链接target=_blank、rel="noopener noreferrer"。编辑框url不参与href；刷新恢复从GET任务preview恢复来源。无效协议、伪造主机、用户名密码及编码路径分隔符均不生成链接。

## 云端红绿与验证

工作目录 `/opt/chickenbro-candidates/poe2-20260918/source`，PATH前缀 `/opt/chickenbro-candidates/poe2-20260918/runtime/node-v22.19.0-linux-x64/bin`；只用已装依赖。

先只上传新增测试，对旧实现运行两个组件测试文件：27项，24通过、3失败，分别为ready返回第一步仍跳回第二步、成功重试未消费恢复记录、缺少ninja原页链接。恶意链接防护用例因旧实现完全没有链接而通过；修复后再确认仍不产生链接。红测证据：`evidence/link-research/final-fix-red.log`。

上传修复并补充卸载后消费/较新记录不删除/父级拒绝交付保留的定向断言。最终命令：

```sh
npm run typecheck
node node_modules/eslint/bin/eslint.js \
 apps/mini-taro/src/web/Poe2CharacterImport.tsx \
 apps/mini-taro/src/web/poe2-character-import.test.tsx \
 apps/mini-taro/src/web/WebPoe2.tsx \
 apps/mini-taro/src/web/web-poe2.test.tsx --max-warnings=0
npm run test:taro -- apps/mini-taro/src/web/poe2-character-import.test.tsx \
 apps/mini-taro/src/web/web-poe2.test.tsx
```

最终typecheck、相关lint通过；Vitest 2文件29项通过，2.06秒，`evidence/link-research/final-fix-tests.log`。覆盖ready→第二步→返回①稳定停留且可创建新任务；加载失败跨重挂载仍可恢复；成功交付后卸载不影响消费；新记录与父级false不被误删；ninja已存来源恢复可用且编辑框改变不改原链接；恶意URL不跳。既有来源/轮询/跨账号时序测试同步通过。`git diff --check`通过。

没有扩大采集、引擎或Chat回归。业务验收与移动/真实浏览器操作继续由root Task6执行。

## 最新独立构建

```sh
WOW_APP_ENV=test WOW_TEST_LOGIN_UI=1 \
WOW_H5_PUBLIC_PATH=/poe2-candidate/ \
WOW_API_V2_PREFIX=/poe2-candidate/api/v2 \
WOW_WEB_AUTH_API_PREFIX=/poe2-candidate/api/v2 \
WOW_WEB_CSRF_COOKIE_NAME=__Host-chickenbro-poe2-candidate-csrf \
WOW_BACKEND_API_BASE_URL=https://www.chickenbro.cloud \
WOW_TARO_ISOLATED_BUILD=1 \
WOW_TARO_OUTPUT_ROOT=/opt/chickenbro-candidates/poe2-20260918/task5-web-build \
npm run build:h5
```

输出仍为独立 `/opt/chickenbro-candidates/poe2-20260918/task5-web-build`；当前web与服务未动。构建日志 `evidence/link-research/final-fix-build.log`，完整文件SHA256清单 `evidence/link-research/final-fix-web-sha256.txt`。

最终构建成功，webpack 5.91.0耗时26682ms、2条体积告警。最新完整文件SHA256清单的SHA256=`51e606352ba7afeeb831156d3bec02a5d9b5309d6a740233da1e818d9aa48600`。该清单及独立产物供root在唯一scoped复审通过后部署Candidate；本任务未进行发布或浏览器验收。
