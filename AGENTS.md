# Repository Agent Guidelines

This repository is being rebuilt around one product: Chickenbro Chat and SimulationCraft tasks shared by the WeChat Mini Program and Web client.

## Current Truth

- Read [docs/project-state.json](docs/project-state.json), then [docs/roadmap.md](docs/roadmap.md), before Standard or Strict work.
- Use [docs/chickenbro-simc-architecture.md](docs/chickenbro-simc-architecture.md) for ownership and dependency direction, and [docs/chickenbro-simc-production-runbook.md](docs/chickenbro-simc-production-runbook.md) for migration, deployment, rollback, recovery and retirement.
- [docs/plans/README.md](docs/plans/README.md) is the only implementation-plan whitelist. Directory presence and Git history are not execution authority.
- [docs/verification-matrix.md](docs/verification-matrix.md), [docs/project-owner-map.json](docs/project-owner-map.json) and [docs/backend-owner-map.json](docs/backend-owner-map.json) define the current verification and owner control plane.
- Keep `docs/roadmap.md` concise. Put unconfirmed ideas in [docs/roadmap/ideas.md](docs/roadmap/ideas.md); do not revive deleted product domains through an incidental note or historical artifact.

## Product Boundary

- The only user-facing business functions are Chickenbro conversations and SimC jobs.
- The Mini Program has Chat, SimC submit/list/detail and the Web-login confirmation page. Web exposes the same Chat and SimC data after login.
- Mini Bearer sessions and Web HttpOnly sessions remain independent transports. Both resolve through server-owned identity mapping to the same opaque internal `user_id`.
- Shared history lives on the server and is owner-scoped. Never synchronize cookies, OpenID, access tokens or client-local history between clients.
- Web login uses an opaque, short-lived, single-use Mini confirmation ticket. Never place `user_id`, OpenID, tokens or personal data in the scene.
- Out-of-scope news, gear, talent, profile, old simulator, WebSim and prototype APIs may be used only as fenced migration or rollback inputs until retirement; they cannot gain new product behavior.

## User Experience and Acceptance

- Lead product discussions with the user scenario, visible friction, proposed normal and exception paths, observable acceptance, then implementation details.
- Cross-client acceptance requires: Mini login; Mini-confirmed Web login; Chat created and continued from both directions; one SimC job visible with the same status/result from both clients; second-user isolation; independent logout.
- A prototype bypass, HTTP 200, running service, dry-run, successful process exit, Candidate label or SimC return code 0 is not user acceptance.
- Keep verified facts, inference and unresolved assumptions separate. Technical constraints become primary when they affect privacy, data truth, availability, recovery or rollback.

## Engineering Boundaries

- Preserve the Taro workspace, typed domain/API layers and explicit `mini`, `web` or `public` transport context.
- Server applications own identity, Chat, SimC and worker behavior; route modules adapt HTTP only. Clients never select ownership or trust identities supplied in request bodies.
- Chat sends and SimC submissions are idempotent. Queue claims use leases and ownership checks; semantic SimC results require positive domain metrics and provenance.
- Keep the SimC runtime on the cloud server. Do not install or run SimulationCraft locally.
- Protect dirty worktrees and unrelated user changes. Never reset, clean, force-push, rewrite history or overwrite work in place.

## Superpowers and Harness

- If a relevant `superpowers:*` skill is exposed, use it as a method layer. Harness remains the repository control plane for scope, evidence, release and closure.
- Choose planning, debugging, TDD, review, worktree or parallel methods only when they reduce a concrete delivery risk; do not create a second authority document for a method.
- Use the smallest applicable verification for a bounded Light change. Standard and Strict work must follow the current phase plan and verification matrix.

## Verification Discipline

- Use local code review as the primary pre-merge review. Review the source diff against current owners, plans and contracts, then run fresh targeted tests.
- `codex review` is optional second-opinion evidence and never the sole gate.
- Treat local, Candidate, live, user-accepted and recovery-verified evidence as separate levels. Never promote partial, skipped, blocked or stale evidence.
- Missing dependencies may be reported as an environment limitation; do not install or download them without the required explicit authorization.
- Before a completion claim, run the fresh checks selected by the verification matrix and verify the exact commit/build/runtime identities involved.

## Candidate, Cutover and Cleanup

- Runtime/API/data/client changes should pass an isolated Candidate before production cutover when feasible. Record commit/build identity, database identity, smoke results and rollback.
- Keep async backfill/sync disabled unless the task explicitly requires it.
- Production cutover and destructive retirement are distinct gates. A successful Candidate never authorizes deletion.
- Local cleanup must use the commit-bound, per-file SHA inventory and must have zero `review` and zero retained callers.
- Cloud cleanup must use an exact manifest, protect the new database/services/current SimC runtime, and prove zero connections plus zero live configuration references for every retired database or service.
- No destructive cleanup may run before independent restore verification, capacity readiness, real Mini/Web acceptance, first-new-write reconciliation and a stable production-health window.
- Git history is the archive for deleted legacy code and documents; recovery-critical production data requires an independent restore-verified backup.

## Remote Operations

- Routine project-remote synchronization and known-server inspection/deployment operations follow the repository's existing approval boundaries. Inspect local status first and preserve unrelated changes.
- Stop for force pushes, history rewrites, new dependencies, arbitrary third-party downloads, remote conflicts, changed providers/repos, or any operation outside the current authorization.
- Keep secrets out of logs, files and evidence. Inspect only whether required credentials are configured; never print their values.

## Roadmap and Closure

- Use status labels consistently: `已完成`, `正在推进`, `下一步`, `后续`, `暂缓`, `待决策`.
- When the user confirms a product decision, update the roadmap system in the same turn whenever practical.
- A mid-flow “OK” authorizes continuation, not manual acceptance. Closure requires an explicit post-test acceptance such as “我已测试通过”, “可以收尾” or “合入吧”.
- After accepted closure, run final review and verification, integrate without history rewrite, push `main`, verify local/remote/deployed parity, refresh the WeChat preview when applicable, and remove the finished task worktree/branch only after safety checks.
