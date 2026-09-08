# Web FAQ 内容与折叠

状态：`live_verified`，Web/API/Worker 已部署，待用户体验验收。下方本地阶段记录保留当时状态，以本节发布结果为当前事实。

范围：移除 FAQ 副标题；FAQ 内容区域文本可选；四类依次为认识鸡哥、常见问题、Simc模拟、账号记录。默认展开第一类，各类独立折叠，使用原生 details/summary 支持键盘操作。模型名称按用户要求写为 GPT-Astra。Mini 帮助页不在本次截图页面范围内。

## 历史案例出处

本轮通过 Codex read_thread 读取实际历史提问与最终回复。页面提问已简化并去除角色姓名、报告标识等，结果明确标注为历史摘要，不代表当前版本结论或当前角色个人模拟。

| 案例 | 历史任务 ID | 采用的结论 |
| --- | --- | --- |
| 血 DK 四件套 | 01a06a33-5528-78c0-97c7-325b5555dbfa | 466 万、101 次命中、22.5% 符能浪费；区分整场与战斗时间 |
| 武器战排名 | 01a06a64-f60d-7be0-9336-638e04df10fb | 同层 97%，22.5 万与可比样本 27.1 万；技能频率与资源 |
| 先知元素萨属性 | 01a056f0-9a0b-73e1-846f-4166f20beb9d | 修正精通必然最高，不采用存在历史场景限制的模板数值 |
| 先知四件套天赋比较 | 01a05686-cb06-7c70-832d-4bdd7c0d9d92 | 1/3/5 目标固定窗口风元素约领先 2%–4%；非完整副本模拟 |
| 密谋小径引怪 | 01a05594-3cef-7640-b16d-8f4163c1ac92 | 机器人先攻击召唤物，约 3.8 秒后符文命中；高度与寻路仅推测 |

## 本地验证

- `npm run test:taro -- apps/mini-taro/src/web/web-shell-stream.test.tsx`：14 项通过，覆盖 FAQ 导航、返回与草稿/回复保留。
- `npm run typecheck`、`npm run lint`：通过。
- `npm run build:h5`：通过，保留两项资源/入口体积警告。
- 浏览器组件预览：由实际 TSX 服务端渲染和实际 SCSS 编译生成，额外添加全局 user-select:none 以验证覆盖；并非登录后的完整 H5 或生产验收。
- 默认仅第一类展开；鼠标展开第二类后第一类仍展开；Enter 收起第二类。
- 5 个案例；FAQ 标题和正文 computed user-select 为 text；鼠标实际拖选返回“鸡哥是使用 GPT-Astra 模型的魔兽世”。
- 默认 879px 与 390px 视口无横向溢出。临时视口覆盖已恢复。
- `git diff --check`：通过。


## 后续：任务 ID 与换装重跑

2026-09-08 用户进一步要求任务列表可复制完整 ID，并让鸡哥按 ID 换装重跑。Web 列表/FAQ、本账号 baseJobId 复用、完整 equipmentOverrides、编译 v4 与旧 worker 任务兼容已本地实现。未发布、未启用生产 v4、未跑真实云端换装；不把本地 fixture 视为新 DPS 证据。

浏览器直接运行实际 WebSimcView/SimcModel/FAQ 组件，API 使用明确标识的本地演示任务：点击复制后，粘贴到临时输入框，值完整等于 `2110bcab-5fd2-4f5f-8f10-000000000001`；仍停留任务列表。879px 与 390px 无水平溢出，ID 可选，FAQ 新示例可以展开。临时粘贴检查输入框已移除。

验证涵盖：完整 ID 复制、失败提示、复制不打开报告；完整装备参数校验、注入拒绝、场景哈希变化、原快照不变；原任务参数保留、owner 隔离、重复提交幂等、缺场景拒绝；编译 v4 重放 v1/v2/v3 任务；双端 domain guard 接受新场景。未新增依赖，后端沿用此前已存在的隔离虚拟环境。

