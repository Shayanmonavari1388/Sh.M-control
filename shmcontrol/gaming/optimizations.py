"""
Windows gaming optimizations – real toggles only.
Each action returns (ok, message). Dangerous changes need confirmation at UI.
"""

from __future__ import annotations

import logging
import platform
import subprocess
from shmcontrol.core import winproc
from typing import Optional

logger = logging.getLogger("shmcontrol.gaming.opt")


def _is_windows() -> bool:
    return platform.system() == "Windows"


def _run(cmd: list[str], timeout: int = 20) -> tuple[bool, str]:
    try:
        r = winproc.run(cmd, capture_output=True, text=True, timeout=timeout, shell=False)
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode == 0, out.strip() or ("OK" if r.returncode == 0 else "Failed")
    except Exception as e:
        return False, str(e)


def set_high_performance_power() -> tuple[bool, str]:
    if not _is_windows():
        return False, "Windows only"
    return _run(["powercfg", "/setactive", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"])


def set_balanced_power() -> tuple[bool, str]:
    if not _is_windows():
        return False, "Windows only"
    return _run(["powercfg", "/setactive", "381b4222-f694-41f0-9685-ff5bb260df2e"])


def enable_windows_game_mode(on: bool = True) -> tuple[bool, str]:
    """Toggle Windows Game Mode via registry (HKCU)."""
    if not _is_windows():
        return False, "Windows only"
    try:
        import winreg
        key_path = r"Software\Microsoft\GameBar"
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path) as k:
            winreg.SetValueEx(k, "AutoGameModeEnabled", 0, winreg.REG_DWORD, 1 if on else 0)
        return True, "Game Mode " + ("ON" if on else "OFF")
    except Exception as e:
        return False, str(e)


def enable_hags(on: bool = True) -> tuple[bool, str]:
    """Hardware-accelerated GPU scheduling (needs reboot). Admin often required."""
    if not _is_windows():
        return False, "Windows only"
    val = 2 if on else 1
    try:
        import winreg
        path = r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "HwSchMode", 0, winreg.REG_DWORD, val)
        return True, f"HAGS set to {val} (reboot may be required)"
    except PermissionError:
        return False, "Administrator required for HAGS"
    except Exception as e:
        return False, str(e)


def empty_working_sets() -> tuple[bool, str]:
    """
    Best-effort standby memory trim.
    Full EmptyStandbyList needs sysinternals/admin; we trim current process working set lightly.
    """
    if not _is_windows():
        return False, "Windows only"
    try:
        import ctypes
        ctypes.windll.kernel32.SetProcessWorkingSetSize(-1, -1, -1)
        return True, "Working set trimmed (light). Full standby clear needs admin tool."
    except Exception as e:
        return False, str(e)


def clean_temp_files() -> tuple[bool, str]:
    """Delete user TEMP files older policy – only %TEMP% of current user."""
    import os
    import time
    from pathlib import Path
    temp = Path(os.environ.get("TEMP") or os.environ.get("TMP") or ".")
    removed = 0
    errors = 0
    now = time.time()
    try:
        for p in temp.glob("*"):
            try:
                if p.is_file() and now - p.stat().st_mtime > 3600:
                    p.unlink(missing_ok=True)
                    removed += 1
            except Exception:
                errors += 1
        return True, f"Removed {removed} temp files ({errors} locked)"
    except Exception as e:
        return False, str(e)


def set_process_priority(pid: int, level: str = "high") -> tuple[bool, str]:
    import psutil
    mapping = {
        "normal": getattr(psutil, "NORMAL_PRIORITY_CLASS", None),
        "above_normal": getattr(psutil, "ABOVE_NORMAL_PRIORITY_CLASS", None),
        "high": getattr(psutil, "HIGH_PRIORITY_CLASS", None),
    }
    cls = mapping.get(level)
    if cls is None:
        return False, "Priority class not available"
    try:
        psutil.Process(pid).nice(cls)
        return True, f"PID {pid} → {level}"
    except Exception as e:
        return False, str(e)


def disable_fullscreen_optimizations_hint() -> str:
    return (
        "Fullscreen optimizations are per-exe (Compatibility tab). "
        "Sh.M Control does not silently rewrite every game shortcut."
    )
