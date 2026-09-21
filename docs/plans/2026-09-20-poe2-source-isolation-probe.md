# POE2 WeGame 来源采集隔离探测

日期：2026-09-20  
范围：仅验证云端隔离方案可行性；没有实现产品代码、修改服务、提交或发布。

## 结论

专用采集进程可以在不改宿主防火墙、系统 DNS 或现有 Candidate 服务的前提下访问 WeGame 公网 HTTPS，同时由 systemd 的 cgroup/BPF 地址策略阻断 loopback、RFC1918、link-local 和云 metadata 地址。现有失败的直接原因是宿主 `/etc/resolv.conf` 指向 `127.0.0.53`；loopback 全拒绝后，DNS 请求在到达 systemd-resolved stub 前被拦截。

可行解是给采集 unit 只读绑定独立 `resolv.conf`，使用明确配置的公网 DNS，并继续完整拒绝 `127.0.0.0/8`，不为宿主 resolver 开放任意 loopback 端口。本次 transient probe 验证了该路径。

## 云端探测条件

- 主机：`wow-lighthouse`
- Candidate 根目录：`/opt/chickenbro-candidates/poe2-20260918`
- systemd 255，cgroup v2
- transient unit：`RuntimeMaxSec=30s`、`DynamicUser=yes`
- 主要隔离属性：`NoNewPrivileges=yes`、`ProtectSystem=strict`、`ProtectHome=yes`、`PrivateTmp=yes`、`PrivateDevices=yes`、空 capability 集、`RestrictAddressFamilies=AF_INET AF_INET6`
- 内核地址拒绝：`127/8`、`10/8`、`172.16/12`、`192.168/16`、`169.254/16`、`::1/128`、`fc00::/7`、`fe80::/10`
- unit 私有 DNS 文件：`1.1.1.1`、`8.8.8.8`，只读绑定到 `/etc/resolv.conf`
- 连接超时：公网 HTTPS 5 秒；每个拒绝目标 1.5 秒
- 未登录，没有调用猜测 API，没有输出分享 URL、token、响应正文或凭据值

## 观测证据

隔离 unit 以临时 UID/GID `62846:62846` 运行。环境变量名只有：

```text
INVOCATION_ID, LANG, LOGNAME, MEMORY_PRESSURE_WATCH,
MEMORY_PRESSURE_WRITE, PATH, SYSTEMD_EXEC_PID, USER
```

按 `SECRET`、`TOKEN`、`PASSWORD`、`DATABASE`、`QQ_`、`COOKIE`、`KEY` 检查，没有匹配的环境变量名。该 unit 没有加载 Candidate API/worker 的 EnvironmentFile，也没有继承服务凭据。

公网路径结果：

```text
direct_dns_ok 1.1.1.1:53 response_bytes=51 id_match=true
system_dns_ok www.wegame.com.cn addresses=1
https_ok HTTP/1.1 302 Moved Temporarily bytes_sampled=397
```

`302` 证明该隔离进程完成了公网 DNS、TCP、TLS、SNI 和 WeGame HTTP 响应读取；它不代表分享内容业务验收。

受保护目标结果：

```text
169.254.169.254:80  timeout after 1502 ms
127.0.0.1:8796     timeout after 1502 ms
10.0.0.1:80        timeout after 1501 ms
```

这些目标均未建立连接。此前已知 `127.0.0.1:8796` 是 Candidate API，因此 loopback 拒绝不是由“端口没有监听”产生。metadata、loopback、RFC1918 均受同一 unit 的 systemd IPAddressDeny 内核策略约束。

探测结束后，远端临时目录与 transient unit 均已清理；`chickenbro-poe2-candidate-api` 和 `chickenbro-poe2-candidate-worker` 仍为 active。没有修改全局 nftables/iptables、宿主 `/etc/resolv.conf` 或服务配置。

## 建议的正式边界

采用单独的最小采集服务和 systemd socket：

1. `chickenbro-poe2-source-browser.socket` 创建 Unix socket，由 systemd 固定 owner/group 和 `SocketMode=0660`；只有需要发起采集的 Candidate 应用账户加入该 socket 的调用组。
2. `chickenbro-poe2-source-browser.service` 使用 `DynamicUser=yes`，不配置数据库、QQ、Cookie、对象存储或应用 EnvironmentFile。socket activation 把已打开的 Unix socket FD 交给动态用户进程，浏览器不需要访问应用运行目录或 TCP loopback。
3. 服务仅接受版本化的小型请求，例如 `{request_id, canonical_url}`；拒绝客户端传入 header、Cookie、代理、调试端口、任意脚本或任意目标 URL。响应只返回净化后的 role、equipment、skills、passives、jewels、source timestamps 与确定性状态。
4. 浏览器只自然打开已校验的 canonical URL。Playwright request/response/redirect 事件逐次执行 HTTPS host + path allowlist；阻断广告、遥测及非必要资源。每次重定向都重新校验。DNS rebinding 到私网仍会被 systemd IPAddressDeny 拦截。
5. 不开放 remote debugging TCP；浏览器子进程与采集器同一 cgroup，unit 终止时整体回收。保留 60 秒业务上限，并在 systemd 再设略高的硬上限；本次探测采用更严格的 30 秒上限。
6. 采集器内实现响应限制：单响应 2 MiB、必要响应累计 8 MiB、全局并发 2、owner 并发 1、关闭开关。缺必需响应返回 `INCOMPLETE`；`GetJewels` 空值保留 `jewels.status=missing`。
7. 独立 DNS 文件作为部署产物只读绑定，不改宿主 resolver。公网 resolver 地址应作为运维配置并做部署前可达性检查；resolver 故障返回 `SOURCE_UNAVAILABLE`，不回退到 `127.0.0.53`。

建议 service 保留 `AF_UNIX AF_INET AF_INET6`，其中 AF_UNIX 仅用于 IPC；继续拒绝全部 loopback IP。若将来需要更强的“只能访问指定公网域名”出口约束，应增加专用出口代理或独立网络命名空间，在代理侧做 TLS SNI/域名 allowlist，并让 namespace 只路由到该代理。不要用放开 `127/8` 的方式接入宿主代理或 DNS。

## 未覆盖与后续验收

- 本次是 Python 网络探针，不是 Chromium 页面采集。已证明现有云环境能承载所需 DNS/HTTPS 与内核私网拒绝组合，但还没有证明 Chromium 依赖、sandbox、自然页面响应捕获和 60 秒回收合同。
- 本次只读取 WeGame 根路径的响应头样本，没有使用原始公开分享 URL，因此没有产生 GetRoleInfo/GetTalentTree/GetEquipments/GetSkills/GetJewels/BtGetBase 的新业务快照。
- 应用层 host/path/redirect/body allowlist、并发限制、Unix socket 鉴权与净化 schema 尚未实现或测试。
- `1.1.1.1`、`8.8.8.8` 仅用于本次可行性探测。正式 resolver 需要结合部署地域验证长期可用性与合规要求。
- 正式 Candidate 验收仍需用用户给定公开分享页，在上述专用服务中跑 Chromium，确认自然请求集合、净化字段、缺口、退出回收和第二请求并发拒绝；HTTP 成功不能替代这些业务证据。
