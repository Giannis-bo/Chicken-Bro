import re
from urllib.parse import quote, unquote, urlsplit

from .domain import SourceProvider, SourceRef


_WEGAME_HOST = "www.wegame.com.cn"
_NINJA_HOST = "poe.ninja"
_WEGAME_PATH = "/helper/poe2/"
_SHARE_FRAGMENT = re.compile(r"^/share/([A-Za-z0-9_-]+)$")
_NINJA_PATH = re.compile(
    r"^/poe2/profile/([^/]+)/([^/]+)/character/([^/]+)$"
)
_VALID_PERCENT_ESCAPE = re.compile(r"%(?:[0-9A-Fa-f]{2})")


def _invalid() -> ValueError:
    return ValueError("POE2_SOURCE_URL_INVALID")


def _decoded_segment(raw: str) -> str:
    # Validate escapes before unquoting, and never feed the decoded value back
    # through unquote. Encoded separators and percent signs are not identities.
    without_escapes = _VALID_PERCENT_ESCAPE.sub("", raw)
    if "%" in without_escapes:
        raise _invalid()
    try:
        decoded = unquote(raw, encoding="utf-8", errors="strict")
    except (UnicodeDecodeError, ValueError) as exc:
        raise _invalid() from exc
    if (
        not decoded
        or decoded in {".", ".."}
        or any(char in decoded for char in ("/", "\\", "%", "?", "#"))
        or any(ord(char) < 32 or ord(char) == 127 for char in decoded)
    ):
        raise _invalid()
    return decoded


def _base_parts(value: str):
    try:
        parts = urlsplit(value.strip())
        port = parts.port
    except ValueError as exc:
        raise _invalid() from exc
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or port not in (None, 443)
        or parts.query
    ):
        raise _invalid()
    return parts


def parse_character_url(value: str, expected_provider: str) -> SourceRef:
    """Parse one selected entry's URL without network access or repeat decoding."""
    try:
        expected = SourceProvider(expected_provider)
    except (TypeError, ValueError) as exc:
        raise ValueError("POE2_SOURCE_PROVIDER_INVALID") from exc
    if not isinstance(value, str):
        raise _invalid()

    parts = _base_parts(value)
    host = parts.hostname.lower()
    if host == _NINJA_HOST:
        actual = SourceProvider.NINJA
    elif host == _WEGAME_HOST:
        actual = SourceProvider.WEGAME
    else:
        raise _invalid()
    if actual is not expected:
        raise ValueError("POE2_SOURCE_PROVIDER_MISMATCH")

    if actual is SourceProvider.WEGAME:
        match = _SHARE_FRAGMENT.fullmatch(parts.fragment)
        if parts.path != _WEGAME_PATH or match is None:
            raise _invalid()
        share_id = match.group(1)
        return SourceRef(
            provider=actual,
            canonical_url=f"https://{_WEGAME_HOST}{_WEGAME_PATH}#/share/{share_id}",
            share_id=share_id,
        )

    if parts.fragment:
        raise _invalid()
    match = _NINJA_PATH.fullmatch(parts.path)
    if match is None:
        raise _invalid()
    account, league, character = (_decoded_segment(part) for part in match.groups())
    encoded = "/".join(quote(part, safe="-._~") for part in (account, league, character))
    return SourceRef(
        provider=actual,
        canonical_url=f"https://{_NINJA_HOST}/poe2/profile/{encoded.split('/')[0]}/"
        f"{encoded.split('/')[1]}/character/{encoded.split('/')[2]}",
        account=account,
        league=league,
        character=character,
    )
