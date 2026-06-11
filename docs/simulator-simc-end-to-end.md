# SimC End-to-End Flow

## Goal

Make the simulator tab prove the first usable path: the mini program accepts a prompt, the backend extracts a SimCraft profile, runs server-side `simc`, and returns a readable result.

## Current Flow

1. The simulator page renders a `SimC 输入` textarea and a `提交模拟` button.
2. The page posts to `POST /api/simulator/analyze` with:

```json
{
  "mode": "simcraft",
  "prompt": "帮我跑一下冰法单体 5 分钟，并解释属性收益\n```simc\nmage=\"冰法样例\"\ntalents=CAE\ngear_ilvl=700\n```",
  "runSimulation": true
}
```

3. The backend extracts the fenced `simc` or `simulationcraft` code block.
4. If a profile is present, the backend runs `WOW_SIMC_BIN` or a `simc`/`simulationcraft` binary on `PATH`.
5. The response includes the normalized request, execution stages, simulation status, parsed DPS metric, real Mythic+ reference data, and concise Chinese recommendations.

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
- Codex Worker remains an optional asynchronous reviewer. The main request path is backend validation, then SimC execution, then LLM interpretation.
- The mini program does not hold OpenAI, Codex, or SimC credentials. All execution stays behind the backend.

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
