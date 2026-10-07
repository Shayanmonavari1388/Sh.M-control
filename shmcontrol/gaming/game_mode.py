"""
Sh.M Control - Game Mode
Manual ON/OFF + auto-detect games.
Raises process priority, switches power plan, restores on exit.
"""

from __future__ import annotations

import logging
import platform
import re
import subprocess
from shmcontrol.core import winproc
import time
from dataclasses import dataclass, field
from typing import Optional

import psutil

from shmcontrol.database.models import db
from shmcontrol.notifications.notify import notify_windows

logger = logging.getLogger("shmcontrol.gaming")


@dataclass
class GameProfile:
    name: str
    executable: str
    priority: str = "high"
    power_plan: str = "high_performance"
    close_apps: list[str] = field(default_factory=list)


@dataclass
class GameModeState:
    active: bool = False
    manual: bool = False
    game_name: Optional[str] = None
    pid: Optional[int] = None
    previous_power_plan: Optional[str] = None
    previous_priority: Optional[int] = None
    closed_pids: list[int] = field(default_factory=list)


_POWER_GUIDS = {
    "balanced": "381b4222-f694-41f0-9685-ff5bb260df2e",
    "high_performance": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
    "power_saver": "a1841308-3541-4fab-bc81-f71556f20b4a",
}

# Built-in common game process names (no network needed)
_BUILTIN_GAMES = [
    ("Valorant", "valorant.exe"),
    ("VALORANT-Win64", "valorant-win64-shipping.exe"),
    ("CS2", "cs2.exe"),
    ("CSGO", "csgo.exe"),
    ("GTA V", "gta5.exe"),
    ("GTA V", "gtav.exe"),
    ("Fortnite", "fortniteclient-win64-shipping.exe"),
    ("Apex", "r5apex.exe"),
    ("Warzone", "cod.exe"),
    ("Warzone", "modernwarfare.exe"),
    ("League of Legends", "league of legends.exe"),
    ("League Client", "leagueclient.exe"),
    ("Dota 2", "dota2.exe"),
    ("Minecraft", "javaw.exe"),
    ("Roblox", "robloxplayerbeta.exe"),
    ("Rocket League", "rocketleague.exe"),
    ("Overwatch", "overwatch.exe"),
    ("PUBG", "tslgame.exe"),
    ("Elden Ring", "eldenring.exe"),
    ("Cyberpunk", "cyberpunk2077.exe"),
    ("Steam Game", "gameoverlayui.exe"),
]


