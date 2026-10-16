# 旧版个人 QQ 退役

状态：2026-10-16 已清理并验证。用户明确授权移除炸鸡 QQ（旧版）全部能力和云端环境。保留炸鸡队长 Web 的 QQ OAuth、Chat/SimC/POE2，以及官方炸鸡 QQBot 原单测试群 Candidate。

## 执行结果

- 移除旧版 transport、persona、测试和 NapCat 启动工具，共53条可执行路径；撤销共享 Chat/Worker/identity 的旧版挂接，6份旧SQL移至 `docs/archive/legacy-qq/migrations`，不再由迁移runner加载。历史Git、计划与发布证据保留并标记退役。
- 移除云端4个systemd单元、2个NapCat容器、专属网络与镜像、13个独立正式/Candidate/测试/恢复验证数据库、32个原目录/文件入口，以及专属系统用户与组。精确目标见 [云端执行器](cloud_cleanup.py) 和 [最终回读](cloud-final.json)。
- 两个旧版专属本地工作区与分支已归档并移除；原WIP（含ignored验证材料）、源码及分支均独立恢复核验。主目录原旧版WIP先保留私有恢复副本；无关Codex记录与官方工作区保持。
- Web后端1811文件、磁盘/公网15文件、官方QQBot最新28文件匹配；保留的4个服务PID、进程cwd、Web/代码/引擎指针未变。公网readiness ready、官方网关READY、白名单仍为1群。旧端口16099/13001关闭。

## 恢复核验与保留

本地私有恢复目录 `/Users/boyuan/.codex/recovery/legacy-qq-20261016` 保存WIP、完整旧工作区（1927/1965文件）及Git bundle，已独立解包哈希校验与unbundle/fsck。

云端root私有目录 `/var/lib/chickenbro-retirement/legacy-qq-20261016` 保留文件归档、数据库dump、原容器定义/账号配置和离线镜像。13134文件已独立解包核验元数据/哈希，13库均独立恢复并逐表核对计数与内容指纹；基础镜像与两个容器可写层均在最初为空的隔离Docker数据目录加载，配置及全部层一致，未启动QQ应用。验证副本与撤下的重复文件已清理；凭据、会话和原始消息只在私有恢复包中。

恢复入口见 [恢复说明](RECOVERY.md)。退役不授权重新开通群业务。

## 代码与验证

- 所有运行/测试在云端独立源目录进行，无新增依赖或本地应用运行。
- 后端888项：887通过，1项Windows目录junction检查在Linux跳过。
- 控制面63项全部通过；全新隔离PostgreSQL的迁移及durable Chat共22项全部通过，无跳过。
- 退役合同先红后绿，保留网站QQ登录；清理器3项故障/续跑/容器替换身份检查先红后绿。
- 独立只读审查与修复见 [审查摘要](review.json)。初始控制面发现空路径数组和云端归档Git属主配置问题，均修正后通过；旧迁移集成测试固定在0008的断言更新为当前完整产品迁移并确认不创建qq_channel。
- 空镜像验证首次以源daemon的manifest ID查找vfs的config ID失败，随后按配置内容与全部层核对通过；另一次验证socket路径过长，缩短独立运行路径后通过。原失败记录保留私有目录，未对保留产品重启或切换。
