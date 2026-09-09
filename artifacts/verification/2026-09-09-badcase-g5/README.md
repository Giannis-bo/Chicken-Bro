# G5 角色发现能力验证

2026-09-09，用户要求分别深入验证并将其视为常规能力支持。本轮完成真实只读 API 可行性与根因验证，没有修改产品代码、生产配置或用户会话，没有发布。未将查询结果冒充模型端到端回归。

## 1. 按角色查 WCL 报告：可行

实际带现有服务凭据查询 GraphQL schema，Character 有 recentReports(limit,page)。按角色名、服务器、地区直接查询：

- 桃花别死 / 阿古斯 / CN：角色 ID 99563963，hidden=false；第一页三份报告 C4LfAhjJX8g1b3wM、LPV3pf4nM9yhKw1Y、yAvBdZfb4K6Mxk8c，最后一份与历史用户报告相同；has_more_pages=true。第二页另外三份报告，current_page=2、has_more_pages=true。
- Fusionbolt / 凤凰之神 / CN：角色 ID 99955280，hidden=false；第一页 JMy4CPTmR2WXrQ1F、DZVCMtHyKLhAJdPR、yZQkADcjmr1bdnCx，has_more_pages=true。
- 分别读取第一份报告，masterData 确认目标角色及服务器，friendlyPlayers 确认参战：桃花别死 source=4，44 个匹配 fight；Fusionbolt source=4，1 个匹配 fight。各选一场成功读取3条施法事件，均有后续分页，未声称全量战斗分析完成。
- 不存在的测试角色 Zzcbg5probe / argus / CN 返回 character=null，不能包装成网络失败或已有报告。

入口缺在本产品：当前 query_warcraftlogs_report 只收报告URL，不提供按角色的发现工具。上游接口、当前凭据与这两个国服样本都可用。仅代表已索引且当前凭据可访问的记录，不承诺任何玩家所有日志均可见。

## 2. Raider.IO 身份不匹配：确定的规范化缺陷

真实 API 支持以中文服务器请求，且返回了完整度可供研究的角色资料：

| 输入 | 返回显示名 | 返回 canonical 路径 | 当前校验 |
|---|---|---|---|
| Fusionbolt / 凤凰之神 | Al'ar | /characters/cn/alar/Fusionbolt | false |
| Fusionbolt / alar | Al'ar | /characters/cn/alar/Fusionbolt | false |
| 桃花别死 / 阿古斯 | Argus | /characters/cn/argus/桃花别死 | false |

Fusionbolt 返回 Shaman / Elemental、16 个装备槽及天赋数据；桃花别死返回 Death Knight / Unholy、15 个装备槽及天赋数据。装备数量不等于 SimC 输入已完整，不推断缺少的等级/其他字段。

根因：RaiderIOResearch._identity_matches 将请求 realm 与 raw.realm 直接比较；_identity 仅统一大小写及横线/下划线/空格，不处理显示名到 canonical slug 的对应，更不能把中文名对应到英文名。因此中文输入误拒，alar 对 Al'ar 也误拒。当前测试数据中的 realm 与路径 slug 相同，没有覆盖此类真实响应。

进一步用 WCL worldData.server 验证中文“凤凰之神”和 slug“alar”均返回 server ID 584 / region CN / slug alar。这为独立的服务器别名规范化提供了实际验证过的路径。不能简单删掉服务器校验；地区、角色名和规范化服务器需共同匹配，不能把同名异服当成目标。

## 接入方向

1. 补充统一的角色定位步骤，接收角色名、服务器、地区；从上下文取已有条件，歧义才澄清。服务端校验输入，使用上游确认的 canonical 服务器身份；不同来源的名称/slug必须有依据，不维护针对这两个玩家的特判。
2. 新增角色 WCL 发现工具，返回经确认的角色身份、有限数量的近期报告、分页和状态；再复用报告读取器按 actor + server + friendlyPlayers 定位 fight/source。重名或多角色时先消歧，不直接选第一个同名 actor；重叠上传报告不能当成独立战斗次数。
3. 修复 Raider.IO 的 canonical 身份校验：比对受信 profile_url 的地区/角色/服务器与独立解析的预期身份，并保留真正的错服/错名/错地区、恶意URL拒绝。中文别名无法确认时返回具体缺口，而非静默降低校验标准。跨供应商 slug 不能未经验证假定总是一致，可按需用现有 WCL server 查询确认别名；接口不可用时保守失败并缓存已验证映射。
4. 由鸡哥主动调用这些工具，使用原始问题验证“只给角色名”流程；覆盖中文/英文服务器、大小写、同名异服、隐藏/不存在、上游限流、报告分页和部分结果。无需用户手动找链接才能开始。研究角色/日志的能力不改变 SimC 新角色仅允许 Raider.IO 导入的现有政策。

