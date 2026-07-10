"""
config.py
โหลดค่า config + จัดการ path ให้ทำงานได้ทั้งตอนรันจากซอร์ส (python app.py)
และตอน build เป็น .exe / .app แล้ว (PyInstaller frozen)

ที่วางไฟล์ตั้งค่า/ลับ: ~/.quotation-manager/
  - config.json
  - credentials.json
(ใช้โฟลเดอร์ home เพราะ .exe (Windows) กับ .app (macOS) วางไฟล์คนละที่กัน
 การชี้มา home ทำให้ทั้งสอง OS หาไฟล์เจอเหมือนกัน)
"""
import json
import os
import sys

APP_FOLDER = ".quotation-manager"

_DEFAULTS = {
    "sheet_id": "PUT_YOUR_GOOGLE_SHEET_ID_HERE",
    "documents_tab": "documents",
    "items_tab": "items",
    "credentials_file": "credentials.json",
}


def app_dir() -> str:
    """โฟลเดอร์ที่ตัวโปรแกรมอยู่ (ตอน dev = โปรเจกต์, ตอน build = ที่วาง exe/app)"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def user_config_dir() -> str:
    """~/.quotation-manager/ (สร้างให้ถ้ายังไม่มี)"""
    d = os.path.join(os.path.expanduser("~"), APP_FOLDER)
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:  # noqa: BLE001
        pass
    return d


def resource_path(rel: str) -> str:
    """path ของไฟล์ที่ฝังมากับ exe เช่น frontend/index.html (PyInstaller -> _MEIPASS)"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def _drop_example():
    """ยังไม่มี config -> วางไฟล์ตัวอย่างไว้ให้ในโฟลเดอร์ home ผู้ใช้จะได้รู้ว่าต้องแก้ที่ไหน"""
    try:
        p = os.path.join(user_config_dir(), "config.example.json")
        if not os.path.exists(p):
            with open(p, "w", encoding="utf-8") as f:
                json.dump(_DEFAULTS, f, ensure_ascii=False, indent=2)
    except Exception:  # noqa: BLE001
        pass


def load_config() -> dict:
    """อ่าน config.json จาก ~/.quotation-manager/ ก่อน แล้วค่อย fallback ที่ข้างๆ ตัวโปรแกรม"""
    cfg = dict(_DEFAULTS)
    for p in (os.path.join(user_config_dir(), "config.json"),
              os.path.join(app_dir(), "config.json")):
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    cfg.update(json.load(f))
                cfg["_config_path"] = p
                return cfg
            except Exception as e:  # noqa: BLE001
                print(f"[config] อ่าน {p} ไม่ได้: {e}")
    _drop_example()
    return cfg


def credentials_path(cfg: dict) -> str:
    """หา credentials.json: env -> ~/.quotation-manager/ -> ข้างๆ ตัวโปรแกรม"""
    env = os.environ.get("GSPREAD_CREDENTIALS")
    if env and os.path.exists(env):
        return env
    name = cfg.get("credentials_file", "credentials.json")
    for base in (user_config_dir(), app_dir()):
        p = os.path.join(base, name)
        if os.path.exists(p):
            return p
    return os.path.join(user_config_dir(), name)