独立审查发现无附魔值投影问题：已补修明确 null/空字符串为 null、数字字符串为数字，未知字段仍不猜补；追加回归并复审无剩余 actionable findings。保留记录目录已纳入对应 owner 的精确 disposition，62 项控制面测试通过。

发布步骤与回滚条件见 `docs/plans/2026-09-06-chickenbro-simc-tools.md` 的任务 ID 后续节。上线需要 API 与 Worker 同时支持编译 v4，并进行真实云端任务验证。替换输入的装等选项按 SimulationCraft 官方 Equipment 文档核验（https://github.com/simulationcraft/simc/wiki/Equipment），未下载文档或安装/运行本地引擎。

最终本地结果：419 项后端、292 项前端、62 项控制面通过；typecheck、lint、H5 构建与 diff 检查通过。H5 保留既有资源体积警告。独立审查补修后复审通过；未提交、推送或部署。


## 正式发布结果（2026-09-08）

用户明确授权“是的，部署”。功能提交 15b6c5e6c，旧客户端兼容补修 f2932f8b6eb68ea7627ca428e14f460a57ab4ad4；均在本地 codex/faq-simc-task-rerun，未推送/合入 main。

- 正式 Web 为 f2932f8b6 完整生产构建；index 为 JS/CSS 加入同提交缓存版本。
- 正式 API/Worker 为原 wcl-8a1a893b1 发布根的七文件精确覆盖，manifest.json 记录旧/新 SHA。不是全量后端与 main 同步。原数据库 chickenbro_prod、迁移及 SimC 二进制保持不变；通过追加专用 EnvironmentFile 同步启用 compiler v4。
- Candidate 使用 chickenbro_test 与真实 Chat/SimC；原配置和饰品互换两项均成功，装备报告匹配、原任务未变、同 owner 双端可见、其他 owner 404。Candidate 仅后端真实运行验证，Web 在本地实际组件和生产页面验证。测试站当前根与服务已恢复原 d94646b6e，临时 dropin 已移除；测试库补齐既有第五项并发迁移，候选发布根保留。
- 正式验证使用专用临时验证会话，结束即撤销。真实鸡哥按基线任务 8000e8b5-d0a3-4b51-85a4-6a9efc70bbeb 创建 e30fbab5-73ef-4b2f-a24a-de1a52aba1f7；DPS 228678.27 / 226853.58，100 次迭代只证明执行链路与装备一致性，不作为装备收益结论。原场景保留、实际报告装备、跨端可见与其他账号隔离通过。
- 正式浏览器原用户登录态恢复，既有 Giannis 任务显示完整 ID，点击后系统剪贴板与完整 ID 完全一致；FAQ 四类/五案例/换装示例与 GPT-Astra 可见，折叠交互和 text 选择样式通过，无横向溢出。此前本地鼠标拖选已验证。
- 新客户端通过 scenarioVersion=2 获取完整装备覆盖；旧小程序工作台响应保持原场景字段，报告仍含实际装备。12 项后端合同/跨端回归、6 项客户端回归、类型/lint、生产 H5 重新通过；线上旧版列表/详情与新客户端字段核对通过。
- 生产回滚点及七文件清单见 production-publish.json / manifest.json。恢复旧编译前先停 API 新写并排空 v4 任务，再恢复旧代码/Web 指针、移除本轮两项 dropin 与非秘密 compiler env，reload/restart。无删除旧根、无数据库回滚或清理。
- 本轮未重新扫码、未上传/发布小程序、未宣称用户验收。裸域 chickenbro.cloud 的附加检查遇到证书主机名不匹配，既有 TLS 配置未改；正式入口使用 https://www.chickenbro.cloud/。

正式 www 入口 readiness 为 ready，34 项公网静态文件 SHA 与发布 manifest 一致；最终 62 项控制面通过。见 public-verification.json。
