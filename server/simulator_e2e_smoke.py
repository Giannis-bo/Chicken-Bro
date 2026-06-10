#!/usr/bin/env python3
import argparse
import importlib
import json
import os
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

SMOKE_PROMPT = (
    "帮我跑一下 smoke profile\n"
    "```simc\n"
    "iterations=1\n"
    "max_time=1\n"
    "warrior=\"SmokeWarrior\"\n"
    "level=80\n"
    "race=human\n"
    "role=attack\n"
    "spec=arms\n"
    "actions=/auto_attack\n"
    "```"
)


def smoke_request_body():
    return {
        "mode": "simcraft",
        "prompt": SMOKE_PROMPT,
    }


def post_smoke_request(base_url, timeout):
    request = Request(
        f"{base_url.rstrip('/')}/api/simulator/analyze",
        data=json.dumps(smoke_request_body(), ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload


def summarize_payload(payload, captured_profile=""):
    from server.simulator_payload import parse_simcraft_metrics

    simulation = payload["simulation"]
    observed_dps = (simulation.get("metrics") or {}).get("dps")
    if not observed_dps:
        observed_dps = parse_simcraft_metrics(simulation.get("summary", "")).get("dps", "")
    return {
        "request": payload["request"],
        "simulation": simulation,
        "recommendations": payload["recommendations"],
        "observedDps": observed_dps,
        "capturedProfile": captured_profile,
    }


def validate_smoke_result(result):
    if not result["simulation"].get("ran"):
        raise SystemExit("simulator smoke failed: simulation.ran was not true")
    if not result.get("observedDps"):
        raise SystemExit("simulator smoke failed: no DPS value found in metrics or summary")


def write_fake_simc(path, captured_profile):
    path.write_text(
        "#!/bin/sh\n"
        f"cat > {captured_profile}\n"
        "printf 'DPS Ranking:\\n1. SmokeProfile 140002 dps\\nScale Factors:\\nintellect=9.4 haste=6.8 mastery=5.9\\n'\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def run_local_smoke():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        fake_simc = tmp_path / "simc"
        captured_profile = tmp_path / "captured-profile.simc"
        write_fake_simc(fake_simc, captured_profile)

        os.environ["WOW_NEWS_DB"] = str(tmp_path / "wow-news.sqlite3")
        os.environ["WOW_SIMC_BIN"] = str(fake_simc)
        os.environ["WOW_NEWS_ENABLE_COLLECTORS"] = "0"

        import server.news_backend as backend

        backend = importlib.reload(backend)
        backend.init_db()
        backend.Handler.log_message = lambda self, format, *args: None

        server = ThreadingHTTPServer(("127.0.0.1", 0), backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            payload = post_smoke_request(f"http://127.0.0.1:{server.server_port}", 15)
        finally:
            server.shutdown()
            server.server_close()
            os.environ.pop("WOW_NEWS_DB", None)
            os.environ.pop("WOW_SIMC_BIN", None)
            os.environ.pop("WOW_NEWS_ENABLE_COLLECTORS", None)

        return summarize_payload(payload, captured_profile.read_text(encoding="utf-8"))


def run_remote_smoke(base_url, timeout):
    return summarize_payload(post_smoke_request(base_url, timeout))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a SimC prompt through the simulator backend.")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("WOW_SIMULATOR_SMOKE_BASE_URL", ""),
        help="Backend base URL. If omitted, start a local backend with a fake simc binary.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("WOW_SIMULATOR_SMOKE_TIMEOUT", "15")),
        help="HTTP timeout in seconds for a backend smoke request.",
    )
    args = parser.parse_args()
    result = run_remote_smoke(args.base_url, args.timeout) if args.base_url else run_local_smoke()
    validate_smoke_result(result)
    print(json.dumps(result, ensure_ascii=False))
