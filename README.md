# Quotation Manager

โปรแกรมจัดการ **ใบเสนอราคา / ใบแจ้งหนี้ / ใบเสร็จรับเงิน** — หน้าตาเดิมจาก HTML template
เก็บข้อมูลเป็น **ไฟล์ JSON ในเครื่อง** (1 ไฟล์ต่อ 1 เอกสาร) รันเป็น app บน Win/Mac

**Stack:** FastAPI + pywebview (native window) — ไม่ต้องมีเน็ต ไม่ต้องตั้งค่าคลาวด์

> ไม่อยากลง Python? ให้ **GitHub Actions build ให้** (ดูข้อ 2) เครื่องเราไม่ต้องแตะ Python เลย
> ไฟล์ `.exe`/`.app` ที่ได้มี Python ฝังในตัว ดับเบิลคลิกเปิดได้เลย

---

## 1. ที่เก็บข้อมูล (ไม่ต้องตั้งค่าอะไรก็ใช้ได้)

เอกสารถูกเก็บเป็นไฟล์ JSON ในโฟลเดอร์ **`~/.quotation-manager/data/`** อัตโนมัติ
เปิดโปรแกรมแล้วเซฟได้เลย ไม่ต้องมี Google account / credentials ใดๆ

- `~` = โฟลเดอร์ home — Windows: `C:\Users\<ชื่อ>\.quotation-manager\data\` / Mac: `/Users/<ชื่อ>/.quotation-manager/data/`
- **สำรองข้อมูล** = ก็อปโฟลเดอร์ `data/` ไปเก็บ / **ย้ายเครื่อง** = ก็อปโฟลเดอร์ไปวางที่เครื่องใหม่
- **อยากได้คลาวด์/หลายเครื่อง** = ตั้ง `data_dir` ให้ชี้ไปโฟลเดอร์ที่ Google Drive / Dropbox / OneDrive ซิงก์อยู่ แล้วมันจะ sync ให้เอง (ดูด้านล่าง)

### เปลี่ยนที่เก็บ (ไม่บังคับ)
สร้างไฟล์ `~/.quotation-manager/config.json` (ก็อปจาก `config.example.json`):
```json
{ "data_dir": "~/Dropbox/quotation-data" }
```
หรือกำหนดผ่าน env `QM_DATA_DIR=/path/to/data` ตอนรันก็ได้

---

## 2. Build ด้วย GitHub Actions (ไม่ต้องลง Python) ✅

1. push โปรเจกต์นี้ขึ้น GitHub repo ของคุณ
2. ไปแท็บ **Actions** → เลือก workflow **build** → กด **Run workflow**
   (หรือ push tag: `git tag v1.0.0 && git push --tags` → build อัตโนมัติ)
3. รอ ~3-5 นาที → เข้าไปใน run → หัวข้อ **Artifacts** ล่างสุด โหลดได้เลย:
   - `QuotationManager-Windows` → ข้างในมี `QuotationManager.exe`
   - `QuotationManager-macOS` → ข้างในมี `QuotationManager.app`

### เปิดครั้งแรก (ไฟล์ยังไม่ได้เซ็นชื่อ ระบบจะเตือน — ปกติ)
- **Windows:** ขึ้น "Windows protected your PC" → กด **More info → Run anyway**
- **macOS:** คลิกขวาที่ `.app` → **Open** → กด **Open** ซ้ำ (ครั้งเดียว ครั้งต่อไปเปิดปกติ)

## 3. รันตอน dev (ถ้าอยากแก้โค้ด)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |  Mac: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
จุดสีที่ toolbar: 🟢 = บันทึกลงเครื่องได้ / 🔴 = เขียนโฟลเดอร์เก็บข้อมูลไม่ได้ (hover ดูเหตุผล)

> เทสในเบราว์เซอร์โดยไม่เปิดหน้าต่าง native: `make serve` แล้วเปิด http://127.0.0.1:8000
> รันด้วย Docker: ดู [DOCKER.md](DOCKER.md)

---

## รูปแบบไฟล์ข้อมูล

`~/.quotation-manager/data/2026 0001.json` — 1 ไฟล์ = 1 เอกสาร:
```json
{
  "document": { "doc_no": "2026 0001", "doc_type": "quotation", "client_html": "...", "grand_total": 21400, "...": "..." },
  "items": [ { "seq": 1, "item_name": "...", "price": 20000, "qty": 1, "amount": 20000 } ]
}
```
เปิดอ่าน/แก้ด้วย text editor ได้ตรงๆ

## Flow ใช้งาน
- **🆕 สร้างใหม่** → ดึงเลขถัดไปให้อัตโนมัติ (`{ปี} {ลำดับ 4 หลัก}`)
- **💾 บันทึก** → เขียนทับไฟล์ตาม `doc_no` (มีแล้วทับ, ยังไม่มีสร้างใหม่)
- **📁 เอกสารทั้งหมด** → คลิกใบเก่ามาแก้/ก็อป
- **🖨️ PDF** → พิมพ์/เซฟ PDF เหมือนเดิม

## ขยายต่อ
- เลข running แยกตามประเภทเอกสาร: แก้ `next_doc_no()` ใน `backend/store.py`
- อยากได้ที่เก็บแบบอื่น (เช่น SQLite): เขียนคลาสหน้าตาเหมือน `DocumentStore` มาสลับใน `backend/server.py`
