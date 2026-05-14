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
        
        self.callback = callback
        self.listen_thread = LoggedThread(
            target=self._process_queue_loop,
            name=f"{self.name}-process-queue",
            daemon=True,
        )
        self.listen_thread.start()
        self._log_add("INFO", "Started background listening thread for callbacks.")

    def _process_queue_loop(self):
        """
        اللوب الداخلي الذي يقرأ من الـ Queue وينفذ الـ Callback.
        """
        while self.running:
            try:
                # نسحب البيانات من الكيو، مع وضع timeout عشان اللوب ميستهلكش المعالج (CPU)
                # السحب هيرجع لنا tuple فيها (عنوان الكلاينت، والبيانات)
                item = self.receive_queue.get(timeout=1)
                
                # التأكد من صحة البيانات المسحوبة
                if item and len(item) == 2:
                    addr, data = item
                    
                    if self.callback:
                        # تنفيذ دالة الكول باك وتمرير العنوان والبيانات لها
                        self.callback()
                        
            except queue.Empty:
                # لو الكيو فاضي وعدت ثانية، كمل اللوب عادي
                continue
            except Exception as e:
                self._log_add("ERROR", f"Error in callback processing: {e}")
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
        """الدالة اللي بتتعامل مع كل كلاينت لوحده (استقبال بيانات)"""
        while self.running:
            try:
                data = client_sock.recv(self.buffer_size)
                if not data:
                    # لو الكلاينت قفل الاتصال
                    break
                
                self._log_add("INFO", f"Received from {addr}: {data}")
                self.receive_queue.put((addr, data)) # بنحط العنوان مع الداتا
                
                # --- التعديل هنا: استدعاء الـ Callback إذا كان موجوداً ---
                if self.on_receive_callback:
                    try:
                        # نقوم بتمرير عنوان الكلاينت والبيانات المستلمة للدالة
                        self.on_receive_callback(addr, data)
                    except Exception as cb_err:
                        self._log_add("ERROR", f"Callback execution error: {cb_err}")
                # ---------------------------------------------------------

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
        thread = LoggedThread(
            target=self._connection_monitor,
            name=f"TCPClient-{self.ip}:{self.port}-reconnect-watchdog",
            daemon=True,
        )
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

        self.VisionClient_TRIG = TCPClient("127.0.0.1", 8081)
        self.VisionClient_ID = TCPClient("127.0.0.1", 8080)
        self.cobotClient = TCPClient("192.168.57.2", 9000)
             
        self.triggerserver = TCPServer(ip="0.0.0.0", port=5000)
        self.triggerserver.start() # تشغيل السيرفر فوراً في الكونستركتور
        

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

    def extract_serial_number(self, barcode):
        """
        تستخرج هذه الدالة الجزء الخاص بالسيريال (0000001) من النص الكامل للباركود.
        مثال للنص: '2605TL0000001BISI'
        """
        # الطريقة الأولى: باستخدام Regex للبحث عن الأرقام المحصورة بين الحروف
        match = re.search(r'[A-Z]+(\d+)[A-Z]+', barcode)
        if match:
            serial_part = match.group(1)
            return serial_part
        # الطريقة الثانية: إذا كان طول الكود ثابتاً دائماً في ماكينات Beko， يمكنك استخدام الـ Slicing مباشرة
        # return barcode_text[6:13]
        return None


    def determine_program_from_barcode(self, barcode, excel_file_path="program_mapping.xlsx"):
    
        """
        دالة لاستخراج الحرف الثالث من آخر الباركود والبحث عنه في الإكسل.
        """
        # 1. استخراج الحرف الثالث من الآخر
        # إذا كان النص "2605TL0000001BISI"، فإن barcode_text[-3] سيجلب حرف "I"
        # (إذا كنت تقصد حرف S، استخدم [-2])
        target_char = barcode[-3]
        try:
            # 2. فتح ملف الإكسل
            workbook = openpyxl.load_workbook(excel_file_path)
            
            # اختيار الشيت النشط (أو يمكنك كتابة اسم الشيت: workbook['Sheet1'])
            sheet = workbook.active 
            
            # 3. البحث داخل الصفوف
            # نفترض أن الحرف موجود في العمود الأول (A) والقيمة المطلوبة في العمود الثاني (B)
            # min_row=2 لتجاهل الصف الأول إذا كان يحتوي على عناوين (Headers)
            for row in sheet.iter_rows(min_row=2, values_only=True):
                excel_char = row[0]  # القيمة في العمود الأول A
                excel_value = row[1] # القيمة في العمود الثاني B
                
                # التأكد من تطابق الحرف
                if excel_char == target_char:
                    return excel_value # إرجاع القيمة اللي قدامه
                    
            # في حالة انتهاء البحث ولم يتم إيجاد الحرف
            return "الحرف غير موجود في ملف الإكسل."

        except FileNotFoundError:
            return "خطأ: ملف الإكسل غير موجود في المسار المحدد."
        except Exception as e:
            return f"حدث خطأ غير متوقع: {e}"
     
    def sequance_handler(self):
        
        while self.cobotClient.connected:
            if not self.vision_queue.empty():
                try:
                    barcode = self.vision_queue.get() 
                    program = self.determine_program_from_barcode(barcode) # دالة بتحدد البرنامج المناسب للباركود
                    serial_number = self.extract_serial_number(barcode) # دالة بتستخرج الرقم التسلسلي من الباركود
                    self.vision_queue.task_done() # تأكيد إننا خلصنا التعامل مع الباركود في الـ Queue
                    if program == 1 :
                        result = self.cobotClient.send_request(1)
                        list_of_results =[]
                        for i in range(3): # لو عايز تبعت 3 برامج مختلفة مثلاً
                            x = 11
                            y = 21
                            self.VisionClient_ID.send_only(f"{barcode}_{i}")
                            test_result = self.VisionClient_TRIG.send_request(x)
                            list_of_results.append(test_result)    
                            result = self.cobotClient.send_request(y) # ممكن تبعت إشارة للسيرفر إنه يجهز البرنامج التالي أو يعمل حاجة تانية بين الاختبارات   
                            x+=1 
                            y+=1
                        if 0 in list_of_results:
                            final_result = "fail"
                        else:
                            final_result = "pass"
                        ex.result_reporting(ID=barcode, serial_num=serial_number, result=final_result)
                    if program == 2 :
                        result = self.cobotClient.send_request(2)
                        list_of_results =[]
                        for i in range(3): # لو عايز تبعت 3 برامج مختلفة مثلاً
                            x = 11
                            y = 21
                            self.VisionClient_ID.send_only(f"{barcode}_{i}")
                            test_result = self.VisionClient_TRIG.send_request(x)
                            list_of_results.append(test_result)    
                            result = self.cobotClient.send_request(y) # ممكن تبعت إشارة للسيرفر إنه يجهز البرنامج التالي أو يعمل حاجة تانية بين الاختبارات   
                            x+=1 
                            y+=1
                        if 0 in list_of_results:
                            final_result = "fail"
                        else:
                            final_result = "pass"
                        ex.result_reporting(ID=barcode, serial_num=serial_number, result=final_result)
                    if program == 3:
                        result = self.cobotClient.send_request(3)
                        list_of_results =[]
                        for i in range(3): # لو عايز تبعت 3 برامج مختلفة مثلاً
                            x = 11
                            y = 21
                            self.VisionClient_ID.send_only(f"{barcode}_{i}")
                            test_result = self.VisionClient_TRIG.send_request(x)
                            list_of_results.append(test_result)    
                            result = self.cobotClient.send_request(y) # ممكن تبعت إشارة للسيرفر إنه يجهز البرنامج التالي أو يعمل حاجة تانية بين الاختبارات   
                            x+=1 
                            y+=1
                        if 0 in list_of_results:
                            final_result = "fail"
                            self.cobotClient.send_only(0)
                        else:
                            final_result = "pass"
                            self.cobotClient.send_only(1)
                        ex.result_reporting(ID=barcode, serial_num=serial_number, result=final_result)
                    if program == 4 :
                        result = self.cobotClient.send_request(4)
                        list_of_results =[]
                        for i in range(3): # لو عايز تبعت 3 برامج مختلفة مثلاً
                            x = 11
                            y = 21
                            self.VisionClient_ID.send_only(f"{barcode}_{i}")
                            test_result = self.VisionClient_TRIG.send_request(x)
                            list_of_results.append(test_result)    
                            result = self.cobotClient.send_request(y) # ممكن تبعت إشارة للسيرفر إنه يجهز البرنامج التالي أو يعمل حاجة تانية بين الاختبارات   
                            x+=1 
                            y+=1
                        if 0 in list_of_results:
                            final_result = "fail"
                            self.cobotClient.send_only(0)
                        else:
                            final_result = "pass"
                            self.cobotClient.send_only(1)
                        ex.result_reporting(ID=barcode, serial_num=serial_number, result=final_result)
                           
                    if program == 5 :
                        result = self.cobotClient.send_request(5)
                        list_of_results =[]
                        for i in range(3): # لو عايز تبعت 3 برامج مختلفة مثلاً
                            x = 11
                            y = 21
                            self.VisionClient_ID.send_only(f"{barcode}_{i}")
                            test_result = self.VisionClient_TRIG.send_request(x)
                            list_of_results.append(test_result)    
                            result = self.cobotClient.send_request(y) # ممكن تبعت إشارة للسيرفر إنه يجهز البرنامج التالي أو يعمل حاجة تانية بين الاختبارات   
                            x+=1 
                            y+=1
                        if 0 in list_of_results:
                            final_result = "fail"
                            self.cobotClient.send_only(0)
                        else:
                            final_result = "pass"
                            self.cobotClient.send_only(1)
                        ex.result_reporting(ID=barcode, serial_num=serial_number, result=final_result)  # تخلص التعامل مع الداتا، ممكن تحطها في كيو تاني
                except Exception as e:
                    print(f"Error in sequence handler: {e}")
                    break
        pass

    def run(self):
        self.VisionClient_TRIG.start_reconnection_watchdog()
        self.VisionClient_ID.start_reconnection_watchdog()
        self.cobotClient.start_reconnection_watchdog()
        self.triggerserver.start_listening(self.sequance_handler) # تعيين الـ Callback

        LoggedThread(
            target=self.get_barcode_from_scanner,
            name="App-barcode-from-scanner",
            daemon=True,
        ).start()

################################################################"""





