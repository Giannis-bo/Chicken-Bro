import json
import os
import re
import subprocess
import uuid
from pathlib import Path


DEFAULT_JOBS_DIR = Path(os.environ.get("WOW_CODEX_JOBS_DIR", "/var/lib/wow-backend/codex-jobs"))
DEFAULT_CODEX_BIN = os.environ.get("WOW_CODEX_BIN", "codex")
DEFAULT_SANDBOX = os.environ.get("WOW_CODEX_SANDBOX", "workspace-write")
DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("WOW_CODEX_TIMEOUT_SECONDS", "900"))
ALLOWED_SANDBOXES = {"read-only", "workspace-write"}
SAFE_JOB_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def normalize_sandbox(value):
    sandbox = (value or DEFAULT_SANDBOX).strip()
    if sandbox not in ALLOWED_SANDBOXES:
        raise ValueError(f"unsupported codex sandbox: {sandbox}")
    return sandbox


def build_codex_command(
    prompt_path,
    job_dir,
    output_path,
    schema_path=None,
    sandbox=None,
    codex_bin=None,
):
    command = [
        codex_bin or DEFAULT_CODEX_BIN,
        "--ask-for-approval",
        "never",
        "exec",
        "--json",
        "--skip-git-repo-check",
        "--cd",
        str(job_dir),
        "--sandbox",
        normalize_sandbox(sandbox),
        "--output-last-message",
        str(output_path),
    ]
    if schema_path:
        command.extend(["--output-schema", str(schema_path)])
    command.append("-")
    return command


def parse_jsonl_events(stdout):
    events = []
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            events.append({"type": "raw", "message": line})
    return events


def run_codex_job(
    prompt,
    jobs_dir=DEFAULT_JOBS_DIR,
    job_id=None,
    schema=None,
    sandbox=None,
    timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
    runner=subprocess.run,
):
    if not str(prompt or "").strip():
        raise ValueError("codex prompt is required")

    job_id = job_id or uuid.uuid4().hex
    if not SAFE_JOB_ID_PATTERN.match(job_id):
        raise ValueError("invalid codex job_id")
    job_dir = Path(jobs_dir) / job_id
    job_dir.mkdir(parents=True, exist_ok=False)
    prompt_path = job_dir / "prompt.txt"
    output_path = job_dir / "last-message.txt"
    schema_path = job_dir / "result.schema.json" if schema else None

    prompt_text = str(prompt)
    prompt_path.write_text(prompt_text, encoding="utf-8")
    if schema_path:
        schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")

    command = build_codex_command(
        prompt_path=prompt_path,
        job_dir=job_dir,
        output_path=output_path,
        schema_path=schema_path,
        sandbox=sandbox,
    )
    try:
        completed = runner(
            command,
            cwd=str(job_dir),
            input=prompt_text,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        status = "succeeded" if completed.returncode == 0 else "failed"
        return_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as error:
        status = "timed_out"
        return_code = -1
        stdout = error.output or ""
        stderr = f"codex exec timed out after {timeout_seconds} seconds"
        if error.stderr:
            stderr = f"{stderr}: {error.stderr}"

    result = {
        "jobId": job_id,
        "status": status,
        "returnCode": return_code,
        "jobDir": str(job_dir),
        "lastMessage": output_path.read_text(encoding="utf-8") if output_path.exists() else "",
        "events": parse_jsonl_events(stdout),
        "stderr": stderr,
    }
    (job_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
