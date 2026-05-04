import keyboard
import time

print("في انتظار قراءة الباركود (سيتم التقاطه ككيبورد)...")
print("اضغط ESC لإيقاف البرنامج.")

recorded_keys = []
barcode = ""
def on_key_event(e):
    if e.event_type == keyboard.KEY_DOWN:
        if e.name == 'enter': # عادة الإسكانر يرسل زر Enter بعد قراءة الباركود
            barcode = "".join(recorded_keys)
            print(f"تمت قراءة الباركود: {barcode}")
            recorded_keys.clear() # تفريغ القائمة للباركود القادم
        elif len(e.name) == 1: # لتجاهل أزرار زي Shift و CapsLock
            recorded_keys.append(e.name)

# الاستماع لكل ضغطات الكيبورد
keyboard.hook(on_key_event)

# إبقاء البرنامج يعمل حتى تضغط على زر ESC
keyboard.wait('esc')