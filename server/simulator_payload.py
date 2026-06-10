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
    if request_data["mode"] == "simcraft" and not request_data["profile"]:
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
    if request_data["mode"] == "simcraft":
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


def analyze_simulator_request(payload, codex_runner=None):
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
