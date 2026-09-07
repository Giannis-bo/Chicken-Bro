"""Bounded, private App Server stdio protocol; never forwards provider envelopes."""

import json
import os
import selectors
import time
from collections import deque

from server.app.chickenbro.stream import CodexStreamError

_MAX_LINE_BYTES = 1024 * 1024
_MAX_TEXT_CHARS = 262144
_BODY_METHODS = {"item/started", "item/completed", "item/agentMessage/delta", "item/reasoning/summaryTextDelta", "turn/completed"}
_APPROVAL_METHODS = {"item/commandExecution/requestApproval", "item/fileChange/requestApproval"}


def invalid():
    return CodexStreamError("CODEX_OUTPUT_INVALID")


def read_messages(process, deadline):
    """Read raw bytes so buffered readline cannot strand already-read JSON lines."""
    source = process.stdout
    if source is None:
        raise invalid()
    selector = None
    try:
        selector = selectors.DefaultSelector()
        selector.register(source, selectors.EVENT_READ)
    except (OSError, ValueError, AttributeError):
        if selector is not None:
            selector.close()
        selector = None
    buffered = b""
    try:
        while True:
            if time.monotonic() >= deadline:
                raise CodexStreamError("CODEX_TIMEOUT")
            if b"\n" not in buffered:
                if selector is not None:
                    if not selector.select(max(0, deadline - time.monotonic())):
                        raise CodexStreamError("CODEX_TIMEOUT")
                    chunk = os.read(source.fileno(), 65536)
                else:
                    # Only in-memory test streams lack a file descriptor on the Linux runtime.
                    chunk = source.read(65536)
                if not chunk:
                    raise invalid()
                buffered += chunk
                if len(buffered) > _MAX_LINE_BYTES:
                    raise invalid()
                continue
            line, buffered = buffered.split(b"\n", 1)
            try:
                value = json.loads(line)
            except (ValueError, UnicodeError):
                raise invalid() from None
            if not isinstance(value, dict):
                raise invalid()
            yield value
    finally:
        if selector is not None:
            selector.close()


