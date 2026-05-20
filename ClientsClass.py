import socket
import threading
import time
import queue
try:
    import pyodbc
except ModuleNotFoundError:
    pyodbc = None
import os
import re
import textwrap
from datetime import datetime
import csv
import pandas as pd
from openpyxl import load_workbook
import openpyxl
from openpyxl.styles import Font
import scanner as sc
import excel as ex
from thread_logger import LoggedThread, get_logger as _get_thread_logger
import pandas as pd


def _to_bytes(message, is_hex=False):
    """
    تحويل أي قيمة لـ bytes جاهزه للإرسال على السوكيت.
    بيتعامل مع: bytes, str, int, float (وأي رقم).
    لو is_hex=True بيفسر الـ str كـ hex.

    قبل التعديل: send_only(1) كان بيرمي 'int' object has no attribute 'encode'.
    """
    if isinstance(message, bytes):
        return message
    if isinstance(message, bytearray):
        return bytes(message)
    if is_hex and isinstance(message, str):
        return bytes.fromhex(message)
    # نحوّل أي رقم لـ str قبل encode
    return str(message).encode('utf-8')


class TCPServer:
    def __init__(self, ip="0.0.0.0", port=5000, timeout=None, buffer_size=4096):
        """
        :param ip: "0.0.0.0" تعني الاستماع على كل كروت الشبكة المتاحة
        """
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.buffer_size = buffer_size
        self.server_sock = None
        self.running = False
        
        # إدارة الكلاينت المتصلين
        self.clients = [] # قائمة لتخزين السوكيتس الخاصة بالكلاينتس
        self._log_lock = threading.Lock()
        self._log_seq = 0
        self._log = list()
        self.name = "TCP_SERVER"

        # الكيوز
        self.shared_queue = queue.Queue()
        self.receive_queue = queue.Queue()
        


    def start_listening(self, callback):
        """
        كل اللي بنعمله هنا إننا بنسجل الفانكشن اللي هتشتغل 
        أول ما أي داتا توصل.
        """
        self.callback = callback
        self._log_add("INFO", "Callback registered. Waiting for incoming data...")


    
    def start(self):
        """بدء تشغيل السيرفر وحجز البورت"""
        try:
            self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # SO_REUSEADDR عشان لو السيرفر قفل يفتح تاني فوراً على نفس البورت
            self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_sock.bind((self.ip, self.port))
            self.server_sock.listen(5) # أقصى عدد من الاتصالات المنتظرة
            self.running = True
            
            # تشغيل خيط لاستقبال الكلاينتس الجدد
            self.accept_thread = LoggedThread(
                target=self._accept_loop,
                name=f"{self.name}-accept-loop",
                daemon=True,
            )
            self.accept_thread.start()
            
            self._log_add("INFO", f"Server started on {self.ip}:{self.port}")
            return True
        except Exception as e:
            self._log_add("ERROR", f"Failed to start server: {e}")
            return False

    def _accept_loop(self):
        """لوب دائم لاستقبال أي كلاينت بيحاول يتصل"""
        while self.running:
            try:
                client_sock, addr = self.server_sock.accept()
                self._log_add("INFO", f"New connection from {addr}")
                
                # تشغيل خيط خاص لكل كلاينت عشان السيرفر يخدم كذا حد في نفس الوقت
                client_handler = LoggedThread(
                    target=self._handle_client,
                    args=(client_sock, addr),
                    name=f"{self.name}-client-{addr[0]}:{addr[1]}",
                    daemon=True,
                )
                client_handler.start()
                self.clients.append(client_sock)
                
            except Exception as e:
                if self.running:
                    self._log_add("ERROR", f"Accept error: {e}")
                break

    
    
    def _handle_client(self, client_sock, addr):
        """
        الدالة دي بتشتغل في Thread منفصل لكل كلاينت بيتصل، 
        وبتفضل مستنية داتا منه.
        """
        while self.running:
            try:
                # السطر ده بيفضل عامل بلوك (واقف) لحد ما الكلاينت يبعت داتا
                data = client_sock.recv(self.buffer_size)
                
                if not data:
                    # لو الداتا فاضية، معناه إن الكلاينت قفل الاتصال
                    break
                
                self._log_add("INFO", f"Received from {addr}: {data}")
                
                # ============== السحر كله هنا ==============
                # أول ما الداتا توصل، ننده الـ Callback فوراً
                if hasattr(self, 'callback') and self.callback:
                    try:
                        # بنبعت الـ client_sock (عشان لو حبيت ترد عليه)، والـ addr، والـ data
                        self.callback(client_sock, addr, data)
                    except Exception as cb_err:
                        self._log_add("ERROR", f"Error inside callback: {cb_err}")
                # ==========================================

            except Exception as e:
                self._log_add("WARNING", f"Client {addr} disconnected: {e}")
                break
        
        # لما اللوب يخلص (الكلاينت يقفل)، ننظف السوكيت
        client_sock.close()
        if client_sock in self.clients:
            self.clients.remove(client_sock)
        self._log_add("INFO", f"Connection closed for {addr}")  
    
    def broadcast(self, message, is_hex=False):
        """إرسال رسالة لكل الكلاينتس المتصلين حالياً"""
        data_to_send = self._prepare_data(message, is_hex)
        for client in self.clients:
            try:
                client.sendall(data_to_send)
            except:
                pass # هنا السوكيت غالباً ميت، الـ handle_client هينظفه

    def _prepare_data(self, message, is_hex):
        return _to_bytes(message, is_hex)

    def stop(self):
        """إيقاف السيرفر تماماً"""
        self.running = False
        for client in self.clients:
            client.close()
        if self.server_sock:
            self.server_sock.close()
        self._log_add("INFO", "Server stopped.")

    def _log_add(self, level: str, msg: str):
        with self._log_lock:
            self._log_seq += 1
            self._log.append((self._log_seq, time.time(), level, msg))
        print(f"[{self.name}][{level}] {msg}")

    def get_last_received(self, block=False, timeout=None):
        try:
            return self.receive_queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None


