# 默认最近三场与分类编号

最新增加玩家快捷写法与 Boss 序号（如 `H乌拉特克`、`H8/H9/H10`），当前状态见[快捷查询记录](../2026-10-15-qq-query-shorthand/README.md)。本文保留最近三场与编号修复证据。

用户已提供团本／大秘境成绩的真实群回复截图，本轮要求每类默认最近 3 场，编号按类别重置。

- 统一上限为 3：来源合并、时间排序、去重与筛选后截取，格式化同样限制每类最多 3 场。标题和不完整来源提示使用同一上限。
- 原源码的两个类别均从 1 枚举，但 QQ 显示时继续了上一个有序列表的编号。改用加粗文本形式的显式数字（`**1. Boss**`），不触发 Markdown 有序列表自动续号，团本和大秘境分别显示 1、2、3。
- 保留团本全部分区、当前赛季大秘境、指定 Boss／副本／层数、四舍五入取整、原始分数判色和具体日志链接。

云端 86 项相关测试通过：[cloud-tests.log](cloud-tests.log)。需求回归先在旧版失败：[red-tests.log](red-tests.log)。新增校验同一回复两个类别均限制 3 条、编号独立、源文本不含自动列表标记。运行清单：[manifest.json](manifest.json)、[runtime-manifest.json](runtime-manifest.json)。

Candidate 精确更新 `query_commands.py`、`character_source.py`、`runtime.py` 三个文件，旧文件哈希已校验并备份，仅重启官方 QQ channel。网关 READY、`queryPresentation=markdown_recent3_v1`、queryOnly=true、白名单数量 1。配置、凭据、数据库和菜单未变更，网站 API/Worker 与官方 AI Worker PID 不变。[部署回执](deployment.json)、[部署后真实来源和格式核对](deployed-source.json)。回退目录见部署回执，未执行恢复演练。

仅在炸鸡test 复验：

```text
@炸鸡 /角色查询 Giannis 白银之手
```

应显示「团本 · 最近 3 场」和「大秘境 · 最近 3 场」，两类均从 1 编到 3。记录不足时按实际条数显示。新数量和客户端编号显示待真实群确认；第二用户完整验收继续 pending。源码未提交、推送或合入。
