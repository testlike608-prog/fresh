import sys
import os
import subprocess
import datetime
import openpyxl
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QCheckBox, QFrame, QFileDialog,
    QGraphicsDropShadowEffect, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QColor, QPalette, QPixmap, QPainter, QBrush, QPen, QLinearGradient

# ─── CONFIG ───────────────────────────────────────────────────────────────────
EXCEL_PATH = os.path.join(os.path.expanduser("~"), "Desktop", "Fresh_LeakTest_Results.xlsx")

MODELS = [
    "Select Model...",
    "Fresh FW-1000", "Fresh FW-1200", "Fresh FW-1400",
    "Fresh FW-2000", "Fresh FW-2200", "Fresh TL-800",
    "Fresh TL-1000", "Fresh TL-1200", "Fresh Auto-500",
]

PROCESSES = ["Scan", "Processing", "Result", "Saving"]

# ─── DARK / LIGHT THEMES ──────────────────────────────────────────────────────
DARK = {
    "bg":           "#0f1117",
    "surface":      "#1a1d27",
    "surface2":     "#22263a",
    "border":       "#2e3350",
    "accent":       "#e8192c",          # Fresh red
    "accent_soft":  "#ff4757",
    "accent_glow":  "rgba(232,25,44,0.18)",
    "text":         "#f0f2ff",
    "text_muted":   "#8b8fa8",
    "pass_color":   "#00e676",
    "fail_color":   "#ff1744",
    "step_active":  "#e8192c",
    "step_done":    "#00e676",
    "step_idle":    "#2e3350",
}

LIGHT = {
    "bg":           "#f4f5fb",
    "surface":      "#ffffff",
    "surface2":     "#eef0fa",
    "border":       "#d0d4ea",
    "accent":       "#e8192c",
    "accent_soft":  "#ff4757",
    "accent_glow":  "rgba(232,25,44,0.10)",
    "text":         "#1a1d27",
    "text_muted":   "#6b7080",
    "pass_color":   "#00a651",
    "fail_color":   "#e8192c",
    "step_active":  "#e8192c",
    "step_done":    "#00a651",
    "step_idle":    "#d0d4ea",
}

# ─── FRESH LOGO (SVG-like via QPainter) ───────────────────────────────────────
def make_logo_pixmap(size=48, dark=True):
    px = QPixmap(size, size)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    # Red circle background
    p.setBrush(QBrush(QColor("#e8192c")))
    p.setPen(Qt.NoPen)
    p.drawEllipse(2, 2, size - 4, size - 4)
    # White "F" letter
    p.setPen(QPen(QColor("white"), 0))
    p.setBrush(QBrush(QColor("white")))
    font = QFont("Arial Black", int(size * 0.5), QFont.Bold)
    p.setFont(font)
    p.drawText(px.rect(), Qt.AlignCenter, "F")
    p.end()
    return px


# ─── STEP INDICATOR WIDGET ────────────────────────────────────────────────────
class StepIndicator(QWidget):
    def __init__(self, steps, theme):
        super().__init__()
        self.steps = steps
        self.theme = theme
        self.current_step = -1  # -1 = idle
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self.step_labels = []
        self.connectors = []

        for i, step in enumerate(steps):
            # Step circle + label
            col = QVBoxLayout()
            col.setSpacing(4)
            col.setAlignment(Qt.AlignHCenter)

            dot = QLabel("●")
            dot.setAlignment(Qt.AlignCenter)
            dot.setFixedSize(36, 36)
            dot.setFont(QFont("Arial", 16))

            lbl = QLabel(step)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFont(QFont("Segoe UI", 9, QFont.Medium))

            col.addWidget(dot)
            col.addWidget(lbl)

            container = QWidget()
            container.setLayout(col)
            self._layout.addWidget(container)
            self.step_labels.append((dot, lbl))

            if i < len(steps) - 1:
                line = QLabel("──────")
                line.setAlignment(Qt.AlignCenter)
                line.setFont(QFont("Arial", 12))
                self._layout.addWidget(line, 1)
                self.connectors.append(line)

        self.apply_theme(theme)

    def apply_theme(self, theme):
        self.theme = theme
        self.refresh()

    def set_step(self, idx):
        """idx: 0-based active step, -1=idle, 99=all done"""
        self.current_step = idx
        self.refresh()

    def refresh(self):
        T = self.theme
        for i, (dot, lbl) in enumerate(self.step_labels):
            if self.current_step == -1:
                color = T["step_idle"]
            elif i < self.current_step:
                color = T["step_done"]
            elif i == self.current_step:
                color = T["step_active"]
            else:
                color = T["step_idle"]
            dot.setStyleSheet(f"color: {color};")
            lbl.setStyleSheet(f"color: {T['text_muted']};")

        for line in self.connectors:
            line.setStyleSheet(f"color: {T['border']};")


