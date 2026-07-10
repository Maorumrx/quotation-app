"""
backend/server.py
FastAPI: เสิร์ฟหน้า HTML + API สำหรับ list / load / save / delete / เลขถัดไป
ที่เก็บข้อมูล = ไฟล์ JSON ในเครื่อง (ดู backend/store.py)
"""
import os
import subprocess
import sys

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from config import data_dir, load_config, resource_path
from .models import DocumentPayload
from .store import DocumentStore, StoreError

app = FastAPI(title="Quotation Manager")

_cfg = load_config()
_db = DocumentStore(data_dir=data_dir(_cfg))


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