class CodexStdioSession:
    def __init__(self, process, deadline):
        self.process = process
        self.messages = read_messages(process, deadline)
        self.deferred = deque()
        self.thread_id = None
        self.turn_id = None
        self.items = {}
        self.final_id = None
        self.final_text = None

    def send(self, message):
        payload = (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")
        source = self.process.stdin
        if source is None:
            raise invalid()
        # FileIO writes can be partial, especially for a large conversation prompt.
        while payload:
            written = source.write(payload)
            if not written:
                raise invalid()
            payload = payload[written:]
        source.flush()

    def _check_request(self, message):
        if "id" in message and "method" in message:
            identity = message["id"]
            if not isinstance(identity, (str, int)) or isinstance(identity, bool):
                raise invalid()
            if message["method"] in _APPROVAL_METHODS:
                self.send({"id": identity, "result": {"decision": "cancel"}})
            else:
                self.send({"id": identity, "error": {"code": -32601, "message": "Unsupported request"}})
            raise invalid()
        if message.get("method") == "error":
            params = message.get("params")
            if (not isinstance(params, dict) or self.thread_id is None or self.turn_id is None
                    or params.get("threadId") != self.thread_id or params.get("turnId") != self.turn_id
                    or params.get("willRetry") is not True):
                raise invalid()

    def request(self, identity, method, params):
        self.send({"id": identity, "method": method, "params": params})
        for message in self.messages:
            self._check_request(message)
            if "id" in message:
                if type(message["id"]) is not int or message["id"] != identity or "error" in message:
                    raise invalid()
                result = message.get("result")
                if not isinstance(result, dict):
                    raise invalid()
                return result
            if message.get("method") in _BODY_METHODS:
                # Notifications may precede turn/start's response on stdio.
                if identity != 3 or len(self.deferred) >= 128:
                    raise invalid()
                self.deferred.append(message)
        raise invalid()

    def stream(self, *, prompt, job_dir, developer_instructions, profile_config):
        try:
            self.request(1, "initialize", {"clientInfo": {"name": "chickenbro_chat", "version": "1.0"}})
            self.send({"method": "initialized", "params": {}})
            result = self.request(2, "thread/start", {
                "cwd": str(job_dir), "ephemeral": True, "sandbox": "read-only", "approvalPolicy": "never",
                "developerInstructions": developer_instructions,
                "config": profile_config,
            })
            self.thread_id = self._id(result.get("thread", {}).get("id"))
            result = self.request(3, "turn/start", {
                "threadId": self.thread_id, "summary": "auto", "input": [{"type": "text", "text": prompt}],
            })
            self.turn_id = self._id(result.get("turn", {}).get("id"))
            while True:
                message = self.deferred.popleft() if self.deferred else next(self.messages)
                self._check_request(message)
                if "id" in message:
                    raise invalid()
                method = message.get("method")
                if method not in _BODY_METHODS:
                    continue
                params = message.get("params")
                if not isinstance(params, dict) or params.get("threadId") != self.thread_id:
                    raise invalid()
                if method == "turn/completed":
                    turn = params.get("turn", {})
                    if (turn.get("id") != self.turn_id or turn.get("status") != "completed"
                            or turn.get("error") is not None or not self.final_text):
                        raise invalid()
                    yield {"type": "completed", "text": self.final_text}
                    return
                if params.get("turnId") != self.turn_id:
                    raise invalid()
                event = self._item_event(method, params)
                if event is not None:
                    yield event
        except (StopIteration, KeyError, AttributeError, TypeError):
            raise invalid() from None
        finally:
            self.messages.close()

    @staticmethod
    def _id(value):
        if not isinstance(value, str) or not value or len(value) > 256:
            raise invalid()
        return value

    def _item_event(self, method, params):
        # Only the explicitly public summary channel is forwarded. Raw reasoning,
        # commentary, commands, tool arguments and tool results stay private.
        if method == "item/reasoning/summaryTextDelta":
            state = self.items.get(self._id(params.get("itemId")))
            text = params.get("delta")
            if state is None or state["done"] or state["phase"] != "public_summary" or not isinstance(text, str):
                raise invalid()
            text = text[:max(0, 16000 - len(state["text"]))]
            state["text"] += text
            return {"type": "progress", "text": text} if text else None
        if method == "item/agentMessage/delta":
            identity = self._id(params.get("itemId"))
            state = self.items.get(identity)
            text = params.get("delta")
            if state is None or state["done"] or not isinstance(text, str):
                raise invalid()
            if state["phase"] != "final_answer":
                return None
            state["text"] += text
            if len(state["text"]) > _MAX_TEXT_CHARS:
                raise invalid()
            return {"type": "delta", "text": text} if text else None
        item = params.get("item")
        if not isinstance(item, dict):
            raise invalid()
        if item.get("type") == "reasoning":
            identity = self._id(item.get("id"))
            if method == "item/started":
                if identity in self.items or len(self.items) >= 256:
                    raise invalid()
                self.items[identity] = {"phase": "public_summary", "text": "", "done": False}
            else:
                state = self.items.get(identity)
                if state is None or state["done"]:
                    raise invalid()
                state["done"] = True
            return None
        if item.get("type") != "agentMessage":
            return None
        identity = self._id(item.get("id"))
        phase = item.get("phase")
        if method == "item/started":
            if identity in self.items or len(self.items) >= 256:
                raise invalid()
            if phase == "final_answer":
                if self.final_id is not None:
                    raise invalid()
                self.final_id = identity
            self.items[identity] = {"phase": phase, "text": "", "done": False}
            return None
        state = self.items.get(identity)
        if state is None or state["done"]:
            raise invalid()
        state["done"] = True
        if phase != "final_answer":
            if state["phase"] == "final_answer":
                raise invalid()
            return None
        if state["phase"] not in {None, "final_answer"} or self.final_id not in {None, identity}:
            raise invalid()
        text = item.get("text")
        if not isinstance(text, str) or not text.strip() or len(text) > _MAX_TEXT_CHARS:
            raise invalid()
        # The application persists concatenated deltas; never silently accept a rewrite.
        if state["text"] and text != state["text"]:
            raise invalid()
        self.final_id, self.final_text = identity, text
        return None
