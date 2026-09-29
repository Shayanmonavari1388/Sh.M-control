"""Background poller: Remote commands -> local execution -> result to Telegram via Worker.

Critical: for sleep/hibernate/shutdown/restart we ACK *before* suspending the machine,
otherwise the command stays pending and re-runs after every resume (infinite loop).
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from shmcontrol.api.cloud import is_configured, poll_commands, ack_command, register_device
from shmcontrol.api.command_runner import run_command
from shmcontrol.config.settings import settings_manager, get_app_data_dir

logger = logging.getLogger("shmcontrol.api.poller")

# Actions that kill network / process before ACK can complete
POWER_CMDS = frozenset({
    "sleep", "hibernate", "shutdown", "restart", "lock",
})

_processed_lock = threading.Lock()
_processed_ids: set[int] = set()
_PROCESSED_FILE = "processed_cloud_cmds.txt"


def _load_processed() -> None:
    global _processed_ids
    try:
        p = get_app_data_dir() / _PROCESSED_FILE
        if p.exists():
            ids = set()
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.isdigit():
                    ids.add(int(line))
            # keep last 500 only
            _processed_ids = set(sorted(ids)[-500:])
    except Exception:
        pass


def _remember(cid: int) -> None:
    with _processed_lock:
        _processed_ids.add(cid)
        try:
            p = get_app_data_dir() / _PROCESSED_FILE
            # append; periodically rewrite trimmed
            with open(p, "a", encoding="utf-8") as f:
                f.write(f"{cid}\n")
            if len(_processed_ids) > 600:
                trimmed = sorted(_processed_ids)[-400:]
                _processed_ids.clear()
                _processed_ids.update(trimmed)
                p.write_text("\n".join(str(x) for x in trimmed) + "\n", encoding="utf-8")
        except Exception:
            pass


def _already_done(cid: int) -> bool:
    with _processed_lock:
        return cid in _processed_ids


_load_processed()


class CloudPoller:
    def __init__(self, interval: float = 4.0) -> None:
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="remote-poller", daemon=True)
        self._thread.start()
        logger.info("Remote poller started")

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                has_tg = bool(getattr(settings_manager.settings, "telegram_user_id", None))
                sync = bool(getattr(settings_manager.settings, "cloud_sync_enabled", False)) or has_tg
                if is_configured() and sync:
                    try:
                        register_device(
                            name=getattr(settings_manager.settings, "device_name", None) or "PC",
                            refresh_link=False,
                        )
                    except Exception:
                        pass
                    for c in poll_commands():
                        self._handle_one(c)
            except Exception as e:
                logger.debug("poller loop: %s", e)
            self._stop.wait(self.interval)

    def _handle_one(self, c: dict) -> None:
        cid = int(c.get("id") or 0)
        cmd = str(c.get("command") or "").strip().lower()
        args = str(c.get("args") or "")
        tg = c.get("telegram_user_id")
        tg_id = int(tg) if tg else None

        if not cid or not cmd:
            return
        if _already_done(cid):
            # Ensure cloud is not stuck pending
            try:
                ack_command(cid, "done", "skipped: already executed", telegram_user_id=tg_id)
            except Exception:
                pass
            return

        # Mark locally first so a crash/resume cannot double-run
        _remember(cid)

        if cmd in POWER_CMDS:
            # ACK before suspending so server is not left pending (prevents reboot loops)
            try:
                ack_command(
                    cid,
                    "done",
                    f"Executing {cmd}…",
                    telegram_user_id=tg_id,
                )
            except Exception as e:
                logger.warning("pre-ack failed for %s: %s", cmd, e)
            # Longer wait for shutdown/restart/hibernate so ACK reaches remote
            time.sleep(1.2 if cmd in ("shutdown", "restart", "hibernate") else 0.5)
            try:
                result = run_command(cmd, args)
                logger.info("Power cmd %s -> %s", cmd, (result or "")[:120])
            except Exception as e:
                logger.exception("power cmd failed")
                try:
                    ack_command(cid, "error", str(e), telegram_user_id=tg_id)
                except Exception:
                    pass
            return

        # Normal commands: execute then ack with result
        try:
            result = run_command(cmd, args)
        except Exception as e:
            result = f"error: {e}"
        try:
            ack_command(cid, "done", result, telegram_user_id=tg_id)
        except Exception as e:
            logger.debug("ack failed: %s", e)
        logger.info("Executed %s -> %s", cmd, (result or "")[:120])


cloud_poller = CloudPoller()
