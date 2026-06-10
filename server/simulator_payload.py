import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

try:
    from .llm_client import call_chat_completion, llm_configured, llm_model
except ImportError:
    from llm_client import call_chat_completion, llm_configured, llm_model

try:
    from .codex_worker import run_codex_job
except ImportError:
    try:
        from codex_worker import run_codex_job
    except ImportError:
        run_codex_job = None


DEFAULT_SIMC_VERSION_FILE = "/var/lib/wow-backend/simc-version.json"
SIMC_AGENT_MAX_ROUNDS = 3
SIMC_AGENT_FORBIDDEN_KEYS = {"html", "json", "output", "save", "xml"}
SIMC_AGENT_OFF_TOPIC_PATTERNS = [
    "代打",
    "卡bug",
    "卡 bug",
    "外挂",
    "脚本刷",
    "写代码",
    "剧情",
]


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def int_env(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def truthy_env(name):
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def simc_binary():
    configured = os.environ.get("WOW_SIMC_BIN")
    if configured:
        return configured if os.path.exists(configured) else ""
    return shutil.which("simc") or shutil.which("simulationcraft") or ""


def simc_version_status():
    path = Path(os.environ.get("WOW_SIMC_VERSION_FILE", DEFAULT_SIMC_VERSION_FILE))
    status = {
        "checkedAt": "",
        "localTag": "",
        "latestTag": "",
        "updateAvailable": False,
        "source": "none",
        "image": "",
    }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return status
    for key in status:
        if key in payload:
            status[key] = payload[key]
    status["updateAvailable"] = bool(status["updateAvailable"])
    return status


def looks_like_simc_profile_line(line):
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False
    if "=" not in stripped:
        return False
    key = stripped.split("=", 1)[0].strip()
    if key in {"talents", "gear_ilvl", "race", "role", "level", "spec", "profile_set"}:
        return True
    if key == "copy" or key.startswith(("gear_", "profileset.")):
        return True
    return key.replace("_", "").replace("-", "").isalnum() and stripped.count('"') >= 2


def extract_fenced_simc_profile(lines):
    in_simc_fence = False
    profile_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            fence_language = stripped[3:].strip().lower()
            if in_simc_fence:
                break
            in_simc_fence = fence_language in {"simc", "simulationcraft"}
            continue
        if in_simc_fence:
            profile_lines.append(line.rstrip())
    return "\n".join(profile_lines).strip()


def extract_simc_profile_from_prompt(prompt):
    lines = str(prompt or "").splitlines()
    fenced_profile = extract_fenced_simc_profile(lines)
    if fenced_profile:
        return fenced_profile

    start_index = -1
    for index, line in enumerate(lines):
        if looks_like_simc_profile_line(line):
            start_index = index
            break
    if start_index < 0:
        return ""

    profile_lines = []
    for line in lines[start_index:]:
        if line.strip().startswith("```"):
            break
        profile_lines.append(line.rstrip())
    return "\n".join(profile_lines).strip()


def normalize_agent_round(value):
    try:
        round_number = int(value)
    except (TypeError, ValueError):
        return 1
    return max(1, min(round_number, SIMC_AGENT_MAX_ROUNDS))


def simc_agent_message(source):
    return str(source.get("message") or source.get("prompt") or source.get("question") or "").strip()


def is_simc_agent_off_topic(text):
    lowered = str(text or "").lower()
    return any(pattern in lowered for pattern in SIMC_AGENT_OFF_TOPIC_PATTERNS)


def infer_simc_agent_intent(text):
    lowered = str(text or "").lower()
    if is_simc_agent_off_topic(lowered):
        return "out_of_scope"
    if any(keyword in lowered for keyword in ["属性", "急速", "精通", "暴击", "全能", "scale", "权重"]):
        return "stat_weights"
    if any(keyword in lowered for keyword in ["饰品", "装备", "武器", "换不换", "配装"]):
        return "gear_compare"
    if "天赋" in lowered:
        return "talent_compare"
    return "baseline"


def infer_simc_agent_scenario(text):
    lowered = str(text or "").lower()
    duration = 300
    duration_match = re.search(r"(\d+)\s*分钟", lowered)
    if duration_match:
        duration = max(60, min(900, int(duration_match.group(1)) * 60))
    if any(keyword in lowered for keyword in ["大秘境", "aoe", "群体", "多目标", "五目标", "5目标"]):
        return {
            "fightStyle": "HecticAddCleave",
            "durationSeconds": duration,
            "targets": 5,
            "label": "大秘境多目标",
        }
    return {
        "fightStyle": "Patchwerk",
        "durationSeconds": duration,
        "targets": 1,
        "label": "单体基准",
    }


def append_simc_option(lines, key, value):
    prefix = f"{key}="
    if any(line.strip().startswith(prefix) for line in lines):
        return
    lines.append(f"{key}={value}")


def build_agent_simc_profile(profile, intent, scenario):
    lines = [line.rstrip() for line in str(profile or "").splitlines() if line.strip()]
    if not lines:
        return ""
    lines.append("")
    append_simc_option(lines, "iterations", int_env("WOW_SIMC_AGENT_ITERATIONS", 10000))
    append_simc_option(lines, "fight_style", scenario["fightStyle"])
    append_simc_option(lines, "desired_targets", scenario["targets"])
    append_simc_option(lines, "max_time", scenario["durationSeconds"])
    append_simc_option(lines, "vary_combat_length", "0.2")
    if intent == "stat_weights":
        append_simc_option(lines, "calculate_scale_factors", "1")
        append_simc_option(lines, "scale_only", "int,crit,haste,mastery,vers")
    return "\n".join(lines).strip()


def validate_agent_simc_profile(profile):
    errors = []
    warnings = []
    text = str(profile or "").strip()
    if not text:
        errors.append("missing character source")
    if len(text) > int_env("WOW_SIMC_AGENT_MAX_PROFILE_CHARS", 12000):
        errors.append("profile too large")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip().lower()
        if key in SIMC_AGENT_FORBIDDEN_KEYS:
            errors.append(f"forbidden simc output option: {key}")
    if text and "talents=" not in text:
        warnings.append("缺少 talents，模拟可信度会下降")
    if text and not any(looks_like_simc_profile_line(line) for line in text.splitlines()):
        errors.append("profile is not a recognizable SimC template")
    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
    }


