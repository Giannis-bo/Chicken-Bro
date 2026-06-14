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

## Scope Boundaries

- The roadmap is the long-lived product and engineering control plane. It does not replace detailed task plans.
- Concrete implementation plans may still live in `docs/plans/`.
- Product direction, data trust rules, SimC/WebSim contracts, release readiness, and personal-workspace ideas should all be routed through the roadmap system.
