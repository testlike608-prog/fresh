"""
gui_log_bridge.py
-----------------
يربط الـ thread_logger الموجود بالـ GUI:
- بنضيف QtLogHandler للوجر الأساسي
- كل ما يحصل log line، الـ handler بيعمل emit لإشارة Qt
- الـ GUI Log Viewer بيلسن للإشارة ويعرض الرسائل

كمان: redirect لـ stdout/stderr عشان أي print() يطلع في الـ GUI viewer برضو.
"""

import logging
import sys
from PySide6.QtCore import QObject, Signal

# نستورد thread_logger من الكود الأصلي
import thread_logger


class QtLogEmitter(QObject):
    """object صغير وبس عشان يكون عنده signal — مش بنرث من QtLogHandler عشان QObject."""
    log_emitted = Signal(str, str)  # (level, message)


class QtLogHandler(logging.Handler):
    """logging handler بيبعت كل سجل لـ Qt signal."""

    def __init__(self, emitter: QtLogEmitter):
        super().__init__()
        self.emitter = emitter
        self.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s",
            datefmt="%H:%M:%S",
        ))

    def emit(self, record):
        try:
            msg = self.format(record)
            self.emitter.log_emitted.emit(record.levelname, msg)
        except Exception:
            # لا نستخدم self.handleError() عشان sys.stderr اتعمله redirect
            # للـ logger نفسه وده بيسبب infinite recursion
            # نكتب على الـ original stderr مباشرة لو موجود
            try:
                original_stderr = getattr(sys, "_original_stderr", None)
                if original_stderr:
                    import traceback
                    traceback.print_exc(file=original_stderr)
            except Exception:
                pass


class StreamToLogger:
    """يحوّل أي write() لـ stdout/stderr لـ log.info — عشان print() يطلع في الـ GUI."""

    def __init__(self, logger, level=logging.INFO):
        self.logger = logger
        self.level = level
        self._buffer = ""
        self._in_write = False  # guard ضد الـ recursion

    def write(self, message):
        if not message or self._in_write:
            return
        self._in_write = True
        try:
            self._buffer += message
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                if line.strip():
                    self.logger.log(self.level, line.rstrip())
        except Exception:
            pass
        finally:
            self._in_write = False

    def flush(self):
        if self._buffer.strip() and not self._in_write:
            self._in_write = True
            try:
                self.logger.log(self.level, self._buffer.rstrip())
                self._buffer = ""
            except Exception:
                pass
            finally:
                self._in_write = False

    def isatty(self):
        return False


def install_qt_handler(emitter: QtLogEmitter, capture_stdout: bool = True):
    """
    ينصّب الـ handler على:
    1. thread_logger ("threadlog") — كل logs البرنامج
    2. debug_monitor logger
    3. root logger (catch-all)
    4. stdout/stderr (لو capture_stdout=True)
    """
    handler = QtLogHandler(emitter)
    handler.setLevel(logging.DEBUG)

    # نلصقه بكل الـ loggers المهمة
    for name in ("threadlog", "debug_monitor", ""):  # "" = root
        lg = logging.getLogger(name)
        # نتفادى إضافة الـ handler نفسه مرتين
        if not any(isinstance(h, QtLogHandler) for h in lg.handlers):
            lg.addHandler(handler)

    if capture_stdout:
        # نأخذ logger خاص للـ stdout عشان مايتغبشش الـ format
        stdout_logger = logging.getLogger("stdout")
        if not any(isinstance(h, QtLogHandler) for h in stdout_logger.handlers):
            stdout_logger.setLevel(logging.INFO)
            stdout_logger.propagate = False
            stdout_logger.addHandler(handler)

        stderr_logger = logging.getLogger("stderr")
        if not any(isinstance(h, QtLogHandler) for h in stderr_logger.handlers):
            stderr_logger.setLevel(logging.WARNING)
            stderr_logger.propagate = False
            stderr_logger.addHandler(handler)

        # نحتفظ بالـ original streams (مهم للـ Nuitka build)
        if not hasattr(sys, "_original_stdout"):
            sys._original_stdout = sys.stdout
            sys._original_stderr = sys.stderr
        sys.stdout = StreamToLogger(stdout_logger, logging.INFO)
        sys.stderr = StreamToLogger(stderr_logger, logging.WARNING)
