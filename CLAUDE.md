# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **Thai-language desktop app** for managing quotations / invoices / receipts
(ใบเสนอราคา / ใบแจ้งหนี้ / ใบเสร็จรับเงิน). It runs as a native window (pywebview)
wrapping a local FastAPI server, and uses a **Google Sheet as its database** (no SQL).
UI text, comments, and user-facing errors are Thai — keep that convention.

**Stack:** FastAPI + uvicorn · pywebview (native window) · gspread + Google Sheets ·
pydantic · PyInstaller (packaging). Frontend is a single static `frontend/index.html`.

## Commands

```bash
# Dev run (opens the native window)
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py

# Build a double-click binary for the CURRENT OS only
pip install pyinstaller
python build.py            # -> dist/QuotationManager.exe (Win) or .app (macOS)
```

- **No test suite, linter, or `package.json`** exists. There is nothing to `npm`/`pytest`.
- **CI builds only**, on git tag `v*` or manual dispatch (`.github/workflows/build.yml`);
  it builds Windows + macOS artifacts via PyInstaller. It does not run tests.

## Runtime config (not in the repo)

Config and secrets live in **`~/.quotation-manager/`**, never in the project tree
(`config.json` + `credentials.json` are gitignored). See `config.py`:
- `load_config()` reads `~/.quotation-manager/config.json`, falling back to next-to-binary.
  On first run with no config it drops a `config.example.json` there.
- `credentials_path()` resolves the service-account JSON: env `GSPREAD_CREDENTIALS`
  → `~/.quotation-manager/` → next-to-binary.
- `resource_path()` / `sys._MEIPASS` handle the PyInstaller-frozen vs. source-run split —
  use these helpers for any bundled asset path, don't hardcode.

Google setup (service account, sharing the Sheet with `client_email`, enabling
Sheets + Drive APIs) is documented in `README.md`.

## Architecture

**Startup (`app.py`):** grabs a free localhost port, runs uvicorn in a **daemon thread**
(with signal handlers disabled since it's off the main thread), waits for the port, then
opens a pywebview window pointed at `http://127.0.0.1:<port>`. The window closing ends the app.

**Server (`backend/server.py`):** FastAPI serving `frontend/index.html` at `/` plus a small REST API:
`GET /api/health`, `GET /api/documents` (list), `GET /api/documents/{doc_no}` (load),
`POST /api/documents` (upsert), `DELETE /api/documents/{doc_no}`, `GET /api/next-no`.
Sheet failures surface as HTTP 503 with a Thai message; the frontend shows a red/green
status dot from `/api/health`.

**Data layer (`backend/sheets.py`, `SheetDB`):** the whole "database" is two tabs in one
Google Sheet — **`documents`** (one row per document, column order = `DOC_COLUMNS`) and
**`items`** (one row per line item, keyed by `doc_no`, column order = `ITEM_COLUMNS`).
Key behaviors to preserve:
- **Lazy connection.** `_connect()` only runs on first Sheet access. The app opens and edits/prints
  fine with no credentials — only *saving* fails, loudly. Don't make startup depend on the Sheet.
- **`_ensure_tabs()` / `_ensure_header()`** auto-create tabs and rewrite the header row if it drifts,
  so **`DOC_COLUMNS` / `ITEM_COLUMNS` order is the schema** — changing/reordering them changes the
  sheet layout. Reads use `get_all_records()` (header row as keys), so a header/column mismatch
  silently corrupts reads. Keep model fields, these column lists, and the write `row_values` in sync.
- **Save = upsert + full item replace.** `save_document()` finds the row by `doc_no` in column A
  (updates in place or appends); `_replace_items()` deletes all existing item rows for that `doc_no`
  (bottom-up, so indices don't shift) then re-appends. Items are not diffed.
- `next_doc_no()` derives the next number as `"{year} {seq:04d}"` from the max sequence of the
  current year in column A.

**Models (`backend/models.py`):** pydantic shapes shared by API and sheet layer. Note `client_html`,
`issuer_*` rich rows, and `payment_info` are stored as **HTML strings** (the UI is contenteditable);
`_client_name_from_html()` strips tags to derive a plain client name for the list view.

**Frontend (`frontend/index.html`, single file):** a WYSIWYG print-style editor. Fields are
`[contenteditable]` elements tagged with `data-field="..."`; `data-html="1"` means the field's
`innerHTML` (not text) is the stored value. `getField`/`setField`/`collectDocument`/`applyDocument`
map between the DOM and the API payload. Totals (`recalc`), Thai baht text (`bahtText`), and row
add/delete/renumber are computed client-side. `doc_type` (quotation|invoice|receipt) is a document
field that swaps titles/labels via `setDocType`. Line-item table state is cached in `localStorage`
(`persistTable`). Printing uses the browser print dialog against print CSS in the same file.

## Conventions

- Keep Thai for UI copy, comments, and `SheetError` messages — they're shown to end users.
- The Google Sheet is the source of truth; there is no migration system. Any schema change is a
  coordinated edit across `models.py`, the `*_COLUMNS` lists, and the save `row_values`.
- Path handling must keep working both from source and PyInstaller-frozen — always go through
  `config.py`'s `app_dir` / `user_config_dir` / `resource_path`.

> Note: the repo-level `.claude/CLAUDE.md` (a "3D Co-op Game" ruleset) is unrelated to this project
> and does not apply here.
