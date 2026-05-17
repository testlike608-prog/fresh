"""
test_program.py
---------------
Tests شامله للبرنامج. بتختبر:
  1. قراءة program_mapping.xlsx
  2. استخراج Serial Number من الباركود
  3. تحديد البرنامج من الباركود
  4. TCPServer/TCPClient (محلي على 127.0.0.1)
  5. سلوك الـ watchdog لما الاتصال يتقطع
  6. result_reporting بيكتب صح في Excel
  7. debug_monitor snapshot

تشغيل:
    python test_program.py
    # أو
    python -m unittest test_program -v
"""

import os
import sys
import time
import socket
import threading
import unittest
import tempfile
import queue
from unittest import mock

# ─── Mock للموديولز اللي مش موجودة في بيئة الـ tests ─────────────────────────
# keyboard module مش موجود في Linux sandbox، نعمل stub
sys.modules.setdefault("keyboard", mock.MagicMock(KEY_DOWN="down"))
sys.modules.setdefault("pyodbc", mock.MagicMock())

# scanner بيستورد keyboard، فلازم نـ mock keyboard أولاً ثم نستورد scanner
import scanner  # noqa: E402

# ─── الآن نستورد باقي الموديولز ─────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ClientsClass  # noqa: E402
import excel as ex   # noqa: E402
import debug_monitor # noqa: E402


# ════════════════════════════════════════════════════════════════════════════
#                              Excel & Mapping
# ════════════════════════════════════════════════════════════════════════════
class TestProgramMapping(unittest.TestCase):
    """يتأكد إن ملف program_mapping.xlsx شغّال وبيرجع القيم الصحيحة."""

    def test_xlsx_readable(self):
        from openpyxl import load_workbook
        wb = load_workbook("program_mapping.xlsx")
        ws = wb.active
        self.assertGreater(ws.max_row, 1, "الملف لازم يحتوي على بيانات")

    def test_xlsx_via_pandas(self):
        import pandas as pd
        df = pd.read_excel("program_mapping.xlsx")
        self.assertIn("Capacity", df.columns)
        self.assertIn("program", df.columns)
        self.assertGreaterEqual(len(df), 5)

    def test_known_mapping_values(self):
        """E→1, F→1, G→2, ... P→5 زي ما اتفقنا."""
        app = self._make_app_without_starting_server()
        try:
            for char, expected_program in [("E", 1), ("F", 1), ("G", 2), ("M", 5), ("P", 5)]:
                fake_barcode = f"2605TL000001B{char}SI"
                result = app.determine_program_from_barcode(fake_barcode)
                self.assertEqual(int(result), expected_program,
                                 f"للحرف {char} متوقع {expected_program} لكن طلع {result}")
        finally:
            self._cleanup_app(app)

    def test_unknown_character_returns_message(self):
        app = self._make_app_without_starting_server()
        try:
            result = app.determine_program_from_barcode("2605TL000001BZSI")
            self.assertIsInstance(result, str)
            self.assertIn("غير موجود", result)
        finally:
            self._cleanup_app(app)

    def test_missing_file_handled(self):
        app = self._make_app_without_starting_server()
        try:
            result = app.determine_program_from_barcode(
                "2605TL000001BESI",
                excel_file_path="this_file_does_not_exist.xlsx",
            )
            self.assertIn("غير موجود", str(result))
        finally:
            self._cleanup_app(app)

    # ── helpers ──
    def _make_app_without_starting_server(self):
        """بنعمل App بدون ما الـ TCPServer يحجز بورت (عشان مايلخبطش الـ tests التانية)."""
        with mock.patch.object(ClientsClass.TCPServer, "start", return_value=True):
            app = ClientsClass.App()
        return app

    def _cleanup_app(self, app):
        try:
            app.stop()
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════════════
#                          Serial extraction
# ════════════════════════════════════════════════════════════════════════════
class TestSerialExtraction(unittest.TestCase):

    def setUp(self):
        with mock.patch.object(ClientsClass.TCPServer, "start", return_value=True):
            self.app = ClientsClass.App()

    def tearDown(self):
        self.app.stop()

    def test_extract_standard_barcode(self):
        # 2605TL0000001BISI → بين الحروف الأرقام هي 0000001
        serial = self.app.extract_serial_number("2605TL0000001BISI")
        # ملحوظة: regex بياخد أكبر سلسلة أرقام بين حروف
        # 2605TL... → أول مجموعه أرقام بعد حروف هي 0000001
        self.assertIsNotNone(serial)

    def test_extract_no_digits(self):
        serial = self.app.extract_serial_number("ABCDEF")
        self.assertIsNone(serial)

    def test_extract_short_barcode(self):
        serial = self.app.extract_serial_number("A1B")
        self.assertEqual(serial, "1")


