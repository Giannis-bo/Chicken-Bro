# 运营后台发布 · 2026-09-09

已按用户确认范围实现、合入并发布 `/admin`。用户明确确认浏览器当前「袁博」QQ 会话就是指定本人账号；通过该会话显示的内部 ID 配置唯一管理员，未按昵称、手填 QQ 号或首次登录自动授权。身份只保存在云端 root-owned 0600 配置中，仓库记录其 SHA256。

## 功能与口径

总览/用户趋势/Chat 反馈与耗时/SimC 状态耗时及专精分布；今天、近7/30天、自定义日期。统一北京时间、最多366天；任务/提问按发起日期归入所选期间，反馈和状态展示查询时的当前值。后台只读，不包含访问埋点、Token或费用推算。排除固定测试账号和已知四类模拟验收身份；实际 QQ 用户依当前 provider/appid 归属，不统计旧微信或无身份测试记录。

## 验证

- [本地](local-checks.json)：本任务后端470项通过；合并并行Badcase源码后的后端555项通过；最终前端269项、typecheck、lint及H5构建通过。编译保留既有大资源警告。独立PostgreSQL验证时区、去重、反馈分母、测试排除、异常SimC结果及无样本null。主目录控制面63项通过；worktree曾因另一任务的未跟踪旧证据链接缺失而有1项失败，未伪称该次全通过。
- [隔离验收](candidate-final.jsonl)：独立数据库、目录、Cookie、18790/18794 API/Worker；管理员/第二账号、CSRF、QQ授权地址、真实图片答案4729、SimC正指标/来源、幂等及归属隔离通过。首轮使用无关图片被产品规则拒绝，见[保留记录](initial-candidate-failure.json)，只改验收素材后重跑；未放宽产品规则。临时会话已撤销，进程已停止。
- [生产业务](production.jsonl)：复用专用验收账号，没有新增生产身份；真实图片/Worker/SSE、正SimC指标、幂等、第二账号隔离通过；非管理员403，匿名401。
- [真实浏览器](browser-verification.json)：复用用户真实QQ会话读取后台、刷新今天日期；最终原生控件样式和390宽度布局验证。没有冒充本轮重新走完QQ OAuth或用户手工验收。
- [独立对账](live-reconciliation.json)：11个真实QQ用户、7个期间活跃用户、32次提问、5个模拟任务与独立SQL相符（19:58前后快照，会随使用变化）；API和Worker加载同一绑定；200/403审计存在；匿名401且no-store；14个公网Web文件与最终清单逐个SHA一致。

## 身份与并行发布

后端运行源码 `03275ee5ce677afe9c4e1d0d6a735642beed8e6b`，目录 `/opt/chickenbro-releases/admin-ops-03275ee5ce677afe9c4e1d0d6a735642beed8e6b`，8个后端文件覆盖/新增，见[后端清单](manifest.json)。

最终Web源码 `8fba1535f226c5dd6eebbcd3980fc2ca52c4075f`，目录 `/var/www/chickenbro-web/releases/admin-ops-web-8fba1535f226c5dd6eebbcd3980fc2ca52c4075f`，见[最终Web清单](web-final-manifest.json)。首轮正式浏览器发现Taro改写button/input选择器，已改成明确CSS类并补发纯Web产物；最终构建确认不再生成对应taro-button-core/taro-input-core选择器。

本任务开始后的Badcase工作并行合入main，合并保留其所有源码和四个当时WIP文件；运行清单只覆盖本任务已验收管理员范围，没有把main上的未发布Badcase变更冒充本次运行产物。main的合并提交、后端运行提交、最终Web提交分别记录；后续其他任务可发布新的后端，须沿用权限配置并核验这些文件。

## 回滚

原后端 `simc-experiments-7ef8a5dfd9a48de9c9d6c12c660b6564446fd5eb`、原Web `help-unread-32a43a17f6b47fed83f45c0bfb094aabaff8e0e6` 保留且逐文件未变；首个admin Web也保留。[发布](promotion.jsonl)、[绑定](admin-binding.json)、[Web补发](web-final-publication.json)均有独立证据。

本批仅新增API/Worker的 `99-zzzzzz-admin-ops-03275ee5ce67.conf`，引用 `/etc/chickenbro-admin-ops-03275ee5ce67.env`，字段只有 `WOW_ADMIN_USER_ID`。完整恢复入口（root、现有运行时）：

```bash
/opt/chickenbro-runtime/bin/python /var/tmp/chickenbro-admin-release-03275ee5ce67/rollback_all.py /var/tmp/chickenbro-admin-release-03275ee5ce67/manifest.json /var/tmp/chickenbro-admin-web-8fba1535f226/manifest.json
```

该入口拒绝后续其他版本，先把最终Web恢复为同API合同的首个admin Web，再由本批部署器在空闲门禁下恢复原后端/原Web、移除仅本批两个drop-in并重启匹配API/Worker。不覆盖数据库、不删除用户记录，不移除其他批次配置。恢复脚本/原产物已核对，**本轮未实际执行生产回滚演练**；如果已有后续版本，必须先核验新版本的恢复方案，不能直接调用本入口。

隔离库 `chickenbro_admin_candidate_20260909` 及私有 `/var/lib/chickenbro-admin-ops-candidate` 留作复核，无同步/回填调度。生产权限绑定与QQ归属测试不依赖公开管理密钥。
