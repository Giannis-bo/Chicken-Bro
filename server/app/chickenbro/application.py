import base64
import json
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from server.app.chickenbro.codex_adapter import CodexChatPort, CodexTimeout, CodexUnavailable
from server.app.chickenbro.domain import AgentRunStatus, Conversation, ConversationStatus
from server.app.chickenbro.stream import ChatEvent, CodexStreamError
from server.app.identity.domain import Principal


class ChatApplicationError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


CHAT_TIMEOUT_SECONDS = 180


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


class ChatApplication:
    def __init__(
        self,
        *,
        repository: Any,
        codex: CodexChatPort,
        clock: Callable[[], datetime] | None = None,
        timeout_seconds: int = CHAT_TIMEOUT_SECONDS,
        max_message_chars: int = 4000,
        max_output_chars: int = 8000,
    ):
        self._repository = repository
        self._codex = codex
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._timeout_seconds = max(1, timeout_seconds)
        self._max_message_chars = max(1, max_message_chars)
        self._max_output_chars = max(1, max_output_chars)

    def create_conversation(self, principal: Principal, title: str = "炸鸡队长对话") -> Any:
        bounded_title = str(title or "炸鸡队长对话").strip()[:80] or "炸鸡队长对话"
        return self._repository.create_conversation(principal.user_id, bounded_title, _utc(self._clock))

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
        conversation = self._repository.get_conversation(principal.user_id, conversation_id)
        if conversation is None:
            raise ChatApplicationError("CONVERSATION_NOT_FOUND", "conversation not found")
        return {
            "conversation": conversation,
            "messages": self._repository.list_messages(principal.user_id, conversation_id),
        }

    def replay_run(
        self,
        principal: Principal,
        run_id: UUID,
    ) -> Iterator[ChatEvent]:
        run = self._repository.get_agent_run(principal.user_id, run_id)
        if run is None:
            raise ChatApplicationError("CHAT_RUN_NOT_FOUND", "chat run not found")
        yield from self._replay_agent_run(principal, run)

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
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise ChatApplicationError("IDEMPOTENCY_KEY_REQUIRED", "idempotency key is required")
        idempotency_key = idempotency_key.strip()
        if len(idempotency_key) > 128:
            raise ChatApplicationError("IDEMPOTENCY_KEY_INVALID", "idempotency key is invalid")

        if client_message_id is not None:
            client_message_id = str(client_message_id).strip()
            if not client_message_id or len(client_message_id) > 128:
                raise ChatApplicationError("CLIENT_MESSAGE_ID_INVALID", "client message id is invalid")
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
            raise ChatApplicationError(
                "CHAT_PERSISTENCE_FAILED",
                "user message and agent run could not be persisted",
            ) from error
        request_id = str(uuid4())
        run_id = str(_as_uuid(_value(run, "id")))
        sequence = 1
        yield ChatEvent(
            "started",
            request_id,
            str(conversation_id),
            sequence,
            run_id=run_id,
        )

        answer_parts: list[str] = []
        completed = False
        try:
            history = self._repository.list_messages(principal.user_id, conversation_id)
            prompt = self._prompt(history, message)
            for raw_event in self._codex.stream(prompt=prompt, timeout_seconds=self._timeout_seconds):
                event_type = str(_value(raw_event, "type", "")).strip().lower()
                if event_type in {"delta", "item.delta", "message.delta"}:
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
            if not completed or not "".join(answer_parts).strip():
                raise CodexStreamError("CODEX_OUTPUT_INVALID")
            answer = "".join(answer_parts).strip()
            try:
                self._repository.complete_run_with_assistant(
                    principal.user_id,
                    conversation_id,
                    _as_uuid(_value(run, "id")),
                    answer,
                    _utc(self._clock),
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
            sequence += 1
            yield ChatEvent(
                "completed",
                request_id,
                str(conversation_id),
                sequence,
                run_id=run_id,
                text=answer,
            )
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
        except Exception:
            yield from self._fail_run(
                principal,
                run,
                request_id,
                conversation_id,
                sequence,
                CodexStreamError("CODEX_EXECUTION_FAILED"),
            )

    def _fail_run(
        self,
        principal: Principal,
        run: Any,
        request_id: str,
        conversation_id: UUID,
        sequence: int,
        error: CodexStreamError,
    ) -> Iterator[ChatEvent]:
        self._repository.finish_agent_run(
            principal.user_id,
            _as_uuid(_value(run, "id")),
            AgentRunStatus.FAILED,
            None,
            error.code,
            _utc(self._clock),
        )
        yield ChatEvent(
            "failed",
            request_id,
            str(conversation_id),
            sequence + 1,
            run_id=str(_as_uuid(_value(run, "id"))),
            error_code=error.code,
            retryable=error.code in {"CODEX_UNAVAILABLE", "CODEX_TIMEOUT", "CODEX_EXECUTION_FAILED"},
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
        if status_value == AgentRunStatus.FAILED.value:
            error_code = str(_value(run, "public_error_code", "") or "CODEX_OUTPUT_INVALID")
            yield ChatEvent(
                "failed",
                request_id,
                conversation_id,
                2,
                run_id=run_id,
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
            2,
            run_id=run_id,
            text=str(_value(assistant, "content", "")),
        )

    @staticmethod
    def _prompt(history: Sequence[Any], message: str) -> str:
        rows = []
        for item in list(history)[-20:]:
            role = str(_value(item, "role", "user"))
            content = str(_value(item, "content", ""))[:4000]
            if content:
                rows.append(f"{role}: {content}")
        return (
            "你是炸鸡队长，只使用原生 Codex 回答。\n"
            "公开来源检索必须有界：最多进行 2 次公开来源检索；如果来源被拒绝、不可读或无法验证，"
            "立即停止检索并给出明确阻塞结论，不要重复搜索、轮询或等待；本轮必须输出最终回答。\n"
            "来源 API 路由必须优先：如果玩家消息或上下文包含 Warcraft Logs/WCL 报告链接，必须调用 "
            "query_warcraftlogs_report；如果包含 Raider.IO 角色链接，必须调用 query_raiderio_character。"
            "这两个工具会在云端 API 服务内使用已配置的 WCL/Raider.IO 凭据查询，再根据工具返回的数据分析；"
            "不要用 web_search 或 research_public_web 打开这些链接，也不要让玩家自行查询。若来源 API 返回 blocked、"
            "partial 或不可用，明确说明 API 阻塞原因，不猜测战斗数据；拿到结果后再输出最终回答。\n"
            + "\n".join(rows)
        )


__all__ = (
    "ChatApplication",
    "ChatApplicationError",
    "ConversationPage",
)
