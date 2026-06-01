"""
gui_app.py
----------
الـ GUI الرئيسي للمشروع — PySide6.

الهيكل:
- Sidebar (يسار): Logo + nav buttons (Status / Logs / Settings) + Theme toggle
- Content area (يمين): QStackedWidget بـ 3 صفحات
  1. StatusPage   : إضاءات اتصال + المرحلة الحالية + إحصائيات
  2. LogsPage     : عرض الـ logs مع filtering + auto-scroll
  3. SettingsPage : IPs, ports, paths

تشغيل:
    python gui_app.py
"""

import sys
import os
import time

# نضمن إن المسار الحالي في sys.path (مهم للـ Nuitka build)
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QFont, QTextCursor, QTextCharFormat, QColor, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QPushButton, QStackedWidget, QFrame, QPlainTextEdit, QLineEdit,
    QComboBox, QCheckBox, QSizePolicy, QSpacerItem, QProgressBar, QButtonGroup,
    QScrollArea,
)

import gui_styles
from gui_log_bridge import QtLogEmitter, install_qt_handler
from gui_settings import SettingsPage as TestModeSettingsPage
from config import config


# ════════════════════════════════════════════════════════════════════
#                    Status Indicator (LED-style)
# ════════════════════════════════════════════════════════════════════
class StatusIndicator(QLabel):
    """دائرة ملوّنة صغيرة بتبيّن حالة الاتصال (أخضر=متصل، أحمر=مفصول)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self._state = False
        self._update_style()

    def set_state(self, connected: bool):
        if connected == self._state:
            return
        self._state = connected
        self._update_style()

    def _update_style(self):
        color = gui_styles.SUCCESS if self._state else gui_styles.DANGER
        # شيك حد خفيف عشان يكون فيه عمق
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                border-radius: 6px;
                border: 2px solid rgba(255, 255, 255, 0.1);
            }}
        """)


# ════════════════════════════════════════════════════════════════════
#                         Connection Card
# ════════════════════════════════════════════════════════════════════
class ConnectionCard(QFrame):
    """كارت بيعرض حالة connection واحد."""

    def __init__(self, name, ip, port, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setMinimumHeight(90)

        layout = QGridLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        # الصف الأول: indicator + name + status pill
        self.indicator = StatusIndicator()
        self.name_label = QLabel(name)
        self.name_label.setObjectName("CardValue")
        self.name_label.setStyleSheet("font-size: 14px; font-weight: 600;")

        self.status_pill = QLabel("DISCONNECTED")
        self.status_pill.setObjectName("StatusPillBad")
        self.status_pill.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.indicator, 0, 0)
        layout.addWidget(self.name_label, 0, 1)
        layout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum), 0, 2)
        layout.addWidget(self.status_pill, 0, 3)

        # الصف الثاني: ip:port + last seen
        self.endpoint_label = QLabel(f"{ip}:{port}")
        self.endpoint_label.setObjectName("CardSub")
        self.endpoint_label.setStyleSheet("color: #94A3B8; font-size: 12px;")
        layout.addWidget(self.endpoint_label, 1, 1, 1, 3)

    def set_connected(self, connected: bool):
        self.indicator.set_state(connected)
        if connected:
            self.status_pill.setText("CONNECTED")
            self.status_pill.setObjectName("StatusPillOk")
        else:
            self.status_pill.setText("DISCONNECTED")
            self.status_pill.setObjectName("StatusPillBad")
        # نطبق الـ style تاني بعد تغيير الـ objectName
        self.status_pill.style().unpolish(self.status_pill)
        self.status_pill.style().polish(self.status_pill)


# ════════════════════════════════════════════════════════════════════
#                            Stat Card
# ════════════════════════════════════════════════════════════════════
class StatCard(QFrame):
    """كارت إحصائي (Total / Pass / Fail / etc.)"""

    def __init__(self, title, value="0", sub="", color=None, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setMinimumHeight(90)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(2)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("CardTitle")

        self.value_label = QLabel(str(value))
        self.value_label.setObjectName("CardValue")
        if color:
            self.value_label.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: 700;")

        self.sub_label = QLabel(sub)
        self.sub_label.setObjectName("CardSub")

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.sub_label)
        layout.addStretch()

    def set_value(self, value, sub=None):
        self.value_label.setText(str(value))
        if sub is not None:
            self.sub_label.setText(sub)


