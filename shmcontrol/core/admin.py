"""Windows admin elevation helpers."""

from __future__ import annotations

import os
import sys
from pathlib import Path


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
    Re-launch elevated on Windows. Always pass project folder as working directory.
    """
    if sys.platform != "win32":
        return True
    if is_admin():
        return True
    if os.environ.get("SHM_SKIP_ELEVATE") == "1":
        return False
    try:
        import ctypes

        if getattr(sys, "frozen", False):
            work_dir = str(Path(sys.executable).resolve().parent)
            exe = str(Path(sys.executable).resolve())
            rest = sys.argv[1:]
            params = " ".join(f'"{a}"' if " " in str(a) else str(a) for a in rest)
        else:
            script = Path(sys.argv[0]).resolve()
            work_dir = str(script.parent)
            exe = str(Path(sys.executable).resolve())
            parts = [f'"{script}"']
            for a in sys.argv[1:]:
                parts.append(f'"{a}"' if " " in str(a) else str(a))
            params = " ".join(parts)

        print(f"[admin] elevating: exe={exe}", flush=True)
        print(f"[admin] params={params}", flush=True)
        print(f"[admin] work_dir={work_dir}", flush=True)

        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe, params, work_dir, 1
        )
        if rc > 32:
            print("[admin] Elevated process started — this window will close.", flush=True)
            sys.exit(0)
        print(f"[admin] UAC failed or cancelled (rc={rc})", flush=True)
        return False
    except Exception as e:
        print(f"[admin] elevate error: {e}", flush=True)
        return False