# ─── RESULT BADGE ─────────────────────────────────────────────────────────────
class ResultBadge(QLabel):
    def __init__(self, theme):
        super().__init__("—")
        self.theme = theme
        self.setAlignment(Qt.AlignCenter)
        self.setFont(QFont("Arial Black", 36, QFont.Bold))
        self.setFixedHeight(100)
        self.setStyleSheet(f"color: {theme['text_muted']}; letter-spacing: 4px;")

    def set_result(self, result, theme):
        self.theme = theme
        if result == "PASS":
            self.setText("✔  PASS")
            self.setStyleSheet(
                f"color: {theme['pass_color']}; letter-spacing: 4px; "
                f"background: rgba(0,230,118,0.08); border-radius: 12px;"
            )
        elif result == "FAIL":
            self.setText("✘  FAIL")
            self.setStyleSheet(
                f"color: {theme['fail_color']}; letter-spacing: 4px; "
                f"background: rgba(255,23,68,0.08); border-radius: 12px;"
            )
        else:
            self.setText("—")
            self.setStyleSheet(f"color: {theme['text_muted']}; letter-spacing: 4px;")


# ─── MAIN WINDOW ──────────────────────────────────────────────────────────────
class FreshLeakTestApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.dark_mode = True
        self.theme = DARK
        self.current_step = -1
        self.test_result = "—"
        self.last_image_path = ""
        self._timer = QTimer()
        self._timer.timeout.connect(self._advance_step)

        self.setWindowTitle("Fresh — Leak Test Monitor")
        self.setMinimumSize(780, 600)
        self.resize(860, 640)
        self._build_ui()
        self._apply_theme()

    # ── UI BUILD ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── HEADER ──────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(72)
        self.header = header
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(28, 0, 28, 0)

        # Logo + company name
        self.logo_lbl = QLabel()
        self.logo_lbl.setPixmap(make_logo_pixmap(40))
        h_lay.addWidget(self.logo_lbl)

        brand = QVBoxLayout()
        brand.setSpacing(0)
        self.brand_title = QLabel("FRESH")
        self.brand_title.setFont(QFont("Arial Black", 16, QFont.Bold))
        self.brand_sub = QLabel("Leak Test Monitor")
        self.brand_sub.setFont(QFont("Segoe UI", 9))
        brand.addWidget(self.brand_title)
        brand.addWidget(self.brand_sub)
        h_lay.addLayout(brand)
        h_lay.addStretch()

        # Dark/Light toggle
        self.theme_check = QCheckBox("Dark Mode")
        self.theme_check.setChecked(True)
        self.theme_check.setFont(QFont("Segoe UI", 9))
        self.theme_check.toggled.connect(self._toggle_theme)
        h_lay.addWidget(self.theme_check)

        root.addWidget(header)

        # ── DIVIDER ─────────────────────────────────────────────────────────
        self.divider = QFrame()
        self.divider.setFixedHeight(1)
        root.addWidget(self.divider)

        # ── BODY ────────────────────────────────────────────────────────────
        body = QWidget()
        self.body = body
        b_lay = QVBoxLayout(body)
        b_lay.setContentsMargins(32, 28, 32, 28)
        b_lay.setSpacing(22)

        # Row 1: Model selector card
        model_card = self._card()
        mc_lay = QHBoxLayout(model_card)
        mc_lay.setContentsMargins(20, 16, 20, 16)

        self.model_icon = QLabel("⚙")
        self.model_icon.setFont(QFont("Segoe UI Emoji", 20))
        mc_lay.addWidget(self.model_icon)

        mc_text = QVBoxLayout()
        mc_text.setSpacing(2)
        lbl_model_title = QLabel("Washing Machine Model")
        lbl_model_title.setFont(QFont("Segoe UI", 9, QFont.Medium))
        self.lbl_model_small = lbl_model_title
        self.model_combo = QComboBox()
        self.model_combo.addItems(MODELS)
        self.model_combo.setFont(QFont("Segoe UI", 11))
        self.model_combo.setFixedHeight(38)
        mc_text.addWidget(lbl_model_title)
        mc_text.addWidget(self.model_combo)
        mc_lay.addLayout(mc_text, 1)

        # Run button
        self.run_btn = QPushButton("▶  Run Test")
        self.run_btn.setFixedSize(140, 44)
        self.run_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.clicked.connect(self._run_test)
        mc_lay.addWidget(self.run_btn)

        b_lay.addWidget(model_card)

        # Row 2: Step indicator card
        step_card = self._card()
        sc_lay = QVBoxLayout(step_card)
        sc_lay.setContentsMargins(20, 14, 20, 14)
        self.lbl_process = QLabel("PROCESS STATUS")
        self.lbl_process.setFont(QFont("Segoe UI", 8, QFont.Bold))
        sc_lay.addWidget(self.lbl_process)

        self.step_indicator = StepIndicator(PROCESSES, self.theme)
        sc_lay.addWidget(self.step_indicator)
        b_lay.addWidget(step_card)

        # Row 3: Result card
        result_card = self._card()
        rc_lay = QVBoxLayout(result_card)
        rc_lay.setContentsMargins(20, 18, 20, 18)
        rc_lay.setAlignment(Qt.AlignCenter)

        self.lbl_result_title = QLabel("TEST RESULT")
        self.lbl_result_title.setFont(QFont("Segoe UI", 8, QFont.Bold))
        self.lbl_result_title.setAlignment(Qt.AlignCenter)
        rc_lay.addWidget(self.lbl_result_title)

        self.result_badge = ResultBadge(self.theme)
        rc_lay.addWidget(self.result_badge)
        b_lay.addWidget(result_card)

        # Row 4: Open Excel button
        self.excel_btn = QPushButton("📊  Open Results Sheet")
        self.excel_btn.setFixedHeight(44)
        self.excel_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.excel_btn.setCursor(Qt.PointingHandCursor)
        self.excel_btn.clicked.connect(self._open_excel)
        b_lay.addWidget(self.excel_btn)

        root.addWidget(body, 1)

        # ── STATUS BAR ──────────────────────────────────────────────────────
        self.status_lbl = QLabel("Ready — Select a model to begin.")
        self.status_lbl.setFont(QFont("Segoe UI", 8))
        self.status_lbl.setContentsMargins(28, 6, 28, 6)
        self.status_bar_w = QWidget()
        sb_lay = QHBoxLayout(self.status_bar_w)
        sb_lay.setContentsMargins(0, 0, 0, 0)
        sb_lay.addWidget(self.status_lbl)
        root.addWidget(self.status_bar_w)

    def _card(self):
        card = QFrame()
        card.setFrameShape(QFrame.NoFrame)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 40))
        card.setGraphicsEffect(shadow)
        return card

    # ── THEME ─────────────────────────────────────────────────────────────────
    def _toggle_theme(self, checked):
        self.dark_mode = checked
        self.theme = DARK if checked else LIGHT
        self._apply_theme()

    def _apply_theme(self):
        T = self.theme
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {T['bg']};
                color: {T['text']};
            }}
        """)

        self.header.setStyleSheet(f"background: {T['surface']}; border-bottom: 1px solid {T['border']};")
        self.divider.setStyleSheet(f"background: {T['border']};")
        self.body.setStyleSheet(f"background: {T['bg']};")

        self.brand_title.setStyleSheet(f"color: {T['accent']};")
        self.brand_sub.setStyleSheet(f"color: {T['text_muted']};")
        self.theme_check.setStyleSheet(f"color: {T['text_muted']};")

        # Cards
        card_style = f"""
            QFrame {{
                background: {T['surface']};
                border: 1px solid {T['border']};
                border-radius: 14px;
            }}
        """
        for card in self.centralWidget().findChildren(QFrame):
            card.setStyleSheet(card_style)

        # Model combo
        self.model_combo.setStyleSheet(f"""
            QComboBox {{
                background: {T['surface2']};
                color: {T['text']};
                border: 1.5px solid {T['border']};
                border-radius: 8px;
                padding: 4px 12px;
                selection-background-color: {T['accent']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 32px;
            }}
            QComboBox QAbstractItemView {{
                background: {T['surface']};
                color: {T['text']};
                selection-background-color: {T['accent']};
                border: 1px solid {T['border']};
                border-radius: 6px;
            }}
        """)

        # Run button
        self.run_btn.setStyleSheet(f"""
            QPushButton {{
                background: {T['accent']};
                color: white;
                border: none;
                border-radius: 10px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {T['accent_soft']};
            }}
            QPushButton:pressed {{
                background: #c0001f;
            }}
            QPushButton:disabled {{
                background: {T['border']};
                color: {T['text_muted']};
            }}
        """)

        # Excel button
        self.excel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {T['surface']};
                color: {T['text']};
                border: 1.5px solid {T['border']};
                border-radius: 10px;
            }}
            QPushButton:hover {{
                border-color: {T['accent']};
                color: {T['accent']};
            }}
        """)

        # Labels
        self.lbl_model_small.setStyleSheet(f"color: {T['text_muted']}; background: transparent; border: none;")
        self.lbl_process.setStyleSheet(f"color: {T['text_muted']}; background: transparent; border: none;")
        self.lbl_result_title.setStyleSheet(f"color: {T['text_muted']}; background: transparent; border: none;")
        self.model_icon.setStyleSheet("background: transparent; border: none;")
        self.status_bar_w.setStyleSheet(f"background: {T['surface']}; border-top: 1px solid {T['border']};")
        self.status_lbl.setStyleSheet(f"color: {T['text_muted']};")

        self.step_indicator.apply_theme(T)
        self.result_badge.set_result(self.test_result, T)

    # ── TEST LOGIC ────────────────────────────────────────────────────────────
    def _run_test(self):
        if self.model_combo.currentIndex() == 0:
            self.status_lbl.setText("⚠  Please select a model first.")
            return

        self.run_btn.setEnabled(False)
        self.current_step = 0
        self.test_result = "—"
        self.result_badge.set_result("—", self.theme)
        self.step_indicator.set_step(0)
        self.status_lbl.setText("⏳  Test running — Scanning...")
        self._timer.start(1200)  # simulate step every 1.2s

    def _advance_step(self):
        self.current_step += 1
        step_names = ["Scanning...", "Processing data...", "Evaluating result...", "Saving to Excel..."]

        if self.current_step < len(PROCESSES):
            self.step_indicator.set_step(self.current_step)
            self.status_lbl.setText(f"⏳  {step_names[self.current_step]}")
        else:
            self._timer.stop()
            self.step_indicator.set_step(99)
            # Simulate result (demo: PASS if even model index, FAIL if odd)
            idx = self.model_combo.currentIndex()
            result = "PASS" if idx % 2 == 0 else "FAIL"
            self.test_result = result
            self.result_badge.set_result(result, self.theme)
            self._save_to_excel(result)
            self.run_btn.setEnabled(True)
            icon = "✅" if result == "PASS" else "❌"
            self.status_lbl.setText(f"{icon}  Test complete — {result}. Results saved.")

    def _save_to_excel(self, result):
        model = self.model_combo.currentText()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        image_path = self.last_image_path or "N/A"

        # Create or load workbook
        if os.path.exists(EXCEL_PATH):
            wb = openpyxl.load_workbook(EXCEL_PATH)
            ws = wb.active
        else:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Leak Test Results"
            ws.append(["Timestamp", "Model", "Result", "Image Path"])

        ws.append([now, model, result, image_path])
        os.makedirs(os.path.dirname(EXCEL_PATH), exist_ok=True)
        wb.save(EXCEL_PATH)

    def _open_excel(self):
        if not os.path.exists(EXCEL_PATH):
            self.status_lbl.setText("⚠  No results file yet. Run a test first.")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(EXCEL_PATH)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", EXCEL_PATH])
            else:
                subprocess.Popen(["xdg-open", EXCEL_PATH])
        except Exception as e:
            self.status_lbl.setText(f"Could not open file: {e}")


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = FreshLeakTestApp()
    window.show()
    sys.exit(app.exec_())