# General Class
class  TCPClient():
    def __init__(self, ip, port, timeout=None, buffer_size=4096, name=None):
        """
        :param timeout: لو خليته None هيفضل مستني للأبد لحد ما السيرفر يرد
        :param name: اسم اختياري للعميل يظهر في اللوج (مفيد لما يكون عندك أكتر من client)
        """
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.buffer_size = buffer_size
        self.sock = None  # هنا هنحتفظ بالسوكيت عشان يفضل مفتوح
        self.connected = False
        self._send_queue: "queue.Queue[dict]" = queue.Queue()
        self._log_lock = threading.Lock()
        self._log_seq = 0
        self._log = list()
        # اسم افتراضي معبّر بدل ما يطلع [][INFO] في اللوج
        self.name = name if name else f"TCPClient-{ip}:{port}"
        self.current_program_label =""
        self.current_program_data=""

        # ── علم لإيقاف monitors و listeners ──────────────────────────────
        self._stop_monitor = threading.Event()
        # قفل بيمنع التداخل بين send_request و watchdog ping
        self._send_lock = threading.Lock()

        # كيو الاستقبال (ينعمل من بدري عشان get_last_received مايرميش AttributeError)
        self.receive_queue = queue.Queue()

        self.shared_queue = queue.Queue()
        self.shared_queue2= queue.Queue() #FOR DUMMY shared between scanner and data proccesing function
        self.shared_queue3= queue.Queue() # for dummies shared between scanner and i/o writer function

    def connect(self):
        """دالة لفتح الاتصال مرة واحدة"""
        try:
            if self.connected:
                print(f"[{self.ip}] Already connected.")
                return True
            
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout) # تحديد وقت الانتظار (أو None للانتظار الدائم)
            self.sock.connect((self.ip, self.port))
            self.connected = True
            # ضعه داخل دالة connect() بعد السطر self.sock.connect(...)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

            # لتعديل الوقت على ويندوز/لينكس ليصبح الفحص سريعاً (مثلاً كل 5 ثواني)
            if hasattr(socket, "SIO_KEEPALIVE_VALS"): # Windows
                # (تفعيل، الوقت بالمللي ثانية قبل بدء الفحص، الوقت بين الفحص والتالي)
                self.sock.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 5000, 3000))
            elif hasattr(socket, "TCP_KEEPIDLE"): # Linux
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 5)
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 3)
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
            print(f"[{self.ip}] : [{self.port}] Connected successfully.")
            return True
        except Exception as e:
            print(f"[{self.ip}] : [{self.port}] Connection Failed: {e}")
            self.connected = False
            return False
            
    def ensure_connected(self):
        """تتأكد إننا متصلين، تحاول لحد ما تتصل أو يتم إيقاف الـ monitor."""
        while not self.connected and not self._stop_monitor.is_set():
            self._log_add("INFO", f"Trying to reconnect to {self.ip}...")
            if self.connect():
                self._log_add("INFO", "✅ Reconnected successfully!")
                break
            else:
                try:
                    from config import config as _cfg
                    delay = float(_cfg.get("reconnect_retry_delay", 5.0))
                except Exception:
                    delay = 5.0
                self._log_add("WARNING", f"❌ Retrying in {delay} seconds...")
                if self._stop_monitor.wait(timeout=delay):
                    break
    
    def start_reconnection_watchdog(self):
        """تشغيل خيط المراقبة في الخلفية"""
        thread = LoggedThread(
            target=self._connection_monitor,
            name=f"TCPClient-{self.ip}:{self.port}-reconnect-watchdog",
            daemon=True,
        )
        thread.start()

    def _connection_monitor(self):
        """
        watchdog حقيقي بيراقب الاتصال بدون ما يبعت داتا للسيرفر.

        الطريقة:
        - بنستخدم select.select لمعرفه لو السوكيت لسه شغال (writable).
        - بنفحص لو فيه بيانات في الـ buffer جاهزة للقراءة (MSG_PEEK).
        - لو السوكيت اتقفل من الناحيه التانيه، recv بترجع b'' فبنعرف الاتصال راح.
        - مش بنبعت "ping" عشان مانلخبطش السيرفر الحقيقي بأوامر مش متوقعة.
        """
        import select
        log = _get_thread_logger()
        log.info(f"Connection watchdog started for {self.name}")

        while not self._stop_monitor.is_set():
            if not self.connected:
                # لو لقيناه فصل، نصلحه
                self.ensure_connected()
            else:
                # فحص بدون إرسال داتا
                try:
                    if self.sock is None:
                        self.connected = False
                        continue

                    # 1. فحص لو السوكيت writable (مش مقفول)
                    _, writable, errored = select.select([], [self.sock], [self.sock], 0.5)
                    if errored:
                        raise OSError("socket reported error via select")

                    # 2. peek لو في داتا قادمه عشان نعرف لو السيرفر قفل
                    self.sock.setblocking(False)
                    try:
                        peek = self.sock.recv(1, socket.MSG_PEEK)
                        if peek == b'':
                            # السيرفر قفل الاتصال
                            raise ConnectionResetError("peer closed connection (peek returned empty)")
                    except BlockingIOError:
                        # مفيش داتا — ده الوضع الطبيعي = الاتصال شغال
                        pass
                    finally:
                        try:
                            self.sock.setblocking(True)
                            self.sock.settimeout(self.timeout)
                        except Exception:
                            pass

                except Exception as e:
                    self._log_add("WARNING", f"Connection lost in background: {e}")
                    self.connected = False
                    if self.sock:
                        try:
                            self.sock.close()
                        except Exception:
                            pass
                        self.sock = None

            # فحص كل N ثواني (من config) — قابل للإيقاف فوراً
            try:
                from config import config as _cfg
                check_interval = float(_cfg.get("reconnect_check_interval", 3.0))
            except Exception:
                check_interval = 3.0
            if self._stop_monitor.wait(timeout=check_interval):
                break

        log.info(f"Connection watchdog stopped for {self.name}")
    
    def _get_sock(self):
         
        local_ip, local_port = self.sock.getsockname()
        return local_ip,local_port
   
    def send_request(self, message , is_hex=False):
        """
        إرسال واستقبال فقط (بدون إغلاق الاتصال)
        """
        if not self.connected or self.sock is None:
            print(f"[{self.ip}]:[{self.port}] Error: Not connected! Trying to connect...")
            self.ensure_connected()
           

        try:
            # 1. تجهيز الرسالة (بيتعامل مع int/str/bytes/float عبر _to_bytes)
            data_to_send = _to_bytes(message, is_hex)

            # 2. الإرسال
            self.sock.sendall(data_to_send)

            # 3. الاستقبال (هنا هيفضل مستني لحد ما السيرفر يرد)
            # طالما timeout=None أو وقت كبير، هيفضل واقف هنا (Blocking)
            response = self.sock.recv(self.buffer_size)

            return  response

        except (socket.timeout):
            print(f"[{self.ip}]:[{self.port}] Timeout: Server took too long to respond.")
            return None

        except (OSError, BrokenPipeError, ConnectionResetError, socket.error) as e:
            # ⚠️ هنا أهم تعديل: لو حصل أي خطأ في السوكيت (السيرفر قفل أو السلك اتشال)
            print(f"[{self.ip}]:[{self.port}] Connection Lost ({e}). Reconnecting...")
            
            self.connected = False
            if self.sock:
                try:
                    self.sock.close()
                except:
                    pass
                self.sock = None
            
            # محاولة إعادة الاتصال فوراً
            self.ensure_connected()
            
            # اختياري: ممكن تخليها تحاول تبعت الرسالة تاني بعد ما رجع الاتصال
            # return self.send_request(message, is_hex) 
            return None

        except Exception as e:
            print(f"[{self.ip}]:[{self.port}] General Error: {e}")
            return None
    
    '''
    def _start_monitoring(self):
        """بدء خيط المراقبة"""
        if self._monitor_thread is None or not self._monitor_thread.is_alive():
            self._stop_monitor.clear()
            self._monitor_thread = threading.Thread(target=self._monitor_connections, daemon=True)
            self._monitor_thread.start()

    def _monitor_connections(self):
        """فانكشن المراقبة اللي بتشيك على حالة الاتصال كل فترة"""
        print(f"[{self.ip}] Connection monitor started.")
        while not self._stop_monitor.is_set():
            if self.connected and self.sock:
                try:
                    # بنبعث "بيانات فارغة" عشان نختبر لو السوكيت لسه شغال (Keep-alive check)
                    # MSG_PEEK بيشوف البيانات من غير ما يسحبها من البافر
                    self.sock.send(b"", socket.MSG_DONTWAIT)
                except (OSError, BrokenPipeError):
                    print(f"[{self.ip}] Monitor detected broken connection!")
                    self.connected = False
                    # هنا ممكن تختار تنادي self.connect() تاني لو عايز Auto-reconnect
                    break
            time.sleep(5)  # شيك كل 5 ثواني مثلاً
     
   '''
    
    def disconnect(self):
        """إغلاق الاتصال وإيقاف المونيتور"""
        self._stop_monitor.set() # وقف اللوب في المونيتور
        self.connected = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = None
        self._log_add("INFO", f"[{self.ip}] Connection Closed.")

    def _log_add(self, level: str, msg: str):
        with self._log_lock:
            self._log_seq += 1
            self._log.append((self._log_seq, time.time(), level, msg))
            if len(self._log) > 5000:
                self._log = self._log[-3000:]
        print(f"[{self.name}][{level}] {msg}")
    
    def start_listening(self, callback=None):
        """
        دالة لبدء عملية الاستماع في Thread منفصل
        :param callback: دالة اختيارية يتم استدعاؤها فور استلام بيانات
        """
        # ملحوظه: receive_queue معرفه من الـ __init__ مرة واحدة بس،
        # عشان get_last_received يقدر يتنادى قبل أو بعد start_listening.
        self.listen_thread = LoggedThread(
            target=self._listen_loop,
            args=(callback,),
            name=f"TCPClient-{self.ip}:{self.port}-listen-loop",
            daemon=True,
        )
        self.listen_thread.start()
        self._log_add("INFO", f"[{self.ip}] : [{self.port}] Started listening for incoming data...")
        

    def _listen_loop(self, callback):
        """الـ Loop الداخلي اللي بيفضل مستني داتا"""
        while self.connected:
            try:
                # الكود هيفضل واقف هنا لحد ما السيرفر يبعت حاجة
                data = self.sock.recv(self.buffer_size)
                
                if not data:
                    # لو السيرفر بعت داتا فاضية معناها قفل الاتصال
                    print(f"[{self.ip}] Server closed the connection.")
                    self.connected = False
                    break
                
                if callback:
                    callback(data)
                # إضافة البيانات للكيو
                #self.receive_queue.put(data)

                # اختياري: تسجيل اللوج
                # self._log_add("INFO", f"Received data: {data}")

            except socket.timeout:
                continue # لو حصل تايم أوت يرجع يحاول يستقبل تاني
            except Exception as e:
                if self.connected:
                    print(f"[{self.ip}] Listening Error: {e}")
                    self.connected = False
                break

    def get_last_received(self, block=False, timeout=None):
        """دالة لسحب آخر داتا وصلت من الكيو"""
        try:
            return self.receive_queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None


    def send_only(self, message, is_hex=False):
            """
            إرسال رسالة فقط دون انتظار أي رد من السيرفر
            """
            if not self.connected or self.sock is None:
                print(f"[{self.ip}]:[{self.port}] Error: Not connected! Trying to connect...")
                if not self.connect():
                    return False

            try:
                # 1. تجهيز الرسالة (بيتعامل مع int/str/bytes/float)
                data_to_send = _to_bytes(message, is_hex)

                # 2. الإرسال (sendall تضمن وصول البيانات بالكامل للـ Buffer)
                self.sock.sendall(data_to_send)
                
                # اختياري: إضافة لوج للعملية
                # self._log_add("INFO", f"Message sent (No response expected): {message}")
                
                return True

            except (OSError, BrokenPipeError, ConnectionResetError, socket.error) as e:
                print(f"[{self.ip}]:[{self.port}] Send Failed ({e}). Reconnecting...")
                self.connected = False
                if self.sock:
                    try: self.sock.close()
                    except: pass
                    self.sock = None
                return False
                
            except Exception as e:
                print(f"[{self.ip}]:[{self.port}] General Error in send_only: {e}")
                return False

