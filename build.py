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
    "--collect-all", "webview",       # เก็บ backend ของ pywebview ให้ครบ กัน error ตอนรัน
    "--add-data", f"frontend{SEP}frontend",   # ฝังหน้า HTML เข้าไป
    "app.py",
]

print("รันคำสั่ง:\n ", " ".join(cmd), "\n")
raise SystemExit(subprocess.call(cmd))
