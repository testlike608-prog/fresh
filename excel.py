from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from pathlib import Path
import pandas as pd
import os
from datetime import datetime

import serial


def get_image_path(image_name, folder_name="result_images"):
    """
    فانكشن بتاخد اسم الصورة واسم الفولدر وترجع الباث الكامل
    """
    # تحديد مسار الفولدر الحالي اللي فيه ملف الكود
    current_dir = Path(__file__).parent
    
    # دمج المسار مع الفولدر واسم الصورة
    image_path = current_dir / folder_name / image_name
    
    # التأكد إذا كانت الصورة موجودة فعلاً (اختياري لكن مفيد)
    if image_path.exists():
        return str(image_path.resolve())
    else:
        return f"خطأ: الصورة '{image_name}' غير موجودة في فولدر '{folder_name}'"
""""
# --- أمثلة للاستخدام ---

# 1. لو الصورة اسمها pic1.png وفي فولدر اسمه images
print(get_image_path("pic1.png"))

# 2. لو عايز تغير اسم الفولدر كمان
print(get_image_path("logo.jpg", folder_name="assets"))

# 3. استخدام متغير لاسم الصورة
my_photo = "profile.jpeg"
full_link = get_image_path(my_photo)
print(full_link)
"""
def result_reporting(ID, description, serial_num, result, file_path="results_report.xlsx"):
    image_path = []
    for i in range(0, 4):  # لو حابب تضيف لحد 4 صور
        image_path.append(get_image_path(f"{ID}_{i}.png"))
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    new_data = {
        'id': [ID],
        'description': [description],
        'serial': [serial_num],
        'image path1': [image_path[0]],
        'image path2': [image_path[1]],  # لو حابب تضيف صورة تانية
        'image path3': [image_path[2]],  # لو حابب تضيف صورة تانية
        'image path4': [image_path[3]],  # لو حابب تضيف صورة تانية
        'result': [result],
        'timestamp': [current_time]
    }
    
    # تحويل البيانات إلى DataFrame
    new_df = pd.DataFrame(new_data)
    
    try:
        # 2. التأكد من وجود الملف مسبقاً
        if os.path.exists(file_path):
            # إذا كان الملف موجوداً، نقرأه ثم ندمج البيانات الجديدة معه
            # نستخدم mode='a' مع ExcelWriter للإضافة (Append)
            with pd.ExcelWriter(file_path, mode='a', engine='openpyxl', if_sheet_exists='overlay') as writer:
                # نقرأ الملف الحالي لمعرفة آخر صف مكتوب
                existing_df = pd.read_excel(file_path)
                # إضافة الصف الجديد بعد آخر صف موجود
                new_df.to_excel(writer, startrow=len(existing_df) + 1, index=False, header=False)
        else:
            # 3. إذا كان الملف غير موجود، نقوم بإنشائه وكتابة الهيدر (العناوين)
            new_df.to_excel(file_path, index=False)
            
        print("تمت إضافة البيانات بنجاح.")
        
    except Exception as e:
        print(f"حدث خطأ أثناء تحديث الملف: {e}")

# --- مثال على الاستخدام في مشروعك ---
# يمكنك استدعاء هذه الفانكشن في كل مرة ينتهي فيها النظام من فحص قطعة معينة
                        #ID 
def get_model_value(input_string , file_path, search_column):
    try:
        # 1. استخراج آخر 3 حروف من النص المدخل
        # هذه الخطوة مفيدة جداً في مشاريعك البرمجية للتعامل مع الأكواد المختصرة
        suffix = input_string[-3:]
        
        # 2. قراءة ملف الإكسيل
        df = pd.read_excel(file_path)
        
        # 3. البحث عن الصف الذي يحتوي على الـ suffix في العمود المحدد
        # نستخدم .astype(str) لضمان مطابقة النصوص حتى لو كانت البيانات في الإكسيل أرقاماً
        match = df[df[search_column].astype(str) == suffix]
        
        # 4. التأكد من وجود نتائج واستخراج القيمة من عمود 'model'
        if not match.empty:
            # الوصول لعمود 'model' في أول صف مطابق نتيجه البحث
            result_value = match.iloc[0]['model']
            return result_value
        else:
            return "لم يتم العثور على القيمة المطلوبة"
            
    except KeyError:
        return "خطأ: تأكد من صحة أسماء الأعمدة (العمود المراد البحث فيه أو عمود model)"
    except Exception as e:
        return f"حدث خطأ: {e}"

# --- تجربة الكود ---
# لنفترض أن النص المدخل ينتهي بـ "B01" وتريد البحث عنه في عمود اسمه "Code"
# ليجلب لك القيمة المقابلة في عمود "model"
if __name__ == "__main__":
    # كود الاختبار اللي كان بيتنفذ على الـ import — الآن جواه __main__ guard
    try:
        wb = load_workbook('test.xlsx')
        sheet = wb.active
        sheet['A1'] = "Result"
        sheet['A1'].font = Font(bold=True, color="FF0000")
        wb.save('test_styled.xlsx')
    except Exception as e:
        print(f"Test workbook step skipped: {e}")

    final_value = get_model_value("Project_B01", "production_data.xlsx", "Code")
    print(f"Model: {final_value}")