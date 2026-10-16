# 私有恢复入口

本次只保留恢复能力；用户已退役该产品，重新部署/登录/开启群业务需要新的明确授权。

## 本地

私有目录 `/Users/boyuan/.codex/recovery/legacy-qq-20261016` 中：`legacy-qq.bundle` 含原main和两旧分支；每工作区的 `full-worktree.tar.gz`、`full-manifest.json`、`wip.tar.gz`、`working-tree.patch` 保存源码及原WIP。先在空目录建立Git、从bundle恢复原commit并核对，再解包WIP；禁止覆盖当前主目录或官方QQBot的WIP。私有 `worktree-cleanup.json` 记录原工作区/分支/SHA。

## 云端

root/0700目录 `/var/lib/chickenbro-retirement/legacy-qq-20261016` 保存精确清单及恢复证明。先将 `files.tar.gz` 解包至独立空目录核对 `file-manifest.json`，将目标dump恢复至新隔离数据库核对 `database-recovery.json`，不要覆盖运行中的数据库。

`napcat-image.tar` 保存原基础镜像；`container-images.tar` 保存两个原容器的可写层。使用私有 `container-images-restore.json` 的tag以及 `container-image-recovery-private.json` 的配置/层信息，在隔离环境加载核对。原manifest ID与vfs config ID可能不同，不能只按daemon的ID认定失败。所有挂载、启动配置和原容器ID在 `container-inspect.json`，挂载数据由文件归档独立覆盖。

私有 `account-recovery-private.json` 保存原系统账号/组的精确条目；仅在无UID/GID冲突的新隔离环境恢复。`unit-enabled-before.json` 保存原单元启用状态，四个 `.unit.txt` 保存原有效单元。群配置、登录材料与凭据保持root私有。恢复旧服务后仍保持停机，开启业务需用户新授权。

清理器以固定容器ID、逐资源fsync日志和无FORCE的PostgreSQL drop执行，未完成批次的intent保存在 `apply-progress.json`；本批已完成后按归档恢复，不重放apply。
