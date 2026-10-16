# 玩家快捷写法与 Boss 序号

2026-10-15 用户明确反馈「OK，我测试过了，可以。」当前三个查询命令及本轮快捷写法通过用户验收。Candidate 和源码保持未提交、未推送、未合入；新的 WCL 战斗日志分析由新会话继续推进。

用户授权支持 `H乌拉特克` 等玩家写法，随后补充 `H8/H9/H10`，并确认当前团本 H9 指唤潮者、H10 指 12.1.5 的基希克斯。

## 当前支持

| 写法 | 识别结果 |
| --- | --- |
| `H乌拉特克`、`H乌拉`、`H 乌拉`、`英雄乌拉` | 英雄乌拉特克 |
| `H8` | 所选团本英雄 8 号；当前为乌拉特克，Boss ID 3492 |
| `H9`、`H唤潮者` | 当前团本英雄唤潮者，Boss ID 3379 |
| `H10`、`H基希克斯` | 当前团本英雄基希克斯，Boss ID 3513，涵盖 12.1.5 记录 |
| `N8`、`M8` | 所选团本普通／史诗 8 号 |
| `诸王+12`、`诸王 +12` | 大秘境诸王之眠 +12 |

名称和简称在实时 WCL 目录内匹配，有歧义则返回候选；数字使用所选团本的目录顺序。[当前真实目录](catalog-order.json)的第 8/9/10 个条目依次为 Ula'tek、Nymrissa Wavecaller、Kith'ix，与用户给出的玩家含义一致。唤潮者、基希克斯是本轮用户确认的中文简称。

同时存在多个当前团本时，按序号查询须填写 `团本=名称`；序号越界返回实际范围及 Boss 候选。重复／冲突条件拒绝，Boss 名称与序号不能同时指定。原有 `Boss=`、`难度=` 和英文名／明确 Boss ID 继续可用。数字 Boss ID 使用 `Boss=3492`，不与第几号 Boss 混用。

保留三条固定命令、每类最近 3 场、各类独立编号、四舍五入整数分数、团本全部分区与当前赛季大秘境。H10 命中具体 Boss ID 3513，全部分区读取包含 12.1.5；不会用其他 Boss 的记录填补空结果。

## 验证与 Candidate

- 云端 95 项相关测试通过：[cloud-tests.log](cloud-tests.log)。新增覆盖难度前缀、中文简称、数字序号、明确 ID、重复／冲突条件、越界、多个团本选择、裸副本与层数。需求回归均先在旧实现失败：[red-tests.log](red-tests.log)、[ordinal-red-tests.log](ordinal-red-tests.log)、[boss-alias-red-tests.log](boss-alias-red-tests.log)。
- 改动累计涉及查询解析、来源选择和名称标签 3 个文件。按用户逐次补充，分三次精确更新，每次部署前检查无待处理任务、旧文件哈希、备份哈希，只重启官方 QQ channel。回执：[快捷名称](word-shorthand-deployment.json)、[数字序号](ordinal-deployment.json)、[中文别名](deployment.json)。回退目录见各回执；未执行恢复演练。
- 全部阶段网关 READY、queryOnly=true、白名单数量 1；配置、凭据、数据库和菜单未变更，网站 API/Worker 与官方 AI Worker PID 保持不变。累计清单：[manifest.json](manifest.json)、[完整运行清单](runtime-manifest.json)。健康文件 runtimeRevision 为接入环境标识，本轮源码按哈希定位。
- 部署后使用真实公开来源核对：[序号及 H乌拉](ordinal-source.json)、[中文别名及 H10 分区读取](deployed-source.json)。来源读取不是群内收发验收；Giannis 未有的 Boss 成绩仍如实返回无记录。

## 真实群复验

在炸鸡test 选取真实 @炸鸡，分别发送：

```text
@炸鸡 /角色团本查询 Giannis 白银之手 H乌拉特克
@炸鸡 /角色团本查询 Giannis 白银之手 H8
@炸鸡 /角色团本查询 Giannis 白银之手 H9
@炸鸡 /角色团本查询 Giannis 白银之手 H10
@炸鸡 /角色大米查询 Giannis 白银之手 诸王+12
```

应命中对应 Boss／副本，按最多 3 条展示。序号形式在查询范围中显示「8号／9号／10号」及 Boss 名称。无记录不变成 0 分；多个匹配提示选择。用户已确认测试通过，继续仅开放炸鸡test，未提交、推送或合入。
