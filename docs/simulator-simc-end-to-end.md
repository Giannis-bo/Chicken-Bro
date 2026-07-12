# SimC End-to-End Flow

## Goal

Keep the simulator SimC path deterministic and evidence-bound: the mini program can still accept a raw prompt/profile, but the current core path is saved talent + gear templates -> backend validation -> queued SimC task -> task list/detail read model.

## Current Flow

1. `pages/simulator/simulator` is the 智能分析 tab and now renders the 炸鸡队长 chat surface directly through `pages/simulator/chickenbro-chat.js`. It no longer asks the player to choose SimC / WCL / Chickenbro cards first.
2. `GET /api/simulator/home` remains a compatibility payload for backend smoke and older clients, but it is not the current mini-program first screen.
3. `pages/simulator/chickenbro` is an independent route that uses the same shared chat controller as the tab entry.
4. `pages/simulator/simc` is still the SimC submission path, but the player-facing entry is now from `pages/builds/builds` quick action `simc`, saved templates, or direct navigation during development.
5. The SimC page posts to `POST /api/simulator/analyze` with:

```json
{
  "mode": "simcraft",
  "prompt": "帮我跑一下冰法单体 5 分钟，并解释属性收益\n```simc\nmage=\"冰法样例\"\ntalents=CAE\ngear_ilvl=700\n```",
  "runSimulation": true
}
```

6. The backend extracts the fenced `simc` or `simulationcraft` code block.
7. If a profile is present, the backend runs `WOW_SIMC_BIN` or a `simc`/`simulationcraft` binary on `PATH`.
8. The legacy raw-profile response includes the normalized request, execution stages, simulation status, parsed DPS metric, reference data, allowed-number guardrails, and concise Chinese recommendations. The template path described below does not use LLM/Codex interpretation for final task execution.

Task history uses `GET /api/simulator/tasks?guest=1` and `GET /api/simulator/task?id=...&guest=1`. Authenticated requests use Bearer token; guest mode is explicit and scoped by guest id.

## Legacy SimC Agent Flow

`mode=simcraft_agent` remains a supported backend mode for legacy or direct SimC routes. It is no longer the 智能分析 tab's primary first screen. This mode treats the textarea as a conversation entry instead of a raw profile-only form:

```json
{
  "mode": "simcraft_agent",
  "message": "我是冰法，想跑单体 5 分钟并解释属性收益\n```simc\nmage=\"冰法样例\"\ntalents=CAE\ngear_ilvl=700\n```",
  "round": 1,
  "runSimulation": true
}
```

Agent behavior:

- Natural-language-only requests identify intent, infer class/spec/item level/scenario when possible, and ask for the smallest missing playable slot.
- Clarification is no longer hard-capped at three rounds. The agent keeps asking for the smallest missing playable slot until it can produce a validated SimC template.
- Off-topic requests such as代打、卡 bug、外挂、无关代码或剧情问题 return `agent.status=off_topic` and refocus the player on SimC simulation.
- When the request includes a known class/spec, the backend can generate a minimal executable SimC template for all 13 classes and 40 specializations, including `demonhunter/devourer` (`噬灭`), without per-spec special-case logic.
- A fenced `/simc` export is converted into an executable template by appending controlled backend defaults such as `iterations`, `fight_style`, `desired_targets`, `max_time`, and scale-factor settings when the player asks for stat weights.
- Mythic+ multi-target scenarios attach a WoW.gg Midnight Week 12 reference before the final report. DPS and tank specs use Avg DPS / Max DPS / Max Key; healer specs also include Avg HPS / Max HPS so the report does not judge healers by DPS alone.
- Codex Worker is skipped until a validated executable template exists. The main path remains deterministic validation, server-side SimC execution, and optional LLM interpretation.

## Builds-to-SimC Linkage

The 职业专精 tab is now a first-class SimC entry point. The current `pages/builds/builds` quick action `simc` navigates to `/pages/simulator/simc?from=builds`, and `tasks` navigates to `/pages/simulator/tasks?from=builds`. Older detail-page `buildContext` imports may still fill class/spec/talent context when present, but the current player-facing stable path is saved talent + gear templates -> SimC confirmation -> queued task -> task list/detail.

Backend rules:

- `buildContext` can fill class/spec when the player did not type them again in chat.
- A talent import code from `buildContext.details.talents.importCode` is allowed to become `talents=<code>` in the generated SimC template.
- Gear rows from `buildContext.details.gear.gear` remain comparison context only. They are not converted into SimC `gear_*` lines unless the system later has item id, bonus id, enchant, gem, and current-character export data.
- WebSim submissions must carry a canonical `profileSource=websim` profile only after server-side talent encoding succeeds and every core SimC gear slot except optional `off_hand` is SimC-ready.
- `/api/websim/profile`, `/api/websim/simulate`, the saved task request, and the profile piped into `simc` must remain byte-for-byte consistent after normalization; otherwise the route is not considered a trustworthy WebSim-to-SimC path.
- The LLM prompt must label gear rows as candidates and preserve source evidence, so the report explains what can be compared now and what still requires a character export.
- Saved task detail pages intentionally hide the full generated SimC template and raw SimC output.

## Template Task Flow

`mode=simcraft_template` is the current player-facing path for saved talent/gear templates. It has two different phases:

1. Confirmation uses `confirmOnly=true`. The backend parses the selected talent template, parses or replays the structured gear template, validates class/spec/race/scenario, builds a deterministic draft profile, and returns `simcReport.schemaRevision=simc-report-v2`. Confirmation must not run SimC, call LLM, or call Codex Worker.
2. Final submit uses `confirmOnly=false` and `saveTask=true`. The backend repeats validation, creates or reuses a queued `simulator_tasks` row, stores `request_json`, `analysis_json`, and `summary_json`, returns `taskId`, and starts the background runner when `WOW_SIMC_TEMPLATE_TASK_AUTORUN` allows it.
3. The runner owns the state transition `queued -> running -> completed/failed`. It pipes the stored normalized profile to `simc`, parses DPS only from SimC output, records `taskTiming`, updates `analysis_json`, regenerates `summary_json`, and never calls LLM/Codex.
4. Duplicate active submits are deduped by `simcTaskFingerprint`, which includes user/template/class/spec/race/scenario/analysis-type inputs. If the same task is already `queued` or `running`, the API returns the active task lock instead of inserting another row.

The player-facing scenario contract is intentionally small:

- `single`: `fight_style=Patchwerk`, `desired_targets=1`, `max_time=300`.
- `aoe_5`: `fight_style=Patchwerk`, `desired_targets=5`, `max_time=300`.
- `mythic_plus`: `fight_style=DungeonSlice`, `desired_targets=5`, `max_time=360`; this is a SimC dungeon approximation, not a real route or a stable 5-target AOE target dummy.

Do not label `DungeonSlice` as `AOE5目标`. Only `aoe_5` may use that label. Real Mythic+ reference windows may attach to `mythic_plus`; they must not attach to the 5-target target-dummy scenario.

Generated template/WebSim profiles also carry a combat-preparation contract:

- Generated profiles must set `optimal_raid=0` before adding explicit preparation lines. This prevents SimC's generic raid preset from silently granting cross-class buffs.
- Self-class raid buffs are on by default only for the profile's own class and only when the SimC override token is verified, such as `override.arcane_intellect=1` for mage and `override.skyfury=1` for shaman. A priest profile must not receive mage/shaman buffs.
- Spec/class preparations such as Enhancement shaman weapon imbues and rogue poisons require their own class/spec evidence chain. A token found in the production SimC binary is not enough; the exact generated profile must pass an executable smoke before the line is marked `verified` and allowed to affect trusted DPS copy.
- Generic temporary effects such as weapon oil, combat potion, and Bloodlust/Heroism are off by default and must stay behind explicit user-facing toggles.
- `simcReport.preparation` is the player-facing read model for this policy. Task submit, task list, and task detail should show the preparation summary/evidence state without exposing raw profile text.

The durable payload split is:

- `request_json`: normalized executable request, including slim template context, `simcTaskFingerprint`, scenario, race, and the generated profile needed by the runner.
- `analysis_json`: execution state and public `simcReport`; detail reads this after stripping profile/raw output/debug fields.
- `summary_json`: compact task-list read model only. It contains state, title, build tags, scenario, DPS display for data compatibility, timing, and update time. The frontend task card intentionally does not display DPS or old benchmark copy.

`summary_json` is added by migration marker `simulator_task_summary_v1`. Empty or legacy rows are backfilled by `backfill_simulator_task_summaries`; list reads still merge with a generated fallback from `request_json`/`analysis_json` so older tasks can recover race/class/spec/hero/scenario tags.

## Task List Contract

`GET /api/simulator/tasks` returns task rows scoped to the authenticated user or explicit guest id. For `simcraft_template` rows, consumers should read `task.simcReportSummary` instead of parsing full `analysis`.

Frontend display rules in `pages/simulator/tasks.*`:

- Title format is `专精职业_YYYY-MM-DD HH:mm`, for example `元素萨满祭司_2026-06-27 11:23`.
- Status text is localized: `queued/running -> 进行中`, `completed -> 已完成`, `failed -> 失败`, `blocked -> 已阻断`; colors are orange/yellow for active, green for completed, red for failed, and purple for blocked.
- Tags are value-only chips from summary build/scenario: race, class, spec, hero talent, and scenario. Do not render labels such as `种族：` or placeholder text such as `待补`.
- Completion time is always shown as `完成时间：YYYY-MM-DD HH:mm` or `完成时间：未完成`.
- Task cards must not show `SimC completed with xxx DPS` or `大秘境基准 xxx DPS`; those belong to detail/result views only when explicitly needed.

## Task Detail Contract

`GET /api/simulator/task?id=...` returns one task after owner/guest checks. For `simcraft_template` tasks, public detail must be stripped before it reaches the mini program:

- Remove full `profile`, `draftProfile`, raw SimC stdout, `llm`, `codex`, `allowedNumbers`, and `guestId`.
- Rebuild or normalize `simcReport` as `simc-report-v2`, then preserve any existing verified `simcReport.build.statSnapshot`.
- Keep only player-facing result data: hero title, status, concise summary, DPS result if the final SimC run produced one, scenario display, and verified stat rows.
- Do not render legacy AI report sections such as player question, build-context dump, report explanation, next actions, evidence lists, execution stages, generated SimC template, or raw SimC summary.

Generated preview DPS remains hidden in detail. A generated template may prove that the profile shape is valid, but only a final SimC run with parsed DPS can display a DPS result.

## Stat Snapshot Contract

The current task detail can show the simulated character attributes only when a verified compact snapshot is available. The snapshot shape is `statStatus=verified`, one primary metric, and the secondary metrics `crit/haste/mastery/versatility` with display values and percentages when available.

The active confirmation flow uses the `POST /api/websim/gear/stat-snapshots` async stat-snapshot API. The Builds and SimC pages submit canonical `selectionIntent + profileContext`, poll a pending request within fixed attempt/time limits, and only accept a verified result whose signature still matches the current class/spec/race/scenario/talents/gear context. A changed signature makes the old snapshot stale/read-only and prevents an old completion from replacing the new request.

Profile readiness and stat execution outcome are separate contracts. `profileReadiness=ready` means the canonical resolver and profile serializer authorize Worker execution; it does not promise a verified stat payload. Execution must end either with an immutable verified snapshot or an explicit fail-closed problem/blocker with no fabricated snapshot. The accepted Phase 5D closure matrix is 32 verified outcomes plus 8 explicit fail-closed outcomes.

Snapshot sources, in priority order:

1. `simcReport.build.statSnapshot` already stored in `analysis_json`.
2. Verified `statSnapshot` carried by the submitted gear template metadata.
3. A detail-time backfill from stored `gearSnapshot + talent rawString + class/spec/race/scenario`, using `build_websim_gear_stats_response`, written back into `analysis_json`.

Frontend `pages/simulator/simc.js` only sends a cached `metadata.statSnapshot` when its request signature still matches the selected class/spec/race/scenario/talents/gear context. Stale snapshots must be omitted. The backend detail backfill is deliberately detail-only; list reads should not run stat calculations. The legacy synchronous `/api/websim/gear/stats` route remains compatibility-only and is not the active frontend refresh path.

Old tasks cannot always recover attributes. If neither a verified snapshot nor enough stored `gearSnapshot`/talent context exists, the detail page should simply omit stat rows instead of showing `待补` placeholders.

Legacy `simcraft_agent` responses and template confirmation responses may add an `agent` object. Older examples look like:

```json
{
  "agent": {
    "status": "simc_completed",
    "round": 2,
    "intent": "stat_weights",
    "missingSlots": [],
    "question": "",
    "quickReplies": [],
    "draftProfile": "mage=\"冰法样例\"\n...",
    "validation": {
      "passed": true,
      "errors": [],
      "warnings": []
    },
    "summaryCards": [
      {
        "title": "结论",
        "text": "本次 SimC 已跑通，当前模板约为 123456 DPS。"
      }
    ]
  }
}
```

Player-facing task details should lead with the simplified SimC result and run context. The current saved detail page intentionally does not render recommendations, Mythic+ benchmark text, execution stages, the full generated SimC template, or raw SimC summary.

## WCL And Chickenbro Entries

`pages/simulator/wcl` remains a WCL input surface in code, but it is not registered in `app.json` and is not part of the current 智能分析 first screen. The backend parses report URL/code/fight and blocks deterministically when the report is missing or credentials are unavailable. Without `WOW_WARCRAFTLOGS_CLIENT_ID` / `WOW_WARCRAFTLOGS_CLIENT_SECRET` or another supported WCL credential, the system must not call LLM to fabricate log conclusions.

`pages/simulator/simulator` and `pages/simulator/chickenbro` are the current 炸鸡队长 chat entries. Both use `pages/simulator/chickenbro-chat.js`, post to `POST /api/chickenbro/messages`, and can read `GET /api/chickenbro/sessions`, `GET /api/chickenbro/jobs`, and `GET /api/chickenbro/profiles`.

Chickenbro rules:

- Frontend sends a short message plus bounded context such as `productPhase`, `region`, `classKey`, `specKey`, and `scenarioKey`; it does not send raw DB access, API keys, full logs, or complete SimC profiles to an LLM.
- Backend stores lightweight sessions/messages/jobs, builds a bounded context, validates topic scope and allowed numbers, then either runs the configured Codex runner or returns deterministic fallback.
- `WOW_CHICKENBRO_CODEX_ENABLED=1` enables the Codex runner. Without a published profile, the backend may use direct Codex chat mode for in-scope WoW questions so the player can test the conversation feel, but the answer must not present general model knowledge as local evidence.
- `published` spec profiles may support conclusions; `partial` profiles are background only; `stale` / `blocked` / `needs_review` profiles do not enter the conclusion chain.
- Codex output must pass `validate_chickenbro_codex_output`. Schema failure, unknown evidence refs, unapproved numbers, timeout, or missing runner falls back to deterministic response.
- The frontend fallback explicitly says the backend is unavailable and must not substitute fake coaching conclusions.

## Response Shape

```json
{
  "mode": "simcraft",
  "status": "ready",
  "request": {
    "prompt": "...",
    "profileSource": "prompt",
    "runSimulation": true
  },
  "stages": [
    {
      "key": "profile_check",
      "title": "Profile 检查",
      "status": "passed",
      "executor": "backend",
      "summary": "已识别 prompt SimCraft profile"
    },
    {
      "key": "simc_execution",
      "title": "SimC 执行",
      "status": "completed",
      "executor": "simcraft",
      "summary": "SimC 已执行成功，DPS 123456",
      "metric": "123456"
    },
    {
      "key": "mythic_plus_reference",
      "title": "真实大秘境对标",
      "status": "completed",
      "executor": "backend",
      "summary": "武器战士：Avg DPS 184K，Max DPS 298K，来源 WoW.gg Mythic+ DPS Tier List",
      "metric": "184K"
    },
    {
      "key": "ai_interpretation",
      "title": "AI 解读",
      "status": "completed",
      "executor": "llm",
      "summary": "已基于真实执行状态生成建议"
    }
  ],
  "simulation": {
    "ran": true,
    "available": true,
    "summary": "DPS Ranking: ...",
    "metrics": {
      "dps": "123456"
    }
  },
  "mythicPlusReference": {
    "specKey": "warrior-arms",
    "specName": "武器战士",
    "avgDps": "184K",
    "maxDps": "298K",
    "maxKey": "+24",
    "comparisonText": "Avg DPS 184K，Max DPS 298K"
  },
  "recommendations": [
    "本次 SimC 已跑通，当前 profile 约为 123456 DPS；先把这个作为基准，再比较装备或天赋变体。"
  ]
}
```

## First-Phase Boundaries

- Natural-language-only prompts can generate a minimal template once the class/spec is known.
- Natural-language-only prompts with missing specialization return `profile_check=blocked`, `simc_execution=skipped`, and `agent.status=needs_clarification`.
- The highest-fidelity prompt format remains natural language plus a fenced SimC profile, because exported talents and gear are more accurate than generated defaults.
- LLM output is optional. The deterministic SimC result and heuristic recommendation path must still return a useful conclusion when LLM credentials are absent.
- Codex Worker remains optional and bounded for legacy/adjacent flows. The `simcraft_template` final submit path is backend validation, queued task execution, and deterministic public `simcReport`; it must not call LLM or Codex Worker.
- The mini program does not hold OpenAI, Codex, or SimC credentials. All execution stays behind the backend.

## SimC Conclusion Correctness Standard

Passing tests is not sufficient unless the tests assert the semantic correctness of the player-facing SimC conclusion. Any change that touches SimC profile generation, DPS parsing, report wording, task detail rendering, or Mythic+ reference comparison must preserve these rules:

- DPS always means raw damage per second. Do not imply `K`, `万`, or any scaled unit unless the value explicitly comes from a reference source that already labels it that way.
- A `prompt` or `explicit` profile may be described as a runnable SimC result only when `simulation.ran=true` and `simulation.metrics.dps` was parsed from a final DPS line such as `DPS=` or `DPS Ranking`.
- A `generated` profile is only a template execution check. It must use `simulation.quality=preview`, `metricLabel=模板试跑 DPS`, and `metricUnit=伤害/秒`; player-facing copy must not call it a real-character baseline, qualified DPS, or gearing conclusion.
- Real Mythic+ reference values such as `168K` or `250K` must stay visually and semantically separate from SimC raw DPS. Reports must not compare a generated-template DPS value as if it were the same evidence type as real log data.
- Completed SimC results should include a backend benchmark status when an external reference window is attached: `reasonable`, `outlier_high`, `outlier_low`, or `unverified`. Outliers must tell the player to re-check profile, gear completeness, scenario, item level, and SimC version before trusting the number.
- SimC failure, timeout, missing profile, or missing final DPS must never produce a simulated DPS claim. The report should state the backend reason and fall back to verified reference data or ask for a complete `/simc` export.
- LLM output is not trusted for numeric truth. Backend guards and tests must reject unsupported million-scale claims, progress numbers, timestamps, iteration counts, report IDs, and any number not parsed from final SimC DPS output or trusted reference data.

Required test coverage for future SimC changes:

- Backend tests in `tests/news_backend_test.py` must cover DPS parsing from full SimC output before summary truncation, rejecting unrelated large numbers, generated-profile preview labeling, SimC failure wording, and Mythic+ reference guardrails.
- Backend tests must also cover `simcraft_template` confirm-only behavior, queued final submit, active task lock reuse, runner success/failure state transitions, `summary_json` backfill, and task-detail stat snapshot backfill.
- Backend and WebSim tests must cover combat-preparation profile policy: `optimal_raid=0`, own-class raid buff only, no cross-class raid buffs, partial/pending state for class/spec preparations without executable SimC smoke evidence, and public `simcReport.preparation` copy.
- WebSim tests in `tests/websim_payload_test.py` must cover canonical profile reuse, full core gear gating, talent encoding failures, candidate gear blocking, and fake-SimC capture of the exact submitted profile.
- Frontend tests in `tests/simulator-page.test.js` must cover the visible task-list title/status/tag/completion-time contract, removal of card DPS/benchmark copy, and task-detail labels, units, stat rows, and generated-preview hiding.
- A deployable SimC change must pass `python3 -m unittest discover -s tests -p '*_test.py'`, `node --test tests/*.test.js`, local `python3 server/simulator_e2e_smoke.py`, and after deployment the live smoke command below.

## Verification

Local verification:

```bash
python3 -m unittest discover -s tests -p '*_test.py'
node --test tests/*.test.js
python3 server/simulator_e2e_smoke.py
python3 server/simulator_e2e_smoke.py --base-url http://124.223.51.33 --timeout 90
```

Focused checks for this path:

```bash
python -m unittest tests.news_backend_test
node --test tests/simulator-page.test.js tests/frontend-api-client.test.js
git diff --check
```

Simulated prompts already covered:

- Ice mage baseline profile returns `123456` DPS in the fake SimC test.
- Route-level fake SimC call returns `130001` DPS through `POST /api/simulator/analyze`.
- Local HTTP smoke script returns `140002` DPS through a temporary backend server.
- Lighthouse smoke script returned `simulation.ran=true` and observed a real SimC `DPS=119.357...` from `http://124.223.51.33`.
- A fenced profile followed by extra Chinese explanation stops extraction at the closing code fence.
- All 39 class/spec combinations generate a validated minimal template and attach a real WoW.gg Mythic+ reference for multi-target scenarios.
- Completed reports keep recommendations and summary cards to three items or fewer.

Online verification after deployment:

1. Deploy backend to Lighthouse.
2. Confirm `systemctl status wow-backend` is healthy.
3. Confirm `/opt/wow-simc/current/simc` exists and is executable.
4. Run:

```bash
python3 server/simulator_e2e_smoke.py --base-url http://124.223.51.33 --timeout 90
```

5. Confirm `simulation.ran` is `true`, `simulation.metrics.dps` is present, and the mini program renders the summary.
