"""
Sh.M Control – Premium Dark UI
Quality target: polished gaming utility (unique identity, not a clone).
Accent: cyan → indigo (distinct from purple competitor themes).
"""

DARK_GAMING_QSS = """
/* ===== Base ===== */
QWidget {
    background-color: transparent;
    color: #e8edf7;
    font-family: "Segoe UI", "Tahoma", sans-serif;
    font-size: 13px;
}
QMainWindow, QDialog {
    background-color: #0b0e14;
}

/* ===== Sidebar ===== */
#sidebar {
    background-color: #0f131a;
    border-left: 1px solid #1a2030;
    min-width: 220px;
    max-width: 220px;
}
#sidebarBrand {
    border-bottom: 1px solid #1a2030;
    padding: 4px 0 8px 0;
}
#appTitle {
    color: #f1f5ff;
    font-size: 16px;
    font-weight: 800;
    background: transparent;
    padding: 0;
}
#appVersion {
    color: #5b657a;
    font-size: 11px;
    background: transparent;
    padding: 0;
}
#navSection {
    color: #4a5568;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1.2px;
    padding: 18px 16px 6px 16px;
    background: transparent;
}
#sidebar QPushButton {
    background-color: transparent;
    border: none;
    border-radius: 12px;
    padding: 10px 12px;
    margin: 2px 10px;
    text-align: right;
    color: #8b95a8;
    font-size: 13px;
    font-weight: 600;
}
#sidebar QPushButton:hover {
    background-color: #161c28;
    color: #e8edf7;
}
#sidebar QPushButton:checked {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #0ea5e9, stop:1 #6366f1);
    color: #ffffff;
}

/* ===== Headers ===== */
#pageHeader {
    color: #f8fafc;
    font-size: 26px;
    font-weight: 800;
    background: transparent;
    border: none;
    padding: 0;
}
#pageSubtitle {
    color: #6b7280;
    font-size: 12px;
    background: transparent;
    border: none;
}
#sectionTitle {
    color: #7dd3fc;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1.4px;
    background: transparent;
    border: none;
}

/* ===== Cards ===== */
QFrame#card {
    background-color: #121722;
    border: 1px solid #1e2636;
    border-radius: 16px;
}
QFrame#card:hover {
    border: 1px solid #2a3548;
}

QFrame#metricCard {
    background-color: #121722;
    border: 1px solid #1e2636;
    border-radius: 16px;
}

QLabel#cardTitle {
    color: #8b95a8;
    font-size: 12px;
    font-weight: 600;
    background: transparent;
    border: none;
}
QLabel#cardValue {
    color: #f8fafc;
    font-size: 28px;
    font-weight: 800;
    background: transparent;
    border: none;
}
QLabel#cardValueOk { color: #34d399; font-size: 28px; font-weight: 800; background: transparent; border: none; }
QLabel#cardValueWarn { color: #fbbf24; font-size: 28px; font-weight: 800; background: transparent; border: none; }
QLabel#cardValueCrit { color: #f87171; font-size: 28px; font-weight: 800; background: transparent; border: none; }
QLabel#cardValueInfo { color: #38bdf8; font-size: 28px; font-weight: 800; background: transparent; border: none; }
QLabel#cardSub {
    color: #6b7280;
    font-size: 11px;
    background: transparent;
    border: none;
}

QLabel#statusChip {
    background-color: #161c28;
    border: 1px solid #2a3548;
    border-radius: 12px;
    padding: 5px 12px;
    color: #8b95a8;
    font-size: 11px;
    font-weight: 600;
}
QLabel#statusChipErr {
    color: #f87171;
    border: 1px solid rgba(248, 113, 113, 0.45);
    background: rgba(248, 113, 113, 0.12);
}
QLabel#statusChipOk {
    background-color: rgba(16, 185, 129, 0.12);
    border: 1px solid rgba(16, 185, 129, 0.35);
    border-radius: 12px;
    padding: 5px 12px;
    color: #34d399;
    font-size: 11px;
    font-weight: 700;
}

/* ===== Buttons ===== */
QPushButton {
    background-color: #1a2232;
    border: 1px solid #2a3548;
    border-radius: 12px;
    padding: 9px 16px;
    color: #e2e8f0;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #243044;
    border-color: #38bdf8;
}
QPushButton#primary {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #0ea5e9, stop:1 #6366f1);
    border: none;
    color: white;
    font-weight: 800;
    border-radius: 12px;
    padding: 10px 18px;
}
QPushButton#primary:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #38bdf8, stop:1 #818cf8);
}
QPushButton#danger {
    background-color: #dc2626;
    border: none;
    color: white;
    font-weight: 700;
    border-radius: 12px;
}
QPushButton#success {
    background-color: #059669;
    border: none;
    color: white;
    font-weight: 700;
    border-radius: 12px;
}
QPushButton#ghost {
    background-color: transparent;
    border: 1px solid #2a3548;
    color: #8b95a8;
}
QPushButton#seg {
    background-color: #161c28;
    border: 1px solid #1e2636;
    border-radius: 10px;
    padding: 8px 14px;
    color: #8b95a8;
}
QPushButton#seg:checked {
    background-color: #6366f1;
    border: none;
    color: white;
    font-weight: 700;
}

/* ===== Inputs ===== */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {
    background-color: #0f131a;
    border: 1px solid #1e2636;
    border-radius: 12px;
    padding: 9px 12px;
    color: #e2e8f0;
    selection-background-color: #0ea5e9;
}
QLineEdit:focus, QComboBox:focus {
    border-color: #38bdf8;
}
QComboBox::drop-down { border: none; width: 28px; }
QComboBox QAbstractItemView {
    background-color: #121722;
    border: 1px solid #1e2636;
    selection-background-color: rgba(14, 165, 233, 0.25);
    color: #e2e8f0;
}

/* ===== Tables ===== */
QTableWidget {
    background-color: #0f131a;
    border: 1px solid #1e2636;
    border-radius: 14px;
    gridline-color: transparent;
    selection-background-color: rgba(14, 165, 233, 0.18);
    alternate-background-color: #121722;
}
QHeaderView::section {
    background-color: #121722;
    color: #6b7280;
    padding: 10px 12px;
    border: none;
    border-bottom: 1px solid #1e2636;
    font-weight: 700;
    font-size: 11px;
}
QTableWidget::item {
    padding: 6px 8px;
    border: none;
}

/* ===== Scroll ===== */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 4px 2px;
}
QScrollBar::handle:vertical {
    background: #1e2636;
    border-radius: 4px;
    min-height: 32px;
}
QScrollBar::handle:vertical:hover { background: #2a3548; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

/* ===== Progress ===== */
QProgressBar {
    background-color: #1a2232;
    border: none;
    border-radius: 4px;
    max-height: 6px;
    min-height: 6px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #0ea5e9, stop:1 #6366f1);
    border-radius: 4px;
}
QProgressBar#barOk::chunk { background-color: #34d399; }
QProgressBar#barWarn::chunk { background-color: #fbbf24; }
QProgressBar#barCrit::chunk { background-color: #f87171; }
QProgressBar#barDown::chunk { background-color: #22d3ee; }
QProgressBar#barUp::chunk { background-color: #a78bfa; }

/* ===== Group / misc ===== */
QGroupBox {
    background-color: #121722;
    border: 1px solid #1e2636;
    border-radius: 14px;
    margin-top: 12px;
    padding: 16px 12px 12px 12px;
    font-weight: 600;
    color: #8b95a8;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 8px;
    color: #7dd3fc;
}
QToolTip {
    background-color: #1a2232;
    color: #f1f5f9;
    border: 1px solid #2a3548;
    border-radius: 8px;
    padding: 6px 10px;
}
QMessageBox { background-color: #0f131a; }
QCheckBox { color: #c5cdd8; spacing: 8px; }
QCheckBox::indicator {
    width: 18px; height: 18px;
    border-radius: 6px;
    border: 1px solid #2a3548;
    background: #0f131a;
}
QCheckBox::indicator:checked {
    background: #0ea5e9;
    border-color: #0ea5e9;
}
"""
