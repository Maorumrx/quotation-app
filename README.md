# Quotation Manager

โปรแกรมจัดการ **ใบเสนอราคา / ใบแจ้งหนี้ / ใบเสร็จรับเงิน** — หน้าตาเดิมจาก HTML template
เพิ่มระบบ บันทึก/โหลด ลง **Google Sheets** เป็น database รันเป็น app บน Win/Mac

**Stack:** FastAPI + pywebview (native window) + gspread + Google Sheets

> ไม่อยากลง Python? ให้ **GitHub Actions build ให้** (ดูข้อ 3) เครื่องเราไม่ต้องแตะ Python เลย
> ไฟล์ `.exe`/`.app` ที่ได้มี Python ฝังในตัว ดับเบิลคลิกเปิดได้เลย

---

## 1. เตรียม Google Sheet + Service Account (ทำครั้งเดียว)

1. สร้าง Google Sheet เปล่า 1 ไฟล์ → ก็อป **Sheet ID** จาก URL
   `https://docs.google.com/spreadsheets/d/`**`<SHEET_ID>`**`/edit`
   (ไม่ต้องสร้างแท็บเอง โปรแกรมสร้าง `documents` + `items` ให้อัตโนมัติ)
2. [Google Cloud Console](https://console.cloud.google.com/) → สร้าง project
3. เปิด API 2 ตัว: **Google Sheets API** + **Google Drive API**
4. *IAM & Admin → Service Accounts* → สร้าง → *Keys → Add Key → JSON*
   → ได้ไฟล์มา เปลี่ยนชื่อเป็น **`credentials.json`**
5. เปิด `credentials.json` ดู `client_email` → เอา email นั้นไป **Share** Sheet ให้ (สิทธิ์ Editor)

## 2. วางไฟล์ตั้งค่า (บนเครื่องที่จะใช้งานจริง)

สร้างโฟลเดอร์ **`~/.quotation-manager/`** แล้ววาง 2 ไฟล์นี้ลงไป:

| ไฟล์ | ที่มา |
|------|-------|
| `config.json` | ก็อปจาก `config.example.json` แล้วใส่ `sheet_id` ของคุณ |
| `credentials.json` | ไฟล์ service account จากข้อ 1 |

> `~` = โฟลเดอร์ home — Windows: `C:\Users\<ชื่อ>\.quotation-manager\`  /  Mac: `/Users/<ชื่อ>/.quotation-manager/`
> ครั้งแรกที่เปิดโปรแกรม มันจะสร้างโฟลเดอร์นี้ + วาง `config.example.json` ให้เอง

---

## 3. Build ด้วย GitHub Actions (ไม่ต้องลง Python) ✅

1. push โปรเจกต์นี้ขึ้น GitHub repo ของคุณ
2. ไปแท็บ **Actions** → เลือก workflow **build** → กด **Run workflow**
   (หรือ push tag: `git tag v1.0.0 && git push --tags` → build อัตโนมัติ)
3. รอ ~3-5 นาที → เข้าไปใน run → หัวข้อ **Artifacts** ล่างสุด โหลดได้เลย:
   - `QuotationManager-Windows` → ข้างในมี `QuotationManager.exe`
   - `QuotationManager-macOS` → ข้างในมี `QuotationManager.app`

### เปิดครั้งแรก (ไฟล์ยังไม่ได้เซ็นชื่อ ระบบจะเตือน — ปกติ)
- **Windows:** ขึ้น "Windows protected your PC" → กด **More info → Run anyway**
- **macOS:** คลิกขวาที่ `.app` → **Open** → กด **Open** ซ้ำ (ครั้งเดียว ครั้งต่อไปเปิดปกติ)

## 4. รันตอน dev (ถ้าอยากแก้โค้ด)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |  Mac: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
จุดสีที่ toolbar: 🟢 = เชื่อม Sheet ได้ / 🔴 = ยังไม่พร้อม (hover ดูเหตุผล)

---

## โครงสร้าง Google Sheet

**`documents`** — 1 แถว = 1 เอกสาร
`doc_no | doc_type | doc_date | issuer_* | client_html | wht_rate | subtotal | wht_amount | grand_total | ... | updated_at`

**`items`** — 1 แถว = 1 รายการ (ผูกด้วย `doc_no`)
`doc_no | seq | item_name | item_desc | price | qty | amount`

→ ทำ Pivot สรุปรายได้รายเดือน / ยอด WHT ได้จากใน Sheet ตรงๆ

## Flow ใช้งาน
- **🆕 สร้างใหม่** → ดึงเลขถัดไปให้อัตโนมัติ
- **💾 บันทึกลง Sheet** → upsert ตาม `doc_no` (มีแล้วทับ, ยังไม่มีเพิ่มใหม่)
- **📁 เอกสารทั้งหมด** → คลิกใบเก่ามาแก้/ก็อป
- **🖨️ PDF** → พิมพ์/เซฟ PDF เหมือนเดิม

## ขยายต่อ
- ปุ่มลบเอกสาร: route `DELETE /api/documents/{doc_no}` พร้อมแล้ว เพิ่มปุ่มใน UI ได้เลย
- เลข running แยกตามประเภทเอกสาร: แก้ `next_doc_no()` ใน `backend/sheets.py`
