# Task 3 — WeGame 公开分享采集与隔离

2026-09-20。初次审查 R1–R3 已完成定向修复，最新实现/部署身份及13项验证见文末“审查修复”；交复审。没有提交、推送、合入、生产变更或重启 Candidate API/worker。所有程序、测试、Chromium 和网络验证均在 `ssh wow-lighthouse` 执行；本地只读写和传输文件。

## 文件及装配

本任务新增文件：

- `server/app/poe2/imports/sources/wegame.py`
- `server/poe2_source_browser.cjs`
- `server/poe2-source-browser/chickenbro-poe2-source-browser.service`
- `server/poe2-source-browser/chickenbro-poe2-source-browser.socket`
- `server/poe2-source-browser/resolv.conf`
- `tests/app_poe2_wegame_source_test.py`
- `tests/poe2_source_browser_test.cjs`
- 本报告。

唯一来源端口：`collect_wegame(ref: SourceRef, *, owner_id=None, socket_path=SOCKET_PATH) -> dict`；模块同时导出 `collect` 别名。应用必须传已 claim 行的 `row.user_id`，不能从用户请求/URL 接收 owner。无 owner 的路径只保留给直接测试，统一使用一个保守调用者 key。

```python
from server.app.poe2.imports.sources.wegame import collect_wegame

# Task4 在 ImportWorker 执行端使用已 claim 的 owner；此任务不修改 worker。
snapshot = collect_wegame(ref, owner_id=row.user_id)
```

IPC 请求仅接受 `{version:1, canonical_url, owner_key}`，owner_key 为固定 domain separator 加 UUID 的 SHA256。不能注入 header、Cookie、代理、脚本、调试端口或浏览器参数。服务 Unix socket `/run/chickenbro-poe2-source-browser/collector.sock` 为 `0600 ubuntu:ubuntu`，只由 Candidate 应用账户及 root 调用。连接请求上限4096字节，未发送完整请求3秒断开；回复上限8MiB，客户端63秒超时。来源错误只公开 `SOURCE_UNAVAILABLE/AUTH_REQUIRED/RATE_LIMITED/INCOMPLETE`；连接错误/超时是可重试 `ConnectionError/TimeoutError`，不返回底层异常或原始来源正文。

## 净化 schema（Task4 集成合同）

```text
{
  schema_version: 1,
  role: {name: str, level: int, class_id?: int, class_name?: str, league_id?: str},
  equipment: [Item],
  skills: {items: [Item], base_info: [{id?, name?, description?}]},
  passives: {
    hashes: [int],
    jewel_slots: {numeric_socket_key: {type?, radius?}},
    skill_overrides: {numeric_node_key: {id?, name?, stats?, grantedStrength?, grantedDexterity?, grantedIntelligence?}},
    specialisations: {set1?: [int], set2?: [int]},
    quest_stats: [source quest values]
  },
  jewels: {status: "missing"} | {status: "present", items: [{jewel: {...}, ...}]},
  source: {
    provider: "wegame", fetched_at: ISO8601 UTC,
    source_updated_at: null,
    schema_gaps: ["unknown_item_fields" | "unknown_jewel_structure"],
    snapshot_hash: lowercase SHA256
  }
}
```

`Item` 保留来源命名，不提前猜测 PoB 映射。具体字段由代码 `ITEM_KEYS` 白名单定义，覆盖 `baseType/typeLine/name/inventoryId/id/frameType/frameTypeId/rarity/ilvl/identified/league`，properties/requirements 的 name/type/displayMode/values，全部本次观察到的显式/隐式/附魔/rune/bonded/utility 等 mods、description，以及 crafted/fractured/desecrated/mutated/doubleCorrupted/flags、socket/socketedItems/sockets/group、gemSkill/gemSockets/gemTabs/pages/skillName/stats、grantedSkills、support 和武器/辅助需求。递归保留 socketedItems 及其词缀，不把 mods 的 `{description:...}` 擅自改写为字符串。

装备物品 ID、技能映射 ID、天赋节点 ID 属于映射依据；角色 ID、openid、account_name、share_code/token、URL、图像和请求字段全部移除。还递归收集已知敏感字段的值，删除这些值在其他公开字符串中的复现；实际分享 URL/token 也传入值级清理。未知条目字段不输出原始 key/value，而标记固定枚举 `source.schema_gaps`。Task4 必须将非空 schema_gaps 视为映射缺口，保留 needs_input，不能宣称完整。`jewels.status=present` 只表示自然响应提供非空 jewel 结构，不代表已完成语义映射。

