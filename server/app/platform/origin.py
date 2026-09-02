from typing import Any, Protocol
from urllib.parse import urlsplit


class OriginRejectedError(ValueError):
    pass


class HeaderRequest(Protocol):
    headers: Any


def header_value(request: HeaderRequest, name: str) -> str:
    value = request.headers.get(name)
    if value is None:
        value = request.headers.get(name.lower())
    return value if isinstance(value, str) else ""


def require_web_origin(request: HeaderRequest, expected_origin: str) -> None:
    expected = urlsplit(expected_origin)
    canonical_origin = f"{expected.scheme}://{expected.netloc}"
    if (
        not expected.scheme
        or not expected.netloc
        or expected.path not in {"", "/"}
        or expected.query
        or expected.fragment
        or header_value(request, "origin") != canonical_origin
        or header_value(request, "host") != expected.netloc
    ):
        raise OriginRejectedError("Web Origin or Host is not allowed")
