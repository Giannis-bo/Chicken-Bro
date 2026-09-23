"""Read-only OneBot login/group checks using the standard library, without message sends."""
import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import time
import uuid
from datetime import datetime, timezone


def read_exact(sock, size):
    chunks = bytearray()
    while len(chunks) < size:
        chunk = sock.recv(size - len(chunks))
        if not chunk:
            raise RuntimeError("OneBot connection closed")
        chunks.extend(chunk)
    return bytes(chunks)


def connect(token=None):
    sock = socket.create_connection(("127.0.0.1", 13001), timeout=10)
    key = base64.b64encode(os.urandom(16)).decode()
    lines = ["GET / HTTP/1.1", "Host: 127.0.0.1:13001", "Upgrade: websocket",
             "Connection: Upgrade", "Sec-WebSocket-Version: 13", "Sec-WebSocket-Key: " + key]
    if token:
        lines.append("Authorization: Bearer " + token)
    sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
    header = bytearray()
    while not header.endswith(b"\r\n\r\n") and len(header) < 8192:
        header.extend(read_exact(sock, 1))
    lines = header.decode("ascii").split("\r\n")
    status = int(lines[0].split()[1])
    if status == 101:
        expected = base64.b64encode(hashlib.sha1(
            (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        headers = {line.split(":", 1)[0].lower(): line.split(":", 1)[1].strip()
                   for line in lines[1:] if ":" in line}
        if headers.get("sec-websocket-accept") != expected:
            sock.close()
            raise RuntimeError("Invalid WebSocket handshake")
    return sock, status


def send(sock, body, opcode=1):
    mask = os.urandom(4)
    size = len(body)
    if size < 126:
        header = bytes([0x80 | opcode, 0x80 | size])
    elif size < 65536:
        header = bytes([0x80 | opcode, 0xFE]) + struct.pack("!H", size)
    else:
        header = bytes([0x80 | opcode, 0xFF]) + struct.pack("!Q", size)
    sock.sendall(header + mask + bytes(value ^ mask[i % 4] for i, value in enumerate(body)))


def receive(sock):
    parts = bytearray()
    while True:
        first, second = read_exact(sock, 2)
        size = second & 0x7F
        if size == 126:
            size = struct.unpack("!H", read_exact(sock, 2))[0]
        elif size == 127:
            size = struct.unpack("!Q", read_exact(sock, 8))[0]
        if size + len(parts) > 2 * 1024**2:
            raise RuntimeError("OneBot response exceeds verification bound")
        mask = read_exact(sock, 4) if second & 0x80 else None
        body = read_exact(sock, size)
        if mask:
            body = bytes(value ^ mask[i % 4] for i, value in enumerate(body))
        opcode = first & 15
        if opcode == 8:
            raise RuntimeError("OneBot closed the connection")
        if opcode == 9:
            send(sock, body, opcode=10)
            continue
        if opcode == 10:
            continue
        if opcode not in (0, 1):
            raise RuntimeError("Unexpected OneBot frame type")
        parts.extend(body)
        if first & 0x80:
            return json.loads(parts)


def call(sock, action, params=None):
    echo = uuid.uuid4().hex
    send(sock, json.dumps({"action": action, "params": params or {}, "echo": echo}).encode())
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        sock.settimeout(max(0.1, deadline - time.monotonic()))
        result = receive(sock)
        if result.get("echo") == echo:
            return result
    raise RuntimeError("OneBot response timed out")


def main():
    private = Path("/etc/chickenbro-qq-channel")
    credentials = json.loads((private / "credentials.json").read_text())
    channel = json.loads((private / "channel.json").read_text())
    unauth_sock, unauth_status = connect()
    unauth_retcode = None
    if unauth_status == 101:
        unauth_result = receive(unauth_sock)
        unauth_retcode = unauth_result.get("retcode")
        if unauth_retcode != 1403 or unauth_result.get("status") != "failed":
            unauth_sock.close()
            raise RuntimeError("OneBot did not reject the unauthenticated connection")
    elif unauth_status not in (401, 403):
        unauth_sock.close()
        raise RuntimeError("Unexpected unauthenticated handshake response")
    unauth_sock.close()
    sock, status = connect(credentials["onebotToken"])
    if status != 101:
        sock.close()
        raise RuntimeError("OneBot authentication failed")
    try:
        login = call(sock, "get_login_info")
        if login.get("retcode") != 0:
            raise RuntimeError("Cannot read login identity")
        identity_matches = str(login["data"]["user_id"]) == channel["botQQ"]
        if not identity_matches:
            raise RuntimeError("Logged-in QQ does not match configured bot")
        groups = call(sock, "get_group_list")
        if groups.get("retcode") != 0:
            raise RuntimeError("Cannot read group membership")
        joined = {str(group["group_id"]) for group in groups["data"]}
        allowed_joined = bool(channel["allowedGroups"]) and set(channel["allowedGroups"]).issubset(joined)
        owner_verified = False
        if allowed_joined and len(channel["allowedGroups"]) == 1 and len(channel["adminQQs"]) == 1:
            owner = call(sock, "get_group_member_info", {
                "group_id": int(channel["allowedGroups"][0]), "user_id": int(channel["adminQQs"][0]),
                "no_cache": True,
            })
            owner_verified = owner.get("retcode") == 0 and (owner.get("data") or {}).get("role") == "owner"
        print(json.dumps({"observedAt": datetime.now(timezone.utc).isoformat(),
            "scope": "read_only_onebot_login_and_group_membership",
            "unauthenticatedHttpStatus": unauth_status, "unauthenticatedRetcode": unauth_retcode,
            "unauthenticatedRejected": True, "authenticatedWebSocket": status == 101,
            "botIdentityMatches": identity_matches, "configuredGroupsJoined": allowed_joined,
            "configuredGroupOwnerVerified": owner_verified, "messagesSent": 0,
            "businessEnabled": channel["enabled"], "channelAdapter": "not_implemented"}, indent=2))
        return 0 if identity_matches and allowed_joined and owner_verified else 1
    finally:
        sock.close()


if __name__ == "__main__":
    raise SystemExit(main())
