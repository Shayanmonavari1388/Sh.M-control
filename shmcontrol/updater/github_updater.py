"""
Auto-update from GitHub Releases.
Repo: https://github.com/shayanmonavary1388/Sh.M-control
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from shmcontrol import __version__

logger = logging.getLogger("shmcontrol.updater")

GITHUB_OWNER = "shayanmonavary1388"
GITHUB_REPO = "Sh.M-control"
API_RELEASES = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
REPO_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"


@dataclass
class UpdateInfo:
    available: bool
    current: str
    latest: str
    notes: str = ""
    download_url: Optional[str] = None
    asset_name: Optional[str] = None
    html_url: Optional[str] = None
    error: Optional[str] = None


def _parse_version(v: str) -> tuple[int, ...]:
    v = (v or "").strip().lstrip("vV")
    parts = re.findall(r"\d+", v)
    return tuple(int(x) for x in parts) if parts else (0,)


def is_newer(latest: str, current: str) -> bool:
    try:
        return _parse_version(latest) > _parse_version(current)
    except Exception:
        return latest != current and bool(latest)


def check_for_update(timeout: float = 12.0) -> UpdateInfo:
    current = __version__
    try:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": f"ShMControl/{current}",
        }
        token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        r = httpx.get(API_RELEASES, headers=headers, timeout=timeout, follow_redirects=True)
        if r.status_code == 404:
            return UpdateInfo(
                available=False,
                current=current,
                latest=current,
                notes="No releases published yet on GitHub.",
                html_url=REPO_URL + "/releases",
            )
        if r.status_code != 200:
            return UpdateInfo(
                available=False,
                current=current,
                latest=current,
                error=f"GitHub API {r.status_code}",
            )
        data = r.json()
        tag = str(data.get("tag_name") or data.get("name") or "").strip()
        notes = str(data.get("body") or "")[:2000]
        html = data.get("html_url") or (REPO_URL + "/releases")
        assets = data.get("assets") or []
        download_url = None
        asset_name = None
        # Prefer windows zip / exe
        preferred = []
        for a in assets:
            name = (a.get("name") or "").lower()
            url = a.get("browser_download_url")
            if not url:
                continue
            if name.endswith(".zip") or name.endswith(".exe"):
                preferred.append((name, url, a.get("name")))
        if preferred:
            # Prefer name containing shmcontrol
            preferred.sort(key=lambda x: (0 if "shm" in x[0] else 1, x[0]))
            asset_name = preferred[0][2]
            download_url = preferred[0][1]
        latest = tag.lstrip("vV") or current
        return UpdateInfo(
            available=is_newer(latest, current),
            current=current,
            latest=latest,
            notes=notes,
            download_url=download_url,
            asset_name=asset_name,
            html_url=html,
        )
    except Exception as e:
        logger.exception("update check failed")
        return UpdateInfo(
            available=False,
            current=current,
            latest=current,
            error=str(e),
        )


def download_update(url: str, dest_dir: Optional[Path] = None, timeout: float = 120.0) -> Path:
    dest_dir = dest_dir or Path(tempfile.gettempdir()) / "ShMControlUpdate"
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = url.split("?")[0].rstrip("/").split("/")[-1] or "update.bin"
    path = dest_dir / name
    with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    return path


def open_releases_page() -> None:
    import webbrowser
    webbrowser.open(REPO_URL + "/releases")


def apply_downloaded_zip(zip_path: Path) -> tuple[bool, str]:
    """
    Extract zip next to the running app and prompt restart.
    For source runs: extracts into parent of package.
    """
    import zipfile
    import shutil

    if not zip_path.exists():
        return False, "file missing"
    try:
        extract_to = Path(tempfile.gettempdir()) / "ShMControlExtract"
        if extract_to.exists():
            shutil.rmtree(extract_to, ignore_errors=True)
        extract_to.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_to)
        return True, str(extract_to)
    except Exception as e:
        return False, str(e)
