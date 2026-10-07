"""Windows-safe subprocess: never flash a console window."""
from __future__ import annotations

import subprocess
import sys
from typing import Any, Optional, Sequence, Union

Cmd = Union[str, Sequence[str]]


def _flags() -> int:
    if sys.platform != "win32":
        return 0
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))


def run(
    cmd: Cmd,
    *,
    timeout: Optional[float] = 30,
    text: bool = True,
    shell: bool = False,
    input: Optional[str] = None,
    env: Optional[dict] = None,
    cwd: Optional[str] = None,
    capture_output: bool = True,
    check: bool = False,
) -> subprocess.CompletedProcess:
    kwargs: dict[str, Any] = dict(
        capture_output=capture_output,
        text=text,
        timeout=timeout,
        shell=shell,
        env=env,
        cwd=cwd,
        check=check,
    )
    fl = _flags()
    if fl:
        kwargs["creationflags"] = fl
    return subprocess.run(cmd, input=input, **kwargs)


def popen_detached(cmd: Cmd, *, shell: bool = False) -> subprocess.Popen:
    kwargs: dict[str, Any] = dict(
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        shell=shell,
    )
    fl = _flags()
    if fl:
        kwargs["creationflags"] = fl
    return subprocess.Popen(cmd, **kwargs)

# re-export for except clauses
TimeoutExpired = subprocess.TimeoutExpired
