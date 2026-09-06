"""Public engine version from the verified, already-installed cloud executable."""
import os
import re
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Mapping

from server.app.simulation.readiness import (
    ManagedSimcRuntimeError, inspect_managed_simc_runtime, runtime_revision_matches_identity,
)

_BANNER = re.compile(r'\bSimulationCraft ([0-9]{3,6}-[0-9]{1,4}[A-Za-z0-9.-]{0,24}) for World of Warcraft ([0-9]+\.[0-9]+\.[0-9]+\.([0-9]+))\b')


@lru_cache(maxsize=8)
def _probe_version(binary: str, binary_sha256: str, size: int, modified_ns: int) -> tuple[str, str, str]:
    # No profile and a closed stdin: this asks the engine for its banner only.
    # A private file avoids retaining arbitrary child output in process memory.
    with tempfile.TemporaryFile() as output:
        subprocess.run([binary], stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                       timeout=3, check=False, cwd=str(Path(binary).parent))
        output.seek(0)
        text = output.read(8193)
    if len(text) > 8192:
        raise ValueError('version output exceeds limit')
    match = _BANNER.search(text.decode('utf-8', errors='replace'))
    if match is None:
        raise ValueError('version banner missing')
    return match.groups()


def get_simc_runtime_info(env: Mapping[str, str] | None = None) -> dict:
    source_env = os.environ if env is None else env
    unavailable = {'status': 'unavailable', 'version': None, 'gameVersion': None, 'build': None,
                   'sourceCommit': None, 'runtimeRevision': None}
    try:
        identity = inspect_managed_simc_runtime(source_env)
        revision = source_env.get('WOW_SIMC_RUNTIME_REVISION', '').strip() or identity.runtime_revision
        if not runtime_revision_matches_identity(revision, identity):
            return unavailable
        before = identity.binary_path.stat()
        version, game_version, build = _probe_version(str(identity.binary_path), identity.binary_sha256,
                                                     before.st_size, before.st_mtime_ns)
        # Revalidate the managed link and hash after the probe, including cache hits.
        if inspect_managed_simc_runtime(source_env) != identity:
            return unavailable
    except (ManagedSimcRuntimeError, OSError, subprocess.SubprocessError, ValueError):
        return unavailable
    return {'status': 'available', 'version': version, 'gameVersion': game_version, 'build': build,
            'sourceCommit': identity.source_commit, 'runtimeRevision': revision}
