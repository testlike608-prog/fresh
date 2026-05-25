"""
gui_settings.py
---------------
Settings page بـ Test Mode محمي بباسوورد.

الميزات:
- بدون Test Mode: الـ fields read-only (للقراءة فقط)
- مع Test Mode: الـ fields قابلة للتعديل + زرار Save
- زرار Lock/Unlock بـ password
- زرار تغيير الباسوورد
- ملاحظة: بعض التعديلات (الـ IPs/Ports) محتاجه restart عشان تطبق
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QSpinBox, QDoubleSpinBox, QDialog, QDialogButtonBox,
    QMessageBox, QScrollArea, QSizePolicy, QSpacerItem, QFormLayout,
    QFileDialog, QListWidget, QComboBox,
)

import gui_styles
from config import config


# ════════════════════════════════════════════════════════════════════
#                        Password Dialog
# ════════════════════════════════════════════════════════════════════
class PasswordDialog(QDialog):
    """Dialog صغير بيطلب الباسوورد للدخول لـ Test Mode."""

    def __init__(self, parent=None, title="Test Mode Login", message="ادخل باسوورد Test Mode للتعديل"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(380)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        icon_row = QHBoxLayout()
        lock_icon = QLabel("🔒")
        lock_icon.setStyleSheet("font-size: 32px;")
        title_box = QVBoxLayout()
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 600;")
        msg_lbl = QLabel(message)
        msg_lbl.setStyleSheet("color: #94A3B8; font-size: 12px;")
        msg_lbl.setWordWrap(True)
        title_box.addWidget(title_lbl)
        title_box.addWidget(msg_lbl)
        icon_row.addWidget(lock_icon)
        icon_row.addLayout(title_box, 1)
        layout.addLayout(icon_row)

        # حقل الباسوورد
        self.pw_edit = QLineEdit()
        self.pw_edit.setObjectName("FilterEdit")
        self.pw_edit.setEchoMode(QLineEdit.Password)
        self.pw_edit.setPlaceholderText("الباسوورد")
        self.pw_edit.returnPressed.connect(self.accept)
        layout.addWidget(self.pw_edit)

        # رسالة خطأ
        self.error_lbl = QLabel("")
        self.error_lbl.setStyleSheet(f"color: {gui_styles.DANGER}; font-size: 11px;")
        self.error_lbl.setVisible(False)
        layout.addWidget(self.error_lbl)

        # الأزرار
        btns = QDialogButtonBox(QDialogButtonBox.Cancel)
        cancel_btn = btns.button(QDialogButtonBox.Cancel)
        cancel_btn.setObjectName("SecondaryBtn")
        cancel_btn.setText("إلغاء")

        ok_btn = QPushButton("دخول")
        ok_btn.setObjectName("PrimaryBtn")
        ok_btn.clicked.connect(self.accept)
        btns.addButton(ok_btn, QDialogButtonBox.AcceptRole)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self.pw_edit.setFocus()

    def get_password(self):
        return self.pw_edit.text()

    def show_error(self, msg):
        self.error_lbl.setText(msg)
        self.error_lbl.setVisible(True)
        self.pw_edit.clear()
        self.pw_edit.setFocus()


# ════════════════════════════════════════════════════════════════════
#                     Change Password Dialog
# ════════════════════════════════════════════════════════════════════
class ChangePasswordDialog(QDialog):
    """Dialog لتغيير الباسوورد."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("تغيير الباسوورد")
        self.setMinimumWidth(400)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        title_lbl = QLabel("🔑  تغيير الباسوورد")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title_lbl)

        form = QFormLayout()
        form.setSpacing(8)

        self.old_pw = QLineEdit()
        self.old_pw.setObjectName("FilterEdit")
        self.old_pw.setEchoMode(QLineEdit.Password)
        self.old_pw.setPlaceholderText("الباسوورد الحالي")

        self.new_pw = QLineEdit()
        self.new_pw.setObjectName("FilterEdit")
        self.new_pw.setEchoMode(QLineEdit.Password)
        self.new_pw.setPlaceholderText("باسوورد جديد (4 حروف على الأقل)")

        self.confirm_pw = QLineEdit()
        self.confirm_pw.setObjectName("FilterEdit")
        self.confirm_pw.setEchoMode(QLineEdit.Password)
        self.confirm_pw.setPlaceholderText("أكد الباسوورد الجديد")

        form.addRow("الباسوورد الحالي:", self.old_pw)
        form.addRow("الباسوورد الجديد:", self.new_pw)
        form.addRow("تأكيد الباسوورد:",   self.confirm_pw)
        layout.addLayout(form)

        self.error_lbl = QLabel("")
        self.error_lbl.setStyleSheet(f"color: {gui_styles.DANGER}; font-size: 11px;")
        self.error_lbl.setVisible(False)
        layout.addWidget(self.error_lbl)

        btns = QHBoxLayout()
        btns.addStretch()

        cancel_btn = QPushButton("إلغاء")
        cancel_btn.setObjectName("SecondaryBtn")
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("حفظ")
        save_btn.setObjectName("PrimaryBtn")
        save_btn.clicked.connect(self._on_save)

        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        layout.addLayout(btns)

    def _on_save(self):
        old = self.old_pw.text()
        new = self.new_pw.text()
        confirm = self.confirm_pw.text()

        if not config.verify_password(old):
            self._show_error("الباسوورد الحالي غلط")
            return
        if len(new) < 4:
            self._show_error("الباسوورد الجديد لازم يكون 4 حروف على الأقل")
            return
        if new != confirm:
            self._show_error("الباسوورد الجديد والتأكيد مش متطابقين")
            return

        if config.set_password(new):
            QMessageBox.information(self, "تم", "اتغيرت الباسوورد بنجاح.")
            self.accept()
        else:
            self._show_error("فشل تغيير الباسوورد")

    def _show_error(self, msg):
        self.error_lbl.setText(msg)
        self.error_lbl.setVisible(True)


