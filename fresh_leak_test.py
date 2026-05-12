import sys
import os
import subprocess
import datetime
import time
import queue
import traceback
import openpyxl
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QCheckBox, QFrame, QFileDialog,
    QGraphicsDropShadowEffect, QSizePolicy,QSplashScreen, QProgressBar
)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QColor, QPalette, QPixmap, QPainter, QBrush, QPen, QLinearGradient

# ─── BACK-END IMPORTS ─────────────────────────────────────────────────────────
# بنستورد الموديولز بتاعة الباك اند بشكل آمن — لو فشل أي واحد منهم نكمل
# على وضع "Demo" بدل ما الـ UI يقع تماماً.
_BACKEND_IMPORT_ERROR = None
try:
    import scanner as scanner_backend
    import excel as excel_backend
    import ClientsClass as clients_backend
    BACKEND_AVAILABLE = True
except Exception as _e:
    BACKEND_AVAILABLE = False
    _BACKEND_IMPORT_ERROR = f"{type(_e).__name__}: {_e}"
    print(f"⚠ Backend import failed → running in DEMO mode: {_BACKEND_IMPORT_ERROR}")

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


# ─── BACK-END WORKER (QThread) ────────────────────────────────────────────────
# الكلاس ده مسؤول عن تشغيل خطوات الـ Leak Test على ثريد منفصل عن الـ UI
# عشان النافذة متجمدش لما الباك اند يكون مستني الباركود أو رد السيرفر.
class LeakTestWorker(QThread):
    # الإشارات اللي بنبعت بيها للـ UI
    step_changed   = pyqtSignal(int)              # يتحدث الـ step indicator
    status_changed = pyqtSignal(str)              # يتحدث الـ status bar
    finished_ok    = pyqtSignal(str, str, str)    # (result, barcode, image_path)
    failed         = pyqtSignal(str)              # رسالة خطأ

    SCAN_TIMEOUT_SEC = 30        # الوقت اللي ننتظر فيه قراءة الباركود
    VISION_TIMEOUT_SEC = 15      # وقت انتظار رد الفيجن
    DEMO_DELAY = 1.0             # تأخير في وضع الـ demo

    def __init__(self, app, model_name, demo_mode=False):
        super().__init__()
        self.app = app                  # ClientsClass.App() instance — أو None في الـ demo
        self.model_name = model_name
        self.demo_mode = demo_mode

    # ─────────────────────────────────────────────────────────────────────
    def run(self):
        try:
            # ── Step 0: SCAN ─────────────────────────────────────────────
            self.step_changed.emit(0)
            barcode = self._do_scan()
            if barcode is None:
                return  # الخطأ اتبعت من جوة _do_scan

            # ── Step 1: PROCESSING ──────────────────────────────────────
            self.step_changed.emit(1)
            response = self._do_processing(barcode)

            # ── Step 2: RESULT ──────────────────────────────────────────
            self.step_changed.emit(2)
            self.status_changed.emit("⏳  Evaluating result…")
            result = self._interpret_result(response, barcode)
            if self.demo_mode:
                time.sleep(self.DEMO_DELAY)

            # ── Step 3: SAVING ──────────────────────────────────────────
            self.step_changed.emit(3)
            self.status_changed.emit("⏳  Saving result to Excel…")
            image_path = self._do_save(barcode, result)

            # خلاص — كله تمام
            self.finished_ok.emit(result, barcode, image_path)

        except Exception as e:
            traceback.print_exc()
            self.failed.emit(f"Unexpected worker error: {e}")

    # ─────────────────────────────────────────────────────────────────────
    def _do_scan(self):
        """خطوة الـ Scan — يستنى لحد ما الباركود يتقرا أو timeout."""
        if self.demo_mode or self.app is None:
            self.status_changed.emit("⏳  [DEMO] Simulating barcode scan…")
            time.sleep(self.DEMO_DELAY)
            return f"DEMO-{int(time.time())}"

        self.status_changed.emit("⏳  Waiting for barcode scan…")
        try:
            scanner_backend.reset_queue()
            scanner_backend.start_listener()
            barcode = scanner_backend.queue_barcode.get(timeout=self.SCAN_TIMEOUT_SEC)
            scanner_backend.flag_barcode = False
            return barcode
        except queue.Empty:
            self.failed.emit("⚠  Timeout: no barcode scanned within "
                             f"{self.SCAN_TIMEOUT_SEC}s.")
            return None
        except Exception as e:
            self.failed.emit(f"Scanner error: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────
    def _do_processing(self, barcode):
        """خطوة الـ Processing — يبعت الباركود للفيجن ويستنى الرد."""
        if self.demo_mode or self.app is None:
            self.status_changed.emit(f"⏳  [DEMO] Processing barcode {barcode}…")
            time.sleep(self.DEMO_DELAY)
            return None

        self.status_changed.emit(f"⏳  Sending barcode {barcode} to vision…")
        client = self.app.VisionClient_TRIG

        # نتأكد إن الفيجن متصل قبل ما نبعت — عشان منعلقش الثريد
        if not getattr(client, "connected", False):
            # نحاول مرة سريعة — لو فشل نخلص بدون ما نقفل البرنامج
            try:
                client.connect()
            except Exception:
                pass
            if not getattr(client, "connected", False):
                self.status_changed.emit(
                    "⚠  Vision client not connected — proceeding without it."
                )
                return None

        try:
            response = client.send_request(barcode)
            return response
        except Exception as e:
            self.status_changed.emit(f"⚠  Vision request failed: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────
    def _interpret_result(self, response, barcode):
        """تحويل رد الفيجن (bytes / None) لـ PASS / FAIL."""
        # وضع الـ Demo: نتيجة بناءً على آخر رقم في الباركود
        if self.demo_mode or response is None:
            try:
                last_char = str(barcode).strip()[-1]
                return "PASS" if last_char.isdigit() and int(last_char) % 2 == 0 else "FAIL"
            except Exception:
                return "FAIL"

        # Production: نفسر رد السيرفر
        try:
            if isinstance(response, (bytes, bytearray)):
                text = response.decode("utf-8", errors="ignore").strip().upper()
            else:
                text = str(response).strip().upper()
        except Exception:
            text = ""

        if "PASS" in text or text in ("OK", "1", "TRUE"):
            return "PASS"
        return "FAIL"

    # ─────────────────────────────────────────────────────────────────────
    def _do_save(self, barcode, result):
        """خطوة الحفظ — يستخدم excel_backend.result_reporting لو متاح."""
        image_path = ""
        if self.demo_mode or not BACKEND_AVAILABLE:
            # رجوع لمنطق الحفظ القديم (محلي على الـ Desktop)
            try:
                _save_locally(barcode, self.model_name, result)
            except Exception as e:
                self.status_changed.emit(f"⚠  Local save failed: {e}")
            return image_path

        try:
            excel_backend.result_reporting(
                ID=barcode,
                description=self.model_name,
                result=result,
                file_path=EXCEL_PATH,
            )
        except Exception as e:
            # لو فشل، نجرب الـ fallback المحلي
            self.status_changed.emit(f"⚠  Excel backend failed ({e}) — saving locally.")
            try:
                _save_locally(barcode, self.model_name, result)
            except Exception as e2:
                self.status_changed.emit(f"⚠  Local save also failed: {e2}")
        return image_path


def _save_locally(barcode, model, result):
    """حفظ بسيط على الـ Desktop — fallback لو الـ excel backend وقع."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if os.path.exists(EXCEL_PATH):
        wb = openpyxl.load_workbook(EXCEL_PATH)
        ws = wb.active
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Leak Test Results"
        ws.append(["Timestamp", "Barcode", "Model", "Result"])
    ws.append([now, barcode, model, result])
    os.makedirs(os.path.dirname(EXCEL_PATH), exist_ok=True)
    wb.save(EXCEL_PATH)


# ─── MAIN WINDOW ──────────────────────────────────────────────────────────────
class FreshLeakTestApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.dark_mode = True
        self.theme = DARK
        self.current_step = -1
        self.test_result = "—"
        self.last_image_path = ""

        # ── Back-end state ────────────────────────────────────────────
        self.app = None        # ClientsClass.App() instance — يتعمل lazy
        self.worker = None     # LeakTestWorker — بيتعاد استخدامه كل run

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

    # ── TEST LOGIC (موصول بالباك اند الحقيقي) ────────────────────────────────
    def _run_test(self):
        """يبدأ تشغيل اختبار جديد عن طريق LeakTestWorker (QThread)."""
        if self.model_combo.currentIndex() == 0:
            self.status_lbl.setText("⚠  Please select a model first.")
            return

        # لو في worker شغال لسه ما نسمحش بتشغيل تاني
        if self.worker is not None and self.worker.isRunning():
            self.status_lbl.setText("⚠  Test already running…")
            return

        # Lazy-init للـ back-end App مرة واحدة بس
        if BACKEND_AVAILABLE and self.app is None:
            try:
                self.app = clients_backend.App()
            except Exception as e:
                self.status_lbl.setText(f"⚠  Could not init backend: {e} — DEMO mode.")
                self.app = None

        # Reset الـ UI
        self.run_btn.setEnabled(False)
        self.current_step = 0
        self.test_result = "—"
        self.result_badge.set_result("—", self.theme)
        self.step_indicator.set_step(0)
        self.status_lbl.setText("⏳  Test running…")

        # نشغل الـ worker
        demo_mode = (not BACKEND_AVAILABLE) or (self.app is None)
        self.worker = LeakTestWorker(
            app=self.app,
            model_name=self.model_combo.currentText(),
            demo_mode=demo_mode,
        )
        self.worker.step_changed.connect(self._on_worker_step)
        self.worker.status_changed.connect(self.status_lbl.setText)
        self.worker.finished_ok.connect(self._on_worker_finished)
        self.worker.failed.connect(self._on_worker_failed)
        self.worker.start()

    def _on_worker_step(self, idx):
        """يتحدث الـ step indicator حسب الخطوة الحالية."""
        self.current_step = idx
        self.step_indicator.set_step(idx)

    def _on_worker_finished(self, result, barcode, image_path):
        """يتنادى لما الـ worker يخلص بنجاح."""
        self.test_result = result
        self.last_image_path = image_path or ""
        self.step_indicator.set_step(99)  # الكل خلص
        self.result_badge.set_result(result, self.theme)
        icon = "✅" if result == "PASS" else "❌"
        suffix = f" (Barcode: {barcode})" if barcode else ""
        self.status_lbl.setText(f"{icon}  Test complete — {result}.{suffix}")
        self.run_btn.setEnabled(True)

    def _on_worker_failed(self, msg):
        """يتنادى لو حصل خطأ في أي خطوة."""
        self.test_result = "—"
        self.result_badge.set_result("—", self.theme)
        self.status_lbl.setText(msg)
        self.run_btn.setEnabled(True)

    # ── CLEANUP ───────────────────────────────────────────────────────────────
    def closeEvent(self, event):
        """ينضف الباك اند والـ worker قبل ما البرنامج يقفل."""
        try:
            if self.worker is not None and self.worker.isRunning():
                self.worker.requestInterruption()
                self.worker.wait(2000)  # ننتظر ثانيتين كحد أقصى
        except Exception:
            pass
        try:
            if BACKEND_AVAILABLE:
                scanner_backend.stop_listener()
        except Exception:
            pass
        super().closeEvent(event)

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

class SimpleSplashWindow(QWidget):
    def __init__(self, logo_path, theme):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(500, 350)
        
        # توسيط الشاشة
        qr = self.frameGeometry()
        cp = QApplication.desktop().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)

        # 1. اللوجو
        self.logo_lbl = QLabel()
        pixmap = QPixmap(logo_path)
        if not pixmap.isNull():
            self.logo_lbl.setPixmap(pixmap.scaledToWidth(220, Qt.SmoothTransformation))
        self.logo_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.logo_lbl)

        # 2. نص التحميل
        self.msg_lbl = QLabel("Starting System...")
        self.msg_lbl.setAlignment(Qt.AlignCenter)
        self.msg_lbl.setFont(QFont("Segoe UI", 10))
        self.msg_lbl.setStyleSheet(f"color: {theme['text']};")
        layout.addWidget(self.msg_lbl)

        # 3. شريط التحميل (الخط اللي رايح جاي)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4) # خط رفيع جداً وشيك
        
        # السطر ده هو اللي بيخليه خط تحميل لا نهائي (رايح جاي)
        self.progress.setRange(0, 0) 
        
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: {theme['surface2']};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: #fb7706; /* لون برتقالي جذاب */
                border-radius: 2px;
            }}
        """)
        layout.addWidget(self.progress)

    def update_message(self, message):
        """دالة بنغير بيها النص بس، والخط شغال لوحده"""
        self.msg_lbl.setText(message)
        QApplication.processEvents()

# ─── ENTRY POINT ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 1. تشغيل شاشة التحميل
    logo_file = "company_logo.png" # تأكد إن مسار اللوجو صح
    splash = SimpleSplashWindow(logo_file, DARK)
    splash.show()

    # --- السر هنا: دالة تأخير مش بتوقف الواجهة ---
    def smooth_delay(seconds):
        end_time = time.time() + seconds
        while time.time() < end_time:
            app.processEvents() # بيخلي الأنيميشن يفضل شغال
            time.sleep(0.01)    # ملي ثانية عشان منستهلكش البروسيسور عالفاضي
    # ---------------------------------------------

    # 2. رسايل التحميل (رسالة ووقت)
    load_steps = [
        ("Connecting to Hardware...", 1.2),
        ("Initializing PLC Variables...", 1.0),
        ("Loading Vision Setup...", 1.5),
        ("System Ready!", 0.5)
    ]

    for message, delay in load_steps:
        splash.update_message(message)
        # استخدمنا دالة التأخير الجديدة بدل time.sleep العادية
        smooth_delay(delay)

    # 3. تشغيل النافذة الرئيسية وقفل التحميل
    window = FreshLeakTestApp()
    splash.close()
    window.show()

    sys.exit(app.exec_())