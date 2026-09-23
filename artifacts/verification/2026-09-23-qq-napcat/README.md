# QQ NapCat 环境准备记录

时间：2026-09-23。本页保存首次环境准备与登录检查；用户随后授权接入，最新实现与部署见[通道实施记录](implementation.md)。以下“当前边界”为准备阶段的证据边界。

## 已验证

- 实例 metadata：`ins-93tgv1rb` / `ap-shanghai`；SSH alias `wow-lighthouse`。
- NapCat `4.18.28` / Linux QQ `3.2.30-50969`，镜像已按 RepoDigest 固定。
- 容器 `chickenbro-napcat` 运行，未见自动重启/OOM；采样内存约 330 MiB，限制 768 MiB / 1 CPU。
- 管理页 HTTP 200；未认证管理调用返回业务码 `-1 / Unauthorized`，认证后的版本和 QQ 登录状态读取通过。HTTP 状态本身不能证明鉴权。
- 仅宿主机 loopback 发布 `16099` 和 `13001`；配置有独立 WebUI/OneBot token，凭据 root/0600。
- 生产 API/Worker 的 PID、启动时间与 backend/Web 指针前后完全一致，readiness 通过。
- Docker Hub 直连超时后使用现有 `127.0.0.1:7890` 出站代理下载项目指定镜像；下载前 Docker 无运行容器。临时 Docker 代理 drop-in 已移除并恢复 daemon。

结构化结果：[首次环境准备](environment.json)、[最新登录状态](login-status.json)、[OneBot 身份和群验证](onebot-login.json)、[重启恢复缺口](restart-recovery.json)。验证器：[verify-environment.py](../../../server/qq-channel/verify-environment.py)。

本地验证：Shell/Python/JSON 语法、`git diff --check` 通过；`project-state`、项目/后端 owners、refactor-inventory 相关控制面测试 16/16 通过。新增文件已加入准确的保留规则。没有应用代码改动，因此本次未运行 Chat/SimC/PoB 业务测试或 Web 构建。

## 当前边界

- QQ 已扫码登录，`coreReady=true`；实际小号、目标群成员关系和指定群主均核实。未生成鸡哥群回复，未发送测试群消息。
- OneBot 已通过授权 `get_login_info`、`get_group_list`、`get_group_member_info` 只读往返。无凭据连接先返回 HTTP 101，随后返回业务码 `1403 / failed` 并关闭；因此仅看握手状态会误判。
- 鸡哥业务适配器未实现，业务配置 `enabled=false`；机器人、允许群和管理员准确值已写入私有配置。
- 数据库、现有 API/Worker、Nginx、网站制品未修改。没有执行产品发布或业务回退演练。
- 本机文件保留未提交；环境准备不等于正式群开放。

## 登录恢复检查

首次扫码后身份、入群、群主及鉴权验证通过；设置自动登录账号后重启独立 NapCat 容器，QQ 快捷登录返回“登录态已失效，请重新登录。”。数据目录挂载保留，快捷登录列表为空，根因尚未确定。用户再次扫码后已恢复在线并重新验证，自动恢复仍未通过。没有再次重启或反复尝试密码登录。

## 云端保留内容

- `/opt/chickenbro-qq-channel`：固定镜像、启动脚本、脱敏证据副本。
- `/var/lib/chickenbro-qq-channel`：私有 QQ 登录数据、配置和插件目录。
- `/etc/chickenbro-qq-channel`：私有凭据与关闭的通道配置。
- `/tmp/chickenbro-napcat-20260923.iFip3N`：本次部署脚本与只包含 PID/路径的生产基线。正式基线副本保存在 `/opt/chickenbro-qq-channel/production-before.txt`。

恢复方式为停止容器并保留以上数据。后续登录、更新或移除均核对这些精确目标，不使用泛化 prune/clean。

## 后续自动登录修复

密码回退配置后，新容器启动及随后一次容器重启均无需扫码恢复登录，见 [automatic-login-recovery.json](automatic-login-recovery.json)。当前通道已恢复，真实群收发仍待复验。上方首次环境和重启失败记录为历史证据。
