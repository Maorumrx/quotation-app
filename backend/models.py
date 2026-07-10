"""
backend/models.py
โครงข้อมูล (pydantic) ของเอกสาร 1 ใบ = document + items[]
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class Item(BaseModel):
    seq: int = 1
    item_name: str = ""
    item_desc: str = ""
    price: float = 0
    qty: float = 1
    amount: float = 0


class Document(BaseModel):
    doc_no: str = ""
    doc_type: str = "quotation"          # quotation | invoice | receipt
    doc_date: str = ""
    issuer_name: str = ""
    issuer_address: str = ""
    issuer_tax: str = ""
    issuer_contact: str = ""
    client_html: str = ""                # เก็บเป็น HTML เพราะมีชื่อ+ที่อยู่+เลขภาษี
    wht_rate: float = 3
    subtotal: float = 0
    wht_amount: float = 0
    grand_total: float = 0
    price_terms: str = ""
    agreement: str = ""
    assurance: str = ""
    payment_info: str = ""               # HTML
    status: str = ""


class DocumentPayload(BaseModel):
    """สิ่งที่ frontend ยิงมาตอนกด Save"""
    document: Document
    items: List[Item] = Field(default_factory=list)


class DocumentSummary(BaseModel):
    """แถวเดียวใน list เอกสาร (ไม่รวม items)"""
    doc_no: str
    doc_type: str
    doc_date: str
    client_name: str = ""
    grand_total: float = 0
    status: str = ""
