"""Cross-platform process resource measurements used by hard resource gates."""

from __future__ import annotations

import os
import sys


class ProcessResourceUsageUnavailable(RuntimeError):
    pass


def _windows_peak_working_set_bytes() -> int:
    import ctypes
    from ctypes import wintypes

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    get_current_process = kernel32.GetCurrentProcess
    get_current_process.argtypes = []
    get_current_process.restype = wintypes.HANDLE
    get_process_memory_info = psapi.GetProcessMemoryInfo
    get_process_memory_info.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessMemoryCounters),
        wintypes.DWORD,
    ]
    get_process_memory_info.restype = wintypes.BOOL
    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    if not get_process_memory_info(
        get_current_process(),
        ctypes.byref(counters),
        counters.cb,
    ):
        error_code = ctypes.get_last_error()
        raise ProcessResourceUsageUnavailable(
            f"GetProcessMemoryInfo failed with Windows error {error_code}"
        )
    return int(counters.PeakWorkingSetSize)


def peak_rss_bytes() -> int:
    if os.name == "nt":
        observed = _windows_peak_working_set_bytes()
    else:
        import resource

        observed = int(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss or 0
        )
        if sys.platform != "darwin":
            observed *= 1024
    if observed <= 0:
        raise ProcessResourceUsageUnavailable(
            "peak resident-set measurement is unavailable"
        )
    return observed


__all__ = ("ProcessResourceUsageUnavailable", "peak_rss_bytes")
