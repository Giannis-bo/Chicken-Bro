# Task 6 — 真实 Candidate 集成验收

2026-09-20，最小真实Candidate集成验收已通过（最终结果见末节）。所有程序仅云端执行；本地仅读写文件/SSH/rsync。未提交、push、合入或生产切换。产品代码由实施/审查代理维护，本任务只新增验收脚本与净化证据。

## 修复前已通过

`tests/poe2_character_candidate_smoke.py` 在最终 Candidate API/worker/collector上执行：真实已签发 web_cookie A/B会话通过 `/me`；错误CSRF 403；两来源错配422；创建幂等；B读取/取消/补充A任务均404；A取消成功。会话由测试数据库签发，未执行QQ登录流程。会话保留云私有600文件，未进入证据。

最终collector对用户分享只执行一次实际公网采集：`needs_input`，97级Amazon预览可见，572项缺口，含MISSING_JEWELS、JEWELS_UNMAPPED、装备/词缀/技能未映射、版本/任务/抗性进度未确认；buildId和baselineJobId均为空。净化证据 `artifacts/verification/2026-09-20-poe2-character-import/api.json`。完整国服真实资料缺样本，有限映射不能记作ready或完整国服验收。

真实云Chromium使用公网Candidate与同一A会话，恢复上述相同任务：
- 两来源输入错配均禁用读取；
- 已采集WeGame任务刷新恢复、预览及珠宝缺口显示；
- 桌面和390px截图，390px无横向溢出，补充输入框可聚焦；
- 取消后刷新仍为已取消；
- 新建ninja任务进入needs_input。

截图已遮蔽全部input/textarea，不含分享链接、XML或cookies。`wegame-desktop.png`、`wegame-mobile.png`为已完成步骤证据。

## 修复前阻碍与后续（历史记录，已由末节关闭）

浏览器在ninja needs_input发现缺少“打开原页”链接；当前组件没有a/href，无法完成brief中原页入口验收。已通知root，与独立整体审查发现的ready返回第一步再次恢复并跳第二步问题一起处理。按root指示暂停，等唯一修复波次完成后继续。

待执行：真实ninja XML补充ready与Life2813/ES962/Armour7284/Evasion14138；复用已有baseline且无额外POST jobs；ready返回第一步；三步详情和导出；手动/示例导入兼容；WoW导航；B访问已完成构筑/基线隔离。API/采集与当前浏览器通过范围不代表这些待验收项完成。

## 测试校正记录

API初轮将来源错配错误状态预期写成400，实际路由合同为422，测试修正后通过；初轮在外部采集前停止。浏览器最初过早启动，尚无WeGame任务ID文件，停止后等API完成再启动；未导致重复公网采集。最后浏览器停止于原页链接缺失，净化失败记录保留 `browser-failure.json`。

## 修复后最终继续结果 — PASS

F1/F2经原UI实施代理修复、独立复审PASS并由root更新Candidate Web后，在最终产物上继续真实浏览器。前半已完成WeGame采集和预览截图沿用；恢复同一已取消任务确认状态，没有新增WeGame公网请求。

真实国际服流程使用用户给定的wuba-4006 / forbiddenrites / 玩個那個破大錘链接，配合既有真实 `ninja-build.xml`。以下均在公网Candidate真实Cookie/CSRF、云Chromium完成：
- 原页入口href对应实际链接，target=_blank、rel含noopener，刷新仍正确；没有自动访问ninja上游。
- needs_input补充真实XML，未确认时按钮禁用；确认后ready，成功build/baseline关联正确。
- Life=2813、EnergyShield=962、Armour=7284、Evasion=14138；进入第二步期间POST `/poe2/jobs`次数为0，复用导入任务产生的成功baseline。
- 390px无横向溢出，桌面/移动成功基线截图；第三步完整详情及真实导出文本存在，截图全量遮蔽输入/textarea。
- ready返回第一步保持可用，清除已消费任务恢复ID，能创建不同ID的新ninja任务并取消。
- 教学示例导入、手动XML导入均成功进入第二步；WoW切换及SimC导航通过。
- B真实会话读取A import/build/baseline均404，B retry A import为404。
- 浏览器pageerror为空。两来源错配在新版重复验证通过。

最终浏览器净化证据 `browser.json`，截图 `ninja-ready-mobile.png`、`ninja-ready-desktop.png`、`details-export-masked.png`。历史 `browser-failure.json`只代表修复前原页链接缺失，不是最终结果。

单条真实Chat读取同一既有WeGame任务已通过，无新采集/计算/研究：conversation `73fe3d4c-c37f-57ae-824d-828f8d16d792`，DB绑定run `9839ab7b-1a93-4cb6-9d90-802fdfe1b906`为succeeded；持久 `native-tool-observations.jsonl`精确一条 `poe2_character_get`，status=cancelled、errorCode为空、elapsedMs=116。最终答复正确报告WeGame、已取消、角色预览、资料缺口及无build/baseline。端到端18.151秒；原始SSE/消息只在云私有600文件。净化证据 `chat.json`。这是实际Chat读取能力证明；Task5 gateway78项为独立工程证据。

Task6最小集成验收已完成。真实完整国服映射样本与用户体验验收继续待验收；当前国服needs_input结论不变。没有数据库恢复演练、QQ登录或生产发布的新增证明。root另行维护最终产物manifest、身份与全局交付状态。
