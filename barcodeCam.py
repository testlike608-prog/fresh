import cv2
from pyzbar.pyzbar import decode

# رابط الكاميرا (غير البيانات حسب كاميرتك)
url = "rtsp://admin:password@192.168.57.36:554/Streaming/Channels/101"

cap = cv2.VideoCapture(url)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # فك تشفير الباركود من الفريم الحالي
    barcodes = decode(frame)
    
    for barcode in barcodes:
        # استخراج البيانات وتحويلها لنص
        barcode_data = barcode.data.decode('utf-8')
        barcode_type = barcode.type
        print(f"Found {barcode_type} Barcode: {barcode_data}")

        # رسم مربع حول الباركود للتأكد
        (x, y, w, h) = barcode.rect
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

    cv2.imshow('Barcode Scanner', frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()