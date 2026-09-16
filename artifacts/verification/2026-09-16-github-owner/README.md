# GitHub 用户名更新

2026-09-16 已发布，源码 `4407d547facc1f6d44cfa1758b46d47379f7ae5d`。顶部 GitHub 入口更新为 https://github.com/Giannis-bo/Chicken-Bro，本地 origin 同步到新地址。

13 项 WebShell 测试、类型检查、Lint、H5 构建通过，构建保留资源体积建议警告。实际本地与公网构建在 1440、390、320px 下验证链接可见、目标正确、新标签页打开、noopener/noreferrer 及无页面脚本异常；使用隔离 API 和导航目标夹具，无生产业务写入。GitHub API 独立确认新仓库为 PUBLIC。

服务器隔离静态验收及公网 13 份文件 SHA-256 全部匹配，readiness 三次 ready，API/Worker active，后端版本不变。证据见本目录 JSON。

Web 已切换至 `/var/www/chickenbro-web/releases/github-owner-4407d547facc1f6d44cfa1758b46d47379f7ae5d`。旧版目录及哈希清单保留，恢复包为 root/0700 `/var/lib/chickenbro-github-owner-20260916/`。在指针、后端与两版清单均匹配时，执行以下命令恢复；本次未实际回切：

```sh
sudo flock -w 30 /var/lock/chickenbro-release.lock python3 /var/lib/chickenbro-github-owner-20260916/deploy-web.py rollback /var/lib/chickenbro-github-owner-20260916/release-manifest.json
```