`jewel_slots` 的6个插槽不是珠宝物品。空 `GetJewels.jewel_data` 返回 `status=missing`，不添加 `items:[]`。`base_info` 只使用页面自然触发的可选 BtGetBase，可能为空；不能重放 API 来填补。来源没有可信的统一更新时刻，因此 `source_updated_at=null`，不拿 last_login_time 冒充快照更新。snapshot_hash 覆盖净化内容及 schema_gaps，不包含读取时钟；不使用角色账户或分享标识生成公开 hash。

## 浏览器和服务边界

真实部署：

- `/etc/systemd/system/chickenbro-poe2-source-browser.socket`
- `/etc/systemd/system/chickenbro-poe2-source-browser.service`
- `/opt/chickenbro-poe2-source-browser/collector.cjs`
- `/opt/chickenbro-poe2-source-browser/resolv.conf`
- Node 为现有 `runtime/node-v22.19.0-linux-x64/bin/node`，Playwright/Chromium/私有库使用现有 `runtime/browser`。宿主 `/usr/bin/node` 是18，不满足现有 Playwright，因此服务明确绑定已有Node22；未下载或安装任何依赖。

collector `DynamicUser=yes`，空 capability、NoNewPrivileges、只读系统、私有tmp/devices。`/opt /var /run /etc` 为服务私有只读文件视图，仅绑定 collector、Node22、browser依赖、CA证书和公网 resolv.conf。验证服务视图看不到 Candidate evidence、`/var/lib/chickenbro`、`/home/ubuntu/.codex`、`/etc/chickenbro`。环境只含 systemd 标准名称及 PATH/HOME/LANG/POE2_SOURCE_ENABLED，没有应用数据库、QQ、Cookie、API key 或代理环境。

公网 DNS `1.1.1.1/8.8.8.8` 只绑定到本unit `/etc/resolv.conf`；继续拒绝全部loopback，没有修改系统resolver或全局防火墙。systemd cgroup/BPF 拒绝 RFC1918、loopback、link-local、CGNAT、metadata、保留/多播地址及IPv6本地地址。真实 Chromium 随 collector 位于该cgroup，公网分享采集成功。

仅允许自然页面必要请求：主站固定分享HTML，5个Profile读取接口及可选BtGetBase；实际观察到的 `wegame.gtimg.com/g.2002052-r.4de9d/helper/poe2/assets/*.js|css` 和3个精确版本的 Vue/SDK/WG UI 静态路径。经济、统计、广告、遥测、图片、无关站点均拒绝；没有为了页面统计请求放开 GetSkillsDps/货币接口。来源静态版本变化会 fail closed，需复核新自然路径。CDP 在 Request/Response 两阶段检查，重定向目的地重新校验。响应使用 `Fetch.takeResponseBodyAsStream` + `IO.read(65536)` 按实际读取字节执行单响应2MiB、采集API累计8MiB限制；流超限中断，不先无界读取完整response。浏览器禁用service worker、websocket、popup和Worker/SharedWorker，不开放TCP remote debugging，只用Playwright调试pipe。

每任务独立Node子进程和Chromium上下文，60,000ms外部deadline；超时强制停止并回收任务子孙及其独立进程组。Chromium自身是detached进程组，所以实现专门枚举/proc祖先关系并停止/清理它，不能仅kill Node进程组。服务整体 KillMode=control-group、MemoryMax=1536M、TasksMax=192。全局同时2个，owner同时1个，超额立即RATE_LIMITED。

开关：服务 `POE2_SOURCE_ENABLED=1`；修改为0并仅重启collector后，新请求返回SOURCE_UNAVAILABLE。紧急停用可 stop 专用socket和service（socket单独停止不终止既有采集，service停止会按cgroup回收）。当前仅start，未enable开机启动，便于Candidate受控集成。无需修改或重启Candidate API/worker来关闭collector。

## 有界验证结果

