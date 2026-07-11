"""
config.py
โหลดค่า config + จัดการ path ให้ทำงานได้ทั้งตอนรันจากซอร์ส (python app.py)
และตอน build เป็น .exe / .app แล้ว (PyInstaller frozen)

ที่วางไฟล์ตั้งค่า + ข้อมูล: ~/.quotation-manager/
  - config.json         (ไม่บังคับ — ปรับ data_dir ได้)
  - data/*.json         (เอกสาร 1 ไฟล์ต่อ 1 ใบ)
(ใช้โฟลเดอร์ home เพราะ .exe (Windows) กับ .app (macOS) วางไฟล์คนละที่กัน
 การชี้มา home ทำให้ทั้งสอง OS หาไฟล์เจอเหมือนกัน)
"""
import json
import os
import sys

APP_FOLDER = ".quotation-manager"

# เวอร์ชันของแอป — ใช้เทียบกับ GitHub Release ล่าสุดเพื่อแจ้งเตือนอัปเดต
# ตอนออก build ใหม่: bump ค่านี้ให้ตรงกับ tag ที่จะ push (เช่น v1.0.5 -> "1.0.5")
APP_VERSION = "1.0.6"

_DEFAULTS = {
    "data_dir": "",   # ว่าง = ใช้ ~/.quotation-manager/data
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


def load_config() -> dict:
    """อ่าน config.json จาก ~/.quotation-manager/ ก่อน แล้วค่อย fallback ที่ข้างๆ ตัวโปรแกรม
    (config.json ไม่บังคับ — ไม่มีก็ใช้ค่า default ได้เลย)"""
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
    return cfg


def data_dir(cfg: dict) -> str:
    """โฟลเดอร์เก็บเอกสาร: env QM_DATA_DIR -> config.data_dir -> ~/.quotation-manager/data"""
    env = os.environ.get("QM_DATA_DIR")
    if env:
        return env
    d = (cfg.get("data_dir") or "").strip()
    if d:
        return os.path.expanduser(d)
    return os.path.join(user_config_dir(), "data")
