"""Linux-only child launcher: deny networking before executing the data-only engine."""
import ctypes
import errno
import os
import sys


def deny_network():
    lib = ctypes.CDLL('libseccomp.so.2', use_errno=True)
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    context = lib.seccomp_init(0x7fff0000)  # allow; explicit network denials below
    if not context:
        raise RuntimeError('POE2_SANDBOX_UNAVAILABLE')
    try:
        for name in (b'socket', b'socketpair', b'connect', b'accept', b'accept4', b'bind', b'listen'):
            syscall = lib.seccomp_syscall_resolve_name(name)
            if syscall >= 0 and lib.seccomp_rule_add(context, 0x50000 | errno.EPERM, syscall, 0) != 0:
                raise RuntimeError('POE2_SANDBOX_UNAVAILABLE')
        if lib.seccomp_load(context) != 0:
            raise RuntimeError('POE2_SANDBOX_UNAVAILABLE')
    finally:
        lib.seccomp_release(context)


if __name__ == '__main__':
    deny_network()
    os.execv(sys.argv[1], sys.argv[1:])