##################################################################
class AppStage:
    """
    المراحل اللي ممكن البرنامج يكون فيها — قراءتها بتقول لك إنت واقف فين.
    الـ GUI بيستخدمها يعرض الشكل والـ progress.
    """
    IDLE             = "IDLE"               # مفيش حاجه شغّاله — بنستنى باركود
    BARCODE_RECEIVED = "BARCODE_RECEIVED"   # وصلنا باركود جديد من الـ scanner
    PROGRAM_LOOKUP   = "PROGRAM_LOOKUP"     # بنبحث في program_mapping.xlsx
    SENDING_PROGRAM  = "SENDING_PROGRAM"    # بنبلّغ الكوبوت برقم البرنامج
    VISION_TEST_1    = "VISION_TEST_1"      # اختبار 1/6
    VISION_TEST_2    = "VISION_TEST_2"      # اختبار 2/6
    VISION_TEST_3    = "VISION_TEST_3"      # اختبار 3/6
    VISION_TEST_4    = "VISION_TEST_4"      # اختبار 4/6
    VISION_TEST_5    = "VISION_TEST_5"      # اختبار 5/6
    VISION_TEST_6    = "VISION_TEST_6"      # اختبار 6/6

    REPORTING        = "REPORTING"          # بنكتب في results_report.xlsx
    DONE             = "DONE"               # خلصنا الباركود ده
    ERROR            = "ERROR"              # حصل غلط

    # عدد دورات اختبار الرؤية في كل برنامج
    VISION_TEST_COUNT = 6

    @classmethod
    def get_vision_test_count(cls):
        try:
            from config import config as _cfg
            count = int(_cfg.get("vision_test_count", cls.VISION_TEST_COUNT))
        except Exception:
            count = cls.VISION_TEST_COUNT
        return max(1, min(cls.VISION_TEST_COUNT, count))

    # ترتيب المراحل عشان الـ progress bar
    ORDER = [
        IDLE, BARCODE_RECEIVED, PROGRAM_LOOKUP, SENDING_PROGRAM,
        VISION_TEST_1, VISION_TEST_2, VISION_TEST_3, VISION_TEST_4, VISION_TEST_5, VISION_TEST_6, REPORTING, DONE,
    ]

    LABELS = {
        IDLE:             "في الانتظار",
        BARCODE_RECEIVED: "تم استقبال باركود",
        PROGRAM_LOOKUP:   "البحث عن البرنامج",
        SENDING_PROGRAM:  "إرسال البرنامج للكوبوت",
        VISION_TEST_1:    "اختبار الرؤية 1/6",
        VISION_TEST_2:    "اختبار الرؤية 2/6",
        VISION_TEST_3:    "اختبار الرؤية 3/6",
        VISION_TEST_4:    "اختبار الرؤية 4/6",
        VISION_TEST_5:    "اختبار الرؤية 5/6",
        VISION_TEST_6:    "اختبار الرؤية 6/6",
        REPORTING:        "كتابة التقرير",
        DONE:             "انتهى",
        ERROR:            "خطأ",
    }


