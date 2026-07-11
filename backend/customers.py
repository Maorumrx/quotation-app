"""
backend/customers.py
สมุดลูกค้า: เก็บรายชื่อบริษัท/ลูกค้าไว้ใช้ซ้ำ (เลือกแล้วเติมอัตโนมัติ ไม่ต้องพิมพ์ทุกใบ)

ไฟล์เดียว: data_dir/customers.json  ->  { "customers": [ {id,name,address,tax_id,phone,_updated_at}, ... ] }
ปริมาณลูกค้าของฟรีแลนซ์ไม่เยอะ ใช้ไฟล์เดียวพอ เขียนแบบ atomic (tmp -> os.replace) เหมือน DocumentStore
"""
from __future__ import annotations

import datetime as _dt
import json
import os
from typing import List

from .models import Customer
from .store import StoreError  # ใช้ error ที่มีข้อความไทยร่วมกัน

_FILE = "customers.json"


class CustomerStore:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    def _path(self) -> str:
        return os.path.join(self.data_dir, _FILE)

    def _ensure_dir(self):
        try:
            os.makedirs(self.data_dir, exist_ok=True)
        except OSError as e:  # noqa: BLE001
            raise StoreError(f"สร้างโฟลเดอร์เก็บข้อมูลไม่ได้: {self.data_dir} ({e})") from e

    # ---------- read ----------
    def _load_raw(self, strict: bool = False) -> list:
        """อ่าน list ดิบจากไฟล์
        - ไฟล์ยังไม่มี = คืน [] (ปกติ ยังไม่เคยบันทึกลูกค้า)
        - ไฟล์มีแต่พัง: strict=False คืน [] (ใช้ตอนอ่านมาโชว์), strict=True โยน StoreError
          (ใช้ตอนจะ 'เขียนทับ' — กันเคสไฟล์เดียวพังแล้ว save ทับ = ลูกค้าหายหมด)
        """
        if not os.path.exists(self._path()):
            return []
        try:
            with open(self._path(), "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError) as e:  # noqa: BLE001
            if strict:
                raise StoreError(
                    "ไฟล์สมุดลูกค้า (customers.json) เสียหาย อ่านไม่ได้ — "
                    "หยุดบันทึกเพื่อกันข้อมูลลูกค้าเดิมหาย โปรดแก้/กู้ไฟล์ก่อน"
                ) from e
            return []
        items = data.get("customers") if isinstance(data, dict) else data
        return [c for c in items if isinstance(c, dict)] if isinstance(items, list) else []

    def list_customers(self) -> List[Customer]:
        # ข้าม record ที่ผิดรูป (field ผิดชนิด) แทนที่จะ 500 ทั้ง list — ให้สมุดยังใช้ได้
        out: List[Customer] = []
        for c in self._load_raw():
            try:
                out.append(Customer(**c))
            except (TypeError, ValueError):  # รวม pydantic ValidationError
                continue
        out.sort(key=lambda c: c.name.lower())
        return out

    # ---------- write ----------
    def _write_raw(self, items: list):
        self._ensure_dir()
        path = self._path()
        tmp = path + ".tmp"
        try:
            # เก็บสำเนา .bak ของไฟล์เดิม (best-effort) เผื่อกู้คืน ก่อนเขียนทับ
            if os.path.exists(path):
                try:
                    with open(path, "rb") as src, open(path + ".bak", "wb") as dst:
                        dst.write(src.read())
                except OSError:
                    pass
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"customers": items}, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)  # atomic กันไฟล์พังถ้าเซฟค้างกลางคัน
        except OSError as e:  # noqa: BLE001
            raise StoreError(f"บันทึกสมุดลูกค้าไม่ได้: {e}") from e

    @staticmethod
    def _next_id(items: list) -> str:
        mx = 0
        for c in items:
            cid = str(c.get("id") or "")
            if cid.startswith("c") and cid[1:].isdigit():
                mx = max(mx, int(cid[1:]))
        return f"c{mx + 1}"

    def save_customer(self, cust: Customer) -> Customer:
        """upsert: หา record เดิมด้วย id -> เลขภาษี -> ชื่อ (กันสร้างซ้ำ) แล้วเขียนทับ/เพิ่มใหม่"""
        name = (cust.name or "").strip()
        if not name:
            raise StoreError("ยังไม่มีชื่อลูกค้า")
        items = self._load_raw(strict=True)  # กันเขียนทับไฟล์ที่พัง = ลูกค้าเดิมหายหมด
        tax = (cust.tax_id or "").strip()

        idx = None
        if cust.id:
            idx = next((i for i, c in enumerate(items) if str(c.get("id")) == cust.id), None)
        if idx is None and tax:
            idx = next((i for i, c in enumerate(items)
                        if str(c.get("tax_id") or "").strip() == tax), None)
        if idx is None:  # ไม่มีเลขภาษี -> จับคู่ด้วยชื่อ (เฉพาะรายที่ยังไม่มีเลขภาษี)
            idx = next((i for i, c in enumerate(items)
                        if str(c.get("name") or "").strip() == name
                        and not str(c.get("tax_id") or "").strip()), None)

        rec = {
            "name": name,
            "address": (cust.address or "").strip(),
            "tax_id": tax,
            "phone": (cust.phone or "").strip(),
            "_updated_at": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        if idx is None:
            rec["id"] = cust.id or self._next_id(items)
            items.append(rec)
        else:
            rec["id"] = items[idx].get("id") or cust.id or self._next_id(items)
            items[idx] = rec
        self._write_raw(items)
        return Customer(**rec)

    def delete_customer(self, cust_id: str):
        items = self._load_raw(strict=True)  # กันเขียนทับไฟล์ที่พัง
        kept = [c for c in items if str(c.get("id")) != str(cust_id)]
        if len(kept) != len(items):
            self._write_raw(kept)
