"""Read only the four workflow documents shipped alongside this release.

These documents are subordinate workflow guidance, never source evidence or
permission to override the core prompt. No caller-controlled paths are accepted.
"""

import hashlib
import os
from pathlib import Path
import stat


SKILL_IDS = ('mechanics', 'wcl-analysis', 'rankings', 'simc-experiment')
MAX_SKILL_BYTES = 16 * 1024
_SKILLS_ROOT = Path(__file__).resolve().parent / 'agent' / 'skills'


def _unavailable(code):
    return {
        'sourceKey': 'chickenbro_skill', 'status': 'unavailable', 'errorCode': code,
        'limitations': ['The requested workflow is unavailable. Follow the core rules; do not invent its contents.'],
    }


def read_chickenbro_skill(arguments):
    """Return an exact UTF-8 workflow and digest, or a path-free failure packet."""
    if (not isinstance(arguments, dict) or set(arguments) != {'skillId'}
            or not isinstance(arguments['skillId'], str) or arguments['skillId'] not in SKILL_IDS):
        return _unavailable('SKILL_ARGUMENTS_INVALID')
    skill_id = arguments['skillId']
    path = _SKILLS_ROOT / (skill_id + '.md')
    try:
        # Disallow redirected release content, including Windows junctions.
        for component in (path, _SKILLS_ROOT, _SKILLS_ROOT.parent):
            if component.is_symlink() or (hasattr(component, 'is_junction') and component.is_junction()):
                return _unavailable('SKILL_CONTENT_UNAVAILABLE')
        root = _SKILLS_ROOT.resolve(strict=True)
        if path.resolve(strict=True).parent != root:
            return _unavailable('SKILL_CONTENT_UNAVAILABLE')
        before = path.stat()
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_SKILL_BYTES:
            return _unavailable('SKILL_CONTENT_UNAVAILABLE')
        flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
        with os.fdopen(os.open(path, flags), 'rb') as handle:
            opened = os.fstat(handle.fileno())
            if (not stat.S_ISREG(opened.st_mode) or not os.path.samestat(before, opened)
                    or opened.st_size > MAX_SKILL_BYTES):
                return _unavailable('SKILL_CONTENT_UNAVAILABLE')
            raw = handle.read(MAX_SKILL_BYTES + 1)
        if len(raw) > MAX_SKILL_BYTES:
            return _unavailable('SKILL_CONTENT_UNAVAILABLE')
        content = raw.decode('utf-8')
        if not content.strip():
            return _unavailable('SKILL_CONTENT_UNAVAILABLE')
    except (OSError, UnicodeError, ValueError, RuntimeError):
        return _unavailable('SKILL_CONTENT_UNAVAILABLE')
    return {
        'sourceKey': 'chickenbro_skill', 'status': 'available', 'skillId': skill_id,
        'version': 'sha256:' + hashlib.sha256(raw).hexdigest(), 'content': content,
    }
