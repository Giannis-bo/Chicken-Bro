# Web 顶部 GitHub 入口

2026-09-16 已发布。源码提交 `7cb12c79bdc6c0c16d9c064e66a0242359db1ea1`。

顶部 FAQ 前新增 GitHub 链接，复用导航样式，新标签页打开 `https://github.com/boyuan19910222-ui/Chicken-Bro`，包含 noopener/noreferrer 与无障碍名称。

## 验证

- 13 项 WebShell 测试、TypeScript、Lint、H5 构建与 diff 检查通过。构建保留资源体积建议警告。
- 本地构建及实际公网构建均在 Chromium 检查 1440、390、320px 视口，链接可见且位于视口内，href、target、rel 与新标签页行为通过，无页面脚本异常。
- 浏览器使用隔离 API 夹具，GitHub 目标页拦截仅用于核对导航；不产生生产业务写入，不作为真实 QQ 登录或 Chat/SimC 新任务验收。
- 服务器独立 loopback 静态验收及正式公网 13 文件 SHA-256 全部匹配发布清单。readiness 三次 ready，API/Worker active，后端源码保持 `057378afc7b30e904b6bdd333283c93867dfb4b0`。

## 发布与恢复

Web 原子切换至 `/var/www/chickenbro-web/releases/github-7cb12c79bdc6c0c16d9c064e66a0242359db1ea1`。原 `changelog-40c17dbe379f5123c14ae70c321982a4c1b8bc6f` 目录保留，切换前后清单核验一致。

恢复材料位于 root/0700 `/var/lib/chickenbro-github-20260916/`，包含固定 manifest、静态包、执行器和旧版清单。按当前版本与清单匹配门禁，可执行：

```sh
sudo flock -w 30 /var/lock/chickenbro-release.lock python3 /var/lib/chickenbro-github-20260916/deploy-web.py rollback /var/lib/chickenbro-github-20260916/release-manifest.json
```

本次核对了恢复材料与旧文件哈希，未执行生产回切演练。
