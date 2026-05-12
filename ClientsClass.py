import socket
import threading
import time
import queue
import pyodbc
import os
import textwrap
from datetime import datetime
import csv
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font
import scanner as sc



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

        # الكيوز (كما في الكود الخاص بك)
        self.shared_queue = queue.Queue()
        self.receive_queue = queue.Queue()

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
            self.accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
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
                client_handler = threading.Thread(
                    target=self._handle_client, 
                    args=(client_sock, addr), 
                    daemon=True
                )
                client_handler.start()
                self.clients.append(client_sock)
                
            except Exception as e:
                if self.running:
                    self._log_add("ERROR", f"Accept error: {e}")
                break

    def _handle_client(self, client_sock, addr):
        """الدالة اللي بتتعامل مع كل كلاينت لوحده (استقبال بيانات)"""
        while self.running:
            try:
                data = client_sock.recv(self.buffer_size)
                if not data:
                    # لو الكلاينت قفل الاتصال
                    break
                
                self._log_add("INFO", f"Received from {addr}: {data}")
                self.receive_queue.put((addr, data)) # بنحط العنوان مع الداتا
                
                # مثال لرد تلقائي (Echo) لو حابب:
                # client_sock.sendall(b"Message Received")

            except Exception as e:
                self._log_add("WARNING", f"Client {addr} disconnected: {e}")
                break
        
        # تنظيف بعد ما الكلاينت يخرج
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
        if isinstance(message, bytes):
            return message
        elif is_hex:
            return bytes.fromhex(message)
        else:
            return message.encode('utf-8')

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
    def __init__(self, ip, port, timeout=None, buffer_size=4096):
        """
        :param timeout: لو خليته None هيفضل مستني للأبد لحد ما السيرفر يرد
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
        self.name =""
        self.current_program_label =""
        self.current_program_data=""

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
            print(f"[{self.ip}] : [{self.port}] Connected successfully.")
            return True
        except Exception as e:
            print(f"[{self.ip}] : [{self.port}] Connection Failed: {e}")
            self.connected = False
            return False
            
    def ensure_connected(self):
        """تتأكد إننا متصلين، ولو مش متصلين تحاول للأبد"""
        while not self.connected:
            self._log_add("INFO", f"Trying to reconnect to {self.ip}...")
            if self.connect():
                self._log_add("INFO", "✅ Reconnected successfully!")
                break
            else:
                self._log_add("WARNING", "❌ Retrying in 5 seconds...")
                time.sleep(5)    
    
    def start_reconnection_watchdog(self):
        """تشغيل خيط المراقبة في الخلفية"""
        thread = threading.Thread(target=self._connection_monitor, daemon=True)
        thread.start()

    def _connection_monitor(self):
        """الدالة اللي بتراقب الاتصال كل كام ثانية"""
        while True:
            if not self.connected:
                # لو لقيناه فصل، نصلحه
                self.ensure_connected()
            else:
                # لو متصل، نتأكد إنه "فعلاً" لسه شغال
                try:
                    # محاولة إرسال بايت فارغ للتأكد من الـ Socket
                    # MSG_PEEK بتشوف الداتا من غير ما تسحبها، أو ابعت حرف تافه لو السيرفر بيسمح
                    self.sock.send(b'', socket.MSG_OOB) 
                except Exception:
                    self._log_add("WARNING", "⚠️ Connection lost in background!")
                    self.connected = False
            
            time.sleep(3) # افحص كل 3 ثواني
    
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
            # 1. تجهيز الرسالة
            data_to_send = None
            if isinstance(message, bytes):
                data_to_send = message
            elif is_hex:
                data_to_send = bytes.fromhex(message)
            else:
                data_to_send = message.encode('utf-8')
                #data_to_send = [chunk.encode('utf-8') for chunk in message]

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
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        self.sock = None
        self.connected = False
        print(f"[{self.ip}] Connection Closed.")

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
        self.receive_queue = queue.Queue() # كيو لاستقبال البيانات
        self.listen_thread = threading.Thread(target=self._listen_loop, args=(callback,), daemon=True)
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
                # 1. تجهيز الرسالة بنفس المنطق اللي استخدمته في send_request
                data_to_send = None
                if isinstance(message, bytes):
                    data_to_send = message
                elif is_hex:
                    data_to_send = bytes.fromhex(message)
                else:
                    data_to_send = message.encode('utf-8')

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

        self.VisionClient_TRIG = TCPClient("127.0.0.1", 8080)
        self.VisionClient_ID = TCPClient("127.0.0.1", 8080)
        self.cobotClient = TCPClient("192.168.57.2", 9000)
             


        

    def get_barcode_from_scanner(self):
        # هنا بنستخدم الكيو اللي في scanner.py عشان نجيب الباركود اللي اتقرا
        while True:
            try:
                if sc.flag_barcode: # لو العلم True يعني فيه باركود جاهز
                    sc.flag_barcode = False # تصفير العلم
                    barcode = sc.queue_barcode.get(timeout=10) # هينتظر لحد ما يجي باركود أو 10 ثواني
                    self.vision_queue.put(barcode)
                    self.report_queue.put(barcode) # لو حابب تشارك الباركود مع دوال تانية في App
                    print(f"Barcode received and put in vision_queue: {barcode}")
                    sc.queue_barcode.task_done() # تأكيد إننا خلصنا التعامل مع الباركود
                else:
                    time.sleep(0.1) # لو مفيش باركود جاهز، ننتظر شوية قبل ما نشيك تاني
    
            except queue.Empty:
                print("No barcode received within the timeout period.")

    def result_handling(self, data):
        pass
            

    def sequance_handler(self, data):
        
        pass

    def run(self):
        self.VisionClient_TRIG.start_reconnection_watchdog()
        self.VisionClient_ID.start_reconnection_watchdog()
        self.cobotClient.start_reconnection_watchdog()
        self.cobotClient.start_listening(callback=self.sequance_handler)
        threading.Thread(target=self.get_barcode_from_scanner, daemon=True).start()

################################################################"""





