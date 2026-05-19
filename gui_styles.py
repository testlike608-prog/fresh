"""
gui_styles.py
-------------
QSS stylesheets للـ Light و Dark themes — شكل مودرن نظيف.
الـ accent اللي اخترته: أزرق إلكتروني #3B82F6 (نفس Linear / Notion).
"""

# ─── ألوان أساسية (تستخدم كـ python objects لو محتاج تكون dynamic) ───
ACCENT       = "#3B82F6"   # blue-500
ACCENT_HOVER = "#2563EB"   # blue-600
ACCENT_DIM   = "#60A5FA"   # blue-400
SUCCESS      = "#10B981"   # green
WARNING      = "#F59E0B"   # amber
DANGER       = "#EF4444"   # red
NEUTRAL      = "#6B7280"   # gray

# ────────────────────────────────────────────────────────────────────
DARK_THEME = """
* {
    font-family: 'Segoe UI', 'Inter', 'Roboto', system-ui, sans-serif;
    color: #E5E7EB;
}

QMainWindow, QWidget#MainWindow {
    background-color: #0F172A;
}

/* ── Sidebar ── */
QWidget#Sidebar {
    background-color: #1E293B;
    border-right: 1px solid #334155;
}
QLabel#SidebarTitle {
    color: #F1F5F9;
    font-size: 18px;
    font-weight: 700;
    padding: 20px 16px 8px 16px;
}
QLabel#SidebarSubtitle {
    color: #94A3B8;
    font-size: 11px;
    padding: 0px 16px 16px 16px;
    letter-spacing: 1px;
    text-transform: uppercase;
}
QPushButton#NavButton {
    background: transparent;
    color: #CBD5E1;
    border: none;
    border-left: 3px solid transparent;
    text-align: left;
    padding: 12px 18px 12px 21px;
    font-size: 14px;
    font-weight: 500;
}
QPushButton#NavButton:hover {
    background-color: #334155;
    color: #F1F5F9;
}
QPushButton#NavButton:checked {
    background-color: #1E40AF;
    color: #FFFFFF;
    border-left: 3px solid #3B82F6;
    font-weight: 600;
}

/* ── Content area ── */
QWidget#ContentArea {
    background-color: #0F172A;
}
QLabel#PageTitle {
    color: #F1F5F9;
    font-size: 24px;
    font-weight: 700;
    padding-bottom: 4px;
}
QLabel#PageSubtitle {
    color: #94A3B8;
    font-size: 13px;
    padding-bottom: 16px;
}

/* ── Cards ── */
QFrame#Card {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 10px;
}
QLabel#CardTitle {
    color: #94A3B8;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
}
QLabel#CardValue {
    color: #F1F5F9;
    font-size: 22px;
    font-weight: 700;
}
QLabel#CardSub {
    color: #64748B;
    font-size: 11px;
}

/* ── Stage progress ── */
QLabel#StageLabel {
    color: #F1F5F9;
    font-size: 16px;
    font-weight: 600;
}
QLabel#StageStep {
    color: #94A3B8;
    font-size: 12px;
}
QProgressBar#StageProgress {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 6px;
    height: 8px;
    text-align: center;
}
QProgressBar#StageProgress::chunk {
    background-color: #3B82F6;
    border-radius: 5px;
}

/* ── Log viewer ── */
QPlainTextEdit#LogView {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 8px;
    color: #E5E7EB;
    font-family: 'Consolas', 'Courier New', 'Cascadia Code', monospace;
    font-size: 12px;
    padding: 8px;
    selection-background-color: #1E40AF;
}

/* ── Log toolbar ── */
QLineEdit#FilterEdit {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 6px;
    color: #F1F5F9;
    padding: 6px 10px;
}
QLineEdit#FilterEdit:focus {
    border: 1px solid #3B82F6;
}
QComboBox {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 6px;
    color: #F1F5F9;
    padding: 5px 10px;
}
QComboBox:focus { border: 1px solid #3B82F6; }
QComboBox QAbstractItemView {
    background-color: #1E293B;
    color: #F1F5F9;
    selection-background-color: #3B82F6;
    border: 1px solid #334155;
}

/* ── Buttons ── */
QPushButton#PrimaryBtn {
    background-color: #3B82F6;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 600;
}
QPushButton#PrimaryBtn:hover { background-color: #2563EB; }
QPushButton#PrimaryBtn:pressed { background-color: #1D4ED8; }

QPushButton#SecondaryBtn {
    background-color: transparent;
    color: #CBD5E1;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 6px 12px;
}
QPushButton#SecondaryBtn:hover {
    background-color: #1E293B;
    color: #F1F5F9;
    border: 1px solid #64748B;
}

QPushButton#ThemeToggle {
    background: transparent;
    color: #94A3B8;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 10px;
    text-align: center;
}
QPushButton#ThemeToggle:hover {
    color: #F1F5F9;
    border: 1px solid #475569;
}

/* ── Scrollbars ── */
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 4px 0;
}
QScrollBar::handle:vertical {
    background: #334155;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: #475569; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0px; }

/* ── Checkbox ── */
QCheckBox { color: #CBD5E1; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #475569;
    border-radius: 4px;
    background-color: #1E293B;
}
QCheckBox::indicator:checked {
    background-color: #3B82F6;
    border: 1px solid #3B82F6;
}

/* ── Status pill ── */
QLabel#StatusPillOk {
    background-color: rgba(16, 185, 129, 0.15);
    color: #10B981;
    border-radius: 10px;
    padding: 3px 10px;
    font-weight: 600;
    font-size: 11px;
}
QLabel#StatusPillBad {
    background-color: rgba(239, 68, 68, 0.15);
    color: #EF4444;
    border-radius: 10px;
    padding: 3px 10px;
    font-weight: 600;
    font-size: 11px;
}
"""