def build_agent_clarification_question(missing_slots, round_number):
    if round_number >= SIMC_AGENT_MAX_ROUNDS:
        return "信息仍不足，不能执行真实 SimC。请粘贴游戏内 /simc 插件导出，或提供可导入的角色名、服务器和地区。"
    if "character_source" in missing_slots:
        return "要做准确 SimC，需要角色数据来源。请粘贴游戏内 /simc 插件导出，或提供角色名、服务器和地区。"
    return "还差一项关键信息：请说明这次要模拟单体、团本 Boss，还是大秘境多目标。"


def build_agent_quick_replies(missing_slots):
    if "character_source" in missing_slots:
        return ["粘贴 /simc 导出", "提供角色名服务器", "只生成待补齐模板"]
    return ["单体 5 分钟", "大秘境多目标", "比较装备收益"]


def build_agent_summary_cards(request_data, simulation, scenario):
    dps = (simulation.get("metrics") or {}).get("dps", "")
    if simulation.get("ran") and dps:
        conclusion = f"本次 SimC 已跑通，当前模板约为 {dps} DPS。"
    elif simulation.get("ran"):
        conclusion = "本次 SimC 已跑通，但输出摘要中没有解析到 DPS。"
    else:
        conclusion = f"本次没有完成真实 SimC：{simulation.get('error') or '未执行'}。"
    return [
        {"title": "结论", "text": conclusion},
        {
            "title": "模拟条件",
            "text": f"{scenario['label']}，{scenario['durationSeconds']} 秒，{scenario['fightStyle']}。",
        },
        {
            "title": "边界",
            "text": "这个结论只适用于本次模板和场景，不应直接外推到其他装备、天赋或大秘境层数。",
        },
    ]


