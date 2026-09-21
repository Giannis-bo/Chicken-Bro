"""One Linux subreaper per browser job; never adopts another job's descendants."""
import ctypes
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time


def reap_all():
    # Killing a parent reparents even setsid/double-fork children to this
    # subreaper. Iterate until waitpid confirms no descendants remain.
    children_file = Path(f'/proc/self/task/{os.getpid()}/children')
    while True:
        for value in children_file.read_text().split():
            try:
                os.kill(int(value), signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
            if pid == 0:
                time.sleep(0.005)
        except ChildProcessError:
            return


def main():
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), 'subreaper unavailable')
    stopped = False

    def stop(*_):
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    timeout = int(sys.argv[1]) / 1000
    # Reserve a bounded part of the outer deadline for process reaping.
    deadline = time.monotonic() + max(0.05, timeout - min(0.5, timeout / 5))
    request = sys.stdin.buffer.readline(4097)
    result = {'ok': False, 'code': 'SOURCE_UNAVAILABLE', 'retryable': True}
    process = subprocess.Popen(
        [sys.argv[2], sys.argv[3], '--capture-stdio'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        start_new_session=True,
        env={'PATH': '/usr/bin:/bin', 'HOME': '/tmp', 'LANG': 'C.UTF-8'},
    )
    try:
        process.stdin.write(request)
        process.stdin.close()
        data = bytearray()
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while not stopped and time.monotonic() < deadline:
                ready = selector.select(min(0.05, max(0, deadline - time.monotonic())))
                if ready:
                    part = os.read(process.stdout.fileno(), 65536)
                    if not part:
                        break
                    data.extend(part)
                    if len(data) > 8 * 1024 * 1024:
                        break
                    if b'\n' in data:
                        parsed = json.loads(data)
                        if isinstance(parsed, dict):
                            result = parsed
                        break
                # A exited writer may still have unread bytes in its pipe.
                # Only framing/EOF, the byte cap, or the deadline ends reads.
    finally:
        reap_all()
    print(json.dumps(result, separators=(',', ':')), flush=True)


if __name__ == '__main__':
    main()
