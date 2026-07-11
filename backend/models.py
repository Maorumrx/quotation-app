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
    doc_date_iso: str = ""               # วันที่จากปฏิทินแบบ ISO (YYYY-MM-DD) ไว้เปิดกลับมาแก้
    sign_left: str = ""                  # ลายเซ็นซ้าย (PNG data URL — วาดหรืออัปโหลด)
    sign_right: str = ""                 # ลายเซ็นขวา (PNG data URL)
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


class TaxRateBucket(BaseModel):
    """ยอดภาษีหัก ณ ที่จ่าย จัดกลุ่มตามอัตรา (เช่น 3%, 5%)"""
    rate: float = 0            # อัตรา % (เช่น 3)
    base: float = 0            # ฐานภาษี = มูลค่างานก่อนหักภาษี (subtotal รวม)
    wht: float = 0             # ภาษีที่ถูกหักไว้ (wht_amount รวม)
    count: int = 0             # จำนวนใบเสร็จในกลุ่มนี้


class TaxSummary(BaseModel):
    """สรุปภาษีรายปี (พ.ศ.) — คิดจากใบเสร็จรับเงินในปีนั้น"""
    year_be: int               # ปีภาษี พ.ศ.
    count: int = 0             # จำนวนใบเสร็จทั้งหมดในปีนั้น
    total_income: float = 0    # รายได้รวม (subtotal รวม = ก่อนหักภาษี)
    total_wht: float = 0       # ภาษีถูกหักรวม
    net_total: float = 0       # ยอดรับสุทธิรวม (grand_total รวม)
    by_rate: List[TaxRateBucket] = Field(default_factory=list)
