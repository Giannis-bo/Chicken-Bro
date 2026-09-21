"""Server-controlled native ImportTab conversion under the existing engine sandbox."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from .engine import MAX_SOURCE_BYTES, PobEngine, decode_build, engine_slot
from .imports.mapping import ENGINE_COMMIT


def convert_character(character: dict) -> str:
    if not isinstance(character, dict) or character.get('_mapping', {}).get('engine_commit') != ENGINE_COMMIT:
        raise ValueError('POE2_CHARACTER_INVALID')
    payload_text = json.dumps(character, ensure_ascii=False)
    if len(payload_text.encode()) > MAX_SOURCE_BYTES:
        raise ValueError('POE2_CHARACTER_INVALID')
    engine = PobEngine()
    if not (engine.root / 'src/HeadlessWrapper.lua').is_file() or not Path(engine.lua).is_file():
        raise RuntimeError('POE2_ENGINE_UNAVAILABLE')
    # Checking the checkout binds import semantics, beyond a caller-provided label.
    identity = subprocess.run(['/usr/bin/git', '-c', 'safe.directory=' + str(engine.root),
                              '-C', str(engine.root), 'rev-parse', 'HEAD'],
                              capture_output=True, timeout=5, check=False)
    if identity.returncode or identity.stdout.decode().strip() != ENGINE_COMMIT:
        raise ValueError('POE2_ENGINE_VERSION_MISMATCH')
    with tempfile.TemporaryDirectory(prefix='poe2-character-') as directory:
        input_path, output_path = Path(directory) / 'input.json', Path(directory) / 'output.json'
        input_path.write_text(payload_text)
        env = {k: v for k, v in os.environ.items() if k in {'PATH', 'LD_LIBRARY_PATH', 'LUA_PATH', 'LUA_CPATH', 'LANG'}}
        env.update(HOME=directory, POE2_INPUT=str(input_path), POE2_OUTPUT=str(output_path))
        command = ['/usr/bin/prlimit', '--as=1073741824', '--cpu=40', '--nofile=128', '--',
                   sys.executable, str(Path(__file__).with_name('engine_runner.py')),
                   engine.lua, str(Path(__file__).with_suffix('.lua'))]
        try:
            with engine_slot():
                response = subprocess.run(command, cwd=engine.root / 'src', env=env,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                          timeout=45, check=False)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError('POE2_ENGINE_TIMEOUT') from exc
        if response.returncode or not output_path.is_file() or output_path.stat().st_size > 4_000_000:
            raise RuntimeError('POE2_CHARACTER_CONVERSION_FAILED')
        result = json.loads(output_path.read_text())
        if not isinstance(result, dict) or result.get('error'):
            raise ValueError('POE2_CHARACTER_CONVERSION_FAILED')
        return decode_build(result.get('xml', ''))
