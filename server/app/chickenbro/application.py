import base64
import json
import logging
import re
from collections.abc import Callable, Iterator, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from threading import BoundedSemaphore
from typing import Any
from uuid import UUID, uuid4, uuid5

from server.app.chickenbro.codex_adapter import CodexChatPort, CodexTimeout, CodexUnavailable
from server.app.chickenbro.delivery import BackgroundDelivery, DeliveryCapacity
from server.app.chickenbro.domain import ConversationUnavailable, ConversationBusy, ChatAccountBusy, AgentRunStatus, Conversation, ConversationStatus
from server.app.chickenbro.stream import ChatEvent, CodexStreamError
from server.app.identity.domain import Principal

_LOG = logging.getLogger(__name__)

class ChatApplicationError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


CHAT_TIMEOUT_SECONDS = 480
CHAT_STALE_RUN_GRACE_SECONDS = 60
CHAT_CONVERSATION_NAMESPACE = UUID("83b4eebf-fcf3-51ea-b9ff-d676d1957f48")
_IDEMPOTENCY_KEY = re.compile(r"[A-Za-z0-9._~-]{8,128}\Z")


@dataclass(frozen=True)
class ConversationPage:
    items: tuple[Conversation, ...]
    next_cursor: str | None


def _value(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _as_uuid(value: Any) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _utc(clock: Callable[[], datetime]) -> datetime:
    value = clock()
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _encode_conversation_cursor(row: Any) -> str:
    updated_at = _value(row, "updated_at")
    if not isinstance(updated_at, datetime):
        raise ChatApplicationError("INVALID_CURSOR", "conversation cursor cannot be encoded")
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    payload = {
        "updatedAt": updated_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "id": str(_as_uuid(_value(row, "id"))),
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    return encoded.rstrip(b"=").decode("ascii")


def _decode_conversation_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        if not isinstance(cursor, str) or not cursor or len(cursor) > 1024:
            raise ValueError("invalid cursor envelope")
        padding = "=" * (-len(cursor) % 4)
        raw = base64.b64decode(
            cursor + padding,
            altchars=b"-_",
            validate=True,
        )
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict) or set(payload) != {"updatedAt", "id"}:
            raise ValueError("invalid cursor payload")
        raw_updated_at = payload["updatedAt"]
        if not isinstance(raw_updated_at, str):
            raise ValueError("invalid cursor timestamp")
        updated_at = datetime.fromisoformat(raw_updated_at.replace("Z", "+00:00"))
        if updated_at.tzinfo is None:
            raise ValueError("cursor timestamp must be timezone-aware")
        return updated_at.astimezone(timezone.utc), UUID(str(payload["id"]))
    except (UnicodeError, ValueError, TypeError) as error:
        raise ChatApplicationError("INVALID_CURSOR", "conversation cursor is invalid") from error


def _bounded_idempotency_key(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ChatApplicationError("IDEMPOTENCY_KEY_REQUIRED", "idempotency key is required")
    if not _IDEMPOTENCY_KEY.fullmatch(value):
        raise ChatApplicationError("IDEMPOTENCY_KEY_INVALID", "idempotency key is invalid")
    return value


class ChatApplication:
    def __init__(
        self,
        *,
        repository: Any,
        codex: CodexChatPort,
        clock: Callable[[], datetime] | None = None,
        timeout_seconds: int = CHAT_TIMEOUT_SECONDS,
        stale_run_grace_seconds: int = CHAT_STALE_RUN_GRACE_SECONDS,
        max_message_chars: int = 4000,
        max_output_chars: int = 8000,
    ):
        self._generation_capacity = BoundedSemaphore(8)
        self._repository = repository
        self._codex = codex
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._timeout_seconds = max(1, timeout_seconds)
        self._stale_run_grace_seconds = max(1, stale_run_grace_seconds)
        self._max_message_chars = max(1, max_message_chars)
        self._max_output_chars = max(1, max_output_chars)

    def start_delivery(
        self,
        principal: Principal,
        conversation_id: UUID,
        content: str,
        *,
        client_message_id: str | None,
        idempotency_key: str,
    ) -> Iterator[ChatEvent]:
        """Admit synchronously, then generate independently of the HTTP subscriber."""
        if getattr(self._repository, "durable", False):
            from server.app.chickenbro.durable import DurableSubscription
            source = self.stream_message(principal, conversation_id, content,
                client_message_id=client_message_id, idempotency_key=idempotency_key)
            first = next(source)
            executions = self._repository.executions
            if not executions.contains(principal.user_id,first.run_id):
                def legacy_replay():
                    try:
                        yield first
                        yield from source
                    finally:
                        source.close()
                return legacy_replay()
            source.close()
            return DurableSubscription(first, executions, principal.user_id)
        try:
            return BackgroundDelivery(
                self.stream_message(principal, conversation_id, content,
                                    client_message_id=client_message_id, idempotency_key=idempotency_key),
                capacity=self._generation_capacity,
            )
        except DeliveryCapacity:
            raise ChatApplicationError("CODEX_UNAVAILABLE", "鸡哥当前请求较多，请稍后再试。") from None

    def create_conversation(
        self,
        principal: Principal,
        title: str = "炸鸡队长对话",
        *,
        idempotency_key: str,
    ) -> Any:
        bounded_title = str(title or "炸鸡队长对话").strip()[:256] or "炸鸡队长对话"
        key = _bounded_idempotency_key(idempotency_key)
        conversation_id = uuid5(
            CHAT_CONVERSATION_NAMESPACE,
            f"{principal.user_id}:{key}",
        )
        conversation = self._repository.create_conversation(
            principal.user_id,
            conversation_id,
            bounded_title,
            _utc(self._clock),
        )
        if _value(conversation, "status") not in {ConversationStatus.ACTIVE, "active"}:
            raise ChatApplicationError("CONVERSATION_NOT_FOUND", "conversation not found")
        if str(_value(conversation, "title", "")) != bounded_title:
            raise ChatApplicationError(
                "IDEMPOTENCY_CONFLICT",
                "idempotency identity belongs to a different conversation request",
            )
        return conversation

    def delete_conversation(self, principal: Principal, conversation_id: UUID) -> None:
        self._recover_stale_agent_runs(principal, conversation_id)
        try:
            self._repository.archive_conversation(principal.user_id, conversation_id)
        except ConversationUnavailable as error:
            raise ChatApplicationError("CONVERSATION_NOT_FOUND", "conversation not found") from error
        except ConversationBusy as error:
            raise ChatApplicationError("CHAT_CONVERSATION_BUSY", "鸡哥正在回复此会话，请等待回复结束后再删除。") from error

    def list_conversations(
        self,
        principal: Principal,
        cursor: str | None = None,
        limit: int = 20,
    ) -> ConversationPage:
        bounded_limit = min(max(int(limit), 1), 50)
        boundary = _decode_conversation_cursor(cursor) if cursor else None
        rows = self._repository.list_conversations(
            principal.user_id,
            boundary,
            bounded_limit + 1,
        )
        items = tuple(rows[:bounded_limit])
        next_cursor = (
            _encode_conversation_cursor(items[-1])
            if len(rows) > bounded_limit and items
            else None
        )
        return ConversationPage(items=items, next_cursor=next_cursor)

    def load_conversation(self, principal: Principal, conversation_id: UUID) -> Any:
        if getattr(self._repository, 'durable', False):
            self._recover_stale_agent_runs(principal, conversation_id)
        conversation = self._repository.get_conversation(principal.user_id, conversation_id)
        if conversation is None:
            raise ChatApplicationError("CONVERSATION_NOT_FOUND", "conversation not found")
        messages = [dict(row) if isinstance(row, dict) else asdict(row)
                    for row in self._repository.list_messages(principal.user_id, conversation_id)]
        by_id = {str(row["id"]): row for row in messages}
        for run in self._repository.list_run_presentations(principal.user_id, conversation_id):
            status = _value(run, "status")
            if status not in {"succeeded", "failed"}:
                continue
            reply = by_id.get(str(_value(run, "assistant_message_id")))
            finished = _value(run, "finished_at")
            if reply is None and status == "failed" and finished is not None:
                reply = {"id": _value(run, "id"), "role": "assistant", "content": "",
                         "created_at": finished}
                messages.append(reply)
            if reply is not None:
                if status == "succeeded":
                    reply["resolved"] = _value(run, "resolved")
                reply.update(progress_text=_value(run, "public_progress", ""),
                             reply_status="completed" if status == "succeeded" else "failed",
                             completed_at=finished,
                             duration_ms=self._timing(run, finished).get("duration_ms"))
        messages.sort(key=lambda row: row["created_at"])
        return {"conversation": conversation, "messages": messages}

    def set_feedback(self, principal: Principal, conversation_id: UUID, message_id: UUID,
                     resolved: bool) -> bool:
        if type(resolved) is not bool:
            raise ChatApplicationError("FEEDBACK_INVALID", "请选择已解决或未解决")
        saved = self._repository.set_feedback(principal.user_id, conversation_id, message_id,
                                              resolved, self._clock())
        if saved is None:
            raise ChatApplicationError("FEEDBACK_MESSAGE_NOT_FOUND", "这条回答已不可用，请刷新会话")
        if saved != resolved:
            raise ChatApplicationError("FEEDBACK_ALREADY_SUBMITTED", "评价已确认，不能修改")
        return saved

    @staticmethod
    def _timing(run: Any, finished: datetime | None) -> dict[str, Any]:
        started = _value(run, "started_at")
        if not isinstance(started, datetime) or not isinstance(finished, datetime):
            return {}
        return {"completed_at": finished.isoformat(),
                "duration_ms": max(0, int((finished - started).total_seconds() * 1000))}

    def _find_idempotent_run(
        self,
        principal: Principal,
        conversation_id: UUID,
        message: str,
        client_message_id: str | None,
        idempotency_key: str,
    ) -> Any | None:
        existing_message = None
        if client_message_id:
            existing_message = self._repository.get_message_by_client_id(
                principal.user_id,
                client_message_id,
            )
        existing_run = self._repository.get_run_by_idempotency(
            principal.user_id,
            idempotency_key,
        )
        if existing_message is None and existing_run is None:
            return None

        run = existing_run
        if run is None and existing_message is not None:
            run = self._repository.get_run_for_user_message(
                principal.user_id,
                _as_uuid(_value(existing_message, "id")),
            )
        if run is None:
            raise ChatApplicationError(
                "CHAT_PERSISTENCE_FAILED",
                "persisted message has no agent run",
            )

        persisted_message = existing_message
        if persisted_message is None:
            persisted_message = next(
                (
                    item
                    for item in self._repository.list_messages(
                        principal.user_id,
                        _as_uuid(_value(run, "conversation_id")),
                    )
                    if _as_uuid(_value(item, "id"))
                    == _as_uuid(_value(run, "user_message_id"))
                ),
                None,
            )
        if (
            persisted_message is None
            or _as_uuid(_value(run, "user_message_id"))
            != _as_uuid(_value(persisted_message, "id"))
            or _as_uuid(_value(persisted_message, "conversation_id")) != conversation_id
            or str(_value(persisted_message, "content", "")) != message
            or str(_value(persisted_message, "client_message_id", "") or "")
            != str(client_message_id or "")
            or str(_value(run, "idempotency_key", "")) != idempotency_key
        ):
            raise ChatApplicationError(
                "IDEMPOTENCY_CONFLICT",
                "idempotency identity belongs to a different request",
            )
        return run

    def stream_message(
        self,
        principal: Principal,
        conversation_id: UUID,
        content: str,
        *,
        client_message_id: str | None,
        idempotency_key: str,
    ) -> Iterator[ChatEvent]:
        conversation = self._repository.get_conversation(principal.user_id, conversation_id)
        if conversation is None or _value(conversation, "status") not in {ConversationStatus.ACTIVE, "active"}:
            raise ChatApplicationError("CONVERSATION_NOT_FOUND", "conversation not found")
        message = str(content or "").strip()
        if not message:
            raise ChatApplicationError("MESSAGE_REQUIRED", "message is required")
        if len(message) > self._max_message_chars:
            raise ChatApplicationError("MESSAGE_TOO_LONG", "message is too long")
        idempotency_key = _bounded_idempotency_key(idempotency_key)

        if client_message_id is not None:
            client_message_id = str(client_message_id).strip()
            if not client_message_id or len(client_message_id) > 128:
                raise ChatApplicationError("CLIENT_MESSAGE_ID_INVALID", "client message id is invalid")
        self._recover_stale_agent_runs(principal, None)
        existing_run = self._find_idempotent_run(
            principal,
            conversation_id,
            message,
            client_message_id,
            idempotency_key,
        )
        if existing_run is not None:
            run = existing_run
            yield from self._replay_agent_run(principal, run)
            return

        now = _utc(self._clock)
        runtime_revision = str(getattr(self._codex, "runtime_revision", "") or "").strip()
        if not 1 <= len(runtime_revision) <= 160:
            raise ChatApplicationError(
                "CODEX_UNAVAILABLE",
                "Codex runtime revision is not configured",
            )
        try:
            _user_message, run = self._repository.start_message_run(
                principal.user_id,
                conversation_id,
                message,
                client_message_id,
                idempotency_key,
                now,
                runtime_revision=runtime_revision,
            )
        except Exception as error:
            from server.app.chickenbro.durable import ChatQueueFull
            if isinstance(error, ChatQueueFull):
                raise ChatApplicationError('CODEX_UNAVAILABLE','鸡哥当前请求较多，请稍后再试。') from error
            try:
                raced_run = self._find_idempotent_run(
                    principal,
                    conversation_id,
                    message,
                    client_message_id,
                    idempotency_key,
                )
            except ChatApplicationError:
                raise
            except Exception:
                raced_run = None
            if raced_run is not None:
                yield from self._replay_agent_run(principal, raced_run)
                return
            if isinstance(error, ConversationUnavailable):
                raise ChatApplicationError("CONVERSATION_NOT_FOUND", "conversation not found") from error
            if isinstance(error, ChatAccountBusy):
                raise ChatApplicationError(
                    "CHAT_ACCOUNT_BUSY",
                    "鸡哥正在回复你的另一条消息，请等待回复结束后再发送。",
                ) from error
            raise ChatApplicationError(
                "CHAT_PERSISTENCE_FAILED",
                "user message and agent run could not be persisted",
            ) from error
        request_id = str(uuid4())
        run_id = str(_as_uuid(_value(run, "id")))
        sequence = 1
        try:
            yield ChatEvent(
                "started",
                request_id,
                str(conversation_id),
                sequence,
                run_id=run_id,
            )
        except GeneratorExit:
            if not getattr(self._repository, "durable", False):
                self._cancel_run(principal, run)
            raise
        if getattr(self._repository, "durable", False):
            return
        yield from self.execute_run(principal, run, request_id=request_id)

    def execute_run(self, principal: Principal, run: Any, *, request_id: str | None = None):
        conversation_id = _as_uuid(_value(run, "conversation_id"))
        request_id = request_id or str(uuid4())
        run_id = str(_value(run, "id"))
        sequence = 1
        progress_chars = 0
        answer_parts: list[str] = []
        completed = False
        terminal_persisted = False
        try:
            history = self._repository.list_messages(principal.user_id, conversation_id)
            prompt = self._prompt(history, "")
            scoped_stream = getattr(self._codex, "stream_for_chat", None)
            if callable(scoped_stream):
                codex_events = scoped_stream(principal=principal, conversation_id=conversation_id,
                    run_id=_as_uuid(_value(run, "id")), prompt=prompt, timeout_seconds=self._timeout_seconds)
            else:
                codex_events = self._codex.stream(prompt=prompt, timeout_seconds=self._timeout_seconds)
            try:
                for raw_event in codex_events:
                    event_type = str(_value(raw_event, "type", "")).strip().lower()
                    if event_type == "progress":
                        text = _value(raw_event, "text", "")
                        if not isinstance(text, str):
                            raise CodexStreamError("CODEX_OUTPUT_INVALID")
                        text = text[:max(0, 16000 - progress_chars)]
                        for offset in range(0, len(text), 8000):
                            chunk = text[offset:offset + 8000]
                            self._repository.append_public_progress(principal.user_id,
                                _as_uuid(_value(run, "id")), chunk)
                            progress_chars += len(chunk)
                            sequence += 1
                            yield ChatEvent("progress", request_id, str(conversation_id), sequence,
                                            run_id=run_id, text=chunk)
                    elif event_type in {"delta", "item.delta", "message.delta"}:
                        delta = str(_value(raw_event, "text", "") or _value(raw_event, "delta", ""))
                        if not delta:
                            continue
                        if sum(len(part) for part in answer_parts) + len(delta) > self._max_output_chars:
                            raise CodexStreamError("CODEX_OUTPUT_INVALID")
                        answer_parts.append(delta)
                        sequence += 1
                        yield ChatEvent(
                            "delta",
                            request_id,
                            str(conversation_id),
                            sequence,
                            run_id=run_id,
                            text=delta,
                        )
                    elif event_type in {"completed", "item.completed", "turn.completed"}:
                        completed = True
                        final_text = str(_value(raw_event, "text", "") or "").strip()
                        if final_text and not answer_parts:
                            if len(final_text) > self._max_output_chars:
                                raise CodexStreamError("CODEX_OUTPUT_INVALID")
                            answer_parts.append(final_text)
                        break
                    elif event_type in {"failed", "turn.failed", "error"}:
                        raise CodexStreamError("CODEX_OUTPUT_INVALID")
            finally:
                close = getattr(codex_events, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        pass
            if not completed or not "".join(answer_parts).strip():
                raise CodexStreamError("CODEX_OUTPUT_INVALID")
            answer = "".join(answer_parts).strip()
            finished = _utc(self._clock)
            try:
                self._repository.complete_run_with_assistant(
                    principal.user_id,
                    conversation_id,
                    _as_uuid(_value(run, "id")),
                    answer,
                    finished,
                )
            except Exception:
                yield from self._fail_run(
                    principal,
                    run,
                    request_id,
                    conversation_id,
                    sequence,
                    CodexStreamError("CHAT_PERSISTENCE_FAILED"),
                )
                return
            terminal_persisted = True
            sequence += 1
            yield ChatEvent(
                "completed",
                request_id,
                str(conversation_id),
                sequence,
                run_id=run_id,
                text=answer,
                **self._timing(run, finished),
            )
        except GeneratorExit:
            if not terminal_persisted:
                self._cancel_run(principal, run)
            raise
        except CodexUnavailable as error:
            yield from self._fail_run(principal, run, request_id, conversation_id, sequence, error)
        except CodexTimeout as error:
            yield from self._fail_run(principal, run, request_id, conversation_id, sequence, error)
        except CodexStreamError as error:
            yield from self._fail_run(principal, run, request_id, conversation_id, sequence, error)
        except TimeoutError:
            yield from self._fail_run(
                principal,
                run,
                request_id,
                conversation_id,
                sequence,
                CodexTimeout(),
            )
        except Exception as error:
            _LOG.error("chat_run_failed run_id=%s reason=application_exception exception_type=%s", run_id, type(error).__name__)
            yield from self._fail_run(
                principal,
                run,
                request_id,
                conversation_id,
                sequence,
                CodexStreamError("CODEX_EXECUTION_FAILED"),
            )

    def _recover_stale_agent_runs(
        self,
        principal: Principal,
        conversation_id: UUID | None,
    ) -> None:
        now = _utc(self._clock)
        stale_before = now - timedelta(
            seconds=self._timeout_seconds + self._stale_run_grace_seconds,
        )
        try:
            if getattr(self._repository, 'durable', False):
                self._repository.executions.recover(principal.user_id)
            recovered = self._repository.recover_stale_agent_runs(
                principal.user_id,
                conversation_id,
                stale_before,
                now,
            )
            if recovered:
                _LOG.warning("chat_runs_recovered reason=stale_or_process_interrupted count=%s", recovered)
        except Exception as error:
            raise ChatApplicationError(
                "CHAT_PERSISTENCE_FAILED",
                "stale agent runs could not be recovered",
            ) from error

    def _cancel_run(self, principal: Principal, run: Any) -> None:
        _LOG.warning("chat_run_cancelled run_id=%s reason=generation_iterator_closed", _value(run, "id"))
        try:
            self._repository.finish_agent_run(
                principal.user_id,
                _as_uuid(_value(run, "id")),
                AgentRunStatus.FAILED,
                None,
                "CODEX_EXECUTION_FAILED",
                _utc(self._clock),
            )
        except Exception:
            return

    def _fail_run(
        self,
        principal: Principal,
        run: Any,
        request_id: str,
        conversation_id: UUID,
        sequence: int,
        error: CodexStreamError,
    ) -> Iterator[ChatEvent]:
        _LOG.warning("chat_run_failed run_id=%s reason=%s", _value(run, "id"), error.code)
        finished = _utc(self._clock)
        self._repository.finish_agent_run(
            principal.user_id,
            _as_uuid(_value(run, "id")),
            AgentRunStatus.FAILED,
            None,
            error.code,
            finished,
        )
        yield ChatEvent(
            "failed",
            request_id,
            str(conversation_id),
            sequence + 1,
            run_id=str(_as_uuid(_value(run, "id"))),
            error_code=error.code,
            retryable=error.code in {"CODEX_UNAVAILABLE", "CODEX_TIMEOUT", "CODEX_EXECUTION_FAILED"},
            **self._timing(run, finished),
        )

    def _replay_agent_run(
        self,
        principal: Principal,
        run: Any,
    ) -> Iterator[ChatEvent]:
        run_id = str(_as_uuid(_value(run, "id")))
        conversation_id = str(_as_uuid(_value(run, "conversation_id")))
        status = _value(run, "status")
        status_value = status.value if isinstance(status, AgentRunStatus) else str(status)
        if status_value == AgentRunStatus.STREAMING.value:
            raise ChatApplicationError("CHAT_RUN_IN_PROGRESS", "chat run is still in progress")
        request_id = str(uuid4())
        yield ChatEvent(
            "started",
            request_id,
            conversation_id,
            1,
            run_id=run_id,
        )
        sequence = 1
        presentations = self._repository.list_run_presentations(principal.user_id, _as_uuid(conversation_id))
        presentation = next((row for row in presentations if str(_value(row, "id")) == run_id), run)
        progress = _value(presentation, "public_progress", "")
        for offset in range(0, len(progress), 8000):
            sequence += 1
            yield ChatEvent("progress", request_id, conversation_id, sequence,
                            run_id=run_id, text=progress[offset:offset + 8000])
        timing = self._timing(run, _value(run, "finished_at"))
        if status_value == AgentRunStatus.FAILED.value:
            error_code = str(_value(run, "public_error_code", "") or "CODEX_OUTPUT_INVALID")
            yield ChatEvent(
                "failed",
                request_id,
                conversation_id,
                sequence + 1,
                run_id=run_id,
                **timing,
                error_code=error_code,
                retryable=error_code in {"CODEX_UNAVAILABLE", "CODEX_TIMEOUT", "CODEX_EXECUTION_FAILED"},
            )
            return
        if status_value != AgentRunStatus.SUCCEEDED.value:
            raise ChatApplicationError("CHAT_RUN_NOT_REPLAYABLE", "chat run cannot be replayed")
        assistant_message_id = _value(run, "assistant_message_id")
        messages = self._repository.list_messages(
            principal.user_id,
            _as_uuid(_value(run, "conversation_id")),
        )
        assistant = next(
            (
                item for item in messages
                if assistant_message_id is not None
                and _as_uuid(_value(item, "id")) == _as_uuid(assistant_message_id)
            ),
            None,
        )
        if assistant is None:
            raise ChatApplicationError(
                "CHAT_PERSISTENCE_FAILED",
                "completed run has no persisted assistant message",
            )
        yield ChatEvent(
            "completed",
            request_id,
            conversation_id,
            sequence + 1,
            run_id=run_id,
            text=str(_value(assistant, "content", "")),
            **timing,
        )

    @staticmethod
    def _prompt(history: Sequence[Any], message: str) -> str:
        rows = []
        for item in list(history)[-20:]:
            role_value = _value(item, "role", "user")
            role = str(getattr(role_value, "value", role_value))
            content = str(_value(item, "content", ""))[:4000]
            if content:
                rows.append({"role": role, "content": content})
        return json.dumps({"messages": rows}, ensure_ascii=False)


__all__ = (
    "ChatApplication",
    "ChatApplicationError",
    "ConversationPage",
)