# ════════════════════════════════════════════════════════════════════
#                       Settings Field Row
# ════════════════════════════════════════════════════════════════════
class FieldRow(QWidget):
    """صف فيه label + input field. الـ input بيكون disabled بشكل افتراضي."""

    def __init__(self, label, key, value, kind="text", parent=None):
        super().__init__(parent)
        self.key = key
        self.kind = kind

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(12)

        lbl = QLabel(label)
        lbl.setStyleSheet("font-weight: 500; min-width: 200px;")
        lbl.setMinimumWidth(200)
        layout.addWidget(lbl)

        if kind == "int":
            self.input = QSpinBox()
            if key == "vision_test_count":
                self.input.setRange(1, 30)
            else:
                self.input.setRange(0, 999999)
            self.input.setValue(int(value))
            self.input.setMinimumWidth(280)
        elif kind == "float":
            self.input = QDoubleSpinBox()
            self.input.setRange(0.1, 600.0)
            self.input.setSingleStep(0.5)
            self.input.setDecimals(1)
            self.input.setValue(float(value))
            self.input.setMinimumWidth(280)
        else:  # text
            self.input = QLineEdit(str(value))
            self.input.setObjectName("FilterEdit")
            self.input.setMinimumWidth(280)

        self.input.setEnabled(False)
        layout.addWidget(self.input, 1)

    def value(self):
        if self.kind in ("int",):
            return int(self.input.value())
        elif self.kind == "float":
            return float(self.input.value())
        return self.input.text()

    def set_value(self, value):
        if self.kind == "int":   self.input.setValue(int(value))
        elif self.kind == "float": self.input.setValue(float(value))
        else: self.input.setText(str(value))

    def set_editable(self, editable: bool):
        self.input.setEnabled(editable)


