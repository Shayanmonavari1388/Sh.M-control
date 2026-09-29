"""Windows admin elevation helpers."""

from __future__ import annotations

import os
import sys


def is_admin() -> bool:
    if sys.platform != "win32":
        try:
            return os.geteuid() == 0
        except AttributeError:
            return True
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def ensure_admin() -> bool:
    """
    On Windows, if not elevated, re-launch with UAC (runas) and exit parent.
    If user declines UAC, continue without admin (return False).
    """
    if sys.platform != "win32":
        return True
    if is_admin():
        return True
    # Skip re-elevate loop
    if os.environ.get("SHM_SKIP_ELEVATE") == "1":
        return False
    try:
        import ctypes
        if getattr(sys, "frozen", False):
            # PyInstaller EXE: elevate the EXE with remaining args
            exe = sys.executable
            args = " ".join(
                f'"{a}"' if (" " in a or not a) else a for a in sys.argv[1:]
            )
        else:
            exe = sys.executable
            # python.exe + script + args
            args = " ".join(
                f'"{a}"' if (" " in a or not a) else a for a in sys.argv
            )
        # Mark child to avoid infinite elev loops if still not admin
        env_flag = ""
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe, args, None, 1
        )
        if rc > 32:
            # Elevated instance is starting; exit this process
            sys.exit(0)
        # User cancelled or error – continue without admin
        return False
    except Exception:
        return False