def skipped_codex_worker_result(error="not executable"):
    return {
        "enabled": truthy_env("WOW_CODEX_SIMULATOR_ENABLED"),
        "called": False,
        "status": "skipped",
        "jobId": "",
        "lastMessage": "",
        "error": error,
    }


def build_simulator_home_payload():
    has_simc = bool(simc_binary())
    has_llm = llm_configured()
    version_status = simc_version_status()
    return {
        "navTitle": "模拟器",
        "kicker": "能力 04",
        "title": "构筑模拟器与 AI 分析",
        "desc": "把 SimCraft、WCL 日志和配装问题统一提交到轻量后端，由后端执行模拟并生成可复核的 AI 分析。",
        "metrics": [
            {"value": "Ready" if has_llm else "Prompt", "label": "LLM"},
            {"value": "Ready" if has_simc else "待安装", "label": "SimCraft"},
            {"value": "WCL", "label": "日志复盘"},
        ],
        "quickActions": [
            {"key": "simcraft", "title": "跑 SimCraft", "desc": "粘贴 profile 后由服务器执行模拟或生成待执行任务。"},
            {"key": "wcl", "title": "分析 WCL", "desc": "提交战斗日志链接，分析循环、爆发和减员问题。"},
            {"key": "gearCompare", "title": "配装对比", "desc": "比较多套装备、饰品、属性收益和升级优先级。"},
            {"key": "llmAdvice", "title": "AI 建议", "desc": "把模拟结果、日志片段和角色目标整理成可执行建议。"},
        ],
        "tasks": [
            {"title": "SimCraft profile 分析", "status": "可提交", "desc": "后端会检测 simc 是否可用，并返回模拟状态、摘要和 AI prompt。"},
            {"title": "WCL 战斗日志分析", "status": "LLM", "desc": "先结构化日志 URL 和问题，再交给 LLM 生成复盘建议。"},
        ],
        "capabilities": {
            "simcraft": has_simc,
            "llm": has_llm,
            "wcl": True,
        },
        "simcraftVersion": version_status,
        "lastCheckedAt": utc_now(),
    }


def normalize_analysis_request(payload):
    source = payload if isinstance(payload, dict) else {}
    prompt = str(source.get("prompt") or "").strip()
    explicit_profile = str(source.get("profile") or "").strip()
    extracted_profile = extract_simc_profile_from_prompt(prompt)
    profile = explicit_profile or extracted_profile
    mode = source.get("mode") or "simcraft"
    run_simulation = bool(source.get("runSimulation"))
    if mode == "simcraft" and run_simulation and not profile:
        run_simulation = False
    if mode == "simcraft" and profile:
        run_simulation = True
    return {
        "mode": mode,
        "character": str(source.get("character") or "").strip(),
        "prompt": prompt,
        "profile": profile,
        "profileSource": "explicit" if explicit_profile else ("prompt" if extracted_profile else "none"),
        "wclUrl": str(source.get("wclUrl") or "").strip(),
        "question": str(source.get("question") or prompt or "").strip(),
        "runSimulation": run_simulation,
    }


