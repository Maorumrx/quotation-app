"""
app.py  — จุดเริ่มโปรแกรม
- รัน FastAPI (uvicorn) ใน background thread บน localhost พอร์ตว่างอัตโนมัติ
- เปิดหน้าต่าง native ด้วย pywebview ชี้มาที่ localhost

รันตอน dev:   python app.py
ตอน build:    ดู build.py
"""
import os
import socket
import subprocess
import sys
import threading
import time

import uvicorn
import webview

from backend.server import app


def _open_in_os(path: str) -> bool:
    """เปิดไฟล์/โฟลเดอร์ด้วยโปรแกรมเริ่มต้นของ OS (แอปรันในเครื่อง) — คืน True ถ้าเปิดได้"""
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]  # Windows เท่านั้น
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception:  # noqa: BLE001  (เปิดไม่ได้ไม่ใช่เรื่องคอขาดบาดตาย ไฟล์เซฟไปแล้ว)
        return False


class Api:
    """สะพาน JS -> Python สำหรับ pywebview (เรียกจาก window.pywebview.api.*)
    ใช้เซฟไฟล์ PDF: เปิด native save dialog แล้วเขียนไฟล์ลงที่ผู้ใช้เลือก
    (ทำฝั่ง Python เพราะ WebView บางตัวบล็อกการดาวน์โหลด blob — วิธีนี้ได้ save dialog จริงชัวร์กว่า)
    """

    def __init__(self):
        self._window = None

    def set_window(self, window):
        self._window = window

    def save_pdf(self, payload):
        from backend.pdf import render_pdf

        try:
            pdf_bytes = render_pdf(payload or {})
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"สร้าง PDF ไม่ได้: {e}"}

        doc = (payload or {}).get("document") or {}
        doc_no = str(doc.get("doc_no") or "document")
        default_name = (doc_no.strip()
                        .replace(" ", "_").replace("/", "-").replace("\\", "-")) + ".pdf"

        result = self._window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=default_name,
            file_types=("PDF ไฟล์ (*.pdf)",),
        )
        if not result:
            return {"ok": False, "canceled": True}
        path = result[0] if isinstance(result, (list, tuple)) else result
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            with open(path, "wb") as f:
                f.write(pdf_bytes)
        except OSError as e:
            return {"ok": False, "error": f"เขียนไฟล์ไม่ได้: {e}"}
        # เปิดไฟล์ที่เพิ่งเซฟให้ดูทันที (เปิดไม่ได้ก็ไม่เป็นไร ไฟล์เซฟเรียบร้อยแล้ว)
        opened = _open_in_os(path)
        return {"ok": True, "path": path, "opened": opened}


def _free_port() -> int:
    """ขอพอร์ตว่างจาก OS"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Server(uvicorn.Server):
    # ปิด signal handler เพราะรันใน thread ไม่ใช่ main thread
    def install_signal_handlers(self):  # noqa: D401
        pass


def _wait_until_up(port: int, timeout: float = 8.0):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def main():
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = _Server(config)

    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    _wait_until_up(port)

    api = Api()
    window = webview.create_window(
        "ใบเสนอราคา / ใบแจ้งหนี้ / ใบเสร็จ",
        f"http://127.0.0.1:{port}",
        width=1180,
        height=880,
        min_size=(900, 600),
        js_api=api,
    )
    api.set_window(window)
    webview.start()  # block จนปิดหน้าต่าง


if __name__ == "__main__":
    main()
