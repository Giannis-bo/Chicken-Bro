"""Credential-free IPC adapter for the isolated Candidate browser collector."""
import hashlib
import json
import socket
from uuid import UUID

from ..domain import SourceProvider, SourceRef
from ..urls import parse_character_url

SOCKET_PATH = '/run/chickenbro-poe2-source-browser/collector.sock'
MAX_RESPONSE = 8 * 1024 * 1024
SOURCE_ERRORS = {'SOURCE_UNAVAILABLE', 'AUTH_REQUIRED', 'RATE_LIMITED', 'INCOMPLETE'}


def collect_wegame(ref: SourceRef, *, owner_id=None, socket_path=SOCKET_PATH) -> dict:
    """owner_id must come from the claimed DB row, never an HTTP body or source URL."""
    if ref.provider != SourceProvider.WEGAME:
        raise ValueError('SOURCE_UNAVAILABLE')
    checked = parse_character_url(ref.canonical_url, 'wegame')
    owner = str(UUID(str(owner_id))) if owner_id is not None else 'direct-test-caller'
    request = json.dumps({
        'version': 1, 'canonical_url': checked.canonical_url,
        'owner_key': hashlib.sha256(('poe2-import-owner:' + owner).encode()).hexdigest(),
    }, separators=(',', ':')).encode() + b'\n'
    if len(request) > 4096:
        raise ValueError('SOURCE_UNAVAILABLE')
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(63)
            connection.connect(socket_path)
            connection.sendall(request)
            with connection.makefile('rb') as stream:
                raw = stream.readline(MAX_RESPONSE + 1)
    except socket.timeout:
        raise TimeoutError('SOURCE_UNAVAILABLE') from None
    except OSError:
        raise ConnectionError('SOURCE_UNAVAILABLE') from None
    if len(raw) > MAX_RESPONSE or not raw.endswith(b'\n'):
        raise RuntimeError('INCOMPLETE')
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise RuntimeError('INCOMPLETE') from None
    if not isinstance(result, dict):
        raise RuntimeError('INCOMPLETE')
    if result.get('ok') is not True:
        code = result.get('code')
        if result.get('retryable') is True:
            raise TimeoutError('SOURCE_UNAVAILABLE')
        raise RuntimeError(code if code in SOURCE_ERRORS else 'SOURCE_UNAVAILABLE')
    if not isinstance(result.get('snapshot'), dict):
        raise RuntimeError('INCOMPLETE')
    return result['snapshot']


collect = collect_wegame