def build_llm_prompt(request_data, simulation):
    sections = [
        "你是魔兽世界构筑与日志分析助手，请给玩家可执行、可复核的建议。",
        f"分析模式：{request_data['mode']}",
        f"角色/专精：{request_data['character'] or '未提供'}",
        f"玩家问题：{request_data['question'] or '请给出构筑和输出优化建议'}",
    ]
    if request_data["wclUrl"]:
        sections.append(f"WCL 链接：{request_data['wclUrl']}")
    if request_data["profile"]:
        profile = request_data["profile"][:3000]
        sections.append(f"SimCraft profile 或配装输入：\n{profile}")
    if simulation.get("summary"):
        sections.append(f"SimCraft 执行摘要：\n{simulation['summary']}")
    if simulation.get("error"):
        sections.append(f"SimCraft 执行错误：\n{simulation['error']}")
    if request_data["mode"] in {"simcraft", "simcraft_agent"} and not request_data["profile"]:
        sections.append("缺少 SimCraft profile：本次只可做输入说明和 profile 补全建议，不能声称已经完成 SimC 模拟。")
    sections.append("如果模拟失败或未执行，请直接说明服务器返回的原因，不要把它描述成无法访问本地工具。")
    sections.append("输出格式：先给 3 条优先级最高的结论，再列验证方式和下一步需要补充的数据。")
    return "\n\n".join(sections)


def build_codex_simulator_prompt(request_data, simulation):
    profile = request_data["profile"][:6000] if request_data["profile"] else "未提供"
    summary = simulation.get("summary") or "无"
    error = simulation.get("error") or "无"
    return "\n\n".join([
        "你是 Codex Agent Worker，负责复核魔兽世界 SimCraft 模拟请求。",
        "后端已经先用服务器本地 simc 执行了一次模拟；请基于真实执行状态输出中文复核结论，不要编造 DPS。",
        f"模式：{request_data['mode']}",
        f"问题：{request_data['question'] or '请复核本次 SimC 模拟'}",
        f"SimC 是否运行：{bool(simulation.get('ran'))}",
        f"SimC 错误：{error}",
        f"SimC 输出摘要：\n{summary[:4000]}",
        f"SimC profile：\n{profile}",
        "请输出：1. 是否真实跑通；2. 关键 DPS/属性证据；3. 如果失败，最可能的 profile 问题和下一步修复。",
    ])


def call_codex_worker(request_data, simulation, codex_runner=None):
    enabled = truthy_env("WOW_CODEX_SIMULATOR_ENABLED")
    if not enabled:
        return {
            "enabled": False,
            "called": False,
            "status": "disabled",
            "jobId": "",
            "lastMessage": "",
            "error": "WOW_CODEX_SIMULATOR_ENABLED is not enabled",
        }
    runner = codex_runner or run_codex_job
    if not runner:
        return {
            "enabled": True,
            "called": False,
            "status": "unavailable",
            "jobId": "",
            "lastMessage": "",
            "error": "codex worker is unavailable",
        }
    prompt = build_codex_simulator_prompt(request_data, simulation)
    try:
        result = runner(
            prompt,
            timeout_seconds=int_env("WOW_CODEX_SIMULATOR_TIMEOUT_SECONDS", 180),
        )
    except Exception as error:
        return {
            "enabled": True,
            "called": True,
            "status": "failed",
            "jobId": "",
            "lastMessage": "",
            "error": str(error),
        }
    return {
        "enabled": True,
        "called": True,
        "status": result.get("status", ""),
        "jobId": result.get("jobId", ""),
        "lastMessage": result.get("lastMessage", ""),
        "error": result.get("stderr", ""),
    }


def run_simcraft(profile):
    binary = simc_binary()
    if not binary:
        return {"ran": False, "available": False, "summary": "", "error": "simcraft binary not found"}
    if not profile.strip():
        return {"ran": False, "available": True, "summary": "", "error": "empty profile"}

    try:
        result = subprocess.run(
            [binary, "-"],
            input=profile,
            text=True,
            capture_output=True,
            timeout=int_env("WOW_SIMC_TIMEOUT_SECONDS", 45),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"ran": False, "available": True, "summary": "", "error": str(error)}

    output = (result.stdout or result.stderr or "").strip()
    return {
        "ran": result.returncode == 0,
        "available": True,
        "summary": output[:4000],
        "error": "" if result.returncode == 0 else (result.stderr or f"simc exited {result.returncode}")[:1000],
    }


