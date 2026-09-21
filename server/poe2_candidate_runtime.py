"""Start the isolated POE2 Candidate with host credentials kept in memory."""

import os
from pathlib import Path
import sys
from urllib.parse import urlparse

from server.test_login_runtime import prepare_environment as prepare_test_environment


_CANDIDATE_ROOT = "/opt/chickenbro-candidates/poe2-20260918"


def prepare_environment(source, read_text=lambda path: Path(path).read_text()):
    """Validate the production source credential, then force every Candidate boundary."""
    source_database = urlparse(source.get("WOW_DATABASE_URL", ""))
    if source_database.password is not None:
        raise ValueError("POE2 Candidate database password must come from PGPASSFILE")
    env = prepare_test_environment(source, read_text=read_text)
    database = urlparse(env["WOW_DATABASE_URL"])
    env["WOW_DATABASE_URL"] = database._replace(path="/chickenbro_poe2_candidate").geturl()
    runtime_root = _CANDIDATE_ROOT + "/runtime/root"
    pob_root = _CANDIDATE_ROOT + "/upstream/pob"
    env.update({
        "WOW_APP_ENV": "test",
        "WOW_DATABASE_RUNTIME": "postgres_only",
        "WOW_API_V2_HOST": "127.0.0.1",
        "WOW_API_V2_PORT": "8796",
        "WOW_WEB_ORIGIN": "https://www.chickenbro.cloud",
        "WOW_WEB_COOKIE_NAME": "__Host-chickenbro-poe2-candidate-session",
        "WOW_WEB_CSRF_COOKIE_NAME": "__Host-chickenbro-poe2-candidate-csrf",
        "WOW_WEB_SESSION_TTL_SECONDS": "86400",
        "WOW_TEST_LOGIN_ENABLED": "1",
        "WOW_CHAT_DURABLE_ENABLED": "1",
        "WOW_CHAT_WORKER_TOOL_PORT": "18794",
        "WOW_WORKER_V2_HEARTBEAT_PATH": "/var/lib/chickenbro/poe2-candidate-worker-heartbeat.json",
        "WOW_CODEX_JOBS_DIR": "/var/lib/chickenbro/poe2-candidate-codex-jobs",
        "WOW_CHICKENBRO_CODEX_ENABLED": "1",
        "WOW_CODEX_BIN": "/usr/local/bin/codex",
        "WOW_CODEX_HOME": "/home/ubuntu/.codex",
        "CODEX_HOME": "/home/ubuntu/.codex",
        "WOW_CODEX_PROFILE": "chickenbro-production",
        "WOW_CODEX_SANDBOX": "read-only",
        "HOME": "/home/ubuntu",
        "WOW_SIMC_BIN": "/opt/wow-simc/current/simc",
        "WOW_SIMC_SUPPORTED_SPECS": "all",
        "WOW_SIMC_COMPILER_REVISION": "chickenbro-simc-compiler-v6",
        "POE2_POB_ROOT": pob_root,
        "POE2_LUAJIT": runtime_root + "/usr/bin/luajit",
        "POE2_ENGINE_VERSION": "v0.23.1@7d6f530cbdab20389ff8bc6ba97a37ac27f74e41",
        "POE2_ENGINE_LOCK": "/var/lib/chickenbro/poe2-candidate-engine.lock",
        "LD_LIBRARY_PATH": runtime_root + "/usr/lib/x86_64-linux-gnu",
        "LUA_CPATH": runtime_root + "/usr/lib/x86_64-linux-gnu/lua/5.1/?.so;;",
        "LUA_PATH": pob_root + "/runtime/lua/?.lua;" + pob_root + "/runtime/lua/?/init.lua;;",
        "HTTP_PROXY": "http://127.0.0.1:7890",
        "HTTPS_PROXY": "http://127.0.0.1:7890",
        "ALL_PROXY": "http://127.0.0.1:7890",
        "NO_PROXY": "127.0.0.1,localhost,::1,169.254.169.254,raider.io,www.raider.io,warcraftlogs.com,www.warcraftlogs.com,.api.blizzard.com,gateway.battlenet.com.cn",
        "WOW_QQ_APPID": "",
        "WOW_QQ_APP_KEY": "",
        "WOW_QQ_REDIRECT_URI": "",
    })
    return env


def exec_args(mode):
    if mode == "api":
        return ["-m", "uvicorn", "server.app.main:app", "--host", "127.0.0.1", "--port", "8796"]
    if mode == "worker":
        return ["-m", "server.app.worker.main", "--worker-id", "chickenbro-poe2-candidate-worker"]
    raise ValueError("mode must be api or worker")


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        raise SystemExit("usage: python -m server.poe2_candidate_runtime api|worker")
    try:
        command = exec_args(arguments[0])
        environment = prepare_environment(os.environ)
    except Exception:
        raise SystemExit("POE2 Candidate runtime configuration failed; no service was started.") from None
    os.environ.clear()
    os.environ.update(environment)
    os.execv(sys.executable, [sys.executable, *command])


if __name__ == "__main__":
    main()
