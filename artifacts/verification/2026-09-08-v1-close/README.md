# 1.0 收尾验证（2026-09-08）

用户已明确接受当前 1.0，实现基线为 `06c5bbcce0cae1e8f8b8a6f1c8a129c375852cb8`。本轮变更为已接受的 Mini 账号与外观移除、Web 更新日志精简、FAQ 文案及文档同步。复核当前核心实现，不扩展新功能。

## 审查

独立静态审查完整客户端 diff，并抽查 Chat owner/事务/幂等/数据库账号互斥、删除与发送竞态、任务 ID 重跑 owner 与原参数保留。无已确认阻塞性代码问题；P3 FAQ 退出文案已修正为 Web 退出不影响 Mini。文档复核进一步纠正头像入口的过时承诺：当前 Mini 登录确认页也不挂载头像选择组件，Web 继续显示已保存头像。

CodeRabbit CLI/MCP 当前不可用，未安装或调用。采用本地源码与独立审查，不能声称通过了 CodeRabbit。

已有 COS 安全记录仅纳入文档收尾，检查时间保持原值；未重做云端权限变更或历史日志调查。

## 新鲜验证

| 检查 | 结果 |
| --- | --- |
| 前端 `npm run test:taro` | 321 通过（包含最终 FAQ 文案调整） |
| 后端 `npm run test:backend` | 420 通过 |
| 迁移 `npm run test:migration` | 77 通过，无跳过 |
| 运维 `npm run test:ops` | 101 Node + 14 Python 通过 |
| 控制面 `npm run test:control` | 62 通过 |
| 类型 / lint | 通过 |
| H5 / WeApp | 构建通过；现有包体积警告保留 |
| 文档链接 / diff 空白检查 | 本轮变更与新增 Markdown 相对文件链接全部可达；通过 |
| 生成包内容 | Mini 无账号与外观、保留 FAQ/更新日志；H5 无被删除的顶部说明 |

后端首次使用系统 Python 缺少 FastAPI；切换本机已有 `/tmp/chickenbro-merge-check-venv-20260907` 后完整通过，无安装。首次迁移因未配置 DSN 跳过 14 项；随后使用已有 PostgreSQL 16 在 `/tmp/wow-v1-close/pgdata` 创建独立 UTF8 测试实例，预建 `wow_app`，77 项无跳过通过。未连接生产库，也未本地运行 SimC。

## 发布边界

当前为仓库收尾；两处 UI 精简与 FAQ 修改未部署 Web、未上传 Mini 或提交微信审核。此前生产业务证据延续各自发布记录，未冒充本轮真实微信扫码、云端模拟或线上 SHA 全量复核。

本地/远端/构建最终身份在提交后核对；Git SHA 相同只能证明仓库一致，不能证明线上运行版本一致。

提交前 WeApp sourceHash 为 `sha256:f6f83fc8f9eee0841dffd990f17ee3c12c4120723470167361663e5db0a3fa62`，构建时间 `2026-09-08T06:52:16.808Z`；该构建 gitHead 为本轮基线，不冒充未生成的合并 commit。合入后重新执行 `refresh:weapp` 绑定最终 main，结果以生成的 `apps/mini-taro/dist/weapp/wow-build.json` 为准。

## 后续最终发布

上述未部署说明是首次文档收尾状态。用户随后授权双端上线日志与最终发布，源码 `d2a2b752c` 已部署 Web、上传 Mini `1.0.0`；现状见 [发布证据](publish.json)。微信审核/公开发布待用户后台操作。后端 79 文件与最新源码一致，无需更新服务。
