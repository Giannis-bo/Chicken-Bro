# 2026-09-11 联合发布

源码`22c681f99f457329f1b25570343b7f9be401201b`的研究预算、原生拒绝、G10昵称与SimC机制诊断已联合上线。API/Worker同步运行`/opt/chickenbro-releases/badcase-22c681f99f457329f1b25570343b7f9be401201b`，Web为`/var/www/chickenbro-web/releases/research-22c681f99f457329f1b25570343b7f9be401201b`。后续证据/控制面提交不改变此运行身份。

[结果](result.json)记录13个公网Web文件SHA通过和45.6秒观察；[最终核对](final-check.json)确认两个进程实际目录、配置摘要、目标产物、旧版本逐文件保留及私有恢复快照。该批17个backend覆盖文件和基底860文件见[后端清单](manifest.json)，13个Web文件见[Web清单](web-manifest.json)。没有改生产配置或引擎版本。

原始私有回执和固定执行器保留在云端root/0700 `/var/lib/chickenbro-joint-research-20260911/`；[脚本哈希](script-hashes.json)绑定实际执行器。[语义门禁](semantic-review.json)绑定三份完整回执并记录研究/原生/G10/精度判词。首次Candidate失败与零模型补验分别保留于上级目录。生产新增0009为additive，不回填或重写历史研究。

本项研究Candidate/live各3模型+1SimC，总6/2；原生任务总5/8模型，本次live1；G10总7模型/6SimC/31来源，本次live1模型+2SimC。精度复用G10，不额外调用。48次额度耗尽由受控零上游夹具形成，不是48次真实查询。

## 恢复边界

旧backend为`/opt/chickenbro-releases/badcase-342039cab3516176e7436e7af30dc2e1c7897bfc`，旧Web为`/var/www/chickenbro-web/releases/food-342039cab3516176e7436e7af30dc2e1c7897bfc`。私有`badcase-recovery.json`保留原API/Worker环境，root/0600且manifest绑定已核验；不把其内容写入仓库。

如需恢复，先在`/run/lock/chickenbro-release.lock`下重新核对当前指针和本批manifest；恢复Web到上述旧目录，再使用同目录`deploy.py`的`Release.run('rollback')`执行排空门禁与API/Worker同步回切，最后按runbook核对业务和公网旧Web哈希。独占锁内调用类方法，不嵌套调用再次获取同锁的CLI；不要重放`execute.py`。保留新增表及生产新写入，不覆盖旧dump、不删除数据。

本轮没有执行回滚或恢复演练；保留和校验恢复材料不等于恢复已演练。QQ仅验证授权URL及CSRF/会话合同，没有新做真人QQ登录；未宣称用户手工验收。
