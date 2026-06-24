# SimC End-to-End Flow

## Goal

Make the simulator tab prove the first usable path: the mini program accepts a prompt, the backend extracts a SimCraft profile, runs server-side `simc`, and returns a readable result.

## Current Flow

1. `pages/simulator/simulator` renders the 智能分析 hub from `GET /api/simulator/home`. Current modules are `simc`, `wcl`, `chickenbro`, and `tasks`.
2. `pages/simulator/simc` renders the SimC conversation/submission path.
3. The SimC page posts to `POST /api/simulator/analyze` with:

```json
{
  "mode": "simcraft",
  "prompt": "帮我跑一下冰法单体 5 分钟，并解释属性收益\n```simc\nmage=\"冰法样例\"\ntalents=CAE\ngear_ilvl=700\n```",
  "runSimulation": true
}
```

4. The backend extracts the fenced `simc` or `simulationcraft` code block.
5. If a profile is present, the backend runs `WOW_SIMC_BIN` or a `simc`/`simulationcraft` binary on `PATH`.
6. The response includes the normalized request, execution stages, simulation status, parsed DPS metric, real Mythic+ reference data, allowed-number guardrails, and concise Chinese recommendations.

Task history uses `GET /api/simulator/tasks?guest=1` and `GET /api/simulator/task?id=...&guest=1`. Authenticated requests use Bearer token; guest mode is explicit and scoped by guest id.

## SimC Agent Flow

The simulator tab now uses `mode=simcraft_agent` for the primary player-facing path. This mode treats the textarea as a conversation entry instead of a raw profile-only form:

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
- When the request includes a known class/spec, the backend can generate a minimal executable SimC template for all 13 classes and 39 specializations without per-spec special-case logic.
- A fenced `/simc` export is converted into an executable template by appending controlled backend defaults such as `iterations`, `fight_style`, `desired_targets`, `max_time`, and scale-factor settings when the player asks for stat weights.
- Mythic+ multi-target scenarios attach a WoW.gg Midnight Week 12 reference before the final report. DPS and tank specs use Avg DPS / Max DPS / Max Key; healer specs also include Avg HPS / Max HPS so the report does not judge healers by DPS alone.
- Codex Worker is skipped until a validated executable template exists. The main path remains deterministic validation, server-side SimC execution, and optional LLM interpretation.

## Builds-to-SimC Linkage

The 职业专精 detail page is now a first-class SimC entry point. When a player taps `带当前构筑去 SimC`, the mini program stores a compact `buildContext` locally and navigates to `/pages/simulator/simc?from=builds`. The SimC page reads that context, shows the imported source, and automatically sends a confirmation prompt with the current specialization, active query, talent import code, gear candidates, stat trend, source name, publication date, and analysis window.

Backend rules:

- `buildContext` can fill class/spec when the player did not type them again in chat.
- A talent import code from `buildContext.details.talents.importCode` is allowed to become `talents=<code>` in the generated SimC template.
- Gear rows from `buildContext.details.gear.gear` remain comparison context only. They are not converted into SimC `gear_*` lines unless the system later has item id, bonus id, enchant, gem, and current-character export data.
- WebSim submissions must carry a canonical `profileSource=websim` profile only after server-side talent encoding succeeds and every core SimC gear slot except optional `off_hand` is SimC-ready.
- `/api/websim/profile`, `/api/websim/simulate`, the saved task request, and the profile piped into `simc` must remain byte-for-byte consistent after normalization; otherwise the route is not considered a trustworthy WebSim-to-SimC path.
- The LLM prompt must label gear rows as candidates and preserve source evidence, so the report explains what can be compared now and what still requires a character export.
- Saved task detail pages show the build context summary but intentionally hide the full generated SimC template and raw SimC output.

The response adds an `agent` object:

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

Player-facing task details should lead with the simplified conclusion, then show at most three concise recommendations, SimC DPS, real Mythic+ reference data, and execution stages. The saved detail page intentionally does not render the full generated SimC template or raw SimC summary.

## WCL And Chickenbro Entries

`pages/simulator/wcl` is the WCL input surface. The backend parses report URL/code/fight and blocks deterministically when the report is missing or credentials are unavailable. Without `WOW_WARCRAFTLOGS_CLIENT_ID` / `WOW_WARCRAFTLOGS_CLIENT_SECRET` or another supported WCL credential, the system must not call LLM to fabricate log conclusions.

`pages/simulator/chickenbro` is the current 炸鸡队长证据教练 entry. It posts to `POST /api/chickenbro/messages` and can read `GET /api/chickenbro/sessions`, `GET /api/chickenbro/jobs`, and `GET /api/chickenbro/profiles`.

Chickenbro rules:

- Frontend sends a short message plus bounded context such as `productPhase`, `region`, `classKey`, `specKey`, and `scenarioKey`; it does not send raw DB access, API keys, full logs, or complete SimC profiles to an LLM.
- Backend stores lightweight sessions/messages/jobs, builds a bounded context, validates topic scope and allowed numbers, then either runs the configured Codex runner or returns deterministic fallback.
- `published` spec profiles may support conclusions; `partial` profiles are background only; `stale` / `blocked` / `needs_review` profiles do not enter the conclusion chain.
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
- Codex Worker remains optional and bounded. The main SimC request path is backend validation, then SimC execution, then optional LLM interpretation. Chickenbro uses a separate `/api/chickenbro/*` session/job boundary and deterministic fallback.
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
- WebSim tests in `tests/websim_payload_test.py` must cover canonical profile reuse, full core gear gating, talent encoding failures, candidate gear blocking, and fake-SimC capture of the exact submitted profile.
- Frontend tests in `tests/simulator-page.test.js` must cover the visible task-detail labels, units, and copy for generated preview metrics versus full `/simc` results.
- A deployable SimC change must pass `python3 -m unittest discover -s tests -p '*_test.py'`, `node --test tests/*.test.js`, local `python3 server/simulator_e2e_smoke.py`, and after deployment the live smoke command below.

## Verification

Local verification:

```bash
python3 -m unittest discover -s tests -p '*_test.py'
node --test tests/*.test.js
python3 server/simulator_e2e_smoke.py
python3 server/simulator_e2e_smoke.py --base-url http://124.223.51.33 --timeout 90
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
