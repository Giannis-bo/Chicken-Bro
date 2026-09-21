### Task 3: WeGame 公开分享采集与隔离

**Files:** 新增 `imports/sources/wegame.py`、`server/poe2_source_browser.cjs`、`tests/app_poe2_wegame_source_test.py`、`tests/poe2_source_browser_test.cjs`；修改 Candidate runtime/deploy 配置。

**Interfaces:** `collect_wegame(ref: SourceRef) -> dict`，返回只包含 role、equipment、skills、passives、jewels、source timestamps 的净化快照；失败返回确定性的 SOURCE_UNAVAILABLE/AUTH_REQUIRED/RATE_LIMITED/INCOMPLETE。

- [ ] 写浏览器适配器合同测试：任一请求转私网/元数据地址即拒绝；60 秒退出；单响应 2 MiB/必要响应总量 8 MiB；缺必需资源是 INCOMPLETE；缺珠宝内容保留 missing，不补空数组代表完整。

```python
def test_missing_jewels_stays_missing(self):
    snapshot = normalize_capture(self.capture_with_empty_jewels)
    self.assertEqual(snapshot['jewels']['status'], 'missing')
    self.assertNotIn('openid', snapshot['role'])
```

- [ ] 云端失败测试后实现新独立浏览器账户/进程，最小环境、无宿主凭据、无外部 remote debugging；采集 allowlist 精确到必要站点及路径，阻断广告/遥测。通过网络命名空间/出口代理或等效实际内核策略拒绝内网，单靠 URL 字符串过滤不计通过。
- [ ] 浏览器只打开 canonical_url 并观察页面自然响应；不重放额外 API、无登录、无验证码绕过。采集器强制域名/重定向/响应体/总时限；返回明确状态并关闭上下文。
- [ ] 全局并发 2、owner 并发 1、关闭开关；云端验证拒绝内网连接、并发超额与退出回收。
- [ ] 实际打开用户给定 WeGame 分享，保存净化后的 schema、条目数量和字段缺口，与前次样本作字段层比较；来源改变只报差异，不固定断言角色永久不变。公开使用规范未确认时保持 Candidate 范围。

## Binding context

Local workspace /Users/boyuan/Documents/wow_mini_program/.worktrees/poe2-20260918; cloud ssh wow-lighthouse, root /opt/chickenbro-candidates/poe2-20260918. ALL execution and testing cloud; local only file read/edit/transfer. No commit/push/merge; no production changes; no subagents. Root coordinates service deployment.

Read docs/plans/2026-09-20-poe2-jewels-recheck.md. Public page GetJewels response empty, clicking page merely toggles display; do not issue guessed APIs. Need capture GetRoleInfo/GetTalentTree/GetEquipments/GetSkills/GetJewels plus observed BtGetBase optional mapping IDs. Strip unrelated economy, openid/role IDs/account references not needed downstream, requests and telemetry. Preserve source metadata needed for mapping but do not print raw share URLs/tokens.

Cloud has systemd 255+cgroup v2, nft/iptables/unshare; no bwrap. Existing Playwright and chromium paths runtime/browser/node_modules/playwright and runtime/browser/chrome-headless-shell-linux64/chrome-headless-shell, private libs runtime/browser/root/usr/lib/x86_64-linux-gnu. Existing worker runs ubuntu with NoNewPrivileges=yes and ProtectSystem=strict; it cannot simply sudo per request.

Root tested isolated systemd DynamicUser+IPAddressDeny RFC1918/127/169.254: connect to metadata and Candidate localhost timeout (kernel drop). DNS also failed with blanket loopback deny because host resolver is local. Design a dedicated least-privileged collector service with reliable DNS and kernel-enforced private destination denial; do not relax deny for arbitrary loopback ports. An allowlisted public resolver in a private resolv.conf is an option; verify actual resolver traffic and public request. IPC to application should be restricted Unix socket or similarly explicit channel without putting DB/QQ credentials in browser process.

Service deployment files can be delivered for root to apply in Candidate; bounded cloud probes/isolated test processes authorized. Do not change firewall rules globally or break existing production traffic.

Report docs/plans/2026-09-20-poe2-link-task3-report.md: files, interfaces, evidence and limitations; root dispatches independent review.

补充已验证研究：读取 `2026-09-20-poe2-source-isolation-probe.md`。DynamicUser + 私有公网 resolv.conf + IPAddressDeny 可同时访问公网 WeGame 并阻断 metadata/loopback/RFC1918；使用报告中确切配置，不重复大范围方案探测。尚需实际 Chromium 和 IPC 验证。root 已清理短期探针；不要依赖它存在。

Task2 唯一端口 `collect(ref: SourceRef)->dict`，来源错误抛 ValueError/RuntimeError(code)，code限定SOURCE_UNAVAILABLE/AUTH_REQUIRED/RATE_LIMITED/INCOMPLETE；TimeoutError/ConnectionError代表可重试基础设施异常。缺珠宝应返回正常净化snapshot（missing），由Task4转needs_input。请在报告完整列明净化snapshot schema，让Task4无需重新阅读私有rawcapture；所有递归公共值与issues不得包含openid/分享token/请求rawbody。Task2独立审查已将collector净化列为本任务显式验收项。

本任务提供collector的安全IPC客户端和部署文件；Task4在worker/main.py最终注入collect/map/convert（三端齐备才启用）。本任务不需要改数据库/state machine。服务启动和隔离测试可在本任务云端完成，但不要重启Candidate API/worker；仅创建本次专用collector unit，不改生产unit/globalfirewall/resolver。
