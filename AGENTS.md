# Repository Agent Guidelines

This repository maintains a project roadmap as shared context for all agents and development environments. Every agent working in this repo should follow these rules before planning or changing product direction.

## Roadmap First

- Read [docs/roadmap.md](docs/roadmap.md) before making product, UX, data, backend, simulator, WebSim, deployment, or prioritization decisions.
- Use [docs/roadmap/ideas.md](docs/roadmap/ideas.md) as the intake pool for loose ideas, local discussion outcomes, and directions that are not yet committed to a milestone.
- Keep existing execution plans under [docs/plans/](docs/plans/) as historical implementation evidence. Do not rewrite them just to match the current roadmap.

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
- Treat older plan documents as historical implementation evidence; current review practice is defined by this section and the active task scope.
- `codex review` is optional second-opinion review only. Do not treat it as a required gate. If it is unavailable, slow, times out, hangs, or fails due to CLI argument/config/auth/environment issues, record that fact briefly and continue with local CR plus targeted tests.
- When reviewing uncommitted work, use `codex review --uncommitted` only. When reviewing committed branch changes against a base branch, use `codex review --base <base>` only. Do not combine `--uncommitted` with `--base`.
- Do not block commit, deploy, or handoff solely because `codex review` failed or did not return. Blocking decisions should come from local CR findings, failing tests, unsafe diff state, or unresolved user/product requirements.

## Cloud Deployment Approval

- For this repository, routine operations on the known cloud server do not require an extra approval prompt once the user asks for deployment, sync, smoke, or remote verification work.
- Covered operations include SSH inspection, remote backups, applying repository-owned database migrations, copying changed project files to the existing deployment directory, restarting existing services, checking logs, and HTTP smoke tests.
- Server-side SimulationCraft runtime updates on the known cloud server are also covered once the user asks for SimC update, SimC sync, WebSim/SimC readiness repair, deployment, cutover-readiness work, or authorizes the health follow-up automation for SimC. Covered SimC operations include downloading the configured SimulationCraft source archive from the configured repo/branch, building it under `/opt/wow-simc`, atomically switching `/opt/wow-simc/current`, updating `/opt/wow-simc/.commit` and version state, restarting or triggering existing project services, and running SimC/API smoke checks. `wow-data-health-followup.timer` may automatically trigger the configured `wow-simc-runtime-update.service` when `/api/data/health` reports the configured SimC runtime has `updateAvailable=true`.
- This does not turn local downloads, arbitrary third-party downloads, dependency installation, repository cloning/pulling, remote git push/pull, or changing `SIMC_GITHUB_REPO` / `SIMC_BRANCH` into implicit actions; those still follow the Network / Download Approval rule unless the user explicitly includes them in the current request.

## Scope Boundaries

- The roadmap is the long-lived product and engineering control plane. It does not replace detailed task plans.
- Concrete implementation plans may still live in `docs/plans/`.
- Product direction, data trust rules, SimC/WebSim contracts, release readiness, and personal-workspace ideas should all be routed through the roadmap system.
- For already implemented features, current code and live verification take precedence over stale wording in older docs; update README and architecture docs to match the shipped behavior, while treating old plans as historical evidence unless the user explicitly asks to rewrite them.
