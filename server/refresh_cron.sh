#!/usr/bin/env bash
set -u

API_URL="${WOW_NEWS_REFRESH_URL:-http://127.0.0.1/api/news/refresh?mode=scheduled}"
LOG_FILE="${WOW_NEWS_REFRESH_LOG:-/home/ubuntu/wow-news-backend/logs/refresh_cron.log}"
TIMEOUT_SECONDS="${WOW_NEWS_REFRESH_TIMEOUT:-45}"

mkdir -p "$(dirname "$LOG_FILE")"

{
  printf '[%s] refresh start url=%s\n' "$(date -Is)" "$API_URL"
  python3 - "$API_URL" "$TIMEOUT_SECONDS" <<'PY'
import socket
import sys
from urllib.request import Request, urlopen

api_url = sys.argv[1]
timeout = int(sys.argv[2])
socket.setdefaulttimeout(timeout)

request = Request(api_url, method="POST")
with urlopen(request, timeout=timeout) as response:
    body = response.read().decode("utf-8", errors="replace")
    print(f"status={response.status}")
    print(body[:1000])
PY
  status=$?
  if [ "$status" -eq 0 ]; then
    printf '[%s] refresh finish status=ok\n' "$(date -Is)"
  else
    printf '[%s] refresh finish status=failed exit=%s\n' "$(date -Is)" "$status"
  fi
  exit "$status"
} >>"$LOG_FILE" 2>&1
