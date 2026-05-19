"""
build_exe.py
------------
بنبني الـ exe بـ Nuitka. شغّل من ويندوز:
    python build_exe.py

اللي بيحصل:
  1. بنتأكد إن Nuitka موجود (لو لأ، نطبع طريقة التنصيب).
  2. بننده Nuitka مع كل الـ flags اللازمة للـ PySide6 + الـ data files.
  3. الناتج بيتسحب في فولدر dist/ مع كل الـ dependencies.
  4. الـ exe النهائي: dist/gui_app.dist/gui_app.exe

ملاحظات للـ user:
  - أول build بياخد 10-15 دقيقة عشان Nuitka بتحلّل كل المكتبات.
  - الـ builds اللي بعدها بتاخد دقيقتين تلاتة (incremental).
  - الـ exe النهائي ~100-150 MB (لأنه شامل PySide6 + Python runtime).
"""

import sys
import os
import subprocess
import shutil


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENTRY = "gui_app.py"
APP_NAME = "TestStationController"

# الملفات الإضافية اللي لازم تكون جنب الـ exe وقت التشغيل
DATA_FILES = [
    "program_mapping.xlsx",
    "results_report.xlsx",
    "company_logo.png",
    "config.json",
]

# الباكدجات اللي لازم Nuitka يضمها صراحةً (بعضها مش بتظهر للـ static analyzer)
INCLUDE_PACKAGES = [
    "PySide6",
    "openpyxl",
    "pandas",
    "numpy",
    "keyboard",
    "scanner",
    "ClientsClass",
    "thread_logger",
    "debug_monitor",
    "excel",
    "gui_styles",
    "gui_log_bridge",
    "gui_settings",
    "config",
]


def check_nuitka():
    """يتأكد إن nuitka منصّب."""
    try:
        out = subprocess.check_output(
            [sys.executable, "-m", "nuitka", "--version"],
            stderr=subprocess.STDOUT, text=True
        )
        print(f"✓ Nuitka found: {out.strip().splitlines()[0]}")
        return True
    except Exception:
        print("✗ Nuitka not found. Install it first:")
        print("    pip install nuitka")
        print("On Windows you also need a C compiler (Nuitka will offer to download it).")
        return False


def build():
    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",                # build كامل بدون python خارجي
        "--assume-yes-for-downloads",  # يقبل تنزيل MinGW تلقائياً لو محتاج
        "--enable-plugin=pyside6",     # plugin لازم لـ PySide6
        "--windows-console-mode=disable",  # شيل الـ console (GUI app)
        "--windows-icon-from-ico=meeserve.ico",  # icon (Nuitka هيحوّلها)
        f"--output-filename={APP_NAME}.exe",
        f"--output-dir=dist",
        "--remove-output",             # امسح build folder القديم
        "--show-progress",
        "--lto=no",                    # أسرع compile (lto=yes أصغر exe بس أبطأ)
    ]

    # ضم الـ packages المهمة
    for pkg in INCLUDE_PACKAGES:
        cmd.append(f"--include-package={pkg}")

    # ضم data files (Excel + image)
    for f in DATA_FILES:
        path = os.path.join(SCRIPT_DIR, f)
        if os.path.exists(path):
            # --include-data-files=src=dest
            cmd.append(f"--include-data-files={f}={f}")
        else:
            print(f"  (skip missing data file: {f})")

    # ضم فولدر logs إن وُجد (Nuitka بتعمله empty لو مش موجود)
    logs_dir = os.path.join(SCRIPT_DIR, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    cmd.append("--include-data-dir=logs=logs")

    # الـ entry point
    cmd.append(ENTRY)

    print("\n" + "=" * 70)
    print("Running Nuitka build... (this may take 10-15 minutes the first time)")
    print("=" * 70)
    print("Command:")
    for arg in cmd:
        print(f"  {arg}")
    print("=" * 70 + "\n")

    return subprocess.call(cmd)


def post_build():
    """تنظيف وتجهيز النسخة النهائية."""
    dist_dir = os.path.join(SCRIPT_DIR, "dist", "gui_app.dist")
    if not os.path.exists(dist_dir):
        print("✗ Build directory not found. Build might have failed.")
        return False

    # نتأكد إن فولدر logs/ موجود في الـ output
    logs_in_dist = os.path.join(dist_dir, "logs")
    os.makedirs(logs_in_dist, exist_ok=True)

    # نمسح أي ملفات .log قديمة من الـ build
    for fn in os.listdir(logs_in_dist):
        if fn.endswith(".log"):
            try: os.remove(os.path.join(logs_in_dist, fn))
            except Exception: pass

    exe_path = os.path.join(dist_dir, f"{APP_NAME}.exe")
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print("\n" + "=" * 70)
        print(f"✓ BUILD SUCCESSFUL")
        print("=" * 70)
        print(f"  Executable:  {exe_path}")
        print(f"  Size:        {size_mb:.1f} MB")
        print(f"  Total dist:  {sum(os.path.getsize(os.path.join(r,f)) for r,_,fs in os.walk(dist_dir) for f in fs) / (1024*1024):.1f} MB")
        print(f"\n  Run with:   {APP_NAME}.exe")
        print(f"\n  لنقل البرنامج: انسخ الفولدر '{dist_dir}' كامل لأي جهاز.")
        print("=" * 70)
        return True
    else:
        print(f"✗ Expected exe not found at {exe_path}")
        return False


def main():
    if not check_nuitka():
        return 1

    rc = build()
    if rc != 0:
        print(f"\n✗ Build failed with code {rc}")
        return rc

    if not post_build():
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