# ════════════════════════════════════════════════════════════════════
#                       Folder Row (مع زرار Browse)
# ════════════════════════════════════════════════════════════════════
class FolderRow(QWidget):
    """صف فيه label + حقل مسار + زرار Browse لاختيار فولدر من الجهاز."""

    kind = "folder"

    def __init__(self, label, key, value, parent=None):
        super().__init__(parent)
        self.key = key

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(12)

        lbl = QLabel(label)
        lbl.setStyleSheet("font-weight: 500; min-width: 200px;")
        lbl.setMinimumWidth(200)
        layout.addWidget(lbl)

        self.input = QLineEdit(str(value))
        self.input.setObjectName("FilterEdit")
        self.input.setMinimumWidth(200)
        self.input.setEnabled(False)
        layout.addWidget(self.input, 1)

        self.browse_btn = QPushButton("📂  Browse")
        self.browse_btn.setObjectName("SecondaryBtn")
        self.browse_btn.setEnabled(False)
        self.browse_btn.clicked.connect(self._on_browse)
        layout.addWidget(self.browse_btn)

    def _on_browse(self):
        start = self.input.text().strip()
        folder = QFileDialog.getExistingDirectory(
            self, "اختر فولدر صور النتيجة", start
        )
        if folder:
            self.input.setText(folder)

    def value(self):
        return self.input.text()

    def set_value(self, value):
        self.input.setText(str(value))

    def set_editable(self, editable: bool):
        self.input.setEnabled(editable)
        self.browse_btn.setEnabled(editable)


# ════════════════════════════════════════════════════════════════════
#                  Folder List Row (لفولدرات النسخ الاحتياطي)
# ════════════════════════════════════════════════════════════════════
class FolderListRow(QWidget):
    """
    محرّر لليستة فولدرات — كل سطر فولدر، مع أزرار إضافة وحذف.
    بيستخدم لفولدرات النسخ الاحتياطي لصور النتيجة.
    """

    kind = "folder_list"

    def __init__(self, label, key, values, parent=None):
        super().__init__(parent)
        self.key = key

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(8)
        lbl = QLabel(label)
        lbl.setStyleSheet("font-weight: 500;")
        top.addWidget(lbl)
        top.addStretch()

        self.add_btn = QPushButton("➕  إضافة فولدر")
        self.add_btn.setObjectName("SecondaryBtn")
        self.add_btn.setEnabled(False)
        self.add_btn.clicked.connect(self._on_add)
        top.addWidget(self.add_btn)

        self.remove_btn = QPushButton("🗑  حذف المحدد")
        self.remove_btn.setObjectName("SecondaryBtn")
        self.remove_btn.setEnabled(False)
        self.remove_btn.clicked.connect(self._on_remove)
        top.addWidget(self.remove_btn)
        layout.addLayout(top)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("FilterEdit")
        self.list_widget.setMaximumHeight(130)
        self.list_widget.setEnabled(False)
        for v in (values or []):
            self.list_widget.addItem(str(v))
        layout.addWidget(self.list_widget)

        hint = QLabel("كل صورة نتيجة هتتنسخ نسخة إضافية في كل الفولدرات دي.")
        hint.setStyleSheet("color: #94A3B8; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

    def _on_add(self):
        folder = QFileDialog.getExistingDirectory(
            self, "اختر فولدر نسخة احتياطية"
        )
        if not folder:
            return
        existing = {
            self.list_widget.item(i).text()
            for i in range(self.list_widget.count())
        }
        if folder in existing:
            QMessageBox.information(self, "موجود", "الفولدر ده مضاف بالفعل.")
            return
        self.list_widget.addItem(folder)

    def _on_remove(self):
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))

    def value(self):
        return [
            self.list_widget.item(i).text()
            for i in range(self.list_widget.count())
        ]

    def set_value(self, values):
        self.list_widget.clear()
        if isinstance(values, (list, tuple)):
            for v in values:
                self.list_widget.addItem(str(v))

    def set_editable(self, editable: bool):
        self.list_widget.setEnabled(editable)
        self.add_btn.setEnabled(editable)
        self.remove_btn.setEnabled(editable)


