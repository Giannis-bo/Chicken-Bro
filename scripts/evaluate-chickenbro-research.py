#!/usr/bin/env python3
"""Run repeatable, human-reviewed Chickenbro research evaluations on the cloud runtime."""

import argparse
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
from typing import Any
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.app.api.errors import resolve_request_id, ApiProblem, api_problem_handler
from server.app.api.routes.source_gateway import router as source_gateway_router
from server.app.chickenbro.codex_adapter import NativeCodexChatAdapter, _load_profile
from server.app.chickenbro.source_gateway import (
    SOURCE_GATEWAY_PATH,
    ChickenbroSourceGateway,
    ServerConfiguredSourceQuery,
)


DEFAULT_CASES_PATH = ROOT / "tests/fixtures/chickenbro-research-cases.json"
OBSERVATION_FIELDS = (
    "tool", "sourceKey", "status", "reasonCode", "elapsedMs", "factCount",
    "argumentsSha256", "evidenceRefs", "limitations",
)
EVIDENCE_FIELDS = (
    "id", "sourceName", "sourceUrl", "title", "checkedAt", "sourceScope",
    "reportCode", "fightId", "api", "sourceStatus",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--case", action="append", dest="case_ids", default=[])
    parser.add_argument("--port", type=int, default=8791)
    parser.add_argument("--timeout", type=int, default=300)
    return parser.parse_args()


def _load_cases(selected_ids: list[str]) -> list[dict[str, Any]]:
    document = json.loads(DEFAULT_CASES_PATH.read_text(encoding="utf-8"))
    cases = document.get("cases") if isinstance(document, dict) else None
    if not isinstance(cases, list):
        raise ValueError("evaluation cases must contain a cases array")
    by_id = {
        str(item.get("id")): item
        for item in cases
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    requested = selected_ids or list(by_id)
    missing = [case_id for case_id in requested if case_id not in by_id]
    if missing:
        raise ValueError("unknown evaluation case: " + ", ".join(missing))
    return [by_id[case_id] for case_id in requested]


def _build_gateway_app(gateway: ChickenbroSourceGateway) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.chickenbro_source_gateway = gateway
    app.add_exception_handler(ApiProblem, api_problem_handler)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = resolve_request_id(request.headers.get("X-Request-Id"))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response

    app.include_router(source_gateway_router)
    return app


def _bind_loopback(port: int) -> socket.socket:
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        listener.bind(("127.0.0.1", port))
        listener.listen(128)
        listener.set_inheritable(False)
        return listener
    except Exception:
        listener.close()
        raise


def _start_gateway(gateway: ChickenbroSourceGateway, port: int):
    listener = _bind_loopback(port)
    config = uvicorn.Config(
        _build_gateway_app(gateway), host="127.0.0.1", port=port,
        log_level="warning", access_log=False,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(
        target=server.run, kwargs={"sockets": [listener]},
        name="chickenbro-evaluation-source-gateway", daemon=True,
    )
    thread.start()
    deadline = time.monotonic() + 10
    while thread.is_alive() and not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    if not server.started:
        server.should_exit = True
        thread.join(timeout=2)
        listener.close()
        raise RuntimeError("source gateway failed to start")
    return server, thread, listener


def _safe_observations(job_dir: Path) -> list[dict[str, Any]]:
    path = job_dir / "native-tool-observations.jsonl"
    if not path.is_file():
        return []
    output = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            raw = json.loads(line)
        except (json.JSONDecodeError, UnicodeError):
            continue
        if not isinstance(raw, dict):
            continue
        item = {key: raw[key] for key in OBSERVATION_FIELDS if key in raw}
        item["evidence"] = [
            {key: evidence[key] for key in EVIDENCE_FIELDS if key in evidence}
            for evidence in raw.get("evidence", [])
            if isinstance(evidence, dict)
        ]
        output.append(item)
    return output


def _configuration_identity(adapter: NativeCodexChatAdapter) -> dict[str, Any]:
    profile_name = str(os.environ.get("WOW_CODEX_PROFILE") or "").strip()
    profile = _load_profile(profile_name or None)
    return {
        "profile": profile_name or "default",
        "model": str(profile.get("model") or "configured-default"),
        "reasoningEffort": str(profile.get("model_reasoning_effort") or "configured-default"),
        "runtimeRevision": adapter.runtime_revision,
    }


def _new_job(previous: set[Path], jobs_dir: Path) -> Path | None:
    created = [path for path in jobs_dir.iterdir() if path.is_dir() and path not in previous]
    return max(created, key=lambda path: path.stat().st_mtime_ns) if created else None


def _run_case(
    case: dict[str, Any], adapter: NativeCodexChatAdapter, jobs_dir: Path,
    timeout_seconds: int, configuration: dict[str, Any],
) -> dict[str, Any]:
    started = time.monotonic()
    first_text_ms = None
    final_answer = ""
    status = "failed"
    error_code = ""
    previous_jobs = {path for path in jobs_dir.iterdir() if path.is_dir()}
    try:
        for event in adapter.stream(prompt=str(case["prompt"]), timeout_seconds=timeout_seconds):
            text = str(event.get("text") or "")
            if text and first_text_ms is None:
                first_text_ms = round((time.monotonic() - started) * 1000)
            if event.get("type") == "completed":
                final_answer = text
        status = "succeeded" if final_answer else "failed"
        if not final_answer:
            error_code = "EMPTY_FINAL_ANSWER"
    except Exception as error:
        error_code = str(getattr(error, "code", "EVALUATION_RUN_FAILED"))[:80]
    total_ms = round((time.monotonic() - started) * 1000)
    job_dir = _new_job(previous_jobs, jobs_dir)
    return {
        "caseId": str(case["id"]),
        "category": str(case.get("category") or ""),
        "prompt": str(case["prompt"]),
        "humanRubric": case.get("humanRubric", []),
        "evaluationStatus": "awaiting_review",
        "runStatus": status,
        "errorCode": error_code,
        "finalAnswer": final_answer,
        "firstTextMs": first_text_ms,
        "totalMs": total_ms,
        "toolObservations": _safe_observations(job_dir) if job_dir else [],
        "configuration": configuration,
    }


def main() -> int:
    args = _parse_args()
    if args.timeout < 1:
        raise SystemExit("--timeout must be positive")
    cases = _load_cases(args.case_ids)
    output_dir = args.output_dir.resolve()
    jobs_dir = output_dir / "jobs"
    output_dir.mkdir(parents=True, exist_ok=True)
    jobs_dir.mkdir(parents=True, exist_ok=True)

    gateway = ChickenbroSourceGateway(query_service=ServerConfiguredSourceQuery())
    adapter = NativeCodexChatAdapter(
        enabled=True,
        source_gateway=gateway,
        source_gateway_url=f"http://127.0.0.1:{args.port}{SOURCE_GATEWAY_PATH}",
        jobs_dir=jobs_dir,
    )
    configuration = _configuration_identity(adapter)
    server, thread, listener = _start_gateway(gateway, args.port)
    run_id = uuid4().hex
    results = []
    try:
        for case in cases:
            result = _run_case(case, adapter, jobs_dir, args.timeout, configuration)
            results.append(result)
            (output_dir / f"{result['caseId']}.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            print(json.dumps({"caseId": result["caseId"], "status": result["runStatus"],
                              "totalMs": result["totalMs"]}), flush=True)
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()

    summary = {
        "runId": run_id,
        "evaluationStatus": "awaiting_review",
        "configuration": configuration,
        "caseCount": len(results),
        "results": results,
    }
    (output_dir / "evaluation-results.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0 if all(item["runStatus"] == "succeeded" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
