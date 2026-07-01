#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import subprocess


PUBLIC_ENDPOINTS = [
    ("health", "/health"),
    ("builds_home", "/api/builds/home"),
    ("news_home", "/api/news/home"),
    ("data_health", "/api/data/health"),
    ("websim_bootstrap", "/api/websim/bootstrap"),
    ("websim_gear_initial", "/api/websim/gear?class=mage&spec=frost&compact=1&mode=initial"),
    ("websim_gear_slot_head", "/api/websim/gear?class=mage&spec=frost&compact=1&mode=slot&slot=head"),
    ("websim_talents", "/api/websim/talents?class=mage&spec=frost&hero=spellslinger"),
]


def curl_once(base_url: str, path: str) -> tuple[int, float, int]:
    output = subprocess.check_output(
        [
            "curl",
            "-sS",
            "-o",
            "/dev/null",
            "-w",
            "%{http_code} %{time_total} %{size_download}",
            f"{base_url.rstrip('/')}{path}",
        ],
        text=True,
    ).strip()
    code, elapsed, size = output.split()
    return int(code), float(elapsed), int(size)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://124.223.51.33")
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()

    rows = []
    for name, path in PUBLIC_ENDPOINTS:
        results = [curl_once(args.base_url, path) for _ in range(args.repeat)]
        rows.append(
            {
                "name": name,
                "code": results[-1][0],
                "p50Seconds": statistics.median(item[1] for item in results),
                "maxSeconds": max(item[1] for item in results),
                "bytes": results[-1][2],
            }
        )
    print(json.dumps({"baseUrl": args.base_url, "repeat": args.repeat, "rows": rows}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