# ════════════════════════════════════════════════════════════════════
#               Scan Mode Row (Manual / Camera toggle)
# ════════════════════════════════════════════════════════════════════
class ScanModeRow(QWidget):
    """صف لاختيار وضع إدخال الباركود: كيبورد أو كاميرا."""

    kind = "combo"

    def __init__(self, label, key, value, parent=None):
        super().__init__(parent)
        self.key = key

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(12)

        lbl = QLabel(label)
        lbl.setStyleSheet("font-weight: 500; min-width: 200px;")
        lbl.setMinimumWidth(200)
        layout.addWidget(lbl)

        self.combo = QComboBox()
        self.combo.addItem("🖊  Manual Scanner (سكانر كيبورد)", "manual")
        self.combo.addItem("📷  Camera Scanner (كاميرا عادية)", "camera")
        self.combo.setMinimumWidth(280)
        self.combo.setEnabled(False)
        self.set_value(value)
        layout.addWidget(self.combo, 1)

    def value(self):
        return self.combo.currentData()

    def set_value(self, value):
        for i in range(self.combo.count()):
            if self.combo.itemData(i) == str(value):
                self.combo.setCurrentIndex(i)
                return

    def set_editable(self, editable: bool):
        self.combo.setEnabled(editable)


# ════════════════════════════════════════════════════════════════════
#               Camera Select Row (اختيار الكاميرا)
# ════════════════════════════════════════════════════════════════════
class CameraSelectRow(QWidget):
    """صف لاختيار الكاميرا مع زرار Detect للكشف عن الكاميرات المتاحة."""

    kind = "int"

    def __init__(self, label, key, value, parent=None):
        super().__init__(parent)
        self.key = key

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(12)

        lbl = QLabel(label)
        lbl.setStyleSheet("font-weight: 500; min-width: 200px;")
        lbl.setMinimumWidth(200)
        layout.addWidget(lbl)

        self.combo = QComboBox()
        self.combo.setMinimumWidth(200)
        self.combo.setEnabled(False)
        # قيمة افتراضية
        self.combo.addItem(f"Camera {int(value)}", int(value))
        layout.addWidget(self.combo, 1)

        self.detect_btn = QPushButton("🔍  اكتشاف الكاميرات")
        self.detect_btn.setObjectName("SecondaryBtn")
        self.detect_btn.setEnabled(False)
        self.detect_btn.setToolTip("يكتشف كل الكاميرات المتوفرة على الجهاز")
        self.detect_btn.clicked.connect(self._detect_cameras)
        layout.addWidget(self.detect_btn)

    def _detect_cameras(self):
        """يكتشف الكاميرات المتاحة بتجربة فتح أول 6 كاميرات."""
        try:
            import cv2
        except ImportError:
            QMessageBox.warning(self, "خطأ", "مكتبة OpenCV مش موجودة.\nركّب الأول:\n  pip install opencv-python")
            return

        from PySide6.QtWidgets import QApplication
        current_val = self.combo.currentData()
        self.detect_btn.setEnabled(False)
        self.detect_btn.setText("🔍  يكتشف...")
        QApplication.processEvents()

        found = []
        for i in range(6):
            # CAP_DSHOW أسرع على Windows
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                found.append(i)
                cap.release()

        self.combo.clear()
        if not found:
            self.combo.addItem("❌ مفيش كاميرات", -1)
        else:
            for idx in found:
                self.combo.addItem(f"📷  Camera {idx}", idx)
            # نرجع للقيمة اللي كانت محددة لو لسه موجودة
            for i in range(self.combo.count()):
                if self.combo.itemData(i) == current_val:
                    self.combo.setCurrentIndex(i)
                    break

        self.detect_btn.setText("🔍  اكتشاف الكاميرات")
        self.detect_btn.setEnabled(True)

    def value(self):
        v = self.combo.currentData()
        return int(v) if v is not None else 0

    def set_value(self, value):
        for i in range(self.combo.count()):
            if self.combo.itemData(i) == int(value):
                self.combo.setCurrentIndex(i)
                return
        # لو القيمة مش موجودة في الـ combo — نضيفها
        self.combo.clear()
        self.combo.addItem(f"Camera {int(value)}", int(value))

    def set_editable(self, editable: bool):
        self.combo.setEnabled(editable)
        self.detect_btn.setEnabled(editable)


