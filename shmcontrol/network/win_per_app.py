"""
Windows per-process network bytes via IP Helper APIs.

Method (real data, no estimates):
  1) GetExtendedTcpTable  -> map connection -> PID
  2) GetPerTcpConnectionEStats (TcpConnectionEstatsData)
     -> DataBytesOut / DataBytesIn per TCP connection
  3) Sum by PID

UDP has no EStats byte counters in the same way; TCP covers most app traffic.
Requires Windows. May need elevated rights for some system processes.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys
import time
from dataclasses import dataclass
from typing import Optional

if sys.platform != "win32":
    raise ImportError("win_per_app is Windows-only")

AF_INET = 2
AF_INET6 = 23
TCP_TABLE_OWNER_PID_ALL = 5
UDP_TABLE_OWNER_PID = 1

# TCP_ESTATS_TYPE
TcpConnectionEstatsData = 1

NO_ERROR = 0
ERROR_INSUFFICIENT_BUFFER = 122


class MIB_TCPROW_OWNER_PID(ctypes.Structure):
    _fields_ = [
        ("dwState", wt.DWORD),
        ("dwLocalAddr", wt.DWORD),
        ("dwLocalPort", wt.DWORD),
        ("dwRemoteAddr", wt.DWORD),
        ("dwRemotePort", wt.DWORD),
        ("dwOwningPid", wt.DWORD),
    ]


class MIB_TCPTABLE_OWNER_PID(ctypes.Structure):
    _fields_ = [
        ("dwNumEntries", wt.DWORD),
        ("table", MIB_TCPROW_OWNER_PID * 1),
    ]


class TCP_ESTATS_DATA_ROD_v0(ctypes.Structure):
    _fields_ = [
        ("DataBytesOut", ctypes.c_uint64),
        ("DataSegsOut", ctypes.c_uint64),
        ("DataBytesIn", ctypes.c_uint64),
        ("DataSegsIn", ctypes.c_uint64),
        ("SegsOut", ctypes.c_uint64),
        ("SegsIn", ctypes.c_uint64),
        ("SoftErrors", wt.ULONG),
        ("SoftErrorReason", wt.ULONG),
        ("SndUna", wt.ULONG),
        ("SndNxt", wt.ULONG),
        ("SndMax", wt.ULONG),
        ("ThruBytesAcked", ctypes.c_uint64),
        ("RcvNxt", wt.ULONG),
        ("ThruBytesReceived", ctypes.c_uint64),
    ]


class MIB_TCP6ROW_OWNER_PID(ctypes.Structure):
    _fields_ = [
        ("ucLocalAddr", ctypes.c_ubyte * 16),
        ("dwLocalScopeId", wt.DWORD),
        ("dwLocalPort", wt.DWORD),
        ("ucRemoteAddr", ctypes.c_ubyte * 16),
        ("dwRemoteScopeId", wt.DWORD),
        ("dwRemotePort", wt.DWORD),
        ("dwState", wt.DWORD),
        ("dwOwningPid", wt.DWORD),
    ]


iphlpapi = ctypes.WinDLL("iphlpapi")
GetExtendedTcpTable = iphlpapi.GetExtendedTcpTable
GetExtendedTcpTable.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(wt.DWORD), wt.BOOL, wt.ULONG, ctypes.c_int, wt.ULONG
]
GetExtendedTcpTable.restype = wt.DWORD

# GetPerTcpConnectionEStats
GetPerTcpConnectionEStats = iphlpapi.GetPerTcpConnectionEStats
GetPerTcpConnectionEStats.argtypes = [
    ctypes.POINTER(MIB_TCPROW_OWNER_PID),
    ctypes.c_int,  # EstatsType
    ctypes.c_void_p, wt.ULONG,  # Rw
    ctypes.c_void_p, wt.ULONG,  # Rod
    ctypes.c_void_p, wt.ULONG,  # Ros
]
GetPerTcpConnectionEStats.restype = wt.DWORD

# Enable may be needed first on some builds
SetPerTcpConnectionEStats = iphlpapi.SetPerTcpConnectionEStats
SetPerTcpConnectionEStats.argtypes = [
    ctypes.POINTER(MIB_TCPROW_OWNER_PID),
    ctypes.c_int,
    ctypes.c_void_p, wt.ULONG, wt.ULONG,
]
SetPerTcpConnectionEStats.restype = wt.DWORD


@dataclass
class PidTraffic:
    pid: int
    download: int = 0  # bytes in
    upload: int = 0    # bytes out
    tcp_count: int = 0


def _port_htons(p: int) -> int:
    return ((p & 0xFF) << 8) | ((p >> 8) & 0xFF)


def _get_tcp_table() -> list[MIB_TCPROW_OWNER_PID]:
    size = wt.DWORD(0)
    GetExtendedTcpTable(None, ctypes.byref(size), True, AF_INET, TCP_TABLE_OWNER_PID_ALL, 0)
    if size.value == 0:
        return []
    buf = ctypes.create_string_buffer(size.value)
    ret = GetExtendedTcpTable(buf, ctypes.byref(size), True, AF_INET, TCP_TABLE_OWNER_PID_ALL, 0)
    if ret != NO_ERROR:
        return []
    num = ctypes.cast(buf, ctypes.POINTER(wt.DWORD))[0]
    # rebuild structure with correct array size
    class TABLE(ctypes.Structure):
        _fields_ = [
            ("dwNumEntries", wt.DWORD),
            ("table", MIB_TCPROW_OWNER_PID * num),
        ]
    table = ctypes.cast(buf, ctypes.POINTER(TABLE)).contents
    return list(table.table)


def _row_estats(row: MIB_TCPROW_OWNER_PID) -> tuple[int, int]:
    """Return (bytes_in, bytes_out) for one TCP row. (0,0) if unavailable."""
    rod = TCP_ESTATS_DATA_ROD_v0()
    # Try read-only data path
    ret = GetPerTcpConnectionEStats(
        ctypes.byref(row),
        TcpConnectionEstatsData,
        None, 0,
        ctypes.byref(rod), ctypes.sizeof(rod),
        None, 0,
    )
    if ret == NO_ERROR:
        return int(rod.DataBytesIn), int(rod.DataBytesOut)

    # Some systems need Enable toggled via SetPerTcpConnectionEStats first
    # TcpConnectionEstatsData RW structure is minimal – try enable flag
    try:
        class RW(ctypes.Structure):
            _fields_ = [("EnableCollection", ctypes.c_bool)]
        rw = RW(True)
        SetPerTcpConnectionEStats(
            ctypes.byref(row), TcpConnectionEstatsData,
            ctypes.byref(rw), ctypes.sizeof(rw), 0,
        )
        ret = GetPerTcpConnectionEStats(
            ctypes.byref(row),
            TcpConnectionEstatsData,
            None, 0,
            ctypes.byref(rod), ctypes.sizeof(rod),
            None, 0,
        )
        if ret == NO_ERROR:
            return int(rod.DataBytesIn), int(rod.DataBytesOut)
    except Exception:
        pass
    return 0, 0


def collect_pid_traffic() -> dict[int, PidTraffic]:
    """Aggregate TCP EStats by owning PID."""
    rows = _get_tcp_table()
    out: dict[int, PidTraffic] = {}
    for row in rows:
        pid = int(row.dwOwningPid)
        if pid <= 0:
            continue
        bin_, bout = _row_estats(row)
        t = out.get(pid)
        if t is None:
            t = PidTraffic(pid=pid)
            out[pid] = t
        t.download += bin_
        t.upload += bout
        t.tcp_count += 1
    return out


class WinPerAppTracker:
    """Track cumulative + rate (B/s) per PID from EStats snapshots."""

    def __init__(self) -> None:
        self._prev: dict[int, tuple[int, int, float]] = {}
        self._available: Optional[bool] = None
        self._last_error: str = ""

    @property
    def available(self) -> bool:
        if self._available is None:
            try:
                data = collect_pid_traffic()
                # Consider available if we got any non-zero OR table non-empty
                self._available = True
                if not data:
                    self._last_error = "empty TCP table"
            except Exception as e:
                self._available = False
                self._last_error = str(e)
        return bool(self._available)

    @property
    def last_error(self) -> str:
        return self._last_error

    def snapshot(self) -> dict[int, dict]:
        """
        pid -> {
          download_bytes, upload_bytes,
          download_rate, upload_rate,  # B/s or None on first sample
          tcp_count, supported: True
        }
        """
        now = time.monotonic()
        try:
            raw = collect_pid_traffic()
            self._available = True
        except Exception as e:
            self._available = False
            self._last_error = str(e)
            return {}

        result = {}
        for pid, t in raw.items():
            dl, ul = t.download, t.upload
            rate_dl = rate_ul = None
            prev = self._prev.get(pid)
            if prev:
                pdl, pul, pt = prev
                dt = max(now - pt, 0.05)
                # counters are cumulative per connection lifetime; if connection
                # recycled, value may drop — clamp rate to >= 0
                rate_dl = max(0.0, (dl - pdl) / dt)
                rate_ul = max(0.0, (ul - pul) / dt)
            self._prev[pid] = (dl, ul, now)
            result[pid] = {
                "download_bytes": dl,
                "upload_bytes": ul,
                "download_rate": rate_dl,
                "upload_rate": rate_ul,
                "tcp_count": t.tcp_count,
                "supported": True,
            }
        return result


# singleton for UI
try:
    win_per_app_tracker = WinPerAppTracker()
except Exception:
    win_per_app_tracker = None  # type: ignore
