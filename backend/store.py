"""
backend/store.py
ที่เก็บข้อมูล: ไฟล์ JSON 1 ไฟล์ต่อ 1 เอกสาร ในโฟลเดอร์ data_dir
  data_dir/{doc_no}.json  ->  { "document": {...}, "items": [...] }

ข้อดี: เป็น text เปิดอ่าน/แก้ได้, สำรอง = ก็อปโฟลเดอร์, ออฟไลน์, ไม่ต้องตั้งค่าคลาวด์
อยากได้คลาวด์: วาง data_dir ไว้ในโฟลเดอร์ที่ Google Drive/Dropbox ซิงก์ให้ ก็ sync อัตโนมัติ
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
from typing import List, Optional

from .models import Document, DocumentPayload, DocumentSummary


class StoreError(Exception):
    """error ที่อยากส่งข้อความไทยกลับไปให้ผู้ใช้เห็น"""


# ห้ามให้ doc_no จาก client กลายเป็น path (กัน ../ / \ ฯลฯ)
_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def _safe_name(doc_no: str) -> str:
    name = _UNSAFE.sub("_", doc_no or "").strip().strip(".")
    if not name or name in (".", ".."):
        raise StoreError("เลขที่เอกสารไม่ถูกต้อง")
    return name


def _client_name_from_html(html: str) -> str:
    """ดึงชื่อลูกค้าคร่าวๆ จาก client_html (เอาข้อความใน <b> ตัวแรก)"""
    if not html:
        return ""
    m = re.search(r"<b>(.*?)</b>", html, re.S)
    raw = m.group(1) if m else html
    return re.sub(r"<[^>]+>", "", raw).strip()


class DocumentStore:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    # ---------- paths / dir ----------
    def _ensure_dir(self):
        try:
            os.makedirs(self.data_dir, exist_ok=True)
        except OSError as e:  # noqa: BLE001
            raise StoreError(f"สร้างโฟลเดอร์เก็บข้อมูลไม่ได้: {self.data_dir} ({e})") from e

    def _path(self, doc_no: str) -> str:
        return os.path.join(self.data_dir, _safe_name(doc_no) + ".json")

    def health(self):
        """เช็คว่าเขียนโฟลเดอร์เก็บข้อมูลได้ไหม (โยน StoreError ถ้าไม่ได้)"""
        self._ensure_dir()
        if not os.access(self.data_dir, os.W_OK):
            raise StoreError(f"เขียนโฟลเดอร์เก็บข้อมูลไม่ได้: {self.data_dir}")

    # ---------- read ----------
    @staticmethod
    def _read(path: str) -> Optional[DocumentPayload]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return DocumentPayload(**raw)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return None

    def _iter_payloads(self):
        self._ensure_dir()
        for name in sorted(os.listdir(self.data_dir)):
            if not name.endswith(".json"):
                continue
            p = self._read(os.path.join(self.data_dir, name))
            if p and p.document.doc_no.strip():
                yield p

    def list_documents(self) -> List[DocumentSummary]:
        out: List[DocumentSummary] = []
        for p in self._iter_payloads():
            d = p.document
            out.append(DocumentSummary(
                doc_no=d.doc_no,
                doc_type=d.doc_type,
                doc_date=d.doc_date,
                client_name=_client_name_from_html(d.client_html),
                grand_total=d.grand_total,
                status=d.status,
            ))
        out.sort(key=lambda d: d.doc_no, reverse=True)  # ใหม่สุดขึ้นก่อน
        return out

    def get_document(self, doc_no: str) -> Optional[DocumentPayload]:
        path = self._path(doc_no)
        if not os.path.exists(path):
            return None
        return self._read(path)

    # ---------- write ----------
    def save_document(self, payload: DocumentPayload) -> str:
        doc = payload.document
        if not doc.doc_no.strip():
            raise StoreError("ไม่มีเลขที่เอกสาร (doc_no)")
        self._ensure_dir()
        payload.items.sort(key=lambda x: x.seq)
        data = payload.model_dump()
        data["_updated_at"] = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        path = self._path(doc.doc_no)
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)  # atomic: กันไฟล์พังถ้าเซฟค้างกลางคัน
        except OSError as e:  # noqa: BLE001
            raise StoreError(f"บันทึกไฟล์ไม่ได้: {e}") from e
        return doc.doc_no

    def delete_document(self, doc_no: str):
        path = self._path(doc_no)
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError as e:  # noqa: BLE001
            raise StoreError(f"ลบไฟล์ไม่ได้: {e}") from e

    def clear_all(self) -> dict:
        """ล้างเอกสารทั้งหมด: ย้ายไฟล์ .json ทุกใบไปโฟลเดอร์สำรอง (กู้คืนได้)
        เลขรันจะรีเซ็ตเองเพราะ next_doc_no อ่านเฉพาะ .json ที่อยู่ชั้นบนสุด
        (โฟลเดอร์ _backup_* ถูกข้าม). คืน {count, backup_dir}."""
        self._ensure_dir()
        names = [
            n for n in os.listdir(self.data_dir)
            if n.endswith(".json") and os.path.isfile(os.path.join(self.data_dir, n))
        ]
        if not names:
            return {"count": 0, "backup_dir": ""}
        stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = os.path.join(self.data_dir, f"_backup_{stamp}")
        try:
            os.makedirs(backup, exist_ok=True)
        except OSError as e:  # noqa: BLE001
            raise StoreError(f"ล้างข้อมูลไม่ได้: {e}") from e

        # ย้ายทีละไฟล์แบบ best-effort: ถ้าไฟล์ไหนติด (เช่นเปิดค้างบน Windows)
        # ก็ข้ามไปไฟล์อื่น แล้วค่อยรายงานรวม ไม่ทิ้งให้ค้างครึ่งๆ แบบเงียบๆ
        moved, failed = [], []
        for n in names:
            try:
                os.replace(os.path.join(self.data_dir, n),
                           os.path.join(backup, n))
                moved.append(n)
            except OSError:
                failed.append(n)
        if failed:
            raise StoreError(
                f"ย้ายได้ {len(moved)} ไฟล์ แต่ติด {len(failed)} ไฟล์ "
                f"(อาจเปิดไฟล์ค้างอยู่): {', '.join(failed[:5])}"
            )
        return {"count": len(moved), "backup_dir": backup}

    # ---------- tax summary ----------
    @staticmethod
    def _doc_be_year(doc: Document) -> Optional[int]:
        """หาปี พ.ศ. ของเอกสาร:
        1) จาก doc_date_iso (YYYY-MM-DD, ค.ศ.) -> +543
        2) ถ้าไม่มี ให้ดึงปี พ.ศ. 4 หลัก (25xx) จากข้อความ doc_date
        คืน None ถ้าหาไม่ได้ (เช่นวันที่ยังเป็น placeholder ___/___/____)
        """
        iso = (doc.doc_date_iso or "").strip()
        m = re.match(r"^(\d{4})-\d{2}-\d{2}$", iso)
        if m:
            return int(m.group(1)) + 543
        m = re.search(r"\b(25\d{2})\b", doc.doc_date or "")
        if m:
            return int(m.group(1))
        return None

    def tax_summary(self, year_be: int) -> dict:
        """สรุปภาษีรายปี (พ.ศ.) จาก 'ใบเสร็จรับเงิน' ในปีนั้น
        - ใช้ใบเสร็จเป็นเกณฑ์รับรู้รายได้ (รับเงินแล้ว) กันนับซ้ำกับใบแจ้งหนี้/ใบเสนอราคา
        - รายได้รวม = ผลรวม subtotal (มูลค่างานก่อนหักภาษี)
        - ภาษีหัก ณ ที่จ่าย แยกตามอัตรา = จัดกลุ่มตาม wht_rate
        """
        buckets: dict = {}   # rate -> {"base","wht","count"}
        count = 0
        total_income = total_wht = net_total = 0.0
        for p in self._iter_payloads():
            d = p.document
            if d.doc_type != "receipt":
                continue
            if self._doc_be_year(d) != year_be:
                continue
            count += 1
            total_income += d.subtotal
            total_wht += d.wht_amount
            net_total += d.grand_total
            key = round(d.wht_rate, 2)
            b = buckets.setdefault(key, {"base": 0.0, "wht": 0.0, "count": 0})
            b["base"] += d.subtotal
            b["wht"] += d.wht_amount
            b["count"] += 1
        by_rate = [
            {"rate": r, "base": v["base"], "wht": v["wht"], "count": v["count"]}
            for r, v in sorted(buckets.items())
        ]
        return {
            "year_be": year_be,
            "count": count,
            "total_income": total_income,
            "total_wht": total_wht,
            "net_total": net_total,
            "by_rate": by_rate,
        }

    # ---------- next number ----------
    def next_doc_no(self) -> str:
        """เลขถัดไป: '{ปีค.ศ.} {ลำดับ 4 หลัก}' อิงเลขล่าสุดของปีนี้"""
        year = _dt.datetime.now().year
        max_seq = 0
        for p in self._iter_payloads():
            m = re.match(rf"^{year}\s+(\d+)$", p.document.doc_no.strip())
            if m:
                max_seq = max(max_seq, int(m.group(1)))
        return f"{year} {max_seq + 1:04d}"