# ════════════════════════════════════════════════════════════════════
#                           Settings Page
# ════════════════════════════════════════════════════════════════════
class SettingsPage(QWidget):
    """صفحة Settings مع Test Mode."""

    # signal بيتبعت لما الـ Test Mode يتفعل / يتلغي
    test_mode_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._test_mode = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        # ─── Header ───
        header_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Settings")
        title.setObjectName("PageTitle")
        subtitle = QLabel("الإعدادات قابلة للتعديل من Test Mode بدون إعادة بناء البرنامج")
        subtitle.setObjectName("PageSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header_row.addLayout(title_box)
        header_row.addStretch()

        # Test Mode badge
        self.mode_badge = QLabel("🔒 Read-only")
        self.mode_badge.setObjectName("StatusPillBad")
        header_row.addWidget(self.mode_badge)

        layout.addLayout(header_row)

        # ─── Test Mode bar ───
        mode_card = QFrame()
        mode_card.setObjectName("Card")
        mc_layout = QHBoxLayout(mode_card)
        mc_layout.setContentsMargins(20, 14, 20, 14)
        mc_layout.setSpacing(12)

        info = QVBoxLayout()
        mc_title = QLabel("Test Mode")
        mc_title.setStyleSheet("font-size: 14px; font-weight: 600;")
        self.mc_sub = QLabel("الإعدادات للقراءة فقط. ادخل Test Mode بالباسوورد عشان تعدل.")
        self.mc_sub.setObjectName("CardSub")
        self.mc_sub.setStyleSheet("color: #94A3B8; font-size: 12px;")
        info.addWidget(mc_title)
        info.addWidget(self.mc_sub)
        mc_layout.addLayout(info, 1)

        self.unlock_btn = QPushButton("🔓  دخول Test Mode")
        self.unlock_btn.setObjectName("PrimaryBtn")
        self.unlock_btn.clicked.connect(self._on_toggle_mode)
        mc_layout.addWidget(self.unlock_btn)

        layout.addWidget(mode_card)

        # ─── Connections card ───
        layout.addWidget(self._make_section_label("الاتصالات (Connections)"))
        conn_card = self._make_card([
            ("Vision (TRIG) IP",   "vision_trig_ip",      "text"),
            ("Vision (TRIG) Port", "vision_trig_port",    "int"),
            ("Vision (ID) IP",     "vision_id_ip",        "text"),
            ("Vision (ID) Port",   "vision_id_port",      "int"),
            ("Cobot IP",           "cobot_ip",            "text"),
            ("Cobot Port",         "cobot_port",          "int"),
            ("Trigger Server IP",  "trigger_server_ip",   "text"),
            ("Trigger Server Port","trigger_server_port", "int"),
        ])
        layout.addWidget(conn_card)

        # ─── Files card ───
        layout.addWidget(self._make_section_label("مسارات الملفات (File Paths)"))
        files_card = self._make_card([
            ("Program mapping", "program_mapping_file", "text"),
            ("Results report",  "results_report_file",  "text"),
        ])
        layout.addWidget(files_card)

        # ─── Result Images card ───
        layout.addWidget(self._make_section_label("صور النتيجة (Result Images)"))
        layout.addWidget(self._make_result_images_card())

        # ─── Test sequence card ───
        layout.addWidget(self._make_section_label("Test Sequence"))
        sequence_card = self._make_card([
            ("Vision test count", "vision_test_count", "int"),
        ])
        layout.addWidget(sequence_card)

        # ─── Intervals card ───
        layout.addWidget(self._make_section_label("الفترات الزمنية (Intervals — seconds)"))
        intervals_card = self._make_card([
            ("Watchdog interval",          "watchdog_interval",          "float"),
            ("Reconnect check interval",   "reconnect_check_interval",   "float"),
            ("Reconnect retry delay",      "reconnect_retry_delay",      "float"),
            ("Debug monitor interval",     "debug_monitor_interval",     "float"),
        ])
        layout.addWidget(intervals_card)

        # ─── Scan Input Mode card ───
        layout.addWidget(self._make_section_label("وضع قراءة الباركود (Scan Input Mode)"))
        layout.addWidget(self._make_scan_mode_card())

        # ─── Actions row ───
        actions_card = QFrame()
        actions_card.setObjectName("Card")
        al = QHBoxLayout(actions_card)
        al.setContentsMargins(20, 14, 20, 14)
        al.setSpacing(10)

        info_lbl = QLabel("ملاحظة: تغيير الـ IPs/Ports يحتاج إعادة تشغيل البرنامج")
        info_lbl.setStyleSheet(f"color: {gui_styles.WARNING}; font-size: 12px;")
        al.addWidget(info_lbl, 1)

        self.change_pw_btn = QPushButton("🔑  تغيير الباسوورد")
        self.change_pw_btn.setObjectName("SecondaryBtn")
        self.change_pw_btn.setEnabled(False)
        self.change_pw_btn.clicked.connect(self._on_change_password)
        al.addWidget(self.change_pw_btn)

        self.reset_btn = QPushButton("↺  استعادة الافتراضيات")
        self.reset_btn.setObjectName("SecondaryBtn")
        self.reset_btn.setEnabled(False)
        self.reset_btn.clicked.connect(self._on_reset)
        al.addWidget(self.reset_btn)

        self.save_btn = QPushButton("💾  حفظ التغييرات")
        self.save_btn.setObjectName("PrimaryBtn")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._on_save)
        al.addWidget(self.save_btn)

        layout.addWidget(actions_card)

        # ─── About ───
        about_card = QFrame()
        about_card.setObjectName("Card")
        ab = QVBoxLayout(about_card)
        ab.setContentsMargins(20, 14, 20, 14)
        ab.setSpacing(4)
        at = QLabel("ABOUT")
        at.setObjectName("CardTitle")
        ab.addWidget(at)
        ab_text = QLabel(
            "Industrial Test Station Controller\n"
            "Version 1.0 \n"
            "© 2026 Meeserv"
        )
        ab_text.setStyleSheet("color: #94A3B8; line-height: 1.6;")
        ab.addWidget(ab_text)

        # ضيف config file location
        try:
            from config import CONFIG_FILE
            path_lbl = QLabel(f"📁 Config file: {CONFIG_FILE}")
            path_lbl.setStyleSheet("color: #64748B; font-size: 11px; font-family: Consolas, monospace;")
            path_lbl.setWordWrap(True)
            ab.addWidget(path_lbl)
        except Exception:
            pass

        layout.addWidget(about_card)
        layout.addStretch()

    # ─── Helpers ────────────────────────────────────────────────────
    def _make_section_label(self, text):
        l = QLabel(text)
        l.setStyleSheet("font-size: 13px; font-weight: 600; padding-top: 4px;")
        return l

    def _make_card(self, fields):
        """يبني كارت بصفوف FieldRow."""
        card = QFrame()
        card.setObjectName("Card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 14, 20, 14)
        cl.setSpacing(2)

        for label, key, kind in fields:
            row = FieldRow(label, key, config.get(key, ""), kind=kind)
            self._track_row(row)
            cl.addWidget(row)

        return card

    def _make_result_images_card(self):
        """
        كارت صور النتيجة:
        - الفولدر الأساسي (FolderRow بزرار Browse)
        - فولدرات النسخ الاحتياطي (FolderListRow)
        كله للقراءة فقط لحد ما يتفتح Test Mode.
        """
        card = QFrame()
        card.setObjectName("Card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 14, 20, 14)
        cl.setSpacing(6)

        # الفولدر الأساسي
        primary_row = FolderRow(
            "فولدر صور النتيجة",
            "result_images_folder",
            config.get("result_images_folder", "result_images"),
        )
        self._track_row(primary_row)
        cl.addWidget(primary_row)

        # فاصل
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #1E293B;")
        cl.addWidget(sep)

        # فولدرات النسخ الاحتياطي
        backup_row = FolderListRow(
            "فولدرات نسخ إضافية (Backup)",
            "result_images_backup_folders",
            config.get("result_images_backup_folders", []),
        )
        self._track_row(backup_row)
        cl.addWidget(backup_row)

        return card

    def _make_scan_mode_card(self):
        """
        كارت وضع قراءة الباركود:
        - ScanModeRow: تبديل بين Manual (كيبورد) و Camera (كاميرا)
        - CameraSelectRow: اختيار الكاميرا مع زرار Detect
        """
        card = QFrame()
        card.setObjectName("Card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 14, 20, 14)
        cl.setSpacing(6)

        # hint في أعلى الكارت
        hint = QLabel(
            "اختار Manual لو عندك سكانر باركود (بيتصل كـ keyboard)، "
            "أو Camera لو عايز تقرأ الباركود بكاميرا عادية."
        )
        hint.setStyleSheet("color: #94A3B8; font-size: 11px;")
        hint.setWordWrap(True)
        cl.addWidget(hint)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #1E293B;")
        cl.addWidget(sep)

        # وضع الإدخال
        mode_row = ScanModeRow(
            "وضع القراءة",
            "scan_mode",
            config.get("scan_mode", "manual"),
        )
        self._track_row(mode_row)
        cl.addWidget(mode_row)

        # اختيار الكاميرا
        cam_row = CameraSelectRow(
            "الكاميرا المستخدمة",
            "camera_index",
            config.get("camera_index", 0),
        )
        self._track_row(cam_row)
        cl.addWidget(cam_row)

        return card

    def _track_row(self, row):
        if not hasattr(self, "_rows"): self._rows = []
        self._rows.append(row)

    # ─── Test Mode toggle ───────────────────────────────────────────
    def _on_toggle_mode(self):
        if self._test_mode:
            # خروج من Test Mode
            self._set_test_mode(False)
            return

        # دخول — نطلب الباسوورد
        dlg = PasswordDialog(self)
        while True:
            if dlg.exec() != QDialog.Accepted:
                return
            pw = dlg.get_password()
            if config.verify_password(pw):
                self._set_test_mode(True)
                return
            dlg.show_error("الباسوورد غلط — حاول تاني")

    def _set_test_mode(self, enabled: bool):
        self._test_mode = enabled
        for row in getattr(self, "_rows", []):
            row.set_editable(enabled)

        if enabled:
            self.mode_badge.setText("🔓 Test Mode")
            self.mode_badge.setObjectName("StatusPillOk")
            self.mc_sub.setText("Test Mode مفعّل — تقدر تعدل كل الإعدادات. اضغط حفظ لما تخلص.")
            self.unlock_btn.setText("🔒  قفل (خروج)")
            self.unlock_btn.setObjectName("SecondaryBtn")
            self.save_btn.setEnabled(True)
            self.change_pw_btn.setEnabled(True)
            self.reset_btn.setEnabled(True)
        else:
            self.mode_badge.setText("🔒 Read-only")
            self.mode_badge.setObjectName("StatusPillBad")
            self.mc_sub.setText("الإعدادات للقراءة فقط. ادخل Test Mode بالباسوورد عشان تعدل.")
            self.unlock_btn.setText("🔓  دخول Test Mode")
            self.unlock_btn.setObjectName("PrimaryBtn")
            self.save_btn.setEnabled(False)
            self.change_pw_btn.setEnabled(False)
            self.reset_btn.setEnabled(False)

        # نعيد تطبيق الـ style لإن الـ objectName اتغير
        for w in (self.mode_badge, self.unlock_btn):
            w.style().unpolish(w); w.style().polish(w)

        self.test_mode_changed.emit(enabled)

    # ─── Save ───────────────────────────────────────────────────────
    def _on_save(self):
        updates = {}
        for row in self._rows:
            val = row.value()
            if isinstance(val, str) and not val.strip():
                QMessageBox.warning(self, "خطأ", f"حقل {row.key} فاضي")
                return
            updates[row.key] = val

        changed = config.update_many(updates)
        if changed:
            QMessageBox.information(
                self, "تم الحفظ",
                f"اتحفظ {changed} تعديل في config.json.\n\n"
                f"ملاحظة: التعديلات على IP/Port محتاجة restart للبرنامج عشان تطبق."
            )
        else:
            QMessageBox.information(self, "مفيش تعديل", "مفيش حاجه اتغيرت من اللي محفوظ.")

    def _on_reset(self):
        reply = QMessageBox.question(
            self, "تأكيد",
            "هترجع كل الإعدادات للافتراضي. الباسوورد هيفضل زي ما هو.\n\nمتأكد؟",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes: return
        config.reset_to_defaults(keep_password=True)
        # نحدث الحقول
        for row in self._rows:
            row.set_value(config.get(row.key, ""))
        QMessageBox.information(self, "تم", "الإعدادات رجعت للافتراضي.")

    def _on_change_password(self):
        ChangePasswordDialog(self).exec()
