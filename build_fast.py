"""
build_fast.py
-------------
بيبني الـ exe بـ PyInstaller (أسرع بكتير من Nuitka).

شغّله على Windows من Terminal أو Command Prompt:
    python build_fast.py

الناتج: dist\TestStation\TestStation.exe
        (فولدر كامل، انسخه لأي جهاز وشغّله)

الوقت: ~2-4 دقائق (أول مرة) / 1-2 دقيقة (بعد كده)
"""

import sys
import os
import subprocess
import shutil

# ─── إعدادات ───────────────────────────────────────────────────────────────
APP_NAME   = "TestStation"
ENTRY      = "gui_app.py"        # نقطة البداية
ICON       = "meeserve.ico"      # icon (اختياري — لو مش موجود يتجاهل)
DIST_DIR   = "dist"
BUILD_DIR  = "build_pyinstaller"

BASE = os.path.dirname(os.path.abspath(__file__))

# ─── Data files ────────────────────────────────────────────────────────────
# كل ملف بيتكتب كـ  "src;dest"  (dest = فولدر داخل الـ exe)
DATA_FILES = [
    ("config.json",            "."),
    ("program_mapping.xlsx",   "."),
    ("gui_styles.py",          "."),   # لو بتعمل import منه كـ module
]
# ضيف logo لو موجود
for logo in ("company_logo.png", "meeserve.png", "logo.png"):
    if os.path.exists(os.path.join(BASE, logo)):
        DATA_FILES.append((logo, "."))

# ─── Hidden imports ────────────────────────────────────────────────────────
# PyInstaller أحياناً بيفوته بعض الـ imports — نحددها صراحةً
HIDDEN_IMPORTS = [
    # PySide6
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtNetwork",
    # Project modules
    "ClientsClass",
    "config",
    "scanner",
    "excel",
    "thread_logger",
    "debug_monitor",
    "gui_log_bridge",
    "gui_settings",
    "gui_styles",
    "barcode_utils",
    "camera_hub",
    "camera_barcode",
    "live_image",
    # Libraries
    "openpyxl",
    "openpyxl.styles",
    "openpyxl.utils",
    "openpyxl.drawing.image",
    "pandas",
    "PIL",
    "PIL.Image",
    "PIL.ImageTk",
    "cv2",
    "zxingcpp",
    "keyboard",
    "serial",
]

# ─── Collect all ────────────────────────────────────────────────────────────
# بعض المكتبات عندها resources لازم تتجمع كلها
COLLECT_ALL = [
    "PySide6",
    "cv2",
]


# ════════════════════════════════════════════════════════════════════════════
def check_pyinstaller():
    try:
        out = subprocess.check_output(
            [sys.executable, "-m", "PyInstaller", "--version"],
            stderr=subprocess.STDOUT, text=True
        ).strip()
        print(f"✓ PyInstaller {out}")
        return True
    except Exception:
        print("PyInstaller مش موجود — بنثبّته...")
        rc = subprocess.call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        return rc == 0


def build():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--windowed",               # بدون console (GUI app)
        "--noconfirm",              # لا تسأل وامسح القديم
        "--clean",                  # امسح الـ cache قبل البيلد
        f"--distpath={DIST_DIR}",
        f"--workpath={BUILD_DIR}",
    ]

    # Icon
    icon_path = os.path.join(BASE, ICON)
    if os.path.exists(icon_path):
        cmd += ["--icon", icon_path]

    # Data files
    for src, dst in DATA_FILES:
        src_full = os.path.join(BASE, src)
        if os.path.exists(src_full):
            cmd += ["--add-data", f"{src_full}{os.pathsep}{dst}"]
        else:
            print(f"  (تجاهل ملف غير موجود: {src})")

    # ضيف فولدر logs فاضي
    logs_dir = os.path.join(BASE, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    cmd += ["--add-data", f"{logs_dir}{os.pathsep}logs"]

    # Hidden imports
    for hi in HIDDEN_IMPORTS:
        cmd += ["--hidden-import", hi]

    # Collect all (plugins + resources)
    for pkg in COLLECT_ALL:
        cmd += ["--collect-all", pkg]

    # Entry point
    cmd.append(os.path.join(BASE, ENTRY))

    print("\n" + "=" * 65)
    print(f"  Building {APP_NAME}.exe with PyInstaller...")
    print("=" * 65)

    return subprocess.call(cmd)


def post_build():
    app_dir = os.path.join(BASE, DIST_DIR, APP_NAME)
    exe     = os.path.join(app_dir, f"{APP_NAME}.exe")

    if not os.path.exists(exe):
        print(f"\n✗ مش لاقي الـ exe في {exe}")
        return False

    # ضيف فولدر logs فاضي في الناتج
    os.makedirs(os.path.join(app_dir, "logs"), exist_ok=True)
    # ضيف فولدر result_images فاضي
    os.makedirs(os.path.join(app_dir, "result_images"), exist_ok=True)

    total_mb = sum(
        os.path.getsize(os.path.join(r, f))
        for r, _, fs in os.walk(app_dir) for f in fs
    ) / (1024 * 1024)

    exe_mb = os.path.getsize(exe) / (1024 * 1024)

    print("\n" + "=" * 65)
    print("  ✓ BUILD SUCCESSFUL")
    print("=" * 65)
    print(f"  الفولدر:   {app_dir}")
    print(f"  الـ exe:    {exe_mb:.1f} MB")
    print(f"  الكل:      {total_mb:.1f} MB")
    print()
    print("  للتشغيل:    شغّل  TestStation.exe  من داخل الفولدر")
    print("  للنقل:      انسخ فولدر dist\\TestStation كامل على أي جهاز")
    print("=" * 65)
    return True


def main():
    os.chdir(BASE)

    if not check_pyinstaller():
        print("✗ فشل تثبيت PyInstaller")
        return 1

    rc = build()
    if rc != 0:
        print(f"\n✗ فشل البيلد (code {rc})")
        return rc

    if not post_build():
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
