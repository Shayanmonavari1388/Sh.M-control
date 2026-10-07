"""About / Developer — Shayan Monavari."""

from __future__ import annotations

import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget, QScrollArea,
)

from shmcontrol import __app_name__, __version__
from shmcontrol.ui.i18n import get_language

SITE = "https://shayanmonavari.ir/"
GITHUB = "https://github.com/shayanmonavary1388/Sh.M-control"
GITHUB_PROFILE = "https://github.com/shayanmonavary1388"
TELEGRAM = "https://t.me/Theshayanmonavari"
INSTAGRAM = "https://www.instagram.com/theshayanmonavari"
LINKEDIN = "https://www.linkedin.com/in/shayanmonavari"
PHONE = "tel:+989332131754"


class AboutPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)

        self.title = QLabel()
        self.title.setObjectName("pageHeader")
        lay.addWidget(self.title)

        self.sub = QLabel()
        self.sub.setObjectName("pageSubtitle")
        self.sub.setWordWrap(True)
        lay.addWidget(self.sub)

        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 18, 20, 18)
        cl.setSpacing(10)

        self.name = QLabel("شایان منوری  ·  Shayan Monavari")
        self.name.setStyleSheet("font-size: 20px; font-weight: 800; color: #e2e8f0;")
        cl.addWidget(self.name)

        self.role = QLabel()
        self.role.setWordWrap(True)
        self.role.setStyleSheet("color: #94a3b8; font-size: 13px;")
        cl.addWidget(self.role)

        self.bio = QLabel()
        self.bio.setWordWrap(True)
        self.bio.setStyleSheet("color: #cbd5e1; font-size: 13px; line-height: 1.5;")
        cl.addWidget(self.bio)

        self.app_info = QLabel()
        self.app_info.setWordWrap(True)
        self.app_info.setStyleSheet("color: #64748b; font-size: 12px;")
        cl.addWidget(self.app_info)

        lay.addWidget(card)

        links = QFrame()
        links.setObjectName("card")
        ll = QVBoxLayout(links)
        ll.setContentsMargins(16, 14, 16, 14)
        ll.setSpacing(8)
        self.links_title = QLabel()
        self.links_title.setStyleSheet("font-weight: 700; color: #e2e8f0;")
        ll.addWidget(self.links_title)

        row1 = QHBoxLayout()
        self.btn_site = QPushButton()
        self.btn_site.setObjectName("primary")
        self.btn_site.clicked.connect(lambda: webbrowser.open(SITE))
        self.btn_github = QPushButton()
        self.btn_github.clicked.connect(lambda: webbrowser.open(GITHUB))
        self.btn_tg = QPushButton()
        self.btn_tg.clicked.connect(lambda: webbrowser.open(TELEGRAM))
        row1.addWidget(self.btn_site)
        row1.addWidget(self.btn_github)
        row1.addWidget(self.btn_tg)
        ll.addLayout(row1)

        row2 = QHBoxLayout()
        self.btn_ig = QPushButton()
        self.btn_ig.clicked.connect(lambda: webbrowser.open(INSTAGRAM))
        self.btn_li = QPushButton()
        self.btn_li.clicked.connect(lambda: webbrowser.open(LINKEDIN))
        self.btn_phone = QPushButton()
        self.btn_phone.clicked.connect(lambda: webbrowser.open(PHONE))
        row2.addWidget(self.btn_ig)
        row2.addWidget(self.btn_li)
        row2.addWidget(self.btn_phone)
        ll.addLayout(row2)

        self.url_hint = QLabel()
        self.url_hint.setWordWrap(True)
        self.url_hint.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.url_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        ll.addWidget(self.url_hint)

        lay.addWidget(links)
        lay.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll)
        self.retranslate()

    def retranslate(self) -> None:
        fa = get_language() == "fa"
        self.title.setText("درباره سازنده" if fa else "About Developer")
        self.sub.setText(
            f"{__app_name__} v{__version__}"
        )
        self.role.setText(
            "برنامه‌نویس وب و توسعه‌دهنده اندروید · دانش‌آموز شبکه و نرم‌افزار"
            if fa else
            "Web developer & Android developer · Network & Software student"
        )
        self.bio.setText(
            "سلام، من شایان منوری هستم. کارم را از هنرستان مفتح شروع کردم و بیشتر روی "
            "برنامه‌نویسی اندروید (جاوا/کاتلین) و وب کار می‌کنم. به انیمیشن و طراحی هم علاقه دارم "
            "و سعی می‌کنم پروژه‌ها هم ظاهر خوب داشته باشند هم عملکرد قوی."
            if fa else
            "Hi, I'm Shayan Monavari. I started at Mofateh vocational school and focus on "
            "Android (Java/Kotlin) and web development. I also care about animation and design, "
            "aiming for both polished UI and solid performance."
        )
        self.app_info.setText(
            f"ساخته‌شده توسط شایان منوری · انتشار: GitHub\n{GITHUB}"
            if fa else
            f"Built by Shayan Monavari · Published on GitHub\n{GITHUB}"
        )
        self.links_title.setText("لینک‌ها" if fa else "Links")
        self.btn_site.setText("وب‌سایت" if fa else "Website")
        self.btn_github.setText("GitHub پروژه" if fa else "Project GitHub")
        self.btn_tg.setText("تلگرام" if fa else "Telegram")
        self.btn_ig.setText("اینستاگرام" if fa else "Instagram")
        self.btn_li.setText("لینکدین" if fa else "LinkedIn")
        self.btn_phone.setText("تماس" if fa else "Call")
        self.url_hint.setText(
            f"سایت: {SITE}\nگیت‌هاب: {GITHUB}\nپروفایل: {GITHUB_PROFILE}"
        )

    def on_show(self) -> None:
        self.retranslate()
