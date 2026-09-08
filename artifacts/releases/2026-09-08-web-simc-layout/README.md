# Web SimC 主题与桌面布局发布

日期：2026-09-08。用户已确认本地预览并明确授权“部署到线上，然后提交，合入”。

本批复用 WebShell 当前主题，SimC 提交/任务/报告配色与插画随主题变化。桌面提交页并排放置战斗与精度卡片并等高，摘要与左侧整体上下对齐，版本信息靠近标题。保留窄屏与长内容自然滚动；未修改任何 API、模拟参数或数据所有权。

## 验证

- 本地源码 diff 审查完成；发现并移除桌面摘要样式误覆盖窄屏的修改。CodeRabbit 未安装且无可用连接工具，使用仓库现行本地审查流程，未安装依赖。
- 前端 321/321；控制面 62/62；typecheck、lint、git diff --check 通过。
- 最终 H5 构建成功，保留既有 asset/entrypoint 体积警告。
- 实际组件与示例数据：1366×768、1440×900 初始与就绪状态一屏显示；390px 无横向溢出、保留纵向滚动。
- 最后标题与摘要调整在 1366×768 实测：左侧整体与摘要顶部 226.99px，底部 690.74px；两张下方卡片等高，页面 scrollHeight=768px。
- 公网 27 文件 SHA256 全部匹配；readiness 所有组件 ready。线上首页可打开，当前浏览器未登录，未重新执行扫码或登录后业务验收，也未创建真实模拟任务。

## 发布身份与回滚

部署先于 Git 提交，采用内容绑定：[manifest.json](manifest.json) 记录部署前基线、四个实际变更源码文件 SHA256、所有 Web 产物 SHA256 和 buildHash。包含此记录的提交持有对应源码，不能把基线 SHA 当成最终源码身份。

新目录：`/var/www/chickenbro-web/releases/simc-layout-27e3dd08b8a75bab`。

旧目录：`/var/www/chickenbro-web/releases/v1-d2a2b752c89bb2ac43c6065509151878a30a9d09`。

通过校验 current 仍指向旧目录、验证新目录全部文件后，原子替换 `/var/www/chickenbro-web/current`；原目录完整保留。见 [部署结果](deploy.json) 与 [公网验证](live.json)。不重启后端，不改数据库、SimC runtime、小程序。

如需回滚，先核对 current 仍为本次新目录，再建立临时符号链接指向上述旧目录并原子替换 current，复查首页和 readiness；不删除任何 release。