class App():
    def __init__(self):

        self.vision_queue = queue.Queue()
        self.report_queue = queue.Queue()
        # علم لإيقاف العامل (sequance worker) عند الخروج
        self._stop_app = threading.Event()

        # ── الـ IPs/Ports جايين من config (قابلين للتعديل من الـ GUI) ────
        # ملحوظه: __init__ بس بيبني الـ objects. مفيش حاجه بتتصل ولا server بيقوم
        # لحد ما يتنده start(). ده عشان الـ GUI تكون كاملة قبل البدء.
        from config import config as _cfg

        self.VisionClient_TRIG = TCPClient(
            _cfg.get("vision_trig_ip"), _cfg.get("vision_trig_port"),
            buffer_size=_cfg.get("tcp_buffer_size", 4096),
            name="VisionClient_TRIG",
        )
        self.VisionClient_ID = TCPClient(
            _cfg.get("vision_id_ip"), _cfg.get("vision_id_port"),
            buffer_size=_cfg.get("tcp_buffer_size", 4096),
            name="VisionClient_ID",
        )
        self.cobotClient = TCPClient(
            _cfg.get("cobot_ip"), _cfg.get("cobot_port"),
            buffer_size=_cfg.get("tcp_buffer_size", 4096),
            name="cobotClient",
        )

        # السيرفر اتعمل لكن مش هيقوم لحد ما start()
        self.triggerserver = TCPServer(
            ip=_cfg.get("trigger_server_ip"),
            port=_cfg.get("trigger_server_port"),
            buffer_size=_cfg.get("tcp_buffer_size", 4096),
        )

        # ── State tracking للـ GUI ─────────────────────────────────────
        # الـ GUI بيقرا الحالات دي كل ثانية ويعرضها في الـ Status panel
        self.current_stage = AppStage.IDLE
        self.current_barcode = None
        self.current_program = None
        self.current_step = 0     # رقم خطوة اختبار الرؤية الحالية
        self.last_event_time = time.time()
        self.start_time = time.time()
        self.stats = {
            "total":    0,
            "pass":     0,
            "fail":     0,
            "errors":   0,
            "skipped":  0,   # الباركودات اللي حرفها مش لاقيه في الإكسل
        }
        self._state_lock = threading.Lock()

        # ── Start/Stop control ─────────────────────────────────────────
        # الـ GUI بتستخدم is_running عشان تعرف لون الزرار وحالة البرنامج
        self.is_running = False
        self._start_stop_lock = threading.Lock()

    def _set_stage(self, stage, **extra):
        """ضبط الـ stage الحالي + أي حقول إضافية بـ thread-safe."""
        with self._state_lock:
            self.current_stage = stage
            self.last_event_time = time.time()
            for k, v in extra.items():
                setattr(self, k, v)

    def get_state_snapshot(self):
        """يرجع dict فيه كل الحالة الحالية — مفيد للـ GUI."""
        with self._state_lock:
            return {
                "is_running":      self.is_running,
                "stage":           self.current_stage,
                "barcode":         self.current_barcode,
                "program":         self.current_program,
                "step":            self.current_step,
                "vision_test_count": AppStage.get_vision_test_count(),
                "last_event_time": self.last_event_time,
                "uptime":          time.time() - self.start_time,
                "stats":           dict(self.stats),
                "queue_sizes": {
                    "vision_queue":  self.vision_queue.qsize(),
                    "report_queue":  self.report_queue.qsize(),
                    "scanner_queue": sc.queue_barcode.qsize(),
                },
                "connections": {
                    "VisionClient_TRIG": self.VisionClient_TRIG.connected,
                    "VisionClient_ID":   self.VisionClient_ID.connected,
                    "cobotClient":       self.cobotClient.connected,
                    "triggerserver":     self.triggerserver.running,
                },
            }
        

    def get_barcode_from_scanner(self):
        """
        ياخد الباركود من scanner.queue_barcode (اللي بيتعمل put فيه من thread الـ keyboard hook)
        ويحطه في vision_queue + report_queue.

        ملحوظة: شيلنا الـ flag و race condition عليه — الكيو نفسه thread-safe.
        """
        log = _get_thread_logger()
        while not self._stop_app.is_set():
            try:
                # هينتظر لحد ما يجي باركود أو نص ثانية (عشان نقدر نتحقق من _stop_app)
                barcode = sc.queue_barcode.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                self.vision_queue.put(barcode)
                self.report_queue.put(barcode)
                log.info(f"Barcode received and put in vision_queue: {barcode}")
            finally:
                sc.queue_barcode.task_done()

    def extract_serial_number(self, barcode):
        """
        تستخرج هذه الدالة الجزء الخاص بالسيريال (0000001) من النص الكامل للباركود.
        مثال للنص: '2605TL0000001BISI'
        """
        # الطريقة الأولى: باستخدام Regex للبحث عن الأرقام المحصورة بين الحروف
        self.cobotClient._log_add("INFO", f"Extracting serial number from barcode: {barcode}")
        match = re.search(r'[A-Z]+(\d+)[A-Z]+', barcode)
        if match:
            serial_part = match.group(1)
            return serial_part
        # الطريقة الثانية: إذا كان طول الكود ثابتاً دائماً في ماكينات Beko， يمكنك استخدام الـ Slicing مباشرة
        # return barcode_text[6:13]
        return None


    def determine_program_from_barcode(self, barcode, excel_file_path=None):
        # نقرأ الـ default من config لو ماتمررش
        if excel_file_path is None:
            from config import config as _cfg
            excel_file_path = _cfg.get("program_mapping_file", "program_mapping.xlsx")
        self.cobotClient._log_add("INFO", f"Determining program for barcode: {barcode}")
        target_char = barcode[-3]
        self.cobotClient._log_add("INFO", f"Target character for barcode {barcode}: {target_char}")

        try:
            # 1. قراءة ملف الإكسل بالكامل في ثانية واحدة
            # نفترض أن العمود الأول اسمه 'Character' والعمود الثاني اسمه 'Program'
            # لو ما عندكش أسماء أعمدة (Headers)، قولي عشان نعدلها برقم العمود
            df = pd.read_excel(excel_file_path)
            
            # تأكد من أسماء الأعمدة في ملفك، هنا فرضنا أن العمود الأول هو index 0 والثاني index 1
            char_column = df.columns[0]
            value_column = df.columns[1]

            # 2. البحث المباشر بدون loops
            match = df[df[char_column] == target_char]

            if not match.empty:
                # جلب القيمة المقابلة للحرف
                excel_value = match[value_column].values[0]
                self.cobotClient._log_add("INFO", f" got the value: {excel_value}")
                return excel_value
            else:
                self.cobotClient._log_add("INFO", f"Character {target_char} not found in Excel file.")
                return "الحرف غير موجود في ملف الإكسل."

        except FileNotFoundError:
            self.cobotClient._log_add("INFO", f"Excel file not found at path: {excel_file_path}")
            return "خطأ: ملف الإكسل غير موجود في المسار المحدد."
        except Exception as e:
            self.cobotClient._log_add("INFO", f"Unexpected error occurred with pandas: {e}")
            return f"حدث خطأ غير متوقع: {e}"

    # ─── Callback خفيف جداً يخرج فوراً ─────────────────────────────────────
    def sequance_handler(self, client_sock, addr, data):
        """
        callback بسيط جداً بيتنادى من TCPServer كل ما تيجي داتا.
        لازم يخلص بسرعة عشان مايلوكش thread الكلاينت.
        """
        try:
            self.cobotClient._log_add(
                "INFO",
                f"Trigger received from {addr}: {data!r} (len={len(data) if data else 0})"
            )
            # نخزن الـ trigger في receive_queue للسيرفر — العامل التاني هو اللي يقرأ
            self.triggerserver.receive_queue.put({"addr": addr, "data": data, "ts": time.time()})
        except Exception as e:
            self.cobotClient._log_add("ERROR", f"sequance_handler callback failed: {e}")

    # ─── العامل الحقيقي اللي بيشغل برامج الفحص ─────────────────────────
    def _run_test_program(self, program, barcode):
        """
        ينفّذ تتابع فحص واحد (المنطق المشترك بين برامج 1-5).
        بيحدّث self.current_stage في كل خطوة عشان الـ GUI تتابع.

        :return: "pass" أو "fail"
        """
        program = int(program)

        # 1. إرسال رقم البرنامج للكوبوت
        self._set_stage(AppStage.SENDING_PROGRAM, current_program=program)
        
        self.cobotClient.send_request(program)

        stage_map = {
            0: AppStage.VISION_TEST_1,
            1: AppStage.VISION_TEST_2,
            2: AppStage.VISION_TEST_3,
            3: AppStage.VISION_TEST_4,
            4: AppStage.VISION_TEST_5,
            5: AppStage.VISION_TEST_6,
        }

        list_of_results = []
        vision_test_count = AppStage.get_vision_test_count()
        # دورات اختبار الرؤية: نبعت ID للفيجن + trigger + نستلم النتيجه + نبلّغ الكوبوت
        for i in range(vision_test_count):
            self._set_stage(stage_map[i], current_step=i + 1)
            x = 11 + i   # 11..16 — قيم الـ trigger
            y = 21 + i   # 21..26 — إشارات بين الاختبارات للكوبوت
            self.VisionClient_ID.send_only(f"{barcode}_{i}")
            raw_result = self.VisionClient_TRIG.send_request(x)
            # ── BUG FIX ─────────────────────────────────────────────
            # send_request بيرجع bytes (زي b"0" أو b"1")، مش int. لو سيبناها
            # bytes الـ check `0 in list_of_results` هيدور على integer 0 ومش
            # هيلاقيه أبدًا في list of bytes → كل حاجه بتطلع pass غلط!
            # هنا بنحوّل الرد لـ int بشكل آمن.
            parsed = self._parse_vision_response(raw_result)
            self.cobotClient._log_add(
                "INFO",
                f"Vision test {i+1}/{vision_test_count}: raw={raw_result!r} parsed={parsed}",
            )
            list_of_results.append(parsed)
            self.cobotClient.send_request(y)

        # لو فيه أي 0 (أو None للأخطاء) → fail
        # 0 = fail من الفيجن
        # None = timeout أو error في الاتصال — نعتبره fail برضو لأمان
        final_result = "fail" if any(r == 0 or r is None for r in list_of_results) else "pass"
        self.cobotClient.send_only(0 if final_result == "fail" else 1)

        return final_result

    @staticmethod
    def _parse_vision_response(raw):
        """
        يحوّل رد الفيجن (bytes/str/None) لـ int أو None لو مش قادر.
        أمثلة:
          b"0"    → 0
          b"1"    → 1
          b"1\r\n"→ 1
          "1"     → 1
          0       → 0  (لو الـ socket رجّع int لأي سبب)
          None    → None  (timeout/error)
          b""     → None  (connection closed)
        """
        if raw is None:
            return None
        if isinstance(raw, (int, float)):
            return int(raw)
        if isinstance(raw, (bytes, bytearray)):
            text = raw.decode("utf-8", errors="ignore").strip()
        else:
            text = str(raw).strip()
        if not text:
            return None
        # نحاول int مباشرة
        try:
            return int(text)
        except ValueError:
            pass
        # محاولة float ثم int (لو الرد جه "1.0" مثلاً)
        try:
            return int(float(text))
        except ValueError:
            return None

    def _sequance_worker(self):
        """العامل الرئيسي: بيستلم باركودات من vision_queue وينفّذ تتابع الفحص."""
        log = _get_thread_logger()
        log.info("Sequance worker started - waiting for barcodes in vision_queue...")

        while not self._stop_app.is_set():
            try:
                barcode = self.vision_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                # 1. وصل باركود جديد
                self._set_stage(
                    AppStage.BARCODE_RECEIVED,
                    current_barcode=barcode, current_step=0,
                )

                # 2. البحث عن البرنامج
                self._set_stage(AppStage.PROGRAM_LOOKUP)
                program = self.determine_program_from_barcode(barcode)
                serial_number = self.extract_serial_number(barcode)

                try:
                    program_int = int(program)
                except (TypeError, ValueError):
                    # الحرف مش موجود في الإكسل → نتجاهل الباركود ونرجع نستنى scan تاني
                    log.warning(
                        f"⚠ Barcode {barcode}: char not in mapping file "
                        f"(lookup returned {program!r}). Waiting for next scan..."
                    )
                    with self._state_lock:
                        self.stats["skipped"] += 1
                    # نرجع الـ stage لـ IDLE (مش ERROR) ونستنى الباركود اللي بعده
                    self._set_stage(
                        AppStage.IDLE,
                        current_barcode=None,
                        current_program=None,
                        current_step=0,
                    )
                    continue

                # 3. تنفيذ سيكوينس الاختبار (Cobot + Vision)
                final_result = self._run_test_program(program_int, barcode)

                # 4. كتابة التقرير
                self._set_stage(AppStage.REPORTING)
                ex.result_reporting(ID=barcode, serial_num=serial_number, result=final_result)

                # 5. تحديث الإحصائيات
                with self._state_lock:
                    self.stats["total"] += 1
                    self.stats[final_result] = self.stats.get(final_result, 0) + 1

                # 6. خلصنا
                self._set_stage(AppStage.DONE)
                log.info(f"Done barcode={barcode} program={program_int} result={final_result}")

                time.sleep(0.5)
                self._set_stage(AppStage.IDLE, current_step=0)

            except Exception as e:
                log.exception(f"Error processing barcode {barcode}: {e}")
                self._set_stage(AppStage.ERROR)
                with self._state_lock:
                    self.stats["errors"] += 1
            finally:
                self.vision_queue.task_done()

    def start(self):
        """
        يشغل البرنامج: يفتح الـ TCP server، يبدأ الـ reconnect watchdogs،
        ويشغل الـ workers. آمن للنداء أكتر من مرة.
        """
        log = _get_thread_logger()
        with self._start_stop_lock:
            if self.is_running:
                log.warning("App.start() called but already running")
                return True

            log.info("=" * 50)
            log.info("App: STARTING...")
            log.info("=" * 50)

            self._stop_app.clear()
            for client in (self.VisionClient_TRIG, self.VisionClient_ID, self.cobotClient):
                client._stop_monitor.clear()

            # 1. نشغّل الـ scanner listener — لازم يكون قبل أي حاجه عشان نلتقط
            #    الباركودات بمجرد ما المستخدم يدوس Start. مفيش keyboard hook قبل ذلك.
            try:
                sc.start_listener()
                log.info("Scanner listener started")
            except Exception as e:
                log.warning(f"Scanner listener could not start: {e}")

            # 2. نشغّل الـ TCP server
            if not self.triggerserver.start():
                log.error("App.start() failed: TCPServer.start() returned False")
                # نوقف الـ scanner اللي بدأناه
                try: sc.stop_listener()
                except Exception: pass
                return False
            self.triggerserver.start_listening(self.sequance_handler)

            self.VisionClient_TRIG.start_reconnection_watchdog()
            self.VisionClient_ID.start_reconnection_watchdog()
            self.cobotClient.start_reconnection_watchdog()

            LoggedThread(
                target=self.get_barcode_from_scanner,
                name="App-barcode-from-scanner",
                daemon=True,
            ).start()

            LoggedThread(
                target=self._sequance_worker,
                name="App-sequance-worker",
                daemon=True,
            ).start()

            self.is_running = True
            self.start_time = time.time()
            self._set_stage(AppStage.IDLE, current_step=0,
                            current_barcode=None, current_program=None)
            log.info("App: STARTED successfully")
            return True

    def run(self):
        """alias قديم - مازال يشتغل عشان الـ tests و main.py."""
        return self.start()

    def stop(self):
        """إيقاف البرنامج بشكل نضيف. قابل للتشغيل تاني بـ start()."""
        log = _get_thread_logger()
        with self._start_stop_lock:
            if not self.is_running:
                log.warning("App.stop() called but not running")
                return

            log.info("App: STOPPING...")
            self._stop_app.set()

            # نوقف الـ scanner listener (keyboard hook)
            try:
                sc.stop_listener()
                log.info("Scanner listener stopped")
            except Exception as e:
                log.warning(f"scanner.stop_listener failed: {e}")

            for client in (self.VisionClient_TRIG, self.VisionClient_ID, self.cobotClient):
                try:
                    client.disconnect()
                except Exception as e:
                    log.warning(f"client.disconnect failed: {e}")
            try:
                self.triggerserver.stop()
            except Exception as e:
                log.warning(f"server.stop failed: {e}")

            self.is_running = False
            self._set_stage(AppStage.IDLE, current_step=0,
                            current_barcode=None, current_program=None)
            log.info("App: STOPPED")
