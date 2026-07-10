"""
backend/server.py
FastAPI: เสิร์ฟหน้า HTML + API สำหรับ list / load / save / เลขถัดไป
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from config import credentials_path, load_config, resource_path
from .models import DocumentPayload
from .sheets import SheetDB, SheetError

app = FastAPI(title="Quotation Manager")

_cfg = load_config()
_db = SheetDB(
    credentials_file=credentials_path(_cfg),
    sheet_id=_cfg.get("sheet_id", ""),
    documents_tab=_cfg.get("documents_tab", "documents"),
    items_tab=_cfg.get("items_tab", "items"),
)


@app.get("/")
def index():
    return FileResponse(resource_path("frontend/index.html"))


@app.get("/api/health")
def health():
    """ให้ frontend เช็คว่าเชื่อม Sheet ได้ไหม จะได้ขึ้นสถานะสีเขียว/แดง"""
    try:
        _db.list_documents()
        return {"sheet_ok": True}
    except SheetError as e:
        return {"sheet_ok": False, "message": str(e)}


@app.get("/api/documents")
def list_documents():
    try:
        return [d.model_dump() for d in _db.list_documents()]
    except SheetError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/documents/{doc_no:path}")
def get_document(doc_no: str):
    try:
        payload = _db.get_document(doc_no)
    except SheetError as e:
        raise HTTPException(status_code=503, detail=str(e))
    if payload is None:
        raise HTTPException(status_code=404, detail="ไม่พบเอกสาร")
    return payload.model_dump()


@app.post("/api/documents")
def save_document(payload: DocumentPayload):
    try:
        doc_no = _db.save_document(payload)
        return {"ok": True, "doc_no": doc_no, "message": "บันทึกแล้ว"}
    except SheetError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.delete("/api/documents/{doc_no:path}")
def delete_document(doc_no: str):
    try:
        _db.delete_document(doc_no)
        return {"ok": True}
    except SheetError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/next-no")
def next_no():
    try:
        return {"doc_no": _db.next_doc_no()}
    except SheetError as e:
        return JSONResponse({"doc_no": "", "message": str(e)}, status_code=200)