先上传测试，云端确认 JS/Python 分别因新模块不存在失败；再实现。最终云端 `task3-tests.log`：8个Node tests、2个Python tests全通过。覆盖URL/重定向判断、private/metadata拒绝、遥测经济拒绝、必需响应缺失、缺珠宝、敏感值复现净化、未知结构schema_gaps、2MiB/8MiB边界、并发和关闭开关、真实Unix IPC的owner1/global2及任意options拒绝、客户端owner绑定和不可用socket可重试。

deadline回收测试使用500ms加速同一60秒默认deadline机制，启动独立detached子孙进程，确认到期后其不再运行；没有另耗60秒重复真实分享。真实采集完成后unit回到7个Node线程、约8.5MiB，无残留Chromium任务。

实际内核探针加入**当前collector同一cgroup**，直接尝试 `127.0.0.1:8796`、`169.254.169.254:80`、`10.0.0.1:80`，全部1秒连接超时；其中8796是已运行Candidate API，证明loopback拒绝不是关闭端口造成。`sudo -u nobody` 连接IPC得到PermissionError。上述策略对整个collector及Chromium子进程生效，不依赖URL字符串检查。

真实用户分享：12.42秒成功，17件equipment、16组skills、105个passive hashes、6个jewel_slots、jewels=missing。当前角色97级、Amazon。此前两次同一分享 GetSkills 请求已自然发出，但在45秒响应等待内没有完整响应，返回INCOMPLETE；后续同一白名单自然收到200，不增加业务API。最终没有固定断言该角色属性长期不变。

与前次珠宝复查样本的字段级比较：name/level/class_id/class_name/league_id、装备/技能/天赋数量均未变化；旧样本可选base_info=10，本次自然页base_info=0。明确保留这项字段缺口，不挪用旧数据填入当前snapshot。实际快照227303字节；对比旧私有请求/响应中的openid、role_id、account_name、share_code值，均未出现在净化快照中。

云端证据根 `/opt/chickenbro-candidates/poe2-20260918/evidence/link-research/`：

- `task3-snapshot.json`：本次实际成功页面的净化快照。
- `task3-reference-normalized.json`：旧私有rawcapture经最终normalizer离线净化，仅供字段比较。
- `task3-comparison.json`：无秘密的字段/计数差异，旧样本经最终normalizer `schema_gaps=[]`。
- `task3-tests.log`：最终8+2定向测试。

最后恢复无临时诊断代码的正式collector并重启**仅本次collector服务**；源码与部署script SHA256均为 `4d0b249344aee7eb91c1a347dd49369084560b126cbd3952a00abc54601d784d`。最终socket/collector/API/worker均active。真实快照是在最后加固前读取：后续加固增加未知字段schema_gaps、hash纳入gaps、禁止Worker/SharedWorker及完整子孙回收，最终定向tests全通过；按root有界要求没有再次探测真实分享，因此该实际快照source尚无schema_gaps字段，Task4可使用最终schema合同/旧样本的最终normalizer离线产物，不能把旧样本冒充当前采集。

## 交接和限制

Task4负责worker owner参数、mapper/convert装配以及schema_gaps/缺珠宝/缺base_info的业务决策。此任务没有改worker、mapper、Web、Chat或数据库状态机。公开使用规范仍未确认，保持Candidate范围。完整国服构筑尚缺珠宝和映射验收；成功采集、服务active和局部tests不代表完整构筑可计算或生产发布。

## 审查修复 R1 / R2 / R3（当前最终身份）

修复文件限定为 `server/poe2_source_browser.cjs`、`tests/poe2_source_browser_test.cjs`、专用service与本报告；新增标准库监督器 `server/poe2_source_supervisor.py`。没有新增依赖或请求真实分享。本节替代上文旧版按PPid扫描回收及旧部署hash描述。

