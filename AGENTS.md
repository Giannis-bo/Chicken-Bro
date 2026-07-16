# Repository Agent Guidelines

This repository maintains a project roadmap as shared context for all agents and development environments. Every agent working in this repo should follow these rules before planning or changing product direction.

## Roadmap First

- Read [docs/roadmap.md](docs/roadmap.md) before making product, UX, data, backend, simulator, WebSim, deployment, or prioritization decisions.
- For frontend work, read [docs/plans/2026-07-14-target-first-14-route-rebuild.md](docs/plans/2026-07-14-target-first-14-route-rebuild.md), [DESIGN.md](DESIGN.md), and [docs/design/current-ui/README.md](docs/design/current-ui/README.md) after the roadmap. These are the only active UI execution authorities.
- Do not scan `docs/plans/` by date or treat directory presence as authority. [docs/plans/README.md](docs/plans/README.md) is the explicit plan whitelist; a domain plan may be read only when a current architecture or runbook links to that exact file.
- Only files reachable from the current roadmap, plan whitelist, design contract, current UI control plane, or a stable architecture/runbook may influence implementation. Git history and unlinked files are not execution context.
- Keep the existing Taro workspace, typed data/API layers, route behavior, build tooling, and the 14 files listed in `docs/design/current-ui/target-registry.json`. Source components and runtime utility assets are implementation inputs, not visual evidence.
- Target geometry must come from an isolated target-only measurement. Runtime output, existing CSS, old review reports, component dimensions, and prior redlines may not write or adjust target bounds.
- Pass `news_home` first, then the other two baselines and the remaining eleven routes. Fix shared rendering contracts in shared owners and do not add route-private visual patches for shared defects.
- Use [docs/roadmap/ideas.md](docs/roadmap/ideas.md) as the intake pool for loose ideas, local discussion outcomes, and directions that are not yet committed to a milestone.
- Delete superseded frontend execution documents and evidence from the working tree. Git history is the archive.
- Do not append execution timelines to `docs/roadmap.md`. Keep it short enough to be read as control context; attach current evidence through stable architecture/runbook/source links.

## Capturing Confirmed Ideas

- When the user clearly confirms an idea with “OK”, “认可”, “就按这个”, or an equivalent approval, update the roadmap system in the same turn whenever practical.
- If the idea is still exploratory, add it to `docs/roadmap/ideas.md` with source, problem, benefit, risk/question, suggested milestone, and status.
- If the idea is already decision-ready and belongs to an active direction, update `docs/roadmap.md` with the milestone, user value, key actions, completion criteria, and evidence links.
- If it is not practical to edit docs in the current turn, explicitly remind the user that the idea should be captured in the roadmap.

## Status Discipline

- Use the roadmap status labels consistently: `已完成`, `正在推进`, `下一步`, `后续`, `暂缓`, `待决策`.
- Do not invent undocumented historical decisions. If an idea cannot be verified from the repo, current conversation, or user confirmation, mark it as `待补录` or `待确认` in `docs/roadmap/ideas.md`.
- When work completes, update status and evidence links instead of rewriting old plan documents.

## Review Workflow

- Use local CR as the primary pre-merge review path. Inspect the diff directly, read relevant project docs/context, run targeted verification with local tests, smoke checks, or runtime logs as appropriate, and report findings with file/line references.
- Before commit, push, deployment, or handoff, review the diff against the roadmap and current plan boundaries, fix technically valid findings, and re-run the relevant verification.
- Review only against the current roadmap, active plan, route contracts, source diff, tests, and fresh evidence.
- `codex review` is optional second-opinion review only. Do not treat it as a required gate. If it is unavailable, slow, times out, hangs, or fails due to CLI argument/config/auth/environment issues, record that fact briefly and continue with local CR plus targeted tests.
- When reviewing uncommitted work, use `codex review --uncommitted` only. When reviewing committed branch changes against a base branch, use `codex review --base <base>` only. Do not combine `--uncommitted` with `--base`.
- Do not block commit, deploy, or handoff solely because `codex review` failed or did not return. Blocking decisions should come from local CR findings, failing tests, unsafe diff state, or unresolved user/product requirements.

## Imagegen Asset Handling Guard

- Imagegen and image-based design work are allowed. The guard prevents large image payloads from entering the long-lived main project session; it does not replace visual review with text-only guessing.
- Do not load generated/reference PNG payloads into the main session with `view_image`, raw reads, base64, data URLs, Markdown embeds, or serialized image-tool/thread outputs.
- Never inspect an imagegen task with thread/history readers such as `read_thread`, even with output inclusion disabled: completed image-generation records may still serialize the full PNG payload. Observe completion only through agent status plus filesystem path, mtime, byte-size, and hash metadata.
- Run generation and visual review in disposable isolated contexts. Review one route target, or one target/runtime pair, at a time and return only whitelisted paths, metadata, structured differences, and status.
- Target and runtime metadata may be checked by filesystem tools, but visual payloads remain confined to disposable contexts.
- Image generation alone never proves design lock, component fidelity, runtime acceptance, or release readiness.

## Cloud Deployment Approval

- For this repository, routine operations on the known cloud server do not require an extra approval prompt once the user asks for deployment, sync, smoke, or remote verification work.
- Covered operations include SSH inspection, remote backups, applying repository-owned database migrations, copying changed project files to the existing deployment directory, restarting existing services, checking logs, and HTTP smoke tests.
- Server-side SimulationCraft runtime updates on the known cloud server are also covered once the user asks for SimC update, SimC sync, WebSim/SimC readiness repair, deployment, cutover-readiness work, or authorizes the health follow-up automation for SimC. Covered SimC operations include downloading the configured SimulationCraft source archive from the configured repo/branch, building it under `/opt/wow-simc`, atomically switching `/opt/wow-simc/current`, updating `/opt/wow-simc/.commit` and version state, restarting or triggering existing project services, and running SimC/API smoke checks. `wow-data-health-followup.timer` may automatically trigger the configured `wow-simc-runtime-update.service` when `/api/data/health` reports the configured SimC runtime has `updateAvailable=true`.
- This does not turn local downloads, arbitrary third-party downloads, dependency installation, repository cloning/pulling, remote git push/pull, or changing `SIMC_GITHUB_REPO` / `SIMC_BRANCH` into implicit actions; those still follow the Network / Download Approval rule unless the user explicitly includes them in the current request.

## Scope Boundaries

- The roadmap is the long-lived product and engineering control plane. It does not replace detailed task plans.
- Concrete implementation plans may still live in `docs/plans/`.
- Product direction, data trust rules, SimC/WebSim contracts, release readiness, and personal-workspace ideas should all be routed through the roadmap system.
- For implemented features, current code and live verification take precedence over documentation wording. Retain a domain plan only while a current architecture document or runbook links to it.
