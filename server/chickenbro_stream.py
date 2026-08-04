import json
import re


class ChickenbroStreamValidationError(ValueError):
    pass


_ALLOWED_RESPONSE_KEYS = {
    "answer",
    "confidence",
    "answerLayer",
    "basisLabel",
    "priorityActions",
    "evidenceRefs",
    "limitations",
    "missingInputs",
    "nextQuestion",
    "claimRefs",
}
_NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9.])(?:\+?\d{2,}(?:\.\d+)?|\d+\.\d+)%?(?![\d.])")
_ANSWER_KEY_PATTERN = re.compile(r'"answer"\s*:\s*"')


def chickenbro_text_numbers(value):
    return _NUMBER_PATTERN.findall(str(value or ""))


class ChickenbroAnswerStream:
    """Accumulates a structured model response without exposing raw provider events.

    Only the `answer` JSON string can be emitted.  A 64-character tail remains
    private until the JSON string closes so a numeric token cannot be exposed
    before its complete value is validated.
    """

    def __init__(self, allowed_numbers=None, max_buffer_chars=24000, holdback_chars=64):
        self.allowed_numbers = {str(number).rstrip("%") for number in (allowed_numbers or [])}
        self.max_buffer_chars = max_buffer_chars
        self.holdback_chars = holdback_chars
        self._raw = ""
        self._answer_start = None
        self._answer = ""
        self._answer_closed = False
        self._emitted_length = 0
        self._terminal_error = ""
        self._completed_payload = None

    def feed(self, content):
        if self._terminal_error:
            return []
        if not isinstance(content, str):
            self._terminal_error = "provider content must be text"
            return []
        self._raw += content
        if len(self._raw) > self.max_buffer_chars:
            raise ChickenbroStreamValidationError("stream response exceeded bounded buffer")

        try:
            payload = json.loads(self._raw)
        except json.JSONDecodeError:
            return self._emit_incomplete_prefix()

        try:
            self._validate_complete_payload(payload)
        except ChickenbroStreamValidationError as error:
            self._terminal_error = str(error)
            return []
        self._completed_payload = payload
        self._answer = payload["answer"]
        self._answer_closed = True
        return self._emit(force=True)

    def finish(self):
        if self._terminal_error:
            raise ChickenbroStreamValidationError(self._terminal_error)
        if self._completed_payload is None:
            try:
                payload = json.loads(self._raw)
            except json.JSONDecodeError as error:
                raise ChickenbroStreamValidationError("incomplete structured model response") from error
            self._validate_complete_payload(payload)
            self._completed_payload = payload
            self._answer = payload["answer"]
            self._answer_closed = True
        return self._completed_payload

    def _emit_incomplete_prefix(self):
        if self._answer_start is None:
            match = _ANSWER_KEY_PATTERN.search(self._raw)
            if not match:
                return []
            self._answer_start = match.end()
        try:
            answer, closed = self._decode_answer_prefix()
        except ChickenbroStreamValidationError as error:
            self._terminal_error = str(error)
            return []
        self._answer = answer
        self._answer_closed = closed
        if not self._numbers_are_allowed(answer, allow_decimal_prefix=True):
            self._terminal_error = "model_output_invalid: unapproved number"
            return []
        return self._emit(force=closed)

    def _decode_answer_prefix(self):
        value = []
        index = self._answer_start
        while index < len(self._raw):
            char = self._raw[index]
            if char == '"':
                return "".join(value), True
            if ord(char) < 0x20:
                raise ChickenbroStreamValidationError("invalid control character in answer")
            if char != "\\":
                value.append(char)
                index += 1
                continue
            if index + 1 >= len(self._raw):
                break
            escaped = self._raw[index + 1]
            simple = {"\"": '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}
            if escaped in simple:
                value.append(simple[escaped])
                index += 2
                continue
            if escaped != "u":
                raise ChickenbroStreamValidationError("invalid JSON escape in answer")
            if index + 6 > len(self._raw):
                break
            codepoint = self._raw[index + 2:index + 6]
            if not re.fullmatch(r"[0-9a-fA-F]{4}", codepoint):
                raise ChickenbroStreamValidationError("invalid unicode escape in answer")
            value.append(chr(int(codepoint, 16)))
            index += 6
        return "".join(value), False

    def _numbers_are_allowed(self, answer, allow_decimal_prefix=False):
        numbers = chickenbro_text_numbers(answer)
        for index, number in enumerate(numbers):
            if number.rstrip("%") not in self.allowed_numbers:
                if (
                    allow_decimal_prefix
                    and index == len(numbers) - 1
                    and answer.endswith(number)
                    and any(allowed.startswith(f"{number}.") for allowed in self.allowed_numbers)
                ):
                    continue
                return False
        return True

    def _emit(self, force=False):
        if not self._numbers_are_allowed(self._answer, allow_decimal_prefix=not force):
            self._terminal_error = "model_output_invalid: unapproved number"
            return []
        end = len(self._answer) if force else max(0, len(self._answer) - self.holdback_chars)
        if end <= self._emitted_length:
            return []
        delta = self._answer[self._emitted_length:end]
        self._emitted_length = end
        return [delta] if delta else []

    def _validate_complete_payload(self, payload):
        if not isinstance(payload, dict):
            raise ChickenbroStreamValidationError("model response must be an object")
        unknown = set(payload) - _ALLOWED_RESPONSE_KEYS
        if unknown:
            raise ChickenbroStreamValidationError("model response has unknown fields")
        answer = payload.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise ChickenbroStreamValidationError("model response is missing answer")
        if not self._numbers_are_allowed(answer):
            raise ChickenbroStreamValidationError("model_output_invalid: unapproved number")