# ────────────────────────────────────────────────────────────────────
LIGHT_THEME = """
* {
    font-family: 'Segoe UI', 'Inter', 'Roboto', system-ui, sans-serif;
    color: #0F172A;
}

QMainWindow, QWidget#MainWindow {
    background-color: #F8FAFC;
}

/* ── Sidebar ── */
QWidget#Sidebar {
    background-color: #FFFFFF;
    border-right: 1px solid #E2E8F0;
}
QLabel#SidebarTitle {
    color: #0F172A;
    font-size: 18px;
    font-weight: 700;
    padding: 20px 16px 8px 16px;
}
QLabel#SidebarSubtitle {
    color: #64748B;
    font-size: 11px;
    padding: 0px 16px 16px 16px;
    letter-spacing: 1px;
    text-transform: uppercase;
}
QPushButton#NavButton {
    background: transparent;
    color: #475569;
    border: none;
    border-left: 3px solid transparent;
    text-align: left;
    padding: 12px 18px 12px 21px;
    font-size: 14px;
    font-weight: 500;
}
QPushButton#NavButton:hover {
    background-color: #F1F5F9;
    color: #0F172A;
}
QPushButton#NavButton:checked {
    background-color: #EFF6FF;
    color: #1E40AF;
    border-left: 3px solid #3B82F6;
    font-weight: 600;
}

/* ── Content area ── */
QWidget#ContentArea { background-color: #F8FAFC; }
QLabel#PageTitle {
    color: #0F172A;
    font-size: 24px;
    font-weight: 700;
    padding-bottom: 4px;
}
QLabel#PageSubtitle {
    color: #64748B;
    font-size: 13px;
    padding-bottom: 16px;
}

/* ── Cards ── */
QFrame#Card {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
}
QLabel#CardTitle {
    color: #64748B;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
}
QLabel#CardValue {
    color: #0F172A;
    font-size: 22px;
    font-weight: 700;
}
QLabel#CardSub {
    color: #94A3B8;
    font-size: 11px;
}

/* ── Stage progress ── */
QLabel#StageLabel { color: #0F172A; font-size: 16px; font-weight: 600; }
QLabel#StageStep { color: #64748B; font-size: 12px; }
QProgressBar#StageProgress {
    background-color: #F1F5F9;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    height: 8px;
}
QProgressBar#StageProgress::chunk {
    background-color: #3B82F6;
    border-radius: 5px;
}

/* ── Log viewer ── */
QPlainTextEdit#LogView {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    color: #1E293B;
    font-family: 'Consolas', 'Courier New', 'Cascadia Code', monospace;
    font-size: 12px;
    padding: 8px;
    selection-background-color: #BFDBFE;
}

/* ── Log toolbar ── */
QLineEdit#FilterEdit {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    color: #0F172A;
    padding: 6px 10px;
}
QLineEdit#FilterEdit:focus { border: 1px solid #3B82F6; }
QComboBox {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    color: #0F172A;
    padding: 5px 10px;
}
QComboBox:focus { border: 1px solid #3B82F6; }
QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    color: #0F172A;
    selection-background-color: #3B82F6;
    selection-color: white;
    border: 1px solid #E2E8F0;
}

/* ── Buttons ── */
QPushButton#PrimaryBtn {
    background-color: #3B82F6;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 600;
}
QPushButton#PrimaryBtn:hover { background-color: #2563EB; }
QPushButton#PrimaryBtn:pressed { background-color: #1D4ED8; }

QPushButton#SecondaryBtn {
    background-color: #FFFFFF;
    color: #475569;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    padding: 6px 12px;
}
QPushButton#SecondaryBtn:hover {
    background-color: #F1F5F9;
    color: #0F172A;
    border: 1px solid #CBD5E1;
}

QPushButton#ThemeToggle {
    background: transparent;
    color: #64748B;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    padding: 6px 10px;
}
QPushButton#ThemeToggle:hover {
    color: #0F172A;
    border: 1px solid #CBD5E1;
}

/* ── Scrollbars ── */
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 4px 0;
}
QScrollBar::handle:vertical {
    background: #CBD5E1;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: #94A3B8; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0px; }

/* ── Checkbox ── */
QCheckBox { color: #475569; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #CBD5E1;
    border-radius: 4px;
    background-color: #FFFFFF;
}
QCheckBox::indicator:checked {
    background-color: #3B82F6;
    border: 1px solid #3B82F6;
}

/* ── Status pill ── */
QLabel#StatusPillOk {
    background-color: rgba(16, 185, 129, 0.15);
    color: #047857;
    border-radius: 10px;
    padding: 3px 10px;
    font-weight: 600;
    font-size: 11px;
}
QLabel#StatusPillBad {
    background-color: rgba(239, 68, 68, 0.15);
    color: #B91C1C;
    border-radius: 10px;
    padding: 3px 10px;
    font-weight: 600;
    font-size: 11px;
}
"""

# ─── ألوان للـ log levels (في الـ log viewer) ───
LOG_COLORS = {
    "dark": {
        "DEBUG":    "#64748B",
        "INFO":     "#E5E7EB",
        "WARNING":  "#FBBF24",
        "ERROR":    "#F87171",
        "CRITICAL": "#FCA5A5",
    },
    "light": {
        "DEBUG":    "#94A3B8",
        "INFO":     "#1E293B",
        "WARNING":  "#B45309",
        "ERROR":    "#B91C1C",
        "CRITICAL": "#7F1D1D",
    },
}
