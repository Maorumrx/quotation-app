# Quotation Manager — dev / test / build helper
# ใช้: make setup แล้วก็ make serve (เทสในเบราว์เซอร์) หรือ make run / make build
#
# หมายเหตุ OS:
#   - make run   = หน้าต่าง native (pywebview) ต้องมีจอ/GUI backend (รันบนเครื่องจริง Win/Mac)
#   - make build = ได้ไฟล์ของ OS ที่รันเท่านั้น (.exe ต้อง build บน Windows / .app บน macOS)
#   - make serve = FastAPI อย่างเดียว เปิดเทสในเบราว์เซอร์ ใช้ได้ทุกที่รวมถึง Linux/headless

VENV := .venv
PY   := $(VENV)/bin/python
PIP  := $(VENV)/bin/pip
PORT ?= 8000

.PHONY: help setup serve run build clean docker-build docker-up docker-down

help:            ## แสดงคำสั่งทั้งหมด
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	 | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-8s\033[0m %s\n", $$1, $$2}'

setup:           ## สร้าง venv + ลง dependencies
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

serve:           ## รัน FastAPI อย่างเดียว → เทสที่ http://127.0.0.1:$(PORT) (headless ได้)
	$(PY) -m uvicorn backend.server:app --host 127.0.0.1 --port $(PORT) --reload

run:             ## รันแอปจริงแบบหน้าต่าง native (ต้องมีจอ/GUI)
	$(PY) app.py

build:           ## แพ็กเป็น .exe/.app ของ OS ที่รันอยู่ (ต้องมี pyinstaller)
	$(PIP) install pyinstaller
	$(PY) build.py

clean:           ## ลบ build artifacts
	rm -rf build dist *.spec

docker-build:    ## build docker image
	docker compose build

docker-up:       ## รันใน docker → http://127.0.0.1:8000
	docker compose up

docker-down:     ## หยุด container
	docker compose down