def call_llm(prompt):
    return call_chat_completion(
        "你是面向中文魔兽世界玩家的构筑、SimCraft 和 WCL 分析助手。",
        prompt,
        temperature=0.2,
    )


def heuristic_recommendations(request_data, simulation):
    recommendations = []
    if request_data["mode"] in {"simcraft", "simcraft_agent"}:
        dps = simulation.get("metrics", {}).get("dps")
        if simulation.get("ran") and dps:
            recommendations.append(f"本次 SimC 已跑通，当前 profile 约为 {dps} DPS；先把这个作为基准，再比较装备或天赋变体。")
        elif simulation.get("ran"):
            recommendations.append("本次 SimC 已跑通，先把返回摘要作为基准样本，再逐项比较装备、天赋和属性收益。")
        elif not request_data["profile"]:
            recommendations.append("未执行 SimC：当前输入缺少完整 SimCraft profile，请先粘贴角色导出的 profile 或提供可生成 profile 的角色数据。")
        recommendations.append("先用当前角色 profile 跑基准 DPS，再逐项比较饰品、武器和副属性，不要只看聚合榜单。")
        recommendations.append("如果 SimCraft 未执行，先确认服务器已安装 simc，并补充完整 talent、gear 和 fight_style。")
    if request_data["wclUrl"]:
        recommendations.append("把 WCL 链接与具体 boss、难度、尝试编号一起提交，才能对齐技能覆盖和死亡时间线。")
    if simulation.get("ran"):
        recommendations.append("优先查看模拟输出中的 scale factors、top gear deltas 和 fight style，避免把单体结论套到大秘境。")
    recommendations.append("下一步建议补充角色名/服务器、目标场景、可替换装备列表和当前痛点。")
    return recommendations


def build_pipeline_stages(request_data, simulation, llm_result):
    has_profile = bool(request_data.get("profile"))
    profile_source = request_data.get("profileSource") or "none"
    dps = (simulation.get("metrics") or {}).get("dps", "")

    if has_profile:
        profile_stage = {
            "key": "profile_check",
            "title": "Profile 检查",
            "status": "passed",
            "executor": "backend",
            "summary": f"已识别 {profile_source} SimCraft profile",
        }
    else:
        profile_stage = {
            "key": "profile_check",
            "title": "Profile 检查",
            "status": "blocked",
            "executor": "backend",
            "summary": "缺少完整 SimCraft profile",
        }

    if simulation.get("ran"):
        simc_summary = "SimC 已执行成功"
        if dps:
            simc_summary = f"SimC 已执行成功，DPS {dps}"
        simc_stage = {
            "key": "simc_execution",
            "title": "SimC 执行",
            "status": "completed",
            "executor": "simcraft",
            "summary": simc_summary,
            "metric": dps,
        }
    elif request_data.get("mode") in {"simcraft", "simcraft_agent"} and not has_profile:
        simc_stage = {
            "key": "simc_execution",
            "title": "SimC 执行",
            "status": "skipped",
            "executor": "simcraft",
            "summary": simulation.get("error") or "missing simcraft profile",
            "metric": "",
        }
    else:
        simc_stage = {
            "key": "simc_execution",
            "title": "SimC 执行",
            "status": "failed" if simulation.get("error") else "skipped",
            "executor": "simcraft",
            "summary": simulation.get("error") or "simulation not requested",
            "metric": "",
        }

    ai_stage = {
        "key": "ai_interpretation",
        "title": "AI 解读",
        "status": "completed" if llm_result.get("called") and not llm_result.get("error") else ("failed" if llm_result.get("called") else "skipped"),
        "executor": "llm",
        "summary": "已基于真实执行状态生成建议" if llm_result.get("content") else (llm_result.get("error") or "LLM 未配置"),
    }
    return [profile_stage, simc_stage, ai_stage]


