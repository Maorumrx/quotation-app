"""
backend/sheets.py
ชั้นคุยกับ Google Sheets (ใช้ 2 แท็บ: documents + items)

โครงสร้างตาราง:
  documents:  doc_no | doc_type | doc_date | issuer_name | issuer_address |
              issuer_tax | issuer_contact | client_html | wht_rate |
              subtotal | wht_amount | grand_total | price_terms |
              agreement | assurance | payment_info | status | updated_at
  items:      doc_no | seq | item_name | item_desc | price | qty | amount

หมายเหตุ: การเชื่อมต่อทำแบบ lazy — ถ้า credentials/sheet_id ยังไม่พร้อม
app จะยังเปิดได้ปกติ (แก้ไข+พิมพ์ PDF ได้) แค่เซฟลง Sheet ไม่ได้ และจะฟ้อง error ชัดๆ
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import List, Optional

import gspread
from google.oauth2.service_account import Credentials

from .models import Document, DocumentPayload, DocumentSummary, Item

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

DOC_COLUMNS = [
    "doc_no", "doc_type", "doc_date", "issuer_name", "issuer_address",
    "issuer_tax", "issuer_contact", "client_html", "wht_rate", "subtotal",
    "wht_amount", "grand_total", "price_terms", "agreement", "assurance",
    "payment_info", "status", "updated_at",
]
ITEM_COLUMNS = ["doc_no", "seq", "item_name", "item_desc", "price", "qty", "amount"]


class SheetError(Exception):
    """error ที่อยากส่งข้อความไทยกลับไปให้ผู้ใช้เห็น"""


class SheetDB:
    def __init__(self, credentials_file: str, sheet_id: str,
                 documents_tab: str = "documents", items_tab: str = "items"):
        self.credentials_file = credentials_file
        self.sheet_id = sheet_id
        self.documents_tab = documents_tab
        self.items_tab = items_tab
        self._gc = None
        self._sh = None

    # ---------- connection (lazy) ----------
    def _connect(self):
        if self._sh is not None:
            return
        import os
        if not self.sheet_id:
            raise SheetError("ยังไม่ได้ตั้ง sheet_id ใน config.json")
        if not os.path.exists(self.credentials_file):
            raise SheetError(
                f"หาไฟล์ credentials ไม่เจอ: {self.credentials_file}\n"
                "วาง credentials.json ไว้ในโฟลเดอร์ ~/.quotation-manager/"
            )
        try:
            creds = Credentials.from_service_account_file(
                self.credentials_file, scopes=SCOPES)
            self._gc = gspread.authorize(creds)
            self._sh = self._gc.open_by_key(self.sheet_id)
        except Exception as e:  # noqa: BLE001
            raise SheetError(f"เชื่อมต่อ Google Sheet ไม่ได้: {e}") from e
        self._ensure_tabs()

    def _ensure_tabs(self):
        """สร้างแท็บ + หัวตาราง ถ้ายังไม่มี"""
        existing = {ws.title for ws in self._sh.worksheets()}
        if self.documents_tab not in existing:
            ws = self._sh.add_worksheet(self.documents_tab, rows=200,
                                        cols=len(DOC_COLUMNS))
            ws.update([DOC_COLUMNS], "A1")
        if self.items_tab not in existing:
            ws = self._sh.add_worksheet(self.items_tab, rows=500,
                                        cols=len(ITEM_COLUMNS))
            ws.update([ITEM_COLUMNS], "A1")
        # กันกรณีแท็บมีแต่หัวหาย
        self._ensure_header(self._sh.worksheet(self.documents_tab), DOC_COLUMNS)
        self._ensure_header(self._sh.worksheet(self.items_tab), ITEM_COLUMNS)

    @staticmethod
    def _ensure_header(ws, cols: List[str]):
        head = ws.row_values(1)
        if head != cols:
            ws.update([cols], "A1")

    # ---------- helpers ----------
    def _docs_ws(self):
        self._connect()
        return self._sh.worksheet(self.documents_tab)

    def _items_ws(self):
        self._connect()
        return self._sh.worksheet(self.items_tab)

    @staticmethod
    def _client_name_from_html(html: str) -> str:
        """ดึงชื่อลูกค้าคร่าวๆ จาก client_html (เอาข้อความใน <b> ตัวแรก)"""
        if not html:
            return ""
        m = re.search(r"<b>(.*?)</b>", html, re.S)
        raw = m.group(1) if m else html
        return re.sub(r"<[^>]+>", "", raw).strip()

    # ---------- read ----------
    def list_documents(self) -> List[DocumentSummary]:
        ws = self._docs_ws()
        rows = ws.get_all_records()  # list[dict] ใช้หัวตารางเป็น key
        out: List[DocumentSummary] = []
        for r in rows:
            if not str(r.get("doc_no", "")).strip():
                continue
            out.append(DocumentSummary(
                doc_no=str(r.get("doc_no", "")),
                doc_type=str(r.get("doc_type", "quotation")),
                doc_date=str(r.get("doc_date", "")),
                client_name=self._client_name_from_html(str(r.get("client_html", ""))),
                grand_total=_to_float(r.get("grand_total")),
                status=str(r.get("status", "")),
            ))
        # ใหม่สุดขึ้นก่อน
        out.sort(key=lambda d: d.doc_no, reverse=True)
        return out

    def get_document(self, doc_no: str) -> Optional[DocumentPayload]:
        ws = self._docs_ws()
        rows = ws.get_all_records()
        doc_row = next((r for r in rows if str(r.get("doc_no")) == doc_no), None)
        if not doc_row:
            return None
        doc = Document(
            doc_no=str(doc_row.get("doc_no", "")),
            doc_type=str(doc_row.get("doc_type", "quotation")),
            doc_date=str(doc_row.get("doc_date", "")),
            issuer_name=str(doc_row.get("issuer_name", "")),
            issuer_address=str(doc_row.get("issuer_address", "")),
            issuer_tax=str(doc_row.get("issuer_tax", "")),
            issuer_contact=str(doc_row.get("issuer_contact", "")),
            client_html=str(doc_row.get("client_html", "")),
            wht_rate=_to_float(doc_row.get("wht_rate")),
            subtotal=_to_float(doc_row.get("subtotal")),
            wht_amount=_to_float(doc_row.get("wht_amount")),
            grand_total=_to_float(doc_row.get("grand_total")),
            price_terms=str(doc_row.get("price_terms", "")),
            agreement=str(doc_row.get("agreement", "")),
            assurance=str(doc_row.get("assurance", "")),
            payment_info=str(doc_row.get("payment_info", "")),
            status=str(doc_row.get("status", "")),
        )
        items = self._items_for(doc_no)
        return DocumentPayload(document=doc, items=items)

    def _items_for(self, doc_no: str) -> List[Item]:
        ws = self._items_ws()
        rows = ws.get_all_records()
        items = [
            Item(
                seq=int(_to_float(r.get("seq")) or 0),
                item_name=str(r.get("item_name", "")),
                item_desc=str(r.get("item_desc", "")),
                price=_to_float(r.get("price")),
                qty=_to_float(r.get("qty")),
                amount=_to_float(r.get("amount")),
            )
            for r in rows if str(r.get("doc_no")) == doc_no
        ]
        items.sort(key=lambda x: x.seq)
        return items

    # ---------- write ----------
    def save_document(self, payload: DocumentPayload) -> str:
        """upsert เอกสาร 1 ใบ (แทนที่ items เดิมทั้งหมดของ doc_no นี้)"""
        doc = payload.document
        if not doc.doc_no.strip():
            raise SheetError("ไม่มีเลขที่เอกสาร (doc_no)")

        ws = self._docs_ws()
        now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row_values = [
            doc.doc_no, doc.doc_type, doc.doc_date, doc.issuer_name,
            doc.issuer_address, doc.issuer_tax, doc.issuer_contact,
            doc.client_html, doc.wht_rate, doc.subtotal, doc.wht_amount,
            doc.grand_total, doc.price_terms, doc.agreement, doc.assurance,
            doc.payment_info, doc.status, now,
        ]

        # หา row เดิมของ doc_no (คอลัมน์ A)
        col_a = ws.col_values(1)
        target = None
        for i, v in enumerate(col_a):
            if i == 0:
                continue  # header
            if v == doc.doc_no:
                target = i + 1  # 1-based
                break
        if target:
            ws.update([row_values], f"A{target}")
        else:
            ws.append_row(row_values, value_input_option="USER_ENTERED")

        self._replace_items(doc.doc_no, payload.items)
        return doc.doc_no

    def _replace_items(self, doc_no: str, items: List[Item]):
        ws = self._items_ws()
        col_a = ws.col_values(1)
        # เก็บ index แถวเดิมของ doc_no (จากล่างขึ้นบน เพื่อไม่ให้ index เลื่อน)
        to_delete = [i + 1 for i in range(1, len(col_a)) if col_a[i] == doc_no]
        for idx in sorted(to_delete, reverse=True):
            ws.delete_rows(idx)
        if items:
            new_rows = [
                [doc_no, it.seq, it.item_name, it.item_desc,
                 it.price, it.qty, it.amount]
                for it in items
            ]
            ws.append_rows(new_rows, value_input_option="USER_ENTERED")

    def delete_document(self, doc_no: str):
        ws = self._docs_ws()
        col_a = ws.col_values(1)
        for i in range(len(col_a) - 1, 0, -1):
            if col_a[i] == doc_no:
                ws.delete_rows(i + 1)
        self._replace_items(doc_no, [])

    # ---------- next number ----------
    def next_doc_no(self) -> str:
        """เลขถัดไป: '{ปีค.ศ.} {ลำดับ 4 หลัก}' อิงเลขล่าสุดของปีนี้"""
        year = _dt.datetime.now().year
        try:
            ws = self._docs_ws()
            nums = ws.col_values(1)[1:]
        except SheetError:
            nums = []
        max_seq = 0
        for n in nums:
            m = re.match(rf"^{year}\s+(\d+)$", str(n).strip())
            if m:
                max_seq = max(max_seq, int(m.group(1)))
        return f"{year} {max_seq + 1:04d}"


def _to_float(v) -> float:
    if v is None or v == "":
        return 0.0
    try:
        return float(str(v).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0.0
