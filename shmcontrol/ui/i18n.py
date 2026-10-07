"""
Sh.M Control – simple FA/EN translations.
No external gettext dependency.
"""

from __future__ import annotations

from typing import Callable

_current = "fa"
_listeners: list[Callable[[str], None]] = []

# key -> {en, fa}
STRINGS: dict[str, dict[str, str]] = {
    # App / nav
    "app_name": {"en": "Sh.M Control", "fa": "Sh.M Control"},
    "nav_overview": {"en": "OVERVIEW", "fa": "نمای کلی"},
    "nav_gaming_sec": {"en": "GAMING", "fa": "گیمینگ"},
    "nav_network_sec": {"en": "NETWORK", "fa": "شبکه"},
    "nav_tools": {"en": "TOOLS", "fa": "ابزارها"},
    "dashboard": {"en": "Dashboard", "fa": "داشبورد"},
    "monitoring": {"en": "Monitoring", "fa": "مانیتورینگ"},
    "ping_guard": {"en": "Ping Guard", "fa": "پایداری پینگ"},
    "overlay": {"en": "Overlay", "fa": "اورلی"},

    "system": {"en": "System", "fa": "سیستم"},
    "gaming": {"en": "Gaming", "fa": "بازی"},
    "connectivity": {"en": "Connectivity", "fa": "اتصال بازی"},
    "cooling": {"en": "Fan / RGB", "fa": "فن / RGB"},
    "network": {"en": "Network", "fa": "شبکه"},
    "dns": {"en": "DNS", "fa": "DNS"},
    "usage": {"en": "App Internet Usage", "fa": "مصرف اینترنت برنامه‌ها"},
    "timer": {"en": "System Timer", "fa": "تایمر سیستم"},
    "telegram": {"en": "Telegram", "fa": "تلگرام"},
    "alerts": {"en": "Alerts", "fa": "هشدارها"},
    "logs": {"en": "Logs", "fa": "لاگ‌ها"},
    "about": {"en": "About", "fa": "درباره سازنده"},
    "settings": {"en": "Settings", "fa": "تنظیمات"},
    "local_agent": {"en": "Local agent ready", "fa": "عامل محلی آماده است"},
    "open_dashboard": {"en": "Open Dashboard", "fa": "باز کردن داشبورد"},
    "exit_completely": {"en": "Exit Completely", "fa": "خروج کامل"},
    "exit_title": {"en": "Exit", "fa": "خروج"},
    "exit_msg": {
        "en": "Close Sh.M Control completely?\n\nYes = Exit\nNo = Minimize to tray",
        "fa": "خروج کامل از Sh.M Control؟\n\nبله = خروج\nخیر = رفتن به سینی سیستم",
    },
    "tray_minimized": {
        "en": "Minimized to tray — use Exit Completely to quit",
        "fa": "به سینی سیستم منتقل شد — برای خروج کامل از Exit Completely استفاده کنید",
    },

    # Dashboard
    "dash_title": {"en": "Dashboard", "fa": "داشبورد"},
    "dash_sub": {
        "en": "Live metrics · no estimated values",
        "fa": "نمایش زنده · بدون مقدار تخمینی",
    },
    "sec_performance": {"en": "PERFORMANCE", "fa": "عملکرد"},
    "sec_network": {"en": "NETWORK", "fa": "شبکه"},
    "sec_system": {"en": "SYSTEM", "fa": "سیستم"},
    "cpu_usage": {"en": "CPU Usage", "fa": "مصرف CPU"},
    "ram_usage": {"en": "RAM Usage", "fa": "مصرف RAM"},
    "gpu_usage": {"en": "GPU Usage", "fa": "مصرف GPU"},
    "gpu_memory": {"en": "GPU Memory", "fa": "حافظه GPU"},
    "cpu_temp": {"en": "CPU Temp", "fa": "دمای CPU"},
    "gpu_temp": {"en": "GPU Temp", "fa": "دمای GPU"},
    "gpu_fan": {"en": "GPU Fan", "fa": "فن GPU"},
    "disk_usage": {"en": "Disk Usage", "fa": "مصرف دیسک"},
    "download": {"en": "Download", "fa": "دانلود"},
    "upload": {"en": "Upload", "fa": "آپلود"},
    "local_ip": {"en": "Local IP", "fa": "IP محلی"},
    "public_ip": {"en": "Public IP", "fa": "IP عمومی"},
    "graphics": {"en": "Graphics", "fa": "کارت گرافیک"},
    "uptime": {"en": "Uptime", "fa": "مدت روشن بودن"},
    "system_timer": {"en": "System Timer", "fa": "تایمر سیستم"},
    "game_mode": {"en": "Game Mode", "fa": "حالت بازی"},
    "not_available": {"en": "Not available", "fa": "در دسترس نیست"},
    "sensor_na": {"en": "Sensor not available", "fa": "سنسور موجود نیست"},
    "idle": {"en": "Idle", "fa": "غیرفعال"},
    "no_scheduled": {"en": "No scheduled action", "fa": "عمل زمان‌بندی‌شده‌ای نیست"},
    "off": {"en": "Off", "fa": "خاموش"},
    "active": {"en": "Active", "fa": "فعال"},
    "not_engaged": {"en": "Not engaged", "fa": "فعال نشده"},
    "network_online": {"en": "Network · Online", "fa": "شبکه · آنلاین"},
    "gpu_prefix": {"en": "GPU ·", "fa": "GPU ·"},

    # Usage
    "usage_title": {"en": "App Internet Usage", "fa": "مصرف اینترنت برنامه‌ها"},
    "usage_sub": {
        "en": "Icon · software name · download / upload · real totals only",
        "fa": "آیکون · نام نرم‌افزار · دانلود / آپلود · فقط داده واقعی",
    },
    "refresh": {"en": "Refresh", "fa": "بروزرسانی"},
    "period_today": {"en": "Today (1 day)", "fa": "امروز (۱ روز)"},
    "period_7": {"en": "7 Days", "fa": "۷ روز"},
    "period_30": {"en": "30 Days", "fa": "۳۰ روز"},
    "applications": {"en": "APPLICATIONS", "fa": "برنامه‌ها"},
    "active_procs": {"en": "ACTIVE NETWORK PROCESSES", "fa": "پروسه‌های فعال شبکه"},
    "total_shown": {"en": "Total (shown):", "fa": "جمع (نمایش‌داده‌شده):"},
    "system_all": {"en": "System (all traffic)", "fa": "سیستم (کل ترافیک)"},
    "vpn_tunnel": {"en": "VPN / Tunnel", "fa": "VPN / تانل"},
    "no_vpn": {"en": "No VPN adapter detected right now.", "fa": "در حال حاضر آداپتر VPN پیدا نشد."},
    "no_vpn_proc": {"en": "No VPN client process found", "fa": "پروسس کلاینت VPN پیدا نشد"},
    "usage_limits": {"en": "Usage Limits", "fa": "سقف مصرف"},
    "scope": {"en": "Scope", "fa": "محدوده"},
    "target": {"en": "Target", "fa": "هدف"},
    "limit_mb": {"en": "Limit MB", "fa": "سقف (مگابایت)"},
    "action": {"en": "Action", "fa": "عملیات"},
    "add_limit": {"en": "Add / Update Limit", "fa": "افزودن / ویرایش سقف"},
    "check_limits": {"en": "Check Limits", "fa": "بررسی سقف‌ها"},
    "delete_limit": {"en": "Delete Selected Limit", "fa": "حذف مورد انتخاب‌شده"},
    "limit_saved": {"en": "Limit saved", "fa": "سقف ذخیره شد"},
    "no_limit_exceeded": {"en": "No limits exceeded", "fa": "هیچ سقفی رد نشده است"},
    "usage_note_win": {
        "en": "Windows without a kernel driver: system total is accurate. Apps with open connections appear as chips below (no fake per-app GB).",
        "fa": "در ویندوز بدون درایور کرنل: مجموع سیستم دقیق است. برنامه‌های دارای اتصال فعال پایین صفحه نشان داده می‌شوند (بدون گیگابایت جعلی).",
    },
    "no_usage_yet": {
        "en": "No usage recorded yet for this period.",
        "fa": "برای این بازه هنوز مصرفی ثبت نشده است.",
    },

    # Settings
    "settings_title": {"en": "Settings", "fa": "تنظیمات"},
    "language": {"en": "Language:", "fa": "زبان:"},
    "start_windows": {"en": "Start with Windows", "fa": "اجرا همراه با ویندوز"},
    "minimize_tray": {"en": "Minimize to System Tray", "fa": "کوچک‌سازی به سینی سیستم"},
    "close_to_tray": {
        "en": "Close button minimizes to Tray (uncheck = full exit)",
        "fa": "دکمه بستن به سینی برود (غیرفعال = خروج کامل)",
    },
    "monitor_interval": {"en": "Monitoring Interval (ms):", "fa": "بازه پایش (میلی‌ثانیه):"},
    "save_settings": {"en": "Save Settings", "fa": "ذخیره تنظیمات"},
    "saved": {"en": "Saved.", "fa": "ذخیره شد."},
    "updates": {"en": "Updates", "fa": "به‌روزرسانی"},
    "current_version": {"en": "Current version:", "fa": "نسخه فعلی:"},
    "check_updates": {"en": "Check for Updates", "fa": "بررسی به‌روزرسانی"},
    "update_note": {
        "en": "Auto-update downloads are not enabled yet (safety). Check reports version status only — no silent install.",
        "fa": "دانلود خودکار هنوز فعال نیست (امنیت). فقط وضعیت نسخه گزارش می‌شود — نصب خاموش انجام نمی‌شود.",
    },
    "lang_restart": {
        "en": "Language applied. Some labels refresh immediately; restart if anything looks mixed.",
        "fa": "زبان اعمال شد. بیشتر برچسب‌ها همین الان عوض می‌شوند؛ اگر چیزی مخلوط بود برنامه را یک‌بار ببندید و باز کنید.",
    },

    # DNS
    "dns_title": {"en": "DNS Manager", "fa": "مدیریت DNS"},
    "dns_sub": {
        "en": "Status/Latency from real DNS queries (UDP/53). Apply/Restore need Administrator on Windows.",
        "fa": "وضعیت/تأخیر از کوئری واقعی DNS (UDP/53). اعمال/بازگردانی در ویندوز به دسترسی Administrator نیاز دارد.",
    },
    "search_dns": {"en": "Search DNS...", "fa": "جستجوی DNS..."},
    "adapter": {"en": "Adapter:", "fa": "آداپتر:"},
    "read_current": {"en": "Read Current", "fa": "خواندن فعلی"},
    "refresh_list": {"en": "Refresh List", "fa": "بروزرسانی لیست"},
    "test_selected": {"en": "Test Selected", "fa": "تست انتخاب‌شده"},
    "apply_dns": {"en": "Apply DNS", "fa": "اعمال DNS"},
    "restore_dns": {"en": "Restore Previous DNS", "fa": "بازگردانی DNS قبلی"},
    "current_dns": {"en": "Current DNS:", "fa": "DNS فعلی:"},

    # Timer
    "timer_title": {"en": "System Timer", "fa": "تایمر سیستم"},
    "schedule": {"en": "Schedule", "fa": "زمان‌بندی"},
    "cancel_timer": {"en": "Cancel Timer", "fa": "لغو تایمر"},
    "no_timer": {"en": "No scheduled action", "fa": "عمل زمان‌بندی‌شده‌ای نیست"},

    # Common
    "yes": {"en": "Yes", "fa": "بله"},
    "no": {"en": "No", "fa": "خیر"},
    "cancel": {"en": "Cancel", "fa": "انصراف"},
    "error": {"en": "Error", "fa": "خطا"},
}


def set_language(lang: str) -> None:
    global _current
    lang = (lang or "en").lower()
    if lang not in ("fa", "en"):
        lang = "en"
    _current = lang
    for cb in list(_listeners):
        try:
            cb(lang)
        except Exception:
            pass


def get_language() -> str:
    return _current


def t(key: str, **kwargs) -> str:
    """Translate key for current language."""
    entry = STRINGS.get(key)
    if not entry:
        return key
    text = entry.get(_current) or entry.get("en") or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except Exception:
            pass
    return text


def on_language_change(callback: Callable[[str], None]) -> None:
    if callback not in _listeners:
        _listeners.append(callback)