def parse_simcraft_metrics(output):
    metrics = {}
    text = str(output or "")
    dps_match = re.search(r"\bDPS=(\d+(?:\.\d+)?)", text)
    if dps_match:
        metrics["dps"] = f"{float(dps_match.group(1)):.3f}".rstrip("0").rstrip(".")
        return metrics
    dps_rank_match = re.search(r"\b(\d+(?:\.\d+)?)\s+dps\b", text.replace(",", ""), re.IGNORECASE)
    if dps_rank_match:
        metrics["dps"] = f"{float(dps_rank_match.group(1)):.3f}".rstrip("0").rstrip(".")
    return metrics


def analyze_simc_agent_request(payload, codex_runner=None):
    source = payload if isinstance(payload, dict) else {}
    message = simc_agent_message(source)
    round_number = normalize_agent_round(source.get("round") or source.get("conversationRound"))
    intent = infer_simc_agent_intent(message)
    scenario = infer_simc_agent_scenario(message)
    explicit_profile = str(source.get("profile") or "").strip()
    extracted_profile = extract_simc_profile_from_prompt(message)
    source_profile = explicit_profile or extracted_profile
    profile_source = "explicit" if explicit_profile else ("prompt" if extracted_profile else "none")
    missing_slots = [] if source_profile else ["character_source"]

    request_data = {
        "mode": "simcraft_agent",
        "character": str(source.get("character") or "").strip(),
        "prompt": message,
        "profile": "",
        "profileSource": profile_source,
        "wclUrl": str(source.get("wclUrl") or "").strip(),
        "question": message,
        "runSimulation": False,
    }

    if intent == "out_of_scope":
        simulation = {
            "ran": False,
            "available": bool(simc_binary()),
            "summary": "",
            "error": "out of scope",
            "metrics": {},
        }
        agent = {
            "status": "off_topic",
            "round": round_number,
            "intent": intent,
            "confidence": 0.95,
            "missingSlots": [],
            "question": "这个问题不属于 SimC 模拟范围。我可以帮你做角色 DPS、装备、饰品、天赋或属性收益模拟。",
            "quickReplies": ["跑当前角色基准", "比较装备收益", "查看属性收益"],
            "draftProfile": "",
            "validation": {"passed": False, "errors": ["out of scope"], "warnings": []},
            "summaryCards": build_agent_summary_cards(request_data, simulation, scenario),
        }
        llm_result = call_llm(build_llm_prompt(request_data, simulation))
        codex_result = skipped_codex_worker_result("out of scope")
        return build_simc_agent_payload(request_data, simulation, agent, llm_result, codex_result)

    if missing_slots:
        status = "insufficient_data" if round_number >= SIMC_AGENT_MAX_ROUNDS else "needs_clarification"
        simulation = {
            "ran": False,
            "available": bool(simc_binary()),
            "summary": "",
            "error": "missing character source",
            "metrics": {},
        }
        agent = {
            "status": status,
            "round": round_number,
            "intent": intent,
            "confidence": 0.78,
            "missingSlots": missing_slots,
            "question": build_agent_clarification_question(missing_slots, round_number),
            "quickReplies": build_agent_quick_replies(missing_slots),
            "draftProfile": "",
            "validation": {"passed": False, "errors": missing_slots, "warnings": []},
            "summaryCards": build_agent_summary_cards(request_data, simulation, scenario),
        }
        llm_result = call_llm(build_llm_prompt(request_data, simulation))
        codex_result = skipped_codex_worker_result("missing character source")
        return build_simc_agent_payload(request_data, simulation, agent, llm_result, codex_result)

    draft_profile = build_agent_simc_profile(source_profile, intent, scenario)
    validation = validate_agent_simc_profile(draft_profile)
    request_data["profile"] = draft_profile
    request_data["runSimulation"] = validation["passed"]
    if validation["passed"]:
        simulation = run_simcraft(draft_profile)
    else:
        simulation = {
            "ran": False,
            "available": bool(simc_binary()),
            "summary": "",
            "error": "; ".join(validation["errors"]) or "template invalid",
        }
    simulation = dict(simulation)
    simulation["metrics"] = parse_simcraft_metrics(simulation.get("summary", ""))
    status = "simc_completed" if simulation.get("ran") else ("template_invalid" if not validation["passed"] else "simc_failed")
    agent = {
        "status": status,
        "round": round_number,
        "intent": intent,
        "confidence": 0.88,
        "missingSlots": [],
        "question": "",
        "quickReplies": [],
        "draftProfile": draft_profile,
        "validation": validation,
        "summaryCards": build_agent_summary_cards(request_data, simulation, scenario),
        "scenario": scenario,
    }
    llm_result = call_llm(build_llm_prompt(request_data, simulation))
    codex_result = call_codex_worker(request_data, simulation, codex_runner=codex_runner) if validation["passed"] else skipped_codex_worker_result("template invalid")
    return build_simc_agent_payload(request_data, simulation, agent, llm_result, codex_result)


