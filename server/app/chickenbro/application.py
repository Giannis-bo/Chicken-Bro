from collections.abc import Callable, Iterator, Sequence
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from server.app.chickenbro.codex_adapter import CodexChatPort, CodexTimeout, CodexUnavailable
from server.app.chickenbro.domain import AgentRunStatus, ConversationStatus, MessageRole
from server.app.chickenbro.stream import ChatEvent, CodexStreamError
from server.app.identity.prototype import PrototypePrincipal


class ChatApplicationError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


PROTOTYPE_CHAT_TIMEOUT_SECONDS = 180


def _value(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _as_uuid(value: Any) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _utc(clock: Callable[[], datetime]) -> datetime:
    value = clock()
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class PrototypeChatApplication:
    def __init__(
        self,
        *,
        repository: Any,
        codex: CodexChatPort,
        clock: Callable[[], datetime] | None = None,
        timeout_seconds: int = PROTOTYPE_CHAT_TIMEOUT_SECONDS,
        max_message_chars: int = 4000,
        max_output_chars: int = 8000,
    ):
        self._repository = repository
        self._codex = codex
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._timeout_seconds = max(1, timeout_seconds)
        self._max_message_chars = max(1, max_message_chars)
        self._max_output_chars = max(1, max_output_chars)

    def create_conversation(self, principal: PrototypePrincipal, title: str = "炸鸡队长对话") -> Any:
        bounded_title = str(title or "炸鸡队长对话").strip()[:80] or "炸鸡队长对话"
        return self._repository.create_conversation(principal.user_id, bounded_title, _utc(self._clock))

    def load_conversation(self, principal: PrototypePrincipal, conversation_id: UUID) -> Any:
        conversation = self._repository.get_conversation(principal.user_id, conversation_id)
        if conversation is None:
            raise ChatApplicationError("CONVERSATION_NOT_FOUND", "conversation not found")
        return {
            "conversation": conversation,
            "messages": self._repository.list_messages(principal.user_id, conversation_id),
        }

    def stream_message(
        self,
        principal: PrototypePrincipal,
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
        if len(idempotency_key) > 200:
            raise ChatApplicationError("IDEMPOTENCY_KEY_INVALID", "idempotency key is invalid")

        if client_message_id:
            client_message_id = str(client_message_id).strip()
            if not client_message_id or len(client_message_id) > 200:
                raise ChatApplicationError("CLIENT_MESSAGE_ID_INVALID", "client message id is invalid")
            existing = self._repository.find_message_by_client_id(
                principal.user_id,
                conversation_id,
                client_message_id,
            )
            if existing is not None:
                raise ChatApplicationError("MESSAGE_ALREADY_EXISTS", "message already exists")

        now = _utc(self._clock)
        user_message = self._repository.insert_message(
            principal.user_id,
            conversation_id,
            MessageRole.USER,
            message,
            client_message_id,
            now,
        )
        run = self._repository.start_agent_run(
            principal.user_id,
            conversation_id,
            _as_uuid(_value(user_message, "id")),
            now,
        )
        request_id = str(uuid4())
        sequence = 1
        yield ChatEvent("started", request_id, str(conversation_id), sequence)

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
                    yield ChatEvent("delta", request_id, str(conversation_id), sequence, text=delta)
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
            assistant = self._repository.insert_message(
                principal.user_id,
                conversation_id,
                MessageRole.ASSISTANT,
                answer,
                None,
                _utc(self._clock),
            )
            self._repository.finish_agent_run(
                principal.user_id,
                _as_uuid(_value(run, "id")),
                AgentRunStatus.SUCCEEDED,
                _as_uuid(_value(assistant, "id")),
                "",
                _utc(self._clock),
            )
            sequence += 1
            yield ChatEvent("completed", request_id, str(conversation_id), sequence, text=answer)
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
        principal: PrototypePrincipal,
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
            error_code=error.code,
            retryable=error.code in {"CODEX_UNAVAILABLE", "CODEX_TIMEOUT", "CODEX_EXECUTION_FAILED"},
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


__all__ = ("ChatApplicationError", "PrototypeChatApplication")
