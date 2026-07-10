# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **Thai-language desktop app** for managing quotations / invoices / receipts
(ใบเสนอราคา / ใบแจ้งหนี้ / ใบเสร็จรับเงิน). It runs as a native window (pywebview)
wrapping a local FastAPI server, and stores each document as a **local JSON file**
(one file per document, no DB, no cloud). UI text, comments, and user-facing errors
are Thai — keep that convention.

**Stack:** FastAPI + uvicorn · pywebview (native window) · pydantic ·
PyInstaller (packaging). Frontend is a single static `frontend/index.html`.

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

Data and config live under **`~/.quotation-manager/`**, never in the project tree
(`config.json` + `data/` are gitignored). See `config.py`:
- `load_config()` reads an **optional** `~/.quotation-manager/config.json`, falling back to
  next-to-binary. No config file is fine — defaults apply.
- `data_dir(cfg)` resolves where documents are stored: env `QM_DATA_DIR` → `config.json`'s
  `data_dir` → default `~/.quotation-manager/data`. Point `data_dir` at a Drive/Dropbox-synced
  folder to get cloud/multi-device sync for free.
- `resource_path()` / `sys._MEIPASS` handle the PyInstaller-frozen vs. source-run split —
  use these helpers for any bundled asset path, don't hardcode.

## Architecture

**Startup (`app.py`):** grabs a free localhost port, runs uvicorn in a **daemon thread**
(with signal handlers disabled since it's off the main thread), waits for the port, then
opens a pywebview window pointed at `http://127.0.0.1:<port>`. The window closing ends the app.

**Server (`backend/server.py`):** FastAPI serving `frontend/index.html` at `/` plus a small REST API:
`GET /api/health` (`{ok, message?}`), `GET /api/documents` (list), `GET /api/documents/{doc_no}` (load),
`POST /api/documents` (upsert), `DELETE /api/documents/{doc_no}`, `GET /api/next-no`.
`StoreError` surfaces as HTTP 500 with a Thai message; the frontend shows a red/green
status dot from `/api/health`.

**Data layer (`backend/store.py`, `DocumentStore`):** each document is **one JSON file**
`data_dir/{doc_no}.json` holding `{"document": {...}, "items": [...]}` (a `DocumentPayload`).
Key behaviors to preserve:
- **Untrusted `doc_no`.** It comes from the client via the URL path, so `_safe_name()` strips
  path separators / `..` to prevent traversal before it's used as a filename — keep this.
- **App works with no data yet.** `_ensure_dir()` creates `data_dir` on demand; opening/editing/printing
  never depends on prior state. Only a genuinely unwritable dir makes `health()`/saves fail, loudly.
- **Save = atomic full overwrite.** `save_document()` writes to a `.tmp` file then `os.replace()`s it
  into place (crash-safe), storing the whole payload (items sorted by `seq`) plus an `_updated_at`
  stamp. Reads tolerate corrupt/foreign files by returning `None` and skipping them in lists.
- `next_doc_no()` derives `"{year} {seq:04d}"` from the max sequence among current-year docs.

**Models (`backend/models.py`):** pydantic shapes shared by API and store. Note `client_html`,
`issuer_*` rich rows, and `payment_info` are stored as **HTML strings** (the UI is contenteditable);
`store._client_name_from_html()` strips tags to derive a plain client name for the list view.
Extra keys on disk (e.g. `_updated_at`) are ignored on load (pydantic default).

**Frontend (`frontend/index.html`, single file):** a WYSIWYG print-style editor. Fields are
`[contenteditable]` elements tagged with `data-field="..."`; `data-html="1"` means the field's
`innerHTML` (not text) is the stored value. `getField`/`setField`/`collectDocument`/`applyDocument`
map between the DOM and the API payload. Totals (`recalc`), Thai baht text (`bahtText`), and row
add/delete/renumber are computed client-side. `doc_type` (quotation|invoice|receipt) is a document
field that swaps titles/labels via `setDocType`. Line-item table state is cached in `localStorage`
(`persistTable`). Printing uses the browser print dialog against print CSS in the same file.

## Conventions

- Keep Thai for UI copy, comments, and `StoreError` messages — they're shown to end users.
- The JSON files are the source of truth; there is no migration system. A model change in
  `models.py` just changes what future saves write — old files still load (missing fields take
  pydantic defaults, extra fields are ignored).
- To swap storage (e.g. SQLite), implement a class with the same 5 methods + `health()` as
  `DocumentStore` and wire it into `backend/server.py` — nothing else needs to change.
- Path handling must keep working both from source and PyInstaller-frozen — always go through
  `config.py`'s `app_dir` / `user_config_dir` / `resource_path`.

> Note: the repo-level `.claude/CLAUDE.md` (a "3D Co-op Game" ruleset) is unrelated to this project
> and does not apply here.