def build_simc_agent_payload(request_data, simulation, agent, llm_result, codex_result):
    stages = build_pipeline_stages(request_data, simulation, llm_result)
    recommendations = heuristic_recommendations(request_data, simulation)
    if agent["status"] == "needs_clarification":
        recommendations = [agent["question"]]
    elif agent["status"] == "insufficient_data":
        recommendations = [agent["question"], "第三轮后不再继续追问，建议先拿到 /simc 导出再提交。"]
    elif agent["status"] == "off_topic":
        recommendations = [agent["question"]]
    return {
        "mode": "simcraft_agent",
        "status": "ready",
        "createdAt": utc_now(),
        "capabilities": {
            "simcraft": bool(simc_binary()),
            "llm": llm_configured(),
            "codex": codex_result["enabled"],
        },
        "request": request_data,
        "agent": agent,
        "stages": stages,
        "simulation": simulation,
        "codex": codex_result,
        "recommendations": recommendations,
        "llm": {
            "prompt": build_llm_prompt(request_data, simulation),
            "called": llm_result["called"],
            "model": llm_result.get("model", llm_model()),
            "content": llm_result["content"],
            "error": llm_result["error"],
        },
    }


def analyze_simulator_request(payload, codex_runner=None):
    source = payload if isinstance(payload, dict) else {}
    if (source.get("mode") or "") == "simcraft_agent":
        return analyze_simc_agent_request(source, codex_runner=codex_runner)

    request_data = normalize_analysis_request(payload)
    if request_data["runSimulation"]:
        simulation = run_simcraft(request_data["profile"])
    else:
        simulation = {
            "ran": False,
            "available": bool(simc_binary()),
            "summary": "",
            "error": "missing simcraft profile" if request_data["mode"] == "simcraft" and not request_data["profile"] else "simulation not requested",
        }
    simulation = dict(simulation)
    simulation["metrics"] = parse_simcraft_metrics(simulation.get("summary", ""))
    prompt = build_llm_prompt(request_data, simulation)
    llm_result = call_llm(prompt)
    codex_result = call_codex_worker(request_data, simulation, codex_runner=codex_runner)
    stages = build_pipeline_stages(request_data, simulation, llm_result)

    return {
        "mode": request_data["mode"],
        "status": "ready",
        "createdAt": utc_now(),
        "capabilities": {
            "simcraft": bool(simc_binary()),
            "llm": llm_configured(),
            "codex": codex_result["enabled"],
        },
        "request": request_data,
        "stages": stages,
        "simulation": simulation,
        "codex": codex_result,
        "recommendations": heuristic_recommendations(request_data, simulation),
        "llm": {
            "prompt": prompt,
            "called": llm_result["called"],
            "model": llm_result.get("model", llm_model()),
            "content": llm_result["content"],
            "error": llm_result["error"],
        },
    }
