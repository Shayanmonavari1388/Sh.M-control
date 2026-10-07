"""
Sh.M Control - System Control
Shutdown / Restart / Sleep / Hibernate / Lock with confirmation.
"""

from __future__ import annotations

import logging
import platform
import subprocess
from shmcontrol.core import winproc
from enum import Enum

logger = logging.getLogger("shmcontrol.system.control")


class SystemAction(str, Enum):
    SHUTDOWN = "shutdown"
    RESTART = "restart"
    SLEEP = "sleep"
    HIBERNATE = "hibernate"
    LOCK = "lock"
    CANCEL_SHUTDOWN = "cancel_shutdown"


def _is_windows() -> bool:
    return platform.system() == "Windows"


def _run(cmd: list[str], timeout: int = 30) -> tuple[bool, str]:
    try:
        r = winproc.run(cmd, capture_output=True, text=True, timeout=timeout, shell=False)
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        return r.returncode == 0, out
    except Exception as e:
        return False, str(e)


def _popen(cmd: list[str]) -> None:
    """Fire-and-forget (needed for sleep — process never returns until wake)."""
    winproc.popen_detached(cmd, shell=False)


def execute_system_action(
    action: SystemAction, force: bool = False, delay_seconds: int = 0
) -> tuple[bool, str]:
    """
    Execute a system action. Returns (success, message).
    Caller MUST show confirmation UI before destructive actions.
    Uses argv lists only (no shell) to avoid injection.
    """
    try:
        delay_seconds = max(0, int(delay_seconds))

        if action == SystemAction.CANCEL_SHUTDOWN:
            if _is_windows():
                _run(["shutdown", "/a"])
                return True, "Scheduled shutdown cancelled"
            _run(["shutdown", "-c"])
            return True, "Shutdown cancelled"

        if action == SystemAction.LOCK:
            if _is_windows():
                winproc.run(
                    ["rundll32.exe", "user32.dll,LockWorkStation"],
                    check=False, shell=False,
                )
                return True, "Workstation locked"
            for cmd in (["loginctl", "lock-session"], ["gnome-screensaver-command", "-l"]):
                ok, _ = _run(cmd)
                if ok:
                    return True, "Session locked"
            return False, "Lock not supported on this platform"

        if action == SystemAction.SLEEP:
            if _is_windows():
                # Do NOT wait for the process — SetSuspendState blocks until wake
                # and causes a false "timeout" failure.
                # Method 1: powercfg request + rundll32 suspend
                try:
                    _popen([
                        "powershell",
                        "-NoProfile",
                        "-WindowStyle", "Hidden",
                        "-Command",
                        # Force suspend (not hibernate): bHibernate=false
                        "Add-Type -AssemblyName System.Windows.Forms; "
                        "[void][System.Windows.Forms.Application]::SetSuspendState("
                        "[System.Windows.Forms.PowerState]::Suspend, $false, $false)",
                    ])
                    return True, "Sleep initiated"
                except Exception as e:
                    logger.debug("sleep powershell failed: %s", e)
                    # Fallback
                    try:
                        _popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"])
                        return True, "Sleep initiated (fallback)"
                    except Exception as e2:
                        return False, f"Sleep failed: {e2}"
            try:
                _popen(["systemctl", "suspend"])
                return True, "Suspend initiated"
            except Exception as e:
                return False, str(e)

        if action == SystemAction.HIBERNATE:
            if _is_windows():
                # shutdown /h returns quickly
                ok, msg = _run(["shutdown", "/h"], timeout=10)
                if ok:
                    return True, "Hibernate initiated"
                # Fallback fire-and-forget
                try:
                    _popen(["shutdown", "/h"])
                    return True, "Hibernate initiated"
                except Exception as e:
                    return False, f"Hibernate failed: {msg or e}"
            try:
                _popen(["systemctl", "hibernate"])
                return True, "Hibernate initiated"
            except Exception as e:
                return False, str(e)

        if action == SystemAction.SHUTDOWN:
            if _is_windows():
                cmd = ["shutdown", "/s", "/t", str(delay_seconds)]
                if force:
                    cmd.append("/f")
                _run(cmd, timeout=15)
                return True, f"Shutdown scheduled in {delay_seconds}s"
            mins = max(delay_seconds // 60, 0)
            _run(["shutdown", "-h", f"+{mins}"], timeout=15)
            return True, "Shutdown scheduled"

        if action == SystemAction.RESTART:
            if _is_windows():
                cmd = ["shutdown", "/r", "/t", str(delay_seconds)]
                if force:
                    cmd.append("/f")
                _run(cmd, timeout=15)
                return True, f"Restart scheduled in {delay_seconds}s"
            mins = max(delay_seconds // 60, 0)
            _run(["shutdown", "-r", f"+{mins}"], timeout=15)
            return True, "Restart scheduled"

        return False, f"Unknown action: {action}"
    except Exception as exc:
        logger.exception("System action failed: %s", action)
        return False, str(exc)
