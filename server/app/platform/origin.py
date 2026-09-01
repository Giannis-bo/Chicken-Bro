from fastapi import Request


class OriginRejectedError(ValueError):
    pass


def require_web_origin(request: Request, expected_origin: str) -> None:
    if request.headers.get("origin") != expected_origin:
        raise OriginRejectedError("Web Origin is not allowed")
