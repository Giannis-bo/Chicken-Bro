"""Read-only, redacted NapCat preparation checks; never returns a login QR or token."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def request(url, body=None, credential=None):
    headers = {"Content-Type": "application/json"}
    if credential:
        headers["Authorization"] = "Bearer " + credential
    req = urllib.request.Request(
        url, data=None if body is None else json.dumps(body).encode(), headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-before", type=Path, required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit("Run as root")
    private = Path("/etc/chickenbro-qq-channel")
    config = Path("/var/lib/chickenbro-qq-channel/config")
    credentials = json.loads((private / "credentials.json").read_text())
    channel = json.loads((private / "channel.json").read_text())
    core = json.loads((config / "napcat.json").read_text())
    onebot = json.loads((config / "onebot11.json").read_text())
    lock = json.loads(Path("/opt/chickenbro-qq-channel/image-lock.json").read_text())
    container = json.loads(command("docker", "inspect", "chickenbro-napcat"))[0]
    host = container["HostConfig"]
    base = "http://127.0.0.1:16099/api"
    status, unauthorized = request(base + "/QQLogin/CheckLoginStatus", {})
    _, auth = request(base + "/auth/login", {
        "hash": hashlib.sha256((credentials["webuiToken"] + ".napcat").encode()).hexdigest()
    })
    credential = (auth.get("data") or {}).get("Credential")
    if not credential:
        raise SystemExit("Management authentication failed")
    try:
        _, login = request(base + "/QQLogin/CheckLoginStatus", {}, credential)
        _, version = request(base + "/base/GetNapCatVersion", credential=credential)
    finally:
        request(base + "/auth/logout", {}, credential)
    _, readiness = request("http://127.0.0.1:8790/api/v2/health/readiness")
    services = command("systemctl", "show", "chickenbro-api", "chickenbro-worker",
                       "-p", "MainPID", "-p", "ExecMainStartTimestamp", "-p", "ActiveState")
    backend = command("readlink", "-f", "/opt/chickenbro")
    web = command("readlink", "-f", "/var/www/chickenbro-web/current")
    current = services + "\n" + backend + "\n" + web
    expected_ports = {
        "6099/tcp": [{"HostIp": "127.0.0.1", "HostPort": "16099"}],
        "3001/tcp": [{"HostIp": "127.0.0.1", "HostPort": "13001"}],
    }
    checks = {
        "containerRunning": container["State"]["Running"],
        "noAutomaticRestartsOrOOM": container["RestartCount"] == 0 and not container["State"]["OOMKilled"],
        "imageMatchesLock": container["Config"]["Image"] == lock["image"],
        "loopbackPortsOnly": host["PortBindings"] == expected_ports,
        "resourceLimits": host["Memory"] == 768 * 1024**2 and host["NanoCpus"] == 10**9
            and host["MemorySwap"] == 1024**3 and host["PidsLimit"] == 256,
        "notPrivileged": host["Privileged"] is False,
        "onlyChannelMounts": len(container["Mounts"]) == 3 and all(
            m["Source"].startswith("/var/lib/chickenbro-qq-channel/") for m in container["Mounts"]),
        "credentialsPrivate": all(stat.S_IMODE((private / name).stat().st_mode) == 0o600
            for name in ("credentials.json", "channel.json")),
        "secretConsoleAndFileLogsOff": host["LogConfig"]["Type"] == "none"
            and not core["fileLog"] and not core["consoleLog"],
        "managementRejectsUnauthenticated": unauthorized.get("code") != 0
            and unauthorized.get("message") == "Unauthorized",
        "managementAuthenticated": login.get("code") == 0 and version.get("code") == 0,
        "distinctNonemptyTokens": len(credentials["webuiToken"]) >= 32
            and len(credentials["onebotToken"]) >= 32
            and credentials["webuiToken"] != credentials["onebotToken"],
        "onebotTokenConfigured": onebot["network"]["websocketServers"][0]["token"] == credentials["onebotToken"],
        "businessDisabled": channel["enabled"] is False,
        "productionProcessesAndPointersUnchanged": current == args.production_before.read_text().strip(),
        "productionReadiness": readiness.get("status") == "ready",
        "temporaryDockerProxyRemoved": not Path(
            "/run/systemd/system/docker.service.d/90-chickenbro-napcat-pull.conf").exists(),
    }
    result = {
        "observedAt": datetime.now(timezone.utc).isoformat(),
        "scope": "napcat_environment_preparation_only",
        "image": lock["image"], "napcatVersion": version.get("data", {}).get("version"),
        "linuxQQVersion": command("docker", "exec", "chickenbro-napcat", "dpkg-query", "-W", "-f=${Version}", "linuxqq"),
        "container": "chickenbro-napcat", "checks": checks,
        "managementUnauthenticatedHttpStatus": status,
        "qqLoggedIn": bool(login.get("data", {}).get("isLogin")),
        "coreReady": bool(login.get("data", {}).get("coreReady")),
        "channelIdentityConfigured": bool(channel.get("botQQ")) and bool(channel.get("allowedGroups"))
            and bool(channel.get("adminQQs")),
        "onebotAuthenticatedRoundTrip": "requires_separate_onebot_check" if login.get("data", {}).get("isLogin") else "pending_qq_login",
        "groupBusinessAcceptance": "not_run", "channelAdapter": "not_implemented",
        "production": {"backendPointer": backend, "webPointer": web,
                       "processSnapshotSha256": hashlib.sha256(current.encode()).hexdigest()},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