# ════════════════════════════════════════════════════════════════════════════
#                            TCP server/client
# ════════════════════════════════════════════════════════════════════════════
def _get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class TestTCPServerClient(unittest.TestCase):
    """tests على TCPServer/TCPClient الحقيقيين عبر loopback."""

    def setUp(self):
        self.port = _get_free_port()
        self.server = ClientsClass.TCPServer(ip="127.0.0.1", port=self.port)
        self.assertTrue(self.server.start(), "السيرفر مش قادر يبدأ")
        self.received = []
        self.server.start_listening(self._cb)
        time.sleep(0.1)

    def tearDown(self):
        try:
            self.server.stop()
        except Exception:
            pass
        time.sleep(0.1)

    def _cb(self, client_sock, addr, data):
        self.received.append(data)

    def test_client_can_connect_and_send(self):
        client = ClientsClass.TCPClient("127.0.0.1", self.port, timeout=2.0, name="testclient")
        self.assertTrue(client.connect())
        self.assertTrue(client.send_only(b"hello"))
        time.sleep(0.3)
        self.assertIn(b"hello", self.received)
        client.disconnect()

    def test_disconnect_does_not_crash(self):
        """قبل التعديل كان بيرمي AttributeError على _stop_monitor."""
        client = ClientsClass.TCPClient("127.0.0.1", self.port, timeout=2.0)
        client.connect()
        # ده اللي كان بيقع البرنامج
        client.disconnect()
        self.assertFalse(client.connected)

    def test_client_name_appears_in_log(self):
        """قبل التعديل كان يطبع [][INFO] ... دلوقتي بيطبع [TCPClient-ip:port]."""
        client = ClientsClass.TCPClient("127.0.0.1", self.port, name="MyCobot")
        self.assertEqual(client.name, "MyCobot")
        client2 = ClientsClass.TCPClient("127.0.0.1", self.port)
        self.assertIn("127.0.0.1", client2.name)

    def test_get_last_received_before_listen_does_not_crash(self):
        """قبل التعديل كان يرمي AttributeError لو get_last_received اتنادت قبل start_listening."""
        client = ClientsClass.TCPClient("127.0.0.1", self.port)
        # ده كان بيرمي AttributeError
        result = client.get_last_received(block=False)
        self.assertIsNone(result)


# ════════════════════════════════════════════════════════════════════════════
#                               Watchdog
# ════════════════════════════════════════════════════════════════════════════
class TestConnectionWatchdog(unittest.TestCase):
    """يتأكد إن الـ watchdog بيلاحظ لما السيرفر يقفل."""

    def test_watchdog_detects_dead_server(self):
        port = _get_free_port()
        server = ClientsClass.TCPServer(ip="127.0.0.1", port=port)
        server.start()
        server.start_listening(lambda s, a, d: None)
        time.sleep(0.1)

        client = ClientsClass.TCPClient("127.0.0.1", port, timeout=1.0, name="watchdog-test")
        self.assertTrue(client.connect())
        client.start_reconnection_watchdog()
        self.assertTrue(client.connected)

        # نقفل السيرفر — الـ watchdog لازم يكتشف الفصل
        server.stop()

        # نستنى لحد ما الـ watchdog يلاحظ (interval=3s) — مع poll عشان مايبقاش flaky
        deadline = time.time() + 10
        while time.time() < deadline:
            if not client.connected:
                break
            time.sleep(0.2)

        self.assertFalse(
            client.connected,
            "watchdog ماشافش إن السيرفر اقفل — connected لسه True"
        )
        client._stop_monitor.set()  # نوقف الـ watchdog عشان مايعملش busy reconnect
        client.disconnect()