class GameModeManager:
    def __init__(self) -> None:
        self.state = GameModeState()
        self.enabled = False
        self._last_scan = 0.0

    @property
    def is_active(self) -> bool:
        return bool(self.state.active)

    def load_profiles_from_db(self) -> list[GameProfile]:
        profiles: list[GameProfile] = []
        try:
            rows = db.execute(
                "SELECT name, executable FROM games WHERE enabled = 1 "
                "AND executable IS NOT NULL AND executable != ''"
            )
            for r in rows:
                profiles.append(
                    GameProfile(
                        name=r["name"],
                        executable=(r["executable"] or "").lower(),
                    )
                )
        except Exception as e:
            logger.debug("load profiles: %s", e)
        # Always include builtins
        for name, exe in _BUILTIN_GAMES:
            profiles.append(GameProfile(name=name, executable=exe.lower()))
        return profiles

    def force_activate(self, label: str = "Manual") -> tuple[bool, str]:
        """Turn Game Mode ON without waiting for a game process."""
        try:
            if self.state.active and self.state.manual:
                return True, f"Already ON ({self.state.game_name})"
            if self.state.active and not self.state.manual:
                # Keep game session but mark as active
                return True, f"Already ON for {self.state.game_name}"

            prev_plan = self._get_active_power_plan()
            self._set_power_plan("high_performance")
            # Windows Game Mode registry (best-effort)
            try:
                from shmcontrol.gaming import optimizations as opt
                opt.enable_windows_game_mode(True)
            except Exception:
                pass

            self.state = GameModeState(
                active=True,
                manual=True,
                game_name=label,
                pid=None,
                previous_power_plan=prev_plan,
            )
            self.enabled = True
            notify_windows(
                "Sh.M Control – Game Mode",
                f"Game Mode ON: {label}",
                key="game_mode_on",
                cooldown=5,
            )
            try:
                db.log("INFO", "gaming", "game_mode_force_on", label)
            except Exception:
                pass
            return True, f"Game Mode ON ({label})"
        except Exception as e:
            logger.exception("force_activate failed")
            return False, str(e)

    def force_deactivate(self) -> tuple[bool, str]:
        if not self.state.active:
            self.enabled = False
            return True, "Game Mode already OFF"
        name = self.state.game_name or "Manual"
        self.exit_game_mode()
        self.enabled = False
        return True, f"Game Mode OFF ({name})"

    def scan_and_apply(self) -> None:
        if not self.enabled:
            if self.state.active and not self.state.manual:
                self.exit_game_mode()
            return
        now = time.monotonic()
        if now - self._last_scan < 2.0:
            return
        self._last_scan = now

        # Manual mode stays active until user turns off
        if self.state.manual and self.state.active:
            return

        profiles = self.load_profiles_from_db()
        if not profiles:
            return

        found: Optional[tuple[GameProfile, int]] = None
        try:
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    pname = (proc.info.get("name") or "").lower()
                    if not pname:
                        continue
                    for profile in profiles:
                        exe = profile.executable.lower()
                        if not exe:
                            continue
                        if pname == exe or pname == exe.replace(".exe", "") + ".exe":
                            found = (profile, int(proc.info["pid"]))
                            break
                    if found:
                        break
                except (psutil.Error, ProcessLookupError):
                    continue
        except Exception as e:
            logger.debug("scan processes: %s", e)
            return

        if found:
            profile, pid = found
            if self.state.active and self.state.pid == pid:
                return
            if self.state.active and self.state.pid != pid:
                self.exit_game_mode()
            self.enter_game_mode(profile, pid)
        else:
            if self.state.active and not self.state.manual:
                # Game closed
                try:
                    if self.state.pid and not psutil.pid_exists(self.state.pid):
                        self.exit_game_mode()
                except Exception:
                    self.exit_game_mode()

    def enter_game_mode(self, profile: GameProfile, pid: int) -> None:
        logger.info("Entering Game Mode for %s (pid=%s)", profile.name, pid)
        prev_plan = self._get_active_power_plan()
        prev_prio = None
        try:
            p = psutil.Process(pid)
            prev_prio = p.nice()
            if platform.system() == "Windows" and hasattr(psutil, "HIGH_PRIORITY_CLASS"):
                p.nice(psutil.HIGH_PRIORITY_CLASS)
            else:
                try:
                    p.nice(-5)
                except Exception:
                    pass
        except (psutil.Error, ProcessLookupError) as e:
            logger.debug("priority set failed: %s", e)

        self._set_power_plan(profile.power_plan or "high_performance")
        try:
            from shmcontrol.gaming import optimizations as opt
            opt.enable_windows_game_mode(True)
        except Exception:
            pass

        self.state = GameModeState(
            active=True,
            manual=False,
            game_name=profile.name,
            pid=pid,
            previous_power_plan=prev_plan,
            previous_priority=prev_prio,
        )
        notify_windows(
            "Sh.M Control – Game Mode",
            f"Game Mode ON: {profile.name}",
            key=f"game_start_{profile.name}",
            cooldown=60,
        )
        try:
            db.log("INFO", "gaming", "game_mode_enter", profile.name)
        except Exception:
            pass

    def exit_game_mode(self) -> None:
        if not self.state.active:
            return
        name = self.state.game_name or "unknown"
        pid = self.state.pid
        logger.info("Exiting Game Mode for %s", name)

        if pid is not None and self.state.previous_priority is not None:
            try:
                p = psutil.Process(pid)
                p.nice(self.state.previous_priority)
            except (psutil.Error, ProcessLookupError, ValueError):
                pass

        if platform.system() == "Windows" and self.state.previous_power_plan:
            self._set_power_plan_guid(self.state.previous_power_plan)

        notify_windows(
            "Sh.M Control – Game Mode",
            f"Game Mode OFF: {name}",
            key=f"game_exit_{name}",
            cooldown=60,
        )
        try:
            db.log("INFO", "gaming", "game_mode_exit", name)
        except Exception:
            pass
        self.state = GameModeState()

    def _get_active_power_plan(self) -> Optional[str]:
        if platform.system() != "Windows":
            return None
        try:
            proc = winproc.run(
                ["powercfg", "/getactivescheme"],
                capture_output=True, text=True, timeout=10,
            )
            m = re.search(
                r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
                proc.stdout or "",
            )
            return m.group(1) if m else None
        except Exception as e:
            logger.debug("get power plan: %s", e)
            return None

    def _set_power_plan(self, name: str) -> None:
        guid = _POWER_GUIDS.get(name)
        if guid:
            self._set_power_plan_guid(guid)

    def _set_power_plan_guid(self, guid: str) -> None:
        if platform.system() != "Windows":
            return
        try:
            winproc.run(
                ["powercfg", "/setactive", guid],
                capture_output=True, timeout=10,
            )
        except Exception as e:
            logger.debug("set power plan: %s", e)


game_mode_manager = GameModeManager()