# ════════════════════════════════════════════════════════════════════
#                          Stage Progress Card
# ════════════════════════════════════════════════════════════════════
class StageProgressCard(QFrame):
    """كارت كبير بيوضح المرحلة الحالية + الـ progress."""

    STAGES_DISPLAY = [
        ("IDLE",             "في الانتظار",            0),
        ("BARCODE_RECEIVED", "استقبال الباركود",       10),
        ("PROGRAM_LOOKUP",   "البحث عن البرنامج",      20),
        ("SENDING_PROGRAM",  "إرسال للكوبوت",          30),
        ("VISION_TEST_1",    "Vision test 1/6",      40),
        ("VISION_TEST_2",    "Vision test 2/6",      50),
        ("VISION_TEST_3",    "Vision test 3/6",      60),
        ("VISION_TEST_4",    "Vision test 4/6",      70),
        ("VISION_TEST_5",    "Vision test 5/6",      80),
        ("VISION_TEST_6",    "Vision test 6/6",      90),
        ("REPORTING",        "كتابة التقرير",         95),
        ("DONE",             "انتهى",                100),
        ("ERROR",            "خطأ",                  100),
    ]
    STAGE_MAP = {s[0]: s for s in STAGES_DISPLAY}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        # Title
        title = QLabel("المرحلة الحالية")
        title.setObjectName("CardTitle")
        layout.addWidget(title)

        # Stage label
        self.stage_label = QLabel("في الانتظار")
        self.stage_label.setObjectName("StageLabel")
        layout.addWidget(self.stage_label)

        # Sub info
        self.sub_label = QLabel("جاهز لاستقبال باركود جديد")
        self.sub_label.setObjectName("StageStep")
        layout.addWidget(self.sub_label)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setObjectName("StageProgress")
        self.progress.setMinimum(0)
        self.progress.setMaximum(100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(10)
        layout.addWidget(self.progress)

        # Steps dots
        steps_layout = QHBoxLayout()
        steps_layout.setSpacing(4)
        self.step_dots = []
        # نعرض كل المراحل ما عدا ERROR في الـ dots
        for stage_key, label, pct in self.STAGES_DISPLAY[:-1]:
            dot = QLabel("●")
            dot.setStyleSheet("color: #475569; font-size: 14px;")
            dot.setToolTip(label)
            steps_layout.addWidget(dot)
            self.step_dots.append((stage_key, dot))
        steps_layout.addStretch()
        layout.addLayout(steps_layout)

    def set_stage(self, stage_key, barcode=None, program=None, step=0, total_steps=6):
        entry = self.STAGE_MAP.get(stage_key, self.STAGE_MAP["IDLE"])
        _, label, pct = entry
        total_steps = max(1, min(6, int(total_steps or 6)))
        if stage_key.startswith("VISION_TEST") and step > 0:
            label = f"Vision test {step}/{total_steps}"
            pct = 30 + int((min(step, total_steps) / total_steps) * 60)

        self.stage_label.setText(label)

        # نبني الـ sub label
        parts = []
        if barcode:
            parts.append(f"باركود: {barcode}")
        if program is not None:
            parts.append(f"برنامج: {program}")
        if stage_key.startswith("VISION_TEST") and step > 0:
            parts.append(f"Step {step}/{total_steps}")
        sub = "  •  ".join(parts) if parts else "جاهز لاستقبال باركود جديد"
        self.sub_label.setText(sub)

        # Progress
        self.progress.setValue(pct)

        # Dots — نلون اللي عدّت
        passed_so_far = True
        for key, dot in self.step_dots:
            if key.startswith("VISION_TEST"):
                try:
                    if int(key.rsplit("_", 1)[1]) > total_steps:
                        dot.setVisible(False)
                        continue
                except Exception:
                    pass
            dot.setVisible(True)
            if key == stage_key:
                if stage_key == "ERROR":
                    dot.setStyleSheet(f"color: {gui_styles.DANGER}; font-size: 14px;")
                else:
                    dot.setStyleSheet(f"color: {gui_styles.ACCENT}; font-size: 14px;")
                passed_so_far = False
            elif passed_so_far:
                dot.setStyleSheet(f"color: {gui_styles.SUCCESS}; font-size: 14px;")
            else:
                dot.setStyleSheet("color: #475569; font-size: 14px;")

        # حالة الـ error
        if stage_key == "ERROR":
            self.stage_label.setStyleSheet(f"color: {gui_styles.DANGER}; font-size: 16px; font-weight: 600;")
        else:
            self.stage_label.setStyleSheet("")


# ════════════════════════════════════════════════════════════════════
#                             Status Page
# ════════════════════════════════════════════════════════════════════

class CameraPreviewWidget(QWidget):
    """
    ويدجت بيعرض صورة لايف من camera_hub.
    بيتحدث كل 80ms (~12fps) من خلال QTimer.
    لو الكاميرا مش شغالة بيعرض placeholder.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._preview_w = 320
        self._preview_h = 240

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # ── العنوان ──
        title_row = QHBoxLayout()
        title = QLabel("📷  Live Camera")
        title.setStyleSheet("font-size: 13px; font-weight: 600;")
        title_row.addWidget(title)
        title_row.addStretch()

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet("color: #4B5563; font-size: 16px;")
        title_row.addWidget(self._status_dot)
        layout.addLayout(title_row)

        # ── إطار الصورة ──
        frame_container = QFrame()
        frame_container.setFixedSize(self._preview_w, self._preview_h)
        frame_container.setStyleSheet(
            "background: #0F172A; border: 1px solid #1E293B; border-radius: 8px;"
        )
        frame_layout = QVBoxLayout(frame_container)
        frame_layout.setContentsMargins(0, 0, 0, 0)

        self._img_label = QLabel()
        self._img_label.setAlignment(Qt.AlignCenter)
        self._img_label.setFixedSize(self._preview_w, self._preview_h)
        self._img_label.setStyleSheet("border-radius: 8px;")
        self._show_placeholder()
        frame_layout.addWidget(self._img_label)

        layout.addWidget(frame_container)

        # ── QTimer للتحديث ~~12fps ──
        self._cam_timer = QTimer(self)
        self._cam_timer.timeout.connect(self._refresh_frame)
        self._cam_timer.start(80)   # 80ms ≈ 12fps

    def _show_placeholder(self):
        """يعرض رسالة لما الكاميرا مش شغالة."""
        self._img_label.clear()
        self._img_label.setText("الكاميرا غير متصلة\nأو لم تبدأ بعد")
        self._img_label.setStyleSheet(
            "color: #4B5563; font-size: 13px; border-radius: 8px;"
        )
        self._status_dot.setStyleSheet("color: #4B5563; font-size: 16px;")

    def _refresh_frame(self):
        """يسحب أحدث فريم من camera_hub ويعرضه."""
        try:
            import camera_hub
            frame = camera_hub.get_frame()
            if frame is None:
                self._show_placeholder()
                return

            import cv2
            # تحويل BGR → RGB عشان Qt
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch  = frame_rgb.shape
            qt_img    = QImage(
                frame_rgb.data, w, h,
                ch * w,
                QImage.Format_RGB888
            )
            pixmap = QPixmap.fromImage(qt_img).scaled(
                self._preview_w, self._preview_h,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self._img_label.setPixmap(pixmap)
            self._img_label.setStyleSheet("border-radius: 8px;")
            self._status_dot.setStyleSheet("color: #10B981; font-size: 16px;")  # أخضر

        except Exception:
            self._show_placeholder()


class StatusPage(QWidget):
    """صفحة Status: اتصالات + المرحلة + إحصائيات."""

    def __init__(self, get_state_fn, parent=None):
        super().__init__(parent)
        self.get_state_fn = get_state_fn

        # نلف الكل في scroll area عشان يطلع على شاشات صغيرة
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        main = QVBoxLayout(content)
        main.setContentsMargins(28, 24, 28, 24)
        main.setSpacing(18)

        # ── Header مع badge وزراران ──
        header_row = QHBoxLayout()
        title_box = QVBoxLayout()

        # Title row مع الـ STOPPED/RUNNING badge جنبه
        title_row = QHBoxLayout()
        title = QLabel("Status Dashboard")
        title.setObjectName("PageTitle")
        title_row.addWidget(title)

        # ⏹ STOPPED badge — افتراضياً بيكون ظاهر (البرنامج متوقف)
        self.state_badge = QLabel("⏹  STOPPED")
        self.state_badge.setObjectName("StateBadgeStopped")
        self.state_badge.setStyleSheet(
            f"background-color: rgba(239, 68, 68, 0.15);"
            f"color: {gui_styles.DANGER};"
            f"border: 1px solid {gui_styles.DANGER};"
            f"border-radius: 14px;"
            f"padding: 4px 14px;"
            f"font-size: 13px;"
            f"font-weight: 700;"
            f"letter-spacing: 1px;"
        )
        title_row.addWidget(self.state_badge)
        title_row.addStretch()

        title_box.addLayout(title_row)

        self.header_subtitle = QLabel("البرنامج متوقف — اضغط Start للبدء")
        self.header_subtitle.setObjectName("PageSubtitle")
        self.header_subtitle.setStyleSheet(f"color: {gui_styles.DANGER}; font-size: 13px;")
        title_box.addWidget(self.header_subtitle)

        header_row.addLayout(title_box, 1)

        # زرار فتح ملف Excel
        # ── زرار Start (الأخضر الكبير) ──
        self.start_btn = QPushButton("▶  Start")
        self.start_btn.setObjectName("StartBtn")
        self.start_btn.setToolTip("ابدأ تشغيل البرنامج (افتح الـ TCP server + connections)")
        self.start_btn.setMinimumWidth(110)
        self.start_btn.setStyleSheet(
            f"QPushButton#StartBtn {{ background-color: {gui_styles.SUCCESS}; color: white;"
            f"  border: none; border-radius: 6px; padding: 8px 18px;"
            f"  font-weight: 700; font-size: 14px; }}"
            f"QPushButton#StartBtn:hover {{ background-color: #059669; }}"
            f"QPushButton#StartBtn:disabled {{ background-color: #1F2937; color: #4B5563; }}"
        )
        self.start_btn.clicked.connect(self._on_start_clicked)
        header_row.addWidget(self.start_btn)

        # ── زرار Stop (الأحمر) ──
        self.stop_btn = QPushButton("■  Stop")
        self.stop_btn.setObjectName("StopBtn")
        self.stop_btn.setToolTip("إيقاف البرنامج (يقفل الـ connections)")
        self.stop_btn.setMinimumWidth(110)
        self.stop_btn.setStyleSheet(
            f"QPushButton#StopBtn {{ background-color: {gui_styles.DANGER}; color: white;"
            f"  border: none; border-radius: 6px; padding: 8px 18px;"
            f"  font-weight: 700; font-size: 14px; }}"
            f"QPushButton#StopBtn:hover {{ background-color: #DC2626; }}"
            f"QPushButton#StopBtn:disabled {{ background-color: #1F2937; color: #4B5563; }}"
        )
        self.stop_btn.setEnabled(False)  # مفصول لحد ما البرنامج يبدأ
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        header_row.addWidget(self.stop_btn)

        # فاصل
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #334155; max-width: 1px;")
        header_row.addWidget(sep)

        self.open_excel_btn = QPushButton("📊  فتح ملف التقرير")
        self.open_excel_btn.setObjectName("PrimaryBtn")
        self.open_excel_btn.setToolTip("افتح results_report.xlsx في البرنامج الافتراضي")
        self.open_excel_btn.clicked.connect(self._open_results_file)
        header_row.addWidget(self.open_excel_btn)

        # زرار فتح فولدر الـ logs
        self.open_logs_btn = QPushButton("📁  فولدر اللوج")
        self.open_logs_btn.setObjectName("SecondaryBtn")
        self.open_logs_btn.setToolTip("افتح فولدر logs اللي فيه threads.log و monitor.log")
        self.open_logs_btn.clicked.connect(self._open_logs_folder)
        header_row.addWidget(self.open_logs_btn)

        main.addLayout(header_row)

        # حفظ المرجع للـ app عشان نقدر نتحكم فيه
        self._app_ref_for_buttons = None
        self._app_init_error = None

        # ── Stage Progress (كارت كبير) ──
        self.stage_card = StageProgressCard()
        main.addWidget(self.stage_card)

        # ── Live Camera Preview ──
        cam_row = QHBoxLayout()
        self.camera_preview = CameraPreviewWidget()
        cam_row.addWidget(self.camera_preview)
        cam_row.addStretch()
        main.addLayout(cam_row)

        # ── Connection cards (2x2 grid) ──
        connections_title = QLabel("الاتصالات")
        connections_title.setStyleSheet("font-size: 13px; font-weight: 600; padding-top: 8px;")
        main.addWidget(connections_title)

        conn_grid = QGridLayout()
        conn_grid.setSpacing(12)
        self.conn_cards = {}

        # الـ mapping بين كل card key والـ config keys بتاعت الـ IP والـ Port
        self._card_config_keys = {
            "VisionClient_TRIG": ("vision_trig_ip",    "vision_trig_port"),
            "VisionClient_ID":   ("vision_id_ip",      "vision_id_port"),
            "cobotClient":       ("cobot_ip",          "cobot_port"),
            "triggerserver":     ("trigger_server_ip", "trigger_server_port"),
        }

        cards_info = [
            ("VisionClient_TRIG", "Vision (Trigger)",
             config.get("vision_trig_ip",    "127.0.0.1"), config.get("vision_trig_port",    8081)),
            ("VisionClient_ID",   "Vision (ID)",
             config.get("vision_id_ip",      "127.0.0.1"), config.get("vision_id_port",      8080)),
            ("cobotClient",       "Cobot",
             config.get("cobot_ip",          "192.168.57.2"), config.get("cobot_port",       9000)),
            ("triggerserver",     "Trigger Server",
             config.get("trigger_server_ip", "0.0.0.0"),   config.get("trigger_server_port", 5000)),
        ]
        for i, (key, label, ip, port) in enumerate(cards_info):
            card = ConnectionCard(label, ip, port)
            self.conn_cards[key] = card
            conn_grid.addWidget(card, i // 2, i % 2)
        main.addLayout(conn_grid)

        # نسجّل listener على config عشان لما يتحفظ أي IP/Port يتحدث تلقائياً
        config.add_listener(self._on_config_changed)

        # ── Stats grid (3 cards) ──
        stats_title = QLabel("الإحصائيات")
        stats_title.setStyleSheet("font-size: 13px; font-weight: 600; padding-top: 8px;")
        main.addWidget(stats_title)

        stats_grid = QGridLayout()
        stats_grid.setSpacing(12)
        self.total_card = StatCard("Total Scanned", "0", "إجمالي الباركودات")
        self.pass_card  = StatCard("Passed", "0", "نجحت", color=gui_styles.SUCCESS)
        self.fail_card  = StatCard("Failed", "0", "فشلت", color=gui_styles.DANGER)
        self.error_card = StatCard("Errors", "0", "أخطاء", color=gui_styles.WARNING)
        stats_grid.addWidget(self.total_card, 0, 0)
        stats_grid.addWidget(self.pass_card, 0, 1)
        stats_grid.addWidget(self.fail_card, 0, 2)
        stats_grid.addWidget(self.error_card, 0, 3)
        main.addLayout(stats_grid)

        # ── Queue/timing row ──
        queue_grid = QGridLayout()
        queue_grid.setSpacing(12)
        self.queue_card    = StatCard("Vision Queue", "0", "في الانتظار")
        self.last_bc_card  = StatCard("Last Barcode", "-", "آخر باركود")
        self.last_evt_card = StatCard("Last Event", "-", "آخر حدث")
        self.uptime_card   = StatCard("Uptime", "0s", "وقت التشغيل")
        queue_grid.addWidget(self.queue_card, 0, 0)
        queue_grid.addWidget(self.last_bc_card, 0, 1)
        queue_grid.addWidget(self.last_evt_card, 0, 2)
        queue_grid.addWidget(self.uptime_card, 0, 3)
        main.addLayout(queue_grid)

        main.addStretch()

        # Timer للتحديث
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(500)

    def _on_config_changed(self, key, value):
        """
        بيتنده من config listener لما أي قيمة تتغير.
        ممكن يتنده من أي ثريد، فبنستخدم QTimer.singleShot
        عشان التحديث يحصل على الـ main (GUI) thread بأمان.
        """
        # مش محتاجين نعمل حاجة لو المفتاح مش IP أو Port
        all_ip_port_keys = {
            k for pair in self._card_config_keys.values() for k in pair
        }
        if key in all_ip_port_keys:
            QTimer.singleShot(0, self._refresh_endpoints)

    def _refresh_endpoints(self):
        """يحدّث labels الـ IP:Port في كل connection card من config الحالي."""
        for card_key, card in self.conn_cards.items():
            ip_key, port_key = self._card_config_keys[card_key]
            ip   = config.get(ip_key,   "")
            port = config.get(port_key, "")
            card.endpoint_label.setText(f"{ip}:{port}")

    def _update_state_badge(self, is_running: bool):
        """يحدّث الـ badge وكلام الـ subtitle حسب وضع البرنامج."""
        if is_running:
            self.state_badge.setText("▶  RUNNING")
            self.state_badge.setStyleSheet(
                f"background-color: rgba(16, 185, 129, 0.15);"
                f"color: {gui_styles.SUCCESS};"
                f"border: 1px solid {gui_styles.SUCCESS};"
                f"border-radius: 14px;"
                f"padding: 4px 14px;"
                f"font-size: 13px;"
                f"font-weight: 700;"
                f"letter-spacing: 1px;"
            )
            self.header_subtitle.setText("البرنامج شغّال — يستقبل باركودات")
            self.header_subtitle.setStyleSheet(
                f"color: {gui_styles.SUCCESS}; font-size: 13px;"
            )
        else:
            self.state_badge.setText("⏹  STOPPED")
            self.state_badge.setStyleSheet(
                f"background-color: rgba(239, 68, 68, 0.15);"
                f"color: {gui_styles.DANGER};"
                f"border: 1px solid {gui_styles.DANGER};"
                f"border-radius: 14px;"
                f"padding: 4px 14px;"
                f"font-size: 13px;"
                f"font-weight: 700;"
                f"letter-spacing: 1px;"
            )
            self.header_subtitle.setText("البرنامج متوقف — اضغط Start للبدء")
            self.header_subtitle.setStyleSheet(
                f"color: {gui_styles.DANGER}; font-size: 13px;"
            )

    # ─── Start/Stop handlers ────────────────────────────────────────
    def set_app_ref(self, app_ref):
        """يربط الـ Status page بالـ App عشان أزرار Start/Stop تشتغل."""
        self._app_ref_for_buttons = app_ref
        self._app_init_error = None
        # نضبط حالة الأزرار حسب is_running الحالي
        is_running = bool(getattr(app_ref, "is_running", False)) if app_ref else False
        self.start_btn.setEnabled(not is_running)
        self.stop_btn.setEnabled(is_running)

    def set_app_init_error(self, error):
        self._app_ref_for_buttons = None
        self._app_init_error = str(error) if error else None
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _on_start_clicked(self):
        from PySide6.QtWidgets import QMessageBox
        if not self._app_ref_for_buttons:
            if self._app_init_error:
                QMessageBox.critical(
                    self,
                    "فشل إنشاء الـ App",
                    "الـ GUI اشتغل لكن الـ App الداخلي ما اتبناش.\n\n"
                    f"السبب:\n{self._app_init_error}",
                )
            else:
                QMessageBox.warning(self, "خطأ", "الـ App مش متربط بالـ GUI")
            return
        # نعطل الزرارين أثناء التشغيل عشان مايتدوسش مرتين
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        try:
            ok = self._app_ref_for_buttons.start()
            if not ok:
                QMessageBox.warning(
                    self, "فشل التشغيل",
                    "البرنامج مقدرش يبدأ. ممكن يكون الـ port محجوز من برنامج تاني.\n"
                    "اتأكد من الـ trigger_server_port في Settings."
                )
                self.start_btn.setEnabled(True)
                self.stop_btn.setEnabled(False)
                return
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"حصل خطأ أثناء التشغيل:\n{e}")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            return
        # شغّال — نخلي Stop active
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def _on_stop_clicked(self):
        from PySide6.QtWidgets import QMessageBox
        if not self._app_ref_for_buttons:
            return
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        try:
            self._app_ref_for_buttons.stop()
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"حصل خطأ أثناء الإيقاف:\n{e}")
        # متوقف — نخلي Start active
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    # ─── فتح ملفات بالبرنامج الافتراضي (cross-platform) ─────────────
    def _open_path(self, path, kind="file"):
        """يفتح file أو folder بالبرنامج الافتراضي على Windows/Linux/Mac."""
        import os, sys, subprocess
        from PySide6.QtWidgets import QMessageBox

        if not os.path.exists(path):
            QMessageBox.warning(
                self, "الملف مش موجود",
                f"الملف ده مش موجود لسه:\n\n{path}\n\n"
                f"هيتعمل أول ما باركود يتعالج (لو ده ملف التقرير)."
            )
            return

        try:
            if sys.platform == "win32":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            QMessageBox.critical(self, "خطأ في الفتح", f"مقدرتش أفتح {path}:\n\n{e}")

    def _open_results_file(self):
        """يفتح results_report.xlsx من المسار في config (يقبل التغيير من Test Mode)."""
        try:
            from config import config
            rel_path = config.get("results_report_file", "results_report.xlsx")
        except Exception:
            rel_path = "results_report.xlsx"
        # نخليه absolute عشان os.startfile يلاقيه
        import os
        path = os.path.abspath(rel_path)
        self._open_path(path, kind="file")

    def _open_logs_folder(self):
        """يفتح فولدر logs اللي فيه threads.log و monitor.log."""
        import os
        # نحدد الفولدر بناءً على مكان gui_app.py (نفس مكان الـ exe)
        here = os.path.dirname(os.path.abspath(__file__))
        logs_dir = os.path.join(here, "logs")
        os.makedirs(logs_dir, exist_ok=True)  # نضمن وجوده
        self._open_path(logs_dir, kind="folder")

    def _fmt_duration(self, seconds):
        if seconds < 0: return "-"
        s = int(seconds)
        h, rem = divmod(s, 3600)
        m, s = divmod(rem, 60)
        if h: return f"{h}h {m}m"
        if m: return f"{m}m {s}s"
        return f"{s}s"

    def _fmt_time_ago(self, ts):
        if not ts: return "-"
        delta = time.time() - ts
        if delta < 1:   return "الآن"
        if delta < 60:  return f"منذ {int(delta)}ث"
        if delta < 3600: return f"منذ {int(delta // 60)}د"
        return f"منذ {int(delta // 3600)}س"

    def refresh(self):
        try:
            state = self.get_state_fn()
        except Exception:
            return
        if not state:
            return

        # Start/Stop buttons sync (في حال App اتوقف من حد تاني)
        is_running = bool(state.get("is_running", False))
        if self._app_ref_for_buttons:
            # نسيب الـ enabled state يتزامن مع الواقع
            if self.start_btn.isEnabled() == is_running:
                self.start_btn.setEnabled(not is_running)
            if self.stop_btn.isEnabled() != is_running:
                self.stop_btn.setEnabled(is_running)

        # ⏹/▶ badge — يتغير بين STOPPED و RUNNING
        self._update_state_badge(is_running)

        # Connections
        conns = state.get("connections", {})
        for key, card in self.conn_cards.items():
            card.set_connected(conns.get(key, False))

        # Stage
        self.stage_card.set_stage(
            state.get("stage", "IDLE"),
            barcode=state.get("barcode"),
            program=state.get("program"),
            step=state.get("step", 0),
            total_steps=state.get("vision_test_count", 6),
        )

        # Stats
        stats = state.get("stats", {})
        self.total_card.set_value(stats.get("total", 0))
        self.pass_card.set_value(stats.get("pass", 0))
        self.fail_card.set_value(stats.get("fail", 0))
        self.error_card.set_value(stats.get("errors", 0))

        # Queues
        qsizes = state.get("queue_sizes", {})
        self.queue_card.set_value(
            qsizes.get("vision_queue", 0),
            f"Scanner: {qsizes.get('scanner_queue', 0)}",
        )

        # Last barcode + time
        self.last_bc_card.set_value(state.get("barcode") or "-")
        self.last_evt_card.set_value(self._fmt_time_ago(state.get("last_event_time", 0)))
        self.uptime_card.set_value(self._fmt_duration(state.get("uptime", 0)))


# ════════════════════════════════════════════════════════════════════
#                            Logs Page
# ════════════════════════════════════════════════════════════════════
class LogsPage(QWidget):
    """صفحة الـ Logs مع filter وauto-scroll."""

    def __init__(self, current_theme="dark", parent=None):
        super().__init__(parent)
        self._current_theme = current_theme
        self._max_lines = 5000
        self._auto_scroll = True
        self._level_filter = "ALL"
        self._text_filter = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        # ── Header ──
        title = QLabel("Logs")
        title.setObjectName("PageTitle")
        subtitle = QLabel("سجلات النظام المباشرة — يتم تحديثها فور حدوثها")
        subtitle.setObjectName("PageSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        # ── Toolbar ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        # Level filter
        self.level_combo = QComboBox()
        self.level_combo.addItems(["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.level_combo.currentTextChanged.connect(self._on_level_changed)
        toolbar.addWidget(QLabel("المستوى:"))
        toolbar.addWidget(self.level_combo)

        # Text filter
        self.filter_edit = QLineEdit()
        self.filter_edit.setObjectName("FilterEdit")
        self.filter_edit.setPlaceholderText("بحث في الـ logs...")
        self.filter_edit.textChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.filter_edit, 1)

        # Auto-scroll checkbox
        self.autoscroll_cb = QCheckBox("Auto-scroll")
        self.autoscroll_cb.setChecked(True)
        self.autoscroll_cb.toggled.connect(self._on_autoscroll)
        toolbar.addWidget(self.autoscroll_cb)

        # Clear button
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("SecondaryBtn")
        self.clear_btn.clicked.connect(self.clear)
        toolbar.addWidget(self.clear_btn)

        layout.addLayout(toolbar)

        # ── Log view ──
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("LogView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(self._max_lines)
        layout.addWidget(self.log_view, 1)

        # Counter
        self.counter_label = QLabel("0 entries")
        self.counter_label.setObjectName("CardSub")
        layout.addWidget(self.counter_label)

        self._entry_count = 0
        self._raw_entries = []  # نخزن الـ entries عشان نقدر نعمل filtering retroactively

    def set_theme(self, theme):
        self._current_theme = theme
        # نعيد رسم كل الـ entries بالألوان الجديدة
        self._redraw_all()

    def _on_level_changed(self, txt):
        self._level_filter = txt
        self._redraw_all()

    def _on_filter_changed(self, txt):
        self._text_filter = txt.lower()
        self._redraw_all()

    def _on_autoscroll(self, checked):
        self._auto_scroll = checked

    def clear(self):
        self.log_view.clear()
        self._raw_entries.clear()
        self._entry_count = 0
        self.counter_label.setText("0 entries")

    def _passes_filter(self, level, message):
        if self._level_filter != "ALL" and level != self._level_filter:
            return False
        if self._text_filter and self._text_filter not in message.lower():
            return False
        return True

    def _redraw_all(self):
        self.log_view.clear()
        for level, message in self._raw_entries:
            if self._passes_filter(level, message):
                self._append_styled(level, message)

    def _append_styled(self, level, message):
        color = gui_styles.LOG_COLORS.get(self._current_theme, gui_styles.LOG_COLORS["dark"]).get(level, "#E5E7EB")
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if level in ("WARNING", "ERROR", "CRITICAL"):
            fmt.setFontWeight(QFont.Bold)
        cursor.insertText(message + "\n", fmt)
        if self._auto_scroll:
            self.log_view.setTextCursor(cursor)
            self.log_view.ensureCursorVisible()

    def add_log(self, level, message):
        self._raw_entries.append((level, message))
        if len(self._raw_entries) > self._max_lines:
            self._raw_entries = self._raw_entries[-self._max_lines:]
        self._entry_count += 1
        self.counter_label.setText(f"{self._entry_count} entries")

        if self._passes_filter(level, message):
            self._append_styled(level, message)


# ════════════════════════════════════════════════════════════════════
#                          Settings Page
# ════════════════════════════════════════════════════════════════════
class SettingsPage(QWidget):
    """صفحة Settings — معلومات وعرض الـ paths."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        title = QLabel("Settings")
        title.setObjectName("PageTitle")
        subtitle = QLabel("إعدادات وروابط ملفات النظام")
        subtitle.setObjectName("PageSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Connection settings card
        conn_card = QFrame()
        conn_card.setObjectName("Card")
        conn_layout = QVBoxLayout(conn_card)
        conn_layout.setContentsMargins(20, 18, 20, 18)
        conn_layout.setSpacing(8)

        cct = QLabel("CONNECTIONS")
        cct.setObjectName("CardTitle")
        conn_layout.addWidget(cct)

        for label, value in [
            ("Vision (Trigger)",  "127.0.0.1:8081"),
            ("Vision (ID)",       "127.0.0.1:8080"),
            ("Cobot",             "192.168.57.2:9000"),
            ("Trigger Server",    "0.0.0.0:5000"),
        ]:
            row = QHBoxLayout()
            l = QLabel(label)
            l.setStyleSheet("font-weight: 500;")
            v = QLabel(value)
            v.setStyleSheet("color: #94A3B8; font-family: Consolas, monospace;")
            row.addWidget(l)
            row.addStretch()
            row.addWidget(v)
            conn_layout.addLayout(row)

        layout.addWidget(conn_card)

        # Files card
        files_card = QFrame()
        files_card.setObjectName("Card")
        fl = QVBoxLayout(files_card)
        fl.setContentsMargins(20, 18, 20, 18)
        fl.setSpacing(8)

        flt = QLabel("FILES & LOGS")
        flt.setObjectName("CardTitle")
        fl.addWidget(flt)

        for label, path in [
            ("Program mapping",  "program_mapping.xlsx"),
            ("Results report",   "results_report.xlsx"),
            ("Thread logs",      "logs/threads.log"),
            ("Monitor snapshots","logs/monitor.log"),
        ]:
            row = QHBoxLayout()
            l = QLabel(label)
            l.setStyleSheet("font-weight: 500;")
            v = QLabel(path)
            v.setStyleSheet("color: #94A3B8; font-family: Consolas, monospace;")
            row.addWidget(l)
            row.addStretch()
            row.addWidget(v)
            fl.addLayout(row)

        layout.addWidget(files_card)

        # About card
        about_card = QFrame()
        about_card.setObjectName("Card")
        al = QVBoxLayout(about_card)
        al.setContentsMargins(20, 18, 20, 18)
        al.setSpacing(8)

        at = QLabel("ABOUT")
        at.setObjectName("CardTitle")
        al.addWidget(at)

        about_text = QLabel(
            "Industrial Test Station Controller\n"
            "Version 1.0  •  Built with PySide6\n"
            "© 2026 Meeserv"
        )
        about_text.setStyleSheet("color: #94A3B8; line-height: 1.6;")
        al.addWidget(about_text)

        layout.addWidget(about_card)
        layout.addStretch()


# ════════════════════════════════════════════════════════════════════
#                            Main Window
# ════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):

    def __init__(self, app_ref=None, log_emitter=None, app_init_error=None, parent=None):
        super().__init__(parent)
        self.app_ref = app_ref
        self.log_emitter = log_emitter
        self._app_init_error = app_init_error

        self._theme = "dark"
        self.setWindowTitle("Test Station Controller")
        self.setMinimumSize(900, 600)
        self.resize(900, 600)

        # Central widget
        central = QWidget()
        central.setObjectName("MainWindow")
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar ──
        self.sidebar = self._build_sidebar()
        root.addWidget(self.sidebar)

        # ── Content stack ──
        self.content = QStackedWidget()
        self.content.setObjectName("ContentArea")

        # Pages
        get_state = self._get_state if app_ref else lambda: None
        self.status_page = StatusPage(get_state)
        self.logs_page   = LogsPage(self._theme)
        self.settings_page = TestModeSettingsPage()

        # ⚠ مهم: نربط الـ status_page بالـ app عشان Start/Stop buttons يشتغلوا
        # من غير السطر ده الزرار هيرمي "الـ App مش متربط بالـ GUI"
        if app_ref is not None:
            self.status_page.set_app_ref(app_ref)
        elif self._app_init_error:
            self.status_page.set_app_init_error(self._app_init_error)

        self.content.addWidget(self.status_page)
        self.content.addWidget(self.logs_page)
        self.content.addWidget(self.settings_page)

        root.addWidget(self.content, 1)

        # Connect logs
        if self.log_emitter:
            self.log_emitter.log_emitted.connect(self.logs_page.add_log)

        # Apply theme
        self._apply_theme()

    def _get_state(self):
        if self.app_ref and hasattr(self.app_ref, "get_state_snapshot"):
            try:
                return self.app_ref.get_state_snapshot()
            except Exception:
                return None
        return None

    def _build_sidebar(self):
        side = QWidget()
        side.setObjectName("Sidebar")
        side.setFixedWidth(220)

        layout = QVBoxLayout(side)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Brand
        brand = QLabel("⬢ TestStation")
        brand.setObjectName("SidebarTitle")
        layout.addWidget(brand)

        sub = QLabel("CONTROL PANEL")
        sub.setObjectName("SidebarSubtitle")
        layout.addWidget(sub)

        # Nav buttons
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        self.btn_group.buttonClicked.connect(self._on_nav_click)

        self.nav_buttons = {}
        items = [
            ("status",   "📊  Status"),
            ("logs",     "📜  Logs"),
            ("settings", "⚙️  Settings"),
        ]
        for key, label in items:
            btn = QPushButton(label)
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setProperty("page_key", key)
            layout.addWidget(btn)
            self.btn_group.addButton(btn)
            self.nav_buttons[key] = btn

        # Status default
        self.nav_buttons["status"].setChecked(True)

        layout.addStretch()

        # Theme toggle
        self.theme_btn = QPushButton("🌙  Dark Mode")
        self.theme_btn.setObjectName("ThemeToggle")
        self.theme_btn.clicked.connect(self.toggle_theme)
        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(14, 8, 14, 14)
        wl.addWidget(self.theme_btn)
        layout.addWidget(wrap)

        return side

    def _on_nav_click(self, btn):
        key = btn.property("page_key")
        idx = {"status": 0, "logs": 1, "settings": 2}.get(key, 0)
        self.content.setCurrentIndex(idx)

    def toggle_theme(self):
        self._theme = "light" if self._theme == "dark" else "dark"
        self._apply_theme()

    def _apply_theme(self):
        if self._theme == "dark":
            self.setStyleSheet(gui_styles.DARK_THEME)
            self.theme_btn.setText("Light Mode")
        else:
            self.setStyleSheet(gui_styles.LIGHT_THEME)
            self.theme_btn.setText("Dark Mode")
        self.logs_page.set_theme(self._theme)

    def closeEvent(self, event):
        if self.app_ref:
            try:
                self.app_ref.stop()
            except Exception:
                pass
        event.accept()


def main():
    qapp = QApplication(sys.argv)
    qapp.setApplicationName("Test Station Controller")

    emitter = QtLogEmitter()

    import thread_logger
    log = thread_logger.setup(watchdog_interval=2.0)

    # App without auto-start. User must press Start in the GUI.
    # scanner.start_listener() now runs inside App.start(), so no keyboard hook
    # is active until the user presses Start.
    app_ref = None
    app_init_error = None
    try:
        import ClientsClass as cc
        import debug_monitor
        app_ref = cc.App()
        debug_monitor.start(app_ref=app_ref, interval=2.0, force=True, verbose_console=False)
        log.info("=== GUI: App created (STOPPED by default) ===")
    except Exception as e:
        app_init_error = e
        log.exception(f"Could not create App: {e}")

    install_qt_handler(emitter, capture_stdout=True)

    win = MainWindow(app_ref=app_ref, log_emitter=emitter, app_init_error=app_init_error)
    win.show()
    log.info("=== GUI: window shown - default state is STOPPED, press Start to begin ===")
    return qapp.exec()


if __name__ == "__main__":
    sys.exit(main())
