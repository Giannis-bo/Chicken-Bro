import json
import os
import time
from urllib.request import Request, urlopen


class ChickenbroStreamUnavailable(RuntimeError):
    pass


class ChickenbroStreamProtocolError(RuntimeError):
    pass


def int_env(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def llm_configured():
    return bool(os.environ.get("WOW_LLM_API_URL", "").strip() and os.environ.get("WOW_LLM_API_KEY", "").strip())


def llm_model():
    return os.environ.get("WOW_LLM_MODEL", "gpt-4.1-mini")


def chickenbro_stream_config():
    enabled = os.environ.get("WOW_CHICKENBRO_STREAM_ENABLED", "").strip() == "1"
    api_url = os.environ.get("WOW_CHICKENBRO_STREAM_API_URL", "").strip()
    api_key = os.environ.get("WOW_CHICKENBRO_STREAM_API_KEY", "").strip()
    model = os.environ.get("WOW_CHICKENBRO_STREAM_MODEL", "").strip()
    return {"enabled": bool(enabled and api_url and api_key and model), "model": model if enabled and api_url and api_key and model else ""}


def stream_chat_completion(system_prompt, user_prompt, schema, temperature=0.3, opener=urlopen, clock=time.monotonic):
    config = chickenbro_stream_config()
    if not config["enabled"]:
        raise ChickenbroStreamUnavailable("chickenbro stream provider is not configured")
    api_url = os.environ.get("WOW_CHICKENBRO_STREAM_API_URL", "").strip()
    api_key = os.environ.get("WOW_CHICKENBRO_STREAM_API_KEY", "").strip()
    body = json.dumps(
        {
            "model": config["model"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "stream": True,
            "response_format": {"type": "json_object"},
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = Request(
        api_url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )
    timeout_seconds = max(1, int_env("WOW_CHICKENBRO_STREAM_TIMEOUT_SECONDS", 60))
    deadline = clock() + timeout_seconds
    with opener(request, timeout=timeout_seconds) as response:
        for raw_line in response:
            if clock() >= deadline:
                raise ChickenbroStreamUnavailable(
                    f"chickenbro stream provider exceeded {timeout_seconds} seconds"
                )
            line = raw_line.decode("utf-8").strip()
            if not line or line.startswith(":"):
                continue
            if not line.startswith("data:"):
                raise ChickenbroStreamProtocolError("malformed provider SSE event")
            data = line[5:].strip()
            if data == "[DONE]":
                return
            try:
                payload = json.loads(data)
            except json.JSONDecodeError as error:
                raise ChickenbroStreamProtocolError("malformed provider SSE payload") from error
            choices = payload.get("choices") if isinstance(payload, dict) else None
            if not isinstance(choices, list) or not choices:
                raise ChickenbroStreamProtocolError("provider SSE payload has no choices")
            delta = choices[0].get("delta") if isinstance(choices[0], dict) else None
            content = delta.get("content") if isinstance(delta, dict) else ""
            if content is None:
                continue
            if not isinstance(content, str):
                raise ChickenbroStreamProtocolError("provider delta content must be text")
            if content:
                yield content


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
