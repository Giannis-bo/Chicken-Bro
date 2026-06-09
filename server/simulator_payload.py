import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


DEFAULT_SIMC_VERSION_FILE = "/var/lib/wow-backend/simc-version.json"


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def int_env(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


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


def build_simulator_home_payload():
    has_simc = bool(simc_binary())
    has_llm = bool(os.environ.get("WOW_LLM_API_URL") and os.environ.get("WOW_LLM_API_KEY"))
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
    return {
        "mode": source.get("mode") or "simcraft",
        "character": str(source.get("character") or "").strip(),
        "profile": str(source.get("profile") or "").strip(),
        "wclUrl": str(source.get("wclUrl") or "").strip(),
        "question": str(source.get("question") or "").strip(),
        "runSimulation": bool(source.get("runSimulation")),
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
    sections.append("输出格式：先给 3 条优先级最高的结论，再列验证方式和下一步需要补充的数据。")
    return "\n\n".join(sections)


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
    api_url = os.environ.get("WOW_LLM_API_URL", "").strip()
    api_key = os.environ.get("WOW_LLM_API_KEY", "").strip()
    model = os.environ.get("WOW_LLM_MODEL", "gpt-4.1-mini")
    if not api_url or not api_key:
        return {"called": False, "model": model, "content": "", "error": "llm is not configured"}

    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是面向中文魔兽世界玩家的构筑、SimCraft 和 WCL 分析助手。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
    ).encode("utf-8")
    request = Request(
        api_url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=int_env("WOW_LLM_TIMEOUT_SECONDS", 30)) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as error:
        return {"called": True, "model": model, "content": "", "error": str(error)}

    choices = payload.get("choices") or []
    content = ""
    if choices:
        content = ((choices[0].get("message") or {}).get("content") or "").strip()
    return {"called": True, "model": model, "content": content, "error": "" if content else "empty llm response"}


def heuristic_recommendations(request_data, simulation):
    recommendations = []
    if request_data["mode"] == "simcraft":
        recommendations.append("先用当前角色 profile 跑基准 DPS，再逐项比较饰品、武器和副属性，不要只看聚合榜单。")
        recommendations.append("如果 SimCraft 未执行，先确认服务器已安装 simc，并补充完整 talent、gear 和 fight_style。")
    if request_data["wclUrl"]:
        recommendations.append("把 WCL 链接与具体 boss、难度、尝试编号一起提交，才能对齐技能覆盖和死亡时间线。")
    if simulation.get("ran"):
        recommendations.append("优先查看模拟输出中的 scale factors、top gear deltas 和 fight style，避免把单体结论套到大秘境。")
    recommendations.append("下一步建议补充角色名/服务器、目标场景、可替换装备列表和当前痛点。")
    return recommendations


def analyze_simulator_request(payload):
    request_data = normalize_analysis_request(payload)
    simulation = run_simcraft(request_data["profile"]) if request_data["runSimulation"] else {
        "ran": False,
        "available": bool(simc_binary()),
        "summary": "",
        "error": "simulation not requested",
    }
    prompt = build_llm_prompt(request_data, simulation)
    llm_result = call_llm(prompt)

    return {
        "mode": request_data["mode"],
        "status": "ready",
        "createdAt": utc_now(),
        "capabilities": {
            "simcraft": bool(simc_binary()),
            "llm": bool(os.environ.get("WOW_LLM_API_URL") and os.environ.get("WOW_LLM_API_KEY")),
        },
        "request": request_data,
        "simulation": simulation,
        "recommendations": heuristic_recommendations(request_data, simulation),
        "llm": {
            "prompt": prompt,
            "called": llm_result["called"],
            "model": llm_result["model"],
            "content": llm_result["content"],
            "error": llm_result["error"],
        },
    }
