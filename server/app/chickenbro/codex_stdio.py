"""Bounded, private App Server stdio protocol; never forwards provider envelopes."""

import base64
import binascii
import json
import os
import selectors
import time
from collections import deque

from server.app.chickenbro.stream import CodexStreamError

_MAX_LINE_BYTES = 1024 * 1024
_MAX_TEXT_CHARS = 262144
_BODY_METHODS = {"item/started", "item/completed", "item/agentMessage/delta", "item/reasoning/summaryTextDelta", "turn/completed", "thread/tokenUsage/updated"}
_APPROVAL_METHODS = {"item/commandExecution/requestApproval", "item/fileChange/requestApproval"}


FAILURE_KINDS = frozenset(('protocol_invalid', 'transport_eof', 'rpc_error',
    'upstream_error', 'turn_failed', 'final_missing'))


# Fixed names from the installed App Server ErrorNotification JSON schema.
# Never retain message, additionalDetails, misalignment instructions or raw envelopes.
UPSTREAM_KINDS = frozenset(('contextWindowExceeded', 'sessionBudgetExceeded',
    'usageLimitExceeded', 'rateLimitExceeded', 'serverOverloaded', 'cyberPolicy',
    'misalignmentPolicyViolation', 'internalServerError', 'unauthorized', 'badRequest',
    'threadRollbackFailed', 'sandboxError', 'other', 'httpConnectionFailed',
    'responseStreamConnectionFailed', 'responseStreamDisconnected',
    'responseTooManyFailedAttempts', 'activeTurnNotSteerable', 'unknown'))


def clean_token_usage(value):
    total=value.get('total') if isinstance(value,dict) else None
    keys=('inputTokens','cachedInputTokens','outputTokens','reasoningOutputTokens','totalTokens')
    if not isinstance(total,dict) or not all(type(total.get(k)) is int and 0<=total[k]<=10**12 for k in keys):
        return None
    return {k:total[k] for k in keys}


def invalid(kind='protocol_invalid', upstream=None):
    error = CodexStreamError("CODEX_OUTPUT_INVALID")
    error.failure_kind = kind if kind in FAILURE_KINDS else 'protocol_invalid'
    if kind in ('upstream_error', 'turn_failed', 'rpc_error'):
        info = upstream.get('codexErrorInfo') if isinstance(upstream, dict) else None
        name = info if isinstance(info, str) else next(iter(info)) if isinstance(info, dict) and len(info) == 1 else None
        error.upstream_kind = name if name in UPSTREAM_KINDS else 'unknown'
        if error.upstream_kind in ('cyberPolicy', 'misalignmentPolicyViolation'):
            error.code = 'CODEX_REQUEST_REJECTED'
        detail = info.get(name) if isinstance(info, dict) else None
        status = detail.get('httpStatusCode') if isinstance(detail, dict) else None
        if type(status) is int and 100 <= status <= 599:
            error.upstream_http_status = status
    return error


def validate_images(images):
    # Only normalized, server-owned image bytes may cross the model boundary.
    # Remote URLs and local paths must never trigger provider-side fetches.
    if not isinstance(images, (list, tuple)) or len(images) > 9:
        raise invalid()
    for url in images:
        if not isinstance(url, str) or len(url) > 7 * 1024 * 1024:
            raise invalid()
        header, separator, payload = url.partition(',')
        if not separator or header not in {'data:image/png;base64', 'data:image/jpeg;base64'} or not payload:
            raise invalid()
        try:
            if len(base64.b64decode(payload, validate=True)) > 5 * 1024 * 1024:
                raise invalid()
        except (ValueError, binascii.Error):
            raise invalid() from None
    return tuple(images)


def read_messages(process, deadline, max_line_bytes=_MAX_LINE_BYTES):
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
                    raise invalid('transport_eof')
                buffered += chunk
                if len(buffered) > max_line_bytes:
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
        self.deadline = deadline
        self.messages = read_messages(process, deadline)
        self.deferred = deque()
        self.thread_id = None
        self.turn_id = None
        self.items = {}
        self.final_id = None
        self.final_text = None
        self.token_usage = None

    def send(self, message):
        payload = (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")
        source = self.process.stdin
        if source is None:
            raise invalid()
        payload = memoryview(payload)
        try:
            descriptor = source.fileno()
        except (OSError, ValueError, AttributeError):
            # In-memory test transports have no OS pipe to wait on.
            while payload:
                if time.monotonic() >= self.deadline:
                    raise CodexStreamError("CODEX_TIMEOUT")
                written = source.write(payload)
                if not written:
                    raise invalid()
                payload = payload[written:]
            source.flush()
            return

        # A runtime that stops consuming stdin must not hold an account run
        # forever. Nonblocking writes also bound stdout/stdin backpressure cycles.
        was_blocking = os.get_blocking(descriptor)
        selector = selectors.DefaultSelector()
        try:
            os.set_blocking(descriptor, False)
            selector.register(descriptor, selectors.EVENT_WRITE)
            while payload:
                remaining = self.deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise CodexStreamError("CODEX_TIMEOUT")
                try:
                    written = os.write(descriptor, payload[:65536])
                except BlockingIOError:
                    continue
                if not written:
                    raise invalid()
                payload = payload[written:]
        finally:
            selector.close()
            try:
                os.set_blocking(descriptor, was_blocking)
            except OSError:
                pass

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
                    or params.get("threadId") != self.thread_id or params.get("turnId") != self.turn_id):
                raise invalid()
            if params.get("willRetry") is not True:
                raise invalid('upstream_error', params.get('error'))

    def request(self, identity, method, params):
        self.send({"id": identity, "method": method, "params": params})
        for message in self.messages:
            self._check_request(message)
            if "id" in message:
                if type(message["id"]) is not int or message["id"] != identity:
                    raise invalid()
                if "error" in message:
                    raise invalid('rpc_error', message.get('error'))
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

    def stream(self, *, prompt, job_dir, developer_instructions, profile_config, images=()):
        try:
            images = validate_images(images)
            # App Server may echo all input images in a single userMessage line.
            self.messages.close()
            self.messages = read_messages(
                self.process, self.deadline, _MAX_LINE_BYTES + sum(len(url) for url in images))
            self.request(1, "initialize", {"clientInfo": {"name": "chickenbro_chat", "version": "1.0"}})
            self.send({"method": "initialized", "params": {}})
            result = self.request(2, "thread/start", {
                "cwd": str(job_dir), "ephemeral": True, "sandbox": "read-only", "approvalPolicy": "never",
                "developerInstructions": developer_instructions,
                "config": profile_config,
            })
            self.thread_id = self._id(result.get("thread", {}).get("id"))
            result = self.request(3, "turn/start", {
                "threadId": self.thread_id, "summary": "auto", "input": [
                    {"type": "text", "text": prompt},
                    *[{"type": "image", "url": url} for url in images],
                ],
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
                if method == 'thread/tokenUsage/updated':
                    if params.get('turnId') == self.turn_id:
                        self.token_usage = clean_token_usage(params.get('tokenUsage')) or self.token_usage
                    continue
                if method == "turn/completed":
                    turn = params.get("turn", {})
                    if turn.get("id") != self.turn_id:
                        raise invalid()
                    if turn.get("status") != "completed" or turn.get("error") is not None:
                        raise invalid('turn_failed', turn.get('error'))
                    if not self.final_text:
                        raise invalid('final_missing')
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
