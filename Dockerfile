# Quotation Manager — dev/test container
#
# หมายเหตุ: container นี้รัน "FastAPI server" อย่างเดียว (เทสผ่านเบราว์เซอร์)
# หน้าต่าง native (pywebview) รันใน container ไม่ได้ เพราะไม่มีจอ/GUI backend
# ไฟล์ .exe/.app ตัวจริงต้อง build บน Windows/macOS หรือผ่าน GitHub Actions

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# รันด้วย non-root user
RUN useradd --create-home --uid 1000 app
WORKDIR /app

# ลง deps ก่อน (cache layer ดีขึ้นเวลาแก้โค้ด)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ก็อปโค้ดเข้ามา (secret ไม่เข้า image — ดู .dockerignore, ให้ mount ตอน run แทน)
COPY . .
RUN chown -R app:app /app

USER app
EXPOSE 8000

# serve FastAPI + หน้าจอ ที่ 0.0.0.0 เพื่อให้ host เข้าถึงผ่าน port map ได้
CMD ["sh", "-c", "python -m uvicorn backend.server:app --host 0.0.0.0 --port ${PORT}"]
