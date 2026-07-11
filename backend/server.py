"""
backend/server.py
FastAPI: เสิร์ฟหน้า HTML + API สำหรับ list / load / save / delete / เลขถัดไป
ที่เก็บข้อมูล = ไฟล์ JSON ในเครื่อง (ดู backend/store.py)
"""
import json as _json
import os
import ssl
import subprocess
import sys
import webbrowser
from functools import lru_cache
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from config import APP_VERSION, data_dir, load_config, resource_path
from .customers import CustomerStore
from .models import Customer, DocumentPayload, TaxSummary
from .store import DocumentStore, StoreError

# หน้า/asset ของ GitHub สำหรับเช็คเวอร์ชันใหม่
# ชี้ไป repo "สาธารณะเฉพาะไฟล์แจก" (quotation-releases) — โค้ดจริงอยู่ repo private แยกต่างหาก
# ต้องเป็น repo public เพราะแอปยิงเช็คแบบไม่มี token และผู้ใช้โหลดไฟล์โดยไม่ต้อง login
_REPO = "Maorumrx/quotation-releases"
_LATEST_RELEASE_API = f"https://api.github.com/repos/{_REPO}/releases/latest"
_RELEASES_PAGE = f"https://github.com/{_REPO}/releases/latest"


def _ver_tuple(v: str):
    out = []
    for p in (v or "").lstrip("v").split("."):
        try:
            out.append(int(p))
        except ValueError:
            out.append(0)
    return tuple(out)


def _is_newer(latest: str, current: str) -> bool:
    """latest ใหม่กว่า current ไหม — pad ให้ยาวเท่ากันก่อน กัน 1.0 < 1.0.0 ผิดพลาด"""
    if not latest:
        return False
    a, b = _ver_tuple(latest), _ver_tuple(current)
    n = max(len(a), len(b))
    a += (0,) * (n - len(a))
    b += (0,) * (n - len(b))
    return a > b


@lru_cache(maxsize=1)
def _ssl_context():
    """SSL context ที่ชี้ไปยัง CA bundle ของ certifi (สร้างครั้งเดียว—cache ไว้)

    ตอน frozen build (PyInstaller) ตัว ssl หา CA ของระบบไม่เจอ (โดยเฉพาะ macOS และ
    Windows onefile) ทำให้ urlopen โยน CERTIFICATE_VERIFY_FAILED แล้วเช็คอัปเดตเงียบ
    ตายทั้งที่มี release ใหม่ — ใช้ certifi มาเป็น CA เพื่อให้ยิง HTTPS สำเร็จทุก OS

    fallback เฉพาะกรณี "ไม่มี certifi" (รันจากซอร์สที่ยังไม่ลง dep) เท่านั้น —
    ถ้า certifi มีแต่ cacert.pem หาย ปล่อยให้ error โผล่ (จะได้รู้ว่า bundle พัง)
    แทนที่จะเงียบกลับไปใช้ system CA ที่พังบน frozen build เหมือนบั๊กเดิม
    """
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def _fetch_latest_release():
    """คืน (tag, html_url) ของ release ล่าสุด หรือ (None, page) ถ้ายังไม่มี/เน็ตล่ม"""
    req = Request(_LATEST_RELEASE_API,
                  headers={"Accept": "application/vnd.github+json",
                           "User-Agent": "quotation-app"})
    with urlopen(req, timeout=6, context=_ssl_context()) as r:
        data = _json.loads(r.read().decode("utf-8"))
    return (data.get("tag_name") or "").lstrip("v"), (data.get("html_url") or _RELEASES_PAGE)

app = FastAPI(title="Quotation Manager")

_cfg = load_config()
_db = DocumentStore(data_dir=data_dir(_cfg))
_cust = CustomerStore(data_dir=data_dir(_cfg))


@app.get("/")
def index():
    return FileResponse(resource_path("frontend/index.html"))


@app.get("/api/health")
def health():
    """ให้ frontend เช็คว่าเก็บข้อมูลได้ไหม จะได้ขึ้นสถานะสีเขียว/แดง"""
    try:
        _db.health()
        return {"ok": True}
    except StoreError as e:
        return {"ok": False, "message": str(e)}


@app.get("/api/documents")
def list_documents():
    try:
        return [d.model_dump() for d in _db.list_documents()]
    except StoreError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/documents/{doc_no:path}")
