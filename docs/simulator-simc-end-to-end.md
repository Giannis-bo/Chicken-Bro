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
5. The response includes the normalized request, a three-step execution path, simulation status, parsed DPS metric, raw summary, and Chinese recommendations.

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

- Natural-language-only requests identify intent, infer a default scenario, and ask for exactly one missing high-impact input.
- Clarification is capped at three rounds. On the third round, missing character data becomes `agent.status=insufficient_data` instead of another open-ended question.
- Off-topic requests such as代打、卡 bug、外挂、无关代码或剧情问题 return `agent.status=off_topic` and refocus the player on SimC simulation.
- A fenced `/simc` export is converted into an executable template by appending controlled backend defaults such as `iterations`, `fight_style`, `desired_targets`, `max_time`, and scale-factor settings when the player asks for stat weights.
- Codex Worker is skipped until a validated executable template exists. The main path remains deterministic validation, server-side SimC execution, and optional LLM interpretation.

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

Player-facing result cards should lead with the simplified conclusion, then show simulation conditions, caveats, execution stages, optional AI text, and the generated SimC template for review.

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
  "recommendations": [
    "本次 SimC 已跑通，当前 profile 约为 123456 DPS；先把这个作为基准，再比较装备或天赋变体。"
  ]
}
```

## First-Phase Boundaries

- Natural-language-only prompts do not invent a profile yet; they return guidance asking for a profile or more character data.
- Natural-language-only prompts return `profile_check=blocked`, `simc_execution=skipped`, and `simulation.error=missing simcraft profile`.
- The first usable prompt format is natural language plus a fenced SimC profile.
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

Online verification after deployment:

1. Deploy backend to Lighthouse.
2. Confirm `systemctl status wow-backend` is healthy.
3. Confirm `/opt/wow-simc/current/simc` exists and is executable.
4. Run:

```bash
python3 server/simulator_e2e_smoke.py --base-url http://124.223.51.33 --timeout 90
```

5. Confirm `simulation.ran` is `true`, `simulation.metrics.dps` is present, and the mini program renders the summary.
