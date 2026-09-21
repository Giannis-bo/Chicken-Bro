# POE2 天赋树第一阶段

> 当前状态（2026-09-21）：已完成。用户已验收并授权发布，运行源码 `77cee1603` 已上线，提交与合入已完成；见[正式发布记录](../../artifacts/releases/2026-09-21-poe2/README.md)。下文 Candidate、禁止提交与待验收等表述记录此前阶段，不代表当前状态。

用户已批准会话中的第一阶段设计：完整天赋树、升华、已点高亮、节点详情。当前会话直接执行，保持已有 Candidate 和全部 WIP；不提交、合入或切生产。

## 接入与验收

- [x] 云端 PoB 输出只读树快照：实际坐标、连线、节点效果、分配状态、武器组、当前升华。GET 构筑树先做 owner 校验；历史计算视图读取对应 job 的导出码；引擎版本不匹配明确拒绝。
- [x] typed domain/API 增加只读树合同；独立 Canvas 展示拖拽、缩放、搜索、定位已点、节点详情及升华切换。切账号/构筑后丢弃旧请求；空树、加载失败可重试。原始构筑与结果方案明确区分。
- [x] 同版本官方发布包提取图标为自托管静态图集，记录来源及哈希。缺少图标可显示节点轮廓，不影响分配语义。
- [x] 云端相关单测、类型检查、H5 构建；真实构筑节点逐项核对 PoB，浏览器验证天赋/升华/详情/搜索/390px，两账号隔离。保存 Candidate 发布前备份及发布后文件清单。

## 文件职责

- `server/app/poe2/tree_view.lua`：从已载入的 PoB spec 导出实际树视图。
- `server/app/poe2/engine.py`、`bridge.lua`：复用现有受限云端进程，增加只读视图模式。
- `server/app/poe2/application.py`、`server/app/api/routes/poe2.py`：鉴权、版本核对和构筑/结果树接口。
- `packages/domain/src/poe2-tree.ts`、`packages/api-client/src/poe2.ts`：合同与 transport。
- `apps/mini-taro/src/web/Poe2PassiveTree.tsx`、`poe2-tree-canvas.ts`：交互与绘制；`WebPoe2.tsx` 挂载。
- `scripts/prepare-poe2-tree-art.py`：云端确定性提取已有发布包中的资源。

所有执行、测试、构建和下载仅云端；本地只读写源文件和传输。测试重点：跨账号/构筑迟到结果、旧引擎构筑、武器组分配、升华空状态、实际珠宝/属性节点效果。保留原有天赋调整输入，图上编辑为后续范围。

交付：云端 Candidate 验证完成，等待用户验收。历史 Candidate 记录 `verification/2026-09-20-poe2-passive-tree/README.md`（保留于原工作树，未纳入 Git；正式验收见本页发布记录）。
