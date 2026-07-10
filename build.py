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

APP_NAME = "QuotationManager"
SEP = ";" if os.name == "nt" else ":"  # add-data ใช้ ; บน Windows, : บน mac/linux

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm", "--clean",
    "--windowed",                     # ไม่มีหน้าต่าง console
    "--onefile",                      # รวมเป็นไฟล์เดียว คลิกเดียวเปิด
    "--name", APP_NAME,
    "--add-data", f"frontend{SEP}frontend",   # ฝังหน้า HTML เข้าไป

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

print("รันคำสั่ง:\n ", " ".join(cmd), "\n")
raise SystemExit(subprocess.call(cmd))
