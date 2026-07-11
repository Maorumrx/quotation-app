"""
build.py — สร้างไฟล์ดับเบิลคลิก (รันเองก็ได้ แต่ปกติให้ GitHub Actions รันให้)
Windows -> dist/QuotationManager.exe   (onefile คลิกเดียว)
macOS   -> dist/QuotationManager.app   (bundle)

ใช้เอง:
  pip install pyinstaller
  python build.py

หมายเหตุ: build ได้เฉพาะ OS ที่รันอยู่ (จะได้ .exe ต้อง build บน Windows / .app ต้อง build บน Mac)
"""
import os
import subprocess
import sys

# สำคัญมาก: บน Windows เมื่อ output ถูก redirect (เช่นใน GitHub Actions) Python จะใช้
# encoding เป็น cp1252/cp437 ไม่ใช่ utf-8 การ print ข้อความ "ภาษาไทย" ด้านล่างจะทำให้เกิด
# UnicodeEncodeError แล้ว build.py ตายก่อนจะได้เรียก PyInstaller (= สาเหตุที่ Windows build
# ล้มมาตลอด ส่วน macOS ใช้ utf-8 จึงผ่าน). บังคับ stdout/stderr เป็น utf-8 ก่อนพิมพ์อะไร
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

APP_NAME = "QuotationManager"
SEP = ";" if os.name == "nt" else ":"  # add-data ใช้ ; บน Windows, : บน mac/linux

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm", "--clean",
    "--windowed",                     # ไม่มีหน้าต่าง console
    "--onefile",                      # รวมเป็นไฟล์เดียว คลิกเดียวเปิด
    "--name", APP_NAME,
    "--add-data", f"frontend{SEP}frontend",   # ฝังหน้า HTML + ฟอนต์ไทย (frontend/fonts) เข้าไป

    # xhtml2pdf/reportlab มีไฟล์ data + submodule ที่ PyInstaller มองไม่เห็นจาก import ตรง ๆ
    # (เช่น reportlab/fonts, ตัว parser ของ xhtml2pdf) — เก็บให้ครบ ไม่งั้นสร้าง PDF ตอน build แล้วพัง
    "--collect-all", "reportlab",
    "--collect-all", "xhtml2pdf",

    # certifi: ฝัง cacert.pem เข้าไปด้วย ไม่งั้น certifi.where() ชี้ไปไฟล์ที่ไม่มีใน
    # onefile bundle -> เช็คอัปเดต (ยิง HTTPS ไป GitHub) เจอ CERTIFICATE_VERIFY_FAILED
    "--collect-all", "certifi",

    # หมายเหตุสำคัญ: ห้ามใช้ --collect-all webview
    # PyInstaller มี hook ในตัวสำหรับ pywebview อยู่แล้ว (เก็บ DLL ของ WebView2 /
    # pythonnet บน Windows ให้เอง). --collect-all จะไป "บังคับ import" backend ทุกตัว
    # ตอน analyze — บน Windows ต้องโหลด backend winforms/clr (.NET) ซึ่งพังระหว่าง
    # build ทำให้ exit code 1 (mac ใช้ backend cocoa จึงไม่พัง). ดู docs ทางการ:
    # https://pywebview.flowrl.com/guide/freezing.html

    # ตัด backend/renderer ที่โปรเจกต์นี้ไม่ได้ใช้ทิ้ง กัน PyInstaller เก็บมาเกิน
    "--exclude-module", "PyQt5",
    "--exclude-module", "PyQt6",
    "--exclude-module", "PySide2",
    "--exclude-module", "PySide6",
    "--exclude-module", "gi",         # GTK (backend ฝั่ง Linux เท่านั้น)
    "app.py",
]

LOG_FILE = "pyinstaller-output.log"

print("รันคำสั่ง:\n ", " ".join(cmd), "\n", flush=True)

# จับ output ทั้งหมด (stdout+stderr) เขียนลงไฟล์เสมอ เผื่อ PyInstaller ตายกลางคัน
# จะได้มี log จริงไว้ให้ CI upload / ดูสาเหตุ (ไม่พึ่ง warn-*.txt ที่บางทีไม่ถูกเขียน)
proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
output = proc.stdout or ""
print(output, flush=True)
with open(LOG_FILE, "w", encoding="utf-8") as f:
    f.write(output)

raise SystemExit(proc.returncode)
