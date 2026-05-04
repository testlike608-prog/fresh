import sys
import numpy as np
import cv2
from ctypes import *
from pyzbar.pyzbar import decode
from MvCameraControl_class import *

def connect_camera():
    deviceList = MV_CC_DEVICE_INFO_LIST()
    tlayerType = MV_GIGE_DEVICE | MV_USB_DEVICE
    ret = MvCamera.MV_CC_EnumDevices(tlayerType, deviceList)
    
    if ret != 0 or deviceList.nDeviceNum == 0:
        print("لم يتم العثور على كاميرات!")
        return None

    cam = MvCamera()
    stDeviceImg = cast(deviceList.pDeviceInfo[0], POINTER(MV_CC_DEVICE_INFO)).contents
    cam.MV_CC_CreateHandle(stDeviceImg)
    
    ret = cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
    if ret != 0:
        print(f"فشل فتح الكاميرا: {hex(ret)}")
        return None

    # ضبط الـ Trigger Mode لـ Off عشان يشتغل Continuous Video
    # ... كود الفتح ...
    ret = cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
    
    # --- التعديل هنا: ضبط الفورمات لـ Mono8 ---
    # 0x01080001 هو الهكس كود لـ PixelFormat_Mono8
    ret = cam.MV_CC_SetEnumValue("PixelFormat", 0x01080001)
    if ret != 0:
        print(f"تحذير: فشل ضبط الكاميرا على Mono8. قد تحتاج للتحويل البرمجي.")

    # ضبط الـ Trigger Mode لـ Off 
    cam.MV_CC_SetEnumValue("TriggerMode", 0) 
    cam.MV_CC_StartGrabbing()
    return cam

# --- بداية التشغيل ---
my_cam = connect_camera()

if my_cam:
    print("Camera Connected Successfully! Press 'q' to exit.")
    try:
        while True:
            stOutFrame = MV_FRAME_OUT()
            memset(byref(stOutFrame), 0, sizeof(MV_FRAME_OUT))
            
            # سحب الفريم من الكاميرا بـ Timeout قدره 1000ms
            ret = my_cam.MV_CC_GetImageBuffer(stOutFrame, 1000)

            if ret == 0:
                # 1. استخراج البيانات وتحويلها لـ Numpy Array
                nHeight = stOutFrame.stFrameInfo.nHeight
                nWidth = stOutFrame.stFrameInfo.nWidth
                nDataLen = stOutFrame.stFrameInfo.nFrameLen
                
                # التصحيح هنا: نستخدم pBufAddr اللي موجود في stOutFrame مباشرة
                pData = (c_ubyte * nDataLen)()
                memmove(byref(pData), stOutFrame.pBufAddr, nDataLen)
                
                # 2. تحويل الصورة لـ Numpy
                # جرب الأول reshape العادي (للكاميرات المونو)
                img = np.frombuffer(pData, dtype=np.uint8).reshape(nHeight, nWidth)

                # 3. قراءة الباركود
                barcodes = decode(img)
                for barcode in barcodes:
                    data = barcode.data.decode('utf-8')
                    print(f"Barcode Found: {data}")
                    (x, y, w, h) = barcode.rect
                    cv2.rectangle(img, (x, y), (x + w, y + h), (255, 255, 255), 2)

                # 4. عرض الصورة
                cv2.imshow('Hikvision Barcode Scanner', img)

                # تنظيف البافر مهم جداً عشان الميموري ماتتحرقش
                my_cam.MV_CC_FreeImageBuffer(stOutFrame)
            # الخروج عند الضغط على q
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # إغلاق الكاميرا بأمان
        my_cam.MV_CC_StopGrabbing()
        my_cam.MV_CC_CloseDevice()
        my_cam.MV_CC_DestroyHandle()
        cv2.destroyAllWindows()