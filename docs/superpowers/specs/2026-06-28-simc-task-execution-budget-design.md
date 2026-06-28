# SimC Task Execution Budget Design

## Goal

Keep SimC task results meaningful by preserving the existing scenario inputs and `iterations`, while preventing repeated timeout failures and limiting each player to at most two active template simulations.

## Decisions

- Do not reduce `iterations`, `fight_style`, `desired_targets`, or `max_time` for the single-target, 5-target AOE, or approximate Mythic+ scenarios.
- Treat `queued` and `running` `simcraft_template` tasks as active tasks.
- Allow at most two active template tasks for the same player.
- Reuse an existing active task when the same player submits the same fingerprint again.
- Block a third different active template task with a structured `taskLock.reason = "active_simc_task_limit"` response.
- Use template-specific SimC execution timeouts instead of the global 45 second timeout.
- Block known upstream SimC crash combinations before launching SimC. Current known blocker: `deathknight/unholy` + `rider_of_the_apocalypse`.

## Components

- `server/news_backend.py` owns queue admission, active task counting, and the structured task lock response.
- `server/postgres_personal_store.py` already exposes active rows for the PostgreSQL runtime path and will continue to be used by the backend admission check.
- `server/simulator_payload.py` owns SimC profile construction and process execution. It will pass a template timeout to the process layer without changing the generated profile.
- `server/websim_payload.py` owns gear-stat snapshot execution and known SimC compatibility blockers shared by preflight and template confirmation.
- `pages/simulator/simc.js` will check active task count through the existing task list endpoint before submit and block the button when the player already has two active tasks.
- `pages/simulator/simc.wxml` will show the submit button state clearly.

## Testing

- Backend tests cover third-task rejection, same-fingerprint reuse, and template timeout propagation while preserving profile inputs.
- Backend tests cover the known Unholy Death Knight + Rider of the Apocalypse upstream SimC crash blocker without launching SimC.
- Frontend tests cover active-task counting, submit button blocking, and backend lock response handling.
