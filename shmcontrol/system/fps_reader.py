"""
Best-effort FPS reader (no game injection).

Sources (in order):
1) RivaTuner Statistics Server (RTSS) shared memory – if RTSS is running
2) Otherwise None → UI shows N/A

Exclusive-fullscreen injection is intentionally NOT used (anti-cheat safe).
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys
from typing import Optional

FILE_MAP_READ = 0x0004


class RTSS_SHARED_MEMORY_HEADER(ctypes.Structure):
    _fields_ = [
        ("dwSignature", wt.DWORD),
        ("dwVersion", wt.DWORD),
        ("dwAppEntrySize", wt.DWORD),
        ("dwAppArrOffset", wt.DWORD),
        ("dwAppArrSize", wt.DWORD),
        ("dwOSDEntrySize", wt.DWORD),
        ("dwOSDArrOffset", wt.DWORD),
        ("dwOSDArrSize", wt.DWORD),
        ("dwOSDFrame", wt.DWORD),
    ]


class RTSS_SHARED_MEMORY_APP_ENTRY(ctypes.Structure):
    _fields_ = [
        ("dwProcessID", wt.DWORD),
        ("szName", ctypes.c_char * 260),
        ("dwFlags", wt.DWORD),
        ("dwTime0", wt.DWORD),
        ("dwTime1", wt.DWORD),
        ("dwFrames", wt.DWORD),
        ("dwFrameTime", wt.DWORD),  # 1000 * 1000 / FPS  (microseconds? actually 100ns units in some versions)
        # remaining fields omitted – enough for FPS estimate
    ]


def read_rtss_fps() -> Optional[float]:
    """Return FPS of the most active RTSS-tracked app, or None."""
    if sys.platform != "win32":
        return None
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        OpenFileMappingW = kernel32.OpenFileMappingW
        OpenFileMappingW.argtypes = [wt.DWORD, wt.BOOL, wt.LPCWSTR]
        OpenFileMappingW.restype = wt.HANDLE
        MapViewOfFile = kernel32.MapViewOfFile
        MapViewOfFile.argtypes = [wt.HANDLE, wt.DWORD, wt.DWORD, wt.DWORD, ctypes.c_size_t]
        MapViewOfFile.restype = ctypes.c_void_p
        UnmapViewOfFile = kernel32.UnmapViewOfFile
        CloseHandle = kernel32.CloseHandle

        hMap = OpenFileMappingW(FILE_MAP_READ, False, "RTSSSharedMemoryV2")
        if not hMap:
            return None
        pMem = MapViewOfFile(hMap, FILE_MAP_READ, 0, 0, 0)
        if not pMem:
            CloseHandle(hMap)
            return None
        try:
            hdr = RTSS_SHARED_MEMORY_HEADER.from_address(pMem)
            # Signature 'RTSS' = 0x52545353
            if hdr.dwSignature != 0x52545353 and hdr.dwSignature != 0x53535452:
                return None
            best_fps = None
            arr_off = hdr.dwAppArrOffset
            entry_size = hdr.dwAppEntrySize
            for i in range(min(hdr.dwAppArrSize, 256)):
                addr = pMem + arr_off + i * entry_size
                # read PID + frame time with smaller struct if entry larger
                pid = ctypes.c_uint32.from_address(addr).value
                if pid == 0:
                    continue
                # dwFrameTime is at offset after name etc. – use full struct if size matches
                if entry_size >= ctypes.sizeof(RTSS_SHARED_MEMORY_APP_ENTRY):
                    app = RTSS_SHARED_MEMORY_APP_ENTRY.from_address(addr)
                    # In RTSS, dwFrameTime is time between frames in 0.1µs or 100ns units.
                    # Common formula: FPS = 1000000 / dwFrameTime  when dwFrameTime is µs.
                    ft = int(app.dwFrameTime)
                    if ft <= 0:
                        continue
                    # Heuristic: typical values 16000–33333 for 60–30 FPS if microseconds
                    if ft > 1000:
                        fps = 1_000_000.0 / ft
                    else:
                        fps = 1000.0 / ft
                    if 1.0 <= fps <= 500.0:
                        if best_fps is None or fps > best_fps:
                            best_fps = fps
            return best_fps
        finally:
            UnmapViewOfFile(pMem)
            CloseHandle(hMap)
    except Exception:
        return None


def get_fps() -> Optional[float]:
    return read_rtss_fps()
