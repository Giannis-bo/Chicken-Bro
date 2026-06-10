import json
import os
from urllib.request import Request, urlopen


def int_env(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def llm_configured():
    return bool(os.environ.get("WOW_LLM_API_URL", "").strip() and os.environ.get("WOW_LLM_API_KEY", "").strip())


def llm_model():
    return os.environ.get("WOW_LLM_MODEL", "gpt-4.1-mini")


def call_chat_completion(system_prompt, user_prompt, temperature=0.2):
    api_url = os.environ.get("WOW_LLM_API_URL", "").strip()
    api_key = os.environ.get("WOW_LLM_API_KEY", "").strip()
    model = llm_model()
    if not api_url or not api_key:
        return {"called": False, "model": model, "content": "", "error": "llm is not configured"}

    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
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