## 证据与限制

probe.jsonl 包含 schema 和两份公开角色响应；identity-check.json 是现行本地校验对真实响应的结果。discovery.jsonl、membership.jsonl、boundary.jsonl 分别记录报告发现、参战/事件读取、别名/分页/不存在情况。对应 probe.py 可复现读取过程；环境只在云端进程内使用，未保存凭据。

初次 ReportPagination 的单独 schema introspection 返回 Internal server error，但实际 recentReports 查询及分页成功，不能据 introspection 故障认定业务能力缺失。一次未带字段参数的 Raider.IO 查询报 HTTPError，未记录状态码，不能推断原因；之后带明确 fields 的 canonical 请求成功。

官方入口：https://www.warcraftlogs.com/v2-api-docs/warcraft/characterdata.doc.html 、https://www.warcraftlogs.com/v2-api-docs/warcraft/character.doc.html 、https://raider.io/api 。文档网页存在403，本结论主要依据实际 GraphQL schema 与业务响应。

## 用户授权后的修复与最终验证

用户随后明确“OK，修复”。新增 character_discovery.py 及 query_warcraftlogs_character 工具/网关入口，按上游确认的服务器身份发现公开角色和有界报告页；服务器/角色缺失、隐藏、不匹配及上游不可用分别处理。每页最多10条、最多20页，不自动无限翻页；保留 hasMore 与 nextPage，空报告页保留角色身份。工具只走服务端短期来源能力，未向模型暴露凭据。

Raider.IO 改用受信 profile_url 的规范地区/服务器/名字校验：显示名与slug可对应时直接核验，中文等别名通过上游 server 查询验证后再匹配。角色名/地区/规范服务器不符及恶意地址保持拒绝；别名来源抛出故障时返回 unavailable/identity_unverified，不伪称角色不匹配。别名解析仍依赖现有 WCL 服务可用性，失败时保守拒绝；本轮没有新增别名缓存。

测试先覆盖缺失入口与真实别名误拒，再通过实现；追加故障分类测试首次失败（blocked而非unavailable）后修正。最终444项后端、62项控制面通过，覆盖公开报告发现/分页、空页、未知角色、隐藏、错服务器、错误输入、真实RPC到网关结果、合法别名、错名/地区/服务器/URL及别名源故障。

首轮真实鸡哥只注入G5：报告发现成功，但随后生产旧查询器读取裸报告失败，验证出对未发布G1的依赖；Raider.IO查询正常。不能把该轮当作整条链路通过，见 candidate.jsonl。

最终组合回归注入当前本地G1+G5来源代码、工具与规则：

- WCL 原提问“就根据这个名字找一下我的log”，前文明确国服阿古斯桃花别死：54.99秒。自动发现报告，读取两份报告目录，再读取fight=3/source=4，均成功；最终给出近期报告与参战场次链接。
- Raider.IO 原提问“你去搜索Fusionbolt-凤凰之神”：21.55秒。主动用中文服务器构造链接，成功返回元素萨满、装备等级与评分等角色快照信息，不再要求手工链接。

见 combined.jsonl、combined-answers.md 和 fix-verification.json。六个运行源码快照的SHA256均与最终本地文件逐一核对一致。真实模型使用当前云端profile，独立8791来源网关与临时工具脚本；只读公开来源，没有正式用户会话写入、SimC提交或生产配置修改，临时服务已关闭。未做客户端真机验收，未提交/发布；G1和G5需作为相关依赖组合验证后发布，不能只发布发现工具却遗漏裸报告读取修复。
