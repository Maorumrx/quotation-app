"""
app.py  — จุดเริ่มโปรแกรม
- รัน FastAPI (uvicorn) ใน background thread บน localhost พอร์ตว่างอัตโนมัติ
- เปิดหน้าต่าง native ด้วย pywebview ชี้มาที่ localhost

รันตอน dev:   python app.py
ตอน build:    ดู build.py
"""
import socket
import threading
import time

import uvicorn
import webview

from backend.server import app


# PDF ทำฝั่งเว็บวิว (window.print -> Save as PDF) เพื่อให้เอกสารเหมือนหน้าจอเป๊ะ
# จึงไม่มีสะพาน Api/สร้าง PDF ฝั่ง Python อีกต่อไป (เลิกใช้ xhtml2pdf แล้ว)


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

    webview.create_window(
        "ใบเสนอราคา / ใบแจ้งหนี้ / ใบเสร็จ",
        f"http://127.0.0.1:{port}",
        width=1180,
        height=880,
        min_size=(900, 600),
    )
    webview.start()  # block จนปิดหน้าต่าง


if __name__ == "__main__":
    main()
