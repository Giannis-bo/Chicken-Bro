# Repository Agent Guidelines

Chickenbro now targets Web-only Chat and SimulationCraft with QQ website login. The 1.0 Mini/Web product is historical. The six-phase rebuild and legacy retirement are complete; historical plans are not new execution authority.

## Current Truth and Scope

- Before Standard or Strict work, read [project state](docs/project-state.json), then [roadmap](docs/roadmap.md). [plans/README.md](docs/plans/README.md) is the only implementation-plan whitelist; new work requires current user authorization.
- Use the [architecture](docs/chickenbro-simc-architecture.md), [verification matrix](docs/verification-matrix.md), [project owners](docs/project-owner-map.json) and [backend owners](docs/backend-owner-map.json). Production procedures belong in the [runbook](docs/chickenbro-simc-production-runbook.md).
- Keep the roadmap concise; record confirmed product decisions there and unconfirmed ideas in [ideas](docs/roadmap/ideas.md). Use `已完成`, `正在推进`, `下一步`, `后续`, `暂缓`, `待决策` consistently.
- [server/app/chickenbro/agent/AGENTS.md](server/app/chickenbro/agent/AGENTS.md) is a runtime product prompt loaded by Chat, not a repository development policy. Treat edits to it as runtime behavior changes.

## Product and Engineering Boundaries

- Only Chickenbro conversations and SimC jobs gain product behavior. Do not revive news, gear, talent, profile, old simulator, WebSim or prototype domains.
- QQ website identities map to server-owned opaque `user_id`; only Web HttpOnly sessions authenticate production requests. QQ creates new accounts; retained WeChat data is not migrated or linked automatically. History and tools remain owner-scoped.
- Web login uses QQ OAuth authorization code with a short-lived, one-use browser-bound state. Validate callback host and QQ app identity. Provider tokens/secrets remain server-side and never enter public responses, logs or stored business records.
- Preserve Taro, typed domain/API layers and explicit `web` and `public` transport context. Server applications own identity, Chat, SimC and workers; HTTP routes adapt transport only. Clients cannot select ownership through request bodies.
- Chat sends and SimC submissions are idempotent; queue claims require leases and ownership checks. SimC results require positive domain metrics and provenance. Keep SimulationCraft on the cloud server; do not install or run it locally.
- Protect dirty worktrees and unrelated changes. Do not reset, clean, force-push, rewrite history or overwrite WIP. Keep credentials out of logs and evidence; inspect configuration presence, not secret values.

## Work and Verification

- Use skills as methods, not a second control plane. Follow global skill selection and authorization rules; select planning, debugging, TDD, worktree or parallel methods only for a concrete delivery risk.
- Lead product discussions with the scenario, friction, normal/exception paths and observable acceptance. Distinguish verified facts, inference and unresolved assumptions.
- Light documentation/configuration changes use the smallest relevant checks. Standard/Strict changes follow the current authorized plan and verification matrix; do not rerun historical migration or retirement for routine changes.
- Review the diff locally against current owners and contracts, then run fresh targeted checks. CodeRabbit and `codex review` are optional second opinions unless the user explicitly requests them; old memory does not add a mandatory remote-review gate.
- Report local, Candidate, live, user-accepted and recovery-verified evidence separately. HTTP 200, a running service, dry-run, process exit 0 or SimC return code 0 is not business acceptance. Bind results to the actual commit/build/runtime involved.
- Use the verification matrix for affected Web acceptance, including Chat/SimC truth and second-user isolation. Missing dependencies require the applicable download/install authorization; do not report skipped checks as passed.

## Release, Recovery and Closure

- Use an isolated Candidate for runtime/API/data/client changes when feasible; record identities, smoke evidence and rollback. Keep async backfill/sync disabled unless explicitly required.
- Production cutover does not authorize destructive retirement. New cloud/data deletion requires an exact manifest, zero live references/connections and independent restore-verified recovery under the runbook. Historical no-backup authorizations cannot be reused.
- Historical six-phase inventory and cutover gates apply only to their migration/retirement scope. Routine local config/document cleanup uses an exact diff, protects WIP and retains recoverability; it does not require production cutover acceptance.
- A mid-flow “OK” continues the approved work; it is not proof of manual testing. Explicit post-test acceptance or a clear “可以收尾/合入吧” authorizes closure within the agreed scope. Local-only instructions still prohibit push or deployment.
- For authorized release closure, review and verify, integrate without history rewrite, push `main`, verify relevant local/remote/deployed identities, and verify the Web artifact. Mini build, preview, upload and public release are retired. Remove finished worktrees/branches only after safety checks.
