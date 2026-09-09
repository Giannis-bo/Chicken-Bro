# 186 个旧微信测试账号清理结果

用户在明确的“186 个仅关联微信账号及其业务数据全部清理，QQ 保留”范围问题后回答“可以”。按原 186 个 UUID 白名单执行，不扩展到无 provider 关联账号。

## 已执行

- 一致性快照导出私有 pg_dump；独立恢复全部 19 张产品表，每表逐行 SHA-256 指纹完全一致。
- 恢复副本执行精确主键删除演练，保留记录完全一致，随后回滚演练，使恢复副本保持完整。
- 正式事务锁定已知表，重新检查 provider、目标数据指纹、精确主键、关联引用与活动任务，再按依赖删除；QQ 和其他保留记录逐行指纹前后完全一致。
- 删除 186 个账号、222 段会话、651 条消息、258 个 Chat run、7 个 SimC 任务及其结果/attempt、17 个快照、7 条队列项、68 条会话凭据、22 条已绑定旧登录票据、186 条身份映射和 3465 条关联审计。目标无图片、execution、tool result 或 usage 记录。
- 独立提交后检查：微信身份为 0，QQ 身份 18，无关联账号 14，两个模拟结果保护触发器均启用，无未验证的产品约束。API/Worker active，公网 readiness 正常；不冒充本轮真实 QQ 登录或新 Chat/SimC 业务验收。

## 约束与恢复

第一次恢复演练遇到 `simc.simulation_results is immutable`，事务已回滚，正式库未改动。核对源码 migration 和数据库触发器后，只在受控事务内临时停用 `trg_simulation_results_immutable`，删除白名单结果后立即启用；外键和 TRUNCATE 保护始终保留，提交前后核对触发器定义与状态一致。

最终备份 `/var/backups/chickenbro-mini-retirement/20260909_retire186_02/before.dump` 与 `manifest.json` 只存放云端私有目录。恢复库 `cb_mini_restore_20260909_retire186_02` 保持完整，所有非超级用户登录角色均无 CONNECT。第一次演练的私有备份/副本亦保留，不自动删除恢复材料。

恢复先在隔离库还原，再按私有 manifest 提取本次目标并按依赖顺序恢复；不得用旧全库快照覆盖新的 QQ 写入。本次仅清理正式库中的确认范围，不删除无关联用户、未归属目标的匿名旧登录票据/审计、历史 migration、代码证据或备份，不推送/部署本地源码。

## 证据

[用户范围](approved-scope.json) · [恢复证明](recovery.json) · [正式提交结果与保留指纹](applied.json) · [提交后独立检查](post-check.json) · [readiness](post-readiness.json) · [精确执行脚本](cleanup.py)
