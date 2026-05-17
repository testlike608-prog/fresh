import socket
import threading
import time
import queue
import pyodbc
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
                self._log_add("WARNING", "❌ Retrying in 5 seconds...")
                # نوم قابل للإيقاف فوراً عن طريق _stop_monitor.set()
                if self._stop_monitor.wait(timeout=5):
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

            # فحص كل 3 ثواني، لكن قابل للإيقاف فوراً
            if self._stop_monitor.wait(timeout=3):
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
class App():
    def __init__(self):

        self.vision_queue = queue.Queue()
        self.report_queue = queue.Queue()
        # علم لإيقاف العامل (sequance worker) عند الخروج
        self._stop_app = threading.Event()

        self.VisionClient_TRIG = TCPClient("127.0.0.1", 8081, name="VisionClient_TRIG")
        self.VisionClient_ID = TCPClient("127.0.0.1", 8080, name="VisionClient_ID")
        self.cobotClient = TCPClient("192.168.57.2", 9000, name="cobotClient")

        self.triggerserver = TCPServer(ip="0.0.0.0", port=5000)
        self.triggerserver.start() # تشغيل السيرفر فوراً في الكونستركتور
        

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


    def determine_program_from_barcode(self, barcode, excel_file_path="program_mapping.xlsx"):
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
        - بيبعت رقم البرنامج للكوبوت
        - بيلف 3 مرات: يبعت ID + يستنى نتيجه من الفيجن + يبلغ الكوبوت
        - يحدد pass/fail بناءً على لو فيه 0 في النتائج
        - يبعت إشارة نهائية للكوبوت (للبرامج 3-5 بس زي ما كان في الكود الأصلي)
        :return: "pass" أو "fail"
        """
        program = int(program)
        # برنامج 1 بيستخدم send_only بدل send_request زي ما كان في الكود الأصلي
        if program :
            self.cobotClient.send_request(program)
            list_of_results = []
            for i in range(3):
                x = 11 + i
                y = 21 + i
                self.VisionClient_ID.send_only(f"{barcode}_{i}")
                test_result = self.VisionClient_TRIG.send_request(x)
                list_of_results.append(test_result)
                # إشارة بين الاختبارات
                self.cobotClient.send_request(y)

            final_result = "fail" if 0 in list_of_results else "pass"
        # برامج 3-5 بتبعت إشارة نهائية للكوبوت (نفس منطق الكود الأصلي)
            self.cobotClient.send_only(0 if final_result == "fail" else 1)

        return final_result

    def _sequance_worker(self):
        """
        العامل الرئيسي: بيستلم باركودات من vision_queue وينفّذ تتابع الفحص.
        ده اللي كان غلط متحط جوّا الـ callback — دلوقتي في thread منفصل.
        """
        log = _get_thread_logger()
        log.info("Sequance worker started — waiting for barcodes in vision_queue...")

        while not self._stop_app.is_set():
            try:
                # blocking get مع timeout عشان نقدر نخرج لما _stop_app يتفعّل
                barcode = self.vision_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                program = self.determine_program_from_barcode(barcode)
                serial_number = self.extract_serial_number(barcode)

                # لو determine رجع نص خطأ بدل رقم، نعرضه ونتجاهل الباركود
                # نستخدم try/int بدل isinstance لأن pandas/numpy بترجع np.int64 مش int
                try:
                    program_int = int(program)
                except (TypeError, ValueError):
                    log.warning(f"Skipping barcode {barcode}: program lookup returned {program!r}")
                    continue

                final_result = self._run_test_program(program_int, barcode)
                ex.result_reporting(ID=barcode, serial_num=serial_number, result=final_result)
                log.info(f"Done barcode={barcode} program={program} result={final_result}")

            except Exception as e:
                log.exception(f"Error processing barcode {barcode}: {e}")
            finally:
                self.vision_queue.task_done()


    def run(self):
        self.VisionClient_TRIG.start_reconnection_watchdog()
        self.VisionClient_ID.start_reconnection_watchdog()
        self.cobotClient.start_reconnection_watchdog()
        self.triggerserver.start_listening(self.sequance_handler)

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

    def stop(self):
        """Stop all workers and disconnect cleanly."""
        self._stop_app.set()
        for client in (self.VisionClient_TRIG, self.VisionClient_ID, self.cobotClient):
            try:
                client.disconnect()
            except Exception:
                pass
        try:
            self.triggerserver.stop()
        except Exception:
            pass

    def stop(self):
        """Stop all workers and disconnect cleanly."""
        self._stop_app.set()
        for client in (self.VisionClient_TRIG, self.VisionClient_ID, self.cobotClient):
            try:
                client.disconnect()
            except Exception:
                pass
        try:
            self.triggerserver.stop()
        except Exception:
            pass
            pass
            pass