def get_document(doc_no: str):
    try:
        payload = _db.get_document(doc_no)
    except StoreError as e:
        raise HTTPException(status_code=500, detail=str(e))
    if payload is None:
        raise HTTPException(status_code=404, detail="ไม่พบเอกสาร")
    return payload.model_dump()


@app.post("/api/documents")
def save_document(payload: DocumentPayload):
    try:
        doc_no = _db.save_document(payload)
        return {"ok": True, "doc_no": doc_no, "message": "บันทึกแล้ว"}
    except StoreError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/documents/{doc_no:path}")
def delete_document(doc_no: str):
    try:
        _db.delete_document(doc_no)
        return {"ok": True}
    except StoreError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/next-no")
def next_no():
    try:
        return {"doc_no": _db.next_doc_no()}
    except StoreError as e:
        return JSONResponse({"doc_no": "", "message": str(e)}, status_code=200)


@app.get("/api/customers")
def list_customers():
    """สมุดลูกค้า — รายชื่อลูกค้าที่บันทึกไว้ (เรียงตามชื่อ)"""
    try:
        return [c.model_dump() for c in _cust.list_customers()]
    except StoreError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/customers")
def save_customer(cust: Customer):
    """เพิ่ม/แก้ลูกค้า (upsert กันซ้ำด้วย id/เลขภาษี/ชื่อ)"""
    try:
        return _cust.save_customer(cust).model_dump()
    except StoreError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/customers/{cust_id:path}")
def delete_customer(cust_id: str):
    try:
        _cust.delete_customer(cust_id)
        return {"ok": True}
    except StoreError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tax/summary")
def tax_summary(year: int):
    """สรุปภาษีรายปี (พ.ศ.) — รายได้รวม + ภาษีหัก ณ ที่จ่ายแยกตามอัตรา จากใบเสร็จในปีนั้น"""
    try:
        return TaxSummary(**_db.tax_summary(year)).model_dump()
    except StoreError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/data-dir")
def get_data_dir():
    """คืน path โฟลเดอร์เก็บข้อมูล (ให้ frontend โชว์ได้)"""
    return {"path": _db.data_dir}


@app.post("/api/open-data-dir")
def open_data_dir():
    """สั่งให้ OS เปิดโฟลเดอร์เก็บข้อมูลใน File Explorer / Finder (แอปรันในเครื่อง)"""
    path = _db.data_dir
    try:
        _db.health()  # สร้างโฟลเดอร์ให้ถ้ายังไม่มี + เช็คว่าเข้าถึงได้
    except StoreError as e:
        raise HTTPException(status_code=500, detail=str(e))
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]  # มีเฉพาะ Windows
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"เปิดโฟลเดอร์ไม่ได้: {e}")
    return {"ok": True, "path": path}


@app.post("/api/clear-all")
def clear_all():
    """ล้างเอกสารทั้งหมด (ย้ายไปโฟลเดอร์สำรอง) — เลขรันจะรีเซ็ตเองหลังจากนี้"""
    try:
        result = _db.clear_all()
        return {"ok": True, **result}
    except StoreError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/version")
def version():
    return {"version": APP_VERSION}


@app.get("/api/check-update")
def check_update():
    """เทียบเวอร์ชันปัจจุบันกับ GitHub Release ล่าสุด (ไม่ล่มถ้าเน็ตมีปัญหา)"""
    try:
        latest, url = _fetch_latest_release()
    except Exception as e:  # noqa: BLE001  (เน็ตล่ม/ยังไม่มี release -> ไม่ต้องเตือน)
        return {"current": APP_VERSION, "latest": "", "update_available": False,
                "url": _RELEASES_PAGE, "error": str(e)}
    return {
        "current": APP_VERSION,
        "latest": latest,
        "update_available": _is_newer(latest, APP_VERSION),
        "url": url,
    }


@app.post("/api/open-release")
def open_release():
    """เปิดหน้า release ล่าสุดในเบราว์เซอร์ (URL ฝั่ง server ตัดสินเอง ไม่รับจาก client)"""
    try:
        _, url = _fetch_latest_release()
    except Exception:  # noqa: BLE001
        url = _RELEASES_PAGE
    try:
        webbrowser.open(url)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"เปิดลิงก์ไม่ได้: {e}")
    return {"ok": True, "url": url}
