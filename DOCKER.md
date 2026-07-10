# รันด้วย Docker (สำหรับ dev / test)

Container นี้รัน **FastAPI server** เพื่อเทสผ่านเบราว์เซอร์
(หน้าต่าง native/pywebview รันใน Docker ไม่ได้ และไฟล์ `.exe`/`.app`
ต้อง build บน Windows/macOS หรือผ่าน GitHub Actions — ดู README)

## เริ่มใช้

```bash
docker compose up --build        # หรือ:  make docker-up
# เปิด http://127.0.0.1:8000
```

**ไม่ต้องตั้งค่าอะไรก่อนเลย** — เอกสารถูกเก็บเป็นไฟล์ JSON ในโฟลเดอร์ `./data/`
บนเครื่อง host (mount เข้า container) จะไม่หายเวลาลบ container

หยุด: `docker compose down` (หรือ `make docker-down`)

## หมายเหตุ

- เอกสารทั้งหมดอยู่ใน `./data/*.json` — เปิดอ่าน/แก้/สำรอง (ก็อปโฟลเดอร์) ได้ตรงๆ
- `data/` ถูก gitignore + dockerignore แล้ว — ข้อมูลไม่เข้า git และไม่เข้า image
- เปลี่ยนที่เก็บ: `QM_DATA_DIR=/path/to/data docker compose up`
- เปลี่ยนพอร์ต: `PORT=9000 docker compose up`
- โหมด live-reload ตอนแก้โค้ด: ปลด comment บล็อก dev ใน `docker-compose.yml`