- **R1**：在任何role/equipment等字段净化前，先解析明确支持的 `GetJewels.jewel_data` JSON，再将解析结果与普通capture合并收集敏感值。新增fixture仅在该JSON内提供openid，令同值出现在jewel.name、role.name和equipment.name，断言整个snapshot无该值。旧代码该断言失败，修复后通过。
- **R2**：每个任务单独启动Python supervisor，启动Node前调用 Linux `PR_SET_CHILD_SUBREAPER`。Node主动退出、SIGKILL或崩溃后，其detached Chromium/子孙会重新归属**该任务的supervisor**。结束时不断kill当前直接子进程并waitpid回收，直到ChildProcessError证明无剩余子孙，才输出结果并退出；broker等supervisor close后才释放owner/global gate。没有杀共享collector cgroup或另一任务。监督器使用最小环境，Node/browser无应用凭据；使用标准库ctypes/selector/subprocess，不新增安装。默认60秒中预留500ms开始清理，外层60秒也只向supervisor发SIGTERM触发清理，不先杀掉subreaper。
- **R3**：新增`finishCapture`，500ms自然可选响应窗口后停止接纳新事件，等待已接纳的pending响应handler全部settle，然后重新检查failed。所有handler的异常均进入失败状态，不再从晚到失败返回正常snapshot。定向用例在完成窗口开始后注册的在途promise于30ms报RATE_LIMITED，窗口5ms先结束，断言仍等待该handler且拒绝返回成功。

云端红绿：`task3-review-red.log` 中R1为实际断言失败，R3为新收束函数尚不存在，R2首轮接口变更测试尚不能调用新supervisor。随后额外执行**旧实现的实际R2复现**：detached子孙启动后worker主动退出，结果 `worker_exited=true, detached_child_still_exists=true`，存 `task3-r2-red.json`；该测试自行终止遗留测试子孙。修复后 `task3-review-green.log` 为 **11个JS + 2个Python全部通过**。R2最终用例确认/proc中子孙PID已消失，同时另一任务正常返回成功；原deadline detached子孙回收用例也通过。

部署新增 `/opt/chickenbro-poe2-source-browser/poe2_source_supervisor.py` 并在unit中只读绑定。仅重启专用collector，不重启API/worker。额外在实际服务mount namespace中以DynamicUser UID/GID运行已部署supervisor与不联网的短Node任务，返回 `{"ok":true,"snapshot":{"supervisor":true}}`，确认私有文件视图下Python/ctypes/Node组合可用。该离线部署smoke不替代真实浏览器验收。

最终源码与部署身份：

| 产物 | SHA256 |
| --- | --- |
| collector.cjs / source server/poe2_source_browser.cjs | `e1907581fca5bf83cbbf63fad9fe106c912b1c28b2e3a74939e2be16f47da1c4` |
| poe2_source_supervisor.py（source/部署一致） | `e4f9176537c4c3e46687a3394f1e64ab9548654d69f16280b6849c5fb7b81b8b` |
| 当前专用service | `01d89279c2e09c554e4af6553b6521ef152f980b9cfdb7eee1de181e83534ca0` |

collector/API/worker均active。Task6仍需将最终上述身份与真实owner注入、自然分享采集、schema/gaps、missing jewels/base_info导致的needs_input以及任务结束回收绑定；本轮没有再次请求分享，历史成功snapshot不冒充最终版E2E。

### 第二轮修复 R4 / P2

仅修改 `server/poe2_source_supervisor.py` 的退出条件，新增 `tests/poe2_source_supervisor_test.py` 并更新本报告。子进程已退出不再提前结束stdout读取；继续读取直到完整JSON换行/EOF，仍受8MiB大小上限、原deadline和SIGTERM停止条件限制。子孙回收顺序保持不变。

单个大响应回归采用227303字符payload及末尾`tail=complete`，通过测试harness将每次pipe读取限制到1024字节并在读取后让出5ms，确定性形成worker已正常退出而管道尾部仍未读完的时序。云端旧版先失败：`result.ok=False`（`task3-r4-red.log`）；删除poll提前退出后，同一用例通过，完整payload和尾部标记均匹配（1 test，1.254秒）。追加运行受影响的R2父死detached子孙/另一并行任务及deadline回收两项JS测试，两项通过（1.507秒）。输出 `evidence/link-research/task3-r4-green.log`。

只上传、安装改动的supervisor，重启专用collector以刷新其只读文件bind mount；API/worker没有重启。source文件、宿主部署路径以及服务实际mount namespace内的supervisor SHA256均为 `b2dadd3c8d898eac0e0fb509dd26f30e8925ffcec9a97b0bc392cf13b1fa3d31`，替代上表旧supervisor hash。collector JS及unit身份不变。没有请求真实分享、安装依赖或提交推送；最终真实页证据仍交Task6。