# ════════════════════════════════════════════════════════════════════════════
#                           Excel result reporting
# ════════════════════════════════════════════════════════════════════════════
class TestResultReporting(unittest.TestCase):

    def test_creates_new_file_with_header(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "results.xlsx")
            ex.result_reporting("BC001", "0000001", "pass", file_path=path)
            self.assertTrue(os.path.exists(path))

            import pandas as pd
            df = pd.read_excel(path)
            self.assertEqual(len(df), 1)
            self.assertIn("id", df.columns)
            self.assertEqual(df.iloc[0]["id"], "BC001")
            self.assertEqual(df.iloc[0]["result"], "pass")

    def test_appends_to_existing_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "results.xlsx")
            ex.result_reporting("BC001", "0000001", "pass", file_path=path)
            ex.result_reporting("BC002", "0000002", "fail", file_path=path)

            import pandas as pd
            df = pd.read_excel(path)
            self.assertEqual(len(df), 2)
            self.assertEqual(set(df["id"]), {"BC001", "BC002"})


# ════════════════════════════════════════════════════════════════════════════
#                          Scanner barcode handling
# ════════════════════════════════════════════════════════════════════════════
class TestScannerLogic(unittest.TestCase):
    """نختبر منطق _on_key_event بدون ما نشغل keyboard hook حقيقي."""

    def setUp(self):
        scanner.reset_queue()
        scanner._recorded_keys.clear()
        scanner.last_barcode = None

    def test_barcode_assembled_on_enter(self):
        # نمثل المستخدم بيكتب "ABC123" ثم Enter
        FakeEvt = type("E", (), {})
        for ch in "abc123":
            e = FakeEvt()
            e.event_type = "down"  # KEY_DOWN
            e.name = ch
            scanner._on_key_event(e)

        e = FakeEvt()
        e.event_type = "down"
        e.name = "enter"
        scanner._on_key_event(e)

        bc = scanner.queue_barcode.get_nowait()
        self.assertEqual(bc, "abc123")

    def test_duplicate_barcode_ignored(self):
        FakeEvt = type("E", (), {})
        # نقرأ أول مرة
        for ch in "x1":
            e = FakeEvt(); e.event_type = "down"; e.name = ch
            scanner._on_key_event(e)
        e = FakeEvt(); e.event_type = "down"; e.name = "enter"
        scanner._on_key_event(e)
        self.assertEqual(scanner.queue_barcode.qsize(), 1)

        # نقرأ نفس الباركود → لازم يتجاهل
        for ch in "x1":
            e = FakeEvt(); e.event_type = "down"; e.name = ch
            scanner._on_key_event(e)
        e = FakeEvt(); e.event_type = "down"; e.name = "enter"
        scanner._on_key_event(e)
        self.assertEqual(scanner.queue_barcode.qsize(), 1, "الباركود المتكرر مايتحطش في الكيو")


# ════════════════════════════════════════════════════════════════════════════
#                          Debug monitor
# ════════════════════════════════════════════════════════════════════════════
class TestDebugMonitor(unittest.TestCase):

    def test_snapshot_runs_without_app(self):
        text = debug_monitor.snapshot(app_ref=None)
        self.assertIn("MONITOR", text)
        self.assertIn("scanner", text)

    def test_snapshot_with_app_shows_clients(self):
        with mock.patch.object(ClientsClass.TCPServer, "start", return_value=True):
            app = ClientsClass.App()
        try:
            text = debug_monitor.snapshot(app_ref=app)
            # لازم يطلع اسم الـ clients
            self.assertIn("VisionClient_TRIG", text)
            self.assertIn("cobotClient", text)
        finally:
            app.stop()

    def test_is_enabled_respects_env(self):
        with mock.patch.dict(os.environ, {"DEBUG": "1"}):
            self.assertTrue(debug_monitor.is_enabled())
        with mock.patch.dict(os.environ, {"DEBUG": "0"}):
            self.assertFalse(debug_monitor.is_enabled())


# ════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # Verbose output
    unittest.main(verbosity=2)
